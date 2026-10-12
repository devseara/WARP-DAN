"""Build Bestiary with real WARP in a fresh isolated fixture (no client launch).

The output includes a token-checked manifest of emitted native entry points.
The existing user profiles, source EXE, and installed game are never modified.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
PROBE = '''/* Bestiary isolated export manifest. */
BestiaryBuildProbe = function(_) {
	const probeOwner = Exe.ActivePatch;
	const previous = CACHE.get("BestiaryUI.Native.v1");
	LIFECYCLE
	const file = new TextFile(MARKER, "w");
	if (!file.Valid) throw Error("Cannot write Bestiary build manifest");
	file.WriteLine(JSON.stringify({token: TOKEN, bestiary: CACHE.get("BestiaryUI.Native.v1"), previousToggle: previous.toggle.vir, previousReceiver: previous.receiver ? previous.receiver.vir : 0, sharedRoute: CACHE.get("SharedPacket0BEF.Router.v4"), extensions: CACHE.get("SharedPacket0BEF.Extensions.v1"), commands: CACHE.get("CustomSlashCommand.RegistryByOwner")}));
	file.Close(); return true;
};
BestiaryBuildProbe.validate = function() { return true; };
'''


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, required=True)
    ap.add_argument('--profile', type=Path, help='Read existing inputs/patches into an isolated copy; never modify it')
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--lifecycle', choices=['reapply', 'remove'], help='Exercise native patch removal or reapplication inside WARP')
    ap.add_argument('--coexist', choices=['before', 'after'], help='Build beside Item Collection, Auto Hunt, AutoSupport and PIN')
    args = ap.parse_args()
    source, output = args.source.resolve(), args.output.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    output.mkdir(parents=True, exist_ok=False)
    fixture = output / 'warp-fixture'
    fixture.mkdir()
    (fixture / 'Outputs').mkdir()
    for name in ('win32', 'Scripts', 'Tables', 'Patches', 'Inputs', 'Languages', 'Styles', 'Assets'):
        shutil.copytree(ROOT / name, fixture / name, ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT / 'Patches.yml', fixture / 'Patches.yml')
    # Only these existing chrome files are needed by the native preview.
    chrome = fixture / 'Images/CollectionUI/chrome'
    chrome.mkdir(parents=True)
    shutil.copy2(ROOT / 'Images/CollectionUI/chrome/title_bar_760.bmp', chrome)
    shutil.copytree(ROOT / 'Images/BestiaryUI', fixture / 'Images/BestiaryUI')
    if args.coexist or args.profile:
        shutil.copytree(ROOT / 'Images', fixture / 'Images', dirs_exist_ok=True)
    with (fixture / 'Tables/Patch.yml').open('a', encoding='utf-8') as f:
        f.write('\n65002 : BestiaryBuildProbe\n')
    with (fixture / 'Patches/UI.yml').open('a', encoding='utf-8') as f:
        f.write('\nBestiaryBuildProbeGroup:\n    title: Bestiary build probe\n    patches:\n'
                '        - BestiaryBuildProbe:\n            title: Bestiary export probe\n'
                '            recommend: no\n            author: WARP diagnostics\n'
                '            desc: Isolated export manifest.\n')
    target, marker = output / 'bestiary-preview.exe', output / 'native-manifest.json'
    token = uuid.uuid4().hex
    probe = PROBE.replace('MARKER', json.dumps(marker.as_posix())).replace('TOKEN', json.dumps(token))
    action = ''
    if args.lifecycle:
        action = ('Exe.SetActivePatch("BestiaryUI"); BestiaryUI.cleanup("BestiaryUI"); '
                  'Exe.ClearPatch(); Warp.SetPatchState("BestiaryUI", false); ')
        if args.lifecycle == 'reapply':
            action += ('Exe.SetActivePatch("BestiaryUI"); Warp.SetPatchState("BestiaryUI", true); '
                       'BestiaryUI("BestiaryUI"); ')
        action += 'Exe.ActivePatch = probeOwner;'
    probe = probe.replace('LIFECYCLE', action)
    (fixture / 'Scripts/Patches/BestiaryBuildProbe.qjs').write_bytes(probe.replace('\n', '\r\n').encode())
    profile = output / 'bestiary-preview.yml'
    patches = ['BestiaryUI']
    if args.coexist:
        peers = ['InGamePincodeUI', 'AutoCombatUI', 'AutoSupportUI', 'ItemCollectionUI']
        patches = patches + peers if args.coexist == 'before' else peers + patches
    patches += ['BestiaryBuildProbe']
    profile.write_text('from: ' + json.dumps(str(source)) + '\nto: ' + json.dumps(str(target)) +
                       '\ninputs: {}\npatches:\n' + ''.join('    - ' + p + '\n' for p in patches), encoding='utf-8')
    if args.profile:
        if args.coexist:
            raise ValueError('--profile and --coexist are mutually exclusive')
        saved = args.profile.read_text(encoding='utf-8-sig')
        for key, value in [('from', str(source)), ('to', str(target))]:
            saved, count = re.subn(r'^' + key + r':[^\n]*', lambda m: key + ': ' + json.dumps(value), saved, flags=re.M)
            if count != 1:
                raise ValueError('Expected exactly one profile ' + key + ' field')
        if len(re.findall(r'^patches:', saved, re.M)) != 1:
            raise ValueError('Expected one patch list')
        # Current WARP saved profiles end with the patches list. Do not append
        # into an unrelated YAML key if a different format is supplied.
        if re.search(r'^\S', saved.split('\npatches:', 1)[1], re.M):
            raise ValueError('Expected patches as the final profile key')
        saved = re.sub(r'^ +-[ ]+(BestiaryUI|BestiaryBuildProbe)[ ]*$', '', saved, flags=re.M)
        profile.write_text(saved.rstrip() + '\n    - BestiaryUI\n    - BestiaryBuildProbe\n', encoding='utf-8')
    run = subprocess.run([str(fixture / 'win32/WARP_console.exe'), '-using', str(profile)],
                         cwd=fixture, capture_output=True, timeout=180)
    (output / 'build.log').write_bytes(run.stdout + run.stderr)
    if run.returncode != 0 or b"-E-" in run.stdout + run.stderr or not target.is_file() or not marker.is_file():
        raise RuntimeError(f'WARP build failed ({run.returncode}); see {output / "build.log"}')
    state = json.loads(marker.read_text(encoding='utf-8'))
    if state['token'] != token:
        raise RuntimeError('Stale export manifest')
    if args.lifecycle != 'remove' and not state.get('bestiary'):
        raise RuntimeError('Bestiary native entry points missing')
    report = {'source': str(source), 'source_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
              'target': str(target), 'target_sha256': hashlib.sha256(target.read_bytes()).hexdigest(),
              'build_passed': True, 'live_accepted': False, 'lifecycle': args.lifecycle}
    (output / 'build-result.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
