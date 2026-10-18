"""Emitted x86 palette/UI tests; OS dialogs/menus are never mocked or called.

Native window allocation, capture, draw and GPU boundaries are mocked. Actual
input routing, visual clipping and DirectX remain live acceptance gates.
"""
import argparse
import json
from pathlib import Path
import struct
from PIL import Image
from verify_graymap import Machine
from unicorn.x86_const import UC_X86_REG_ECX

class Harness:
    def __init__(self,folder,record=None):
        self.m=json.loads((folder/'manifest.json').read_text())['graymap']
        self.vm=Machine(folder/'graymap.exe');self.state=self.m['state']['vir']
        self.e=self.m['colors']['exports'];self.ui=self.e['GrayUI'];self.record=record;self.cursor=0
        self.aligned=self.m['ui'].get('alignedRows',False);self.menu_x=150 if self.aligned else 85
        self.max_scroll=self.m['ui'].get('scrollMax',32);self.preset_row=3 if self.aligned else 1
        self.control_x=134 if self.aligned else 65
        self.saved=[];self.uploads=[];self.captured=0;self.attached=[];self.draws=[];self.blits=[];self.surfaces={};self.text_calls=[];self.radio_skins={};self.bitmap_paths=[]
        self.bind(0xFC1394,12,self.modulepath);self.bind(0xFC1224,28,self.open)
        self.bind(0xFC122C,20,self.read);self.bind(0xFC1234,20,self.write);self.bind(0xFC1238,4,lambda a:1)
        tex=self.vm.alloc(0x140);self.tex=tex
        self.vm.put(tex,0xFD7160);self.vm.put(tex+12,512);self.vm.put(tex+16,256)
        self.vm.put(tex+8,1);self.vm.u.mem_write(tex+0x24,b'graymap\\cells.tga\0')
        self.vm.put(tex+0x12C,0x111);self.vm.put(tex+0x130,0x222)
        self.vm.stub(0x56A5C0,28,self.upload);self.vm.stub(0x53BBA0,28,self.upload);self.vm.put(self.state+16,tex)
        self.vm.stub(0xDBBC4F,0,lambda a:self.vm.alloc(a[0]),argc=1)
        self.vm.stub(0x8172B0,0,lambda a:self.window(self.this(),0x1029820))
        self.vm.stub(0x9D0AA0,0,lambda a:self.window(self.this(),0x1042D4C))
        self.vm.stub(0x983C90,0,lambda a:self.window(self.this(),0x103FED4))
        self.vm.stub(0x836870,0,self.scroll_constructor)
        self.vm.stub(0x83C2C0,4,lambda a:0x99)
        self.vm.stub(0x9ACD80,16,self.skin)
        self.vm.stub(0x9A1BC0,8,self.radio_lookup)
        self.vm.stub(0xA1CB70,8,self.size)
        self.vm.stub(0xA1B780,4,self.addchild)
        pos=self.vm.get(self.m['ui']['rowTable']+16);self.vm.stub(pos,8,self.position)
        self.vm.stub(0xA4B750,4,self.capture);self.vm.stub(0xA32E00,0,lambda a:self.captured)
        self.vm.stub(0xA482E0,0,self.release)
        self.vm.stub(0xA25A70,36,self.text)
        self.vm.stub(0xA1CB30,4,self.clear)
        self.vm.stub(0xA1D460,20,lambda a:0)
        self.vm.stub(0xA90350,0,lambda a:0x7700)
        self.vm.stub(0xA9F030,0,lambda a:a[0],argc=1)
        self.vm.stub(0xA8D4A0,4,lambda a:self.bitmap_paths.append(bytes(self.vm.u.mem_read(a[0],260)).split(b'\0')[0]) or 0x8800)
        self.vm.stub(0xA1D260,16,lambda a:self.blits.append(a))
        self.vm.stub(0x81A5A0,4,lambda a:0)
        api=self.e['GrayUIApi'];self.page_destroy=self.vm.get(api+16)
        self.vm.stub(self.page_destroy,4,lambda a:0x77)
        if self.m['ui'].get('radioTable') or self.m['ui'].get('toggleTable'):self.vm.stub(self.vm.get(api+24),4,lambda a:0x88)
        self.tooltips=[];self.hidden_tips=0;self.tick=100;self.tooltip_window=self.vm.alloc(32);self.tip_manager=self.vm.alloc(256)
        self.vm.put(0x121333C,self.tip_manager)
        self.vm.stub(0xA764A0,4,lambda a:0)  # cursor shape; actual A23470 executes
        self.vm.stub(0xA753D0,24,self.show_tip)
        self.vm.stub(0xA753A0,0,self.hide_tip)
    def this(self):return self.vm.u.reg_read(UC_X86_REG_ECX)
    def show_tip(self,a):
        assert self.this()==self.tip_manager and a[3:]==[0xFFFFFFFF,0,0]
        self.tooltips.append((self.string(a[0]),a[1],a[2]));self.tick+=1
        self.vm.put(self.tip_manager+0x1C,self.tooltip_window);self.vm.put(self.tip_manager+0x20,self.tick)
    def hide_tip(self,a):
        assert self.this()==self.tip_manager;self.hidden_tips+=1;self.vm.put(self.tip_manager+0x1C,0)
    def scroll_constructor(self,a):
        w=self.window(self.this(),0x102AEF4)
        for off,value in [(0xA0,13),(0xA4,13),(0x88,1),(0xA8,1),(0xAC,1),(0xB0,1)]:self.vm.put(w+off,value)
        return w
    def text(self,a):self.draws.append(self.string(a[2]));self.text_calls.append(a)
    def skin(self,a):
        values=[]
        for p in a:
            ptr=self.vm.get(p);length=self.vm.get(p+16);capacity=self.vm.get(p+20)
            assert length<=capacity and length<260
            values.append(bytes(self.vm.u.mem_read(ptr,length)))
        if self.m['ui'].get('compactToggle'):
            assert values[0].endswith(b'GameSettingsUI\\toggle_off.bmp') and values[1].endswith(b'GameSettingsUI\\toggle_on.bmp')
            assert values[2:]==[values[0],values[0]]
        else:
            assert values[0].endswith(b'radiobtn_off.bmp') and values[1].endswith(b'radiobtn_on1.bmp') and values[2].endswith(b'radiobtn_on.bmp')
        self.radio_skins[self.this()]=values
    def radio_lookup(self,a):
        key=self.vm.get(a[1]);assert key in [0,1,2]
        node=self.vm.alloc(24);self.vm.put(node+20,0x9900+key);self.vm.put(a[0],node);return a[0]
    def stub(self,pop,callback):
        addr=self.vm.alloc(16);self.vm.stub(addr,pop,callback);return addr
    def bind(self,iat,pop,callback):self.vm.put(iat,self.stub(pop,callback))
    def string(self,p):return bytes(self.vm.u.mem_read(p,260)).split(b'\0')[0].decode('ascii')
    def modulepath(self,a):
        self.vm.u.mem_write(a[1],b'C:\\Game\\client.exe\0');return 18
    def open(self,a):
        assert self.string(a[0])=='C:\\Game\\savedata\\graymap.bin'
        assert a[1] in (0x80000000,0x40000000)
        self.cursor=0;return 9 if self.record is not None or a[1]==0x40000000 else 0xFFFFFFFF
    def read(self,a):
        data=(self.record or b'')[self.cursor:self.cursor+a[2]];self.cursor+=len(data)
        if data:self.vm.u.mem_write(a[1],data)
        self.vm.put(a[3],len(data));return 1
    def write(self,a):
        self.record=bytes(self.vm.u.mem_read(a[1],a[2]));self.saved.append(self.record);self.vm.put(a[3],a[2]);return 1
    def size(self,a):
        w=self.this();self.vm.put(w+0x14,a[0]);self.vm.put(w+0x18,a[1])
        bitmap=self.vm.alloc(64);pixels=self.vm.alloc(a[0]*a[1]*4)
        self.vm.put(bitmap+4,a[0]);self.vm.put(bitmap+8,a[1]);self.vm.put(bitmap+24,pixels);self.vm.put(w+0x24,bitmap)
        self.surfaces[w]=(a[0],a[1],pixels)
    def position(self,a):self.vm.put(self.this()+0x1C,a[0]);self.vm.put(self.this()+0x20,a[1])
    def window(self,w,table):
        self.vm.put(w,table);head=self.vm.alloc(16)
        self.vm.put(head,head);self.vm.put(head+4,head);self.vm.put(w+0x50,head);self.vm.put(w+0x28,1)
        return w
    def link(self,parent,child):
        head=self.vm.get(parent+0x50);tail=self.vm.get(head+4);node=self.vm.alloc(16)
        self.vm.put(tail,node);self.vm.put(node,head);self.vm.put(node+4,tail);self.vm.put(node+8,child);self.vm.put(head+4,node)
        self.vm.put(child+0x10,parent)
    def addchild(self,a):self.link(self.this(),a[0]);self.attached.append(a[0])
    def capture(self,a):
        assert self.this()==0x131F4E8;self.captured=a[0]
    def release(self,a):
        assert self.this()==0x131F4E8;self.captured=0
    def clear(self,a):
        width,height,pixels=self.surfaces[self.this()];self.vm.u.mem_write(pixels,struct.pack('<I',a[0])*(width*height))
    def upload(self,a):
        assert self.this()==self.tex and a[:4]==[0,0,512,256] and a[5:]==[0,0]
        self.uploads.append(bytes(self.vm.u.mem_read(a[4],512*256*4)));return 0
    def call(self,name,args=(),w=0):return self.vm.run(self.e[name],args,ecx=w)
    def attach(self):
        self.root=self.window(self.vm.alloc(512),0x1047C98)
        page=self.window(self.vm.alloc(512),0x1047C98);self.link(self.root,page);self.native=[]
        for y,height in [(0,32),(32,64),(96,32),(128,32),(160,32),(192,32)]:
            window=self.window(self.vm.alloc(512),self.m['ui']['rowTable']);self.link(page,window)
            self.vm.put(window+0x20,y);self.vm.put(window+0x18,height);self.native.append(window)
        self.call('_GrayAttach@4',[page]);self.page=page
        self.rows=[w for w in self.attached if self.vm.get(w)==self.m['ui']['rowTable']]
        self.bar=self.vm.get(self.ui+16);self.popup=self.vm.get(self.ui+20)
        self.radios=[w for w in self.attached if self.vm.get(w)==self.m['ui'].get('toggleTable',self.m['ui'].get('radioTable'))]
        return page
    def click(self,w,x,y,right=False):
        if w==self.vm.get(self.ui+20) and self.mode():
            x-=self.vm.get(w+0x1C);y-=self.vm.get(w+0x20)
        self.call('@GrayRightDown@16' if right else '@GrayDown@16',[x&0xFFFFFFFF,y&0xFFFFFFFF],w)
        assert self.captured==w
        self.call('@GrayRightUp@16' if right else '@GrayUp@16',[x&0xFFFFFFFF,y&0xFFFFFFFF],w)
        assert self.captured==0,'native mouse capture remains held after release'
        self.popup=self.vm.get(self.ui+20)
    def labels(self,r):
        self.draws=[];self.call('@GrayDraw@8',w=self.rows[r]);return self.draws
    def mode(self):return self.vm.get(self.ui+28)
    def scroll(self):return self.vm.get(self.ui+24)
    def bottom(self):
        for _ in range(20):
            if self.scroll()==self.max_scroll:break
            self.call('@GrayWheel@12',[-120&0xFFFFFFFF],self.bar)
        assert self.scroll()==self.max_scroll
    def open_preset(self):
        self.click(self.rows[self.preset_row],self.control_x+10 if self.aligned else 100,14 if self.aligned else 8)
    def preset(self,index):
        self.open_preset();assert self.mode()==1
        y=self.vm.get(self.ui+52)+4+index*18;self.click(self.popup,self.menu_x+10,y);assert self.mode()==0
    def color(self,which,rgb,apply=True):
        self.click(self.rows[4+which] if self.aligned else self.rows[2],self.control_x+10 if self.aligned else 80 if which==0 else 260,14 if self.aligned else 8);assert self.mode()==2+which
        for i,shift in enumerate([16,8,0]):self.click(self.popup,64+((rgb>>shift)&255),60+i*28)
        if apply:self.click(self.popup,245,225);assert self.mode()==0

def verify(folder):
    h=Harness(folder);h.call('_GrayPrepare@0')
    expected=Image.open(Path(__file__).resolve().parents[1]/'Assets/GrayMap/cells.tga').convert('RGBA');raw=bytearray()
    for y in reversed(range(256)):
        for x in range(512):
            r,g,b,a=expected.getpixel((x,y));raw.extend((b,g,r,a))
    assert h.uploads==[bytes(raw)]
    h.call('_GrayPrepare@0');assert len(h.uploads)==1
    h.vm.put(h.tex+0x12C,0x333);h.call('_GrayPrepare@0');assert len(h.uploads)==2
    h.vm.put(h.tex,0xFD5BF0);h.vm.put(h.tex+0x128,0x555);h.call('_GrayPrepare@0');assert len(h.uploads)==3
    h.attach();assert len(h.attached)==12 and len(h.rows)==6 and len(h.radios)==3
    h.call('_GrayAttach@4',[h.page]);assert len(h.attached)==12,'duplicate children on repeated creation'
    assert len(h.radio_skins)==3
    assert h.vm.get(h.rows[0]+0x28)==1 and h.vm.get(h.rows[2]+0x28)==0
    h.bottom()
    for child in h.native+h.rows:
        if h.vm.get(child+0x28):assert h.vm.get(child+0x20)+h.vm.get(child+0x18)<=272
    assert all(h.vm.get(w+0x28)==1 for w in h.rows)
    if h.m['ui'].get('nativeScrollbar'):
        assert h.surfaces[h.bar][:2]==(13,272)
        h.call('@GrayScrollDraw@8',w=h.bar)
        assert h.vm.run(0x848F80,ecx=h.bar)==157,'stock thumb size differs from content ratio'
        assert h.vm.get(h.m['ui']['scrollTable']+53*4)==0x848F80,'native scrollbar virtual lost'
        for suffix in [b'scroll0up.bmp',b'scroll0mid.bmp',b'scroll0down.bmp',b'scroll0bar_up.bmp',b'scroll0bar_mid.bmp',b'scroll0bar_down.bmp']:
            assert any(p.endswith(suffix) for p in h.bitmap_paths),('stock scrollbar skin missing',suffix)
    assert h.labels(3)==['Preset','Tactical'] and h.blits[-1][2]==0x8800
    assert h.labels(0)==['Gray Map'] and h.labels(1)==['Cell Grid'] and h.labels(2)==['Hide Scenery']
    for r in range(6):h.labels(r)
    for label in ['Gray Map','Cell Grid','Hide Scenery','Preset','Walkable','Blocked']:
        assert any(h.string(a[2])==label and a[7]==1 for a in h.text_calls),('label not bold',label)
    for i,w in enumerate(h.rows):
        assert h.vm.get(w+0x1C)==16 and h.vm.get(w+0x20)==232+i*32-h.max_scroll and h.surfaces[w][:2]==(350,32)
    assert h.blits[-1][0]+16==314,'preset arrow not aligned with native Graphics control column'
    assert h.vm.get(h.m['ui']['toggleTable']+20*4)==0x9A1AC0,'native switch renderer replaced'
    assert h.vm.get(h.m['ui']['toggleTable']-4)==h.vm.get(0x1042C70-4),'native switch RTTI lost'
    for i,w in enumerate(h.radios):
        assert h.surfaces[w][:2]==(34,15),'Effects switch size differs from stock'
        assert h.vm.get(w+0x1C)==134 and h.vm.get(w+0x10)==h.rows[i],'switch not in its aligned row'
        before=h.vm.get(h.state+i*4)
        for expected in [1-before,before]:
            h.click(w,5,5);assert h.vm.get(h.state+i*4)==expected
            h.blits=[];h.vm.run(0x9A1AC0,ecx=w)
            assert h.blits[-1][2]==0x9900+expected,'native switch renderer missed state'
    for i,name in [(1,'Classic gray'),(2,'High contrast'),(3,'Warm stone'),(0,'Tactical')]:
        h.preset(i);assert h.labels(3)==['Preset',name]
    saved=h.record
    h.open_preset();h.call('@GrayPopupDraw@8',w=h.popup)
    assert h.surfaces[h.popup][:2]==(182,94),'dropdown can overwrite the full page'
    assert h.vm.get(h.popup+0x1C)==150
    assert all(0<=a[0]<182 and 0<=a[1]<94 for a in h.text_calls[-5:]),'popup text outside its native bitmap'
    for _ in range(3):h.call('_GrayPrepare@0')
    assert h.mode()==1,'opening a preset blocks the returning frame path'
    h.open_preset();assert h.mode()==0 and h.record==saved
    h.color(0,0x123456,False);h.call('@GrayPopupDraw@8',w=h.popup);h.call('_GrayPrepare@0')
    assert h.surfaces[h.popup][:2]==(350,238),'color editor can overwrite the full page'
    assert h.mode()==2 and h.record==saved and h.uploads[-1]!=bytes(raw)
    h.click(h.popup,320,225);h.call('_GrayPrepare@0');assert h.uploads[-1]==bytes(raw) and h.record==saved
    h.color(0,0x123456);h.color(1,0xAABBCC);h.call('_GrayPrepare@0')
    assert struct.unpack('<6I',h.record[:24])[2:5]==(0x123456,0xAABBCC,4)
    fresh=Harness(folder,h.record);fresh.call('_GrayPrepare@0');assert fresh.vm.get(fresh.state)==0 and fresh.uploads[-1]==h.uploads[-1]
    h.color(0,0xFFFFFF,False);h.click(h.popup,40,145,right=True)
    h.click(h.popup,245,225);assert struct.unpack_from('<I',h.record,24)[0]==0xFFFFFF
    h.click(h.rows[4],144,14);h.call('@GrayDown@16',[60,52],h.popup)
    h.call('@GrayMove@16',[299,52],h.popup);h.call('@GrayUp@16',[0xFFFFFFFF,52],h.popup);assert not h.captured
    h.click(h.popup,320,225);assert h.mode()==0
    h.call('@GrayDown@16',[5,150],h.bar);h.call('@GrayMove@16',[5,0],h.bar);h.call('@GrayUp@16',[5,0],h.bar)
    assert h.scroll()==0 and h.captured==0
    h.bottom()
    # Execute the real native coordinate conversion through row/control parents.
    phrases=['original map','cell borders','Characters and monsters','palette','walkable','blocked']
    for i,w in enumerate(h.rows):
        h.call('@GrayCursor@16',[10,15],w);tip,x,y=h.tooltips[-1]
        assert phrases[i] in tip and (x,y)==(38,232+i*32-h.max_scroll+35)
    for i,w in enumerate(h.radios):
        h.call('@GrayCursor@16',[5,5],w);tip,x,y=h.tooltips[-1]
        assert phrases[i] in tip and (x,y)==(167,232+i*32-h.max_scroll+34)
    h.call('@GrayCursor@16',[0xFFFFFFFF,0],h.rows[0]);assert h.vm.get(h.tip_manager+0x1C)==0
    h.call('@GrayCursor@16',[10,15],h.rows[0]);before=h.hidden_tips
    h.open_preset();assert h.hidden_tips==before+1 and not h.vm.get(h.tip_manager+0x1C)
    count=len(h.tooltips);h.call('@GrayCursor@16',[10,15],h.rows[0]);assert len(h.tooltips)==count
    h.open_preset()
    h.call('@GrayCursor@16',[10,15],h.rows[0]);h.call('@GrayWheel@12',[120],h.bar);assert not h.vm.get(h.tip_manager+0x1C)
    h.bottom();h.call('@GrayCursor@16',[10,15],h.rows[0]);before=h.hidden_tips
    h.vm.put(h.tip_manager+0x20,h.tick+1) # another native producer reused the tip
    h.call('@GrayCursor@16',[0xFFFFFFFF,0],h.rows[0]);assert h.hidden_tips==before
    malformed=[b'',h.record[:12],h.record+b'x',b'BAD!'+h.record[4:]]
    for offset,value in [(4,2),(8,0x1000000),(16,5),(20,4),(24,0x1000000)]:
        data=bytearray(h.record);struct.pack_into('<I',data,offset,value);malformed.append(bytes(data))
    for record in malformed:
        broken=Harness(folder,record);broken.call('_GrayPrepare@0');assert broken.uploads==[bytes(raw)]
    h.vm.put(h.root+0x58,0)
    h.call('@GrayCursor@16',[10,15],h.rows[0])
    assert h.call('@GrayPageDestroy@12',[1],h.page)==0x77 and h.vm.get(h.state+20)==0 and h.captured==0
    assert not h.vm.get(h.tip_manager+0x1C),'owned tooltip survives page teardown'
    assert h.vm.get(h.root+0x58)==0,'invalidates a partially destroyed settings root'
    assert h.vm.get(h.ui)==0
    return dict(passed=True,default_atlas_exact=True,presets=4,malformed_records=9,aligned_rows=6,native_tooltips=True,native_tooltip_coordinates=True,tooltip_ownership=True,nonblocking_callbacks=True,native_arrow=True,native_effects_switches=True,native_scrollbar=h.m['ui'].get('nativeScrollbar',False),bold_labels=True,bounded_popup_surfaces=True,scroll_footer_bounds=True,mouse_release=True,persistence=True,live_accepted=False)

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('build',type=Path)
    print(json.dumps(verify(ap.parse_args().build.resolve()),indent=2))
if __name__=='__main__':main()
