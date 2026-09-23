"""Read-only motion audit of effective clan resources and accepted local Thief art.

Texture registration is a screening measurement, not an anatomical landmark.
Use the unmodified native/custom loops and source-pixel sheets to confirm defects.
"""
import argparse
import configparser
import hashlib
import io
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from package_clan_skin_assets import ROOT,GrfFile
from review_original_job_directions import native_context
from review_full_swordman_set import ORIGIN,body,head
from sprite_formats import anchor,read_act,read_spr
from fix_archer_design_alignment import neck_point
from build_female_mage_v10 import fit_patch

WORK=ROOT/'Assets/ClanBodySkins/all-jobs-motion-audit-20260923'
GAME=Path('C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes')
GROUPS=['Idle','Walk','Sit','Pickup','Attack 1','Attack 2','Hit','Native action 7','Death','Standby','Attack 3','Attack 4','Cast']


def load(path):return json.loads(path.read_text(encoding='utf8'))
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf8',newline='\n')
def sha(raw):return hashlib.sha256(raw).hexdigest()


def inventory():
    config=configparser.ConfigParser();config.read(GAME/'DATA.INI',encoding='utf-8-sig')
    names=[v for k,v in sorted(config['Data'].items(),key=lambda item:int(item[0]))]
    archives=[(name,GrfFile(GAME/name)) for name in names]
    manifest=load(ROOT/'Inputs/ClanBodySkins/records/clan-sprites-current.json')
    resources=list(manifest['resources']);thief=load(ROOT/'Inputs/ClanBodySkins/records/clan-thief-full-review.json')
    for row in ([] if any(r['job']=='thief' for r in resources) else thief['files']):
        key='남' if row['sex']=='male' else '여'
        resources.append(dict(job='thief',sex=row['sex'],entry=f'data/sprite/clan_skins/1/인간족/몸통/{key}/도둑_{key}'+Path(row['path']).suffix,source=thief['work']+'/'+row['path'],sha256=row['sha256']))
    rows=[]
    try:
        for row in resources:
            raw=(ROOT/row['source']).read_bytes();assert sha(raw)==row['sha256'],row['source']
            hits=[name for name,a in archives if row['entry'] in a.entries]
            selected=next(((name,a) for name,a in archives if row['entry'] in a.entries),None)
            loose=[GAME/row['entry'],GAME/row['entry'].encode('cp949').decode('cp1252')]
            effective=sha(selected[1].read(row['entry'])) if selected else None
            rows.append(dict(**row,archives=hits,effective_archive=selected[0] if selected else None,effective_sha256=effective,matches_accepted=effective==row['sha256'] if selected else None,loose_files=[str(p) for p in loose if p.exists()]))
    finally:
        for _,a in archives:a.close()
    path=WORK/'inventory.json'
    if path.exists():assert load(path)['resources']==rows,'Audit sources changed; use another directory'
    native_pins=[]
    for job,sex in sorted({(r['job'],r['sex']) for r in rows}):
        folder=native_context(job,sex)[0]
        for name in ('body.spr','body.act','head.spr','head.act'):
            reference=folder/name
            assert reference.is_file(), ('Missing durable native reference',reference)
            native_pins.append(dict(job=job,sex=sex,path=str(reference.relative_to(ROOT)),sha256=sha(reference.read_bytes())))
    if path.exists() and load(path).get('native_reference_pins'):
        assert load(path)['native_reference_pins']==native_pins,'Native references changed; use another audit directory'
    save(path,dict(date='2026-09-23',archive_priority=names,resources=rows,grf_modified=False,native_reference_pins=native_pins))
    for job in sorted({r['job'] for r in rows}):
        selected=[r for r in rows if r['job']==job]
        print(json.dumps(dict(job=job,archives=[r['effective_archive'] for r in selected],matches=[r['matches_accepted'] for r in selected],loose=sum(len(r['loose_files']) for r in selected))),flush=True)


def pairs():
    inv=load(WORK/'inventory.json');archives={name:GrfFile(GAME/name) for name in inv['archive_priority']}
    blobs={};folders={};states={}
    try:
        for r in inv['resources']:
            assert not r['loose_files'],'Resolve loose-file precedence before certifying the effective pair'
            key=(r['job'],r['sex']);local=ROOT/r['source']
            if r['effective_archive']:
                raw=archives[r['effective_archive']].read(r['entry']);assert sha(raw)==r['effective_sha256'];state='installed: '+r['effective_archive']
            else:
                assert r['job']=='thief';raw=local.read_bytes();assert sha(raw)==r['sha256'];state='accepted local pair; not installed'
            blobs.setdefault(key,{})[local.suffix]=raw;folders[key]=local.parent.parent;states[key]=state
    finally:
        for a in archives.values():a.close()
    return {key:(read_spr(v['.spr']),read_act(v['.act'])) for key,v in blobs.items()},folders,states


def refs():return load(ROOT/'Assets/ClanBodySkins/Acolyte/motion-v3/../registration-v2/head-neck-reference.json')


def torso_box(job,sex,ai,reference):
    _,_,native,heads,ha=native_context(job,sex)
    target=neck_point(reference,sex,native,heads,ha,ai,0)
    bottom=body(sex,ai,0,job=job).getbbox()[3]-ORIGIN[1]
    height=(bottom-target[1])/4;x,y=target/4
    half=4.5 if ai%8 in (2,6) else 6.0
    return (np.rint(np.array([x-half,y+height*.10,x+half,y+height*.36])*4)/4).tolist()


def walk_sheet(job,sex,ai,pair,reference):
    native=native_context(job,sex)[2];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',12)
    frames=len(native.actions[ai]);width=180;board=Image.new('RGB',(frames*width,760),'#283746');pen=ImageDraw.Draw(board)
    region=torso_box(job,sex,ai,reference);crop=np.rint(np.array(region)*4+[*ORIGIN,*ORIGIN]).astype(int)
    for fi in range(frames):
        for row,selected in enumerate((None,pair)):
            im=body(sex,ai,fi,selected,job=job);im.alpha_composite(head(sex,ai,fi,job=job,pair=selected))
            im=im.crop((140,40,500,540)).resize((180,250),Image.Resampling.NEAREST);board.paste(im,(fi*width,row*275+24),im)
            pen.text((fi*width+3,row*275+3),f'{job} {sex} F{fi} '+('native' if row==0 else 'custom'),font=font,fill='white')
        # This labelled diagnostic removes ONLY the native head-anchor translation.
        bob=np.array(anchor(native.actions[ai][fi]))-anchor(native.actions[ai][0]);im=body(sex,ai,fi,pair,job=job)
        box=crop+np.tile(np.rint(bob*4).astype(int),2);detail=im.crop(tuple(box)).resize((144,160),Image.Resampling.NEAREST)
        board.paste(detail,(fi*width+18,582),detail);pen.text((fi*width+3,558),'Upper cloth / native bob removed',font=font,fill='#bfd5e5')
    out=WORK/'sheets'/f'{job}-{sex}-a{ai}.png';out.parent.mkdir(exist_ok=True);board.save(out)


def sheets(job):
    loaded,_,_=pairs();reference=refs()
    for (j,sex),pair in loaded.items():
        if j!=job:continue
        for ai in range(8,16):walk_sheet(j,sex,ai,pair,reference)
    print('Saved all eight-direction walking sheets for '+job,flush=True)


def screen():
    loaded,folders,states=pairs();reference=refs();summaries=[];all_metrics=[];data={};images=WORK/'review-images';images.mkdir(exist_ok=True)
    known={};pixel_checks=0
    def image_path(image,folder):
        nonlocal pixel_checks
        stream=io.BytesIO();image.save(stream,format='PNG');raw=stream.getvalue();name=sha(raw)+'.png';pixel_checks+=1
        if name in known:return known[name]
        existing=folder/'review/images'/name
        if existing.is_file() and existing.read_bytes()==raw:path=existing
        else:path=images/name;path.write_bytes(raw)
        # All paths served beneath the shared clan asset root.
        url='/'+path.relative_to(ROOT/'Assets/ClanBodySkins').as_posix();known[name]=url;return url
    for (job,sex),pair in loaded.items():
        _,_,native,heads,ha=native_context(job,sex);assert len(pair[1].actions)==len(native.actions)==104
        actions=[];rows=[];head_matches=0
        for ai,frames in enumerate(pair[1].actions):
            assert len(frames)==len(native.actions[ai])
            timeline=[]
            for fi,f in enumerate(frames):
                nb=body(sex,ai,fi,job=job);cb=body(sex,ai,fi,pair,job=job);nh=head(sex,ai,fi,job=job);ch=head(sex,ai,fi,job=job,pair=pair)
                same=nh.tobytes()==ch.tobytes();head_matches+=same
                point=neck_point(reference,sex,native,heads,ha,ai,fi)+ORIGIN
                metrics={}
                for label,im in [('native',nb),('custom',cb)]:
                    mask=np.asarray(im)[:,:,3]>127;bounds=im.getbbox();delta_y=anchor(f)[1]-anchor(native.actions[ai][fi])[1] if label=='custom' else 0
                    metrics[label]=dict(bounds=bounds,area_native=float(mask.sum()/16),native_anchor_to_bottom=float((bounds[3]-point[1])/4),neck_to_bottom=float((bounds[3]-point[1])/4-delta_y),width_native=(bounds[2]-bounds[0])/4)
                height=metrics['native']['neck_to_bottom'];ratio=metrics['custom']['neck_to_bottom']/height if height>8 else None
                row=dict(job=job,sex=sex,action=ai,frame=fi,direction=ai%8,group=ai//8,head_pixels_identical=same,head_anchor_delta=(np.array(anchor(f))-anchor(native.actions[ai][fi])).tolist(),metadata_identical=(f.anchors,f.ranges,f.sound)==(native.actions[ai][fi].anchors,native.actions[ai][fi].ranges,native.actions[ai][fi].sound),height_ratio=ratio,**metrics)
                rows.append(row);timeline.append([image_path(im,folders[job,sex]) for im in (nb,cb,nh,ch)])
            actions.append(dict(ms=round(pair[1].speeds[ai]*25),frames=timeline))
        baselines={d:next(r['height_ratio'] for r in rows if r['action']==d and r['frame']==0) for d in range(8)}
        for r in rows:r['idle_normalized_height']=r['height_ratio']/baselines[r['direction']] if r['height_ratio'] and baselines[r['direction']] else None
        groups=[]
        for g in range(13):
            values=[r['idle_normalized_height'] for r in rows if r['group']==g and r['idle_normalized_height']]
            groups.append(dict(group=g,label=GROUPS[g],median=float(np.median(values)) if values else None,minimum=min(values,default=None),maximum=max(values,default=None)))
        transforms=sorted({(l.sx,l.sy,l.angle) for fs in pair[1].actions for f in fs for l in f.layers})
        item=dict(job=job,sex=sex,state=states[job,sex],actions=104,frame_uses=len(rows),native_head_pixel_matches=head_matches,act_transforms=transforms,speeds_match=pair[1].speeds==native.speeds,metadata_match=all(r['metadata_identical'] for r in rows),groups=groups)
        summaries.append(item);all_metrics.extend(rows);data.setdefault(job,{})[sex]=dict(state=states[job,sex],actions=actions)
        for ai in range(8,16):walk_sheet(job,sex,ai,pair,reference)
        print(json.dumps(dict(job=job,sex=sex,frames=len(rows),heads_identical=head_matches,walk_height=groups[1])),flush=True)
    save(WORK/'screening.json',dict(status='screening_requires_visual_interpretation',pairs=summaries,frame_uses=len(all_metrics),render_checks=pixel_checks,unique_images=len(known),metrics=all_metrics,limitations=['Bounding boxes and neck-to-bottom ratios are not anatomical proof.','ACT scale and head identity do not validate motion inside the bitmap.']))
    save(WORK/'review-data.json',dict(groups=GROUPS,jobs=data))
    (WORK/'review.html').write_text((ROOT/'tools/clan_motion_review.html').read_text(encoding='utf8'),encoding='utf8',newline='\n')


def track(jobs):
    loaded,_,_=pairs();reference=refs();results=[]
    for (job,sex),pair in loaded.items():
        if jobs and job not in jobs:continue
        native=native_context(job,sex)[2]
        for ai in range(8,16):
            box=torso_box(job,sex,ai,reference);fits={}
            for label,selected in [('native',None),('custom',pair)]:
                base=body(sex,ai,0,selected,job=job);samples=[]
                for fi in range(8):
                    hint=np.array(anchor(native.actions[ai][fi]))-anchor(native.actions[ai][0]);im=body(sex,ai,fi,selected,job=job)
                    _,fit=fit_patch(im,base,box,hint=hint,scale_range=(.75,1.30));fit['frame']=fi;fit['native_bob']=hint.tolist();fit['relative_shift']=[fit['dx']-hint[0],fit['dy']-hint[1]];samples.append(fit)
                fits[label]=samples
            custom=np.array([r['relative_shift'] for r in fits['custom']]);stock=np.array([r['relative_shift'] for r in fits['native']]);extra=custom-stock
            row=dict(job=job,sex=sex,action=ai,direction=ai-8,roi_native=box,texture_tracks=fits,custom_minus_native_shift=extra.tolist(),extra_shift_range=np.ptp(extra,axis=0).tolist(),custom_scale_range=[float(np.ptp([r[k] for r in fits['custom']])) for k in ['sx','sy']],minimum_correlation=min(r['correlation'] for r in fits['custom']),interpretation='Texture-fit screen. Occlusion or changing cloth features may invalidate a fit; inspect its ROI and raw sequence.')
            native_confidence=min(r['correlation'] for r in fits['native'])
            saturated=any(min(r['sx'],r['sy'])<=.751 or max(r['sx'],r['sy'])>=1.299 or max(abs(v) for v in r['relative_shift'])>=3.99 for fs in fits.values() for r in fs)
            row.update(minimum_native_correlation=native_confidence,minimum_pair_correlation=min(native_confidence,row['minimum_correlation']),fit_saturated=saturated,translation_comparison_reliable=min(native_confidence,row['minimum_correlation'])>=.75 and not saturated)
            results.append(row);print(json.dumps({k:row[k] for k in ['job','sex','direction','extra_shift_range','custom_scale_range','minimum_correlation']}),flush=True)
        save(WORK/f'{job}-{sex}-torso-tracks.json',[r for r in results if (r['job'],r['sex'])==(job,sex)])
    save(WORK/('torso-tracks-'+('-'.join(jobs) if jobs else 'all')+'.json'),results)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['inventory','sheets','screen','track']);p.add_argument('--job',action='append');p.add_argument('--work',type=Path);a=p.parse_args();WORK=(a.work or WORK).resolve()
    if not WORK.is_relative_to((ROOT/'Assets/ClanBodySkins').resolve()):p.error('--work must stay within Assets/ClanBodySkins')
    WORK.mkdir(exist_ok=True)
    if a.stage=='inventory':inventory()
    elif a.stage=='sheets':
        for job in a.job or ['acolyte']:sheets(job)
    elif a.stage=='track':track(a.job)
    else:screen()
