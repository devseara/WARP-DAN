"""Native-body registration corrections, built separately from accepted resources.

This builder edits the existing sprite rig and palette/masks. It does not invent
head offsets, re-center tight crops, or replace approved costume artwork.
"""
import argparse
import copy
import hashlib
import io
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from audit_clan_motion import ROOT, WORK as AUDIT, load, save, sha, refs
from review_original_job_directions import native_context
from review_full_swordman_set import ORIGIN, body, head
from fix_archer_design_alignment import neck_point
from refine_clan_combat_necks import components
from preview_clan_reference_revision import bake
from sprite_formats import Layer, anchor, read_spr, read_act, write_spr, write_act
from render_native_wing_anatomy import rgba
from spr_reader import Spr
from fix_acolyte_motion import fit_sole

WORK=ROOT/'Assets/ClanBodySkins/neck-motion-correction-v1'
FONT=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',13)


def original_pairs():
    blobs={}
    for r in load(AUDIT/'inventory.json')['resources']:
        p=ROOT/r['source'];raw=p.read_bytes();assert sha(raw)==r['sha256'],p
        blobs.setdefault((r['job'],r['sex']),{})[p.suffix]=raw
    return {k:(read_spr(v['.spr']),read_act(v['.act'])) for k,v in blobs.items()}


def native_skin(job,sex,ai,fi):
    """The original job's skin palette, rendered with its exact ACT placement."""
    _,spr,act,_,_=native_context(job,sex);c=Image.new('RGBA',(640,640))
    for l in act.actions[ai][fi].layers:
        if l.index<0:continue
        raw=spr.images[l.index];idx=np.frombuffer(raw.pixels,np.uint8).reshape(raw.height,raw.width)
        ranges={'swordman': [(72,79),(128,135),(168,175)] if sex=='male' else [(168,175)], 'thief':[(72,79),(128,135)]}.get(job,[(128,135)])
        selected=np.zeros(idx.shape,bool)
        for lo,hi in ranges:selected|=(idx>=lo)&(idx<=hi)
        im=np.array(rgba(spr,l.index,l.kind));im[~selected]=0
        im=Image.fromarray(im)
        if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        im=im.resize((raw.width*4,raw.height*4),Image.Resampling.NEAREST)
        c.alpha_composite(im,((l.x-raw.width//2)*4+ORIGIN[0],(l.y-raw.height//2)*4+ORIGIN[1]))
    return c


def original_neck(job,sex,ai,fi):
    _,_,act,heads,ha=native_context(job,sex)
    point=neck_point(refs(),sex,act,heads,ha,ai,fi)+ORIGIN
    return point,native_skin(job,sex,ai,fi)


def neck_bridge(image,job,sex,ai,fi):
    """Restore only original neck-skin pixels in the existing dark aperture.

    The native mask bounds the anatomy; a narrow neck window and dark-interior
    mask protect ivory/gold collar rims. No skin is copied onto the armor field.
    """
    point,skin=original_neck(job,sex,ai,fi);x,y=np.rint(point).astype(int)
    source=np.array(skin);before=np.array(image);after=before.copy()
    window=np.zeros((640,640),bool);window[max(0,y-20):min(640,y+17),max(0,x-18):min(640,x+19)]=True
    rgb=before[:,:,:3].astype(float);lum=rgb@np.array([.2126,.7152,.0722])
    interior=((lum<70)&(rgb.max(axis=2)<100))|(before[:,:,3]==0)
    # The custom open collar can expose more neck than the stock closed shirt.
    # Continue the existing native neck material by at most two game pixels,
    # only inside that aperture; the bright collar rim remains the occluder.
    neck=np.zeros_like(source);neck[window]=source[window]
    extended=neck.copy()
    for shift in range(1,9):
        donor=np.zeros_like(neck);donor[shift:]=neck[:-shift]
        take=(donor[:,:,3]==255)&(extended[:,:,3]==0)&window
        extended[take]=donor[take]
    selected=window&(extended[:,:,3]==255)&interior
    after[selected]=extended[selected]
    assert np.array_equal(before[~selected],after[~selected])
    return Image.fromarray(after),dict(method='Original neck palette/mask inside dark collar aperture',
        changed_pixels=int(np.any(before!=after,axis=2).sum()),window=[int(x-18),int(y-20),int(x+19),int(y+17)],
        outside_mask_pixel_identical=True,maximum_neck_continuation_native=2.)


def upper_translation(image,source,target,rigid_depth=40,transition=152,rigid_x=False,preserve_boots=False):
    """Translate the upper body continuously, with unchanged lower body pixels.

    Horizontal movement is a shear, never a horizontal resize. The inverse
    vertical map must remain monotone. Neck and shoulder pixels move rigidly.
    """
    source,target=np.array(source,float),np.array(target,float);delta=target-source
    first=source[1]+rigid_depth;last=first+max(transition,abs(delta[1])*3.2)
    if preserve_boots:
        last=image.getbbox()[3]-24
        first=min(first,last-max(36.,abs(delta[1])*1.9))
        assert first>=source[1]+28, ('Insufficient torso-to-sole span',source,target,first,last)
    # Lying/low poses may end the transition below the visible canvas.
    # A monotone inverse still preserves the pose without crop recentering.
    sy=np.linspace(0,639,640*16);t=np.clip((sy-first)/(last-first),0,1);weight=1-t*t*(3-2*t)
    dy=sy+delta[1]*weight;derivative=np.diff(dy)/np.diff(sy)
    assert derivative.min()>.20
    source_y=np.interp(np.arange(640),dy,sy)
    t=np.clip((source_y-first)/(last-first),0,1);w=1-t*t*(3-2*t)
    yy=np.rint(source_y).astype(int);xw=np.ones_like(w) if rigid_x else w
    xx=np.rint(np.arange(640)[None,:]-delta[0]*xw[:,None]).astype(int)
    valid=(xx>=0)&(xx<640)&(yy[:,None]>=0)&(yy[:,None]<640)
    result=np.zeros((640,640,4),np.uint8);data=np.asarray(image)
    result[valid]=data[np.broadcast_to(yy[:,None],xx.shape)[valid],xx[valid]]
    fixed_from=int(np.ceil(last))+1
    if not rigid_x:assert np.array_equal(result[fixed_from:],data[fixed_from:])
    return Image.fromarray(result),dict(method='Continuous upper-body translation; native head restored',
        source=source.tolist(),target=target.tolist(),delta_4x=delta.tolist(),rigid_to_4x=first,
        fixed_from_4x=fixed_from,min_vertical_jacobian=float(derivative.min()),lower_body_pixels_preserved=not rigid_x,rigid_boot_region=preserve_boots,horizontal_registration='whole-pose translation' if rigid_x else 'upper-body shear')


def collar_only_translation(image,source,target,grips):
    source,target=np.array(source,float),np.array(target,float);delta=target-source
    yy,xx=np.indices((640,640));dx=abs(xx-target[0]);dy=abs(yy-target[1])
    def falloff(distance,inner,outer):
        t=np.clip((distance-inner)/(outer-inner),0,1);return 1-t*t*(3-2*t)
    weight=falloff(dx,12,52)*falloff(dy,8,52)
    locked=np.zeros((640,640),bool)
    for p in grips:
        distance=np.hypot(xx-p[0],yy-p[1]);locked|=distance<=12
        weight*=1-falloff(distance,12,30)
    sx=xx-delta[0]*weight;sy=yy-delta[1]*weight
    jac=np.gradient(sx,axis=1)*np.gradient(sy,axis=0)-np.gradient(sx,axis=0)*np.gradient(sy,axis=1)
    assert jac.min()>.20,('Bow neck field folds',float(jac.min()))
    source_pixels=np.asarray(image);ix,iy=np.rint(sx).astype(int),np.rint(sy).astype(int)
    assert ix.min()>=0 and iy.min()>=0 and ix.max()<640 and iy.max()<640
    result=source_pixels[iy,ix].copy()
    assert np.array_equal(result[locked],source_pixels[locked])
    outside=weight==0;assert np.array_equal(result[outside],source_pixels[outside])
    return Image.fromarray(result),dict(method='Local collar registration with accepted bow grips locked',
        source=source.tolist(),target=target.tolist(),minimum_jacobian=float(jac.min()),
        grip_points=grips,grip_patch_radius_4x=12,grip_pixels_identical=True,outside_collar_field_identical=True)


def calibrate():
    pairs=original_pairs();records=[]
    for (job,sex),pair in pairs.items():
        if job!='mage' and (job,sex)!=('thief','male'):continue
        _,_,native,heads,ha=native_context(job,sex);seen=set()
        for ai,frames in enumerate(pair[1].actions):
            if ai//8 in (3,7,8):continue
            for fi,f in enumerate(frames):
                hf=ha.actions[ai][min(fi,len(ha.actions[ai])-1)];hl=next(l for l in hf.layers if l.index>=0)
                if hl.index not in (3,4) or f.layers[0].index in seen:continue
                seen.add(f.layers[0].index)
                point,skin=original_neck(job,sex,ai,fi);yy,xx=np.indices((640,640));sk=np.asarray(skin)[:,:,3]>127
                sk&=(abs(xx-point[0])<36)&(abs(yy-point[1])<28)
                gs=[g for g in components(sk) if len(g)>12]
                if not gs:continue
                g=min(gs,key=lambda g:np.linalg.norm(np.array([g[:,1].mean(),g[:,0].mean()])-point))
                weights=np.ones(len(g)) if job=='mage' else np.exp(-np.sum((g[:,::-1]-point)**2,axis=1)/(2*14**2))
                target=np.average(g[:,::-1],axis=0,weights=weights)
                im=body(sex,ai,fi,pair,job=job);a=np.asarray(im);rgb=a[:,:,:3].astype(float)
                region=(abs(xx-point[0])<108)&(yy>point[1]-68)&(yy<point[1]+28)&(a[:,:,3]>127)
                color=((rgb[:,:,2]>rgb[:,:,0]*1.3)&(rgb[:,:,2]>rgb[:,:,1]*1.03)) if job=='mage' else ((rgb[:,:,0]>130)&(rgb[:,:,0]-rgb[:,:,1]>38)&(abs(rgb[:,:,1]-rgb[:,:,2])<26))
                groups=[]
                for group in components(color&region):
                    gy,gx=group[:,0],group[:,1];w,h=np.ptp(gx)+1,np.ptp(gy)+1
                    if len(group)>24 and 12<w<104 and h<52 and w/h>1.1:groups.append(group)
                if not groups:continue
                groups.sort(key=lambda g:g[:,0].mean() + .12*abs(g[:,1].mean()-point[0]))
                g=groups[0];source=np.array([g[:,1].mean(),g[:,0].mean()])
                records.append(dict(job=job,sex=sex,action=ai,frame=fi,native_sprite=native.actions[ai][fi].layers[0].index,custom_sprite=f.layers[0].index,layer_xy=[f.layers[0].x,f.layers[0].y],source=source.tolist(),target=target.tolist(),delta_native=((target-source)/4).tolist(),feature_bounds=[int(g[:,1].min()),int(g[:,0].min()),int(g[:,1].max()+1),int(g[:,0].max()+1)],apply=False,reviewed=False))
        selected=[r for r in records if (r['job'],r['sex'])==(job,sex)]
        for page in range((len(selected)+11)//12):
            board=Image.new('RGB',(4*360,3*220),'#283746');pen=ImageDraw.Draw(board)
            for cell,r in enumerate(selected[page*12:(page+1)*12]):
                x=cell%4*360;y=cell//4*220;point=np.array(r['target']);box=tuple(np.rint(np.tile(point,2)+[-80,-75,80,95]).astype(int))
                for col,p in enumerate((None,pair)):
                    im=body(sex,r['action'],r['frame'],p,job=job);d=ImageDraw.Draw(im)
                    q=np.array(r['target'] if col==0 else r['source']);d.ellipse((q[0]-3,q[1]-3,q[0]+3,q[1]+3),outline='#00ffff' if col==0 else '#ff00ff',width=2)
                    im=im.crop(box);board.paste(im,(x+col*175,y+25),im)
                pen.text((x+3,y+3),f"{job} {sex} C{r['custom_sprite']} N{r['native_sprite']} A{r['action']} F{r['frame']}",font=FONT,fill='white')
                pen.text((x+3,y+196),'delta '+str([round(v,2) for v in r['delta_native']]),font=FONT,fill='white')
            folder=WORK/'calibration-review';folder.mkdir(exist_ok=True);board.save(folder/f'{job}-{sex}-{page}.png')
        print(job,sex,'proposals',len(selected),flush=True)
    path=WORK/'collar-calibration.json'
    assert not path.exists(),'Calibration already exists; preserve reviewed points'
    save(path,records)


def build(jobs,sex_filter=None):
    pairs=original_pairs();checks=[];files=[]
    source_pins=load(AUDIT/'inventory.json')
    save(WORK/'source-pins.json',source_pins)
    calibration_hash=sha((WORK/'collar-calibration.json').read_bytes())
    for (job,sex),old in pairs.items():
        if job not in jobs or (sex_filter and sex!=sex_filter):continue
        _,_,native,heads,ha=native_context(job,sex);act=copy.deepcopy(old[1]);images=[];seen={};records=[]
        calibration=load(WORK/'collar-calibration.json') if (WORK/'collar-calibration.json').exists() else []
        collar_rows={(r['job'],r['sex'],r['custom_sprite']):r for r in calibration}
        acolyte_rows={(r['sex'],r['action'],r['frame']):r for r in load(WORK/'acolyte-walk-collars.json')}
        bow_rows={(r['sex'],r['action'],r['frame']):r for r in load(WORK/'archer-bow-grips.json')['frames']}
        for ai,frames in enumerate(act.actions):
            for fi,f in enumerate(frames):
                nf=native.actions[ai][fi];before=body(sex,ai,fi,old,job=job);im=before;proof=[]
                c=collar_rows.get((job,sex,f.layers[0].index))
                if c and c.get('apply'):
                    offset=(np.array([f.layers[0].x,f.layers[0].y])-c['layer_xy'])*4
                    source=np.array(c['source'])+offset;target=np.array(c['target'])+offset
                    im,p=upper_translation(im,source,target,rigid_depth=120 if job=='mage' else 84,transition=152,rigid_x=(job=='mage'),preserve_boots=True);proof.append(p)
                if job=='acolyte' and (sex,ai,fi) in acolyte_rows:
                    r=acolyte_rows[sex,ai,fi];assert r['reviewed']
                    im,p=upper_translation(im,r['source'],r['target'],rigid_depth=80,preserve_boots=True);p['method']='Actual native neck-cap registration for side/rear walking';proof.append(p)
                if job=='archer':
                    delta=np.array(anchor(f))-anchor(nf)
                    if delta.any():
                        target=neck_point(refs(),sex,native,heads,ha,ai,fi)+ORIGIN
                        if ai//8==10:im,p=collar_only_translation(im,target+delta*4,target,bow_rows[sex,ai,fi]['points'])
                        else:im,p=upper_translation(im,target+delta*4,target)
                        proof.append(p)
                    f.anchors=copy.deepcopy(nf.anchors)
                if job in ('swordman','acolyte','archer') and ai//8 not in (3,7,8) and not(job=='archer' and ai//8==10):
                    im,p=neck_bridge(im,job,sex,ai,fi);proof.append(p)
                stature_fixed=False
                if (job,sex) in [('merchant','female'),('thief','male')] and ai//8 in (0,1):
                    point=neck_point(refs(),sex,native,heads,ha,ai,0 if ai//8==0 else fi)+ORIGIN
                    destination=body(sex,ai,fi,job=job).getbbox()[3]
                    if im.getbbox()[3]!=destination:
                        im,p=fit_sole(im,point[1],destination);p['method']='Native idle/walk sole registration with rigid torso and boots';proof.append(p)
                    stature_fixed=True
                    assert im.getbbox()[3]==destination
                if job=='archer' and sex=='female' and ai//8==11 and nf.layers[0].index==107:
                    pixels=np.array(im);groups=sorted(components(pixels[:,:,3]>127),key=len,reverse=True)
                    extras=[g for g in groups[1:] if len(g)>8]
                    assert len(extras)==1 and len(extras[0])==20,('Unexpected fragment topology',ai,fi,[len(g) for g in groups])
                    g=extras[0];bounds=[int(g[:,1].min()),int(g[:,0].min()),int(g[:,1].max()+1),int(g[:,0].max()+1)]
                    assert 360<=bounds[1]<=400,('Fragment outside inspected skirt-edge region',bounds)
                    pixels[g[:,0],g[:,1]]=0;im=Image.fromarray(pixels);proof.append(dict(method='Remove inspected resampling island from skirt edge',pixels=20,bounds=bounds,native_sprite=107))
                if c and c.get('apply') and not stature_fixed:assert im.getbbox()[3]==before.getbbox()[3],(job,sex,ai,fi,'Sole moved')
                box=im.getbbox();assert box and min(box[:2])>0 and max(box[2:])<640
                image,x,y=bake([(im.crop(box),box[0]-ORIGIN[0],box[1]-ORIGIN[1])]);key=(image.size,sha(image.tobytes()))
                if key not in seen:seen[key]=len(images);images.append(image)
                f.layers=[Layer(x,y,seen[key],sx=.25,sy=.25)]
                pair=images,act
                assert body(sex,ai,fi,pair,job=job).tobytes()==im.tobytes()
                assert head(sex,ai,fi,job=job,pair=pair).tobytes()==head(sex,ai,fi,job=job).tobytes()
                assert (f.anchors,f.ranges,f.sound)==(nf.anchors,nf.ranges,nf.sound)
                records.append(dict(job=job,sex=sex,action=ai,frame=fi,native_sprite=nf.layers[0].index,
                    changed_pixels=int(np.any(np.array(before)!=np.array(im),axis=2).sum()),corrections=proof))
        sb,ab=write_spr(images),write_act(act);decoded=read_spr(sb);independent=Spr(sb)
        assert len(act.actions)==104 and sum(map(len,act.actions))==456 and act.speeds==native.speeds
        for i,im in enumerate(decoded):assert im.tobytes()==rgba(independent,i,1).tobytes()
        dest=WORK/job/'assets';dest.mkdir(parents=True,exist_ok=True)
        for ext,raw in [('.spr',sb),('.act',ab)]:
            p=dest/f'{sex}-angel-{job}-neck-v1{ext}';p.write_bytes(raw)
            files.append(dict(job=job,sex=sex,path=p.relative_to(WORK).as_posix(),sha256=sha(raw)))
        save(WORK/job/f'{sex}-verification.json',dict(status='candidate_needs_visual_review',user_accepted=False,installed=False,source_tool_sha256=sha(Path(__file__).read_bytes()),calibration_sha256=calibration_hash,files=[v for v in files if v['job']==job and v['sex']==sex],checks=records))
        checks+=records;print(job,sex,'changed frames',sum(bool(r['changed_pixels']) for r in records),flush=True)
    all_files=[];all_frames=0
    for report in sorted(WORK.glob('*/*-verification.json')):
        record=load(report)
        if 'checks' not in record or 'files' not in record:continue
        all_files+=record['files'];all_frames+=len(record['checks'])
    save(WORK/'build-summary.json',dict(status='candidate_needs_visual_review',installed=False,user_accepted=False,files=all_files,frame_uses=all_frames,native_head_renders_identical=all_frames))


def samples(job,sex,actions):
    old=original_pairs()[job,sex];p=WORK/job/'assets'/f'{sex}-angel-{job}-neck-v1';new=read_spr(p.with_suffix('.spr').read_bytes()),read_act(p.with_suffix('.act').read_bytes())
    for ai in actions:
        frames=len(new[1].actions[ai]);board=Image.new('RGB',(frames*210,735),'#283746');pen=ImageDraw.Draw(board)
        for fi in range(frames):
            for row,pair in enumerate((None,old,new)):
                im=body(sex,ai,fi,pair,job=job);im.alpha_composite(head(sex,ai,fi,job=job,pair=pair));im=im.crop((110,40,530,500)).resize((210,230),Image.Resampling.NEAREST)
                board.paste(im,(fi*210,row*236+20),im);pen.text((fi*210+3,row*236+2),f'{job} {sex} A{ai} F{fi} '+['Native','Before','Candidate'][row],font=FONT,fill='white')
        dest=WORK/'review';dest.mkdir(exist_ok=True);board.save(dest/f'{job}-{sex}-a{ai}.png')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['build','samples','calibrate']);p.add_argument('--job',action='append');p.add_argument('--sex');p.add_argument('--action',type=int,action='append');a=p.parse_args();WORK.mkdir(exist_ok=True)
    if a.stage=='calibrate':calibrate()
    elif a.stage=='build':build(a.job or ['swordman','mage','acolyte','archer','merchant','thief'],a.sex)
    else:samples(a.job[0],a.sex,a.action)
