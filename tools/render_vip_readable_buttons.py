"""Exact-size code-native RO button skins for the approved readable VIP layout.

Extends the existing deterministic skin exporter. Draws new PNGs from geometry
and font metrics; never edits or rescales the approved reference artwork.
"""
import argparse,hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from render_vip_ragnarok_skin import gradient

STATES=('out','over','press','off')
BUTTONS=(('applyvip','Apply VIP',128,22,12),('openstore','Open Store',128,22,12),
 ('openstorage','Open Storage',128,22,12),('vipbuffs','VIP Buffs',128,22,12),
 ('main_upgrade','Upgrade',60,20,12),('refresh','Refresh',60,20,12),
 ('main_close','X',18,18,12),('close','X',15,18,11),
 ('upgrade','Upgrade',53,18,11),('purchase','Purchase',56,18,11),
 ('yes','Yes',28,18,11),('no','No',23,18,11),('cancel','Cancel',43,18,11),
 ('scroll_top','',10,10,0),('scroll_bot','',10,10,0))

def render(output):
    output.mkdir(parents=True,exist_ok=False);records=[]
    for prefix,label,w,h,size in BUTTONS:
        for state in STATES:
            im=Image.new('RGBA',(w,h),(244,252,255,255));d=ImageDraw.Draw(im)
            gray=state=='off'
            edge=(114,119,137,255) if gray else (30,64,126,255)
            top=(249,250,252,255) if gray else (235,247,255,255)
            bottom=(199,204,218,255) if gray else (160,197,250,255)
            if state=='over':top=(247,252,255,255);bottom=(182,216,255,255)
            if state=='press':top=(159,194,240,255);bottom=(212,233,255,255)
            gradient(im,(1,1,w-2,h-2),top,bottom)
            d=ImageDraw.Draw(im)
            d.polygon([(3,0),(w-4,0),(w-1,3),(w-1,h-4),(w-4,h-1),(3,h-1),(0,h-4),(0,3)],outline=edge)
            d.line([(3,1),(w-4,1),(w-2,3)],fill=(255,255,255,255))
            d.line([(1,3),(1,h-4)],fill=(248,252,255,255))
            d.line([(3,h-2),(w-4,h-2),(w-2,h-4)],fill=(151,164,191,255) if gray else (80,125,203,255))
            # Consistent optical centering, never stretched or painted over at runtime.
            if label:
                font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',size)
                l,t,r,b=font.getbbox(label);assert r-l<=w-4 and b-t<=h-4,(prefix,r-l,w)
                d.text(((w-(r-l))//2-l,(h-(b-t))//2-t),label,font=font,
                       fill=(76,80,98,255) if gray else (10,29,75,255))
            else:
                points=[(4,2),(2,6),(7,6)] if prefix=='scroll_top' else [(2,3),(7,3),(4,7)]
                d.polygon(points,fill=(112,118,136,255) if gray else (32,53,94,255))
            name=f'{prefix}_{state}.png';path=output/name;im.save(path)
            records.append(dict(file=name,width=w,height=h,sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    (output/'manifest.json').write_text(json.dumps(records,indent=2)+'\n')
    assert len(records)==60
    print(f'Exported {len(records)} full-caption PNG states into {output}')

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True)
    render(ap.parse_args().output)
