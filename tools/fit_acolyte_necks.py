"""Register Acolyte head attachments without resampling any body artwork."""
import argparse,copy,hashlib,json,struct
import numpy as np
from PIL import Image
from acolyte_neck_registration import BASE,WORK,native_neck_target
from review_original_job_directions import native_context
from review_full_swordman_set import body,head,ORIGIN
from sprite_formats import read_spr,read_act,write_act,anchor


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ground(image,axis,band):
    yy,xx=np.where(np.asarray(image)[:,:,3]>128)
    points=np.stack((xx+.5-ORIGIN[0],yy+.5-ORIGIN[1]),axis=1)
    along=points@axis;perpendicular=np.array([axis[1],-axis[0]])
    return axis*along[along>=along.max()-7].mean()+perpendicular*(points[along>=along.max()-band]@perpendicular).mean()


def source_collar(row,frame,native,spr):
    first=native.actions[row['action']][row['frame']].layers[0]
    raw=spr.images[first.index]
    top=np.array([first.x-raw.width//2,first.y-raw.height//2])*4
    point=np.array(row['collar_point'],float)-top
    layer=frame.layers[0]
    if layer.mirror:point[0]=raw.width*4-point[0]
    return point+np.array([layer.x-raw.width//2,layer.y-raw.height//2])*4


def run():
    pins=WORK/'native-reference-pins.json'
    if pins.exists():
        from package_clan_skin_assets import ROOT
        for item in json.loads(pins.read_text(encoding='utf8')):
            assert digest(ROOT/item['path'])==item['sha256'],item['path']
    rejected=json.loads((BASE/'user-review.json').read_text(encoding='utf8'))
    for row in rejected['files']:assert digest(BASE/row['path'])==row['sha256']
    rows={(r['sex'],r['sprite']):r for r in json.loads((WORK/'landmark-proposals.json').read_text(encoding='utf8'))}
    for r in json.loads((WORK/'landmark-overrides.json').read_text(encoding='utf8')):rows[r['sex'],r['sprite']].update(r)
    reports=[];files=[];pending=[]
    for sex in ('male','female'):
        _,native_spr,native,_,_=native_context('acolyte',sex)
        stem=BASE/'assets'/f'{sex}-angel-acolyte-v1'
        raw=stem.with_suffix('.spr').read_bytes();images=read_spr(raw);old=read_act(stem.with_suffix('.act').read_bytes());act=copy.deepcopy(old)
        for ai,frames in enumerate(act.actions):
            for fi,frame in enumerate(frames):
                nf=native.actions[ai][fi];nl=nf.layers[0]
                collar=source_collar(rows[sex,nl.index],nf,native,native_spr)
                target=native_neck_target(sex,ai,fi)
                original=body(sex,ai,fi,job='acolyte');previous=body(sex,ai,fi,(images,old),job='acolyte')
                axis=np.array([0.,1.])
                yy,xx=np.where(np.asarray(original)[:,:,3]>128)
                if ai//8==8:
                    axis=np.array([xx.mean()+.5-ORIGIN[0],yy.mean()+.5-ORIGIN[1]])-target;axis/=np.linalg.norm(axis)
                span=np.stack((xx,yy),axis=1)@axis;band=min(60.,float(np.ptp(span))*.28)
                desired=ground(original,axis,band)-ground(previous,axis,band)
                root=np.rint(desired/4).astype(int)
                for layer in frame.layers:layer.x+=int(root[0]);layer.y+=int(root[1])
                head_delta=np.rint((collar+root*4-target)/4).astype(int)
                data=bytearray(frame.anchors[0]);before=anchor(frame)
                struct.pack_into('<ii',data,4,before[0]+int(head_delta[0]),before[1]+int(head_delta[1]));frame.anchors[0]=bytes(data)
                new_pair=images,act
                rendered=body(sex,ai,fi,new_pair,job='acolyte');shifted=Image.new('RGBA',previous.size);shifted.alpha_composite(previous,tuple((root*4).tolist()))
                assert rendered.tobytes()==shifted.tobytes(),(sex,ai,fi,'body pixels changed')
                h=head(sex,ai,fi,job='acolyte',pair=new_pair)
                joint=collar+root*4;tx,ty=np.rint(joint+ORIGIN).astype(int);region=(slice(max(0,ty-20),min(640,ty+21)),slice(max(0,tx-20),min(640,tx+21)))
                contacts=int(np.count_nonzero((np.asarray(h)[:,:,3]>0)[region]&(np.asarray(rendered)[:,:,3]>0)[region]))
                assert contacts>0,(sex,ai,fi,'head detached')
                assert frame.ranges==old.actions[ai][fi].ranges and frame.sound==old.actions[ai][fi].sound
                assert frame.anchors[0][:4]==old.actions[ai][fi].anchors[0][:4] and frame.anchors[0][12:]==old.actions[ai][fi].anchors[0][12:]
                assert frame.anchors[1:]==old.actions[ai][fi].anchors[1:]
                reports.append(dict(sex=sex,action=ai,frame=fi,native_sprite=nl.index,body_translation_native=root.tolist(),head_anchor_delta_native=head_delta.tolist(),collar_world_4x=joint.tolist(),head_neck_error_4x=float(np.linalg.norm(target+head_delta*4-joint)),head_neck_contact_pixels=contacts,body_pixels_preserved=True))
        assert act.speeds==old.speeds and act.tail==old.tail
        pending.append((sex,raw,write_act(act)))
    out=WORK/'assets';out.mkdir(exist_ok=True)
    for sex,spr,act in pending:
        for ext,raw in [('.spr',spr),('.act',act)]:
            path=out/f'{sex}-angel-acolyte-v2{ext}';path.write_bytes(raw);files.append(dict(sex=sex,path=path.relative_to(WORK).as_posix(),sha256=digest(path),bytes=len(raw)))
        reopened=read_act((out/f'{sex}-angel-acolyte-v2.act').read_bytes());assert len(reopened.actions)==104 and sum(map(len,reopened.actions))==456
        assert digest(out/f'{sex}-angel-acolyte-v2.spr')==digest(BASE/'assets'/f'{sex}-angel-acolyte-v1.spr')
    result=dict(status='attachment_offsets_verified',method='ACT-only body-root translation and head attachment correction; no image resampling',files=files,checked_frame_uses=len(reports),checks=reports,issues=[],installed=False)
    (WORK/'registration-verification.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps(dict(status=result['status'],frames=len(reports),max_attachment_error_native=max(r['head_neck_error_4x'] for r in reports)/4,files=files)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args();run()
