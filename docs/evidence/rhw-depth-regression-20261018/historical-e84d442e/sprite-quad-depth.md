# Sprite quad RHW and floor depth (2025-07-16 Ragexe)

Runtime contract for `UniformSpriteRHW` (ID 388) and `FloorSafeSpriteDepth`
(ID 389). Both are build-specific to the profiled 2025-07-16 client, are
selected in `profiles/2025-07-16 PROFILE MAIN.yml`, and fail closed on any
signature mismatch. Static RE, cave emulation and WARP exports pass. The user
accepted both live on 2026-10-12 with the signed MAIN build
`2025-07-16_Ragexe_riftlock_main.exe` (SHA-256
`BB3094171AC7969474753D5865D43C647D1FA74178681FAE8C1C9F66EBF0B640`, Riftlock
release 1791789858). Head/collar alignment held across zoom, and boots and
shadow were no longer sliced by the floor. Any change to these hooks or the
shared emitter needs a fresh live pass.

## Native pipeline

| Address | Role |
| --- | --- |
| `0xC48F60` / `0x604AA0` | NPC/monster and player layer loops; call actor vf0x24 |
| `0xC40C20` | `CRenderObject::vf0x24` layer rect builder (36 classes) |
| `0xC49D20` | Shadow builder (`shadow.spr/act`), emitted via `0xC4A670` (180°) |
| `0xC4A0D0` | Quad emitter: rect + angle → 4 pretransformed vertices |
| `0x550B10` | Render-list submit; alpha sort key `(v0.rhw+v1.rhw)/2` or `v0.rhw` |
| `0x553E80` / `0x556790` | S = hpc/(7z); `hpc = vpc = (h/2)/tan(7.5°)` |

Layer edges are `screen + (layer + attach) * S * layerScale * actorScale`, one
S per actor, so positions scale exactly with zoom. Each rect row also gets a
synthetic depth `z_v = z + 0.16 * (y - anchorY)` (0.06 on one flag path;
reversed `z - 0.16 * ...` when `[actor+0x9C]` is set) and RHW = 1/z_v plus the
stock contact bias `(actor[0x80] + 3 + arg) * 9e-6 + S/1.34 * 3.6e-5`. The
emitter stores top RHW in v0/v1, bottom RHW in v2/v3, and converts the same
values to per-vertex Z through `0x554040`.

Both DX7 and DX9Ex renderers are fixed-function with XYZRHW vertices. There
are no vertex or pixel shaders. ZENABLE is only set to 0/1, never USEW, and
FOGTABLEMODE to NONE. Depth therefore comes from Z only; RHW affects only
perspective-correct texture interpolation and the client's own alpha sort.

## UniformSpriteRHW: zoom texture warp

With different top/bottom RHW, D3D samples each screen rectangle
perspective-correct, so artwork slides down inside the quad. Edges stay pinned.
The relative tilt grows roughly with S², and the slide grows with distance from
the quad edges. Padded 2x HD canvases drift against tight native head quads.
V16 idle model (`tools/sprite_rhw_warp_model.py`): 1.69x zoom leaves a +7.4 to
+12.4 close-px head-high residual, matching the photographic 10–12 px. A tight
crop would show about 1 px.

Fix: NOP `0xC4A5B1 F3 0F 10 55 E0`, so v2/v3 reuse the native top RHW. XY, UV,
color, Z and sort keys are bit-identical; texture mapping becomes affine.
Coverage was proven by caller census. Every emitter primitive is a 2D screen
rectangle. Its 34 direct calls plus 5 shadow-wrapper calls resolve, via RTTI,
to players, NPCs, hallucinations, afterimages, items, icons, shadows,
CAbleToMakeEffect and CEffectPrim sprites. GND, RSM, water, screen-STR and UI
use other builders and must stay perspective-correct. This replaces the former
ClanBodySkins-only bridge at `0xC4A63E`; that site is stock again. The
dual-weapon helper behind `0xC4A647` writes only Z.

Verify: `python tools/verify_uniform_sprite_rhw.py`. Alone it changes 5 bytes;
with ClanBodySkins both orders give the same hash; it composes with
AllowDualCustomWeaponSprites.

## FloorSafeSpriteDepth: floor slicing below the feet

Rows below the anchor sink behind the floor in front by
`(0.16 + z·cotθ/vpc)` per screen pixel. Only the stock bias protects them. That
bias is constant in RHW, so the protected band shrinks quickly at close zoom,
low camera pitch and low resolution. Native female Mage sit frames reach
+12 px below the anchor and V16 matches them within ±0.5 px. The live boot and
shadow slice is therefore stock behaviour, not an art or anti-warp regression.
The shadow is built with the reversed tilt and drawn 180° about the anchor, so
its lower half sinks the same way.

Fix (two hooks plus one 0xA0-byte cave):

- `0xC40F9F` (replays `subss xmm5,[ebp+0x1C]`). On the +0.16/+0.06 paths, for
  `CPlayer 0x1094810`, `CPc 0x10943A8`, `CNpc 0x10939D4`,
  `CCharacterNpc 0xFD8CE8`, `CHalluPC/PC2/NPC` and `CBlurPC`, it clamps
  `(bottom - anchorY)` and `(top - anchorY)` to <= 0. `pushfd/popfd` preserves
  the `cmp [edi+0x9C],0` result for the native `je` at `0xC40FA4`, and EAX is
  preserved.
- `0xC49FEE..0xC4A003` (replayed). Both pre-rotation shadow offsets are
  clamped to >= 0 before `* 0.16`.

Rows below the anchor keep the anchor plane, so only the floor slope remains
against the stock bias. That is roughly 2–4x more clearance; exact ground-plane
contact would need the view matrix. Rows above the anchor are unchanged, and
the stock bias is kept. The anchor-line depth of affected quads moves forward
by roughly 0.16·h_up·h_dn/(h_up+h_dn) world units, which is below the stock
bias. Effects (`CGndRiser`, `CMandraAttackEffect` and others), items, corpses
and the reversed 0x9C path stay stock. Shadow sort keys move to the anchor
plane, which is still behind the actor's own layers.

Verify: `python tools/verify_floor_safe_sprite_depth.py`. It covers static
signatures/vtables, 66 body and 3 shadow emulation cases per export, and
exports alone, in both orders with UniformSpriteRHW, and stacked with
ClanBodySkins, AllowDualCustomWeaponSprites and AllHatEffectsWorldDepthOracle.
`--exe <client>` re-emulates a built client.

Regression checks: sitting/walking soles and shadow at max zoom and low pitch;
characters directly behind walls or obstacles; slopes, stairs and water; party
members overlapping; ground skills, items and spike effects unchanged.
