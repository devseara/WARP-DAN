"""Export fitted code-native VIP controls using the existing three-column skin.

Matches the established Apply VIP/Open Store compositor. Does not change game
files; output must be a new directory. Captions are part of the resulting PNGs.
"""
import argparse
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

STATES=('out','over','press','off')
LABELS=(('upgrade','Upgrade'),('yes','Yes'),('no','No'),('cancel','Cancel'),('close','X'))
parser=argparse.ArgumentParser();parser.add_argument('--skin',type=Path,required=True)
parser.add_argument('--output',type=Path,required=True)
selection=parser.add_mutually_exclusive_group()
selection.add_argument('--purchase-only',action='store_true')
selection.add_argument('--refresh-only',action='store_true',help='Reuse the current complete Upgrade skin; preserve Refresh 58x18 ABI')
args=parser.parse_args()
if args.purchase_only:LABELS=(('purchase','Purchase'),)
if args.refresh_only:LABELS=(('refresh','Refresh'),)
args.output.mkdir(parents=True,exist_ok=False)
font=ImageFont.truetype('C:/Windows/Fonts/tahoma.ttf',12)
records=[]
for name,label in LABELS:
    left,top,right,bottom=font.getbbox(label)
    width=right-left+8;height=18
    if args.refresh_only:width=58
    for state in STATES:
        if args.refresh_only:
            src=Image.open(args.skin/('upgrade_'+state+'.png')).convert('RGBA')
            assert src.size==(53,18),'Use the current fitted Upgrade button'
        else:
            src=Image.open(args.skin/('openstore_'+('out' if state=='off' else state)+'.png')).convert('RGBA')
            assert src.size==(66,18),'Use the original 66x18 skin, not a complete labelled button'
        skin=Image.new('RGBA',(width,height))
        skin.paste(src.crop((0,0,3,18)),(0,0))
        skin.paste(src.crop((3,0,4,18)).resize((width-6,18),Image.Resampling.NEAREST),(3,0))
        skin.paste(src.crop((src.width-3,0,src.width,18)),(width-3,0))
        if state=='off' and not args.refresh_only:skin.putalpha(skin.getchannel('A').point(lambda value:value*120//255))
        # Retain alpha in corner/disabled pixels; no parent background is baked in.
        color=(153,153,153,255) if state=='off' else (65,99,136,255)
        textx=(width-(right-left))//2-left if args.refresh_only else 4-left
        ImageDraw.Draw(skin).text((textx,(height-(bottom-top))//2-top),label,font=font,fill=color)
        target=args.output/(name+'_'+state+'.png');skin.save(target)
        records.append(dict(file=target.name,width=width,height=height,sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
assert len(records)==4*len(LABELS)
(args.output/'buttons.json').write_text(json.dumps(records,indent=2)+'\n',encoding='utf8')
sheet=Image.new('RGB',(470,30+len(LABELS)*32),(247,250,255));draw=ImageDraw.Draw(sheet)
for i,state in enumerate(STATES):draw.text((120+i*85,5),state,font=font,fill=(40,60,85))
for row,(name,_) in enumerate(LABELS):
    draw.text((5,36+row*32),name,font=font,fill=(40,60,85))
    for column,state in enumerate(STATES):
        im=Image.open(args.output/(name+'_'+state+'.png')).convert('RGBA')
        sheet.paste(im,(120+column*85,32+row*32),im)
sheet.save(args.output.parent/'fitted-buttons-preview.png')
print('Exported',len(records),'complete fitted state PNGs:',[(n,Image.open(args.output/(n+'_out.png')).size) for n,_ in LABELS])
