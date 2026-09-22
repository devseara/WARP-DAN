"""Independent readable VIP artwork/layout oracle."""
from PIL import Image,ImageDraw,ImageFont
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
BUTTONS.update({20:('close',341,1,15,18),21:('yes',150,78,28,18),
                22:('no',186,78,23,18),23:('upgrade',128,240,53,18),
                24:('cancel',189,240,43,18),25:('purchase',126,296,56,18)})
CAPTIONS={1:'X',2:'Apply VIP',3:'Open Store',4:'Open Storage',5:'VIP Buffs',
          6:'Upgrade',9:'Refresh',20:'X',21:'Yes',22:'No',23:'Upgrade',24:'Cancel',25:'Purchase'}
def crop(sx,sy,sw,sh,width,height):
    out=Image.new('RGB',(width,height))
    out.putdata([ATLAS.getpixel((sx+x*sw//width,sy+y*sh//height)) for y in range(height) for x in range(width)])
    return out
def bounds(control):return BUTTONS[control][1:]
def button(control,state,background=(244,252,255,255),caption_state=None):
    width,height=bounds(control)[2:]
    # Independent oracle uses Gacha's original bytes, not the copied VIP file.
    art=Image.open(ROOT/'Assets/GachaUI'/f'button_10_{("out","over","press","off")[state]}.png').convert('RGBA')
    def axis(pos,extent,source):
        return pos if pos<2 else source-extent+pos if pos>=extent-2 else 2+(pos-2)*(source-4)//(extent-4)
    skin=Image.new('RGBA',(width,height))
    skin.putdata([art.getpixel((axis(x,width,51),axis(y,height,20))) for y in range(height) for x in range(width)])
    out=Image.alpha_composite(Image.new('RGBA',skin.size,background),skin)
    disabled=(state if caption_state is None else caption_state)==3
    color=(160,160,160,255) if disabled else (69,96,125,255)
    draw=ImageDraw.Draw(out)
    if control in (7,8):
        for row in range(3):
            y=3+(row if control==7 else 2-row)
            draw.line((width//2-row,y,width//2+row,y),fill=color)
    else:
        font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',11)
        caption=CAPTIONS[control]
        while caption and int(font.getlength(caption))>width-4:caption=caption[:-1]
        x=2+(width-4-int(font.getlength(caption)))//2
        draw.text((x,(height-11)//2-2),caption,font=font,fill=color[:3]+(0,))
    return out.convert('RGB')

def level_box(earned):
    out=Image.open(ROOT/'Assets/VipUI/item_main_bg.png').convert('RGBA')
    if earned:
        art=Image.open(ROOT/'Assets/VipUI/membership_crown.png').convert('RGBA')
        art=art.crop(art.getchannel('A').point(lambda a:255 if a>=32 else 0).getbbox())
        width,height=17,17*art.height//art.width
        if height>17:width,height=17*art.width//art.height,17
        small=Image.new('RGBA',(width,height));pixels=[]
        for y in range(height):
            for x in range(width):
                samples=[art.getpixel(((x*4+xx)*art.width//(width*4),(y*4+yy)*art.height//(height*4))) for yy in range(4) for xx in range(4)]
                alpha=sum(p[3] for p in samples)
                pixels.append(tuple(sum(p[i]*p[3] for p in samples)//alpha for i in range(3))+(alpha//16,) if alpha else (0,0,0,0))
        small.putdata(pixels);out.alpha_composite(small,(1+(17-width)//2,1+(17-height)//2))
    return out.convert('RGB')
def read(m,obj,x,y,w,h):
    ptr,stride,_=m.pixels(obj)
    data=b''.join(bytes(m.u.mem_read(ptr+((y+i)*stride+x)*4,w*4)) for i in range(h))
    return Image.frombytes('RGBA',(w,h),data,'raw','BGRA').convert('RGB')
