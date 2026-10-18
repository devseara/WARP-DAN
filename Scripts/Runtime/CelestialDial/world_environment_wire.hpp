// Copyright (c) rAthena Dev Teams - Licensed under GNU GPL
// For more information, see LICENCE in the main folder
// Shared WENV ABI. Client requests only subscribe; managed rain is server-owned.
#ifndef WORLD_ENVIRONMENT_WIRE_HPP
#define WORLD_ENVIRONMENT_WIRE_HPP
namespace world_environment_wire {
using u8 = unsigned char;
using u16 = unsigned short;
using i16 = short;
using u32 = unsigned int;
constexpr u16 request_id = 0x0bf8, snapshot_id = 0x0bf6, legacy_version = 1, weather_version = 2, rain_version = 3, storm_version = 4, flash_version = 5, version = 6;
constexpr u32 magic = 0x564e4557; // WENV, little-endian.
enum Flags : u16 { Scheduled = 1, NightEnabled = 2, ManagedWeather = 4 };
enum Weather : u32 { Snow = 1, Clouds = 2, Fog = 4, Petals = 8, Leaves = 16, Fireworks = 32, Ambient = 64, Rain = 128, Thunderstorm = 256, LightningFlash = 512 };
constexpr u32 server_weather_mask = Snow | Clouds | Fog | Petals | Leaves | Fireworks;
#pragma pack(push, 1)
struct Request {
    u16 id, length;
    u32 signature;
    u16 protocol, action; // action 0: subscribe or refresh; no mutation actions.
    u32 cookie, request, client_tick;
};
struct Snapshot {
    u16 id, length;
    u32 signature;
    u16 protocol, flags;
    u32 cookie, sequence, request, client_tick;
    u32 unix_low, unix_high;
    i16 utc_offset_minutes;
    u8 phase, local_night; // phase: server night_flag; local: phase && nightenabled.
    u32 duration_ms, remaining_ms, map_id;
    char map_name[16];
};
struct WeatherSnapshot { Snapshot base; u32 weather_mask; };
struct RainSnapshot { WeatherSnapshot base; u32 rain_generation, rain_remaining_ms; };
#pragma pack(pop)
static_assert(sizeof(Request) == 24 && sizeof(Snapshot) == 68, "WENV v1 wire ABI");
static_assert(sizeof(WeatherSnapshot) == 72, "WENV v2 append-only weather ABI");
static_assert(sizeof(RainSnapshot) == 80, "WENV v3-v6 bounded weather lease ABI");
}
#endif
