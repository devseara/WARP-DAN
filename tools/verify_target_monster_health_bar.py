"""Execute the emitted HUD x86 against bounded native-call fixtures."""
import argparse,struct,json,re,hashlib
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import pefile
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import *
ROOT=Path(__file__).resolve().parents[1]
from target_monster_hud_layout import make_layout
from target_monster_hud_designs import identify_design
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('exe',nargs='?',type=Path,default=ROOT/'Outputs/TargetMonsterHUD-test.exe')
parser.add_argument('--report',type=Path,help='Write the verification results as JSON')
parser.add_argument('--assets-root',type=Path,default=ROOT,help='Root containing the packaged data/texture tree')
args=parser.parse_args()
PE=args.exe
p=pefile.PE(str(PE)); ib=p.OPTIONAL_HEADER.ImageBase
DESIGN,MANIFEST=identify_design(p);W,H=MANIFEST['canvas']
r=lambda a,n:p.get_data(a-ib,n)
def target(a):return a+5+struct.unpack('<i',r(a+1,4))[0]
base=target(target(0xc76591)); state=base+0xe000
LAYOUT=make_layout(W,H,base);INFO_DB=LAYOUT['info_db'];INFO_TEXT=LAYOUT['info_rows'];HP_TEXT=LAYOUT['hp_text']
MODE=0x30000000;WORLD=MODE+0x1000;PLAYER=MODE+0x2000;MOB=MODE+0x3000;GAUGE=MODE+0x4000;INFO=MODE+0x5000;HUD=MODE+0x6000;VIEW=MODE+0x7000;STACK=0x40000000;STOP=0x41000000
class Harness:
 def __init__(self):
  u=self.u=Uc(UC_ARCH_X86,UC_MODE_32);u.mem_map(ib,(p.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(ib,p.get_memory_mapped_image())
  for a,n in [(MODE,0x120000),(STACK,0x10000),(STOP,0x1000)]:u.mem_map(a,n)
  self.text_draws=[];self.text_calls=[];self.native_hp_calls=0;self.native_refreshes=[];self.icon_draws=[];self.icon_exists=True;self.cursor=0;self.ui_block=0;self.modal=0;self.allocs=0;self.actor=True;self.original=0;self.opens=[];self.closes=[];self.missing=set();self.corrupt={};self.option=True;
  for a,v in [(MODE,0x10904b8),(MODE+0xcc,WORLD),(WORLD+0x2c,PLAYER),(PLAYER+0x500,1),(PLAYER+0x514,101),(MOB+0x300,GAUGE),(MOB+0x314,5),(MOB+0x110,101),(GAUGE,0x102be50),(GAUGE+0xa0,680),(GAUGE+0xa4,1000),(0x12515f8,VIEW),(VIEW+0x28,1280),(INFO+0x18,15),(HUD+0x24,MODE+0x8000),(MODE+0x8018,MODE+0x10000),(MODE+0x8004,W)]:self.put(a,v)
  u.mem_write(INFO+0x98,b'\1');u.mem_write(INFO+4,b'Baphomet\0');self.files={f.name:f.read_bytes() for f in (args.assets_root/MANIFEST['resource_root']).glob('target_mob_*.bmp')}
  self.handles={}
  self.ring=self.get(base+0xe0c0)
  for pc in [0xcf33f0,0xa90350,0xa8e500,0xa9f030,0xa8d4a0,0xa1d260,0xc6d1d0,0xc43230,0xd8e9d0,0x4f1940,0xa47b90,0xa69eb0,0x5a1460,0xdbbc4f,0x8361b0,0xa1cb70,0xa2d240,0xa23450,0x863f10,0xa1cb30,0xa21c90,0xa25a70,0x529850,0x83bd30,0x573750,0x573980,0x519200,0x68ea70,0xc14d60,0xc14920]:u.hook_add(UC_HOOK_CODE,self.hook,begin=pc,end=pc)
 def put(self,a,v):self.u.mem_write(a,struct.pack('<I',v&0xffffffff))
 def get(self,a):return struct.unpack('<I',bytes(self.u.mem_read(a,4)))[0]
 def ret(self,n=0,val=0):
  sp=self.u.reg_read(UC_X86_REG_ESP);pc=self.get(sp);self.u.reg_write(UC_X86_REG_EAX,val);self.u.reg_write(UC_X86_REG_ESP,sp+4+n*4);self.u.reg_write(UC_X86_REG_EIP,pc)
 def hook(self,u,pc,size,unused):
  sp=u.reg_read(UC_X86_REG_ESP);ecx=u.reg_read(UC_X86_REG_ECX)
  arg=lambda n:self.get(sp+n*4)
  if pc in (0xc14d60,0xc14920):raise AssertionError('HUD sent an unnecessary query')
  elif pc==0xcf33f0:
   assert ecx==MODE and arg(1)==MODE+0xe9000;self.native_hp_calls+=1
   packet=arg(1)
   if self.actor and self.get(packet+2)==101:
    self.put(MOB+0x300,GAUGE);self.put(GAUGE+0xa0,self.get(packet+6));self.put(GAUGE+0xa4,self.get(packet+10))
   self.ret(1)
  elif pc==0x68ea70:assert arg(1)==0xd5;self.ret(0,int(self.option))
  elif pc==0x573750:
   assert (arg(2),arg(3),arg(4))==(0,1,0) # Stock data-root + CFileMgr disk/GRF mode.
   assert self.get(ecx)==0xfd3074 and self.get(ecx+4)==0xffffffff and self.get(ecx+0x28)==15
   name=bytes(u.mem_read(arg(1),256)).split(b'\0')[0].decode('latin1')
   assert name.rsplit(chr(92),1)[0]==MANIFEST['resource_root'].removeprefix('data/').replace('/',chr(92)),name
   leaf=name.rsplit('\\',1)[1];self.opens.append(leaf)
   if leaf in self.missing:self.handles[ecx]=b'';self.ret(4,0)
   else:
    data=self.corrupt.get(leaf,self.files[leaf]);self.handles[ecx]=data;self.put(ecx+0x10,len(data));self.ret(4,1)
  elif pc==0x573980:
   data=self.handles[ecx];assert len(data)==arg(2);u.mem_write(arg(1),data);self.ret(2,1)
  elif pc==0x519200:
   assert arg(1)==0 # Destroy the stack CFile without freeing its address.
   self.closes.append(ecx);self.ret(1)
  elif pc==0xc6d1d0:
   assert ecx==MODE and arg(1)==MOB;self.native_refreshes.append(self.option);self.ret(1)
  elif pc==0xc43230:
   assert ecx==MOB and arg(1)==0xffffffff;self.ret(1,1257)
  elif pc==0xa90350:self.ret(0,MODE+0xdf000)
  elif pc==0xa8e500:
   path=bytes(u.mem_read(arg(1),256)).split(b'\0')[0].decode('latin1');assert path.endswith('.bmp') and '\\group\\group_' in path;assert ecx==MODE+0xdf000;self.ret(1,int(self.icon_exists))
  elif pc==0xa9f030:self.ret(0,arg(1))
  elif pc==0xa8d4a0:
   assert ecx==MODE+0xdf000;bitmap=MODE+0xe0000
   self.put(bitmap+0x110,0);self.put(bitmap+0x114,24);self.put(bitmap+0x118,24);self.ret(1,bitmap)
  elif pc==0xa1d260:
   assert ecx==HUD and arg(3)==MODE+0xe0000 and arg(4)==1
   x,y=arg(1),arg(2);assert x+24<=W and y+24<=H;self.icon_draws.append((x,y,24,24))
   # Native non-alpha bitmap fixture: a visible dot and a magenta key pixel.
   self.put(MODE+0x10000+((y+12)*W+x+12)*4,0x008070c0)
   self.put(MODE+0x10000+(y*W+x)*4,0x00ff00ff)
   u.mem_write(MODE+0x8028,b'\0');self.ret(4)
  elif pc==0xd8e9d0:
   assert ecx==0x15fa3c0 and arg(1)==MOB;self.ret(1,1)
  elif pc==0x4f1940:
   assert ecx in (MODE+0xd0000-0x1d8,MODE+0xd0000-0x160)
   assert arg(2)==0 and bytes(u.mem_read(arg(1),1))==b'\0'
   dst=ecx if self.get(ecx+20)<16 else self.get(ecx)
   u.mem_write(dst,b'\0');self.put(ecx+16,0);self.ret(2,ecx)
  elif pc==0xa47b90:
   assert ecx==0x131f4e8 and arg(1)==0x271b;self.original+=1;self.ret(1,self.modal)
  elif pc==0xa69eb0:
   assert ecx==WORLD and arg(1)==101;self.ret(1,MOB if self.actor else 0)
  elif pc==0x5a1460:
   assert ecx==MODE+0x160 and arg(1)==101;self.ret(1,INFO)
  elif pc==0xdbbc4f:
   assert arg(1)==0xb4;self.allocs+=1;self.ret(0,HUD)
  elif pc==0x8361b0:assert ecx==HUD;self.ret(0,HUD)
  elif pc==0xa1cb70:
   assert ecx==HUD and arg(1)==W and arg(2)==H;self.put(HUD+0x14,arg(1));self.put(HUD+0x18,arg(2));self.ret(2)
  elif pc==0xa2d240:assert arg(1)==HUD;self.ret(1)
  elif pc==0xa23450:
   assert ecx==HUD;self.put(HUD+0x1c,arg(1));self.put(HUD+0x20,arg(2));self.ret(2)
  elif pc==0x863f10:
   assert ecx==HUD;self.put(HUD+0xa0,arg(1));self.put(HUD+0xa4,arg(2));self.ret(2)
  elif pc==0xa1cb30:
   assert ecx==HUD;u.mem_write(MODE+0x10000,bytes(W*H*4));self.ret(1)
  elif pc==0x529850:
   encoding='latin1' if arg(2)==0x1090ec8 else 'utf8'
   fmt=bytes(u.mem_read(arg(2),256)).split(b'\0')[0].decode(encoding)
   specs=re.findall(r'%(?:08X|u|s|d)',fmt);values=[]
   for idx,spec in enumerate(specs):
    value=arg(3+idx)
    if spec=='%s':value=bytes(u.mem_read(value,128)).split(b'\0')[0].decode('utf8')
    values.append(value)
   text=(fmt%tuple(values)).encode(encoding)
   assert len(text)<128
   u.mem_write(arg(1),text+b'\0');self.ret(0,len(text))
  elif pc==0xa21c90:
   assert ecx==HUD and arg(2)==0 and arg(3)==1 and arg(4) in (12,14) and arg(5)==arg(6)==0
   text=bytes(u.mem_read(arg(1),128)).split(b'\0')[0].decode('utf8')
   font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',arg(4));self.ret(6,round(font.getlength(text)))
  elif pc==0xa25a70:
   assert ecx==HUD and arg(4)==0 and arg(5)==1 and arg(6) in (12,14) and arg(8)==arg(9)==0
   text=bytes(u.mem_read(arg(3),128)).split(b'\0')[0].decode('utf8');x=arg(1);x=x-0x100000000 if x&0x80000000 else x;y=arg(2);y=y-0x100000000 if y&0x80000000 else y
   img=Image.frombytes('RGBA',(W,H),bytes(u.mem_read(MODE+0x10000,W*H*4)),'raw','BGRA');c=arg(7)
   self.text_calls.append((text,x,y,arg(6),c))
   if c!=0x00010101:self.text_draws.append(text)
   # GDI's RGB-only glyph writes clear destination alpha. An opaque fixture
   # would hide missing alpha repair, especially for the outline's extra rows.
   painter=ImageDraw.Draw(img);painter.fontmode='1'
   painter.text((x,y),text,font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',arg(6)),fill=(c&255,(c>>8)&255,(c>>16)&255,0))
   u.mem_write(MODE+0x10000,img.tobytes('raw','BGRA'));self.ret(9,1)
  elif pc==0x83bd30:self.ret(1)
 def run(self,addr,ecx=MODE,argc=0,arguments=None):
  sp=STACK+0x8000;self.put(sp,STOP);self.put(sp+4,1)
  if arguments is not None:
   assert len(arguments)==argc
   for index,value in enumerate(arguments,1):self.put(sp+index*4,value)
  self.u.reg_write(UC_X86_REG_ESP,sp);self.u.reg_write(UC_X86_REG_ECX,ecx)
  expected={reg:0x12340000+reg for reg in (UC_X86_REG_EBX,UC_X86_REG_ESI,UC_X86_REG_EDI,UC_X86_REG_EBP)}
  if addr==base:
   expected.update({UC_X86_REG_EBX:self.ui_block,UC_X86_REG_ESI:MODE,UC_X86_REG_EDI:MODE+0xb000 if self.cursor else 0})
   self.put(MODE+0xb018,self.cursor);self.put(sp+4,0x271b)
  if addr in (base+0x5b00,base+0x9e00):
   expected.update({UC_X86_REG_EDI:MOB,UC_X86_REG_EBP:MODE+0xd0000})
   self.put(sp+4,MOB if addr==base+0x5b00 else 0xffffffff)
  if addr==base+0x2900:self.put(sp+4,MODE+0xe9000)
  for reg,value in expected.items():self.u.reg_write(reg,value)
  self.u.emu_start(addr,STOP,count=5000000)
  assert self.u.reg_read(UC_X86_REG_EIP)==STOP
  assert self.u.reg_read(UC_X86_REG_ESP)==sp+4+argc*4
  if addr==base:assert self.u.reg_read(UC_X86_REG_EAX)==self.modal
  for reg,value in expected.items():assert self.u.reg_read(reg)==value
 def packet(self,title,gid=101,entity=1,length=657,magic=0x4558544e,name=''):
  data=bytearray(length);struct.pack_into('<HHII',data,0,0xbb7,length,magic,gid)
  off,typ=(524,652) if length in (653,657) else (548,772) if length in (773,777) else (129,232)
  raw=title.encode('ascii');data[off:off+min(len(raw),typ-off)]=raw[:typ-off];data[typ]=entity
  nameoff=12 if length in (653,657) else 36;namecap=128 if length in (653,657,773,777) else 31
  data[nameoff:nameoff+min(len(name.encode()),namecap-1)]=name.encode()[:namecap-1]
  seq=self.get(self.ring+4);slot=self.ring+16+(seq&1023)*1024;self.put(slot,length);self.u.mem_write(slot+4,bytes(data));self.put(self.ring+4,seq+1)
 def hp_packet(self,hp,maximum,gid=101,opcode=0x977):
  self.u.mem_write(MODE+0xe9000,struct.pack('<HIII',opcode,gid,hp,maximum));self.run(base+0x2900,MODE,1)
 def update(self):self.run(base,0x131f4e8,1)
 def visible(self):return self.get(HUD+0x28)
# Every inherited vtable slot and RTTI pointer survives cloning.
for off in range(-4,0xd4,4):
 if off in (0,0x50):continue
 assert r(base+0xe100+off,4)==r(0x102be50+off,4),hex(off)
q=(ROOT/'Scripts/Patches/TargetMonsterHealthBar.qjs').read_bytes()
assert q.startswith(b'/*') and b'\n' not in q.replace(b'\r\n',b'')
# Production output has no HUD-specific runtime logging or diagnostic command.
for token in ('/targethudtest','target_monster_hud_trace.log','HUD TEST - 68% preview','THUD-'):
 assert token.encode('ascii') not in PE.read_bytes()
 assert token.encode('utf-16le') not in PE.read_bytes()
assert r(base+0x8000,0x800)==bytes(0x800)
assert r(base+0x9000,0x100)==bytes(0x100)

# Execute the actual relocated helper for every label style. Compare the whole
# surface to a one-pixel dilation of the foreground glyph mask, including
# clipped/empty labels, icon-row positioning and translucent artwork beneath.
for kind,text,font_size,color in [(0,'BAPHOMET',14,0xd7e7ee),(1,'680/1,000 ♦ 68%',12,0xffffff),(2,'MINI BOSS',12,0xb7d7e7),(3,'Mob Level: 81 ♦ Mob ID: 1039',12,0xd7e7ee),(4,'Mob Element: Dark Level: 3 ♦ ',12,0xd7e7ee)]:
 for y in (20,-3,H-12):
  outlined=Harness();dst=MODE+0x10000;label=INFO+0x200
  outlined.u.mem_write(label,text.encode()+b'\0');outlined.put(LAYOUT['icon_state']+12,-2)
  background=Image.new('RGBA',(W,H),(24,48,72,96))
  outlined.u.mem_write(dst,background.tobytes('raw','BGRA'))
  outlined.u.mem_write(dst-4,b'HEAD');outlined.u.mem_write(dst+W*H*4,b'TAIL')
  outlined.run(base+0x4000,HUD,4,[HUD,label,y,kind])
  font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',font_size)
  x=(W-round(font.getlength(text)))//2 if kind!=4 else -2
  mask=Image.new('L',(W+2,H+2));painter=ImageDraw.Draw(mask);painter.fontmode='1'
  painter.text((x+1,y+1),text,font=font,fill=255)
  contour=mask.filter(ImageFilter.MaxFilter(3)).crop((1,1,W+1,H+1))
  glyphs=mask.crop((1,1,W+1,H+1))
  expected=background.copy();expected.paste((1,1,1,255),(0,0,W,H),contour)
  expected.paste((color&255,(color>>8)&255,(color>>16)&255,255),(0,0,W,H),glyphs)
  actual=bytes(outlined.u.mem_read(dst,W*H*4))
  assert actual==expected.tobytes('raw','BGRA'),('outline pixels/alpha',kind,y)
  assert outlined.text_calls[-1]==(text,x,y,font_size,color)
  assert bytes(outlined.u.mem_read(dst-4,4))==b'HEAD' and bytes(outlined.u.mem_read(dst+W*H*4,4))==b'TAIL'
  outlined.u.mem_write(label,b'\0');before=actual
  outlined.run(base+0x4000,HUD,4,[HUD,label,y,kind])
  assert bytes(outlined.u.mem_read(dst,W*H*4))==before

assert struct.unpack('<I',r(0xcac6f0,4))[0]==0xca8a9b
hp_entry=target(0xca8aa2)
if r(hp_entry,1)==b'\xe9':hp_entry=target(hp_entry)
assert hp_entry==base+0x2900
h=Harness();h.update();assert h.visible()==1 and h.allocs==1 and h.original==1 and len(h.opens)==len(h.closes)==2
# Execute the actual monster update against both shared top-HUD reservations.
layout_cell=h.get(base+0xe0ec)
if layout_cell:
 for reserved_y in (114,24):
  h.put(layout_cell,reserved_y);h.update();assert h.get(HUD+0x20)==reserved_y,'Monster HUD ignored the live dial reservation'
for mode in (0,2,4,6):
 h.put(PLAYER+0x500,mode);h.update();assert h.visible()==0
for mode in (1,3,5):
 h.put(PLAYER+0x500,mode);h.update();assert h.visible()==1
for a,v in [(PLAYER+0x514,0),(PLAYER+0x70,3),(GAUGE+0xa0,0),(MODE+0xcc,0),(WORLD+0x2c,0)]:
 old=h.get(a);h.put(a,v);h.update();assert h.visible()==0,hex(a);h.put(a,old)
# First hover waits for a valid name. A refresh for the unchanged actor keeps
# the accepted title; hover exit clears ownership, so no stale name can return.
fresh=Harness();fresh.u.mem_write(INFO+0x98,b'\0');fresh.update();assert fresh.visible()==0
h.update();h.u.mem_write(INFO+0x98,b'\0');h.update();assert h.visible()==1
h.put(PLAYER+0x500,0);h.update();assert h.visible()==0
h.put(PLAYER+0x500,1);h.update();assert h.visible()==0
h.u.mem_write(INFO+0x98,b'\1');h.update();assert h.visible()==1
# Even a reused GID may not use another actor instance's cached name.
h.put(base+0xe0d4,MOB+4);h.u.mem_write(INFO+0x98,b'\0');h.update();assert h.visible()==0
h.u.mem_write(INFO+0x98,b'\1');h.update()
# Heap-backed long names are bounded and terminated inside the static buffer.
h.put(INFO+0x18,200);h.put(INFO+4,INFO+0x200);h.u.mem_write(INFO+0x200,b'A'*200+b'\0')
h.update();assert bytes(h.u.mem_read(state+64,128))==b'A'*127+b'\0'
h.put(INFO+0x18,15);h.u.mem_write(INFO+4,b'Baphomet\0')
# Native HP arrives before first frame, independently of Show Mob Info.
independent=Harness();independent.put(MOB+0x300,0);independent.hp_packet(7600,7600)
assert independent.native_hp_calls==0 and independent.get(MOB+0x300)==0
independent.update();independent.run(base+0x1000,HUD)
assert bytes(independent.u.mem_read(HP_TEXT,1))==b'\0'
assert independent.visible()==1 and independent.text_draws==['NORMAL','BAPHOMET']
assert (independent.get(HUD+0xa0),independent.get(HUD+0xa4))==(7600,7600)
assert all(bytes(independent.u.mem_read(INFO_TEXT+128*i,1))==b'\0' for i in range(3))
# Label toggles and even contradictory label HP cannot alter native HP.
independent.packet('#1257 1/100 1% Lv.51 Dark Lv.2 Undead');independent.update()
assert (independent.get(HUD+0xa0),independent.get(HUD+0xa4))==(7600,7600)
# Each text bit is independent; displayed values always come from native HP.
for title,expected in [('1/100','7,600/7,600'),('1%','100%'),('1/100 1%','7,600/7,600 ♦ 100%'),('Lv.51',''),('','')]:
 independent.packet(title);independent.update();independent.text_draws.clear();independent.run(base+0x1000,HUD)
 assert bytes(independent.u.mem_read(HP_TEXT,64)).split(b'\0')[0].decode()==expected
 assert independent.visible()==1 and independent.get(HUD+0xa0)==7600
 assert independent.text_draws[:2]==['NORMAL','BAPHOMET']
 if expected:assert expected in independent.text_draws
 else:assert all('%' not in label and '/' not in label and 'HP unknown'!=label for label in independent.text_draws)
# With text disabled, damage must still change the actual fill pixels.
full_surface=bytes(independent.u.mem_read(MODE+0x10000,W*H*4))
# Damage/healing continue through stock; full-health seeds avoid a new world bar.
independent.hp_packet(3000,7600);assert independent.native_hp_calls==1
independent.update();assert independent.get(HUD+0xa0)==3000
independent.text_draws.clear();independent.run(base+0x1000,HUD)
assert independent.text_draws==['NORMAL','BAPHOMET']
assert bytes(independent.u.mem_read(MODE+0x10000,W*H*4))!=full_surface
independent.hp_packet(7600,7600);assert independent.native_hp_calls==2
independent.put(GAUGE+0xa0,123);independent.update();assert independent.get(HUD+0xa0)==7600
# Bad pairs do not replace the last authoritative cache value.
for hp,mx in ((1,0),(101,100)):
 independent.hp_packet(hp,mx);independent.update();assert independent.get(HUD+0xa0)==7600
independent.hp_packet(0,7600);independent.update();assert independent.visible()==0
# Both cache generations are independent; new world clears native HP.
independent.run(base+0x2800,WORLD+4)
independent.u.reg_write(UC_X86_REG_EAX,101);independent.run(base+0xa800)
assert independent.u.reg_read(UC_X86_REG_EDX)==0
# No redraw work when name, HP, metadata and tier are unchanged.
h.update();h.put(HUD+0x58,0);h.update();assert h.get(HUD+0x58)==0
# Optional label packet layouts still work without feeding the HP source.
for layout in (653,657,773,777,233,237):
 h.packet('#77 Lv.9 Fire Lv.2 Demon',length=layout);h.update()
 assert bytes(h.u.mem_read(INFO_TEXT,128)).split(b'\0')[0]=='Mob Level: 9 ♦ Mob ID: 77'.encode()
for i in range(70):h.packet('Lv.1',gid=10000+i)
h.packet('#81 Lv.7');h.update();h.update()
assert bytes(h.u.mem_read(INFO_TEXT,128)).split(b'\0')[0]=='Mob Level: 7 ♦ Mob ID: 81'.encode()
# Hover uses the current hit-test result, independent of balloon recreation.
h.cursor=101;h.put(PLAYER+0x500,0);h.put(MODE+0x2ac,MODE+0x9000);h.put(MODE+0x2d8,101);h.update();assert h.visible()==1
h.option=False;h.update();assert h.visible()==0 and h.native_refreshes[-1] is False;h.option=True;h.update();assert h.visible()==1 and h.native_refreshes[-1] is True
h.put(MODE+0x2ac,0);h.update();assert h.visible()==1
# Repeated native balloon destruction must never pulse the custom HUD.
for balloon in (0,MODE+0x9000,0,MODE+0x9100,0)*20:
 h.put(MODE+0x2ac,balloon);h.update();assert h.visible()==1
h.ui_block=1;h.update();assert h.visible()==0;h.ui_block=0
h.modal=1;h.update();assert h.visible()==0;h.modal=0
h.cursor=0;h.update();assert h.visible()==0
h.put(MODE+0x2ac,MODE+0x9000);h.update();assert h.visible()==0
h.cursor=101
h.put(MODE+0x2ac,MODE+0x9000);h.u.mem_write(MOB+0x314,b'\6');h.update();assert h.visible()==0
h.u.mem_write(MOB+0x314,b'\5');h.cursor=0;h.put(MODE+0x2ac,0);h.put(PLAYER+0x500,1)
h.actor=False;h.update();assert h.visible()==0;h.actor=True
h.update();assert h.allocs==1
# A dead player may inspect living monsters; a stale attack cannot select one.
dead=Harness();dead.put(PLAYER+0x70,3);dead.put(INFO+0x94,1118)
dead.packet('#1257 7600/7600 100% Lv.51 Dark Lv.2 Undead',name='Injustice')
for action in (0,1,3,5):
 dead.put(PLAYER+0x500,action);dead.cursor=101;dead.update();assert dead.visible()==1
 dead.cursor=0;dead.update();assert dead.visible()==0
dead.cursor=101;dead.put(MOB+0x70,3);dead.update();assert dead.visible()==0
dead.put(MOB+0x70,0);dead.update();assert dead.visible()==1;dead.run(base+0x1000,HUD)
assert dead.icon_draws and bytes(dead.u.mem_read(state+64,128)).split(b'\0')[0]==b'INJUSTICE'
dead.option=False;dead.update();assert dead.visible()==0 and dead.native_refreshes[-1] is False
dead.option=True;dead.update();assert dead.visible()==1
dead.put(PLAYER+0x70,0);dead.cursor=0;dead.put(PLAYER+0x500,1);dead.update();assert dead.visible()==1
# Complete and optional Show Mob Info fields; Undead may mean element or race.
def line(h,index):return bytes(h.u.mem_read(INFO_TEXT+index*128,128)).split(b'\0')[0].decode('utf8')
h.packet('#1257 7600/7600 100% Lv.51 Dark Lv.2 Undead');h.update()
assert [line(h,i) for i in range(3)]==['Mob Level: 51 ♦ Mob ID: 1257','Mob Element: Dark Level: 2','Mob Race: Undead']
h.packet('Undead Lv.4 Undead');h.update();assert line(h,0)=='' and line(h,1)=='Mob Element: Undead Level: 4' and line(h,2)=='Mob Race: Undead'
h.packet('Lv.99 Demi-Human');h.update();assert [line(h,i) for i in range(3)]==['Mob Level: 99','','Mob Race: Demi-Human']
h.packet('#1002');h.update();assert line(h,0)=='Mob ID: 1002' and line(h,1)==line(h,2)==''
for title in ('#4294967296 Lv.4294967296 Fire Lv.9','HP unavailable','Dark Lv.x','Undeadx','Lv.0'):
 h.packet(title);h.update();assert [line(h,i) for i in range(3)]==['','',''],title
h.packet('#1257 Lv.51 Dark Lv.2 Undead',name='Custom Injustice');h.update();assert bytes(h.u.mem_read(state+64,128)).split(b'\0')[0]==b'CUSTOM INJUSTICE'
h.packet('');h.update();assert [line(h,i) for i in range(3)]==['','','']
# Invalid numeric labels must not enable HP text or reuse another target's flags.
for title in ('1/', '/100', '1/0', '101/100', '1/2/3', '4294967296/4294967296', '101%', '1x%', '%'):
 invalid_label=Harness();invalid_label.packet(title);invalid_label.update();invalid_label.run(base+0x1000,HUD)
 assert invalid_label.text_draws==['NORMAL','BAPHOMET'],title
no_metadata=Harness();no_metadata.packet('1/100 1%',gid=102);no_metadata.update();no_metadata.run(base+0x1000,HUD)
assert no_metadata.text_draws==['NORMAL','BAPHOMET']
# A high-rate percent-only packet must not invent an absolute HP pair.
percent_labels=Harness();percent_labels.put(MOB+0x300,0);percent_labels.packet('40%');percent_labels.update();percent_labels.run(base+0x1000,HUD);assert bytes(percent_labels.u.mem_read(HP_TEXT,11))==b'HP unknown\0'
rendered_surfaces=[]
for tier in range(3):
 h.put(INFO+0x94,[1102,1137,1128][tier])
 h.packet(['#1002 680/1000 68% Lv.1 Neutral Lv.1 Plant','#1096 680/1000 68% Lv.20 Holy Lv.4 Angel','#1039 680/1000 68% Lv.81 Dark Lv.3 Demon'][tier])
 h.u.mem_write(INFO+4,[b'Poring\0',b'Angeling\0',b'Baphomet\0'][tier]);h.put(GAUGE+0xa0,680);h.put(GAUGE+0xa4,1000);h.u.mem_write(MOB+0x304,bytes([tier]));h.update();h.run(base+0x1000,HUD);rendered_surfaces.append(bytes(h.u.mem_read(MODE+0x10000,W*H*4)));assert h.get(MODE+0x10000)==0
 # All tier/name/HP/detail labels retain their foreground and eight outline
 # neighbours; native icon placement must not shift the combined element row.
 for start in range(0,len(h.text_calls),9):
  passes=h.text_calls[start:start+9];assert len(passes)==9
  text,x,y,size,color=passes[-1];assert color!=0x00010101
  assert {(px-x,py-y) for _,px,py,_,_ in passes[:-1]}=={(dx,dy) for dy in (-1,0,1) for dx in (-1,0,1) if dx or dy}
  assert all(label==text and font==size and c==0x00010101 for label,_,_,font,c in passes[:-1])
 # Partial artwork alpha must survive both the BMP blit and outlined text.
 from io import BytesIO
 fixture=Image.open(BytesIO(h.files[MANIFEST['tiers'][tier]['empty']])).convert('RGBA')
 actual=Image.frombytes('RGBA',(W,H),rendered_surfaces[-1],'raw','BGRA')
 if 'divider_bounds' in MANIFEST['tiers'][tier]:
  bounds=tuple(MANIFEST['tiers'][tier]['divider_bounds'])
  assert actual.crop(bounds).tobytes()==fixture.crop(bounds).tobytes()
  alphas=list(fixture.crop(bounds).getchannel('A').tobytes())
  assert len(set(a for a in alphas if 0<a<255))>=15
 for hp,mx in [(1,1000),(1000,1000),(1200,1000),(2_000_000_000,2_100_000_000)]:
  h.put(GAUGE+0xa0,hp);h.put(GAUGE+0xa4,mx);h.update();h.run(base+0x1000,HUD)
# Exact fill clipping for each selectable design: empty, partial, full and clamped.
from io import BytesIO
for tier_index,tier in enumerate(MANIFEST['tiers']):
 bar=Harness();bar.u.mem_write(MOB+0x304,bytes([tier_index]));bar.update()
 empty=Image.open(BytesIO(bar.files[tier['empty']])).convert('RGBA')
 full=Image.open(BytesIO(bar.files[tier['full']])).convert('RGBA')
 left,top,right,bottom=tier['fill']
 for hp,maximum in [(0,1000),(1,1000),(500,1000),(1000,1000),(1200,1000),(2_000_000_000,2_100_000_000)]:
  bar.put(HUD+0xa0,hp);bar.put(HUD+0xa4,maximum);bar.run(base+0x1000,HUD)
  expected=Image.new('RGBA',(W,H))
  expected.paste(empty,(0,0),empty.getchannel('A').point(lambda a:255 if a else 0))
  edge=left+(right-left)*min(hp,maximum)//maximum
  if edge>left:
   crop=full.crop((left,top,edge,bottom))
   expected.paste(crop,(left,top),crop.getchannel('A').point(lambda a:255 if a else 0))
  actual=Image.frombytes('RGBA',(W,H),bytes(bar.u.mem_read(MODE+0x10000,W*H*4)),'raw','BGRA')
  # Name/tier text is above this band; decorations beside and below it must survive.
  bounds=(0,top,W,H)
  assert actual.crop(bounds).tobytes()==expected.crop(bounds).tobytes(),(DESIGN,tier['name'],hp)
h.run(base+0xd000,HUD,1);assert h.get(state)==0
h.update();assert h.allocs==2
assert len(h.opens)==len(h.closes)==6 # No file reopening during frames or window recreation.
for failure in ('missing','header','truncated','alpha_mask'):
 bad=Harness();leaf=MANIFEST['tiers'][0]['empty']
 if failure=='missing':bad.missing.add(leaf)
 elif failure=='header':bad.corrupt[leaf]=b'XX'+bad.files[leaf][2:]
 elif failure=='alpha_mask':bad.corrupt[leaf]=bad.files[leaf][:66]+bytes(4)+bad.files[leaf][70:]
 else:bad.corrupt[leaf]=bad.files[leaf][:-1]
 bad.update();assert bad.visible()==0 and bad.allocs==0
 bad.update();assert len(bad.opens)==1
 assert len(bad.closes)==1
# The nameplate bridge clears owned local presentation fields, never globals.
copy=MODE+0xd0000-0x1dc
for receiver in (copy+4,copy+0x7c):
 h.u.mem_write(receiver,b'old mob label\0');h.put(receiver+16,13);h.put(receiver+20,15)
h.put(copy+0x94,2301);h.u.mem_write(copy+0x98,b'\1');before=bytes(h.u.mem_read(INFO,0x9c))
h.run(base+0x5b00,0x15fa3c0,1)
assert h.get(copy+0x14)==0 and h.get(copy+0x8c)==0 and h.get(copy+0x94)==0
assert bytes(h.u.mem_read(INFO,0x9c))==before
for receiver in (copy+4,copy+0x7c):
 h.u.mem_write(receiver,b'old mob label\0');h.put(receiver+16,13)
h.u.mem_write(MOB+0x314,b'\6');h.run(base+0x5b00,0x15fa3c0,1)
assert h.get(copy+0x14)==13 and h.get(copy+0x8c)==13
h.u.mem_write(MOB+0x314,b'\5');h.option=False;h.run(base+0x5b00,0x15fa3c0,1)
assert h.get(copy+0x14)==13 and h.get(copy+0x8c)==13;h.option=True
# Heap-backed local copies retain ownership/capacity while being emptied.
for receiver in (copy+4,copy+0x7c):
 dst=receiver+0x1000;h.put(receiver,dst);h.put(receiver+20,127);h.put(receiver+16,80);h.u.mem_write(dst,b'X'*80+b'\0')
h.run(base+0x5b00,0x15fa3c0,1)
for receiver in (copy+4,copy+0x7c):
 assert h.get(receiver+20)==127 and h.get(receiver+16)==0 and bytes(h.u.mem_read(h.get(receiver),1))==b'\0'
assert h.get(copy+0x94)==0 and bytes(h.u.mem_read(INFO,0x9c))==before
# Comma grouping covers 32-bit values without corrupting adjacent memory.
for value,expected in [(0,'0'),(999,'999'),(1000,'1,000'),(999999,'999,999'),(1000000,'1,000,000'),(1000000000,'1,000,000,000'),(4294967295,'4,294,967,295')]:
 sp=STACK+0x8000;h.put(sp,STOP);dst=MODE+0xe8000;h.u.mem_write(dst-4,b'HEAD'+b'?'*16+b'TAIL')
 h.u.reg_write(UC_X86_REG_ESP,sp);h.u.reg_write(UC_X86_REG_EAX,value);h.u.reg_write(UC_X86_REG_EDX,dst);h.u.emu_start(base+0x9200,STOP,count=10000)
 assert bytes(h.u.mem_read(dst,16)).split(b'\0')[0].decode()==expected
 assert bytes(h.u.mem_read(dst-4,4))==b'HEAD' and bytes(h.u.mem_read(dst+16,4))==b'TAIL'
# Large absolute HP fits the expanded label, including totals above INT_MAX.
large=Harness();large.packet('1/100 1%');large.put(GAUGE+0xa0,3_000_000_000);large.put(GAUGE+0xa4,4_000_000_000);large.update();large.run(base+0x1000,HUD)
assert bytes(large.u.mem_read(HP_TEXT,64)).split(b'\0')[0]=='3,000,000,000/4,000,000,000 ♦ 75%'.encode()
assert bytes(large.u.mem_read(state+64,128)).split(b'\0')[0]==b'BAPHOMET'
large.put(MOB+0x300,0);large.hp_packet(4294967295,4294967295);large.update();large.run(base+0x1000,HUD)
assert bytes(large.u.mem_read(HP_TEXT,64)).split(b'\0')[0]=='4,294,967,295/4,294,967,295 ♦ 100%'.encode()
# A missing icon leaves the ordinary element text and never hides the HUD.
missing_icon=Harness();missing_icon.icon_exists=False;missing_icon.put(INFO+0x94,1138);missing_icon.packet('Dark Lv.4 Demon');missing_icon.update();missing_icon.run(base+0x1000,HUD)
assert missing_icon.visible()==1 and not missing_icon.icon_draws
# OFF leaves a freshly copied stock group ID intact (including NPCs).
h.option=False;h.put(copy+0x94,1138);h.run(base+0x5b00,0x15fa3c0,1);assert h.get(copy+0x94)==1138;h.option=True
# Fallback tier badges must also disappear only while relocation is on.
h.u.mem_write(MODE+0xd0000-0x1e4,b'\2');h.run(base+0x9e00,MOB,1);assert bytes(h.u.mem_read(MODE+0xd0000-0x1e4,1))==b'\0'
h.option=False;h.u.mem_write(MODE+0xd0000-0x1e4,b'\2');h.run(base+0x9e00,MOB,1);assert bytes(h.u.mem_read(MODE+0xd0000-0x1e4,1))==b'\2';h.option=True
# Each native icon keeps the destination alpha mode and fixes its keyed pixels.
assert h.icon_draws
x,y,iw,ih=h.icon_draws[-1]
assert h.get(MODE+0x10000+((y+12)*W+x+12)*4)>>24==255
assert h.get(MODE+0x10000+(y*W+x)*4)==0
assert bytes(h.u.mem_read(MODE+0x8028,1))==b'\1'
# Keep a deterministic rendering receipt without writing build images by default.
report={
 'exe_sha256':hashlib.sha256(PE.read_bytes()).hexdigest(),
 'design':DESIGN,
 'asset_sha256':{name:hashlib.sha256(data).hexdigest() for name,data in h.files.items()},
 'rendered_surface_sha256':[hashlib.sha256(data).hexdigest() for data in rendered_surfaces],
 'checks':'one-pixel text outlines and clipped RGB-only glyph alpha, independent native HP, per-field HP text visibility, label-only metadata, resource/alpha/formatting, icons, option restoration and dead-player hover',
}
if args.report:
 args.report.parent.mkdir(parents=True,exist_ok=True)
 args.report.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print('PASS:',DESIGN,'target HUD behavior, fill clipping, rendering, protocol, resources and calling conventions')
