"""Export exact active weapon/body pixels for manual grip/socket annotation."""
from __future__ import annotations
import json, hashlib, math, sys
from pathlib import Path
sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFont
from audit_dual_weapon_type_coverage import Corpus, ROOT
from dual_weapon_formats.act_reader import parse_act
from dual_weapon_formats.spr_reader import Spr

CLIENT = Path(r'D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes')
OUT = ROOT/'Outputs/dual_weapon_pixel_audit'
BODY = 'data/sprite/인간족/몸통/여/어쌔신크로스_여'

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    corpus = Corpus(CLIENT)
    coverage = json.loads((ROOT/'docs/evidence/dual-weapon-type-coverage.json').read_text(encoding='utf-8'))
    records = [r for r in coverage['views'] if r['base_type'] in (1,2,6) and r['view'] not in range(600,607) and
               r.get('genders',{}).get('female',{}).get('status')=='resolved' and r['kind']=='single_weapon_view']
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 14)
    inventory = []
    for r in records:
        stem = r['genders']['female']['resource']
        act, spr = parse_act(corpus.read(stem+'.act')), Spr(corpus.read(stem+'.spr'))
        used = {}
        for a, action in enumerate(act['actions']):
            for f, frame in enumerate(action.frames):
                for l in frame.layers:
                    if l.sprite_index>=0:
                        used.setdefault((l.sprite_type,l.sprite_index),[]).append([a,f])
        row = dict(view=r['view'], type=r['base_type'], stem=stem, images=[])
        sheet = Image.new('RGB',(900,math.ceil(len(spr.images)/3)*380),(229,233,235))
        pen = ImageDraw.Draw(sheet)
        for n, src in enumerate(spr.images):
            kind, index = (0,n) if src.is_indexed else (1,n-spr.n_indexed8)
            rgba,w,h=spr.get_rgba(index,kind)
            im=Image.frombytes('RGBA',(w,h),rgba)
            filename=f"view{r['view']}-kind{kind}-image{index}.png"
            im.save(OUT/filename)
            x,y=20+(n%3)*300,40+(n//3)*380
            scale=min(5,260//max(w,h))
            big=im.resize((w*scale,h*scale),Image.Resampling.NEAREST)
            sheet.paste(big,(x,y),big)
            pen.text((x,y-30),f"view {r['view']} image {kind}:{index} {w}x{h}",fill='black',font=font)
            for p in range(0,w+1,5):
                pen.line((x+p*scale,y,x+p*scale,y+h*scale),fill=(190,195,200))
                pen.text((x+p*scale,y+h*scale+3),str(p),fill='black',font=font)
            for p in range(0,h+1,5):
                pen.line((x,y+p*scale,x+w*scale,y+p*scale),fill=(190,195,200))
                pen.text((x+w*scale+3,y+p*scale),str(p),fill='black',font=font)
            row['images'].append(dict(kind=kind,index=index,width=w,height=h,png=filename,
                rgba_sha256=hashlib.sha256(rgba).hexdigest(),uses=used.get((kind,index),[])))
        sheet.save(OUT/f"view{r['view']}-all-images.png")
        inventory.append(row)
    act, spr = parse_act(corpus.read(BODY+'.act')), Spr(corpus.read(BODY+'.spr'))
    body=[]
    for phase,base,count in [(0,32,6),(1,88,8),(2,80,8)]:
        for direction in range(8):
            sheet=Image.new('RGB',(400*4,430*2),(230,235,240))
            pen=ImageDraw.Draw(sheet)
            frames=act['actions'][base+direction].frames
            for f, frame in enumerate(frames[:count]):
                canvas=Image.new('RGBA',(100,100),(230,235,240,255))
                for l in frame.layers:
                    if l.sprite_index<0:continue
                    rgba,w,h=spr.get_rgba(l.sprite_index,l.sprite_type)
                    im=Image.frombytes('RGBA',(w,h),rgba)
                    assert not l.rotation and l.scale_x==l.scale_y==1
                    if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                    canvas.alpha_composite(im,(50+l.x-(w+1)//2,85+l.y-(h+1)//2))
                canvas.save(OUT/f'body-p{phase}-d{direction}-f{f}.png')
                x,y=(f%4)*400,(f//4)*430+25
                sheet.paste(canvas.resize((400,400),Image.Resampling.NEAREST),(x,y))
                pen.text((x+5,y-20),f'phase{phase} D{direction} F{f} origin(50,85)',fill='black',font=font)
                for p in range(0,100,10):
                    pen.line((x+p*4,y,x+p*4,y+400),fill=(180,200,205))
                    pen.line((x,y+p*4,x+400,y+p*4),fill=(180,200,205))
                    pen.text((x+p*4,y+380),str(p-50),fill='black',font=font)
                    pen.text((x+2,y+p*4),str(p-85),fill='black',font=font)
                body.append(dict(phase=phase,direction=direction,frame=f,
                    layers=[dict(index=l.sprite_index,kind=l.sprite_type,x=l.x,y=l.y,mirror=l.mirror) for l in frame.layers],
                    canvas_sha256=hashlib.sha256(canvas.tobytes()).hexdigest()))
            sheet.save(OUT/f'body-p{phase}-d{direction}.png')
    declared={r['stem'] for r in inventory}
    extra=sorted(k for k in corpus.keys if k.startswith('data/sprite/인간족/어세신/어세신_여_') and k.endswith('.spr') and k[:-4] not in declared)
    result=dict(schema='dual_weapon_pixel_inventory/v1',weapons=inventory,body=body,excluded_views=list(range(600,607)),
                other_family_sprites=extra,sources=corpus.sources,unreadable=corpus.unreadable)
    (OUT/'inventory.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    corpus.close()
    print(json.dumps(dict(views=len(inventory),images=sum(len(r['images']) for r in inventory),
                         body_cells=len(body),extra_family_sprites=len(extra))))

if __name__=='__main__':main()
