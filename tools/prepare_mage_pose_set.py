"""Native Mage pose plates using the previously approved original outfit."""
import argparse,json,math,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from review_original_job_directions import native_context
from render_native_wing_anatomy import rgba
from sprite_formats import anchor
from prepare_full_swordman_art import LABELS,sha

ROOT=Path(__file__).resolve().parents[1]
WORK=ROOT/'Assets/ClanBodySkins/Mage/complete-v1'

def style_strips(work=WORK):
    source=work.parent/'design/approved-directions.png';image=Image.open(source).convert('RGB');a=np.array(image)
    eligible=(a.max(axis=2).astype(int)-a.min(axis=2).astype(int)<=18)&(a.min(axis=2)>=145)
    flood=Image.fromarray((eligible*255).astype('uint8')).copy();ImageDraw.floodfill(flood,(0,0),128)
    mask=np.asarray(flood)!=128;data=np.dstack((a,mask.astype('uint8')*255));data[~mask]=0;clear=Image.fromarray(data)
    for row,sex in enumerate(('male','female')):
        y0,y1=round(row*image.height/2),round((row+1)*image.height/2);occupied=mask[y0:y1].sum(axis=0);boundaries=[0]
        for col in range(1,5):
            center=round(col*image.width/5);radius=round(image.width*.04);gaps=np.flatnonzero(occupied[center-radius:center+radius]==0)+center-radius
            assert len(gaps)>2;boundaries.append(int(gaps[len(gaps)//2]))
        boundaries.append(image.width);style=Image.new('RGBA',(1200,340));folder=work/'refs'/sex;folder.mkdir(parents=True,exist_ok=True)
        for col in range(5):
            im=clear.crop((boundaries[col],y0,boundaries[col+1],y1));im=im.crop(im.getbbox());scale=min(280/im.height,224/im.width);im=im.resize((round(im.width*scale),round(im.height*scale)),Image.Resampling.NEAREST)
            style.alpha_composite(im,(col*240+120-im.width//2,315-im.height))
        style.save(folder/'accepted-style.png')

def main(job="mage",work=WORK):
    work.mkdir(parents=True,exist_ok=True);style_strips(work);batches=[];sources=[]
    for sex in ('male','female'):
        src,spr,act,_,_=native_context(job,sex);uses={};bygroup={}
        for ai,frames in enumerate(act.actions):
            for fi,f in enumerate(frames):
                for l in f.layers:
                    if l.index<0:continue
                    assert l.kind==0 and l.sx==l.sy==1 and l.angle==0
                    uses.setdefault(l.index,[]).append((ai,fi,l));bygroup.setdefault(ai//8,set()).add(l.index)
        specs=[('idle-sit',sorted(bygroup[0]|bygroup[2]),5)]
        for d in range(5):specs.append((f'walk-d{d}',[f.layers[0].index for f in act.actions[8+d]],4))
        specs += [('pickup-hit',sorted(bygroup[3]|bygroup[6]),4),('floor-standby',sorted(bygroup[7]|bygroup[8]|bygroup[9]),3),('attack1',sorted(bygroup[4]),4),('attack2',sorted(bygroup[5]),4),('attack3',sorted(bygroup[10]-bygroup[9]),4),('attack4',sorted(bygroup[11]),5),('cast',sorted(bygroup[12]),5)]
        planned=set()
        for name,ids,cols in specs:
            ids=[i for i in ids if i not in planned]
            if not ids:continue
            assert len(set(ids))==len(ids),(sex,name,'duplicate mapping');planned.update(ids)
            cols=min(cols,len(ids))
            records=[];minimum=np.array([-8.,-32.]);maximum=np.array([8.,8.])
            # Keep marks well clear of the body in floor poses.
            mark_offset=np.array([0,-64 if name=='floor-standby' else -32]);minimum=np.minimum(minimum,mark_offset-3)
            for index in ids:
                valid=[u for u in uses[index] if u[2].mirror==0];assert valid
                ai,fi,l=valid[0];im=rgba(spr,index,0);native_anchor=np.array(anchor(act.actions[ai][fi]),float);left=np.array([l.x-im.width//2,l.y-im.height//2],float);local=native_anchor-left
                minimum=np.minimum(minimum,-local);maximum=np.maximum(maximum,np.array(im.size)-local)
                records.append(dict(sprite=index,representative_action=ai,representative_frame=fi,native_anchor=native_anchor.tolist(),native_layer=[l.x,l.y],source_size=list(im.size),head_anchor_in_source=local.tolist(),groups=sorted({LABELS[u[0]//8] for u in uses[index]})))
            origin=np.ceil(-minimum*4+24).astype(int);size=np.ceil(((maximum-minimum)*4+64)/32).astype(int)*32;rows=math.ceil(len(ids)/cols)
            sheet=Image.new('RGB',(cols*int(size[0]),rows*int(size[1])),(0,255,0));pen=ImageDraw.Draw(sheet)
            for cell,rec in enumerate(records):
                im=rgba(spr,rec['sprite'],0).resize(tuple(np.array(rec['source_size'])*4),Image.Resampling.NEAREST);xy=np.array([cell%cols*size[0],cell//cols*size[1]])
                point=xy+origin-np.array(rec['head_anchor_in_source'])*4;sheet.paste(im,tuple(point.astype(int)),im);marker=xy+origin+mark_offset*4;mx,my=marker.astype(int);pen.rectangle((mx-5,my-5,mx+5,my+5),fill=(255,0,255));rec.update(cell=cell,marker_in_cell=(origin+mark_offset*4).tolist())
            path=work/'refs'/sex/(name+'-template.png');sheet.save(path)
            batches.append(dict(sex=sex,name=name,horizontal_crop_padding=24,columns=cols,rows=rows,cells=len(ids),tile_size=size.tolist(),head_anchor_in_cell=origin.tolist(),marker_offset_native=mark_offset.tolist(),template=path.relative_to(work).as_posix(),style=f'refs/{sex}/accepted-style.png',source_spr_sha256=sha(src/'body.spr'),source_act_sha256=sha(src/'body.act'),poses=records))
            print(sex,name,len(ids),'poses',flush=True)
        assert planned==set(uses);sources.append(dict(sex=sex,unique_native_drawings=len(planned),actions=len(act.actions),frame_uses=sum(map(len,act.actions))))
    (work/'art-plan.json').write_text(json.dumps(dict(job=job,status='Building native-pose original '+job.title()+' animation',sources=sources,batches=batches),indent=2),encoding='utf8')

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job',choices=('mage','acolyte','archer','merchant','thief'),default='mage')
    parser.add_argument('--work',type=Path)
    args=parser.parse_args()
    target=args.work or WORK.parent.parent/args.job.title()/'complete-v1'
    if (target/'art-plan.json').exists():
        parser.error('An art plan already exists; use a new --work directory to preserve selected artwork and registration.')
    main(args.job,target.resolve())
