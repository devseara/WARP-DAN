# Off-hand held and dagger/dagger pose-transfer candidate — live rejected, 2026-09-05

The user confirmed the female Assassin sword/dagger combination works, and
provided screenshots showing misplaced off-hand-only and dagger/dagger weapons.
The pictured originals are Zeny Knife (1238/view34) and the blue Twin Edge sword
(13412/view45). The requested off-only placement is the same visible hand used
by that weapon in the working combination.

## Live rejection of this candidate

The deployed candidate with SHA-256
`34c98e38905dc45ce568617b409b88b8cf551a1d6fecb4670258a183b1c36a21`
was rejected by the user after testing: off-hand-only sword and dagger remain
misplaced in all directions, and dagger/dagger remains incorrect. The latest
attachments are `codex-clipboard-e2cb985f-70f4-4ae7-9c04-dac8c6e13dda.png`
(dual daggers) and `codex-clipboard-c3ed964d-0596-4fe6-b313-d1963b413279.png`
(off-hand sword). The images document the pictured poses; the all-directions
scope is the user's live report. Sword/dagger and dagger/sword remain the
reported working combinations. This is a failed placement candidate, not a
pending acceptance or successful placement correction.

## Native-coordinate cause established after rejection

Read the [native-coordinate correction](dual-weapon-native-coordinate-fix-20260905.md)
for the new evidence and candidate. Live ACT layers subtract rounded half-image
extents from file coordinates: the pair28 file center `(11,-27)` becomes native
`(-20,-49)`, exactly matching the legacy family fingerprint. The live working
sword/dagger path therefore uses the embedded legacy core. Its producer is
`0x00C40C20`, dispatched through live actor vtable `0x01094810 + 0x24`; it adds
one pixel to the second bounds after scaling, even for mirrored X.

The old test's direct expansion of raw ACT fields and `ctx[19]=0` omitted both
the native coordinate conversion and the actual working reference. Native
channel5/6 routing bypasses the attachment-anchor adjustment at `0x00605170`,
so adding body-anchor offsets is not the remedy. The corrected generator now
reads the embedded accepted legacy rig into `native_basis.h`.

The new tests match 146 valid live layer records and execute 192 real native
projections. The rejected payload fails all 288 native held reference-hand
comparisons; an initial temporary corrected payload passes all 288. Those
counts cover off-only and dagger/dagger's unchanged dagger hand, not new hilt
acceptance or attacks. The temporary `4ac1a812…` hash identifies a DWCP payload,
not a deployed EXE. The implementation and addresses below remain a historical
record of rejected EXE `34c98e38…`.

## Earlier source-level findings

The previous off-only branch called `prepare(..., pose=0, grip=0)`. Its output
therefore transferred the solo-main ACT position unchanged to off-only, including
its solo-main frame selection. Retaining the correct SPR was insufficient to
put it in the requested hand.

Dagger/dagger used state6 from the canonical rig. Those cells were explicitly
`native_guide_unaccepted` estimates. They used different source frames, angles,
mirroring and centers from the working state9 reference. Passing the former
resource-selection test established only which SPR supplied the image. It did
not validate any of those placement quantities.

## Rejected candidate implementation

[The pose builder](../tools/build_dual_weapon_pose_transfer.py) reads the original
canonical rig and the exact current GRF ACT/SPR resources, following DATA.INI
precedence. It writes a separate
[derived rig](../Inputs/DualWeaponAuthored/rigs/female-assassin-pair28-derived.dwr3)
and [per-cell provenance](../Inputs/DualWeaponAuthored/rigs/female-assassin-pair28-derived.json).
It never edits the original accepted pair28 CSV or canonical rig.

For dagger/dagger, the original dagger hand follows the same pair28 hand. For
the hand previously occupied by the sword, both original solo ACTs provide a
native source cell for the same action/frame. All 96 visible source cells have
valid images, zero native rotation, unit scale and matching native mirroring.
The builder asserts these conditions rather than inventing a missing frame.

The source-center displacement is:

```
delta = dagger_native_ACT.xy - sword_native_ACT.xy
delta.x *= -1 when the reference pose adds an X mirror
dagger_target = working_sword_target + R(reference_pose_angle) * delta
```

This uses a different ACT-derived vector for each source action/frame, but
subtracting two ACT layer centers does not prove the selected images' hilt
pixels are registered to the same physical hand. The checks above establish
valid source cells, not that missing geometric correspondence. The earlier
fixed-hilt experiment tested a different, narrower model; its sign bug and
limits are corrected in the [job-sprite audit](dual-weapon-job-sprite-audit-20260905.md).
The rotation convention follows the native draw at 0x00C4A434–0x00C4A455:
`x' = cos(a)*x - sin(a)*y`, `y' = sin(a)*x + cos(a)*y` in screen coordinates.
Native helpers 0x0054B240/0x0054B2E0 provide the angle lookup values.

For attack, the builder attempts to reconstruct a pair28 actor-relative
weapon center by adding its current stock weapon body/trail ACT center to the
accepted packet delta, then stores an actor target. This arithmetic assumes
those quantities share a verified coordinate basis and scale; the pose test did
not prove that assumption on native packets. `actor_target` denotes a weapon
center in the actor coordinate basis; `packet_delta` denotes an offset from the
stock weapon packet center. Neither is a body-hand socket. Here "body/trail"
means weapon channels 5/6, not the character's job-body sprite. The source action, source frame, extra rotation, mirror and hidden
terminal cells follow pair28. Integer DWR3 coordinates introduce at most half a
sprite-coordinate unit of rounding per axis; the measured maximum is 0.487317.

Off-only held states0/1 copy the pair28 dagger/sword pose records. The compositor
uses those records and the existing per-view grip lookup, and suppresses the
duplicate trail only after replacement preparation succeeds. Both weapons keep
their original image and palette. Equality of those records does not establish
that the native solo packet and dual packet have the same coordinate basis.

**Solo off-only attack80 is unchanged.** Its body timeline differs from dual
attack88, so this patch does not transplant dual attack frame numbers into it.
The attempted change covers held poses, including the pictured case, but that
placement has now failed live testing. Male dual poses and other weapon pair
estimates were not changed.

## Outputs under the synthetic packet model

Direction0/frame0, center relative to the test actor under the harness's
assumed unit scale. These are calculated packet outputs, not measured native
screen coordinates or anatomical hand positions:

| Case / physical role | Before center | After center | Before angle | After angle | After image |
|---|---|---|---|---|---|
| Off-only sword held | (42,-52) | (0,-9) | 0° | 90° | sword sprite0 |
| Off-only dagger held | (33,-48) | (15,-57) | 0° | 0° | dagger sprite0 |
| Dagger/dagger held, former sword hand | (-9,-26) | (-4,-18) | 0° | 90° | dagger sprite0 |
| Dagger/dagger held, original dagger hand | (29,-39) | (15,-57) | 0° | 0° | dagger sprite0 |
| Dagger/dagger attack, former sword hand | (29,-45) | (6,-41) | 0° | -143° | dagger sprite2 |
| Dagger/dagger attack, original dagger hand | (3,-43) | (30,-44) | 0° | 178° | dagger sprite2 |

For example, native held dagger minus sword is `(-9,+4)`. The working sword
pose rotates it by +90° to `(-4,-9)`; adding the working sword center `(0,-9)`
gives `(-4,-18)`. The old estimated main-dagger mirror is also removed to match
the corresponding working physical hand.

## Verification and executable

[Calculated-output execution report](evidence/dual-weapon-pose-transfer-20260905.json),
generated by [the regression](../tools/verify_dual_weapon_pose_transfer.py):

- 208 sword/dagger draws in the harness remain identical before and after the
  change; this does not establish equivalence to the accepted legacy renderer.
- 208 dagger/dagger draws verify source image, source-frame-derived dimensions,
  center, angle, mirror, ordering and hidden cells against the reference plus
  the independently computed native ACT displacement.
- 96 off-only held draws (two weapon types, eight directions, six frames) exactly
  equal the corresponding pair28 output under the same harness assumptions.
  Both old off-only weapon types fail this calculated-output comparison.
- The complete nine-order resource/ABI matrix still handles all 1,296 native
  packets without generic fallback. The real-PE page-protection regression also
  passes, including 19 trampoline traversals.

The old harness constructs packets as `center=(400+ACT.x,300+ACT.y)` and
`width/height=SPR dimensions*ACT scale`, then records calls instead of running
the native draw body or rendering pixels. It sets `ctx[19]=0`, so it never
executes the historical legacy pair28 core. Both its reference and candidate
therefore use the readable compositor under the same synthetic coordinate
assumptions. Live field reads have now demonstrated that these assumptions omit
native half-image normalization and far-edge +1. The independent ACT subtraction
checks that the implementation
emits the chosen formula; it supplies no independent proof that the formula
registers hilts or matches the live renderer. Resource identity, ABI behavior,
and PE integrity checks remain useful within their stated limits.

The latest user screenshots and report reject this candidate's placement.
Do not promote the 208/96 calculated-output comparisons into visual acceptance
or deploy this exact hash as an accepted geometry fix.

EXE SHA-256:
`34c98e38905dc45ce568617b409b88b8cf551a1d6fecb4670258a183b1c36a21`

DWCP SHA-256:
`e1209fae0b9cd734ce00de6ab1e098ed949470e93e0cc9b0535824438cf5ca25`

| Hook VA | Bytes | Target VA |
|---|---|---|
| 0x00D403A0 | E9 EB 24 14 01 | 0x01E82890 |
| 0x00605D41 | E8 5A CB 87 01 89 45 94 90 | 0x01E828A0 |
| 0x00C4A0D0 | E9 EB 16 24 01 90 | 0x01E8B7C0 |
| 0x00C4A647 | E9 54 11 24 01 | 0x01E8B7A0 |

Compositor base/entry: 0x01E7A270 / 0x01E7A880. Context: 0x01E82830.
Depth helper: 0x01E82920. Equipment owner: 0x01E66410.
The trampoline and isolated state pages remain 0x01E5F000 and
[0x01E60000,0x01E65000). Only the same four old mapped hook regions change;
all other existing mapped bytes, including unrelated patches, are preserved.
See [binary proof](evidence/dual-weapon-binary-fix-20260905.json) and
[deployment proof](evidence/dual-weapon-deployment-20260905.json).
