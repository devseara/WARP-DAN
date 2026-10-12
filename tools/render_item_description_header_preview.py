"""QA preview: real emitted background/body; native title and portrait simulated."""
from pathlib import Path
import argparse,json,struct
import pefile
from PIL import Image,ImageDraw,ImageFont
from verify_item_description_native import VM,PIXELS,WIN

def render(directory):
    m=json.loads((directory/'native-manifest.json').read_text(encoding='utf8'))['itemDescription']
    v=VM(pefile.PE(str(directory/'item-description.exe')),m);v.open(itemid=4001,refine=0)
    data=v.response();data[96:128]=b'Card / Enchantment\0'.ljust(32,b'\0');data[128:]=bytes(len(data)-128)
    rows=[(1,'Weight','1.0'),(3,'','LUK +2; Perfect Dodge +1')]
    for n,(section,label,text) in enumerate(rows):
        at=128+n*192;struct.pack_into('<HH',data,at,section,0)
        data[at+16:at+16+len(label)]=label.encode();data[at+64:at+64+len(text)]=text.encode()
    struct.pack_into('<H',data,38,len(rows));assert v.receive(data)==1;v.run('Draw')
    w=v.read32(WIN+0x14);h=220;raw=bytearray(v.u.mem_read(PIXELS,w*h*4))
    for i in range(0,len(raw),4):
        if raw[i:i+3]==b'\xff\x00\xff':raw[i:i+4]=b'\xff\xff\xff\0'
        else:raw[i+3]=255
    image=Image.frombytes('RGBA',(w,h),bytes(raw),'raw','BGRA')
    # This is the already-installed collection art; no game assets are edited.
    art=Path(__file__).resolve().parent/'fixtures/item_description/assets/collection/Poring_Card.bmp'
    portrait=Image.open(art).convert('RGBA');assert portrait.size==(75,100)
    for y in range(100):
        for x in range(75):
            if portrait.getpixel((x,y))[:3]==(255,0,255):portrait.putpixel((x,y),(255,255,255,0))
    image.alpha_composite(portrait,(10,11));draw=ImageDraw.Draw(image)
    font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',12)
    draw.text((90,10),'Poring Card',font=font,fill='#303c4e')
    for x,y,text,color,bold in v.draws:
        if y<h-12:draw.text((x,y),text,font=font,fill=(color&255,(color>>8)&255,(color>>16)&255))
    image.save(directory/'header-style-preview.png')
    print('QA preview saved; native title/portrait boundary simulated, not a live screenshot')
if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('directory',type=Path);render(ap.parse_args().directory)
