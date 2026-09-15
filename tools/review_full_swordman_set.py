"""Render every reopened full-set action beside native originals."""
import json,io,base64,argparse,hashlib
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from prepare_full_swordman_art import WORK,LABELS,native_context
from sprite_formats import read_spr,read_act,anchor
from render_native_wing_anatomy import rgba
from bake_clan_body_frames import composite

SIZE=640;ORIGIN=(320,460)

def body(sex,ai,fi,pair=None,job="swordman"):
    _,spr,act,heads,ha=native_context(job,sex)
    c=Image.new('RGBA',(SIZE,SIZE));ox,oy=ORIGIN
    f=act.actions[ai][fi] if pair is None else pair[1].actions[ai][fi]
    if pair is None:
        for l in f.layers:
            if l.index<0:continue
            im=rgba(spr,l.index,l.kind)
            if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            x,y=(l.x-im.width//2)*4,(l.y-im.height//2)*4
            im=im.resize((im.width*4,im.height*4),Image.Resampling.NEAREST);c.alpha_composite(im,(ox+x,oy+y))
    else:
        im,x,y=composite(pair[0],f);c.alpha_composite(im,(ox+x*4-im.width//2,oy+y*4-im.height//2))
    bounds=c.getbbox();assert bounds and min(bounds[:2])>0 and max(bounds[2:])<SIZE,(sex,ai,fi,'review clipped')
    return c

def head(sex,ai,fi,job="swordman",pair=None):
    _,_,act,heads,ha=native_context(job,sex);f=(act if pair is None else pair[1]).actions[ai][fi]
    hf=ha.actions[ai][min(fi,len(ha.actions[ai])-1)];bx,by=anchor(f);hx,hy=anchor(hf)
    c=Image.new('RGBA',(SIZE,SIZE));ox,oy=ORIGIN
    for l in hf.layers:
        if l.index<0:continue
        im=rgba(heads,l.index,l.kind)
        if l.mirror:im=im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        im=im.resize((im.width*4,im.height*4),Image.Resampling.NEAREST)
        if l.angle:im=im.rotate(-l.angle,Image.Resampling.NEAREST,expand=True)
        c.alpha_composite(im,(ox+(l.x+bx-hx)*4-im.width//2,oy+(l.y+by-hy)*4-im.height//2))
    bounds=c.getbbox()
    assert bounds and min(bounds[:2])>0 and max(bounds[2:])<SIZE,(sex,ai,fi,'head review clipped')
    return c

def joined(sex,ai,fi,pair=None,job="swordman"):
    c=body(sex,ai,fi,pair,job);c.alpha_composite(head(sex,ai,fi,job,pair));return c

def main(boards_only=False, work=WORK, job="swordman", stem="{sex}-angel-complete-v9"):
    plan=json.loads((work/'art-plan.json').read_text(encoding='utf8'));pairs={};data={};checks=[]
    review=work/'review';review.mkdir(exist_ok=True);unique_images=set()
    image_dir=review/'images';image_dir.mkdir(exist_ok=True)
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15)
    for sex in ('male','female'):
        pair=(read_spr((work/'assets'/(stem.format(sex=sex)+'.spr')).read_bytes()),read_act((work/'assets'/(stem.format(sex=sex)+'.act')).read_bytes()));pairs[sex]=pair
        for batch in plan['batches']:
            if batch['sex']!=sex:continue
            count=len(batch['poses']);cols=3;rows=(count+cols-1)//cols
            board=Image.new('RGB',(cols*480,rows*270),'#283746');draw=ImageDraw.Draw(board)
            for n,rec in enumerate(batch['poses']):
                ai,fi=rec['representative_action'],rec['representative_frame'];x=n%cols*480;y=n//cols*270
                draw.text((x+8,y+4),f"{sex} SPR {rec['sprite']} / A{ai} F{fi}: original | new",font=font,fill='white')
                for k,p in enumerate((None,pair)):
                    im=joined(sex,ai,fi,p,job).resize((240,240),Image.Resampling.NEAREST);board.paste(im,(x+k*240,y+26),im)
            board.save(review/f'{sex}-{batch["name"]}-comparison.png')
        if boards_only:continue
        data[sex]=[]
        for ai,frames in enumerate(pair[1].actions):
            records=[]
            # Identical rendered poses/heads share one PNG across all actions.
            for fi,f in enumerate(frames):
                paths=[]
                for label,im in [('original',body(sex,ai,fi,job=job)),('angel',body(sex,ai,fi,pair,job)),('original-head',head(sex,ai,fi,job)),('angel-head',head(sex,ai,fi,job,pair))]:
                    encoded=io.BytesIO();im.save(encoded,format='PNG');raw=encoded.getvalue();digest=hashlib.sha256(raw).hexdigest()
                    path=image_dir/(digest+'.png')
                    if digest not in unique_images:path.write_bytes(raw);unique_images.add(digest)
                    paths.append(path.relative_to(work).as_posix())
                records.append(paths)
            data[sex].append(dict(action=ai,group=LABELS[ai//8],direction=ai%8,ms=round(pair[1].speeds[ai]*25),frames=records))
        checks.append(dict(sex=sex,actions=len(data[sex]),frame_uses=sum(len(a['frames']) for a in data[sex]),review_canvas_clipping=False))
    if boards_only:return
    html='''<!doctype html><meta charset="utf-8"><title>Complete Angel Swordman SPR/ACT review</title>
<style>*{box-sizing:border-box}body{background:#172330;color:#f1f4f8;font:15px system-ui;margin:22px}h1{font-size:25px}p{max-width:1100px;line-height:1.5;color:#c7d3df}button,select{font:inherit;color:inherit;background:#293d51;border:1px solid #70849a;padding:7px;border-radius:5px}label{display:inline-flex;align-items:center;gap:6px}.controls{display:flex;align-items:center;gap:12px;flex-wrap:wrap;margin:16px 0}#stage{display:grid;grid-template-columns:repeat(2,max-content);gap:16px;overflow:auto}figure{margin:0}figcaption{margin-bottom:5px}canvas{image-rendering:pixelated;display:block;background:#283746}.checker canvas{background:repeating-conic-gradient(#555 0% 25%,#333 0% 50%) 0/16px 16px}.white canvas{background:white}.black canvas{background:black}.magenta canvas{background:magenta}a{color:#b7d5ff}#readout{font:14px monospace}</style>
<h1>Complete Angel Swordman · SPR/ACT review</h1>
<p>Male and female: all 104 native actions, 456 frame uses each. Idle, accepted walking, sitting, pickup, four attack groups, hit, native action 7, death, standby and casting. Original frame counts, timing and head anchors are retained. Walking pixels and placement match accepted v8. This is the complete body artwork review; head and equipment are separate game sprites.</p>
<p><a href="assets/male-angel-complete-v9.act">Male ACT</a> · <a href="assets/male-angel-complete-v9.spr">Male SPR</a> · <a href="assets/female-angel-complete-v9.act">Female ACT</a> · <a href="assets/female-angel-complete-v9.spr">Female SPR</a></p>
<div class="controls"><label>Action group <select id="group"></select></label><label>Direction <select id="dir"></select></label><button id="play">Play</button><button id="prev">Previous frame</button><button id="next">Next frame</button><input id="slider" type="range" min="0" value="0"><output id="status"></output></div>
<div class="controls"><label><input type="checkbox" id="heads" checked>Native heads</label><label>Speed <select id="speed"><option value="1">Native</option><option value=".5">Half</option><option value=".25">Quarter</option></select></label><label>Zoom <select id="zoom"><option value=".25">Game size</option><option value=".5" selected>2× game size</option><option value="1">Export pixels (4×)</option><option value="2">8× game size</option></select></label><label>Background <select id="bg"><option value="slate">Slate</option><option value="checker">Checker</option><option value="black">Black</option><option value="white">White</option><option value="magenta">Magenta</option></select></label></div>
<div id="stage"></div><p id="readout"></p>
<script>const DATA=__DATA__,LABELS=__LABELS__,$=id=>document.getElementById(id),cache=new Map();let frame=0,playing=false,timer,token=0;const figures=[];
for(let i=0;i<LABELS.length;i++)$('group').add(new Option(LABELS[i],i));for(let i=0;i<8;i++)$('dir').add(new Option(i,i));const query=new URLSearchParams(location.search),initialAction=Math.max(0,Math.min(103,Number(query.get('action'))||0));$('group').value=Math.floor(initialAction/8);$('dir').value=initialAction%8;frame=Math.max(0,Number(query.get('frame'))||0);
for(const sex of ['male','female'])for(const kind of [0,1]){let fig=document.createElement('figure'),cap=document.createElement('figcaption'),c=document.createElement('canvas');cap.textContent=sex+' / '+(kind?'Angel v9':'Original');c.width=c.height=640;fig.append(cap,c);$('stage').append(fig);figures.push({sex,kind,c});c.onmousemove=e=>{let r=c.getBoundingClientRect(),x=Math.floor((e.clientX-r.left)*640/r.width),y=Math.floor((e.clientY-r.top)*640/r.height);if(x<0||y<0||x>=640||y>=640)return;let rgba=c.getContext('2d').getImageData(x,y,1,1).data;$('readout').textContent=`${cap.textContent}: world (${(x-320)/4}, ${(y-460)/4}), RGBA [${[...rgba]}]`;};}
function action(){return Number($('group').value)*8+Number($('dir').value)}
function load(src){if(!cache.has(src))cache.set(src,new Promise((res,rej)=>{let im=new Image();im.onload=()=>res(im);im.onerror=()=>rej(Error(src));im.src=src}));return cache.get(src)}
async function draw(){let id=++token,a=action(),count=DATA.male[a].frames.length;frame=(frame+count)%count;$('slider').max=count-1;$('slider').value=frame;$('status').textContent=`Action ${a} · Frame ${frame}/${count-1} · ${DATA.male[a].ms} ms`;$('play').textContent=playing?'Pause':'Play';$('stage').className=$('bg').value;
await Promise.all(figures.map(async ({sex,kind,c})=>{let row=DATA[sex][a].frames[frame],im=await load(row[kind]),h=$('heads').checked?await load(row[kind+2]):null;if(id!==token)return;let ctx=c.getContext('2d');ctx.clearRect(0,0,640,640);ctx.drawImage(im,0,0);if(h)ctx.drawImage(h,0,0);c.style.width=c.style.height=640*Number($('zoom').value)+'px';}));}
function schedule(){clearTimeout(timer);if(playing)timer=setTimeout(async()=>{frame++;await draw();schedule()},DATA.male[action()].ms/Number($('speed').value))}
function step(n){playing=false;frame+=n;draw();schedule()}
$('play').onclick=()=>{playing=!playing;draw();schedule()};$('prev').onclick=()=>step(-1);$('next').onclick=()=>step(1);$('slider').oninput=()=>{playing=false;frame=Number($('slider').value);draw();schedule()};for(const id of ['group','dir'])$(id).onchange=()=>{frame=0;draw();schedule()};for(const id of ['heads','zoom','bg'])$(id).onchange=draw;$('speed').onchange=schedule;draw();</script>'''
    html=html.replace('__DATA__',json.dumps(data,separators=(',',':'))).replace('__LABELS__',json.dumps(['Idle','Walk (accepted v8)','Sit','Pickup','Attack 1','Attack 2','Hit','Native action 7','Death','Standby','Attack 3','Attack 4','Cast']))
    if job!='swordman':
        html=html.replace('Swordman',job.title()).replace('accepted walking','walking').replace('Walking pixels and placement match accepted v8. ','').replace('Walk (accepted v8)','Walk').replace('Angel v9','Angel '+job.title()+' '+stem.rsplit('-',1)[-1])
        for sex in ('male','female'):html=html.replace(sex+'-angel-complete-v9',stem.format(sex=sex))
    html=html.replace('Complete Angel '+job.title(),'Angel '+job.title()+' '+stem.rsplit('-',1)[-1])
    if plan.get('head_attachment_policy')=='fit-to-painted-collar':
        html=html.replace('Original frame counts, timing and head anchors are retained.', 'Original frame counts and timing are retained. Each pair uses its own ACT head attachment offsets; body artwork is unchanged.')
    (work/'full-action-review.html').write_text(html,encoding='utf8')
    (work/'review-coverage.json').write_text(json.dumps(dict(coverage=checks,rendered_from_reopened_exports=True,native_head_artwork=True,pair_specific_head_anchors=True,frame_image_references=456*2*4,unique_review_pngs=len(unique_images)),indent=2),encoding='utf8')
    print(json.dumps(checks))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--boards-only',action='store_true');a=p.parse_args();main(a.boards_only)
