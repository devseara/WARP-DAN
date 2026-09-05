# Original mace asset extension audit — 2026-09-05

The accepted coordinate correction does not supply missing weapon artwork or
registration data. Item 1504 has view 8 (`WEAPONTYPE_MACE`). The active archives
contain 41 female job families with matching original club ACT/SPR pairs, but
no female Assassin club pair. A generic sword appearing for the mace is a
native generic carrier, not proof that the original club pixels were
loaded and then drawn with the wrong rotation.

This audit changes no game resources or executable. It uses the accepted EXE
`0bb06dbc84d9e0a5df4fb3002b8946388d00158576ef18be74b3fbff754d4509`.

## Native fallback: what needs changing

The native `thiscall` function at `0x00D42790`, returning with `RET 4`, remaps
views 7 and 8 to view 2 for Assassin and Assassin Cross. The read-only audit
executes the actual function and its jump tables for 12 jobs and 23 input views;
only its actor-job getter is replaced with an ABI stub. For job 4013 the changed
values are exactly `7 -> 2` and `8 -> 2`.

During **solo original-resource acquisition**, the remap is **after** the
first original-view ACT existence check. The stock dual carrier uses a separate
generic pair path; supplying an original club asset does not change that path.

| Native VA | Operation |
| --- | --- |
| `0x00D40C3B` | Build original-view ACT path through `0x00D8A010` |
| `0x00D40C5A` | Test that original-view ACT resource |
| `0x00D40C61` | Branch to fallback when it is absent |
| `0x00D40D6A` | Call job-dependent `0x00D42790` view remap |
| `0x00D40D8E` | Build generic ACT path using the remapped view |
| `0x00D40DAA` | Test the generic fallback ACT resource |

The extension table independently proves these roles: `[0x01227310]` contains
`78 15 01 01`, pointing to `0x01011578 = "act"`; `[0x01227314]` contains
`D8 1E 01 01`, pointing to `0x01011ED8 = "spr"`. `0x00D8A010` supplies index 0,
while `0x00D8A160` supplies index 1. Both wrappers use the same filename builder.

The original-view lookup is not automatically an `_1504` filename. At
`0x00D60DE0`, the client calls `ItemInfoGetter(itemID)`, reads field `+0x40`,
and passes that view to Lua `ReqWeaponNameByClassNum`. The active
`weapontable_f.lub` returns `WeaponNameTable[classNum]`. For item 1504/view 8,
the first female Assassin candidate is therefore:

```text
data/sprite/인간족/어세신/어세신_여_클럽.act
```

Providing this correctly registered ACT and its matching `_클럽.spr` can satisfy
the first lookup before the 8-to-2 solo fallback. Merely loading a club into a donor
job directory does not do that. A global patch to the view remapper is not
necessary just to make this first original path load; its other callers also
need separate analysis before changing it.

## Can the existing assets determine a complete mace transform?

The finite accepted dual rig selects 16 unique original-source cells:

```text
held:   actions 32..39, frame 0
attack: actions 80,81,86,87, frame 4
        actions 82,83,84,85, frame 0
```

Its 224 target hand rows reuse and transform these selected cells. This is
smaller than the complete native animation timeline; success here would not
establish every body action or solo attack frame.

The new audit checks all 41 club donors against the 18 declared single-weapon
resources present in the female Assassin family. It matches the actual visible
RGBA pixels exactly under mirror/quarter-turn transforms, retaining transparent
canvas offsets. It compares the same source action and frame, and does not
silently pick a majority transform when references disagree.

**No donor has a single unambiguous exact-art registration for all 16 cells.**
Knight, Rune Knight, and Dragon Knight are the best direct donors: each has
12 uniquely registered cells and four conflicting held cells, in directions
0, 1, 6 and 7. Dragon Knight action 32/frame 0 illustrates the problem:

| Identical reference art | Donor-to-Assassin translation |
| --- | --- |
| Generic dagger | `(4, 2)` |
| Item resource 1144 | `(5, 3)` |
| Item resource 1142 | `(5, 4)` |
| Item resource 1123 | `(6, 4)` |

Every row is supported by exact visible pixel correspondence. The distinct
translations prove that these references do not define one universal job-space
offset. Selecting one is an explicit registration choice, not a uniquely
recovered answer. Even a unique reference-image match establishes that image's
transform; it does not identify the club's anatomical grip or blade axis.

Undeclared custom weapon sprites are deliberately excluded. Some contain copied
ACTs across job families and can create apparently complete bridges without
demonstrating that those ACTs were registered to each native body.

## Bounded implementation

A practical first extension is the original club SPR with explicit registration
for the finite accepted Assassin rig. Preserve its complete original SPR bytes
and hash, and author metadata or ACT transforms. The required record should
identify the source resource fingerprint, selected image kind/index, local grip
point, orientation axis, target physical hand, target action/direction/frame,
and source-cell mapping. It should retain the native packet edge conversion and
far-endpoint `+1` behavior established by the accepted fix.

There are two reasonable asset interfaces:

1. Install an Assassin-named club ACT/SPR pair. Keep the donor SPR byte-identical
   and give its ACT the Assassin timeline and explicit per-cell registration.
   Native loading can then acquire the original view before fallback. Register
   the generated ACT fingerprint so it cannot silently share another profile.
2. Have the owner acquire an explicit donor resource path and let the compositor
   use separate source-image/grip records. This avoids copying the SPR into each
   job directory, but requires resource lifetime handling and a path/view/profile
   registry. The donor's ACT coordinates are not accepted automatically.

Neither requires baking a weapon into the body SPR. The reusable rendering
interface is two target hand sockets plus per-selected-image grip/orientation
metadata. A single body ACT anchor cannot represent both hands. For weapon types
whose stock artwork contains multiple physical pieces, the profile must also
specify the layer/hand split; counting a paired katar bitmap as one clean weapon
would otherwise duplicate its second piece.

For mace, the next concrete review is the four selected original club images
and the 16 source registrations, followed by both hand orders, off-hand-only,
eight directions, held frames and the accepted attack sequence in the client.
Additional native phases need explicit coverage rather than frame wrapping or
nearest-frame guesses.

## Limits for all weapon types

The earlier exact-art closure reaches held directions for 14 of 23 declared
generic types, but contains inconsistent edge transforms and cycles. It is a
candidate discovery result, not a calibration table. Knuckle, instrument, whip
and gun families do not acquire verified Assassin grips from those bridges;
they need explicit image/hand registration or suitable authored resources.
The server's permission to equip an item and the client's ability to load its
view are separate from correct placement and animation.

The runtime can support arbitrary permitted view IDs through a data-driven
profile registry. Claiming every weapon visually correct additionally requires
the missing resource profiles and their live acceptance. Reusing the accepted
dagger/sword transform for every remaining type would conceal that missing work.

## Reproduction and evidence

```powershell
.venv\Scripts\python.exe -X utf8 -B tools/audit_dual_weapon_mace_retarget.py
```

The [machine-readable result](evidence/dual-weapon-mace-retarget-20260905.json)
records all donor cells, alternative transforms, exact pixel hashes, source
archive identities, the inspected executable hash, the native remap matrix and
the relevant instruction bytes. The tool does not modify the EXE, ACTs, SPRs,
GRFs, or Lua tables. Pixel correspondence and emulator execution are explicitly
separate from live visual acceptance.

## Post-deployment missing-mace report

After installing EXE `91b1690045634a07dae3b09c52a5564b8ae7895b16e53b1bb9235b2ed6bedeb8`,
the user supplied a screenshot showing the equipped mace absent from the world
weapon display. A fresh read of every active archive and loose resource path
confirms that both male and female Assassin `_클럽.act/.spr` pairs are absent
from `update.grf`, `maindata.grf`, `spritedata.grf` and `data.grf`.
All four archive indexes parsed successfully. Dagger, sword, axe and the paired
katar resource family exist; the latter is not a general two-weapon grip profile.
See [the fresh path evidence](evidence/dual-weapon-mace-missing-assets-after-deployment-20260905.json).

No Ragnarok process was running during this inspection, so this record does
not claim a new live registry capture. The installed file hash was verified.
The code and asset facts explain the limitation: the original-view mace path
cannot load, native acquisition falls back, and the owner intentionally refuses
to label mismatched fallback artwork as an original mace. This is expected
missing-asset behavior in the incomplete extension, not new visual acceptance.
