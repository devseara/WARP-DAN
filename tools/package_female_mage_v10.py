"""Verify, review, save and deploy the continuous front/rear Mage correction."""
import argparse,json,hashlib,shutil,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from build_female_mage_v10 import ROOT,OUT,digest,load_pair
from sprite_formats import read_spr,read_act
from review_full_swordman_set import body,joined,ORIGIN
from refine_clan_combat_necks import components
from package_clan_skin_assets import pack_payloads
from clan_grf_transaction import replace_records,finish
from grf_reader import GrfFile
from save_accepted_clan_work import source_closure

BASE=OUT.parent/'female-gait-v9'


def is_accepted():
    path=OUT/'user-acceptance.json'
    if not path.is_file():return False
    record=json.loads(path.read_text(encoding='utf8'))
    expected={f'assets/female-angel-mage-v10{ext}' for ext in ('.spr','.act')}
    rows=record.get('files',[])
    return (record.get('status')=='accepted' and {r['path'] for r in rows}==expected
            and all(digest(OUT/r['path'])==r['sha256'] for r in rows))


def verify():
    r=json.loads((OUT/'verification.json').read_text(encoding='utf8'))
    assert r['changed_actions']==[8,12] and r['changed_frames']==16 and r['unchanged_frame_uses']==440
    for row in r['files']:assert digest(OUT/row['path'])==row['sha256']
    p=OUT/'assets/female-angel-mage-v10.spr';pair=read_spr(p.read_bytes()),read_act(p.with_suffix('.act').read_bytes());old=load_pair(9)
    assert len(pair[1].actions)==104 and sum(map(len,pair[1].actions))==456
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',14)
    for ai in (8,12):
        for fi,f in enumerate(pair[1].actions[ai]):
            im=pair[0][f.layers[0].index];a=np.array(im);opaque=a[:,:,3]>0;rgb=a[:,:,:3].astype(int)
            assert len(components(opaque))==1 and not a[~opaque].any()
            assert not (opaque&(rgb[:,:,1]-rgb[:,:,0]>20)&(rgb[:,:,1]-rgb[:,:,2]>20)).any()
            detail=Image.new('RGB',(900,250),'#283746');pen=ImageDraw.Draw(detail)
            for col,(label,asset) in enumerate((('Original Mage',None),('V9',old),('V10',pair))):
                raw=body('female',ai,fi,asset,job='mage');y0=-45 if ai==8 else -53;crop=raw.crop((ORIGIN[0]-96,ORIGIN[1]+y0*4,ORIGIN[0]+96,ORIGIN[1]-21*4));crop=crop.resize((288,round(crop.height*1.5)),Image.Resampling.NEAREST);detail.paste(crop,(col*300+6,30),crop);pen.text((col*300+5,4),label,font=font,fill='white')
            detail.save(OUT/f'review/details/d{ai-8}-f{fi}.png')
        with Image.open(OUT/f'review/d{ai-8}-loop.png') as animation:
            assert animation.n_frames==8
            for fi in range(8):
                animation.seek(fi);assert animation.info['duration']==75
                with Image.open(OUT/f'review/frames/d{ai-8}-f{fi}.png') as frame:assert animation.convert('RGB').tobytes()==frame.convert('RGB').tobytes()
    board=Image.new('RGB',(900,340),'#283746');pen=ImageDraw.Draw(board)
    for col,(label,ai,asset) in enumerate((('Rear idle reference',4,old),('V9 rear walk',12,old),('V10 rear walk',12,pair))):
        im=joined('female',ai,0,asset,job='mage').crop((80,40,560,620)).resize((240,290),Image.Resampling.NEAREST);board.paste(im,(col*300+30,25),im);pen.text((col*300+5,4),label,font=font,fill='white')
    board.save(OUT/'review/rear-idle-scale.png')
    return r


def viewer():
    rev=digest(OUT/'assets/female-angel-mage-v10.spr')[:12]
    html='''<!doctype html><meta charset="utf-8"><title>Female Mage V10 - front and rear walk</title>
<style>body{margin:24px;background:#182431;color:#eef4fa;font:15px system-ui}h1{font-size:26px}p{max-width:950px;line-height:1.5;color:#c6d5e1}button,select{font:inherit;background:#30465b;color:white;border:1px solid #73869a;border-radius:5px;padding:7px 12px;margin:5px}label{margin:0 12px}input{vertical-align:middle}img{display:block;max-width:100%;image-rendering:pixelated;margin:14px 0}a{color:#b7dfff}</style>
<h1>Female Mage V10 - front and rear walk</h1><p>The front dress stays continuous around the hands and waist. The rear walk matches the standing outfit's proportions and follows the original glove movement. Lower stride pixels and native head anchors are retained. This comparison covers directions 0 and 4.</p>
<select id="dir"><option value="0">Front - direction 0</option><option value="4">Back - direction 4</option></select><button id="play">Pause</button><button id="prev">Previous</button><button id="next">Next</button><label>Frame <input id="frame" type="range" min="0" max="7" value="0"><span id="num"></span></label><select id="speed"><option value="75">Original - 75 ms</option><option value="150">Half speed</option><option value="300">Quarter speed</option></select>
<img id="full" width="900" height="340"><img id="detail" width="900" height="250"><p><a href="assets/female-angel-mage-v10.act">Female ACT</a> - <a href="assets/female-angel-mage-v10.spr">Female SPR</a> - Complete 104-action pair.</p><details><summary>Rear idle-to-walk proportions</summary><img src="review/rear-idle-scale.png"></details>
<script>const REV='__REV__',$=id=>document.getElementById(id),q=new URLSearchParams(location.search);let f=Number(q.get('frame'))||0,playing=q.get('paused')!=='1',timer;$('dir').value=q.get('direction')==='0'?'0':'4';function draw(){let d=$('dir').value;$('frame').value=f;$('num').textContent=f+' / 7';$('play').textContent=playing?'Pause':'Play';$('full').src='review/frames/d'+d+'-f'+f+'.png?v='+REV;$('detail').src='review/details/d'+d+'-f'+f+'.png?v='+REV}function step(n){playing=false;f=(f+n+8)%8;draw()}function loop(){clearInterval(timer);timer=setInterval(()=>{if(playing){f=(f+1)%8;draw()}},+$('speed').value)}$('prev').onclick=()=>step(-1);$('next').onclick=()=>step(1);$('frame').oninput=()=>{playing=false;f=+$('frame').value;draw()};$('play').onclick=()=>{playing=!playing;draw()};$('dir').onchange=()=>{f=0;draw()};$('speed').onchange=loop;for(let d of [0,4])for(let i=0;i<8;i++)for(let kind of ['frames','details']){let im=new Image();im.src='review/'+kind+'/d'+d+'-f'+i+'.png?v='+REV}draw();loop();</script>'''
    (OUT/'walk-review.html').write_text(html.replace('__REV__',rev),encoding='utf8')


def install():
    parent=json.loads((BASE/'deployment.json').read_text(encoding='utf8'));target=Path(parent['target']);game=target.parent;a,b=GrfFile(target),GrfFile(game/'update.grf');payloads={};rows=[]
    try:
        for row in parent['resources']:
            suffix=Path(row['source']).suffix;source=OUT/f'assets/female-angel-mage-v10{suffix}';raw=source.read_bytes();current=hashlib.sha256(a.read(row['entry'])).hexdigest()
            assert current in (row['sha256'],digest(source)),('Unexpected source archive version',row['entry'])
            assert row['entry'] not in b.entries
            payloads[row['entry']]=raw;rows.append(dict(entry=row['entry'],source=source.relative_to(ROOT).as_posix(),sha256=digest(source),previous_sha256=row['sha256']))
    finally:a.close();b.close()
    patch=OUT/'female-mage-v10.grf';pack_payloads(payloads,patch)
    state=dict(status='prepared_requested_correction',revision='female-gait-v10',package_tool='tools/package_female_mage_v10.py',resources=rows);(OUT.parent/'installed-correction.json').write_text(json.dumps(state,indent=2),encoding='utf8')
    tx=replace_records(target,payloads,OUT/'maindata-v10-transaction.json')
    check=GrfFile(target)
    try:
        for name,raw in payloads.items():assert check.read(name)==raw
    finally:check.close()
    report=dict(status='accepted_installed' if is_accepted() else 'deployed_requested_correction',visual_acceptance='Accepted by user; pinned SPR/ACT unchanged' if is_accepted() else 'Pending user front/rear live check',resources=rows,target=str(target),maindata_sha256=digest(target),patch_sha256=digest(patch),transaction='maindata-v10-transaction.json',changed_actions=[8,12],unchanged_frame_uses=440,head_anchors_preserved=True,lower_stride_pixels_preserved=True)
    (OUT/'deployment.json').write_text(json.dumps(report,indent=2),encoding='utf8');state.update(status=report['status'],deployment='female-gait-v10/deployment.json');(OUT.parent/'installed-correction.json').write_text(json.dumps(state,indent=2),encoding='utf8');print(json.dumps(report))


def package(report):
    archive=OUT.parent/'Mage-female-v10-SPR-ACT-correction.zip';files={p for p in OUT.rglob('*') if p.is_file() and p.suffix not in ('.grf','.zip') and p.name!='delivery.json'}
    files.update(source_closure([ROOT/'tools/build_female_mage_v10.py',ROOT/'tools/package_female_mage_v10.py']));files.update((ROOT/'tools/dual_weapon_formats').glob('*.py'));files.update(p for p in (OUT.parent/'native').rglob('*') if p.is_file());files.update((ROOT/'Inputs/ClanBodySkins/records').glob('clan-*.json'))
    for version in (7,9):files.update(OUT.parent/f'female-gait-v{version}/assets/female-angel-mage-v{version}{suffix}' for suffix in ('.spr','.act'))
    files.update([ROOT/'docs/clan-body-skins.md',BASE/'deployment.json',OUT.parent/'installed-correction.json'])
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(files):z.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    r=dict(status='Accepted V10 saved' if is_accepted() else 'Front/rear correction saved',files=report['files'],archive=dict(path=archive.name,sha256=digest(archive),bytes=archive.stat().st_size),viewer='walk-review.html',installed=(OUT/'deployment.json').exists());(OUT/'delivery.json').write_text(json.dumps(r,indent=2),encoding='utf8');print(json.dumps(r))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);g=p.add_mutually_exclusive_group();g.add_argument('--install',action='store_true');g.add_argument('--finish-install',action='store_true');a=p.parse_args();r=verify();viewer()
    try:
        if a.finish_install:finish(OUT/'maindata-v10-transaction.json')
        if a.install or a.finish_install:install()
    finally:package(r)
