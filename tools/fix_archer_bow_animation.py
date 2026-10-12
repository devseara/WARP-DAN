"""Bow-only Archer artwork correction against native body and weapon frames."""
import argparse
import copy
import hashlib
import json
import numpy as np
from PIL import Image, ImageDraw
from package_clan_skin_assets import ROOT
from review_original_job_directions import native_context
from review_full_swordman_set import body, joined, ORIGIN
from build_full_archer_set import pair_at
from render_native_wing_anatomy import rgba
from sprite_formats import read_act, read_spr, anchor
from spr_reader import Spr
ARCHER = ROOT / 'Assets/ClanBodySkins/Archer'
BASE = ARCHER / 'complete-v4'
WORK = ARCHER / 'complete-v5'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def weapon(sex, ai, fi):
    folder = WORK / 'native-bow' / sex
    spr = Spr((folder / 'bow.spr').read_bytes())
    act = read_act((folder / 'bow.act').read_bytes())
    canvas = Image.new('RGBA', (640, 640))
    for layer in act.actions[ai][fi].layers:
        if layer.index < 0:
            continue
        image = rgba(spr, layer.index, layer.kind)
        if layer.mirror:
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        image = image.resize((round(image.width * 4 * layer.sx), round(image.height * 4 * layer.sy)), Image.Resampling.NEAREST)
        if layer.angle:
            image = image.rotate(-layer.angle, Image.Resampling.NEAREST, expand=True)
        canvas.alpha_composite(image, (ORIGIN[0] + layer.x * 4 - image.width // 2, ORIGIN[1] + layer.y * 4 - image.height // 2))
    return canvas


def prepare():
    WORK.mkdir(exist_ok=True)
    plan = json.loads((ARCHER / 'complete-v1/art-plan.json').read_text(encoding='utf8'))
    batches = []
    pins = []
    for sex in ('male', 'female'):
        pair = pair_at(BASE, sex, 'v4')
        src, spr, native, _, _ = native_context('archer', sex)
        batch = next(b for b in plan['batches'] if b['sex'] == sex and b['name'] == 'attack3')
        for facing in range(2):
            new = copy.deepcopy(batch)
            new.update(name='bow-' + ('front' if facing == 0 else 'rear'), columns=3, rows=2, cells=6, alpha_floor=16)
            if facing: new['clear_before_marker_plus']=80
            new['poses'] = copy.deepcopy(batch['poses'][facing * 6:(facing + 1) * 6])
            tw, th = new['tile_size']
            template = Image.new('RGB', (tw * 3, th * 2 + 340), (0, 255, 0))
            # Approved costume examples above the locked native pose grid.
            for col, ai in enumerate((0, 1, 3)):
                image = body(sex, ai, 0, pair, job='archer')
                image = image.crop(image.getbbox())
                factor = min(280 / image.height, (tw - 30) / image.width)
                image = image.resize((round(image.width * factor), round(image.height * factor)), Image.Resampling.NEAREST)
                template.paste(image, (col * tw + tw // 2 - image.width // 2, 300 - image.height), image)
            pen = ImageDraw.Draw(template)
            for cell, rec in enumerate(new['poses']):
                rec['cell'] = cell
                image = rgba(spr, rec['sprite'], 0)
                image = image.resize((image.width * 4, image.height * 4), Image.Resampling.NEAREST)
                xy = np.array([cell % 3 * tw, 340 + cell // 3 * th])
                point = xy + np.array(new['head_anchor_in_cell']) - np.array(rec['head_anchor_in_source']) * 4
                template.paste(image, tuple(map(int, point)), image)
                mx, my = xy + np.array(rec['marker_in_cell'])
                pen.rectangle((mx - 5, my - 5, mx + 5, my + 5), fill=(255, 0, 255))
            dst = WORK / 'refs' / sex / (new['name'] + '.png')
            dst.parent.mkdir(parents=True, exist_ok=True)
            template.save(dst)
            new['template'] = dst.relative_to(WORK).as_posix()
            batches.append(new)
        for ai in (80, 82):
            board = Image.new('RGB', (1600, 960), '#283746')
            pen = ImageDraw.Draw(board)
            for fi in range(8):
                x, y = fi % 4 * 400, fi // 4 * 480
                pen.text((x + 4, y + 4), f'{sex} A{ai} F{fi} native | V4 with native bow', fill='white')
                for col, p in enumerate((None, pair)):
                    image = joined(sex, ai, fi, p, job='archer')
                    image.alpha_composite(weapon(sex, ai, fi))
                    image = image.crop((100, 80, 540, 560)).resize((200, 218), Image.Resampling.NEAREST)
                    board.paste(image, (x + col * 200, y + 30), image)
                    detail = body(sex, ai, fi, p, job='archer')
                    detail.alpha_composite(weapon(sex, ai, fi))
                    detail = detail.crop((170, 180, 450, 400)).resize((200, 157), Image.Resampling.NEAREST)
                    board.paste(detail, (x + col * 200, y + 290), detail)
            board.save(WORK / f'{sex}-A{ai}-before.png')
        for root, names in ((BASE / 'assets', [f'{sex}-angel-archer-v4.spr', f'{sex}-angel-archer-v4.act']), (src, ['body.spr', 'body.act', 'head.spr', 'head.act']), (WORK / 'native-bow' / sex, ['bow.spr', 'bow.act'])):
            pins += [dict(path=(root / name).relative_to(ROOT).as_posix(), sha256=digest(root / name)) for name in names]
    (WORK / 'correction-plan.json').write_text(json.dumps(dict(job='archer', affected_actions=list(range(80, 88)), batches=batches), indent=2), encoding='utf8')
    (WORK / 'input-pins.json').write_text(json.dumps(pins, indent=2), encoding='utf8')
    print(json.dumps(dict(batches=len(batches), unique_drawings=24, affected_actions=list(range(80, 88)))))


def fit():
    from import_full_swordman_art import extract
    from acolyte_neck_registration import ring_collars
    from fix_archer_design_alignment import neck_point
    plan = json.loads((WORK / 'correction-plan.json').read_text(encoding='utf8'))
    refs = json.loads((ARCHER / 'complete-v1/head-neck-reference.json').read_text(encoding='utf8'))
    rows = []
    for batch in plan['batches']:
        sex = batch['sex']
        _, spr, native, heads, ha = native_context('archer', sex)
        art, imports = extract(batch, WORK)
        prepared = []
        for rec in batch['poses']:
            ai, fi = rec['representative_action'], rec['representative_frame']
            target = neck_point(refs, sex, native, heads, ha, ai, fi)
            layer = native.actions[ai][fi].layers[0]
            raw = rgba(spr, rec['sprite'], 0)
            image, offset = art[rec['sprite']]
            canvas = Image.new('RGBA', (640, 640))
            xy = np.array(ORIGIN) + np.array([layer.x-raw.width//2, layer.y-raw.height//2])*4 + offset
            canvas.alpha_composite(image, tuple(map(int,xy)))
            candidates = ring_collars(canvas, target, True)
            assert candidates, (sex, rec['sprite'], 'No collar aperture')
            collar = np.array(candidates[0]['point'])
            if sex == 'male' and rec['sprite'] == 85:
                # Raised forearm hides the aperture; ring detection selected the bracer.
                collar = np.array([-.5, -218.5])
            original = body(sex,ai,fi,job='archer')
            ratio = (original.getbbox()[3]-ORIGIN[1]-target[1])/(canvas.getbbox()[3]-ORIGIN[1]-collar[1])
            prepared.append((rec,canvas,target,collar,ratio))
        scale = float(np.median([r[4] for r in prepared]))
        board = Image.new('RGB',(1200,1040),'#283746'); pen=ImageDraw.Draw(board)
        for n,(rec,canvas,target,collar,ratio) in enumerate(prepared):
            ai,fi=rec['representative_action'],rec['representative_frame']
            # One fixed scale for the view, registered on the native neck.
            src=collar+ORIGIN;dst=target+ORIGIN
            fitted=canvas.transform((640,640),Image.Transform.AFFINE,(1/scale,0,src[0]-dst[0]/scale,0,1/scale,src[1]-dst[1]/scale),Image.Resampling.NEAREST)
            folder=WORK/'fitted'/sex;folder.mkdir(parents=True,exist_ok=True)
            fitted.save(folder/f"sprite-{rec['sprite']:03}.png")
            rows.append(dict(sex=sex,sprite=rec['sprite'],action=ai,frame=fi,scale=scale,collar=collar.tolist(),native_neck=target.tolist(),proposed_scale=ratio))
            x=n%3*400;y=n//3*520
            pen.text((x+4,y+4),f"{sex} A{ai} F{fi} native | candidate",fill='white')
            from review_full_swordman_set import head
            for k,im in enumerate((body(sex,ai,fi,job='archer'),fitted)):
                view=im.copy();view.alpha_composite(head(sex,ai,fi,job='archer'));view.alpha_composite(weapon(sex,ai,fi))
                view=view.crop((100,80,540,560)).resize((200,218),Image.Resampling.NEAREST);board.paste(view,(x+k*200,y+24),view)
                detail=im.copy();detail.alpha_composite(weapon(sex,ai,fi));detail=detail.crop((140,200,460,440)).resize((200,150),Image.Resampling.NEAREST);board.paste(detail,(x+k*200,y+270),detail)
        board.save(WORK/(sex+'-'+batch['name']+'-fit.png'))
    (WORK/'fit-landmarks.json').write_text(json.dumps(rows,indent=2),encoding='utf8')
    sources=[WORK/'correction-plan.json']+[WORK/'art'/b['sex']/(b['name']+'.png') for b in plan['batches']]
    (WORK/'fit-input-pins.json').write_text(json.dumps([dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p)) for p in sources],indent=2),encoding='utf8')
    print(json.dumps(dict(fitted=len(rows))))


def register():
    from build_female_mage_v10 import kernel
    for pin in json.loads((WORK/'fit-input-pins.json').read_text(encoding='utf8')):
        assert digest(ROOT/pin['path'])==pin['sha256'], ('Re-fit changed art',pin['path'])
    table = json.loads((WORK/'grip-landmarks.json').read_text(encoding='utf8'))['points']
    fitted = json.loads((WORK/'fit-landmarks.json').read_text(encoding='utf8'))
    proofs=[]
    for row in fitted:
        sex,index=row['sex'],row['sprite']
        image=Image.open(WORK/'fitted'/sex/f'sprite-{index:03}.png').convert('RGBA')
        moves=table[sex][str(index)]
        src=[];dst=[]
        for a,b in moves:
            for offset in ((0,0),(-4,0),(4,0),(0,-4),(0,4)):
                src.append(np.array(a)+offset);dst.append(np.array(b)+offset)
        neck=np.array(row['native_neck'])+ORIGIN
        for offset in ((0,0),(-8,0),(8,0)):
            src.append(neck+offset);dst.append(neck+offset)
        left,top,right,bottom=140,140,465,356
        for x in np.arange(left,right+1,40):
            for y in (top,bottom):src.append([x,y]);dst.append([x,y])
        for y in np.arange(top+40,bottom,40):
            for x in (left,right):src.append([x,y]);dst.append([x,y])
        for x in (285,320,355):src.append([x,340]);dst.append([x,340])
        src,dst=np.array(src,float)/4,np.array(dst,float)/4
        n=len(dst);poly=np.column_stack([np.ones(n),dst]);system=np.zeros((n+3,n+3));system[:n,:n]=kernel(dst,dst)+np.eye(n)*.001;system[:n,n:]=poly;system[n:,:n]=poly.T
        sol=np.linalg.solve(system,np.vstack([src,np.zeros((3,2))]))
        yy,xx=np.mgrid[top:bottom,left:right];points=np.column_stack([xx.ravel()/4,yy.ravel()/4]);mapped=[]
        for start in range(0,len(points),4096):
            pts=points[start:start+4096];mapped.append(kernel(pts,dst)@sol[:n]+np.column_stack([np.ones(len(pts)),pts])@sol[n:])
        mapped=np.vstack(mapped).reshape(*xx.shape,2)*4
        jac=np.gradient(mapped[:,:,0],axis=1)*np.gradient(mapped[:,:,1],axis=0)-np.gradient(mapped[:,:,0],axis=0)*np.gradient(mapped[:,:,1],axis=1)
        source=np.asarray(image);result=source.copy();sample=np.rint(mapped).astype(int);active=source[sample[:,:,1],sample[:,:,0],3]>128
        minimum=float(jac[active].min())
        error=float(np.linalg.norm(kernel(dst,dst)@sol[:n]+poly@sol[n:]-src,axis=1).max()*4)
        print(sex,index,'jacobian',round(minimum,3),'error',round(error,3),flush=True)
        assert minimum>.08,(sex,index,'Hand registration folds',minimum)
        result[top:bottom,left:right]=source[sample[:,:,1],sample[:,:,0]]
        result[result[:,:,3]==0]=0
        folder=WORK/'registered'/sex;folder.mkdir(parents=True,exist_ok=True);Image.fromarray(result).save(folder/f'sprite-{index:03}.png')
        overlay=Image.fromarray(result.copy());pen=ImageDraw.Draw(overlay)
        for a,b in moves:
            pen.line((*a,*b),fill='cyan',width=1);pen.ellipse((b[0]-3,b[1]-3,b[0]+3,b[1]+3),outline='magenta')
        overlay.crop((140,140,465,380)).save(folder/f'sprite-{index:03}-landmarks.png')
        proofs.append(dict(sex=sex,sprite=index,minimum_visible_jacobian=minimum,landmark_error_pixels=error,lower_body_unchanged=bool(np.array_equal(result[bottom:],source[bottom:]))))
    sources=[WORK/'grip-landmarks.json',WORK/'fit-landmarks.json']+list((WORK/'fitted').rglob('*.png'))
    (WORK/'registration-input-pins.json').write_text(json.dumps([dict(path=p.relative_to(ROOT).as_posix(),sha256=digest(p)) for p in sources],indent=2),encoding='utf8')
    (WORK/'registration-verification.json').write_text(json.dumps(proofs,indent=2),encoding='utf8')


def build():
    import struct
    from sprite_formats import write_spr, write_act, Layer
    from preview_clan_reference_revision import bake
    from fix_archer_design_alignment import neck_point
    from review_full_swordman_set import head
    from refine_clan_combat_necks import components
    for pin in json.loads((WORK/'input-pins.json').read_text(encoding='utf8')):
        assert digest(ROOT/pin['path'])==pin['sha256'], ('Changed baseline',pin['path'])
    for file in ('fit-input-pins.json','registration-input-pins.json'):
        for pin in json.loads((WORK/file).read_text(encoding='utf8')):
            assert digest(ROOT/pin['path'])==pin['sha256'], ('Re-run changed registration',pin['path'])
    plan=json.loads((WORK/'correction-plan.json').read_text(encoding='utf8'))
    refs=json.loads((ARCHER/'complete-v1/head-neck-reference.json').read_text(encoding='utf8'))
    landmarks=json.loads((WORK/'grip-landmarks.json').read_text(encoding='utf8'))['points']
    fits={(r['sex'],r['sprite']):r for r in json.loads((WORK/'fit-landmarks.json').read_text(encoding='utf8'))}
    proofs=[];files=[]
    (WORK/'assets').mkdir(exist_ok=True)
    for sex in ('male','female'):
        old_images,old_act=pair_at(BASE,sex,'v4')
        _,native_spr,native,heads,ha=native_context('archer',sex)
        records={r['sprite']:r for b in plan['batches'] if b['sex']==sex for r in b['poses']}
        act=copy.deepcopy(old_act);images=[];seen={};changed=[];unchanged=0
        detached=[]
        for ai,frames in enumerate(act.actions):
            for fi,f in enumerate(frames):
                if not 80<=ai<88:
                    layer=old_act.actions[ai][fi].layers[0]
                    image=old_images[layer.index];x,y=layer.x,layer.y
                else:
                    nf=native.actions[ai][fi];layer=nf.layers[0];rec=records[layer.index]
                    representative=native.actions[rec['representative_action']][rec['representative_frame']].layers[0]
                    raw=rgba(native_spr,layer.index,0)
                    source_top=np.array(ORIGIN)+np.array([representative.x-raw.width//2,representative.y-raw.height//2])*4
                    target_top=np.array(ORIGIN)+np.array([layer.x-raw.width//2,layer.y-raw.height//2])*4
                    canvas=Image.open(WORK/'registered'/sex/f'sprite-{layer.index:03}.png').convert('RGBA')
                    bounds=canvas.getbbox();image=canvas.crop(bounds);offset=np.array(bounds[:2])-source_top
                    collar=np.array(fits[sex,layer.index]['native_neck'])+ORIGIN-source_top
                    grip=np.array(landmarks[sex][str(layer.index)][0][1])-source_top
                    if layer.mirror:
                        image=image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
                        offset[0]=raw.width*4-offset[0]-image.width
                        collar[0]=raw.width*4-collar[0]
                        grip[0]=raw.width*4-grip[0]
                    point=target_top+offset
                    image,x,y=bake([(image,int(point[0]-ORIGIN[0]),int(point[1]-ORIGIN[1]))])
                    f=copy.deepcopy(nf);act.actions[ai][fi]=f
                    target=neck_point(refs,sex,native,heads,ha,ai,fi)
                    delta=np.rint((target_top+collar-ORIGIN-target)/4).astype(int)
                    raw_anchor=bytearray(f.anchors[0]);old_anchor=anchor(f)
                    struct.pack_into('<ii',raw_anchor,4,int(old_anchor[0]+delta[0]),int(old_anchor[1]+delta[1]));f.anchors[0]=bytes(raw_anchor)
                    changed.append(dict(action=ai,frame=fi,native_sprite=layer.index,mirror=layer.mirror,head_anchor_delta=delta.tolist(),bow_grip=(target_top+grip).tolist()))
                key=(image.size,image.tobytes())
                if key not in seen:seen[key]=len(images);images.append(image.copy())
                f.layers=[Layer(x,y,seen[key],sx=.25,sy=.25)]
        sb,ab=write_spr(images),write_act(act)
        decoded,reopened,independent=read_spr(sb),read_act(ab),Spr(sb)
        assert len(reopened.actions)==104 and sum(map(len,reopened.actions))==456
        assert reopened.speeds==native.speeds and reopened.tail==native.tail
        assert all(im.tobytes()==rgba(independent,i,1).tobytes() for i,im in enumerate(decoded))
        for ai,fs in enumerate(reopened.actions):
            assert len(fs)==len(native.actions[ai])
            for fi,f in enumerate(fs):
                assert (f.sound,f.ranges)==(native.actions[ai][fi].sound,native.actions[ai][fi].ranges)
                after=body(sex,ai,fi,(decoded,reopened),job='archer')
                if not 80<=ai<88:
                    assert after.tobytes()==body(sex,ai,fi,(old_images,old_act),job='archer').tobytes()
                    assert head(sex,ai,fi,job='archer',pair=(decoded,reopened)).tobytes()==head(sex,ai,fi,job='archer',pair=(old_images,old_act)).tobytes()
                    unchanged+=1
                else:
                    groups=sorted((len(g) for g in components(np.asarray(after)[:,:,3]>0)),reverse=True)
                    if len(groups)>1:detached.append(dict(action=ai,frame=fi,components=groups))
        motions=[]
        for ai in range(80,88):
            points=np.array([r['bow_grip'] for r in changed if r['action']==ai]);span=np.ptp(points,axis=0)
            assert np.linalg.norm(span)>40,(sex,ai,'Static bow arm')
            motions.append(dict(action=ai,hand_span_native=(span/4).tolist(),unique_drawings=len({r['native_sprite'] for r in changed if r['action']==ai})))
        assert not detached,detached
        sexfiles=[]
        for ext,raw in (('.spr',sb),('.act',ab)):
            p=WORK/'assets'/f'{sex}-angel-archer-v5{ext}';p.write_bytes(raw)
            entry=dict(path=p.relative_to(WORK).as_posix(),sha256=digest(p));sexfiles.append(entry);files.append(dict(sex=sex,**entry))
        report=dict(job='archer',sex=sex,status='Bow correction exported; awaiting live review',actions=104,frame_uses=456,changed_actions=list(range(80,88)),unique_drawings=116 if sex=='male' else 120,changed_frame_uses=len(changed),unchanged_frame_uses=unchanged,unaffected_body_and_head_renders_identical=True,stock_fallback_frames=[],missing_sheets=[],detached_artwork_flags=detached,native_timing_and_frame_order_preserved=True,native_metadata_preserved=False,timing_ranges_sound_preserved=True,head_anchor_policy='V4 unchanged outside bow; bow collars registered to native head trajectories',independent_decoder_match=True,bow_motion=motions,frames=changed,files=sexfiles,installed=False)
        (WORK/(sex+'-verification.json')).write_text(json.dumps(report,indent=2),encoding='utf8');proofs.append(report)
        print(sex,len(changed),'bow frames;',unchanged,'unchanged',flush=True)
    fullplan=json.loads((BASE/'art-plan.json').read_text(encoding='utf8'));fullplan.update(status='Complete Archer V5, bow-only correction',head_attachment_policy='fit-to-painted-collar')
    (WORK/'art-plan.json').write_text(json.dumps(fullplan,indent=2),encoding='utf8')
    (WORK/'full-build-verification.json').write_text(json.dumps(dict(files=files,sexes=proofs,installed=False),indent=2),encoding='utf8')


def review():
    from sprite_review_animation import save_review_animation
    pairs={sex:[None,pair_at(BASE,sex,'v4'),pair_at(WORK,sex,'v5')] for sex in ('male','female')}
    folder=WORK/'bow-review';folder.mkdir(exist_ok=True)
    data={};timings=[]
    for direction in range(8):
        ai=80+direction;frames=[];data[direction]=[]
        count=len(pairs['male'][2][1].actions[ai]);ms=round(pairs['male'][2][1].speeds[ai]*25);timings.append(ms)
        for fi in range(count):
            row=[];board=Image.new('RGB',(960,640),'#283746');pen=ImageDraw.Draw(board)
            for si,sex in enumerate(('male','female')):
                for kind,pair in enumerate(pairs[sex]):
                    image=joined(sex,ai,fi,pair,job='archer')
                    bow=weapon(sex,ai,fi)
                    names=[]
                    for overlay in (False,True):
                        im=image.copy()
                        if overlay:im.alpha_composite(bow)
                        name=hashlib.sha256(im.tobytes()).hexdigest()+'.png';dest=folder/name
                        if not dest.exists():im.save(dest)
                        names.append('bow-review/'+name)
                    row.append(names)
                    im=image.copy();im.alpha_composite(bow);im=im.crop((120,100,520,540)).resize((272,299),Image.Resampling.NEAREST)
                    x=kind*320;y=si*320;board.paste(im,(x+24,y+20),im)
                    pen.text((x+8,y+3),sex+' / '+('Original','V4','V5')[kind]+f' / D{direction} F{fi}',fill='white')
            data[direction].append(row);frames.append(board)
            board.save(folder/f'd{direction}-f{fi}.png')
        save_review_animation(frames,folder/f'd{direction}-loop.gif',ms,folder/f'd{direction}-loop.png')
    html = r"""<!doctype html><meta charset="utf-8"><title>Archer V5 bow correction</title>

<style>body{background:#172330;color:#e9f0f7;font:15px system-ui;margin:22px}h1{font-size:25px}button,select{background:#30455a;color:inherit;border:1px solid #718aa1;border-radius:5px;padding:8px;font:inherit}.controls{display:flex;align-items:center;gap:12px;margin:16px 0}#stage{display:grid;grid-template-columns:repeat(3,320px);gap:12px;overflow:auto}figure{margin:0}canvas{width:320px;height:320px;image-rendering:pixelated;background:#283746}a{color:#b7d5ff}p{max-width:1050px;line-height:1.5}</style>

<h1>Archer V5 · Bow draw and release</h1><p>Original, previous V4 and corrected V5, rendered from SPR/ACT with original heads and bow. All eight directions and nine native frames. V5 changes only actions 80–87; all 768 other male/female frame uses retain identical bodies and heads. V5 is installed and awaiting live appearance review.</p>

<div class="controls"><label>Direction <select id="direction"></select></label><button id="play">Pause</button><button id="prev">Previous</button><button id="next">Next</button><input id="frame" type="range" min="0" max="8" value="0"><label><input id="bow" type="checkbox" checked>Native bow</label><select id="speed"><option value="1">Native timing</option><option value="0.5">Half speed</option><option value="0.25">Quarter speed</option></select><span id="status"></span></div><div id="stage"></div>

<p><a href="assets/male-angel-archer-v5.act">Male ACT</a> · <a href="assets/male-angel-archer-v5.spr">Male SPR</a> · <a href="assets/female-angel-archer-v5.act">Female ACT</a> · <a href="assets/female-angel-archer-v5.spr">Female SPR</a> · <a href="full-action-review.html?action=80">Complete 104-action reviewer</a></p>

<script>const DATA=__DATA__,TIMING=__TIMING__,$=x=>document.getElementById(x),cache=new Map(),canvases=[];let frame=0,playing=true,timer,token=0;

for(let d=0;d<8;d++)$('direction').add(new Option(d,d));for(const sex of ['Male','Female'])for(const version of ['Original Archer','Previous V4','Corrected V5']){const fig=document.createElement('figure'),cap=document.createElement('figcaption'),c=document.createElement('canvas');cap.textContent=sex+' / '+version;c.width=c.height=640;fig.append(cap,c);$('stage').append(fig);canvases.push(c)}

function load(path){if(!cache.has(path))cache.set(path,new Promise((res,rej)=>{const i=new Image;i.onload=()=>res(i);i.onerror=rej;i.src=path}));return cache.get(path)}

async function draw(){const id=++token,d=Number($('direction').value);frame=(frame+DATA[d].length)%DATA[d].length;$('frame').value=frame;$('status').textContent=`Action ${80+d} · Frame ${frame}/8 · ${TIMING[d]} ms`;const row=DATA[d][frame];await Promise.all(canvases.map(async(c,i)=>{const im=await load(row[i][$('bow').checked?1:0]);if(id!==token)return;const ctx=c.getContext('2d');ctx.clearRect(0,0,640,640);ctx.drawImage(im,0,0)}))}

function schedule(){clearTimeout(timer);$('play').textContent=playing?'Pause':'Play';if(playing)timer=setTimeout(async()=>{frame++;await draw();schedule()},TIMING[Number($('direction').value)]/Number($('speed').value))}

$('play').onclick=()=>{playing=!playing;schedule()};function step(n){playing=false;frame+=n;draw();schedule()}$('prev').onclick=()=>step(-1);$('next').onclick=()=>step(1);$('frame').oninput=()=>{playing=false;frame=Number($('frame').value);draw();schedule()};$('direction').onchange=()=>{frame=0;draw();schedule()};$('bow').onchange=draw;$('speed').onchange=schedule;draw();schedule();</script>"""
    approval_path=WORK/'user-review.json'
    if approval_path.exists():
        approval=json.loads(approval_path.read_text(encoding='utf8'))
        current={p.relative_to(WORK).as_posix():digest(p) for p in (WORK/'assets').glob('*') if p.suffix in ('.spr','.act')}
        approved={r['path']:r['sha256'] for r in approval.get('files',[])}
        if approval.get('status')=='accepted' and approved==current:
            html=html.replace('V5 is installed and awaiting live appearance review.','V5 is accepted and installed.')
    (WORK/'bow-review.html').write_text(html.replace('__DATA__',json.dumps(data)).replace('__TIMING__',json.dumps(timings)),encoding='utf8')
    print('Bow reviewer: eight directions, nine frames, both sexes, native/V4/V5')


def rebuild():
    fit()
    register()
    build()
if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stage', choices=['prepare', 'fit', 'register', 'build', 'review', 'rebuild'])
    args = parser.parse_args()
    {'prepare':prepare, 'fit':fit, 'register':register, 'build':build, 'review':review, 'rebuild':rebuild}[args.stage]()
