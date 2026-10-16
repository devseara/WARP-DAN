"""Build an isolated GrayMap fixture with real WARP; never launch the client."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import uuid

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / '2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source', type=Path, default=SOURCE)
    ap.add_argument('--output', type=Path, required=True)
    ap.add_argument('--lifecycle', choices=['remove', 'reapply'])
    ap.add_argument('--peers', choices=['before', 'after'])
    args = ap.parse_args()
    out, source = args.output.resolve(), args.source.resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = out / 'warp-fixture'
    fixture.mkdir()
    for name in ('win32', 'Scripts', 'Tables', 'Patches', 'Languages', 'Styles'):
        shutil.copytree(ROOT / name, fixture / name)
    (fixture / 'Inputs').mkdir()
    shutil.copytree(ROOT / 'Assets/GrayMap', fixture / 'Assets/GrayMap')
    shutil.copy2(ROOT / 'Patches.yml', fixture / 'Patches.yml')
    with (fixture / 'Tables/Patch.yml').open('a', encoding='utf-8') as f:
        f.write('\n65003 : GrayMapBuildProbe\n')
    with (fixture / 'Patches/Data.yml').open('a', encoding='utf-8') as f:
        f.write('\nGrayMapProbeGroup:\n    title: GrayMap probe\n    patches:\n'
                '        - GrayMapBuildProbe:\n            title: GrayMap export probe\n'
                '            recommend: no\n            author: WARP diagnostics\n'
                '            desc: Isolated build and lifecycle diagnostics.\n')
    marker, target, token = out / 'manifest.json', out / 'graymap.exe', uuid.uuid4().hex
    lifecycle = ''
    if args.lifecycle:
        lifecycle = ('Exe.SetActivePatch("GrayMap"); GrayMap.cleanup("GrayMap"); '
                     'Exe.ClearPatch(); Warp.SetPatchState("GrayMap", false); ')
        if args.lifecycle == 'reapply':
            lifecycle += ('Exe.SetActivePatch("GrayMap"); Warp.SetPatchState("GrayMap", true); '
                          'GrayMap("GrayMap"); ')
    probe = '''/* Isolated GrayMap manifest. */
GrayMapBuildProbe = function(_) {
    const owner = Exe.ActivePatch;
    const previous = CACHE.get("GrayMap.Native.v1") ?? null;
    LIFECYCLE
    Exe.ActivePatch = owner;
    const f = new TextFile(MARKER, "w");
    if (!f.Valid) throw Error("GrayMap manifest cannot be opened");
    f.WriteLine(JSON.stringify({token: TOKEN, graymap: CACHE.get("GrayMap.Native.v1") ?? null,
        previous, commands: CACHE.get("CustomSlashCommand.RegistryByOwner") ?? {}}));
    f.Close();
    return true;
};
'''.replace('LIFECYCLE', lifecycle).replace('MARKER', json.dumps(marker.as_posix())).replace('TOKEN', json.dumps(token))
    (fixture / 'Scripts/Patches/GrayMapBuildProbe.qjs').write_bytes(probe.replace('\n', '\r\n').encode())
    patches = ['GrayMap']
    if args.peers:
        peers = ['FpsOverlay', 'IncrMapQuality']
        patches = peers + patches if args.peers == 'before' else patches + peers
    patches += ['GrayMapBuildProbe']
    profile = out / 'build.yml'
    profile.write_text('from: ' + json.dumps(source.as_posix()) + '\nto: ' + json.dumps(target.as_posix()) +
                       '\ninputs: {}\npatches:\n' + ''.join('    - ' + p + '\n' for p in patches), encoding='utf-8')
    run = subprocess.run([str(fixture / 'win32/WARP_console.exe'), '-using', str(profile)],
                         cwd=fixture, capture_output=True, timeout=180)
    (out / 'build.log').write_bytes(run.stdout + run.stderr)
    if run.returncode or b'-E-' in run.stdout + run.stderr or not target.is_file() or not marker.is_file():
        raise RuntimeError(f'WARP build failed ({run.returncode}); see {out / "build.log"}')
    manifest = json.loads(marker.read_text())
    if manifest['token'] != token:
        raise RuntimeError('Stale manifest')
    if args.lifecycle != 'remove' and not manifest['graymap']:
        raise RuntimeError('GrayMap was not installed; unsupported source or failed preflight')
    if args.lifecycle == 'remove' and manifest['graymap'] is not None:
        raise RuntimeError('GrayMap removal left active state')
    report = dict(source=str(source), source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                  target=str(target), target_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
                  lifecycle=args.lifecycle, peers=args.peers, build_passed=True, live_accepted=False)
    (out / 'build-result.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
