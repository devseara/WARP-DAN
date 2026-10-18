"""Build either AutoHunt layout in a new isolated WARP fixture, with a test manifest."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT / '2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--design', choices=['RO Global AutoHunt UI', 'Custom AutoHunt UI v1'], default='Custom AutoHunt UI v1')
    parser.add_argument('--language', default='English')
    parser.add_argument('--support-design', choices=['RO Global AutoSupport UI','Custom AutoSupport UI v1'], default='RO Global AutoSupport UI')
    parser.add_argument('--support', action='store_true')
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--reuse-fixture', action='store_true', help='Refresh this task-owned fixture after a UI/payload change')
    args = parser.parse_args()
    out = args.output.resolve()
    if args.reuse_fixture:
        assert any(out.is_relative_to((ROOT / 'Outputs' / name).resolve()) for name in ['AutoHuntCustomV1','AutoSupportCustomV1']), 'Reuse is limited to AutoHunt task outputs'
        assert (out / 'warp-fixture/Patches.yml').is_file(), 'No isolated fixture to reuse'
    out.mkdir(parents=True, exist_ok=args.reuse_fixture)
    fixture = out / 'warp-fixture'
    fixture.mkdir(exist_ok=args.reuse_fixture)
    (fixture / 'Outputs').mkdir(exist_ok=args.reuse_fixture)
    for name in ['win32', 'Scripts', 'Tables', 'Patches', 'Inputs', 'Languages', 'Images', 'Styles']:
        if (ROOT / name).exists() and not args.reuse_fixture:
            shutil.copytree(ROOT / name, fixture / name, ignore=shutil.ignore_patterns('__pycache__'))
    for name in ['AutoCombatUI', 'AutoSupportUI', 'ROGlobalZeroMenu', 'BattlepassUI', 'GachaUI', 'VipUI', 'ModernChatUI', 'ModernNpcDialog', 'GrayMap', 'BarterUI', 'TargetMonsterHUD']:
        if (ROOT / 'Assets' / name).is_dir() and not args.reuse_fixture:
            shutil.copytree(ROOT / 'Assets' / name, fixture / 'Assets' / name)
    shutil.copy2(ROOT / 'Patches.yml', fixture / 'Patches.yml')
    if args.reuse_fixture:
        for relative in ['Scripts/Patches/AutoCombatUI.qjs', 'Scripts/Patches/AutoSupportUI.qjs', 'Patches/UI.yml', 'Inputs/AutoUI/custom-v1.bin', 'Inputs/AutoUI/custom-v1.json', 'Inputs/AutoUI/support-custom-v1.bin']:
            shutil.copy2(ROOT / relative, fixture / relative)
    if args.reuse_fixture:
        for path in (ROOT / 'Inputs/AutoUI').glob('*.json'):
            shutil.copy2(path, fixture / 'Inputs/AutoUI' / path.name)
    marker = out / 'manifest.json'
    token = uuid.uuid4().hex
    probe = '''/* Isolated AutoHunt UI build evidence. */
AutoHuntUIBuildProbe=function(_){
 const events=CACHE.get("PatchDiagnostics.Events") || [];
 const rows=events.filter(row=>row.topic==="AutoCombatUI.QjsOnly");
 if(!rows.length)throw Error("Missing AutoCombat UI diagnostics");
 const f=new TextFile(MARKER,"w");if(!f.Valid)throw Error("Manifest unavailable");
 f.WriteLine(JSON.stringify({token:TOKEN,autohunt:rows[rows.length-1].value,autosupport:(events.filter(row=>row.topic==="AutoSupportUI.QjsOnly").pop() || {}).value,events}));f.Close();return true;
};
AutoHuntUIBuildProbe.validate=()=>true;
'''.replace('MARKER', json.dumps(marker.as_posix())).replace('TOKEN', json.dumps(token))
    (fixture / 'Scripts/Patches/AutoHuntUIBuildProbe.qjs').write_bytes(probe.replace('\n', '\r\n').encode('utf-8'))
    if not args.reuse_fixture:
        with (fixture / 'Tables/Patch.yml').open('a', encoding='utf-8') as file:
            file.write('\n65004 : AutoHuntUIBuildProbe\n')
    with (fixture / 'Patches/UI.yml').open('a', encoding='utf-8') as file:
        file.write('\nAutoHuntUIBuildProbeGroup:\n    title: AutoHunt UI build probe\n    patches:\n        - AutoHuntUIBuildProbe:\n            title: AutoHunt UI export probe\n            recommend: no\n            author: WARP diagnostics\n            desc: Isolated verification manifest.\n')
    target = out / 'autohunt.exe'
    if args.profile:
        import yaml
        profile = yaml.safe_load(args.profile.read_text(encoding='utf-8-sig'))
    else:
        profile = {'inputs': {}, 'patches': ['AutoCombatUI']}
    profile['from'], profile['to'] = args.source.resolve().as_posix(), target.as_posix()
    for key, value in [('$autoCombatUILanguage', args.language), ('$autoCombatUIDesign', args.design), ('$autoSupportUIDesign', args.support_design)]:
        profile.setdefault('inputs', {})[key] = {'data': '', 'display': value, 'type': 10}
    if 'AutoCombatUI' not in profile['patches']:
        profile['patches'].append('AutoCombatUI')
    if args.support and 'AutoSupportUI' not in profile['patches']:
        profile['patches'].append('AutoSupportUI')
    profile['patches'].append('AutoHuntUIBuildProbe')
    # JSON is valid YAML and preserves exact strings without shell interpolation.
    profile_path = out / 'profile.yml'
    profile_path.write_text(json.dumps(profile, indent=2), encoding='utf-8')
    process = subprocess.run([str(fixture / 'win32/WARP_console.exe'), '-using', str(profile_path)], cwd=fixture, capture_output=True, timeout=300)
    log = process.stdout + process.stderr
    (out / 'build.log').write_bytes(log)
    if process.returncode or b'-E-' in log or not target.is_file() or not marker.is_file():
        print(log.decode('utf-8', 'replace')[-5000:])
        raise RuntimeError(f'WARP build failed: {out / "build.log"}')
    skipped = fixture / 'SkippedPatches.log'
    assert not skipped.is_file() or not skipped.read_text(encoding='utf-8-sig').strip(), 'WARP skipped patches'
    exported = json.loads(marker.read_text(encoding='utf-8'))
    assert exported['token'] == token, 'Stale build manifest'
    manifest = exported['autohunt']
    assert manifest['design'] == args.design
    assert manifest['windowSize'] == ([760, 520] if args.design == 'Custom AutoHunt UI v1' else [470, 346])
    if 'AutoSupportUI' in profile['patches']:
        support = exported['autosupport']
        assert support['design'] == args.support_design
        assert support['windowSize'] == ([760, 520] if args.support_design == 'Custom AutoSupport UI v1' else [470, 346])
    report = {'design': args.design, 'language': args.language, 'support': 'AutoSupportUI' in profile['patches'],
              'support_design': args.support_design if 'AutoSupportUI' in profile['patches'] else None,
              'source_sha256': hashlib.sha256(args.source.read_bytes()).hexdigest(),
              'target': str(target), 'target_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'live_accepted': False, 'build_passed': True}
    (out / 'build-result.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report))

if __name__ == '__main__':
    main()
