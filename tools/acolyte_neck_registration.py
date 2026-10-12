"""Measure Acolyte neck caps and painted collar openings in world coordinates."""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from package_clan_skin_assets import ROOT
from sprite_formats import read_spr, read_act, anchor
from review_original_job_directions import native_context
from review_full_swordman_set import body, head, ORIGIN
from refine_clan_combat_necks import components

BASE = ROOT / 'Assets/ClanBodySkins/Acolyte/complete-v1'
WORK = BASE.parent / 'registration-v2'


def native_neck_target(sex, ai, fi):
    refs=json.loads((WORK/'head-neck-reference.json').read_text(encoding='utf8'))
    _,_,act,heads,ha=native_context('acolyte',sex)
    frame=act.actions[ai][fi]
    hf=ha.actions[ai][min(fi,len(ha.actions[ai])-1)]
    layer=next(l for l in hf.layers if l.index>=0)
    raw=heads.images[layer.index]
    ref=next(r for r in refs if r['sex']==sex and r['head_sprite']==layer.index)
    point=np.array(ref['point'])
    if layer.mirror:point[0]=raw.width*4-point[0]
    top=(np.array([layer.x,layer.y])+np.array(anchor(frame))-np.array(anchor(hf)))*4-np.array([raw.width,raw.height])*2
    return point+top


def native_cap(spr, act, sex, ai, fi):
    frame = act.actions[ai][fi]
    layer = frame.layers[0]
    raw = spr.images[layer.index]
    indices = np.frombuffer(raw.pixels, np.uint8).reshape(raw.height, raw.width)
    ramp = (indices >= 128) & (indices <= 135)
    top = np.array([layer.x - raw.width // 2, layer.y - raw.height // 2]) * 4
    heads = np.asarray(head(sex, ai, fi, job='acolyte'))[:, :, 3] > 0
    candidates = []
    for group in components(ramp):
        if len(group) < 1:
            continue
        y, x = group[:, 0], group[:, 1]
        cx = raw.width - (x + .5) if layer.mirror else x + .5
        wx, wy = top[0] + cx * 4, top[1] + (y + .5) * 4
        ix = np.clip(np.rint(wx + ORIGIN[0]).astype(int), 0, 639)
        iy = np.clip(np.rint(wy + ORIGIN[1]).astype(int), 0, 639)
        overlap = float(heads[iy, ix].mean())
        width, height = np.ptp(x) + 1, np.ptp(y) + 1
        flat = min(3., width / height) if ai // 8 != 8 else max(width / height, height / width)
        values=indices[y,x]
        cap_tone=float(max(np.count_nonzero(values==132),np.count_nonzero(values==133))/len(group))
        score = overlap * 6 + cap_tone * 12 + min(flat,3.)*.5
        if ai//8 in (0,1,2):
            score = -float(y.mean())*4 + cap_tone*8 + overlap*2
        candidates.append(dict(point=[float(wx.mean()), float(wy.mean())], score=score,
                               overlap=overlap, bounds=[int(x.min()), int(y.min()), int(x.max()+1), int(y.max()+1)],
                               pixels=len(group)))
    return sorted(candidates, key=lambda c: c['score'], reverse=True)


def ring_collars(image,target,simple_pose=False):
    full=np.asarray(image);origin=np.array(ORIGIN)
    c=np.array(target)+origin
    left=max(0,int(c[0]-180));right=min(640,int(c[0]+180))
    upper=max(0,int(c[1]-170));lower=min(640,int(c[1]+120))
    a=full[upper:lower,left:right];rgb=a[:,:,:3].astype(float)
    lum=rgb@np.array([.2126,.7152,.0722]);alpha=(a[:,:,3]>128).astype(float)
    il=np.pad(lum,((1,0),(1,0))).cumsum(0).cumsum(1)
    ia=np.pad(alpha,((1,0),(1,0))).cumsum(0).cumsum(1)
    height,width=alpha.shape
    def mean_box(integral,hx,hy):
        x=np.arange(width);y=np.arange(height)
        lo=np.clip(x-hx,0,width);hi=np.clip(x+hx+1,0,width)
        top=np.clip(y-hy,0,height);bottom=np.clip(y+hy+1,0,height)
        return (integral[bottom[:,None],hi]-integral[top[:,None],hi]-integral[bottom[:,None],lo]+integral[top[:,None],lo])/((2*hx+1)*(2*hy+1))
    yy,xx=np.indices(alpha.shape);wx=xx+.5+left-ORIGIN[0];wy=yy+.5+upper-ORIGIN[1]
    distance=np.hypot(wx-target[0],wy-target[1]);best=np.full(alpha.shape,-1e6);sizes=np.zeros((*alpha.shape,2),int)
    silhouette_top=float(np.flatnonzero(full[:,:,3].any(axis=1))[0])-ORIGIN[1]
    for hx in (4,6,8,10,13,16):
        for hy in (2,3,4,6,8):
            ih=mean_box(il,hx,hy);oh=mean_box(il,hx+4,hy+3);opacity=mean_box(ia,hx,hy);outer_opacity=mean_box(ia,hx+4,hy+3)
            area=(2*hx+1)*(2*hy+1);outer=(2*hx+9)*(2*hy+7)
            rim_pixels=outer_opacity*outer-opacity*area
            rim=(oh*outer-ih*area)/np.maximum(rim_pixels,1)
            score=rim-ih+np.maximum(0,65-ih)*.5-distance*.13+min(2*hx+1,33)
            if simple_pose:score-=(wy-silhouette_top)*.25
            valid=(opacity>.96)&(rim_pixels>(outer-area)*.22)&(ih<90)&(rim>100)&(distance<190)
            score[~valid]=-1e6;select=score>best;best[select]=score[select];sizes[select]=[hx,hy]
    result=[]
    for _ in range(12):
        y,x=np.unravel_index(np.argmax(best),best.shape);value=best[y,x]
        if value<-1e5:break
        hx,hy=sizes[y,x];result.append(dict(point=[x+.5+left-ORIGIN[0],y+.5+upper-ORIGIN[1]],score=float(value),bounds=[int(x+left-hx),int(y+upper-hy),int(x+left+hx+1),int(y+upper+hy+1)],method='Dark aperture enclosed by a bright opaque rim'))
        best[max(0,y-8):y+9,max(0,x-8):x+9]=-1e6
    return result


def audit():
    WORK.mkdir(parents=True,exist_ok=True)
    plan=json.loads((BASE/'art-plan.json').read_text(encoding='utf8'))
    records=[]
    for sex in ('male','female'):
        _,spr,act,_,_=native_context('acolyte',sex)
        stem=BASE/'assets'/f'{sex}-angel-acolyte-v1'
        pair=read_spr(stem.with_suffix('.spr').read_bytes()),read_act(stem.with_suffix('.act').read_bytes())
        poses=[(batch,p) for batch in plan['batches'] if batch['sex']==sex for p in batch['poses']]
        for batch,pose in poses:
            ai,fi=pose['representative_action'],pose['representative_frame']
            native=native_cap(spr,act,sex,ai,fi)
            native_missing=not native
            if native_missing:
                layer=act.actions[ai][fi].layers[0];raw=spr.images[layer.index]
                native=[dict(point=[layer.x*4,(layer.y-raw.height//2+4)*4],score=-99,overlap=0,bounds=[],pixels=0)]
            target=native_neck_target(sex,ai,fi).tolist()
            image=body(sex,ai,fi,pair,job='acolyte')
            collars=ring_collars(image,target,ai//8 in (0,1,2,4))
            records.append(dict(sex=sex,sprite=pose['sprite'],action=ai,frame=fi,batch=batch['name'],
                                native_candidates=native,native_missing=native_missing,collar_candidates=collars,
                                native_point=target,native_palette_point=native[0]['point'],collar_point=collars[0]['point'] if collars else None))
        selected=[r for r in records if r['sex']==sex]
        font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
        for page in range((len(selected)+19)//20):
            board=Image.new('RGB',(1200,950),'#283746');draw=ImageDraw.Draw(board)
            for cell,r in enumerate(selected[page*20:(page+1)*20]):
                x=cell%4*300;y=cell//4*190
                ai,fi=r['action'],r['frame'];center=np.array(r['native_point'])+ORIGIN
                box=(round(center[0]-100),round(center[1]-105),round(center[0]+100),round(center[1]+105))
                for col,custom in enumerate((False,True)):
                    im=body(sex,ai,fi,pair if custom else None,job='acolyte')
                    pen=ImageDraw.Draw(im);point=r['collar_point'] if custom else r['native_point']
                    if point:
                        px,py=np.array(point)+ORIGIN
                        pen.ellipse((px-3,py-3,px+3,py+3),fill=(255,0,255,255) if custom else (0,255,255,255))
                    im=im.crop(box).resize((140,147),Image.Resampling.NEAREST)
                    board.paste(im,(x+col*150,y+27),im)
                draw.text((x+3,y+3),f"{r['sprite']:03} A{ai} F{fi} {r['batch']}",font=font,fill='white')
            board.save(WORK/f'{sex}-landmarks-{page}.png')
    (WORK/'landmark-proposals.json').write_text(json.dumps(records,indent=2),encoding='utf8')
    print(json.dumps(dict(records=len(records),missing_native=[(r['sex'],r['sprite']) for r in records if r['native_missing']],missing_collars=[(r['sex'],r['sprite']) for r in records if r['collar_point'] is None])))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('audit',))
    args=parser.parse_args()
    audit()
