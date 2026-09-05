# Dual/off-hand original-resource fix — 2026-09-05

Current installed scope: [daggers, one-handed swords and one-handed axes](dual-weapon-supported-types-20260905.md), EXE `c2e857e3...eeb02`. The all-type expansion is superseded at the user's request. The backed-up `0bb06dbc...4509` build remains the live-accepted reference; new axe/item placement still requires live validation.

The local patch now retains each item's original resources for off-hand-only
equipment and has a new compositor for the documented female Assassin dual
held/attack pairs. It emits two independently prepared original weapon packets,
including when both items share the same SPR. It does not replace the actor's
native channel 5/6 slots with physical hands.

**Resource selection is verified in emitted x86; the current placement candidate
is live rejected.** After testing deployed SHA-256 `34c98e38…`, the user reports
that off-hand-only sword/dagger remain misplaced in all directions and
dagger/dagger remains incorrect. Pair25 uses poses derived from pair28 through
ACT-center subtraction, which has not established physical hilt registration.
Other non-pair28 canonical poses remain `native_guide_unaccepted`. Original-image
selection and calculated output do not establish hand contact. This supersedes
the old rule that non-pair28 records remain stock, in response to the request
to restore original sprites; it does not grant placement acceptance.

**Crash follow-up:** the first deployed candidate (SHA-256 `ac2ff148…`) is
invalid. It removed execution permission from its own trampolines. The page-protection correction was `e8ebfd16…`; the current placement
candidate is `34c98e38…`; see the [exact reproduction and page fix](dual-weapon-page-protection-crash-20260905.md).
The prior owner harness initialized the state-ready flag and stubbed the native
entry, so it did not test cold initialization or trampoline fetch protection.
That gap is now covered by a separate test of the actual PE instructions.

**Placement follow-up:** the user confirmed sword/dagger works, but reported
wrong off-hand-only held placement and dagger/dagger x/y, frames and angles.
The earlier off-only branch had no authored pose; state6 used estimated data.
The [rejected pose-transfer candidate](dual-weapon-pose-transfer-20260905.md)
copies pair28 records for off-only held and derives pair25 from ACT-center
differences. The harness's 96 off-only comparisons and 208 unchanged pair28
outputs validate arithmetic under synthetic packets, not the accepted legacy
renderer or native hand contact. The latest screenshots reject the resulting
placement. Solo off-hand attack80 retains its prior native transfer.

## Native-coordinate follow-up — current correction authority

The [native-coordinate correction](dual-weapon-native-coordinate-fix-20260905.md)
supersedes this document's earlier family-mismatch explanation. Live pair28,
off-sword and dagger/dagger snapshots all resolve the intended resource family.
The file pair28 center `(11,-27)` normalizes to native `(-20,-49)`, so working
pair28 executes the accepted legacy core. Item13412 `(42,-52)` becomes `(15,-71)`;
item1238 `(33,-48)` becomes `(20,-61)`.

Native `0x00C40C20`, the live CGameActor vtable `0x01094810` entry at `+0x24`,
adds +1 to the second packet edges after scaling, including mirrored X. The
old synthetic packet model missed this and the ACT normalization. Native weapon
channels5/6 bypass `0x00605170` attachment-anchor adjustment; job anchors do not
explain this failure. The correction generates `native_basis.h` from the exact
accepted rig embedded in QJS and reconstructs its native reference packet.

The new evidence verifies 146 valid live layer records and 192 executions of the
native producer. The rejected payload fails 288/288 native held reference-hand
comparisons; initial temporary payload `4ac1a812…` passes 288/288. Its full hash,
comparison scope and limits are in the linked report. That is a DWCP test
payload, not deployment or live placement acceptance. The binary section below
preserves the previously deployed, live-rejected `34c98e38…` candidate.

## Proven causes and corrected earlier inference

1. The pulled legacy core compares row+0x2C to 28 at core+0x407B. Dagger/dagger
   is pair 25 and cannot reach its pose preparation. Editing a pose table alone
   cannot fix that gate.
2. **Earlier family-mismatch inference was wrong.** The legacy comparison
   expects action32/frame0/layer0 at x=-20, y=-49, sprite=0, mirror=0.
   The file has center (11,-27), but loading its 62x44 image subtracts (31,22)
   and yields exactly (-20,-49). Live resource fields confirm the match and
   select the working legacy path. Comparing raw file coordinates directly to
   native layer fields was an analysis and fixture bug.
3. The old equipment hook rejects mainItem==0 before retaining anything.
   Off-hand-only equipment therefore never reaches its custom draw path.
4. ItemToWeaponView was called only as a Boolean classifier. Actual view IDs
   were discarded, and the legacy payload does not consume the external DWC2
   table. This prevents per-view source-frame/grip corrections from taking effect.
5. The legacy image hook records a global last image/layer and a recent ring.
   A queued draw does not own that global record. The new path does not read
   either record: it resolves the current actor's restored stock ACT, SPR image,
   and matching SPR palette before replacing that packet.

There were two different files at the supplied deployed path during the session:

| Snapshot | SHA-256 | Dual hook sites |
|---|---|---|
| Initially inspected | 06bb1d433c32df71d0f0405e6ada3a5ba4be49e1c06805408c3b2a57c13cc75b | Four legacy hooks present |
| Saved rebuild baseline | b06a69f923ca2992da80ba7993eeb162bf09d2ef094d6d30a593b5f08aa9146c | All four sites stock |

The later baseline has no dual compositor installed. The earlier executable
proves the separate legacy gating problem. The generic names in weapontable.lua
are valid native fallback resources; changing those names is not the remedy.

Resource resolution checked loose files and DATA.INI order: update.grf,
maindata.grf, spritedata.grf, then data.grf. Relevant original/pair assets resolve
to spritedata.grf. See the [resource hashes and selected packets](evidence/dual-weapon-resource-fix-20260905.json).

## Implementation and ABI evidence

Source: [compositor.c](../CustomDLL/DualWeapon/compositor.c).
Payload: [compositor.dwcp](../Inputs/DualWeaponRuntime/compositor.dwcp).
Builder/provenance: [build tool](../tools/build_dual_weapon_compositor.py) and
[manifest](../Inputs/DualWeaponRuntime/compositor.json).

The new source uses a C-compatible subset compiled as C++ only for MSVC's explicit
thiscall function-pointer ABI. It is freestanding, has no runtime imports, and
is embedded in the EXE; the intermediate build DLL is not deployed.

The legacy 60-byte actor-row ABI stays intact. Actual main/off view IDs occupy
a separate 8-byte record at state+0x400, indexed by the same actor hash.
Those records end at state+0xC00, before the actor rows at state+0x1000.
The 256 actor rows end at state+0x4C00 inside the existing 0x5000 allocation.

The owner calls stock first, captures off as solo-main and main as solo-main,
then restores the requested stock equipment before publishing. Main capture is
skipped for off-hand-only. Channel-6 resources may be null; required channel-5
resources may not. All retained pointers are reference-counted independently,
including duplicate/shared resources. Failed capture releases temporaries.
An occupied hash collision preserves the other actor and leaves this actor stock.

The new compositor reads native structures with bounds checks:

| Native evidence | Contract |
|---|---|
| 0x0070F2E3 and 0x0070F308 | CAct action vector +0x110/+0x114; stride 12 |
| 0x0070F4FD–0x0070F504 | CActFrame stride 68 |
| 0x0070F394 and 0x0070F3B4 | Frame layer vector +0x20/+0x24; layer stride 36 |
| 0x00605D1D–0x00605D39 | Layer kind +0x20/index +8; CSprite vectors +0x510/+0x514 plus kind*12 |
| 0x006060E7 | Native weapon palette is CSprite+0x110 |
| 0x00C4A0EC | Native draw reads image metadata from packet+0x2C |
| 0x006048C0–0x006048DE | Native queue copies the complete 48-byte packet and palette/draw arguments |
| 0x00D3913D–0x00D3914A | PairMapper(0, offItem) classifies offItem as a solo weapon |
| 0x00C4A0D0 | Draw is thiscall, six stack arguments, RET 0x18 |

The new exported compositor is stdcall with nine DWORD arguments, RET 0x24.
The existing scoped native draw thunk still supplies the same character-depth
helper. The legacy pair28 core is called only for its exact family fingerprint;
its 63,177 bytes and 432 relocations, and the 1,380-byte/3-relocation depth helper,
are unchanged.

The canonical physical order is:
pair25=(dagger,dagger), pair26=(sword,sword), pair27=(axe,axe),
pair28=(sword,dagger), pair29=(axe,dagger), pair30=(axe,sword).
Mixed equipment orders select the corresponding resources without swapping the
authored physical poses. These are states 6,7,8,9,11,13 respectively.

The active rig is female-assassin-pair28-derived.dwr3. Its pair28 cells are
identical to the canonical input; state6 and off-only held states0/1 are generated
by tools/build_dual_weapon_pose_transfer.py. All other dual cells are preserved.

For each visible hand, the compositor resolves the pose's source action/frame,
applies a matching DWC2 selected_frame and correction, then selects the image from
that retained original SPR. A missing visible source image returns stock before
any custom draw. Hidden authored cells remain hidden. Native body channel 5 owns
the replacement when present; a native trail-only frame uses channel 6 as its
basis. A second channel is suppressed only after both hands prepare successfully.

In the rejected candidate, the implementation estimated screen scale from the
packet rectangle, current image dimensions, and ACT scale. The later native
producer audit proves that this estimate omitted the second-edge +1 and that
its raw-file coordinate fixtures omitted native half-image normalization.
The new correction uses the verified native basis described above.
Held `actor_target` records describe weapon centers and subtract stock ACT x/y;
attack `packet_delta` records describe offsets from stock weapon packet centers.
The derived pair25 attack records are converted to actor targets by the builder.
Neither representation is a hand socket on the job-body sprite. ACT-center
differences also do not prove the selected images have matching local hilts.
Per-view grip offsets are then applied. The full 48-byte packet is copied and
its image/palette stays paired. See the
[coordinate and model audit](dual-weapon-job-sprite-audit-20260905.md).

An exact emitted-code example from the current GRFs, direction 0/frame 0:

| Pair / action | Original resource and frame | Center relative to test actor | Angle | Mirror |
|---|---|---|---|---|
| dagger/dagger held (32) | 1238, sprite 0 | (15,-57) | 0° | no |
| dagger/dagger held (32) | 1238, sprite 0 | (-4,-18) | 90° | no |
| sword/dagger held (32) | 1238, sprite 0 | (15,-57) | 0° | no |
| sword/dagger held (32) | 13412, sprite 0 | (0,-9) | 90° | no |
| dagger/dagger attack (88) | 1238, sprite 2 | (30,-44) | 178° | no |
| dagger/dagger attack (88) | 1238, sprite 2 | (6,-41) | -143° | no |

These numbers prove what the candidate emits; they are not a claim that the
draft dagger/dagger poses align with the character's hands in game.

## Executable, hex and relocation proof

Live-rejected placement candidate (historical output filename):
Outputs/dual_weapon_resource_build/2025-07-16_dual_originals_fixed_existing.exe

SHA-256: **34c98e38905dc45ce568617b409b88b8cf551a1d6fecb4670258a183b1c36a21**

The binary-verified candidate was installed at the supplied client path and
subsequently rejected for placement:
2025-07-16_Ragexe_175220998_clientinfo_patched.exe.
The previous file is preserved beside it as
2025-07-16_Ragexe_175220998_clientinfo_patched_before_dual_fix_b06a69f9.exe.
Both post-copy hashes are recorded in the
[deployment proof](evidence/dual-weapon-deployment-20260905.json).


DWCP SHA-256: **e1209fae0b9cd734ce00de6ab1e098ed949470e93e0cc9b0535824438cf5ca25**

| Hook VA | Replacement bytes | Target VA |
|---|---|---|
| 0x00D403A0 | E9 EB 24 14 01 | 0x01E82890 |
| 0x00605D41 | E8 5A CB 87 01 89 45 94 90 | 0x01E828A0 |
| 0x00C4A0D0 | E9 EB 16 24 01 90 | 0x01E8B7C0 |
| 0x00C4A647 | E9 54 11 24 01 | 0x01E8B7A0 |

New compositor base/entry: 0x01E7A270 / 0x01E7A880.
Context: 0x01E82830. Legacy core: 0x01E66A80.
Depth helper: 0x01E82920. Equipment owner: 0x01E66410.
The equipment/draw trampolines stay at 0x01E5F000/0x01E5F010.
State moved from 0x01E5F400 to VA-page-aligned 0x01E60000; its exclusive
protection range is now [0x01E60000, 0x01E65000). The actor registry is
0x01E61000 and the view registry is 0x01E60400. All references are re-emitted.
The stock ACT frame call at 0x00D36EE4 remains E8 C7 85 9D FF.

These cave addresses belong to this exact candidate. A normal WARP rebuild with
a different patch vector can allocate different caves; hook preimages and
payload relocations are checked rather than treating cave addresses as universal.

The saved full LastSession vector reports an unrelated
ROGlobalZeroMenu: AutoSupportUI must run first error. Instead of changing that UI
vector, [the existing-client builder](../tools/build_existing_dual_weapon_client.py)
adds only this patch to the saved deployed baseline.

That exposed a WARP header-growth problem on this already-patched, nine-section
EXE: its new .xdiff header reported file offset 0x200 instead of 0x1696E00, and
20 bytes at old .xdiff RVA 0x1A5EA00 were zeroed. The builder validates the two
new prologue trampolines at the actual new-section file position, repairs the
header, raises SizeOfHeaders from 0x400 to 0x600 to cover the complete
section table ending at file offset 0x408, restores all original mapped bytes
except the four intended hooks,
and preserves the 845-byte original overlay.

The [binary proof](evidence/dual-weapon-binary-fix-20260905.json) verifies:

- Every old section remains at the same RVA with the same size and permissions.
- Only the four hook regions change: 24 differing bytes in .text.
- Every other existing mapped byte, including all unrelated patch code, matches.
- The complete relocated new compositor, canonical rig, DWC2 data and QJS-emitted
  1,638-byte equipment hook match the tested sources.
- The complete legacy renderer and depth payloads match.
- All new hook targets map correctly and raw section ranges do not overlap.
- SizeOfHeaders covers all ten section headers.
- The state allocation owns complete VA pages and all emitted code remains
  outside the range passed to VirtualProtect.

## Verification and limits

[Page-protection execution report](evidence/dual-weapon-page-protection-20260905.json):
the archived crashing PE reproduces a non-executable fetch at 0x01E5F000
with return address 0x01E664A1 on the second empty-equipment call. The replacement
PE completes eight transitions and 19 real trampoline traversals with a
page-rounded VirtualProtect model. State starts uninitialized. Native equipment
and resource bodies are ABI stubs; this does not launch the game or render pixels.
The separate allocator test covers all 4,096 VA page offsets and rejects an
unaligned state range or one overlapping its trampoline.

[Resource execution report](evidence/dual-weapon-resource-fix-20260905.json):
1,296 synthetic packets constructed from real resource metadata across nine
equipment orders, all six pairs, eight
directions, six held frames and eight attack frames. All are handled without
generic fallback. The tests use item 1238/view34, item 13412/view45 and the
available generic axe/view6 resources. They intercept native draw calls and
check original image/palette ownership; they do not simulate GPU pixels.

Off-hand-only: the resource matrix covers 48 dagger held packets and 36 visible
native dagger attack packets. The separate geometry regression covers 96 held
draws across dagger and sword and requires exact equality to the corresponding
readable-compositor pair28 output. `Machine.invoke` synthesizes unit-scale
packets; `ctx[19]=0` disables the legacy core, and native draw calls are recorded
without executing the draw body. These comparisons prove the selected arithmetic,
not live geometry or equivalence to the historically accepted renderer. Solo
attack placement is unchanged.
Blank native frames do not produce a draw and are not invented by the test.

[Owner execution report](evidence/dual-weapon-owner-20260905.json):
eight warm-state equipment-transition/failure cases, balanced AddRef/Release, correct
thiscall/stdcall cleanup, preserved callee-save registers despite volatile
register clobbering, collision handling and null-trail behavior. A separate
compositor negative test fails the second hand after the first can prepare:
zero custom draws occur. Same-item duals produce distinct hand packets.
Foreign palettes are rejected even when the image pointer matches.
The new path succeeds with its legacy capture pointer deliberately unmapped.

The GRF reader also had a real evidence bug: +0x2A is version, not a second
count. Entry count is encoded_count - seed - 7. The fix reads seeded update.grf
correctly and stops dropping 512 entries from zero-seed version-0x200 archives.
The seeded/unseeded synthetic regression reads first, middle and last entries.

Reproduce from the repository root:

~~~powershell
.\.venv\Scripts\python.exe -B tools\build_dual_weapon_pose_transfer.py --client "D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes"
.\.venv\Scripts\python.exe tools\build_dual_weapon_compositor.py
.\.venv\Scripts\python.exe -B tools\verify_dual_weapon_pose_transfer.py --client "D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes"
.\.venv\Scripts\python.exe -B tools\verify_dual_weapon_owner.py
.\.venv\Scripts\python.exe -B tools\verify_dual_weapon_compositor.py --client "D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes"
.\.venv\Scripts\python.exe -B tools\test_grf_reader.py
node tools\verify_dual_weapon_profile.cjs
.\.venv\Scripts\python.exe -B tools\build_existing_dual_weapon_client.py --source Outputs\dual_weapon_resource_build\deployed-client-before-fix.exe --output Outputs\dual_weapon_resource_build\2025-07-16_dual_originals_fixed_existing.exe
.\.venv\Scripts\python.exe -B tools\verify_dual_weapon_page_protection.py --crashed Outputs\dual_weapon_resource_build\crash_ac2ff148.exe --fixed Outputs\dual_weapon_resource_build\2025-07-16_dual_originals_fixed_existing.exe
~~~

The build tool takes --tool-dir for an explicit MSVC x86 toolchain. The recorded
build used MSVC 14.51.36231. DWCP has a checked version, lengths, relocation
bounds and payload CRC; WARP rejects a missing/corrupt payload before writes.
Update the complete repository, including Inputs/DualWeaponRuntime, when pulling
the patch.

Live-rejected checks: dagger/dagger and off-hand-only on candidate `34c98e38…`.
The next candidate requires new native geometry evidence and fresh live checks;
repeating the same synthetic packet oracle cannot resolve the rejection. The
remaining pairs, per-view grips, held/attack transitions and occlusion also
remain unaccepted.
Dual poses outside the documented female Assassin matrix, other weapon classes,
male actors and other job families have no acceptance claim. Expanded custom
axes cannot display missing item-specific ACT/SPR files; the tested axe is view6.
The 2026 profile remains unsupported.
