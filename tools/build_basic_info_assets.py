"""Package the supplied Basic Info artwork without changing the source files.

The client's ImageDrawPart crops rather than stretches. Expand each one-pixel
gradient into a 213-pixel strip once, so each gauge needs one native draw.
"""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from PIL import Image


def build(source, destination):
    destination.mkdir(parents=True, exist_ok=True)
    records = {}
    for path in sorted(source.rglob('*.png')):
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        records[relative.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ('bar_hp_g', 'bar_hp_r', 'bar_sp', 'bar_ap'):
        with Image.open(source / (name + '.png')) as image:
            assert image.width == 1
            image.resize((213, image.height), Image.Resampling.NEAREST).save(
                destination / (name + '_wide.png'))
    manifest = {'source_files': records, 'gauge_width': 213,
                'generated': [name + '_wide.png' for name in
                              ('bar_hp_g', 'bar_hp_r', 'bar_sp', 'bar_ap')]}
    (destination.parent / 'assets.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Packaged {len(records)} original PNGs and four native gauge strips.')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'Inputs/BasicInfoUI/assets')
    args = parser.parse_args()
    build(args.source, args.output)
