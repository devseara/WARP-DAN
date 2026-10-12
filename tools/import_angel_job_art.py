"""Save generated registered sheets and check the native-pose import contract."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

from package_clan_skin_assets import ROOT
from import_full_swordman_art import extract


def run(job, generated):
    work = ROOT / 'Assets/ClanBodySkins' / job.title() / 'complete-v1'
    plan = json.loads((work / 'art-plan.json').read_text(encoding='utf8'))
    records = json.loads((work / 'generation-records.json').read_text(encoding='utf8'))
    audit = []
    for record in records:
        target = work / 'art' / record['sex'] / (record['name'] + '.png')
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            shutil.copyfile(generated / record['source'], target)
        elif record.get('replaces') and target.read_bytes() != (generated / record['source']).read_bytes():
            if target.read_bytes() != (generated / record['replaces']).read_bytes():
                raise ValueError('Refusing to overwrite changed artwork: ' + str(target))
            retired = work / 'rejected' / record['sex'] / record['replaces']
            retired.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(target, retired)
            shutil.copyfile(generated / record['source'], target)
        batch = next(b for b in plan['batches']
                     if (b['sex'], b['name']) == (record['sex'], record['name']))
        try:
            _, checks = extract(batch, work)
            audit.append(dict(sex=record['sex'], batch=record['name'], status='registered',
                              sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                              checks=checks))
            print(record['sex'], record['name'], len(checks), 'registered poses', flush=True)
        except (AssertionError, ValueError) as error:
            audit.append(dict(sex=record['sex'], batch=record['name'], status='needs_correction',
                              error=str(error)))
            print('IMPORT ISSUE', record['sex'], record['name'], str(error), flush=True)
    (work / 'import-audit.json').write_text(json.dumps(audit, indent=2), encoding='utf8')
    return not any(row['status'] == 'needs_correction' for row in audit)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--job', required=True, choices=('acolyte', 'archer', 'merchant', 'thief'))
    parser.add_argument('--generated', type=Path, required=True)
    args = parser.parse_args()
    raise SystemExit(0 if run(args.job, args.generated) else 1)
