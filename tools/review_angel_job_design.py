"""Review only fully authored design actions; never expose stock fallback as custom art."""
import argparse
import hashlib
import io
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from package_clan_skin_assets import ROOT
from review_original_job_directions import native_context
from review_full_swordman_set import joined
from sprite_formats import read_act, read_spr


def main(job, work, revision="v1", previous=None):
    pairs, authored, sources, native, prior = {}, {}, [], {}, {}
    for sex in ('male', 'female'):
        report = json.loads((work / (sex + '-verification.json')).read_text(encoding='utf8'))
        assert report['independent_decoder_match'] and not report['detached_artwork_flags']
        authored[sex] = {row['sprite'] for row in report['imports']}
        stem = work / 'assets' / (sex + '-angel-' + job + '-' + revision)
        pairs[sex] = read_spr(stem.with_suffix('.spr').read_bytes()), read_act(stem.with_suffix('.act').read_bytes())
        native[sex] = native_context(job, sex)[2]
        if previous:
            old_report = json.loads((previous / (sex + '-verification.json')).read_text(encoding='utf8'))
            old_files = {Path(row['path']).suffix: previous / row['path'] for row in old_report['files']}
            for row in old_report['files']:
                assert hashlib.sha256((previous / row['path']).read_bytes()).hexdigest() == row['sha256']
            prior[sex] = read_spr(old_files['.spr'].read_bytes()), read_act(old_files['.act'].read_bytes())
        for row in report['files']:
            raw = (work / row['path']).read_bytes()
            assert hashlib.sha256(raw).hexdigest() == row['sha256']
            sources.append(dict(sex=sex, **row))
    actions = []
    for ai in range(24):
        if all(all(layer.index in authored[sex] for frame in native[sex].actions[ai]
                   for layer in frame.layers if layer.index >= 0) for sex in pairs):
            actions.append(ai)
    assert actions
    images = work / 'review/design/images'
    images.mkdir(parents=True, exist_ok=True)
    data, coverage = {}, {}
    for ai in actions:
        data[ai] = {}
        for sex, pair in pairs.items():
            frames = []
            for fi in range(len(native[sex].actions[ai])):
                row = []
                for selected in ((None, pair, prior[sex]) if previous else (None, pair)):
                    image = joined(sex, ai, fi, selected, job=job)
                    stream = io.BytesIO()
                    image.save(stream, format='PNG')
                    raw = stream.getvalue()
                    path = images / (hashlib.sha256(raw).hexdigest() + '.png')
                    if not path.exists():
                        path.write_bytes(raw)
                    row.append(path.relative_to(work).as_posix())
                frames.append(row)
            data[ai][sex] = dict(ms=round(native[sex].speeds[ai] * 25), frames=frames)
            coverage[sex] = coverage.get(sex, 0) + len(frames)
    board = Image.new('RGB', (1280, 860), '#283746')
    pen = ImageDraw.Draw(board)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 15)
    for si, sex in enumerate(('male', 'female')):
        for group in (0, 2):
            for direction in range(5):
                ai = group * 8 + direction
                if ai not in data:
                    continue
                x, y = direction * 256, si * 430 + (215 if group == 2 else 0)
                label = 'sit' if group == 2 else 'idle'
                pen.text((x + 4, y + 3), f'{sex} / {label} D{direction}', font=font, fill='white')
                for k, path in enumerate(data[ai][sex]['frames'][0][:2]):
                    with Image.open(work / path) as image:
                        image = image.crop((160, 60, 480, 530)).resize((128, 188), Image.Resampling.NEAREST)
                        board.paste(image, (x + k * 128, y + 24), image)
    board.save(work / 'idle-sit-native-review.png')
    html = '''<!doctype html><html lang="en"><meta charset="utf-8">
<title>Angel __JOB__ · outfit review</title>
<style>
*{box-sizing:border-box}body{margin:24px;background:#172330;color:#edf2f7;font:16px system-ui}
h1{font-size:26px;margin-bottom:8px}p{line-height:1.55;max-width:1020px;color:#c8d5e1}
button,select{font:inherit;background:#30485d;border:1px solid #70879c;border-radius:5px;color:white;padding:8px 12px}
.controls{display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin:20px 0}
input{vertical-align:middle}#stage{display:grid;grid-template-columns:repeat(4,minmax(170px,1fr));gap:12px;max-width:1440px}
figure{margin:0}figcaption{margin:8px 0;color:#e3edf6}canvas{width:100%;height:auto;display:block;image-rendering:pixelated;background:#283746}
#stage.black canvas{background:black}#stage.checker canvas{background:repeating-conic-gradient(#515151 0 25%,#686868 0 50%) 0/24px 24px}
details{margin-top:22px}details img{width:100%;max-width:1280px;image-rendering:pixelated}
@media(max-width:950px){#stage{grid-template-columns:repeat(2,minmax(170px,1fr))}}
</style>
<h1>Angel __JOB__ · male and female outfit review</h1>
<p>The approved costume fitted to the original __JOB__ poses, with native heads.
This design preview includes all eight standing and sitting views and the front-walk study.
The remaining animation artwork is not included. This is a partial design build.</p>
<div class="controls"><label>Pose <select id="action"></select></label>
<button id="play">Play</button><button id="prev">Previous</button><button id="next">Next</button>
<label>Frame <input id="frame" type="range" min="0" value="0"><span id="status"></span></label>
<label>Speed <select id="speed"><option value="1">Native</option><option value="2">Half</option></select></label>
<label id="reference-control" hidden>Compare <select id="reference"><option value="0">Original job</option><option value="2">Previous design</option></select></label>
<label>Background <select id="bg"><option value="slate">Slate</option><option value="checker">Checker</option><option value="black">Black</option></select></label></div>
<div id="stage"></div>
<details><summary>Standing and sitting comparison sheet</summary><img src="idle-sit-native-review.png"></details>
<script>
const DATA=__DATA__,ACTIONS=__ACTIONS__,$=id=>document.getElementById(id),cache=new Map(),views=[];
let frame=0,playing=false,timer,token=0;const query=new URLSearchParams(location.search);
for(const ai of ACTIONS){const group=Math.floor(ai/8),dir=ai%8;let label=(group===0?'Standing':group===1?'Walking':'Sitting')+' · direction '+dir;$('action').add(new Option(label,ai))}
if(ACTIONS.includes(Number(query.get('action'))))$('action').value=Number(query.get('action'));frame=Math.max(0,Number(query.get('frame'))||0);
const hasPrevious=DATA[ACTIONS[0]].male.frames[0].length>2;if(hasPrevious){$('reference-control').hidden=false;$('reference').value='2'}
for(const sex of ['male','female'])for(const kind of [0,1]){let fig=document.createElement('figure'),label=document.createElement('figcaption'),canvas=document.createElement('canvas');label.textContent=sex+' / '+(kind?'Angel __JOB__':'Original');canvas.width=400;canvas.height=500;fig.append(label,canvas);$('stage').append(fig);views.push({sex,kind,canvas,label})}
function load(src){if(!cache.has(src))cache.set(src,new Promise((resolve,reject)=>{let i=new Image();i.onload=()=>resolve(i);i.onerror=reject;i.src=src}));return cache.get(src)}
async function draw(){const ticket=++token,a=DATA[$('action').value],n=a.male.frames.length;frame=(frame+n)%n;$('frame').max=n-1;$('frame').value=frame;$('status').textContent=frame+' / '+(n-1);$('play').textContent=playing?'Pause':'Play';$('stage').className=$('bg').value;
await Promise.all(views.map(async v=>{let i=await load(a[v.sex].frames[frame][v.kind===0?Number($('reference').value):1]);v.label.textContent=v.sex+' / '+(v.kind?'Angel __JOB__ __REV__':Number($('reference').value)===2?'Previous design':'Original');if(ticket!==token)return;let c=v.canvas.getContext('2d');c.imageSmoothingEnabled=false;c.clearRect(0,0,400,500);c.drawImage(i,120,40,400,500,0,0,400,500)}))}
function schedule(){clearTimeout(timer);if(playing)timer=setTimeout(async()=>{frame++;await draw();schedule()},DATA[$('action').value].male.ms*Number($('speed').value))}
function step(n){playing=false;frame+=n;draw();schedule()}
$('play').onclick=()=>{playing=!playing;draw();schedule()};$('prev').onclick=()=>step(-1);$('next').onclick=()=>step(1);$('frame').oninput=()=>{playing=false;frame=+$('frame').value;draw();schedule()};$('action').onchange=()=>{frame=0;draw();schedule()};$('speed').onchange=schedule;$('bg').onchange=draw;$('reference').onchange=draw;draw();
</script></html>'''
    html = html.replace('__JOB__', job.title()).replace('__REV__', revision.upper()).replace('__DATA__', json.dumps(data, separators=(',', ':'))).replace('__ACTIONS__', json.dumps(actions))
    if previous:
        html = html.replace('The approved costume fitted', 'The revised head/collar fit is shown beside the previous design. Use Compare to select the original job or previous design. The approved costume fitted')
        details = ''
        for filename, label in [('diagonal-seat-detail.png', 'Female diagonal sitting: V2 / V3 neck join'),
                                ('female-walk-detail.png', 'Female walking collar close-ups'),
                                ('female-sit-detail-0.png', 'Female sitting: directions 0-3'),
                                ('female-sit-detail-1.png', 'Female sitting: directions 4-7'),
                                ('male-sit-detail-0.png', 'Male sitting: directions 0-3'),
                                ('male-sit-detail-1.png', 'Male sitting: directions 4-7')]:
            if (work / filename).is_file():
                details += f'<details><summary>{label}</summary><img src="{filename}"></details>'
        html = html.replace('<script>', details + '<script>', 1)
    (work / 'design-review.html').write_text(html, encoding='utf8')
    report = dict(job=job, revision=revision, status='design_review_only', accepted=False, installed=False,
                  complete_animation_set=False, reviewed_actions=actions, frame_uses=coverage,
                  authored_drawings={sex: len(items) for sex, items in authored.items()},
                  stock_fallback_displayed=False, rendered_from_reopened_exports=True, files=sources)
    feedback = work / 'user-review.json'
    if feedback.is_file():
        reviewed = json.loads(feedback.read_text(encoding='utf8'))
        pins = {row['path']: row['sha256'] for row in reviewed.get('files', [])}
        current = {row['path']: row['sha256'] for row in sources}
        if pins == current:
            report['accepted'] = reviewed.get('status') == 'accepted'
            report['status'] = 'accepted_design_pilot' if report['accepted'] else reviewed.get('status', 'design_review_only')
            installation = work / 'installation.json'
            if report['accepted'] and installation.is_file():
                installed = json.loads(installation.read_text(encoding='utf8'))
                report['installed'] = (installed.get('installed') is True and
                    {row['path']: row['sha256'] for row in installed.get('files', [])} == current)
    (work / 'design-review-verification.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True, choices=('archer', 'acolyte', 'merchant', 'thief'))
    parser.add_argument('--work', type=Path)
    parser.add_argument('--revision', default='v1')
    parser.add_argument('--previous', type=Path)
    args = parser.parse_args()
    main(args.job, args.work.resolve() if args.work else ROOT / 'Assets/ClanBodySkins' / args.job.title() / 'complete-v1', args.revision, args.previous.resolve() if args.previous else None)
