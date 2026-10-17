"""Compile PIN-header inclusion orders with warnings as errors and exact packet-family assertions."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--server',type=Path,default=ROOT.parent/'BanquetOfHeroes')
SERVER=parser.parse_args().server.resolve()
OUT=ROOT/'Outputs/CelestialDial/pincode-header-test'
OUT.mkdir(parents=True,exist_ok=True)
assertions='''
static_assert( PACKETVER == 20250716, "Custom packet version must be loaded first" );
static_assert( PACKETVER_MAIN_NUM == 20250716, "Main family must match the configured client" );
#ifdef PACKETVER_RE_NUM
#error Unexpected renewal packet-family residue from the stock default
#endif
#if !PACKETVER_SUPPORTS_PINCODE
#error PIN feature macros must use the configured client version
#endif
int main() { return 0; }
'''
header='// Copyright (c) rAthena Dev Teams - Licensed under GNU GPL\n// For more information, see LICENCE in the main folder\n'
pin=f'#include "{(SERVER/"src/map/pincode_ui.hpp").as_posix()}"\n'
core='#include <config/core.hpp>\n'
for name,includes in [('pin-first',pin+core),('core-first',core+pin)]:
    source=OUT/(name+'.cpp');source.write_text(header+includes+assertions)
    result=subprocess.run([sys.executable,str(ROOT/'tools/test_celestial_server.py'),
        '--server',str(SERVER),'--include-server-headers','--test-source',str(source)],cwd=ROOT,capture_output=True)
    (OUT/(name+'.log')).write_bytes(result.stdout+result.stderr)
    assert result.returncode==0,(result.stdout+result.stderr).decode(errors='replace')
    assert b'C4005' not in result.stdout+result.stderr
print('PASS: PIN/core inclusion orders, PACKETVER 20250716, main-client family, PIN features and no macro redefinition')
