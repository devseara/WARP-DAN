"""Review-only female revision using actual male collar pixels and native wings.

This does not alter the installed client or production asset builder. It
targets the reported neckline and left/right side views for visual review.
"""
import copy,hashlib,json,math
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from audit_clan_wing_attachment import ROOT,ART,load
from sprite_formats import Layer,read_act,read_spr,write_act,write_spr,anchor
from spr_reader import Spr
from fit_clan_walk_wings import rendered
from build_clan_all_actions import rotate_root
from refine_female_clan_wings import resize
from render_clan_all_action_review import render

OUT=ROOT/'Outputs/clan-body-skins/reference-review-v15'
BASE=ROOT/'Outputs/clan-body-skins/all-actions-v14'
POCKETS={56:(54,12,82,25),57:(56,11,85,25),58:(61,14,82,26),59:(58,17,80,25),60:(51,15,79,26),61:(58,17,82,26)}


def chin(heads,ha,frame,ai,fi):
    hf=ha.actions[ai][fi];h=next(l for l in hf.layers if l.index>=0)
    im=heads.images[h.index];p=np.frombuffer(im.pixels,np.uint8).reshape(im.height,im.width)
    if h.mirror:p=p[:,::-1]
    mask=(p>=130)&(p<=135);ys,xs=np.where(mask)
    assert len(xs)>0
    bottom=int(ys.max());xx=np.flatnonzero(mask[bottom])
    bx,by=anchor(frame);hx,hy=anchor(hf)
    return np.array([h.x+bx-hx-im.width//2+float(xx.mean())+.5,h.y+by-hy-im.height//2+bottom+1])


def transfer_male_collar(images,act,native,heads,ha):
    male,ma,mn,mh,mha=load('male')
    result=list(images);records=[]
    for fi in range(6):
        f=act.actions[32][fi];mf=ma.actions[32][fi]
        b=next(l for l in f.layers if 0<=l.index<len(native.images))
        mb=next(l for l in mf.layers if 0<=l.index<len(mn.images))
        target=images[b.index];donor=male[mb.index]
        female_chin=chin(heads,ha,f,32,fi);male_chin=chin(mh,mha,mf,32,fi)
        shift=female_chin-male_chin
        target_left=np.array([b.x-target.width/8,b.y-target.height/8])
        donor_left=np.array([mb.x-donor.width/8,mb.y-donor.height/8])+shift
        placement=np.rint((donor_left-target_left)*4).astype(int)
        patch=Image.new('RGBA',target.size);patch.alpha_composite(donor,tuple(placement))
        l,t,r,bottom=POCKETS[b.index]
        polygon=[(l-8,0),(r+8,0),(r+12,t+8),(r+10,bottom+10),
                 (l-7,bottom+10),(l-12,t+8)]
        mask=Image.new('L',target.size);ImageDraw.Draw(mask).polygon(polygon,fill=255)
        a=np.array(target);p=np.array(patch);selection=np.asarray(mask)>0
        # Keep the female chest jewel; the donor is the neckline, not a second
        # jewel or a male torso replacement.
        rgb=p[:,:,:3].astype(int)
        jewel=(rgb[:,:,2]-rgb[:,:,0]>35)&(rgb[:,:,1]-rgb[:,:,0]>25)
        # Transfer the matching male brooch with the rim, clearing the old
        # female brooch beneath it so there is one coherent neckline.
        trgb=a[:,:,:3].astype(int)
        target_jewel=(trgb[:,:,2]-trgb[:,:,0]>35)&(trgb[:,:,1]-trgb[:,:,0]>25)&(a[:,:,3]>128)
        target_jewel[80:]=False
        jewel[80:]=False
        jy,jx=np.where(jewel|target_jewel)
        if len(jx):
            selection[max(0,int(jy.min())-6):min(a.shape[0],int(jy.max())+8),
                      max(0,int(jx.min())-7):min(a.shape[1],int(jx.max())+8)]=True
        before=a.copy();a[selection]=p[selection]
        assert np.array_equal(a[~selection],before[~selection])
        result[b.index]=Image.fromarray(a)
        records.append(dict(female_body=b.index,male_body=mb.index,donor_translation_4x=placement.tolist(),
                            female_chin=female_chin.tolist(),male_chin=male_chin.tolist(),
                            pixels_from_male=int(selection.sum()),outside_collar_unchanged=True))
    return result,records


def bake(pieces):
    l=math.floor(min(x for _,x,_ in pieces)/8)*8;t=math.floor(min(y for _,_,y in pieces)/8)*8
    r=math.ceil(max(x+i.width for i,x,_ in pieces)/8)*8;b=math.ceil(max(y+i.height for i,_,y in pieces)/8)*8
    im=Image.new('RGBA',(r-l,b-t))
    for part,x,y in pieces:im.alpha_composite(part,(x-l,y-t))
    return im,(l+r)//8,(t+b)//8


def existing_wings(images,record):
    near=images[123];near=near.crop(near.getbbox());left=near.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    d=record['basis_direction']
    assert d in (1,7)
    templates=([resize(left,.68,.82),near] if d==1 else [left,resize(near,.68,.82)])
    pieces=[]
    for template,part in zip(templates,record['wings']):
        a=np.asarray(template)[:,:,3]>=128;ry=round(template.height*.28)
        edge=np.flatnonzero(a[max(0,ry-3):ry+4].any(axis=0))
        rx=int(edge[0])+4 if part['side']=='right' else int(edge[-1])-4
        template,root=rotate_root(template,(rx,ry),part['angle'])
        pos=np.rint(np.array(part['mount'])-root).astype(int)
        pieces.append((template,int(pos[0]),int(pos[1])))
    return pieces


def side_wing(images,frame,original_spr,original_act,ai,fi):
    body=next(l for l in frame.layers if 0<=l.index<122)
    bi,(bx,by)=rendered(images[body.index],body)
    alpha=np.asarray(bi)[:,:,3]>=128
    wl=original_act.actions[ai][fi].layers[0]
    raw,w,h=original_spr.get_rgba(wl.index,0)
    # Original native sprite/ACT establishes the facing. Preserve the accepted
    # concept's side feathers at full width instead of substituting garment art
    # or squeezing a front-facing feather into a narrow strip.
    wing=Image.open(ART/'female-wing-repair-v08/clean-side-wing.png').convert('RGBA')
    wa=np.asarray(wing)[:,:,3]>=128
    ry=28
    edge=np.flatnonzero(wa[ry-3:ry+4].any(axis=0))
    root=np.array([int(edge[0])+4,ry],float)
    if body.mirror:
        wing=wing.transpose(Image.Transpose.FLIP_LEFT_RIGHT);root[0]=wing.width-1-root[0]
    row=int(np.where(alpha)[0].min())+24
    valid=np.flatnonzero(alpha[row])
    assert len(valid)>5
    tx=bx+int(valid[0]+6 if body.mirror else valid[-1]-6)
    ty=by+row
    pos=np.rint(np.array([tx,ty])-root).astype(int)
    # Native side/profile art sits on the back. The front-quarter sword pose
    # retains foreground armor occlusion; left/right follow the body mirror.
    front_quarter=False
    pieces=[(wing,int(pos[0]),int(pos[1])),(bi,bx,by)] if front_quarter else [(bi,bx,by),(wing,int(pos[0]),int(pos[1]))]
    for layer in frame.layers:
        if layer.index==131:
            im,(x,y)=rendered(images[layer.index],layer);pieces.append((im,x,y))
    return (*bake(pieces),dict(native_sprite=wl.index,native_size=[w,h],scaled_size=list(wing.size),artwork_source="accepted female side wing",
                             body_mirror=body.mirror,mount_4x=[tx,ty],native_act_transform=vars(wl)))


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    images,source,native,heads,ha=load('female')
    images,collars=transfer_male_collar(images,source,native,heads,ha)
    stem=BASE/'data/sprite/clan_skins/1/인간족/몸통/여/검사_여'
    old=read_act(stem.with_suffix('.act').read_bytes());oldimages=read_spr(stem.with_suffix('.spr').read_bytes())
    roots=json.loads((BASE/'female-all-action-roots.json').read_text());roots={(r['action'],r['frame']):r for r in roots}
    original_spr=Spr((ART/'production-v02/source/female-wing.spr').read_bytes())
    original_act=read_act((ART/'production-v02/source/female-wing.act').read_bytes())
    act=copy.deepcopy(old);new_images=[];seen={};changes=[]
    sides=(2,6,10,14,34,35,36,37)
    for ai,frames in enumerate(source.actions):
        for fi,f in enumerate(frames):
            if ai in sides:
                im,x,y,detail=side_wing(images,f,original_spr,original_act,ai,fi)
                changes.append(dict(action=ai,frame=fi,type='native-side-profile',**detail))
            elif ai in (32,33,38,39):
                pieces=existing_wings(images,roots[ai,fi])
                body=next(l for l in f.layers if 0<=l.index<122)
                bi,(bx,by)=rendered(images[body.index],body);pieces.append((bi,bx,by))
                halo=next(l for l in f.layers if l.index==131);part,(hx,hy)=rendered(images[131],halo);pieces.append((part,hx,hy))
                im,x,y=bake(pieces);changes.append(dict(action=ai,frame=fi,type='male-collar-pixels'))
            else:
                l=old.actions[ai][fi].layers[0];im,x,y=oldimages[l.index],l.x,l.y
            key=(im.size,hashlib.sha256(im.tobytes()).hexdigest())
            if key not in seen:seen[key]=len(new_images);new_images.append(im)
            act.actions[ai][fi].layers=[Layer(x,y,seen[key],sx=.25,sy=.25)]
    folder=OUT/'candidate';folder.mkdir(exist_ok=True)
    (folder/'female-reference-preview.spr').write_bytes(write_spr(new_images))
    (folder/'female-reference-preview.act').write_bytes(write_act(act))
    (OUT/'reference-revision.json').write_text(json.dumps(dict(status='PREVIEW ONLY; not installed',male_collar_sources=collars,changes=changes),indent=2),encoding='utf8')
    review(oldimages,old,new_images,act,heads,ha)


def review(oldimages,old,newimages,new,heads,ha):
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    male,ma,mn,mh,mha=load('male')
    board=Image.new('RGB',(900,690),'#283746');p=ImageDraw.Draw(board)
    for col,(images,act,hs,hact,ai,label) in enumerate([(male,ma,mh,mha,32,'Actual male collar reference'),(oldimages,old,heads,ha,32,'Rejected female collar'),(newimages,new,heads,ha,32,'Female / male collar pixels')]):
        im=render(images,act,hs,hact,ai,0);board.paste(im,(col*300,35),im);p.text((col*300+8,10),label,font=font,fill='white')
        crop=im.crop((100,75,200,175)).resize((260,260),Image.Resampling.NEAREST);board.paste(crop,(col*300+20,390),crop)
    board.save(OUT/'collar-donor-comparison.png')
    board=Image.new('RGB',(600,4*320),'#283746');p=ImageDraw.Draw(board)
    for row,ai in enumerate([2,6,34,36]):
        for col,(ims,act,label) in enumerate([(oldimages,old,'Current'),(newimages,new,'Native-facing / accepted art')]):
            im=render(ims,act,heads,ha,ai,0);board.paste(im,(col*300,row*320+20),im)
            p.text((col*300+8,row*320+4),f'{label} / action {ai}',font=font,fill='white')
    board.save(OUT/'side-wings-before-after.png')
    frames=[]
    for ai in [32,33,34,35,36,37,38,39,2,6,10,14]:
        for repeat in range(2):
            for fi in range(len(new.actions[ai])):
                im=Image.new('RGB',(600,340),'#283746');p=ImageDraw.Draw(im)
                for col,(ims,act,label) in enumerate([(oldimages,old,'Current'),(newimages,new,'Reference-based preview')]):
                    tile=render(ims,act,heads,ha,ai,fi);im.paste(tile,(col*300,25),tile);p.text((col*300+8,6),label,font=font,fill='white')
                p.text((8,321),f'Action {ai}, frame {fi} / PREVIEW ONLY',fill='white');frames.append(im)
    frames[0].save(OUT/'reference-revision-preview.gif',save_all=True,append_images=frames[1:],duration=160,loop=0,disposal=2)


if __name__=='__main__':build()
