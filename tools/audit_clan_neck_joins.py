"""Read-only alpha/neck-join screen, with native and exported pixels kept separate.

The inferred neck point only locates a crop. It is not accepted anatomical truth.
Positive central gaps can demonstrate floating pixels; hair overlap, collar shape,
and pose alignment still require inspection of the native/custom layer drawings.
"""
import argparse
from functools import lru_cache
import json
import io
import hashlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from audit_clan_motion import WORK, ROOT, load, save, refs, GROUPS
from review_original_job_directions import native_context
from fix_archer_design_alignment import neck_point
from review_full_swordman_set import ORIGIN

ASSETS = ROOT / 'Assets/ClanBodySkins'
OUT = WORK / 'neck-joins'
FONT = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 13)


@lru_cache(maxsize=160)
def picture(url):
    path = (ASSETS / url.lstrip('/')).resolve()
    assert path.is_relative_to(ASSETS.resolve())
    raw = path.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == path.stem, ('Changed review pixels', path)
    return Image.open(io.BytesIO(raw)).convert('RGBA')


def crop_point(job, sex, ai, fi):
    _, _, act, heads, ha = native_context(job, sex)
    return neck_point(refs(), sex, act, heads, ha, ai, fi) + ORIGIN


def central_columns(body, head, point):
    b, h = np.asarray(body)[:, :, 3] >= 128, np.asarray(head)[:, :, 3] >= 128
    cx, cy = np.rint(point).astype(int)
    columns = []
    for x in range(cx - 8, cx + 9):
        # Local body top; halo, hands and sleeves outside this strip are excluded.
        by = np.flatnonzero(b[max(0, cy-28):min(640, cy+48), x]) + max(0, cy-28)
        hy = np.flatnonzero(h[:, x])
        if not len(by) or not len(hy):
            continue
        columns.append(dict(x=(x-ORIGIN[0])/4, head_bottom=(int(hy[-1])-ORIGIN[1])/4,
                            body_top=(int(by[0])-ORIGIN[1])/4,
                            signed_gap=(int(by[0])-int(hy[-1])-1)/4))
    return columns


def scan():
    dataset = load(WORK/'review-data.json')['jobs']
    old = load(WORK/'screening.json')['metrics']
    deltas = {(r['job'],r['sex'],r['action'],r['frame']):r['head_anchor_delta'] for r in old}
    rows=[]
    for job, sexes in dataset.items():
        for sex, item in sexes.items():
            for ai, action in enumerate(item['actions']):
                for fi, paths in enumerate(action['frames']):
                    nb, cb, nh, ch = map(picture, paths)
                    point = crop_point(job, sex, ai, fi)
                    delta = np.array(deltas[job,sex,ai,fi])
                    native = central_columns(nb, nh, point)
                    custom = central_columns(cb, ch, point+delta*4)
                    # Missing coverage at the original exposed neck is a screen:
                    # intentionally different collars can change this silhouette.
                    cx,cy=np.rint(point).astype(int)
                    box=(cx-12,cy-16,cx+13,cy+25)
                    nm=np.asarray(nb.crop(box))[:,:,3]>=128
                    hm=np.asarray(nh.crop(box))[:,:,3]>=128
                    cm=np.asarray(cb.crop(box))[:,:,3]>=128
                    visible=nm & ~hm
                    missing=visible & ~cm
                    ng=float(np.median([c['signed_gap'] for c in native])) if native else None
                    cg=float(np.median([c['signed_gap'] for c in custom])) if custom else None
                    rows.append(dict(job=job,sex=sex,action=ai,frame=fi,direction=ai%8,group=ai//8,
                        crop_center_4x=point.tolist(),head_anchor_delta=delta.tolist(),
                        native_columns=native,custom_columns=custom,native_median_gap=ng,
                        custom_median_gap=cg,extra_gap=cg-ng if ng is not None and cg is not None else None,
                        original_exposed_neck_pixels=int(visible.sum()),missing_native_neck_coverage=int(missing.sum())))
            r=[r for r in rows if (r['job'],r['sex'])==(job,sex)]
            print(json.dumps(dict(job=job,sex=sex,frames=len(r),
                positive_central_gap=sum((v['custom_median_gap'] or 0)>.5 for v in r),
                max_central_gap=max((v['custom_median_gap'] or 0) for v in r))),flush=True)
    save(OUT/'screen.json',dict(alpha_threshold=128,coordinate_unit='native game pixels; 4 output pixels per native pixel',
        status='geometric_screen_not_anatomical_certification',
        limitations=['Crop points are inferred and unreviewed; do not fit artwork to them without inspection.',
            'Signed column gaps are local silhouette distances, not neck lengths.',
            'Hair can overlap a misplaced collar; no positive gap does not establish correct attachment.',
            'Death and strongly leaning poses may not intersect the vertical neck strip.'],frames=rows))


def sheets(jobs):
    dataset=load(WORK/'review-data.json')['jobs'];metrics=load(OUT/'screen.json')['frames']
    for job in jobs or dataset:
        for sex,item in dataset[job].items():
            selected=[r for r in metrics if (r['job'],r['sex'])==(job,sex)]
            for group in range(13):
                # F0 plus the most separated central join in each action.
                board=Image.new('RGB',(8*228,4*156+42),'#283746');pen=ImageDraw.Draw(board)
                pen.text((8,7),f'{job} {sex} / {GROUPS[group]}: original | custom, F0 above; largest central-gap screen below',font=FONT,fill='white')
                for d in range(8):
                    ai=group*8+d
                    records=[r for r in selected if r['action']==ai]
                    worst=max(records,key=lambda r:r['custom_median_gap'] if r['custom_median_gap'] is not None else -1000)
                    for variant,fi in enumerate((0,worst['frame'])):
                        paths=item['actions'][ai]['frames'][fi];point=crop_point(job,sex,ai,fi)
                        box=tuple(np.rint(np.tile(point,2)+[-56,-85,56,43]).astype(int))
                        for kind in range(2):
                            im=picture(paths[kind]).copy();im.alpha_composite(picture(paths[kind+2]));im=im.crop(box)
                            x=d*228+kind*114;y=42+variant*300
                            board.paste(im,(x,y+21),im)
                            pen.text((x+2,y),f'A{ai} F{fi} '+('N' if kind==0 else 'C'),font=FONT,fill='white')
                            # Body alone shows the aperture instead of concealing it under hair.
                            lower=picture(paths[kind]).crop(box)
                            board.paste(lower,(x,y+151),lower)
                board.save(OUT/f'{job}-{sex}-g{group:02}.png')
            print('Neck sheets: '+job+' '+sex,flush=True)


def overviews(jobs):
    dataset=load(WORK/'review-data.json')['jobs']
    for job in jobs or dataset:
        for sex,item in dataset[job].items():
            board=Image.new('RGB',(8*228,13*156+25),'#283746');pen=ImageDraw.Draw(board)
            pen.text((5,4),f'{job} {sex}: every action / F0 / native then custom at identical world positions',font=FONT,fill='white')
            for ai,action in enumerate(item['actions']):
                point=crop_point(job,sex,ai,0)
                box=tuple(np.rint(np.tile(point,2)+[-56,-85,56,43]).astype(int))
                for kind in range(2):
                    paths=action['frames'][0];im=picture(paths[kind]).copy();im.alpha_composite(picture(paths[kind+2]));im=im.crop(box)
                    x=ai%8*228+kind*114;y=25+ai//8*156
                    board.paste(im,(x,y+19),im);pen.text((x+2,y),f'A{ai} '+('native' if kind==0 else 'custom'),font=FONT,fill='white')
            board.save(OUT/f'{job}-{sex}-all-actions.png')
        print('All-action overviews: '+job,flush=True)


def detail(job,sex,ai,fi):
    paths=load(WORK/'review-data.json')['jobs'][job][sex]['actions'][ai]['frames'][fi]
    point=crop_point(job,sex,ai,fi);cx,cy=np.rint(point).astype(int)
    box=(cx-36,cy-36,cx+36,cy+36)
    board=Image.new('RGB',(4*300,366),'#283746');pen=ImageDraw.Draw(board)
    pen.text((8,8),f'{job} {sex} A{ai} F{fi} / 1 grid cell = 1 output pixel = 0.25 game pixel / shared world crop {box}',font=FONT,fill='white')
    for k,(label,b,h) in enumerate([('Original joined',0,2),('Custom joined',1,3),('Original body',0,None),('Custom body',1,None)]):
        im=picture(paths[b]).copy()
        if h is not None:im.alpha_composite(picture(paths[h]))
        im=im.crop(box).resize((288,288),Image.Resampling.NEAREST)
        board.paste(im,(k*300,55),im);pen.text((k*300+4,32),label,font=FONT,fill='white')
        for t in range(0,289,4):
            color='#536775' if t%16==0 else '#344450'
            # Fine grid is subtle; underlying alpha/RGBA remains available in browser.
            pen.line((k*300+t,55,k*300+t,343),fill=color)
            pen.line((k*300,55+t,k*300+288,55+t),fill=color)
    path=OUT/f'detail-{job}-{sex}-a{ai}-f{fi}.png';board.save(path);return path


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['scan','sheets','overviews','detail']);p.add_argument('--job',action='append');p.add_argument('--sex');p.add_argument('--action',type=int);p.add_argument('--frame',type=int,default=0);a=p.parse_args();OUT.mkdir(exist_ok=True)
    if a.stage=='scan':scan()
    elif a.stage=='sheets':sheets(a.job)
    elif a.stage=='overviews':overviews(a.job)
    else:print(detail(a.job[0],a.sex,a.action,a.frame))
