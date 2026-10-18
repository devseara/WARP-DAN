"""Execute the freshly emitted HUD x86, including the private PNG compositor.

Texture loading, font rasterization, native clear and OS calls are explicit
offline boundaries. These checks do not establish in-game visual acceptance.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from unicorn import UC_HOOK_CODE
from unicorn.x86_const import *
from test_modern_chat_ui import Machine, pack


class HudMachine(Machine):
    def __init__(self, exe, contract, assets):
        super().__init__(str(exe), assets)
        self.c = contract
        self.draws = []
        self.ap = (0, 200)
        self.name = self.alloc(128)
        self.u.mem_write(self.name, b'DevSeara\0')
        self.stub(0xD7FE40, lambda: self.ret(0, self.name))
        self.stub(0x89D340, lambda: self.ret(4, self.ap[self.args(1)[0] - 0xE8]))
        self.stub(0x529850, self.sprintf)
        self.stub(0xA21C90, self.measure)
        self.stub(0xA25A70, self.draw_text)
        self.stub(0xDBBBD4, lambda: self.ret(0))
        self.w(self.c['themeStateVir'], 1)
        self.w(self.c['themeStateVir'] + 4, 1)
        for key, cropped in [('pngDrawVir',False), ('gaugeDrawVir',True)]:
            self.u.hook_add(UC_HOOK_CODE, lambda u,a,s,d,c=cropped: self.observe_png(c),
                            begin=self.c[key],end=self.c[key])
        self.parent = self.window(280, 70, 0x103E35C)
        self.child = self.window(67, 70, self.c['childVtableVir'], self.parent)
        self.w(self.parent + 0xB4, 70)
        self.w(self.parent + 0xB8, 130)
        self.w(self.c['themeStateVir'] + 20, self.child)
        self.w(self.c['themeStateVir'] + 24, self.parent)
        self.values()

    def observe_png(self, cropped):
        x,y,texture,*tail=self.args(5 if cropped else 4)
        name=next(n for n,p in self.textures.items() if p==texture)
        width,height=tail if cropped else (self.r(texture+0x114),self.r(texture+0x118))
        self.draws.append((name,x,y,width,height))

    def cstr(self, p):
        return bytes(self.u.mem_read(p, 256)).split(b'\0')[0].decode('utf-8', errors='strict')

    def texture(self):
        # Prefix is the client's legacy texture directory; filenames are ASCII.
        raw = bytes(self.u.mem_read(self.args(1)[0], 256)).split(b'\0')[0]
        name = raw.split(b'basicinfoui\\')[-1].decode('ascii').replace('\\', '/')
        if not (self.assets / name).is_file():
            self.ret(4, 0)
        else:
            self.ret(4, self.load_texture(name))

    def sprintf(self):
        dest, fmt = self.args(2)
        fmt = bytes(self.u.mem_read(fmt, 256)).split(b'\0')[0].decode('latin1')
        args = self.args(4)[2:]
        if fmt == '%.96s': text = self.cstr(args[0])[:96]
        elif '%d' in fmt:
            count = fmt.count('%d')
            text = fmt % tuple(v if v < 0x80000000 else v - 0x100000000 for v in args[:count])
        else: text = fmt
        raw = text.encode('utf-8' if fmt == '%.96s' else 'latin1')
        self.u.mem_write(dest, raw + b'\0')
        self.ret(0, len(raw))

    def font(self, height):
        return ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf', height)

    def measure(self):
        text, _, _, height, _, _ = self.args(6)
        self.ret(24, math.ceil(self.font(height).getlength(self.cstr(text))))

    def draw_text(self):
        x, y, text, _, _, height, color, _, _ = self.args(9)
        text = self.cstr(text)
        obj = self.u.reg_read(UC_X86_REG_ECX)
        font = self.font(height)
        width = math.ceil(font.getlength(text))
        self.texts.append((text, x, y, width, height, obj))
        pixels, w, h = self.pixels(obj)
        assert x + width <= w and y + height <= h, self.texts[-1]
        im = Image.frombytes('RGBA', (w, h), bytes(self.u.mem_read(pixels, w*h*4)), 'raw', 'BGRA')
        rgb = im.convert('RGB')
        ImageDraw.Draw(rgb).text((x, y-2), text, font=font,
                                fill=(color & 255, color >> 8 & 255, color >> 16 & 255))
        # GDI writes RGB and clears alpha on the pixels it touches. PIL's
        # RGBA antialiasing blends alpha instead, so model that boundary explicitly.
        im.putdata([(*after,0) if before[:3]!=after else before
                    for before,after in zip(im.get_flattened_data(),rgb.get_flattened_data())])
        self.u.mem_write(pixels, im.tobytes('raw', 'BGRA'))
        self.ret(36)

    def values(self, hp=(2189, 2962), sp=(368, 398), ap=(0, 200), levels=(71, 50), job=2):
        for address, value in zip([0x15FF908, 0x15FF90C, 0x15FF910, 0x15FF914], hp + sp):
            self.w(address, value)
        self.ap = ap
        for address, value in zip([0x15FB9F0, 0x15FB9F8, 0x15FB9C8], (*levels, job)):
            self.w(address, value)

    def draw(self, special=False):
        self.texts.clear(); self.draws.clear()
        branch = 'special' if special else 'classic'
        sp = 0x3000F000
        self.u.reg_write(UC_X86_REG_ESP, sp)
        self.u.reg_write(UC_X86_REG_EBP, sp)
        self.u.reg_write(UC_X86_REG_EBX, self.parent)
        self.u.reg_write(UC_X86_REG_ESI, 0xEEEEEEEE)
        self.u.reg_write(UC_X86_REG_EDI, 0xFFFFFFFF)
        self.u.emu_start(self.c[branch+'CodeVir'], self.c[branch+'ExitVir'], count=4000000)
        assert self.u.reg_read(UC_X86_REG_EIP) == self.c[branch+'ExitVir']
        assert self.u.reg_read(UC_X86_REG_ESP) == sp
        assert self.u.reg_read(UC_X86_REG_EBP) == sp
        assert self.u.reg_read(UC_X86_REG_EBX) == self.parent
        assert self.u.reg_read(UC_X86_REG_ESI) == 0xEEEEEEEE
        assert self.u.reg_read(UC_X86_REG_EDI) == 0xFFFFFFFF

    def save(self, path):
        def img(obj):
            p, w, h = self.pixels(obj)
            im = Image.frombytes('RGBA', (w, h), bytes(self.u.mem_read(p, w*h*4)), 'raw', 'BGRA')
            data = [(0, 0, 0, 0) if (r,g,b)==(255,0,255) else (r,g,b,a) for r,g,b,a in im.get_flattened_data()]
            im.putdata(data)
            return im
        canvas = Image.new('RGBA', (280,70), '#e7f3ed')
        canvas.alpha_composite(img(self.parent)); canvas.alpha_composite(img(self.child))
        canvas.resize((840,210), Image.Resampling.NEAREST).save(path)


def test(exe, contract, assets, output):
    m = HudMachine(exe, contract, assets)
    results = []
    for special in (False, True):
        m.draw(special)
        strings = [r[0] for r in m.texts]
        assert strings == ['DevSeara','HP','2189 / 2962','73%','SP','368 / 398','92%','AP','0 / 200','0%','71/50'], strings
        assert ('bar_hp_g_wide.png',64,26,157,14) in m.draws
        assert ('bar_sp_wide.png',64,41,197,14) in m.draws
        assert m.draws[-2:] == [('class/2.png',0,0,67,67), ('bg_level.png',10,51,46,18)]
        pixels,w,h=m.pixels(m.child)
        actual=Image.frombytes('RGBA',(w,h),bytes(m.u.mem_read(pixels,w*h*4)),'raw','BGRA')
        reference=Image.open(assets/'class/2.png').convert('RGBA')
        for src,dst in zip(reference.crop((0,0,67,51)).get_flattened_data(), actual.crop((0,0,67,51)).get_flattened_data()):
            assert dst==src if src[3] else dst[3]==0, (src,dst,'circular PNG alpha changed')
        # Overlay transparency must preserve the colored fill underneath it.
        pixels,w,h=m.pixels(m.parent)
        sample=m.r(pixels+(31*w+100)*4)
        assert sample>>24==255 and (sample>>8&255)>(sample>>16&255), hex(sample)
        results.append('AP/classic compact branch: values, artwork, stack/register preservation')
    m.save(output/'hud-emulated.png')
    for hp, expected in [(0,None),(1,'r'),(25,'r'),(26,'g'),(100,'g'),(150,'g')]:
        m.values(hp=(hp,100)); m.draw()
        fills = [r for r in m.draws if r[0].startswith('bar_hp')]
        assert bool(fills) == (expected is not None)
        if fills:
            assert fills[0][0] == f'bar_hp_{expected}_wide.png'
            assert fills[0][3] == min(213,(hp*213+50)//100)
    m.values(hp=(20,100), ap=(45,200)); m.draw(); m.save(output/'hud-low-hp-emulated.png')
    results.append('HP zero, low/red threshold, green threshold, full and over-max clamping')
    for hp, sp, ap in [((1_000_000_000,2_000_000_000),(10,0),(200,0)),
                       ((-1,100),(-1,-1),(0,0)),
                       ((2_147_483_647,2_147_483_647),(2_147_483_647,2_147_483_647),(200,300))]:
        m.values(hp=hp,sp=sp,ap=ap); m.draw()
        expected = f'{ap[0]} / {ap[1] if ap[1]>0 else 200}'
        assert expected in [r[0] for r in m.texts]
        for text,x,y,w,h,obj in m.texts:
            if obj == m.parent and ' / ' in text: assert x >= 94 and x+w <= 237, (text,x,w)
    results.append('large HP/SP, missing maxima, AP 200 fallback, bounded large-number text')
    for name in ['W'*24, '測試角色名稱'*4]:
        m.u.mem_write(m.name, name.encode()+b'\0'); m.draw()
        assert m.texts[0][0].endswith('...') and m.texts[0][3] <= 132
    results.append('long ASCII and UTF-8 names fit without invalid character cuts')
    m.u.mem_write(m.name,b'DevSeara\0')
    for job, art in [(0,0),(7,7),(13,7),(4003,2),(4036,7),(4055,4010),(4255,4010),(9999,0)]:
        m.values(job=job, levels=(99,70)); m.draw()
        assert f'class/{art}.png' in [r[0] for r in m.draws]
        assert m.texts[-1][0] == '99/70'
    m.values(levels=(100,71)); m.draw(); assert m.texts[-1][0] == '100/71'
    results.append('native child refreshes base/job levels and circular class lineage/fallback')
    # Classic mode must clear the custom child and forward the original branches.
    m.w(m.c['themeStateVir'],0); m.invoke(m.c['childDrawCodeVir'],m.child)
    pixels,w,h=m.pixels(m.child)
    assert bytes(m.u.mem_read(pixels,w*h*4)) == bytes(w*h*4)
    m.u.reg_write(UC_X86_REG_ESP,0x3000F000); m.u.reg_write(UC_X86_REG_EBP,0x3000F000)
    m.u.emu_start(m.c['classicCodeVir'],0x95E6A9,count=10000)
    assert m.u.reg_read(UC_X86_REG_EIP)==0x95E6A9
    original=[]; m.stub(0x95DA30,lambda:(original.append(1),m.ret(0)))
    m.u.emu_start(m.c['specialCodeVir'],m.c['specialExitVir'],count=10000)
    assert original==[1]
    results.append('Classic mode clears custom child and forwards both original draw paths')
    for modern in (0,1):
        m.w(m.c['themeStateVir'],modern)
        m.invoke(m.c['factoryCodeVir'],m.parent,[220,55])
        assert (m.r(m.parent+0x14),m.r(m.parent+0x18)) == ((280,70) if modern else (220,130))
    results.append('factory sizes: New 280x70 and native Classic expanded dimensions')
    # Parent/child overlap must still route the bottom AP row correctly.
    tooltip=[]
    tip_manager=m.alloc(32); m.w(0x121333C,tip_manager)
    job_name=m.alloc(64); m.u.mem_write(job_name,b'Mage\0')
    m.stub(0xD5B580,lambda:m.ret(0,2))
    m.stub(0xD5BB40,lambda:m.ret(8,job_name))
    m.stub(0xA1EF70,lambda:m.ret(8))
    m.stub(0xA753D0,lambda:(tooltip.append(m.cstr(m.args(6)[0])),m.ret(24)))
    for x,y,expected in [(80,26,'Health Pool'),(80,41,'Mana Pool'),(80,67,'Activity Points')]:
        m.invoke(m.c['barHoverCodeVir'],m.parent,[x,y]); assert tooltip[-1]==expected
    for x,y,expected in [(65,26,'Health Pool'),(65,41,'Mana Pool'),(65,67,'Activity Points'),(3,3,'Mage')]:
        m.invoke(m.c['childHoverCodeVir'],m.child,[x,y]); assert tooltip[-1]==expected
    results.append('HP/SP/AP and Job tooltip bounds, including child overlap at the bottom AP row')
    # Execute just the changed Basic Info section of the shared theme toggle.
    # The other windows' toggle code is unchanged and is outside this suite.
    mapped=m.pe.get_memory_mapped_image()
    marker=bytes.fromhex('C7 46 14 18 01 00 00 FF B6 B4 00 00 00 E9')
    offset=mapped.find(marker); assert offset>=0 and mapped.find(marker,offset+1)<0
    width_code=m.base+offset
    resize=[]
    m.stub(0x95DFB0,lambda:(resize.append((m.r(m.u.reg_read(UC_X86_REG_ECX)+0x14),m.args(1)[0])),m.ret(4)))
    # The direct conditional branch immediately precedes the New width.
    start=width_code-13
    assert bytes(m.u.mem_read(start,2))==bytes.fromhex('83 3D')
    calls=[i for i in m.cs.disasm(bytes(m.u.mem_read(start,100)),start) if i.mnemonic=='call' and i.op_str=='0x95dfb0']
    assert calls
    for modern in (0,1,0,1):
        m.w(m.c['themeStateVir'],modern)
        m.u.reg_write(UC_X86_REG_ESI,m.parent); m.u.reg_write(UC_X86_REG_ESP,0x3000F000)
        m.u.emu_start(start,calls[0].address+calls[0].size,count=10000)
        assert resize[-1]==((280,70) if modern else (220,130))
    results.append('shared theme toggle Basic Info resize: Classic/New repeated transitions')
    return results


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('exe',type=Path); p.add_argument('contract',type=Path)
    p.add_argument('--assets',type=Path,default=Path(__file__).resolve().parents[1]/'Inputs/BasicInfoUI/assets')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    results=test(a.exe,json.loads(a.contract.read_text()),a.assets,a.output)
    (a.output/'hud-checks.json').write_text(json.dumps({'passed':results,'limits':__doc__},indent=2))
    print('\n'.join('PASS: '+r for r in results))
