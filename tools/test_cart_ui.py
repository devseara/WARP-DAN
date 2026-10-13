"""Execute CartUI x86, stock cart transfers/drag/description and view identity.

Asset decoding, allocation, window creation, item-copy/string ownership and game
mode dispatch are boundaries. No server connection or gameplay mutation occurs.
"""
import argparse
from pathlib import Path
import struct,io
from PIL import Image,ImageDraw,ImageFont
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EBP
from test_modern_chat_ui import Machine,pack
from test_gacha_ui import GachaMachine
from test_inventory_ui import native_art
from test_inventory_cart_filters import check_dropdown

ROOT=Path(__file__).resolve().parents[1]
FIELDS='api state create destroy process draw down up right move drag wheel event select editdraw editevent hit matches rebuild slot'.split()
def contract(m):
    data=m.pe.get_memory_mapped_image();tag=data.find(b'CartUI.v1\0');assert tag>=0
    record=data.find(pack(m.base+tag));assert record>=0
    return {name:m.r(m.base+record+4+i*4) for i,name in enumerate(FIELDS)}

class CartMachine(Machine):
    def setsize(self,obj,w,h):
        Machine.setsize(self,obj,w,h)
        if not hasattr(self,'surface_vtable'):
            self.surface_vtable=self.alloc(16);destroy=self.alloc(16);self.w(self.surface_vtable,destroy);self.stub(destroy,lambda:self.ret(4))
        self.w(self.r(obj+0x24),self.surface_vtable)
    invoke=GachaMachine.invoke
    def __init__(self,exe):
        super().__init__(exe,ROOT/'Assets/StorageInventoryUI/cartui');self.c=contract(self)
        self.missing=set();self.slots={};self.names={};self.keys=set();self.actions=[];self.icons=[];self.copies=[];self.pet_eggs=set();self.pet_gear=set();self.costumes=set()
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0x817DA0,lambda:self.ret(0,self.u.reg_read(UC_X86_REG_ECX)))
        self.stub(0xA1B780,self.addchild)
        self.stub(0x941B80,self.stockcreate)
        self.stub(0x5A8A20,lambda:self.ret(0))
        self.stub(0x8210A0,self.edittext)
        self.stub(0xA7E780,self.iteminfo)
        self.w(0x159C088,self.alloc(256))
        self.stub(0xD8EBE0,lambda:self.ret(4,int(self.args(1)[0] in self.pet_eggs)))
        self.stub(0xD98320,lambda:self.ret(4,0x123400|int(self.args(1)[0] in self.pet_gear)))
        self.stub(0x5B72D0,self.copyitem)
        self.stub(0x6A1A90,self.emptyitem)
        self.stub(0x4F08F0,lambda:self.ret(0))
        self.stub(0xA4B750,lambda:(self.w(0x131F4E8+0x19C,self.args(1)[0]),self.ret(4)))
        self.stub(0x880BB0,lambda:(self.w(0x131F4E8+0x19C,0),self.ret(8)))
        self.stub(0x880E00,lambda:self.ret(8))
        self.stub(0x8711A0,self.icon)
        self.stub(0xA1D260,self.sprite)
        self.stub(self.r(self.c['api']+8),self.fit)
        self.keyproc=self.alloc(16);self.stub(self.keyproc,lambda:self.ret(4,0x8000 if self.args(1)[0] in self.keys else 0))
        for entry in self.pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if imp.name==b'GetAsyncKeyState':self.w(imp.address,self.keyproc)
        self.mode=self.alloc(0x800);self.modevt=self.alloc(256);self.dispatch=self.alloc(16)
        self.w(self.mode,self.modevt);self.w(self.modevt+0x18,self.dispatch)
        self.stub(self.dispatch,lambda:(self.actions.append(('mode',tuple(self.args(5)))),self.ret(20)))
        self.stub(0xA75340,lambda:self.ret(0,self.mode));self.stub(0x5D98A0,lambda:self.ret(0,0))
        self.stub(0xD5BF70,self.sessioncopy);self.stub(0x6A25F0,lambda:self.ret(4))
        self.stub(0xC938E0,self.native_drag);self.stub(0xA33100,lambda:self.ret(0,0))
        self.desc=self.alloc(256);self.descvt=self.alloc(256);self.descevent=self.alloc(16)
        self.w(self.desc,self.descvt);self.w(self.descvt+0x94,self.descevent)
        self.stub(self.descevent,self.describe);self.stub(0xA39340,lambda:self.ret(4,self.desc))
        self.stub(0x9369F0,lambda:self.ret(4,self.u.reg_read(UC_X86_REG_ECX)))
        self.closed=[];self.stub(0xA2E770,lambda:(self.closed.append(self.args(1)[0]),self.ret(4)))
        self.stub(0xA47B90,lambda:self.ret(4,0))
        self.stub(0xC85FE0,lambda:self.ret(0,0))
        self.stub(0x950780,lambda:self.ret(24,0))
        self.font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',11)
        self.obj=self.window(280,208,0x103D538);self.query=self.alloc(256)
        self.inventory([(2,501,8,0,'Red Potion'),(3,1201,1,4,'Knife'),(4,1201,1,4,'Knife'),(5,4001,1,6,'Poring Card'),(6,909,99,3,'Jellopy')])
        self.w(0x15FB2D4,5);self.w(0x15FB2D8,100);self.w(0x15FB2DC,130);self.w(0x15FB2E0,8000)
        self.invoke(self.c['create'],self.obj,(280,208))
    def addchild(self):
        self.w(self.args(1)[0]+0x10,self.u.reg_read(UC_X86_REG_ECX));self.ret(4)
    def stockcreate(self):
        w=self.u.reg_read(UC_X86_REG_ECX)
        for off in [0xBC,0xC0,0xF4,0xF8]:
            child=self.window(20,20,0x102DD44,w);self.w(w+off,child)
        self.w(w+0xE0,7);self.w(w+0xDC,6);self.ret(8)
    def load_texture(self,name):
        if name in self.missing:return 0
        if name.endswith('.bmp') and (data:=native_art(name)):
            if name not in self.textures:
                im=Image.open(io.BytesIO(data)).convert('RGBA');tex=self.alloc(0x130);raw=im.tobytes('raw','BGRA');pixels=self.alloc(len(raw));self.u.mem_write(pixels,raw)
                self.w(tex+0x114,im.width);self.w(tex+0x118,im.height);self.w(tex+0x11C,pixels);self.textures[name]=tex;self.asset_pixels[name]=list(struct.unpack('<'+'I'*(im.width*im.height),raw))
            return self.textures[name]
        old=self.assets
        if name.startswith('cls_'):self.assets=ROOT/'Assets/StorageInventoryUI/genericsui'
        elif name in ('selected_bg.png','search.png'):self.assets=ROOT/'Assets/StorageInventoryUI/inventoryui'
        try:
            if getattr(self,'native_fallback',False) and not (self.assets/name).exists():
                tex=self.alloc(0x120);self.w(tex+0x114,16);self.w(tex+0x118,16);self.w(tex+0x11C,self.alloc(1024));return tex
            return super().load_texture(name)
        finally:self.assets=old
    def edittext(self):self.ret(0,self.query)
    def string(self,obj,offset,value):
        data=value.encode()+b'\0';ptr=obj+offset
        if len(data)>16:ptr=self.alloc(len(data));self.w(obj+offset,ptr);self.w(obj+offset+20,len(data))
        else:self.w(obj+offset+20,15)
        self.u.mem_write(ptr,data);self.w(obj+offset+16,len(data)-1)
    def inventory(self,rows):
        self.slots={};self.names={};head=self.alloc(12);previous=head
        for row in rows:
            index,id,quantity,type,name=row[:5];refine=row[5] if len(row)>5 else 0;favorite=row[6] if len(row)>6 else 0;identified=row[7] if len(row)>7 else 1
            node=self.alloc(0x110);p=node+8;self.w(previous,node);self.w(node+4,previous);self.w(p,type);self.w(p+4,index);self.w(p+0x10,quantity);self.w(p+0x60,refine)
            self.u.mem_write(p+0x74,bytes([favorite]));self.u.mem_write(p+0x5C,bytes([identified]));self.string(p,0x2C,str(id))
            self.slots[index]=p;self.names[id]=name;previous=node
        self.w(previous,head);self.w(head+4,previous);self.w(0x15FA3C0+0x1720,head);self.w(0x15FA3C0+0x1724,len(rows))
    def iteminfo(self):
        id=self.r(self.args(1)[0]);node=self.alloc(0x100);self.string(node,4,'Unidentified item');self.string(node,0x40,self.names.get(id,'Unknown'));self.w(node+0x84,int(id in self.costumes));self.ret(4,node)
    def copyitem(self):
        target=self.u.reg_read(UC_X86_REG_ECX);source=self.args(1)[0];self.copies.append(source);self.u.mem_write(target,bytes(self.u.mem_read(source,248)));self.ret(4,target)
    def emptyitem(self):
        target=self.u.reg_read(UC_X86_REG_ECX);self.u.mem_write(target,bytes(248));self.ret(4,target)
    def sessioncopy(self):
        out,index=self.args(2);self.u.mem_write(out,bytes(self.u.mem_read(self.slots[index],248)));self.ret(8,out)
    def native_drag(self):
        kind,item,amount,unknown=self.args(4);self.actions.append(('drag',(kind,self.r(item+4),amount,unknown)));self.ret(16)
    def describe(self):
        args=self.args(6);self.actions.append(('describe',bytes(self.u.mem_read(args[2],248))));self.ret(24)
    def fit(self):
        obj,ptr,x,y,width,color=self.args(6);pix,w,h=self.pixels(obj);text=self.cstr(ptr);self.texts.append((text,x,y,obj))
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA');rgb=(color&255,(color>>8)&255,(color>>16)&255);ImageDraw.Draw(im).text((x,y),text,font=self.font,fill=rgb+(255,));self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(24)
    def sprite(self):
        x,y,tex,flag=self.args(4);name=next(n for n,t in self.textures.items() if t==tex);self.images.append((name,x,y,self.u.reg_read(UC_X86_REG_ECX)));self.ret(16)
    def icon(self):
        x,y,item,_,_=self.args(5);self.icons.append((x,y,item));obj=self.u.reg_read(UC_X86_REG_ECX);pix,w,h=self.pixels(obj)
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA');draw=ImageDraw.Draw(im);draw.ellipse((x+6,y+4,x+17,y+18),fill=(173,93,91,255),outline=(75,54,35,255));draw.text((x+14,y+15),str(self.r(item+0x10)),font=self.font,fill=(40,40,40,255));self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(20)
    def state(self,o):return self.r(self.c['state']+o)
    def rebuild(self):self.invoke(self.c['rebuild'],0);self.invoke(self.c['draw'],self.obj)
    def search(self,text):self.u.mem_write(self.query,text.encode()+b'\0');self.invoke(self.c['process'],self.obj);self.rebuild()
    def click(self,x,y):self.invoke(self.c['down'],self.obj,(x,y));self.invoke(self.c['up'],self.obj,(x,y))
    def preview(self,path):
        self.texts=[];self.icons=[];self.invoke(self.c['draw'],self.obj);pix,w,h=self.pixels(self.obj);Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA').convert('RGB').save(path)
    def selected(self,x,y):
        out=self.alloc(248);self.invoke(self.c['select'],self.obj,(out,x,y));return bytes(self.u.mem_read(out,248))


def factory_test(exe):
    """Run stock cart factory/constructor and Create dispatch, not a remap."""
    m=CartMachine(exe);m.native_fallback=True
    for addr in [0xA39340,0xA1CB70,0x941B80,0x817DA0,0xA1B780]:m.u.hook_del(m._machine_stubs[addr])
    def surface():
        w,h,_=m.args(3);obj=m.alloc(0x100);m.setsize(obj,w,h);m.ret(0,m.r(obj+0x24))
    m.stub(0x560E50,surface)
    m.stub(0xDBBC7F,lambda:m.ret(0))
    def localize():
        out=m.args(1)[0];m.string(out,0,'');m.ret(0,out)
    m.stub(0x64D510,localize)
    def assign():
        target=m.u.reg_read(UC_X86_REG_ECX);ptr,n=m.args(2);data=bytes(m.u.mem_read(ptr,n))+b'\0';buf=target if n<16 else m.alloc(n+1)
        if n>=16:m.w(target,buf)
        m.u.mem_write(buf,data);m.w(target+16,n);m.w(target+20,15 if n<16 else n);m.ret(8,target)
    m.stub(0x4F1940,assign)
    def measure():
        out,source,_=m.args(3);m.u.mem_write(out,bytes(m.u.mem_read(source,24)));m.ret(12,out)
    m.stub(0xA24EE0,measure)
    m.stub(0xA21940,lambda:m.ret(20,len(m.cstr(m.args(5)[0]))*6))
    def memory(fill=False):
        dest,src,n=m.args(3);m.u.mem_write(dest,bytes([src&255])*n if fill else bytes(m.u.mem_read(src,n)));m.ret(0,dest)
    for iat,fill in [(0xFC1740,False),(0xFC1760,False),(0xFC1744,True)]:
        target=m.alloc(16);m.stub(target,lambda fill=fill:memory(fill));m.w(iat,target)
    m.stub(0x7A84A0,lambda:m.ret(4,0))
    m.stub(0x7A85A0,lambda:m.ret(4,0)) # Screen-window adjacency bookkeeping.
    for addr in [0xA2D220,0xA2D240,0xA4CCF0,0xA39130]:m.stub(addr,lambda:m.ret(4))
    m.stub(0xA47B90,lambda:m.ret(4,0))
    head=m.alloc(0x20);node=m.alloc(0x20)
    for off in [0,4,8]:m.w(head+off,node);m.w(node+off,head)
    m.u.mem_write(head+13,b'\1');m.w(node+16,0x28);m.w(0x131F4E8+8,head);m.w(0x131F4E8+12,1)
    head=m.alloc(12);m.w(head,head);m.w(head+4,head);m.w(0x131F4E8+0x17C,head)
    m.inventory([]);m.w(0x131F6BC,1);m.stub(0xC3F510,lambda:m.ret(8,1)) # Loaded actor has Pushcart skill.
    msg=m.alloc(32);m.u.mem_write(msg,b'Cart\0');m.stub(0xA9ED30,lambda:m.ret(0,msg))
    m.stub(0x529850,lambda:(m.u.mem_write(m.args(2)[0],b'Cart\0'),m.ret(0,4)))
    edit_vt=m.r(m.c['api']+4)
    try:m.invoke(0xA39340,0x131F4E8,(0x28,))
    except Exception:
        fp=m.u.reg_read(UC_X86_REG_EBP)
        for _ in range(12):
            if fp<0x30000000 or fp>=0x30010000:break
            print('FRAME',hex(fp),hex(m.r(fp+4)));fp=m.r(fp)
        raise
    m.obj=m.u.reg_read(UC_X86_REG_EAX);assert m.obj==m.state(0) and m.state(8)==1
    head=m.r(m.obj+0x50);node=m.r(head);seen=[]
    while node!=head:
        child=m.r(node+8);seen.append(child);assert m.r(child+0x28)==int(child==m.state(4)),(hex(child),m.r(child+0x28));node=m.r(node)
    assert len(seen)>=5 and m.state(4) in seen
    assert (m.r(m.obj+20),m.r(m.obj+24))==(280,296)
    assert (m.r(m.state(4)+20),m.r(m.state(4)+24))==(152,12)
    return m


def selection_geometry_test(exe,output):
    m=CartMachine(exe);m.w(m.c['state']+24,58);m.w(m.c['state']+28,60)
    m.preview(output/'cart-selection.png');pixels,w,h=m.pixels(m.obj)
    def pixel(x,y):return m.r(pixels+(y*w+x)*4)
    def rgba(v):r,g,b,a=v;return a<<24|r<<16|g<<8|b
    art=Image.open(ROOT/'Assets/StorageInventoryUI/inventoryui/selected_bg.png').convert('RGBA')
    for y in range(4,28):assert pixel(56,58+y)==pixel(87,58+y)==rgba(art.getpixel((0,y)))
    for x in range(4,28):
        assert pixel(56+x,58)==rgba(art.getpixel((x,0)))
        assert pixel(56+x,89)==rgba(art.getpixel((x,31)))
    shadow=Image.open(ROOT/'Assets/StorageInventoryUI/cartui/cart_bg.png').convert('RGBA')
    assert pixel(59,75)==rgba(shadow.getpixel((60,73)))
    for n,(x,y,_) in enumerate(m.icons):assert (x+12,y+12)==(72+n%6*32,75+n//6*32)
    assert ('icon_weight.bmp',101,h-16,m.obj) in m.images
    assert ('btn_resize.bmp',w-15,h-15,m.obj) in m.images
    assert not any(t[0].startswith('Wt ') for t in m.texts)
    # A wider grid must change row/column hit arithmetic and native item addresses together.
    m.inventory([(i+2,501,1,0,'Red Potion') for i in range(80)])
    m.w(0x955980,640);m.w(0x95598B,480);m.invoke(m.c['event'],m.obj,(0,14,7,344,328,0));m.rebuild()
    assert struct.unpack_from('<I',m.selected(58+7*32,60),4)[0]==9
    assert struct.unpack_from('<I',m.selected(58,92),4)[0]==10
    m.preview(output/'cart-wide-grid.png');assert len(m.icons)==56

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('exe',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    m=CartMachine(args.exe);s=m.c['state'];assert m.state(8)==1 and m.state(20)==5
    assert struct.unpack_from('<I',m.selected(57,59),4)[0]==0,'creation selected an undrawn item'
    m.invoke(m.c['draw'],m.obj)
    before={i:bytes(m.u.mem_read(a,248)) for i,a in m.slots.items()}
    assert bytes(m.u.mem_read(0x939900,10))==bytes.fromhex('55 8B EC 6A FF 68 CE 24 EC 00'),'shared selector modified'
    assert m.r(0x103D538+10*4)==0x938A50 and m.r(0x103D538+26*4)==0x5A8680,'native drop/double changed'
    for address in [0x94B4BA,0x94DF7F,0x94FAD9]:
        assert bytes(m.u.mem_read(address,1))==b'\xe8' and (address+5+struct.unpack('<i',m.u.mem_read(address+1,4))[0])==m.c['select']
    assert m.selected(57,59)==before[2]
    for x,y in [(10,80),(50,40),(55,59),(56,57),(248,59),(57,186),(200,200)]:assert struct.unpack_from('<I',m.selected(x,y),4)[0]==0
    m.invoke(m.c['down'],m.obj,(58,60));assert m.actions[-1]==('drag',(9,2,8,0xffffffff)),m.actions
    m.invoke(m.c['right'],m.obj,(90,60));assert m.actions[-1]==('describe',before[3]),m.actions
    m.keys={18};m.w(0x131F6BC,1);m.u.mem_write(m.mode+0x5CE,b'\1');m.invoke(m.c['right'],m.obj,(58,60));assert m.actions[-1]==('mode',(0x4D,2,8,0,0)),m.actions
    m.w(0x131F770,1);m.u.mem_write(m.mode+0x5CE,b'\1');m.invoke(m.c['right'],m.obj,(90,60));assert m.actions[-1]==('mode',(0x4F,3,1,0,0)),m.actions
    m.keys={16};m.invoke(m.c['right'],m.obj,(122,60));assert m.actions[-1]==('mode',(0x14F,4,1,0,0)),m.actions
    m.keys=set();m.w(0x131F770,0)
    for kind,event in [(1,0x4C),(6,0x4E)]:
        m.w(m.mode+0x308,kind);m.w(m.mode+0x30C,29);m.w(m.mode+0x318,7)
        m.invoke(m.c['event'],m.obj,(0,0x26,0,0,0,0));assert m.actions[-2:]==[('mode',(event,29,7,0,0)),('mode',(0x12,0,0,0,0))]
    drop=m.alloc(248);m.w(drop,1);m.w(drop+0x10,1);m.w(m.mode+0x308,1);m.w(m.mode+0x318,1)
    m.invoke(0x938A50,m.obj,(58,60,drop));assert m.actions[-2:]==[('mode',(0x4C,29,1,0,0)),('mode',(0x12,0,0,0,0))]
    m.search('kNi');assert m.state(20)==2 and m.selected(58,60)==before[3] and m.selected(90,60)==before[4]
    m.u.mem_write(m.slots[3]+0x1C,pack(4001));n=len(m.actions);m.invoke(m.c['down'],m.obj,(58,60));assert len(m.actions)==n,'stale instance draggable'
    assert struct.unpack_from('<I',m.selected(58,60),4)[0]==0
    m.rebuild();assert struct.unpack_from('<I',m.selected(58,60),0x1C)[0]==4001
    m.w(m.slots[3]+0x10,0);assert struct.unpack_from('<I',m.selected(58,60),4)[0]==0
    m.search('');m.click(233,35);assert m.state(36)==1 and struct.unpack_from('<I',m.selected(58,60),4)[0]==0
    m.preview(args.output/'cart-menu.png');m.click(90,52+4*24);m.invoke(m.c['draw'],m.obj);assert m.state(12)==4 and m.state(20)==1 and m.selected(58,60)==before[5]
    m.click(10,30);assert m.state(12)==0;m.search('absent');assert m.state(20)==0;m.preview(args.output/'cart-empty.png')
    m.search('');m.click(80,35);assert m.r(0x131F4E8+0x1A0)==m.state(4)
    m.invoke(m.c['editevent'],m.state(4),(0,0,0,0,0,0));assert m.r(0x131F4E8+0x1A0)==0
    m.inventory([(i+2,501,1,0,'Red Potion') for i in range(80)]);m.rebuild();m.preview(args.output/'cart-grid.png');assert len(m.icons)==36 and [p for x,y,p in m.icons]==[m.slots[i+2] for i in range(36)]
    m.invoke(m.c['wheel'],m.obj,(0xFFFFFF88,));assert m.state(16)==3
    actions=len(m.actions);m.invoke(m.c['down'],m.obj,(58,60));assert len(m.actions)==actions and struct.unpack_from('<I',m.selected(58,60),4)[0]==0,'scroll selected an undrawn item'
    m.invoke(m.c['draw'],m.obj);assert struct.unpack_from('<I',m.selected(58,60),4)[0]==20
    m.invoke(m.c['down'],m.obj,(267,60));m.invoke(m.c['drag'],m.obj,(267,249));assert m.state(16)==8
    m.invoke(m.c['up'],m.obj,(267,249));assert m.r(0x131F4E8+0x19C)==0
    m.inventory([(2,501,1,0,'Red Potion')]);m.rebuild();assert m.state(16)==0
    m.w(0x955980,640);m.w(0x95598B,480)
    m.invoke(m.c['down'],m.obj,(265,293));assert m.state(32)==6
    m.invoke(m.c['up'],m.obj,(265,293))
    m.invoke(m.c['down'],m.obj,(277,281));assert m.state(32)==6
    m.invoke(m.c['drag'],m.obj,(341,313));assert (m.r(m.obj+0x14),m.r(m.obj+0x18))==(344,328)
    assert struct.unpack_from('<I',m.selected(58,60),4)[0]==0, 'Resize exposed an undrawn item'
    m.invoke(m.c['up'],m.obj,(341,313));assert m.r(0x131F4E8+0x19C)==0
    m.rebuild();assert m.selected(58,60)==bytes(m.u.mem_read(m.slots[2],248))
    m.preview(args.output/'cart-resized.png')
    m.invoke(m.c['event'],m.obj,(0,14,7,1000,1000,0));assert (m.r(m.obj+0x14),m.r(m.obj+0x18))==(640,480)
    m.invoke(m.c['event'],m.obj,(0,14,7,280,296,0));m.rebuild()
    m.click(270,7);assert m.closed==[0x28]
    m.w(0x131F4E8+0x1A0,m.state(4));m.w(0x131F4E8+0x19C,m.obj);m.invoke(m.c['destroy'],m.obj,(1,));assert m.state(8)==0 and m.state(0)==0 and m.r(0x131F4E8+0x1A0)==0 and m.r(0x131F4E8+0x19C)==0
    m.invoke(m.c['create'],m.obj,(280,208));assert m.state(8)==1 and m.state(12)==0 and m.state(16)==0
    m.missing.add('cart_bg.png');m.invoke(m.c['destroy'],m.obj,(1,));m.invoke(m.c['create'],m.obj,(280,208));assert m.state(8)==0
    fallback=[];m.stub(0x948610,lambda:(fallback.append('draw'),m.ret(0)));m.invoke(m.c['draw'],m.obj);assert fallback==['draw']
    check_dropdown(CartMachine(args.exe),False,args.output)
    selection_geometry_test(args.exe,args.output)
    native=factory_test(args.exe)
    native.u.hook_del(native._machine_stubs.pop(0x9369F0))
    native.w(0x131F4E8+0x1A0,native.state(4));native.w(0x131F4E8+0x19C,native.obj)
    native.invoke(native.c['destroy'],native.obj,(1,));assert native.state(8)==0 and native.r(0x131F4E8+0x1A0)==0 and native.r(0x131F4E8+0x19C)==0
    print('PASS: CartUI native factory/create/owned children/editor/destructor, x86 exact-slot search/dropdown, stock drag/ALT/SHIFT/description/drop transfer, stale instance rejection, 36 cells, nine category filters, centered art/full selection/weight/grip, scrolling and resizing, editor focus, close/reopen and stock missing-asset fallback')

if __name__=='__main__':main()
