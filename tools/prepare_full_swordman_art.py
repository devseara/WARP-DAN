"""Catalog remaining native SPR drawings and prepare head-registered art plates."""
import json,math,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from review_original_job_directions import OUT,native_context
from render_native_wing_anatomy import rgba
from sprite_formats import anchor,read_act,read_spr
from bake_clan_body_frames import composite

WORK=Path(__file__).resolve().parents[1]/'Assets/ClanBodySkins/Swordman/complete-v9'
WALK=WORK.parent/'accepted-walk-v8'
LABELS=['idle','walk','sit','pickup','attack1','attack2','hit','pose7','death','standby','attack3','attack4','cast']


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    WORK.mkdir(exist_ok=True);batches=[];sources=[]
    for sex in ('male','female'):
        src,spr,act,_,_=native_context('swordman',sex)
        by_group={};uses={}
        for ai,frames in enumerate(act.actions):
            for fi,f in enumerate(frames):
                for l in f.layers:
                    if l.index<0:continue
                    assert l.kind==0 and l.sx==l.sy==1 and l.angle==0
                    by_group.setdefault(ai//8,set()).add(l.index)
                    uses.setdefault(l.index,[]).append((ai,fi,l))
        planned=set()
        specs=[('idle-sit',sorted(by_group[0]|by_group[2]),5),
               ('pickup-hit',sorted(by_group[3]|by_group[6]),4 if sex=='male' else 5),
               ('floor-standby',sorted(by_group[7]|by_group[8]|by_group[9]),3),
               ('attack1',sorted(by_group[4]),4),('attack2',sorted(by_group[5]),4),
               ('attack3',sorted(by_group[10]-by_group[9]),3 if sex=='male' else 4),
               ('attack4a',sorted(by_group[11])[:7],4),('attack4b',sorted(by_group[11])[7:],4),
               ('cast',sorted(by_group[12]),4)]
        style=Image.new('RGBA',(1200,340))
        si=read_spr((WALK/f'assets/{sex}-angel-walk-v8.spr').read_bytes());sa=read_act((WALK/f'assets/{sex}-angel-walk-v8.act').read_bytes())
        for d in range(5):
            im,x,y=composite(si,sa.actions[8+d][0]);im=im.resize((round(im.width*.75),round(im.height*.75)),Image.Resampling.NEAREST)
            style.alpha_composite(im,(d*240+120+round(x*3)-im.width//2,280+round(y*3)-im.height//2))
        folder=WORK/'refs'/sex;folder.mkdir(parents=True,exist_ok=True);style.save(folder/'accepted-style.png')
        for name,ids,columns in specs:
            assert not (set(ids)&planned);planned.update(ids)
            records=[];minimum=np.array([-8.,-32.]);maximum=np.array([8.,8.])
            for index in ids:
                valid=[u for u in uses[index] if u[0]//8!=1 and u[2].mirror==0]
                assert valid,(sex,index,'no unmirrored reference')
                ai,fi,l=valid[0];im=rgba(spr,index,0);a=np.array(anchor(act.actions[ai][fi]),float)
                left=np.array([l.x-im.width//2,l.y-im.height//2],float)
                local=a-left
                relative_min=-local;relative_max=np.array(im.size)-local
                minimum=np.minimum(minimum,relative_min);maximum=np.maximum(maximum,relative_max)
                records.append(dict(sprite=index,representative_action=ai,representative_frame=fi,
                    native_anchor=a.tolist(),native_layer=[l.x,l.y],source_size=list(im.size),
                    head_anchor_in_source=local.tolist(),groups=sorted({LABELS[u[0]//8] for u in uses[index] if u[0]//8!=1})))
            origin=np.ceil(-minimum*4+24).astype(int)
            size=np.ceil(((maximum-minimum)*4+48)/32).astype(int)*32
            rows=math.ceil(len(ids)/columns);sheet=Image.new('RGB',(columns*int(size[0]),rows*int(size[1])),(0,255,0))
            pen=ImageDraw.Draw(sheet)
            for cell,rec in enumerate(records):
                image=rgba(spr,rec['sprite'],0).resize((rec['source_size'][0]*4,rec['source_size'][1]*4),Image.Resampling.NEAREST)
                cell_origin=np.array([(cell%columns)*size[0],(cell//columns)*size[1]])
                point=origin-np.array(rec['head_anchor_in_source'])*4
                sheet.paste(image,tuple((cell_origin+point).astype(int)),image)
                marker=cell_origin+origin+[0,-128]
                mx,my=marker.astype(int)
                pen.rectangle((mx-5,my-5,mx+5,my+5),fill=(255,0,255))
                rec.update(cell=cell,marker_in_cell=(origin+[0,-128]).tolist())
            path=folder/f'{name}-template.png';sheet.save(path)
            batch=dict(sex=sex,name=name,columns=columns,rows=rows,cells=len(ids),tile_size=size.tolist(),
                head_anchor_in_cell=origin.tolist(),marker_offset_native=[0,-32],
                template=str(path.relative_to(WORK)),style=str((folder/'accepted-style.png').relative_to(WORK)),
                source_spr_sha256=sha(src/'body.spr'),source_act_sha256=sha(src/'body.act'),poses=records)
            batches.append(batch)
            print(sex,name,'poses',len(ids),'grid',columns,rows,'tile',size.tolist(),flush=True)
        expected={i for i,values in uses.items() if any(ai//8!=1 for ai,fi,l in values)}
        assert planned==expected and not (planned&by_group[1])
        sources.append(dict(sex=sex,new_unique_drawings=len(planned),accepted_walking_frames=64))
    (WORK/'art-plan.json').write_text(json.dumps(dict(status='Building full native-pose set; accepted walks preserved',sources=sources,batches=batches),indent=2),encoding='utf8')


if __name__=='__main__':main()
