"""Correct Archer design collar registration without changing the approved stride."""
import argparse
import copy
import hashlib
import json
import struct

import numpy as np
from PIL import Image

from package_clan_skin_assets import ROOT
from build_female_mage_v10 import continuous_warp
from review_original_job_directions import native_context
from review_full_swordman_set import body, head, ORIGIN
from render_native_wing_anatomy import rgba
from sprite_formats import read_spr, read_act, write_spr, write_act, anchor
from spr_reader import Spr
from refine_clan_combat_necks import components

BASE = ROOT / 'Assets/ClanBodySkins/Archer/rejected-design-v1'
WORK = BASE.parent / 'alignment-v2'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def neck_point(refs, sex, native, heads, head_act, ai, fi):
    hf = head_act.actions[ai][min(fi, len(head_act.actions[ai]) - 1)]
    layer = next(layer for layer in hf.layers if layer.index >= 0)
    image = heads.images[layer.index]
    point = np.array(next(row['point'] for row in refs if row['sex'] == sex and row['head_sprite'] == layer.index))
    if layer.mirror:
        point[0] = image.width * 4 - point[0]
    top = (np.array([layer.x, layer.y]) + anchor(native.actions[ai][fi]) - np.array(anchor(hf))) * 4
    return point + top - np.array([image.width, image.height]) * 2


def sitting_collar(row, native, sprite, frame):
    source = native.actions[row['action']][0].layers[0]
    raw = sprite.images[source.index]
    local = np.array(row['point']) - np.array([source.x - raw.width // 2, source.y - raw.height // 2]) * 4
    layer = frame.layers[0]
    if layer.mirror:
        local[0] = raw.width * 4 - local[0]
    return local + np.array([layer.x - raw.width // 2, layer.y - raw.height // 2]) * 4


def main():
    rejection = json.loads((BASE / 'user-review.json').read_text(encoding='utf8'))
    for row in rejection['files']:
        assert digest(BASE / row['path']) == row['sha256']
    for row in json.loads((WORK / 'native-reference-pins.json').read_text(encoding='utf8')):
        assert digest(ROOT / row['path']) == row['sha256']
    landmarks = json.loads((WORK / 'neck-landmarks.json').read_text(encoding='utf8'))
    refs = json.loads((WORK / 'head-neck-reference.json').read_text(encoding='utf8'))
    (WORK / 'assets').mkdir(exist_ok=True)
    proofs, files = [], []
    for sex in ('male', 'female'):
        stem = BASE / 'assets' / (sex + '-angel-archer-v1')
        original_bytes = stem.with_suffix('.spr').read_bytes()
        old_images, old_act = read_spr(original_bytes), read_act(stem.with_suffix('.act').read_bytes())
        images, act = [image.copy() for image in old_images], copy.deepcopy(old_act)
        _, native_spr, native, heads, head_act = native_context('archer', sex)
        walks = []
        if sex == 'female':
            for row in landmarks['female_walk']:
                fi = row['frame']
                source = body(sex, 8, fi, (old_images, old_act), job='archer')
                center, target = np.array(row['source_point']) / 4, np.array(row['target_point']) / 4
                angle = row['angle_radians']
                axis = np.array([np.cos(angle), np.sin(angle)])
                src = [center + t * axis for t in (-4, 0, 4)]
                dst = [target + [t, 0] for t in (-4, 0, 4)]
                # Anchor shoulders; terminate the map above the waist and hands.
                for x in (-13, 13):
                    point = np.array([x, target[1] + 7])
                    src.append(point)
                    dst.append(point)
                lower = int(np.ceil(target[1] + 11))
                revised, proof = continuous_warp(source, src, dst, lower)
                cutoff = ORIGIN[1] + lower * 4
                assert np.array_equal(np.asarray(revised)[cutoff:], np.asarray(source)[cutoff:])
                layer = old_act.actions[8][fi].layers[0]
                sprite = old_images[layer.index]
                x = ORIGIN[0] + layer.x * 4 - sprite.width // 2
                y = ORIGIN[1] + layer.y * 4 - sprite.height // 2
                # Symmetric transparent padding retains the ACT center and
                # allows the collar to move fractionally beyond the old crop.
                padding = 8
                cropped = revised.crop((x - padding, y - padding, x + sprite.width + padding, y + sprite.height + padding))
                restored = Image.new('RGBA', revised.size)
                restored.alpha_composite(cropped, (x - padding, y - padding))
                assert restored.tobytes() == revised.tobytes(), ('Correction clipped', fi)
                uses = [(ai, k) for ai, frames in enumerate(old_act.actions) for k, f in enumerate(frames)
                        if any(item.index == layer.index for item in f.layers)]
                assert uses == [(8, fi)], ('Walking image shared with another action', uses)
                assert len(components(np.asarray(cropped)[:, :, 3] > 0)) == 1, ('Detached collar pixel', fi)
                assert not np.asarray(cropped)[np.asarray(cropped)[:, :, 3] == 0].any()
                images[layer.index] = cropped
                assert head(sex, 8, fi, job='archer', pair=(images, act)).tobytes() == head(sex, 8, fi, job='archer', pair=(old_images, old_act)).tobytes()
                walks.append(dict(frame=fi, sprite=layer.index, native_head_pixels_preserved=True,
                                  lower_body_pixels_preserved=True, **proof))
        sitting = []
        for ai in range(16, 24):
            for fi, frame in enumerate(act.actions[ai]):
                native_frame = native.actions[ai][fi]
                source_index = native_frame.layers[0].index
                row = next(row for row in landmarks['sitting'] if row['sex'] == sex
                           and native.actions[row['action']][0].layers[0].index == source_index)
                collar = sitting_collar(row, native, native_spr, native_frame)
                neck = neck_point(refs, sex, native, heads, head_act, ai, fi)
                delta = np.rint((collar - neck) / 4).astype(int)
                old_anchor = np.array(anchor(frame))
                data = bytearray(frame.anchors[0])
                struct.pack_into('<ii', data, 4, *map(int, old_anchor + delta))
                frame.anchors[0] = bytes(data)
                assert body(sex, ai, fi, (images, act), job='archer').tobytes() == body(sex, ai, fi, (old_images, old_act), job='archer').tobytes()
                error = float(np.linalg.norm(neck + delta * 4 - collar) / 4)
                assert error <= .708
                sitting.append(dict(action=ai, frame=fi, collar_4x=collar.tolist(), head_shift_native=delta.tolist(),
                                    attachment_error_native=error, body_pixels_preserved=True))
        assert act.speeds == old_act.speeds and act.tail == old_act.tail
        for ai, frames in enumerate(act.actions):
            for fi, frame in enumerate(frames):
                previous = old_act.actions[ai][fi]
                assert frame.layers == previous.layers and frame.ranges == previous.ranges and frame.sound == previous.sound
                if ai not in range(16, 24):
                    assert frame.anchors == previous.anchors
                else:
                    assert frame.anchors[0][:4] == previous.anchors[0][:4]
                    assert frame.anchors[0][12:] == previous.anchors[0][12:] and frame.anchors[1:] == previous.anchors[1:]
        changed_images = [i for i, (old, new) in enumerate(zip(old_images, images)) if old.tobytes() != new.tobytes()]
        assert changed_images == ([old_act.actions[8][fi].layers[0].index for fi in range(8)] if sex == 'female' else [])
        sprite_bytes = original_bytes if sex == 'male' else write_spr(images)
        independent = Spr(sprite_bytes)
        decoded = read_spr(sprite_bytes)
        assert all(im.tobytes() == rgba(independent, i, 1).tobytes() for i, im in enumerate(decoded))
        output = WORK / 'assets' / (sex + '-angel-archer-v2')
        sex_files = []
        for ext, raw in (('.spr', sprite_bytes), ('.act', write_act(act))):
            path = output.with_suffix(ext)
            path.write_bytes(raw)
            record = dict(path=path.relative_to(WORK).as_posix(), sha256=digest(path))
            sex_files.append(record)
            files.append(dict(sex=sex, **record))
        report = json.loads((BASE / (sex + '-verification.json')).read_text(encoding='utf8'))
        report.update(status='Corrected design candidate', files=sex_files, native_metadata_preserved=False,
                      native_walk_head_metadata_preserved=True, sitting_body_pixels_preserved=True,
                      sitting_head_anchors_corrected=True, independent_decoder_match=True, installed=False)
        (WORK / (sex + '-verification.json')).write_text(json.dumps(report, indent=2), encoding='utf8')
        proofs.append(dict(sex=sex, changed_images=changed_images, walking=walks, sitting=sitting))
    report = dict(status='design_correction_candidate', accepted=False, installed=False, files=files, checks=proofs,
                  scope='Female front-walk collar only; all sitting head attachments for both sexes')
    (WORK / 'alignment-verification.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    print(json.dumps(dict(status=report['status'], files=files,
                          sitting_frames=sum(len(p['sitting']) for p in proofs), walking_frames=8,
                          minimum_jacobian=min(r['minimum_jacobian'] for p in proofs for r in p['walking']))))


def seat_diagonal_heads():
    """Seat only the six female diagonal sitting head turns one native pixel deeper."""
    source = WORK
    destination = source.parent / 'alignment-v3'
    (destination / 'assets').mkdir(parents=True, exist_ok=True)
    rejection = json.loads((source / 'user-review.json').read_text(encoding='utf8'))
    for row in rejection['files']:
        assert digest(source / row['path']) == row['sha256']
    files, checks = [], []
    for sex in ('male', 'female'):
        stem = source / 'assets' / (sex + '-angel-archer-v2')
        old_bytes = stem.with_suffix('.act').read_bytes()
        old = read_act(old_bytes)
        act = copy.deepcopy(old)
        changed = []
        if sex == 'female':
            for ai in (17, 23):
                for fi, frame in enumerate(act.actions[ai]):
                    x, y = anchor(frame)
                    data = bytearray(frame.anchors[0])
                    struct.pack_into('<ii', data, 4, x, y + 1)
                    frame.anchors[0] = bytes(data)
                    changed.append(dict(action=ai, frame=fi, head_shift_native=[0, 1]))
        assert act.speeds == old.speeds and act.tail == old.tail
        actual = []
        for ai, frames in enumerate(act.actions):
            for fi, frame in enumerate(frames):
                prior = old.actions[ai][fi]
                assert frame.layers == prior.layers and frame.ranges == prior.ranges and frame.sound == prior.sound
                if frame.anchors != prior.anchors:
                    assert sex == 'female' and ai in (17, 23)
                    assert frame.anchors[0][:4] == prior.anchors[0][:4] and frame.anchors[0][12:] == prior.anchors[0][12:]
                    assert frame.anchors[1:] == prior.anchors[1:]
                    x, y = anchor(prior)
                    assert anchor(frame) == (x, y + 1) or list(anchor(frame)) == [x, y + 1]
                    actual.append((ai, fi))
        assert actual == ([(ai, fi) for ai in (17, 23) for fi in range(3)] if sex == 'female' else [])
        new_bytes = write_act(act) if changed else old_bytes
        assert len(new_bytes) == len(old_bytes)
        sprite_bytes = stem.with_suffix('.spr').read_bytes()
        output = destination / 'assets' / (sex + '-angel-archer-v3')
        sex_files = []
        for ext, raw in (('.spr', sprite_bytes), ('.act', new_bytes)):
            path = output.with_suffix(ext)
            path.write_bytes(raw)
            entry = dict(path=path.relative_to(destination).as_posix(), sha256=digest(path))
            sex_files.append(entry)
            files.append(dict(sex=sex, **entry))
        report = json.loads((source / (sex + '-verification.json')).read_text(encoding='utf8'))
        report.update(files=sex_files, status='Diagonal sitting join correction candidate', installed=False,
                      all_body_pixels_preserved_from_v2=True, changed_head_frames=changed)
        (destination / (sex + '-verification.json')).write_text(json.dumps(report, indent=2), encoding='utf8')
        checks.append(dict(sex=sex, sprite_bytes_identical=True, body_layers_identical=True,
                           changed_head_frames=changed, action_frame_uses_checked=sum(map(len, act.actions)),
                           changed_act_bytes=sum(a != b for a, b in zip(old_bytes, new_bytes))))
    result = dict(status='design_correction_candidate', accepted=False, installed=False, complete_animation_set=False,
                  scope='One native pixel deeper seating for all female sitting head turns in directions 1 and 7',
                  files=files, checks=checks, walking_unchanged_from_v2=True, male_pair_unchanged_from_v2=True)
    (destination / 'alignment-verification.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    print(json.dumps(result))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--seat-diagonal', action='store_true', help='Build V3 from the pinned V2 candidate')
    args = parser.parse_args()
    seat_diagonal_heads() if args.seat_diagonal else main()
