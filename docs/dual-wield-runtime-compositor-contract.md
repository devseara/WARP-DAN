# QJS Dual-Weapon Runtime Compositor Contract

> **Rejected and abandoned.** The synthetic-texture branch described below
> crashed in the native indexed texture resolver. Its successor
> [dual-wield-hand-layer-contract.md](dual-wield-hand-layer-contract.md) also
> failed live testing. Both documents are retained only as rejected-design
> evidence; no further QJS renderer is planned.

## Objective

Display each equipped weapon's original client SPR artwork while retaining the
stock ACT5 pair canvas, physical-hand ownership, whole-frame mirroring, and
ACT6 attack overlay. The implementation is QJS-generated x86 only. It must not
require a DLL, new GRF, item/job allowlist, or pre-authored item combinations.

## Proven 2025 Ragexe ABI

- Equipment update: `0x00D403A0`.
- Native weapon classifier: `0x00D8A1D0`, database `0x015FA3C0`.
- Canonical unordered pair mapper: `0x00D39130`, pair types `25..30`.
- ACT frame/layer: `0x0070F4B0` / `0x0070F390`.
- Final SPR image selection completes at `0x00605D41`.
- `CSprite` indexed/BGRA vectors begin at `+0x510` / `+0x51C`.
- Each selected image metadata object is 16 bytes: width/height words and a
  texture wrapper at `+0x8` for BGRA/direct textures.
- Texture manager singleton: `0x0125161C`; create wrapper: `0x00568620`.
- `CTextureDX9` vtable: `0x00FD7160`; surface pointer: `+0x130`.
- `CTextureDX9::Blit` is vtable slot 14 (`0x005699A0`) and calls
  `D3DXLoadSurfaceFromSurface` with independent source/destination rectangles.

## Placement model

The pair mapper is unordered, so weapon-class component order cannot own
equipment slots. A generated socket atlas converts the two canonical
components to physical main/off ownership for every:

`gender,pairType,phase,direction,frame,hand`.

Each eight-byte socket record stores signed ACT5-relative center offsets,
target mirror, pair sprite index, validity, and confidence. The atlas contains
3,072 records (24,576 bytes) per hand-resource family, independent of item
count. Custom jobs reuse their inherited `PCHands` family.

Original image center registration uses the live item ACT layer minus the live
generic single layer for that physical hand. The result is applied inside the
ACT5 texture canvas, never to actor/channel coordinates.

## Mirror and missing-art contract

The extracted numeric weapon corpus proves whole ACT5 mirroring is sufficient:
12,112 authored checks matched and zero mismatched. The 2,224 checks with no
authored original frame must use the untouched stock generic image.

## Runtime cache

A bounded direct-mapped cache keys synthetic metadata by main/off SPR pointers,
socket index, and selected original image pointers. Cache collision, unsupported
renderer backend, texture creation/blit failure, invalid dimensions, absent
artwork, low-confidence socket, or non-weapon off-hand must return the original
stock image pointer.

Synthetic images use the stock ACT5 canvas dimensions. Creation must clear a
transparent texture, clip both source/destination rectangles, blit original
textures through native `CTextureDX9::Blit`, then publish the cache key last.
No partially initialized metadata may reach the renderer.

## Hard gates

1. Stock ACT5 and ACT6 resources remain installed in actor slots.
2. Shields never enter compositor registration.
3. Main/off original SPR/ACT resources are retained only in the actor registry.
4. No texture is created outside channel 5 or outside pair types 25..30.
5. Every miss/failure returns the exact stock metadata pointer.
6. Imports remain unchanged; no dual-weapon DLL dependency appears.
7. Stale custom bridge operands remain zero.
8. Live acceptance covers both genders, idle/movement/attack, off-hand only,
   mixed/same-class pairs, missing original frames, relog, and device reset.
