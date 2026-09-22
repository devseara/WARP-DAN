"""Independent readable VIP artwork/layout oracle."""
from PIL import Image
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
X=lambda x:x*460//1412
Y=lambda y:y*362//1114
ATLAS=Image.open(ROOT/'Assets/VipUI/vip_design.png').convert('RGB')
BUTTONS={1:('main_close',439,3,18,18),2:('applyvip',153,120,128,22),
         3:('openstore',289,120,128,22),4:('openstorage',153,145,128,22),
         5:('vipbuffs',289,145,128,22),6:('main_upgrade',164,252,60,20),
         9:('refresh',164,320,60,20),7:('scroll_top',439,268,10,10),
         8:('scroll_bot',439,328,10,10)}
def crop(sx,sy,sw,sh,width,height):
    out=Image.new('RGB',(width,height))
    out.putdata([ATLAS.getpixel((sx+x*sw//width,sy+y*sh//height)) for y in range(height) for x in range(width)])
    return out
def bounds(control):return BUTTONS[control][1:]
def button(control,state):
    return Image.open(ROOT/'Assets/VipUI'/f'{BUTTONS[control][0]}_{("out","over","press","off")[state]}.png').convert('RGB')
def read(m,obj,x,y,w,h):
    ptr,stride,_=m.pixels(obj)
    data=b''.join(bytes(m.u.mem_read(ptr+((y+i)*stride+x)*4,w*4)) for i in range(h))
    return Image.frombytes('RGBA',(w,h),data,'raw','BGRA').convert('RGB')
