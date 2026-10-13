"""Execute fresh payloads against an existing profiled PE in memory; never emit an EXE."""
import argparse, hashlib, json, struct, sys, zlib
from pathlib import Path
from PIL import Image
import test_inventory_ui as inv
import test_cart_ui as cart
from unicorn.x86_const import UC_X86_REG_ECX

ROOT=Path(__file__).resolve().parents[1]

def overlay(m, feature, old):
    name=feature[:-2];meta=json.loads((ROOT/f'Inputs/{feature}/runtime.json').read_text())
    blob=(ROOT/f'Inputs/{feature}/runtime.bin').read_bytes()
    _,version,size,count,api,api_size,client,crc=struct.unpack_from('<8I',blob)
    assert version==1 and client==20250716 and zlib.crc32(blob[32:])==crc
    source=ROOT/f'Scripts/Runtime/{feature}/runtime.cpp'
    assert meta['source_sha256']==hashlib.sha256(source.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    code=bytearray(blob[32+count*4:]);assert len(code)==size
    address=m.alloc(size)
    for offset in struct.unpack_from('<'+'I'*count,blob,32):
        struct.pack_into('<I',code,offset,struct.unpack_from('<I',code,offset)[0]+address)
    m.u.mem_write(address,bytes(code))
    exports={k:address+v for k,v in meta['exports'].items()}
    is_inv=feature=='InventoryUI';prefix=20 if is_inv else 12;oldpaths=36 if is_inv else 6
    m.u.mem_write(address+api,bytes(m.u.mem_read(old['api'],prefix+oldpaths*4)))
    extras=['battlepassui/Cursor_Hover.bmp'] if is_inv else ['inventoryui/search.png','battlepassui/Cursor_Hover.bmp']
    for i,path in enumerate(extras):
        ptr=m.alloc(len(path)+1);m.u.mem_write(ptr,path.replace('/',chr(92)).encode()+b'\0');m.w(address+api+prefix+(oldpaths+i)*4,ptr)
    m.w(address+api+api_size-4,0xA74410)
    fields=inv.FIELDS if is_inv else cart.FIELDS
    keys=['api','state','create','destroy','process','draw','down','up']
    mapped={'api':name+'Api','state':name+'State'}
    for key in fields[2:]:
        match=[x for x in exports if x.lower().startswith(('@'+name+key+'@').lower()) or x.lower().startswith(('_'+name+key+'@').lower())]
        # Historical record labels use the abbreviated tooltip anchor name.
        if key=='anchor':match=['@InventoryTooltipAnchor@16']
        assert len(match)==1,(key,match)
        mapped[key]=match[0]
    result={key:exports[value] for key,value in mapped.items()}
    result['cursor']=exports['@'+name+'CursorDraw@8']
    table=0x103D460 if is_inv else 0x103D538
    routes={0:'destroy',15:'create',19:'process',20:'draw',25:'down',27:'drag',28:'move',31:'up',32:'right',35:'wheel',37:'event'}
    if is_inv:routes.update({10:'drop',26:'double'})
    for slot,key in routes.items():m.w(table+slot*4,result[key])
    edit=m.r(result['api']+4)
    m.w(edit+20*4,result['editdraw']);m.w(edit+37*4,result['editevent'])
    def branch(at,target,opcode):m.u.mem_write(at,bytes([opcode])+struct.pack('<i',target-at-5))
    if is_inv:
        branch(0x939E30,result['select'],0xE9);branch(0x94D4E1,result['anchor'],0xE8)
    else:
        # Preserve original selector call sites while updating their new target.
        for section in m.pe.sections:
            if not section.Characteristics&0x20000000:continue
            data=section.get_data();start=m.base+section.VirtualAddress
            for i in range(len(data)-5):
                if data[i]==0xE8 and start+i+5+struct.unpack_from('<i',data,i+1)[0]==old['select']:
                    branch(start+i,result['select'],0xE8)
    return result

def install_overlay():
    for module,feature in [(inv,'InventoryUI'),(cart,'CartUI')]:
        original=module.contract
        module.contract=lambda m,original=original,feature=feature:overlay(m,feature,original(m))

def visual_and_cursor(m,is_inv,output):
    w=m.obj;m.inventory([]);m.rebuild();m.w(w+0x28,1)
    def frame():
        m.rebuild();width,height=m.r(w+0x14),m.r(w+0x18)
        return Image.frombytes('RGBA',(width,height),bytes(m.u.mem_read(m.r(m.r(w+0x24)+0x18),width*height*4)),'raw','BGRA')
    first=frame();x=52 if is_inv else 69;right=244 if is_inv else 224
    asset=Image.open(ROOT/'Assets/StorageInventoryUI/inventoryui/search.png').convert('RGBA')
    # All frame edges and the dropdown retain the complete original pixels.
    assert first.crop((x,28,x+3,46)).tobytes()==asset.crop((35,11,38,29)).tobytes()
    assert first.crop((right,28,right+18,46)).tobytes()==asset.crop((190,11,208,29)).tobytes()
    e=m.state(4);assert m.r(e+0x20)==31 and m.r(e+0x18)==12
    assert m.r(e+0x1C)>x and m.r(e+0x1C)+m.r(e+0x14)<=right
    m.w(0x955980,1024);m.w(0x95598B,1024)
    m.invoke(m.c['event'],w,(0,14,7,344,360,0));second=frame()
    assert first.crop((0,0,17,17)).tobytes()==second.crop((0,0,17,17)).tobytes()
    assert first.crop((56,66,88,86)).tobytes()==second.crop((56,66,88,86)).tobytes()
    second.save(output/('inventory-fixed.png' if is_inv else 'cart-fixed.png'))
    fallback=[];paint=[];freed=[];surfaces=[]
    m.stub(0xA74410,lambda:(fallback.append(m.u.reg_read(UC_X86_REG_ECX)),m.ret(0)))
    hit=[w];m.stub(0xA336D0,lambda:m.ret(8,hit[0]))
    m.w(0x12515F8,m.alloc(256))
    delete=m.alloc(16);m.stub(delete,lambda:(freed.append(m.u.reg_read(UC_X86_REG_ECX)),m.ret(4)))
    def surface():
        width,height,_=m.args(3);p=m.alloc(44);vt=m.alloc(4);m.w(vt,delete);m.w(p,vt)
        m.w(p+4,width);m.w(p+8,height);m.w(p+0x18,m.alloc(width*height*4));surfaces.append(p);m.ret(0,p)
    m.stub(0x560E50,surface)
    m.stub(0x53EA90,lambda:(paint.append(tuple(m.args(5))),m.ret(20)))
    def cursor(x,y,hand=True):
        m.w(0x11E40D4,x+m.r(w+0x1C));m.w(0x11E40D8,y+m.r(w+0x20))
        before=len(paint);stock=len(fallback);m.invoke(m.c['cursor'],m.mode,())
        assert (len(paint)>before)==hand,(is_inv,x,y,hand)
        assert (len(fallback)>stock)!=hand
    points=[(335,7),(337,353),(317 if is_inv else 297,35)]
    if is_inv:points += [(315,7)]+[(12,y) for y in (30,63,95,127,159,181,205)]
    for xy in points:cursor(*xy)
    cursor(150,100,False);cursor(80,35,False)
    m.click(317 if is_inv else 297,35)
    for y in range(52,250,24):cursor(85,y)
    m.click(317 if is_inv else 297,35)
    hit[0]=m.alloc(128);cursor(335,7,False);hit[0]=w
    m.w(0x131F4E8+0x19C,w);m.w(m.c['state']+32,25 if is_inv else 6)
    cursor(450,400);m.w(m.c['state']+32,0);cursor(335,7,False)
    m.w(0x131F4E8+0x19C,0)
    surface=surfaces[0];raw=bytes(m.u.mem_read(m.r(surface+0x18),26*22*4))
    bmp=Image.open(ROOT/'Assets/StorageInventoryUI/battlepassui/Cursor_Hover.bmp').convert('RGB')
    expected=b''.join(struct.pack('<I',0 if rgb==(255,0,255) else 0xFF000000|rgb[0]<<16|rgb[1]<<8|rgb[2]) for rgb in bmp.get_flattened_data())
    assert raw==expected and len(surfaces)==1,'Cursor pixel/transparency/cache mismatch'
    m.w(w+0x28,0);cursor(335,7,False);m.w(w+0x28,1)
    if is_inv:
        m.w(w+0x18,17);cursor(335,7);cursor(12,30,False)
    m.invoke(m.c['destroy'],w,(1,));assert freed==[surface];cursor(335,7,False)
    print('PASS fresh '+('Inventory' if is_inv else 'Cart')+' payload: frame, fixed circles, cursor targets/capture/occlusion/pixels/lifecycle')

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('exe',type=Path);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True);install_overlay()
    for module,is_inv in [(inv,True),(cart,False)]:
        cls=module.InventoryMachine if is_inv else module.CartMachine
        visual_and_cursor(cls(args.exe),is_inv,args.output)
        sys.argv=[sys.argv[0],str(args.exe),'--output',str(args.output/('inventory' if is_inv else 'cart'))]
        module.main()
    print('PASS all fresh payload tests; reference PE read only, no EXE emitted')

if __name__=='__main__':main()
