"""Run isolated production WENV polls across 1000 sessions, map changes and relogs."""
import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT.parent / 'BanquetOfHeroes'

SOURCE = r'''// Copyright (c) rAthena Dev Teams - Licensed under GNU GPL
// For more information, see LICENCE in the main folder

#define WORLD_ENVIRONMENT_TEST
#include "MODULE"

#include <cstdio>

int main() {
	using namespace world_environment;
	using namespace world_environment_wire;
	std::strcpy( test_map.name, rain_prototype_map );
	init();
	auto& environment = *environment_for( 2 );
	auto& rain = environment.rain;
	battle_config.day_duration = battle_config.night_duration = 3600000;
	weather_flags[MF_SNOW] = weather_flags[MF_FOG] = 1;
	std::vector<map_session_data> sessions( 1000 );
	Request request = { request_id, sizeof( Request ), magic, version, 0, 1, 1, 1000 };
	for( size_t i = 0; i < sessions.size(); ++i ) {
		auto& sd = sessions[i];
		sd.m = i % 4 ? 2 : 3;
		request.cookie = static_cast<u32>( i + 1 );
		assert( process( &sd, request ) );
		players.push_back( &sd );
	}
	assert( start_storm( 2, 300000 ) );
	size_t peak_snapshots = 0, peak_audio = 0;
	for( int second = 0; second < 180; ++second ) {
		test_tick += 1000;
		if( second == 30 ) {
			for( auto& sd : sessions )
				sd.m = sd.m == 2 ? 3 : 2;
		}
		if( second == 60 ) {
			// Fresh map_session_data must not inherit a previous connection's subscription.
			for( size_t i = 0; i < sessions.size(); i += 5 ) {
				auto& sd = sessions[i];
				sd = map_session_data{};
				assert( !sd.world_environment.cookie && !sd.world_environment.sequence );
				sd.m = i % 4 ? 2 : 3;
				request.cookie = 100000 + static_cast<u32>( i );
				assert( process( &sd, request ) );
			}
		}
		if( second == 90 ) {
			for( size_t i = 0; i < sessions.size(); ++i ) {
				if( i % 4 == 0 )
					sessions[i].fd = 0;
				else if( i % 4 == 1 )
					sessions[i].state.active = false;
				else if( i % 4 == 2 )
					sessions[i].state.pc_loaded = false;
			}
		}
		const auto packets = sent.size(), sounds = thunder_sounds.size();
		poll( 77, test_tick, 0, 0 );
		const size_t snapshots = sent.size() - packets, audio = thunder_sounds.size() - sounds;
		assert( snapshots <= sessions.size() );
		if( snapshots > peak_snapshots )
			peak_snapshots = snapshots;
		if( audio > peak_audio )
			peak_audio = audio;
		size_t expected_audio = 0;
		for( const auto& sd : sessions ) {
			if( ready( &sd ) && sd.m == 2 )
				++expected_audio;
		}
		assert( audio == ( rain.thunder_due ? expected_audio : 0 ) );
		for( size_t i = sounds; i < thunder_sounds.size(); ++i )
			assert( ready( thunder_sounds[i] ) && thunder_sounds[i]->m == 2 );
		for( size_t i = packets; i < sent.size(); ++i ) {
			const auto& packet = sent[i];
			assert( packet.length == 80 && ( sent_weather[i] & ( Snow | Fog ) ) == ( Snow | Fog ) );
			assert( bool( sent_weather[i] & Thunderstorm ) == ( packet.map_id == 2 ) );
			assert( bool( sent_rain_remaining[i] ) == ( packet.map_id == 2 ) );
		}
	}
	stop_storm();
	const auto before = sent.size(), sounds = thunder_sounds.size();
	poll( 77, ++test_tick, 0, 0 );
	for( size_t i = before; i < sent.size(); ++i )
		assert( sent_weather[i] == ( Snow | Fog ) && !sent_rain_remaining[i] );
	assert( thunder_sounds.size() == sounds && !rain.next_audio && !rain.flash );
	assert( battle_config.day_duration == 3600000 && battle_config.night_duration == 3600000 );
	assert( environment.profile.clear_ms == 600000 && environment.profile.rain_ms == 180000 );
	assert( weather_flags[MF_SNOW] && weather_flags[MF_FOG] );
	shutdown();
	std::printf( "PASS: 1000 sessions, 180 production polls, 1000 map transitions, 200 relogs; "
		"peak snapshots per poll=%zu, peak map-local audio recipients=%zu; "
		"disconnected/loading/inactive sessions skipped, native weather and normal durations preserved\n",
		peak_snapshots, peak_audio );
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--server', type=Path, default=SERVER)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    source = args.output.resolve() / 'weather-server-load.cpp'
    source.write_text(SOURCE.replace('MODULE', (args.server.resolve() / 'src/map/world_environment.cpp').as_posix()))
    subprocess.run([sys.executable, str(ROOT / 'tools/test_celestial_server.py'), '--server', str(args.server), '--test-source', str(source)], check=True)


if __name__ == '__main__':
    main()
