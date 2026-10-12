"""Render synchronized before/after movement previews from final SPR/ACT files."""
from pathlib import Path
import json
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from audit_clan_wing_attachment import ROOT, OUT, load
from sprite_formats import read_spr, read_act, anchor
from bake_clan_body_frames import composite


def render(images, act, heads, ha, ai, fi, zoom=2):
    canvas=Image.new('RGBA',(220,280))
    origin=(110,230)
    im,x,y=composite(images,act.actions[ai][fi])
    im=im.resize((im.width//2,im.height//2),Image.Resampling.NEAREST)
    canvas.alpha_composite(im,(origin[0]+x*zoom-im.width//2,origin[1]+y*zoom-im.height//2))
    frame=act.actions[ai][fi]
    hf=ha.actions[ai][min(fi,len(ha.actions[ai])-1)]
    bx,by=anchor(frame);hx,hy=anchor(hf)
    for l in hf.layers:
        if l.index<0:continue
        raw,w,h=heads.get_rgba(l.index,l.kind)
        im=Image.frombytes('RGBA',(w,h),raw)
        if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        im=im.resize((w*zoom,h*zoom),Image.Resampling.NEAREST)
        if l.angle:im=im.rotate(-l.angle,Image.Resampling.NEAREST,expand=True)
        canvas.alpha_composite(im,(origin[0]+(l.x+bx-hx)*zoom-im.width//2,origin[1]+(l.y+by-hy)*zoom-im.height//2))
    return canvas


def main():
    sets={}
    for sex,korean in [('male','남'),('female','여')]:
        images,act,native,heads,ha=load(sex)
        stem=OUT/f'data/sprite/clan_skins/1/인간족/몸통/{korean}/검사_{korean}'
        sets[sex]=(images,act,read_spr(stem.with_suffix('.spr').read_bytes()),read_act(stem.with_suffix('.act').read_bytes()),heads,ha)
    samples=[];durations=[]
    for direction in range(8):
        ai=8+direction
        for repeat in range(2):
            for fi in range(8):
                board=Image.new('RGB',(880,335),'#283746');pen=ImageDraw.Draw(board)
                for si,sex in enumerate(('male','female')):
                    before,ba,after,aa,heads,ha=sets[sex]
                    for ci,(images,act,label) in enumerate([(before,ba,'Previous'),(after,aa,'Corrected')]):
                        tile=render(images,act,heads,ha,ai,fi)
                        x=(si*2+ci)*220
                        board.paste(tile,(x,40),tile)
                        pen.text((x+12,12),f'{sex.title()} / {label}',fill='white')
                pen.text((12,318),f'Walk direction {direction} | frame {fi+1}/8 | native head preview; headgear omitted',fill='white')
                samples.append(board)
                durations.append(round(sets['male'][1].speeds[ai]*25))
                if direction==2 and fi==0 and repeat==0:board.save(OUT/'side-attachment-before-after.png')
    samples[0].save(OUT/'walk-attachment-comparison.gif',save_all=True,append_images=samples[1:],duration=durations,loop=0,disposal=2)
    print(OUT/'walk-attachment-comparison.gif')


if __name__=='__main__':
    main()
