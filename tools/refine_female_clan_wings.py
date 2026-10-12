"""Female v10: complete far wing and mirrored, balanced rear pair.

Build from the existing detailed female feather artwork. Male files and all
non-idle/non-walk female frames are copied/preserved from v9. Wing roots track
the posed torso; no head coordinates or body drawing pixels are edited.
"""
import copy
import hashlib
import json
import math
import shutil
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from audit_clan_wing_attachment import ROOT, load
from fit_clan_walk_wings import rendered
from sprite_formats import Layer, read_act, read_spr, write_act, write_spr, anchor
from render_clan_wing_review import render

BASE=ROOT/'Outputs/clan-body-skins/wing-attachment-v9'
OUT=ROOT/'Outputs/clan-body-skins/female-wings-v10'


def resize(im, sx, sy):
    return im.convert('RGBa').resize((round(im.width*sx),round(im.height*sy)),Image.Resampling.LANCZOS).convert('RGBA')


def mask_at(image, x, y):
    result=np.zeros((640,640),bool)
    alpha=np.asarray(image)[:,:,3]>=128
    assert 0<=x and 0<=y and x+image.width<=640 and y+image.height<=640
    result[y:y+image.height,x:x+image.width]=alpha
    return result


def compose(images, frame, native, masks, direction, right_template):
    body=next(l for l in frame.layers if 0<=l.index<len(native.images))
    bi,(bx,by)=rendered(images[body.index],body)
    ba=np.asarray(bi)[:,:,3]>=128
    neck_mask=masks[body.index]
    if body.mirror:neck_mask=neck_mask.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    neck=neck_mask.getbbox()
    # The neck mask locates the spine without including a raised pauldron in
    # the left/right silhouette average.
    spine=bx+(neck[0]+neck[2])/2
    top=int(np.where(ba)[0].min())
    is_back=direction in (3,4,5)
    mount_y=top+(12 if is_back else 9)*4
    valid=np.flatnonzero(ba[mount_y])
    assert len(valid)>12
    lo,hi=bx+int(valid[0]),bx+int(valid[-1])
    ty=by+mount_y
    right=right_template
    left=right.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if direction==0:
        # A full mirrored feather replaces the previous sliver. The far wing
        # remains slightly shorter but must read outside the left shoulder.
        left=resize(left,.90,.90)
        mounts=[lo+4,hi-4]
        wings=[(left,False),(right,True)]
    elif direction in (1,7):
        if direction==1:
            wings=[(resize(left,.68,.82),False),(right,True)]
        else:
            wings=[(left,False),(resize(right,.68,.82),True)]
        mounts=[lo+4,hi-4]
    elif direction in (2,6):
        wings=[(resize(right if direction==2 else left,.82,1),direction==2)]
        mounts=[hi-4] if direction==2 else [lo+4]
    elif direction==4:
        # Identical mirrored masters at equal-height mounts: no rightward lean.
        wings=[(left,False),(right,True)]
        mounts=[spine-14,spine+14]
    else:
        # Perspective changes width, never makes both leaves point right.
        wings=([(resize(left,.72,.90),False),(right,True)] if direction==3 else
               [(left,False),(resize(right,.72,.90),True)])
        mounts=([spine-7,spine+16] if direction==3 else [spine-16,spine+7])
    parts=[];records=[]
    bodymask=mask_at(bi,320+bx,400+by)
    for i,((wing,is_right),tx) in enumerate(zip(wings,mounts)):
        alpha=np.asarray(wing)[:,:,3]>=128
        ry=round(wing.height*.28)
        edge=np.flatnonzero(alpha[max(0,ry-3):ry+4].any(axis=0))
        rx=int(edge[0])+4 if is_right else int(edge[-1])-4
        tx=int(valid[np.argmin(np.abs(valid-(tx-bx)))])+bx
        wx,wy=round(tx-rx),round(ty-ry)
        wm=mask_at(wing,320+wx,400+wy)
        overlap=int(np.count_nonzero(wm & bodymask))
        for _ in range(8):
            if overlap>=96:break
            shift=-1 if is_right else 1
            wx+=shift;tx+=shift
            wm=mask_at(wing,320+wx,400+wy)
            overlap=int(np.count_nonzero(wm & bodymask))
        visible=int(np.count_nonzero(wm & ~bodymask))
        assert overlap>=64,(direction,body.index,i,'no root overlap',overlap)
        if direction==0:
            assert visible>=450,(body.index,i,'front wing hidden',visible)
        parts.append((wing,wx,wy))
        records.append(dict(side='right' if is_right else 'left',mount=[tx,ty],
                            root=[rx,ry],body_overlap_4x=overlap,visible_outside_body_4x=visible,
                            size=list(wing.size)))
    if direction==4:
        assert wings[0][0].tobytes()==wings[1][0].transpose(Image.Transpose.FLIP_LEFT_RIGHT).tobytes()
        assert records[0]['mount'][1]==records[1]['mount'][1]
    # Front roots tuck behind shoulder armor. On the back, feathers lie over
    # the backplate as in the accepted design. Original body/halo pixels stay.
    ordered=parts+[(bi,bx,by)] if not is_back else [(bi,bx,by)]+parts
    for layer in frame.layers:
        if layer.index==len(native.images)+9:
            im,(x,y)=rendered(images[layer.index],layer)
            ordered.append((im,x,y))
    left_bound=math.floor(min(x for _,x,_ in ordered)/8)*8
    top_bound=math.floor(min(y for _,_,y in ordered)/8)*8
    right_bound=math.ceil(max(x+im.width for im,x,_ in ordered)/8)*8
    bottom_bound=math.ceil(max(y+im.height for im,_,y in ordered)/8)*8
    merged=Image.new('RGBA',(right_bound-left_bound,bottom_bound-top_bound))
    for im,x,y in ordered:merged.alpha_composite(im,(x-left_bound,y-top_bound))
    return merged,(left_bound+right_bound)//8,(top_bound+bottom_bound)//8,records


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    images,source,native,heads,ha,masks=load('female',True)
    # Slot 123 is a complete repaired female wing, unlike the tiny cropped
    # far-wing fragment in slot 122 or the same-handed rear pair in 125/126.
    template=images[123]
    template=template.crop(template.getbbox())
    template.save(OUT/'right-wing-master.png')
    template.transpose(Image.Transpose.FLIP_LEFT_RIGHT).save(OUT/'left-wing-master.png')
    base_stem=BASE/'data/sprite/clan_skins/1/인간족/몸통/여/검사_여'
    original=read_act(base_stem.with_suffix('.act').read_bytes())
    old_images=read_spr(base_stem.with_suffix('.spr').read_bytes())
    world,preview=copy.deepcopy(original),copy.deepcopy(original)
    large=[];small=[];seen={};records=[]
    for ai,frames in enumerate(source.actions):
        for fi,frame in enumerate(frames):
            if ai<16:
                im,x,y,roots=compose(images,frame,native,masks,ai%8,template)
                records.append(dict(action=ai,frame=fi,roots=roots))
            else:
                old=original.actions[ai][fi].layers[0]
                im,x,y=old_images[old.index],old.x,old.y
            key=(im.size,hashlib.sha256(im.tobytes()).hexdigest())
            if key not in seen:
                seen[key]=len(large);large.append(im)
                small.append(im.convert('RGBa').resize((im.width//4,im.height//4),Image.Resampling.LANCZOS).convert('RGBA'))
            index=seen[key]
            world.actions[ai][fi].layers=[Layer(x,y,index,sx=.25,sy=.25)]
            preview.actions[ai][fi].layers=[Layer(x,y,index)]
    verify=[]
    for variant,act,drawings in [('world',world,large),('preview',preview,small)]:
        rel=f'data/sprite/clan_skins/1/{"preview/" if variant=="preview" else ""}인간족/몸통/여/검사_여'
        stem=OUT/rel;stem.parent.mkdir(parents=True,exist_ok=True)
        ab,sb=write_act(act),write_spr(drawings)
        stem.with_suffix('.act').write_bytes(ab);stem.with_suffix('.spr').write_bytes(sb)
        baseline=read_act((BASE/rel).with_suffix('.act').read_bytes())
        baseline_images=read_spr((BASE/rel).with_suffix('.spr').read_bytes())
        decoded=read_act(ab);reopened=read_spr(sb)
        assert decoded.tail==baseline.tail and len(decoded.actions)==104
        assert sum(map(len,decoded.actions))==456
        assert all(a.size==b.size and a.tobytes()==b.tobytes() for a,b in zip(drawings,reopened))
        preserved=0
        for ai,frames in enumerate(decoded.actions):
            for fi,new in enumerate(frames):
                old=baseline.actions[ai][fi]
                assert (new.anchors,new.sound,new.ranges)==(old.anchors,old.sound,old.ranges)
                if ai>=16:
                    a,b=new.layers[0],old.layers[0]
                    assert (a.x,a.y,a.sx,a.sy)==(b.x,b.y,b.sx,b.sy)
                    assert drawings[a.index].tobytes()==baseline_images[b.index].tobytes()
                    preserved+=1
        verify.append(dict(sex='female',variant=variant,updated_frames=len(records),preserved_frames=preserved,
                           spr_sha256=hashlib.sha256(sb).hexdigest(),act_sha256=hashlib.sha256(ab).hexdigest()))
    for path in (BASE/'data').rglob('*'):
        if path.is_file() and path.name.startswith('검사_남'):
            dest=OUT/path.relative_to(BASE);dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copyfile(path,dest)
            assert dest.read_bytes()==path.read_bytes()
    (OUT/'root-verification.json').write_text(json.dumps(records,indent=2),encoding='utf8')
    (OUT/'verification.json').write_text(json.dumps(dict(files=verify,male_files_byte_identical=True,
                                                       front_both_wings_visible=True,back_wings_mirrored=True,
                                                       body_head_anchors_and_timing_unchanged=True,live_acceptance='pending'),indent=2),encoding='utf8')
    render_review(old_images,original,large,world,heads,ha)
    print(json.dumps(verify))


def render_review(old_images,old,new_images,new,heads,ha):
    frames=[];durations=[]
    board=Image.new('RGB',(600,1000),'#283746');pen=ImageDraw.Draw(board)
    pen.text((12,10),'Female / previous',fill='white');pen.text((312,10),'Female / revised',fill='white')
    for row,direction in enumerate((0,4,3)):
        for col,(images,act) in enumerate(((old_images,old),(new_images,new))):
            tile=render(images,act,heads,ha,8+direction,0).resize((264,336),Image.Resampling.NEAREST)
            board.paste(tile,(col*300+18,row*320+30),tile)
            pen.text((col*300+12,row*320+40),('Front','Back','Rear quarter')[row],fill='white')
    board.save(OUT/'female-front-back-before-after.png')
    for direction in range(8):
        for cycle in range(2):
            for fi in range(8):
                tile=Image.new('RGB',(600,350),'#283746');pen=ImageDraw.Draw(tile)
                for col,(images,act,label) in enumerate(((old_images,old,'Previous'),(new_images,new,'Revised'))):
                    sprite=render(images,act,heads,ha,8+direction,fi)
                    tile.paste(sprite,(col*300+40,35),sprite)
                    pen.text((col*300+12,12),'Female / '+label,fill='white')
                pen.text((12,325),f'Walk direction {direction}, frame {fi+1}/8',fill='white')
                frames.append(tile);durations.append(round(new.speeds[8+direction]*25))
    frames[0].save(OUT/'female-walk-before-after.gif',save_all=True,append_images=frames[1:],duration=durations,loop=0,disposal=2)


if __name__=='__main__':
    build()
