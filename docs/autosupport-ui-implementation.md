# AutoSupport UI implementation

Target: 2025-07-16 Ragexe plus BanquetOfHeroes map server.

## Ownership

- `Scripts/Patches/AutoSupportUI.qjs` owns rendering, native input, Skill
  Tree/inventory drag payload forwarding, window/controller lifecycle, and
  snapshot decoding.
- Banquet owns party validation, profile persistence, AutoSupport start/stop,
  skill/item policy, and snapshots.
- The client never chooses an arbitrary name. Player selection sends a
  character ID; Banquet validates current-party membership and returns the
  canonical name.
- The selected master is authoritative. AutoSupport no longer substitutes the
  leader or another member when that player is unavailable.

## Wire contract

ASUI reuses the proven variable-length custom UI transport:

- client request packet: `0x0BF8`;
- server snapshot packet: `0x0BEF`;
- magic: `ASUI` / `0x49555341`;
- messages: Open 1, Snapshot 2, SetScalar 3, Resync 6.

The ASUI snapshot intentionally uses the established 3,792-byte AHUI wire
layout so the native QJS renderer can be reused. Monster rows are interpreted
as party Player rows: `monsterId` carries character ID, the name is canonical
party roster text, and selection bits represent the single master.

The shared response router is version 4 and carries independent AHUI, ASUI,
PINC, and COUI handler cells. Patch order does not change handler ownership.

## UI

Tabs are Basic, Player, Skill, Potion, Looting, Move, and Item. Player is a
scrollable single-choice list of up to eleven other party members. AutoSupport
uses an independent settings-window ID and chains AutoCombat lifecycle hooks.
The persistent controller is one 216x72 group ordered AutoHunt, AutoSupport,
AutoPotion; AutoSupport suppresses the older two-tile AutoCombat controller and
routes the peer tiles through AutoCombat state/senders.

The RO Global/Classic menu adds AutoSupport as a required native UIButton in the
third in-box control-row slot. The full production profile applies AutoSupport
before theme/menu construction, so its route and assets exist deterministically.
The AutoSupport controller uses dedicated red/blue heart-and-cross baked frames.
A native `roz_autosupport` effect pack also ships red, blue-start, and blue-loop
STR files plus their texture layers.

Drag/drop registration resolves client inventory indices before validating and
storing potions, usable items, Fly/Butterfly Wings, Teleport, Warp Portal, and
dedicated recovery-skill slots. Loot controls are persisted and looting runs at
the lowest support priority so it cannot preempt healing/following/buffs.
Delay clicks use a server-owned numeric dialog and map the shared slot numbering
to attack, support, healing, status-recovery, and buff-item persistence.

## Persistence

`support_assistant_profiles` persists both canonical master name and stable
master character ID. Ability category 2 is now saved for the attack-skill page.
Ability and item tables persist UI slot, delay, active state, recovery rows,
Move-tab registrations, and the Looting-page policy.

Apply `sql-files/autosupport/support_assistant.sql` to upgrade existing
schemas before using the UI.

## Current acceptance

Static syntax, the 134-file cross-repository contract, UI/effect deployment,
WARP generation, stale-bridge scan, Release/x64 map-server and generator
compilation, full map-server linking, and 80/80 AutoSupport unit tests pass.
Live Ragexe acceptance still requires
screenshots in Classic/New themes plus Player selection, party change, relog,
all registration pages, low-priority looting, and controller interaction.
