# Completed name-scope cleanup - 2026-09-11

The selected player, guild, party, monster/boss/summon, companion and NPC display
names keep 128-byte capacity (127 encoded bytes plus NUL). NPC overhead group
titles also stay extended, preserving the accepted smelter title.

The cleanup restores independent stock limits for clan/BG/guild-position labels,
server/Gold PC tokens, auction item-search text, script/configuration keys and
other excluded fields. Player-name references in mail, whispers, rosters, logs,
BG participation and clan chat remain extended. Shared name/title/EXTN slots
retain one matching 128-byte transport layout.

## Saved corrections

- Preserve the accepted menu hide/show/reapply callback fixes, character-select
  and Game Start gender/slot fixes, mob-title buffer fix, NPC names and group titles.
- Restore dedicated guild-position `0166` records to 28 bytes and `0161/0174`
  records to 40 bytes, with native stock client handlers. Retire the three
  clan, BG-label and guild-position adapter modules and stale dependencies.
- Use shared packed map/char administrative request/reply structures of 148/138
  bytes. Keep full player names, validate termination and reject truncated targets;
  cover sex-change, ban/block/unban/unblock and VIP operations.
- Guard the complete spawn-event token before scanning and reserve its NUL byte.
- Restore four clan/guild-position SQL columns in fresh schemas; exclude them
  from both canonical-name migrations. The separate scope migration preflights
  all values/defaults before table changes and never silently truncates.
- Update the server guide and existing packet/SQL regressions for the scoped policy.

This resolves the findings in [the historical precommit audit](name-scope-precommit-audit-20260911.md).
Do not revert either original broad-name commit wholesale; its selected identity
support and subsequent character-footer/lifecycle corrections remain necessary.

## Paired release

Paired server commit: `f8f933dff3c3bf77ebd64215fde05a729f57523c`.

Directory: `Outputs/name_scope_cleanup_20260911/` in WARP.

| Artifact | SHA-256 |
|---|---|
| 2025-07-16_Ragexe_name_scope_clean.exe | `f5f0baf59dcc03b03bf667ec7ef0ebbbcb8b3c179c3cc37a3aa4e1342a7535c3` |
| server-build/char-server.exe | `d56e38f20c8a567b4de2b31729c16649a04b90747d231cb464b57a6b5b33a578` |
| server-build/login-server.exe | `2ca0c6f38c561d83f8519d092eeef179def6f854444fb392b08b3cac6c8f96ea` |
| server-build/map-server.exe | `a5d1004d820d0cc72c036270a2389546aeb0f8dbdccf6a95e9c3c48e81af868b` |
| server-build/web-server.exe | `75fa428beeac30ddcb6df89f3095dd8ae2c5d45ccf73e001050a45d4fdbd3bd3` |

Use the new client with the matching rebuilt server processes. The previous
client still uses expanded guild-position records and must not be paired with
this restored dedicated layout. Replace/restart the server programs together
because shared common structures and map/char packet contracts changed.

For a previously upgraded database, use the server's
`sql-files/upgrades/upgrade_20260911.sql` on the main database to restore excluded
label columns to VARCHAR(24). It rejects values/defaults over 23 encoded bytes
and unsupported custom definitions before any table/data change. Resolve any
reported values explicitly and rerun. Fresh schemas already have these widths;
existing wider columns remain readable until the migration is applied.

The binaries and migration are saved separately. This work did not replace live
programs, restart services, or migrate application data. User settings/profile
and server group-permission edits remain outside the fixes' commit scope.

## Verification

- Full 126-patch Main 2025-07-16 profile built through real WARP without patch errors.
- All 22 native name suites pass, including 120 character-footer vectors, stock
  guild-position receive/send/reuse and 0/1/20-row writers, alongside extended
  identity paths. The first run found test assumptions retained from the retired
  guild-position patch: a missing stock CRT import stub and a 128-byte expectation
  in its reuse test. Both were corrected; affected suites were rerun successfully.
  Initial results remain recorded; the production PE did not change during reruns.
- Eight real-WARP name lifecycle cases pass across 1,039 guarded native sites;
  thirteen menu lifecycle cases pass.
- Thirty-two native NPC name/title receiver vectors and 72 actual server buffer
  cases preserve NPC titles through the 127-byte boundary and shorter non-NPC titles.
- Fifty-nine extracted administrative/service/auction/event cases pass, including
  both sex values, account/character sex-change requests, malformed replies,
  fragmented requests, full names, FIFO canaries and record-reuse safety.
- The actual server packet headers and effective shuffled registration table compile
  with the scope assertions and fifteen targeted packet contracts.
- All seven maintained server name serializer suites pass.
- Forty-one isolated SQL fixtures pass: both canonical migration entry points,
  mixed collations, excluded-label preservation, safe narrowing, idempotence,
  byte-length/default/custom-type rejection and no writes on preflight rejection.
- Full Release x64 login, char, map and web solution build passes.
- Item/grade source gate: 96 checks. Full-profile grade case passes. The complete
  two-client, selection-order matrix passes all 22 cases.
- Changed QJS sources remain CRLF, UTF-8 without BOM, with the expected header.

The user's earlier live acceptance is preserved as acceptance of those fixes.
These new release checks are compiled/native-emulation and isolated SQL tests;
no new live screenshot matrix or deployment acceptance is claimed.

The [release manifest](evidence/name-scope-cleanup-20260911.json) records artifact,
source and validation hashes. Full logs and build profiles are beside the release.
