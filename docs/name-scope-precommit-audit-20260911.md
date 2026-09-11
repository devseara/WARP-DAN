# Name-scope precommit audit - 2026-09-11

> Superseded by the [completed scope cleanup and paired release](name-scope-cleanup-20260911.md). Historical findings and hashes below are retained as evidence.

The chosen scope is correct, but cleanup is **not complete**. The current tree restores several excluded runtime limits while retaining expanded guild-position transport, excluded SQL definitions, dormant client adapters, and some unrelated uses of the global identity limit. Two additional boundary defects were reproduced offline. Do not describe the pending changes as a complete scoped rollback or ready to commit yet.

This is an audit of the current working trees against server commit `b8ef7e5a4d21e87bd7568f45c4c45058c3e580ba` and WARP commit `ea2e303ff4a9c1675974e3a37407d14b5a241f1a`, including their parents. It adds this report and reproducible evidence; it does not implement the remaining cleanup. No commit, SQL migration, deployment, or server restart was performed in this audit.

Repository roots used below:

- WARP: `D:/Programs/Games/Ragnarok/01_github/WARP20250716-main`
- Server: `D:/Programs/Games/Ragnarok/01_github/BanquetOfHeroes`

## Required scope

| Value | Required policy | Current status |
|---|---|---|
| Player, guild, and party names | 128-byte capacity, including NUL | Explicit identity constants present |
| Monsters, bosses/MVPs, and summoned mobs | 128-byte capacity, including NUL | Canonical mob storage remains expanded |
| Pets, homunculi, mercenaries, elementals | 128-byte capacity, including NUL | Explicit companion constants present |
| NPC display names | 128-byte capacity, including NUL | Explicit display-name constant present |
| NPC overhead group titles | 128-byte capacity, including NUL | Keep the subsequently requested and accepted smelter-title fix |
| Clan labels/master labels, BG queue/lobby identifiers | Original 24-byte capacity | Runtime and dedicated client protocol restored; SQL/client-source leftovers below |
| Guild positions, non-NPC titles, storage/castle labels | Original 24-byte capacity | Content limits restored; guild-position transport still expanded |
| Gold PC service token | Original 24-byte field; 26-byte packet | Restored |
| Script labels and NPC script identifiers | Original independent limits | 24-byte label content; 50-byte NPC identifier; 77-byte combined event buffer |
| Account/resource/map/item/skill identifiers and other unrelated strings | Their original independent contracts | Mostly independent; remaining global-macro dependencies below |

128 bytes means at most 127 **encoded bytes** plus NUL. It is not a 128-character promise. SQL character-column widths and encoded-byte validation are separate requirements.

An eligible name remains eligible when referenced elsewhere: mail sender/recipient, friends, whispers, guild/party rosters, reports, player logs, guild-storage actors, auction sellers/buyers, party booking, and AutoSupport follow targets. Do not revert these merely because they belong to a different feature.

Likewise, shared `0A30`, `0ADF`, spawn/name responses, and EXTN need one matching client/server layout. A shared 128-byte field can carry a shorter non-NPC title or position. Shrinking such a field independently would reintroduce packet offsets and framing failures.

## 1. Administrative request/reply defect - fix before commit

`Server/src/map/chrif.cpp:963` (`chrif_req_login_operation`) and `:985` (`chrif_changesex`) reserve/send 44-byte `0x2B0E` records but copy `NAME_LENGTH` bytes at offset 6. `NAME_LENGTH` now resolves to 128. The operation and remaining fields still use offsets 30, 32, 36, and 40.

`Server/src/char/char_mapif.cpp:1115` still checks/skips 44 bytes and reads those old offsets. Its reply at `:1209` reserves/sends 34 bytes for `0x2B0F`, again copying 128 bytes at offset 6 and writing operation/result at 30/32. The map dispatch table at `src/map/chrif.cpp:62` and reply dispatch also retain the old sizes/offsets.

The extracted current serializer code was compiled with the actual server headers and `safestrncpy` implementation. An oversized canary FIFO measured writes outside each advertised record without corrupting a live process:

| Width control / current width | Record | Reserved and sent | Bytes modified after record |
|---|---|---:|---:|
| 24-byte control | Request `2B0E` | 44 | 0 |
| 128-byte current | Request `2B0E` | 44 | 90 |
| 24-byte control | Reply `2B0F` | 34 | 0 |
| 128-byte current | Reply `2B0F` | 34 | 100 |

All five tested name lengths (0, 1, 23, 24, 127) reproduce the same out-of-record writes. Padding makes this occur even for short names. This proves invalid record writes, not necessarily an allocator-boundary overwrite: the live FIFO may have spare capacity. The probe does not establish the cause of any earlier live crash or character-select gender issue.

This is a **player-name route**, so fixing it means paired 128-byte serialization, receive framing, field offsets, and bounded parsing, not truncating the target name to 24. With the existing fields, the matching record sizes would be 148 and 138 bytes. Ban/block/unblock/unban/VIP and explicit account/character sex-change paths use this request family. The specific administrative request/ACK bodies were not updated in `b8ef7e5`; the global macro expansion changed their writes implicitly.

## 2. Restored event buffer exposes a scanner boundary defect

`Server/src/common/mmo.hpp:198` now defines `EVENT_NAME_LENGTH` as 77. `src/map/map.hpp:487` embeds that buffer immediately before `spawn_data::filepath`.

`Server/src/map/npc.cpp:5360` still scans the event using `%77[^,]`. A scanset can write 77 content bytes **and** a trailing NUL. The extracted actual scan call, compiled with the real `spawn_data` layout, leaves the next field intact for lengths 23/76 but overwrites its first byte with zero for lengths 77/78. The 78-byte input also stops the later comma-delimited conversions.

The old pre-extension server already used this scanset with a 77-byte buffer. Enlarging `EVENT_NAME_LENGTH` masked the boundary error; restoring the original size exposes it again. Correct the scan bound and reject overlong event tokens without partial parsing. Do not grow script labels back to 128 to hide it. In production this function initially zeroes `spawn_data`, so the canary result is a bounds proof, not evidence of a particular observed crash.

## 3. Guild-position transport remains expanded

The **content** boundary is restored: `guild_position::name` uses `GUILD_POSITION_NAME_LENGTH == 24`. The dedicated wire formats still use the identity macro:

| Packet | Current record | Original record | Server source |
|---|---:|---:|---|
| `0166`, position ID/name list | 132 | 28 | `src/map/packets_struct.hpp:4870` |
| `0161`, position update request | 144 | 40 | `src/map/clif.cpp:15522` |
| `0174`, position update ACK | 144 | 40 | `src/map/packets.hpp:848` |

WARP still installs `GuildPositionNamesStatic` from `Scripts/Patches/ExtNameTextStatic.qjs:1182`. Its 144-byte records and 4KB outgoing scratch allocation remain active. `GuildNamesStatic.qjs:60` separately widens the `0166` list to 132-byte records.

This is currently paired transport, not proof of a current client/server mismatch. It nevertheless retains the excluded feature's expansion and client hooks. To complete the requested rollback, restore these three dedicated formats and their client handlers together, retaining guild identity and member-name adaptations. The current guild-position PE tests still expect the expanded format and must change with it. Shared overhead name/position packets require separate treatment, as noted above.

## 4. Excluded SQL definitions and migration policy remain expanded

`Server/sql-files/main.sql` still contains these `VARCHAR(127)` columns; all were `VARCHAR(24)` before `b8ef7e5`:

- `clan.name` and `clan.master` (table at line 352).
- `clan_alliance.name` (table at line 374).
- `guild_position.name` (table at line 555).

`Server/sql-files/upgrades/upgrade_20260905.sql:36` and `:38`-`:39` still include those columns in its widening cursor. Rerunning the migration would widen them again. Restoring runtime copies alone does not clean up this policy.

Correct fresh schemas and the migration allowlist. Any separate narrowing migration for an already upgraded database must preflight existing values and preserve data on rejection; do not silently truncate or assume that these databases only contain short values. This audit did not inspect or modify the live database. Existing wide columns are not by themselves a wire-format error.

The migration tests currently create a clan fixture and assert that its map/resource field stays short, but they do not assert that the excluded clan name stays short. Add explicit clan/guild-position preservation tests when correcting the allowlist.

## 5. Dormant client adapters and stale dependency

- `WARP/Scripts/Patches/ClanNamesStatic.qjs` remains in the tree, but its installer is no longer called.
- `WARP/Scripts/Patches/BattlegroundNamesStatic.qjs` likewise remains without an installer call.
- `WARP/Scripts/Patches/ExtNameTextStatic.qjs:1163` still requires `ClanNamesStatic` to exist even though it no longer installs that adapter.

Searches of Scripts/Patches/tools found no other live callers for these retired installers. Remove the unused modules and stale dependency as part of source cleanup, with patch-load/remove/reapply verification. Clan chat and BG participant **player identities** are separate and must keep their name adapters.

## 6. Remaining non-identity dependencies on NAME_LENGTH

These are verified scope dependencies, not all confirmed runtime failures:

| Site | Remaining dependency | Intended cleanup |
|---|---|---|
| `Server/src/login/login.cpp:640` | Account minimum-name configuration caps at `NAME_LENGTH - 1` (127), while account fields remain 24 | Use the account-name limit; a configured minimum above 23 is impossible to satisfy |
| `src/char/char.hpp:166`, `src/map/map.cpp:289`, `src/map/chrif.cpp:143`, `src/map/chrif.hpp:49` | Server whisper alias / server label buffers inherit 128 | Independent service/server-label capacities |
| `src/char/char_mapif.cpp:541`, `src/map/chrif.cpp:687` | `2AFB` sends/reads two 128-byte service-label slots (261 bytes total instead of 53) | Restore the paired service-label layout |
| `src/map/party.cpp:579` | SQL escape scratch for server/world label uses identity width | Size from the source label contract |
| `src/map/clif.cpp:18406`, `src/map/intif.cpp:2735`, `src/char/int_auction.cpp:276` | Auction **item-search text** inherits 128; internal `3050` grew from 40 to 144 bytes | Independent 24-byte search-text field, paired sender/receiver; buyer/seller names stay extended |
| `src/map/pc.hpp:1937` | `feel_var` / `hate_var` registry-key arrays inherit 128 | Script-token capacity |
| `src/map/atcommand.cpp:10859` | Channel command keyword buffer is 128 while its scanner uses 23 | Command-token capacity |
| `src/char/char.cpp:470` | Escaped map-name scratch derives from player-name width | Map identifier capacity |
| `src/map/map.cpp:5708` | Invisible-wall DB key bound derives from `2 * NAME_LENGTH + 3`; stored wall-name buffer is independently 50 | Independent wall-key contract |
| `src/map/script.cpp:21978` | Generated instance NPC script identifier scratch derives from display-name width | Script-identifier contract |

Do not mechanically classify every identifier-like variable as excluded. For example, `inter.cpp`'s account-info query actually searches **character names**, so its expanded field remains appropriate. `npc_parse_mob`'s `sprite` token resolves the mob database Aegis name, which is also used as a canonical mob-name fallback; it cannot be shrunk independently of that domain. The NPC display/unique-name parser's combined buffer likewise deliberately includes a full display name.

## Commit attribution and documentation

- Server `b8ef7e5`: global name expansion, broad schema migration, credential/resource exceptions. Implicit macro consumers explain why reviewing only its changed lines misses defects.
- WARP `ea2e303`: paired broad native adapters, including the excluded clan/BG/guild-position paths.
- Subsequent WARP footer and lifecycle fixes remain necessary; do not revert either whole original commit.
- `Server/doc/extended-names.md` still describes clans and guild positions as extended and lists obsolete clan sizes. Update it and the migration/PE contracts when completing cleanup.
- `WARP/docs/name-menu-fixes-20260910.md` already discloses that guild-position transport remains wide and SQL was not shrunk. This audit identifies further omissions and prevents that partial scope correction from being mistaken for a complete rollback.

## Evidence and acceptance boundary

Reproduction from the WARP root:

```powershell
.\.venv\Scripts\python.exe docs\evidence\name-scope-precommit-probe-20260911.py --output Outputs\name_scope_precommit_audit_20260911
```

The probe compiled successfully with MSVC. It executes 20 serializer vectors (10 width controls and 10 current-width vectors) plus four actual-layout event scans. Source hashes and results are in [evidence/name-scope-precommit-probe-20260911.json](evidence/name-scope-precommit-probe-20260911.json). Generated C++, build log, and executable are under `Outputs/name_scope_precommit_audit_20260911/`.

These probes deliberately reproduce defects; successful probe execution is **not** a clean-code test result. They do not exercise live client rendering, login operations, SQL migration, or every `NAME_LENGTH` occurrence. Earlier successful client/server tests do not cover these newly identified paths. Production fixes, paired rebuilds, and targeted regression tests remain outstanding.
