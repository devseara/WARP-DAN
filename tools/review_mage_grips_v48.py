"""Compose masked grip authoring candidates with accepted body and native hair."""

import base64
import argparse
import copy
import json
from pathlib import Path
import subprocess
from PIL import Image, ImageDraw
import first_job_hd_sprites as h

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'Assets/HDFirstJobs/animation-audit-v1/female-mage-gripping-v48'
WORK = ROOT / 'Outputs/mage-mounted-grip-v48'
FIX = ROOT / 'Outputs/mage-mounted-runtime-v46/fixtures'
APP = ROOT.parent / 'GRFEditor-main/build/act-workspace/20261012-111129/App'
RENDER = (
    ROOT / 'Assets/HDFirstJobs/animation-audit-v1/female-mage-fox-complete-v15/workspace-render.exe'
)


def main():
    body = h.base.read_act((FIX / 'body.act').read_bytes())
    heads = h.base.read_act((FIX / 'head.act').read_bytes())
    body_images = h.independent_decode((FIX / 'body.spr').read_bytes())
    head_images = [
        im.convert('RGBA').resize((im.width * 2, im.height * 2), Image.Resampling.NEAREST)
        for im in h.base.decode_spr((FIX / 'head.spr').read_bytes())[0]
    ]
    groups = list(range(len(body.actions)))
    for kind in ['current', 'knife', 'rod']:
        if kind == 'current':
            base_weapon = h.base.read_act((FIX / 'weapon.act').read_bytes())
            doc = dict(
                Act=base64.b64encode((FIX / 'weapon.act').read_bytes()).decode(),
                Spr=base64.b64encode((FIX / 'weapon.spr').read_bytes()).decode(),
                Layers=[
                    dict(
                        Action=ai,
                        Frame=fi,
                        Layer=li,
                        Visible=True,
                        Candidate=False,
                        Name='Installed Knife',
                        Role='weapon',
                    )
                    for ai, fs in enumerate(base_weapon.actions)
                    for fi, f in enumerate(fs)
                    for li, l in enumerate(f.layers)
                ],
            )
        else:
            doc = json.loads((OUT / f'{kind}-gripping.actproj').read_text(encoding='utf-8'))
        wa = h.base.read_act(base64.b64decode(doc['Act']))
        wi = h.independent_decode(base64.b64decode(doc['Spr']))
        wm = {(r['Action'], r['Frame'], r['Layer']): r for r in doc['Layers']}
        images = body_images + wi + head_images
        act = copy.deepcopy(body)
        meta = []
        for ai, frames in enumerate(act.actions):
            for fi, f in enumerate(frames):
                meta.append(
                    dict(
                        Action=ai,
                        Frame=fi,
                        Layer=0,
                        Name='Accepted Mage/Fox',
                        Role='body',
                        Visible=True,
                        Candidate=False,
                    )
                )
                for li, l in enumerate(wa.actions[ai][fi].layers):
                    if l.index < 0:
                        continue
                    new = copy.deepcopy(l)
                    new.index += len(body_images)
                    ni = len(f.layers)
                    f.layers.append(new)
                    data = copy.deepcopy(wm[ai, fi, li])
                    data['Layer'] = ni
                    meta.append(data)
                hai, hfi = (ai % 8, 0) if ai // 8 in [4, 5, 9, 10, 11, 12] else (ai, fi)
                hf = heads.actions[hai][hfi]
                a = h.base.anchor(f)
                b = h.base.anchor(hf)
                for l in hf.layers:
                    if l.index < 0:
                        continue
                    new = copy.deepcopy(l)
                    new.x += a[0] - b[0]
                    new.y += a[1] - b[1]
                    new.index += len(body_images) + len(wi)
                    new.kind = 1
                    new.sx *= 0.5
                    new.sy *= 0.5
                    ni = len(f.layers)
                    f.layers.append(new)
                    meta.append(
                        dict(
                            Action=ai,
                            Frame=fi,
                            Layer=ni,
                            Name='Native hair9',
                            Role='head',
                            Visible=True,
                            Candidate=False,
                        )
                    )
        project = WORK / f'temporary-{kind}-composition.actproj'
        project.write_text(
            json.dumps(
                dict(
                    Version=1,
                    Source='Grip review only; accepted body unchanged',
                    Act=base64.b64encode(h.base.write_act(act)).decode(),
                    Spr=base64.b64encode(h.base.write_spr(images)).decode(),
                    Layers=meta,
                ),
                separators=(',', ':'),
            ),
            encoding='utf-8',
        )
        target = OUT / (kind + '-composed')
        result = subprocess.run(
            [str(RENDER), str(APP), str(project), str(target), '2', ','.join(map(str, groups))],
            capture_output=True,
            text=True,
            creationflags=0x08000000,
        )
        assert result.returncode == 0, result.stderr
        project.unlink()
        labels = [
            'idle',
            'walk',
            'sit',
            'pickup',
            'preparation',
            'melee-1',
            'hit',
            'freeze',
            'death',
            'recovery',
            'melee-2',
            'melee-3',
            'cast',
        ]
        for group, label in enumerate(labels):
            count = max(len(body.actions[group * 8 + d]) for d in range(8))
            boards = []
            for fi in range(count):
                board = Image.new('RGBA', (1664, 808), '#263544')
                draw = ImageDraw.Draw(board)
                for d, name in enumerate(
                    [
                        'Front',
                        'Front left',
                        'Left',
                        'Rear left',
                        'Rear',
                        'Rear right',
                        'Right',
                        'Front right',
                    ]
                ):
                    actual = min(fi, len(body.actions[group * 8 + d]) - 1)
                    im = Image.open(target / f'a{group*8+d}-f{actual}.png').convert('RGBA')
                    x = d % 4 * 416
                    y = d // 4 * 404
                    board.alpha_composite(im.crop((48, 96, 464, 472)), (x, y + 28))
                    draw.text((x + 7, y + 7), f'{name} F{fi}', fill='white')
                boards.append(board)
            boards[0].save(
                OUT / f'{kind}-{label}.png',
                save_all=True,
                append_images=boards[1:],
                duration=round(body.speeds[group * 8] * 25),
                loop=0,
                blend=0,
                disposal=0,
            )
    board = Image.new('RGBA', (1536, 560), '#263544')
    draw = ImageDraw.Draw(board)
    for col, (label, path) in enumerate(
        [
            ('Current installed grip', OUT / 'current-composed/a33-f0.png'),
            ('Knife: fingers in front', OUT / 'knife-composed/a33-f0.png'),
            ('Rod / Staff candidate', OUT / 'rod-composed/a33-f0.png'),
        ]
    ):
        board.alpha_composite(Image.open(path).convert('RGBA'), (col * 512, 32))
        draw.text((col * 512 + 12, 12), label, fill='white')
    board.save(OUT / 'comparison.png')
    print(
        'Native workspace composed all448 frame uses per candidate; six rear preparation grips are naturally hidden.'
    )


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.out:
        OUT = args.out.resolve()
    main()
