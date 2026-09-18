"""Render exact-size native VIP UI skins from code, including button captions.

Extends the existing deterministic VIP button pipeline. No screenshot pixels,
character sprites, item icons or game-state text are baked into these assets.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

STATES = ('out', 'over', 'press', 'off')
BUTTONS = (
    ('applyvip', 'Apply VIP', 60), ('openstore', 'Open Store', 68),
    ('openstorage', 'Open Storage', 81), ('vipbuffs', 'VIP Buffs', 57),
    ('upgrade', 'Upgrade', 53), ('purchase', 'Purchase', 56),
    ('refresh', 'Refresh', 58), ('yes', 'Yes', 28), ('no', 'No', 23),
    ('cancel', 'Cancel', 43), ('close', 'X', 15),
)
CENTERED_BUTTONS = tuple((prefix+'_centered', label, 100)
                         for prefix, label, _ in BUTTONS[:4])

def gradient(im, box, top, bottom):
    d = ImageDraw.Draw(im)
    x, y, w, h = box
    for row in range(h):
        color = tuple(a + (b-a)*row//max(1, h-1) for a,b in zip(top,bottom))
        d.line((x,y+row,x+w-1,y+row), fill=color)

def panel(im, box, fill=(247,250,255), edge=(175,190,213)):
    x,y,w,h = box
    d = ImageDraw.Draw(im)
    d.rectangle((x,y,x+w-1,y+h-1), fill=edge)
    d.rectangle((x+1,y+1,x+w-2,y+h-2), fill='white')
    d.rectangle((x+2,y+2,x+w-3,y+h-3), fill=fill)
    d.line((x+2,y+h-2,x+w-2,y+h-2), fill=(220,229,241))

def render(output, centered_only=False):
    output.mkdir(parents=True, exist_ok=False)
    font = ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf', 12)
    records = []
    def save(name, im):
        path=output/name
        im.save(path)
        records.append(dict(file=name,width=im.width,height=im.height,
                            sha256=hashlib.sha256(path.read_bytes()).hexdigest()))

    buttons = CENTERED_BUTTONS if centered_only else BUTTONS+CENTERED_BUTTONS
    for prefix,label,width in buttons:
        for state in STATES:
            im=Image.new('RGBA',(width,18),(247,250,255,255))
            d=ImageDraw.Draw(im)
            edge={'out':(127,153,188),'over':(87,133,187),'press':(85,117,156),'off':(179,186,198)}[state]
            top={'out':(245,250,255),'over':(253,252,236),'press':(171,196,226),'off':(245,246,248)}[state]
            bottom={'out':(181,207,240),'over':(193,221,252),'press':(217,232,251),'off':(223,227,233)}[state]
            d.rectangle((0,1,width-1,16),fill=(*edge,255))
            d.line((1,0,width-2,0),fill=(*edge,255))
            d.line((1,17,width-2,17),fill=(*edge,255))
            gradient(im,(1,1,width-2,16),(*top,255),(*bottom,255))
            d.line((2,2,width-3,2),fill=(225,238,252,255) if state=='press' else (255,255,255,255))
            d.line((2,15,width-3,15),fill=(*edge,255))
            left,top_t,right,bottom_t=font.getbbox(label)
            x=(width-(right-left))//2-left
            y=(18-(bottom_t-top_t))//2-top_t
            color=(136,146,160,255) if state=='off' else (50,76,108,255)
            # No pressed offset: fitted labels always stay within their existing ABI.
            d.text((x,y),label,font=font,fill=color)
            save(prefix+'_'+state+'.png',im)

    if centered_only:
        assert len(records)==16
        (output/'skin-manifest.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
        print(f'Rendered {len(records)} centered VIP button states into {output}')
        return

    for prefix,up in (('scroll_top',True),('scroll_bot',False)):
        for state in STATES:
            im=Image.new('RGBA',(13,13),(247,250,255,255))
            edge=(187,198,215) if state=='off' else (132,158,193)
            panel(im,(0,0,13,13),(224,235,249) if state!='press' else (192,210,235),edge)
            d=ImageDraw.Draw(im)
            points=[(6,3),(3,8),(9,8)] if up else [(3,4),(9,4),(6,9)]
            d.polygon(points,fill=(182,192,208) if state=='off' else (82,112,153))
            save(prefix+('.png' if state=='out' else '_'+state+'.png'),im)

    im=Image.new('RGBA',(736,420),'white')
    panel(im,(0,0,736,420),(255,255,255),(113,137,174))
    gradient(im,(2,2,732,16),(233,243,255,255),(171,191,223,255))
    d=ImageDraw.Draw(im)
    d.line((2,3,733,3),fill='white')
    d.line((1,18,734,18),fill=(129,156,189))
    gradient(im,(2,395,732,22),(246,249,255,255),(228,237,249,255))
    save('background.png',im)

    im=Image.new('RGBA',(421,375),(247,250,255,255))
    panel(im,(20,15,380,20),(255,248,233),(209,191,152))
    panel(im,(20,47,380,300),(242,248,255),(175,190,213))
    for y in (84,135,186,237,288):
        panel(im,(31,y,340,44),(243,248,255),(185,201,223))
        gradient(im,(33,y+2,336,39),(254,255,255,255),(226,236,250,255))
    save('vip_status_bg.png',im)
    im=Image.new('RGBA',(32,32),'white')
    panel(im,(0,0,32,32),(244,248,255),(181,197,219))
    save('item_main_bg.png',im)
    assert len(records)==71
    (output/'skin-manifest.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
    sheet=Image.new('RGB',(650,26+len(buttons)*26),(247,250,255))
    d=ImageDraw.Draw(sheet)
    for col,state in enumerate(STATES):d.text((180+col*115,4),state,font=font,fill=(50,76,108))
    for row,(prefix,_,_) in enumerate(buttons):
        d.text((4,31+row*26),prefix,font=font,fill=(50,76,108))
        for col,state in enumerate(STATES):
            src=Image.open(output/(prefix+'_'+state+'.png'))
            sheet.paste(src,(180+col*115,28+row*26),src)
    sheet.save(output.parent/'button-states.png')
    print(f'Rendered {len(records)} exact-size VIP textures into {output}')

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--centered-only',action='store_true',help='Export only the 16 new main-button states; preserve legacy art')
    args=ap.parse_args()
    render(args.output,args.centered_only)
