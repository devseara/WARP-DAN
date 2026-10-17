"""Journal a long read-only weather soak in bounded sampling chunks; never change game/server state."""
import argparse
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pid', type=int)
    parser.add_argument('--minutes', type=float, default=60)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    assert 1 <= args.minutes <= 240
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    journal = output / 'journal.jsonl'
    assert not journal.exists(), 'Choose a fresh output directory; preserve prior evidence'
    started = time.monotonic()
    records = []
    failures = []
    stationary_position = None
    server = ROOT.parent / 'BanquetOfHeroes'
    configs = ['conf/import/battle_conf.txt', 'conf/world_environment.yml', 'conf/import/world_environment.yml']
    config_hashes = {name: hashlib.sha256((server/name).read_bytes()).hexdigest() for name in configs}
    try:
        with journal.open('x', encoding='utf8') as log:
            while time.monotonic() - started < args.minutes * 60:
                index = len(records)
                target = output / f'chunk-{index:03d}.json'
                seconds = min(30, args.minutes * 60 - (time.monotonic() - started))
                if seconds < 1:
                    break
                result = subprocess.run([
                    sys.executable, str(ROOT / 'tools/sample_celestial_weather.py'), str(args.pid),
                    '--seconds', str(seconds), '--interval', '.25', '--census', '--output', str(target)
                ], capture_output=True, timeout=55)
                if result.returncode:
                    (output / f'chunk-{index:03d}.error.log').write_bytes(result.stdout + result.stderr)
                    raise RuntimeError('Live sampler failed; inspect the chunk error log')
                data = json.loads(target.read_text())
                row = data['summary']
                row['soak_elapsed_seconds'] = time.monotonic() - started
                row['recorded_utc'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
                assert all(hashlib.sha256((server/name).read_bytes()).hexdigest() == digest
                           for name, digest in config_hashes.items()), 'Normal config changed during soak'
                owned = row['owned_census']
                if owned and owned.get('stable'):
                    if owned['parents'] > 1 or owned['primitives'] > 96:
                        failures.append({'chunk': index, 'reason': 'owned weather bound exceeded', 'census': owned})
                    clear = data['samples'] and all(
                        sample['ready'] and not sample['weather'] & 128 and not sample['lease_ms']
                        for sample in data['samples'])
                    if clear and (owned['parents'] or owned['primitives']):
                        failures.append({'chunk': index, 'reason': 'private weather retained throughout clear interval', 'census': owned})
                if row['maps'] != ['prt_fild08']:
                    failures.append({'chunk': index, 'reason': 'test character left the controlled outdoor map', 'maps': row['maps']})
                bounds = row.get('position_bounds')
                if stationary_position is None and bounds:
                    stationary_position = [sum(axis) / 2 for axis in bounds]
                if not bounds or any(abs(value - stationary_position[axis]) > 1
                                     for axis, pair in enumerate(bounds) for value in pair):
                    failures.append({'chunk': index, 'reason': 'character moved from the stationary control position',
                                     'position_bounds': bounds})
                records.append(row)
                log.write(json.dumps(row) + '\n')
                log.flush()
                (output / 'progress.json').write_text(json.dumps({
                    'elapsed_minutes': row['soak_elapsed_seconds'] / 60, 'chunks': len(records),
                    'latest': row, 'failures': failures
                }, indent=2) + '\n')
                print(f"CHUNK {index:03d}: {row['soak_elapsed_seconds']/60:.1f} min; "
                      f"weather={row['weather_masks']}; owned={owned}; private={row['private_bytes']}; handles={row['handles']}", flush=True)
    finally:
        report = {'completed': time.monotonic() - started >= args.minutes * 60 - 1,
                  'seconds': time.monotonic() - started, 'chunks': len(records), 'failures': failures,
                  'configuration_sha256': config_hashes, 'read_only': True,
                  'client_sha256': records[0]['client_sha256'] if records else None,
                  'stationary_position': stationary_position,
                  'not_a_gpu_or_absolute_heap_leak_proof': True}
        (output / 'collection.json').write_text(json.dumps(report, indent=2) + '\n')
    assert not failures, 'Soak recorded anomalies; review before committing'
    print('COMPLETE: collection finished; inspect phase coverage and memory trends before acceptance', flush=True)


if __name__ == '__main__':
    main()
