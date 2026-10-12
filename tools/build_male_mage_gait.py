"""Replace only male walking with full female-referenced painted poses."""
import copy,json
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from prepare_male_mage_gait import OUT,WORK,native_context,sha
from import_full_swordman_art import extract
from export_native_pose_study import collar
from refine_clan_combat_necks import components
from sprite_formats import read_spr,read_act,write_spr,write_act,Layer
from preview_clan_reference_revision import bake
from render_native_wing_anatomy import rgba
from repair_mage_walk_registration import collar_world
from bake_clan_body_frames import composite
from review_full_swordman_set import body,joined,ORIGIN
from sprite_review_animation import save_review_animation
from spr_reader import Spr

BASE=WORK.parent/'walk-repair-v2'

def native_collar(spr,frame):
    l=frame.layers[0];raw=rgba(spr,l.index,0)
    if l.mirror:raw=raw.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    return (np.array([l.x-raw.width//2,l.y-raw.height//2])+collar(raw,2))*4

def clear_key_spill(image):
    # Only green chroma from the explicitly keyed source plate is eligible.
    # Connected edge spill becomes transparent; enclosed spill retains its
    # opacity and loses the excess green instead of making holes in clothing.
    a=np.asarray(image).copy();rgb=a[:,:,:3].astype(int)
    key=(a[:,:,3]>0)&(rgb[:,:,1]-rgb[:,:,0]>20)&(rgb[:,:,1]-rgb[:,:,2]>20)
    clear=a[:,:,3]==0
    for _ in range(8):
        pad=np.pad(clear,1,constant_values=True);adjacent=np.zeros_like(clear)
        for dy in range(3):
            for dx in range(3):adjacent|=pad[dy:dy+clear.shape[0],dx:dx+clear.shape[1]]
        more=key&adjacent&~clear
        if not more.any():break
        clear|=more
    removed=key&clear;interior=key&~clear;a[removed]=0
    a[interior,1]=np.maximum(a[interior,0],a[interior,2])
    return Image.fromarray(a),dict(edge_key_pixels_removed=int(removed.sum()),enclosed_spill_pixels_despilled=int(interior.sum()))

def drop_key_fragments(image):
    # Reviewed 1-2 px detached remnants were dark green matte, not white
    # feather highlights. Restrict removal to tiny green-dominant fragments.
    a=np.asarray(image).copy();removed=0
    for pts in components(a[:,:,3]>0):
        if len(pts)>4:continue
        ys,xs=pts[:,0],pts[:,1];rgb=a[ys,xs,:3].astype(int)
        if rgb.max()<100 and float(np.mean(rgb[:,1]-np.maximum(rgb[:,0],rgb[:,2])))>5:
            a[ys,xs]=0;removed+=len(pts)
    return Image.fromarray(a),removed

def main():
    for p in ('assets','review'): (OUT/p).mkdir(exist_ok=True)
    src=BASE/'assets/male-angel-mage-v2.spr';oldim=read_spr(src.read_bytes());old=read_act(src.with_suffix('.act').read_bytes())
    _,mspr,ma,_,_=native_context('mage','male');_,fspr,fa,_,_=native_context('mage','female')
    plan=json.loads((OUT/'art-plan.json').read_text(encoding='utf8'));art={};imports=[];records={}
    for b in plan['batches']:
        extracted,rows=extract(b,OUT);art.update(extracted);imports+=rows;records.update({p['sprite']:p for p in b['poses']})
    corrections=OUT/'correction-plan.json'
    if corrections.exists():
        for b in json.loads(corrections.read_text(encoding='utf8'))['batches']:
            extracted,rows=extract(b,OUT);art.update(extracted);imports=[r for r in imports if r['sprite'] not in extracted]+rows
    for index,(im,offset) in list(art.items()):
        im,cleanup=clear_key_spill(im);art[index]=(im,offset);next(r for r in imports if r['sprite']==index)['green_spill_cleanup']=cleanup
    placed={};measures=[];scales={};font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    for d in range(5):
        ratios=[]
        for fi in range(8):
            fl=fa.actions[8+d][fi].layers[0];raw=rgba(fspr,fl.index,0);index=ma.actions[8+d][fi].layers[0].index;im,_=art[index]
            ratios.append((raw.getbbox()[3]-collar(raw,2)[1])*4/(im.getbbox()[3]-collar(im,8)[1]))
        # A single scale per view; no per-frame limb/body scaling.
        factor=float(np.median(ratios));scales[d]=factor;assert .8<factor<1.15,(d,factor)
        c0=native_collar(mspr,ma.actions[8+d][0]);ol=old.actions[8+d][0].layers[0];oldc0=collar_world(oldim[ol.index],ol,8,1)
        baseline=oldc0-c0
        for fi in range(8):
            nf=ma.actions[8+d][fi];index=nf.layers[0].index;im,_=art[index];im=im.resize((round(im.width*factor),round(im.height*factor)),Image.Resampling.NEAREST)
            im,fragments=drop_key_fragments(im);next(r for r in imports if r['sprite']==index)['post_scale_key_fragment_pixels_removed']=fragments
            target=native_collar(mspr,nf)+baseline;point=collar(im,8);offset=np.rint(target-point).astype(int);placed[index]=(im,offset,nf.layers[0])
            fl=fa.actions[8+d][fi].layers[0];raw=rgba(fspr,fl.index,0);donor_length=(raw.getbbox()[3]-collar(raw,2)[1])*4;actual_length=im.getbbox()[3]-point[1]
            measures.append(dict(direction=d,frame=fi,native_sprite=index,donor_sprite=fl.index,whole_view_scale=factor,original_female_collar_to_sole_native=donor_length/4,painted_collar_to_sole_native=actual_length/4,sole_height_error_native=(actual_length-donor_length)/4,male_collar_target_4x=target.tolist(),painted_collar_4x=(point+offset).tolist(),whole_pose_offset_4x=offset.tolist(),source=next(r['source'] for r in imports if r['sprite']==index)))
            im.save(OUT/'whole-frames/male'/f'sprite-{index:03d}.png')
    act=copy.deepcopy(old);images=[];seen={}
    def add(im):
        key=(im.size,im.tobytes())
        if key not in seen:seen[key]=len(images);images.append(im)
        return seen[key]
    for ai,frames in enumerate(act.actions):
        for fi,f in enumerate(frames):
            if 8<=ai<16:
                l=ma.actions[ai][fi].layers[0];im,offset,canonical=placed[l.index];xy=offset.copy()
                if l.mirror:
                    # Reflect complete art around the original indexed layer axis.
                    raw=mspr.images[l.index];axis=4*(canonical.x+l.x+raw.width%2)
                    im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT);xy[0]=axis-offset[0]-im.width;xy[1]+=4*(l.y-canonical.y)
                result,x,y=bake([(im,int(xy[0]),int(xy[1]))]);f.layers=[Layer(x,y,add(result),sx=.25,sy=.25)]
            else:
                for l in f.layers:
                    if l.index>=0:l.index=add(oldim[l.index])
    stem=OUT/'assets/male-angel-mage-v3';sb,ab=write_spr(images),write_act(act);stem.with_suffix('.spr').write_bytes(sb);stem.with_suffix('.act').write_bytes(ab)
    decoded=read_spr(sb);parsed=read_act(ab);independent=Spr(sb);assert all(im.tobytes()==rgba(independent,i,1).tobytes() for i,im in enumerate(decoded))
    assert parsed.tail==old.tail and len(parsed.actions)==104 and sum(map(len,parsed.actions))==456
    unchanged=0
    for ai,frames in enumerate(parsed.actions):
        for fi,f in enumerate(frames):
            n=old.actions[ai][fi];assert (f.anchors,f.ranges,f.sound)==(n.anchors,n.ranges,n.sound)
            if not 8<=ai<16:
                a,x,y=composite(oldim,n);b,bx,by=composite(decoded,f);assert (a.size,x,y)==(b.size,bx,by) and a.tobytes()==b.tobytes();unchanged+=1
    pair=(decoded,parsed)
    for d in range(8):
        frames=[];strip=Image.new('RGB',(8*220,3*285),'#283746');spen=ImageDraw.Draw(strip)
        for fi in range(8):
            panel=Image.new('RGB',(900,340),'#283746');pen=ImageDraw.Draw(panel)
            for row,(label,sex,p) in enumerate([('Original female gait','female',None),('Previous male V2','male',(oldim,old)),('Male V3','male',pair)]):
                im=joined(sex,8+d,fi,p,job='mage').crop((80,40,560,620));small=im.resize((240,290),Image.Resampling.NEAREST);panel.paste(small,(row*300+30,25),small);pen.text((row*300+10,4),label,font=font,fill='white')
                small=im.resize((216,261),Image.Resampling.NEAREST);strip.paste(small,(fi*220+2,row*285+22),small);spen.text((fi*220+4,row*285+3),f'{label} F{fi}',font=font,fill='white')
            pen.text((8,318),f'Direction {d} / frame {fi} / native 75 ms',font=font,fill='white');frames.append(panel)
        strip.save(OUT/f'review/d{d}-frames.png');save_review_animation(frames,OUT/f'review/d{d}-loop.gif',75,apng=OUT/f'review/d{d}-loop.png')
    report=dict(status='Male walking artwork rebuilt against original female gait; visual review candidate',actions=104,frame_uses=456,changed_male_walk_frame_uses=64,unchanged_male_nonwalk_frame_uses=unchanged,female_files_modified=False,installed_files_modified=False,native_metadata_preserved=True,independent_decoder_match=True,method='Complete female native pose templates; fixed uniform scale per view; visible collar translated to preserved male collar trajectory; no per-frame scaling or standing-part warping',view_scales=scales,measurements=measures,imports=imports,files=[dict(path=p.relative_to(OUT).as_posix(),sha256=sha(p)) for p in (stem.with_suffix('.spr'),stem.with_suffix('.act'))])
    (OUT/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf8');print(json.dumps({k:v for k,v in report.items() if k not in ('measurements','imports')}));print('Sole-height deviations:',[(d,round(max(abs(r['sole_height_error_native']) for r in measures if r['direction']==d),2)) for d in range(5)])

if __name__=='__main__':main()
