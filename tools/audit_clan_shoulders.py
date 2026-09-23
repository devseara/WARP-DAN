"""Read-only shoulder audit of the published neck-correction candidate."""
import json
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from correct_clan_neck_registration import ROOT,WORK as CANDIDATE,original_pairs,original_neck,load,save,sha
from review_full_swordman_set import body,head
from review_original_job_directions import native_context
from sprite_formats import read_spr,read_act

WORK=ROOT/'Assets/ClanBodySkins/shoulder-audit-20260924'
FONT=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',12)


def prepare():
    manifest=load(ROOT/'Inputs/ClanBodySkins/records/clan-neck-motion-correction.json')
    old=original_pairs();data={};records=[];pins=[];checks=[];playback={}
    for job in ('acolyte','archer'):
        for sex in ('male','female'):
            stem=CANDIDATE/job/'assets'/f'{sex}-angel-{job}-neck-v1'
            for ext in ('.spr','.act'):
                p=stem.with_suffix(ext);r=next(r for r in manifest['files'] if r['job']==job and r['sex']==sex and Path(r['source']).suffix==ext)
                assert sha(p.read_bytes())==r['sha256'];pins.append(dict(path=p.relative_to(ROOT).as_posix(),sha256=r['sha256']))
            current=read_spr(stem.with_suffix('.spr').read_bytes()),read_act(stem.with_suffix('.act').read_bytes())
            native=native_context(job,sex)[2];proof=load(CANDIDATE/job/f'{sex}-verification.json')['checks'];actions={};animations={}
            for ai in (9,11,13,15):
                views=[];base=original_neck(job,sex,ai,0)[0]
                strip_box=np.rint(np.tile(base,2)+[-78,-10,78,82]).astype(int)
                all_bounds=[];outside=[];moves=[];head_matches=[]
                atlases={mode:Image.new('RGBA',(164*8,140*3)) for mode in ('raw','aligned')}
                atlas_box=np.rint(np.tile(base,2)+[-82,-28,82,112]).astype(int)
                first_head=head(sex,ai,0,job=job)
                for fi in range(8):
                    point=original_neck(job,sex,ai,fi)[0];bob=point-base
                    layers=[];joined=[];strips=[]
                    for pair in (None,old[job,sex],current):
                        b=body(sex,ai,fi,pair,job=job);h=head(sex,ai,fi,job=job,pair=pair);c=b.copy();c.alpha_composite(h)
                        layers.append(b);joined.append(c);all_bounds.append(c.getbbox())
                        box=strip_box+np.tile(np.rint(bob).astype(int),2)
                        strips.append(b.crop(tuple(box)))
                    r=next(r for r in proof if r['action']==ai and r['frame']==fi)
                    move=next((p for p in r['corrections'] if 'delta_4x' in p),None)
                    current_delta=move['delta_4x'] if move else [0,0]
                    moves.append((np.array(current_delta)/4).tolist())
                    delta=np.rint(bob).astype(int)
                    restored=Image.new('RGBA',first_head.size)
                    restored.alpha_composite(head(sex,ai,fi,job=job),(-int(delta[0]),-int(delta[1])))
                    head_matches.append(restored.tobytes()==first_head.tobytes())
                    for mode,atlas in atlases.items():
                        box=atlas_box+(np.tile(delta,2) if mode=='aligned' else 0)
                        for row,b in enumerate(layers):atlas.paste(b.crop(tuple(box)),(fi*164,row*140))
                    if job=='acolyte' and ai==15:
                        difference=np.any(np.array(layers[1])!=np.array(layers[2]),axis=2)
                        for correction in r['corrections']:
                            if 'window' in correction:
                                x0,y0,x1,y1=correction['window'];difference[y0:y1,x0:x1]=False
                        outside.append(int(difference.sum()))
                    records.append(dict(job=job,sex=sex,action=ai,frame=fi,direction=ai-8,
                        native_neck_movement_4x=bob.tolist(),correction_translation_native=(np.array(current_delta)/4).tolist(),
                        native_sprite=native.actions[ai][fi].layers[0].index,native_mirror=native.actions[ai][fi].layers[0].mirror,
                        unchanged_outside_neck=(not move),head_pixels_native=head(sex,ai,fi,job=job,pair=current).tobytes()==head(sex,ai,fi,job=job).tobytes()))
                    views.append(dict(joined=joined,strips=strips,layers=layers))
                x0=min(b[0] for b in all_bounds)-8;y0=min(b[1] for b in all_bounds)-8;x1=max(b[2] for b in all_bounds)+8;y1=max(b[3] for b in all_bounds)+8
                w=max(165,(x1-x0+1)//2+12);h=(y1-y0+1)//2+28
                board=Image.new('RGB',(w*8,h*3+26),'#283746');pen=ImageDraw.Draw(board)
                pen.text((5,5),f'{job} {sex} / D{ai-8} / same world origin; original | previous | candidate rows',font=FONT,fill='white')
                strip=Image.new('RGB',(8*164,3*116+28),'#283746');d=ImageDraw.Draw(strip)
                d.text((5,5),'Shoulder/cape detail: only original neck translation removed. No crop-centering or scale normalization.',font=FONT,fill='white')
                for fi,v in enumerate(views):
                    for row,label in enumerate(('Native','Previous','Candidate')):
                        im=v['joined'][row].crop((x0,y0,x1,y1));im=im.resize(((x1-x0+1)//2,(y1-y0+1)//2),Image.Resampling.NEAREST)
                        board.paste(im,(fi*w+(w-im.width)//2,26+row*h+20),im);pen.text((fi*w+4,26+row*h+2),f'{label} F{fi}',font=FONT,fill='white')
                        im=v['strips'][row];strip.paste(im,(fi*164+4,28+row*116+20),im);d.text((fi*164+3,28+row*116+2),f'{label} F{fi}',font=FONT,fill='white')
                board.save(WORK/f'{job}-{sex}-a{ai}-full.png');strip.save(WORK/f'{job}-{sex}-a{ai}-shoulders.png')
                actions[str(ai)]=dict(ms=75,full=f'{job}-{sex}-a{ai}-full.png',shoulders=f'{job}-{sex}-a{ai}-shoulders.png')
                atlas_names={mode:f'{job}-{sex}-a{ai}-{mode}.png' for mode in atlases}
                for mode,im in atlases.items():im.save(WORK/atlas_names[mode])
                animations[str(ai)]={**atlas_names,'moves':moves,'full':actions[str(ai)]['full']}
                shifts=np.array(moves)
                checks.append(dict(job=job,sex=sex,action=ai,direction=ai-8,
                    original_heads_identical_after_normalization=all(head_matches),
                    scale_transforms=sorted({(l.sx,l.sy,l.angle) for f in current[1].actions[ai] for l in f.layers}),
                    frame_count=len(current[1].actions[ai]),speed_ms=current[1].speeds[ai]*25,
                    translation_range_native=np.ptp(shifts,axis=0).tolist(),
                    largest_correction_step_native=float(np.linalg.norm(np.roll(shifts,-1,axis=0)-shifts,axis=1).max()),
                    acolyte_d7_pixels_changed_outside_neck=outside))
            data.setdefault(job,{})[sex]=actions
            playback.setdefault(job,{})[sex]=animations
            print(job,sex,'D1/3/5/7 rendered',flush=True)
    save(WORK/'measurements.json',dict(status='investigation',pairs=pins,frames=records,
        limitations=['Correction vectors alone do not prove visible jitter; they can cancel source displacement.',
            'Normalized strips remove native neck motion only; actual shoulder articulation and source shape remain.']))
    save(WORK/'sheets.json',data)
    save(WORK/'checks.json',checks)
    save(WORK/'playback.json',dict(jobs=playback))
    (WORK/'review.html').write_text((ROOT/'tools/clan_shoulder_review.html').read_text(encoding='utf8'),encoding='utf8',newline='\n')


if __name__=='__main__':
    WORK.mkdir(exist_ok=True);prepare()
