"""Verify server-only automatic storms using production-module and command regressions."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT.parent / 'BanquetOfHeroes'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'Outputs/CelestialDial/auto-storm')
    parser.add_argument('--server', type=Path, default=SERVER)
    args = parser.parse_args()
    server = args.server.resolve()
    output = args.output.resolve()
    logs = output / 'checks'
    logs.mkdir(parents=True, exist_ok=True)
    commands = [
        ('server-module', ['tools/test_celestial_server.py']),
        ('rain-schedule', ['tools/test_celestial_server.py', '--test-source',
                           str(server / 'tools/test_world_environment_rain_schedule.cpp')]),
        ('automatic-storm', ['tools/test_celestial_server.py', '--test-source',
                             str(server / 'tools/test_world_environment_auto_storm.cpp')]),
        ('storm-server', ['tools/test_celestial_server.py', '--test-source',
                          str(server / 'tools/test_world_environment_storm.cpp')]),
        ('profile-schedules', ['tools/test_celestial_server.py', '--test-source',
                              str(server / 'tools/test_world_environment_profiles.cpp')]),
        ('profile-parser', ['tools/test_celestial_weather_profiles.py', '--source-root', str(server),
                            '--output', str(logs / 'profile-parser')]),
        ('rain-command', ['tools/test_celestial_rain_command.py']),
        ('storm-command', ['tools/test_celestial_storm_command.py']),
        ('source-order', ['tools/verify_world_environment_source_order.py']),
        ('pincode-packetver', ['tools/test_pincode_packetver.py']),
    ]
    names = ['src/map/world_environment.cpp', 'src/map/world_environment.hpp',
             'src/common/world_environment_wire.hpp', 'tools/world_environment_test_boundary.hpp',
             'tools/test_world_environment.cpp', 'tools/test_world_environment_rain_schedule.cpp',
             'tools/test_world_environment_auto_storm.cpp', 'tools/test_world_environment_storm.cpp',
             'src/map/atcommand.cpp', 'conf/import/battle_conf.txt', 'conf/world_environment.yml',
             'conf/import/world_environment.yml', 'src/map/world_environment_profiles.cpp',
             'src/map/world_environment_profiles.hpp', 'tools/test_world_environment_profiles.cpp']
    sources = {name: sha(server / name) for name in names}
    for name, command in commands:
        if name != 'profile-parser':
            command.extend(['--server', str(server)])
        print('CHECK ' + name, flush=True)
        result = subprocess.run([sys.executable, *command], cwd=ROOT, capture_output=True)
        (logs / (name + '.log')).write_bytes(result.stdout + result.stderr)
        if result.returncode:
            raise RuntimeError(name + ':\n' + (result.stdout + result.stderr).decode(errors='replace')[-5000:])
        print('PASS ' + name, flush=True)
    config = (server / 'conf/import/battle_conf.txt').read_text()
    values = dict(line.split(':', 1) for line in config.splitlines() if ':' in line and not line.startswith('//'))
    for name, expected in [('day_duration', '3600000'), ('night_duration', '3600000')]:
        assert values[name].strip() == expected, (name, values.get(name))
    assert all(name not in values for name in ['rain_auto_enabled', 'rain_clear_duration', 'rain_duration'])
    assert all(sha(server / name) == digest for name, digest in sources.items()), 'Source changed during tests'
    report = {'passed': True, 'deployed': False, 'live_automatic_storm_accepted': False,
              'checks': [name for name, _ in commands], 'sources': sources,
              'runners': {command[0]: sha(ROOT / command[0]) for _, command in commands},
              'day_ms': 3600000, 'night_ms': 3600000, 'clear_ms': 600000, 'rain_ms': 180000,
              'automatic_sequence': ['rain', 'rain', 'storm'], 'weather_authority': 'per-map YAML profiles',
              'native_map_weather_changed': False}
    (output / 'verification.json').write_text(json.dumps(report, indent=2) + '\n')
    print('PASS: automatic-storm server checks, unchanged normal timings and wire contract', flush=True)


if __name__ == '__main__':
    main()
