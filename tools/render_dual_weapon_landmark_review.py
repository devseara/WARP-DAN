"""Render source-pixel annotations, without claiming a game/GPU screenshot."""
import json, sys
from pathlib import Path
sys.dont_write_bytecode=True
from PIL import Image,ImageDraw,ImageFont
from audit_dual_weapon_type_coverage import Corpus,ROOT
from dual_weapon_formats.spr_reader import Spr
from build_dual_weapon_grip_profile import INPUT,CLIENT,BODY

def main():
    out=ROOT/'Outputs/dual_weapon_pixel_audit'
    ann=json.loads(INPUT.read_text(encoding='utf-8'));inv=json.loads((out/'inventory.json').read_text(encoding='utf-8'))
    c=Corpus(CLIENT);s=Spr(c.read(BODY+'.spr'));font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    entries=list(ann['body_pixels'].items())
    for page in range(4):
        sheet=Image.new('RGB',(1200,780),(230,235,240));pen=ImageDraw.Draw(sheet)
        for cell,(n,pts) in enumerate(entries[page*8:(page+1)*8]):
            rgba,w,h=s.get_rgba(int(n),0);im=Image.frombytes('RGBA',(w,h),rgba)
            x,y=10+(cell%4)*300,35+(cell//4)*390;scale=4
            sheet.paste(im.resize((w*scale,h*scale),Image.Resampling.NEAREST),(x,y),im.resize((w*scale,h*scale),Image.Resampling.NEAREST))
            pen.text((x,y-25),f'Body image {n}: red role0 / cyan role1',font=font,fill='black')
            for role,(px,py) in enumerate(pts):
                cx,cy=x+(px+.5)*scale,y+(py+.5)*scale;color=('red','blue')[role]
                pen.ellipse((cx-4,cy-4,cx+4,cy+4),outline=color,width=1)
                pen.text((x,y+h*scale+5+role*18),f'{role}: ({px},{py})',font=font,fill=color)
        sheet.save(out/f'body-landmarks-page{page}.png')
    for r in inv['weapons']:
        if str(r['view']) not in ann['weapon_pixels']:continue
        sheet=Image.new('RGB',(1000,400),(230,235,240));pen=ImageDraw.Draw(sheet)
        for col,(n,(grip,tip)) in enumerate(ann['weapon_pixels'][str(r['view'])].items()):
            im=Image.open(out/f"view{r['view']}-kind0-image{n}.png").convert('RGBA');w,h=im.size
            scale=4;x,y=col*250+10,30
            large=im.resize((w*scale,h*scale),Image.Resampling.NEAREST);sheet.paste(large,(x,y),large)
            pen.text((x,5),f"view{r['view']} image{n}",font=font,fill='black')
            for label,point,color in [('grip',grip,'red'),('tip',tip,'blue')]:
                cx,cy=x+(point[0]+.5)*scale,y+(point[1]+.5)*scale
                pen.ellipse((cx-4,cy-4,cx+4,cy+4),outline=color,width=1)
                pen.text((x,320 if label=='grip' else 345),f'{label}: {point}',font=font,fill=color)
        sheet.save(out/f"weapon-landmarks-view{r['view']}.png")
    c.close()
if __name__=='__main__':main()
