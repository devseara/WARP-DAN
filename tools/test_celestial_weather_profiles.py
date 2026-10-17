"""Compile the real weather-profile loader with rAthena's real RapidYAML/database parser."""
import argparse
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT.parent / 'BanquetOfHeroes'

HARNESS = r'''// Copyright (c) rAthena Dev Teams - Licensed under GNU GPL
// For more information, see LICENCE in the main folder

#include "PROFILE_HEADER"

#include <algorithm>
#include <cassert>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <string>
#include <vector>

#include <common/database.hpp>
#include <common/malloc.hpp>
#include <common/showmsg.hpp>

// These are allocation/logging boundaries only. Parsing and imports run production code.
char db_path[12] = "db";
void* _mmalloc( size_t size, const char*, int32, const char* ) { return std::malloc( size ); }
void _mfree( void* pointer, const char*, int32, const char* ) { std::free( pointer ); }
void ShowMessage( const char*, ... ) {}
void ShowStatus( const char*, ... ) {}
void ShowWarning( const char*, ... ) {}
void ShowError( const char*, ... ) {}
int32 _vShowMessage( enum msg_type, const char*, va_list ) { return 0; }

int main( int argc, char** argv ) {
	assert( argc == 4 );
	const bool showcase = std::strcmp( argv[3], "showcase" ) == 0;
	do_init_database();
	using namespace world_environment;
	std::vector<s_weather_profile> profiles;
	assert( load_weather_profiles( profiles, argv[1] ) && !profiles.empty() );
	const auto accepted = profiles;
	std::vector<s_weather_profile> default_profiles;
	assert( load_weather_profiles( default_profiles ) && !default_profiles.empty() );
	const auto prototype = std::find_if( profiles.begin(), profiles.end(), []( const auto& entry ) { return entry.map == "prt_fild08"; } );
	assert( prototype != profiles.end() );
	const auto& profile = *prototype;
	assert( profile.map == "prt_fild08" && profile.enabled && profile.automatic && profile.outdoor );
	assert( profile.rain && profile.thunderstorm && profile.storm_every == 3 );
	assert( profile.clear_ms == ( showcase ? 30000u : 600000u ) );
	assert( profile.rain_ms == ( showcase ? 30000u : 180000u ) && profile.storm_ms == ( showcase ? 30000u : 180000u ) );
	const std::string file = std::string( argv[2] ) + "/case.yml";
	const auto check = [&]( const std::string& yaml, bool valid ) {
		std::ofstream stream( file );
		stream << yaml;
		stream.close();
		assert( load_weather_profiles( profiles, file ) == valid );
		if( !valid )
			assert( profiles == accepted );
	};
	const std::string header = "Header:\n  Type: WORLD_ENVIRONMENT_DB\n  Version: 1\n";
	for( const auto& body : {
		"Body: null\n",
		"Body:\n  - Map: prt_fild08\n    NightLighting: []\n",
		"Body:\n  - Map: prt_fild08\n    NightLighting: invalid\n",
		"Body: {}\n",
		"Body:\n  - Map: PRT_FILD08\n",
		"Body:\n  - Map: prt_fild08\n    Enabled: true\n    Outdoor: false\n",
		"Body:\n  - Map: prt_fild08\n    Outdoor: {}\n",
		"Body:\n  - Map: prt_fild08\n    ClearDuration: -1\n",
		"Body:\n  - Map: prt_fild08\n    ClearDuration: 29999\n",
		"Body:\n  - Map: prt_fild08\n    RainDuration: 300001\n",
		"Body:\n  - Map: prt_fild08\n    StormDuration: 0\n",
		"Body:\n  - Map: prt_fild08\n    StormEvery: 1000001\n",
		"Body:\n  - Map: prt_fild08\n    CleerDuration: 60000\n",
		"Body:\n  - Map: prt_fild08\n    Weather: []\n",
		"Body:\n  - Map: prt_fild08\n    Weather:\n      Rain: false\n      Thunderstorm: true\n",
		"Body:\n  - Map: prt_fild08\n    Weather:\n      Snow: true\n",
		"Body:\n  - Map: prt_fild08\n    Weather:\n      Rain: {}\n",
		"Body:\n  - Map: [\n"
	} ) {
		profiles = accepted;
		check( header + body, false );
	}
	check( "Header:\n  Type: OTHER_DB\n  Version: 1\nBody: []\n", false );
	const std::string imported = std::string( argv[2] ) + "/override.yml";
	{
		std::ofstream stream( imported );
		stream << header << "Body:\n  - Map: prt_fild08\n    RainDuration: 60000\n    StormEvery: 2\n    NightLighting: false\n";
	}
	check( header + "Body:\n  - Map: prt_fild08\n    Enabled: true\n    Outdoor: true\n    Automatic: true\n    NightLighting: true\n"
		"    Weather:\n      Rain: true\n      Thunderstorm: true\n"
		"Footer:\n  Imports:\n    - Path: '" + imported + "'\n", true );
	assert( profiles.size() == 1 && profiles.front().enabled && profiles.front().outdoor );
	assert( profiles.front().rain_ms == 60000 && profiles.front().storm_every == 2 && profiles.front().thunderstorm );
	assert( profiles.front().night_lighting.has_value() && !*profiles.front().night_lighting );
	profiles = accepted;
	check( header + "Body: []\nFooter:\n  Imports:\n    - Path: 'missing-weather-profile-test.yml'\n", false );
	check( header + "Body: []\n", true );
	assert( profiles.empty() );
	check( header + "Body:\n  - Map: prt_fild01\n    Enabled: false\n    ClearDuration: 120000\n"
		"  - Map: prt_fild08\n    Enabled: true\n    Outdoor: true\n    RainDuration: 60000\n"
		"    Weather:\n      Rain: true\n      Thunderstorm: false\n", true );
	assert( profiles.size() == 2 && !profiles[0].enabled && profiles[1].rain_ms == 60000 );
	// Exercise the production default location through db_path, with no explicit path.
	std::filesystem::current_path( argv[2] );
	std::filesystem::create_directory( "wenv_db" );
	{
		std::ofstream stream( "wenv_db/world_environment.yml" );
		stream << header << "Body: []\n";
	}
	std::strcpy( db_path, "wenv_db" );
	assert( load_weather_profiles( profiles ) && profiles.empty() );
	std::strcpy( db_path, "missing" );
	assert( !load_weather_profiles( profiles ) && profiles.empty() );
	std::puts( "PASS: real RapidYAML profiles, strict keys/types/bounds, weather rules, imports, transactional failure, defaults and db_path resolution" );
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, default=SERVER)
    parser.add_argument('--output', type=Path, default=ROOT / 'Outputs/CelestialDial/profiles-v6/parser-test')
    parser.add_argument('--config', type=Path, help='Explicit profile fixture (otherwise the server configuration)')
    parser.add_argument('--expect-showcase', action='store_true', help='Validate the temporary 30-second prototype override')
    args = parser.parse_args()
    source_root = args.source_root.resolve()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    vs = Path('C:/Program Files/Microsoft Visual Studio/18/Community')
    version = (vs / 'VC/Auxiliary/Build/Microsoft.VCToolsVersion.default.txt').read_text().strip()
    vc = vs / 'VC/Tools/MSVC' / version
    sdk = Path(os.environ['ProgramFiles(x86)']) / 'Windows Kits/10'
    sdk_version = sorted(path.name for path in (sdk / 'Lib').iterdir() if path.is_dir())[-1]
    env = os.environ.copy()
    env['INCLUDE'] = ';'.join(str(path) for path in [SERVER / 'src', SERVER / '3rdparty/rapidyaml/src',
        SERVER / '3rdparty/rapidyaml/ext/c4core/src', SERVER / '3rdparty/libconfig', vc / 'include',
        sdk / 'Include' / sdk_version / 'ucrt', sdk / 'Include' / sdk_version / 'um', sdk / 'Include' / sdk_version / 'shared'])
    env['LIB'] = ';'.join(str(path) for path in [vc / 'lib/x64', sdk / 'Lib' / sdk_version / 'ucrt/x64',
                                               sdk / 'Lib' / sdk_version / 'um/x64'])
    harness = out / 'profiles-test.cpp'
    harness.write_text(HARNESS.replace('PROFILE_HEADER', (source_root / 'src/map/world_environment_profiles.hpp').as_posix()))
    sources = [harness, source_root / 'src/map/world_environment_profiles.cpp', SERVER / 'src/common/database.cpp']
    objects = []
    compiler = vc / 'bin/Hostx64/x64/cl.exe'
    for index, source in enumerate(sources):
        obj = out / f'{index}.obj'
        flags = ['/W4', '/WX'] if index < 2 else ['/W3', '/wd4100']
        subprocess.run([str(compiler), '/nologo', '/c', '/std:c++17', '/EHsc', '/MT', '/utf-8',
                        '/D_CRT_SECURE_NO_WARNINGS=', *flags, '/Fo' + str(obj), str(source)], env=env, check=True)
        objects.append(obj)
    exe = out / 'profiles-test.exe'
    subprocess.run([str(compiler), '/nologo', '/MT', *map(str, objects), str(SERVER / '.vs/build/ryml.lib'),
                    '/Fe' + str(exe)], env=env, check=True)
    subprocess.run([str(exe), str(args.config.resolve() if args.config else source_root / 'db/world_environment.yml'), out.as_posix(),
                    'showcase' if args.expect_showcase else 'normal'],
                   cwd=source_root, check=True)


if __name__ == '__main__':
    main()
