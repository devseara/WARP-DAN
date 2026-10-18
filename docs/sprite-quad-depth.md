# Sprite quad RHW and floor depth (2025-07-16 Ragexe)

WARP-DAN compatibility (2026-10-18): existing profiles retain the clan-only
perspective bridge. Selecting `UniformSpriteRHW` replaces it in either patch
order; removing that patch restores the legacy bridge. Saved deployment
profiles are preserved. See [upstream integration](upstream-sync-20261018.md)
for the local merge and validation details. The upstream release descriptions
below refer to their explicitly selected universal-fix configuration.

Runtime contract for `UniformSpriteRHW` (ID 390) and `FloorSafeSpriteDepth`
(ID 391). Both are build-specific to the profiled 2025-07-16 client, are
selected in `profiles/2025-07-16 PROFILE MAIN.yml`, and fail closed on any
signature mismatch. Static RE, cave emulation and WARP exports pass. The user
accepted both live on 2026-10-12 with the signed MAIN build
`2025-07-16_Ragexe_riftlock_main.exe` (SHA-256
`BB3094171AC7969474753D5865D43C647D1FA74178681FAE8C1C9F66EBF0B640`, Riftlock
release 1791789858). Head/collar alignment held across zoom, and boots and
shadow were no longer sliced by the floor. Any change to these hooks or the
shared emitter needs a fresh live pass.

## Main integration - 2026-10-18

The original `e84d442e` implementation reached only the historical release
branch through `388e5c3d`. Current main had neither patch, and its signed
client retained stock emitter/depth instructions. The missing fixes explain
the recurring zoom warp on standard HD Mage/Fox bodies; the old clan-only
bridge excluded those resource paths. The complete feature is now merged
into main with IDs390/391, preserving GrayMap388 and CelestialDial389.
The retired classic-NPC profile stays deleted; MAIN selects both fixes.
Historical binary and branch evidence is in
`docs/evidence/rhw-depth-regression-20261018/`. The earlier live acceptance
is evidence for the old release; a rebuilt or upgraded client needs new live
zoom, head-contact, floor/wall and effect checks.

CelestialDial now registers its player-draw wrapper in its WARP cache contract.
FloorSafeSpriteDepth accepts that exact registered CPlayer owner while keeping
the native vf0x24 requirement and rejecting unknown draw owners. Both patch
orders are verified; the native weather wrapper is never replaced.

`tools/verify_uniform_sprite_rhw.py` also gates the active profile, catalog IDs,
tree entries and legacy-owner removal. `tools/verify_sprite_depth_rejections.py`
checks bad emitter/body/shadow signatures and an unknown player vtable.
`tools/verify_sprite_depth_celestial.py --out <new-folder>` exports both weather
orders with the required controller assets. Use the Python environment containing
Unicorn for `tools/test_celestial_sun_shadow.py` native execution checks.

`tools/upgrade_sprite_quad_depth.py --source <client> --out <new-folder>` builds
a separate upgrade while comparing all original PE section bytes. It retires
only the positively identified old clan hook, preserves the registered weather
owner, and adds the two renderer fixes. Existing weather-hook support is pinned
to the audited signed input hash, not an arbitrary vtable pointer. Unknown
prepatched owners fail closed. `tools/release_sprite_quad_depth.py install verify`
is the2026-10-18 paired EXE/manifest/signature release entrypoint, with a closed-
client check, rollback checkpoint and independent manifest verification. It
does not modify GRFs or sprite artwork.

### Installed current-client upgrade

**Crash correction,2026-10-18:** the `601fa320...` upgrade below is rejected.
Its caves were placed inside CelestialState's zero-filled globals and a native
reset overwrote the shadow entry. The exact user null-read crash is reproduced.
The corrected installed client is
`83c027c36c7a0fef5126af25ac88747084fd6248cb72c478070bd47b8f0fd65b`.
Its caves are in a separate `.rhwfix` section outside all original mapped
sections. Native reset/map-update-then-render checks now pass. Details and
release verification are in
`docs/evidence/sprite-depth-state-overlap-20261018/`. The previous483-case
static/order tests did not cover mutable runtime ownership and did not clear
that crash. Retest the corrected release in game before live acceptance.

Source integration is on main through merge `8a624947` and compatibility/
regression commit `a98bbbfb`. On2026-10-18 the current signed
`2025-07-16_Ragexe_175220998_clientinfo_patched.exe` was upgraded in place
from SHA-256 `5d1d4faf3065a27655e9404357af8beb697ede907959fa9c39ccc15aba3cbc36`
to `601fa320dceb31f016649d8183f8f8604668901acc5f81caf25d0a15d6fcce00`.
The two renderer fixes are present, the old clan hook is retired, and the
Celestial player-draw wrapper plus all other existing PE section bytes were
preserved. All GRFs, DLLs and DATA.INI remain byte-identical. Riftlock signing
and an independent complete asset-manifest comparison pass.

`Outputs/sprite-depth-main-20261018/deployment/before/` holds the previous EXE,
manifest and signature as a paired rollback checkpoint. Verification is in
`docs/evidence/rhw-depth-regression-20261018/installed-release.json`.
The source/export matrix covers11 scenarios plus the current-client upgrade,
483 body/shadow emulation cases, four bad-input rejection gates and three
native weather-shadow execution checks. These are offline results; new live
zoom, collar/headgear, floor/wall and effect acceptance is still pending.

## Native pipeline

| Address | Role |
| --- | --- |
| `0xC48F60` / `0x604AA0` | NPC/monster and player layer loops; call actor vf0x24 |
| `0xC40C20` | `CRenderObject::vf0x24` layer rect builder (36 classes) |
| `0xC49D20` | Shadow builder (`shadow.spr/act`), emitted via `0xC4A670` (180Â°) |
| `0xC4A0D0` | Quad emitter: rect + angle â†’ 4 pretransformed vertices |
| `0x550B10` | Render-list submit; alpha sort key `(v0.rhw+v1.rhw)/2` or `v0.rhw` |
| `0x553E80` / `0x556790` | S = hpc/(7z); `hpc = vpc = (h/2)/tan(7.5Â°)` |

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
The relative tilt grows roughly with SÂ², and the slide grows with distance from
the quad edges. Padded 2x HD canvases drift against tight native head quads.
V16 idle model (`tools/sprite_rhw_warp_model.py`): 1.69x zoom leaves a +7.4 to
+12.4 close-px head-high residual, matching the photographic 10â€“12 px. A tight
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
`(0.16 + zÂ·cotÎ¸/vpc)` per screen pixel. Only the stock bias protects them. That
bias is constant in RHW, so the protected band shrinks quickly at close zoom,
low camera pitch and low resolution. Native female Mage sit frames reach
+12 px below the anchor and V16 matches them within Â±0.5 px. The live boot and
shadow slice is therefore stock behaviour, not an art or anti-warp regression.
The shadow is built with the reversed tilt and drawn 180Â° about the anchor, so
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
against the stock bias. That is roughly 2â€“4x more clearance; exact ground-plane
contact would need the view matrix. Rows above the anchor are unchanged, and
the stock bias is kept. The anchor-line depth of affected quads moves forward
by roughly 0.16Â·h_upÂ·h_dn/(h_up+h_dn) world units, which is below the stock
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
