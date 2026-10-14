"""Parse IDUI in WARP's actual Qt engine, stopping before any game EXE export."""
from pathlib import Path
import argparse, hashlib, json, shutil, subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixture = out / 'warp-fixture'
    fixture.mkdir()
    for name in ['win32', 'Scripts', 'Tables', 'Patches', 'Inputs', 'Languages', 'Images', 'Styles']:
        if (ROOT / name).exists():
            shutil.copytree(ROOT / name, fixture / name)
    shutil.copy2(ROOT / 'Patches.yml', fixture / 'Patches.yml')
    source = (ROOT / 'Scripts/Patches/ItemDescriptionUI.qjs').read_text(encoding='utf8')
    marker = out / 'qjs-verification.json'
    # Both versions are parsed by the same Qt engine that reports GUI errors.
    # The known-bad syntax is a negative control, not evaluated in shipped code.
    probe = '''/* Isolated Qt parser probe. Never reaches patching/export. */
const source = SOURCE;
let rejected = false;
try { new Function("return ({...{value:1}});"); } catch (error) { rejected = error.name === "SyntaxError"; }
if (!rejected) throw Error("Expected legacy Qt object-spread rejection");
const ui = new Function(source + "\\nreturn ItemDescriptionNative;")();
if (!ui.Blob || !ui.Blob.exports.ItemDescriptionNativeOpen || ui.LifecycleSites.length !== 6)
    throw Error("IDUI module was not fully evaluated");
const spec = ui.LifecycleSites[0], bridge = {vir:123,size:45};
const copied = Object.assign({}, spec, {bridge:bridge});
if (copied === spec || copied.address !== spec.address || copied.fastHex !== spec.fastHex || copied.bridge !== bridge || spec.bridge)
    throw Error("Lifecycle manifest copy lost fields or mutated input");
const file = new TextFile(MARKER, "w");
if (!file.Valid) throw Error("Cannot write probe report");
file.WriteLine(JSON.stringify({passed:true,actual_warp_engine:true,object_spread_rejected:rejected,
    full_module_evaluated:true,manifest_copy_preserved:true,game_exe_created:false}));
file.Close();
throw Error("IDUI_QJS_PROBE_COMPLETE_NO_EXPORT");
'''.replace('SOURCE', json.dumps(source)).replace('MARKER', json.dumps(str(marker)))
    (fixture / 'Scripts/Init/Initializer.qjs').write_bytes(probe.replace('\n', '\r\n').encode('utf8'))
    # A directory is also an invalid export target if the intentional stop fails.
    target = out / 'no-export'
    target.mkdir()
    session = out / 'probe.yml'
    session.write_text('from: ' + json.dumps(str(args.engine.resolve())) + '\nto: ' + json.dumps(str(target)) +
                       '\ninputs: {}\npatches: []\n', encoding='utf8')
    engine_hash = hashlib.sha256(args.engine.read_bytes()).hexdigest()
    run = subprocess.run([str(fixture / 'win32/WARP_console.exe'), '-using', str(session)],
                         cwd=fixture, capture_output=True, timeout=60)
    log = run.stdout + run.stderr
    (out / 'probe.log').write_bytes(log)
    assert marker.exists() and b'IDUI_QJS_PROBE_COMPLETE_NO_EXPORT' in log, log.decode('utf8', 'replace')[-4000:]
    assert hashlib.sha256(args.engine.read_bytes()).hexdigest() == engine_hash
    assert target.is_dir() and not list(target.iterdir())
    report = json.loads(marker.read_text())
    report['source_sha256'] = hashlib.sha256((ROOT / 'Scripts/Patches/ItemDescriptionUI.qjs').read_bytes()).hexdigest()
    report['engine_sha256'] = engine_hash
    marker.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
