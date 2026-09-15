"""Execute emitted GCHA x86 against explicit native UI/transport boundary doubles.

Offline evidence only; preview is not a live game screenshot.
"""
import argparse
from pathlib import Path
import struct
import io
import re
from PIL import Image, ImageDraw, ImageFont
from unicorn.x86_const import *
from unicorn import UC_HOOK_CODE
from test_modern_chat_ui import Machine, pack

FIELDS = ('state draw hit down up move cursor drag open receiver sender timer start stop destroy vtable fill fit resolver blit packetSize packetCtor packetSend '
          'itemHit rightDown rightUp spinOffset rightOffset rollLead revealStep rollIds rollCount plain png plainCenter').split()

def contract(m):
    data=m.pe.get_memory_mapped_image(); marker=data.find(b'GachaUI.v20\0');version=9
    if marker<0: marker=data.find(b'GachaUI.v19\0');version=8
    if marker<0: marker=data.find(b'GachaUI.v17\0')
    if marker<0: marker=data.find(b'GachaUI.v16\0')
    if marker<0: marker=data.find(b'GachaUI.v15\0');version=7
    if marker<0: marker=data.find(b'GachaUI.v14\0')
    if marker<0: marker=data.find(b'GachaUI.v13\0');version=6
    if marker<0: marker=data.find(b'GachaUI.v12\0')
    if marker<0: marker=data.find(b'GachaUI.v11\0')
    if marker<0: marker=data.find(b'GachaUI.v10\0');version=5
    if marker<0: marker=data.find(b'GachaUI.v9\0')
    if marker<0: marker=data.find(b'GachaUI.v8\0');version=4
    if marker<0: marker=data.find(b'GachaUI.v7\0')
    if marker<0: marker=data.find(b'GachaUI.v6\0')
    if marker<0: marker=data.find(b'GachaUI.v5\0');version=3 if marker>=0 else 2
    if marker<0: marker=data.find(b'GachaUI.v4\0') # reproduce the reported v4 capture crash
    assert marker>=0, 'GachaUI was not applied'
    key=pack(m.base+marker); places=[]; pos=0
    while (pos:=data.find(key,pos))>=0: places.append(m.base+pos); pos+=1
    assert len(places)==1, places
    return {**{name:m.r(places[0]+4+4*i) for i,name in enumerate(FIELDS)},'wireVersion':version}

def snapshot(message=1,request=0,session=77,token=0,view=0,page=1,pages=None,has_next=None,admin=False):
    p=bytearray(3788)
    pages=pages if pages is not None else (10 if view in (2,3,4) else 1)
    struct.pack_into('<HHIHH',p,0,0xBF6,len(p),0x41484347,9,message)
    has_next=(view!=0 and page<pages) if has_next is None else has_next
    struct.pack_into('<13I',p,12,request,session,token,1|(2 if token else 0)|(8 if has_next else 0)|(16 if admin else 0),1000000,54321000,12,50,100,9850,12,view,12)
    def text(off,size,value): p[off:off+size]=value.encode()[:size-1].ljust(size,b'\0')
    for off,size,value in [(64,48,'Zeny Gacha'),(112,128,'12/12 rewards delivered | Spent 10,000,000 Zeny.' if view==0 else ''),
        (240,32,'54,321,000 Zeny'),(272,64,'x1 : 1,000,000z| x5 : 5,000,000z| x10 : 10,000,000z'),
        (336,96,'10 paid + 2 free = 12 rolls for 10,000,000 Zeny?'),(432,32,'0.50%'),(464,32,'1.00%'),
        (496,32,'98.50%'),(528,128,'Grand guaranteed within 100 pulls; Major or better within 10. Pity saves per character.'),
        (1840,96,'Grand: 37/100 | Major+: 3/10'),(3496,32,f'Page {page} / {pages}')]: text(off,size,value)
    struct.pack_into('<4I',p,1824,37,3,100,10)
    struct.pack_into('<3I',p,656,2289,1716,1715)
    struct.pack_into('<6I',p,3472,2270,501,page,pages,10,2)
    for i,name in enumerate(('Grand','Major','Minor')):text(3528+i*24,24,name)
    struct.pack_into('<I',p,3660,3)
    text(3604,32,'0.00%');text(3636,24,'Legendary');text(3664,64,'1,000,000 per pull');text(3728,48,'Featured Grand prizes')
    ids=[2289,1716,1715,40001,40002,501,14003,14533,14592,12210,501,12210]
    names=['Crown','Gakkung Bow','Arbalest','Paragon Token','Infinite Flywing Box (4 Hours)','Red Potion',
        'Battle Manual','Insurance','Job Manual','Bubble Gum','Red Potion','Bubble Gum']
    for i,(id,name) in enumerate(zip(ids,names)):
        off=672+i*96; tier=0 if i<3 else 1 if i<6 else 2
        struct.pack_into('<4I',p,off,id,1,tier,2 if i>=10 else 0); text(off+16,48,name); text(off+64,32,('FREE | ' if i>=10 else 'x1 | ')+['Grand','Major','Minor'][tier])
        text(1936+i*128,128,'DevSeara' if i==0 else 'Extended Character Name '+str(i))
        if view==3:
            struct.pack_into('<I',p,off,0);text(off+16,48,f'Rank #{(page-1)*12+i+1}');text(off+64,32,'1,000,000 Zeny')
    if view==5:
        p[672:1824]=bytes(1152);struct.pack_into('<I',p,52,0)
        if message==8:text(336,96,"Reset THIS machine's records and every character's pity for it?")
    if message==5:
        p[672:1824]=bytes(1152)
        struct.pack_into('<I',p,668,1020)
    return p

def step_snapshot(message, request, count, revealed, delay=220):
    """Wire v3: real IDs only in stopped slots; other slots remain unknown."""
    p=snapshot(message,request)
    struct.pack_into('<I',p,24,1|(revealed<<16))
    struct.pack_into('<I',p,36,count)
    struct.pack_into('<I',p,52,count)
    paid={1:1,6:5,12:10}[count]
    struct.pack_into('<2I',p,3488,paid,count-paid)
    struct.pack_into('<I',p,668,delay)
    p[672+revealed*96:1824]=bytes(1152-revealed*96)
    status=f'{revealed}/{count} rewards delivered' if message!=7 else f'Reward {revealed}/{count}'
    p[112:240]=status.encode().ljust(128,b'\0')
    return p

class GachaMachine(Machine):
    def stub(self,address,fn):
        if address in self.boundaries: self.u.hook_del(self.boundaries[address])
        self.boundaries[address]=self.u.hook_add(UC_HOOK_CODE,lambda u,a,size,data:fn(),begin=address,end=address)
    def invoke(self,address,obj,args=()):
        sp=0x3000F000
        self.u.mem_write(sp,pack(self.stop)+b''.join(pack(a) for a in args))
        saved=[(UC_X86_REG_EBX,0xBBBBBBBB),(UC_X86_REG_ESI,0xEEEEEEEE),
               (UC_X86_REG_EDI,0xFFFFFFFF),(UC_X86_REG_EBP,0xABABABAB)]
        for reg,value in saved:self.u.reg_write(reg,value)
        self.u.reg_write(UC_X86_REG_ECX,obj);self.u.reg_write(UC_X86_REG_ESP,sp)
        try:
            self.u.emu_start(address,self.stop,count=60000000)
            assert self.u.reg_read(UC_X86_REG_EIP)==self.stop,'did not return'
            assert self.u.reg_read(UC_X86_REG_ESP)==sp+4+len(args)*4,'stack imbalance'
            for reg,value in saved:assert self.u.reg_read(reg)==value,'callee-save corruption'
        except Exception:
            print('FAILED',hex(address),'EIP',hex(self.u.reg_read(UC_X86_REG_EIP)),
                  'ESP',hex(self.u.reg_read(UC_X86_REG_ESP)), 'recent text',self.texts[-3:])
            print('contract',self.c)
            raise
    def __init__(self,exe):
        self.boundaries={}
        self.text_colors=[]
        super().__init__(exe,Path('.')); self.c=contract(self); self.sent=[]; self.now=1000
        self.font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',12)
        self.lookups=[]
        def missing_icon(): self.lookups.append(self.args(1)[0]);self.ret(4,0)
        self.stub(self.c['resolver'],missing_icon) # explicitly missing runtime artwork
        self.stub(0xA21C90,self.measure)
        self.stub(self.c['packetCtor'],lambda:self.ret(0,0x20100000))
        self.stub(self.c['packetSend'],self.send)
        self.stub(0xA4B750,self.capture)
        self.stub(0xA32E00,lambda:self.ret(0,self.r(0x131F4E8+0x19C)))
        self.stub(0xA764A0,lambda:self.forward('cursor',1))
        self.stub(0xA23470,lambda:self.ret(8)) # native tooltip reset, retained before our cursor/tooltip
        self.stub(0xC9E1DD,lambda:self.ret(0))
        tick=self.alloc(16);self.stub(tick,lambda:self.ret(0,self.now));self.w(0xFC17B0,tick)
        # Run the emitted timer lifecycle, doubling only the Windows API boundary.
        self.timer_calls=[]
        self.timer_set=self.alloc(16);self.timer_kill=self.alloc(16)
        def set_timer():
            values=self.args(4);assert values==[0,0,100,self.c['timer']],values
            self.timer_calls.append(('set',values));self.ret(16,567)
        def kill_timer():
            values=self.args(2);assert values==[0,567],values
            self.timer_calls.append(('kill',values));self.ret(8,1)
        self.stub(self.timer_set,set_timer);self.stub(self.timer_kill,kill_timer)
        def module():
            assert self.cstr(self.args(1)[0])=='user32.dll';self.ret(4,0x76540000)
        def proc():
            module_id,name=self.args(2);assert module_id==0x76540000
            name=self.cstr(name);assert name in ('SetTimer','KillTimer')
            self.ret(8,self.timer_set if name=='SetTimer' else self.timer_kill)
        for name,boundary in ((b'GetModuleHandleA',module),(b'GetProcAddress',proc)):
            imports=[i.address for entry in self.pe.DIRECTORY_ENTRY_IMPORT for i in entry.imports if i.name==name]
            assert len(imports)==1,(name,imports)
            address=self.alloc(16);self.stub(address,boundary);self.w(imports[0],address)
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0x86B950,lambda:self.ret(4))
        self.stub(0xA2D240,lambda:self.ret(4))
        self.stub(0x880AD0,lambda:self.forward('drag-down',2))
        self.stub(0x880BB0,lambda:self.forward('drag-up',2))
        self.stub(0x880E00,lambda:self.forward('drag-move',2))
        if self.c['wireVersion']>=4:self.plain_boundaries()
    def plain_boundaries(self):
        # Execute the real private name helper, double only native surface/font
        # acquisition and raw GDI. Shared native TextDraw/tooltip cannot own names.
        self.plain_calls=[];self.gdi_color=0x123456
        def context():
            ptr=self.u.reg_read(UC_X86_REG_ECX);self.w(ptr,self.args(1)[0]);self.ret(4,ptr)
        self.stub(0x5443C0,context);self.stub(0x5446F0,lambda:self.ret(0))
        self.stub(0x546F60,lambda:self.ret(16));self.stub(0x546270,lambda:self.ret(20,99))
        def wide(ptr,n):return bytes(self.u.mem_read(ptr,n*2)).decode('utf-16le')
        def convert():
            cp,flags,ptr,n,dst,cap=self.args(6);assert cp==65001
            data=bytes(self.u.mem_read(ptr,n)).decode('utf8').encode('utf-16le');assert len(data)//2<=cap
            self.u.mem_write(dst,data);self.ret(24,len(data)//2)
        def extent():
            dc,ptr,n,out=self.args(4);self.w(out,int(self.font.getlength(wide(ptr,n))));self.w(out+4,12);self.ret(16,1)
        def color():
            dc,value=self.args(2);old=self.gdi_color;self.gdi_color=value;self.ret(8,old)
        def draw():
            surf,x,y,ptr,n=self.args(5);value=wide(ptr,n);self.plain_calls.append(value)
            self.texts.append((value,x,y,self.gdi_color))
            w,h=self.r(surf+4),self.r(surf+8);pix=self.r(surf+0x18)
            im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA')
            col=self.gdi_color;ImageDraw.Draw(im).text((x,y),value,font=self.font,fill=(col&255,col>>8&255,col>>16&255,255))
            self.u.mem_write(pix,im.tobytes('raw','BGRA'));self.ret(20,1)
        for iat,fn in [(0xFC1200,convert),(0xFC1120,lambda:self.ret(8,88)),(0xFC112C,extent),(0xFC10E0,color),(0xFC10DC,draw)]:
            address=self.alloc(16);self.stub(address,fn);self.w(iat,address)
    def load_texture(self,name):
        if (name.startswith('arrow_') or name=='itembox_000.png'):
            old=self.assets;self.assets=Path(__file__).resolve().parents[1]/'Assets/GachaUI'
            try:return super().load_texture(name)
            finally:self.assets=old
        return super().load_texture(name)
    def measure(self):
        ptr,length,*_=self.args(6);value=self.cstr(ptr)
        self.ret(24,int(self.font.getlength(value[:length] if length else value)))
    def right(self,obj,xy,release=False):
        # Execute the actual native WindowManager indirect dispatch instruction,
        # not a private method pointer (the old test missed a wrong vtable slot).
        site=0xA46F32 if release else 0xA46ECD
        self.w(0x11e40e8,3 if release else 1)
        self.stub(site+6,lambda:self.ret(8))
        code=self.alloc(32)
        prefix=b'\xff\x74\x24\x08\xff\x74\x24\x08\x8b\x01\xe9'
        self.u.mem_write(code,prefix+pack(site-(code+len(prefix)+4)))
        self.invoke(code,obj,xy)
    def capture(self): self.w(0x131F4E8+0x19C,self.args(1)[0]);self.ret(4)
    def send(self):
        length,ptr=self.args(2); assert length==32
        self.sent.append(bytes(self.u.mem_read(ptr,length)));self.ret(8)
    def client_artwork(self,game):
        from dual_weapon_formats.grf_reader import GrfFile
        data=(game/'System/itemInfo.lua').read_bytes()
        archives=[GrfFile(game/name) for name in ('pdata.grf','mdata.grf','maindata.grf','data.grf') if (game/name).is_file()]
        self.real_icons={};self.item_nodes={}
        prefix=bytes.fromhex('c0afc0fac0cec5cdc6e4c0ccbdb a'.replace(' ',''))
        try:
            for item in (1161,2289,1716,1715,2270,40001,40002,501,14003,14533,14592,12210):
                block=re.search(rb'\n\t\['+str(item).encode()+rb'\] = \{(.*?)(?=\n\t\[\d+\] = |\Z)',data,re.S)
                if not block:continue
                resource=re.search(rb'\n\s+identifiedResourceName = "([^"]+)"',block[1])
                if not resource:continue
                key=resource[1]
                archive_key=(b'data/texture/'+prefix+b'/item/'+key+b'.bmp').decode('cp949').lower()
                raw=next((blob for archive in archives if (blob:=archive.read(archive_key)) is not None),None)
                if raw is None:continue
                self.real_icons[key.decode('latin1')+'.bmp']=raw
                node=self.alloc(0xB0);self.item_nodes[item]=node
                if len(key)<16:self.u.mem_write(node+0x58,key+b'\0');capacity=15
                else:
                    address=self.alloc(len(key)+1);self.u.mem_write(address,key+b'\0');self.w(node+0x58,address);capacity=len(key)
                self.w(node+0x68,len(key));self.w(node+0x6C,capacity)
        finally:
            for archive in archives:archive.close()
        # Exercise the actual emitted item resolver, with only the native DB lookup doubled.
        self.u.hook_del(self.boundaries.pop(self.c['resolver']))
        address=self.c['resolver']
        self.boundaries[address]=self.u.hook_add(UC_HOOK_CODE,lambda u,a,size,data:self.lookups.append(self.args(1)[0]),begin=address,end=address)
        self.w(0x159C088,self.alloc(32))
        self.stub(0xA7E780,lambda:self.ret(4,self.item_nodes.get(self.r(self.args(1)[0]),0)))
        def format_path():
            dest,fmt,key=self.args(3)
            value=self.cstr(fmt).replace('%s',self.cstr(key)).encode('latin1')
            self.u.mem_write(dest,value+b'\0');self.ret(0,len(value))
        self.stub(0x529850,format_path)
        def texture():
            key=self.cstr(self.args(1)[0]).split('\\')[-1]
            if (key.startswith('arrow_') or key=='itembox_000.png'):self.ret(4,self.load_texture(key));return
            if key not in self.real_icons:self.ret(4,0);return
            if key not in self.textures:
                image=Image.open(io.BytesIO(self.real_icons[key])).convert('RGBA');w,h=image.size
                descriptor=self.alloc(0x130);pixels=self.alloc(w*h*4)
                self.u.mem_write(pixels,image.tobytes('raw','BGRA'))
                for off,value in [(0x110,1),(0x114,w),(0x118,h),(0x11C,pixels)]:self.w(descriptor+off,value)
                self.textures[key]=descriptor
            self.ret(4,self.textures[key])
        self.stub(0xA8D4A0,texture)
        print('Loaded',len(self.real_icons),'actual client item BMPs from GRFs (no game files changed)')
    def text(self):
        obj=self.u.reg_read(UC_X86_REG_ECX);x,y,ptr,length,_,height,color,bold,_=self.args(9)
        string=self.cstr(ptr);string=string[:length] if length else string; self.texts.append((string,x,y,obj))
        self.text_colors.append((string,color,x,y))
        pix,w,h=self.pixels(obj);assert x<w and y<h,(string,x,y,w,h)
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pix,w*h*4)),'raw','BGRA')
        font=ImageFont.truetype('C:/Windows/Fonts/tahomabd.ttf' if bold else 'C:/Windows/Fonts/tahoma.ttf',height)
        ImageDraw.Draw(im).text((x,y-2),string,font=font,fill=(color&255,(color>>8)&255,(color>>16)&255,0))
        self.u.mem_write(pix,im.tobytes('raw','BGRA')); self.ret(36)
    def receive(self,p):
        # Always enter through the on-disk native dispatcher. Calling the private
        # receiver directly concealed the Battlepass/Gacha overwrite regression.
        self.u.mem_write(0x15E8198,bytes(p)); self.invoke(self.r(0xCAD0EC),0)
    def ready(self):
        p=snapshot()[:self.c['packetSize']];struct.pack_into('<H',p,2,len(p));struct.pack_into('<H',p,8,self.c['wireVersion'])
        if self.c['wireVersion']<6:
            p=p[:self.c['packetSize']];struct.pack_into('<H',p,2,len(p))
        if self.c['wireVersion']<5:
            struct.pack_into('<I',p,36,10);struct.pack_into('<I',p,52,10)
        self.receive(p); obj=self.r(self.c['state']); assert obj
        assert self.r(obj)==self.c['vtable']
        return obj

def rolling_tests(exe):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    p=snapshot(5);m.receive(p);origin=m.now
    frames=[]
    for elapsed in (0,100,200,c['rollLead']):
        m.now=origin+elapsed;m.invoke(c['timer'],0,(0,0,0,0))
        assert m.r(s+24)==0
        m.lookups=[];m.texts=[];m.invoke(c['draw'],obj)
        assert not any(y in (143,159,219,235,295,311,182,258,334) for _,x,y,_ in m.texts),'name/quantity/rarity leaked early'
        assert any(text=='Rolling...' for text,_,_,_ in m.texts)
        assert len(m.lookups)==17,m.lookups # 5 featured + 12 independent stand-ins
        frames.append(m.lookups[5:])
        before=len(m.sent);m.invoke(c['down'],obj,(705,395));m.invoke(c['up'],obj,(705,395));assert len(m.sent)==before
        m.right(obj,(30,149));m.right(obj,(30,149),True);assert m.r(s+c['rightOffset'])==0
        m.invoke(c['cursor'],obj,(30,149));assert m.forwards[-1]==('cursor',[0])
    assert frames[0]!=frames[1] and frames[1]!=frames[2],'icons did not cycle'
    assert m.r(c['vtable']+32*4)==c['rightDown'] and m.r(c['vtable']+33*4)==c['rightUp']
    assert m.r(c['vtable']+26*4)==0x5A8680,'unrelated slot 26 must stay native'
    for count in (1,6,12):
        m.receive(step_snapshot(5,m.r(s+44),count,0,1020))
        for index in range(1,count+1):
            duration=1020 if index==1 else 220
            before=len(m.sent);origin=m.now
            m.now=origin+duration-1;m.invoke(c['timer'],0,(0,0,0,0))
            assert len(m.sent)==before and m.r(s+3852)==1 and m.r(s+24)==index-1
            m.now+=1;m.invoke(c['timer'],0,(0,0,0,0))
            assert len(m.sent)==before+1 and m.r(s+3852)==2
            fields=struct.unpack('<HHIHH5I',m.sent[-1])
            assert fields[3]==9 and fields[4]==6 and fields[7:]==(0,index,0),fields
            spin=m.r(s+56)
            m.now+=100;m.invoke(c['timer'],0,(0,0,0,0))
            assert len(m.sent)==before+1 and m.r(s+56)!=spin,'remaining icons froze while awaiting server'
            # Reveal is queued before the matching inventory packet. A delayed
            # delivery ACK must not permit the next slot, retries or a new pull.
            m.receive(step_snapshot(7,m.r(s+44),count,index))
            assert m.r(s+24)==index and m.r(s+3852)==2 and m.r(s+16)==1
            m.now+=7000;m.invoke(c['timer'],0,(0,0,0,0))
            assert len(m.sent)==before+1 and m.r(s+3852)==2
            if count==12 and index in (1,6,12):
                m.lookups=[];m.texts=[];m.invoke(c['draw'],obj)
                labels=[t for t,x,y,_ in m.texts if y in (143,219,295) and x>40]
                assert len(labels)==index,(index,labels)
                assert labels[0]=='Crown'
            message=6 if index<count else 4
            m.receive(step_snapshot(message,m.r(s+44),count,index))
            assert m.r(s+24)==(index if index<count else 12)
            assert m.r(s+3852)==(1 if index<count else 0) and m.r(s+16)==0
        m.lookups=[];m.texts=[];m.invoke(c['draw'],obj)
        assert any(t[0]=='Crown' for t in m.texts)
    # Timer failure never requests a paid completion. Closing remains possible.
    m.invoke(c['stop'],obj);before=len(m.sent);m.receive(snapshot(5,m.r(s+44)))
    assert m.r(s+3852)==2 and len(m.sent)==before
    # timeGetTime wraps without extending the roll or dividing by a bad denominator.
    m.invoke(c['start'],obj);m.now=0xffffff00;m.receive(snapshot(5,m.r(s+44)))
    m.now=(m.now+1020)&0xffffffff;m.invoke(c['timer'],0,(0,0,0,0));assert m.r(s+3852)==2 and len(m.sent)==before+1
    m.invoke(c['down'],obj,(746,9));m.invoke(c['up'],obj,(746,9))
    assert m.r(s+32)==0 and m.r(s+20)==1
    print('PASS: x1/x5/x10 ordered slot requests; reveal/label then delivery ACK before next slot; remaining icons keep spinning; no hidden IDs/retry/double animation; timer failure/wrap/close safety')

def item_description_tests(exe):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    names=m.alloc(16);m.u.mem_write(names,b'item\0');m.stub(c['resolver'],lambda:m.ret(4,names))
    description=m.alloc(0x100);vt=m.alloc(0x100);dispatch=m.alloc(16)
    m.w(description,vt);m.w(vt+0x94,dispatch);constructed=[];destroyed=[];opened=[]
    def ctor():
        item=m.u.reg_read(UC_X86_REG_ECX);m.u.mem_write(item,bytes(0xF8));m.w(item+0x40,15);m.w(item+0x58,15)
        constructed.append(item);m.ret(0,item)
    def format_item():
        dest,fmt,id_=m.args(3);assert m.cstr(fmt)=='%u'
        text=str(id_).encode();m.u.mem_write(dest,text+b'\0');m.ret(0,len(text))
    def show():
        assert m.u.reg_read(UC_X86_REG_ECX)==description
        args=m.args(6);assert args[:2]==[0,24] and args[3:]==[0,0,0]
        item=args[2];assert item==constructed[-1] and bytes(m.u.mem_read(item+0x5c,1))==b'\1'
        id_=m.cstr(item+0x2c);assert m.r(item+0x3c)==len(id_) and m.r(item+0x40)==15
        opened.append(int(id_));m.ret(24)
    def dtor():destroyed.append(m.u.reg_read(UC_X86_REG_ECX));m.ret(0)
    def factory():assert m.args(1)==[12];m.ret(4,description)
    m.stub(0x6A1B20,ctor);m.stub(0x529850,format_item);m.stub(0xA39340,factory);m.stub(dispatch,show);m.stub(0x5A4300,dtor)
    def click(x,y,up=None):
        m.right(obj,(x,y));assert m.r(0x131F4E8+0x19C)==0,'item right-down acquired unsafe native capture'
        m.right(obj,up or (x,y),True)
        assert m.r(s+c['rightOffset'])==0 and m.r(0x131F4E8+0x19C)==0
    ids=[2289,1716,1715,40001,40002,501,14003,14533,14592,12210,501,12210]
    for view in (0,1,2,4):
        m.receive(snapshot(view=view))
        for i,id_ in enumerate(ids):click(30+(i%4)*185,149+(i//4)*76);assert opened[-1]==id_
    for i,id_ in enumerate([2289,1716,1715,2270,501]):click(27+i*35,93);assert opened[-1]==id_
    assert len(opened)==53 and constructed==destroyed and not m.sent
    p=snapshot(view=4)
    for off,id_ in zip((3776,3780,3784),(1161,1201,1202)):struct.pack_into('<I',p,off,id_)
    m.receive(p)
    for i,id_ in enumerate((1161,1201,1202),5):click(27+i*35,93);assert opened[-1]==id_
    assert len(opened)==56 and constructed==destroyed and not m.sent
    m.receive(snapshot(view=4))
    for i in range(5,8):click(27+i*35,93)
    assert len(opened)==56,'empty featured slots opened item descriptions'
    for x,y,up in [(30,149,(90,149)),(30,149,(215,149)),(90,149,None),(450,311,None)]:
        before=len(opened);click(x,y,up);assert len(opened)==before
    # Same item in another slot is still a cancelled right click.
    p=snapshot();struct.pack_into('<I',p,672+96,2289);m.receive(p)
    before=len(opened);click(30,149,(215,149));assert len(opened)==before
    for off in (16,20,52,12,4):
        m.w(s+off,1);before=len(opened);click(30,149);assert len(opened)==before;m.w(s+off,0)
    before=len(opened);m.invoke(c['rightUp'],obj,(30,149));assert len(opened)==before
    m.invoke(c['rightDown'],obj,(30,149));m.receive(snapshot());m.invoke(c['rightUp'],obj,(30,149))
    assert len(opened)==before and m.r(0x131F4E8+0x19C)==0,'fresh snapshot did not cancel capture/identity'
    m.stub(c['resolver'],lambda:m.ret(4,0));click(30,149);assert len(opened)==before
    m.stub(c['resolver'],lambda:m.ret(4,names));m.stub(0xA39340,lambda:m.ret(4,0));click(30,149)
    assert len(opened)==before and constructed==destroyed,'failed description factory leaked temporary CItem'
    # Top-spender rows have no item icons; they cannot expose stale history IDs.
    p=snapshot(view=3)
    for i in range(12):struct.pack_into('<I',p,672+i*96,0)
    m.receive(p);click(30,149);assert len(opened)==before and not m.sent
    print('PASS: native description CItem/ID/identified/message24/lifetime, all featured/prize/result/history icons, same-slot right down/up and cancellation guards, no network purchase')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--preview',type=Path);ap.add_argument('--game',type=Path);args=ap.parse_args()
    m=GachaMachine(args.exe);c=m.c;s=c['state'];obj=m.ready()
    assert m.r(s+32)==567 and len(m.timer_calls)==1
    m.invoke(c['start'],0);assert len(m.timer_calls)==1
    if args.game:m.client_artwork(args.game)
    assert c['packetSize']==3788
    m.invoke(c['draw'],obj)
    assert any(t[0]=='Grand: 37/100 | Major+: 3/10' for t in m.texts)
    assert any(t[0]=='Pull x10' for t in m.texts)
    assert any(t[0].startswith('Infinite Flywing') for t in m.texts)
    for text,x,y,_ in m.texts:
        if y in (143,219,295) and x>40:
            assert m.font.getlength(text)<=124,(text,x,y)
    pix,w,h=m.pixels(obj)
    assert m.r(pix+4*(130*w+10))==0xffffffff
    assert all(v==0 or v>>24==255 for v in struct.unpack('<'+'I'*(w*h),bytes(m.u.mem_read(pix,w*h*4))))
    if args.preview:
        args.preview.parent.mkdir(parents=True,exist_ok=True)
        Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(args.preview)
    print('PASS: native frame, bounded long names, rarity cards, persistent pity text/bar and opaque text; missing icons safe')
    # Invalid wire lengths/versions/counts/tiers/pity denominators cannot alter state.
    for off,fmt,value in [(2,'H',1936),(8,'H',1),(8,'H',2),(8,'H',4),(52,'I',13),(56,'I',5),(680,'I',4),(1832,'I',0),(1836,'I',10001),
                          (3480,'I',0),(3484,'I',0),(3484,'I',101),(3488,'I',6),(3492,'I',3),(36,'I',10)]:
        p=snapshot();struct.pack_into('<'+fmt,p,off,value);before=bytes(m.u.mem_read(s,3856));m.receive(p)
        assert bytes(m.u.mem_read(s,3856))==before,(off,value)
    print('PASS: malformed snapshot rejection and bounded packet-owned strings/counts')
    # Confirm requires server quote: first click only sends a quote request.
    m.invoke(c['down'],obj,(705,395));m.invoke(c['up'],obj,(705,395))
    assert len(m.sent)==1
    fields=struct.unpack('<HHIHH5I',m.sent[-1]);assert fields[4]==1 and fields[8]==10 and fields[6]==77,fields
    m.invoke(c['down'],obj,(705,395));m.invoke(c['up'],obj,(705,395));assert len(m.sent)==1
    seq=m.r(s+44);m.receive(snapshot(3,seq,token=123));assert m.r(s+52)==1
    m.invoke(c['draw'],obj);assert any(t[0]=='10 paid + 2 free = 12 rolls for 10,000,000 Zeny?' for t in m.texts)
    m.invoke(c['down'],obj,(410,275));m.invoke(c['up'],obj,(410,275));assert len(m.sent)==2
    fields=struct.unpack('<HHIHH5I',m.sent[-1]);assert fields[4]==2 and fields[7]==123,fields
    m.invoke(c['down'],obj,(410,275));m.invoke(c['up'],obj,(410,275));assert len(m.sent)==2
    # Keep modal visible while confirmation is in flight; no stale-background flash.
    assert m.r(s+52)==1
    seq=m.r(s+44);m.receive(snapshot(5,seq));assert m.r(s+24)==0 and m.r(s+52)==0
    for index in range(1,13):
        m.now+=1020 if index==1 else 220;m.invoke(c['timer'],0,(0,0,0,0));assert len(m.sent)==index+2
        m.receive(step_snapshot(7,m.r(s+44),12,index));assert m.r(s+24)==index
        m.receive(step_snapshot(6 if index<12 else 4,m.r(s+44),12,index))
    assert m.r(s+24)==12
    print('PASS: quote/confirm token wire, double-click gate, stable confirmation surface, twelve individual reveal/delivery steps')
    # Outside release cancels, only title dragging invokes native movement.
    m.invoke(c['down'],obj,(40,30));m.invoke(c['up'],obj,(500,350));assert len(m.sent)==14
    m.invoke(c['down'],obj,(450,350));assert not any(f[0]=='drag-down' for f in m.forwards)
    m.invoke(c['down'],obj,(450,10));m.invoke(c['drag'],obj,(470,20));m.invoke(c['up'],obj,(470,20))
    assert any(f[0]=='drag-down' for f in m.forwards) and any(f[0]=='drag-move' for f in m.forwards)
    m.invoke(c['cursor'],obj,(700,395));assert m.forwards[-1]==('cursor',[2])
    m.invoke(c['cursor'],obj,(450,350));assert m.forwards[-1]==('cursor',[0])
    m.invoke(c['down'],obj,(746,9));m.invoke(c['up'],obj,(746,9));assert m.r(s+20)==1 and m.r(obj+0x28)==0
    assert m.r(s+32)==0 and [call[0] for call in m.timer_calls]==['set','kill']
    m.invoke(c['stop'],0);assert len(m.timer_calls)==2
    before=bytes(m.u.mem_read(s+64,3788));m.receive(snapshot(4,m.r(s+44)));assert bytes(m.u.mem_read(s+64,3788))==before
    print('PASS: title-only native drag, release-outside cancellation, native hand cursor and late-reply close guard')
    print('PASS: actual timer start/stop helpers, 100ms interval, duplicate-start guard and close cleanup')
    if args.preview:
        m.receive(snapshot());m.receive(snapshot(5));origin=m.now
        for suffix,elapsed in [('rolling',0),('rolling-next',100),('first-reward',1020),('third-reward',1660),('revealed',3200)]:
            m.now=origin+elapsed;m.invoke(c['timer'],0,(0,0,0,0))
            if suffix=='first-reward':m.receive(step_snapshot(6,m.r(s+44),12,1))
            if suffix=='third-reward':m.receive(step_snapshot(6,m.r(s+44),12,3))
            if suffix=='revealed':m.receive(snapshot(4,m.r(s+44)))
            m.invoke(c['draw'],obj)
            pix,w,h=m.pixels(obj)
            Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(args.preview.with_name(args.preview.stem+'-'+suffix+'.png'))
    rolling_tests(args.exe)
    item_description_tests(args.exe)
    pagination_tests(args.exe,args.preview)
    next_page_tests(args.exe,args.preview)
    configurable_text_tests(args.exe,args.preview)
    button_fit_tests(args.exe,args.preview)
    admin_tab_tests(args.exe,args.preview)
    presentation_tests(args.exe,args.preview)
    print('Offline boundary-double tests only. Live game/server acceptance remains required.')

def presentation_tests(exe,preview):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    for view in (1,2,3,4):
        m.receive(snapshot(view=view));m.texts=[];m.invoke(c['draw'],obj)
        assert not any(t[0].startswith('Pull x') for t in m.texts),(view,m.texts)
        before=len(m.sent)
        for x in (590,650,705):
            m.invoke(c['down'],obj,(x,395));m.invoke(c['up'],obj,(x,395))
            m.invoke(c['cursor'],obj,(x,395));assert m.forwards[-1]==('cursor',[0])
        assert len(m.sent)==before
        if view in (3,4):assert any(t[0]=='DevSeara' for t in m.texts),'short character name was truncated'
        if preview and view in (3,4):
            pix,w,h=m.pixels(obj)
            Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview.with_name(preview.stem+f'-view{view}.png'))
    # Pending data keeps the entire existing frame stable (no gray flash or waiting label).
    m.receive(snapshot());m.w(s+8,0);m.invoke(c['draw'],obj);pix,w,h=m.pixels(obj)
    before=bytes(m.u.mem_read(pix,w*h*4));m.w(s+16,1);m.texts=[];m.invoke(c['draw'],obj)
    assert before==bytes(m.u.mem_read(pix,w*h*4))
    assert not any('Waiting for server' in t[0] for t in m.texts)
    m.w(s+16,0)
    # Names are centered in winner strips; hovering names must not draw any popup.
    full='DevSeara '+('Long Character Name '*7);full=full[:127]
    p=snapshot(view=4);p[1936:2064]=full.encode().ljust(128,b'\0');m.receive(p)
    tooltip=[];m.w(0x121333C,m.alloc(0x100))
    m.stub(0xA1EF70,lambda:m.ret(8)) # screen-coordinate conversion only
    def show_tip():tooltip.append(m.cstr(m.args(6)[0]));m.ret(24)
    m.stub(0xA753D0,show_tip)
    m.invoke(c['draw'],obj);pix,w,h=m.pixels(obj);before=bytes(m.u.mem_read(pix,w*h*4))
    m.invoke(c['cursor'],obj,(30,185));assert not tooltip
    m.texts=[];m.invoke(c['draw'],obj);assert any(t.startswith('DevSeara ') for t in m.plain_calls)
    assert before==bytes(m.u.mem_read(pix,w*h*4)),'name hover changed the frame'
    assert not any(y==364 for _,x,y,_ in m.texts),'name popup still drawn'
    assert m.gdi_color==0x123456,'private text draw leaked HDC color'
    assert m.cstr(s+64+1936)==full
    for view in (3,4):
        m.receive(snapshot(view=view));m.texts=[];m.invoke(c['draw'],obj)
        for i in range(12):
            x=20+(i%4)*185;y=134+(i//4)*76
            name='DevSeara' if i==0 else 'Extended Character Name '+str(i)
            row=next(t for t in m.texts if t[0]==name and t[2]==y+(48 if view==4 else 9))
            expected=x+8+((159-int(m.font.getlength(name)))//2 if view==4 else 0)
            assert row[1]==expected,(view,row,expected)
        before=bytes(m.u.mem_read(pix,w*h*4))
        m.invoke(c['cursor'],obj,(95,185 if view==4 else 150));m.invoke(c['draw'],obj)
        assert not tooltip and before==bytes(m.u.mem_read(pix,w*h*4))
    print('PASS: centered winner names, unchanged spender alignment, no name-hover popup; plain SQL names, bounded text, restored GDI color; stable pending frame')

def pagination_tests(exe,preview):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    for view,pages in [(1,1),(1,2),(1,100),(2,10),(3,10),(4,10)]:
        test_pages=range(1,pages+1) if pages<100 else (1,50,99,100)
        for page in test_pages:
            p=snapshot(view=view,page=page,pages=pages);m.receive(p)
            m.texts=[];m.invoke(c['draw'],obj)
            assert any(t[0]==f'Page {page} / {pages}' for t in m.texts)
            for x,delta,enabled in [(611,-1,page>1),(736,1,page<pages)]:
                m.invoke(c['hit'],0,(x,364));assert bool(m.u.reg_read(UC_X86_REG_EAX))==enabled
                before=len(m.sent);m.invoke(c['down'],obj,(x,364));m.invoke(c['up'],obj,(x,364))
                assert len(m.sent)==before+enabled
                if enabled:
                    fields=struct.unpack('<HHIHH5I',m.sent[-1]);assert fields[3]==9 and fields[4]==3 and fields[8:]==(page+delta,view),fields
                    m.receive(p)
            if preview and page in (1,10,100):
                pix,w,h=m.pixels(obj);Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview.with_name(preview.stem+f'-view{view}-page{page}.png'))
    for view in (1,2,3,4):
        for page in (0,11,0xffffffff):
            p=snapshot(view=view,page=page,pages=10);before=bytes(m.u.mem_read(s,3856));m.receive(p)
            assert bytes(m.u.mem_read(s,3856))==before
    # No icon inset under spender text; plain drawing restores the previous GDI color.
    p=snapshot(view=3);m.receive(p);m.invoke(c['draw'],obj);pix,w,h=m.pixels(obj)
    # y=170 now crosses the updated Zeny fixture glyph; sample the blank gap
    # still inside the former 32px icon inset, above the new rank line.
    assert m.r(pix+4*(171*w+30))==0xfff4fbfd and m.gdi_color==0x123456
    assert 'DevSeara' in m.plain_calls
    print('PASS: 12-slot, ten-page History/Spenders/Winners; 1/2/100-page catalogue; bounded request/receive, edge arrows, full page labels; plain SQL names, no spender inset')

def next_page_tests(exe,preview=None):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    loaded=[];original=m.load_texture
    def track(name):loaded.append(name);return original(name)
    m.load_texture=track
    for view in (1,2,3,4):
        # Include an exactly-full final page: row_count == 12 is not sufficient.
        for page,rows,more in [(1,0,False),(1,3,False),(1,12,False),(1,12,True),(2,12,False),(10,12,True)]:
            p=snapshot(view=view,page=page,pages=10,has_next=more)
            struct.pack_into('<I',p,52,rows);m.receive(p)
            m.texts=[];loaded.clear();m.invoke(c['draw'],obj)
            enabled=more and page<10
            assert ('arrow_on_right.png' if enabled else 'arrow_off_right.png') in loaded,(view,page,rows,more,loaded)
            assert ('arrow_on_left.png' if page>1 else 'arrow_off_left.png') in loaded
            assert any(t[0]==f'Page {page} / 10' for t in m.texts)
            m.invoke(c['cursor'],obj,(736,364));assert m.forwards[-1]==('cursor',[2 if enabled else 0])
            before=len(m.sent);m.invoke(c['down'],obj,(736,364));m.invoke(c['up'],obj,(736,364))
            assert len(m.sent)==before+enabled,(view,page,rows,more)
            if enabled:
                fields=struct.unpack('<HHIHH5I',m.sent[-1]);assert fields[4]==3 and fields[8:]==(page+1,view)
            if preview and page==1 and rows==12 and not more:
                pix,w,h=m.pixels(obj);Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview.with_name(preview.stem+f'-view{view}-no-next.png'))
    # Single-page catalogues retain visible gray arrows, instead of hiding them.
    m.receive(snapshot(view=1,pages=1,has_next=False));loaded.clear();m.invoke(c['draw'],obj)
    assert 'arrow_off_left.png' in loaded and 'arrow_off_right.png' in loaded
    print('PASS: every information tab uses actual next-record flag for arrow PNG, hand cursor and click gate; empty/partial/exact-full final pages disable Next; page cap and single-page gray arrows')


def configurable_text_tests(exe,preview=None):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    p=snapshot()
    def put(off,size,text):p[off:off+size]=text.encode()[:size-1].ljust(size,b'\0')
    names=['Legendary','Rare','Common']
    for i,name in enumerate(names):put(3528+i*24,24,name)
    costs='1=100,000 Zeny | 5=450,003 | 10=850,007'
    footer='Legendary within 80; Rare within 8.'
    put(272,64,costs);put(528,128,footer);put(1840,96,'Legendary: 37/80 | Rare+: 3/8')
    m.receive(p);m.texts=[];m.text_colors=[];m.invoke(c['draw'],obj)
    assert any(t[0]=='1,000,000 per pull' for t in m.texts) and any(t[0]==footer for t in m.texts)
    for i,name in enumerate(names):
        assert any(t[0]==name and t[1:3]==(323,66+(2-i)*13) for t in m.texts)
        assert any(t[0]==name and t[2] in (182,258,334) for t in m.texts)
    rate_x=331+max(int(m.font.getlength(name)) for name in names)
    for i,rate in enumerate(('0.50%','1.00%','98.50%')):
        assert any(t[0]==rate and t[1:3]==(rate_x,66+(2-i)*13) for t in m.texts)
    assert any(t[0]=='Legendary: 37/80 | Rare+: 3/8' and t[1:3]==(503,75) for t in m.texts)
    assert any(t.startswith('Bonus:') and color==0xFF0000 for t,color,x,y in m.text_colors)
    if preview:
        pix,w,h=m.pixels(obj);Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview.with_name(preview.stem+'-configurable.png'))
    # Default, user-suffixed and mixed-length names share a compact aligned rate
    # column, eight pixels after the widest visible alias. Long aliases stay bounded.
    for aliases in [('Grand','Major','Minor'),('Grand1','Major1','Minor1'),('W'*20,'Rare','Common')]:
        for i,name in enumerate(aliases):put(3528+i*24,24,name)
        m.receive(p);m.texts=[];m.invoke(c['draw'],obj)
        visible=[next(t[0] for t in m.texts if t[1:3]==(323,66+(2-i)*13)) for i in range(3)]
        rate_x=331+max(int(m.font.getlength(name)) for name in visible)
        assert rate_x<=441
        for i,rate in enumerate(('0.50%','1.00%','98.50%')):
            assert any(t[0]==rate and t[1:3]==(rate_x,66+(2-i)*13) for t in m.texts)
    # Every new wire string is bounded; long display aliases cannot cover percentages.
    for i in range(3):p[3528+i*24:3528+(i+1)*24]=b'W'*24
    p[528:656]=b'W'*128;p[1840:1936]=b'W'*96;m.receive(p);m.texts=[];m.invoke(c['draw'],obj)
    for i in range(3):assert bytes(m.u.mem_read(s+64+3528+i*24+23,1))==b'\0'
    for text,x,y,_ in m.texts:
        if x==323 and y in (66,79,92):assert m.font.getlength(text)<=110
        if y==419:assert x+m.font.getlength(text)<=740
        if x==503 and y==75:assert m.font.getlength(text)<235
    print('PASS: editable names in pity counter, compact measured name/rate spacing, bounded long labels and descriptions, blue bonus text, terminated wire strings')


def button_fit_tests(exe,preview=None):
    buttons=[(10,'Pull x1',574,385,51,20),(11,'Pull x5',631,385,51,20),
             (12,'Pull x10',688,385,58,20),(20,'Cancel',334,264,49,20),(21,'Pull',393,264,34,20)]
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    for modal in (False,True):
        m.receive(snapshot(3,token=123) if modal else snapshot());m.texts=[];m.text_colors=[]
        m.invoke(c['draw'],obj);pix,w,h=m.pixels(obj)
        group=[b for b in buttons if (b[0]>=20)==modal]
        for id_,label,x,y,bw,bh in group:
            drawn=next(t for t in m.texts if t[0]==label and t[2]==y+4)
            width=int(m.font.getlength(label));left=drawn[1]-x;right=x+bw-drawn[1]-width
            assert bw-width==14 and abs(left-right)<=1 and min(left,right)>=6,(label,drawn,left,right)
            assert m.r(pix+4*((y+bh-4)*w+x+bw-2))==0xFFDEEFFB
            assert m.r(pix+4*((y+bh-4)*w+x+bw+1))==0xFFFFFFFF
            for xy in ((x,y),(x+bw-1,y+bh-1),(x+bw//2,y+bh//2)):
                m.invoke(c['hit'],0,xy);assert m.u.reg_read(UC_X86_REG_EAX)==id_,(label,xy)
            for xy in ((x-1,y+4),(x+bw,y+4),(x+4,y-1),(x+4,y+bh)):
                m.invoke(c['hit'],0,xy);assert m.u.reg_read(UC_X86_REG_EAX)==0,(label,xy)
            m.invoke(c['cursor'],obj,(x+bw//2,y+bh//2));assert m.forwards[-1]==('cursor',[2])
            m.invoke(c['cursor'],obj,(x+bw+1,y+4));assert m.forwards[-1]==('cursor',[0])
        if modal and preview:
            Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview.with_name(preview.stem+'-confirmation.png'))
        m.w(s+3852,1);m.texts=[];m.text_colors=[];m.invoke(c['draw'],obj)
        for _,label,x,y,bw,bh in group:
            assert any(t==label and color==0xACACAC and ty==y+4 for t,color,tx,ty in m.text_colors)
            m.invoke(c['hit'],0,(x+bw//2,y+bh//2));assert m.u.reg_read(UC_X86_REG_EAX)==0
        m.w(s+3852,0)
    # Each shrunken target still maps to the same quote/confirm/cancel action.
    for id_,label,x,y,bw,bh in buttons:
        q=GachaMachine(exe);qc=q.c;qs=qc['state'];qo=q.ready()
        if id_>=20:q.receive(snapshot(3,token=123))
        xy=(x+bw//2,y+bh//2)
        q.invoke(qc['down'],qo,xy);q.invoke(qc['up'],qo,(x+bw+1,y+4));assert not q.sent
        q.invoke(qc['down'],qo,xy);q.invoke(qc['up'],qo,xy);assert len(q.sent)==1
        fields=struct.unpack('<HHIHH5I',q.sent[0])
        assert fields[4]==(1 if id_<20 else 5 if id_==20 else 2),(label,fields)
        if id_<20:assert fields[8]=={10:1,11:5,12:10}[id_]
        elif id_==21:assert fields[7]==123
        else:
            assert q.r(qs+52)==1 # keep the modal stable while cancellation is in flight
            q.receive(snapshot(2,q.r(qs+44)));assert q.r(qs+52)==0
    print('PASS: compact five-button paint/hit bounds, centered padded labels, disabled styling, hand cursors, outside-release cancellation and correct x1/x5/x10/confirm/cancel actions')


def admin_tab_tests(exe,preview=None):
    m=GachaMachine(exe);c=m.c;s=c['state'];obj=m.ready()
    def draw(suffix=None):
        m.texts=[];m.invoke(c['draw'],obj)
        if preview and suffix:
            pix,w,h=m.pixels(obj);Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pix,w*h*4)),'raw','BGRA').save(preview.with_name(preview.stem+'-'+suffix+'.png'))
    def click(x,y):m.invoke(c['down'],obj,(x,y));m.invoke(c['up'],obj,(x,y))
    draw();assert not any(t[0]=='Admin' for t in m.texts)
    click(440,31);click(380,302);assert not m.sent
    for view,description in [(1,'List of Possible Rewards'),(2,'Your Latest Zeny Gacha History'),(3,'Top 12 Zeny Gacha Spenders'),(4,'Total List of Winners')]:
        m.receive(snapshot(view=view));draw('description'+str(view))
        assert not any(t[0]==description or t[2]==389 for t in m.texts)
        assert not any(t[2]>=360 and (t[0].startswith(('Bonus:','x1 :','Grand guaranteed','Pull x')) or 'equally likely' in t[0]) for t in m.texts)
        if view==3:
            assert all(any(t[0]==f'Rank #{i+1}' for t in m.texts) for i in range(12))
        p=snapshot(view=view);p[112:240]=b'History storage is unavailable.'.ljust(128,b'\0');m.receive(p);draw()
        assert any(t[0]=='History storage is unavailable.' and t[1:3]==(20,408) for t in m.texts),'server errors must remain visible'
    m.receive(snapshot(view=3,page=2));draw();assert any(t[0]=='Rank #13' for t in m.texts) and any(t[0]=='Rank #24' for t in m.texts)
    m.receive(snapshot(admin=True));draw();assert any(t[0]=='Admin' for t in m.texts)
    click(440,31);fields=struct.unpack('<HHIHH5I',m.sent[-1]);assert fields[4]==3 and fields[9]==5
    m.receive(snapshot(2,m.r(s+44),view=5,admin=True));draw('admin')
    assert any(t[0]=='Administrator Control Panel' and t[1:3]==(34,150) for t in m.texts)
    assert not any('GM level 99+' in t[0] for t in m.texts)
    assert {x for _,x,y,_ in m.texts if y in (150,180,201,221,253)}=={34},'Admin panel text is not left-aligned'
    assert any(t[0]=='Reset This Machine' for t in m.texts) and not any(t[0].startswith(('Pull x','Page ')) for t in m.texts)
    before=len(m.sent);click(613,364);click(736,364);assert len(m.sent)==before # no Admin pagination
    click(380,302);fields=struct.unpack('<HHIHH5I',m.sent[-1]);assert fields[4]==7
    m.receive(snapshot(8,m.r(s+44),token=456,view=5,admin=True));assert m.r(s+52)==2
    draw('admin-confirmation');assert any(t[0]=='Confirm Gacha Reset' for t in m.texts)
    assert any(t[0]=='Reset' for t in m.texts) and not any(t[0]=='Pull' for t in m.texts)
    assert any('every character' in t[0] for t in m.texts) and any('THIS machine only' in t[0] for t in m.texts)
    click(345,274);assert struct.unpack('<HHIHH5I',m.sent[-1])[4]==5 and m.r(s+52)==2
    m.receive(snapshot(2,m.r(s+44),view=5,admin=True));assert not m.r(s+52)
    click(380,302);m.receive(snapshot(8,m.r(s+44),token=789,view=5,admin=True))
    click(410,274);fields=struct.unpack('<HHIHH5I',m.sent[-1]);assert fields[4]==8 and fields[7]==789
    before=len(m.sent);click(410,274);assert len(m.sent)==before and m.r(s+52)==2
    m.receive(snapshot(2,m.r(s+44),view=5,admin=True));assert not m.r(s+52)
    # Malformed/unauthorized Admin snapshots cannot alter the live UI state.
    for p in [snapshot(2,m.r(s+44),view=5),snapshot(8,m.r(s+44),token=789,admin=True),
              snapshot(8,m.r(s+44),view=5,admin=True),snapshot(2,m.r(s+44),view=5,pages=10,admin=True)]:
        before=bytes(m.u.mem_read(s,3856));m.receive(p);assert bytes(m.u.mem_read(s,3856))==before
    m.receive(snapshot(2,m.r(s+44)));draw();assert not any(t[0]=='Admin' for t in m.texts)
    before=len(m.sent);click(465,31);click(380,302);assert len(m.sent)==before
    # Independent machines reuse the same stable native frame with fresh server
    # sessions; custom titles fit the header and old-machine replies are ignored.
    for nonce,name in [(88,'Potion Gacha'),(99,'Equipment Gacha'),(100,'W'*47)]:
        p=snapshot(session=nonce,admin=True);p[64:112]=name.encode().ljust(48,b'\0');m.receive(p);draw('machine'+str(nonce))
        t=next(t for t in m.texts if t[1]==22 and t[2]==55)
        assert name.startswith(t[0]) and m.font.getlength(t[0])<=276
        before=bytes(m.u.mem_read(s,3856));m.receive(snapshot(2,m.r(s+44),session=77))
        assert bytes(m.u.mem_read(s,3856))==before
    print('PASS: removed public-tab captions, left-aligned Administrator Control Panel, unchanged GM-only controls, spender ranks, per-machine reset scope, distinct confirmation/cancel, stable modal and stale-machine rejection')


if __name__=='__main__':main()
