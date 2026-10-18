"""Execute the emitted native dial, packet router and lifecycle bridges in Unicorn.

Native font/canvas/network boundaries are explicit doubles. Captures execute the
real compiled drawing code; they are not live game screenshots.
"""
import argparse
import datetime
import hashlib
import json
import math
from pathlib import Path
import struct
import pefile
from PIL import Image, ImageDraw, ImageFont
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *

ROOT=Path(__file__).resolve().parents[1]
FIELDS='api state frame reset receive draw hit destroy bridge receiver top vtable'.split()
PACKET=struct.Struct('<HHIHH6IhBB3I16s')
EPOCH=int(datetime.datetime(2026,10,16,13,34,8,tzinfo=datetime.timezone.utc).timestamp())

class Machine:
    def __init__(self,path):
        self.pe=pefile.PE(str(path));self.image=self.pe.get_memory_mapped_image();self.base=self.pe.OPTIONAL_HEADER.ImageBase
        self.u=Uc(UC_ARCH_X86,UC_MODE_32)
        self.u.mem_map(self.base,(len(self.image)+4095)&~4095);self.u.mem_write(self.base,self.image)
        self.u.mem_map(0x30000000,0x1000000);self.u.mem_map(0x40000000,0x10000);self.u.mem_map(0x41000000,0x1000)
        self.next=0x30000000;self.now=1000;self.sent=[];self.texts=[];self.stock=[];self.original=[];self.destroyed=[]
        marker=self.image.find(b'CelestialDial.v3\0');assert marker>=0
        key=struct.pack('<I',self.base+marker);record=self.image.find(key);assert record>=0 and self.image.find(key,record+1)<0
        self.c={k:self.r(self.base+record+4+i*4) for i,k in enumerate(FIELDS)}
        self.stub(self.r(self.c['api']+8),lambda:self.ret(0,0x123456))
        self.stub(self.r(self.c['api']+12),self.send)
        clock=self.alloc(16);self.stub(clock,lambda:self.ret(0,self.now));self.w(0xFC17B0,clock)
        self.stub(0xDBBC4F,lambda:self.ret(0,self.alloc(self.args(1)[0])))
        self.stub(0xA1B190,lambda:self.ret(4,self.ecx()))
        self.stub(0xA1B750,lambda:(self.destroyed.append(self.ecx()),self.ret(4,self.ecx())))
        self.stub(0xA245C0,self.resize);self.stub(0xA23450,self.position)
        self.stub(0xA2D240,lambda:self.ret(4));self.stub(0xA1CB30,self.clear)
        self.stub(0xA25A70,self.text);self.stub(0xC9E1DD,lambda:self.ret(0))
        self.stub(0xA21C90,self.measure)
        self.stub(0xA4B750,lambda:(self.w(0x131F4E8+0x19C,self.args(1)[0]),self.ret(4)))
        self.stub(0xA482E0,lambda:(self.w(0x131F4E8+0x19C,0),self.ret(0)))
        self.stub(0xA79710,lambda:(self.original.append(self.ecx()),self.ret(0)))
        for pc in [0xC9E908,0xC9E985,0xCA0AAD]:self.stub(pc,lambda pc=pc:(self.stock.append(pc),self.ret(0)))
        self.weather_hook=self.stub(0xC136A0,lambda:(_ for _ in ()).throw(AssertionError('Dial called native weather')))
        self.mode=self.alloc(0x1000);self.world=self.alloc(0x1000);self.player=self.alloc(0x1000);self.renderer=self.alloc(0x100)
        self.w(self.mode,0x10904B8);self.w(self.mode+0xCC,self.world);self.w(self.world+0x2C,self.player)
        self.w(0x12515F8,self.renderer);self.w(self.renderer+0x28,1280);self.w(self.renderer+0x2C,720)
        # Engine startup populates these BSS degree tables before entering a map.
        for address,function in [(0x124FF40,math.cos),(0x1250A88,math.sin)]:
            self.u.mem_write(address,struct.pack('<360f',*(function(math.radians(angle)) for angle in range(360))))
    def alloc(self,size):
        result=self.next;self.next+=(size+15)&~15;assert self.next<0x31000000;return result
    def r(self,p):return struct.unpack('<I',bytes(self.u.mem_read(p,4)))[0]
    def w(self,p,v):self.u.mem_write(p,struct.pack('<I',v&0xffffffff))
    def ecx(self):return self.u.reg_read(UC_X86_REG_ECX)
    def args(self,n):
        sp=self.u.reg_read(UC_X86_REG_ESP);return [self.r(sp+4+4*i) for i in range(n)]
    def ret(self,n,value=0):
        sp=self.u.reg_read(UC_X86_REG_ESP);target=self.r(sp);self.u.reg_write(UC_X86_REG_ESP,sp+4+n)
        self.u.reg_write(UC_X86_REG_EAX,value&0xffffffff);self.u.reg_write(UC_X86_REG_ECX,0xCCCCCCCC);self.u.reg_write(UC_X86_REG_EDX,0xDDDDDDDD);self.u.reg_write(UC_X86_REG_EIP,target)
    def stub(self,pc,fn):return self.u.hook_add(UC_HOOK_CODE,lambda *unused:fn(),begin=pc,end=pc)
    def invoke(self,pc,args=(),ecx=0,ebx=0xBBBBBBBB):
        sp=0x4000F000;self.u.mem_write(sp,struct.pack('<I',0x41000000)+b''.join(struct.pack('<I',v&0xffffffff) for v in args))
        registers={UC_X86_REG_EBX:ebx,UC_X86_REG_ESI:0xEEEEEEEE,UC_X86_REG_EDI:0xFFFFFFFF,UC_X86_REG_EBP:0xABABABAB}
        for reg,value in registers.items():self.u.reg_write(reg,value)
        self.u.reg_write(UC_X86_REG_ECX,ecx);self.u.reg_write(UC_X86_REG_ESP,sp)
        self.u.emu_start(pc,0x41000000,count=15000000)
        assert self.u.reg_read(UC_X86_REG_EIP)==0x41000000,'did not return'
        assert self.u.reg_read(UC_X86_REG_ESP)==sp+4+len(args)*4,'stack imbalance'
        for reg,value in registers.items():assert self.u.reg_read(reg)==value,'callee-save register changed'
        return self.u.reg_read(UC_X86_REG_EAX)
    def send(self):
        size,ptr=self.args(2);assert size==24;self.sent.append(bytes(self.u.mem_read(ptr,size)));self.ret(8)
    def resize(self):
        w,h=self.args(2);obj=self.ecx();surface=self.alloc(64);pixels=self.alloc(w*h*4)
        self.w(obj+0x14,w);self.w(obj+0x18,h);self.w(obj+0x24,surface);self.w(surface+4,w);self.w(surface+8,h);self.w(surface+0x18,pixels);self.ret(8)
    def position(self):
        x,y=self.args(2);obj=self.ecx();self.w(obj+0x1C,x);self.w(obj+0x20,y);self.ret(8)
    def clear(self):
        surface=self.r(self.ecx()+0x24);self.u.mem_write(self.r(surface+0x18),bytes(self.r(surface+4)*self.r(surface+8)*4));self.ret(4)
    def text(self):
        x,y,ptr,n,unused,height,color,bold,flags=self.args(9);assert unused==bold==flags==0
        value=bytes(self.u.mem_read(ptr,n)).decode('ascii');self.texts.append((value,x,y,height,color))
        surface=self.r(self.ecx()+0x24);w,h=self.r(surface+4),self.r(surface+8);pixels=self.r(surface+0x18)
        im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pixels,w*h*4)),'raw','BGRA')
        font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',height)
        ImageDraw.Draw(im).text((x,y),value,font=font,fill=(color&255,color>>8&255,color>>16&255,0))
        self.u.mem_write(pixels,im.tobytes('raw','BGRA'));self.ret(36)
    def measure(self):
        ptr,n,font_id,height,bold,italic=self.args(6)
        assert font_id==bold==italic==0
        value=bytes(self.u.mem_read(ptr,n)).decode('ascii')
        self.ret(24,round(ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',height).getlength(value)))
    def frame(self):self.invoke(self.c['frame'],(self.mode,))
    def snapshot(self,phase=0,flags=2,offset=480,remaining=0,duration=0,epoch=EPOCH,push=False,sequence=None,weather=0,protocol=5,rain_remaining=0,generation=1,map_name=b'prontera\0'):
        r=struct.unpack('<HHIHH3I',self.sent[-1]);cookie,request,client_tick=r[5:]
        sequence=sequence if sequence is not None else self.r(self.c['state']+20)+1
        return PACKET.pack(0xBF6,80 if protocol>=3 else 72 if protocol==2 else 68,0x564E4557,protocol,flags,cookie,sequence,0 if push else request,0 if push else client_tick,
            epoch&0xffffffff,epoch>>32,offset,phase,int(bool(phase and flags&2)),duration,remaining,1,map_name)+(struct.pack('<I',weather) if protocol>=2 else b'')+(struct.pack('<II',generation,rain_remaining) if protocol>=3 else b'')
    def native_weather(self,effect_id,owner=None,member=True,count=1):
        effect=self.alloc(0x200);head=self.alloc(16);node=self.alloc(16)
        self.w(effect+0x168,effect_id);self.w(0x15C57D8+0x10,self.player if owner is None else owner)
        self.w(0x15C57D8+0x44,effect);self.w(self.player+0x144,head);self.w(self.player+0x148,count)
        self.w(head,node);self.w(node,head);self.w(node+8,effect if member else 0)
        return effect
    def receive(self,p):
        self.u.mem_write(0x15E8198,bytes(p));self.invoke(self.r(0xCAA2E0+(0xBF6-0x73)*4))
    def draw(self,path=None):
        self.texts=[];obj=self.r(self.c['state']);self.invoke(self.c['draw'],ecx=obj)
        if path:
            surface=self.r(obj+0x24);w,h=self.r(surface+4),self.r(surface+8);pixels=self.r(surface+0x18)
            im=Image.frombytes('RGBA',(w,h),bytes(self.u.mem_read(pixels,w*h*4)),'raw','BGRA')
            im.save(path)
        return [t[0] for t in self.texts]

def weather_art_checks(path,out):
    m=Machine(path);s=m.c['state'];m.frame();m.receive(m.snapshot());m.frame()
    obj=m.r(s);surface=m.r(obj+0x24);pixels=m.r(surface+0x18)
    for phase in (0,1):
        m.receive(m.snapshot(phase=phase,push=True));m.frame()
        m.w(s+132,0);m.draw()
        clear=bytes(m.u.mem_read(pixels,280*98*4))
        for mask,name in [(128,'rain'),(2,'clouds'),(1,'snow'),(4,'fog'),(8,'petals'),
                          (16,'leaves'),(32,'fireworks'),(0x80000080,'lightning-preview')]:
            # Render-only preview input. The reserved lightning bit is never a wire flag.
            m.w(s+132,mask);m.draw(out/(path.stem+('-night-' if phase else '-day-')+name+'.png'))
            weather=bytes(m.u.mem_read(pixels,280*98*4));changes=0
            for y in range(70):
                for x in range(104,177):
                    off=(y*280+x)*4
                    if clear[off:off+4]!=weather[off:off+4]:
                        assert (x-140)**2+(y-35)**2<28**2,'Weather artwork escaped the sky inset'
                        changes+=1
            assert changes>20,(phase,name,'Missing weather artwork')
            assert m.invoke(m.c['hit'],(140,35),ecx=obj)==0
    old=m.r(s+20)
    m.receive(m.snapshot(weather=0x80000080,rain_remaining=1000,map_name=b'prt_fild08\0',push=True))
    assert m.r(s+20)==old,'Presentation-only lightning bit was accepted from the server'
    print('PASS',path.name,'day/night weather artwork, clipped inset, click-through and reserved lightning rejection')


def checks(path,out):
    m=Machine(path);s=m.c['state'];assert m.r(m.c['top'])==24
    m.frame();assert len(m.sent)==1 and not m.r(s) and m.r(s+12)
    before=m.snapshot();m.receive(before);m.frame();obj=m.r(s);assert obj and m.r(m.c['top'])==114
    assert m.r(obj+0x1C)==500 and m.r(obj+0x20)==8
    assert m.r(obj+0x2C)==0x3FE,'native window ID collides with another custom UI'
    manifest=path.parent.parent/'manifest.json'
    if manifest.is_file():
        data=json.loads(manifest.read_text());shim=data.get('monsterPosition')
        if shim:
            hud=m.alloc(0x7C);m.u.reg_write(UC_X86_REG_EAX,500);m.invoke(shim,ebx=hud)
            assert m.r(hud+0x1C)==500 and m.r(hud+0x20)==114,'existing monster position bridge ignored the reservation'
            m.invoke(m.c['reset']);m.u.reg_write(UC_X86_REG_EAX,500);m.invoke(shim,ebx=hud)
            assert m.r(hud+0x20)==24,'existing monster position did not restore after dial reset'
            m.frame();m.receive(m.snapshot());m.frame();obj=m.r(s)
    assert m.r(m.c['vtable']-4)==m.r(0x104AC44-4),'RTTI lost'
    assert m.invoke(m.c['hit'],(140,35),ecx=obj)==0,'HUD blocked clicks'
    values=m.draw(out/(path.stem+'-day.png'));assert '21:34:08' in values and 'Day' in values and 'No scheduled change' in values,values
    surface=m.r(obj+0x24);assert bytes(m.u.mem_read(surface+0x28,1))==b'\1','native canvas alpha flag disabled'
    assert m.r(m.r(surface+0x18))==0,'transparent exterior became opaque'
    m.now+=2500;m.frame();assert '21:34:10' in m.draw(),'clock did not advance'
    # The clock follows the server offset, independently of global phase.
    p=m.snapshot(phase=1,offset=-300,push=True);m.receive(p);m.frame();values=m.draw(out/(path.stem+'-night.png'))
    assert 'Night' in values and '08:34:08' in values and 'UTC-05:00' in values,values
    for offset,value in [(0,68),(4,0),(8,7),(12,0),(16,m.r(s+20)),(38,2),(68,64),(72,0),(76,300001)]:
        bad=bytearray(m.snapshot(push=True));struct.pack_into('<H' if offset in (0,8) else '<B' if offset==38 else '<I',bad,offset,value)
        old=m.r(s+20);m.receive(bad);assert m.r(s+20)==old,'bad snapshot was accepted'
    # A short WENV envelope is safely consumed without reading a full snapshot.
    old=m.r(s+20);m.receive(struct.pack('<HHI',0xBF6,8,0x564E4557));assert m.r(s+20)==old
    # Server flags and scoped native ambience coexist; combat/stale effects do not
    # become weather. The test traps any call to the native weather processor.
    for effect,mask,label in [(162,1,'Snow'),(163,8,'Petals'),(333,16,'Leaves'),(515,4,'Fog'),
                               (592,4,'Fog'),(233,2,'Clouds'),(516,2,'Clouds'),(297,32,'Fireworks'),(9999,64,'Ambient')]:
        m.native_weather(effect);m.frame();assert m.r(s+132)==mask and label in m.draw(),(effect,m.draw())
    m.native_weather(162,owner=m.player+16);m.frame();assert m.r(s+132)==0 and 'Clear' in m.draw()
    m.native_weather(162,member=False);m.frame();assert m.r(s+132)==0
    m.native_weather(162,count=0);m.frame();assert m.r(s+132)==0
    m.native_weather(162,count=1025);m.frame();assert m.r(s+132)==64
    m.native_weather(162);m.receive(m.snapshot(weather=4,push=True));m.frame()
    assert m.r(s+132)==5 and 'Snow + Fog' in m.draw()
    m.receive(m.snapshot(weather=63,push=True));m.frame();assert 'Snow +5' in m.draw()
    m.receive(m.snapshot(protocol=1,push=True));m.frame();assert m.r(s+132)==1 and m.r(s+128)==0
    m.w(0x15C57D8+0x44,0);m.receive(m.snapshot(weather=0,push=True));m.frame();assert 'Clear' in m.draw()
    # Exact one-hour deadlines fit the unchanged bottom panel with weather.
    for phase in (0,1):
        m.receive(m.snapshot(phase=phase,flags=3,duration=3600000,remaining=3600000,weather=32,push=True));m.frame();m.draw()
        for value,x,y,size,_ in m.texts:
            if y!=78:continue
            font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',size)
            assert x+font.getlength(value)<=(129 if x==29 else 278),(value,x,font.getlength(value))
    p=m.snapshot(phase=1,flags=3,remaining=3000,duration=600000,push=True);m.receive(p);m.frame();assert 'Day in 00:03' in m.draw()
    m.now+=4000;m.frame();values=m.draw();assert 'Night' in values and 'Awaiting server phase' in values,'client invented a phase transition'
    for w,h in [(800,600),(1024,768),(1920,1080),(3440,1440)]:
        m.w(m.renderer+0x28,w);m.w(m.renderer+0x2C,h);m.frame();assert m.r(obj+0x1C)==(w-280)//2 and m.r(obj+0x20)+98<=m.r(m.c['top'])
    m.w(m.renderer+0x28,200);m.frame();assert not m.r(obj+0x28) and m.r(m.c['top'])==24
    m.w(m.renderer+0x28,1280);m.frame();assert m.r(obj+0x28)
    # Both map lifecycle bridges replay native processing and reject old-cookie replies.
    for packet_id,stock in [(0x91,0xC9E908),(0x92,0xC9E985)]:
        old_cookie=m.r(s+12);stale=m.snapshot(push=True)
        m.invoke(m.r(0xCAA2E0+(packet_id-0x73)*4));assert m.stock[-1]==stock and not m.r(s+12) and not m.r(obj+0x28)
        m.frame();assert m.r(s+12)!=old_cookie;m.receive(stale);assert not m.r(s+44)
        m.receive(m.snapshot());m.frame()
    m.now=(m.now+90001)&0xffffffff;m.frame();assert not m.r(obj+0x28) and m.r(m.c['top'])==24
    m.invoke(m.c['destroy'],(1,),ecx=obj);assert not m.r(s) and not m.r(s+12) and m.destroyed==[obj]
    m.now=0xfffffff0;m.frame();m.receive(m.snapshot(epoch=(1<<32)+1234));m.frame()
    m.now=(m.now+2500)&0xffffffff;m.frame();values=m.draw();assert '14:48:52' in values,values
    preservation=path.parent.parent/'preservation.json'
    if preservation.is_file():
        previous=int(json.loads(preservation.read_text())['previous_framed_router'],16);forwarded=[]
        def legacy():
            assert m.ecx()==0x23456789 and m.u.reg_read(UC_X86_REG_EAX)==0x12345678
            forwarded.append(1);m.ret(0)
        m.stub(previous,legacy)
        for signature in (0x41484347,0x49555042,0x54534554):
            m.u.mem_write(0x15E8198,struct.pack('<HHI',0xBF6,8,signature));m.u.reg_write(UC_X86_REG_EAX,0x12345678)
            m.invoke(m.r(0xCAD0EC),ecx=0x23456789)
        assert len(forwarded)==3,'incremental WENV route swallowed an existing protocol'
    # Execute the actual static frame bridge with its native receiver intact.
    m.invoke(m.c['bridge'],ecx=0x12135F0,ebx=m.mode);assert m.original[-1]==0x12135F0
    m.w(m.mode,0);m.frame();assert not m.r(s+12) and m.r(m.c['top'])==24
    # Old servers are retried with the previous version after each ten seconds.
    m.w(m.mode,0x10904B8);m.frame();latest=struct.unpack_from('<H',m.sent[-1],8)[0]
    assert latest in (5,6)
    for expected in range(latest-1,0,-1):
        m.now+=10000;m.frame();assert struct.unpack_from('<H',m.sent[-1],8)[0]==expected
    m.receive(m.snapshot(protocol=1));m.frame();assert m.r(s+44) and 'Clear' in m.draw()
    rain_checks(path,out)
    print('PASS',path.name,'native clock/phase/weather/rain, v1/v2 fallback, validation, wrap, cleanup, click-through and geometry')

def rain_checks(path,out):
    m=Machine(path);s=m.c['state'];created=[];disposed=[];updates=[];native_alive=[1]
    def append_list(owner,offset,effect):
        head=m.r(owner+offset)
        if not head:
            head=m.alloc(16);m.w(head,head);m.w(head+4,head);m.w(owner+offset,head)
        tail=m.r(head+4);node=m.alloc(16)
        m.w(node,head);m.w(node+4,tail);m.w(node+8,effect);m.w(tail,node);m.w(head+4,node)
        m.w(owner+offset+4,m.r(owner+offset+4)+1)
        return node
    def unlink(owner,offset,effect):
        head=m.r(owner+offset);node=m.r(head)
        for _ in range(m.r(owner+offset+4)):
            if m.r(node+8)==effect:
                m.w(m.r(node+4),m.r(node));m.w(m.r(node)+4,m.r(node+4))
                m.w(owner+offset+4,m.r(owner+offset+4)-1);return
            node=m.r(node)
        raise AssertionError('native destructor boundary received an unowned effect')
    def factory():
        assert m.ecx()==m.player and m.args(5)==[857,0,0,0,0]
        effect=m.alloc(0x12000);m.w(effect,0x1088DE8);m.w(effect+0x168,857);m.w(effect+0x138,m.player)
        append_list(m.player,0x144,effect);append_list(m.world,8,effect);created.append(effect);m.ret(20,effect)
    def native_update():updates.append(m.ecx());m.ret(0,native_alive[0])
    def particles():
        texture,variant=m.args(2)
        assert m.ecx()==created[-1] and variant==0
        assert bytes(m.u.mem_read(texture,30)).split(b'\0')[0]==b'effect\\boh_rain_prototype.bmp'
        m.ret(8)
    def destructor():
        effect=m.ecx();assert m.args(1)==[1];disposed.append(effect);unlink(m.player,0x144,effect);m.ret(4,effect)
    m.stub(0xC44540,factory);m.stub(0xBC4C70,native_update);m.stub(0xBA2D80,destructor)
    m.stub(0xC0D5B0,particles)
    m.stub(0xDBBC7F,lambda:m.ret(0)) # native sized delete: caller removes its arguments.
    baseline=m.native_weather(162)
    # Give the existing native ambience list its normal circular previous links.
    head=m.r(m.player+0x144);node=m.r(head);m.w(head+4,node);m.w(node+4,head)
    def packet(on=True,**extra):
        fields=dict(weather=133 if on else 5,rain_remaining=120000 if on else 0,map_name=b'prt_fild08\0');fields.update(extra)
        return m.snapshot(**fields)
    def retire(effect):
        # Execute the real CWorld update/destruction branch. Only factory,
        # destructor/resource release are explicit engine boundaries.
        head=m.r(m.world+8);node=m.r(head)
        while node!=head and m.r(node+8)!=effect:node=m.r(node)
        assert node!=head
        m.u.reg_write(UC_X86_REG_EBX,m.world);m.u.reg_write(UC_X86_REG_EDI,node)
        m.u.reg_write(UC_X86_REG_EBP,0x4000E000);m.u.reg_write(UC_X86_REG_ESP,0x4000D000)
        m.u.emu_start(0xA6BAE0,0xA6BB7E,count=100000)
        assert m.u.reg_read(UC_X86_REG_EIP)==0xA6BB7E
    m.frame();m.receive(packet());m.frame();assert len(created)==1 and m.r(m.player+0x148)==2
    head=m.alloc(16);m.w(head,head);m.w(head+4,head);m.w(m.world+0x10,head)
    effect=created[-1];process=m.r(m.r(effect)+4)
    assert m.r(m.r(effect)-4)==m.r(0x1088DE8-4),'rain vtable lost native RTTI'
    assert m.invoke(process,ecx=effect)&255==1 and updates==[effect]
    m.invoke(m.r(m.r(effect)+0x3C),ecx=effect)
    values=m.draw(out/(path.stem+'-rain.png'));assert 'Rain +2' in values,values
    for _ in range(3):m.now+=2000;m.receive(packet(push=True));m.frame()
    assert len(created)==1,'repeated weather snapshots duplicated native rain'
    old=m.r(s+20)
    for bad in [m.snapshot(weather=128,rain_remaining=1000,push=True),packet(push=True,generation=0),packet(push=True,rain_remaining=300001)]:
        m.receive(bad);assert m.r(s+20)==old
    m.receive(packet(False,push=True));m.frame();retire(effect)
    assert disposed==[effect] and m.r(m.world+12)==0 and m.r(m.player+0x148)==1
    assert m.r(0x15C57D8+0x44)==baseline and m.r(baseline+0x168)==162
    assert 'Snow + Fog' in m.draw(),'stopping rain cleared baseline weather'
    # Network loss releases only the owned instance, even when native simulation is paused.
    m.now+=1000;m.receive(packet(push=True));m.frame();effect=created[-1]
    m.w(0x1602AA4,0);m.now+=5001;m.frame();retire(effect)
    assert disposed[-1]==effect and m.r(m.player+0x148)==1 and not(m.r(s+132)&128)
    m.now+=1000;m.receive(packet(push=True));m.frame();effect=created[-1]
    # Native lifetime expiry is retried at a bounded rate.
    native_alive[0]=0;retire(effect);assert not m.r(s+144)
    m.now+=1000;native_alive[0]=1;m.frame();assert created[-1]!=effect
    effect=created[-1];process=m.r(m.r(effect)+4)
    stale=packet(push=True);m.invoke(m.c['reset']);assert m.invoke(process,ecx=effect)==0
    retire(effect);m.frame();m.receive(stale);assert not m.r(s+44)
    assert m.r(m.player+0x148)==1 and m.r(0x15C57D8+0x44)==baseline

def native_particle_checks(path):
    """Run the actual CEffect::Process, including its particle-step BOOL gate."""
    m=Machine(path);s=m.c['state'];steps=[];children=[]
    def factory():
        assert m.args(5)==[857,0,0,0,0]
        effect=m.alloc(0x12000);m.w(effect,0x1088DE8);m.w(effect+0x138,m.player)
        m.w(effect+0x168,857);m.w(effect+0x17C,1000);m.ret(20,effect)
    def emit():
        effect=m.ecx();steps.append(effect)
        child=m.alloc(0x900);m.w(child+0x140,effect);m.w(child+0x1D0,157)
        m.w(effect+0x11C84,child);children.append(child)
        for i in range(4):m.w(child+0x3E8+i*0xB4,1)
        m.ret(8,0xabcdef00) # emitter returns no Boolean contract.
    m.stub(0xC44540,factory);m.stub(0xC0D5B0,emit)
    m.stub(0xDBBBD4,lambda:m.ret(0,m.u.reg_read(UC_X86_REG_EAX))) # cookie check preserves the return register.
    m.w(0x1602AA4,1) # native update-count gate; this is not the /effect option.
    m.frame();m.receive(m.snapshot(weather=128,rain_remaining=120000,map_name=b'prt_fild08\0'));m.frame()
    effect=m.r(s+144);assert effect
    process=m.r(m.r(effect)+4)
    for age in range(1,11):
        alive=m.invoke(process,ecx=effect)&255
        assert alive==1,f'Native particle-step BOOL gate retired rain at age {m.r(effect+0x178)}; emitter AL=0, keepalive={alive}'
        assert m.r(effect+0x178)==age and m.r(s+144)==effect
    assert steps==[effect]*12 and len(children)==12
    for child in children:
        assert m.r(child+0x1E4)==72
        for i in range(4):
            p=child+0x3E8+i*0xB4
            assert bytes(m.u.mem_read(p+0x68,1))==b'\0'
            assert m.r(p+0x80) in (0x40000000,0x40200000)
    # Execute the stock primitive update: positions must fall toward ground,
    # while the stock owner and native age/lifetime cleanup remain in place.
    camera=m.alloc(0x100);m.w(m.mode+0xD0,camera);m.stub(0xA75340,lambda:m.ret(0,m.mode))
    child=children[0];p=child+0x3E8
    start_y=struct.unpack('<f',bytes(m.u.mem_read(p+0x88,4)))[0]
    for _ in range(3):assert m.invoke(0xB823D0,ecx=child)&255==1
    end_y=struct.unpack('<f',bytes(m.u.mem_read(p+0x88,4)))[0]
    assert abs(end_y-start_y-16.5)<0.001,'native rain primitive did not fall downward'
    # Stop still reaches native CWorld cleanup through the existing lease gate.
    m.invoke(m.c['reset']);assert m.invoke(process,ecx=effect)==0
    print('PASS',path.name,'real native keepalive/fall, neutral palette, thin streaks, bounded children and stop')

def wet_ground_checks(path):
    m=Machine(path);children=[];quads=[]
    ground=m.alloc(32);resource=m.alloc(0x200);cells=m.alloc(160*160*20)
    terrain=struct.pack('<4fI',-7,-7,-7,-7,0)*(160*160)
    m.u.mem_write(cells,terrain);m.w(m.world+0x28,ground);m.w(ground+4,resource)
    m.w(ground+8,80);m.w(ground+12,80);m.u.mem_write(ground+16,struct.pack('<f',10))
    m.w(resource+0x110,160);m.w(resource+0x114,160);m.w(resource+0x11C,cells)
    def factory():
        effect=m.alloc(0x12000);m.w(effect,0x1088DE8);m.w(effect+0x168,857);m.w(effect+0x138,m.player)
        m.ret(20,effect)
    def emit():
        effect=m.ecx();child=m.alloc(0x900);m.w(child,0x1088C48);m.w(child+0x140,effect);m.w(child+0x1D0,157)
        m.u.mem_write(child+0x10,struct.pack('<3f',0,-20,0));m.w(child+0x204,1)
        textures=m.alloc(4);m.w(textures,0x1111);m.w(child+0x144,textures)
        for i in range(4):m.w(child+0x3E8+i*0xB4,1)
        m.w(effect+0x11C84,child);children.append(child);m.ret(8)
    def texture():
        ptr,*options=m.args(5);name=bytes(m.u.mem_read(ptr,40)).split(b'\0')[0]
        assert options==[0,1,0,0];m.ret(20,0x2222 if b'ripple' in name else 0x3333)
    def submit():
        args=m.args(26);count=args[0]
        assert args[14]==m.renderer and args[15:18]==[0,0,1] and args[18:21]==[210,227,240]
        assert args[25]==1 and m.r(count)<128
        verts=struct.unpack('<12f',struct.pack('<12I',*args[2:14]))
        handle=m.r(m.r(m.ecx()+0x144))
        quads.append((handle,args[1],verts));m.w(count,m.r(count)+1);m.ret(104)
    m.stub(0xC44540,factory);m.stub(0xC0D5B0,emit);m.stub(0x568760,texture);m.stub(0xB7C4E0,submit)
    effects_enabled=[1]
    m.stub(0xD9D020,lambda:m.ret(0,effects_enabled[0]));m.stub(0xB7F8D0,lambda:m.ret(0,1))
    # Native trig tables are data boundaries populated by the game at startup.
    import math
    for i in range(360):
        m.u.mem_write(0x1250A88+i*4,struct.pack('<f',math.sin(math.radians(i))))
        m.u.mem_write(0x124FF40+i*4,struct.pack('<f',math.cos(math.radians(i))))
    m.frame();m.receive(m.snapshot(weather=128,rain_remaining=120000,map_name=b'prt_fild08\0'));m.frame()
    effect=m.r(m.c['state']+144);m.invoke(m.r(m.r(effect)+0x3C),ecx=effect)
    child=children[-1];table=m.r(child);process=m.r(table+4);draw=m.r(table+12)
    assert m.r(table-4)==m.r(0x1088C48-4) and m.r(table)==0xB46640 and m.r(table+56)==0xB7F290
    m.w(0x1602AA4,1);p=child+0x3E8;m.u.mem_write(p+0x88,struct.pack('<f',12))
    assert m.invoke(process,ecx=child)==1
    assert struct.unpack('<f',bytes(m.u.mem_read(p+0x88,4)))[0]==13,'drop did not hit the sampled ground height'
    assert m.invoke(process,ecx=child)==1 and struct.unpack('<H',bytes(m.u.mem_read(p+2,2)))[0]==208
    original_textures=m.r(child+0x144);m.invoke(draw,(m.renderer,),ecx=child)
    assert m.r(child+0x144)==original_textures and m.r(child+0x204)==1,'private texture scope leaked'
    assert any(q[0]==0x1111 for q in quads),'no falling-drop geometry'
    assert any(q[0]==0x2222 for q in quads),'no impact ripple geometry'
    assert any(q[0]==0x3333 for q in quads),'no wet sheen geometry'
    for handle,alpha,vertices in quads:
        if handle in (0x2222,0x3333):assert all(abs(vertices[i]+7.08)<.001 for i in [1,4,7,10]),'ground layer floated above/below terrain'
    assert bytes(m.u.mem_read(cells,len(terrain)))==terrain,'wet rendering mutated native terrain'
    quads.clear();effects_enabled[0]=0;m.invoke(draw,(m.renderer,),ecx=child)
    assert not quads,'rain ground layers bypassed the native /effect render gate'
    effects_enabled[0]=1
    quads.clear();m.u.mem_write(cells,struct.pack('<4fI',-7,-7,-7,-7,1)*(160*160))
    m.invoke(draw,(m.renderer,),ecx=child);assert not quads,'ground effects crossed blocked cells'
    m.invoke(m.c['reset']);assert m.invoke(process,ecx=child)==0
    print('PASS',path.name,'ground collision, ripple/sheens, terrain clipping, texture/RTTI isolation and stop')

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('clients',nargs='*',type=Path)
    ap.add_argument('--rain-only',action='store_true')
    ap.add_argument('--particle-only',action='store_true')
    ap.add_argument('--wet-only',action='store_true')
    ap.add_argument('--receipt',type=Path)
    args=ap.parse_args();out=ROOT/'Outputs/CelestialDial/renders';out.mkdir(parents=True,exist_ok=True)
    paths=[p.resolve() for p in args.clients] or [ROOT/'Outputs/CelestialDial/clients'/f'{name}.exe' for name in ['standalone','monster-first','dial-first','framed-peers','framed-reverse']]
    for path in paths:
        if args.wet_only:wet_ground_checks(path)
        elif args.particle_only:native_particle_checks(path)
        elif args.rain_only:rain_checks(path,out);print('PASS',path.name,'owned rain lifecycle, native world disposal and baseline preservation')
        else:checks(path,out);native_particle_checks(path);wet_ground_checks(path);weather_art_checks(path,out)
    if args.receipt:
        assert not args.rain_only and not args.particle_only and not args.wet_only,'Full acceptance receipts require the complete suite'
        args.receipt.parent.mkdir(parents=True,exist_ok=True)
        args.receipt.write_text(json.dumps({'passed':True,'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'clients':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}},indent=2)+'\n')

if __name__=='__main__':main()
