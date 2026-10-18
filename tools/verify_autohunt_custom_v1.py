"""Execute the emitted custom UI and original AHUI handlers against mocked engine boundaries.

This verifies x86 ABI, settings packets, hit geometry and pixels. It does not
substitute for running the resulting client in-game.
"""
from pathlib import Path
import argparse
import json
import re
import struct
import pefile
import unicorn as uc
from unicorn import x86_const as x
from PIL import Image, ImageDraw, ImageFont

WINDOW, STACK, STOP, HEAP = 0x50000000, 0x60000000, 0x70000000, 0x51000000

def verify_gdi_alpha():
    """Reproduce the actual Windows GDI alpha behavior missed by RGB previews."""
    import ctypes as ct
    from ctypes import wintypes as wt
    g=ct.WinDLL('gdi32',use_last_error=True)
    g.CreateCompatibleDC.argtypes=[wt.HDC];g.CreateCompatibleDC.restype=wt.HDC
    g.CreateDIBSection.argtypes=[wt.HDC,ct.c_void_p,wt.UINT,ct.POINTER(ct.c_void_p),wt.HANDLE,wt.DWORD];g.CreateDIBSection.restype=wt.HBITMAP
    g.CreateFontW.argtypes=[ct.c_int]*5+[wt.DWORD]*8+[wt.LPCWSTR];g.CreateFontW.restype=wt.HFONT
    g.SelectObject.argtypes=[wt.HDC,wt.HGDIOBJ];g.SelectObject.restype=wt.HGDIOBJ
    g.DeleteObject.argtypes=[wt.HGDIOBJ];g.DeleteDC.argtypes=[wt.HDC]
    g.SetBkMode.argtypes=[wt.HDC,ct.c_int];g.SetTextColor.argtypes=[wt.HDC,wt.DWORD]
    g.TextOutW.argtypes=[wt.HDC,ct.c_int,ct.c_int,wt.LPCWSTR,ct.c_int]
    dc=g.CreateCompatibleDC(None);assert dc
    info=struct.pack('<IiiHHIIiiII',40,300,-40,1,32,0,300*40*4,0,0,0,0)
    bits=ct.c_void_p();bitmap=g.CreateDIBSection(dc,info,0,ct.byref(bits),None,0);assert bitmap and bits.value
    font=g.CreateFontW(-15,0,0,0,400,0,0,0,0,0,0,0,0,'Arial');assert font
    old_bitmap=g.SelectObject(dc,bitmap);old_font=g.SelectObject(dc,font)
    try:
        ct.memset(bits,255,300*40*4);g.SetBkMode(dc,1);g.SetTextColor(dc,0x63524A)
        value='Use Normal Attack';assert g.TextOutW(dc,4,4,value,len(value));g.GdiFlush()
        raw=ct.string_at(bits,300*40*4)
        foreground=[raw[i:i+4] for i in range(0,len(raw),4) if raw[i:i+3]!=b'\xff\xff\xff']
        assert foreground and any(pixel[3]==0 for pixel in foreground), 'GDI alpha reproduction changed'
        return {'passed':True,'native_gdi_pixels':len(foreground),'zero_alpha_foreground_pixels':sum(p[3]==0 for p in foreground),'required_composition':'opaque','live_accepted':False}
    finally:
        g.SelectObject(dc,old_font);g.SelectObject(dc,old_bitmap);g.DeleteObject(font);g.DeleteObject(bitmap);g.DeleteDC(dc)

class Machine:
    def __init__(self, directory, game=None):
        self.directory, self.game = directory, game
        self.manifest = json.loads((directory / 'manifest.json').read_text())['autohunt']
        self.custom = self.manifest['customV1']
        assert self.custom
        self.pe = pefile.PE(str(directory / 'autohunt.exe'))
        self.u = uc.Uc(uc.UC_ARCH_X86, uc.UC_MODE_32)
        base = self.pe.OPTIONAL_HEADER.ImageBase
        self.u.mem_map(base, (self.pe.OPTIONAL_HEADER.SizeOfImage + 4095) & ~4095)
        self.u.mem_write(base, self.pe.get_memory_mapped_image())
        for address, size in [(WINDOW, 0x10000), (HEAP, 0x10000), (STACK, 0x10000), (STOP, 0x1000)]:
            self.u.mem_map(address, size)
        self.cfg = self.custom['config']
        self.state = self.cfg[1]
        self.rows, self.keys = self.cfg[11:20], self.cfg[20:24]
        self.write(WINDOW + 0x14, 760); self.write(WINDOW + 0x18, 520)
        self.u.mem_write(WINDOW + 0x38, b'\xff')
        self.write(WINDOW + 0x28, 1)
        self.write(WINDOW + 0x24, HEAP + 0x7000)
        self.write(self.state, WINDOW); self.set(72, 0xFFFF)
        self.set(8, 1); self.set(12, 1); self.set(16, 1)
        self.set(108, 60); self.set(128, 85)
        self.calls, self.texts, self.icon_paths, self.tooltips, self.widget_paths = [], [], [], [], []
        self.capture = 0
        self.image = Image.new('RGB', (760, 520), 'white')
        self.resources = {501: b'\xbb\xa1\xb0\xa3\xc6\xf7\xbc\xc7', 505: b'\xc6\xc4\xb6\xf5\xc6\xf7\xbc\xc7',
                          656: b'\xb0\xa2\xbc\xba\xc6\xf7\xbc\xc7', 12216: b'\xba\xfb\xc0\xc7\xc1\xd6\xb9\xae\xbc\xad',
                          601: b'\xc6\xc4\xb8\xae\xc0\xc7\xb3\xaf\xb0\xb3', 602: b'\xb3\xaa\xba\xf1\xc0\xc7\xb3\xaf\xb0\xb3'}
        self.write(0x0159C088, HEAP + 0x5000)
        self.write(0x0121333C, HEAP + 0x6000)
        self.last_surface = None
        self.fonts = {}
        self.hooks = {self.cfg[2]: self.fill, 0xA25A70: self.text, 0xA21C90: self.extent,
            0xA1CB30: lambda: self.ret(4), 0x529850: self.format,
            0xA90350: lambda: self.ret(0, HEAP), 0xA9F030: lambda: self.ret(0, self.args(1)[0]),
            0xA8D4A0: self.surface, self.cfg[8]: self.blit, 0xA1D2B0: self.crop, 0xA7E780: self.item_lookup,
            self.manifest['scalarSenderVir']: self.scalar,
            0x880AD0: lambda: self.ret(8), 0x880CB0: lambda: self.ret(8), 0x880BB0: self.base_up,
            0xA1EF70: lambda: self.ret(8), 0xA753D0: self.tooltip,
            0xA75340: lambda: self.ret(0, HEAP + 0x3000), STOP + 0x100: self.cancel_drag,
            0xA4B750: self.set_capture, 0xA32E00: lambda: self.ret(0,self.capture),
            0xA482E0: self.release_capture}
        self.u.mem_write(HEAP + 0x3000, struct.pack('<I', HEAP + 0x3800))
        self.write(HEAP + 0x3818, STOP + 0x100)
        self.u.hook_add(uc.UC_HOOK_CODE, self.hook)
        self.populate()

    def write(self, address, value): self.u.mem_write(address, struct.pack('<I', value & 0xFFFFFFFF))
    def read(self, address): return struct.unpack('<I', self.u.mem_read(address, 4))[0]
    def set(self, offset, value): self.write(self.state + offset, value)
    def get(self, offset): return self.read(self.state + offset)
    def cstr(self, address):
        result = bytearray()
        for i in range(1024):
            byte = self.u.mem_read(address + i, 1)[0]
            if not byte: return bytes(result)
            result.append(byte)
        raise AssertionError('unterminated string')
    def args(self, count): return struct.unpack('<' + 'I' * count, self.u.mem_read(self.u.reg_read(x.UC_X86_REG_ESP) + 4, count * 4))
    def ret(self, cleanup, value=0):
        sp = self.u.reg_read(x.UC_X86_REG_ESP)
        self.u.reg_write(x.UC_X86_REG_EAX, value)
        self.u.reg_write(x.UC_X86_REG_ESP, sp + 4 + cleanup)
        self.u.reg_write(x.UC_X86_REG_EIP, self.read(sp))
    def hook(self, machine, address, size, extra):
        if address in self.hooks: self.hooks[address]()
    def invoke(self, address, args=(), receiver=WINDOW):
        sp = STACK + 0xE000
        self.u.mem_write(sp, struct.pack('<'+'I'*(len(args)+1), STOP, *(a & 0xFFFFFFFF for a in args)))
        self.u.reg_write(x.UC_X86_REG_ESP, sp); self.u.reg_write(x.UC_X86_REG_ECX, receiver)
        saved = {x.UC_X86_REG_EBX: 0x12345678, x.UC_X86_REG_ESI: 0x23456789, x.UC_X86_REG_EDI: 0x34567890, x.UC_X86_REG_EBP: 0x45678901}
        for register, value in saved.items(): self.u.reg_write(register, value)
        self.u.emu_start(address, STOP, count=3_000_000)
        assert self.u.reg_read(x.UC_X86_REG_EIP) == STOP, 'instruction bound reached'
        assert self.u.reg_read(x.UC_X86_REG_ESP) == sp + 4 + 4 * len(args), 'stack cleanup changed'
        assert all(self.u.reg_read(register) == value for register, value in saved.items()), 'callee-saved register changed'
    def event(self, name, a, b): self.invoke(self.custom['entries']['AutoHuntCustom' + name], (a, b))
    def click(self, a, b): self.event('Down', a, b); self.event('Up', a, b)
    def draw(self):
        self.texts.clear(); self.icon_paths.clear(); self.image = Image.new('RGB', (760, 520), 'white')
        self.invoke(self.custom['entries']['AutoHuntCustomDraw'])
        assert self.u.mem_read(HEAP + 0x7028, 1) == b'\x00', 'GDI text must use an opaque surface like Item Description'
    def set_capture(self): self.capture=self.args(1)[0];self.ret(4)
    def release_capture(self): self.capture=0;self.ret(0)
    def scalar(self): self.calls.append(self.args(3)); self.ret(12)
    def tooltip(self): self.tooltips.append(self.args(6)); self.ret(24)
    def base_up(self): self.u.mem_write(WINDOW + 0x38, b'\xff'); self.ret(8)
    def cancel_drag(self): self.u.mem_write(HEAP + 0x3388, b'\0'); self.ret(20)
    def drag(self, kind, value, level=1):
        self.write(HEAP + 0x3308, kind); self.write(HEAP + 0x330C, value); self.write(HEAP + 0x3374, level)
        self.u.mem_write(HEAP + 0x3388, b'\1')
    def font(self, size):
        # Native SetFont (0x546F60), automatic face 0, adds three pixels for the
        # Latin client locale. The explicit face-1 path bypasses that adjustment.
        faces={0:'arial.ttf',1:'arial.ttf',2:'msgothic.ttc',4:'mingliu.ttc',5:'tahoma.ttf'}
        if size not in self.fonts: self.fonts[size] = ImageFont.truetype('C:/Windows/Fonts/'+faces[self.cfg[7]], size + (3 if self.cfg[7]==0 else 0))
        return self.fonts[size]
    def decode(self, raw):
        return raw.decode('cp950' if self.manifest['language'] == 'Traditional Chinese' else 'cp1252', errors='replace')
    def fill(self):
        _, a, b, width, height, color = self.args(6)
        assert a + width <= 760 and b + height <= 520, 'pixel write outside owned window'
        ImageDraw.Draw(self.image).rectangle((a,b,a+width-1,b+height-1), fill=(color>>16&255,color>>8&255,color&255))
        self.ret(24)
    def text(self):
        a,b,pointer,count,font,size,color,bold,italic = self.args(9)
        raw = self.cstr(pointer); value = self.decode(raw)
        self.texts.append((a,b,value))
        ImageDraw.Draw(self.image).text((a,b),value,font=self.font(size),fill=(color&255,color>>8&255,color>>16&255))
        self.ret(36)
    def extent(self):
        pointer,count,font,size,bold,italic = self.args(6)
        self.ret(24, int(self.font(size).getlength(self.decode(self.cstr(pointer)))))
    def format(self):
        destination, pointer = self.args(2); fmt = self.cstr(pointer).decode('latin1')
        args = self.args(8)[2:]; iterator = iter(args)
        def replace(match):
            if match.group() == '%%': return '%'
            value = next(iterator)
            if match.group().endswith('s'): return self.cstr(value).decode('latin1')
            return str(value)
        value = re.sub(r'%%|%(?:\.\d+)?[su]', replace, fmt).encode('latin1')
        self.u.mem_write(destination, value + b'\0'); self.ret(0,len(value))
    def item_lookup(self):
        item_id = self.read(self.args(1)[0]); resource = self.resources.get(item_id, b'unknown')
        node, storage = HEAP + 0x1000, HEAP + 0x2000
        self.u.mem_write(storage, resource + b'\0'); self.write(node + 0x58, storage); self.write(node + 0x6C, 32)
        self.ret(4,node)
    def surface(self): self.last_surface = self.cstr(self.args(1)[0]); self.ret(4, HEAP + 0x4000)
    def resource(self):
        if not self.game: return None
        path=self.game / 'data/texture' / self.last_surface.replace(b'\\',b'/').decode('cp1252')
        assert path.is_file(), path
        image=Image.open(path).convert('RGBA')
        pixels=image.load()
        for py in range(image.height):
            for px in range(image.width):
                r,g,b,a=pixels[px,py]
                if (r,g,b)==(255,0,255): pixels[px,py]=(r,g,b,0)
        return image
    def crop(self):
        a,b,surface,alpha,full,sx,sy,width,height=self.args(9)
        self.widget_paths.append(self.last_surface)
        image=self.resource()
        if image:
            assert sx+width<=image.width and sy+height<=image.height, (self.last_surface,sx,sy,width,height,image.size)
            image=image.crop((sx,sy,sx+width,sy+height));self.image.paste(image,(a,b),image)
        self.ret(36)
    def blit(self):
        window,surface,a,b = self.args(4)
        (self.icon_paths if b'/item/' in self.last_surface.replace(b'\\',b'/') else self.widget_paths).append(self.last_surface)
        image=self.resource()
        if image:self.image.paste(image,(a,b),image)
        self.ret(16)
    def populate(self):
        self.u.mem_write(self.state + 184, b'Timer: 02h 15m 00s\0')
        for index,(skill,name,key) in enumerate([(5,'Bash','sm_bash'),(7,'Magnum Break','sm_magnum'),(6,'Provoke','sm_provoke')]):
            for group,key_group in [(1,0),(2,1)]:
                address = self.rows[group] + index*48
                self.u.mem_write(address,struct.pack('<HHII24s12s',skill,10,1000,1,name.encode(),b'1'))
                self.u.mem_write(self.keys[key_group]+index*32,key.encode()+b'\0')
        for index,(item,name,count) in enumerate([(656,'Awakening Potion',12),(12216,'Increase Agility Scroll',5)]):
            self.u.mem_write(self.rows[5]+index*48,struct.pack('<III24s12s',item,1800000,1|count<<16,name.encode(),b'1800'))
        for index,(item,name,count) in enumerate([(501,'Red Potion',248),(501,'Red Potion',28),(505,'Blue Potion',36),(505,'Blue Potion',8)]):
            self.u.mem_write(self.rows[6]+index*48,struct.pack('<IHHIHH24s8s',item,60,25,1,index,count,name.encode(),b'60'))
        for index,(item,kind,count,name) in enumerate([(601,1,120,'Fly Wing'),(26,2,1,'Teleport'),(602,1,8,'Butterfly Wing'),(26,2,2,'Teleport')]):
            self.u.mem_write(self.rows[7]+index*48,struct.pack('<IHHI24s12s',item,count,kind,1,name.encode(),b''))
            self.u.mem_write(self.rows[8]+index*32,b'al_teleport\0')
        self.set(76,10)
        for index in range(10): self.u.mem_write(self.rows[0]+index*40,struct.pack('<II32s',1002+index,0,('Monster '+str(index)).encode()))

def verify(machine):
    m=machine
    # Execute the stock font selector, not a rewritten approximation. Automatic
    # face 0 applies the client locale's +3 adjustment; explicit face 1 does not.
    saved=[(a,bytes(m.u.mem_read(a,n))) for a,n in [(0x159B8A4,1),(0x159B810,4),(0x159B80C,4)]]
    m.u.mem_write(0x159B8A4,b'\1');m.write(0x159B810,0);m.write(0x159B80C,0)
    m.invoke(0x546F60,(0,12,0,0),HEAP+0x9000)
    assert m.read(HEAP+0x9010)==15 and m.read(HEAP+0x900C)==1
    m.invoke(0x546F60,(1,12,0,0),HEAP+0x9000);assert m.read(HEAP+0x9010)==12
    for address,data in saved:m.u.mem_write(address,data)
    for slot,tab in enumerate([0,2,1,3,4,5,6]):
        m.click(30,140+44*slot); assert m.get(4)==tab
        m.draw()
        if tab in (3,5,6): assert any('x ' in s for _,_,s in m.texts), f'quantity missing on tab {tab}'
        if tab in (2,3,5,6): assert len(m.icon_paths) >= (3 if tab==2 else 4 if tab in (3,5) else 2), f'native icons missing on tab {tab}'
        m.image.save(m.directory / f'custom-v1-tab-{tab}.png')
    m.set(4,2)
    for page in (1,2):
        m.set(8,page); m.calls.clear();m.click(680,174); assert m.calls[-1]==(47,(page-1)*8,0)
        m.drag(8,5,10);m.event('Up',185,175);assert m.calls[-1]==(37 if page==1 else 40,0,5|(10<<16))
    # Sparse slots compact visually without renumbering the server's slot IDs.
    m.set(8,1);m.u.mem_write(m.rows[1]+7*48,bytes(m.u.mem_read(m.rows[1],48)));m.u.mem_write(m.rows[1]+48,b'\0'*48)
    m.click(680,168+2*37+6);assert m.calls[-1]==(47,7,0)
    m.click(540,124);m.click(680,168+7*37+6);assert m.calls[-1]==(47,7,0)
    m.click(540,124)
    m.set(8,3);m.set(108,60);m.click(339,378);assert m.calls[-1]==(50,70,0)
    m.event('Down',260,378);m.event('Move',999,378);m.event('Up',999,378);assert m.calls[-1]==(50,100,0)
    assert m.tooltips[-1][1:3]==(1009,354), 'tooltip must follow actual cursor coordinates'
    assert m.custom['payload']['vir'] <= m.tooltips[-1][0] < m.custom['payload']['vir'] + m.custom['payload']['size'], 'tooltip text must outlive the input stack'
    m.event('Down',260,378);m.event('Move',-20,378);m.event('Up',-20,378);assert m.calls[-1]==(50,0,0)
    m.set(4,6);m.calls.clear();m.click(680,174);assert m.calls[-1]==(47,20,0)
    m.write(m.rows[5]+8,1|(65535<<16));m.draw();assert any(s=='x 65535' for _,_,s in m.texts)
    m.write(m.rows[5]+8,1|(7<<16));m.draw();assert any(s=='x 7' for _,_,s in m.texts), 'quantity must update from current snapshot rows'
    m.drag(1,2);m.event('Up',185,175);assert m.calls[-1]==(56,0,2)
    m.set(4,3);m.calls.clear();m.click(711,185);assert m.calls[-1][0:2]==(60,0)
    m.click(400,211);assert m.calls[-1][0:2]==(59,0)
    m.event('Down',480,211);m.event('Move',999,211);m.event('Up',999,211);assert m.calls[-1]==(59,0,100)
    m.drag(1,2);m.event('Up',185,185);assert m.calls[-1]==(58,0,2)
    m.set(4,4);m.set(16,1);m.calls.clear();m.click(170,235);assert m.calls[-1][0]==36
    m.click(685,258);assert m.calls[-1][0]==53
    m.event('Down',560,258);m.event('Move',999,258);m.event('Up',999,258);assert m.calls[-1]==(53,90,0)
    m.click(451,298);assert m.calls[-1][0]==65 and m.get(16)==1
    m.click(600,150);assert m.get(16)==2
    m.click(530,190);assert m.get(168)==1 and m.get(16)==2
    m.click(530,213+3*24+5);assert m.calls[-1][0]==54 and m.calls[-1][2]==3
    m.set(4,0);m.set(124,0);m.calls.clear()
    m.draw();assert any(s=='Core behavior' for _,_,s in m.texts) if m.manifest['language']=='English' else True
    m.click(175,234);assert m.calls[-1][0]==7 and m.get(4)==0 and m.get(8)==3
    m.click(465,234);assert m.calls[-1][0]==65 and m.get(4)==0
    m.click(465,302);assert m.calls[-1][0]==22 and m.get(4)==0
    m.set(40,1);m.click(175,368);assert m.calls[-1]==(20,2,0)
    m.set(40,2);m.click(175,368);assert m.calls[-1]==(20,1,0)
    m.invoke(m.custom['entries']['AutoHuntCustomWheel'],(-1,));assert m.get(124)==0
    m.click(530,150)
    m.set(4,0);m.set(124,0);m.calls.clear();m.click(175,178);assert m.calls[-1][0]==7
    m.click(510,178);assert m.calls[-1][0]==64
    m.invoke(m.custom['entries']['AutoHuntCustomWheel'],(-1,));assert m.get(124)==1
    m.event('Down',724,240);assert m.capture==WINDOW
    m.event('Move',724,999);m.event('Up',724,999);assert m.get(124)==5 and m.capture==0
    m.set(124,0)
    m.set(4,1);m.calls.clear();m.click(175,215);assert m.calls[-1][0]==19
    m.event('Down',724,200);assert m.capture==WINDOW
    m.event('Move',724,999);m.event('Up',724,999);assert m.get(144)==5 and m.capture==0
    m.set(4,5);m.drag(1,2);m.event('Up',185,185);assert m.calls[-1][0]==62
    m.drag(8,26,2);m.event('Up',185,250);assert m.calls[-1][0]==63
    m.calls.clear();m.click(40,500);assert m.calls[-1]==(10,1,0)
    m.set(28,1<<12);m.click(738,12);assert m.read(WINDOW+0x28)==0 and m.get(28)==1<<12
    assert all(call[0] not in (45,46) for call in m.calls), 'settings close must not toggle automation'
    assert any(b'slider_gage_' in p for p in m.widget_paths) and any(b'scroll_thumb_' in p for p in m.widget_paths)
    assert m.cfg[7]==0 if m.manifest['language']=='English' else True
    return {'passed':True,'live_accepted':False,'checks':['seven redesigned tabs','real icon resolver and native skill paths','server inventory quantities, refresh, and 65535 cap','attack/support delays, sparse slot identities, and native drag payloads','buff and potion registration','native RO Global gauges/arrows/scrollbars','healing/potion/loot slider endpoints and capture','physical tooltip anchors and persistent text storage','potion thresholds','loot categories/weight/dropdown/context restoration','Overview core/return controls and pickup modes','advanced toggles/input/wheel and scrollbar capture','monster selection','movement registration','reset','close preserves running state','opaque GDI text surface and stock automatic font selector execution','x86 stack and callee-saved registers']}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path)
    parser.add_argument('--game',type=Path)
    args=parser.parse_args()
    result=verify(Machine(args.directory.resolve(),args.game))
    result['windows_gdi_alpha']=verify_gdi_alpha()
    (args.directory/'custom-verification.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))

if __name__=='__main__': main()
