# Name protocol audit and narrowed scope — 2026-09-10

**Historical audit:** the user subsequently added NPC display names and authorized implementation. See [the applied fixes and validation](name-menu-fixes-20260910.md). The proposal and pre-fix observations below are preserved as audit evidence.

The requested boundary is **player, guild, party, monster and companion identities**. A single global `NAME_LENGTH = 128` is too broad as a protocol policy. Use explicit domain limits and a packet allowlist. Restricting eligibility does not make references to an eligible name disappear from other systems.

This is an audit and migration design, not an applied server/client protocol change. No production QJS, server source, database, deployed EXE or Git commit was changed. Existing server changes to `conf/groups.yml` and `conf/import/groups.yml` were preserved.

## Proposed boundary

| Value | Content capacity, including NUL | Treatment |
|---|---:|---|
| Player character name | 128 | Creation, selection, rename, persistence and every reference to the same identity |
| Guild name | 128 | Guild identity, invitations, alliances, membership and announcements |
| Party name | 128 | Party identity, invitations, membership, booking and announcements |
| Monster name | 128 | Ordinary mobs, bosses/MVPs and summoned/clone mobs represented as monsters; quest/boss labels referring to that name |
| Pet, homunculus, mercenary, elemental name | 128 | Each is a distinct entity type, with its own persistence/status/rename routes where supported |
| NPC/portal visible name | Original domain limit | No new long-name eligibility; do not conflate with the separate 50-byte script identifier |
| Clan name and configured clan master label | Original domain limit | Clan members and chat senders are still **player** names |
| BG queue/lobby/game identifiers | Original domain limit | BG participants and name-bearing player updates still require extended player names |
| Guild position labels, custom titles, castle/storage labels, script labels | Original domain limit | Not implicitly included merely because they are adjacent to an eligible name |
| Gold PC/dynamic-NPC service token | 24 | `GOLDPCCAFE` is a service key, not a long character/NPC display name |
| Account credentials, maps, skill/resource/item identifiers, timestamps | Existing independent limits | Never derive these from an entity-name limit |

128 means **127 encoded content bytes plus NUL**, not 127 Unicode characters. Summons do not need another blanket category: use the name policy of their actual runtime entity type. Item names and character/guild titles are not implicitly selected by the user's entity list.

Friends, whispers/ignore, mail, party/guild rosters, trade, reports, rankings and logs remain in scope **where the field contains a player/guild/party identity**. For example, a mail title keeps its own limit while its sender and receiver retain 128-byte player-name fields. Auto Hunt's custom monster-list packet currently has its own 32-byte field (`AUTOHUNT_UI_MONSTER_NAME_LENGTH`); a canonical long mob name does not automatically prove that this separate UI supports it. Treat that as an explicit client/server surface if full names are required there.

## Shared packet rule

Some packets carry several domains or more than one entity type. Keep a single agreed wire layout per opcode/version. In particular, name replies, spawn/update packets and custom EXTN are shared by players, mobs and NPCs. Limiting NPC input to its original capacity does **not** permit sending a shorter packet under the same opcode while the client expects an enlarged one.

First separate domain/content limits from wire constants. Shared 128-byte transport slots may continue to carry shorter, NUL-padded NPC/title values. A later removal of unused transport expansion must change the server serializers, packet lengths/offsets, WARP readers/writers and tests together. Simply skipping `ClanNamesStatic`, `BattlegroundNamesStatic` or the shared name layer would create another mismatch.

Suggested domains: `CHARACTER_NAME_LENGTH`, `GUILD_NAME_LENGTH`, `PARTY_NAME_LENGTH`, `MOB_NAME_LENGTH`, `PET_NAME_LENGTH`, `HOMUNCULUS_NAME_LENGTH`, `MERCENARY_NAME_LENGTH`, `ELEMENTAL_NAME_LENGTH`, plus independent limits for NPC display/script identifiers, BG identifiers, clan labels and service tokens. These names are a proposed design, not constants already installed. Do not replace every occurrence mechanically or flip `NAME_LENGTH` back to 24 beneath the existing adapters.

## Confirmed current incompatibilities

The first three rows below are server input mismatches. The last is server output/client consumption. Native sender regions and registrations are byte-identical in the clean EXE, the supplied EXE and a fresh current-WARP names-only build.

| Opcode | Operation | Client bytes | Server bytes | Narrowed-scope disposition |
|---|---|---:|---:|---|
| `0A16` | Gold PC/dynamic NPC request | 26 | 130 | Restore the separate 24-byte service-token field |
| `0103` | Expel party member | 30 | 134 | Still in scope: add the missing player-name sender adapter |
| `0BE2` | Macro user report request | 137 | 241 | Still in scope: add the missing player-name sender and shifted fields |
| `0BE3` | Macro user report ACK | 34 | 138 | Still in scope: adapt receive length and subsequent fields/consumers |

### Gold PC

`BanquetOfHeroes/src/map/packets_struct.hpp:5791` uses `char name[NAME_LENGTH]` in `PACKET_CZ_DYNAMICNPC_CREATE_REQUEST`. The effective table registers its `sizeof`. Native sender `0x00914DA0` copies the fixed `GOLDPCCAFE` token with capacity 24 and sends 26 bytes; registration is at `0x00AA4847`. This explains the supplied warning **expected 130, remaining 26** before the handler runs. See `goldpc-packet-20260910.json` and the earlier combined audit for the actual emulated packet bytes.

### Party removal

`clif_parse_RemovePartyMember` (`clif.cpp:15100`) reads `PACKET_CZ_REQ_EXPEL_GROUP_MEMBER`, now 134 bytes. Native sender `0x00C8D634` constructs `0x0103`, copies 24 name bytes at offset 6, and obtains the send length from the unchanged native registration at `0x00AA0659` (30). Its send is at `0x00C8D69F`. The current outgoing-social adapter covers creation/invitation and room operations but omits this sender. The 132-byte region at `0x00C8D634` is identical in all three EXEs (SHA-256 `aad6879038a57876f6c9a23b2a16ac344286743b5b999dec78442da75486c86a`). This is a proven layout incompatibility; no live party-expulsion session was performed.

### Macro reports

`PACKET_CZ_MACRO_USER_REPORT_REQ/ACK` at `packets_struct.hpp:6024/6035` are enabled for this 2025 client. `ReportName[NAME_LENGTH]` enlarges request 137 → 241 and ACK 34 → 138. Request `ReportType` moves 34 → 138 and message 36 → 140; ACK status moves 30 → 134.

Native sender at `0x009F36A8` writes opcode `0BE2`, uses a 24-byte name at packet offset 10, retains the old following offsets, asks `0x00C14460` for the registered 137-byte length, and sends at `0x009F380A`. Native registrations at `0x00AA6689/0x00AA66A1` remain 137/34. A fresh exported length bridge was executed with Unicorn: `0BE3` still requests **34** bytes from `0x00C16570`; positive control `0207` requests **138**, confirming that the extended-name bridge was active. Merely expanding the ACK receive length would still leave its old status/name consumers wrong.

The 656-byte native region at `0x009F36A8` is identical in the original/supplied/fresh builds (SHA-256 `77897465f44a1b612fcc1f21b1edfd5b00ec2376c8f5ce54c9d0e9d39300a55e`). The old client and enlarged server disagree even when names are short. A live report/ACK interaction was not performed.

## Commit attribution

| Repository / commit | Relevant effect |
|---|---|
| Banquet `b8ef7e5` — 2026-09-06 | Changed `NAME_LENGTH` 24 → 128 and `SPAWN_NAME_LENGTH` 48 → 128; broad server/SQL migration. Untouched structs depending on the macro also grew, including the gaps above. |
| WARP `ea2e303` — 2026-09-06 | Paired client adapter migration; omitted the Gold PC distinction, party-removal sender and macro report request/ACK coverage. |
| WARP `9408fc8` — 2026-09-07 | Fixed missing character-select footer/preview/Game Start consumers. Historical regression, not an outstanding current-source finding. |
| Banquet `1f6c250` — 2026-09-07 | Documentation/unit-name follow-up; no repair for these packet gaps. |
| WARP `4ab3aa1` — 2026-09-08 | Fixed the name-adapter allocation/hook ownership lifecycle and expanded the aggregate test gate. Historical name lifecycle finding is already addressed in current source. |
| WARP `77c1dde` — 2026-09-08 | Current menu autofill state has the separate menu callback/visibility issues reproduced in the earlier audit. Narrowing name eligibility does not repair those. |

Reviewed working heads: WARP `77c1dde1dce5c6d4bca8f9cc6a89dab908324cd0`; exact Banquet head and all source/EXE hashes are in `evidence/name-protocol-audit-20260910.json`.

## Audit extent and limits

The source inventory contains **1,005 `NAME_LENGTH` occurrences on 949 lines across 70 files**, plus relevant independent name constants. It includes common structures, map client serializers/parsers, char/map/login links, SQL bindings, web booking, scripts/configuration and companion persistence. It is a reference inventory, not a claim that each occurrence received dynamic acceptance.

Compiled the real server `map/packets.hpp`, `clif_packetdb.hpp` **and `clif_shuffle.hpp`**, before `b8ef7e5` and at the current checkout. `src/custom/defines_pre.hpp` selects `PACKETVER 20250716`. Comparing 996 effective registrations yields **44 changed lengths**. This catches implicit changes that a Git diff of touched packet lines misses. It does not enumerate every outgoing `sizeof` packet, every variable-length row stride or every indirect structure dependency.

Extracted 1,553 native packet registrations using verified x86 registration-call sequences. Built a fresh names-only client through the real WARP console in the isolated fixture; no user profile or production script was modified. Executed the exported receive-length bridge for the report ACK and a known extended control packet.

Do not label every changed registration a current bug: `024A` is the pre-2015 mail notification, while this client uses the modern unread-mail path; current rankings use GIDs (`0AF6`) and name resolution (`0AF7`), not the legacy inline-name ranking list. `08DD` has a current outgoing BG adapter despite its server parser being `clif_parse_dull`. The current name suites cover many intended expanded paths, as documented in the earlier name reviews; this turn did not rerun the entire live/rendering matrix.

The user narrowed the intended feature while this broader inventory was in progress. This report preserves completed evidence and defines the migration boundary. It does not certify all 1,005 references safe or claim the narrower protocol is already implemented.

## Implementation sequence

1. Encode the selected domains and independent fixed fields; keep player references full width wherever they occur.
2. Repair `0A16` with a fixed service-token width and exact-size assertion. Repair `0103` and `0BE2/0BE3` as retained player-name routes, with native producer/consumer tests.
3. Remove only exclusive out-of-scope expansion, with matched server/WARP layouts. Keep shared packet widths stable until their complete producer/consumer contract is updated.
4. Check existing over-limit data before narrowing any database columns; wider SQL storage alone is not a packet mismatch and need not be destructively shrunk to restore wire compatibility.
5. Rebuild all affected server processes and a clean client; verify short, 23/24/127-byte boundary, rejected over-limit, repeated long-to-short and entity-sharing cases. Repeat required live name/render tests if shared text hooks change.
6. Fix and verify the independent menu callback/visibility lifecycle. The current native WARP regression still fails reapplication and hide-before-menu cases.

## Evidence

- `evidence/name-protocol-audit-20260910.json`: revisions, SHA-256s, all 44 registration differences, confirmed gaps and executed length results.
- `evidence/name-length-references-20260910.json`: source reference inventory with path, line, macro and source text.
- `Outputs/namelength_audit_20260910/`: before-migration source snapshot, compiler inputs/logs, effective server tables, native client table, fresh names-only profile/EXE/log and bridge results.
- `evidence/name-audit-packet_table.cpp`, `name-audit-compile.cmd`, `name-audit-compile_old.cmd`: exact compiler probe/commands used (workspace paths and installed MSVC runtime required).
- `repo-menu-goldpc-audit-20260910.md`: separate menu findings, six real-WARP lifecycle builds and Gold PC analysis.
- `name-static-review-20260908.md`, `name-static-lifecycle.md`: historical name findings and fixes.
