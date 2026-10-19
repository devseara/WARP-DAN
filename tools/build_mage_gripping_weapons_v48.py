"""Author finger occlusion and native Rod/Staff registration in Act workspace."""

import base64
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw
import first_job_hd_sprites as h

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'Outputs/mage-mounted-grip-v48'
OUT = ROOT / 'Assets/HDFirstJobs/animation-audit-v1/female-mage-gripping-v48'
APP = ROOT.parent / 'GRFEditor-main/build/act-workspace/20261012-111129/App'
PALMS = [(247, 263), (249, 260), (232, 261), (222, 258), None, (289, 258), (283, 262), (266, 261)]


def run(*args):
    p = subprocess.run(
        list(map(str, args)), capture_output=True, text=True, creationflags=0x08000000
    )
    assert p.returncode == 0, (p.stdout, p.stderr)


def save(path, value):
    path.write_text(json.dumps(value, separators=(',', ':')), encoding='utf-8')


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / 'masks').mkdir(exist_ok=True)
    (OUT / 'candidate').mkdir(exist_ok=True)
    fixtures = ROOT / 'Outputs/mage-mounted-runtime-v46/fixtures'
    knife = h.base.read_act((fixtures / 'weapon.act').read_bytes())
    records = json.loads(
        (
            ROOT
            / 'Assets/HDFirstJobs/animation-audit-v1/female-mage-mounted-attachments-v45/knife-grips.json'
        ).read_text(encoding='utf-8')
    )['landmarks']
    records = {(r['action'], r['frame']): r for r in records}
    rod_native = h.base.read_act((WORK / 'native-staff/롯드.act').read_bytes())
    for kind in ['knife', 'rod']:
        act = copy.deepcopy(knife)
        images = (
            h.independent_decode((fixtures / 'weapon.spr').read_bytes())
            if kind == 'knife'
            else [
                im.convert('RGBA').resize((im.width * 2, im.height * 2), Image.Resampling.NEAREST)
                for im in h.base.decode_spr((WORK / 'native-staff/롯드.spr').read_bytes())[0]
            ]
        )
        # Rod/Staff1601..1609 share this native resource family. Select the
        # original per-direction native weapon pose, then register its handle
        # to the approved near-side glove. No Fox/body pixels are changed.
        grips = (
            {0: (4, 13), 1: (9, 14), 2: (20, 3)} if kind == 'knife' else {0: (8, 20), 1: (2, 17)}
        )
        ops = []
        meta = []
        landmarks = []
        for ai, frames in enumerate(act.actions):
            for fi, frame in enumerate(frames):
                l = frame.layers[0]
                if l.index >= 0:
                    row = records[ai, fi]
                    x, y = row['target_glove_pixel']
                    if ai // 8 == 4:
                        palm = PALMS[ai % 8]
                        if palm is None:
                            # Both hands are naturally hidden in front of the
                            # rider. The old point was a boot, not a palm.
                            meta.append(
                                dict(
                                    Action=ai,
                                    Frame=fi,
                                    Layer=0,
                                    Name='Rear grip naturally occluded',
                                    Role='weapon',
                                    Visible=False,
                                    Candidate=True,
                                )
                            )
                            continue
                        x, y = palm
                        y += [0, 2, 4, 6, 4, 2][fi]
                    if kind == 'rod':
                        d = ai % 8
                        # The source Mage rod exposes its full upright/angled
                        # silhouette through these two native images.
                        index = 1
                        # Rigid rod follows the approved Knight-derived wrist
                        # arc, rotating about its measured grip, not its tip.
                        angle = (
                            0
                            if ai // 8 == 4
                            else {0: 52, 1: -22, 2: -127}[knife.actions[ai][fi].layers[0].index]
                        )
                        if l.mirror:
                            angle = -angle
                        l.index = index
                        l.angle = angle % 360
                        gx, gy = grips[index]
                        im = images[index]
                        sign = -1 if l.mirror else 1
                        relx = sign * ((2 * gx + 1) - im.width / 2) * 0.5
                        rely = ((2 * gy + 1) - im.height / 2) * 0.5
                        theta = math.radians(angle)
                        rx = math.cos(theta) * relx - math.sin(theta) * rely
                        ry = math.sin(theta) * relx + math.cos(theta) * rely
                        l.x = round((x - 256) / 2 - rx)
                        l.y = round((y - 384) / 2 - ry)
                    elif ai // 8 == 4:
                        gx, gy = grips[l.index]
                        im = images[l.index]
                        sign = -1 if l.mirror else 1
                        relx = sign * ((2 * gx + 1) - im.width / 2) * l.sx
                        rely = ((2 * gy + 1) - im.height / 2) * l.sy
                        l.x = round((x - 256) / 2 - relx)
                        l.y = round((y - 384) / 2 - rely)
                    gx, gy = grips[l.index]
                    im = images[l.index]
                    mask = Image.new('RGBA', im.size, 'white')
                    # The old 4x4 texture notch left the handle painted over
                    # most of the closed glove. Occlude the handle with the
                    # actual front-finger volume in shared output coordinates.
                    # Body artwork remains unchanged; per-frame masks account
                    # for mirror and wrist rotation, rather than sharing one
                    # source-space notch across every pose.
                    fingers = Image.new('1', (512, 512))
                    polygon = [
                        (-5, -3),
                        (-7, 1),
                        (-6, 6),
                        (-3, 9),
                        (2, 9),
                        (6, 5),
                        (5, -1),
                        (1, -4),
                    ]
                    if ai // 8 != 4:
                        polygon = [(-5, -4), (-6, 0), (-5, 5), (-1, 7), (4, 5), (6, 0), (3, -4)]
                    ImageDraw.Draw(fingers).polygon(
                        [(x + dx, y + dy) for dx, dy in polygon], fill=1
                    )
                    theta = math.radians(l.angle)
                    cs = math.cos(theta)
                    sn = math.sin(theta)
                    sign = -1 if l.mirror else 1
                    for yy in range(im.height):
                        for xx in range(im.width):
                            dx = sign * (xx + 0.5 - im.width / 2) * l.sx * 2
                            dy = (yy + 0.5 - im.height / 2) * l.sy * 2
                            px = round(256 + 2 * l.x + cs * dx - sn * dy)
                            py = round(384 + 2 * l.y + sn * dx + cs * dy)
                            if 0 <= px < 512 and 0 <= py < 512 and fingers.getpixel((px, py)):
                                mask.putpixel((xx, yy), (255, 255, 255, 0))
                    mp = OUT / 'masks' / f'{kind}-a{ai}-f{fi}.png'
                    mask.save(mp)
                    ops.append(dict(Op='mask-image', Action=ai, Frame=fi, Layer=0, Path=str(mp)))
                    landmarks.append(
                        dict(
                            action=ai,
                            frame=fi,
                            source_hilt=[gx, gy],
                            glove=[x, y],
                            image=l.index,
                            mirror=l.mirror,
                            angle=l.angle,
                            finger_polygon=[[x + dx, y + dy] for dx, dy in polygon],
                        )
                    )
                meta.append(
                    dict(
                        Action=ai,
                        Frame=fi,
                        Layer=0,
                        Name=f'{kind} hand grip',
                        Role='weapon',
                        Visible=True,
                        Candidate=True,
                    )
                )
        seed = OUT / f'{kind}-seed.actproj'
        project = OUT / f'{kind}-gripping.actproj'
        save(
            seed,
            dict(
                Version=1,
                Source='Accepted mounted Mage gloves; native original weapon pixels with finger occlusion',
                Act=base64.b64encode(h.base.write_act(act)).decode(),
                Spr=base64.b64encode(h.base.write_spr(images)).decode(),
                Layers=meta,
            ),
        )
        recipe = OUT / f'{kind}-grip-recipe.json'
        save(recipe, dict(Version=1, Operations=ops))
        run(
            APP / 'GrfCL.exe', 'act', 'apply', '--input', seed, '--recipe', recipe, '--out', project
        )
        run(APP / 'GrfCL.exe', 'act', 'validate', '--input', project)
        # Keep authoring candidates marked as such. The workspace intentionally
        # blocks game export until the user accepts the new grip artwork.
        render_dir = OUT / (
            kind + '-layers-' + hashlib.sha256(project.read_bytes()).hexdigest()[:8]
        )
        if not render_dir.exists():
            run(APP / 'GrfCL.exe', 'act', 'render-all', '--input', project, '--out', render_dir)
        seed.unlink()
        save(OUT / f'{kind}-landmarks.json', landmarks)
    save(
        OUT / 'manifest.json',
        dict(
            status='review_candidate',
            installed=False,
            body_artwork_unchanged=True,
            families=dict(knife=[1201], rod_staff=list(range(1601, 1610))),
            other_item_specific_models_native_fallback=True,
        ),
    )
    print('Created editable Knife and Rod/Staff grip candidates through native Act workspace.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    if args.out:
        OUT = args.out.resolve()
    OUT.mkdir(parents=True, exist_ok=True)
    main()
