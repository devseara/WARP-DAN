"""Collect V9 verification evidence after building matching map/char backends.

Run the native, YAML, core and SQL checks first. This verifies lifecycle
fixtures and pins source/binary identities; it does not invoke MSBuild or
substitute for live acceptance. Package from the same unchanged checkout.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil

import pefile
from verify_bestiary_journal import verify as journal
from verify_bestiary_research_native import verify as research
from verify_bestiary_live_fixes import verify as live

ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCES = [
    'src/char/char-server.vcxproj', 'src/char/int_bestiary.cpp',
    'src/char/int_bestiary.hpp', 'src/char/int_mail.cpp', 'src/char/int_mail.hpp',
    'src/char/inter.cpp', 'src/common/bestiary_definitions.hpp',
    'src/common/bestiary_research_types.hpp', 'src/common/database.cpp',
    'src/common/database.hpp', 'src/config/renewal.hpp',
    'src/map/achievement.cpp', 'src/map/bestiary_catalog.inc',
    'src/map/bestiary_journal.cpp', 'src/map/bestiary_journal.hpp',
    'src/map/bestiary_research.cpp', 'src/map/bestiary_research.hpp',
    'src/map/bestiary_ui.cpp', 'src/map/bestiary_ui.hpp', 'src/map/clif.cpp',
    'src/map/clif.hpp', 'src/map/intif.cpp', 'src/map/map-server.vcxproj',
    'src/map/map-server-generator.vcxproj',
    'src/map/map-server-generator.vcxproj.filters', 'src/map/map.cpp',
    'src/map/mob.cpp', 'src/map/mob.hpp', 'src/map/npc.cpp',
    'src/map/pc.cpp', 'src/map/pc.hpp',
    'db/bestiary_research.yml', 'db/import/bestiary_research.yml',
    'db/import-tmpl/bestiary_research.yml', 'db/bestiary_lore.yml',
    'db/import/bestiary_lore.yml', 'db/import-tmpl/bestiary_lore.yml',
    'sql-files/upgrades/2026-09-12-bestiary-research.sql',
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for name in ['build', 'reapply', 'removed']:
        ap.add_argument('--' + name, type=Path, required=True)
    ap.add_argument('--server', type=Path, default=ROOT.parent/'BanquetOfHeroes')
    args = ap.parse_args()
    build, server = args.build.resolve(), args.server.resolve()
    assert journal(args.reapply)['passed']
    assert research(args.reapply)['passed']
    assert live(args.reapply)['passed']
    assert journal(args.removed)['passed']
    pe = pefile.PE(str(args.removed/'bestiary-preview.exe'), fast_load=True)
    try:
        assert pe.get_data(0xA449A0-pe.OPTIONAL_HEADER.ImageBase, 6) == bytes.fromhex('558bec8b4508')
    finally:
        pe.close()
    life = {'passed': True, 'checks': [
        'Reapply passes journal, personal transport and V8 regression verifiers',
        'Removal restores slash/router ownership and exact ProcessPushButton prologue',
    ], 'live_accepted': False}
    (build/'lifecycle-verification.json').write_text(json.dumps(life, indent=2), encoding='utf-8')
    reports = {}
    for kind in ['core', 'sql']:
        path = ROOT/f'Outputs/Bestiary/verification/research/{kind}-test/verification.json'
        reports[kind] = json.loads(path.read_text(encoding='utf-8'))
        assert reports[kind]['passed'], kind
        shutil.copy2(path, build/f'research-{kind}-verification.json')
    yaml_report = ROOT/'Outputs/Bestiary/verification/native/yaml-test/verification.json'
    assert json.loads(yaml_report.read_text(encoding='utf-8'))['passed']
    for name in ['journal', 'cache', 'encyclopedia', 'live-fixes', 'native-fit', 'research-native']:
        assert json.loads((build/(name+'-verification.json')).read_text(encoding='utf-8'))['passed'], name
    patch = ROOT/'Scripts/Patches/BestiaryUI.qjs'
    raw = patch.read_bytes()
    assert raw.startswith(b'/*') and b'\n' not in raw.replace(b'\r\n', b'')
    for fixture in [build, args.reapply, args.removed]:
        assert raw == (fixture/'warp-fixture/Scripts/Patches/BestiaryUI.qjs').read_bytes()
    report = {
        'passed': True,
        'server_sources': {p: sha(server/p) for p in SERVER_SOURCES},
        'binaries': {n: sha(server/'build/bestiary-v9/bin'/n)
                     for n in ['map-server.exe', 'char-server.exe']},
        'client_patch_sha256': sha(patch),
        'checks': [reports['core']['checks'], *reports['sql']['checks']],
        'live_accepted': False,
        'boundary': 'Requires matching backends built before collecting this evidence; does not build server executables.',
    }
    (build/'research-server-verification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps({'passed': True, 'source_files': len(SERVER_SOURCES), 'lifecycle': life['checks']}, indent=2))


if __name__ == '__main__':
    main()