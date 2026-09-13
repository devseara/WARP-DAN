"""Extract original first-job poses and native Angel Wings for batch fitting."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
from audit_clan_wing_attachment import ROOT,ART
from grf_reader import GrfFile
from spr_reader import Spr
from sprite_formats import read_act,anchor
from render_native_wing_anatomy import rgba

GAME=Path('C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes')
OUT=ROOT/'Outputs/clan-body-skins/first-jobs-v1'
JOBS={'swordman':'검사','mage':'마법사','acolyte':'성직자','archer':'궁수','merchant':'상인','thief':'도둑'}

def main():
    OUT.mkdir(parents=True,exist_ok=True);grfs=[GrfFile(GAME/n) for n in ['palettedata.grf','spritedata.grf']]
    records=[];font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',12)
    try:
        for job,name in JOBS.items():
            for sex,k in [('male','남'),('female','여')]:
                stem=f'data/sprite/인간족/몸통/{k}/{name}_{k}'
                wing=f'data/sprite/로브/천사날개/{k}/{name}_{k}'
                folder=OUT/'source'/job/sex;folder.mkdir(parents=True,exist_ok=True);sources={}
                for kind,key in [('body',stem),('wing',wing)]:
                    for ext in ['spr','act']:
                        matches=[g for g in grfs if key+'.'+ext in g.entries]
                        assert matches,(job,sex,key,ext,'missing original')
                        raw=matches[0].read(key+'.'+ext);(folder/(kind+'.'+ext)).write_bytes(raw)
                        sources[kind+'.'+ext]=dict(archive=Path(matches[0].path).name,path=key+'.'+ext,sha256=hashlib.sha256(raw).hexdigest())
                spr=Spr((folder/'body.spr').read_bytes());act=read_act((folder/'body.act').read_bytes());wa=read_act((folder/'wing.act').read_bytes())
                rows=[]
                for ai,frames in enumerate(act.actions):
                    rows.append(dict(action=ai,frames=len(frames),speed=act.speeds[ai],body_sprites=[f.layers[0].index for f in frames],head_anchors=[anchor(f) for f in frames]))
                record=dict(job=job,sex=sex,native_name=name+'_'+k,body_stem=stem,sources=sources,sprites=len(spr.images),actions=len(act.actions),frames=sum(map(len,act.actions)),wing_actions=len(wa.actions),wing_frames=sum(map(len,wa.actions)),groups=[sum(map(len,act.actions[i:i+8])) for i in range(0,len(act.actions),8)],action_details=rows)
                records.append(record)
                # Native directions and each principal action at one scale.
                actions=[0,1,2,3,4,8,10,12,16,20,24,32,34,40,48,56,64,72,80,88,96]
                board=Image.new('RGB',(7*180,3*220),'#283746');p=ImageDraw.Draw(board)
                for i,ai in enumerate(actions):
                    if ai>=len(act.actions) or not act.actions[ai]:continue
                    f=act.actions[ai][0];x=i%7*180;y=i//7*220
                    for l in f.layers:
                        if l.index<0:continue
                        im=rgba(spr,l.index,l.kind)
                        if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                        im=im.resize((round(im.width*l.sx*2),round(im.height*l.sy*2)),Image.Resampling.NEAREST)
                        if l.angle:im=im.rotate(-l.angle,Image.Resampling.NEAREST,expand=True)
                        board.paste(im,(x+90+l.x*2-im.width//2,y+180+l.y*2-im.height//2),im)
                    p.text((x+6,y+4),f'{job} {sex} A{ai}',font=font,fill='white')
                board.save(folder/'native-action-overview.png')
                print(json.dumps({k:record[k] for k in ['job','sex','sprites','actions','frames','groups']}),flush=True)
        (OUT/'native-source-audit.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf8')
    finally:
        for g in grfs:g.close()

if __name__=='__main__':main()
