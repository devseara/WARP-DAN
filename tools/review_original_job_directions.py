"""Extract transparent directional art and review it with unchanged native heads.

This is a body-scale/turnaround proof, not a substitute for native pose fitting.
No SPR/ACT or installed client files are produced by this tool.
"""
import argparse
import hashlib
import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from audit_first_job_sprite_sources import OUT as SOURCES, JOBS
from audit_clan_wing_attachment import load
from prepare_original_job_art import OUT
from render_native_wing_anatomy import rgba
from sprite_formats import read_act, anchor
from spr_reader import Spr
from original_job_proportions import reference_scale, register_master

VIEW_MAP = (0, 1, 2, 3, 4, 3, 2, 1)
VIEW_NAMES = ('front', 'front-left', 'left', 'rear-left', 'rear')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(job):
    path = OUT/'directional'/job/'transparent-v1.png'
    sheet = Image.open(path)
    if sheet.mode != 'RGBA' or sheet.getchannel('A').getextrema()[0] != 0:
        raise ValueError(f'{job}: an opaque sheet is not a usable sprite master')
    a = np.asarray(sheet)[:, :, 3]
    assert np.count_nonzero(a == 0) > a.size*.15
    records = []
    for row, sex in enumerate(('male', 'female')):
        y0,y1 = round(row*sheet.height/2),round((row+1)*sheet.height/2)
        occupied = (a[y0:y1] > 32).sum(axis=0)
        boundaries = [0]
        for column in range(1,5):
            center=round(column*sheet.width/5);radius=round(sheet.width*.06)
            gaps=np.flatnonzero(occupied[center-radius:center+radius]==0)+center-radius
            if len(gaps)<3:
                raise ValueError(f'{job} {sex}: no clear gutter before direction {column}')
            boundaries.append(int(gaps[len(gaps)//2]))
        boundaries.append(sheet.width)
        for direction in range(5):
            x0,x1=boundaries[direction:direction+2]
            cell=sheet.crop((x0,y0,x1,y1))
            b=cell.getchannel('A').point(lambda p:255 if p>32 else 0).getbbox()
            assert b
            box=(max(0,b[0]-2),max(0,b[1]-2),min(cell.width,b[2]+2),min(cell.height,b[3]+2))
            im=cell.crop(box)
            assert np.count_nonzero(np.asarray(im)[:,:,3]>32)==np.count_nonzero(np.asarray(cell)[:,:,3]>32)
            source_box=(x0+box[0],y0+box[1],x0+box[2],y0+box[3])
            assert im.tobytes()==sheet.crop(source_box).tobytes()
            target=path.parent/'masters'/sex/f'view-{direction}.png'
            target.parent.mkdir(parents=True,exist_ok=True);im.save(target)
            records.append(dict(job=job,sex=sex,direction=direction,view=VIEW_NAMES[direction],
                source_box=source_box,path=str(target.relative_to(OUT)),sha256=sha(target),
                source_rgba_preserved=True))
    return sheet,records


def native_head(heads,ha,frame,direction):
    hf=ha.actions[direction][0]
    bx,by=anchor(frame);hx,hy=anchor(hf)
    l=next(l for l in hf.layers if l.index>=0)
    im=rgba(heads,l.index,l.kind)
    if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    assert l.angle==0
    x=l.x+bx-hx-im.width//2;y=l.y+by-hy-im.height//2
    return im,x,y


@lru_cache(maxsize=12)
def native_context(job,sex):
    durable=Path(__file__).resolve().parents[1]/'Assets/ClanBodySkins'/job.title()/'native'/sex
    src=durable if durable.exists() else SOURCES/'source'/job/sex
    spr=Spr((src/'body.spr').read_bytes());act=read_act((src/'body.act').read_bytes())
    if src==durable:
        heads=Spr((src/'head.spr').read_bytes());ha=read_act((src/'head.act').read_bytes())
    else:
        _,_,_,heads,ha=load(sex)
    return src,spr,act,heads,ha


@lru_cache(maxsize=12)
def front_calibration(job,sex,master_path):
    _,spr,act,heads,ha=native_context(job,sex)
    frame=act.actions[0][0];layer=frame.layers[0]
    native=rgba(spr,layer.index,layer.kind);bounds=native.getbbox()
    top=layer.y-native.height//2+bounds[1]
    foot=layer.y-native.height//2+bounds[3]
    head,hx,hy=native_head(heads,ha,frame,0)
    middle=head.width//2
    yy=np.where(np.asarray(head)[:,max(0,middle-2):middle+3,3]>64)[0]
    top=min(top,hy+int(yy.max())+1-2)
    with Image.open(master_path) as image:
        scale,proof=reference_scale(image.convert('RGBA'),top,foot)
    proof['source_front_master_sha256']=sha(Path(master_path))
    return scale,proof


def fitted_tile(job,sex,direction,records,upper_body=True):
    src,spr,act,heads,ha=native_context(job,sex)
    frame=act.actions[direction][0];l=next(l for l in frame.layers if l.index>=0)
    raw=rgba(spr,l.index,l.kind)
    if l.mirror:raw=raw.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    nx,ny=l.x-raw.width//2,l.y-raw.height//2
    b=raw.getbbox();head,hx,hy=native_head(heads,ha,frame,direction)
    record=next(r for r in records if r['sex']==sex and r['direction']==VIEW_MAP[direction])
    front=next(r for r in records if r['sex']==sex and r['direction']==0)
    art=Image.open(OUT/record['path']).convert('RGBA')
    scale,calibration=front_calibration(job,sex,str(OUT/front['path']))
    center=nx+(b[0]+b[2])/2
    if direction in (0,1,2,6,7):center=hx+head.width/2
    fitted,left4,top4,registration=register_master(art,scale,center,ny+b[3],mirror=direction>=5,
        upper_body=sex if upper_body and job=='swordman' else None)
    canvas=Image.new('RGBA',(600,600));origin=(300,470)
    canvas.alpha_composite(fitted,(origin[0]+left4,origin[1]+top4))
    h=head.resize((head.width*4,head.height*4),Image.Resampling.NEAREST)
    canvas.alpha_composite(h,(origin[0]+hx*4,origin[1]+hy*4))
    bbox=canvas.getbbox();assert bbox and min(bbox[:2])>0 and bbox[2]<600 and bbox[3]<600
    native=Image.new('RGBA',(600,600))
    native.alpha_composite(raw.resize((raw.width*4,raw.height*4),Image.Resampling.NEAREST),(origin[0]+nx*4,origin[1]+ny*4))
    native.alpha_composite(h,(origin[0]+hx*4,origin[1]+hy*4))
    proof=dict(direction=direction,master=VIEW_MAP[direction],mirror=direction>=5,
        native_head_anchor=anchor(frame),native_body_sha256=sha(src/'body.spr'),
        native_act_sha256=sha(src/'body.act'),head_coordinates_unchanged=True,
        head_top_left_4x=[hx*4,hy*4],calibration=calibration,**registration,
        clipping=False,pose_fit_status='Uniform directional proportions; animation pose registration pending')
    return canvas,native,proof


def review(job):
    sheet,records=extract(job)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',12)
    folder=OUT/'directional'/job
    board=Image.new('RGB',(1600,690),'#283746');p=ImageDraw.Draw(board)
    p.text((10,8),f'{job.title()} / '+('9% fuller upper armor / native heads' if job=='swordman' else 'consistent directional proportions / native heads'),font=font,fill='white')
    comparisons=[];turns=[];checks=[]
    for row,sex in enumerate(('male','female')):
        compare=Image.new('RGB',(1500,350),'#283746');cp=ImageDraw.Draw(compare)
        for d in range(8):
            tile,native,proof=fitted_tile(job,sex,d,records);checks.append(dict(sex=sex,**proof))
            x=d*200;y=35+row*325
            thumb=tile.resize((300,300),Image.Resampling.NEAREST).crop((50,0,250,300))
            board.paste(thumb,(x,y),thumb);p.text((x+8,y+295),f'{sex} / direction {d}',font=small,fill='white')
            if d<5:
                for n,im in enumerate((native,tile)):
                    preview=im.resize((300,300),Image.Resampling.NEAREST).crop((75,0,225,300))
                    compare.paste(preview,(d*300+n*150,25),preview)
                    cp.text((d*300+n*150+8,5),('Native' if n==0 else 'New')+f' / {d}',font=small,fill='white')
        compare.save(folder/f'{sex}-native-comparison.png')
    board.save(folder/'eight-direction-study.png')
    for d in range(8):
        panel=Image.new('RGB',(600,350),'#283746');p=ImageDraw.Draw(panel)
        for col,sex in enumerate(('male','female')):
            tile,_,_=fitted_tile(job,sex,d,records)
            tile=tile.resize((300,300),Image.Resampling.NEAREST)
            panel.paste(tile,(col*300,25),tile);p.text((col*300+8,6),f'{job.title()} / {sex} / {d}',font=font,fill='white')
        p.text((8,326),'Shared uniform body scale; native head coordinates',font=small,fill='#cbd7e0')
        turns.append(panel)
    turns[0].save(folder/'turnaround-study.gif',save_all=True,append_images=turns[1:],duration=550,loop=0,disposal=2)
    report=dict(job=job,status='Uniform directional proportions corrected; visual review pending; animation fitting pending',
        proportion_model='One equal-axis affine scale per job and sex, calibrated from the front view',
        upper_body_profile='9% chest, shoulders and upper arms; taper above belt' if job=='swordman' else None,
        source_file='transparent-v1.png',source_sha256=sha(folder/'transparent-v1.png'),
        actual_alpha=True,alpha_range=sheet.getchannel('A').getextrema(),masters=records,
        direction_checks=checks,animation_frames_created=0,runtime_assets_created=False)
    (folder/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',choices=list(JOBS))
    args=parser.parse_args();jobs=[args.job] if args.job else [j for j in JOBS if j!='swordman']
    reports=[review(j) for j in jobs]
    plan_path=OUT/'design-plan.json';plan=json.loads(plan_path.read_text())
    for report in reports:plan['directional_status'][report['job']]=report['status']
    plan_path.write_text(json.dumps(plan,indent=2),encoding='utf8')
    print(json.dumps([dict(job=r['job'],masters=len(r['masters']),directions=len(r['direction_checks']),
        alpha=True,clipping=False,animation_frames=0) for r in reports]))


if __name__=='__main__':main()
