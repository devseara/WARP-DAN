"""Render final SPR/ACT action coverage with the original independent heads."""
import json
import math
from PIL import Image,ImageDraw
from audit_clan_wing_attachment import ROOT,load
from sprite_formats import read_spr,read_act,anchor
from bake_clan_body_frames import composite

OUT=ROOT/'Outputs/clan-body-skins/all-actions-v11'
BASE=ROOT/'Outputs/clan-body-skins/female-wings-v10'
GROUPS=['Idle','Walk','Sit','Pick up','Attack 1','Attack 2','Hit','Action 7','Death','Standby','Attack 3','Attack 4','Casting']


def render(images,act,heads,ha,ai,fi):
    canvas=Image.new('RGBA',(300,300));origin=(150,245)
    im,x,y=composite(images,act.actions[ai][fi])
    im=im.resize((im.width//2,im.height//2),Image.Resampling.NEAREST)
    canvas.alpha_composite(im,(origin[0]+x*2-im.width//2,origin[1]+y*2-im.height//2))
    f=act.actions[ai][fi];hf=ha.actions[ai][min(fi,len(ha.actions[ai])-1)]
    bx,by=anchor(f);hx,hy=anchor(hf)
    for l in hf.layers:
        if l.index<0:continue
        raw,w,h=heads.get_rgba(l.index,l.kind);im=Image.frombytes('RGBA',(w,h),raw)
        if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        im=im.resize((w*2,h*2),Image.Resampling.NEAREST)
        if l.angle:im=im.rotate(-l.angle,Image.Resampling.NEAREST,expand=True)
        canvas.alpha_composite(im,(origin[0]+(l.x+bx-hx)*2-im.width//2,origin[1]+(l.y+by-hy)*2-im.height//2))
    bbox=canvas.getbbox()
    assert bbox and bbox[0]>0 and bbox[1]>0 and bbox[2]<canvas.width and bbox[3]<canvas.height,(ai,fi,bbox)
    return canvas


def main():
    sets={};report=[]
    for sex,korean in [('male','남'),('female','여')]:
        _,_,_,heads,ha=load(sex)
        rel=f'data/sprite/clan_skins/1/인간족/몸통/{korean}/검사_{korean}'
        pairs=[]
        for root in [BASE,OUT]:
            pairs.append((read_spr((root/rel).with_suffix('.spr').read_bytes()),read_act((root/rel).with_suffix('.act').read_bytes())))
        sets[sex]=(*pairs,heads,ha)
        new,act=pairs[1]
        for ai,frames in enumerate(act.actions):
            atlas=Image.new('RGB',(300*len(frames),320),'#283746');pen=ImageDraw.Draw(atlas)
            for fi in range(len(frames)):
                tile=render(new,act,heads,ha,ai,fi);atlas.paste(tile,(300*fi,20),tile)
                pen.text((300*fi+8,6),f'{sex} A{ai} {GROUPS[ai//8]} F{fi}',fill='white')
            folder=OUT/f'review/{sex}';folder.mkdir(parents=True,exist_ok=True)
            atlas.save(folder/f'action-{ai:03}.png')
        report.append(dict(sex=sex,actions_rendered=104,frames_rendered=456,clipping=False))
    for g in range(2,13):
        frames=[];durations=[]
        for direction in range(8):
            ai=g*8+direction
            n=max(len(sets[s][1][1].actions[ai]) for s in sets)
            for repeat in range(2):
                for fi in range(n):
                    board=Image.new('RGB',(1200,340),'#283746');pen=ImageDraw.Draw(board)
                    for si,sex in enumerate(('male','female')):
                        before,after,heads,ha=sets[sex]
                        for ci,((images,act),label) in enumerate([(before,'Previous'),(after,'Revised')]):
                            f=min(fi,len(act.actions[ai])-1)
                            tile=render(images,act,heads,ha,ai,f);x=(si*2+ci)*300
                            board.paste(tile,(x,25),tile);pen.text((x+8,8),f'{sex.title()} / {label}',fill='white')
                    pen.text((8,324),f'{GROUPS[g]} | direction {direction} | frame {fi+1}',fill='white')
                    frames.append(board);durations.append(max(90,round(sets['male'][1][1].speeds[ai]*25)))
        frames[0].save(OUT/f'review/{g:02}-{GROUPS[g].lower().replace(" ","-")}.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=2)
    (OUT/'render-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report))


if __name__=='__main__':main()
