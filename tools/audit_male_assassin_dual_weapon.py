"""Audit male source cells and render unmodified generic pairs on male bodies.

This is asset research, not a male compositor implementation. Packet geometry
executes the installed 2025 PE's native C40C20; CPU previews omit head, effects
and GPU depth, and use fixed inspection timing. No game files are modified.
"""
from __future__ import annotations
import hashlib
import html
import json
import math
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / '.venv/Lib/site-packages'))
sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFont
from audit_dual_weapon_type_coverage import Corpus
from dual_weapon_formats.act_reader import parse_act
from dual_weapon_formats.spr_reader import Spr
from verify_dual_weapon_native_projection import NativeProjector, normalized_layer
from render_dual_weapon_native_overlay import paint
from verify_dual_weapon_compositor import PAIR_NAMES

CLIENT = Path('D:/Programs/Games/Ragnarok/02_client/Banquet of Heroes')
EXE = CLIENT / '2025-07-16_Ragexe_175220998_clientinfo_patched.exe'
OUT = ROOT / 'Outputs/dual_weapon_male_research'
REPORT = ROOT / 'docs/evidence/dual-weapon-male-assassin-assets-20260905.json'
FAMILIES = {'assassin': 'data/sprite/인간족/어세신/어세신_남_',
            'shadow_cross': 'data/sprite/인간족/shadow_cross/shadow_cross_남_'}
BODIES = {'assassin': ('어세신_남', 'assassin'),
          'assassin_high': ('어세신_h_남', 'assassin'),
          'assassin_cross': ('어쌔신크로스_남', 'assassin'),
          'guillotine_cross': ('길로틴크로스_남', 'assassin'),
          'shadow_cross': ('shadow_cross_남', 'shadow_cross')}
GROUPS = {'held32': 32, 'solo80': 80, 'dual88': 88}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    corpus = Corpus(CLIENT)
    assets, cache = {}, {}
    projector = NativeProjector(EXE)
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 14)
    declarations = json.loads((ROOT / 'docs/evidence/dual-weapon-type-coverage.json').read_text(encoding='utf-8'))
    declarations = {r['view']: r['resource_stem'] for r in declarations['views']
                    if r['view'] in [1, 2, 6, *range(34, 48)]}

    def load(stem):
        if stem in assets:
            return cache.get(stem)
        raw, pixels = corpus.read(stem + '.act'), corpus.read(stem + '.spr')
        entry = assets[stem] = {'ACT': corpus.sources.get(stem.lower() + '.act'),
                                'SPR': corpus.sources.get(stem.lower() + '.spr')}
        if raw is None or pixels is None:
            entry['status'] = corpus.absent_status()
            return None
        # The current repository reader does not implement float offsets in 2.6.
        assert raw[3] + raw[2] / 10 <= 2.5, (stem, 'unsupported ACT version')
        act, spr = parse_act(raw), Spr(pixels)
        ims, image_rows = {}, []
        for kind, count in ((0, spr.n_indexed8), (1, spr.n_bgra32)):
            for index in range(count):
                rgba, w, h = spr.get_rgba(index, kind)
                im = Image.frombytes('RGBA', (w, h), rgba)
                ims[(kind, index)] = im
                image_rows.append({'kind': kind, 'index': index, 'width': w, 'height': h,
                                   'rgba_sha256': hashlib.sha256(rgba).hexdigest(),
                                   'alpha_bbox': im.getchannel('A').getbbox(),
                                   'opaque_pixels': sum(a > 0 for a in rgba[3::4])})
        use = defaultdict(set)
        groups = {}
        for ai, action in enumerate(act['actions']):
            for frame in action.frames:
                for l in frame.layers:
                    if (l.sprite_type, l.sprite_index) in ims:
                        use[(l.sprite_type, l.sprite_index)].add(ai)
        for row in image_rows:
            row['used_in_actions'] = sorted(use[(row['kind'], row['index'])])
        for label, base in GROUPS.items():
            cells = []
            for d in range(8):
                frames = act['actions'][base+d].frames if base+d < len(act['actions']) else []
                rows = []
                for f, frame in enumerate(frames):
                    layers = []
                    for l in frame.layers:
                        im = ims.get((l.sprite_type, l.sprite_index))
                        status = ('negative_index' if l.sprite_index < 0 else 'invalid_image') if im is None else (
                            'visible' if im.getchannel('A').getbbox() and l.color[3] and l.scale_x and l.scale_y else 'transparent_or_zero_scale')
                        layers.append({'image': [l.sprite_type, l.sprite_index], 'xy': [l.x, l.y],
                                       'mirror': l.mirror, 'angle': l.rotation,
                                       'scale': [l.scale_x, l.scale_y], 'status': status})
                    rows.append({'frame': f, 'layers': layers, 'anchors': frame.anchors})
                cells.append({'direction': d, 'frame_count': len(frames), 'frames': rows,
                              'visible_frames': [r['frame'] for r in rows if any(l['status'] == 'visible' for l in r['layers'])]})
            groups[label] = cells
        entry.update(status='resolved', act_version=act['version'], spr_version=spr.version,
                     action_count=len(act['actions']), images=image_rows, groups=groups)
        cache[stem] = act, spr, ims
        return cache[stem]

    weapons = {}
    for family, prefix in FAMILIES.items():
        weapons[family] = {}
        for view, suffix in declarations.items():
            stem = prefix + suffix
            load(stem)
            load(stem + '_검광')
            weapons[family][view] = stem
        for suffix in PAIR_NAMES.values():
            load(prefix + suffix)
            load(prefix + suffix + '_검광')
    bodies = {}
    for label, (name, family) in BODIES.items():
        stem = 'data/sprite/인간족/몸통/남/' + name
        load(stem)
        bodies[label] = {'stem': stem, 'candidate_weapon_family': family,
                         'live_resource_mapping_verified': False}

    # Inventory alternates without claiming their job dispatch has been traced.
    variants = sorted(k for k in corpus.keys if k.startswith('data/sprite/인간족/몸통/')
                      and k.endswith('.act') and ('/남/' in k or '/남c/' in k)
                      and any(s in k for s in ('어세신', '어쌔신크로스', '길로틴크로스', 'shadow_cross')))

    # Raw image identity: sharing a suffix does not establish shared texel coordinates.
    gender_comparison = []
    for view, suffix in declarations.items():
        female = 'data/sprite/인간족/어세신/어세신_여_' + suffix
        load(female)
        male = weapons['assassin'][view]
        def signatures(stem):
            return {(r['width'], r['height'], r['rgba_sha256']) for r in assets[stem].get('images', [])}
        gender_comparison.append({'view': view, 'male_images': len(assets[male].get('images', [])),
                                   'female_images': len(assets[female].get('images', [])),
                                   'identical_image_signatures': len(signatures(male) & signatures(female)),
                                   'ACT_equal': assets[male]['ACT']['sha256'] == assets[female]['ACT']['sha256']})

    projected = []
    projection_cache = {}
    def project_layers(stem, action, frame):
        key = stem, action, frame
        if key in projection_cache:
            return projection_cache[key]
        result = projection_cache[key] = []
        data = cache.get(stem)
        if not data or action >= len(data[0]['actions']):
            return result
        frames = data[0]['actions'][action].frames
        if frame >= len(frames):
            return result  # Never modulo an unprofiled resource timeline.
        act, spr, images = data
        for li, raw in enumerate(frames[frame].layers):
            im = images.get((raw.sprite_type, raw.sprite_index))
            if im is None or not im.getchannel('A').getbbox():
                continue
            offset = raw.sprite_index + (spr.n_indexed8 if raw.sprite_type else 0)
            l = normalized_layer(raw, spr.images[offset])
            packet = projector.project(l, (*im.size, 0, 0), origin=(400, 300))
            geometry = [*packet[:4], packet[7]]
            result.append((im, geometry))
            projected.append({'stem': stem, 'action': action, 'frame': frame, 'layer': li,
                              'image': [raw.sprite_type, raw.sprite_index], 'geometry': geometry})
        return result

    for label, body in bodies.items():
        family = body['candidate_weapon_family']
        stock = FAMILIES[family] + PAIR_NAMES[28]
        # A single camera bounds every held/attack frame, including slash art.
        # Do not clip upright male swords to the older female preview viewport.
        corners = []
        for base in (32, 88):
            for d in range(8):
                count = len(cache[body['stem']][0]['actions'][base+d].frames)
                for f in range(count):
                    for stem in (body['stem'], stock, stock + '_검광'):
                        for im, g in project_layers(stem, base+d, f):
                            top, left, bottom, right, angle = g
                            cx, cy = (left+right)/2, (top+bottom)/2
                            c, s = math.cos(math.radians(angle)), math.sin(math.radians(angle))
                            corners.extend((cx+c*(x-cx)-s*(y-cy)-400, cy+s*(x-cx)+c*(y-cy)-300)
                                           for x in (left, right) for y in (top, bottom))
        xmin, xmax = min(x for x,y in corners), max(x for x,y in corners)
        ymin, ymax = min(y for x,y in corners), max(y for x,y in corners)
        width, height = max(360, math.ceil((xmax-xmin)*3)+40), math.ceil((ymax-ymin)*3)+40
        origin = (20/3-xmin, 20/3-ymin)
        for phase, base in (('held', 32), ('attack', 88)):
            body_directions = assets[body['stem']]['groups']['held32' if base == 32 else 'dual88']
            frames = []
            for f in range(max(row['frame_count'] for row in body_directions)):
                sheet = Image.new('RGB', (width*4, (height+30)*2), '#eef1f3')
                pen = ImageDraw.Draw(sheet)
                for d in range(8):
                    canvas = Image.new('RGBA', (width, height), '#dfeaed')
                    for stem in (body['stem'], stock, stock + '_검광'):
                        for im, g in project_layers(stem, base+d, f):
                            paint(canvas, im, g, scale=3, origin=origin)
                    x, y = d % 4 * width, d // 4 * (height+30)
                    sheet.paste(canvas, (x, y+25))
                    pen.text((x+4, y+3), f'{label} {phase} D{d} F{f}', font=font, fill='black')
                frames.append(sheet)
            frames[0].save(OUT / f'{label}-{phase}-f0.png')
            frames[0].save(OUT / f'{label}-{phase}.gif', save_all=True, append_images=frames[1:], duration=150, loop=0)

    # Every raw Zeny image is shown, including art referenced only outside held32.
    zeny = weapons['assassin'][34]
    zeny_images = cache[zeny][2]
    sheet = Image.new('RGBA', (240 * len(zeny_images), 260), '#dfeaed')
    pen = ImageDraw.Draw(sheet)
    for column, (key, im) in enumerate(zeny_images.items()):
        zoom = im.resize((im.width*4, im.height*4), Image.Resampling.NEAREST)
        sheet.alpha_composite(zoom, (column*240+20, 45))
        pen.text((column*240+5, 5), f'Male Zeny kind/index {key}', font=font, fill='black')
    sheet.convert('RGB').save(OUT / 'male-zeny-original-images.png')

    summary = {}
    for family, rows in weapons.items():
        summary[family] = {'resolved_views': [v for v, s in rows.items() if assets[s]['status'] == 'resolved'],
                           'held_frame0_blank_directions': {v: [r['direction'] for r in assets[s].get('groups', {}).get('held32', [])
                                if 0 not in r['visible_frames']] for v, s in rows.items()}}
    cross_family_identical = []
    for view in declarations:
        first, second = assets[weapons['assassin'][view]], assets[weapons['shadow_cross'][view]]
        if all(first.get(k) and second.get(k) and first[k]['sha256'] == second[k]['sha256'] for k in ('ACT', 'SPR')):
            cross_family_identical.append(view)
    report = {'schema': 'male_assassin_dual_weapon_research/v1', 'implemented': False,
              'live_acceptance': False, 'native_exe_sha256': projector.sha256,
              'native_rectangle_producer': '0x00C40C20', 'source_script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'archives': corpus.archive_profiles, 'unreadable_archives': corpus.unreadable,
              'weapon_declarations': declarations, 'weapons': weapons, 'bodies': bodies,
              'alternate_body_paths_not_profiled': variants, 'assets': assets,
              'male_female_original_image_comparison': gender_comparison, 'summary': summary,
              'assassin_shadow_cross_identical_ACT_SPR_views': cross_family_identical,
              'projection_count': len(projected), 'projection_file': str(OUT/'native-projections.json'),
              'preview_limitations': 'Generic art only. Candidate job/resource mapping is not live traced. Head/effects/GPU depth omitted. No wrapping; 150 ms inspection timing.'}
    (OUT/'native-projections.json').write_text(json.dumps(projected, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    REPORT.write_text(json.dumps(report, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
    page = ['<!doctype html><meta charset="utf-8"><title>Male Assassin resource research</title>',
            '<style>body{font:16px system-ui;background:#20272d;color:#eee;margin:24px}img{max-width:100%;image-rendering:pixelated}h2{margin-top:40px}</style>',
            '<h1>Male Assassin family: original generic ACT/SPR overlays</h1>',
            '<p>Research only; male support is not installed. Native 2025 rectangle math; body-first CPU rendering, head and GPU depth omitted. 150 ms/frame. No inferred frame wrapping.</p>']
    for label in bodies:
        page.append('<h2>'+html.escape(label)+'</h2>')
        for phase in ('held', 'attack'):
            page.append(f'<p>{phase}</p><img src="{label}-{phase}.gif">')
    page.append('<h2>Male Zeny original source images</h2><img src="male-zeny-original-images.png">')
    (OUT/'review.html').write_text('\n'.join(page), encoding='utf-8')
    corpus.close()
    print(json.dumps({'summary': summary, 'body_variants': len(variants), 'projection_count': len(projected), 'report': str(REPORT)}))


if __name__ == '__main__':
    main()
