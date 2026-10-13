"""Execute InventoryUI x86, stock use/drag/description callbacks and view identity.

Asset decoding, allocation, font/localization, item-copy/string ownership and game
mode dispatch are boundaries. The lifecycle suite executes the stock factory,
constructor, OnCreate, child-list creation, native editor and destructor.
No server connection or gameplay mutation occurs.
"""
import argparse
from pathlib import Path
import struct,io
from PIL import Image,ImageDraw,ImageFont
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_ECX,UC_X86_REG_EBP
from test_modern_chat_ui import Machine,pack
from test_gacha_ui import GachaMachine
from dual_weapon_formats.grf_reader import GrfFile
from test_inventory_cart_filters import check_dropdown

ROOT=Path(__file__).resolve().parents[1]
FIELDS='api state create destroy process draw down up double right move drag wheel event select editdraw editevent hit matches rebuild slot drop anchor'.split()
NATIVE_ART={}
def native_art(name):
    if name=="Cursor_Hover.bmp":return (ROOT/"Assets/StorageInventoryUI/battlepassui"/name).read_bytes()
    if not NATIVE_ART:
        game=Path('D:/AAARAGNAROK/Banquet of Heroes/Eitr Origin')
        g=GrfFile(str(game/'maindata.grf'))
        for k in g.entries:
            if '/grade_enchant/grade_icon' in k or '/inventory/' in k or k.endswith('/btn_resize.bmp'):
                NATIVE_ART[k.rsplit('/',1)[-1]]=g.read(k)
        g.close()
    return NATIVE_ART.get(name)
def contract(m):
    data=m.pe.get_memory_mapped_image();tag=data.find(b'InventoryUI.v1\0');assert tag>=0
    record=data.find(pack(m.base+tag));assert record>=0
    return {name:m.r(m.base+record+4+i*4) for i,name in enumerate(FIELDS)}

class InventoryMachine(Machine):
    invoke=GachaMachine.invoke
    def __init__(self,exe):
        super().__init__(exe,ROOT/'Assets/StorageInventoryUI/inventoryui');self.c=contract(self)
        self.missing=set();self.slots={};self.names={};self.keys=set();self.actions=[];self.icons=[];self.copies=[];self.pet_eggs=set();self.pet_gear=set();self.costumes=set();self.pet_lookups=[]
        # MSVC cookie validation preserves EAX, including native sort return values.
        self.stub(0xDBBBD4,lambda:self.ret(0,self.u.reg_read(UC_X86_REG_EAX)))
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0xDBBEAE,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0xDBBC7F,lambda:self.ret(0))
        self.stub(0x817DA0,lambda:self.ret(0,self.u.reg_read(UC_X86_REG_ECX)))
        self.stub(0xA1B780,self.addchild)
        self.stub(0x82DAC0,lambda:self.ret(12,1))
        self.stub(0x93F100,self.stockcreate)
        self.stub(0x94E520,lambda:self.ret(0))
        self.stub(0x8210A0,self.edittext)
        self.stub(0xA7E780,self.iteminfo)
        self.w(0x159C088,self.alloc(256))
        self.stub(0xD8EBE0,lambda:(self.pet_lookups.append(('egg',self.args(1)[0])),self.ret(4,int(self.args(1)[0] in self.pet_eggs))))
        self.stub(0xD98320,lambda:(self.pet_lookups.append(('accessory',self.args(1)[0])),self.ret(4,0x123400|int(self.args(1)[0] in self.pet_gear))))
        self.stub(0x5B72D0,self.copyitem)
        self.stub(0x6A1A90,self.emptyitem)
        self.stub(0x4F08F0,lambda:self.ret(0))
        self.stub(0xA4B750,lambda:(self.w(0x131F4E8+0x19C,self.args(1)[0]),self.ret(4)))
        self.stub(0x880BB0,lambda:(self.w(0x131F4E8+0x19C,0),self.ret(8)))
        self.stub(0x880E00,lambda:self.ret(8))
        self.stub(0x8711A0,self.icon)
        self.stub(0xA1D260,self.sprite)
        self.stub(0x872B30,lambda:(self.actions.append(('equipped',tuple(self.args(2)))),self.ret(8)))
        self.stub(0xD9AA70,lambda:self.ret(0,0));self.stub(0xD9A960,lambda:self.ret(0,0))
        self.stub(0xD5ACB0,self.session_at)
        self.stub(self.r(self.c['api']+8),self.fit)
        self.keyproc=self.alloc(16);self.stub(self.keyproc,lambda:self.ret(4,0x8000 if self.args(1)[0] in self.keys else 0))
        self.w(self.r(self.c['api']+16),self.keyproc)
        for entry in self.pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if imp.name==b'GetAsyncKeyState':self.w(imp.address,self.keyproc)
        self.mode=self.alloc(0x800);self.modevt=self.alloc(256);self.dispatch=self.alloc(16)
        self.w(self.mode,self.modevt);self.w(self.modevt+0x18,self.dispatch)
        self.stub(self.dispatch,lambda:(self.actions.append(('mode',tuple(self.args(5)))),self.ret(20)))
        self.stub(0xA75340,lambda:self.ret(0,self.mode));self.stub(0x5D98A0,lambda:self.ret(0,0))
        self.stub(0xD5AA40,self.sessioncopy);self.stub(0x6A25F0,self.copyitem)
        self.stub(0xC938E0,self.native_drag);self.stub(0xA33100,lambda:self.ret(0,0))
        self.desc=self.alloc(256);self.descvt=self.alloc(256);self.descevent=self.alloc(16)
        self.w(self.desc,self.descvt);self.w(self.descvt+0x94,self.descevent)
        self.stub(self.descevent,self.describe);self.stub(0xA39340,lambda:self.ret(4,self.desc))
        self.stub(0x936700,lambda:self.ret(4,self.u.reg_read(UC_X86_REG_ECX)))
        self.stub(0xA2E770,lambda:self.ret(4))
        self.font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',11)
        self.obj=self.window(280,248,0x103D460);self.query=self.alloc(256)
        self.inventory([(2,501,8,0,'Red Potion'),(3,1201,1,4,'Knife'),(4,1201,1,4,'Knife'),(5,4001,1,6,'Poring Card'),(6,909,99,3,'Jellopy')])
        self.invoke(self.c['create'],self.obj,(280,248));self.rebuild()
    def addchild(self):
        self.w(self.args(1)[0]+0x10,self.u.reg_read(UC_X86_REG_ECX));self.ret(4)
    def stockcreate(self):
        w=self.u.reg_read(UC_X86_REG_ECX)
        for off in [0xBC,0xC0,0xF4,0xF8,0xFC,0x114,0x118,0x11C,0x120,0x124,0x12C]:
            child=self.window(20,20,0x102DD44,w);self.w(w+off,child)
        head=self.alloc(12);self.w(head,head);self.w(head+4,head);self.w(w+0xE8,head);self.w(w+0xEC,0)
        tab=self.r(w+0x118);sizes=self.alloc(16)
        for i in range(4):self.w(sizes+i*4,34)
        self.w(tab+0xCC,sizes);self.w(tab+0xB4,0x20000000);self.w(tab+0xB8,0x20000000+4*24);self.w(tab+0x80,0)
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
        elif name=='storagelock.png':self.assets=ROOT/'Assets/StorageInventoryUI/storageui'
        elif name=='cart_bg.png':self.assets=ROOT/'Assets/StorageInventoryUI/cartui'
        try:
            if getattr(self,'native_fallback',False) and not (self.assets/name).is_file():
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
        self.w(previous,head);self.w(head+4,previous);self.w(0x15FA3C0+0x16F0,head);self.w(0x15FA3C0+0x16F4,len(rows))
    def iteminfo(self):
        id=self.r(self.args(1)[0]);node=self.alloc(0x100);self.string(node,4,'Unidentified item');self.string(node,0x40,self.names.get(id,'Unknown'));self.w(node+0x84,int(id in self.costumes));self.ret(4,node)
    def copyitem(self):
        target=self.u.reg_read(UC_X86_REG_ECX);source=self.args(1)[0];self.copies.append(source);self.u.mem_write(target,bytes(self.u.mem_read(source,248)));self.ret(4,target)
    def emptyitem(self):
        target=self.u.reg_read(UC_X86_REG_ECX);self.u.mem_write(target,bytes(248));self.ret(4,target)
    def sessioncopy(self):
        out,index=self.args(2);self.u.mem_write(out,bytes(self.u.mem_read(self.slots[index],248)));self.ret(8,out)
    def session_at(self):
        out,index=self.args(2);source=list(self.slots.values())[index];self.u.mem_write(out,bytes(self.u.mem_read(source,248)));self.ret(8,out)
    def sprite(self):
        x,y,tex,flag=self.args(4);name=next(n for n,t in self.textures.items() if t==tex);self.images.append((name,x,y,self.u.reg_read(UC_X86_REG_ECX)));self.ret(16)
    def native_drag(self):
        kind,item,amount,unknown=self.args(4);self.actions.append(('drag',(kind,self.r(item+4),amount,unknown)));self.ret(16)
    def describe(self):
        args=self.args(6);self.actions.append(('describe',bytes(self.u.mem_read(args[2],248))));self.ret(24)
    def fit(self):
        obj,ptr,x,y,width,color=self.args(6);pix,w,h=self.pixels(obj);text=self.cstr(ptr);self.texts.append((text,x,y,obj))
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA');rgb=(color&255,(color>>8)&255,(color>>16)&255);ImageDraw.Draw(im).text((x,y),text,font=self.font,fill=rgb+(255,));self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(24)
    def icon(self):
        x,y,item,_,_=self.args(5);self.icons.append((x,y,item));obj=self.u.reg_read(UC_X86_REG_ECX);pix,w,h=self.pixels(obj)
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA');draw=ImageDraw.Draw(im);draw.ellipse((x+6,y+4,x+17,y+18),fill=(173,93,91,255),outline=(75,54,35,255));draw.text((x+14,y+15),str(self.r(item+0x10)),font=self.font,fill=(40,40,40,255));self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(20)
    def state(self,o):return self.r(self.c['state']+o)
    def rebuild(self):self.invoke(self.c['draw'],self.obj)
    def search(self,text):self.u.mem_write(self.query,text.encode()+b'\0');self.invoke(self.c['process'],self.obj);self.rebuild()
    def click(self,x,y):self.invoke(self.c['down'],self.obj,(x,y));self.invoke(self.c['up'],self.obj,(x,y));self.rebuild()
    def preview(self,path):
        self.texts=[];self.icons=[];self.invoke(self.c['draw'],self.obj);pix,w,h=self.pixels(self.obj);Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA').convert('RGB').save(path)
    def selected(self,x,y):
        out=self.alloc(248);self.invoke(0x939E30,self.obj,(out,x,y));return bytes(self.u.mem_read(out,248))

def factory_test(exe):
    """Run stock inventory factory/constructor and Create dispatch, not a remap."""
    m=InventoryMachine(exe);m.native_fallback=True
    # Native settings validation reads the render device's viewport dimensions.
    device=m.alloc(0x40);m.w(0x12515F8,device);m.w(device+0x28,1920);m.w(device+0x2C,1080)
    for addr in [0xA39340,0xA1CB70,0x93F100,0x817DA0,0xA1B780,0xA245C0,0x82DAC0]:m.u.hook_del(m._machine_stubs[addr])
    surfacevt=m.alloc(16);surfacefree=m.alloc(16);m.w(surfacevt,surfacefree);m.stub(surfacefree,lambda:m.ret(4))
    def surface():
        w,h,_=m.args(3);obj=m.alloc(0x40);pix=m.alloc(w*h*4);m.w(obj,surfacevt);m.w(obj+4,w);m.w(obj+8,h);m.w(obj+0x18,pix);m.ret(0,obj)
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
    m.u.mem_write(head+13,b'\1');m.w(node+16,8);m.w(0x131F4E8+8,head);m.w(0x131F4E8+12,1)
    head=m.alloc(12);m.w(head,head);m.w(head+4,head);m.w(0x131F4E8+0x17C,head)
    m.invoke(0xA39340,0x131F4E8,(8,))
    m.obj=m.r(0x131F4E8+0x1D4);obj=m.obj;editor=m.state(4)
    assert obj==m.state(0) and m.state(8)==1
    assert (m.r(obj+0x14),m.r(obj+0x18))==(280,296)
    def children():
        head=m.r(m.obj+0x50);node=m.r(head);result=[]
        while node!=head:
            result.append(m.r(node+8));node=m.r(node)
            assert len(result)<128
        return result
    assert len(children())==12 and set(p for p in children() if m.r(p+0x28))=={editor,m.r(obj+0x114),m.r(obj+0x11C),m.r(obj+0x120)}, 'stock controls overlay custom view'
    # Alt+E closes through native settings-save and reopens through message 0x22.
    # Native restore compares the saved current/restore heights, not just 17px.
    saved=m.r(obj+0xF0)
    m.w(0x95598B,1024) # Include resized heights allowed by BiggerInventoryWindow.
    for height in [296,328,360,296]*4:
        m.invoke(m.c['event'],obj,(0,14,7,280,height,0))
        m.invoke(0x95B340,obj)
        m.invoke(m.c['event'],obj,(0,0x22,saved,0,0,0))
        assert m.r(obj+0x18)==height and m.r(obj+0x110)==height,('Alt+E save/reopen unexpectedly changed height',height,m.r(obj+0x18),m.r(obj+0x110),[m.r(saved+o) for o in range(0,36,4)])
        assert m.r(saved+12)==m.r(saved+16)==height, (height,hex(saved),[m.r(saved+o) for o in range(0,36,4)])
    # Repair already-saved mismatches from the earlier runtime, preserving the
    # explicitly minimized 17px state handled separately below.
    m.w(saved+12,328);m.w(saved+16,120)
    m.invoke(m.c['event'],obj,(0,0x22,saved,0,0,0))
    assert m.r(obj+0x18)==328 and m.r(obj+0x110)==328
    m.invoke(m.c['event'],obj,(0,14,7,280,296,0))
    m.u.hook_del(m._machine_stubs[0x8210A0]);m.u.mem_write(m.query,b'Red\0')
    m.invoke(0x8303F0,editor,(m.query,));m.invoke(m.c['process'],obj);m.rebuild();assert m.state(20)==1
    m.click(70,35);assert m.r(0x131F4E8+0x1A0)==editor
    m.click(251,5);assert m.r(obj+0x18)==17 and not m.r(editor+0x28) and not m.r(0x131F4E8+0x1A0)
    m.invoke(0x95B340,obj)
    assert (m.r(saved+12),m.r(saved+16))==(17,296)
    m.invoke(m.c['event'],obj,(0,0x22,saved,0,0,0))
    assert (m.r(obj+0x18),m.r(obj+0x110))==(17,296),'explicit minimize was not preserved on reopen'
    m.click(251,5);assert m.r(obj+0x18)==296 and m.r(editor+0x28)
    m.w(0x955980,1280);m.w(0x95598B,1024)
    m.invoke(m.c['event'],obj,(0,14,7,344,280,0));m.invoke(m.c['process'],obj);m.rebuild();assert m.state(20)==1,'native editor text lost during resize'
    assert (m.r(obj+0x14),m.r(obj+0x18))==(344,296)
    assert bytes(m.u.mem_read(m.c['state']+44,4))==b'Red\0'
    # Exercise the original sale-lock command, popup construction and child art.
    m.click(10,200);m.click(137,m.r(obj+0x18)-12)
    assert m.u.mem_read(0x1600553,1)==b'\1' and m.r(obj+0x128)
    m.click(137,m.r(obj+0x18)-12);assert m.u.mem_read(0x1600553,1)==b'\0' and not m.r(obj+0x128)
    # Window-manager scheduling is a boundary; execute the exact close command,
    # then the same stock virtual destructor that its deferred removal invokes.
    m.stub(0xA2E770,lambda:(m.actions.append(('close',m.args(1)[0])),m.ret(4)))
    prior_category=m.state(12)
    m.click(339,5);assert m.actions[-1]==('close',8)
    m.u.hook_del(m._machine_stubs[0x936700]);m.invoke(m.c['destroy'],obj,(1,));assert m.state(0)==0 and m.state(8)==0
    m.w(0x131F4E8+0x1D4,0);m.invoke(0xA39340,0x131F4E8,(8,));m.obj=m.r(0x131F4E8+0x1D4)
    assert m.obj!=obj and m.state(8)==1 and m.state(12)==prior_category and m.state(16)==0
    m.invoke(m.c['destroy'],m.obj,(1,));m.w(0x131F4E8+0x1D4,0);m.missing.add('bg.png')
    m.invoke(0xA39340,0x131F4E8,(8,));m.obj=m.r(0x131F4E8+0x1D4)
    assert m.state(8)==0 and any(m.r(p+0x28) for p in children()),('missing asset must leave complete stock UI',m.state(8),m.r(m.obj+0x18),[(hex(p),m.r(p+0x28)) for p in children()])
    def geometry():return (m.r(m.obj+0x14),m.r(m.obj+0x18),[(m.r(p),*[m.r(p+o) for o in (0x14,0x18,0x1C,0x20,0x28)]) for p in children()])
    fallback=geometry();m.invoke(m.c['destroy'],m.obj,(1,));m.w(0x131F4E8+0x1D4,0)
    m.w(0x103D460+15*4,0x93F100);m.invoke(0xA39340,0x131F4E8,(8,));m.obj=m.r(0x131F4E8+0x1D4)
    assert geometry()==fallback,'missing-art geometry/controls differ from original native OnCreate'
    return m

def restored_controls_test(exe,output):
    """Execute stock favorite packets, sort, footer commands and hover producer."""
    m=InventoryMachine(exe);obj=m.obj;packets=[];titles=[];tips=[];options=[]
    m.stub(0xA47B90,lambda:m.ret(4,0))
    m.stub(0xC14D60,lambda:m.ret(0,0x1310000))
    m.stub(0xC14460,lambda:m.ret(4,5))
    def send():
        n,p=m.args(2);packets.append(bytes(m.u.mem_read(p,n)));m.ret(8,1)
    m.stub(0xC14920,send)
    payload=m.alloc(0x100);m.w(payload,1);m.w(payload+4,3);m.w(payload+0x84,obj)
    m.invoke(m.c['down'],obj,(90,60));m.invoke(m.c['drop'],obj,(10,200,payload))
    assert packets==[bytes.fromhex('0709030000')],packets
    assert m.state(12)==6 and m.r(payload+0x84)==obj
    # Wait for native inventory update; no optimistic session mutation.
    assert m.u.mem_read(m.slots[3]+0x74,1)==b'\0'
    m.u.mem_write(m.slots[3]+0x74,b'\1');m.click(10,200)
    m.invoke(m.c['down'],obj,(58,60));m.invoke(m.c['drop'],obj,(10,82,payload))
    assert packets[-1]==bytes.fromhex('0709030001')
    count=len(packets)
    m.invoke(m.c['drop'],obj,(10,82,payload));assert len(packets)==count,'replayed drag sent another packet'
    m.invoke(m.c['down'],obj,(58,60));m.w(m.slots[3]+0x60,9)
    m.invoke(m.c['drop'],obj,(10,82,payload));assert len(packets)==count,'changed dragged instance sent packet'
    m.rebuild();m.invoke(m.c['down'],obj,(58,60));m.invoke(m.c['drop'],obj,(260,230,payload));assert len(packets)==count,'outside drop changed favorites'
    m.click(10,20);m.click(5,280);assert m.actions[-1]==('mode',(0x136,0,0,0,0))
    m.click(85,281);assert m.u.mem_read(0x15FFFA0,1)==b'\1' and m.r(m.r(obj+0x114)+0x30)==1
    m.click(85,281);assert m.u.mem_read(0x15FFFA0,1)==b'\0' and m.r(m.r(obj+0x114)+0x30)==0
    m.w(0x131EE7C,m.alloc(0x58));m.stub(0x68FAA0,lambda:(options.append(m.args(1)[0]),m.ret(4)))
    m.click(115,281);assert options==[0x108]
    def title():
        item=m.u.reg_read(UC_X86_REG_ECX);out,flag=m.args(2);titles.append(bytes(m.u.mem_read(item,248)))
        slot=m.r(item+4);name=m.names[int(m.cstr(item+0x2C))];refine=m.r(item+0x60)
        m.string(out,0,('+'+str(refine)+' ' if refine else '')+name);m.ret(8,out)
    m.stub(0x6A2CE0,title)
    # Formatting/localization and the OS tooltip window are boundaries; the
    # native move handler, exact CItem selector and coordinate bridge execute.
    m.stub(0xD5A760,lambda:m.ret(4,0x123456))
    fmt=m.alloc(16);m.stub(0xA9ED30,lambda:m.ret(0,fmt))
    def format_tip():
        out,_,name,qty=m.args(4);m.string(out,0,m.cstr(name)+': '+str(qty)+' ea.');m.ret(0,out)
    m.stub(0xA94930,format_tip)
    manager=m.alloc(32);m.w(0x121333C,manager)
    def show_tip():
        label,x,y,color,_,_=m.args(6);tips.append((m.cstr(label),x,y,color,m.u.reg_read(UC_X86_REG_ECX)));m.ret(24)
    m.stub(0xA753D0,show_tip)
    m.click(10,20);m.w(obj+0x1C,100);m.w(obj+0x20,50)
    m.invoke(m.c['move'],obj,(90,60))
    assert tips[-1]==('+9 Knife: 1 ea.',188,92,0x123456,manager),tips
    assert titles[-1]==bytes(m.u.mem_read(m.slots[3],248))
    m.w(0x15FBA90,1234567);m.w(0x15FBAA0,862);m.w(0x15FBA9C,5030);m.w(0x1602324,50)
    m.invoke(m.c['move'],obj,(160,262));assert tips[-1][0]=='Weight 17%'
    m.u.mem_write(m.slots[3]+0x5D,b'\1');m.w(m.slots[3]+0x68,1900000000);m.u.mem_write(m.slots[3]+0x88,b'\x02\0')
    m.u.mem_write(m.slots[3]+0x75,b'\1');m.rebuild()
    assert any(a[0]=='equipped' for a in m.actions)
    assert ('grade_icon2.bmp',92,75,obj) in m.images
    assert any(t[0]=='1,234,567' for t in m.texts) and any(t[0]=='862 / 5,030' for t in m.texts)
    # Badge pixels come from the supplied PNGs, including the two-badge placement.
    pixels,width,_=m.pixels(obj)
    for filename,dx,dy in [('icon_damaged.png',107,58),('rent_icon.png',111,71)]:
        art=Image.open(ROOT/'Assets/StorageInventoryUI/inventoryui'/filename).convert('RGBA')
        px,py=next((x,y) for y in range(art.height) for x in range(art.width) if art.getpixel((x,y))[3]==255)
        r,g,b,a=art.getpixel((px,py));assert m.r(pixels+((dy+py)*width+dx+px)*4)==(a<<24|r<<16|g<<8|b),filename
    m.preview(output/'inventory-restored.png')
    # Original sort compares native type rank, then the decorated native title.
    m.inventory([(2,501,1,0,'Z Potion',0,1),(3,502,1,0,'A Potion',0,1),(4,1201,1,4,'Knife',0,1)])
    m.stub(0x95B5D0,lambda:m.ret(0)) # Button localization/art refresh; sort stays native.
    m.click(10,200);before=[m.r(m.c['state']+108+i*12) for i in range(m.state(20))]
    m.click(167,281);assert m.u.mem_read(0x160226C,1)==b'\1'
    after=[m.r(m.c['state']+108+i*12) for i in range(m.state(20))]
    assert before==[2,3,4] and after==[3,2,4],(before,after)
    m.click(167,281);assert m.u.mem_read(0x160226C,1)==b'\0'
    assert [m.r(m.c['state']+108+i*12) for i in range(m.state(20))]==before
    assert m.r(m.r(obj+0x124)+0x28) and m.r(m.r(obj+0x12C)+0x28)
    m.click(10,20);assert not m.r(m.r(obj+0x124)+0x28) and not m.r(m.r(obj+0x12C)+0x28)


def selection_geometry_test(exe,output):
    """Check full selected_bg borders and native icon centers in the emitted draw."""
    m=InventoryMachine(exe);m.w(m.c['state']+24,70);m.w(m.c['state']+28,70)
    m.preview(output/'inventory-selection.png')
    pixels,width,_=m.pixels(m.obj)
    def pixel(x,y):return m.r(pixels+(y*width+x)*4)
    def rgba(value):
        r,g,b,a=value;return a<<24|r<<16|g<<8|b
    frame=Image.open(ROOT/'Assets/StorageInventoryUI/inventoryui/selected_bg.png').convert('RGBA')
    for y in range(4,28):
        assert pixel(56,58+y)==pixel(87,58+y)==rgba(frame.getpixel((0,y))),'selection lacks a complete side'
    for x in range(4,28):
        assert pixel(56+x,58)==rgba(frame.getpixel((x,0))),'selection lacks its top edge'
        assert pixel(56+x,89)==rgba(frame.getpixel((x,31))),'selection lacks its bottom edge'
    shadow=Image.open(ROOT/'Assets/StorageInventoryUI/inventoryui/bg.png').convert('RGBA')
    assert pixel(59,75)==rgba(shadow.getpixel((60,41))),'selected background erased the circle shadow'
    for n,(x,y,_) in enumerate(m.icons):
        assert (x+12,y+12)==(72+(n%6)*32,75+(n//6)*32),'item canvas is not centered on its shadow'

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('exe',type=Path);p.add_argument('--output',type=Path,required=True);args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    m=InventoryMachine(args.exe);s=m.c['state'];assert m.state(8)==1 and m.state(20)==5
    before={i:bytes(m.u.mem_read(a,248)) for i,a in m.slots.items()}
    assert m.selected(57,59)==before[2]
    for x,y in [(10,80),(50,40),(55,59),(56,57),(250,219),(200,225),(57,219)]:assert struct.unpack_from('<I',m.selected(x,y),4)[0]==0
    m.invoke(m.c['double'],m.obj,(58,60));assert m.actions[-1]==('mode',(0x1B,2,0,0,0)),m.actions
    m.invoke(m.c['down'],m.obj,(58,60));assert m.actions[-1][0]=='drag' and m.actions[-1][1][1]==2,m.actions
    m.invoke(m.c['right'],m.obj,(90,60));assert m.actions[-1]==('describe',before[3])
    m.search('kNi');assert m.state(20)==2 and struct.unpack_from('<I',m.selected(58,60),4)[0]==3 and struct.unpack_from('<I',m.selected(90,60),4)[0]==4
    m.u.mem_write(m.slots[3]+0x1C,pack(4001));assert struct.unpack_from('<I',m.selected(58,60),4)[0]==0,'stale exact instance became actionable'
    m.rebuild();assert struct.unpack_from('<I',m.selected(58,60),0x1C)[0]==4001
    m.w(m.slots[3]+0xC,0x20);assert struct.unpack_from('<I',m.selected(58,60),4)[0]==0,'changed native equipment instance remained actionable before redraw'
    m.rebuild();assert struct.unpack_from('<I',m.selected(58,60),0xC)[0]==0x20
    m.w(m.slots[3]+0x10,0);assert struct.unpack_from('<I',m.selected(58,60),4)[0]==0
    m.search('');m.click(10,17+4*32+3);assert m.state(12)==4 and m.state(20)==1 and struct.unpack_from('<I',m.selected(58,60),4)[0]==5
    m.click(10,84);assert m.state(12)==2 and m.state(20)==1,'native type4 equipment filter'
    m.preview(args.output/'inventory-equipment.png');assert len(m.icons)==1 and m.icons[0][2]==m.slots[4]
    m.inventory([(2,1750,1,10,'Arrow'),(3,19500,1,5,'Costume Hat'),(4,24000,1,5,'Shadow Gear'),(5,9001,1,7,'Pet Egg'),(6,10013,1,5,'Pet Accessory')]);m.w(m.slots[3]+8,0x400);m.w(m.slots[4]+8,0x10000);m.pet_eggs.add(9001);m.pet_gear.add(10013)
    m.click(10,180);assert m.state(12)==0 and m.state(20)==5,'arrow must expose extra categories'
    for y,cat,slots in [(52,5,[2]),(84,7,[3]),(116,8,[4]),(148,9,[5,6])]:
        m.click(10,y);assert m.state(12)==cat and m.state(20)==len(slots)
        assert [struct.unpack_from('<I',m.selected(58+i*32,60),4)[0] for i in range(len(slots))]==slots
    m.preview(args.output/'inventory-extra-categories.png');assert len(m.icons)==2
    lookups=len(m.pet_lookups);m.rebuild();m.rebuild();assert len(m.pet_lookups)==lookups,'pet classification calls Lua each frame'
    m.string(m.slots[6],0x2C,'10014');m.rebuild();assert len(m.pet_lookups)>lookups and m.state(20)==1,'new item ID did not invalidate classification'
    m.string(m.slots[6],0x2C,'10013');m.rebuild()
    m.u.mem_write(m.slots[5]+0x5D,b'\1');m.rebuild();assert m.state(20)==1,'hidden hatched egg exposed'
    m.click(10,180);assert m.state(12)==0
    m.click(10,20);m.search('absent');assert m.state(20)==0;m.preview(args.output/'inventory-empty.png')
    m.search('');m.click(70,35);assert m.r(0x131F4E8+0x1A0)==m.state(4),'native edit not focused'
    m.invoke(m.c['editevent'],m.state(4),(0,0,0,0,0,0));assert m.r(0x131F4E8+0x1A0)==0
    m.inventory([(i+2,501,1,0,'Red Potion') for i in range(80)]);m.rebuild();m.preview(args.output/'inventory-grid.png');assert len(m.icons)==30,'minimum inventory must display 6x5 cells'
    m.invoke(m.c['wheel'],m.obj,(0xFFFFFF88,));assert m.state(16)==3
    assert struct.unpack_from('<I',m.selected(58,60),4)[0]==0,'changed viewport actionable before draw'
    m.rebuild();assert struct.unpack_from('<I',m.selected(58,60),4)[0]==20
    m.u.mem_write(m.query,b'absent\0');assert struct.unpack_from('<I',m.selected(58,60),4)[0]==0,'edited search selected old scrolled row before draw'
    assert m.state(20)==0;m.search('')
    m.invoke(m.c['down'],m.obj,(270,60));m.invoke(m.c['drag'],m.obj,(270,217));assert m.state(16)==9
    m.invoke(m.c['up'],m.obj,(270,217));assert m.r(0x131F4E8+0x19C)==0
    m.inventory([(2,501,1,0,'Red Potion')]);m.rebuild();assert m.state(16)==0
    m.w(0x955980,1280);m.w(0x95598B,1024) # Same immediate fields as BiggerInventoryWindow.
    # Both outer tips of the native 13px grip must begin a resize.
    m.invoke(m.c['down'],m.obj,(265,293));assert m.state(32)==25
    m.invoke(m.c['up'],m.obj,(265,293))
    m.invoke(m.c['down'],m.obj,(277,281));assert m.state(32)==25
    m.invoke(m.c['drag'],m.obj,(341,313));assert (m.r(m.obj+0x14),m.r(m.obj+0x18))==(344,328)
    m.invoke(m.c['up'],m.obj,(342,278));m.preview(args.output/'inventory-resized.png')
    m.inventory([(2,501,1,0,'Red Potion',0,1)]);m.rebuild();m.u.mem_write(0x1600553,b'\1');n=len(m.actions);m.invoke(m.c['double'],m.obj,(58,60));assert m.actions[-1]==('mode',(0x1B,2,0,0,0)),'sale lock must not block ordinary favorite item use'
    m.invoke(m.c['right'],m.obj,(58,60));assert m.actions[-1][0]=='describe','locked favorite cannot be inspected'
    m.w(0x131F4E8+0x1A0,m.state(4));m.w(0x131F4E8+0x19C,m.obj);m.invoke(m.c['destroy'],m.obj,(1,));assert m.state(8)==0 and m.state(0)==0 and m.r(0x131F4E8+0x1A0)==0 and m.r(0x131F4E8+0x19C)==0
    m.invoke(m.c['create'],m.obj,(280,248));assert m.state(8)==1 and m.state(12)==0 and m.state(16)==0
    lookups=len(m.pet_lookups);m.click(10,180);m.click(10,148);assert len(m.pet_lookups)>lookups,'reopen must reset category cache'
    m.missing.add('bg.png');m.invoke(m.c['destroy'],m.obj,(1,));m.invoke(m.c['create'],m.obj,(280,248));assert m.state(8)==0
    restored_controls_test(args.exe,args.output)
    factory_test(args.exe)
    selection_geometry_test(args.exe,args.output)
    check_dropdown(InventoryMachine(args.exe),True,args.output)
    print('PASS: InventoryUI x86 exact-slot search/category, native use/drag/description, stale instances, 30-slot grid, scroll/resize, native sale/drop locks, favorite drag packets and sorting, footer commands, native hover and badges; stock factory/OnCreate/child controls/native editor/minimize/destructor/reopen, 16 native settings save/restore cycles, persisted-height repair, complete selection frame, centered item canvases and complete missing-asset fallback')

if __name__=='__main__':main()
