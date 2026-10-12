"""Export existing code-native VIP controls as complete, editable PNGs.

One-time migration from the preserved 96-byte-API client. No live game, image
redesign, player data or installed artwork mutation. Output must be a new folder.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
from PIL import Image, ImageDraw, ImageFont
from test_vip_ui import VipMachine, snapshot

STATES=('out','over','press','off')
ap=argparse.ArgumentParser();ap.add_argument('exe');ap.add_argument('--art',type=Path,required=True)
ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
assert hashlib.sha256(Path(args.exe).read_bytes()).hexdigest()=='93792647c31f7618adb9e7c7d5193db08f6dff451e6e98885d72abe8ffae59b6','Use the preserved code-button client'
args.output.mkdir(parents=True,exist_ok=False)
m=VipMachine(args.exe);m.assets=args.art;obj=m.ready(snapshot(flags=1|2|4|8|16));c=m.c
font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',12)
records=[]
def save(name,im):
    path=args.output/name;assert not path.exists();im.save(path)
    records.append({'file':name,'width':im.width,'height':im.height,'sha256':hashlib.sha256(path.read_bytes()).hexdigest()})
def copy(name):
    target=args.output/name;assert not target.exists();shutil.copy2(args.art/name,target)
    im=Image.open(target);records.append({'file':name,'width':im.width,'height':im.height,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()})
def export_pixels(x,y,width,height):
    pix,w,h=m.pixels(obj)
    data=b''.join(bytes(m.u.mem_read(pix+((y+row)*w+x)*4,width*4)) for row in range(height))
    # The native parent uses opaque RGB surfaces; text alpha is not uploaded.
    return Image.frombytes('RGBA',(width,height),data,'raw','BGRA').convert('RGB').convert('RGBA')

# Export the actual old x86 widget compositor, including its text and state skins.
for phase,state in enumerate(STATES):
    for name,control,x,y,width in [('applyvip',2,122,166,60),('openstore',3,188,166,68),
                                  ('openstorage',4,122,192,81),('vipbuffs',5,209,192,57)]:
        m.w(c['state']+4,control if phase==2 else 0)
        m.w(c['state']+8,control if phase==1 else 0)
        m.w(c['state']+24,0 if phase==3 else 1)
        m.invoke(c['draw'],obj);save(f'{name}_{state}.png',export_pixels(x,y,width,18))

# These code-native rectangles/text follow the existing C++ control style. They
# become full PNGs too, so none of their borders or captions are painted at runtime.
face=[(223,236,253),(198,223,250),(180,206,234),(234,236,239)]
for name,label,width,height,textx,texty in [('close','X',18,16,3,0),('refresh','Refresh',58,18,5,0),
        ('yes','Yes',48,22,5,2),('no','No',48,22,5,2),('cancel','Cancel',66,22,5,2)]:
    for phase,state in enumerate(STATES):
        im=Image.new('RGBA',(width,height),(189,202,224,255));draw=ImageDraw.Draw(im)
        draw.rectangle((1,1,width-2,height-2),fill=(*face[phase],255))
        draw.text((textx,texty),label,font=font,fill=(153,153,153,255) if phase==3 else (65,99,136,255))
        save(f'{name}_{state}.png',im)

# Upgrade is already a complete labelled bitmap; preserve the supplied four files.
for state in STATES:copy(f'upgrade_{state}.png')
for name,up in [('scroll_top',True),('scroll_bot',False)]:
    copy(name+'.png') # Keep the user's original normal-state filenames/artwork.
    m.w(c['state']+4,0);m.w(c['state']+8,0);m.w(c['state']+24,1);m.invoke(c['draw'],obj)
    save(name+'_off.png',export_pixels(775,111 if up else 346,13,13))
    for phase,state in [(1,'over'),(2,'press')]:
        im=Image.new('RGBA',(13,13),(174,194,223,255));draw=ImageDraw.Draw(im)
        draw.rectangle((1,1,11,11),fill=(*face[phase],255))
        points=[(6,3),(3,9),(9,9)] if up else [(3,3),(9,3),(6,9)]
        draw.polygon(points,fill=(123,150,207,255));draw.line(points+[points[0]],fill=(246,251,255,255))
        save(name+'_'+state+'.png',im)
assert len(records)==48 and len({r['file'] for r in records})==48
(args.output/'buttons.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
groups=['applyvip','openstore','openstorage','vipbuffs','upgrade','refresh','yes','no','cancel','close','scroll_top','scroll_bot']
sheet=Image.new('RGB',(560,26+len(groups)*30),(248,250,255));draw=ImageDraw.Draw(sheet)
for i,state in enumerate(STATES):draw.text((140+i*103,3),state,font=font,fill=(30,50,80))
for row,name in enumerate(groups):
    draw.text((5,31+row*30),name,font=font,fill=(30,50,80))
    for col,state in enumerate(STATES):
        file=name+'.png' if name.startswith('scroll_') and state=='out' else name+'_'+state+'.png'
        im=Image.open(args.output/file).convert('RGBA');sheet.paste(im,(140+col*103,29+row*30),im)
sheet.save(args.output.parent/'button-states-preview.png')
print('Exported 48 complete state PNGs, labels included. No installed files changed:',args.output)
