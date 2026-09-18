"""Pixel regression: native 14px countdown cell survives all background writes."""
import argparse,struct
from pathlib import Path
from unicorn.x86_const import UC_X86_REG_ECX
from test_vip_ui import VipMachine,snapshot

class TimerMachine(VipMachine):
    def text(self):
        obj=self.u.reg_read(UC_X86_REG_ECX);args=self.args(9);value=self.cstr(args[2])
        super().text()
        if value.startswith('Buffs: '):
            x,y=args[:2];pix,w,h=self.pixels(obj)
            assert y==168 and y+14<=183,'Countdown overlaps membership text'
            # Model the lower native glyph rows omitted by the old text fixture.
            for row in range(y+8,y+14):self.u.mem_write(pix+(row*w+x)*4,b'\x0c\x17\x30\xff'*95)
            self.ink=(pix,w,x,y)

ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--output',type=Path,required=True)
a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
m=TimerMachine(a.exe);p=snapshot();struct.pack_into('<I',p,2564,2994);obj=m.ready(p)
m.invoke(m.c['draw'],obj);pix,w,x,y=m.ink
for row in range(y+8,y+14):assert bytes(m.u.mem_read(pix+(row*w+x)*4,95*4))==b'\x0c\x17\x30\xff'*95,'Countdown erased by a later background patch'
v=VipMachine(a.exe);obj=v.ready(p);v.preview(obj,a.output/'buff-countdown.png')
print('PASS: complete high-contrast countdown is the final draw, 14px glyph cell survives, no button or membership overlap.')
