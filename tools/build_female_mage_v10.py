"""Continuous native-pose registration for front/rear Mage walking artwork.

All pixels come from complete source frames. No hand holes, garment cutouts,
replacement strips, or per-leg copies are introduced by this builder.
"""
from pathlib import Path
import copy,json,hashlib,math
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from sprite_formats import read_spr,read_act,write_spr,write_act,Layer,anchor
from review_original_job_directions import native_context
from review_full_swordman_set import body,joined,ORIGIN
from render_native_wing_anatomy import rgba
from preview_clan_reference_revision import bake
from bake_clan_body_frames import composite
from sprite_review_animation import save_review_animation
from refine_clan_combat_necks import components
from spr_reader import Spr

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'Assets/ClanBodySkins/Mage/female-gait-v10'
ORIGIN=np.array(ORIGIN,float)
FRONT_HANDS=[(-14,-30.5),(12.5,-31)]
FRONT_SOURCE_HINTS=[
 [(-14,-30.5),(12.5,-31)],[(-15,-28.5),(16,-28.5)],
 [(-14.7,-27.5),(16,-28.3)],[(-13.3,-29.5),(16,-29.8)],
 [(-16,-31.3),(14.2,-31.5)],[(-12.5,-29.8),(14,-29.5)],
 [(-14.2,-28.9),(14.5,-29.5)],[(-14.5,-29.3),(15,-29.8)]]
REAR_HANDS=[(-14,-32),(14,-32)]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load_pair(version):
    p=OUT.parent/f'female-gait-v{version}/assets/female-angel-mage-v{version}.spr'
    return read_spr(p.read_bytes()),read_act(p.with_suffix('.act').read_bytes())
def world(p):return np.array(p)*4+ORIGIN


def gray(im):
    a=np.asarray(im).astype(np.float32);return (a[:,:,0]*.299+a[:,:,1]*.587+a[:,:,2]*.114)*(a[:,:,3]/255)


def fit_patch(source,reference,box,hint=(0,0),scale_range=(.78,1.28)):
    """Fit a complete garment/hand feature to its corresponding reference."""
    x0,y0,x1,y1=box;w,h=int(round((x1-x0)*4)),int(round((y1-y0)*4));cx,cy=(x0+x1)/2,(y0+y1)/2
    ref=reference.crop(tuple(np.rint([*world((x0,y0)),*world((x1,y1))]).astype(int)))
    target=gray(ref);weights=np.asarray(ref)[:,:,3]>0
    # Include the local silhouette as well as the feature's visible material.
    weights=np.ones_like(weights,bool)
    tv=target[weights];tv=tv-tv.mean();tn=float(np.linalg.norm(tv));assert tn>1
    best=np.array([1.,1.,float(hint[0]),float(hint[1])]);best_score=-2.
    def score(p):
        sx,sy,dx,dy=p
        patch=source.transform((w,h),Image.Transform.AFFINE,(sx,0,ORIGIN[0]+(cx+dx)*4-sx*w/2,0,sy,ORIGIN[1]+(cy+dy)*4-sy*h/2),Image.Resampling.BILINEAR)
        v=gray(patch)[weights];v=v-v.mean();return float(np.dot(v,tv)/(np.linalg.norm(v)*tn+1e-9))
    best_score=score(best)
    for scale_step,shift_step,radius in [(.05,.5,4),(.02,.25,3),(.005,.125,2)]:
        for _ in range(2):
            for k,step in enumerate([scale_step,scale_step,shift_step,shift_step]):
                seed=best.copy()
                for n in range(-radius,radius+1):
                    candidate=seed.copy();candidate[k]+=n*step
                    if k<2 and not scale_range[0]<=candidate[k]<=scale_range[1]:continue
                    if k>=2 and abs(candidate[k]-hint[k-2])>4:continue
                    value=score(candidate)
                    if value>best_score:best,best_score=candidate,value
    def source_point(point):
        x,y=point;return np.array([cx+best[2]+best[0]*(x-cx),cy+best[3]+best[1]*(y-cy)])
    return source_point,dict(sx=float(best[0]),sy=float(best[1]),dx=float(best[2]),dy=float(best[3]),correlation=best_score,reference_box=list(box))


def glove_tracks(spr,act,ai):
    rows=[]
    for fi,f in enumerate(act.actions[ai]):
        l=f.layers[0];im=rgba(spr,l.index,0)
        if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        a=np.asarray(im);yy,xx=np.indices(a.shape[:2]);wx=xx+l.x-im.width//2;wy=yy+l.y-im.height//2
        light=np.all(a[:,:,:3]==[202,183,175],axis=2)|np.all(a[:,:,:3]==[238,223,215],axis=2)
        bob=anchor(f)[1]-anchor(act.actions[ai][0])[1];hands=[]
        for side in (-1,1):
            mask=light&(side*wx>=8)&(side*wx<=20)&(wy>=-35+bob)&(wy<=-22+bob)&(a[:,:,3]>0)
            assert mask.any();hands.append(np.array([wx[mask].mean(),wy[mask].mean()]))
        rows.append(hands)
    return rows


def kernel(p,q):
    d=np.sum((p[:,None,:]-q[None,:,:])**2,axis=2)
    return d*np.log(d+1e-12)


def continuous_warp(image,source_points,target_points,lower_edge):
    """Inverse thin-plate map with a fixed boundary and fold-over audit."""
    src=list(source_points);dst=list(target_points)
    for x in np.arange(-28,29,4):
        for y in (-65,lower_edge):src.append([x,y]);dst.append([x,y])
    for y in np.arange(-61,lower_edge,4):
        for x in (-28,28):src.append([x,y]);dst.append([x,y])
    src,dst=np.array(src,float),np.array(dst,float)
    assert np.min(np.linalg.norm(dst[:,None,:]-dst[None,:,:]+np.eye(len(dst))[:,:,None]*10000,axis=2))>.05
    n=len(dst);poly=np.column_stack([np.ones(n),dst]);system=np.zeros((n+3,n+3));system[:n,:n]=kernel(dst,dst)+np.eye(n)*.001;system[:n,n:]=poly;system[n:,:n]=poly.T
    solution=np.linalg.solve(system,np.vstack([src,np.zeros((3,2))]))
    top,left=int(ORIGIN[1]-65*4),int(ORIGIN[0]-28*4);bottom,right=int(ORIGIN[1]+lower_edge*4),int(ORIGIN[0]+28*4)
    yy,xx=np.mgrid[top:bottom,left:right];points=np.column_stack([(xx.ravel()-ORIGIN[0])/4,(yy.ravel()-ORIGIN[1])/4]);mapped=[]
    for start in range(0,len(points),4096):
        p=points[start:start+4096];mapped.append(kernel(p,dst)@solution[:n]+np.column_stack([np.ones(len(p)),p])@solution[n:])
    mapped=np.vstack(mapped).reshape(*xx.shape,2)
    dx_x=np.gradient(mapped[:,:,0],.25,axis=1);dx_y=np.gradient(mapped[:,:,0],.25,axis=0);dy_x=np.gradient(mapped[:,:,1],.25,axis=1);dy_y=np.gradient(mapped[:,:,1],.25,axis=0);jac=dx_x*dy_y-dx_y*dy_x
    assert jac.min()>.08,('Warp folds',float(jac.min()))
    source=np.asarray(image);result=source.copy();sample=mapped*4+ORIGIN
    assert sample.min()>=0 and sample.max()<639
    x0=np.floor(sample[:,:,0]).astype(int);y0=np.floor(sample[:,:,1]).astype(int);fx=sample[:,:,0]-x0;fy=sample[:,:,1]-y0
    opacity=np.zeros(x0.shape,float);best_weight=np.zeros(x0.shape,float);donor=np.zeros((*x0.shape,3),np.uint8)
    for dx,dy,weight in ((0,0,(1-fx)*(1-fy)),(1,0,fx*(1-fy)),(0,1,(1-fx)*fy),(1,1,fx*fy)):
        texel=source[y0+dy,x0+dx];alpha=texel[:,:,3].astype(float)/255;covered=weight*alpha;opacity+=covered
        take=covered>best_weight;donor[take]=texel[take,:3];best_weight[take]=covered[take]
    pixels=np.zeros((*x0.shape,4),np.uint8);pixels[:,:,3]=np.rint(opacity*255).astype(np.uint8);valid=pixels[:,:,3]>0
    pixels[valid,:3]=donor[valid]
    result[top:bottom,left:right]=pixels
    error=np.linalg.norm(kernel(dst,dst)@solution[:n]+poly@solution[n:]-src,axis=1)
    assert error.max()<.1,error.max()
    return Image.fromarray(result),dict(minimum_jacobian=float(jac.min()),maximum_landmark_error_native=float(error.max()),source_points=src.tolist(),target_points=dst.tolist(),fixed_lower_boundary=lower_edge,resampling='Coverage-weighted alpha with dominant opaque source colour')


def main():
    for name in ('assets','review/frames','review/details','landmarks'):(OUT/name).mkdir(parents=True,exist_ok=True)
    old,front=load_pair(9),load_pair(7);_,native_spr,native,_,_=native_context('mage','female')
    act=copy.deepcopy(old[1]);images=list(old[0]);reports=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    for ai in (8,12):
        reference=body('female',8,0,front,job='mage') if ai==8 else body('female',4,0,old,job='mage')
        ref_hands=FRONT_HANDS if ai==8 else REAR_HANDS
        tracks=glove_tracks(native_spr,native,ai);movies=[]
        for fi,f in enumerate(act.actions[ai]):
            source=body('female',ai,fi,front if ai==8 else old,job='mage');bob=np.array(anchor(native.actions[ai][fi]))-np.array(anchor(native.actions[ai][0]))
            fit,fit_report=fit_patch(source,reference,(-9,-59,9,-37) if ai==8 else (-11,-59,11,-34),hint=(0,float(bob[1])))
            source_points=[];target_points=[]
            for y in (-57,-51,-45,-39):
                for x in (-6,0,6):source_points.append(fit((x,y)));target_points.append(np.array([x,y])+bob)
            for x in (-13,13):source_points.append(fit((x,-49)));target_points.append(np.array([x,-49])+bob)
            hand_reports=[]
            for side,c in enumerate(ref_hands):
                c=np.array(c,float);hint=(np.array(FRONT_SOURCE_HINTS[fi][side])-c) if ai==8 else np.array([0,float(bob[1]-2)])
                hand_fit,hand_report=fit_patch(source,reference,(c[0]-4.5,c[1]-4.5,c[0]+4.5,c[1]+4.5),hint=hint,scale_range=(.75,1.4))
                target_hand=c+tracks[fi][side]-tracks[0][side]
                for offset in ((-2.5,0),(2.5,0),(0,-3),(0,3)):
                    source_points.append(hand_fit(c+offset));target_points.append(target_hand+offset)
                hand_reports.append(dict(side=side,source_centre=hand_fit(c).tolist(),target_centre=target_hand.tolist(),fit=hand_report))
            # Keep the central upper-leg axes and all lower stride pixels fixed.
            lower_edge=-22 if ai==8 else -9
            for x in (-7,0,7):
                for y in ((-25,) if ai==8 else (-14,)):source_points.append([x,y]);target_points.append([x,y])
            revised,proof=continuous_warp(source,source_points,target_points,lower_edge)
            before=np.asarray(body('female',ai,fi,old,job='mage'));after=np.asarray(revised);boundary=int(ORIGIN[1]+lower_edge*4);assert np.array_equal(before[boundary:],after[boundary:]),(ai,fi,'Stride changed')
            bounds=revised.getbbox();crop=revised.crop(bounds);packed,x,y=bake([(crop,bounds[0]-int(ORIGIN[0]),bounds[1]-int(ORIGIN[1]))]);f.layers=[Layer(x,y,len(images),sx=.25,sy=.25)];images.append(packed)
            panel=Image.new('RGB',(900,340),'#283746');pd=ImageDraw.Draw(panel);current=(images,act)
            for col,(label,p) in enumerate((('Original Mage',None),('V9',old),('V10 continuous fit',current))):
                raw=joined('female',ai,fi,p,job='mage').crop((80,40,560,620)).resize((240,290),Image.Resampling.NEAREST);panel.paste(raw,(col*300+30,25),raw);pd.text((col*300+5,4),label,font=font,fill='white')
            pd.text((8,319),f'Direction {ai-8} / F{fi}',font=font,fill='white');panel.save(OUT/f'review/frames/d{ai-8}-f{fi}.png');movies.append(panel)
            overlay=Image.new('RGB',(640,640),'#283746');overlay.paste(source,(0,0),source);pen=ImageDraw.Draw(overlay)
            for point,target in zip(source_points,target_points):
                sx,sy=world(point);tx,ty=world(target);pen.line((sx,sy,tx,ty),fill='cyan',width=1);pen.ellipse((sx-2,sy-2,sx+2,sy+2),fill='red')
            overlay.crop((200,180,440,460)).save(OUT/f'landmarks/d{ai-8}-f{fi}.png')
            reports.append(dict(action=ai,frame=fi,body_fit=fit_report,hands=hand_reports,warp=proof))
            print(ai,fi,'body fit',fit_report,'jacobian',proof['minimum_jacobian'],flush=True)
        save_review_animation(movies,OUT/f'review/d{ai-8}-loop.gif',75,apng=OUT/f'review/d{ai-8}-loop.png')
    compact=[];mapping={}
    for frames in act.actions:
        for frame in frames:
            for l in frame.layers:
                if l.index not in mapping:mapping[l.index]=len(compact);compact.append(images[l.index])
                l.index=mapping[l.index]
    stem=OUT/'assets/female-angel-mage-v10';stem.with_suffix('.spr').write_bytes(write_spr(compact));stem.with_suffix('.act').write_bytes(write_act(act))
    decoded=read_spr(stem.with_suffix('.spr').read_bytes());parsed=read_act(stem.with_suffix('.act').read_bytes());independent=Spr(stem.with_suffix('.spr').read_bytes());assert all(im.tobytes()==rgba(independent,i,1).tobytes() for i,im in enumerate(decoded));assert parsed.tail==old[1].tail
    unchanged=0
    for ai,frames in enumerate(parsed.actions):
        for fi,f in enumerate(frames):
            original=old[1].actions[ai][fi];assert (f.anchors,f.ranges,f.sound)==(original.anchors,original.ranges,original.sound)
            if ai not in (8,12):
                a,x,y=composite(old[0],original);b,bx,by=composite(decoded,f);assert (a.size,x,y)==(b.size,bx,by) and a.tobytes()==b.tobytes();unchanged+=1
    report=dict(status='Continuous front/rear fit candidate',changed_actions=[8,12],changed_frames=16,unchanged_frame_uses=unchanged,actions=104,frame_uses=456,checks=reports,files=[dict(path=p.relative_to(OUT).as_posix(),sha256=digest(p)) for p in (stem.with_suffix('.spr'),stem.with_suffix('.act'))])
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf8')


if __name__=='__main__':main()
