"""Fit visible wing roots to each posed upper back for idle and walking.

Body artwork, native head anchors, timings, sounds and non-locomotion actions
are preserved. Wing components move as rigid pieces; no feather resampling.
The front idle masters are retained exactly.
"""
from pathlib import Path
import copy
import hashlib
import json
import math
import struct
import numpy as np
from PIL import Image, ImageDraw
from audit_clan_wing_attachment import ROOT, OUT, load, draw_body
from bake_clan_body_frames import composite
from sprite_formats import Layer, write_act, write_spr, read_act, read_spr


def rendered(image, layer):
    if layer.mirror:
        image=image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if layer.angle:
        image=image.rotate(-layer.angle,Image.Resampling.NEAREST,expand=True)
    return image, (layer.x*4-image.width//2,layer.y*4-image.height//2)


def wing_parts(image):
    alpha=np.asarray(image)[:,:,3] >= 128
    live=np.flatnonzero(alpha.any(axis=0))
    # Pair images contain a genuine horizontal gap; single wings do not.
    gaps=[x for x in range(int(live[0])+1,int(live[-1])) if not alpha[:,x].any()]
    split=min(gaps,key=lambda x:abs(x-image.width/2)) if gaps else None
    cuts=[(0,split),(split,image.width)] if split is not None else [(0,image.width)]
    result=[]
    for left,right in cuts:
        part=image.crop((left,0,right,image.height))
        bbox=part.getbbox()
        if bbox:
            result.append((part.crop(bbox),(left+bbox[0],bbox[1])))
    return result


def compose_adjusted(images, frame, count, sex, direction):
    body=next(l for l in frame.layers if 0<=l.index<count)
    bi,(bx,by)=rendered(images[body.index],body)
    ba=np.asarray(bi)[:,:,3]>=128
    ys,xs=np.where(ba)
    top=int(ys.min())
    depth=10 if sex=='male' else (14 if direction in (3,4,5) else 11)
    mount_y=top+depth*4
    band=ba[max(0,mount_y-4):min(bi.height,mount_y+5)]
    edge=np.flatnonzero(band.any(axis=0))
    assert len(edge)>8,(sex,direction,body.index)
    lo,hi=int(edge[0])+bx,int(edge[-1])+bx
    mid=(lo+hi)/2
    near_left,near_right=lo+8,hi-8
    if direction in (3,5):
        targets=([mid,near_right] if direction==3 else [near_left,mid])
    elif direction==4:
        targets=[mid-14,mid+14]
    else:
        targets=[near_left,near_right]
    pieces=[]; rows=[]
    for layer in frame.layers:
        if layer.index<0:
            continue
        part,(px,py)=rendered(images[layer.index],layer)
        is_wing=count<=layer.index<count+9 or layer.index==count+10
        if not is_wing:
            pieces.append((part,px,py))
            continue
        parts=wing_parts(part)
        for pi,(wing,(ox,oy)) in enumerate(parts):
            right=(pi==1 if len(parts)==2 else direction in (0,1,2,3,4))
            alpha=np.asarray(wing)[:,:,3]>=128
            # Feather root: inner contour in the upper third, hidden just
            # beneath the pauldron/back. The complete feather tips are retained.
            ry=round(wing.height*.28)
            strip=alpha[max(0,ry-3):min(wing.height,ry+4)]
            xx=np.flatnonzero(strip.any(axis=0))
            assert len(xx)
            rx=int(xx[0]+min(4,len(xx)//3)) if right else int(xx[-1]-min(4,len(xx)//3))
            tx=targets[1 if right else 0]
            ty=by+mount_y
            valid_x=np.flatnonzero(ba[mount_y])
            assert len(valid_x)
            tx=int(valid_x[np.argmin(np.abs(valid_x-(tx-bx)))])+bx
            new_x=round(tx-rx)
            new_y=round(ty-ry)
            old_x,old_y=px+ox,py+oy
            pieces.append((wing,new_x,new_y))
            # Root sits inside the upper-back silhouette, not beside empty air.
            ix,iy=round(tx-bx),round(ty-by)
            assert ba[iy,ix],(sex,direction,body.index,ix,iy)
            rows.append(dict(wing=layer.index,component=pi,root_source=[rx,ry],
                             mount_world_4x=[round(tx),round(ty)],
                             translation_4x=[new_x-old_x,new_y-old_y],root_inside_body=True))
    left=math.floor(min(x for _,x,_ in pieces)/8)*8
    top=math.floor(min(y for _,_,y in pieces)/8)*8
    right=math.ceil(max(x+i.width for i,x,_ in pieces)/8)*8
    bottom=math.ceil(max(y+i.height for i,_,y in pieces)/8)*8
    canvas=Image.new('RGBA',(right-left,bottom-top))
    for part,x,y in pieces:
        canvas.alpha_composite(part,(x-left,y-top))
    return canvas,(left+right)//8,(top+bottom)//8,rows


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    records=[]
    for sex,korean in [('male','남'),('female','여')]:
        images,act,native,heads,ha=load(sex)
        count=len(native.images)
        world,preview=copy.deepcopy(act),copy.deepcopy(act)
        large,small,seen=[],[],{}
        rows=[]; display={}
        for ai,frames in enumerate(act.actions):
            for fi,frame in enumerate(frames):
                change=1<=ai<16
                if change:
                    im,x,y,parts=compose_adjusted(images,frame,count,sex,ai%8)
                    rows.append(dict(action=ai,frame=fi,parts=parts))
                else:
                    im,x,y=composite(images,frame)
                key=(im.size,hashlib.sha256(im.tobytes()).hexdigest())
                if key not in seen:
                    seen[key]=len(large);large.append(im)
                    small.append(im.convert('RGBa').resize((im.width//4,im.height//4),Image.Resampling.LANCZOS).convert('RGBA'))
                index=seen[key]
                world.actions[ai][fi].layers=[Layer(x,y,index,sx=.25,sy=.25)]
                preview.actions[ai][fi].layers=[Layer(x,y,index)]
                for new in (world.actions[ai][fi],preview.actions[ai][fi]):
                    assert new.anchors==frame.anchors and new.sound==frame.sound and new.ranges==frame.ranges
                if ai<16:
                    display[ai,fi]=(im,x,y)
        for variant,data,drawings in [('world',world,large),('preview',preview,small)]:
            folder=OUT/f'data/sprite/clan_skins/1/{"preview/" if variant=="preview" else ""}인간족/몸통/{korean}'
            folder.mkdir(parents=True,exist_ok=True)
            stem=folder/f'검사_{korean}'
            ab,sb=write_act(data),write_spr(drawings)
            stem.with_suffix('.act').write_bytes(ab);stem.with_suffix('.spr').write_bytes(sb)
            decoded=read_act(ab);decoded_images=read_spr(sb)
            assert decoded.tail==act.tail and len(decoded.actions)==104
            assert sum(map(len,decoded.actions))==456
            assert all(a.size==b.size and a.tobytes()==b.tobytes() for a,b in zip(decoded_images,drawings))
            # Unedited actions reproduce the installed v8 world pixels and
            # coordinates exactly, even if deduplication changes sprite IDs.
            oldfolder=ROOT/f'Outputs/clan-body-skins/native-collar-v8/data/sprite/clan_skins/1/{"preview/" if variant=="preview" else ""}인간족/몸통/{korean}'
            oldact=read_act((oldfolder/f'검사_{korean}.act').read_bytes())
            oldimages=read_spr((oldfolder/f'검사_{korean}.spr').read_bytes())
            preserved=0
            for ai,frames in enumerate(decoded.actions):
                for fi,f in enumerate(frames):
                    assert f.anchors==oldact.actions[ai][fi].anchors
                    if not 1<=ai<16:
                        old=oldact.actions[ai][fi].layers[0];new=f.layers[0]
                        assert (new.x,new.y,new.sx,new.sy)==(old.x,old.y,old.sx,old.sy)
                        assert drawings[new.index].tobytes()==oldimages[old.index].tobytes()
                        preserved+=1
            records.append(dict(sex=sex,variant=variant,frames=456,images=len(drawings),
                                modified_frames=len(rows),preserved_frames=preserved,
                                original_body_and_head_coordinates=True,
                                spr_sha256=hashlib.sha256(sb).hexdigest(),act_sha256=hashlib.sha256(ab).hexdigest()))
        (OUT/f'{sex}-root-registration.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
        board=Image.new('RGB',(8*180,8*250),'#364451');pen=ImageDraw.Draw(board)
        for ai in range(8,16):
            for fi,frame in enumerate(world.actions[ai]):
                tile=draw_body(large,frame,(180,250),3)
                board.paste(tile,(fi*180,(ai-8)*250),tile)
                pen.text((fi*180+5,(ai-8)*250+5),f'{sex} A{ai} F{fi}',fill='white')
        board.save(OUT/f'{sex}-walk-after.png')
        print(sex, len(rows),'fitted idle/walk frames',flush=True)
    (OUT/'verification.json').write_text(json.dumps(records,indent=2),encoding='utf8')


if __name__=='__main__':
    main()
