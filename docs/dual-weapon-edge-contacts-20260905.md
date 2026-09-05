# Old attack motion and visible hilt contact — 2026-09-05

Status: installed at the existing client path; live visual acceptance is pending. The [deployment record](evidence/dual-weapon-edge-contacts-deployment-20260905.json) pins the installed hash and retained backup.

The user rejected the hand overlap in `95674dba...d4220`, viewed the old versus
new attack GIF, and chose the old animation with visible hilt-to-hand edge
contact. This supersedes the palm-center and generic-axis placement policy in
[the previous grip report](dual-weapon-grip-placement-20260905.md).

## Why the latest update felt too close

It did more than remove a hilt gap: it aligned the measured handle center to a
palm point and derived a new blade angle from generic SPR pixels. Applying this
to dual-attack frames also pulled intentionally detached slash images toward
the hands. Numeric agreement with the chosen palm points did not establish the
visual boundary contact the user wanted.

The archived `c2e857e3...eeb02` C compositor, real legacy callback and embedded
rig were checked against the archived EXE bytes and executed to produce the
[old versus current attack GIFs](../Outputs/dual_weapon_attack_comparison/review.html).
All 64 direction/frame cells of each build were rendered from original pixels.
The GIFs use 180 ms/frame for inspection; this is not a measured live ASPD.
The head is omitted and CPU drawing does not simulate native GPU depth.

## Current contract

- Dual attack88–95: restore the accepted reference packet trajectory, source
  frame/image, angle, mirror, order and hidden slash cells through
  `prepare_reference`. Detached attack art is not snapped to body contacts.
- Held32–39: retain the old rig angle and source selection. Project a measured
  boundary in the weapon texture onto a measured boundary in the local fist
  silhouette. A texture-edge coordinate does not receive the texel-center
  `+0.5`; the native producer's far-edge `+1` remains unchanged.
- Equipment slots still own anatomical right/left hands across native body
  mirroring. Restoring the old animation does not restore class-based resource
  sorting. Directions0/1/4/5 assign main to reference role0; the other four
  assign main to role1. Off uses the opposite role, including off-only held.
- Original images and palettes remain intact. No GRF, body sprite, server
  source or server executable is changed. Drake 600–606 remain excluded.

This remains the exact female Assassin Cross body profile, 17 non-Drake weapon
views and classes 1/2/6. The index and dimensions of the selected original image
must match the generated contact record. Other jobs/genders are not enabled.
Off-only phases outside held32 retain the inherited native path; solo80 is not
reinterpreted as dual88.

## Boundary measurement and limits

[The generator](../tools/build_dual_weapon_edge_contacts.py) runs an explicitly
marked, offline-only build with the old rig angle and palm-centered initial
registration. For each view/direction/frame/hand it reads opaque source pixel
squares and finds their first separating contact while moving outward from the
measured grip toward the weapon's opaque-pixel centroid. The latter handles
recessed cleaver handles without treating their tip axis as the only permissible
translation direction. This changes placement, not blade orientation.

The fist mask is explicitly the opaque body pixels within three source texels
in X/Y of the reviewed palm annotation. It is a local hand-seam model, not a
whole-body collision model or a substitute for native occlusion. Source hashes,
the exact mask, contact pixel pair, contact coordinates and displacement are
recorded in [contacts.json](../Outputs/dual_weapon_edge_contacts/contacts.json).
There are 1,632 held contact records: 17 views  × 8 directions  × 6 frames  × 2 roles.
These masks and the final appearance still require live visual acceptance.

The [installed-build preview](../Outputs/dual_weapon_edge_contacts/preview/review.html)
contains all 17 weapon views in both slots, held and attack animations, plus
the six original generic pairs. Its metadata pins EXE `4e233893...` and payload
`175162d2...`. It is an offline rendering of compiled geometry and original
pixels, with the same CPU depth/head limitations described above.

The runtime projects the two stored texture-edge points using the current
native body rectangle, original weapon dimensions, mirroring, zoom and actor
rotation. It does not search pixels during rendering or retain a last-draw
coordinate. Both hands prepare before either draws; channel5/6 ownership and
the existing native depth/color handling remain intact.

## Verification

[Compiled execution](evidence/dual-weapon-edge-contacts-execution-20260905.json)
covers 15,232 cases, 15,232 attack draws and 13,056 held draws. Attack geometry is
compared with the archived compiled compositor in reference-role order;
equipment-slot assignment is checked separately. Held validation projects the
actual opaque pixels and measures both contact and local silhouette penetration.
Maximum geometry/contact error is 0.000177 screen pixels; maximum penetration
is 0.000161, within the 0.001 float-execution tolerance. Both zooms and actor
rotations 0/15/-90 are exercised.

[Off-only and rejection gates](evidence/dual-weapon-edge-contacts-guards-20260905.json)
pass 4,896 off-only cases, 136 same-image dual cases, 9 admitted /520 rejected class
pairs, and explicit gender, body, source-image, Drake and unknown-view guards.
Maximum off-only contact error is 0.000178 pixels.

[The real-PE protection regression](evidence/dual-weapon-edge-contacts-page-protection-20260905.json)
reproduces the old NX crash and passes eight transitions /19 native calls on
this candidate. [Binary verification](evidence/dual-weapon-edge-contacts-binary-20260905.json)
checks the full relocated payload/owner, all four hooks, unchanged remaining
mapped bytes, original legacy/depth code, section bounds and executable code
outside the isolated RW state pages.

## Exact binary

[Candidate EXE](../Outputs/dual_weapon_edge_contacts/client-old-motion-edge-contacts.exe):
`4e23389333cd873e3f136b48a67aa20f95d648c8a254318b6630b4266858636c`.

[DWCP](../Outputs/dual_weapon_edge_contacts/compositor.dwcp):
`175162d22f030a730dc69805c6d07894633ef3376d2406ffa184b07a3d7ab016`.

| Hook VA | Replacement bytes | Target VA |
| --- | --- | --- |
| D403A0 | `E9 FB 26 15 01` | 1E92AA0 |
| 605D41 | `E8 6A CD 88 01 89 45 94 90` | 1E92AB0 |
| C4A0D0 | `E9 FB 18 25 01 90` | 1E9B9D0 |
| C4A647 | `E9 64 13 25 01` | 1E9B9B0 |

Compositor base/entry:`1E7A4F0` /`1E7BD60`; context:`1E92A40`;
owner:`1E66410`; depth helper:`1E92B30`. RW state:`[1E60000,1E65000)`.

## Reproduction

The checked-in contact header and normal DWCP are sufficient for ordinary
patching. To regenerate contacts, first run the pixel inventory audit, then
build the offline reference with `build_dual_weapon_compositor.py
--measure-contacts --output Outputs/dual_weapon_edge_contacts/old-angle-center-reference.dwcp`.
Run `build_dual_weapon_edge_contacts.py` with the bundled Python that includes
Pillow and NumPy; review the output and copy its header to
`CustomDLL/DualWeapon/held_edge_contacts.h`. Compile the normal payload without
`--measure-contacts`, run the two edge verifiers, and build/verify the client
from the stock-hook source. The measurement payload must never be installed.
