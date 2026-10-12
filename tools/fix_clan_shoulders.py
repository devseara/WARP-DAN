"""Coherent diagonal walking shoulder surfaces, preserving native registration.

Reuse the existing F0 garment surface; do not generate a different shoulder
shape per frame. Native neck translation drives the collar-attached surface; the lower arms
retain their existing per-frame artwork. A minimum-error join inside the sleeve/garment overlap meets
the existing animated arms without moving the hands or lower body.
"""
import argparse
import copy
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from correct_clan_neck_registration import ROOT, WORK as SOURCE, original_neck, load, save, sha
from review_full_swordman_set import body, head, ORIGIN
from review_original_job_directions import native_context
from sprite_formats import read_spr, read_act, write_spr, write_act, Layer
from preview_clan_reference_revision import bake
from render_native_wing_anatomy import rgba
from spr_reader import Spr

WORK=ROOT/'Assets/ClanBodySkins/shoulder-motion-v2'
FONT=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)
DIRECTIONS=(1,3,5,7)
JOBS=('acolyte','archer')
REVISION='shoulder-v2'
SOURCE_MANIFEST=None


def source_pair(job,sex):
    if SOURCE_MANIFEST:
        document=load(SOURCE_MANIFEST);pins=document.get('files',document.get('resources'))
        stem=(ROOT/next(r['source'] for r in pins if r['job']==job and r['sex']==sex)).with_suffix('')
    else:
        stem=SOURCE/job/'assets'/f'{sex}-angel-{job}-neck-v1'
        pins=load(ROOT/'Inputs/ClanBodySkins/records/clan-neck-motion-correction.json')['files']
    for ext in ('.spr','.act'):
        p=stem.with_suffix(ext);expected=next(r['sha256'] for r in pins if r['job']==job and r['sex']==sex and Path(r['source']).suffix==ext)
        assert sha(p.read_bytes())==expected
    return read_spr(stem.with_suffix('.spr').read_bytes()),read_act(stem.with_suffix('.act').read_bytes())


def surface(job,sex,ai,fi,pair):
    """One rigid-volume top surface with native shoulder articulation and a seam."""
    current=body(sex,ai,fi,pair,job=job)
    if fi==0:return current,dict(reference_frame=True)
    reference=body(sex,ai,0,pair,job=job)
    origin=np.rint(original_neck(job,sex,ai,0)[0]).astype(int)
    target=np.rint(original_neck(job,sex,ai,fi)[0]).astype(int)
    yy,xx=np.indices((640,640))
    # Mantle and pauldrons are one collar-attached garment surface. Its
    # silhouette and volume remain rigid while native neck translation moves
    # it with the torso. Articulation remains in each frame's arms below it.
    sx=xx-target[0]+origin[0];sy=yy-target[1]+origin[1]
    valid=(sx>=0)&(sx<640)&(sy>=0)&(sy<640)
    donor=np.zeros((640,640,4),np.uint8);src=np.asarray(reference)
    donor[valid]=src[sy[valid],sx[valid]]
    # Profiles expose a bent upper sleeve immediately under the pauldron.
    # Keep their overlap higher so the fixed surface cannot cut across an elbow.
    profile=job=='archer' and ai%8 in (2,6)
    existing=np.asarray(current);start=target[1]+(62 if job=='acolyte' else 42 if profile else 50)
    stop=target[1]+(88 if job=='acolyte' else 60 if profile else 80)
    # The seam is a connected left-to-right path within an authored overlap
    # band below the shoulder cap. Above it: one coherent surface. Below it:
    # the actual frame's moving forearms, hands and lower costume.
    a=donor[start:stop].astype(float)/255;b=existing[start:stop].astype(float)/255
    pa=a[:,:,:3]*a[:,:,3:];pb=b[:,:,:3]*b[:,:,3:]
    cost=np.sum(abs(pa-pb),axis=2)+4*abs(a[:,:,3]-b[:,:,3])
    # Prefer the middle of a matching overlap over its top/bottom edge.
    cost+=.003*abs(np.arange(stop-start)[:,None]-(stop-start-1)/2)
    scores=cost[:,0].copy();parents=np.zeros(cost.shape,np.int16)
    for x in range(1,640):
        choices=np.stack([np.r_[np.inf,scores[:-1]]+.04,scores,np.r_[scores[1:],np.inf]+.04])
        best=choices.argmin(axis=0);parents[:,x]=np.arange(stop-start)+best-1
        scores=cost[:,x]+choices[best,np.arange(stop-start)]
    seam=np.empty(640,np.int16);seam[-1]=scores.argmin()
    for x in range(639,0,-1):seam[x-1]=parents[seam[x],x]
    seam+=start
    replace=yy<seam[None,:]
    result=existing.copy();result[replace]=donor[replace]
    assert np.array_equal(result[stop:],existing[stop:])
    return Image.fromarray(result),dict(reference_frame=0,surface_volume_rigid=True,
        neck_translation_4x=(target-origin).tolist(),join_y_range=[int(seam.min()),int(seam.max())],
        fixed_from_y=int(stop),lower_pixels_identical=True,seam=seam.tolist())


def prototype():
    for job in JOBS:
        for sex in ('male','female'):
            pair=source_pair(job,sex)
            for direction in DIRECTIONS:
                ai=8+direction;records=[]
                sheet=Image.new('RGB',(8*180,3*156),'#283746');pen=ImageDraw.Draw(sheet)
                for fi in range(8):
                    new,proof=surface(job,sex,ai,fi,pair);records.append(proof)
                    n=np.rint(original_neck(job,sex,ai,fi)[0]).astype(int)
                    box=tuple(np.tile(n,2)+[-86,-28,86,104])
                    for row,im in enumerate((body(sex,ai,fi,job=job),body(sex,ai,fi,pair,job=job),new)):
                        c=im.crop(box);sheet.paste(c,(fi*180+4,row*156+22),c)
                        pen.text((fi*180+3,row*156+3),f'{["Native","Before","Fixed"][row]} F{fi}',fill='white',font=FONT)
                sheet.save(WORK/f'{job}-{sex}-d{direction}-detail.png')
                save(WORK/f'{job}-{sex}-d{direction}-fit.json',records)
            print(job,sex,'prototype rendered',flush=True)


def build():
    files=[];all_checks=[]
    for job in JOBS:
        for sex in ('male','female'):
            old=source_pair(job,sex);act=copy.deepcopy(old[1]);images=list(old[0]);checks=[]
            _,_,native,_,_=native_context(job,sex)
            seen={(im.size,sha(im.tobytes())):i for i,im in enumerate(images)}
            for ai,frames in enumerate(act.actions):
                for fi,f in enumerate(frames):
                    before=body(sex,ai,fi,old,job=job);im=before;proof={}
                    if ai//8==1 and ai%8 in DIRECTIONS:
                        im,proof=surface(job,sex,ai,fi,old)
                        box=im.getbbox();assert box and min(box[:2])>0 and max(box[2:])<640
                        sprite,x,y=bake([(im.crop(box),box[0]-ORIGIN[0],box[1]-ORIGIN[1])]);key=(sprite.size,sha(sprite.tobytes()))
                        if key not in seen:seen[key]=len(images);images.append(sprite)
                        f.layers=[Layer(x,y,seen[key],sx=.25,sy=.25)]
                    proof.pop('seam',None)
                    checks.append(dict(action=ai,frame=fi,changed_pixels=int(np.any(np.asarray(before)!=np.asarray(im),axis=2).sum()),**proof))
                    assert body(sex,ai,fi,(images,act),job=job).tobytes()==im.tobytes()
                    assert head(sex,ai,fi,job=job,pair=(images,act)).tobytes()==head(sex,ai,fi,job=job).tobytes()
                    assert (f.anchors,f.ranges,f.sound)==(native.actions[ai][fi].anchors,native.actions[ai][fi].ranges,native.actions[ai][fi].sound)
            assert len(act.actions)==104 and sum(map(len,act.actions))==456 and act.speeds==native.speeds
            dest=WORK/job/'assets';dest.mkdir(parents=True,exist_ok=True)
            sb,ab=write_spr(images),write_act(act)
            decoded=read_spr(sb);independent=Spr(sb)
            for i,im in enumerate(decoded):assert im.tobytes()==rgba(independent,i,1).tobytes()
            reopened=decoded,read_act(ab)
            for r in checks:
                ai,fi=r['action'],r['frame']
                im=surface(job,sex,ai,fi,old)[0] if ai//8==1 and ai%8 in DIRECTIONS else body(sex,ai,fi,old,job=job)
                assert body(sex,ai,fi,reopened,job=job).tobytes()==im.tobytes()
            for ext,raw in (('.spr',sb),('.act',ab)):
                p=dest/f'{sex}-angel-{job}-{REVISION}{ext}';p.write_bytes(raw)
                files.append(dict(job=job,sex=sex,source=p.relative_to(ROOT).as_posix(),sha256=sha(raw)))
            save(WORK/job/f'{sex}-verification.json',dict(status='passed',actions=104,frame_uses=456,independent_decode=True,native_heads_identical=True,unchanged_actions_render_identical=True,checks=checks))
            all_checks+=checks
            print(job,sex,'exported; changed',sum(bool(r['changed_pixels']) for r in checks),flush=True)
    save(WORK/'build-summary.json',dict(status='passed',files=files,frame_uses=len(all_checks),changed_frame_uses=sum(bool(r['changed_pixels']) for r in all_checks),tool_sha256=sha(Path(__file__).read_bytes())))


def verify_surfaces():
    rows=[]
    for job in JOBS:
        for sex in ('male','female'):
            stem=WORK/job/'assets'/f'{sex}-angel-{job}-{REVISION}'
            pair=read_spr(stem.with_suffix('.spr').read_bytes()),read_act(stem.with_suffix('.act').read_bytes())
            old=source_pair(job,sex)
            for direction in DIRECTIONS:
                ai=direction+8;point=np.rint(original_neck(job,sex,ai,0)[0]).astype(int)
                profile=job=='archer' and direction in (2,6)
                bottom=62 if job=='acolyte' else 42 if profile else 50
                fixed=88 if job=='acolyte' else 60 if profile else 80
                ref=body(sex,ai,0,pair,job=job).crop(tuple(np.tile(point,2)+[-86,-28,86,bottom]))
                for fi in range(8):
                    point=np.rint(original_neck(job,sex,ai,fi)[0]).astype(int)
                    im=body(sex,ai,fi,pair,job=job);before=body(sex,ai,fi,old,job=job)
                    box=tuple(np.tile(point,2)+[-86,-28,86,bottom]);assert im.crop(box).tobytes()==ref.tobytes(),(job,sex,ai,fi,'shoulder surface changed')
                    cut=int(point[1]+fixed);assert im.crop((0,cut,640,640)).tobytes()==before.crop((0,cut,640,640)).tobytes()
                    rows.append(dict(job=job,sex=sex,direction=direction,frame=fi,shoulder_shape_identical_after_native_translation=True,
                        rigid_region=[int(v) for v in box],lower_region_identical=True,fixed_from_y=cut))
    save(WORK/'surface-verification.json',dict(status='passed',frame_uses=len(rows),checks=rows))
    print('Verified',len(rows),'walking surfaces and preserved lower regions.',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('stage',choices=['prototype','build','verify'],default='prototype',nargs='?');parser.add_argument('--job',action='append');parser.add_argument('--direction',type=int,action='append');parser.add_argument('--work',type=Path);parser.add_argument('--revision');parser.add_argument('--sources',type=Path);args=parser.parse_args()
    if args.job:JOBS=tuple(args.job)
    if args.direction is not None:DIRECTIONS=tuple(args.direction)
    if args.work:WORK=args.work.resolve()
    if args.revision:REVISION=args.revision
    if args.sources:SOURCE_MANIFEST=args.sources.resolve()
    assert set(JOBS)<=set(['acolyte','archer']) and set(DIRECTIONS)<=set(range(8))
    WORK.mkdir(parents=True,exist_ok=True)
    if args.stage=='build':build()
    elif args.stage=='verify':verify_surfaces()
    else:prototype()
