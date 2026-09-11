# Scoped names and menu fixes — 2026-09-10

> Superseded by the [completed scope cleanup and paired release](name-scope-cleanup-20260911.md). Historical findings and hashes below are retained as evidence.

> Server candidate superseded: the September 11 live report exposed a mob-title buffer overwrite. See [the correction and runtime-client audit](map-server-name-scope-regression-20260911.md). The client candidate remains unchanged.

Applied across WARP and the adjacent BanquetOfHeroes checkout. The client uses
the checked-in profiles/2025-07-16 PROFILE MAIN.yml (126 patches), with a pristine
2025-07-16 source and asset-copy prompts disabled. This is a new build of that
profile, not a reconstruction of every historical binary-only modification in
the supplied already-patched client.

## Deliverable

- Client: Outputs/2025-07-16_name_menu_fixed_20260910/2025-07-16_Ragexe_name_menu_fixed.exe
- SHA-256: 2b111715ae643bee75963b2a4b0d152dda8a4d27b8ded4e49f3fc52570f473d5
- Paired server programs: Outputs/name_scope_fix_20260910/server-build/
- Profile, build log, artifact hashes and verification records are beside the
  client. Nothing was deployed, restarted or committed.

Use the client with the paired rebuilt server. Gold PC's correction is in the
server packet definition: replacing only the client cannot fix an old server
expecting 130 bytes. Common guild/clan/storage layouts also changed, so update
and restart affected server processes together.

## Name boundary

Lengths describe encoded bytes, not Unicode character counts.

| Domain | Capacity |
|---|---:|
| Player, guild and party identities | 128 bytes including NUL |
| Monsters, bosses, summons/clones represented as mobs | 128 bytes including NUL |
| Pets, homunculi, mercenaries and elementals | 128 bytes including NUL |
| NPC/portal display names | 128 bytes including NUL |
| BG queue/lobby identifiers, clan labels, Gold PC service tokens | 24 bytes including NUL |
| NPC overhead group titles | 128 bytes including NUL; [September 11 correction](npc-group-title-fix-20260911.md) |
| Guild positions, other unit/group titles, castle/storage labels | 24 bytes including NUL |
| NPC script identifier | Existing 50-byte content limit |
| Script event label | Existing 24-byte content limit; buffer adds NUL |

NAME_LENGTH remains a compatibility spelling for canonical identity code.
Independent constants govern the excluded domains. Player references remain
extended in mail, friends, whispers, reports, rosters, logs and other systems.

Shared name/EXTN packets retain one agreed 128-byte transport layout.
Non-NPC title and position values retain shorter content limits in those transport slots.
The already-paired guild-position transport also remains wide; its accepted
content/storage capacity is 23 bytes. This change does not claim that every
legacy wire slot was reduced to the smallest possible size.

Account credentials, resource names, timestamps, item/skill/map identifiers and
other independently-sized domains keep their existing contracts. Auto Hunt's
separate monster-list UI retains its existing 32-byte custom field; canonical
mob names do not imply that every custom presentation has the same capacity.

No SQL columns were shrunk or records deleted. Wider SQL storage is compatible
with bounded reads. Previously overlong excluded labels are bounded when
loaded/copied; their original stored data was not destructively migrated.

## Confirmed fixes

| Route | Applied correction |
|---|---|
| Gold PC / dynamic NPC 0A16 | Separate 24-byte service token; server size is 26, matching the native client |
| Party expel 0103 | Client sends 134 bytes with full player name and original account ID |
| Macro report 0BE2 | Client sends 241 bytes; type at 138 and message at 140; retains 100-byte message-content limit |
| Macro report ACK 0BE3 | Client consumes 138 bytes, reads status at 134 and constructs an owned full-name string |
| BG queue family | Paired serializers, registrations and client consumers restored to stock identifiers |
| Clan info | Stock 74-byte header and 24-byte alliance labels; members/chat retain extended player identities |

New request adapters reject unterminated/over-limit player names instead of
silently targeting truncated identities. Server report parsing also requires
bounded terminators before string comparison.

The hide-button crash is independent of NAME_LENGTH. The old menu could retain
a direct call to code cleared during feature reapplication. Custom buttons now
use stable request/visibility cells. The producer owns the callback value;
removing it restores zero, and reapplying it publishes the new target.
Mouse-up checks the cell before calling; layout ignores absent producers.
The AutoSupport-to-AutoHunt scalar route and shared state follow the same
ownership rules.

## Verification

- Real WARP built all 126 profile patches without patch errors.
- All 21 name suites pass on the full EXE, including NPC overlay, guild/clan,
  BG, character lifecycle, companions and request/ACK gaps. The first aggregate
  run hit the party harness's old scratch-memory location. Moving test stubs
  outside the larger PE and rerunning passed. The accepted-name-validation.json
  preserves the original result and resolution.
- The complete native macro sender passes short/long-message, 127/128-byte-name,
  register/stack, normal SEH restoration and native string-destruction checks.
  Allocation-failure exception unwinding was not injected.
- Thirteen real-WARP menu lifecycle cases pass, including hide-before-menu,
  hide/show, individual/all producer removal, showing removed producers and
  reapplication. Emulated callback returns preserve the stack ABI. Direct
  inspection of the final EXE confirms all three current callback targets.
- Eight name lifecycle cases pass across 1,084 guarded sites: removal,
  reapplication, failure rollback and name/color ownership. UI-after-disable
  was rerun after the final UI cleanup.
- Actual server headers and the effective shuffled packet table compile and
  pass 15 packet contracts. Of 996 registrations, 31 retain changed lengths
  versus the pre-extension server, down from 44. This does not enumerate every
  variable packet or outgoing-only layout.
- Full x64 Release server solution builds pass. The artifact manifest contains
  paired login, char, map and web hashes.
- The item/grade source gate passes 96 checks. The full-profile EXE passes its
  grade/custom-label contract with Rare/Epic/Mythic/Legendary.
- All 22 two-client selection-order cases pass. Results are recorded in
  Outputs/item_grade_scope_accepted_20260910/matrix-validation.log.
  Temporary test groups disable mutex behavior so all intended features remain
  selected; earlier development fixtures that omitted this are not acceptance
  artifacts.
- Changed production QJS files are UTF-8 without BOM and use CRLF.

Offline native execution and compiled layouts do not certify live behavior.
The repository requires live screenshots for both clients' item/grade vectors.
The reported hide/re-enable and Gold PC interactions also need an in-game run
with paired programs. The older accepted 2026 screenshot hash does not accept
this change.

## Evidence and reproduction

- [Original scope and commit audit](name-protocol-scope-audit-20260910.md)
- [Crash and Gold PC audit](repo-menu-goldpc-audit-20260910.md)
- evidence/name-length-references-20260910.json: 1,005 occurrences across
  949 lines/70 files; an inventory, not dynamic acceptance of every occurrence.
- evidence/menu-fixed-lifecycle-20260910.json
- evidence/name-scope-fixed-packets-20260910.json
- evidence/name-scope-client-validation-20260910.json
- tools/verify_all_name_packets.py
- tools/verify_menu_patch_lifecycle.py
- tools/verify_name_scope.cpp and docs/evidence/name-scope-compile-20260910.cmd
- tools/verify_item_grade_matrix_warp.py accepts --source-2026 and --output
  arguments for repeating the matrix in a fresh isolated fixture.

The server introduction was b8ef7e5, paired with WARP ea2e303. The audit
distinguishes the already-fixed character-footer/name-hook lifecycle commits
from these remaining gaps. User edits to conf/groups.yml and
conf/import/groups.yml were preserved.
