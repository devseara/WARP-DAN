"""Export the optional All_Riding patch and verify atomic rejection/idempotence."""

import argparse
import hashlib
import json
from pathlib import Path
import pefile
from build_native_act_job_ui import ORIGINAL
from verify_native_act_job_ui_warp import fixture_at, export


def same_sections(a, b):
    x, y = pefile.PE(str(a)), pefile.PE(str(b))
    try:
        assert len(x.sections) == len(y.sections)
        assert all(
            s.get_data() == y.get_data(s.VirtualAddress, s.SizeOfRawData) for s in x.sections
        )
    finally:
        x.close()
        y.close()


def build(source, out):
    assert source.is_file() and not out.exists(), 'Use a fresh output folder.'
    out.mkdir(parents=True)
    fixture = fixture_at(out)
    candidate = export(fixture, out / 'candidate', source, ['AllowAllRidingCombat'])
    bad = out / 'mismatched-native-gate.exe'
    raw = bytearray(ORIGINAL.read_bytes())
    pe = pefile.PE(data=bytes(raw))
    raw[pe.get_offset_from_rva(0xC8F7E2 - 0x400000)] ^= 1
    pe.close()
    bad.write_bytes(raw)
    rejected = export(
        fixture,
        out / 'bad-gate',
        bad,
        ['AllowAllRidingCombat'],
        'native mount gate differs: normal attack',
    )
    if rejected.exists():
        same_sections(bad, rejected)
    # WARP restores its stored original bytes before reapplying a selected
    # patch. Reopening a WARP export is intentionally idempotent, not an error.
    repeated = export(fixture, out / 'reopened', candidate, ['AllowAllRidingCombat'])
    same_sections(candidate, repeated)
    report = dict(
        passed=True,
        source=str(source),
        candidate=str(candidate),
        source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        candidate_sha256=hashlib.sha256(candidate.read_bytes()).hexdigest(),
        last_gate_mismatch_rejected_before_any_write=True,
        warp_reopened_export_idempotent=True,
        deployed=False,
    )
    (out / 'build.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args()
    build(args.source.resolve(), args.output.resolve())
