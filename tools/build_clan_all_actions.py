"""Apply accepted wing masters to every remaining Swordman action.

Torso landmarks were marked on the audit sheets, not inferred from raised
hands or head offsets. Rotations follow the torso in bent and fallen poses.
The installed v10 idle/walk pixels and all original animation metadata remain.
"""
import copy
import hashlib
import json
import math
import numpy as np
from PIL import Image,ImageDraw
from audit_clan_wing_attachment import ROOT,load
from fit_clan_walk_wings import rendered
from refine_female_clan_wings import resize
from sprite_formats import Layer,read_act,read_spr,write_act,write_spr

BASE=ROOT/'Outputs/clan-body-skins/female-wings-v10'
OUT=ROOT/'Outputs/clan-body-skins/all-actions-v14'

# Coordinates on the 5x5 audit sheets, in displayed pixels. Each marks the
# upper-back/spine level beneath the collar, excluding raised arms. Conversion
# below stores stable full-resolution coordinates in the verification report.
MARKS={
 'male':[
  [(90,62),(274,61),(461,64),(639,61),(815,63),(93,256),(274,257),(453,251),(632,251),(814,253),(90,442),(270,442),(451,441),(631,443),(811,443),(92,632),(272,632),(452,632),(632,632),(812,632),(90,822),(273,841),(453,839),(635,827),(815,827)],
  [(90,63),(270,63),(455,66),(635,66),(812,57),(94,247),(272,256),(450,257),(640,245),(812,256),(104,442),(287,480),(448,448),(626,444),(807,444),(86,635),(266,635),(455,636),(635,636),(815,636),(93,825),(273,825),(451,821),(630,821),(810,821)],
  [(92,64),(272,64),(452,64),(632,64),(810,54),(92,245),(271,245),(451,245),(631,245),(811,245),(90,437),(270,443),(450,443),(630,443),(810,443),(88,631),(269,631),(450,626),(630,626),(810,626),(92,815),(270,815),(450,815)]],
 'female':[
  [(88,59),(271,65),(451,65),(635,67),(811,63),(79,242),(259,242),(443,241),(638,252),(815,253),(88,446),(271,441),(451,441),(631,441),(811,441),(88,631),(268,631),(449,632),(629,632),(809,632),(90,823),(270,823),(450,823),(635,840),(815,840)],
  [(87,67),(269,66),(449,90),(629,90),(810,66),(90,255),(272,255),(451,256),(631,255),(811,255),(92,448),(271,450),(464,441),(643,451),(816,449),(91,636),(270,636),(452,642),(632,642),(812,642),(90,824),(270,824),(452,824),(630,833),(810,833)],
  [(91,69),(274,70),(453,70),(633,70),(813,70),(90,262),(270,260),(450,260),(634,259),(814,259),(89,450),(269,450),(449,450),(632,444),(812,444),(90,640),(270,640),(450,640),(630,640),(810,640),(89,830),(270,830),(450,830),(630,830),(810,830)],
  [(90,70),(270,70)]]}
ANGLES={'male':{52:15,53:15,68:-10,69:-10,70:8,71:8,72:-8,73:-8,78:30,79:-10,80:60,81:130},
        'female':{50:10,51:10,52:10,53:-15,54:-15,55:-15,80:25,81:-8,82:50,83:130,84:15,85:15,87:18,88:18,89:18}}


def landmarks(sex,images,count):
    result={};index=45
    for page in MARKS[sex]:
        for i,(x,y) in enumerate(page):
            im=images[index]
            ox=(i%5)*180+max(0,(180-im.width//2)//2)
            oy=(i//5)*190+30
            point=[2*(x-ox),2*(y-oy)]
            assert 0<=point[0]<im.width and 0<=point[1]<im.height,(sex,index,point,im.size)
            result[index]=dict(center=point,angle=ANGLES[sex].get(index,0))
            index+=1
    assert index==count,(sex,index,count)
    return result


def rotate_root(image,root,angle):
    if not angle:return image,np.array(root,float)
    out=image.rotate(-angle,Image.Resampling.NEAREST,expand=True)
    theta=math.radians(angle)
    matrix=np.array([[math.cos(theta),-math.sin(theta)],[math.sin(theta),math.cos(theta)]])
    p=matrix@(np.array(root)-np.array([(image.width-1)/2,(image.height-1)/2]))
    return out,p+np.array([(out.width-1)/2,(out.height-1)/2])


def compose(images,frame,count,rig,sex,group,facing=None):
    body=next(l for l in frame.layers if 0<=l.index<count)
    old_wing=next(l for l in frame.layers if count<=l.index<count+9)
    bi,(bx,by)=rendered(images[body.index],body)
    assert body.angle==0 and body.sx==body.sy==.25
    local=np.array(rig[body.index]['center'],float)
    angle=rig[body.index]['angle']
    if body.mirror:
        local[0]=bi.width-1-local[0];angle=-angle
    # Female combat annotations were at chest level. Raise the mount along
    # the torso axis, retaining the accepted idle/walk and fallen poses.
    lift=(32 if group==4 else 16 if group in (6,7) else 20) if sex=='female' and group in (4,5,6,7,9,10,11,12) else 0
    if lift:
        radians=math.radians(angle)
        local+=np.array([math.sin(radians),-math.cos(radians)])*lift
    alpha=np.asarray(bi)[:,:,3]>=128
    # Marked centers may land in a seam; snap at most a few source pixels to
    # the torso. This avoids attaching a root to transparent collar holes.
    py,px=np.where(alpha)
    distance=(px-local[0])**2+(py-local[1])**2
    nearest=int(np.argmin(distance))
    assert distance[nearest]<=24**2,(sex,body.index,'landmark outside torso')
    local=np.array([px[nearest],py[nearest]],float)
    center=local+np.array([bx,by])
    theta=math.radians(angle);axis=np.array([math.cos(theta),math.sin(theta)])
    offsets=np.arange(-56,57)
    points=np.rint(local[None,:]+offsets[:,None]*axis).astype(int)
    good=(points[:,0]>=0)&(points[:,0]<bi.width)&(points[:,1]>=0)&(points[:,1]<bi.height)
    occupied=np.zeros(len(offsets),bool)
    occupied[good]=alpha[points[good,1],points[good,0]]
    first=last=56
    while first>0 and occupied[first-1]:first-=1
    while last<len(offsets)-1 and occupied[last+1]:last+=1
    lo,hi=int(offsets[first]),int(offsets[last])
    assert hi-lo>=8,(sex,body.index,'torso section too narrow',lo,hi)
    family=old_wing.index-count
    family={5:1,6:2,7:3,8:4}.get(family,family)
    direction=8-family if old_wing.mirror and family not in (0,4) else family
    if facing is not None:direction=facing
    is_back=direction in (3,4,5) and group!=8
    near=images[count+1];near=near.crop(near.getbbox())
    left=near.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    right=near
    if direction==0 or group==8:
        wings=[(resize(left,.9,.9) if sex=='female' else left,False),(right,True)]
        mounts=[lo+4,hi-4]
    elif direction in (1,7):
        if sex=='female':
            wings=([(resize(left,.68,.82),False),(right,True)] if direction==1 else [(left,False),(resize(right,.68,.82),True)])
            mounts=[lo+4,hi-4]
        else:
            wings=[(right,True)] if direction==1 else [(left,False)]
            mounts=[hi-4] if direction==1 else [lo+4]
    elif direction in (2,6):
        wings=[(resize(right if direction==2 else left,.82,1),direction==2)]
        mounts=[hi-4] if direction==2 else [lo+4]
    else:
        if sex=='male':
            # The accepted male rear feather has its own broader silhouette.
            rear=images[count+3];rear=rear.crop((rear.width//2,0,rear.width,rear.height))
            right=rear.crop(rear.getbbox());left=right.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        if direction==4:wings=[(left,False),(right,True)];mounts=[-14,14]
        elif direction==3:wings=[(resize(left,.72,.9),False),(right,True)];mounts=[-7,16]
        else:wings=[(left,False),(resize(right,.72,.9),True)];mounts=[-16,7]
    pieces=[];records=[]
    for (wing,is_right),offset in zip(wings,mounts):
        wa=np.asarray(wing)[:,:,3]>=128
        ry=round(wing.height*.28)
        edge=np.flatnonzero(wa[max(0,ry-3):ry+4].any(axis=0))
        rx=int(edge[0])+4 if is_right else int(edge[-1])-4
        fan=(8 if not is_right else -8) if sex=='female' and group in (4,5,9,10,11,12) else 0
        wing_angle=angle+fan
        wing,root=rotate_root(wing,(rx,ry),wing_angle)
        target=center+np.clip(offset,lo+2,hi-2)*axis
        position=np.rint(target-root).astype(int)
        overlap=0
        # Test actual alpha overlap after rotation; grow inward only as needed.
        for step in range(17):
            wx,wy=position
            x0,y0=max(wx,bx),max(wy,by)
            x1,y1=min(wx+wing.width,bx+bi.width),min(wy+wing.height,by+bi.height)
            if x1>x0 and y1>y0:
                a=np.asarray(wing)[y0-wy:y1-wy,x0-wx:x1-wx,3]>=128
                b=alpha[y0-by:y1-by,x0-bx:x1-bx]
                overlap=int(np.count_nonzero(a&b))
            if overlap>=64:break
            target=center+np.clip(offset*(1-(step+1)/17),lo+2,hi-2)*axis
            position=np.rint(target-root).astype(int)
        assert overlap>=64,(sex,body.index,direction,'detached wing root',overlap)
        pieces.append((wing,int(position[0]),int(position[1])))
        records.append(dict(side='right' if is_right else 'left',mount=target.tolist(),angle=wing_angle,torso_lift_4x=lift,body_overlap_4x=overlap))
    ordered=[(bi,bx,by)]+pieces if is_back else pieces+[(bi,bx,by)]
    for layer in frame.layers:
        if layer.index==count+9:
            im,(x,y)=rendered(images[layer.index],layer);ordered.append((im,x,y))
    l=math.floor(min(x for _,x,_ in ordered)/8)*8;t=math.floor(min(y for _,_,y in ordered)/8)*8
    r=math.ceil(max(x+im.width for im,x,_ in ordered)/8)*8;b=math.ceil(max(y+im.height for im,_,y in ordered)/8)*8
    merged=Image.new('RGBA',(r-l,b-t))
    for im,x,y in ordered:merged.alpha_composite(im,(x-l,y-t))
    return merged,(l+r)//8,(t+b)//8,dict(body=body.index,basis_direction=direction,center=center.tolist(),wings=records)


def build():
    OUT.mkdir(parents=True,exist_ok=True);reports=[]
    for sex,korean in [('male','남'),('female','여')]:
        images,source,native,heads,ha,masks=load(sex,True)
        from refine_clan_combat_necks import refine
        images,neck_records=refine(images,native,masks,sex,OUT/'neck-drawings')
        from build_clan_closed_collar import close_collars
        images,bridge_records=close_collars(images,native,source,heads,ha,sex,neck_records)
        (OUT/f'{sex}-neck-refinement.json').write_text(json.dumps({'apertures':neck_records,'closed_collars':bridge_records},indent=2),encoding='utf8')
        count=len(native.images);rig=landmarks(sex,images,count)
        oldstem=BASE/f'data/sprite/clan_skins/1/인간족/몸통/{korean}/검사_{korean}'
        old=read_act(oldstem.with_suffix('.act').read_bytes());oldimages=read_spr(oldstem.with_suffix('.spr').read_bytes())
        world,preview=copy.deepcopy(old),copy.deepcopy(old)
        large=[];small=[];seen={};records=[]
        for ai,frames in enumerate(source.actions):
            for fi,frame in enumerate(frames):
                if ai<16:
                    layer=old.actions[ai][fi].layers[0];im,x,y=oldimages[layer.index],layer.x,layer.y
                else:
                    facing=None
                    if sex=='female' and ai//8 in (4,5,6,7,9,10,11,12):
                        # Native combat head views identify front/rear torso
                        # poses. Garment frame 1 is reused for both and cannot
                        # decide whether feathers belong over the backplate.
                        hf=ha.actions[ai][min(fi,len(ha.actions[ai])-1)]
                        head=next(l for l in hf.layers if l.index>=0)
                        assert head.index in (1,3,9,10,11,12)
                        base=3 if head.index in (3,11,12) else 1
                        facing=8-base if head.mirror else base
                    im,x,y,record=compose(images,frame,count,rig,sex,ai//8,facing)
                    records.append(dict(action=ai,frame=fi,**record))
                key=(im.size,hashlib.sha256(im.tobytes()).hexdigest())
                if key not in seen:
                    seen[key]=len(large);large.append(im)
                    small.append(im.convert('RGBa').resize((im.width//4,im.height//4),Image.Resampling.LANCZOS).convert('RGBA'))
                index=seen[key]
                world.actions[ai][fi].layers=[Layer(x,y,index,sx=.25,sy=.25)]
                preview.actions[ai][fi].layers=[Layer(x,y,index)]
        for variant,act,drawings in [('world',world,large),('preview',preview,small)]:
            rel=f'data/sprite/clan_skins/1/{"preview/" if variant=="preview" else ""}인간족/몸통/{korean}/검사_{korean}'
            stem=OUT/rel;stem.parent.mkdir(parents=True,exist_ok=True)
            ab,sb=write_act(act),write_spr(drawings)
            stem.with_suffix('.act').write_bytes(ab);stem.with_suffix('.spr').write_bytes(sb)
            baseline=read_act((BASE/rel).with_suffix('.act').read_bytes());baselineimages=read_spr((BASE/rel).with_suffix('.spr').read_bytes())
            check=read_act(ab);reopened=read_spr(sb)
            assert len(check.actions)==104 and sum(map(len,check.actions))==456 and check.tail==baseline.tail
            assert all(a.size==b.size and a.tobytes()==b.tobytes() for a,b in zip(drawings,reopened))
            for ai,frames in enumerate(check.actions):
                for fi,frame in enumerate(frames):
                    before=baseline.actions[ai][fi]
                    assert (frame.anchors,frame.sound,frame.ranges)==(before.anchors,before.sound,before.ranges)
                    if ai<16:
                        a,b=frame.layers[0],before.layers[0]
                        assert (a.x,a.y,a.sx,a.sy)==(b.x,b.y,b.sx,b.sy)
                        assert drawings[a.index].tobytes()==baselineimages[b.index].tobytes()
            reports.append(dict(sex=sex,variant=variant,actions=104,frames=456,updated_frames=len(records),
                                preserved_idle_walk_frames=88,images=len(drawings),
                                spr_sha256=hashlib.sha256(sb).hexdigest(),act_sha256=hashlib.sha256(ab).hexdigest()))
        (OUT/f'{sex}-torso-landmarks.json').write_text(json.dumps(rig,indent=2),encoding='utf8')
        (OUT/f'{sex}-all-action-roots.json').write_text(json.dumps(records,indent=2),encoding='utf8')
        print(sex,len(records),'remaining action frames fitted',flush=True)
    (OUT/'verification.json').write_text(json.dumps(reports,indent=2),encoding='utf8')
    return OUT


if __name__=='__main__':build()
