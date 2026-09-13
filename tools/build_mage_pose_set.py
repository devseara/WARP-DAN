"""Build a complete native-action Mage pair from whole-pose painted drawings."""
import argparse,copy,json
import numpy as np
from pathlib import Path
from PIL import Image
from prepare_mage_pose_set import WORK,native_context,sha
from import_full_swordman_art import extract
from sprite_formats import Layer,read_act,read_spr,write_act,write_spr
from spr_reader import Spr
from render_native_wing_anatomy import rgba
from preview_clan_reference_revision import bake

def build(sex,partial=False):
    plan=json.loads((WORK/'art-plan.json').read_text(encoding='utf8'));src,spr,native,_,_=native_context('mage',sex);art={};imports=[];missing=[]
    for b in plan['batches']:
        if b['sex']!=sex:continue
        if not (WORK/'art'/sex/(b['name']+'.png')).exists():missing.append(b['name']);continue
        assert sha(src/'body.spr')==b['source_spr_sha256'] and sha(src/'body.act')==b['source_act_sha256']
        drawings,rows=extract(b,WORK);art.update(drawings);imports+=rows
    overrides=WORK/'art-overrides.json'
    if overrides.exists():
        for override in json.loads(overrides.read_text(encoding='utf8')):
            if override['sex']!=sex:continue
            b=copy.deepcopy(next(b for b in plan['batches'] if b['sex']==sex and b['name']==override['base_batch']))
            b['name']=override['art_batch'];drawings,rows=extract(b,WORK);selected=set(override['selected_sprites'])
            for index in selected:art[index]=drawings[index]
            imports=[r for r in imports if r['sprite'] not in selected]+[dict(r,correction_reason=override['reason']) for r in rows if r['sprite'] in selected]
    if missing and not partial:raise ValueError(('Missing artwork',sex,missing))
    records={p['sprite']:p for b in plan['batches'] if b['sex']==sex for p in b['poses']}
    ratios={}
    for index,(im,offset) in art.items():
        rec=records[index];head=rec['head_anchor_in_source'][1]*4;raw=rgba(spr,index,0)
        n=raw.getbbox()[3]*4-head;g=offset[1]+im.getbbox()[3]-head
        if abs(n)>60 and abs(g)>60 and n*g>0:ratios.setdefault(rec['representative_action'],[]).append(n/g)
    scales={ai:float(np.median(values)) for ai,values in ratios.items()}
    for index,(im,offset) in list(art.items()):
        rec=records[index];factor=scales.get(rec['representative_action'],1.0)
        row=next(r for r in imports if r['sprite']==index)
        adjustments=WORK/'pose-adjustments.json'
        manual=next((r for r in json.loads(adjustments.read_text(encoding='utf8')) if r['sex']==sex and r['sprite']==index),None) if adjustments.exists() else None
        if manual:
            assert manual['source_sha256']==row['source_sha256']
            factor=manual['fixed_scale']
        assert .65<factor<1.4,(sex,index,'unexpected scale',factor)
        center=np.array(rec['head_anchor_in_source'])*4
        placed=np.rint(center+(offset-center)*factor).astype(int)
        if manual:placed+=np.array(manual['translation_4x'])
        fitted=im.resize((round(im.width*factor),round(im.height*factor)),Image.Resampling.NEAREST)
        art[index]=(fitted,placed);fitted.save(WORK/'whole-frames'/sex/f'sprite-{index:03d}.png')
        row=next(r for r in imports if r['sprite']==index);row.update(whole_pose_adjustment=manual,sequence_action=rec['representative_action'],native_sequence_scale=factor,final_offset_4x=placed.tolist(),final_size=list(fitted.size))
    (WORK/(sex+'-sequence-scale.json')).write_text(json.dumps(dict(method='Fixed uniform scale per native action/view, measured from median original collar-anchor-to-sole extent; no per-frame or per-limb scaling',scales=scales),indent=2),encoding='utf8')
    act=copy.deepcopy(native);images=[];seen={};stock=[]
    for ai,frames in enumerate(act.actions):
        for fi,f in enumerate(frames):
            pieces=[]
            for l in native.actions[ai][fi].layers:
                if l.index<0:continue
                raw=rgba(spr,l.index,l.kind)
                if l.index in art:im,offset=art[l.index];dx,dy=map(int,offset)
                else:stock.append([ai,fi]);im=raw.resize((raw.width*4,raw.height*4),Image.Resampling.NEAREST);dx=dy=0
                if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);dx=raw.width*4-im.width-dx
                pieces.append((im,(l.x-raw.width//2)*4+dx,(l.y-raw.height//2)*4+dy))
            image,x,y=bake(pieces);key=(image.size,image.tobytes())
            if key not in seen:seen[key]=len(images);images.append(image)
            f.layers=[Layer(x,y,seen[key],sx=.25,sy=.25)]
    out=WORK/'assets';out.mkdir(exist_ok=True);stem=out/f'{sex}-angel-mage-v1';sb,ab=write_spr(images),write_act(act);stem.with_suffix('.spr').write_bytes(sb);stem.with_suffix('.act').write_bytes(ab)
    decoded=read_spr(sb);parsed=read_act(ab);independent=Spr(sb)
    assert all(im.tobytes()==rgba(independent,i,1).tobytes() for i,im in enumerate(decoded))
    assert parsed.tail==native.tail and len(parsed.actions)==104 and sum(map(len,parsed.actions))==456
    for ai,fs in enumerate(parsed.actions):
        assert len(fs)==len(native.actions[ai])
        for fi,f in enumerate(fs):
            n=native.actions[ai][fi];assert (f.anchors,f.ranges,f.sound)==(n.anchors,n.ranges,n.sound)
    r=dict(job='mage',sex=sex,status='Complete artwork review' if not missing else 'Partial artwork in development',actions=104,frame_uses=456,unique_drawings=len(art),stock_fallback_frames=stock,missing_sheets=missing,imports=imports,detached_artwork_flags=[r['sprite'] for r in imports if r['detached_component_sizes']],native_metadata_preserved=True,independent_decoder_match=True,installed=False,files=[dict(path=p.relative_to(WORK).as_posix(),sha256=sha(p)) for p in (stem.with_suffix('.spr'),stem.with_suffix('.act'))]);(WORK/f'{sex}-verification.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in r.items() if k not in ('imports','stock_fallback_frames')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sex',choices=['male','female'],required=True);p.add_argument('--partial',action='store_true');a=p.parse_args();build(a.sex,a.partial)
