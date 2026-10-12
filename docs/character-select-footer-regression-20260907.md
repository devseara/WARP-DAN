# Character-select footer regression — 2026-09-07

The current [weapon coverage deployment](dual-wield-original-weapon-sprites.md), EXE 6e470532…, preserves the complete v2 footer correction. Its native parser and 120 preview/Game Start vectors pass again: [execution evidence](evidence/assassin-weapon-character-footer-20260907.json).


The 2025-07-16 client stored correct 279-byte `CHARACTER_INFO` records but
37 character-select and refresh instructions retained old footer offsets or the old record-copy length.
The fix updates those displacements in `CharacterNamesStatic.qjs`. It does not
change the packet format, character data, card positions, or weapon compositor.

## Introducing commit and activation

WARP commit [`ea2e303ff4a9c1675974e3a37407d14b5a241f1a`](https://github.com/YlenXWalker/WARP20250716-main/commit/ea2e303ff4a9c1675974e3a37407d14b5a241f1a),
2026-09-06 06:31:48 +08, `feat(names): support canonical 128-byte names in Main 2025 client`,
introduced `CharacterNamesStatic.qjs` and the 175-to-279-byte layout change.
It paired with BanquetOfHeroes `b8ef7e5` (06:30:56 +08). Its parent is `80129fc`.
The later merge `f79af33` brought the name work and weapon checkpoint together.
[Commit and exact baseline-byte audit](evidence/character-select-footer-origin-20260907.json).

The previous live weapon EXE `7568ea26...` has all 330 original character-layout
instructions. The user's full repatch `e0948969...` has all 330 widened instructions,
but the 37 omitted footer/copy consumers remain stock. The subsequently installed
grip build `93b65d24...` preserves that same mismatch. Thus the incomplete name
patch entered the source in `ea2e303` and became active in the user's new patch
set; it was already present before rebasing the grip contacts onto that EXE.

## Live proof

Read-only capture of PID16252 / SHA-256
`93b65d24eeeaf54b0a77002b30c6b375253e942507685aba6d567f365a495bc0`
found two records in the actual login owner:

| Record | Correct slot / sex / six stats | Old UI reads |
|---|---|---|
| GID5, Louis | 0 / male / all 99 | 0 / female / all 0 |
| GID6, female character | 1 / female / all 99 | 0 / female / all 0 |

Both names are shorter than 24 bytes. Consequently, the old footer locations
fall in zero-filled padding of the new 128-byte name. Both previews address
slot 0, the second overwrites the first preview, gender selects female resources,
and the stat panel displays zero. The received records themselves are intact.

[Live capture](evidence/character-select-footer-live-before-20260907.json).

| Field | Stock offset | Canonical offset | Example consumer VA |
|---|---:|---:|---:|
| STR–LUK | `84..89` | `EC..F1` | `0079F304` through `0079F46C` |
| Character slot | `8A` | `F2` | `0079C761` |
| Map name | `8E` | `F6` | `0079F4B9` |
| Deletion reservation | `9E` | `106` | `0079C828` |
| Robe palette | `A2` | `10A` | `0079C81B` |
| Sex, including compatibility write | `AE` | `116` | `0079C646`, `0079C655`, 14 resource/stat reads |

All offsets in this table are hexadecimal. Name remains at `6C` (108 decimal).
The `175` multipliers at `007954FD` and `0079975D` position screen columns;
they are not record indexing and must remain unchanged.

## Fix, binary and verification

Installed EXE: `2025-07-16_Ragexe_175220998_clientinfo_patched.exe`, SHA-256
`eed157256a8b8fbedcf6a1e11ab04c930cb1975401e44c137524f6f92d628357`.
Candidate: `Outputs/character_select_footer_20260907/client-character-footer-v2.exe`.
Backups beside the game EXE:
`2025-07-16_Ragexe_175220998_clientinfo_patched_before_char_footer_93b65d24.exe`
and `2025-07-16_Ragexe_175220998_clientinfo_patched_before_char_footer_v2_c87d98b5.exe`.

Only the 37 profiled instructions and PE checksum change: **66 different bytes**.
File length, every other mapped byte, EOF overlay, embedded GRF loader and complete
dual-weapon payload are identical to `93b65d24...`. No server rebuild was performed.

- [Exact before/after hex and addresses](evidence/character-select-footer-binary-v2-20260907.json).
- [Native instruction regression](evidence/character-select-footer-execution-v2-20260907.json):
  the old PE reproduces the observed slot/gender/stat failure. The corrected PE passes
  120 parser/preview vectors, including 127-byte names, slots 0/1/8/14/67, both sexes,
  and account-sex fallback. Name bytes survive preview normalization unchanged.
- Existing native page/create/delete regression passes, including 68 records,
  pagination, malformed pages, owner bounds, stack balance and deletion compaction.
- QJS syntax, CRLF / UTF-8 without BOM and 96 item/grade source checks pass.
- [Atomic deployment and hashes](evidence/character-select-footer-deployment-v2-20260907.json).

The prior native suite tested record storage but did not execute these preview
consumers. Its passing result did not establish complete character-select coverage.
The new checks supplement it; GPU appearance still requires live acceptance.

## Game Start transfer and first incomplete correction

The first installed candidate `c87d98b5...` corrected 26 preview/footer accesses,
but missed three byte-sized gender loads in the initial-card, repaint and Game
Start paths. The user rejected it: Louis still looked female and original artwork
still fell back. This first candidate is superseded, not visually accepted.

Game Start at `0079D71C` still loaded `[ESI+AE]`, then called `00D96C00`.
The setter writes `(gender & 1)` to `CSession+E78` (`015FB238`) and
`CSession+5538` (`015FF8F8`). Read-only inspection of the running first candidate
found character ID5, account gender1 (`015FB23C`), but both character-gender fields0
and the actual actor gender0. [Live session/actor evidence](evidence/character-select-game-start-live-before-20260907.json).
The earlier inspection's `session.gender` label
referred to **account** gender; the updated inspector labels all three distinctly.

The expanded correction adds those three loads, their robe/deletion reads, the
alternate character-preview slot/robe consumers, and the native record refresh at
`00D224C0`. That refresh now copies 279 bytes (69 DWORDs + WORD + BYTE), addresses
slot `F2`, and normalizes the map at `F6`. Its old 175-byte copy left the true footer
untouched. Both slot0 and slot1 refresh paths are executed in the new regression.

The Game Start test now executes the actual `00D96C00` setter, verifies both real
session destinations and stack balance, and reproduces the old male-to-female
transfer. Initial-card and repaint fallback branches execute for both sexes,
account fallback, and long names. These supplement the initial 26-consumer test.

## Original-weapon report

The bad builds retained a female actor for account2000000 with items1238/1219 and
generic dagger/dagger resources. The compatibility archive was open. Male
Gladius resources cannot be selected when the character gender is incorrectly0.
The female compositor separately supports views1/2/6/34..47; views31..33 are
excluded, so female Gladius fallback is a current coverage limit, not acceptance.
The user confirmed Louis is male after installing `eed15725...`. This accepts the
reported gender correction; no new automated live capture of the final male weapon
resources was made in that confirmation. Female Gladius still falls back.

A subsequent [eight-archive audit](evidence/female-gladius-coverage-20260907.json)
opened every configured archive successfully: female Assassin ACT/SPR files for
1207/1216/1219 are absent, while the original female Thief files are present in
`spritedata.grf`. The male compatibility overlay contains only male counterparts.
The female `profiled_view()` code also excludes31..33 and its held-contact table
has only17 entries. Female support therefore requires both compatible resource
mappings/ACTs and measured compositor profile entries, not just archive loading.
