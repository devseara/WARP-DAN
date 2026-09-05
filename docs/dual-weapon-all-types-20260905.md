# Historical all-weapon extension — 2026-09-05

**Superseded:** the user limited the patch to dagger1, one-handed sword2 and
one-handed axe6. [Current scope and deployed build](dual-weapon-supported-types-20260905.md).
The records below describe the preceding all-type experiment, not the current
class admission policy.

**Status:** the approved GM server slot change is deployed and a mace in the
off-hand is verified live. The client source, runtime payload and isolated EXE
candidate now accept all 23 weapon classes with resource-identity guards.
**All-type sprite placement is not complete or live accepted.** Missing job
artwork, per-image registration and the native attack carrier require further
work. At the user's request, extension EXE `91b16900...edeb8` was installed at
2026-09-05 07:51:24 UTC. The previous accepted reference EXE is backed up; this
deployment does not establish new live placement acceptance. See the
[deployment record](evidence/dual-weapon-all-type-deployment-20260905.json).

## What is actually deployed

The [server deployment](gm-all-weapons-server-20260905.md) installed map-server
SHA-256 `21d80fc5186130ec1b65efc8cc37e347c8eb8f8dbfb161e177994224c74d479e`.
The guards use `PC_PERM_USE_ALL_EQUIPMENT`; the current import configuration
grants it to Admin group99. The compiled Renewal/classic equipment matrix passes
188,786 checks. Login and char processes remained running during the graceful
map restart.

The user reconnected and swapped the mace and knife. Read-only captures of the
same client actor `1481185360` record actual main/off item fields:

| Capture | +0x440 main | +0x444 off |
|---|---:|---:|
| [Mace main](evidence/dual-weapon-live-mace-after-server-20260905.json) | 1504 | 1238 |
| [Mace off](evidence/dual-weapon-live-off-mace-after-server-20260905.json) | 1238 | 1504 |

This verifies the newly permitted slot, not the original mace artwork. The game
EXE in both captures is the accepted
`0bb06dbc84d9e0a5df4fb3002b8946388d00158576ef18be74b3fbff754d4509`.

## Client changes implemented

`Scripts/Patches/AllowDualCustomWeaponSprites.qjs` no longer uses the old
item-range pair mapper `D39130` as a universal weapon classifier. It resolves
the item's real view through `D8A1D0`, then the active Lua base class through
`D5DDB0` (`RET4`), admitting exactly 1..23. The old pair result is retained only
for legacy dispatch; asymmetric native axe combinations no longer prevent
resource ownership.

A successful native solo load does not necessarily supply original art:
Assassin mace8 can fall back to sword2. Before retaining either hand, the owner
calls `D60DE0(itemId)` and compares its active Lua weapon suffix with both loaded
channel5 filenames plus their exact `.act`/`.spr` extensions. It consumes the
returned string immediately, performs bounded scans, and preserves CP949
multibyte bytes while folding standalone ASCII case. Missing/mismatched names
leave the requested stock state intact and do not publish an original-art row.
No Lua calls occur in the draw hook. The 60-byte row layout is unchanged.

The generalized C compositor in `CustomDLL/DualWeapon/compositor.c`:

- Admits all 23 classes independently of combined pair codes, but requires
  retained female Assassin ACT names at **CResource+0x14**. The earlier shorthand
  `+20` was decimal, not hexadecimal; the test fixture now contains native names
  at the same verified offset.
- Reconstructs the accepted pair28 native packet basis from the current packet,
  including ACT edge normalization and the native second-endpoint `+1`.
- Computes original-image center registration at runtime, retaining fractional
  parity, independent positive X/Y scales, source mirror and actor rotation.
  It selects actual source frames/images and palettes. The old view34/45-only
  placement admission and estimated canonical-pose branch are removed.
- Preserves opaque legacy rendering only for actual views45/34 or34/45 with
  the accepted native carrier fingerprint. A generic pair28 carrier alone is
  insufficient to identify those original items.
- Prepares both hands before suppressing stock. Missing exact source cells,
  extra real image layers, nonzero source rotations or unsupported scales
  leave stock visible. Held actions32..39 and native dual actions88..95 are
  supported. The inherited solo off-hand non-held path, including its native
  frame-zero fallback, remains distinct; no phase80-to88 substitution is made.

The checked-in runtime is the new candidate payload. The previous accepted
payload is preserved as
`Outputs/dual_weapon_all_types/accepted-compositor-b774459f.dwcp`.
The canonical DWR3/DWC2 byte blobs remain embedded for layout compatibility;
the generalized path uses the generated native reference basis, not the earlier
estimated canonical poses.

## Rebuilt candidate and exact addresses

Candidate: [client-all-types-candidate.exe](../Outputs/dual_weapon_all_types/client-all-types-candidate.exe).
This exact file is now installed in the game directory. Its SHA-256 and all
four installed hooks were verified after atomic replacement. It has no new
live placement acceptance. The backup filename is
`2025-07-16_Ragexe_175220998_clientinfo_patched_before_all_types_0bb06dbc.exe`.

| Artifact | SHA-256 |
|---|---|
| Candidate EXE | `91b1690045634a07dae3b09c52a5564b8ae7895b16e53b1bb9235b2ed6bedeb8` |
| Current runtime DWCP | `aee8b54a4a6087c107f5f6d53fe4d1e493eac70ed788bbaab8216bb0657e5728` |

These are PE32 preferred-image VAs for the 2025-07-16 profile only:

| Hook VA | New bytes | Target |
|---|---|---|
| `00D403A0` | `E9 EB 76 14 01` | `01E87A90` equip entry |
| `00605D41` | `E8 5A 1D 88 01 89 45 94 90` | `01E87AA0` capture |
| `00C4A0D0` | `E9 EB 68 24 01 90` | `01E909C0` draw wrapper |
| `00C4A647` | `E9 54 63 24 01` | `01E909A0` depth bridge |

Owner `01E66410`, 2,266 bytes; compositor base `01E7A4E0`, entry `01E7B400`;
context `01E87A30`; unchanged legacy core relocated to `01E66CF0`; unchanged
depth helper relocated to `01E87B20`. The protected state remains the exclusive
range `[01E60000,01E65000)`, outside every executable allocation.

The [binary report](evidence/dual-weapon-all-type-binary-20260905.json) verifies
the complete emitted owner and all relocations, unchanged legacy/depth bytes,
only four changed mapped hook regions, preserved unrelated mapped bytes/overlay,
and repaired WARP section/header bounds. The builder's stale 1,638-byte owner
assertion was removed; it verifies the full current emission and records its
size/hash. Candidate builds can select a separate DWCP/evidence path and restore
the normal runtime and WARP settings afterward.

## Verification and its limits

| Evidence | Result |
|---|---|
| [Owner machine code](evidence/dual-weapon-owner-20260905.json) | 596 cases, including529 class pairs,23 off-only classes and suffix/refcount/ABI failures |
| [Native reference geometry](evidence/dual-weapon-all-type-native-basis-20260905.json) | 576 off-only +672 dagger/dagger cases; zero differences beyond tolerance |
| [General source registration](evidence/dual-weapon-all-type-registration-20260905.json) | 48 dimension/scale/mirror mutations, plus seven rejection guards |
| [All-type compositor](evidence/dual-weapon-all-type-compositor-20260905.json) | 529 pairs in held/attack,23 off-only classes,17 real views in both roles;5,168 original-image checks;20 rejection guards;25 legacy-route checks |
| [Generic sword carrier geometry](evidence/dual-weapon-sword-carrier-20260905.json) | 288 held cases; maximum difference0.000122071 |
| [Native selector](evidence/dual-weapon-native-type-dispatch-20260905.json) | 434 class +98 item cases executing original selector/pair-mapper bytes |
| [NX regression](evidence/dual-weapon-all-type-page-protection-20260905.json) | Candidate8 transitions/19 native calls pass; archived crash reproduced at01E5F000 |

The class matrix deliberately reuses known weapon images to isolate admission;
it does not claim 529 combinations have real artwork. The real-view matrix uses
views1,2,6 and34..47, with their actual active ACT/SPR files. Source selection,
arithmetic and ABI evidence do not establish live anatomical grip contact for
new weapons. The payload also passes the profile/CRC gate and all4,096 virtual
page alignment residues. QJS remains UTF-8 without BOM and CRLF.

## Why every weapon still needs more work

The [complete active-archive audit](evidence/dual-weapon-type-coverage.json)
parses all four DATA.INI archives. Of201 declared single-weapon views,32 resolve
in the female Assassin family. Only17 meet the selected-source contract. Generic
Assassin families exist for dagger, sword, axe and katar; katar itself has missing
required attack cells and cannot be declared fully supported.

For mace1504, Lua view8 resolves `_클럽`. The first native lookup checks
`data/sprite/인간족/어세신/어세신_여_클럽.act`; this pair is absent. `D8A010`
builds ACT names, `D8A160` SPR names. A correctly authored matched pair would
load before the native8-to2 fallback. The [mace donor audit](dual-weapon-mace-asset-extension-20260905.md)
finds41 donor families, but none has one unambiguous registration across all16
selected source cells. Different identical-art witnesses imply different
translations. Copying one universal donor-job offset is not established by that
evidence.

The [native dispatch audit](dual-weapon-native-type-dispatch-20260905.md) proves
mace/knife selects body attack80, while the accepted combinations select88.
Furthermore, the generic sword body **and trail have no visible images in any
of their64 action88..95 cells**. A selector-only hook would therefore produce no
weapon packets for this compositor. Both a scoped valid dual carrier and
consistent body animation selection are needed before those attacks can work.

A maintainable completion path is per-resource/per-selected-image grip data,
an accepted body timeline, and an actor-owned carrier installed only when that
coverage is complete. Direct drawing from the job renderer is another viable
architecture, but it still needs those per-hand/per-frame registrations. The
existing coordinate tables describe weapon centers and packet deltas; they are
not a full anatomical hand-socket table for every job, gender and weapon type.
Neither this candidate nor the GM override fabricates that missing information.
