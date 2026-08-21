# Dual-Wield Original Weapon Sprite Contract

## Current status

**Abandoned.** The final QJS-only hand-layer build
`7F877D0B8333AA4774A4249E4D71770C8D3FE0B6ECE1349B8CAD13B4842C1A1E`
passed static and offline gates but reproduced the same visible failure in the
live client. That live result is authoritative and rejects the implementation.

`AllowDualCustomWeaponSprites.qjs` has been restored to the verified 5.7 KB
zero-write fail-closed version (`4D52B89F...`). It does not change equipment,
ACT resources, hand placement, sprites, actions, or rendering. The accepted
behavior is the stock generic dual/off-hand artwork with native placement.

No further QJS implementation is planned. The previous slot, action, pose,
synthetic-texture, and final-draw designs remain documented only as rejected
research so they are not repeated.

## Proven native architecture

The unpatched runtime trace and the supplied screenshots establish the actual
resource roles:

- channel/ACT5 is the precomposed generic pair raster;
- both weapon silhouettes are already positioned inside that raster;
- channel/ACT6 is the attack overlay/trail, not an independent off-hand ACT;
- this is why an off-hand item can appear correct only during attack stance
  when it is incorrectly assigned to ACT6; and
- `PCHands.lua` and `weapontable.lub` select resource identity and filenames,
  but do not provide arbitrary item-pair hand geometry.

There is no native ACT5=main/ACT6=off mapping that can be enabled by swapping
resources.

## Rejected implementations

### Replacing original SPR/ACT pairs

Installing item SPR/ACT resources in channels 5 and 6 replaced the ACT5
composite and ACT6 overlay. That discarded native composite placement and put
weapons on the wrong hand.

### Replacing only SPR resources

Keeping generic ACTs while replacing only SPRs crashed at `0x00C40C41`.
Disassembly proves the renderer uses the ACT layer's `sprite_kind` and
`sprite_index` at `0x00605D1D..0x00605D39` to fetch SPR metadata. A generic ACT
index is not guaranteed to exist in an item SPR, producing the invalid pointer
later dereferenced by the draw routine.

### Treating ACT5/ACT6 as hand geometry

The stock-geometry/item-identity prototype preserved resource pairing but
still treated ACT5 and ACT6 as the two hands. Live screenshots disproved that
assumption: the primary weapon inherited composite-canvas placement while the
supposed off-hand looked correct only during the ACT6 attack overlay.

### Generated coordinate tables

The previous pose/origin/ownership compositor produced visibly incorrect
placement and was removed. Item/job allowlists and hand-offset guesses are not
acceptable substitutes for a proven generalized model.

## What a valid QJS solution requires

A generalized solution must retain ACT5's final composite pixel placement but
replace the two silhouettes independently. Evidence-backed options are:

1. a validated QJS compositor that derives both component registrations from
   the deployed pair and single ACT/SPR assets and proves them for every
   gender, action, direction, frame, and pair order; or
2. runtime creation of a replacement composite sprite containing both original
   item images while preserving the native composite canvas.

The second option requires sprite-image composition support that current WARP
QJS APIs have not demonstrated. The first must be accepted against native
assets and live screenshots before it can be enabled again.

## Pixel-compositor feasibility gate

The retained extraction contains 661 weapon files and three complete resource
families: Assassin, Guillotine Cross, and Shadow Cross. The new oracle evaluates
the final two-mask union for both genders, all six pair types, idle/attack,
eight directions, and every native frame.

```text
total frames:      4,032
exact rigid unions:   48
separated frames:  3,912
unseparated frames:  120
non-exact frames:  3,984
oracle SHA-256:
C947543EBFBBFE687702EBF954C660221A060277F7AE615CC8D10A76CABF2BA8
```

The 120 unseparated frames are consistent across all three families: male
dagger/dagger attack frames and male sword/axe idle/attack frames. A widened
96-candidate check of male sword/axe idle direction 2 frame 0 found a 72-pixel
native target versus a 195-pixel best two-single union, with 123 spill pixels
and zero exclusive axe pixels. This is clipped/re-authored pair art, not a
rigid composition whose missing hand position can be recovered.

Assassin female sword-containing attacks are even less rigid. The worst
sword/sword frames explain only 15.70% of the target with 19.17% precision,
leaving 247 residual and 194 spill pixels.

All 36 pair ACTs across the three families and both genders contain zero anchor
records. Shadow Cross body ACTs and original item ACTs contain only one anchor
per frame, not independent left/right hand anchors.

Therefore the hard gate rejects a generalized two-layer QJS compositor. A
complete implementation must create a replacement composite texture at runtime
and may need clipping/masking; coordinate-only layers cannot reproduce the
native art.

Static reverse engineering found a possible native texture path:

- `CSprite::LoadSPRFile` at `0x007282D0` retains per-image dimensions and
  packed CPU pixel data;
- `0x00729650` expands the client's packed indexed pixels;
- `CTexMgr::CreateTexture` at `0x005685A0` creates a texture from raw pixels;
- the texture manager singleton is `0x0125161C`; and
- the client imports `D3DXLoadSurfaceFromMemory` and
  `D3DXLoadSurfaceFromSurface`.

This is not an existing WARP QJS API. Implementing it safely requires a new
QJS-generated native subsystem for palette conversion, clipping/composition,
texture ownership, cache eviction, and device-reset reconstruction. It is not
authorized by the failed rigid-layer oracle alone.

## Fail-closed verification

The active QJS must contain no allocation or EXE write API. The PE gate proves
these sites remain byte-for-byte identical to the clean Ragexe:

```text
0x00D403A0 equipment entry
0x00D36EE4 first ACT-frame call
0x00D37110 second ACT-frame call
0x00605CD9 final ACT-layer call
```

Run:

```text
python -B tools/verify_dual_weapon_sprite_only.py
win32/WARP_console.exe -using "profiles/2025-07-16 PROFILE MAIN.yml"
python tools/fix_custom_bridge_iats.py <patched.exe> --dll cps.dll --write
python -B tools/verify_dual_weapon_sprite_only.py --exe <patched.exe> --original <clean.exe>
```

Current safe Profile Main SHA-256:

```text
C40A90F65D779931405D089C230119E66F9C53337D49C60C914939555730ED22
```

This build is byte-identical to a Profile Main variant with
`AllowDualCustomWeaponSprites` removed from the selection list.
