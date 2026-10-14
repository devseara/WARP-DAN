"""Execute actual IDUI x86 with mocked engine boundaries; no claim of live UI acceptance."""
from pathlib import Path
import argparse,json,struct
import pefile
from unicorn import Uc,UC_ARCH_X86,UC_MODE_32,UC_HOOK_CODE
from unicorn.x86_const import *
from PIL import Image,ImageDraw,ImageFont

STOP=0x50000000;STACK=0x50010000;WIN=0x50100000;ITEM=0x50101000
SURFACE=0x50200000;PIXELS=0x50300000;PACKET=0x50600000
OFF={'owner':0,'seq':4,'pending':8,'ready':12,'force':16,'origin':20,'sent':24,'w':28,'h':32,
     'scroll':36,'content':40,'layout':44,'pressed':48,'hover':52,
     'children':68,'lines':72,'hits':76,'request':80,'snapshot':176,
     'loading':119528,'deferred':119532,'last_send':119536,'headline_kind':119540,'headline':119544,'bonus':119548,
     'info_level':119552,'info_weapon':119556,'info_weight':119560,'shapes':119564}
HITS=118064;LINES=13616;SHAPES=119568
class VM:
    def __init__(self,pe,m):
        self.m=m;self.u=Uc(UC_ARCH_X86,UC_MODE_32);self.now=1000;self.sent=[];self.draws=[];self.observed_scope=[]
        self.native_calls=[];self.stubs={};self.surface_size=0
        mapped=pe.get_memory_mapped_image();self.u.mem_map(0x400000,(len(mapped)+4095)&~4095);self.u.mem_write(0x400000,mapped)
        self.u.mem_map(STOP,0x800000);self.state=m['state']['vir'];self.entries=m['entries']
        self.write32(WIN,0x1032aac);self.write32(WIN+0x1f8,12);self.write32(WIN+0x1c,20);self.write32(WIN+0x20,20);self.u.mem_write(WIN+0x28,b'\1')
        self.renderer=0x50108000;self.write32(0x12515f8,self.renderer);self.write32(self.renderer+0x28,1024);self.write32(self.renderer+0x2c,768)
        head=0x50105000;first=head+0x20;second=head+0x40
        for a,values in [(head,[first,second,0]),(first,[second,head,0x50106000]),(second,[head,first,0x50106400])]:self.u.mem_write(a,struct.pack('<III',*values))
        self.write32(WIN+0x50,head);self.child=0x50106000;self.close=0x50106400
        for p in [self.child,self.close]:self.write32(p+0x10,WIN);self.u.mem_write(p+0x28,b'\1');self.write32(p+0x1c,30);self.write32(p+0x20,40)
        self.write32(WIN+0x208,self.close);self.write32(WIN+0x1b0,self.child)
        self.set_size(WIN,[280,144]);self.write32(0xfc17b0,STOP+0x100)
        self.stub(STOP+0x100,0,lambda ecx,args:self.now)
        self.stub(0x5d98a0,0,lambda ecx,args:int(self.cstring(ecx+0x2c)or b'0'))
        self.scrollbar = self.state + 119344
        self.scroll_surface = 0x50700000; self.scroll_pixels = 0x50701000
        self.textures = {}; self.loaded_paths = []; self.texture_next = 0x50720000
        self.scroll_destroyed = 0
        self.stub(0x836870,0,self.scroll_ctor)
        self.stub(0x83c2c0,4,self.scroll_dtor)
        self.stub(0xa90350,0,lambda ecx,args:0x5010a000)
        self.stub(0xa9f030,0,lambda ecx,args:self.read32(self.u.reg_read(UC_X86_REG_ESP)+4))
        self.stub(0xa8e500,4,lambda ecx,args:1 if self.load_texture(ecx,args) else 0)
        self.stub(0xa8d4a0,4,self.load_texture)
        self.stub(0xa1cb30,4,self.scroll_clear)
        self.stub(0xa1d260,16,self.scroll_blit)
        self.stub(0xa1d460,20,self.scroll_fill)
        self.stub(0xa23340,0,lambda ecx,args:self.write32(ecx+0x58,1))
        self.stub(0xa4b750,4,lambda ecx,args:self.write32(0x131f4e8+0x19c,args[0]))
        self.stub(0xa245c0,8,self.set_size)
        self.stub(0xa21c90,24,lambda ecx,args:len(self.cstring(args[0]).decode('utf8','replace'))*6)
        self.stub(0xa25a70,36,self.draw_text)
        self.stub(0xa32e00,0,lambda ecx,args:self.read32(0x131f4e8+0x19c))
        self.stub(0xa482e0,0,lambda ecx,args:self.write32(0x131f4e8+0x19c,0))
        self.stub(m['packetRefs']['packetCtorA'],0,lambda ecx,args:STOP+0x200)
        self.stub(m['packetRefs']['packetSend'],8,self.send)
        self.stub(0xa7e780,4,lambda ecx,args:0)
        self.write32(0x159c088,0)
        for i,addr in enumerate(m['original']):
            if i in [4,19,20,25,28,31,32,35,37,0]:
                self.stub(addr,{0:4,4:8,19:0,20:0,25:8,28:8,31:8,32:8,35:4,37:24}[i],self.original(i))
        self.stub(m['config'][57],8,self.scope_event);self.stub(m['config'][58],8,self.scope_event)
        self.stub(0xa39340,4,lambda ecx,args:0)
        self.stub(0x6a1b20,0,lambda ecx,args:0)
        self.stub(0x6a25f0,4,lambda ecx,args:self.u.mem_write(ecx,bytes(self.u.mem_read(args[0],0xb8))) or ecx)
        self.stub(0x6a2a70,0,lambda ecx,args:0x5010b000)
        self.stub(0x6a6570,4,lambda ecx,args:self.u.mem_write(ecx+0x2c,str(args[0]).encode()+b'\0'))
        self.stub(0x4f08f0,0,lambda ecx,args:0)
        if m.get('headerHook'):
            site=m['headerHook']['address'];resume=m['headerHook']['resume'];draw=m['original'][20]
            self.u.mem_write(draw,b'\x57\x8b\xf9\xe9'+struct.pack('<i',site-(draw+8)))
            self.u.mem_write(resume,b'\x5f\xc3')
        self.u.hook_add(UC_HOOK_CODE,self.hook)
    def read32(self,a):return struct.unpack('<I',self.u.mem_read(a,4))[0]
    def write32(self,a,v):self.u.mem_write(a,struct.pack('<I',v&0xffffffff));return 0
    def s(self,key,v=None):
        a=self.state+OFF[key]
        if v is not None:self.write32(a,v)
        return self.read32(a)
    def cstring(self,p):
        for n in range(4096):
            if self.u.mem_read(p+n,1)==b'\0':return bytes(self.u.mem_read(p,n))
        raise AssertionError('unterminated native string')
    def stub(self,address,pop,fn):self.stubs[address]=(pop,fn)
    def original(self,slot):
        def call(ecx,args):
            self.native_calls.append((slot,ecx,args))
            if slot==37 and args[1]==24:self.u.mem_write(ecx+0xb8,bytes(self.u.mem_read(args[2],0xb8)))
            return 0
        return call
    def scope_event(self,ecx,args):self.observed_scope.append((self.s('origin'),ecx,args));return 0
    def scroll_ctor(self,ecx,args):
        assert ecx==self.scrollbar
        self.u.mem_write(ecx,bytes(0xb4));self.write32(ecx,0x102aef4)
        for off,val in [(0xa0,13),(0xa4,13),(0x88,1),(0xa8,1),(0xac,1),(0xb0,1)]:self.write32(ecx+off,val)
        return ecx
    def scroll_dtor(self,ecx,args):
        assert ecx==self.scrollbar and args==[0];self.scroll_destroyed+=1;return ecx
    def load_texture(self,ecx,args):
        path=self.cstring(args[0]).decode('cp949');self.loaded_paths.append(path)
        if path in self.textures:return self.textures[path]
        leaf=path.replace('\\','/').rsplit('/',1)[-1]
        file=Path(__file__).resolve().parents[1]/'tools/fixtures/item_description/assets'/leaf
        if not file.exists() and 'basic_interface' in path:file=file.parent/'basic_interface'/leaf
        if not file.exists():return 0
        im=Image.open(file).convert('RGBA');return self.add_texture(path,im)
    def add_texture(self,path,im):
        t=self.texture_next;self.texture_next+=0x200+im.width*im.height*4
        self.write32(t+0x114,im.width);self.write32(t+0x118,im.height);self.write32(t+0x11c,t+0x200)
        self.u.mem_write(t+0x200,im.tobytes('raw','BGRA'));self.textures[path]=t;return t
    def scroll_clear(self,ecx,args):
        assert ecx==self.scrollbar
        self.u.mem_write(self.scroll_pixels,struct.pack('<I',args[0])*13*self.read32(ecx+0x18));return 0
    def scroll_fill(self,ecx,args):
        x,y,w,h,color=args
        for yy in range(max(0,y),min(y+h,self.read32(ecx+0x18))):
            for xx in range(max(0,x),min(x+w,13)):self.write32(self.scroll_pixels+(yy*13+xx)*4,color)
        return 0
    def scroll_blit(self,ecx,args):
        x,y,t,flags=args
        assert ecx==self.scrollbar and t
        tw=self.read32(t+0x114);th=self.read32(t+0x118);pixels=self.read32(t+0x11c)
        for yy in range(th):
            if not 0<=y+yy<self.read32(ecx+0x18):continue
            for xx in range(tw):
                if not 0<=x+xx<13:continue
                value=self.read32(pixels+(yy*tw+xx)*4)
                if value&0xffffff!=0xff00ff:self.write32(self.scroll_pixels+((y+yy)*13+x+xx)*4,value)
        return 0
    def set_size(self,ecx,args):
        w,h=args;
        if ecx==getattr(self,'scrollbar',0):
            assert w==13 and 0<h<=1024
            self.write32(ecx+0x14,w);self.write32(ecx+0x18,h);self.write32(ecx+0x24,self.scroll_surface)
            self.write32(self.scroll_surface+4,w);self.write32(self.scroll_surface+0x18,self.scroll_pixels)
            self.u.mem_write(self.scroll_pixels,bytes(w*h*4)+b'\xcd'*64);return 0
        assert 1<=w<=1024 and 1<=h<=1024
        self.write32(ecx+0x14,w);self.write32(ecx+0x18,h);self.write32(ecx+0x24,SURFACE)
        self.write32(SURFACE+4,w);self.write32(SURFACE+0x18,PIXELS);self.surface_size=w*h*4
        self.u.mem_write(PIXELS,b'\xff'*self.surface_size+b'\xCD'*64);return 0
    def draw_text(self,ecx,args):
        x,y,p,count,font,height,color,bold,last=args
        self.draws.append((x,y,self.cstring(p).decode('utf8','replace'),color,bold));return 1
    def send(self,ecx,args):self.sent.append(bytes(self.u.mem_read(args[1],args[0])));return 0
    def hook(self,u,pc,size,_):
        if pc==STOP:u.emu_stop();return
        if self.m.get('headerHook') and pc==self.m['original'][20]:
            self.stubs[pc][1](self.u.reg_read(UC_X86_REG_ECX),[])
            return # Execute the actual underlay detour before the stock art/title boundary.
        if pc not in self.stubs:return
        pop,fn=self.stubs[pc];sp=self.u.reg_read(UC_X86_REG_ESP)
        args=[self.read32(sp+4+i*4)for i in range(pop//4)]
        result=fn(self.u.reg_read(UC_X86_REG_ECX),args)
        self.u.reg_write(UC_X86_REG_EAX,(result or 0)&0xffffffff);self.u.reg_write(UC_X86_REG_EIP,self.read32(sp));self.u.reg_write(UC_X86_REG_ESP,sp+4+pop)
    def run(self,name,args=(),ecx=WIN,pop=None):
        address=name if isinstance(name,int) else self.entries.get('ItemDescription'+name,0)
        assert address
        sp=STACK+0xf000;self.u.mem_write(sp,struct.pack('<'+'I'*(len(args)+1),STOP,*[(v&0xffffffff)for v in args]))
        self.u.reg_write(UC_X86_REG_ESP,sp);self.u.reg_write(UC_X86_REG_ECX,ecx);self.u.reg_write(UC_X86_REG_EDX,0)
        saved=[(UC_X86_REG_EBX,0x11223344),(UC_X86_REG_ESI,0x22334455),(UC_X86_REG_EDI,0x33445566),(UC_X86_REG_EBP,0x44556677)]
        for reg,value in saved:self.u.reg_write(reg,value)
        # Bound the full 64-row text layout plus original skin/scrollbar rendering.
        self.u.emu_start(address,STOP,count=10_000_000)
        assert self.u.reg_read(UC_X86_REG_EIP)==STOP,'instruction limit'
        assert self.u.reg_read(UC_X86_REG_ESP)==sp+4+(len(args)*4 if pop is None else pop),(name,'stack mismatch',hex(self.u.reg_read(UC_X86_REG_ESP)))
        assert all(self.u.reg_read(reg)==value for reg,value in saved),(name,'callee-saved register')
        return self.u.reg_read(UC_X86_REG_EAX)
    def add_child(self,parent=WIN,address=0x50106800):
        # Append a child the stock code creates after the card was activated.
        head=self.read32(parent+0x50);last=self.read32(head+4);node=address+0x100
        self.u.mem_write(node,struct.pack('<III',head,last,address));self.write32(last,node);self.write32(head+4,node)
        self.write32(address+0x10,parent);self.u.mem_write(address+0x28,b'\1');return address
    def open(self,itemid=1201,index=7,refine=7,scope=1,identified=1):
        self.now+=200 # Real opens are user-paced; the server spaces requests 150 ms apart.
        data=bytearray(0xb8);struct.pack_into('<I',data,4,index);struct.pack_into('<I',data,0x60,refine)
        data[0x5c]=identified;data[0x2c:0x2c+len(str(itemid))+1]=str(itemid).encode()+b'\0';struct.pack_into('<I',data,0x40,15)
        struct.pack_into('<I',data,0x98,5);struct.pack_into('<I',data,0x1c,4001)
        self.u.mem_write(ITEM,bytes(data));self.s('origin',scope);self.run('Message',[0,24,ITEM,0,0,0]);self.s('origin',0)
    def response(self):
        r=self.sent[-1];request=struct.unpack_from('<I',r,12)[0];id,index=struct.unpack_from('<II',r,16);scope,refine,grade=struct.unpack_from('<HHH',r,24)
        data=bytearray(12416);struct.pack_into('<HHIHHIIIII',data,0,0xbef,len(data),0x49554449,1,2,request,1,0,id,index)
        struct.pack_into('<HHH',data,32,scope,refine,grade);struct.pack_into('<HHHH',data,40,1,0,0,4)
        data[64:72]=b'Unbound\0';data[96:103]=b'Weapon\0'
        rows=[(1,0,'Base ATK','17',0),(3,1,'Native effect','An accurate server-provided effect. '*3,0),(4,0,'Refine bonus','+14 ATK',0),(8,2,'Slot 1','Installed card',4001),(10,0,'Base level','1',0),(11,0,'Storage','Allowed by item policy',0)]
        for n,(section,kind,label,text,id)in enumerate(rows):
            off=128+n*192;struct.pack_into('<HHIHH',data,off,section,kind,id,0,1 if id else 0)
            data[off+16:off+16+len(label)]=label.encode();data[off+64:off+64+len(text)]=text.encode()
        struct.pack_into('<H',data,38,len(rows));return data
    def receive(self,data):self.u.mem_write(PACKET,bytes(data));return self.run('Receive',[PACKET,len(data)],ecx=0)
    def render(self,path):
        self.draws=[];self.run('Draw');w=self.read32(WIN+0x14);h=self.read32(WIN+0x18)
        raw=bytearray(self.u.mem_read(PIXELS,w*h*4))
        for i in range(0,len(raw),4):
            if raw[i:i+3]==b'\xff\x00\xff':raw[i:i+4]=b'\xff\xff\xff\x00'
            else:raw[i+3]=255
        image=Image.frombytes('RGBA',(w,h),bytes(raw),'raw','BGRA');d=ImageDraw.Draw(image)
        font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',12)
        for x,y,text,color,bold in self.draws:d.text((x,y),text,font=font,fill=(color&255,(color>>8)&255,(color>>16)&255))
        d.text((12,10),'Native header is retained (engine boundary mocked)',font=font,fill='#566880')
        image.save(path)

def verify(directory):
    export=json.loads((directory/'native-manifest.json').read_text(encoding='utf8'));m=export['itemDescription'];pe=pefile.PE(str(directory/'item-description.exe'))
    checks=[]
    for h in m['hooks']:assert struct.unpack('<I',pe.get_data(h['address']-0x400000,4))[0]==h['replacement']
    checks.append('All main/comparison static vtable edits match exported native callback addresses')
    v=VM(pe,m);v.s('origin',9);v.run('InventoryRight',[4,5]);v.run('EquipmentRight',[6,7]);assert [x[0]for x in v.observed_scope]==[1,1] and v.s('origin')==9
    checks.append('Inventory/equipment event wrappers preserve arguments, registers and enclosing scope')
    v=VM(pe,m);v.open();assert len(v.sent)==1 and len(v.sent[0])==96
    assert struct.unpack_from('<IIHHH',v.sent[0],16)==(1201,7,1,7,0)
    assert v.s('ready')==1 and v.s('loading')==1 and v.s('pending')==1
    assert (v.read32(WIN+0x14),v.read32(WIN+0x18))==(360,560),'final geometry must be taken at open'
    assert v.u.mem_read(v.child+0x28,1)==b'\0' and v.u.mem_read(v.close+0x28,1)==b'\1'
    checks.append('Owned item requests serialize index, refine and identity; the pane takes its final geometry and hides the stock body in the opening frame')
    v.draws=[];v.run('Draw');assert not v.draws and v.s('lines')==0,'loading skeleton must not paint stock or stale text'
    response=v.response();assert v.receive(response)==1 and v.s('ready')==1 and v.s('loading')==0 and not v.s('pending')
    checks.append('Loading skeleton is replaced in place by the validated snapshot')
    v.render(directory/'native-body-preview.png');assert v.s('lines')>6
    assert bytes(v.u.mem_read(PIXELS+v.surface_size,64))==b'\xCD'*64
    assert v.s('headline_kind')==1 and v.s('headline')==17 and v.s('bonus')==14
    assert any(t=='17' for _,_,t,*_ in v.draws) and any(t=='+14' for _,_,t,*_ in v.draws),'headline ATK and refine bonus'
    checks.append('Real payload layout/draw executes with bounded writes, wraps long server text and derives the ATK headline')
    fresh=lambda:VM(pe,m)
    for off,fmt,value in [(8,'H',2),(12,'I',999),(24,'I',999),(28,'I',999),(38,'H',65),(44,'H',6),(128,'H',99),(130,'H',99)]:
        t=fresh();t.open();data=t.response();struct.pack_into('<'+fmt,data,off,value);assert t.receive(data)==0 and t.s('loading'),(off,'malformed accepted')
    t=fresh();t.open();data=t.response();data[128+64:128+192]=b'X'*128;assert t.receive(data)==0
    t=fresh();t.open();assert t.receive(t.response()[:-1])==0
    checks.append('Malformed size/version/token/item/index/count/section/kind/unterminated text is rejected before use')
    t=fresh();t.open(scope=0,index=0);assert struct.unpack_from('<I',t.sent[0],20)[0]==0 and struct.unpack_from('<H',t.sent[0],26)[0]==0
    t=fresh();t.open(identified=0);assert not t.sent and not t.s('ready') and t.u.mem_read(t.child+0x28,1)==b'\1'
    checks.append('Catalog routes carry no invented instance fields; unidentified owned items keep native disclosure')
    t=fresh();t.open();old=t.response();t.open(itemid=1202);assert t.receive(old)==0 and t.s('loading')
    checks.append('An old item response cannot populate a newly selected item')
    t=fresh();t.open();t.now+=6000;t.run('Process');assert not t.s('pending') and not t.s('ready')
    assert t.read32(WIN+0x14)==280 and t.u.mem_read(t.child+0x28,1)==b'\1'
    t.open(itemid=1202);assert not t.s('ready') and t.s('pending'),'a silent server must not keep blanking descriptions'
    assert t.receive(t.response())==1 and t.s('ready') and not t.s('loading')
    t.open(itemid=1203);assert t.s('ready') and t.s('loading'),'a proven server re-enables the opening skeleton'
    checks.append('Absent server times out from OnProcess back to the native body; later opens skip the skeleton until a reply proves the module')
    t=fresh();t.open();t.receive(t.response());t.run('Draw');before=len(t.sent)
    t.open();assert t.s('ready') and not t.s('loading'),'same instance must reopen from its accepted snapshot'
    assert len(t.sent)==before+1 and struct.unpack_from('<H',t.sent[-1],10)[0]==1
    checks.append('Reopening the same instance paints its accepted card immediately while the server revalidates it')
    t2=fresh();t2.open();t2.receive(t2.response())
    t2.now-=199;t2.open(itemid=1202) # Net +1 ms: this request lands inside the server window.
    assert t2.s('deferred') and len(t2.sent)==1,'second request within the server window must be queued, not dropped'
    t2.now+=50;t2.run('Process');assert len(t2.sent)==1;t2.now+=150;t2.run('Process');assert len(t2.sent)==2 and not t2.s('deferred')
    assert struct.unpack_from('<I',t2.sent[-1],16)[0]==1202 and t2.receive(t2.response())==1 and t2.s('ready')
    checks.append('Requests are spaced to the server 150 ms window from OnProcess instead of being silently dropped')
    t=fresh();t.open();t.receive(t.response());t.run('Draw');late=t.add_child();t.run('Draw');assert t.u.mem_read(late+0x28,1)==b'\0'
    t.run('Message',[0,29,0,0,0,0]);assert t.s('ready') and t.read32(WIN+0x14)==360 and t.u.mem_read(late+0x28,1)==b'\0'
    assert [x for x in t.native_calls if x[0]==37][-1][2][1]==29
    t.run('Message',[0,5,0,0,0,0]);assert not t.s('ready') and not t.s('owner') and t.u.mem_read(late+0x28,1)==b'\1'
    assert t.u.mem_read(t.child+0x28,1)==b'\1' and t.read32(WIN+0x14)==280
    checks.append('Children created after activation stay hidden, incidental native messages resume the card, and close restores every child')
    t=fresh();t.open();t.receive(t.response());t.run('Draw');h=t.read32(WIN+0x18);sent=len(t.sent)
    for x,y in [(20,h-20),(100,h-20),(t.read32(WIN+0x14)-40,h-20)]:t.run('Down',[x,y]);t.run('Up',[x,y])
    assert len(t.sent)==sent and t.s('ready'),'there are no footer actions'
    assert not any(struct.unpack_from('<H',r,10)[0]==3 for r in t.sent)
    checks.append('No Original/Compare/Refresh footer: former button positions are inert and no compare request is ever sent')
    t=fresh();t.open();t.receive(t.response());t.run('Destroy',[0]);assert not t.s('owner') and not t.s('ready');assert t.receive(t.response())==0
    checks.append('Destruction clears ownership; delayed replies cannot dereference a destroyed window')
    result={'passed':True,'checks':checks,'engine_boundaries_mocked':True,'live_accepted':False}
    (directory/'native-verification.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('directory',type=Path);print(json.dumps(verify(p.parse_args().directory),indent=2))
