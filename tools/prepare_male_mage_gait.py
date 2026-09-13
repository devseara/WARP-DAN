"""Retarget complete female Mage pose guides to the native male head contract.

The donor is original artwork, not the generated female costume. Foot palette
measurements are silhouette measurements, never inferred skeleton joints.
"""
import copy,json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from prepare_mage_pose_set import WORK,native_context,sha
from render_native_wing_anatomy import rgba
from sprite_formats import anchor

OUT=WORK.parent/'male-gait-v3'

def prepare_diagonal_correction(batch, spr, act):
    b=copy.deepcopy(batch);b.update(name='walk-d1-row2',cells=4,rows=1)
    b['poses']=b['poses'][4:]
    sheet=Image.new('RGB',(1280,788),(0,255,0))
    style=Image.open(WORK/'refs/male/accepted-style.png').convert('RGBA').crop((240,0,480,340));sheet.paste(style,(520,0),style);pen=ImageDraw.Draw(sheet)
    for cell,p in enumerate(b['poses']):
        p['cell']=cell;f=act.actions[9][cell+4];l=f.layers[0];raw=rgba(spr,l.index,0);left=np.array([l.x-raw.width//2,l.y-raw.height//2]);origin=np.array([cell*320+160,492]);point=origin-(np.array(anchor(f))-left)*4;im=raw.resize((raw.width*4,raw.height*4),Image.Resampling.NEAREST);sheet.paste(im,tuple(point.astype(int)),im);mx,my=origin+[0,-128];pen.rectangle((mx-5,my-5,mx+5,my+5),fill=(255,0,255))
    sheet.save(OUT/'refs/male/walk-d1-row2-reference.png')
    (OUT/'correction-plan.json').write_text(json.dumps({'batches':[b]},indent=2),encoding='utf8')

def main():
    for folder in ('refs/male','art/male','metrics'): (OUT/folder).mkdir(parents=True,exist_ok=True)
    ms,mspr,ma,_,_=native_context('mage','male');fs,fspr,fa,_,_=native_context('mage','female')
    plan=json.loads((WORK/'art-plan.json').read_text(encoding='utf8'));batches=[];metrics=[]
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    overlay=Image.new('RGB',(8*175,5*210),'#283746');pen=ImageDraw.Draw(overlay)
    for d in range(5):
        b=copy.deepcopy(next(b for b in plan['batches'] if b['sex']=='male' and b['name']==f'walk-d{d}'))
        # Uniform generous cells preserve absolute native head-relative positions.
        height=512 if d>=3 else 448
        b.update(tile_size=[320,height],head_anchor_in_cell=[160,152],horizontal_crop_padding=16)
        sheet=Image.new('RGB',(1280,height*2),(0,255,0));draw=ImageDraw.Draw(sheet)
        donor_deltas=[]
        for fi,p in enumerate(b['poses']):
            mf=ma.actions[8+d][fi];ff=fa.actions[8+d][fi];l=ff.layers[0];raw=rgba(fspr,l.index,0)
            donor_anchor=np.array(anchor(ff));male_anchor=np.array(anchor(mf));delta=male_anchor-donor_anchor;donor_deltas.append(delta.tolist())
            left=np.array([l.x-raw.width//2,l.y-raw.height//2]);local=donor_anchor-left
            cell=np.array([fi%4*320,fi//4*height]);origin=cell+np.array(b['head_anchor_in_cell']);point=origin-local*4
            assert (point-cell>=0).all() and (point-cell+np.array(raw.size)*4<np.array([320,height])).all(),(d,fi,'template clipped')
            sheet.paste(raw.resize((raw.width*4,raw.height*4),Image.Resampling.NEAREST),tuple(point.astype(int)),raw.resize((raw.width*4,raw.height*4),Image.Resampling.NEAREST))
            marker=origin+[0,-128];mx,my=map(int,marker);draw.rectangle((mx-5,my-5,mx+5,my+5),fill=(255,0,255));p['marker_in_cell']=[160,24]
            pix=np.frombuffer(fspr.images[l.index].pixels,dtype=np.uint8).reshape(raw.height,raw.width)
            yy,xx=np.indices(pix.shape);wy=yy+left[1]
            boot=(pix>=88)&(pix<=95)&(wy>=-21)
            ys,xs=np.where(boot);assert len(xs)>20
            bounds=[int(xs.min()+left[0]),int(ys.min()+left[1]),int(xs.max()+left[0]+1),int(ys.max()+left[1]+1)]
            low=ys>=ys.max()-2;sole=[float(np.median(xs[low])+left[0]),int(ys.max()+left[1])]
            metrics.append(dict(direction=d,frame=fi,donor_sprite=l.index,male_sprite=p['sprite'],female_anchor=donor_anchor.tolist(),male_anchor=male_anchor.tolist(),donor_to_male_translation_native=delta.tolist(),boot_color_indices=[88,95],boot_search_y_min=-21,boot_palette_pixel_count=int(len(xs)),both_boot_palette_bounds_native=bounds,lowest_boot_band_median_native=sole,retargeted_boot_bounds_native=(np.array(bounds)+np.tile(delta,2)).tolist(),note='Visible boot color extent only; not a knee/ankle joint or automatic foot ownership assignment'))
            a=np.asarray(raw).copy();a[boot,:3]=[0,245,230];highlight=Image.fromarray(a)
            panel=Image.new('RGBA',(80,88));panel.alpha_composite(highlight,tuple((left+[40,64]).astype(int)));panel=panel.resize((160,176),Image.Resampling.NEAREST)
            overlay.paste(panel,(fi*175,d*210+25),panel);pen.text((fi*175+4,d*210+4),f'D{d} F{fi}',font=font,fill='white')
            p['donor_sprite']=l.index;p['donor_anchor']=donor_anchor.tolist();p['donor_to_male_translation_native']=delta.tolist()
        assert len(set(map(tuple,donor_deltas)))==1,(d,'phase rhythm mismatch')
        b['donor_sources']={'spr':str(fs/'body.spr'),'spr_sha256':sha(fs/'body.spr'),'act_sha256':sha(fs/'body.act')}
        template=OUT/b['template'];sheet.save(template)
        style=Image.open(WORK/'refs/male/accepted-style.png').convert('RGBA');combined=Image.new('RGB',(1280,340+height*2),(0,255,0));combined.paste(style,(40,0),style);combined.paste(sheet,(0,340));combined.save(OUT/f'refs/male/walk-d{d}-generation-reference.png')
        batches.append(b)
    prepare_diagonal_correction(batches[1],fspr,fa)
    overlay.save(OUT/'metrics/female-boot-palette-overlay.png')
    (OUT/'metrics/female-gait.json').write_text(json.dumps(dict(method='Complete original female Mage poses translated to male anchors with one constant per view; no phase shifts, limb stretching, or joint inference',frame_count=8,frame_duration_ms=75,source_spr_sha256=sha(fs/'body.spr'),source_act_sha256=sha(fs/'body.act'),frames=metrics),indent=2),encoding='utf8')
    (OUT/'art-plan.json').write_text(json.dumps(dict(job='mage',batches=batches),indent=2),encoding='utf8')
    print(json.dumps({'batches':len(batches),'donor_frames':len(metrics),'output':str(OUT)}))

if __name__=='__main__':main()
