"""Execute emitted StorageUI x86 with original CItem constructors and selection.

Native OS/font/database/surface boundaries are explicit doubles. Original PNGs
are rendered from the bundle. These checks do not replace live game acceptance.
"""
import argparse,struct,json,io
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from unicorn.x86_const import UC_X86_REG_EAX,UC_X86_REG_ECX
from test_modern_chat_ui import Machine,pack
from test_gacha_ui import GachaMachine
from test_shop_ui import ShopMachine,NAMES
from test_trade_ui import TradeMachine
from test_vending_ui import VendingMachine

ROOT=Path(__file__).resolve().parents[1]
FIELDS='api state construct create process draw down up move drag right destroy event editevent wheel select build category contains hit itemhit'.split()
def contract(m):
    data=m.pe.get_memory_mapped_image();marker=data.index(b'StorageUI.v1\0');record=data.index(pack(m.base+marker))
    return {n:m.r(m.base+record+4+i*4) for i,n in enumerate(FIELDS)}

class StorageMachine(Machine):
    invoke=GachaMachine.invoke
    text=GachaMachine.text
    measure=ShopMachine.measure
    copy_bytes=VendingMachine.copy_bytes
    def native_icon(self):
        x,y,item,_,_=self.args(5);self.native_items.append((x,y,item));id=int(self.cstr(item+0x2c))
        pix,w,h=self.pixels(self.u.reg_read(UC_X86_REG_ECX));im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA')
        if id in self.real_icons:
            icon=self.real_icons[id].copy();icon.putdata([(r,g,b,0 if (r,g,b)==(255,0,255) else a) for r,g,b,a in icon.get_flattened_data()]);im.alpha_composite(icon,(x+(24-icon.width)//2,y+(24-icon.height)//2))
        ImageDraw.Draw(im).text((x+14,y+15),str(self.r(item+0x10)),font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',10),fill='#282828')
        self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(20)
    def setsize(self,obj,w,h):
        Machine.setsize(self,obj,w,h)
        if not hasattr(self,'surface_vtable'):
            self.surface_vtable=self.alloc(16);destroy=self.alloc(16);self.w(self.surface_vtable,destroy)
            self.stub(destroy,lambda:self.ret(4))
        self.w(self.r(obj+0x24),self.surface_vtable)
    def __init__(self,exe,native_create=False):
        self.text_colors=[];super().__init__(str(exe),ROOT/'Assets/StorageInventoryUI')
        self.c=contract(self)
        self.missing=set();self.native_items=[];self.real_icons={};self.closed=[];self.moves=[];self.events=[];self.iteminfo={};self.names={501:'Red Potion',502:'Orange Potion',1201:'Knife',1202:'Knife',4001:'Poring Card',512:'Apple'}
        self.query=self.alloc(128);self.u.mem_write(self.query,b'\0')
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0xDBBC7F,lambda:self.ret(0));self.stub(0xDBBBD4,lambda:self.ret(0,self.u.reg_read(UC_X86_REG_EAX)))
        self.message=self.alloc(64);self.u.mem_write(self.message,b'Storage\0')
        self.stub(0xA9ED30,lambda:self.ret(0,self.message));self.stub(0x529850,self.sprintf)
        if native_create:
            self.u.hook_del(self._machine_stubs.pop(0xA1CB70))
            self.stub(0x560E50,self.surface)
            self.stub(0xA47B90,lambda:self.ret(4,0))
        self.stub(0xE07D7B,self.copy_bytes);self.stub(0xE07D4B,self.copy_bytes)
        self.stub(0xA21C90,self.measure);self.stub(0x8210A0,lambda:self.ret(0,self.query))
        self.stub(0xA7E780,self.info);self.w(0x159C088,self.alloc(64));self.eggs=set();self.pet_accessories=set();self.pet_calls=[0,0]
        self.stub(0xD8EBE0,lambda:self.pet_predicate(0,self.eggs))
        self.stub(0xD98320,lambda:self.pet_predicate(1,self.pet_accessories))
        self.stub(self.r(self.c['api']+20),self.name)
        self.stub(0xA1D260,self.sprite);self.stub(0xA1D460,self.fill);self.stub(0x871160,self.empty_slot);self.stub(0x8711A0,self.native_icon);self.stub(0x897860,self.native_name)
        self.stub(0xA4B750,lambda:(self.w(0x131F4E8+0x19c,self.args(1)[0]),self.ret(4)))
        self.stub(0x880BB0,lambda:self.ret(8));self.stub(0x880E00,lambda:(self.moves.append(tuple(self.args(2))),self.ret(8)))
        # Native session ownership is modeled; CItem copy/empty functions below
        # execute original x86, including the original inline-string copy logic.
        self.head=self.alloc(16);self.w(self.head,self.head);self.w(self.head+4,self.head);self.w(0x15FA3C0+0x1718,self.head)
        self.obj=self.alloc(0x194);self.invoke(self.c['construct'],self.obj);assert self.r(self.obj)==self.r(self.c['api']+4)
        # Factory original constructor call stays at the exact id33 arm. UI child
        # setup boundary here supplies the same pointer fields as stock OnCreate.
        if not native_create:self.stub(0x93DC60,self.create_children)
        else:self.setsize(self.obj,280,458)
        self.invoke(self.c['create'],self.obj,(280,458));self.editor=self.r(self.obj+0xF0)
        self.u.mem_write(self.obj+0x190,b'\1');self.w(self.obj+0x18C,600)
        self.stub(0x9544F0,self.native_event)
        self.out=self.alloc(0xF8)
    def sprintf(self):
        dest,fmt=self.args(2);self.u.mem_write(dest,b'Storage\0');self.ret(0,7)
    def surface(self):
        width,height,_=self.args(3);temp=self.alloc(0x100);self.setsize(temp,width,height);self.ret(0,self.r(temp+0x24))
    def load_texture(self,name):
        if name in self.missing:return 0
        if name.endswith('.bmp'):
            if name not in self.textures:
                from test_inventory_ui import native_art
                raw=native_art(name)
                t=self.alloc(0x130)
                if raw:
                    im=Image.open(io.BytesIO(raw)).convert('RGBA');width,height=im.size;pix=self.alloc(width*height*4)
                    self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.w(t+0x11C,pix)
                else:width,height=44,18
                self.w(t+0x114,width);self.w(t+0x118,height);self.textures[name]=t
            return self.textures[name]
        old=self.assets;self.assets=old/('genericsui' if name.startswith(('clos_','cls_')) else 'inventoryui' if name=='selected_bg.png' else 'storageui')
        try:return super().load_texture(name)
        finally:self.assets=old
    def sprite(self):
        x,y,t,flag=self.args(4);pix,w,h=self.pixels(self.u.reg_read(UC_X86_REG_ECX));tw,th=self.r(t+0x114),self.r(t+0x118)
        raw=bytes(self.u.mem_read(self.r(t+0x11c),tw*th*4));im=Image.frombytes('RGBA',(tw,th),raw,'raw','BGRA');im.putdata([(r,g,b,0 if (r,g,b)==(255,0,255) else 255) for r,g,b,a in im.get_flattened_data()])
        dest=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA');dest.alpha_composite(im,(x,y));self.u.mem_write(pix,dest.tobytes('raw','BGRA'));self.ret(16)
    def create_children(self):
        w=self.u.reg_read(UC_X86_REG_ECX);self.setsize(w,280,458)
        for off in [0xBC,0xC0,0xC4,0xC8,0xCC,0xD0,0xF4,*range(0x100,0x120,4),0x168]:self.w(w+off,self.window(20,20));self.w(self.r(w+off)+0x28,1)
        # Poison nonpointer flag bytes. The skin must never treat +F8 as a child.
        self.w(w+0xF8,0x01010101)
        edit=self.window(122,18,0xFD9190,w);self.w(w+0xF0,edit);self.w(edit+0x88,20);self.ret(8)
    def native_event(self):
        args=tuple(self.args(6));self.events.append(args)
        if args[1:3]==(6,0xC9):self.closed.append(self.u.reg_read(UC_X86_REG_ECX))
        self.ret(24)
    def info(self):
        id=self.r(self.args(1)[0]);self.ret(4,self.iteminfo.get(id,0))
    def pet_predicate(self,index,values):
        self.pet_calls[index]+=1;self.ret(4,(0xABCD1200 if index else 0)|int(self.args(1)[0] in values))
    def name(self):
        id=self.args(1)[0];value=self.names.get(id,'Item '+str(id)).encode()+b'\0';p=self.alloc(len(value));self.u.mem_write(p,value);self.ret(4,p)
    def fill(self):
        x,y,ww,hh,color=self.args(5);p,w,h=self.pixels(self.u.reg_read(UC_X86_REG_ECX));assert x+ww<=w and y+hh<=h,(x,y,ww,hh,w,h)
        color=0xff000000|((color&255)<<16)|(color&0xff00)|((color>>16)&255)
        for row in range(y,y+hh):self.u.mem_write(p+(row*w+x)*4,pack(color)*ww)
        self.ret(20)
    def empty_slot(self):
        x,y=self.args(2);p,w,h=self.pixels(self.u.reg_read(UC_X86_REG_ECX));im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(p,w*h*4)),'raw','BGRA');ImageDraw.Draw(im).ellipse((x+6,y+10,x+25,y+18),fill='#dbe4f0');self.u.mem_write(p,im.tobytes('raw','BGRA'));self.ret(8)
    def native_name(self):
        x,y,width,item,_,_,size=self.args(7);p,w,h=self.pixels(self.u.reg_read(UC_X86_REG_ECX));im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(p,w*h*4)),'raw','BGRA');id=int(self.cstr(item+0x2c));name=self.names.get(id,'Item '+str(id));refine=self.r(item+0x60);name=(f'+{refine} ' if refine else '')+name
        ImageDraw.Draw(im).text((x,y-2),name,font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',size),fill='#504f50');self.u.mem_write(p,im.tobytes('raw','BGRA'));self.ret(28)
    def rows(self,values):
        previous=self.head;self.items=[]
        for row in values:
            slot,id,kind,amount,refine=row;p=self.alloc(0x100);item=p+8;self.w(previous,p);self.w(p+4,previous);self.w(p,self.head);previous=p
            for off,value in [(0,kind),(4,slot),(0x10,amount),(0x3c,len(str(id))),(0x40,15),(0x60,refine)]:self.w(item+off,value)
            self.u.mem_write(item+0x2c,str(id).encode()+b'\0');self.w(item+0xF0,15);self.u.mem_write(item+0x5c,b'\1');self.items.append(item)
        self.w(self.head+4,previous);self.w(0x15FA3C0+0x171C,len(values));self.w(self.obj+0x188,len(values))
    def search(self,value):self.u.mem_write(self.query,value.encode()+b'\0');self.invoke(self.c['process'],self.obj)
    def draw(self,path=None):
        self.native_items=[];self.invoke(self.c['draw'],self.obj);p,w,h=self.pixels(self.obj);im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(p,w*h*4)),'raw','BGRA').convert('RGB')
        if path:im.save(path)
        return im
    def select(self,x,y):self.invoke(self.c['select'],self.obj,(self.out,x,y));return self.r(self.out+4)
    def click(self,x,y):self.invoke(self.c['down'],self.obj,(x,y));self.invoke(self.c['up'],self.obj,(x,y))
    def action_boundaries(self):
        self.keys=set();self.actions=[];self.tooltips=[];self.control_tips=[]
        proc=self.alloc(16);self.stub(proc,lambda:self.ret(4,0x8000 if self.args(1)[0] in self.keys else 0))
        for entry in self.pe.DIRECTORY_ENTRY_IMPORT:
            for imp in entry.imports:
                if imp.name==b'GetAsyncKeyState':self.w(imp.address,proc)
        self.mode=self.alloc(0x800);vt=self.alloc(256);dispatch=self.alloc(16);self.w(self.mode,vt);self.w(vt+0x18,dispatch)
        self.stub(dispatch,lambda:(self.actions.append(('mode',tuple(self.args(5)))),self.ret(20)))
        self.stub(0xA75340,lambda:self.ret(0,self.mode));self.stub(0x6A25F0,lambda:self.ret(4))
        self.stub(0xC938E0,self.native_drag)
        self.desc=self.alloc(256);vt=self.alloc(256);event=self.alloc(16);self.w(self.desc,vt);self.w(vt+0x94,event)
        self.stub(event,lambda:(self.actions.append(('describe',bytes(self.u.mem_read(self.args(6)[2],248)))),self.ret(24)))
        self.stub(0xA39340,lambda:self.ret(4,self.desc))
        self.stub(0xD5A760,lambda:(self.tooltips.append(bytes(self.u.mem_read(self.args(1)[0],248))),self.ret(4,0)))
        self.w(0x121333C,self.mode)
        self.stub(0x6A2CE0,self.item_string);self.stub(0xA753D0,self.show_tip)
    def show_tip(self):
        label,x,y,color,_,_=self.args(6)
        self.control_tips.append((self.cstr(label),x,y,color,self.u.reg_read(UC_X86_REG_ECX)));self.ret(24)
    def native_drag(self):
        kind,item,amount,unknown=self.args(4);self.actions.append(('drag',kind,bytes(self.u.mem_read(item,248)),amount,unknown));self.ret(16)
    def item_string(self):
        out,_=self.args(2);self.u.mem_write(out,b'Item\0');self.w(out+16,4);self.w(out+20,15);self.ret(8,out)

def native_callbacks(m):
    m.rows([(10,1201,4,1,2),(11,1201,4,3,9)]);m.action_boundaries();m.search('Knife');m.draw()
    m.invoke(m.c['down'],m.obj,(70,92));a=m.actions[-1];assert a[0:2]==('drag',6) and struct.unpack_from('<I',a[2],4)[0]==11 and a[3]==3
    m.invoke(m.c['right'],m.obj,(70,92));a=m.actions[-1];assert a[0]=='describe' and struct.unpack_from('<I',a[1],4)[0]==11 and struct.unpack_from('<I',a[1],0x60)[0]==9
    m.keys.add(0x10);m.invoke(m.c['right'],m.obj,(70,92));assert m.actions[-1]==('mode',(0x14d,11,3,0,0));m.keys.clear()
    m.invoke(m.c['move'],m.obj,(70,92));assert struct.unpack_from('<I',m.tooltips[-1],4)[0]==11
    m.search('absent');before=len(m.actions);m.draw();m.invoke(m.c['right'],m.obj,(70,60));m.invoke(m.c['down'],m.obj,(70,60));assert len(m.actions)==before
    m.search('Knife');m.draw();m.w(m.items[1]+0x1c,4001);m.invoke(m.c['right'],m.obj,(70,92));assert len(m.actions)==before

def control_tooltips(m):
    m.rows([]);m.action_boundaries();m.draw();m.w(m.obj+0x1c,100);m.w(m.obj+0x20,50)
    def hover(x,y,label):
        before=len(m.control_tips);m.invoke(m.c['move'],m.obj,(x,y))
        assert len(m.control_tips)==before+1
        assert m.control_tips[-1]==(label,100+(33 if x<33 else x),y+34,0xffffffff,m.mode),m.control_tips[-1]
    for row,label in enumerate(['Search','Usable','Weapon','Armor','ETC','Card','Ammunition','Costume','Shadow Gear','Pet','Cash']):
        hover(16,39+row*30,label)
    hover(25,405,'Change to Block');m.click(25,405);hover(25,405,'Change to List')
    m.click(25,405);hover(25,405,'Change to Block')
    for _ in range(3):hover(230,405,'Sort Refine');m.click(230,405)
    hover(120,428,'Lock Storage Transfers');m.click(120,428);hover(120,428,'Unlock Storage Transfers')
    m.click(120,428);hover(120,428,'Lock Storage Transfers')
    before=len(m.control_tips);m.invoke(m.c['move'],m.obj,(150,150));assert len(m.control_tips)==before,'empty grid shows a control tooltip'
    m.click(246,35);before=len(m.control_tips);m.invoke(m.c['move'],m.obj,(16,39));assert len(m.control_tips)==before,'open dropdown exposes covered tabs'
    m.click(246,35)
    m.invoke(m.c['down'],m.obj,(308,441));m.invoke(m.c['drag'],m.obj,(308,505));m.invoke(m.c['up'],m.obj,(308,505))
    hover(25,469,'Change to Block');hover(230,469,'Sort Refine');hover(120,492,'Lock Storage Transfers')
    m.click(270,492);before=len(m.control_tips);m.invoke(m.c['move'],m.obj,(16,39));assert len(m.control_tips)==before,'closing storage shows a control tooltip'

def lifecycle(exe):
    m=StorageMachine(exe,native_create=True)
    head=m.r(m.obj+0x50);node=m.r(head)
    while node!=head:
        child=m.r(node+8);assert m.r(child+0x28)==int(child==m.editor);node=m.r(node)
    m.invoke(m.r(m.r(m.editor)+25*4),m.editor,(3,3));assert m.r(0x131F4E8+0x1A0)==m.editor
    m.w(0x131F4E8+0x19C,m.obj);m.invoke(m.c['destroy'],m.obj,(1,));assert m.r(m.c['state'])==0 and m.r(0x131F4E8+0x1A0)==0 and m.r(0x131F4E8+0x19C)==0
    m.obj=m.alloc(0x194);m.invoke(m.c['construct'],m.obj);m.setsize(m.obj,280,458);m.invoke(m.c['create'],m.obj,(280,458));assert m.r(m.c['state'])==m.obj
    m.invoke(m.c['destroy'],m.obj,(1,));m.missing.add('bg.png');m.obj=m.alloc(0x194);m.invoke(m.c['construct'],m.obj);assert m.r(m.obj)==0x103CA40

def factory(exe):
    m=StorageMachine(exe,native_create=True);m.invoke(m.c['destroy'],m.obj,(1,))
    m.stub(0x7A84A0,lambda:m.ret(4,0));m.stub(0x7A85A0,lambda:m.ret(4,0))
    for address in [0xA2D220,0xA2D240,0xA4CCF0,0xA39130]:m.stub(address,lambda:m.ret(4))
    head=m.alloc(0x20);node=m.alloc(0x20)
    for off in [0,4,8]:m.w(head+off,node);m.w(node+off,head)
    m.u.mem_write(head+13,b'\1');m.w(node+16,33);m.w(0x131F4E8+8,head);m.w(0x131F4E8+12,1)
    head=m.alloc(12);m.w(head,head);m.w(head+4,head);m.w(0x131F4E8+0x17C,head)
    m.invoke(0xA39340,0x131F4E8,(33,));m.obj=m.u.reg_read(UC_X86_REG_EAX);assert m.obj==m.r(m.c['state']) and m.r(m.obj)==m.r(m.c['api']+4)
    assert (m.r(m.obj+20),m.r(m.obj+24))==(312,445)
    m.editor=m.r(m.obj+0xf0);return m

def native_events(m):
    m.u.hook_del(m._machine_stubs.pop(0x9544F0));m.action_boundaries();m.stub(0xA2E770,lambda:(m.closed.append(m.args(1)[0]),m.ret(4)))
    m.stub(0x96B660,lambda:m.ret(0,1));m.stub(0x96C560,lambda:m.ret(0));m.stub(0xA4CCF0,lambda:m.ret(4))
    config=m.alloc(32);m.w(config+8,280);m.w(config+12,458)
    m.invoke(m.c['event'],m.obj,(0,0x22,config,0,0,0));assert m.r(m.obj+0x164)==config and m.r(m.obj+24)==445
    error=m.alloc(4);proc=m.alloc(16);m.stub(proc,lambda:m.ret(0,error));m.w(0xFC1998,proc)
    def strtol():
        ptr,end,base=m.args(3);s=m.cstr(ptr);m.w(end,ptr+len(s));m.ret(0,int(s,base))
    proc=m.alloc(16);m.stub(proc,strtol);m.w(0xFC1834,proc);m.stub(0xA7ED80,lambda:m.ret(4,0))
    m.stub(0x93A480,lambda:m.ret(0,m.message)) # CRT display formatting only.
    m.rows([(10,501,0,2,0),(11,1201,4,1,3)]);m.w(m.obj+0x180,0)
    m.invoke(m.c['event'],m.obj,(0,0x17,0,0,0,0));assert m.r(m.obj+0xEC)==1
    m.w(m.obj+0x180,2);m.invoke(m.c['event'],m.obj,(0,0x17,0,0,0,0));assert m.r(m.obj+0xEC)==1
    node=m.r(m.r(m.obj+0xE8));assert m.r(node+8+4)==11 and m.r(node+8+0x60)==3
    m.invoke(m.c['event'],m.obj,(0,0x37,2,600,0,0));assert m.r(m.obj+0x188)==2 and m.r(m.obj+0x18C)==600
    for kind,event in [(1,0x37),(9,0x4f)]:
        m.w(m.mode+0x308,kind);m.w(m.mode+0x30c,11);m.w(m.mode+0x318,3)
        m.invoke(m.c['event'],m.obj,(0,0x26,0,0,0,0));assert m.actions[-2:]==[('mode',(event,11,3,0,0)),('mode',(0x12,0,0,0,0))]
    m.w(0x121333C,m.mode);m.click(270,428);assert m.actions[-1]==('mode',(0x39,0,0,0,0)) and m.closed==[*range(0x92,0x99),0x135,0x99]

def categories(m):
    expected=[(0,1),(1,1),(2,1),(3,4),(4,2),(5,3),(6,5),(7,4),(8,3),(9,3),(10,6),(11,2),(12,2),(13,2),(14,2),(15,3),(16,6),(17,6),(18,11),(19,6)]
    m.rows([(1,1201,4,1,0)]);item=m.items[0]
    for kind,cat in expected:
        m.w(item,kind)
        for chosen in [0,1,2,3,4,5,6,7,8,9,11]:
            m.invoke(m.c['category'],0,(item,1201,chosen));assert m.u.reg_read(UC_X86_REG_EAX)==int(chosen in (0,cat)),(kind,chosen)
    for mask,category in [(0x10000,8),(0x200000,8),(0x400,7),(0x2000,7)]:
        m.w(item+8,mask);m.invoke(m.c['category'],0,(item,1201,category));assert m.u.reg_read(UC_X86_REG_EAX)==1
    m.w(item+8,0);info=m.alloc(0x100);m.iteminfo[1201]=info;m.w(info+0x84,1);m.invoke(m.c['category'],0,(item,1201,7));assert m.u.reg_read(UC_X86_REG_EAX)==1;m.w(info+0x84,0)
    for id,values in [(2001,m.eggs),(2002,m.pet_accessories)]:
        values.add(id);m.invoke(m.c['category'],0,(item,id,9));assert m.u.reg_read(UC_X86_REG_EAX)==1
    # Native item-info selects the visible unidentified/identified name.
    m.u.mem_write(info+4,b'Unknown Knife\0');m.w(info+20,13);m.w(info+24,15)
    m.u.mem_write(info+0x40,b'Knife\0');m.w(info+0x50,5);m.w(info+0x54,15)
    m.w(m.c['state']+8,0);m.u.mem_write(item+0x5c,b'\0');m.search('Unknown');m.draw();assert m.r(m.c['state']+24)==1
    m.search('Knife');m.draw();assert m.r(m.c['state']+24)==1
    m.search('Unknown');m.u.mem_write(item+0x5c,b'\1');m.draw();assert m.r(m.c['state']+24)==0

def pet_cache(exe):
    m=StorageMachine(exe);m.w(m.c['state']+8,2);m.rows([(10,1201,4,1,0),(11,1201,4,1,9)]);m.draw();m.draw();assert m.pet_calls==[1,1]
    m.rows([(12,2225,4,1,0)]);m.draw();assert m.pet_calls==[2,2]
    m.rows([(13,1201,4,1,0)]);m.draw();assert m.pet_calls==[3,3]
    m.invoke(m.c['destroy'],m.obj,(1,));m.obj=m.alloc(0x194);m.invoke(m.c['construct'],m.obj);m.invoke(m.c['create'],m.obj,(280,458));m.u.mem_write(m.obj+0x190,b'\1');m.w(m.c['state']+8,2);m.draw();assert m.pet_calls==[4,4]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe',type=Path);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    m=StorageMachine(a.exe);s=m.c['state'];assert (m.r(m.obj+20),m.r(m.obj+24))==(312,445)
    assert (m.r(m.editor+28),m.r(m.editor+32),m.r(m.editor+20),m.r(m.editor+24))==(86,30,151,12)
    assert m.r(m.editor)==m.r(m.c['api']+8)
    values=[(10,501,0,1,0),(11,1201,4,1,9),(12,1201,4,1,2),(13,502,2,7,0),(14,4001,6,2,0),(15,512,0,3,0)]
    m.rows(values);m.draw(a.output/'storage-list.png')
    assert m.select(70,60)==10 and m.select(70,92)==11 and m.select(70,124)==12
    assert m.select(70,300)==0 and m.select(10,60)==0 and m.select(70,400)==0
    # Original CItem copying preserves slot identity and complete refine/cards.
    m.w(m.items[1]+0x1c,0x12345678);m.draw();assert m.select(70,92)==11 and m.r(m.out+0x60)==9 and m.r(m.out+0x1c)==0x12345678
    # Server change between draw and click invalidates that displayed item.
    m.w(m.items[1]+4,99);assert m.select(70,92)==0;m.w(m.items[1]+4,11);m.draw()
    m.search('kNiFe');assert m.select(70,60)==0;m.draw(a.output/'storage-search.png');assert m.r(s+24)==2
    assert m.select(70,60)==11 and m.select(70,92)==12 and m.select(70,124)==0
    m.search('no matches');m.draw(a.output/'storage-empty.png');assert m.r(s+24)==0 and m.select(70,60)==0
    m.search('');m.draw();m.click(230,405);m.draw();assert m.select(70,60)==11 and m.select(70,92)==12
    m.click(230,405);m.draw();assert m.select(70,60)==10 and m.select(70,188)==12
    m.click(230,405);m.click(25,405);m.draw(a.output/'storage-block.png');assert m.r(s+12)==1
    assert [m.select(60+32*i,60) for i in range(6)]==[10,11,12,13,14,15]
    assert m.select(281,60)==0 and m.select(60,92)==0
    m.rows([(i+1,501,0,1,0) for i in range(91)]);m.draw();m.invoke(m.c['wheel'],m.obj,(0xffffff88,));m.draw();assert m.r(s+20)==3 and m.select(60,60)==22
    m.search('no match');m.draw();assert m.r(s+20)==0
    # All eleven native categories remain reachable; the unsupported sticker
    # entry from the newer artwork is removed from both drawing and hit map.
    for row,cat in enumerate([0,1,2,3,4,5,6,7,8,9,11]):m.invoke(m.c['hit'],0,(16,39+row*30));assert m.u.reg_read(UC_X86_REG_EAX)==10+cat
    m.click(270,428);assert m.closed==[m.obj]
    categories(StorageMachine(a.exe));native_callbacks(StorageMachine(a.exe,native_create=True));control_tooltips(StorageMachine(a.exe,native_create=True));lifecycle(a.exe);native_events(factory(a.exe));pet_cache(a.exe)
    print('PASS StorageUI native factory/ctor/OnCreate/children/destructor/reopen/fallback, original CItem copy/cards/refine, stale-row suppression, visible-name search, empty results, stable refine sorting, list/block hits, scroll/clamp, eleven native categories, original drag/tooltip/description/withdraw callbacks, native update/count/close events, editor focus/release, original asset rendering, x86 ABI. Live game acceptance pending.')

if __name__=='__main__':main()
