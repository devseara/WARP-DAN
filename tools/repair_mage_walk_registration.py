"""Repair atlas-row registration drift using visible native collar motion.

Only complete walking-frame placement changes. Source pixels, frame order,
timing, native heads and all non-walking actions are preserved.
"""
import copy,json,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from prepare_mage_pose_set import WORK,native_context
from sprite_formats import read_spr,read_act,write_spr,write_act,Layer
from render_native_wing_anatomy import rgba
from export_native_pose_study import collar
from preview_clan_reference_revision import bake
from bake_clan_body_frames import composite
from review_full_swordman_set import body,joined,ORIGIN
from sprite_review_animation import save_review_animation

OUT=WORK.parent/'walk-repair-v2'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def collar_world(image,layer,band,unit):
    if layer.mirror:image=image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    left=np.array([layer.x*4-image.width*unit//2,layer.y*4-image.height*unit//2])
    return left+collar(image,band)*unit

def build(sex):
    OUT.mkdir(exist_ok=True);(OUT/'assets').mkdir(exist_ok=True);(OUT/'review').mkdir(exist_ok=True)
    original_path=WORK/f'assets/{sex}-angel-mage-v1.spr';before_images=read_spr(original_path.read_bytes());before=read_act(original_path.with_suffix('.act').read_bytes())
    _,native_spr,native,heads,ha=native_context('mage',sex);act=copy.deepcopy(before);images=list(before_images);changes=[];proof=[]
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    for d in range(8):
        ai=8+d;points=[]
        for fi in range(8):
            nl=native.actions[ai][fi].layers[0];raw=rgba(native_spr,nl.index,nl.kind)
            if nl.mirror:raw=raw.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            # Indexed loader uses floor(native_width/2), including odd sizes.
            npnt=(np.array([nl.x-raw.width//2,nl.y-raw.height//2])+collar(raw,2))*4
            cl=before.actions[ai][fi].layers[0];im=before_images[cl.index]
            cpnt=collar_world(im,cl,8,1);points.append((npnt,cpnt))
        baseline_offset=points[0][1]-points[0][0]
        grid=Image.new('RGB',(8*220,340),'#283746');draw=ImageDraw.Draw(grid)
        for fi,(npnt,cpnt) in enumerate(points):
            target=npnt+baseline_offset;shift=np.rint(target-cpnt).astype(int)
            cl=before.actions[ai][fi].layers[0];im=before_images[cl.index]
            if cl.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            left=cl.x*4-im.width//2;top=cl.y*4-im.height//2
            result,x,y=bake([(im,left+int(shift[0]),top+int(shift[1]))]);images.append(result);act.actions[ai][fi].layers=[Layer(x,y,len(images)-1,sx=.25,sy=.25)]
            changes.append(dict(action=ai,frame=fi,native_collar_4x=npnt.tolist(),before_collar_4x=cpnt.tolist(),reference_frame_zero_offset_4x=baseline_offset.tolist(),translation_4x=shift.tolist(),after_collar_4x=(cpnt+shift).tolist(),rounding_error_4x=(cpnt+shift-target).tolist()))
            # Actual visible collar marks, no native head hiding the point.
            b=body(sex,ai,fi,(before_images,before),job='mage');p=ImageDraw.Draw(b);point=np.array(ORIGIN)+cpnt;p.ellipse((point[0]-4,point[1]-4,point[0]+4,point[1]+4),fill='red')
            native_body=body(sex,ai,fi,job='mage');p=ImageDraw.Draw(native_body);point=np.array(ORIGIN)+npnt;p.ellipse((point[0]-4,point[1]-4,point[0]+4,point[1]+4),fill='cyan')
            for row,pic in enumerate((native_body,b)):
                crop=pic.crop((220,170,440,300));grid.paste(crop,(fi*220,row*160+25),crop)
            draw.text((fi*220+5,3),f'F{fi} shift {shift[0]/4:g},{shift[1]/4:g}',font=font,fill='white')
        grid.save(OUT/f'review/{sex}-d{d}-collar-points.png')
    # Compact the output; unchanged action images retain their exact pixels.
    packed=[];seen={}
    for frames in act.actions:
        for f in frames:
            for l in f.layers:
                if l.index<0:continue
                im=images[l.index];key=(im.size,im.tobytes())
                if key not in seen:seen[key]=len(packed);packed.append(im)
                l.index=seen[key]
    stem=OUT/f'assets/{sex}-angel-mage-v2';sb,ab=write_spr(packed),write_act(act);stem.with_suffix('.spr').write_bytes(sb);stem.with_suffix('.act').write_bytes(ab)
    reopened=(read_spr(sb),read_act(ab));unchanged=0
    assert reopened[1].tail==before.tail and len(reopened[1].actions)==104
    for ai,frames in enumerate(reopened[1].actions):
        for fi,f in enumerate(frames):
            old=before.actions[ai][fi];assert (f.anchors,f.ranges,f.sound)==(old.anchors,old.ranges,old.sound)
            a,x,y=composite(before_images,old);b,bx,by=composite(reopened[0],f)
            if 8<=ai<16:
                change=next(r for r in changes if r['action']==ai and r['frame']==fi)
                # Tight opaque pixels must be identical, including all limbs.
                assert a.crop(a.getbbox()).tobytes()==b.crop(b.getbbox()).tobytes()
                ca=a.getbbox();cb=b.getbbox();left_a=x*4-a.width//2+ca[0];top_a=y*4-a.height//2+ca[1];left_b=bx*4-b.width//2+cb[0];top_b=by*4-b.height//2+cb[1]
                assert [left_b-left_a,top_b-top_a]==change['translation_4x']
            else:assert (a.size,x,y)==(b.size,bx,by) and a.tobytes()==b.tobytes();unchanged+=1
    for d in range(8):
        ai=8+d;movie=[];strip=Image.new('RGB',(8*220,3*290),'#283746');draw=ImageDraw.Draw(strip)
        for fi in range(8):
            panel=Image.new('RGB',(900,340),'#283746');pen=ImageDraw.Draw(panel)
            for k,(label,pair) in enumerate([('Original',None),('Delivered V1',(before_images,before)),('Registered V2',reopened)]):
                im=joined(sex,ai,fi,pair,job='mage').crop((80,40,560,620));preview=im.resize((240,290),Image.Resampling.NEAREST);panel.paste(preview,(k*300+30,25),preview);pen.text((k*300+8,4),label,font=font,fill='white')
                small=im.resize((216,261),Image.Resampling.NEAREST);strip.paste(small,(fi*220+2,k*290+22),small);draw.text((fi*220+5,k*290+4),f'{label} F{fi}',font=font,fill='white')
            pen.text((8,317),f'{sex} D{d} / F{fi} / original 75 ms',font=font,fill='white');movie.append(panel)
        strip.save(OUT/f'review/{sex}-d{d}-comparison.png');save_review_animation(movie,OUT/f'review/{sex}-d{d}-comparison.gif',75,apng=OUT/f'review/{sex}-d{d}-comparison-apng.png')
    report=dict(sex=sex,status='Walking registration correction for review; anatomy unchanged',unchanged_nonwalk_frames=unchanged,walking_frames=64,source_pose_pixels_unchanged=True,native_metadata_unchanged=True,changes=changes,files=[dict(path=p.relative_to(OUT).as_posix(),sha256=sha(p)) for p in (stem.with_suffix('.spr'),stem.with_suffix('.act'))])
    (OUT/f'{sex}-verification.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items() if k!='changes'}),flush=True)

if __name__=='__main__':
    for sex in ('male','female'):build(sex)
