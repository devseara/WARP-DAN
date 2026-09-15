"""Import explicitly keyed whole-pose plates through their registration marks."""
import argparse,json,copy,math,hashlib
import numpy as np
from PIL import Image
from prepare_full_swordman_art import WORK,WALK,sha,native_context
from sprite_formats import read_spr,read_act,write_spr,write_act,Layer,anchor
from refine_clan_combat_necks import components
from preview_clan_reference_revision import bake
from render_native_wing_anatomy import rgba
from spr_reader import Spr
from bake_clan_body_frames import composite


def extract(batch, work=WORK):
    path=work/'art'/batch['sex']/(batch['name']+'.png')
    a=np.asarray(Image.open(path).convert('RGBA')).copy();rgb=a[:,:,:3].astype(int)
    green=(rgb[:,:,1]>95)&(rgb[:,:,1]-rgb[:,:,0]>48)&(rgb[:,:,1]-rgb[:,:,2]>48)
    pink=(rgb[:,:,0]>160)&(rgb[:,:,2]>145)&(rgb[:,:,1]<120)
    marks=[p for p in components(pink) if len(p)>=12]
    if batch.get('allow_empty_cell_marks') and len(marks)>batch['cells']:
        # Ignore added page markers only after proving their trailing cells
        # contain no body artwork. This never discards a drawn pose.
        assert len(marks)==batch['columns']*batch['rows']
        marks.sort(key=lambda p:float(p[:,0].mean()))
        full=[]
        for start in range(0,len(marks),batch['columns']):
            full+=sorted(marks[start:start+batch['columns']],key=lambda p:float(p[:,1].mean()))
        centers=np.array([[p[:,1].mean(),p[:,0].mean()] for p in full])
        spacing=float(np.median(np.diff(centers[:batch['columns'],0])))
        for mark in full[batch['cells']:]:
            x=float(mark[:,1].mean());y=int(mark[:,0].max())+8
            left=max(0,round(x-spacing*.45));right=min(a.shape[1],round(x+spacing*.45))
            assert (green[y:,left:right]|pink[y:,left:right]).all(),(path,'extra marker cell is not empty')
        marks=full[:batch['cells']]
    assert len(marks)==batch['cells'],(path,'registration mark count',len(marks),batch['cells'])
    # Each row has a wide vertical separation; then sort marks left to right.
    marks.sort(key=lambda p:float(p[:,0].mean()))
    ordered=[]
    for start in range(0,len(marks),batch['columns']):
        ordered+=sorted(marks[start:start+batch['columns']],key=lambda p:float(p[:,1].mean()))
    points=np.array([[p[:,1].mean(),p[:,0].mean()] for p in ordered])
    # Clear each explicit registration square and its resampled color fringe.
    for mark in ordered:
        y0,x0=mark.min(axis=0);y1,x1=mark.max(axis=0)
        pink[max(0,y0-4):y1+5,max(0,x0-4):x1+5]=True
    expected=np.array([np.array(p['marker_in_cell'])+np.array([p['cell']%batch['columns'],p['cell']//batch['columns']])*batch['tile_size']+[0,340] for p in batch['poses']])
    # Fit translation and ONE uniform scale, never stretch individual poses.
    center=expected.mean(axis=0);outcenter=points.mean(axis=0)
    scale=float(((expected-center)*(points-outcenter)).sum()/((expected-center)**2).sum())
    shift=outcenter-center*scale
    residual=np.linalg.norm(points-(expected*scale+shift),axis=1)
    assert max(residual)<5,(path,'marker grid distorted',residual.tolist())
    assert .35<scale<2.5
    result={};report=[]
    for p,marker in zip(batch['poses'],points):
        cell=p['cell'];tw,th=batch['tile_size']
        top_left=np.array([cell%batch['columns']*tw,340+cell//batch['columns']*th])*scale+shift
        bottom_right=top_left+np.array([tw,th])*scale
        box=np.rint([*top_left,*bottom_right]).astype(int)
        padding=math.ceil(batch.get('horizontal_crop_padding',0)*scale)
        box[0]=max(0,box[0]);box[1]=max(0,box[1]);box[2]=min(a.shape[1],box[2]);box[3]=min(a.shape[0],box[3])
        l,t,r,b=box
        if cell//batch['columns']==0:
            candidates=[y for y in range(max(0,t-8),min(t+12,b)) if green[y,l:r].mean()>.985]
            assert candidates,(path,cell,'top green gutter missing')
            t=max(t,candidates[0])
        if padding:
            # Use actual empty gutters around a nominal cell boundary. A wide
            # robe may cross the nominal line without touching its neighbour.
            clear_columns=(green[t:b]|pink[t:b]).all(axis=0)
            boundaries=[]
            for edge in (l,r):
                lo=max(0,edge-padding);hi=min(a.shape[1],edge+padding+1)
                candidates=np.flatnonzero(clear_columns[lo:hi])+lo
                assert len(candidates),(path,cell,'no clear robe gutter',edge)
                boundaries.append(int(min(candidates,key=lambda x:abs(x-edge))))
            l,r=boundaries
        cell_a=a[t:b,l:r].copy();key=green[t:b,l:r]|pink[t:b,l:r]
        cell_a[key]=0
        groups=sorted(components(cell_a[:,:,3]>0),key=len,reverse=True)
        assert groups and len(groups[0])>1000,(path,cell,'body missing')
        # Never silently erase disconnected fingers or body pieces.
        detached=[len(g) for g in groups[1:] if len(g)>=max(10,len(groups[0])*.0008)]
        keep=np.zeros(key.shape,bool)
        for gi,g in enumerate(groups):
            if gi==0 or len(g)>=max(10,len(groups[0])*.0008):keep[g[:,0],g[:,1]]=True
        cell_a[~keep]=0
        im=Image.fromarray(cell_a);bounds=im.getbbox();assert bounds
        assert bounds[0]>0 and bounds[1]>0 and bounds[2]<im.width and bounds[3]<im.height,(path,cell,'clipped')
        im=im.crop(bounds)
        local_marker=marker-np.array([l+bounds[0],t+bounds[1]])
        factor=1/scale
        fitted=im.transform((math.ceil(im.width*factor),math.ceil(im.height*factor)),Image.Transform.AFFINE,(scale,0,0,0,scale,0),resample=Image.Resampling.NEAREST)
        source_marker=(np.array(p['head_anchor_in_source'])+batch['marker_offset_native'])*4
        offset=np.rint(source_marker-local_marker*factor).astype(int)
        adjustments=work/'registration-adjustments.json'
        manual=None
        if adjustments.exists():
            manual=next((r for r in json.loads(adjustments.read_text(encoding='utf8')) if r['sex']==batch['sex'] and r['sprite']==p['sprite'] and r['source_sha256']==sha(path)),None)
            if manual:
                assert sha(path)==manual['source_sha256']
                f=manual['whole_pose_scale'];fitted=fitted.resize((round(fitted.width*f),round(fitted.height*f)),Image.Resampling.NEAREST)
                offset=np.array(manual['offset_4x'])
        dst=work/'whole-frames'/batch['sex']/f"sprite-{p['sprite']:03d}.png";dst.parent.mkdir(parents=True,exist_ok=True);fitted.save(dst)
        result[p['sprite']]=(fitted,offset)
        report.append(dict(sprite=p['sprite'],source=str(path.relative_to(work)),source_sha256=sha(path),marker=marker.tolist(),uniform_scale=factor,marker_residual=float(residual[cell]),offset_4x=offset.tolist(),source_size=p['source_size'],art_size=list(fitted.size),whole_pose_registration_adjustment=manual,detached_component_sizes=detached,removed_speck_pixels=sum(len(g) for g in groups[1:] if len(g)<max(10,len(groups[0])*.0008))))
    return result,report


def build(sex,partial=False):
    plan=json.loads((WORK/'art-plan.json').read_text(encoding='utf8'))
    context=native_context('swordman',sex);src,native_spr,native,_,_=context
    old_images=read_spr((WALK/f'assets/{sex}-angel-walk-v8.spr').read_bytes());old_act=read_act((WALK/f'assets/{sex}-angel-walk-v8.act').read_bytes())
    art={};imports=[];missing=[]
    for batch in plan['batches']:
        if batch['sex']!=sex:continue
        if not (WORK/'art'/sex/(batch['name']+'.png')).exists():missing.append(batch['name']);continue
        assert sha(src/'body.spr')==batch['source_spr_sha256'] and sha(src/'body.act')==batch['source_act_sha256']
        images,report=extract(batch);art.update(images);imports+=report
    corrections=WORK/'correction-plan.json'
    if corrections.exists():
        for batch in json.loads(corrections.read_text(encoding='utf8'))['batches']:
            if batch['sex']!=sex:continue
            assert (WORK/'art'/sex/(batch['name']+'.png')).exists()
            corrected,rows=extract(batch)
            art.update(corrected)
            imports=[r for r in imports if r['sprite'] not in corrected]+rows
    if missing and not partial:raise ValueError(('missing full pose sheets',sex,missing))
    act=copy.deepcopy(native);images=[];seen={};custom=0;stock=[];walk=0
    def index(im):
        key=(im.size,im.tobytes())
        if key not in seen:seen[key]=len(images);images.append(im)
        return seen[key]
    for ai,frames in enumerate(act.actions):
        for fi,f in enumerate(frames):
            if 8<=ai<16:
                f.layers=copy.deepcopy(old_act.actions[ai][fi].layers)
                for l in f.layers:
                    if l.index>=0:l.index=index(old_images[l.index])
                walk+=1;continue
            pieces=[];is_custom=True
            for l in native.actions[ai][fi].layers:
                if l.index<0:continue
                raw=rgba(native_spr,l.index,l.kind)
                if l.index in art:
                    im,offset=art[l.index];dx,dy=map(int,offset)
                    if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);dx=raw.width*4-im.width-dx
                else:
                    is_custom=False
                    im=raw.resize((raw.width*4,raw.height*4),Image.Resampling.NEAREST);dx=dy=0
                    if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                pieces.append((im,(l.x-raw.width//2)*4+dx,(l.y-raw.height//2)*4+dy))
            im,x,y=bake(pieces);f.layers=[Layer(x,y,index(im),sx=.25,sy=.25)]
            if is_custom:custom+=1
            else:stock.append([ai,fi])
    folder=WORK/'assets';folder.mkdir(exist_ok=True);stem=folder/f'{sex}-angel-complete-v9'
    sb,ab=write_spr(images),write_act(act);stem.with_suffix('.spr').write_bytes(sb);stem.with_suffix('.act').write_bytes(ab)
    decoded=read_spr(sb);reopened=read_act(ab);independent=Spr(sb)
    assert reopened.speeds==native.speeds and reopened.tail==native.tail and len(reopened.actions)==104
    for i,im in enumerate(decoded):assert im.tobytes()==rgba(independent,i,1).tobytes()
    for ai,fs in enumerate(reopened.actions):
        assert len(fs)==len(native.actions[ai])
        for fi,f in enumerate(fs):
            n=native.actions[ai][fi];assert (f.anchors,f.sound,f.ranges)==(n.anchors,n.sound,n.ranges)
            for l in f.layers:assert 0<=l.index<len(decoded)
            if 8<=ai<16:
                a,x,y=composite(old_images,old_act.actions[ai][fi]);b,bx,by=composite(decoded,f)
                assert (a.size,x,y)==(b.size,bx,by) and a.tobytes()==b.tobytes(),(ai,fi,'accepted walk changed')
    report=dict(sex=sex,status='Complete artwork review' if not stock else 'Work in progress, not deliverable',actions=104,frame_uses=sum(map(len,reopened.actions)),new_unique_native_drawings=len(art),new_nonwalk_frame_uses=custom,accepted_walk_frame_uses=walk,accepted_walk_pixels_and_placement_identical=True,native_metadata_preserved=True,independent_decoder_match=True,stock_fallback_frames=stock,missing_sheets=missing,imports=imports,detached_artwork_flags=[dict(sprite=r['sprite'],sizes=r['detached_component_sizes']) for r in imports if r['detached_component_sizes']],files=[dict(path=str(p.relative_to(WORK)),sha256=sha(p)) for p in (stem.with_suffix('.spr'),stem.with_suffix('.act'))],installed_files_modified=False)
    (WORK/f'{sex}-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('imports','stock_fallback_frames')}))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sex',required=True,choices=['male','female']);p.add_argument('--partial',action='store_true');args=p.parse_args();build(args.sex,args.partial)
