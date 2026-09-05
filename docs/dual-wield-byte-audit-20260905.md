# Dual-wield byte audit — 2026-09-05

> Historical pre-fix audit. The later [resource fix](dual-weapon-resource-fix-20260905.md)
> adds a compositor and off-hand-only ownership. The legacy payload hashes below
> remain useful for identifying old binaries, not for describing the full current patch.


## Native-coordinate erratum — 2026-09-05

The [native-coordinate correction](dual-weapon-native-coordinate-fix-20260905.md)
resolves the coordinate-family uncertainty below. The active pair28 file center
`(11,-27)` and native `(-20,-49)` are the same resource: loading its 62x44 image
subtracts rounded half-width/height. The live working sword/dagger actor passes
the embedded family fingerprint and uses the accepted legacy core. Comparing
these two representations as evidence of different families was incorrect.

Live snapshots now exist for pair28, off-hand sword and dagger/dagger on EXE
`34c98e38905dc45ce568617b409b88b8cf551a1d6fecb4670258a183b1c36a21`.
Native CGameActor vtable `0x01094810` entry `+0x24` targets `0x00C40C20`, whose
second X/Y packet edges include +1 after scaling, even when mirrored. Weapon
channels5/6 bypass the `0x00605170` attachment-anchor path. The new audit verifies
146 valid live layer records and executes 192 native projections. Its initial
held matrix reproduces 288/288 errors on the rejected payload and zero on a
temporary corrected DWCP; see that report for scope and non-deployment status.
The historical pair gate, table contents and exact legacy bytes below remain
valid findings about the pulled core, but do not describe the newer compositor.

## Historical finding

The pulled patch is a **female Assassin-family, pair-28 compositor**, not a
generalized dual-weapon compositor. Sword/dagger and dagger/sword reuse fixed
physical sword/dagger roles. Dagger/dagger fails a literal pair-28 predicate
before pose lookup, and the embedded DWR3 also has no dagger/dagger records.

The user no longer has the failing EXE. These results establish the behavior
of the pulled source and a fresh isolated WARP build. They do not reconstruct
the deleted EXE or accept any new visual behavior.

Reproducible evidence:
[report](evidence/dual-weapon-20260905/report.json),
[disassembly](evidence/dual-weapon-20260905/core-scope.disasm.txt),
[verifier](../tools/verify_dual_weapon_scope.py).

## Actual artifacts

Baseline source: commit 6d108f2, before this audit's header/profile correction:

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| QJS | 283,189 | 50DA8C4D3A40BE954630C1583C26DFECA251955C5DA1B32D03F614AAB6A534F8 |
| Runtime core | 63,177 | 233F65B298BFEC24AC1E79DF2BE487C4468D2BFDDF69F84314C8B45EBA3FC4A5 |
| Embedded DWR3 | 16,044 | 8AAFF54EEBD6A574A7039362F2863F3D8D6EDA1CA771BD3D41258E89ECDBA4A0 |
| Depth helper | 1,380 | E2907B79240E3A9341F84F1F7A58948576C23E2626FE95BC1F482849A4149F80 |

The runtime has 432 relocations. Rig CRC32 after the 20-byte header is
9B91515F, matching the header. All three payloads are byte-identical after
this change.

This is not the 65,548-byte/441-relocation 85B core or the
68,364-byte/460-relocation pair25 framefix core in historical handoffs.
Their defects cannot be attributed to this payload without a new trace.

Native input: PE32/x86, machine 0x014C, image base 0x00400000,
2025-07-16 Ragexe, SHA-256
73349F3606DE8E9535D91B73E0177813C38369F06795F5A91200715A177F1A9F.
Compiler provenance of this embedded core was not recovered; historical
pinned-toolchain reproductions concern different cores.

## First barrier: hardcoded family/pair predicate

These offsets are **within the extracted core**, not native Ragexe addresses:

~~~asm
core+4060  83 7F 08 00           cmp dword ptr [edi+08], 0 ; rig exists
core+4071  83 7A 38 00           cmp dword ptr [edx+38], 0 ; female row
core+407B  83 7A 2C 1C           cmp dword ptr [edx+2C], 28
core+407F  0F 85 8D 00 00 00     jne core+4112
~~~

EDX is the retained actor registry row: +2C is pair type, +30/+34 are base
weapon types and +38 is gender. Subsequent instructions accept only (2,1)
or (1,2) before probing the native ACT family fingerprint. Pair25 (1,1)
is rejected before that fingerprint probe.

With diagnostics disabled in the deterministic test context, rejection
reaches the unhandled return:

~~~asm
core+F19C  5F                    pop edi
core+F19D  33 C0                 xor eax,eax
core+F19F  5E                    pop esi
core+F1A0  81 C4 00 05 00 00     add esp,500h
core+F1A6  C2 24 00              ret 24h
~~~

The final-draw wrapper tests this return value and tail-jumps to the stock
draw trampoline on zero. A misplaced *custom* dagger/dagger draw therefore
is not explained by this source under the tested contracts. It would require
a different core, additional hooks, changed state, or different resources;
the deleted EXE cannot distinguish those possibilities.

## Second barrier: the embedded table is pair28-only

Counts include hidden records. A record represents one physical hand in one pose.

| Embedded state | Gender | Held records | Attack records |
|---|---|---:|---:|
| 9 | Female | 96 | 128 |
| 10 | Female | 96 | 128 |
| 6 — dagger/dagger | All | 0 | 0 |
| Other dual states | All | 0 | 0 |
| Solo/off-hand-only states | All | 0 | 0 |

The total is **448 records**, not the 1,344 records in
Inputs/DualWeaponAuthored/rigs/female-assassin-canonical.dwr3.
The QJS writes DualWeaponAuthoredRigHex. It does not read that external rig,
pose CSV, grip CSV or an edited ACT during patching. Editing those files
cannot alter the poses in this EXE.

There is no embedded DWC1/DWC2 table or correction-table pointer in the
current context. The classifier's positive expanded view is used only as a
predicate; expanded view IDs are not retained in the 60-byte actor row.
That is a missing input for generalized per-view registration, not evidence
of a stale selected-frame variable in an executing DWC2 path.

## Why the reversed mixed order works

At core+3FBD..4059 the core selects retained channel-5 or channel-6 resources.
It tests main type 1 at core+3FEB and off type 2 at core+400D, then swaps local
SPR/ACT resource roles. The physical sword and dagger keep their calibrated
roles when equipment order reverses.

The verifier executes these original instructions for both orders and checks
the SPR pointers at the family boundary. Correspondence holds across all
112 held/attack cells per order. This proves resource-role selection, not
final pixel geometry.

Dagger/dagger needs a dagger in the physical role formerly occupied by the
sword. Its hilt location, bitmap extent, source frame, mirror, baked blade
orientation and final rotation need not match the sword. Reusing the center
and angle of another bitmap is not a verified hand attachment.

Concrete samples from the local spritedata.grf corpus:

| Female Assassin ACT | Held action32/frame0 (x,y) | Attack action88/frame0 (x,y) |
|---|---:|---:|
| Generic dagger/dagger | (12,-33) | (15,-43) |
| Generic dagger/sword | (11,-27) | (18,-44) |

These are **whole combined-raster ACT offsets**, not two hand sockets.
Both have ACT rotation 0; this does not mean the blades have the same
orientation inside their SPR images.

In that corpus, item1238 has no visible sprite in action80 frames0/1.
Item13412 has sprite2 at (25,-61) and (31,-65) respectively. A blanket
88..95 to 80..87 remap is therefore not a complete source-frame rule.

The historical report records entry names, hashes and raw file layer fields;
active archive priority and loose-file overrides were not resolved at that
point. **Corrected:** pair28 file center (11,-27) normalizes to native
(-20,-49,sprite0), matching the core fingerprint. Later live resource reads
confirm this exact family. The earlier isolated build still is not the deleted
live baseline; the linked native-coordinate audit identifies the later actual
EXE, snapshots and dispatch path.

## Stale information versus verified faults

- **False success on 2026: confirmed and fixed.** SupportsPose:false used to
  make validation succeed and application return true without writes.
  Validation now returns false; direct application throws before EXE access.
- **Registry overrun: absent in this core.** Both equipment code and core use
  60-byte rows. 0x1000 + 256*60 = 0x4C00, below the 0x5000 allocation.
  The 68-byte/0x5400 calculation describes another build.
- **Native slot replacement/action remapping: stale header.** The current
  equipment hook restores the requested stock state before publishing
  retained references. Capture/final-draw/depth hooks own rendering;
  native ACT call 0x00D36EE4 remains stock.
- **No family restrictions: false as a scope statement.** A literal
  female/pair28 predicate precedes the ACT fingerprint check.
- **Only data work remains: false for this core.** Supplying the external
  all-pairs rig in emulator memory still rejects pair25 at the pair gate.
  Code, data and verification must change together.
- **DWC2 attack/selected-frame bugs and pair25 raw-pixel fixes:** historical,
  not reproduced here because this core contains no DWC2 path.
- **Universal body/socket or rotation conclusions:** old results reject the
  tested models on their datasets, not every possible compositor.
  Pair28 rotation/mirror correspondence is not acceptance for all views.

No stale X/Y variable was demonstrated in this payload. The proven expansion
blockers are explicit restrictions and absent registration data. Capture-ring
lifetime, actor-address reuse and device lifecycle require live instrumentation
before any claim of correctness.

## Rebuilt EXE and exact addresses

Isolated output:
Outputs/dual_weapon_audit_20260905/dual_weapon_pair28_scope_audit_20250716.exe

SHA-256:
A0497CC5F11ECFAF7F0FA0B0B58441162E790AC53D7D22A3D57DADA5AAE6036B

This is a single-patch audit artifact, not a full game profile or an accepted
dagger/dagger fix. No deployed EXE was replaced.

| Site | Native VA | File offset | New bytes | Destination |
|---|---|---|---|---|
| Equipment | 00D403A0 | 0093F7A0 | E9 DB 8A 9F 00 | 01738E80 |
| Image capture | 00605D41 | 00205141 | E8 4A 31 13 01 89 45 94 90 | 01738E90 |
| Final draw | 00C4A0D0 | 008494D0 | E9 DB 7C AF 00 90 | 01741DB0 |
| Vertex depth | 00C4A647 | 00849A47 | E9 44 77 AF 00 | 01741D90 |
| ACT lookup, unchanged | 00D36EE4 | 009362E4 | E8 C7 85 9D FF | 0070F4B0 |

Core VA 01725640, file offset 00F5D640. Its pair gate core+407B is at
VA 017296BB, file offset 00F616BB **in this build only**. Addresses change
with allocation and patch composition; do not transplant these jumps.

## Verification

WARP_console loaded all scripts and wrote the target successfully. Verification
compares all 63,177 core bytes after 432 relocations, all 1,380 depth-helper
bytes after three relocations, the exact rig, and native hook preimages.
It also checks that the native ACT call remains unchanged.

Unicorn executed **1,008 cases**: six pair types, both mixed orders,
eight directions, six held frames and eight attack frames:

- 224 pair28 cases reached the family success boundary, with verified
  physical resource roles.
- 784 other-pair cases returned EAX=0 for stock fallback.
- Extra tests rejected male pair28 and pair25 with a populated all-pairs rig.

The emulator uses controlled native ACT lookup stubs and stops successful
cases before pose preparation. It proves these branches and resource roles;
it does **not** test final X/Y, source image correctness, body occlusion,
angles, native refcounts or live screenshots.

The Node regression test checks 2025 validation, allocation readiness, 2026
rejection, profile switching and zero EXE accesses on unsupported application.

~~~powershell
.\.venv\Scripts\python.exe -B tools\verify_dual_weapon_scope.py --exe Outputs\dual_weapon_audit_20260905\dual_weapon_pair28_scope_audit_20250716.exe
node tools\verify_dual_weapon_profile.cjs
~~~

Dependencies: pefile, capstone, unicorn (tested with Unicorn 2.1.4).
Optional --grf <archive> records the raw ACT corpus evidence.

## Implementation route

Keep the stock-first resource owner and two-packet rendering contract.
Recover/reconstruct readable source for this exact core before extending it;
do not combine unrelated historical payload offsets.

1. Resolve resource family independently of pair28, then select the ordered
   pair's pose. Preserve distinct physical hands for identical categories
   and identical views.
2. Retain expanded main/off views and select validated source
   action/frame/layer plus per-view/per-hand grip registration. A missing
   registration must keep the entire native draw.
3. Prepare both packets against the current stock packet's coordinate basis,
   then suppress stock only on complete success. Preserve native reference
   ownership and publish complete records atomically.

Keep coordinate domains explicit. A bitmap center is not a grip:
placement must account for its center-to-grip vector after scale, mirror and
rotation. A native combined ACT offset alone does not identify both grips.

Start with one dagger/dagger view pair, restore/author its missing held and
attack registrations, and trace actor, pair, view, hand, action, frame, layer,
source image, center, mirror and rotation at the final packet boundary.
Compare with pair28 controls and require live screenshots for contact and
occlusion. Missing dagger/dagger authoring and the deleted live EXE prevent
claiming that expansion complete in this audit.
