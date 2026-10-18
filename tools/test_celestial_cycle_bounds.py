"""Execute the actual native battle_config duration clamps with showcase/normal values."""
import argparse
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--server', type=Path, default=ROOT.parent / 'BanquetOfHeroes')
    args = parser.parse_args()
    text = (args.server / 'src/map/battle.cpp').read_text(encoding='utf8')
    clamps = []
    for name in ['day_duration', 'night_duration']:
        pattern = rf'if \(battle_config\.{name} && battle_config\.{name} < \d+\)\s+battle_config\.{name} = \d+;'
        matches = re.findall(pattern, text)
        assert len(matches) == 1, (name, 'Missing or ambiguous production clamp')
        clamps.append(matches[0])
    source = '''// Copyright (c) rAthena Dev Teams - Licensed under GNU GPL
// For more information, see LICENCE in the main folder
#include <cassert>
#include <cstdio>
static struct { int day_duration = 0, night_duration = 0; } battle_config;
static void adjust() {
CLAMPS
}
int main() {
    constexpr int cases[][2] = {{0,0},{1,30000},{29999,30000},{30000,30000},{60000,60000},{3600000,3600000}};
    for( const auto& test : cases ) {
        battle_config.day_duration = battle_config.night_duration = test[0];
        adjust();
        assert( battle_config.day_duration == test[1] && battle_config.night_duration == test[1] );
    }
    std::puts("PASS: actual day/night clamps retain disabled/normal timings and permit 30-second showcase phases");
}
'''.replace('CLAMPS', '\n'.join(clamps))
    output = ROOT / 'Outputs/CelestialDial/cycle-bounds'
    output.mkdir(parents=True, exist_ok=True)
    path = output / 'cycle-bounds.cpp'
    path.write_text(source, encoding='utf8')
    subprocess.run([sys.executable, str(ROOT / 'tools/test_celestial_server.py'), '--server', str(args.server),
                    '--test-source', str(path)], check=True)


if __name__ == '__main__':
    main()
