"""Extract an approved costume sheet and compare its scale with native bodies.

This produces art masters and a sizing study, not animation-ready SPR files.
No accepted Swordman or installed game asset is modified.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from audit_first_job_sprite_sources import ROOT, OUT as SOURCES, JOBS
from audit_clan_wing_attachment import load
from render_native_wing_anatomy import rgba
from sprite_formats import read_act, anchor
from spr_reader import Spr
from original_job_proportions import reference_scale, register_master

OUT = ROOT / 'Outputs/clan-body-skins/first-jobs-original-v1'
JOBS = {k: v for k, v in JOBS.items() if k != 'swordman'}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(sheet):
    """Split on actual transparent gutters, not arbitrary equal-width cells."""
    alpha = np.asarray(sheet)[:, :, 3]
    records = []
    for row, sex in enumerate(('male', 'female')):
        y0, y1 = round(row * sheet.height / 2), round((row + 1) * sheet.height / 2)
        occupied = (alpha[y0:y1] > 32).sum(axis=0)
        boundaries = [0]
        for column in range(1, 5):
            nominal = round(column * sheet.width / 5)
            radius = round(sheet.width * .06)
            zeros = np.flatnonzero(occupied[nominal-radius:nominal+radius] == 0) + nominal-radius
            if len(zeros) < 3:
                raise ValueError(f'No transparent gutter: row {row}, column {column}')
            boundaries.append(int(zeros[len(zeros)//2]))
        boundaries.append(sheet.width)
        for column, job in enumerate(JOBS):
            cell_box = (boundaries[column], y0, boundaries[column+1], y1)
            cell = sheet.crop(cell_box)
            mask = cell.getchannel('A').point(lambda x: 255 if x > 32 else 0)
            bounds = mask.getbbox()
            assert bounds
            box = (max(0, bounds[0]-2), max(0, bounds[1]-2),
                   min(cell.width, bounds[2]+2), min(cell.height, bounds[3]+2))
            art = cell.crop(box)
            assert (np.asarray(art)[:, :, 3] > 32).sum() == (np.asarray(cell)[:, :, 3] > 32).sum()
            target = OUT / 'masters' / job / f'{sex}-approved-front.png'
            target.parent.mkdir(parents=True, exist_ok=True)
            art.save(target)
            source_box = [cell_box[0]+box[0], y0+box[1], cell_box[0]+box[2], y0+box[3]]
            assert art.tobytes() == sheet.crop(source_box).tobytes()
            records.append(dict(job=job, sex=sex, path=str(target.relative_to(OUT)),
                                source_box=source_box, size=list(art.size), sha256=digest(target),
                                source_rgba_preserved=True))
    return records


def head_piece(heads, ha, frame):
    hf = ha.actions[0][0]
    bx, by = anchor(frame)
    hx, hy = anchor(hf)
    layer = next(l for l in hf.layers if l.index >= 0)
    im = rgba(heads, layer.index, layer.kind)
    if layer.mirror:
        im = im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    x = layer.x + bx - hx - im.width//2
    y = layer.y + by - hy - im.height//2
    # This is only a collar-height guide for the sizing proof. Final pose
    # fitting must review the actual face/collar overlap in every direction.
    a = np.asarray(im)[:, :, 3]
    middle = a[:, round(im.width*.40):round(im.width*.60)] > 64
    chin_y = y + int(np.where(middle)[0].max()) + 1
    return im, x, y, chin_y


def scale_study(records):
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 13)
    small = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 11)
    board = Image.new('RGB', (1500, 640), '#283746')
    draw = ImageDraw.Draw(board)
    draw.text((12, 8), 'Original artwork / front scale study only - poses and animation not yet fitted', font=font, fill='white')
    reports = []
    for row, sex in enumerate(('male', 'female')):
        _, _, _, heads, ha = load(sex)
        for column, job in enumerate(JOBS):
            rec = next(r for r in records if (r['job'], r['sex']) == (job, sex))
            art = Image.open(OUT/rec['path']).convert('RGBA')
            folder = SOURCES/'source'/job/sex
            spr = Spr((folder/'body.spr').read_bytes())
            act = read_act((folder/'body.act').read_bytes())
            frame = act.actions[0][0]
            layer = next(l for l in frame.layers if l.index >= 0)
            native = rgba(spr, layer.index, layer.kind)
            if layer.mirror:
                native = native.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
            nx, ny = layer.x-native.width//2, layer.y-native.height//2
            bounds = native.getbbox()
            head, hx, hy, chin = head_piece(heads, ha, frame)
            foot_y = ny+bounds[3]
            top = min(ny+bounds[1], chin-2)
            scale, _ = reference_scale(art, top, foot_y)
            resized, left4, top4, registration = register_master(art, scale, hx+head.width/2, foot_y)
            x0, y0 = column*300, 35+row*300
            draw.text((x0+8, y0), f'{job.title()} / {sex}', font=font, fill='white')
            for index in range(2):
                origin = (x0+75+index*150, y0+232)
                if index == 0:
                    b = native.resize((native.width*2,native.height*2),Image.Resampling.NEAREST)
                    board.paste(b,(origin[0]+nx*2,origin[1]+ny*2),b)
                else:
                    b = resized.convert('RGBa').resize((resized.width//2,resized.height//2),Image.Resampling.LANCZOS).convert('RGBA')
                    board.paste(b,(origin[0]+round(left4/2),origin[1]+round(top4/2)),b)
                h = head.resize((head.width*2,head.height*2),Image.Resampling.NEAREST)
                board.paste(h,(origin[0]+hx*2,origin[1]+hy*2),h)
                draw.text((x0+20+index*150,y0+253), 'Native' if index == 0 else 'New design',font=small,fill='#cbd7e0')
            reports.append(dict(job=job,sex=sex,native_head_anchor=anchor(frame),
                                source_body_sha256=digest(folder/'body.spr'),
                                source_act_sha256=digest(folder/'body.act'),
                                study_body_box_4x=registration['body_scale_box_4x'],
                                uniform_scale_4x=scale,
                                geometry_status='Sizing study only; pose registration pending'))
    board.save(OUT/'front-scale-study.png')
    return reports


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--acceptance-message', required=True)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    source_hash = digest(args.source)
    saved = OUT/'approved-costume-designs.png'
    if saved.exists() and digest(saved) != source_hash:
        raise ValueError('A different sheet is already recorded; create a new design revision')
    shutil.copyfile(args.source, saved)
    sheet = Image.open(saved)
    assert sheet.mode == 'RGBA'
    assert sheet.getchannel('A').getextrema()[0] == 0
    records = extract(sheet)
    studies = scale_study(records)
    plan = json.loads((OUT/'design-plan.json').read_text())
    plan.update(status='All five original costume designs approved; directional art and animation in development',
                design_acceptance=dict(message=args.acceptance_message,
                    scope='Ten original front costume designs only; animation and runtime acceptance pending',
                    source_file=saved.name,source_sha256=source_hash),
                generation=dict(tool='Built-in image generation',source_file=str(args.source),
                    actual_transparency=True,alpha_range=sheet.getchannel('A').getextrema()),
                masters=records,scale_study=studies,
                directional_status=plan.get('directional_status', {job:'pending' for job in JOBS}),
                runtime_status=plan.get('runtime_status', {job:'not built' for job in JOBS}))
    (OUT/'design-plan.json').write_text(json.dumps(plan,indent=2),encoding='utf8')
    print(json.dumps(dict(approved_source_sha256=source_hash,cutouts=len(records),
                         rgba_crop_checks='passed',output=str(OUT),runtime_assets_created=False)))


if __name__ == '__main__':
    main()
