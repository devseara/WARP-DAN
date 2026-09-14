"""Execute the emitted x86 chat hooks against bounded native UI test doubles.

This checks calling conventions, layout, filter identity, alpha/key conversion,
all five selected-tab draws, idle/active input resources and native forwarding.
It is not a substitute for in-game screenshot acceptance.
"""
import argparse
import struct
from pathlib import Path

import capstone
import pefile
from PIL import Image
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *

def pack(value):
    return struct.pack('<I', value & 0xffffffff)

ASSETS = Path(__file__).resolve().parents[1] / 'Assets' / 'ModernChatUI'

def over(source, destination):
    sa, da = source >> 24, destination >> 24
    if sa == 0 or source & 0xffffff == 0xff00ff:
        return destination
    if sa == 255 or da == 0:
        return source
    remain = (da * (255-sa) + 127) // 255
    alpha = sa + remain
    return (alpha << 24) | sum(((((source >> s) & 255)*sa +
                                ((destination >> s) & 255)*remain + alpha//2)//alpha) << s
                               for s in (0,8,16))

class Machine:
    def __init__(self, exe, assets):
        self.pe = pefile.PE(exe)
        self.base = self.pe.OPTIONAL_HEADER.ImageBase
        self.u = Uc(UC_ARCH_X86, UC_MODE_32)
        self.u.mem_map(0, 0x1000) # Native floating event's fs:[0] SEH chain.
        size = (self.pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095
        self.u.mem_map(self.base, size)
        self.u.mem_write(self.base, self.pe.get_memory_mapped_image())
        self.u.mem_map(0x20000000, 0x08000000)
        self.u.mem_map(0x30000000, 0x10000)
        self.heap = 0x20000000
        self.stop = 0x30000000
        self.texts = []
        self.images = []
        self.forwards = []
        self.textures = {}
        self.asset_pixels = {}
        self.assets = assets
        self.cs = capstone.Cs(capstone.CS_ARCH_X86, capstone.CS_MODE_32)
        self.stub(0xA1CB30, self.clear)
        self.stub(0xA245C0, self.resize)
        self.stub(0x85F630, self.resize)
        self.stub(0xA1CB70, self.resize)
        self.stub(0xA23340, lambda: self.ret(0))
        self.stub(0xA90350, lambda: self.ret(0, 0x20000000))
        self.stub(0xA9F030, lambda: self.ret(0, self.args(1)[0]))
        self.stub(0xA8D4A0, self.texture)
        self.stub(0xA25A70, self.text)
        self.stub(0xA21C90, lambda: self.ret(24,len(self.cstr(self.args(6)[0]))*6))
        self.stub(0x851960, self.native_pane)
        self.stub(0x824870, self.native_edit)
        self.stub(0x824FC0, self.native_edit)
        self.stub(0x857910, lambda: self.forward('other_tab', 0))
        self.stub(0x8F6C20, lambda: self.forward('click', 2))
        self.stub(0x8FC220, lambda: self.forward('event', 6))
        # OS/window-manager boundaries only. Execute real TabCtrl selection,
        # BeginWindowDrag, main mouse-move, coordinate conversion and release.
        self.stub(0xA36FA0, lambda: self.ret(4))
        self.stub(0x7A8550, lambda: self.ret(4))
        self.stub(0x7A87F0, lambda: self.ret(4))
        self.stub(0x7A8BB0, lambda: self.ret(4,0))
        self.stub(0x874AF0, self.position)
        self.stub(0xA482E0, self.release_capture)
        self.stub(0xA4B760, self.focus)
        self.stub(0xDBBBD4, lambda: self.ret(0))
        tick=self.alloc(16); self.stub(tick,lambda: self.ret(0,1000)); self.w(0xFC17B0,tick)
        # This layout suite exercises the native-font fallback. The separate
        # controls/font suite exercises successful private GDI font creation.
        no_gdi=self.alloc(16); self.stub(no_gdi,lambda:self.ret(4,0)); self.w(0xFC1268,no_gdi)
        self.w(0x1602614,1920); self.w(0x1602618,1080)

    def stub(self, address, fn):
        self.u.hook_add(UC_HOOK_CODE, lambda u,a,s,d: fn(), begin=address, end=address)

    def alloc(self, size):
        address = self.heap
        self.heap += (size + 15) & ~15
        assert self.heap < 0x28000000
        return address

    def r(self, address):
        return struct.unpack('<I', self.u.mem_read(address,4))[0]

    def w(self, address, value):
        self.u.mem_write(address, pack(value))

    def cstr(self, address):
        return bytes(self.u.mem_read(address, 256)).split(b'\0')[0].decode('latin1')

    def args(self, count):
        sp = self.u.reg_read(UC_X86_REG_ESP)
        return [self.r(sp+4+i*4) for i in range(count)]

    def ret(self, cleanup, value=0):
        sp = self.u.reg_read(UC_X86_REG_ESP)
        target = self.r(sp)
        self.u.reg_write(UC_X86_REG_ESP, sp+4+cleanup)
        self.u.reg_write(UC_X86_REG_EAX, value)
        self.u.reg_write(UC_X86_REG_ECX, 0xCCCCCCCC)
        self.u.reg_write(UC_X86_REG_EDX, 0xDDDDDDDD)
        self.u.reg_write(UC_X86_REG_EIP, target)

    def invoke(self, address, obj, args=()):
        sp = 0x3000F000
        self.u.mem_write(sp, pack(self.stop)+b''.join(pack(a) for a in args))
        for reg,value in [(UC_X86_REG_EBX,0xBBBBBBBB),(UC_X86_REG_ESI,0xEEEEEEEE),
                          (UC_X86_REG_EDI,0xFFFFFFFF),(UC_X86_REG_EBP,0xABABABAB)]:
            self.u.reg_write(reg,value)
        self.u.reg_write(UC_X86_REG_ECX,obj)
        self.u.reg_write(UC_X86_REG_ESP,sp)
        self.u.emu_start(address,self.stop,count=12000000)
        assert self.u.reg_read(UC_X86_REG_EIP)==self.stop, 'did not return'
        assert self.u.reg_read(UC_X86_REG_ESP)==sp+4+len(args)*4, 'stack imbalance'
        for reg,value in [(UC_X86_REG_EBX,0xBBBBBBBB),(UC_X86_REG_ESI,0xEEEEEEEE),
                          (UC_X86_REG_EDI,0xFFFFFFFF),(UC_X86_REG_EBP,0xABABABAB)]:
            assert self.u.reg_read(reg)==value, 'callee-save register corrupted'

    def window(self,w=594,h=240,vt=0x1037F80,parent=0):
        obj = self.alloc(0x200)
        self.w(obj,vt)
        self.w(obj+0x10,parent)
        self.w(obj+0x30,1)
        self.setsize(obj,w,h)
        return obj

    def setsize(self,obj,w,h):
        assert 0 < w <= 2048 and 0 < h <= 2048, (w,h)
        self.w(obj+0x14,w); self.w(obj+0x18,h)
        surf=self.alloc(0x40); pix=self.alloc(w*h*4)
        self.w(surf+4,w); self.w(surf+8,h); self.w(surf+0x18,pix)
        self.w(obj+0x24,surf)

    def pixels(self,obj):
        surf=self.r(obj+0x24)
        return self.r(surf+0x18),self.r(surf+4),self.r(surf+8)

    def resize(self):
        self.setsize(self.u.reg_read(UC_X86_REG_ECX),*self.args(2)); self.ret(8)

    def position(self):
        obj=self.u.reg_read(UC_X86_REG_ECX)
        x,y=self.args(2); self.w(obj+0x1c,x); self.w(obj+0x20,y); self.ret(8)

    def release_capture(self):
        self.w(0x131F4E8+0x19c,0); self.ret(0)

    def focus(self):
        self.w(0x131F4E8+0x1a0,self.args(1)[0]); self.ret(4)

    def clear(self):
        pix,w,h=self.pixels(self.u.reg_read(UC_X86_REG_ECX))
        self.u.mem_write(pix,pack(self.args(1)[0])*(w*h)); self.ret(4)

    def texture(self):
        name=self.cstr(self.args(1)[0]).split('\\')[-1]
        self.ret(4,self.load_texture(name))

    def load_texture(self, name):
        if name not in self.textures:
            obj=self.alloc(0x130)
            with Image.open(self.assets/name) as src:
                im=src.convert('RGBA')
                w,h=im.size
                data=im.tobytes('raw','BGRA')
            pixels=self.alloc(len(data))
            self.u.mem_write(pixels,data)
            self.w(obj+0x110,1); self.w(obj+0x11c,pixels)
            self.w(obj+0x114,w); self.w(obj+0x118,h)
            self.textures[name]=obj
            self.asset_pixels[name]=list(struct.unpack('<'+'I'*(w*h),data))
        return self.textures[name]

    def image(self):
        obj=self.u.reg_read(UC_X86_REG_ECX)
        x,y,tex,flag=self.args(4)
        name=next(k for k,v in self.textures.items() if v==tex)
        self.images.append((name,x,y,obj))
        assert x<2048 and y<2048,(name,x,y)

    def text(self):
        obj=self.u.reg_read(UC_X86_REG_ECX)
        x,y,string,_,_,height,color,_,_=self.args(9)
        self.texts.append((self.cstr(string),x,y,obj))
        pix,w,h=self.pixels(obj)
        assert x<w and y<h,(x,y,w,h)
        self.w(pix+(y*w+x)*4,color) # GDI-like zero-alpha foreground pixel
        self.ret(36)

    def native_pane(self):
        obj=self.u.reg_read(UC_X86_REG_ECX)
        if self.r(obj+0x10)==0:
            self.forwards.append(('other_pane',[])); self.ret(0); return
        pix,w,h=self.pixels(obj)
        self.u.mem_write(pix,pack(0xFFFF00FF)*(w*h))
        for i,value in enumerate([0xFFFF00FF,0x00FF00FF,0,0x0000FF00,0x00FFFFFF,0x80304050,0xFF000000]):
            self.w(pix+i*4,value)
        self.ret(0)

    def native_edit(self):
        obj=self.u.reg_read(UC_X86_REG_ECX)
        if self.r(obj+0x10)==0:
            self.forwards.append(('other_edit',[])); self.ret(0); return
        assert self.r(obj+0x8C)==1
        assert self.r(obj+0xF4)==0,'native text/caret inset was not normalized'
        color=self.r(obj+0x90)|(self.r(obj+0x94)<<8)|(self.r(obj+0x98)<<16)
        assert color==0xFF00FF
        assert self.r(obj+0xA8)==0xC7C7C7
        pix,w,h=self.pixels(obj)
        self.u.mem_write(pix,pack(color)*(w*h))
        self.w(pix+4,self.r(obj+0xA8))
        self.w(pix+8,0) # Native black caret must not become a transparent hole.
        self.ret(0)

    def forward(self,name,count):
        if name=='event' and self.args(count)[1]==0x16:
            self.w(self.u.reg_read(UC_X86_REG_ECX)+0x114,self.args(count)[2])
        self.forwards.append((name,self.args(count))); self.ret(count*4,0x12345678)

    def targets(self,address,limit=2048):
        ins=self.cs.disasm(bytes(self.u.mem_read(address,limit)),address)
        return [int(i.op_str,16) for i in ins if i.mnemonic=='call' and i.op_str.startswith('0x')]

    def setup(self,w=594,h=240,names=('Main','Market','Battle','Party','Guild')):
        parent=self.window(w,h)
        tab=self.window(355,16,0x102DD44,parent)
        self.w(tab+0x80,1) # horizontal UITabCtrl
        edit_vt=self.alloc(0xE0); set_text=self.alloc(16)
        self.stub(set_text,lambda: self.ret(4))
        self.w(edit_vt+0xD4,set_text); self.w(edit_vt+0x10,0xA23450)
        self.w(tab+0xD8,self.window(10,10,edit_vt,tab))
        self.w(parent+0x138,tab); self.w(parent+0x124,42)
        for off in [0xB8,0xBC,0xC0,0xE0,0xE4,0xE8,0x100,0x104,0x128,0x12C]:
            child=self.window(9,9,0x102DD44,parent)
            self.w(parent+off,child)
        namesptr=self.alloc(24*len(names)); widths=self.alloc(4*len(names))
        self.w(tab+0xB4,namesptr); self.w(tab+0xB8,namesptr+24*len(names))
        self.w(tab+0xCC,widths); self.w(tab+0xD0,widths+4*len(names))
        for i,name in enumerate(names):
            self.u.mem_write(namesptr+i*24,name.encode()+b'\0')
            self.w(namesptr+i*24+16,len(name)); self.w(namesptr+i*24+20,15)
            self.w(widths+i*4,71)
        panes=self.alloc(4*len(names))
        self.w(parent+0xF4,panes); self.w(parent+0xF8,panes+4*len(names))
        for i in range(len(names)):
            self.w(panes+i*4,self.window(w-8,h-62,0x102D280,parent))
        return parent,tab

def main():
    p=argparse.ArgumentParser(); p.add_argument('exe')
    p.add_argument('--assets',type=Path,default=ASSETS); args=p.parse_args()
    m=Machine(args.exe,args.assets)
    main_draw=m.r(0x1037FD0); shared_tab_draw=m.r(0x102DD94); pane_draw=m.r(0x102D2D0)
    assert main_draw!=0x8F3340 and pane_draw!=0x851960,'patch absent'
    names=('Main','Market','Battle','Party','Guild')
    png_draw=next(t for t in m.targets(main_draw)
                  if bytes(m.u.mem_read(t,12))==bytes.fromhex('55 8b ec 83 ec 20 53 56 57 8b 71 24'))
    m.stub(png_draw,m.image) # Observe only; run the real emitted PNG compositor.
    parent,tab=m.setup()
    for active in (0,1):
        m.u.mem_write(0x131F50C,bytes([active])); m.texts.clear(); m.images.clear()
        m.invoke(main_draw,parent)
        assert m.r(tab)!=0x102DD44,'chat must have an instance-owned tab vtable'
        tab_draw=m.r(m.r(tab)+0x50)
        assert tab_draw!=shared_tab_draw,'inventory skin must not own chat paint'
        assert m.r(tab+0x1C)==3 and m.r(tab+0x20)==220
        assert m.r(tab+0x14)==530 and m.r(tab+0x18)==20
        assert m.r(m.r(parent+0xB8)+0x1C)==0xFFFFFF9C,'white dialog layer visible'
        assert m.r(m.r(parent+0x12C)+0x1C)==549
        assert m.r(m.r(parent+0x12C)+0x20)==226
        assert not any(name.startswith('textbox_') for name,_,_,_ in m.images)
        assert any(row[:3]==('btn_emote2.png',549,202) for row in m.images)
        assert any(row[:3]==('icon_direct.png',574,203) for row in m.images)
        for off in (0xE0,0xE4,0xE8):
            assert m.r(m.r(parent+off)+0x20)==0xFFFFFF9C,'recipient selector visible'
        message=m.r(parent+0xBC)
        assert m.r(message+0x20)==(200 if active else 0xFFFFFF9C)
        recipient=m.r(parent+0xC0)
        assert m.r(recipient+0x20)==(200 if active else 0xFFFFFF9C)
        if active:
            assert (m.r(message+0x1c),m.r(message+0x14),m.r(message+0x18))==(116,423,16)
            assert (m.r(recipient+0x1c),m.r(recipient+0x14),m.r(recipient+0x18))==(23,81,16)
        assert any('Enter to type' in x[0] for x in m.texts)==(not active)
        pix,w,h=m.pixels(parent)
        assert m.r(pix+(10*w+10)*4)==0x80111114,'message panel is not translucent'
        assert m.r(pix+(198*w+3)*4)==0x80404040,'input gray missing'
        assert m.r(pix+(208*w+297)*4)==0x80404040
        assert m.r(pix+(230*w+544)*4)==0x80404040,'settings/lock backing absent'
        assert m.r(pix+(230*w+564)*4)==0x807C808B,'control divider absent'
        assert m.r(pix+(208*w+108)*4)==0xA0A0A3AA,'PM divider absent'
        assert any(name=='icon_lock_on.png' for name,_,_,_ in m.images)
        for selected in range(5):
            m.w(parent+0x114,selected); m.w(tab+0x7C,selected)
            m.invoke(main_draw,parent)
            m.texts.clear(); m.images.clear(); m.invoke(tab_draw,tab)
            assert [x[0] for x in m.texts]==list(names),m.texts
            assert [x[1] for x in m.texts]==[(106-len(n)*6)//2+i*106 for i,n in enumerate(names)]
            assert not m.images,'tab icons must not be drawn'
            pix,w,h=m.pixels(tab)
            data=bytes(m.u.mem_read(pix,w*h*4))
            assert pack(0xFFFF00FF) not in data
            expected=0x80292C34 if selected==0 else 0x801E2026
            assert m.r(pix+(3*w+30)*4)==expected,'tab background is not translucent'
            for index,(_,x,y,_) in enumerate(m.texts):
                assert m.r(pix+(y*w+x)*4)==(0xFFFFFFFF if index==selected else 0xFFC7C7C7)
            for i in range(1,5):
                assert m.r(pix+(10*w+i*106-1)*4)==0,'tab partition gap absent'
                assert m.r(pix+(10*w+i*106)*4)!=0,'tab border absent'
            for i in range(5):
                pane=m.r(m.r(parent+0xF4)+4*i)
                assert m.r(pane+0x20)==(4 if i==selected else 0xFFFFFF9C)
    pane=m.r(m.r(parent+0xF4)); m.invoke(pane_draw,pane)
    pix,_,_=m.pixels(pane)
    assert [m.r(pix+4*i) for i in range(7)]==[0,0,0,0xFF00FF00,0xFFFFFFFF,0x80304050,0xFF000000]
    # Other UI list/tab surfaces retain their original native implementation.
    other=m.window(100,100,0x102DD44,0); m.invoke(tab_draw,other)
    assert m.forwards[-1][0]=='other_tab'
    m.invoke(pane_draw,other); assert m.forwards[-1][0]=='other_pane'
    for slot in (0x1028DFC,0x1028EE8):
        edit=m.window(90,16,slot-0x50,parent)
        m.invoke(m.r(slot),edit)
        pix,_,_=m.pixels(edit)
        assert m.r(pix)==0x80404040 and m.r(pix+4)==(0xFF000000 | m.r(edit+0xA8))
        assert m.r(pix+8)==0xFF000000,'black native caret erased'
        m.invoke(m.r(slot),other); assert m.forwards[-1][0]=='other_edit'
    # Obsolete textbox PNG recoloring cannot change the new uniform gray input.
    tex=m.load_texture('textbox_off.png'); tw,th=m.r(tex+0x114),m.r(tex+0x118)
    center=m.r(tex+0x11c)+(th//2*tw+tw//2)*4
    original_center=m.r(center); m.w(center,0xFF171923)
    m.invoke(m.r(0x1028DFC),edit); assert m.r(edit+0xA8)==0xC7C7C7
    m.w(center,0xFFF7FAFE)
    m.invoke(m.r(0x1028DFC),edit); assert m.r(edit+0xA8)==0xC7C7C7
    m.w(center,original_center)
    click=m.r(0x1037FE4); event=m.r(0x1038014)
    for active in (0,1):
        for x in (8,100,107,108,116,200,542):
            before=len(m.forwards); m.u.mem_write(0x131F50C,bytes([active]))
            m.w(0x131F4E8+0x19c,0); m.invoke(click,parent,[x,205])
            assert len(m.forwards)==before,'input click reached stock recipient/drag handling'
            assert bytes(m.u.mem_read(0x131F50C,1))==b'\1'
            target=m.r(parent+(0xC0 if x<108 else 0xBC))
            assert m.r(0x131F4E8+0x1a0)==target
            assert m.r(parent+0xB4)==target,'native last-focused chat edit not updated'
            assert m.r(0x131F4E8+0x19c)==0,'input click started window dragging'
    m.stub(0xA39340,lambda:(m.forwards.append(('emoji_window',m.args(1)[0])),m.ret(4)))
    for active in (0,1):
        for x in (543,550,566,567,580,590):
            m.u.mem_write(0x131F50C,bytes([active]));before=len(m.forwards)
            m.invoke(click,parent,[x,205])
            expected=('emoji_window',0x57) if x<567 else ('event',[m.r(parent+0xBC),6,0xB8,0,0,0])
            assert m.forwards[before:]==[expected]
            assert m.r(parent+0xB4)==m.r(parent+0xBC)
    for x,y in [(2,205),(591,205),(567,197),(567,218)]:
        before=len(m.forwards);m.invoke(click,parent,[x,y])
        assert len(m.forwards)==before,'outside control bounds submitted chat'
    for slot in (0x1028DC0,0x1028EAC):
        assert m.r(slot)==0x5A4960,'native recipient keyboard focus still disabled'
        m.invoke(m.r(slot),m.r(parent+0xC0)); assert m.u.reg_read(UC_X86_REG_EAX)&255==1
        m.invoke(m.r(slot),m.r(parent+0xBC)); assert m.u.reg_read(UC_X86_REG_EAX)&255==1
        m.invoke(m.r(slot),other); assert m.u.reg_read(UC_X86_REG_EAX)&255==1
    for off in (0xE0,0xE4,0xE8):
        before=len(m.forwards); m.invoke(event,parent,[m.r(parent+off),6,0,0,0,0])
        assert len(m.forwards)==before,'removed selector dispatched a popup'
    m.invoke(event,parent,[m.r(parent+0xC0),6,0,0,0,0])
    assert m.forwards[-1]==('event',[m.r(parent+0xC0),6,0,0,0,0])
    for x,mapped in [(575,False),(576,True),(583,True),(584,False)]:
        before=len(m.forwards); m.invoke(click,parent,[x,225])
        if mapped: assert m.forwards[-1]==('click',[577,5])
        else: assert len(m.forwards)==before
    before=len(m.forwards); m.invoke(event,parent,[tab,0x74,0,0,0,0])
    assert len(m.forwards)==before
    for unlocked in (0,1):
        m.u.mem_write(0x15FAAEC,bytes([unlocked]))
        for kind in (0x75,0x76):
            m.invoke(event,parent,[tab,kind,0,0,0,0])
            assert m.forwards[-1]==('event',[tab,kind,0,0,0,0]),'native detach/dock suppressed'
        m.images.clear(); m.invoke(main_draw,parent)
        assert any(name==f'icon_lock_{"off" if unlocked else "on"}.png' for name,_,_,_ in m.images)
    tab_click=m.r(m.r(tab)+0x64)
    assert tab_click==0x858B90,'native tab selection/capture not retained'
    assert m.r(m.r(tab)+0x6c)==0x85A620,'native tab detachment not retained'
    assert m.r(0x102DD44+0x6c)==0x85A620,'drag handler of unrelated tabs changed'
    assert m.r(0x1037F80+0x6c)==0x8F87C0 and m.r(0x1037F80+0x7c)==0x8F72E0
    pane_vector=(m.r(parent+0xF4),m.r(parent+0xF8))
    names_vector=bytes(m.u.mem_read(m.r(tab+0xB4),5*24))
    for unlocked in (0,1):
        m.u.mem_write(0x15FAAEC,bytes([unlocked]))
        for index in range(5):
            m.w(parent+0x1c,100); m.w(parent+0x20,120)
            m.w(0x131F4E8+0x19c,0)
            x,y=40+106*index,8
            m.invoke(tab_click,tab,[x,y])
            assert m.r(tab+0x7c)==index and m.r(parent+0x114)==index
            assert m.r(0x131F4E8+0x19c)==tab
            m.w(tab+0xAC,0); m.w(tab+0xB0,0)
            m.invoke(m.r(m.r(tab)+0x6c),tab,[x,0xffffffd8])
            assert m.forwards[-1]==('event',[tab,0x75,index,0,0,0])
            m.invoke(m.r(m.r(tab)+0x7c),tab,[x,0xffffffd8])
            assert m.r(0x131F4E8+0x19c)==0
            # Unoccupied frame starts main dragging, not tab capture.
            m.invoke(click,parent,[2,30])
            assert m.r(0x131F4E8+0x19c)==(parent if unlocked else 0)
            if unlocked: assert m.r(parent+0x7c)==102 and m.r(parent+0x80)==150
            m.invoke(m.r(0x1037F80+0x6c),parent,[27,60])
            expected=(125,150) if unlocked else (100,120)
            assert (m.r(parent+0x1c),m.r(parent+0x20))==expected
            m.invoke(m.r(m.r(parent)+0x7c),parent,[0,0])
            assert m.r(0x131F4E8+0x19c)==0
            m.invoke(m.r(0x1037F80+0x6c),parent,[3+x+50,220+y+60])
            assert (m.r(parent+0x1c),m.r(parent+0x20))==expected,'drag continues after release'
            assert (m.r(parent+0xF4),m.r(parent+0xF8))==pane_vector
            assert bytes(m.u.mem_read(m.r(tab+0xB4),5*24))==names_vector
            assert (m.r(tab+0x1c),m.r(tab+0x20))==(3,220),'tab moved independently'
    m.invoke(tab_click,tab,[800,8]); assert m.r(0x131F4E8+0x19c)==0,'miss captured chat'
    m.invoke(event,parent,[tab,0x16,3,0,0,0])
    assert m.forwards[-1]==('event',[tab,0x16,3,0,0,0])
    # Replacement dock gate admits a returning page at the new equal widths.
    jump=next(m.cs.disasm(bytes(m.u.mem_read(0x8FC637,5)),0x8FC637))
    assert jump.mnemonic=='jmp'
    dock_gate=int(jump.op_str,16); dock_capacity=m.targets(dock_gate,16)[0]
    for count in (1,4,5,11,12):
        for width in (180,300,594,800):
            dock_parent,_=m.setup(width,100,tuple(f'Tab{i}' for i in range(count)))
            m.invoke(dock_capacity,dock_parent)
            assert m.u.reg_read(UC_X86_REG_EAX)==int(count<12 and width-60>=(count+1)*32)
    # Scoped native event clear operations must not flash magenta on alpha surfaces.
    for site in (0x8F6CE7,0x8FC555,0x8FC9C2,0x8FCAD8,0x8FCB33,0x8FE02A,0x8FE229,0x9022A2,0x90235D):
        assert bytes(m.u.mem_read(site,5))==bytes.fromhex('68 00 00 00 00')
    # Floating title/body skin, opaque text, native gear and return control.
    floating=m.window(320,200,0x1037EA8)
    m.u.mem_write(floating+0x114,b'Battle\0'); m.w(floating+0x124,6); m.w(floating+0x128,15)
    for offset in (0xDC,0xE0,0xE4):
        m.w(floating+offset,m.window(9,9,0x102DD44,floating))
    float_pane=m.window(312,165,0x102D280,floating)
    m.w(floating+0xB4,float_pane)
    for unlocked in (0,1):
        m.u.mem_write(0x15FAAEC,bytes([unlocked])); m.texts.clear()
        m.invoke(m.r(0x1037EA8+0x50),floating)
        assert m.texts==[('Battle',5,3,floating)]
        pix,w,h=m.pixels(floating)
        assert m.r(pix+(20*w+20)*4)==0x80111114
        assert m.r(pix+(3*w+5)*4)==0xFFC7C7C7
        assert m.r(m.r(floating+0xE4)+0x1c)==0xFFFFFF9C
        assert m.r(m.r(floating+0xE0)+0x1c)==292
        assert m.r(m.r(floating+0xDC)+0x1c)==(308 if unlocked else 0xFFFFFF9C)
        m.invoke(pane_draw,float_pane); pix,_,_=m.pixels(float_pane)
        assert [m.r(pix+4*i) for i in range(7)]==[0x80111114]*3+[0xFF00FF00,0xFFFFFFFF,0x80304050,0xFF000000]
        assert m.r(pix+(m.r(float_pane+0x14)*m.r(float_pane+0x18)-1)*4)==0x80111114
    # Execute the real floating dispatcher: 0x165 docks; 0xCA DELETES a page.
    m.w(0x131F6B0,parent)
    m.invoke(m.r(0x1037EA8+0x94),floating,[m.r(floating+0xDC),6,0x165,0,0,0])
    assert m.forwards[-1]==('event',[floating,0x76,0,0,0,0]),m.forwards[-3:]
    # Execute floating move/resize and its native drag-back release path.
    # Only saved-map lookup, absent settings dialog, and text reflow are doubled.
    float_record=m.alloc(0x80)
    m.stub(0x8DAC90,lambda:m.ret(4,float_record))
    find_main=[0]
    m.stub(0xA47B90,lambda:m.ret(4,find_main[0] if m.args(1)[0]==1 else 0))
    m.stub(0x8642D0,lambda:m.ret(0))
    m.w(floating+0xE8,16); m.w(floating+0xF0,15)
    m.w(floating+0xBC,m.window(14,14,0x102DD44,floating))
    m.w(float_pane+0x1c,5); m.w(float_pane+0x20,20)
    for unlocked in (0,1):
        m.u.mem_write(0x15FAAEC,bytes([unlocked]))
        m.w(floating+0x1c,600); m.w(floating+0x20,300); m.w(0x131F4E8+0x19c,0)
        m.invoke(m.r(0x1037EA8+0x64),floating,[30,8])
        assert m.r(0x131F4E8+0x19c)==(floating if unlocked else 0)
        m.invoke(m.r(0x1037EA8+0x6c),floating,[55,38])
        expected=(625,330) if unlocked else (600,300)
        assert (m.r(floating+0x1c),m.r(floating+0x20))==expected
        if unlocked: assert (m.r(float_record+0x34),m.r(float_record+0x38))==expected
        m.invoke(m.r(0x1037EA8+0x7c),floating,[55,38])
        assert m.r(0x131F4E8+0x19c)==0
    m.invoke(m.r(0x1037EA8+4),floating,[360,240])
    m.invoke(m.r(0x1037EA8+0x50),floating)
    assert (m.r(float_pane+0x14),m.r(float_pane+0x18))==(352,205)
    assert (m.r(float_record+0x3c),m.r(float_record+0x40))==(360,240)
    assert m.r(m.r(floating+0xDC)+0x1c)==348
    assert m.r(m.r(floating+0xE0)+0x1c)==332
    assert m.r(m.r(floating+0xE4)+0x1c)==0xFFFFFF9C
    find_main[0]=parent
    m.w(parent+0x1c,100); m.w(parent+0x20,120)
    m.w(floating+0x1c,150); m.w(floating+0x20,100)
    m.invoke(m.r(0x1037EA8+0x64),floating,[30,8])
    m.invoke(m.r(0x1037EA8+0x7c),floating,[30,8])
    assert m.forwards[-1]==('event',[floating,0x76,0,0,0,0]),'native drag-back dock suppressed'
    find_main[0]=0
    # Button resource setters retain native IDs/callbacks and use supplied PNGs.
    def resource_setter(argc):
        m.forwards.append(('resource',m.cstr(m.args(argc)[0]),m.args(argc)[1:]))
        m.ret(argc*4)
    m.stub(0x82DAC0,lambda:resource_setter(3))
    m.stub(0x82DA00,lambda:resource_setter(1))
    for sites,filename,argc in [((0x8F0933,0x8F0972,0x8F09B1),'icon_settings.png',3),
                               ((0x8F072A,0x8F0769,0x8F07A8),'btn_min.png',3),
                               ((0x8F0D25,),'btn_expand.png',1)]:
        for site in sites:
            target=m.targets(site,5)[0]
            m.invoke(target,floating,[0xDEADBEEF]+list(range(argc-1)))
            assert m.forwards[-1][1].endswith('\\'+filename)
            assert m.forwards[-1][2]==list(range(argc-1))
    # Actual edit-layout trampoline executes both native branches then reapplies bottom layout.
    for active in (0,1):
        m.u.mem_write(0x131F50C,bytes([active])); m.invoke(0x8F9840,parent)
        assert m.r(m.r(parent+0xB8)+0x20)==0xFFFFFF9C
        assert m.r(tab+0x20)==220
    for width,height in [(600,298),(800,360),(594,120)]:
        m.setsize(parent,width,height); m.invoke(main_draw,parent)
        assert m.r(tab+0x20)==height-20
        step=(width-60)//5
        assert m.r(tab+0x14)==step*5
        m.texts.clear(); m.invoke(tab_draw,tab)
        assert len(m.texts)==5
        pix,w,h=m.pixels(parent)
        assert m.r(pix+((height-42)*w+width-4)*4)==0x80404040,'input backing ends early'
        assert m.r(pix+((height-32)*w+width-5)*4)!=0,'input did not extend to right edge'
        # Drawing and native hit-testing must agree at EVERY divider boundary.
        for i in range(1,5):
            m.invoke(0x848E60,tab,[i*step-1,8]); assert m.u.reg_read(UC_X86_REG_EAX)==i-1
            m.invoke(0x848E60,tab,[i*step,8]); assert m.u.reg_read(UC_X86_REG_EAX)==i
    # Execute the actual native PM-vs-public send branch and recipient getters.
    # The final game/network dispatcher is a test double: no messages are sent.
    dispatch=m.alloc(16); dispatch_vt=m.alloc(0x30); game=m.alloc(0x20)
    m.w(game,dispatch_vt); m.w(dispatch_vt+0x18,dispatch); m.w(0x121333C,game)
    m.stub(dispatch,lambda:(m.forwards.append(('whisper',m.args(5)[0],m.cstr(m.args(5)[1]))),m.ret(20)))
    m.stub(0x4F1940,lambda:m.ret(8)) # Assign last-message string, outside routing contract.
    def branch_exit(kind):
        m.forwards.append(('route_exit',kind)); m.u.emu_stop()
    m.stub(0x8FCCBA,lambda:branch_exit('whisper'))
    m.stub(0x8FDC9D,lambda:branch_exit('public_or_command'))
    recipient=m.r(parent+0xC0)
    for name,message,private in [('WhisperTarget','PM test',True),('', 'Public test',False),
                                 ('WhisperTarget','/where',False)]:
        m.u.mem_write(recipient+0xD8,name.encode()+b'\0')
        m.w(recipient+0xE8,len(name)); m.w(recipient+0xEC,15)
        m.w(0x131F4E8+0x1A0,m.r(parent+0xBC))
        frame,sp=0x3000E800,0x3000D000
        m.u.mem_write(frame-0x198,message.encode()+b'\0')
        m.u.reg_write(UC_X86_REG_EBP,frame); m.u.reg_write(UC_X86_REG_EDI,parent)
        m.u.reg_write(UC_X86_REG_ESP,sp)
        before=len(m.forwards); m.u.emu_start(0x8FDC30,m.stop,count=10000)
        assert m.u.reg_read(UC_X86_REG_ESP)==sp,'native whisper route stack imbalance'
        if private:
            assert m.forwards[before:]==[('whisper',0x0B,name),('route_exit','whisper')]
        else: assert m.forwards[before:]==[('route_exit','public_or_command')]
    # Pixel-level tests use every real supplied PNG, not placeholder image stubs.
    surface=m.window(602,32)
    pix,w,h=m.pixels(surface)
    for asset in sorted(args.assets.glob('*.png')):
        tex=m.load_texture(asset.name); tw,th=m.r(tex+0x114),m.r(tex+0x118)
        for background in (0,0xFF19202A,0x80333753):
            m.u.mem_write(pix,pack(background)*(w*h))
            m.invoke(png_draw,surface,[3,2,tex,0])
            for sy in range(th):
                actual=list(struct.unpack('<'+'I'*tw,m.u.mem_read(pix+((sy+2)*w+3)*4,tw*4)))
                expected=[over(p,background) for p in m.asset_pixels[asset.name][sy*tw:(sy+1)*tw]]
                assert actual==expected,(asset.name,background,sy)
            assert m.r(pix+(2*w+2)*4)==background
            assert m.r(pix+(2*w+3+tw)*4)==background
    print('PASS: x86 stack/register preservation, five page identities/selections, resized bottom layout,')
    print('      supplied PNGs, uniform gray input in both focus states, preserved black caret,')
    print('      visible GDI text, magenta cleanup, scoped hooks, native detach notifications,')
    print('      native selection forwarding, lock boundaries/icons and input trampoline.')
    print('      translucent main/floating panels; native whole-window drag/release from frame.')
    print('      native floating return button -> dock event; resized docking capacity; supplied controls.')
    print('      restored PM recipient, native focus/events, visible divider, centered input and gray controls.')
    print('      actual native whisper/public routing and exact tab hit-test partition boundaries.')
    print('      separate Emoji List/send hit regions, centered text-only tabs, native font fallback.')

if __name__=='__main__': main()
