# Original weapon grips and anatomical equipment hands — 2026-09-05

Status: superseded after the user reported hand overlap and preferred the old attack motion. See [old motion and pixel-edge contacts](dual-weapon-edge-contacts-20260905.md).

[Deployment record](evidence/dual-weapon-pixel-grips-deployment-20260905.json) records the exact target, verified hash and retained `_before_pixel_grips_c2e857e3.exe` backup.

The user accepted the general dagger/sword/axe result in `c2e857e3...eeb02`,
then reported floating hilts and reversed equipment hands. That acceptance
does not accept the new pixel-grip build described here. Drake weapons are
explicitly excluded at the user's request.

## What was wrong

The previous C compositor registered native **bitmap centers**, assuming the
solo ACT registration also registered each hilt. The input CSV's 48 grip rows
contained identity offsets; they were not measurements of painted handle pixels.
A Zeny Knife loop, a sword handle and an axe shaft therefore could miss the
same fist by different amounts. A single X/Y correction cannot solve this.

The compositor also sorted resources by dagger/sword/axe class. Furthermore,
the native ACT mirrors the same arm drawings in opposite directions. Reference
role0/role1 are not invariant anatomical right/left hands. The old views45/34
legacy bypass could skip corrections entirely. The new held/dual path removes
that bypass and assigns equipment slots before preparing the two draws.

Read-only [live baseline](evidence/dual-weapon-grip-before-live-20260905.json):
EXE `c2e857e3e9d63b510f8b7f31015f821f951aab5033aeb404806acb1751eeeb02`,
actor items `[1238,13412]`, views `[34,45]`, gender0, held action39. The body
resources resolve to the female Assassin Cross ACT/SPR. The live screenshot
inspection confirmed the Zeny Knife gap; it was not inferred solely from a test.

## Generic sprites projected onto the existing body

The user's proposed check is implemented in
[render_dual_weapon_native_overlay.py](../tools/render_dual_weapon_native_overlay.py).
It loads the active generic pairs25–30 and the exact female Assassin Cross body,
executes the original PE's `0x00C40C20` packet producer, and draws their original
pixels in a review atlas. The six held pair atlases include all eight directions;
pair28 comparisons include all six held and eight dual-attack frames. Adjacent
direction pairs share body pixels. Candidate panels use packets emitted by the
compiled x86 compositor, not a second implementation of its placement formula.

[Animated review](../Outputs/dual_weapon_native_overlay/review.html),
[generic pair28](../Outputs/dual_weapon_native_overlay/stock-pair28-all-directions.png),
[native overlay records](../Outputs/dual_weapon_native_overlay/native-overlay.json).

This revealed that several inherited blade angles also differed from the
generic dual art. The candidate therefore measures each visible pair28 blade's
axis directly from its original SPR pixels. The established common pair28 pose
convention is retained for the supported originals; the six native pair shapes
are inspection references, not six newly authored independent runtime rigs.

The review uses CPU nearest-neighbor sampling and draws the body before the
weapon layers. It omits the head to expose the arms. It does **not** simulate
the native GPU's depth/occlusion or certify live acceptance. Some attack images
contain only a blade fragment: its axis is measurable, but a hidden hilt is not
invented. The existing terminal role0 visibility remains explicit.

## Pixel data and scope

[Authored landmarks](../Inputs/DualWeaponAuthored/grips/female-assassin-pixel-landmarks.json)
contain per-image handle centers and tips, body fist contact pixels, generic
blade-axis points, and pinned source ACT/SPR hashes. Texel coordinates are
zero-based; their projected center uses `pixel + 0.5`. Loop handles may surround
an unpainted center, so handle-neighborhood validation is separate from the
requirement that blade-axis/tip endpoints lie on real painted pixels.

| Original view | Resource suffix | Class |
| --- | --- | --- |
| 1 / 2 / 6 | generic dagger / sword / axe | 1 / 2 / 6 |
| 34 / 35 / 36 / 37 / 38 | 1238 / 1239 / 1240 / 1144 / 13049 | dagger |
| 39 / 40 / 41 / 42 / 43 / 44 | 1119 / 1122 / 1123 / 1126 / 1142 / 1143 | sword |
| 45 / 46 / 47 | 13412 / 13413 / priest sword | sword |

All **92 SPR images** in those 17 non-Drake resources were exported and inspected.
The existing exact source selection uses **68 full weapon images**: four per
view. The remaining 24 are partial art outside those selected cells; they receive
no fabricated full-weapon hilt/tip. The [profile report](evidence/dual-weapon-grip-profile-20260905.json)
enumerates every image, dimensions, hashes and status.

The current body profile covers held32–39, frames0–5, and dual attack88–95,
frames0–7: **112 cells**, using 28 unique unmirrored body bitmaps. Their mirrors
produce 56 distinct rendered body poses. Main/right owns reference role0 in
directions0/1/4/5 and role1 in directions2/3/6/7; off/left owns the opposite.
Off-only held weapons always use that off/left socket, regardless of type.

This is the **female Assassin Cross body** profile, verified by the current
ACT and SPR filenames, layer/image index, dimensions, coordinates, mirror,
angle and scale. Other body profiles are not admitted by this new held/dual
path. Drake600–606 and unknown views do not borrow another weapon's grip.
Only classes1/2/6 remain allowed. Off-only **other native phases**, including
solo attack80, retain the inherited resource path; they have not acquired
these held/dual sockets. Native attack80 and dual88 are not interchangeable.

## Placement contract

1. Recover the current native actor origin and scale from the incoming stock
   channel5/6 packet. Remove the far-edge `+1` before recovering scale.
2. Project the annotated body texel through that frame's native mirrored
   rectangle, preserving the native `+1` endpoints and actor rotation.
3. Project the measured generic blade-axis vector through its native pair28
   rectangle. Derive the final weapon angle from this axis and the selected
   original image's grip-to-tip vector, including reflection and scale.
4. Set `weapon_center = projected_body_grip - rotated_weapon_grip_offset`.
   Draw the original SPR image with its original palette. No GRF, body bitmap,
   ACT resource, real item field or texture is modified.

The freestanding `atan2` approximation range-reduces to `|z| <= tan(pi/8)` and
uses the alternating series through `z^19`. It introduces no CRT/import.
The emitted x86 angles are tested against independently projected native
generic endpoints, not against this approximation copied into Python.
Both hands prepare successfully before either draws; current depth/color and
the existing depth helper remain intact. Channel5/6 ownership avoids duplicate
draws. Neither channel is itself an equipment hand.

## Proof and its limits

[x86 execution report](evidence/dual-weapon-pixel-grips-execution-20260905.json):
**17,818 cases / 31,012 original-image draws**, all 68 selected images, both
slots, all held/dual cells, two zooms, actor rotations0/15/-90, all three off-only
held carriers, same-image duals, class/family/view/source guards and a legacy
bypass sentinel. Maximum projected grip-to-body-texel distance is
**0.000204 screen pixels** (rounded up). Blade-axis error must be below
0.001 degrees against execution of native C40C20 on the generic source.
Nine class pairs pass and the other520 reject.

These numeric tests prove the projection and selected-image/slot contract.
They do **not** turn manual palm/hilt annotations into independently proven
anatomy or replace live visual review. The old legacy-equality verifiers are
historical oracles for `0bb...`/`c2e...`; equality with their type-sorted centers
is intentionally no longer the acceptance condition.

The owner passes 596 cases. The [native producer check](evidence/dual-weapon-pixel-grips-projection-20260905.json)
passes192 cases and matches146 valid captured layers/300 anchors. The
[page-protection regression](evidence/dual-weapon-pixel-grips-page-protection-20260905.json)
reproduces the old NX crash at `0x01E5F000` and completes all eight transitions /
19 native equipment calls on this candidate without it. QJS profile selection,
payload CRC/missing-file guards, and all4096 state-page alignment residues pass.

## Candidate binary and exact addresses

[EXE](../Outputs/dual_weapon_grip_placement/client-pixel-grips.exe), SHA-256
`95674dbae0b470c7cef7eade9580dea06038f337228d5f10753f1d73ff5d4220`.
[DWCP](../Outputs/dual_weapon_grip_placement/compositor.dwcp), SHA-256
`d4cf89876727a28d4c8fd4f6fce3249016c5c5cc310eca67d10453ad04be813c`.

| Hook VA | Exact bytes | Target VA |
| --- | --- | --- |
| D403A0 | `E9 FB 96 14 01` | 1E89AA0 |
| 605D41 | `E8 6A 3D 88 01 89 45 94 90` | 1E89AB0 |
| C4A0D0 | `E9 FB 88 24 01 90` | 1E929D0 |
| C4A647 | `E9 64 83 24 01` | 1E929B0 |

Compositor base/entry: `1E7A4F0` / `1E7B6E0`; context `1E89A40`;
equipment owner `1E66410` (2284 bytes); depth helper `1E89B30`.
RW state stays isolated at `[1E60000,1E65000)`; trampolines stay executable.
The [binary verifier](evidence/dual-weapon-pixel-grips-binary-20260905.json)
checks the entire relocated compositor/data and equipment owner, four mapped
hook edits, unchanged remaining mapped sections/overlay, stock frame call,
legacy/depth bytes, headers, section bounds and all emitted code outside RW state.

Reproduce from the repository root:

```powershell
.\.venv\Scripts\python.exe tools/build_dual_weapon_grip_profile.py
.\.venv\Scripts\python.exe tools/build_dual_weapon_compositor.py --output Outputs/dual_weapon_grip_placement/compositor.dwcp
.\.venv\Scripts\python.exe tools/verify_dual_weapon_pixel_grips.py --exe Outputs/dual_weapon_grip_placement/client-pixel-grips.exe
```

## Correction to the earlier documentation

`dual_socket_extract.py` extracts layer1 **pair-guide origins**, not body hand
sockets. Its CSV remains a historical artifact and is not input to the new
pixel-grip runtime. The accepted artifact's “main/off” layer labels describe
reference weapon roles; they do not prove anatomical equipment ownership after
the body ACT mirrors. The [job-sprite audit](dual-weapon-job-sprite-audit-20260905.md)
already distinguished these concepts; this implementation now makes that
distinction explicit in separate image-grip and body-contact data.
