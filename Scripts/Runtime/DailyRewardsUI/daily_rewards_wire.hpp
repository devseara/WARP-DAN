// DRUI v1 prefix, v2 attendance bundles, v3 catalog and v4 sixth Roll reward.
#pragma once
namespace daily_rewards_wire {
using u32 = unsigned int;
using u16 = unsigned short;
constexpr u32 magic = 0x49555244; // DRUI
constexpr u16 version = 1, request_id = 0x0bf8, snapshot_id = 0x0bf4;
constexpr u16 bundle_version = 2, catalog_version = 3;
constexpr u16 six_reward_version = 4;
constexpr u32 six_reward_capability = 0x34555244; // DRU4
constexpr u16 reroll_version = 5;
constexpr u32 reroll_capability = 0x35555244; // DRU5
constexpr u32 max_rerolls = 100;
constexpr u32 max_roll_pool = 1024;
// Read-only Open/Refresh do not use date. Keep slot=DRU2 so old servers
// still negotiate bundles; DRU3 in date opts into the complete icon catalog.
constexpr u32 catalog_capability = 0x33555244; // DRU3
// Open/Refresh do not otherwise use slot. Old servers ignore this capability
// and return v1; new servers send v2 only to clients explicitly requesting it.
constexpr u32 bundle_capability = 0x32555244; // DRU2
enum Action : u16 { Open, Refresh, AttendanceClaim, QuestClaim, Roll, Close, Reroll };
// Reroll keeps the 32-byte request: slot packs quest(3), used(7), attendance
// page(2), reward page(8); attendance_page echoes the displayed price.
inline u32 reroll_slot(u32 quest, u32 used, u32 attendance, u32 rewards) {
    return quest | (used << 3) | (attendance << 10) | (rewards << 12);
}
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
struct CatalogSnapshot { BundleSnapshot bundle; u32 roll_ids[max_roll_pool]; };
struct SixRewardSnapshot { CatalogSnapshot catalog; Item sixth_roll; };
struct RerollInfo { u32 used, limit, cost, zeny, pending; };
struct RerollSnapshot { SixRewardSnapshot six; RerollInfo reroll; };
#pragma pack(pop)
static_assert(sizeof(Request) == 32, "DRUI request ABI");
static_assert(sizeof(Snapshot) == 3308, "DRUI snapshot ABI");
static_assert(sizeof(BundleSnapshot) == 5268, "DRUI v2 bundle snapshot ABI");
static_assert(sizeof(CatalogSnapshot) == 9364, "DRUI v3 catalog snapshot ABI");
static_assert(sizeof(SixRewardSnapshot) == 9420, "DRUI v4 six-reward snapshot ABI");
static_assert(sizeof(RerollSnapshot) == 9440, "DRUI v5 reroll snapshot ABI");
}
