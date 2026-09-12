# Bestiary — initial implementation

This is the single implementation and operator guide for the native 2025-07-16
Bestiary (layout V9, BSUI v3). The approved initial build is installed in the
local game/server directories. Cleanup preserves its behavior; automated checks
and live acceptance have separate meanings. Open the 760×500 journal with
`/bestiary`; it fits an 800×600 viewport.

## Encyclopedia and native UI

The unrestricted encyclopedia provides name/ID search, element and advanced
race/size/type/level filters, sorting, six monsters per page, adjusted server
HP/EXP/drop values, native item descriptions, skills/summons, original editorial
lore, real minimaps and native navigation. Info has 40 statistics in four local
subpages, including STR/AGI/VIT/INT/DEX/LUK, accuracy, defenses, motion and traits.
Native SPR/ACT sprites use a fitted union of all idle frames, preserving scale
and position through animation. Portrait rectangles are 240×156 on Monsters
and 210×168 on Research. Missing resources fail quietly.

A private UIFrameWnd (window ID 0x3FA) and UIEditCtrl reuse Item Collection's
stateless native helpers, 27-byte search limit and 250ms debounce. Shared slash
and 0x0BEF packet routes preserve other custom windows. No runtime DLL or shared
item-name renderer modification is required. Search/filter changes are bounded;
local Info pages use no network request. Research and Rewards have separate
layouts and account state.

## Player behavior

Research is shared across characters on an account. Natural registered monsters
with positive EXP record lifetime kills. The first eligible kill discovers a
monster; five tiers grant journal points once each. Encyclopedia information is
always available, including monsters excluded from research.

| Curve | Lifetime kill thresholds | Points per tier |
| --- | --- | --- |
| Normal | 1, 25, 100, 500, 1,500 | 1, 2, 3, 5, 10 |
| Boss | 1, 10, 50, 150, 500 | 1, 2, 3, 5, 10 |
| MVP | 1, 2, 5, 10, 25 | 1, 2, 3, 5, 10 |

The initial roster follows this checkout's **pre-renewal** mob database and its
imports: 625 positive-EXP definitions. Three starter groups (Poring Family,
Meadow Neighbors, Cave Dwellers) follow their lowest required member tier,
with 10 points per group tier. The group view opens its limiting member.
Favorites and one tracked monster persist account-wide. The tracker appears
inside the journal and continues updating on the Monsters page.

Rewards has All, Available, Claimed and Cabinet views. Click an eligible card
to claim, or Claim All. Mastering each researchable monster grants its cabinet
trophy; the starter groups grant a trophy at tier 1. Overall rewards are:

| Points | Reward |
| --- | --- |
| 25 | 5 Fly Wings (ItemId 601) |
| 50 | 20 Red Potions (501) |
| 100 | Beginner cosmetic title (1000) |
| 250 | 5 Butterfly Wings (602) |
| 500 | Specialist cosmetic title (1001) |

Utility items are account-bound and delivered to the claiming character's
normal mail inbox. Inventory capacity does not affect creating the reward;
normal mail attachment withdrawal handles space checks. Cabinet title cards
use the existing native title equipment handler. Both title definitions have
no bonus script. Title display still requires in-game acceptance.

## Credit and persistence

Eligible damage contributors and alive, connected party members within the
native AREA_SIZE of the defeated monster receive credit. One account receives
one credit per final death, even if multiple characters qualify. Damage credit
is frozen before death event callbacks and recorded only after rebirth checks.
No credit is granted for command/script/player summons, monster slaves, clones,
AI guardians, instance mobs, zero-EXP targets or scripted removal. Natural test
spawns are required: `@monster` is deliberately excluded.

Combat callbacks copy records to a bounded 65,536-record queue. A worker flushes
and commits a local WAL before the map service sends batches to the char
service. No combat callback runs SQL or waits for disk. The char service owns
account progress and applies each stream/sequence once in an InnoDB transaction.
Lost acknowledgements and reconnects replay safely. Queue failure is reported
in server logs and the Research UI.

**Durability boundary:** sudden process termination can lose credits still in
the unflushed memory queue. Disk-committed records are replayable; reward claims
use only SQL-committed milestones. Preserve `save/bestiary-<map_port>/research.wal`
and its stream checkpoint together. A restored database older than the WAL floor
fails closed. Do not delete the WAL to clear an error.

Claims lock the account directly with an exclusive key lock and insert the
unique `(account_id, reward_id, reward_version)` receipt, mail message/attachment
and cabinet entitlement in the same transaction. Failed insertion rolls back
all of them. Claim All handles at most 16 claims per RPC and continues from a
cursor; partial successes remain claimed if a later request fails. Retrying is
safe. Earned milestone points and tiers are immutable when curves are raised.

## Native protocol and cache

The 2025-07-16 client remains 760×500. BSUI v3 message 8 is a 128-byte personal
request; message 9 is a fixed 2,176-byte personal snapshot with six bounded rows.
The 5,120-byte encyclopedia payload and 64-entry catalog cache are separate.
Personal sequence IDs reject stale replies; destruction clears personal state.
An eight-second client timeout preserves the display and enables explicit
Sync progress recovery. Idle clients do not poll for personal refreshes.

Map-to-char research uses 0x30F8/0x38F8 protocol version 1. Both services compare
the canonical definition fingerprint. Progress commits mark only affected
accounts dirty; ordinary personal snapshots are coalesced with a two-second
cooldown. Claim/preference completion can refresh sooner. Kills never invalidate
the encyclopedia. `@reloadmobdb` retains its V8 catalog invalidation behavior.

## Install, configuration and rollback

Use the matching **client, map-server and char-server** from the V9 archive.
Stop map and char services and finish any Visual Studio builds before replacing
executables. The additive migration is
`sql-files/upgrades/2026-09-12-bestiary-research.sql`; apply it to the character
SQL database before starting the new services. Existing mail tables must be
InnoDB. The installer verifies schemas and preserves binary backups.

Definitions live in `db/bestiary_research.yml` with an empty initial
`db/import/bestiary_research.yml`. Imports extend definitions with distinct IDs;
edit existing base entries to tune their values. Preserve earned reward IDs,
versions, group IDs and trophy IDs. Raising a reward version intentionally makes
that reward claimable again, so do not change versions for cosmetic text edits.
Both services validate the same file at startup. **Research definition changes
currently require restarting both services**; `@reloadmobdb` refreshes monster
catalog data and does not reload research curves or drops/EXP configuration.

To roll back, stop both services and restore their recorded binary backups;
launch the prior client. Keep the additive SQL tables and WAL for recovery.
Do not restore only one service or erase progress/claim rows. Existing earned
items are ordinary account-bound mail attachments and must not be reissued.

Useful read-only checks in the character database:

```sql
SELECT * FROM bestiary_progress WHERE account_id = YOUR_ACCOUNT_ID;
SELECT source, target, MAX(tier), SUM(points)
FROM bestiary_milestones WHERE account_id = YOUR_ACCOUNT_ID GROUP BY source, target;
SELECT * FROM bestiary_claims WHERE account_id = YOUR_ACCOUNT_ID;
SELECT * FROM bestiary_entitlements WHERE account_id = YOUR_ACCOUNT_ID;
SELECT * FROM bestiary_preferences WHERE account_id = YOUR_ACCOUNT_ID;
```

## Verification and live acceptance

Automated checks execute the actual capture functions, definitions, WAL worker,
char SQL service and transaction-free mail insertion. They cover party support,
account deduplication/exclusions, concurrent journal producers, replay/gaps,
corruption, queue capacity, cross-character ownership, concurrent claims,
attachment insertion failure and Claim All. SQL tests use empty cloned schemas
in isolated fixture databases; they do not modify real player progress.

The emitted native x86 is tested for transport isolation, malformed/stale
packets, page actions, timeout recovery and teardown, alongside the existing
journal/cache/encyclopedia/Escape/minimap/fitting regressions. Synthetic native
renders check all personal views. These are not live gameplay acceptance.

After installation: kill naturally spawned Porings solo and with nearby party
support; compare a second character on the same account; favorite/track and
reopen; restart both services; claim the 25-point bundle twice and verify one
mail attachment; test withdrawal with full inventory; equip the earned title
from Cabinet. Also verify physical Escape, opaque gef_dun02/gl_prison minimaps,
comma formatting and one visible refresh after `@reloadmobdb`.

## Native input, reload and numeric contracts

### Physical Escape ownership

The actual 2025-07-16 `UIWindowMgr::ProcessPushButton` entry is `0x00A449A0`,
`thiscall(virtualKey, pressed)` with `ret 8`. The hook verifies the exact
`55 8B EC 8B 45 08` prologue before replacing six bytes; stock fallback replays
those bytes and resumes at `0x00A449A6`. Patch removal restores the prologue.
This entry is separate from the existing `CloseCutinOnEsc` hook.

Only a pressed VK_ESCAPE with the visible, exact private Bestiary vtable may
be handled. Native modal count at manager +0x1B4 must be zero and the first
visible top-level object in list +0x17C must be Bestiary. The list scan is
bounded. All other keys/window ownership states preserve stock behavior and
the original registers/flags. The private message handler dismisses Filters,
then the element popup, then the frame, clearing only Bestiary-owned input
focus/capture. A native item description in front keeps its own Escape path.
No keyboard polling or timer hook is used.

### Reload notification and cache

V8 sets request `filter_flags` bit 0 at byte 106 to subscribe to catalog
invalidation; unknown bits and all reserved fields remain rejected. Unmodified
V3 clients send zero and never receive the new unsolicited message. The
matching V8 backend is required for the subscription bit.

After `mob_reload()` finishes loading and rebinding live mobs/NPCs, the backend
sends subscribed active players an exact 20-byte BSUI v3 message 7: opcode
0x0BEF/u16, length/u16, magic/u32, version/u16, message/u16, revision/u32,
reserved-zero/u32. This uses the catalog revision already advanced by reload.
The client validates length/schema, ignores duplicates, retires in-flight
requests and empties cached pages while retaining the last displayed entry.
It requests fresh data once on the next visible draw; a closed journal defers
that request until reopening. Old-revision responses cannot replace the entry.
There is no idle polling, and ordinary close/reopen preserves a valid cache.
The former Reload button becomes Retry only after a request failure.

`@reloadmobdb` loads monster data using the battle/drop/EXP configuration
currently in memory. This integration does not make that command reread
`drops.conf` or `exp.conf`; configuration changes still require their normal
server reload/restart procedure.

### Opaque minimaps and numbers

All 1,129 native minimap thumbnails replace the RGB565 magenta key bucket
(R >= 248, G < 4, B >= 248) with the journal's pale opaque background before
nearest-neighbor sizing. Native map imagery remains intact, with no texture
color-key holes in the habitat card.

The numeric draw helper groups HP, Base EXP, Job EXP and every Info statistic
into a separate 64-byte scratch string. Zero, signs, decimal/percentage suffixes
and full signed/unsigned 64-bit values are preserved; nonnumeric fields pass
through unchanged. Server values remain unformatted on the wire, avoiding
truncation in the original 24-byte fields and applying no additional rates.


## Build, verification and accepted artifacts

Server sources live in the sibling `BanquetOfHeroes` checkout. Build all three
Release x64 targets: `src/map/map-server.vcxproj`,
`src/map/map-server-generator.vcxproj`, and `src/char/char-server.vcxproj`.
Both map projects must compile `bestiary_ui.cpp`, `bestiary_research.cpp` and
`bestiary_journal.cpp`. The generator omission that caused eight unresolved
research symbols has been fixed and its optimized x64 link verified.

The WARP patch is `Scripts/Patches/BestiaryUI.qjs`, with generated native fitting
code from `tools/native/bestiary_preview.cpp`. QJS files require CRLF and UTF-8
without BOM. `tools/build_bestiary_native_preview.py` rebuilds the embedded
freestanding helper. `tools/build_bestiary_preview.py` builds an isolated WARP
fixture; pass `--source`, `--output`, and optionally the local `--profile`.
`--lifecycle reapply` and `--lifecycle remove` verify patch ownership cleanup.

Runtime BMPs are in `Images/BestiaryUI/journal`; approved artwork inputs are in
`Images/BestiaryUI/source`. `tools/build_bestiary_journal_assets.py --game <dir>`
regenerates native assets using the active GRF order. Synthetic render fixtures
are in `tools/fixtures/bestiary`. Scratch builds and reports belong under
`Outputs/Bestiary`, not source control. Never commit runtime WALs or credentials.

Python tools require pefile, capstone, unicorn and Pillow. YAML comparison
also uses PyYAML. SQL verification also
requires PyMySQL and access to create an isolated fixture database. The C++
verification scripts currently target the installed MSVC 14.51/Windows SDK
10.0.26100.0 paths; adjust them for another build host.

Run `verify_bestiary_journal.py`, `verify_bestiary_cache.py`,
`verify_bestiary_encyclopedia.py`, `verify_bestiary_live_fixes.py`,
`verify_bestiary_research_native.py` and `verify_bestiary_native_fit.py` against
the same build directory. The fitter additionally takes `--game <dir>`.
`render_bestiary_journal.py <build> --game <dir>` renders all current pages.
Run `verify_bestiary_server_yaml.py`, `verify_bestiary_research_core.py` and
`verify_bestiary_research_sql.py` for the actual server loader, journal/capture
and SQL/mail boundaries. SQL tests create only empty-schema fixture databases;
connection settings are read privately from the server configuration.

`tools/verify_bestiary_release.py --build <dir> --reapply <dir> --removed <dir>`
collects the current verification reports and source identities for packaging.
`tools/package_bestiary_journal.py` packages verified client/server binaries,
assets, schema, definitions, reports and this guide. It checks recorded source
hashes. Installation requires stopped map/char services and no active compiler.
The existing accepted V9 archive and its verification/rollback evidence remain
in `Outputs/Bestiary`; cleanup does not silently replace the installed client.

Initial installed SHA-256 identities before source cleanup:

| Artifact | SHA-256 |
| --- | --- |
| Native client V9 | `0989913f2cd017c536e8dbac5bd3dd0bf01ed887220ffe79e359a1364a728235` |
| Map server V9 | `bfbc2678670b68a7204791a6f7118b49d2047d316160b1cfd081ecd98b35ffd0` |
| Char server V9 | `4b6dc362d839112db9bcfae5bec545e98da37894c74e8a10d716e2977d36baba` |

Research definitions are local calibration, not a claim to reproduce Global's
undocumented formulas. Numeric tuning, new groups and additional cosmetic
content can extend this baseline while preserving stable earned IDs.

## What the sources support

| Source | Supported observation | Limit |
| --- | --- | --- |
| [ROO Global 20/05/2026 patch notes](https://roglobal.com/news/1568) | Bestiary gained Claim All. A new-MVP event rewarded research level 6 with a permanent title and materials delivered by mail. | The event's prizes and delayed mailing are not the permanent Bestiary reward table. The notes do not establish a complete kill curve. |
| [Origin Monster Glossary guide](https://pinoygamer.ph/articles/ragnarok-origin-guide-book-of-gears-monster-glossary-journal-and-card-album.21690/) | Describes individual research, groups, an overall progress gauge, milestone rewards and a cabinet for special monster collectibles. | Community reporting; it does not establish present Global numeric balance or server implementation. |
| [Origin encyclopedia guide](https://sites.google.com/view/coddiwompledad/ragnarok-origin/new-to-ro-origin/monster-encyclopedia) | Independently describes those three progression layers and research-related cabinet collectibles. | Community guide of the Origin feature family; region/version is insufficiently pinned for exact Global rules. |
| [Classic research guide](https://rooccompanion.com/guide/monster-research/) | Describes 0â€“10 research, five-monster elemental lines and the lowest member constraining a line. | Explicitly fan-made **Classic**, not proof of Global's current curve or grouping rule. |

Global's own patch notes support a useful title-and-item milestone model. The
broader research/group/cabinet structure is supported by community descriptions.
Exact Global kill thresholds, per-kill scaling, specimen odds, party radius,
stamina restrictions and account-sharing behavior remain unverified. Do not
label locally selected values as official Global rules.

