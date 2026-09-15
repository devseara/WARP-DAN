"""Save original job pose/wing references and a supplied approved design."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from package_clan_skin_assets import ROOT
from grf_reader import GrfFile
from sprite_formats import read_act
from spr_reader import Spr

JOBS = {'acolyte': '성직자', 'archer': '궁수', 'merchant': '상인', 'thief': '도둑'}
GAME = Path('C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes')


def prepare(job, design, game=GAME):
    work = ROOT / 'Assets/ClanBodySkins' / job.title()
    target = work / 'design/approved-directions.png'
    target.parent.mkdir(parents=True, exist_ok=True)
    raw = design.read_bytes()
    if target.exists() and target.read_bytes() != raw:
        raise ValueError('A different design is already saved; use a new revision')
    target.write_bytes(raw)
    provenance = dict(job=job, source=str(design), sha256=hashlib.sha256(raw).hexdigest(),
                      reference_role='Previously approved costume directions; animation is unreviewed',
                      source_has_opaque_checkerboard=True)
    (target.parent / 'provenance.json').write_text(json.dumps(provenance, indent=2), encoding='utf8')
    grfs = [GrfFile(game / name) for name in ('palettedata.grf', 'spritedata.grf')]
    rows = []
    try:
        for sex, key in [('male', '남'), ('female', '여')]:
            folder = work / 'native' / sex
            folder.mkdir(parents=True, exist_ok=True)
            resources = []
            for kind, stem in [('body', f'data/sprite/인간족/몸통/{key}/{JOBS[job]}_{key}'),
                               ('wing', f'data/sprite/로브/천사날개/{key}/{JOBS[job]}_{key}')]:
                for ext in ('.spr', '.act'):
                    entry = stem + ext
                    archive = next(g for g in grfs if entry in g.entries)
                    data = archive.read(entry)
                    destination = folder / (kind + ext)
                    if destination.exists() and destination.read_bytes() != data:
                        raise ValueError('Native reference changed: ' + str(destination))
                    destination.write_bytes(data)
                    resources.append(dict(kind=kind + ext, entry=entry, archive=Path(archive.path).name,
                                          sha256=hashlib.sha256(data).hexdigest()))
            for ext in ('.spr', '.act'):
                source = ROOT / 'Assets/ClanBodySkins/Mage/native' / sex / ('head' + ext)
                shutil.copyfile(source, folder / ('head' + ext))
            act = read_act((folder / 'body.act').read_bytes())
            sprite = Spr((folder / 'body.spr').read_bytes())
            rows.append(dict(sex=sex, actions=len(act.actions), frame_uses=sum(map(len, act.actions)),
                             unique_sprites=len(sprite.images), resources=resources))
    finally:
        for archive in grfs:
            archive.close()
    (work / 'native/source-audit.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
    print(json.dumps(dict(job=job, coverage=[{k: v for k, v in row.items() if k != 'resources'} for row in rows])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', choices=JOBS, required=True)
    parser.add_argument('--design', type=Path, required=True)
    parser.add_argument('--game', type=Path, default=GAME)
    args = parser.parse_args()
    prepare(args.job, args.design, args.game)
