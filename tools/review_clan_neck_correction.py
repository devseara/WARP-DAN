"""Review reopened correction pairs using verified, lossless delta PNGs.

The patches are a storage optimization only. Every reconstructed review canvas
must exactly equal the corresponding reopened SPR/ACT render.
"""
import argparse
import io
from pathlib import Path
import numpy as np
from PIL import Image
from correct_clan_neck_registration import WORK, AUDIT, ROOT, original_pairs, load, save, sha
from review_full_swordman_set import body, head, ORIGIN
from review_original_job_directions import native_context
from sprite_formats import read_spr, read_act, anchor
from refine_clan_combat_necks import components


def main(jobs=None, sources=None, topology_pairs=None):
    old_pairs=original_pairs();data=load(AUDIT/'review-data.json');screen=load(AUDIT/'neck-joins/screen.json')
    points={(r['job'],r['sex'],r['action'],r['frame']):r['crop_center_4x'] for r in screen['frames']}
    output=WORK/'review/patches';output.mkdir(parents=True,exist_ok=True);verified={};written={};records=[];dataset={}
    if jobs and (WORK/'review-data.json').exists():
        dataset=load(WORK/'review-data.json')['jobs']
        records=[r for r in load(WORK/'review-verification.json')['pairs'] if r['job'] not in jobs]
    for (job,sex),old in old_pairs.items():
        if jobs and job not in jobs:continue
        stem=(ROOT/sources[job,sex]).with_suffix('') if sources and (job,sex) in sources else WORK/job/'assets'/f'{sex}-angel-{job}-neck-v1'
        new=(read_spr(stem.with_suffix('.spr').read_bytes()),read_act(stem.with_suffix('.act').read_bytes())) if stem.with_suffix('.spr').exists() else old
        native=native_context(job,sex)[2];actions=[];changed=0;topology=[]
        for ai,frames in enumerate(new[1].actions):
            assert len(frames)==len(native.actions[ai])
            rows=[]
            for fi,frame in enumerate(frames):
                baseline=data['jobs'][job][sex]['actions'][ai]['frames'][fi]
                url=baseline[1];source=ROOT/'Assets/ClanBodySkins'/url.lstrip('/')
                if url not in verified:
                    if not source.exists():
                        source.parent.mkdir(parents=True,exist_ok=True);body(sex,ai,fi,old,job=job).save(source)
                    raw=source.read_bytes();assert sha(raw)==source.stem
                    if len(verified)>100:verified.pop(next(iter(verified)))
                    verified[url]=Image.open(io.BytesIO(raw)).convert('RGBA')
                for slot in (0,2,3):
                    dependency=ROOT/'Assets/ClanBodySkins'/baseline[slot].lstrip('/')
                    if not dependency.exists():
                        rendered=body(sex,ai,fi,job=job) if slot==0 else head(sex,ai,fi,job=job,pair=old if slot==3 else None)
                        dependency.parent.mkdir(parents=True,exist_ok=True);rendered.save(dependency);assert sha(dependency.read_bytes())==dependency.stem
                before=verified[url];after=body(sex,ai,fi,new,job=job);original=body(sex,ai,fi,job=job)
                assert head(sex,ai,fi,job=job,pair=new).tobytes()==head(sex,ai,fi,job=job).tobytes()
                assert (frame.anchors,frame.ranges,frame.sound)==(native.actions[ai][fi].anchors,native.actions[ai][fi].ranges,native.actions[ai][fi].sound)
                topology_before=body(sex,ai,fi,topology_pairs[job,sex],job=job) if topology_pairs and (job,sex) in topology_pairs else before
                diff=np.any(np.asarray(before)!=np.asarray(after),axis=2);patch=None
                if diff.any():
                    changed+=1;yy,xx=np.where(diff);box=[int(xx.min()),int(yy.min()),int(xx.max()+1),int(yy.max()+1)]
                    detail=after.crop(box);buffer=io.BytesIO();detail.save(buffer,format='PNG');raw=buffer.getvalue();digest=sha(raw);path=output/(digest+'.png')
                    if digest not in written:path.write_bytes(raw);written[digest]=True
                    patch=dict(url='/'+path.relative_to(ROOT/'Assets/ClanBodySkins').as_posix(),box=box)
                    reconstructed=before.copy();reconstructed.paste(detail,box[:2]);assert reconstructed.tobytes()==after.tobytes()
                    # New separated opaque fragments are not automatically removed.
                    if not np.array_equal(np.asarray(topology_before)[:,:,3],np.asarray(after)[:,:,3]):
                        old_groups=sorted([len(g) for g in components(np.asarray(topology_before)[:,:,3]>127) if len(g)>8],reverse=True)
                        new_groups=sorted([len(g) for g in components(np.asarray(after)[:,:,3]>127) if len(g)>8],reverse=True)
                        if len(new_groups)>len(old_groups):topology.append(dict(action=ai,frame=fi,before=old_groups,after=new_groups))
                rows.append(dict(original=baseline[0],before=url,original_head=baseline[2],before_head=baseline[3],patch=patch,center=points[job,sex,ai,fi],old_head_delta=(np.array(anchor(old[1].actions[ai][fi]))-anchor(native.actions[ai][fi])).tolist()))
            actions.append(dict(ms=round(new[1].speeds[ai]*25),frames=rows))
        assert new[1].speeds==native.speeds
        links={ext:('/'+stem.with_suffix('.'+ext).relative_to(ROOT/'Assets/ClanBodySkins').as_posix()) for ext in ['act','spr']} if stem.with_suffix('.spr').exists() else {}
        dataset.setdefault(job,{})[sex]=dict(state='Correction candidate; not installed' if changed else 'Unchanged baseline',changed_frames=changed,actions=actions,files=links)
        records.append(dict(job=job,sex=sex,frames=456,changed_frames=changed,native_heads_identical=456,review_reconstruction_exact=True,new_fragment_flags=topology))
        print(job,sex,'changed',changed,'new fragment flags',len(topology),flush=True)
    save(WORK/'review-data.json',dict(jobs=dataset,groups=data['groups']))
    save(WORK/'review-verification.json',dict(status='pixel_checks_complete_requires_visual_review',frame_uses=sum(r['frames'] for r in records),patch_images_generated_this_run=len(written),pairs=records))
    (WORK/'review.html').write_text((ROOT/'tools/clan_neck_correction_review.html').read_text(encoding='utf8'),encoding='utf8',newline='\n')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--job',action='append');p.add_argument('--work',type=Path);p.add_argument('--sources',type=Path);p.add_argument('--topology-baseline',type=Path);a=p.parse_args()
    if a.work:WORK=a.work.resolve()
    sources={(r['job'],r['sex']):r['source'] for r in load(a.sources)['files']} if a.sources else None
    baseline={}
    if a.topology_baseline:
        doc=load(a.topology_baseline);rows=doc.get('files',doc.get('resources'))
        for r in rows:
            if a.job and r['job'] not in a.job:continue
            path=ROOT/r['source'];raw=path.read_bytes();assert sha(raw)==r['sha256']
            baseline.setdefault((r['job'],r['sex']),{})[path.suffix]=raw
        baseline={k:(read_spr(v['.spr']),read_act(v['.act'])) for k,v in baseline.items()}
    main(a.job,sources,baseline)
