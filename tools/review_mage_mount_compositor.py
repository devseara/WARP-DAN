"""Render exact native-selected head/weapon geometry with the Act workspace.

No artwork, gameplay ACT/SPR or attachment offsets are edited. The temporary
composed pair is a diagnostic representation of the tested renderer decisions.
"""

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import first_job_hd_sprites as h

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Outputs/mage-mounted-runtime-v46'
OUT = ROOT / 'Assets/HDFirstJobs/animation-audit-v1/female-mage-renderer-v46'
APP = ROOT.parent / 'GRFEditor-main/build/act-workspace/20261012-111129/App'
RENDER = (
    ROOT / 'Assets/HDFirstJobs/animation-audit-v1/female-mage-fox-complete-v15/workspace-render.exe'
)


def main():
    OUT.mkdir(exist_ok=True)
    report = json.loads((WORK / 'compositor-verification.json').read_text(encoding='utf-8'))
    assert report['passed'] and report['native_anchor_cases'] == 448
    fixtures = WORK / 'fixtures'
    acts = {
        name: h.base.read_act((fixtures / (name + '.act')).read_bytes())
        for name in ['body', 'head', 'weapon']
    }
    textures = {
        name: h.independent_decode((fixtures / (name + '.spr')).read_bytes())
        for name in ['body', 'weapon']
    }
    textures['head'] = [
        im.convert('RGBA') for im in h.base.decode_spr((fixtures / 'head.spr').read_bytes())[0]
    ]
    images = list(textures['body'])
    head_index = []
    for image in textures['head']:
        head_index.append(len(images))
        images.append(image.resize((image.width * 2, image.height * 2), Image.Resampling.NEAREST))
    weapon_index = list(range(len(images), len(images) + len(textures['weapon'])))
    images.extend(textures['weapon'])
    proof = WORK / 'temporary-proof.act'
    spr = proof.with_suffix('.spr')
    spr.write_bytes(h.base.write_spr(images))
    selections = {(r['action'], r['frame']): r for r in report['head_selections']}
    for phase in ['before', 'after']:
        act = copy.deepcopy(acts['body'])
        for ai, frames in enumerate(act.actions):
            for fi, frame in enumerate(frames):
                row = selections[ai, fi]
                hai, hfi = (
                    (ai, fi) if phase == 'before' else (row['head_action'], row['head_frame'])
                )
                hf = acts['head'].actions[hai][hfi]
                delta = tuple(a - b for a, b in zip(h.base.anchor(frame), h.base.anchor(hf)))
                if phase == 'after':
                    assert list(delta) == row['anchor_delta']
                    for layer in acts['weapon'].actions[ai][fi].layers:
                        if layer.index < 0:
                            continue
                        layer = copy.deepcopy(layer)
                        layer.index = weapon_index[layer.index]
                        frame.layers.append(layer)
                for layer in hf.layers:
                    if layer.index < 0:
                        continue
                    layer = copy.deepcopy(layer)
                    layer.x += delta[0]
                    layer.y += delta[1]
                    layer.index = head_index[layer.index]
                    layer.kind = 1
                    layer.sx *= 0.5
                    layer.sy *= 0.5
                    frame.layers.append(layer)
        proof.write_bytes(h.base.write_act(act))
        run = subprocess.run(
            [
                str(RENDER),
                str(APP),
                str(proof),
                str(OUT / phase),
                '2',
                ','.join(map(str, range(104))),
            ],
            capture_output=True,
            text=True,
            creationflags=0x08000000,
            timeout=180,
        )
        assert run.returncode == 0, (run.stdout, run.stderr)
    directions = [
        'Front',
        'Front left',
        'Left',
        'Rear left',
        'Rear',
        'Rear right',
        'Right',
        'Front right',
    ]
    for group, count, name in [(4, 6, 'preparation'), (10, 9, 'attack'), (12, 5, 'casting')]:
        for phase in ['before', 'after']:
            boards = []
            for fi in range(count):
                board = Image.new('RGBA', (1664, 808), '#263544')
                draw = ImageDraw.Draw(board)
                for d, label in enumerate(directions):
                    image = Image.open(OUT / phase / f'a{group * 8 + d}-f{fi}.png').convert('RGBA')
                    x, y = (d % 4) * 416, (d // 4) * 404
                    board.alpha_composite(image.crop((48, 96, 464, 472)), (x, y + 28))
                    draw.text((x + 8, y + 7), f'{label} / F{fi}', fill='white')
                boards.append(board)
            boards[0].save(
                OUT / f'{phase}-{name}.png',
                save_all=True,
                append_images=boards[1:],
                duration=110,
                loop=0,
                disposal=0,
                blend=0,
            )
    board = Image.new('RGBA', (1024, 560), '#263544')
    draw = ImageDraw.Draw(board)
    for col, phase in enumerate(['before', 'after']):
        image = Image.open(OUT / phase / 'a82-f3.png').convert('RGBA')
        board.alpha_composite(image, (col * 512, 32))
        draw.text(
            (col * 512 + 18, 16),
            'Live V45 selection' if col == 0 else 'V46 tested renderer selection',
            fill='white',
        )
    board.save(OUT / 'comparison.png')
    counts = list(map(len, acts['body'].actions))
    html = '''<!doctype html><meta charset="utf-8"><title>Female Mage renderer V46</title>
<style>body{background:#17232e;color:#e5edf5;font:16px Segoe UI;margin:20px}img{image-rendering:pixelated;max-width:100%}.pair{display:flex;gap:12px}.pair div{background:#263544;padding:12px}.pair img{width:512px}button,select{font:inherit;padding:6px;margin:5px}a{color:#8de5cd}p{max-width:1100px}</style>
<h1>Female Mage / Fox · V46 renderer candidate</h1>
<p><b>Verified offline; not installed. Live visual acceptance pending.</b> The existing artwork is unchanged. These Act workspace renders use the actual hair9 resource, native compositor-selected frames and native attachment deltas. The equipped layer is the same dedicated Knife1201 pair already installed in the GRF.</p>
<p>The left side reproduces V45 selection; the right shows the corrected paths. Allocator, item database and file I/O boundaries are controlled fixtures in the native execution test. This page is diagnostic proof, not a live game capture.</p>
<select id="action"></select><select id="dir"></select><button id="prev">Previous</button><button id="play">Play</button><button id="next">Next</button><span id="frame"></span>
<div class="pair"><div><b>Before: V45</b><br><img id="before"></div><div><b>V46 candidate</b><br><img id="after"></div></div>
<h2>Eight directions · Preparation</h2><img src="after-preparation.png">
<h2>Eight directions · Long melee</h2><img src="after-attack.png">
<h2>Eight directions · Casting</h2><img src="after-casting.png">
<script>const counts=COUNTS,labels=['Idle','Walk','Sitting','Pickup','Preparation','Short melee','Hit','Strong hit','Prone','Attack ready','Long melee','Melee variant','Casting'],dirs=DIRS;let f=3,playing=false;const $=id=>document.getElementById(id);labels.forEach((v,i)=>$('action').add(new Option(v,i)));dirs.forEach((v,i)=>$('dir').add(new Option(v,i)));$('action').value=10;$('dir').value=2;function show(){const a=+$('action').value*8+(+$('dir').value);f=(f+counts[a])%counts[a];for(const p of ['before','after'])$(p).src=p+'/a'+a+'-f'+f+'.png';$('frame').textContent='A'+a+' F'+f+' / '+(counts[a]-1)}$('prev').onclick=()=>{f--;show()};$('next').onclick=()=>{f++;show()};$('play').onclick=()=>{playing=!playing;$('play').textContent=playing?'Pause':'Play'};$('action').onchange=()=>{f=0;show()};$('dir').onchange=()=>{f=0;show()};setInterval(()=>{if(playing){f++;show()}},110);show()</script>'''.replace(
        'COUNTS', json.dumps(counts)
    ).replace(
        'DIRS', json.dumps(directions)
    )
    (OUT / 'review.html').write_text(html, encoding='utf-8')
    spr.unlink()
    proof.unlink()
    result = dict(
        status='offline_verified_candidate',
        installed=False,
        gameplay_artwork_unchanged=True,
        native_compositor_report_sha256=hashlib.sha256(
            (WORK / 'compositor-verification.json').read_bytes()
        ).hexdigest(),
        actual_live_hair_resource='sprite/인간족/머리통/여/9_여',
        native_workspace_rendered_images=896,
        temporary_composed_pair_removed=True,
        live_visual_acceptance=False,
    )
    (OUT / 'proof.json').write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8'
    )
    print('Rendered native-selection proof:', OUT / 'review.html')


if __name__ == '__main__':
    main()
