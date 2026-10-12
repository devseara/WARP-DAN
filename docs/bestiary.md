# Bestiary - native journal and account research

This is the single implementation, player-behavior and operator guide for the
2025-07-16 native Bestiary: **layout V12, BSUI v3**. It covers the WARP client
and the matching sibling `BanquetOfHeroes` server. The user accepted the Fixed
EXE on 2026-09-13 with "all good" after testing the repaired mouse interactions.

## Accepted build

- Game EXE: `Banquet_Bestiary_Interactive_Rewards_20260913_Fixed.exe`.
- SHA-256: `14708cd6a9a3d3d526ea673d81f7def93878b68eeb284a2ee4103a9aed1c839f`.
- Recipe: `profiles/bestiary-accepted-20260913.yml`.
- Machine-readable acceptance, cleanup and verification evidence:
  `docs/evidence/bestiary-accepted.json`.
- The EXE, ZIPs, full logs and rollback backups remain under the local game
  directory and `Outputs/Bestiary`; generated game binaries are not Git source.

Cleanup must preserve the accepted PE byte-for-byte. Fixture reports describe
mocked native boundaries; the user's acceptance is recorded separately rather
than relabelling synthetic renders as live screenshots. The V11 Interactive
Rewards EXE is superseded because it cleared clicks in a native poll callback.

## Journal and menu

Open `/bestiary` or its dedicated RO Global menu button. The journal is 760x500
and fits an 800x600 game viewport. Monsters, Research and Rewards retain separate
state. The encyclopedia is unrestricted and includes search/filter/sort, adjusted
server stats and drops, native sprites and item descriptions, skills/summons,
lore, real minimaps and native Navigation. Info exposes 40 statistics in four
local pages. Missing resources fail quietly.

The journal is a private UIFrameWnd (`0x3FA`) using native UIEditCtrl children.
The menu button is a native UIButton (`0x3FB`) that calls the same toggle as the
slash command. It occupies the next compact grid slot after the other visible
custom buttons. Disabled BestiaryUI publishes a zero callback, preventing button
creation/display/clicks. Enable/remove/reapply works in either menu/feature order.

Hide/Show New Buttons offers Bestiary alongside Auto Hunt, AutoSupport and Item
Collection. Choices apply to both Classic and Renewal. If both patches select
the same custom button, the last applied/edited patch wins; removing it restores
the remaining choice, and removing both restores producer defaults. Show never
reactivates a disabled feature. Visibility writes stay outside the native NBV tag
because tag cleanup must not reclaim another patch's shared storage. The native
tag is balanced and uses the supported single-argument `BeginTag` form.

Both themes have normal, hover and pressed BMP states: Renewal 45x41, Classic
32x34. The illustrated book/paw artwork uses native Classic frames and a
borderless Renewal exterior. Native MENU retains the final reserved grid slot.

## Rewards and item interaction

Rewards has All, Available, Claimed and Cabinet views. Click eligible card text
to claim or use **Claim all available**, which includes every available reward
even while the list is filtered. Claimed/locked cards remain inspectable.

Each item reward shows up to five native ItemId icons with its own `x<quantity>`
label. Hover the 24x24 icon to see its identified name from the client's loaded
itemInfo manager. Right-button press and release on the same current icon opens
the standard item-information window. Icon inspection sends no claim packet;
left icon clicks are consumed while card text remains the claim target. Loading,
search edits, refreshes, tab changes, close and destruction reject stale presses.

Rewards search is a separate native edit, limited to 27 bytes and debounced for
250 ms. A new query resets paging and disables stale card actions until its reply
arrives. Reward-card searches cover reward names/descriptions, server item display
and Aegis names, and title names. All-digit queries match exact positive reward,
item or title IDs; zero/overflow match nothing. Cabinet searches title/trophy
labels and IDs as text. Empty search restores the selected full view. Monsters
search and its cache are unaffected.

Utility items are identified, account-bound and mailed to the claiming character's
normal inbox. Full inventory does not prevent creation of the reward mail; normal
attachment withdrawal checks apply. A bundle, its mail, receipt and entitlements
commit atomically. Failed attachment insertion rolls the entire reward back.

## Research and progression

Research is account-wide. Natural registered positive-EXP monsters grant lifetime
kill credit; all encyclopedia entries remain visible even when excluded from
research. The configured research roster has 625 definitions and 653 rewards.
Each monster has five tiers and grants its mastery trophy after tier 5.

| Curve | Lifetime kill thresholds | Points per tier |
| --- | --- | --- |
| Normal | 1, 25, 100, 500, 1,500 | 1, 2, 3, 5, 10 |
| Boss | 1, 10, 50, 150, 500 | 1, 2, 3, 5, 10 |
| MVP | 1, 2, 5, 10, 25 | 1, 2, 3, 5, 10 |

The 12 groups follow their least-completed required member. Selecting a group
opens that limiting member. Existing group IDs 1-3, their membership, all kill
curves and existing reward IDs/versions were preserved. New groups reconcile
committed historical kills on account load; repeated loads do not duplicate
points. Favorites and one tracked monster persist per account. The journal
tracker updates on the Monsters page as well as Research.

| ID | Group | Points per tier | Required MobIds |
| --- | --- | --- | --- |
| 1 | Poring Family | 10 | 1002, 1113, 1031 |
| 2 | Meadow Neighbors | 10 | 1063, 1007, 1008, 1052 |
| 3 | Cave Dwellers | 10 | 1015, 1076, 1005 |
| 4 | Prontera Sewers | 10 | 1051, 1053, 1054, 1175 |
| 5 | Ant Colony | 10 | 1095, 1105, 1160, 1176 |
| 6 | Byalan Shallows | 10 | 1141, 1066, 1067, 1044 |
| 7 | Payon Spirits | 15 | 1026, 1188, 1170, 1180 |
| 8 | Orc Encampment | 15 | 1023, 1273, 1213 |
| 9 | Desert Predators | 15 | 1019, 1106, 1030, 1037 |
| 10 | Pyramid Guardians | 15 | 1041, 1032, 1029, 1146 |
| 11 | Clock Tower | 20 | 1269, 1193, 1195, 1191 |
| 12 | Glast Heim Knights | 20 | 1163, 1132, 1219, 1179 |

The static active-spawn audit found 498 naturally researchable species and an
11,258-point ceiling, with all new group members present. This is a checked local
configuration, not a guarantee about future NPC edits or dynamic availability.
Fourteen point milestones extend through 10,000 points; six use multi-item bundles.

| Points | Reward |
| --- | --- |
| 25 | Earn 25 account journal points. |
| 50 | Earn 50 account journal points. |
| 100 | Earn 100 account journal points. |
| 250 | Earn 250 account journal points. |
| 500 | Earn 500 account journal points. |
| 750 | 20 White Potions, 10 Blue Potions, 10 Green Potions, 20 Fly Wings and 5 Butterfly Wings. |
| 1,000 | Earn the cosmetic Expert title at 1,000 journal points. |
| 1,500 | 10 Phracon, 5 Emveretarcon, 15 Iron and 5 Steel. |
| 2,500 | 10 each of Red Blood, Crystal Blue, Wind of Verdure and Green Live. |
| 3,500 | 40 White Potions, 20 Blue Potions, 20 Green Potions, 10 Awakening Potions and 10 Butterfly Wings. |
| 5,000 | Earn the cosmetic Master title at 5,000 journal points. |
| 6,500 | 20 Steel, 5 Star Crumb, 3 Oridecon and 3 Elunium. |
| 7,500 | 5 each of Flame Heart, Mystic Frozen, Rough Wind and Great Nature. |
| 10,000 | Earn the cosmetic Grand Master title at 10,000 journal points. |

## Titles

Claim or Claim All grants a kind-2 account title entitlement after validating
committed progress. Each character receives owned entitlements through the native
title list projection; select one in **Rewards -> Cabinet** to equip it through
`clif_change_title`. The char service persists the entitlement with the claim
receipt. An unearned title cannot be equipped through Bestiary.

`db/bestiary_research.yml` selects the Title ID; `db/title_db.yml` defines its
server name/icon, and the client's `title_tbl` uses that same ID. These seven
already existed in both tables and have no bonus scripts:

| Title ID | Title | Requirement | Server icon |
| --- | --- | --- | --- |
| 1000 | Beginner | 100 journal points | EFST_TITLE1 |
| 1001 | Specialist | 500 journal points | EFST_TITLE2 |
| 1002 | Expert | 1,000 journal points | EFST_TITLE3 |
| 1003 | Master | 5,000 journal points | EFST_TITLE4 |
| 1004 | Grand Master | 10,000 journal points | EFST_TITLE5 |
| 1025 | Poring Mania | Poring Family: all members at tier 5 | EFST_TITLE26 |
| 1035 | Orc Slayer | Orc Encampment: all members at tier 5 | EFST_TITLE36 |

An editable copy is installed at
`data/luafiles514/lua files/datainfo/titletable.lub`. It is plain Lua under a `.lub`
extension, matching the working source in `maindata.grf`. All 63 labels and the
original translation attribution are preserved. The accepted profile embeds its
GRF order; that archive already has the same seven labels. Future label edits
must reach the active GRF or use a profile that reads the data folder first.
`tools/sync_bestiary_titles.py` verifies the mapping and accepts `--grf-list` for
an embedded profile instead of assuming `DATA.INI` controls the EXE.

## Lore coverage and attribution

All 1,014 active MobIds are covered, including the battleground import: 203
community-wiki summaries, 45 official publisher notes and 32 in-game dialogue
accounts; the other 734 entries are labelled original field notes for undocumented
creatures and alternate encounters. Searches covered all 584 display names.
Only identifiable Ragnarok material was retained; other-game/anime material was
excluded from the selected accounts. Community material is attributed as such,
and original notes do not invent an official history. Lore remains separate from
current combat statistics.

`db/bestiary_lore.yml` loads on startup and `@reloadmobdb`. A strict candidate
loader rejects malformed entries/imports while preserving the previous valid
snapshot. Every Id must exist; generated Text is nonempty and bounded to 16,384 bytes, Source
at most 63 bytes, and neither contains NUL. The server wraps text into 90-byte
lines with UTF-8-safe long-word splitting and sends four lines per page. Imports
in `db/import/bestiary_lore.yml` can override base entries and are preserved.

Reviewed paraphrases live in `tools/fixtures/bestiary/lore/`. The generator follows
the selected MOB_DB import chain and active static NPC sources, assigns published
summaries to base encounters, and generates data-grounded original notes for the
remaining IDs. Full per-ID provenance and input hashes are retained in the server's
`db/bestiary_lore_sources.json`. No raw retrieved wiki introductions are shipped.
The bibliography below is the authoritative human-readable source list.

## Credit, claims and durability

Eligible damage contributors and alive connected party members within native
AREA_SIZE receive one credit per account per final death. Damage attribution is
frozen before death callbacks and recorded after rebirth checks. Command/script/
player summons, monster slaves, clones, AI guardians, instances, zero-EXP targets
and scripted removal are excluded. `@monster` therefore does not test research.

Combat callbacks copy records into a bounded 65,536-record queue. A worker flushes
and commits a local WAL before map sends batches to char; combat callbacks do not
run SQL or wait for disk. Char owns account progress and applies stream/sequence
records once in InnoDB transactions. Lost acknowledgements and reconnects replay
safely. Operational recording failures remain visible in logs and the journal.

Sudden termination can lose credits still in the unflushed memory queue. Disk-
committed records are replayable; claims use only SQL-committed milestones. Keep
`save/bestiary-<map_port>/research.wal` and its checkpoint together. A database
restored behind the WAL floor fails closed; deleting the WAL is not recovery.

Claims exclusively lock the account and write unique
`(account_id, reward_id, reward_version)` receipts, mail/attachments and cabinet
entitlements in one transaction. Claim All handles up to 16 claims per RPC and
continues by cursor. Partial completed batches remain claimed if a later batch
fails; retries are duplicate-safe. Earned tiers/points remain immutable if curves
are raised. New groups can reconcile from historical committed kills.

Reward YAML accepts either legacy `Item`/`Quantity` or `Items` (one to five distinct
Item/Quantity stacks). Quantities are 1-100; the forms cannot be combined. Numeric
Title IDs must exist and be cosmetic. The definition fingerprint includes bundle
order/quantities while preserving legacy contributions. Do not change earned IDs
or reward Version for a cosmetic edit: a higher Version permits another claim.
Research definitions require restarting matching map and char services.

## Wire, cache and native contracts

| Interface | Contract |
| --- | --- |
| Client request | `0x0BF8`, BSUI v3, 128 bytes; personal message 8 |
| Catalog response | `0x0BEF`, 5,120 bytes; separate 64-entry cache |
| Legacy personal response | message 9, 2,176 bytes, six bounded rows |
| Reward-item response | opt-in `filter_flags & 2`; message 10, 2,440 bytes |
| Map/char research | `0x30F8` / `0x38F8`, protocol 1, matching fingerprint |

The reward extension preserves the first 2,176 bytes and appends six packed
44-byte rows: `uint16 count`, reserved zero, five `uint32 item_id, quantity` pairs.
Counts are <=5 and quantities 1-100. V12 accepts only the exact legacy or extended
message/length pair and clears old previews after a legacy response. Old requests
continue receiving the legacy response. Personal queries/cache never enter the
encyclopedia cache. Sequence IDs reject stale replies; destruction clears state.

An eight-second personal timeout retains the display and exposes Sync progress
recovery. Idle clients do not poll for personal refreshes. The server coalesces
ordinary personal refreshes for two seconds; claim/preference completion can
refresh sooner. Kills mark affected accounts dirty, not the catalog cache.

Catalog requests use flag bit 0 at byte 106 to subscribe to reload notifications;
personal flag bit 1 is separate. After `mob_reload()` completes, subscribed active
players receive exact 20-byte BSUI v3 message 7 (opcode/length/magic/version/message,
revision and reserved-zero). The client ignores duplicates, retires stale requests,
clears cache and requests once on the next visible draw. Closed journals defer the
refresh until reopening. Unsubscribed older clients do not receive the notice.
`@reloadmobdb` uses battle/drop/EXP configuration already in memory; it does not
reread those configuration files. Close/reopen normally preserves valid cache.

### Mouse and item information

UIFrameWnd slots 32/33 are right-down/up. Slot 30 remains native `0xA23470`: the
manager calls it unconditionally at `0xA46EDB` between button events. V11 wrongly
used slot 30 for right-down and erased pending left clicks. V12 preserves it.
`verify_bestiary_mouse_dispatch.py` executes actual `0xA46ED3..0xA46F4C` dispatch;
it passes on the working V10, reproduces the V11 failure and passes on V12.
Calling down/up directly is insufficient to test this integration.

`CUIItemInfo@AdventureGuide` uses right-down slot 32 (`0x99C060`). The ItemId-only
caller at `0x77D9B7` preserves CItem constructor defaults; Bestiary follows that
pattern, identifies the item and sends window 12 message 24. Both native strings
at CItem +0x2C/+0x44 are destroyed even if the window factory fails. No inventory
mutation is involved. itemInfo identified name is an MSVC string at +0x40 (resource
stem +0x58), confirmed by setter `0xA7E9D0` and loader `0xA7F968`. Tooltip `0xA753D0`
receives the native tooltip-manager ECX after `0xA1EF70` converts coordinates.
Shared item/grade renderer hooks are not changed; there is no runtime DLL or
socket recv hook. All rendering and input remain on the client main thread.

### Escape, fitting and numbers

`UIWindowMgr::ProcessPushButton` at `0xA449A0` is thiscall(key,pressed), ret 8.
The guarded six-byte `55 8B EC 8B 45 08` prologue is replayed on fallback at
`0xA449A6` and restored on removal. Only a pressed Escape with the exact visible
Bestiary VTable, zero modal count (+0x1B4), and Bestiary as the first visible
window in the bounded top-level list (+0x17C) is handled. Dismiss Filters, then
the element popup, then the frame; release only Bestiary-owned focus/capture.
A native description in front retains its own Escape behavior. No key polling.

Native sprites fit the union of their idle frames, keeping scale/position stable:
Monsters portrait 240x156, Research 210x168. Minimap export converts the RGB565
magenta bucket (R>=248, G<4, B>=248) to an opaque journal background. Number drawing
groups HP, EXP and all Info fields in a separate 64-byte buffer, preserving signs,
fractions/suffixes and signed/unsigned 64-bit values. Values are not rate-adjusted
again or preformatted into the narrow wire fields.

## Assets and artwork provenance

Runtime files are `Images/BestiaryUI/journal` and `Images/BestiaryUI/menuicon`.
The canonical client location is
`data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/bestiary/{journal,menuicon}`. WARP emits the native
interface prefix from Item Collection; `tools/bestiary_paths.py` centralizes
packaging/verification. The local old `data/texture/bestiary` path is a junction
to the canonical directory for compatibility with older EXEs.

`tools/build_bestiary_journal_assets.py` regenerates the journal assets and keeps
the QJS resource list synchronized. `tools/build_bestiary_menu_buttons.py` produces
six native 24-bit BI_RGB BMPs with deterministic sizing/color-key conversion.
The native Classic frames and reference icons are retained beside
`Images/BestiaryUI/source/menuicon/journal-native.png`, with
`native-frame-provenance.json`. The original generated master was approved visually.
The exact generation prompt is retained here:

> Create ONE native Ragnarok Online Bestiary menu icon, a brown leather field journal with a golden paw emblem. It must look like the small hand-painted game sprites in the classic Ragnarok interface, not a flat vector app icon. Slightly tilted three-quarter perspective closed book, thick dark brown outline, saturated red-brown leather, warm brass corner pieces, visible cream paper edge, clear simple gold paw on the cover. Charming compact illustrated RPG inventory icon, carefully grouped colors and crisp pixel-like readable shapes, restrained shading and bright highlights. Designed to read at 32x32 pixels, so avoid fine detail. ONE isolated icon filling roughly 80% of a square canvas on a genuinely transparent alpha background. Absolutely no beige tile or plate, no button frame, no surrounding rectangular box, no backdrop, no glow, no external drop shadow, no labels, no text or lettering, no mockup. Only the floating illustrated journal icon; it will be placed borderless in a Renewal menu and into an existing native Classic button frame.

## Build, verification and packaging

Use WARP in this repository with the clean 2025-07-16 client source (SHA-256
`ead7c0a316bc6c27705a5a6876daf5093abec31677f3c1af7525c1709b201bff`). The accepted
profile captures its 128 selected patches; unrelated profile/staging work is not
part of this session commit. Full local server artifacts also reflect the server
checkout in which they were built; the scoped server commit contains Bestiary
changes only. Source/binary ledgers record that boundary.

```powershell
python tools/build_bestiary_preview.py --source <clean-exe> --profile profiles/bestiary-accepted-20260913.yml --output <fresh-build-dir>
python tools/build_bestiary_backend.py --output ../BanquetOfHeroes/build/<fresh-dir>
python tools/verify_bestiary_lore.py
python tools/verify_bestiary_server_yaml.py
python tools/verify_bestiary_research_core.py
python tools/verify_bestiary_research_sql.py
```

The backend builder compiles Release x64 char-server, map-server and map-server-
generator, pins inputs, and never deploys. Both map targets include the three
Bestiary sources. Python uses pefile, capstone, unicorn, Pillow and PyYAML;
SQL tests also require PyMySQL and permission to create disposable fixture DBs.
The local verifiers target MSVC 14.51 / Windows SDK 10.0.26100.0. QJS stays UTF-8
without BOM, CRLF and tab-indented. The native fitting blob is regenerated only
with `tools/build_bestiary_native_preview.py` when its C++ source changes.

Run these against the same client build directory:

- `verify_bestiary_journal.py`, `verify_bestiary_cache.py`,
  `verify_bestiary_encyclopedia.py`, `verify_bestiary_live_fixes.py`;
- `verify_bestiary_research_native.py`, `verify_bestiary_rewards_ui.py`,
  `verify_bestiary_reward_items.py`, `verify_bestiary_mouse_dispatch.py`;
- `verify_bestiary_native_fit.py` additionally takes `--game <game-dir>`;
- build `--coexist after --lifecycle reapply` and `--lifecycle remove` fixtures
  and verify callback ownership and native dispatch after reapplication;
- `verify_menu_patch_lifecycle.py` and `verify_bestiary_menu.py` exercise the
  custom menu, patch-order removal/reapply and both theme/visibility variants.

`render_bestiary_journal.py <build-dir> --game <game-dir>` renders emitted x86
with synthetic packets/native assets; it is a layout test, not a live screenshot.
Core/SQL tests execute actual server capture, WAL, definitions, title projection,
owned-only equip, replay, concurrent claims, account binding, rollback and Claim
All. Fixture SQL databases do not modify live progress.

`tools/package_bestiary_release.py` is the current release packager. It verifies
source/binary identities, all client gates and the supplied title-table report.
It ships this single guide, assets, source/provenance, migrations and machine
verification data. `--install-client` preserves existing EXEs and backs up changed
resources. Pass `--acceptance docs/evidence/bestiary-accepted.json` only for an
artifact whose hash matches the user-accepted build. Other builds remain unaccepted.

Lore regeneration uses `build_bestiary_lore.py --output <review-dir>`;
`--install` copies the reviewed YAML/provenance. `verify_bestiary_lore.py` checks
content and this guide's source block; explicit `--update-source-list` refreshes
only that block. Title publishing uses `sync_bestiary_titles.py --game <dir>
--output <dir> [--grf-list <embedded-INI>] [--install]`. Button-only packaging
remains available through `package_bestiary_menu_buttons.py`.

## Deployment and recovery

For a fresh server apply `sql-files/upgrades/2026-09-12-bestiary-research.sql` to
the character database. Both mail tables must be InnoDB; the row-preserving engine
migration is `2026-09-13-bestiary-mail-innodb.sql`. Preserve all import files,
research milestones, claim receipts and WAL/checkpoints.

`tools/install_bestiary_expansion.py` runs a read-only preflight unless passed
`--activate`. It requires zero online characters, verifies build identities and
test reports, recognizes only the known local map/char batch supervisors, backs
up binaries/WAL/mail, stops gracefully, conditionally converts mail tables,
verifies row identity, installs matching binaries and waits for the fingerprint
handshake. Optional `--start-login` starts an already-stopped login service.
It never force-kills a game server or resets player progress. No service restart
was needed for the V12 client-only mouse fix or this acceptance cleanup.

The approved local deployments are retained under `Outputs/Bestiary/activation-20260913` and `Outputs/Bestiary/lore-rewards-activation-20260913`. The latter
loaded all 1,014 lore entries and synchronized fingerprint 1861179977, 12 groups
and 653 rewards. Mail rows were identical across migration; tests created no
live player claims. Binaries/WAL/mail backups and the previous lore remain in
those directories, outside the release archive.

Rollback requires graceful map/char stop and restoring their matching backed-up
binaries/research YAML together. Keep InnoDB tables and progress receipts. Preserve
WAL/checkpoint pairs; do not restore an older progress database independently.
LUA/texture and EXE backups are independent from account storage. Useful read-only
SQL inspection: bestiary_progress, bestiary_milestones, bestiary_claims,
bestiary_entitlements and bestiary_preferences, filtered by account_id.

## Feature provenance

Research thresholds and reward amounts are local calibration. [ROO Global's
2026-05-20 notes](https://roglobal.com/news/1568) support Claim All and event
milestones with titles/material mail, but do not establish this server's numeric
curve. [Origin glossary reporting](https://pinoygamer.ph/articles/ragnarok-origin-guide-book-of-gears-monster-glossary-journal-and-card-album.21690/)
and an [Origin encyclopedia guide](https://sites.google.com/view/coddiwompledad/ragnarok-origin/new-to-ro-origin/monster-encyclopedia)
support the broader structure; the [Classic research guide](https://rooccompanion.com/guide/monster-research/)
is a separate fan guide. None establishes exact current Global formulas or
account-sharing rules for this implementation.

## Lore sources

Reviewed 2026-09-13. Community-wiki adaptations credit Ragnarok Wiki contributors
and are shortened/paraphrased under [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/),
unless an individual page says otherwise. Official iRO entries are short factual
paraphrases. The included `npc/other/monster_museum.txt` supplies 28 local exhibit
accounts and `npc/cities/yuno.txt` four dialogue accounts, with file/line provenance
in the per-ID JSON. No source is silently presented as another kind of authority.

<!-- BESTIARY_LORE_SOURCES_BEGIN -->
| Monster IDs | Source | Kind |
| --- | --- | --- |
| 1193 | [Alarm](https://ragnarok.fandom.com/wiki/Alarm) | Community wiki |
| 1735 | [Alicel](https://ragnarok.fandom.com/wiki/Alicel) | Community wiki |
| 1736 | [Aliot](https://ragnarok.fandom.com/wiki/Aliot) | Community wiki |
| 1737 | [Aliza](https://ragnarok.fandom.com/wiki/Aliza) | Community wiki |
| 1271 | [Alligator](https://ragnarok.fandom.com/wiki/Alligator) | Community wiki |
| 1095 | [Andre](https://ragnarok.fandom.com/wiki/Andre) | Community wiki |
| 1096 | [Angeling](https://ragnarok.fandom.com/wiki/Angeling) | Community wiki |
| 1627 | [Anopheles](https://ragnarok.fandom.com/wiki/Anopheles) | Community wiki |
| 1097 | [Ant Egg](https://ragnarok.fandom.com/wiki/Ant_Egg) | Community wiki |
| 1098 | [Anubis](https://ragnarok.fandom.com/wiki/Anubis) | Community wiki |
| 1016 | [Archer Skeleton](https://ragnarok.fandom.com/wiki/Archer_Skeleton) | Community wiki |
| 1099 | [Argiope](https://ragnarok.fandom.com/wiki/Argiope) | Community wiki |
| 1100 | [Argos](https://ragnarok.fandom.com/wiki/Argos) | Community wiki |
| 1266 | [Aster](https://ragnarok.fandom.com/wiki/Aster) | Community wiki |
| 1867 | [Banshee](https://ragnarok.fandom.com/wiki/Banshee) | Community wiki |
| 1039 | [Baphomet](https://ragnarok.fandom.com/wiki/Baphomet) | Community wiki |
| 1102 | [Bathory](https://ragnarok.fandom.com/wiki/Bathory) | Community wiki |
| 1060 | [Bigfoot](https://ragnarok.fandom.com/wiki/Bigfoot) | Community wiki |
| 1268 | [Bloody Knight](https://ragnarok.fandom.com/wiki/Bloody_Knight) | Community wiki |
| 1025 | [Boa](https://ragnarok.fandom.com/wiki/Boa) | Community wiki |
| 1188 | [Bongun](https://ragnarok.fandom.com/wiki/Bongun) | Community wiki |
| 1211 | [Brilight](https://ragnarok.fandom.com/wiki/Brilight) | Community wiki |
| 1103 | [Caramel](https://ragnarok.fandom.com/wiki/Caramel) | Community wiki |
| 1267 | [Carat](https://ragnarok.fandom.com/wiki/Carat) | Community wiki |
| 1638 | [Cecil Damon](https://ragnarok.fandom.com/wiki/Cecil_Damon) | Community wiki |
| 1283 | [Chimera](https://ragnarok.fandom.com/wiki/Chimera) | Community wiki |
| 1011 | [Chonchon](https://ragnarok.fandom.com/wiki/Chonchon) | Community wiki |
| 1246 | [Christmas Cookie](https://ragnarok.fandom.com/wiki/Christmas_Cookie) | Community wiki |
| 1269 | [Clock](https://ragnarok.fandom.com/wiki/Clock) | Community wiki |
| 1270 | [Clock Tower Manager](https://ragnarok.fandom.com/wiki/Clock_Tower_Manager) | Community wiki |
| 1104 | [Coco](https://ragnarok.fandom.com/wiki/Coco) | Community wiki |
| 1009 | [Condor](https://ragnarok.fandom.com/wiki/Condor) | Community wiki |
| 1265 | [Cookie](https://ragnarok.fandom.com/wiki/Cookie) | Community wiki |
| 1067 | [Cornutus](https://ragnarok.fandom.com/wiki/Cornutus) | Community wiki |
| 1073 | [Crab](https://ragnarok.fandom.com/wiki/Crab) | Community wiki |
| 1209 | [Cramp](https://ragnarok.fandom.com/wiki/Cramp) | Community wiki |
| 1018 | [Creamy](https://ragnarok.fandom.com/wiki/Creamy) | Community wiki |
| 1293 | [Creamy Fear](https://ragnarok.fandom.com/wiki/Creamy_Fear) | Community wiki |
| 1248 | [Cruiser](https://ragnarok.fandom.com/wiki/Cruiser) | Community wiki |
| 1260 | [Dark Frame](https://ragnarok.fandom.com/wiki/Dark_Frame) | Community wiki |
| 1272 | [Dark Lord](https://ragnarok.fandom.com/wiki/Dark_Lord) | Community wiki |
| 1105 | [Deniro](https://ragnarok.fandom.com/wiki/Deniro) | Community wiki |
| 1106 | [Desert Wolf](https://ragnarok.fandom.com/wiki/Desert_Wolf) | Community wiki |
| 1582 | [Deviling](https://ragnarok.fandom.com/wiki/Deviling) | Community wiki |
| 1109 | [Deviruchi](https://ragnarok.fandom.com/wiki/Deviruchi) | Community wiki |
| 1110 | [Dokebi](https://ragnarok.fandom.com/wiki/Dokebi) | Community wiki |
| 1046 | [Doppelganger](https://ragnarok.fandom.com/wiki/Doppelganger) | Community wiki |
| 1091 | [Dragon Fly](https://ragnarok.fandom.com/wiki/Dragon_Fly) | Community wiki |
| 1111 | [Drainliar](https://ragnarok.fandom.com/wiki/Drainliar) | Community wiki |
| 1113 | [Drops](https://ragnarok.fandom.com/wiki/Drops) | Community wiki |
| 1504 | [Dullahan](https://ragnarok.fandom.com/wiki/Dullahan) | Community wiki |
| 1114 | [Dustiness](https://ragnarok.fandom.com/wiki/Dustiness) | Community wiki |
| 1093 | [Eclipse](https://ragnarok.fandom.com/wiki/Eclipse) | Community wiki |
| 1115 | [Eddga](https://ragnarok.fandom.com/wiki/Eddga) | Community wiki |
| 1116 | [Eggyra](https://ragnarok.fandom.com/wiki/Eggyra) | Community wiki |
| 1033 | [Elder Willow](https://ragnarok.fandom.com/wiki/Elder_Willow) | Community wiki |
| 1957 | [Entweihen Crothen](https://ragnarok.fandom.com/wiki/Entweihen_Crothen) | Community wiki |
| 1117 | [Evil Druid](https://ragnarok.fandom.com/wiki/Evil_Druid) | Community wiki |
| 1205 | [Executioner](https://ragnarok.fandom.com/wiki/Executioner) | Community wiki |
| 1007 | [Fabre](https://ragnarok.fandom.com/wiki/Fabre) | Community wiki |
| 1005 | [Familiar](https://ragnarok.fandom.com/wiki/Familiar) | Community wiki |
| 1118 | [Flora](https://ragnarok.fandom.com/wiki/Flora) | Community wiki |
| 1119 | [Frilldora](https://ragnarok.fandom.com/wiki/Frilldora) | Community wiki |
| 1253 | [Gargoyle](https://ragnarok.fandom.com/wiki/Gargoyle) | Community wiki |
| 1120 | [Ghostring](https://ragnarok.fandom.com/wiki/Ghostring) | Community wiki |
| 1036 | [Ghoul](https://ragnarok.fandom.com/wiki/Ghoul) | Community wiki |
| 1121 | [Giearth](https://ragnarok.fandom.com/wiki/Giearth) | Community wiki |
| 1258 | [Goblin Archer](https://ragnarok.fandom.com/wiki/Goblin_Archer) | Community wiki |
| 1840 | [Golden Savage](https://ragnarok.fandom.com/wiki/Golden_Savage) | Community wiki |
| 1086 | [Golden Thief Bug](https://ragnarok.fandom.com/wiki/Golden_Thief_Bug) | Community wiki |
| 1040 | [Golem](https://ragnarok.fandom.com/wiki/Golem) | Community wiki |
| 1277 | [Greatest General](https://ragnarok.fandom.com/wiki/Greatest_General) | Community wiki |
| 1259 | [Gryphon](https://ragnarok.fandom.com/wiki/Gryphon) | Community wiki |
| 2071 | [Headless Mule](https://ragnarok.fandom.com/wiki/Headless_Mule) | Community wiki |
| 1213 | [High Orc](https://ragnarok.fandom.com/wiki/High_Orc) | Community wiki |
| 1127 | [Hode](https://ragnarok.fandom.com/wiki/Hode) | Community wiki |
| 1128 | [Horn](https://ragnarok.fandom.com/wiki/Horn) | Community wiki |
| 1129 | [Horong](https://ragnarok.fandom.com/wiki/Horong) | Community wiki |
| 1035 | [Hunter Fly](https://ragnarok.fandom.com/wiki/Hunter_Fly) | Community wiki |
| 1068 | [Hydra](https://ragnarok.fandom.com/wiki/Hydra) | Community wiki |
| 1029 | [Isis](https://ragnarok.fandom.com/wiki/Isis) | Community wiki |
| 1130 | [Jakk](https://ragnarok.fandom.com/wiki/Jakk) | Community wiki |
| 1131 | [Joker](https://ragnarok.fandom.com/wiki/Joker) | Community wiki |
| 1072 | [Kaho](https://ragnarok.fandom.com/wiki/Kaho) | Community wiki |
| 1132 | [Khalitzburg](https://ragnarok.fandom.com/wiki/Khalitzburg) | Community wiki |
| 1734 | [Kiel D-01](https://ragnarok.fandom.com/wiki/Kiel-D-01) | Community wiki |
| 1219 | [Abysmal Knight](https://ragnarok.fandom.com/wiki/Knight_of_Abyss) | Community wiki |
| 1282 | [Kobold Archer](https://ragnarok.fandom.com/wiki/Kobold_Archer) | Community wiki |
| 1587 | [Kraben](https://ragnarok.fandom.com/wiki/Kraben) | Community wiki |
| 1779 | [Ktullanux](https://ragnarok.fandom.com/wiki/Ktullanux) | Community wiki |
| 1070 | [Kukre](https://ragnarok.fandom.com/wiki/Kukre) | Community wiki |
| 1688 | [Lady Tanee](https://ragnarok.fandom.com/wiki/Lady_Tanee) | Community wiki |
| 1373 | [Lord of the Dead](https://ragnarok.fandom.com/wiki/Lord_of_the_Dead) | Community wiki |
| 1063 | [Lunatic](https://ragnarok.fandom.com/wiki/Lunatic) | Community wiki |
| 1836 | [Magmaring](https://ragnarok.fandom.com/wiki/Magmaring) | Community wiki |
| 1138 | [Magnolia](https://ragnarok.fandom.com/wiki/Magnolia) | Community wiki |
| 1139 | [Mantis](https://ragnarok.fandom.com/wiki/Mantis) | Community wiki |
| 1045 | [Marc](https://ragnarok.fandom.com/wiki/Marc) | Community wiki |
| 1140 | [Marduk](https://ragnarok.fandom.com/wiki/Marduk) | Community wiki |
| 1242 | [Marin](https://ragnarok.fandom.com/wiki/Marin) | Community wiki |
| 1141 | [Marina](https://ragnarok.fandom.com/wiki/Marina) | Community wiki |
| 1143 | [Marionette](https://ragnarok.fandom.com/wiki/Marionette) | Community wiki |
| 1144 | [Marse](https://ragnarok.fandom.com/wiki/Marse) | Community wiki |
| 1145 | [Martin](https://ragnarok.fandom.com/wiki/Martin) | Community wiki |
| 1090 | [Mastering](https://ragnarok.fandom.com/wiki/Mastering) | Community wiki |
| 1146 | [Matyr](https://ragnarok.fandom.com/wiki/Matyr) | Community wiki |
| 1147 | [Maya](https://ragnarok.fandom.com/wiki/Maya) | Community wiki |
| 1289 | [Maya Purple](https://ragnarok.fandom.com/wiki/Maya_Purple) | Community wiki |
| 1148 | [Medusa](https://ragnarok.fandom.com/wiki/Medusa) | Community wiki |
| 1274 | [Megalith](https://ragnarok.fandom.com/wiki/Megalith) | Community wiki |
| 1264 | [Merman](https://ragnarok.fandom.com/wiki/Merman) | Community wiki |
| 1058 | [Metaller](https://ragnarok.fandom.com/wiki/Metaller) | Community wiki |
| 1191 | [Mimic](https://ragnarok.fandom.com/wiki/Mimic) | Community wiki |
| 1149 | [Minorous](https://ragnarok.fandom.com/wiki/Minorous) | Community wiki |
| 1059 | [Mistress](https://ragnarok.fandom.com/wiki/Mistress) | Community wiki |
| 1150 | [Moonlight Flower](https://ragnarok.fandom.com/wiki/Moonlight_Flower) | Community wiki |
| 1055 | [Muka](https://ragnarok.fandom.com/wiki/Muka) | Community wiki |
| 1041 | [Mummy](https://ragnarok.fandom.com/wiki/Mummy) | Community wiki |
| 1026 | [Munak](https://ragnarok.fandom.com/wiki/Munak) | Community wiki |
| 1151 | [Myst](https://ragnarok.fandom.com/wiki/Myst) | Community wiki |
| 1249 | [Myst Case](https://ragnarok.fandom.com/wiki/Myst_Case) | Community wiki |
| 1203 | [Mysteltainn](https://ragnarok.fandom.com/wiki/Mysteltainn) | Community wiki |
| 1255 | [Nereid](https://ragnarok.fandom.com/wiki/Nereid) | Community wiki |
| 2022 | [Nidhoggr's Shadow](https://ragnarok.fandom.com/wiki/Nidhoggr%27s_Shadow) | Community wiki |
| 1061 | [Nightmare](https://ragnarok.fandom.com/wiki/Nightmare) | Community wiki |
| 1180 | [Nine Tail](https://ragnarok.fandom.com/wiki/Nine_Tail) | Community wiki |
| 1044 | [Obeaune](https://ragnarok.fandom.com/wiki/Obeaune) | Community wiki |
| 1189 | [Orc Archer](https://ragnarok.fandom.com/wiki/Orc_Archer) | Community wiki |
| 1686 | [Orc Baby](https://ragnarok.fandom.com/wiki/Orc_Baby) | Community wiki |
| 1087 | [Orc Hero](https://ragnarok.fandom.com/wiki/Orc_Hero) | Community wiki |
| 1273 | [Orc Lady](https://ragnarok.fandom.com/wiki/Orc_Lady) | Community wiki |
| 1190 | [Orc Lord](https://ragnarok.fandom.com/wiki/Orc_Lord) | Community wiki |
| 1152 | [Orc Skeleton](https://ragnarok.fandom.com/wiki/Orc_Skeleton) | Community wiki |
| 1023 | [Orc Warrior](https://ragnarok.fandom.com/wiki/Orc_Warrior) | Community wiki |
| 1153 | [Orc Zombie](https://ragnarok.fandom.com/wiki/Orc_Zombie) | Community wiki |
| 1038 | [Osiris](https://ragnarok.fandom.com/wiki/Osiris) | Community wiki |
| 1308 | [Panzer Goblin](https://ragnarok.fandom.com/wiki/Panzer_Goblin) | Community wiki |
| 1154 | [Pasana](https://ragnarok.fandom.com/wiki/Pasana) | Community wiki |
| 1256 | [Pest](https://ragnarok.fandom.com/wiki/Pest) | Community wiki |
| 1158 | [Phen](https://ragnarok.fandom.com/wiki/Phen) | Community wiki |
| 1159 | [Phreeoni](https://ragnarok.fandom.com/wiki/Phreeoni) | Community wiki |
| 1049 | [Picky](https://ragnarok.fandom.com/wiki/Picky) | Community wiki |
| 1160 | [Piere](https://ragnarok.fandom.com/wiki/Piere) | Community wiki |
| 1071 | [Pirate Skeleton](https://ragnarok.fandom.com/wiki/Pirate_Skeleton) | Community wiki |
| 1616 | [Pitman](https://ragnarok.fandom.com/wiki/Pitman) | Community wiki |
| 1161 | [Plankton](https://ragnarok.fandom.com/wiki/Plankton) | Community wiki |
| 1077 | [Poison Spore](https://ragnarok.fandom.com/wiki/Poison_Spore) | Community wiki |
| 1402 | [Poison Toad](https://ragnarok.fandom.com/wiki/Poison_Toad) | Community wiki |
| 1031 | [Poporing](https://ragnarok.fandom.com/wiki/Poporing) | Community wiki |
| 1002 | [Poring](https://ragnarok.fandom.com/wiki/Poring) | Community wiki |
| 1008 | [Pupa](https://ragnarok.fandom.com/wiki/Pupa) | Community wiki |
| 1254 | [Raggler](https://ragnarok.fandom.com/wiki/Raggler) | Community wiki |
| 1276 | [Raydric Archer](https://ragnarok.fandom.com/wiki/Raydric_Archer) | Community wiki |
| 1164 | [Requiem](https://ragnarok.fandom.com/wiki/Requiem) | Community wiki |
| 1052 | [Rocker](https://ragnarok.fandom.com/wiki/Rocker) | Community wiki |
| 1012 | [Roda Frog](https://ragnarok.fandom.com/wiki/Roda_Frog) | Community wiki |
| 1165 | [Sandman](https://ragnarok.fandom.com/wiki/Sandman) | Community wiki |
| 1243 | [Sasquatch](https://ragnarok.fandom.com/wiki/Sasquatch) | Community wiki |
| 1166 | [Savage](https://ragnarok.fandom.com/wiki/Savage) | Community wiki |
| 1167 | [Savage Babe](https://ragnarok.fandom.com/wiki/Savage_Babe) | Community wiki |
| 1001 | [Scorpion](https://ragnarok.fandom.com/wiki/Scorpion) | Community wiki |
| 1074 | [Shellfish](https://ragnarok.fandom.com/wiki/Shellfish) | Community wiki |
| 1037 | [Side Winder](https://ragnarok.fandom.com/wiki/Sidewinder) | Community wiki |
| 1076 | [Skeleton](https://ragnarok.fandom.com/wiki/Skeleton) | Community wiki |
| 1196 | [Skeleton Prisoner](https://ragnarok.fandom.com/wiki/Skeleton_Prisoner) | Community wiki |
| 1169 | [Skeleton Worker](https://ragnarok.fandom.com/wiki/Skeleton_Worker) | Community wiki |
| 1056 | [Smokie](https://ragnarok.fandom.com/wiki/Smokie) | Community wiki |
| 1170 | [Sohee](https://ragnarok.fandom.com/wiki/Sohee) | Community wiki |
| 1028 | [Soldier Skeleton](https://ragnarok.fandom.com/wiki/Soldier_Skeleton) | Community wiki |
| 1014 | [Spore](https://ragnarok.fandom.com/wiki/Spore) | Community wiki |
| 1174 | [Stainer](https://ragnarok.fandom.com/wiki/Stainer) | Community wiki |
| 1278 | [Stalactic Golem](https://ragnarok.fandom.com/wiki/Stalactic_Golem) | Community wiki |
| 1784 | [Stapo](https://ragnarok.fandom.com/wiki/Stapo) | Community wiki |
| 1042 | [Steel Chonchon](https://ragnarok.fandom.com/wiki/Steel_Chonchon) | Community wiki |
| 1207 | [Sting](https://ragnarok.fandom.com/wiki/Sting) | Community wiki |
| 1065 | [Strouf](https://ragnarok.fandom.com/wiki/Strouf) | Community wiki |
| 1069 | [Swordfish](https://ragnarok.fandom.com/wiki/Swordfish) | Community wiki |
| 1175 | [Tarou](https://ragnarok.fandom.com/wiki/Tarou) | Community wiki |
| 1622 | [Teddy Bear](https://ragnarok.fandom.com/wiki/Teddy_Bear) | Community wiki |
| 1034 | [Thara Frog](https://ragnarok.fandom.com/wiki/Thara_Frog) | Community wiki |
| 1051 | [Thief Bug](https://ragnarok.fandom.com/wiki/Thief_Bug) | Community wiki |
| 1048 | [Thief Bug Egg](https://ragnarok.fandom.com/wiki/Thief_Bug_Egg) | Community wiki |
| 1089 | [Toad](https://ragnarok.fandom.com/wiki/Toad) | Community wiki |
| 1312 | [Turtle General](https://ragnarok.fandom.com/wiki/Turtle_General) | Community wiki |
| 1618 | [Ungoliant](https://ragnarok.fandom.com/wiki/Ungoliant) | Community wiki |
| 1066 | [Vadon](https://ragnarok.fandom.com/wiki/Vadon) | Community wiki |
| 1092 | [Vagabond Wolf](https://ragnarok.fandom.com/wiki/Vagabond_Wolf) | Community wiki |
| 1032 | [Verit](https://ragnarok.fandom.com/wiki/Verit) | Community wiki |
| 1685 | [Vesper](https://ragnarok.fandom.com/wiki/Vesper) | Community wiki |
| 1176 | [Vitata](https://ragnarok.fandom.com/wiki/Vitata) | Community wiki |
| 1088 | [Vocal](https://ragnarok.fandom.com/wiki/Vocal) | Community wiki |
| 1179 | [Whisper](https://ragnarok.fandom.com/wiki/Whisper) | Community wiki |
| 1261 | [Wild Rose](https://ragnarok.fandom.com/wiki/Wild_Rose) | Community wiki |
| 1010 | [Willow](https://ragnarok.fandom.com/wiki/Willow) | Community wiki |
| 1263 | [Wind Ghost](https://ragnarok.fandom.com/wiki/Wind_Ghost) | Community wiki |
| 1013 | [Wolf](https://ragnarok.fandom.com/wiki/Wolf) | Community wiki |
| 1192 | [Wraith](https://ragnarok.fandom.com/wiki/Wraith) | Community wiki |
| 1291 | [Wraith Dead](https://ragnarok.fandom.com/wiki/Wraith_Dead) | Community wiki |
| 1057 | [Yoyo](https://ragnarok.fandom.com/wiki/Yoyo) | Community wiki |
| 1177 | [Zenorc](https://ragnarok.fandom.com/wiki/Zenorc) | Community wiki |
| 1178 | [Zerom](https://ragnarok.fandom.com/wiki/Zerom) | Community wiki |
| 1015 | [Zombie](https://ragnarok.fandom.com/wiki/Zombie) | Community wiki |
| 1197 | [Zombie Prisoner](https://ragnarok.fandom.com/wiki/Zombie_Prisoner) | Community wiki |
| 1715, 1721, 1751, 1752, 1753, 1754, 1765 | [Novus, Dragon Egg, Valkyrie Randgris, Skogul, Frus, Skeggiold, Valkyrie](https://renewal.playragnarok.com/news/eventdetail.aspx?id=167&p=43) | Official iRO |
| 1614, 1615, 1619, 1620, 1621, 1623, 1628 | [Mineral, Obsidian, Porcellio, Noxious, Venomous, RSX-0806, Holden](https://renewal.playragnarok.com/news/eventdetail.aspx?id=197&p=15) | Official iRO |
| 1634, 1635, 1636, 1637, 1639, 1652, 1654, 1655, 1656, 1657 | [Seyren Windsor, Eremes Guile, Howard Alt-Eisen, Margaretha Sorin, Kathryne Keyron, Egnigem Cenia, Armeyer Dinze, Errende Ebecee, Kavach Icarus, Laurell Weinder](https://renewal.playragnarok.com/news/eventdetail.aspx?id=294&p=11) | Official iRO |
| 1400, 1404, 1406, 1492 | [Karakasa, Miyabi Doll, Kapha, Samurai Specter](https://renewal.playragnarok.com/news/eventdetail.aspx?id=339&p=9) | Official iRO |
| 1613, 1617 | [Metaling, Old Stove](https://renewal.playragnarok.com/news/updatedetail.aspx?id=106&p=9) | Official iRO |
| 1653, 1681, 1682 | [Wickebine Tres, Gemini-S58, Remover](https://renewal.playragnarok.com/news/updatedetail.aspx?id=222) | Official iRO |
| 1378, 1384, 1493, 1586 | [Demon Pungus, Deleter, Dryad, Leaf Cat](https://renewal.playragnarok.com/news/updatedetail.aspx?id=243) | Official iRO |
| 1986, 1987, 1988, 1989, 1992, 1994, 1995, 1999 | [Tatacho, Centipede, Nepenthes, Hillslion, Cornus, Luciola Vespa, Pinguicula, Centipede Larva](https://renewal.playragnarok.com/news/updatedetail.aspx?id=70) | Official iRO |
<!-- BESTIARY_LORE_SOURCES_END -->
