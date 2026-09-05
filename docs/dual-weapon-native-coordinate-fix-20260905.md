# Native dual-weapon coordinate correction — 2026-09-05

**User acceptance, 2026-09-05:** the user reported this correction working after
retesting deployed EXE `0bb06dbc84d9e0a5df4fb3002b8946388d00158576ef18be74b3fbff754d4509`.
This records the user's successful retest of the existing reference weapon cases;
it does not accept additional weapon types, items, jobs, genders, or every cell
of a live animation matrix. See [the deployment acceptance record](evidence/dual-weapon-native-basis-deployment-20260905.json).

The live client uses a different coordinate representation from the old test
harness. The ACT loader converts file coordinates to integer image edges;
the native packet producer then scales those edges and adds one pixel to the
second X/Y endpoints. The rejected compositor and its tests omitted this
contract. Sword/dagger works because the live pair28 resource passes the
accepted **legacy** renderer's family check; the other cases use the new path.

This is now supported by live resource reads and execution of native PE code.
It supersedes the earlier claim that this resource set failed the pair28 family
fingerprint. It also explains why reproducing the previous synthetic packet
tests did not reproduce the player's result.

## Live binary and resource identity

All three read-only snapshots identify the same deployed EXE SHA-256:
`34c98e38905dc45ce568617b409b88b8cf551a1d6fecb4670258a183b1c36a21`.

| Snapshot | Items main/off | Views main/off | Pair |
| --- | --- | --- | ---: |
| [Working pair28](evidence/dual-weapon-live-pair28-20260905.json) | 13412 / 1238 | 45 / 34 | 28 |
| [Off-hand sword](evidence/dual-weapon-live-off-sword-20260905.json) | 0 / 13412 | 0 / 45 | 0 |
| [Dagger/dagger](evidence/dual-weapon-live-dagger-dagger-20260905.json) | 1238 / 1238 | 34 / 34 | 25 |

The live actor vtable is `0x01094810` (`CGameActor`); its `+0x24` entry points
to `0x00C40C20`. The retained resources resolve to the expected female Assassin
weapon family. Dagger/dagger legitimately retains the same original SPR/ACT
objects for both hands; separate output packets still distinguish their poses.
Stale registry rows are reported separately and excluded from this actor's
evidence. The snapshots are not atomic process dumps.

## File ACT centers are not native layer edges

For each valid selected image, live native layer coordinates are:

```text
native_x = file_ACT_x - ceil(image_width / 2)
native_y = file_ACT_y - ceil(image_height / 2)
```

Held action32/frame0 examples:

| Resource | File ACT x/y | Image width/height | Live native x/y |
| --- | --- | --- | --- |
| Generic pair28 | (11,-27) | 62 × 44 | (-20,-49) |
| Item13412 sword | (42,-52) | 53 × 38 | (15,-71) |
| Item1238 dagger | (33,-48) | 26 × 26 | (20,-61) |

Thus the apparently different `(11,-27)` pair28 resource becomes the exact
`(-20,-49,sprite0,mirror0)` fingerprint used by the legacy core. The live
sword/dagger result uses that core. The old harness instead expanded raw ACT
coordinates directly into native `Layer` memory and set `ctx[19]=0`, so it
tested neither this normalization nor the actual working legacy path.

[The native projection verifier](../tools/verify_dual_weapon_native_projection.py)
matches all nine layer fields in **146 valid live layer records**, with zero
mismatches. It also checks the 300 captured frame-anchor records. The 154 invalid
sprite records are recorded separately; no sentinel normalization is invented.

## Native projection and anchor routing

`0x00C40C20..0x00C412C8` is the verified 1,704-byte packet producer, SHA-256
`88ac1917182e29a8edde3588a2677fd45c0475384de21bc2f1a9c257df1fa096`.
Its second X and Y bounds receive **+1 after scaling**, including mirrored X.
For simple images and zero extra attachment offset:

```text
left   = origin_x + (native_x + (mirror ? width : 0)) * scale_x
right  = origin_x + (native_x + (mirror ? 0 : width)) * scale_x + 1
top    = origin_y + native_y * scale_y
bottom = origin_y + (native_y + height) * scale_y + 1
```

The verifier additionally covers image grid dimensions, actor scale, layer
scale and explicit offsets. Recovering native scale therefore removes +1
**before** taking the absolute edge difference. `abs(right-left)/image_width`
alone gives the wrong scale, with different errors for normal and mirrored
packets. The accepted legacy compositor's subsequent scale convention is kept
only after reconstructing its reference packet; it is not confused with native
projection scale.

The profiled attachment-anchor routing at `0x00605170` bypasses weapon channels
5/6. Native job anchors are therefore not the cause of this weapon-coordinate
failure, and adding a compensating body-anchor offset would address the wrong
path. A future body-socket compositor remains a separate architecture; see the
[job-sprite audit](dual-weapon-job-sprite-audit-20260905.md).

## Corrected reference basis and evidence

[The basis generator](../tools/build_dual_weapon_native_basis.py) reads the exact
accepted rig embedded in `AllowDualCustomWeaponSprites.qjs`, then normalizes the
selected reference resources. It emits
[native_basis.h](../CustomDLL/DualWeapon/native_basis.h): 112 held/attack cells,
224 hand records, 208 visible hands. This avoids treating the external canonical
rig's encoding as interchangeable with the embedded legacy rig. Source frame,
layer, mirror correction, visibility, order and stock body/trail channel remain
explicit. The generator records resource and source hashes.

The correction recovers the native projection/origin from the current packet,
reconstructs the accepted pair28 guide packet, then applies the accepted legacy
pose in that basis. Off-hand-only selects the corresponding original reference
hand. Dagger/dagger preserves the original dagger hand; the other dagger uses
native image-center registration relative to the former sword image, preserving
fractional coordinates. That substitution still assumes native solo ACTs
register their grips to the same hand; it is not an independently authored
anatomical hilt landmark.

[Projection report](evidence/dual-weapon-native-projection-20260905.json):
**192 cases execute the actual native producer instructions**. Status effects
are disabled and origin/attachment offsets are explicit fixture inputs. The
native virtual entry is not replaced by a rectangle-formula stub.

[Before report](../Outputs/dual_weapon_native_basis/before.json) and
[initial after report](../Outputs/dual_weapon_native_basis/after.json): the legacy
core executes against normalized resources and passes its real family check,
without a discriminator stub. The matrix uses eight directions, six held frames,
and native scales 1.0 and 2.3423.

| Comparison | Rejected payload | Initial corrected payload |
| --- | ---: | ---: |
| Off-hand-only sword/dagger vs corresponding legacy hand | 192 / 192 differ | 0 / 192 differ |
| Dagger/dagger's original dagger hand vs legacy dagger | 96 / 96 differ | 0 / 96 differ |
| Total | **288 / 288 fail** | **288 / 288 pass** |

Example output centers relative to fixture origin `(960,495)`, direction0/frame0,
native scale 1.0; figures below are rounded to six decimals for display:

| Case | Rejected center | Corrected center | Executed legacy reference |
| --- | --- | --- | --- |
| Off-hand dagger | (29.500000,-46.799988) | (33.854858,-47.977264) | (33.854858,-47.977264) |
| Off-hand sword | (16.606079,9.156250) | (4.387085,-5.022736) | (4.387085,-5.022736) |
| Dagger/dagger, original dagger hand | (46.049988,-41.799988) | (33.854858,-47.977264) | (33.854858,-47.977264) |

These first 288 comparisons do **not** validate the replacement dagger's hilt
contact, the full attack matrix, or live body occlusion. They establish a
previously failing native-coordinate regression for the unchanged reference
hands. Later tests must be recorded with their own scope rather than silently
extending these counts.

## Reproduction and binary status

Run from the repository root; the PE path is read-only input to these verifiers:

```powershell
.\.venv\Scripts\python.exe -B tools/verify_dual_weapon_native_projection.py --client "D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes" --exe "D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes\2025-07-16_Ragexe_175220998_clientinfo_patched.exe"
.\.venv\Scripts\python.exe -B tools/build_dual_weapon_native_basis.py --client "D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes" --check
.\.venv\Scripts\python.exe -B tools/verify_dual_weapon_native_basis.py --client "D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes" --exe "D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes\2025-07-16_Ragexe_175220998_clientinfo_patched.exe" --payload Inputs/DualWeaponRuntime/compositor.dwcp --output Outputs/dual_weapon_native_basis/recheck.json
```

The initial passing **temporary DWCP payload**, not a deployed EXE, has SHA-256
`4ac1a812fb5bbbb21eec4fdcff122adc913d258f7f6e86b9ed610f10ee60c658`.
Its snapshot manifest is
[Outputs/dual_weapon_native_basis/compositor.json](../Outputs/dual_weapon_native_basis/compositor.json).
Do not confuse that payload hash with a final client hash or transplant the old
candidate's cave addresses into a new build. Final PE identity, relocated bytes
and deployment status must be recorded after the final build is verified.

At the initial temporary-payload stage, live hand contact was still unaccepted.
Native execution established the coordinate contract that the original synthetic
tests missed. The later user acceptance below applies to the final deployed EXE;
the offline comparisons retain their stated scope.

## Final implementation and deployed binary

The final regression expands the historical initial comparisons above:
[1,248 cases](evidence/dual-weapon-native-basis-regression-20260905.json) pass,
comprising 576 off-hand held cases and 672 dagger/dagger held/attack cases.
All directions and frames use zoom 1.0/2.3423 and actor angles 0/15/-90.
It checks 1,824 original-image draws, with maximum numeric error 0.000184472
against independently reconstructed legacy geometry. Native C40C20 and the
full legacy core execute in the verifier; source images, frame selection,
angles, mirroring, order, current-packet depth/color and the x86 ABI are checked.

The final dagger registration applies axis scaling BEFORE rotation, matching
native final-vertex construction. Reversing those operations caused up to
2.71938 pixels of additional error in the inspected attack cells. Actor rotation
is retained in both final weapon angle and the registration displacement.
The canonical mirror flag is absolute; the unrelated canonical fallback also
no longer XORs the source mirror a second time. Fixed views34/45 validate their
accepted identity grip records at basis-build time. Other fallback paths still
use canonical DWR3/DWC2; no additional weapon-family acceptance is implied.

The earlier integer-derived DWR3 is **not a runtime input**. The builder embeds
the unchanged canonical rig plus the compiled native reference table. Source,
header and basis-builder hashes are recorded in the payload manifest.

Deployed to the user's existing client path:
`D:/Programs/Games/Ragnarok/02_client/Banquet of Heroes/2025-07-16_Ragexe_175220998_clientinfo_patched.exe`

- EXE SHA-256: `0bb06dbc84d9e0a5df4fb3002b8946388d00158576ef18be74b3fbff754d4509`
- DWCP SHA-256: `b774459f9a579039a15dcdba1849afb5e7aa602a079a2e448818b8799abbe79c`
- Basis header SHA-256: `647268dd7348e8e18b38087e76b5a624df3a9160811194f16796e9eff769a8b1`
- Previous EXE is retained as `_before_native_basis_34c98e38.exe` beside the client.

| Hook VA | Installed bytes | Target VA |
| --- | --- | --- |
| `0x00D403A0` | `E9 7B 74 14 01` | `0x01E87820` |
| `0x00605D41` | `E8 EA 1A 88 01 89 45 94 90` | `0x01E87830` |
| `0x00C4A0D0` | `E9 7B 66 24 01 90` | `0x01E90750` |
| `0x00C4A647` | `E9 E4 60 24 01` | `0x01E90730` |

Compositor entry: `0x01E7AFB0`; context: `0x01E877C0`. The full relocated
compositor/data, equipment owner, unchanged legacy/depth cores, four hook
regions, other mapped bytes, PE section bounds and header size are verified in
[the binary report](evidence/dual-weapon-native-basis-binary-20260905.json).
The state pages remain `[0x01E60000,0x01E65000)`, separate from executable caves;
[the cold protection test](evidence/dual-weapon-native-basis-page-protection-20260905.json)
reproduces the prior NX fault and passes the corrected equipment transitions.
[Deployment hashes](evidence/dual-weapon-native-basis-deployment-20260905.json)
were verified after replacement. The user subsequently reported success with
this deployed correction on 2026-09-05. This is user-reported visual acceptance
of the existing reference cases, alongside the separately recorded offline
matrix. Dagger substitution preserves native solo registration; no independently
measured anatomical hilt or additional weapon-family acceptance is implied.
