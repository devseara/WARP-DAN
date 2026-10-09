// DRUI v1 prefix and negotiated v2 attendance bundle extension.
#pragma once
namespace daily_rewards_wire {
using u32 = unsigned int;
using u16 = unsigned short;
constexpr u32 magic = 0x49555244; // DRUI
constexpr u16 version = 1, request_id = 0x0bf8, snapshot_id = 0x0bf4;
constexpr u16 bundle_version = 2;
// Open/Refresh do not otherwise use slot. Old servers ignore this capability
// and return v1; new servers send v2 only to clients explicitly requesting it.
constexpr u32 bundle_capability = 0x32555244; // DRU2
enum Action : u16 { Open, Refresh, AttendanceClaim, QuestClaim, Roll, Close };
enum Kind : u32 { AnyMonster = 1, Monster, Collection, UseItem, Pvp };
enum Flags : u16 { Ready = 1, RollClaimed = 2, Failed = 4 };
#pragma pack(push, 1)
struct Item { u32 id, amount; char name[48]; };
struct Quest { u32 kind, target, required, progress, claimed; char title[64]; Item rewards[6]; };
struct Day { u32 day, status; Item reward; }; // 0 locked, 1 claimable, 2 claimed
struct Request { u16 id, length; u32 signature; u16 protocol, action;
    u32 sequence, date, slot, attendance_page, reward_page; };
struct Snapshot { u16 id, length; u32 signature; u16 protocol, flags;
    u32 sequence, date, reset_remaining, attendance_page, reward_page, reward_pages, reward_total;
    u32 attendance_day, roll_count; char status[96];
    Day attendance[7]; Quest quests[5]; Item roll[5], possible[6]; };
struct BundleSnapshot { Snapshot base; Item attendance_extra[7][5]; };
#pragma pack(pop)
static_assert(sizeof(Request) == 32, "DRUI request ABI");
static_assert(sizeof(Snapshot) == 3308, "DRUI snapshot ABI");
static_assert(sizeof(BundleSnapshot) == 5268, "DRUI v2 bundle snapshot ABI");
}
