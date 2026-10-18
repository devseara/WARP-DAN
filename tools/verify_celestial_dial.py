"""Run the bounded client/server acceptance checks and save a reproducible receipt."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'Outputs/CelestialDial'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,default=OUT/'rain-v3')
    ap.add_argument('--clients',default='clients-final')
    ap.add_argument('--candidate',default='existing-client-final/release/2025-07-16_Ragexe_175220998_clientinfo_patched.exe')
    ap.add_argument('--upgrade-receipt',type=Path)
    ap.add_argument('--baseline',type=Path)
    ap.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes')
    ap.add_argument('--runtime-source',type=Path,default=ROOT/'Scripts/Runtime/CelestialDial')
    ap.add_argument('--runtime-inputs',type=Path,default=ROOT/'Inputs/CelestialDial')
    ap.add_argument('--reuse-native-logs',action='store_true',help='Use successful native execution logs from this exact candidate and fixtures')
    args=ap.parse_args();out=args.output.resolve();server=args.server.resolve()
    checks=[];logs=out/'checks';logs.mkdir(parents=True,exist_ok=True)
    candidate=out/args.candidate
    commands=[
        ('generated-monster-source',['tools/build_target_monster_health_bar.py','--check']),
        ('server-module',['tools/test_celestial_server.py']),
        ('rain-command',['tools/test_celestial_rain_command.py']),
        ('rain-schedule',['tools/test_celestial_server.py','--test-source',str(ROOT.parent/'BanquetOfHeroes/tools/test_world_environment_rain_schedule.cpp')]),
        ('automatic-storm',['tools/test_celestial_server.py','--test-source',str(ROOT.parent/'BanquetOfHeroes/tools/test_world_environment_auto_storm.cpp')]),
        ('storm-server',['tools/test_celestial_server.py','--test-source',str(ROOT.parent/'BanquetOfHeroes/tools/test_world_environment_storm.cpp')]),
        ('storm-command',['tools/test_celestial_storm_command.py']),
        ('source-order',['tools/verify_world_environment_source_order.py']),
        ('pincode-packetver',['tools/test_pincode_packetver.py']),
        ('weather-lifecycle',['tools/test_celestial_weather_lifecycle.py',str(candidate),'--output',str(logs/'weather-lifecycle.json')]),
        ('server-session-load',['tools/test_celestial_weather_server_load.py','--output',str(logs/'server-session-load')]),
        ('weather-profiles',['tools/test_celestial_weather_profiles.py','--source-root',str(server),'--output',str(logs/'profiles-parser')]),
        ('profile-schedules',['tools/test_celestial_server.py','--test-source',str(server/'tools/test_world_environment_profiles.cpp')]),
        ('profile-client',['tools/test_celestial_weather_profile_client.py',str(candidate)]),
        ('native-client-fixtures',['tools/test_celestial_dial.py',*[str(out/args.clients/(name+'.exe')) for name in ['standalone','monster-first','dial-first','framed-peers','framed-reverse']]]),
        ('installed-client-candidate',['tools/test_celestial_dial.py',str(candidate)]),
    ]
    for name,path in [('candidate',candidate)]+[(name,out/args.clients/(name+'.exe')) for name in ['standalone','monster-first','dial-first','framed-peers','framed-reverse']]:
        commands.append(('storm-lighting-'+name,['tools/test_celestial_storm.py',str(path)]))
        commands.append(('sun-shadow-'+name,['tools/test_celestial_sun_shadow.py',str(path),'--runtime-meta',str(args.runtime_inputs/'runtime.json')]))
    for name in ['framed-peers','framed-reverse']:
        commands.append((name,['tools/test_packet_0bf6_route.py',str(out/args.clients/(name+'.exe')),'--expect','bpui,gcha','--with-wenv']))
    for name in ['monster-first','dial-first']:
        commands.append((name,['tools/verify_target_monster_health_bar.py',str(out/args.clients/(name+'.exe')),
            '--assets-root',str(out/args.clients/'fixture'),'--report',str(logs/(name+'.json'))]))
    for name,command in commands:
        if command[0] in ['tools/test_celestial_server.py','tools/test_celestial_rain_command.py','tools/test_celestial_storm_command.py',
                          'tools/test_celestial_weather_server_load.py','tools/verify_world_environment_source_order.py','tools/test_pincode_packetver.py']:
            command.extend(['--server',str(server)])
            command[:]=[value.replace(str(ROOT.parent/'BanquetOfHeroes'),str(server)) for value in command]
        print('CHECK '+name,flush=True)
        if args.reuse_native_logs and name in ('native-client-fixtures','installed-client-candidate'):
            # Hash-bound receipts are written by the caller only after exit code 0.
            receipt=json.loads((logs/(name+'.json')).read_text())
            assert receipt['passed'] and receipt['test_sha256']==hashlib.sha256((ROOT/'tools/test_celestial_dial.py').read_bytes()).hexdigest()
            for file,digest in receipt['clients'].items():assert hashlib.sha256(Path(file).read_bytes()).hexdigest()==digest
            assert set(receipt['clients'])==set(command[1:])
            checks.append(name);print('PASS '+name+' (verified execution receipt)',flush=True);continue
        run=subprocess.run([sys.executable,*command],cwd=ROOT,capture_output=True)
        (logs/(name+'.log')).write_bytes(run.stdout+run.stderr)
        if run.returncode:
            raise RuntimeError(name+' failed:\n'+(run.stdout+run.stderr).decode(errors='replace')[-4000:])
        checks.append(name);print('PASS '+name,flush=True)
    for name in ['CelestialDial','AutoCombatUI','TargetMonsterHealthBar']:
        b=(ROOT/'Scripts/Patches'/(name+'.qjs')).read_bytes()
        assert b.startswith(b'/*') and b.count(b'\n')==b.count(b'\r\n') and not b.startswith(b'\xef\xbb\xbf')
    meta=json.loads((args.runtime_inputs/'runtime.json').read_text())
    source=args.runtime_source/'runtime.cpp'
    wire=source.with_name('world_environment_wire.hpp')
    assert meta['source_sha256']==hashlib.sha256(source.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    assert meta['wire_sha256']==hashlib.sha256(wire.read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    assert meta['ground_sha256']==hashlib.sha256(source.with_name('rain_ground.inl').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    assert meta['weather_art_sha256']==hashlib.sha256(source.with_name('weather_art.inl').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    assert meta['sun_shadow_sha256']==hashlib.sha256(source.with_name('sun_shadow.inl').read_bytes().replace(b'\r\n',b'\n')).hexdigest()
    assert meta['payload_sha256']==hashlib.sha256((args.runtime_inputs/'runtime.bin').read_bytes()).hexdigest()
    assert wire.read_bytes()==(server/'src/common/world_environment_wire.hpp').read_bytes()
    build=json.loads((out/'server-build/build-result.json').read_text());assert build['passed']
    for name,digest in build['sources'].items():assert hashlib.sha256((server/name).read_bytes()).hexdigest()==digest
    for target in build['targets']:assert hashlib.sha256(Path(target['path']).read_bytes()).hexdigest()==target['sha256']
    if args.upgrade_receipt:
        preservation=json.loads(args.upgrade_receipt.read_text())
        assert preservation['unrelated_bytes_preserved'] and (preservation['size_preserved'] or preservation.get('owned_section_migration'))
        assert hashlib.sha256(candidate.read_bytes()).hexdigest()==preservation['sha256']
        assert args.baseline and hashlib.sha256(args.baseline.read_bytes()).hexdigest()==preservation['source_sha256']
    else:
        preservation=json.loads((candidate.parent.parent/'preservation.json').read_text())
        assert hashlib.sha256(candidate.read_bytes()).hexdigest()==preservation['candidate_sha256']
        assert hashlib.sha256(Path(preservation['source']).read_bytes()).hexdigest()==preservation['source_sha256'],'installed client changed during verification'
    report={'passed':True,'checks':checks,'source_and_wire_checks':True,'server_build':build,
            'preservation':preservation,'live_visual_accepted':False,'deployed':False}
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS: complete offline Celestial dial checks; no client/server deployment or live screenshot acceptance',flush=True)

if __name__=='__main__':main()
