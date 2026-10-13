"""Execute the fresh Storage payload in an existing PE's memory; never write an EXE."""
import argparse, hashlib, json, struct, sys, zlib, base64, io
from pathlib import Path
from PIL import Image
from unicorn.x86_const import UC_X86_REG_EAX, UC_X86_REG_ECX
import test_storage_ui as storage

ROOT=Path(__file__).resolve().parents[1]

def overlay(m, old):
    blob=(ROOT/'Inputs/StorageUI/runtime.bin').read_bytes()
    meta=json.loads((ROOT/'Inputs/StorageUI/runtime.json').read_text())
    magic,version,size,count,api,api_size,client,crc=struct.unpack_from('<8I',blob)
    assert (magic,version,api_size,client)==(0x49555353,1,152,20250716)
    assert zlib.crc32(blob[32:])==crc
    for key,path in [('source_sha256','Scripts/Runtime/StorageUI/runtime.cpp'),('cursor_header_sha256','Scripts/Runtime/InventoryCartCursor.h')]:
        assert meta[key]==hashlib.sha256((ROOT/path).read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    code=bytearray(blob[32+count*4:]);assert len(code)==size;address=m.alloc(size)
    for off in struct.unpack_from('<'+'I'*count,blob,32):
        struct.pack_into('<I',code,off,struct.unpack_from('<I',code,off)[0]+address)
    m.u.mem_write(address,bytes(code));exports={k:address+v for k,v in meta['exports'].items()}
    m.u.mem_write(address+api,bytes(m.u.mem_read(old['api'],124)))
    paths=['storageui/bg_.png','battlepassui/Cursor_Hover.bmp','btn_resize.bmp','inventory/icon_num.bmp','inventory/item_drop_lock_off.bmp','inventoryui/selected_bg.png']
    for i,path in enumerate(paths):
        raw=path.replace('/',chr(92)).encode()+b'\0';ptr=m.alloc(len(raw));m.u.mem_write(ptr,raw);m.w(address+api+24+(25+i)*4,ptr)
    m.w(address+api+148,0xA74410)
    result={'api':exports['StorageApi'],'state':exports['StorageState']}
    for key in [*storage.FIELDS[2:],'editdraw','cursordraw','drop','tooltipanchor']:
        matched=[x for x in exports if x.lower().startswith(('@storage'+key+'@').lower()) or x.lower().startswith(('_storage'+key+'@').lower())]
        if key=='build':matched=['_StorageBuildView@0']
        assert len(matched)==1,(key,matched)
        result[key]=exports[matched[0]]
    table=m.r(result['api']+4);edit=m.r(result['api']+8)
    for slot,key in {10:'drop',0:'destroy',15:'create',19:'process',20:'draw',25:'down',27:'drag',28:'move',31:'up',32:'right',35:'wheel',37:'event'}.items():m.w(table+slot*4,result[key])
    m.w(edit+20*4,result['editdraw']);m.w(edit+37*4,result['editevent'])
    for site,key in [(0xA3A694,'construct'),(0x94AEDA,'select'),(0x94D28F,'select'),(0x94F239,'select'),(0x94D2E1,'tooltipanchor')]:
        m.u.mem_write(site,b'\xE8'+struct.pack('<i',result[key]-site-5))
    return result

def revision(exe,output,reference=None):
    m=storage.StorageMachine(exe,native_create=True);w=m.obj;s=m.c['state'];m.action_boundaries()
    # Read original item art used by the approved preview; no source image edits.
    if reference and reference.exists():
        assets=json.loads(reference.read_text());m.real_icons[501]=Image.open(io.BytesIO(base64.b64decode(assets['red_potion']['src'].split(',')[1]))).convert('RGBA')
    m.rows([]);first=m.draw()
    asset=Image.open(ROOT/'Assets/StorageInventoryUI/storageui/search.png').convert('RGB')
    assert first.crop((84,28,257,46)).tobytes()==asset.crop((51,11,224,29)).tobytes(),'full search art'
    for state,file in enumerate(['null','down','up']):
        m.w(s+16,state);im=m.draw();art=Image.open(ROOT/f'Assets/StorageInventoryUI/storageui/refine_order_{file}.png').convert('RGBA')
        # Check every fully opaque source pixel: transparent pixels reveal the footer.
        for y in range(9):
            for x in range(81):
                if art.getpixel((x,y))[3]==255:assert im.getpixel((208+x,401+y))==art.getpixel((x,y))[:3]
    m.w(s+16,0);m.click(25,405);before=m.draw()
    for xy in [(298,60),(298,80),(298,370)]:m.invoke(m.c['hit'],0,xy);assert m.u.reg_read(UC_X86_REG_EAX)==0
    # Height grows in whole rows, including diagonal drags; width stays fixed.
    m.invoke(m.c['down'],w,(305,438));m.invoke(m.c['drag'],w,(450,566));m.invoke(m.c['up'],w,(450,566))
    assert (m.r(w+20),m.r(w+24))==(312,573)
    after=m.draw(output/'storage-taller.png')
    assert before.crop((57,57,281,89)).tobytes()==after.crop((57,57,281,89)).tobytes(),'shadow pixels scaled'
    m.rows([(i+1,501,0,1,0) for i in range(100)]);m.draw();m.invoke(m.c['hit'],0,(298,80));assert m.u.reg_read(UC_X86_REG_EAX)==7
    m.search('absent');m.draw();m.invoke(m.c['hit'],0,(298,80));assert m.u.reg_read(UC_X86_REG_EAX)==0
    m.search('');m.rows([(i+1,501,0,1,0) for i in range(7)]);m.draw()
    assert [(x,y) for x,y,item in m.native_items]==[(61+i*32,61) for i in range(7)],'item canvas centers'
    # Rapid custom tab down/drag/up and mismatched releases never invoke the
    # native drag/save handler or any close/transaction mode message.
    native_up=[];m.stub(0x880BB0,lambda:(native_up.append(1),m.ret(8)))
    for i in range(160):
        x,y=16,39+(i%11)*30
        m.invoke(m.c['down'],w,(x,y));m.invoke(m.c['drag'],w,(x+8,y+4))
        m.invoke(m.c['up'],w,(x,y if i%3 else 39+((i+1)%11)*30))
    assert not native_up and not m.moves and not m.closed and not m.actions
    assert m.r(0x131F4E8+0x19c)==0
    # A queued message from a hidden legacy close child cannot close this skin.
    child=m.window(10,10,0,w);m.w(child+0x28,0)
    m.invoke(m.c['event'],w,(child,6,0xC9,0,0,0));assert not m.closed
    m.click(247,35);m.invoke(m.c['hit'],0,(100,51));assert m.u.reg_read(UC_X86_REG_EAX)==30
    m.click(100,51);assert m.r(s+8)==0
    # Lock suppresses transfer starts and pending native deposits, but allows descriptions.
    m.click(120,m.r(w+24)-16);m.draw();m.keys.add(0x10)
    action_count=len(m.actions);m.invoke(m.c['down'],w,(70,60));m.invoke(m.c['up'],w,(70,60));m.invoke(m.c['right'],w,(70,60));assert len(m.actions)==action_count
    m.keys.clear();m.invoke(m.c['right'],w,(70,60));assert m.actions[-1][0]=='describe'
    item=m.alloc(64);m.w(item,1);m.w(item+0x10,1)
    m.invoke(m.c['drop'],w,(70,60,item));assert m.actions[-1]==('mode',(0x12,0,0,0,0))
    m.invoke(m.c['event'],w,(0,0x26,0,0,0,0));assert m.actions[-1]==('mode',(0x12,0,0,0,0))
    m.click(120,m.r(w+24)-16);m.draw();m.invoke(m.c['down'],w,(70,60));assert m.actions[-1][0]=='drag';m.invoke(m.c['up'],w,(70,60))
    # Original drop still owns one-item submission, quantity prompts and cart deposits.
    m.stub(0xA47B90,lambda:m.ret(4,0));m.stub(0xC85FE0,lambda:m.ret(0,0))
    count=len(m.events);m.invoke(m.c['drop'],w,(70,60,item));assert m.events[count][1]==0x26
    prompt=m.alloc(256);vt=m.alloc(256);event=m.alloc(16);m.w(prompt,vt);m.w(vt+0x94,event);m.w(0x131F6D4,prompt);prompts=[]
    m.stub(event,lambda:(prompts.append(tuple(m.args(6))),m.ret(24)));m.stub(0xA4BF30,lambda:m.ret(8,prompt))
    m.w(item+0x10,12);m.invoke(m.c['drop'],w,(70,60,item));assert prompts[-1]==(0,0xD,7,0,0,0)
    m.w(item,9);m.invoke(m.c['drop'],w,(70,60,item));assert len(prompts)==2
    # Native item description and tooltip retain the full CItem, including refine/cards.
    m.invoke(m.c['move'],w,(70,60));x=m.alloc(4);y=m.alloc(4);m.invoke(m.c['tooltipanchor'],w,(x,y));assert (m.r(x),m.r(y))==(57+m.r(w+0x1c),41+m.r(w+0x20))
    m.draw(output/'storage-revised-block.png')
    m.click(25,m.r(w+24)-46);m.draw(output/'storage-revised-list.png')
    # Exactly one native close request, even if the acknowledgement is delayed.
    y=m.r(w+24)-15;m.click(270,y);m.click(270,y);assert m.closed==[w]
    m.invoke(m.c['destroy'],w,(1,));assert m.r(s)==0
    print('PASS exact search/refine pixels, centered cells, conditional scroll, vertical resize, rapid tab input, queued child close isolation, close debounce')

def cursor(exe):
    m=storage.StorageMachine(exe);w=m.obj;m.w(w+0x28,1);m.action_boundaries();fallback=[];paint=[];surfaces=[];freed=[]
    m.stub(0xA74410,lambda:(fallback.append(m.u.reg_read(UC_X86_REG_ECX)),m.ret(0)))
    hit=[w];m.stub(0xA336D0,lambda:m.ret(8,hit[0]));m.w(0x12515F8,m.alloc(256))
    delete=m.alloc(16);m.stub(delete,lambda:(freed.append(m.u.reg_read(UC_X86_REG_ECX)),m.ret(4)))
    def surface():
        width,height,_=m.args(3);p=m.alloc(44);vt=m.alloc(4);m.w(vt,delete);m.w(p,vt)
        m.w(p+4,width);m.w(p+8,height);m.w(p+0x18,m.alloc(width*height*4));surfaces.append(p);m.ret(0,p)
    m.stub(0x560E50,surface);m.stub(0x53EA90,lambda:(paint.append(tuple(m.args(5))),m.ret(20)))
    def point(x,y,hand=True):
        m.w(0x11E40D4,x+m.r(w+0x1c));m.w(0x11E40D8,y+m.r(w+0x20));before=len(paint);stock=len(fallback)
        m.invoke(m.c['cursordraw'],m.mode);assert (len(paint)>before)==hand,(x,y,hand);assert (len(fallback)>stock)!=hand
    for xy in [(302,7),(270,429),(120,429),(230,405),(25,405),(305,439),(247,35),*[(16,39+i*30) for i in range(11)]]:point(*xy)
    m.click(120,429);point(120,429);m.click(247,35)
    for i in range(11):point(100,51+i*22)
    m.click(247,35);point(140,100,False);point(90,35,False)
    hit[0]=m.alloc(128);point(302,7,False);hit[0]=w
    m.w(0x131F4E8+0x19c,w);m.w(m.c['state']+32,23);point(500,600)
    m.w(m.c['state']+32,0);point(302,7,False);m.w(0x131F4E8+0x19c,0)
    bmp=Image.open(ROOT/'Assets/StorageInventoryUI/battlepassui/Cursor_Hover.bmp').convert('RGB')
    expected=b''.join(struct.pack('<I',0 if rgb==(255,0,255) else 0xff000000|rgb[0]<<16|rgb[1]<<8|rgb[2]) for rgb in bmp.get_flattened_data())
    assert bytes(m.u.mem_read(m.r(surfaces[0]+0x18),26*22*4))==expected and len(surfaces)==1
    m.invoke(m.c['destroy'],w,(1,));assert freed==surfaces;point(302,7,False)
    print('PASS Storage hand targets, exact bitmap pixels, capture, occlusion, resize outside bounds, cursor lifetime')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('exe',type=Path);ap.add_argument('--output',required=True,type=Path);ap.add_argument('--preview-art',type=Path,help='Optional original item artwork JSON for visual test fixtures');a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    old=storage.contract;storage.contract=lambda m:overlay(m,old(m))
    revision(a.exe,a.output,a.preview_art);cursor(a.exe)
    sys.argv=[sys.argv[0],str(a.exe),'--output',str(a.output)];storage.main()
    print('PASS fresh Storage payload; existing client read only, no EXE generated')

if __name__=='__main__':main()
