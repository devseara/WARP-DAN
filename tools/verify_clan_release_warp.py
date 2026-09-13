"""Verify clan-only and both native-preview orders using real WARP exports."""
import argparse
import json
from pathlib import Path
import tempfile
from build_native_act_job_ui import build as build_native
from verify_native_act_job_ui_warp import fixture_at, export, verify as verify_preview, ORIGINAL
from verify_clan_body_skins import verify as verify_clan, HOOKS, ROOT


def run(existing=None):
    build_native(check=True)
    out = existing or Path(tempfile.mkdtemp(prefix='clan-release-warp-', dir=ROOT / 'Outputs'))
    fixture = out / 'fixture' if existing else fixture_at(out)
    rows = []
    cases = [('clan-only', ['ClanBodySkins']),
             ('clan-first', ['ClanBodySkins', 'NativeActJobPreviews']),
             ('native-first', ['NativeActJobPreviews', 'ClanBodySkins'])]
    for name, patches in cases:
        target = out / name / 'client.exe' if existing else export(fixture, out / name, ORIGINAL, patches)
        row = verify_clan(target, source=ORIGINAL if name == 'clan-only' else None, verbose=False)
        if name != 'clan-only':
            payload = int(row['payload_va'], 16)
            writes = [(va, size) for va, size, _ in HOOKS] + [(0xc4a63e, 9)]
            allocations = [(payload, row['payload_bytes'])]
            allocations += [(row['native_api'][i + 1], size + 5) for i, (_, size, _) in enumerate(HOOKS)]
            allocations += [(row['perspective']['bridge_va'], row['perspective']['bridge_bytes'])]
            ui = verify_preview(ORIGINAL, target, True, writes, allocations)
            row.update(native_preview_verified=True, unrelated_native_code_verified=True, native_changed_bytes=len(ui['existing_code_changes']))
        row['case'] = name
        rows.append(row)
        print('PASS ' + name, flush=True)
    report = dict(status='source_and_export_verified', cases=rows, live_tested=False)
    (ROOT / 'docs/evidence/clan-runtime-v2.json').write_text(json.dumps(report, indent=2), encoding='utf8')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--existing', type=Path, help='Reverify an existing three-case export directory')
    run(parser.parse_args().existing)
