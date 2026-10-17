"""Compile the actual rainprototype ACMD body with explicit server boundaries."""
import argparse
from pathlib import Path
import subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes')
SERVER=parser.parse_args().server.resolve()
source=(SERVER/'src/map/atcommand.cpp').read_text(encoding='utf8')
start=source.index('ACMD_FUNC(rainprototype)')
end=source.index('/*==========================================\n * Clearing Weather Effects',start)
command=source[start:end]
header='''// Copyright (c) rAthena Dev Teams - Licensed under GNU GPL
// For more information, see LICENCE in the main folder
#define WORLD_ENVIRONMENT_TEST
#include "MODULE"
#include <cstdio>
using uint32 = uint32_t;
#define ACMD_FUNC(name) static int32 atcommand_##name(int32 fd, map_session_data* sd, const char*, const char* message)
#define nullpo_retr(result, pointer) do { if (!(pointer)) return result; } while (0)
#define safesnprintf std::snprintf
#define strcmpi _stricmp
static char atcmd_output[256];
static void clif_displaymessage(int32, const char*) {}
'''.replace('MODULE',(SERVER/'src/map/world_environment.cpp').as_posix())
tests='''
int main() {
    map_session_data sd;
    sd.m = 2;
    world_environment::init();
    std::strcpy(test_map.name, "prt_fild08");
    const char* invalid[] = {"", "start 0", "start 301", "start -1", "start xyz", "start 2x", "start 1 extra", "start 999999999999999"};
    for (const auto* input: invalid) {
        assert(atcommand_rainprototype(1, &sd, "rainprototype", input) == -1);
        assert(world_environment::rain_remaining() == 0);
    }
    assert(atcommand_rainprototype(1, &sd, "rainprototype", "start") == 0);
    assert(world_environment::rain_remaining() == 120000);
    assert(atcommand_rainprototype(1, &sd, "rainprototype", "status") == 0);
    assert(atcommand_rainprototype(1, &sd, "rainprototype", "stop") == 0);
    assert(world_environment::rain_remaining() == 0);
    assert(atcommand_rainprototype(1, &sd, "rainprototype", "start 300") == 0);
    assert(world_environment::rain_remaining() == 300000);
    assert(atcommand_rainprototype(1, &sd, "rainprototype", "stop") == 0);
    auto second = test_profiles.front();
    second.map = "prt_fild01";
    test_profiles.push_back(second);
    assert(world_environment::reload_profiles());
    assert(atcommand_rainprototype(1, &sd, "rainprototype", "start 120") == 0);
    sd.m = 4;
    assert(atcommand_rainprototype(1, &sd, "rainprototype", "start 60") == 0);
    assert(world_environment::rain_remaining(2) == 120000);
    assert(world_environment::rain_remaining(4) == 60000);
    assert(atcommand_rainprototype(1, &sd, "rainprototype", "stop") == 0);
    assert(world_environment::rain_remaining(2) == 120000);
    assert(world_environment::rain_remaining(4) == 0);
    sd.m = 3;
    assert(atcommand_rainprototype(1, &sd, "rainprototype", "stop") == 0);
    assert(world_environment::rain_remaining(2) == 0);
    sd.m = 2;
    std::strcpy(test_map.name, "prt_in");
    assert(atcommand_rainprototype(1, &sd, "rainprototype", "start 60") == -1);
    assert(world_environment::rain_remaining() == 0);
    std::puts("PASS: actual rainprototype command, duration grammar/bounds, default, status, stop and map restriction");
}
'''
path=ROOT/'Outputs/CelestialDial/rain-v3/rain-command-test.cpp';path.parent.mkdir(parents=True,exist_ok=True);path.write_text(header+command+tests,encoding='utf8')
subprocess.run([sys.executable,str(ROOT/'tools/test_celestial_server.py'),'--server',str(SERVER),'--test-source',str(path)],cwd=ROOT,check=True)
