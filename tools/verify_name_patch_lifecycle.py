#!/usr/bin/env python3
"""Run native WARP patch lifecycle regressions in a disposable isolated copy.

The probe uses real SetActivePatch/ClearPatch/cleanup behavior, then inspects the
exported PE. No live client or user's WARP session is controlled. --reference-ref
can reproduce the defect using committed sources without changing the checkout.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    import pefile
    output = args.output.resolve()
    fixture = output / 'warp-fixture'
    fixture.mkdir(parents=True, exist_ok=True)
    for name in ('win32', 'Scripts', 'Tables', 'Patches', 'Inputs', 'Languages', 'Styles'):
        shutil.copytree(ROOT / name, fixture / name, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__'))
    shutil.copy2(ROOT / 'Patches.yml', fixture / 'Patches.yml')
    for asset in ('AutoCombatUI', 'AutoSupportUI'):
        shutil.copytree(ROOT / 'Assets' / asset, fixture / 'Assets' / asset, dirs_exist_ok=True)
    if args.reference_ref:
        files = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only',
                                         args.reference_ref, 'Scripts'], cwd=ROOT, text=True)
        for relative in files.splitlines():
            if relative.endswith(('.qjs', '.mjs')):
                data = subprocess.check_output(['git', 'show', f'{args.reference_ref}:{relative}'], cwd=ROOT)
                (fixture / relative).write_bytes(data)
    with (fixture / 'Tables/Patch.yml').open('a', encoding='utf-8') as stream:
        stream.write('\n65000 : TestNameLifecycle\n')
    with (fixture / 'Patches/Special.yml').open('a', encoding='utf-8') as stream:
        stream.write('''
NameLifecycleProbe:
    title: Name lifecycle test
    patches:
        - TestNameLifecycle:
            title: Test name lifecycle
            recommend: no
            author: Louis T Steinhil
            desc: Isolated lifecycle regression probe.
''')
    original = pefile.PE(str(args.source), fast_load=True)
    # Explicit guarded native overwrite spans, including generated numeric tables.
    sites = {}
    modules = list((ROOT / 'Scripts/Patches').glob('*NamesStatic.qjs'))
    modules.append(ROOT / 'Scripts/Patches/ExtNamePartyStatic.qjs')
    pattern = r'[\[(]\s*(0x[\da-fA-F]{6,8}|\d{7,8})\s*,\s*"([\da-fA-F]{2}(?: [\da-fA-F]{2})+)"'
    for module in modules:
        for address, expected in re.findall(pattern, module.read_text(encoding='utf-8')):
            va, raw = int(address, 0), bytes.fromhex(expected)
            if original.get_data(va - 0x400000, len(raw)) == raw:
                sites[va] = max(sites.get(va, 0), len(raw))
    for va, length in ((0xc14866, 14), (0xc9eb37, 12), (0xcb3add, 6), (0xcb3bd8, 6)):
        sites[va] = length
    cases = []
    for mode in ('disable', 'reapply', 'failure', 'colors-first-disable', 'names-first-disable',
                 'colors-first-remove-colors', 'names-first-remove-colors', 'ui-after-disable'):
        if args.case and mode not in args.case:
            continue
        target = output / (mode + '.exe')
        marker = output / (mode + '-state.json')
        initial = ('apply("CustomPlayerNameColor"); apply("CustomExtName");'
                   if mode.startswith('colors-first') else 'apply("CustomExtName");')
        if mode.startswith('names-first'):
            initial += ' apply("CustomPlayerNameColor");'
        action = initial + ('\nremoveFeature("CustomPlayerNameColor");\n' if mode.endswith('remove-colors') else '\nremoveNames();\n')
        if mode == 'reapply':
            action += 'apply("CustomExtName"); removeNames(); apply("CustomExtName");\n'
        if mode == 'ui-after-disable':
            action += 'apply("AutoCombatUI"); apply("AutoSupportUI");\n'
        if mode == 'failure':
            action += '''
const saved = MailNamesStatic.install;
MailNamesStatic.install = function() { throw Error("lifecycle injected failure"); };
let rejected = false;
try { apply("CustomExtName"); }
catch (error) { rejected = String(error).includes("lifecycle injected failure"); }
finally { MailNamesStatic.install = saved; }
if (!rejected) throw Error("failure injection did not execute");
// Model WARP's failed-feature rollback even for the reference implementation.
Exe.SetActivePatch("CustomExtName"); Exe.ClearPatch();
Warp.SetPatchState("CustomExtName", false); Exe.ActivePatch = probeOwner;
'''
        token = uuid.uuid4().hex
        code = '''/*
 * Author(s): Louis T Steinhil
 * Description: Disposable Main 2025-07-16 real-WARP lifecycle test probe.
 */
TestNameLifecycle = function(_) {
 const probeOwner = Exe.ActivePatch;
 const apply = function(name) {
  Exe.SetActivePatch(name); Warp.SetPatchState(name, true);
  if (name === "CustomExtName") CustomExtName(name);
  else if (name === "AutoCombatUI") AutoCombatUI(name);
  else if (name === "AutoSupportUI") AutoSupportUI(name);
  else CustomPlayerNameColor(name);
  Exe.ActivePatch = probeOwner;
 };
 const removeFeature = function(name) {
  Exe.SetActivePatch(name);
  if (name === "CustomExtName" && typeof CustomExtName.cleanup === "function") CustomExtName.cleanup(name);
  if (name === "CustomPlayerNameColor" && typeof CustomPlayerNameColor.cleanup === "function") CustomPlayerNameColor.cleanup(name);
  Exe.ClearPatch(); Warp.SetPatchState(name, false); Exe.ActivePatch = probeOwner;
 };
 const removeNames = function() { removeFeature("CustomExtName"); };
''' + action + '''
 const state = CACHE.get("ExtNameTextStatic.State");
 const file = new TextFile(MARKER, "w");
 if (!file.Valid) throw Error("lifecycle marker unavailable");
 file.WriteLine(JSON.stringify({token: RUN_TOKEN, stateVir: state.stateVir, features: state.features,
  frameVir: state.bridgeVir, users: CACHE.get("ExtNameTextStatic.Users")}));
 file.Close(); Exe.ActivePatch = probeOwner; return true;
};
TestNameLifecycle.validate = function() { return true; };
NameLifecycleProbe = TestNameLifecycle;
'''
        code = code.replace('RUN_TOKEN', json.dumps(token))
        code = code.replace('MARKER', json.dumps(str(marker).replace('\\', '/')))
        (fixture / 'Scripts/Patches/NameLifecycleProbe.qjs').write_bytes(code.replace('\n', '\r\n').encode())
        profile = output / (mode + '.yml')
        profile.write_text(f'from: {json.dumps(str(args.source.resolve()))}\n'
                           f'to: {json.dumps(str(target))}\ninputs: {{}}\n'
                           'patches:\n    - TestNameLifecycle\n', encoding='utf-8')
        process = subprocess.run([str(fixture / 'win32/WARP_console.exe'), '-using', str(profile)],
                                 cwd=fixture, capture_output=True, text=True, timeout=90)
        (output / (mode + '.log')).write_text(process.stdout + process.stderr, encoding='utf-8')
        if process.returncode or not marker.is_file() or not target.is_file():
            cases.append({'case': mode, 'passed': False, 'error': 'probe did not finish', 'returncode': process.returncode})
            print('FAIL ' + mode + ': probe did not finish', flush=True)
            continue
        state = json.loads(marker.read_text())
        if state.get('token') != token:
            raise RuntimeError(f'{mode}: stale probe marker')
        pe = pefile.PE(str(target), fast_load=True)
        mismatch = [hex(va) for va, size in sites.items()
                    if pe.get_data(va - 0x400000, size) != original.get_data(va - 0x400000, size)]
        frame = pe.get_data(0xc7642d - 0x400000, 5)
        frame_stock = frame == original.get_data(0xc7642d - 0x400000, 5)
        active = mode == 'reapply' or mode.endswith('remove-colors')
        colors = 'colors' in mode or mode == 'names-first-disable'
        try:
            mask = int.from_bytes(pe.get_data(state['stateVir'] - 0x400000 + 4, 4), 'little')
        except pefile.PEFormatError:
            mask = None  # A removed owner can leave a dangling cached state.
        if active:
            bg = pe.get_data(0xb3a0e9 - 0x400000, 5)
            dest = 0xb3a0ee + int.from_bytes(bg[1:], 'little', signed=True)
            try:
                body = pe.get_data(dest - 0x400000, 5)
            except pefile.PEFormatError:
                body = b''
            valid = bg[0] == 0xe9 and body == bytes.fromhex('68 3c 01 00 00') and mask == 1 and not frame_stock
        else:
            valid = not mismatch and mask == (2 if colors else 0) and frame_stock != colors
        row = {'case': mode, 'passed': valid, 'checked_native_sites': len(sites),
               'nonstock_native_sites': mismatch, 'features': mask, 'frame_stock': frame_stock,
               'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}
        cases.append(row)
        print(('PASS ' if valid else 'FAIL ') + mode + f': native sites={len(sites)}, features={mask}, frame_stock={frame_stock}', flush=True)
    report = {'reference_ref': args.reference_ref, 'source': str(args.source.resolve()),
              'cases': cases, 'passed': all(row['passed'] for row in cases)}
    (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    return 0 if report['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--deps', type=Path)
    parser.add_argument('--reference-ref')
    parser.add_argument('--case', action='append', choices=['disable', 'reapply', 'failure', 'colors-first-disable', 'names-first-disable', 'colors-first-remove-colors', 'names-first-remove-colors', 'ui-after-disable'])
    args = parser.parse_args()
    if args.deps:
        sys.path.insert(0, str(args.deps.resolve()))
    return run(args)


if __name__ == '__main__':
    raise SystemExit(main())
