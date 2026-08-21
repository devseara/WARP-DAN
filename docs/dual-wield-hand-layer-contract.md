# QJS Dual-Weapon Hand-Layer Contract

> **Rejected and abandoned (2026-08-21).** Live testing of build
> `7F877D0B8333AA4774A4249E4D71770C8D3FE0B6ECE1349B8CAD13B4842C1A1E`
> reproduced the same visible placement/art failure. Passing source, PE,
> relocation, import, mirror-oracle, and offline-preview gates did not prove
> the Ragexe runtime result. This document is retained only as rejected-design
> evidence; it is not an implementation plan.

## Objective

Show each equipped weapon's original client SPR artwork for off-hand-only and
dual-wield states without replacing the client's native weapon slots, creating
combination assets, importing a DLL, adding a GRF, or filtering by item/job ID.

## Proven 2025 Ragexe path

- Equipment update: `0x00D403A0`.
- Native item weapon classifier: `0x00D8A1D0`.
- Canonical pair mapper: `0x00D39130`, pair types `25..30`.
- Original item resource loader: the stock main-only equipment path.
- ACT frame/layer: `0x0070F4B0` / `0x0070F390`.
- Selected image capture: `0x00605D41`.
- Universal final native sprite draw: `0x00C4A0D0`, `thiscall`, six arguments,
  callee cleanup `ret 0x18`.

`ACT5` is a precomposed generic pair raster and `ACT6` is its attack overlay.
They are not main/off-hand slots. The patch must leave both resources installed
by the stock equipment updater.

## Ownership

The equipment hook runs the requested stock update first. It rejects shields
through the native classifier, temporarily invokes stock single-item loading to
obtain each original SPR/ACT pair, retains those resources, and replays the
requested stock state before returning. A bounded 256-row registry owns only
retained item and generic-reference resources. Main-hand-only equipment is not
registered or modified.

Registry collision, missing resources, failed classification, or an unsupported
pair leaves the actor entirely stock.

## Rendering

The image-selection hook records the current actor, channel, stock image, and
ACT layer after native resolution. The final-draw hook intercepts only when all
of these match a live registry row and the channel is exactly 5.

For off-hand-only, the stock packet center is already the authoritative native
off-hand placement. The replacement transfers only the original-item versus
generic-single ACT delta, item scale, mirror parity, rotation, metadata, and
the original SPR palette.

For dual wield, a compact socket table supplies the two physical-hand centers
for every gender, pair type, idle/attack phase, direction, and frame. These
sockets are derived from the deployed generic pair/single assets and contain no
item IDs. The only family-dependent sockets are female sword-containing pairs;
the runtime selects them from the loaded generic sword ACT fingerprint, never
from a job ID.

The hook prepares both hand packets before drawing. On complete success it
calls the original native renderer for off-hand then main-hand and suppresses
only that stock channel-5 pair draw. Any failure calls the exact original draw
once. `ACT6`, body sprites, effects, shields, and main-hand-only sprites are
never intercepted.

## Safety gates

1. QJS is UTF-8 without BOM, CRLF-only, and contains no DLL/GRF dependency.
2. `0x00D36EE4` and `0x00D37110` remain stock; no legacy action remap survives.
3. Equipment, image-capture, and final-draw hooks resolve inside the PE.
4. The final-draw trampoline replays the exact six-byte prologue and the
   handled bridge returns with `ret 0x18`.
5. COFF constant relocations are emitted as nested QJS arrays and resolve to
   addresses inside the embedded core allocation.
6. The 14,336-frame mirror oracle reports 12,112 authored matches, 2,224 safe
   stock fallbacks, and zero mismatches.
7. Imports contain no dual-weapon DLL and stale custom bridge operands are zero.

Run:

```powershell
python -B tools/verify_dual_weapon_hand_layer.py `
  --exe Outputs/dual_weapon_hand_layer_20250716.exe
python -B tools/verify_dual_weapon_compositor_mirror_contract.py
```

## Live acceptance

- male and female Assassin/Assassin Cross/Guillotine Cross/Shadow Cross;
- main-only, shield, off-hand-only, same-class, and mixed-class equipment;
- idle, movement, attack stance, and all eight attack directions;
- relog, map change, repeated equip/unequip, Alt+Tab/device reset, and exit;
- missing original frames must display stock generic art rather than disappear.
