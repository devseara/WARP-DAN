# Dual-Wield Original Weapon Sprites - Production Scope and Expansion Handoff

Current authority: [old attack motion and held hilt-to-hand pixel-edge contact](dual-weapon-edge-contacts-20260905.md). Earlier acceptance records below are historical and keep their original scope.

Installed EXE: `4e233893...58636c`. The old attack motion and angles are restored with anatomical equipment slots; held poses use measured opaque-pixel boundary contacts. Seventeen non-Drake dagger/sword/axe views on the female Assassin Cross body are profiled. `95674dba` was rejected for hand overlap and is backed up. Live acceptance of the new edge-contact build is pending.

Male expansion: [asset audit, original generic animation previews and implementation design](dual-weapon-male-assassin-research-20260905.md). Research confirms missing held source cells in directions 2–5 for nine original views; male support is not enabled.

## Historical native-coordinate correction, 2026-09-05

The historical [native-coordinate correction](dual-weapon-native-coordinate-fix-20260905.md)
records the earlier center-based implementation. Live fields prove file ACT center `(11,-27)` becomes native pair28 layer
`(-20,-49)` by subtracting rounded half-image extents. Working sword/dagger uses
the accepted legacy core. Native producer `0x00C40C20`, reached through
CGameActor vtable `0x01094810 + 0x24`, adds +1 after scaling to the second edges,
even when mirrored. The old synthetic fixture missed both contracts.

The corrected reference basis is generated from the exact embedded legacy rig.
Tests match 146 valid live layer records, execute 192 native projections, and
reproduce 288/288 failing held reference-hand cases on the rejected payload.
The initial temporary `4ac1a812…` DWCP passes those 288 cases; this is neither a
deployed EXE hash nor live visual acceptance. Native channel5/6 routing bypasses
attachment-anchor adjustment at `0x00605170`, so body anchors are not the cause
of this current bug. The linked report separates the proven coordinate fix from
the accepted reference correction and the separately unaccepted new weapon families.

## Prior resource fix authority — 2026-09-05

[The resource fix and executable proof](dual-weapon-resource-fix-20260905.md)
records the earlier ownership/patching work. The patch now adds a readable compositor and a versioned external payload
for dual/off-hand original resources. It consumes the canonical DWR3 and DWC2,
retains actual item view IDs, and tests both hand packets before suppressing stock.
The earlier legacy core remains only for its exact accepted pair28 family.

The [byte audit](dual-wield-byte-audit-20260905.md) describes the pulled,
pre-fix implementation. Its pair28 gate and missing off-hand-only registration
explain the reported generic sprites; its scope statements are historical now.
Machine-code resource tests do not establish live coordinate, frame, angle, or
occlusion acceptance. Non-pair28 poses remain marked unaccepted.

## Live rejection and coordinate erratum — 2026-09-05

The current pose-transfer candidate
`34c98e38905dc45ce568617b409b88b8cf551a1d6fecb4670258a183b1c36a21`
has **failed live placement testing**. The user reports off-hand-only sword and
dagger misplaced in every direction, and dagger/dagger still incorrect; the
latest screenshots show the reported displaced poses. Sword/dagger and reversed
dagger/sword remain the reported working reference. Read the
[rejected candidate record](dual-weapon-pose-transfer-20260905.md) for its exact
hash, source, emitted examples, and test limitations.

The documented held `actor_target` values are weapon-center coordinates in an
actor basis; attack `packet_delta` values are offsets from a stock weapon packet
center. Neither table supplies anatomical hand sockets on the job sprite.
Subtracting source ACT layer centers does not establish that their selected SPR
images share a hilt registration. Copying the tables into a different packet
basis requires native transform evidence, not just matching CSV integers.

The rejected pose-transfer regression uses synthetic packets based on raw ACT
centers and SPR dimensions and sets `ctx[19]=0`, so it does not execute the
accepted legacy pair28 renderer. The later live audit now proves the raw/native
coordinate difference and the actual legacy family match. Its 208 unchanged pair28 draws and 96 matching off-only outputs
prove calculated-output relationships within that harness; they do not prove
live screen geometry or hand contact.

The historical job-sprite conclusion below was too broad. A sign mismatch in
its landmark fitting was also found and fixed: the old 37.553 px mean / 106.228 px
maximum result is invalid as a consistent fit. The corrected values are
31.908 / 107.055 px. Those results reject only the tested shared-origin,
fixed-vector model. They do not reject separate per-hand/per-body-frame sockets
and per-selected-image grips. See the
[job-sprite audit](dual-weapon-job-sprite-audit-20260905.md) for source hashes,
the independent regression, native ACT anchor evidence, and remaining options.

## Historical handoff records

The sections below preserve earlier experiments, source hashes, deleted
artifact paths and live reports. Their dates do not establish that their
implementation is present in the current patch. In particular, 85B's registry
overrun and DWC2 bugs, pair25 framefix binaries, and claims that expansion is
only a data task do not describe the current core. Use the current audit's
hashes and addresses when reproducing its findings.

## Current handoff - stable boundary and recovery plan - 2026-08-29

## Live status checklist - 2026-08-30

| Scope | Resource visibility | Placement/frame/angle | Status |
|---|---|---|---|
| Female Assassin pair 28 dagger+sword and reversed sword+dagger, views 34/45 | Both originals; generic suppressed | Live accepted across held/attack directions; body occlusion accepted | Working |
| Female Assassin pair 26 sword+sword | Both originals appear | Live result remains incorrect after the F8E7 state7 guide candidate | Not working |
| Female Assassin pair 25 dagger+dagger | Originals can appear | Coordinates, frames, and angles are generated/unaccepted | Not working |
| Female Assassin mixed axe pairs 29/30 | Current live result shows only the axe; the other hand is absent | Generated/unaccepted | Not working |
| Female Assassin pair 27 axe+axe | No complete accepted two-hand matrix | Generated/unaccepted | Not working |
| Expanded dagger/sword views other than accepted 34/45 | Originals may appear | Per-view placement, frames, and angles remain unaccepted | Not working |
| Axe expanded views 58-61 and 200-206 | Extracted Assassin ACT/SPR resources are absent; only generic axe view 6 is locally complete | No accepted grip data | Not working |
| Female Assassin Cross and Guillotine Cross | Share the Assassin hand family, but no complete job matrix has passed | Unaccepted | Not accepted |
| Female Shadow Cross | Separate hand-resource family has no authored pose/grip table | Unimplemented | Not working |
| All male Assassin-family jobs | Male held D2-5 policy and authored tables are absent | Unimplemented | Not working |

The all-original 85B/F8E7 lineage is now closed as an expansion base. It is a
resource-visibility oracle only. Exact binary and table audit found:

- the 85B EXE allocates `0x5000` bytes but uses 256 actor rows of 68 bytes at
  `state+0x1000`; the registry ends at `0x5400`, a `0x400` overrun;
- its correction code applies DWC2 only when `phase == 0`; all 184 attack
  correction records are skipped, including 136 non-identity records;
- the exact correction block reads DWC2 offsets `+8`, `+0xA`, `+0xC`, and
  `+0xD`, but never consumes the `selected_frame` byte at `+0xF`;
- F8E7 changes state 7 only. States 6, 8, 11, and 13 still contain the old
  generated relative-delta geometry; they are not the documented native-guide
  targets and are not user-authored placements;
- neither 85B nor F8E7 reads `docs/dual-wield-pose-matrix.csv` or the
  `ActEditorWork` files. The non-pair matrix rows are generated documentation,
  not imported runtime data;
- the only recovered user-edited ACT is the attack file under
  `tmp/safety_backup`; no builder references it, and the edited held ACT is
  absent. The remaining-pair ACT hashes still equal their generator manifest;
- DWC2 contains only views 1, 2, 6, and 34-47: 17 of the 45 dual-capable
  weapon views. A missing held correction aborts custom preparation;
- the renderer core is reproducible from the retained C only with the pinned
  MSVC x86 v14.29 toolchain: 65,548 bytes and all 441 relocations match 85B.
  The default MSVC 18 compiler produces different code and must not be used.

Pinned 85B core reproduction:

~~~text
call "C:/Program Files/Microsoft Visual Studio/18/Community/VC/Auxiliary/Build/vcvars32.bat" -vcvars_ver=14.29
cl.exe /c /TP /O2 /GS- /Gz dual_weapon_runtime_viewaware.c
compiler: Microsoft C/C++ 19.29.30159 x86
source SHA-256: DDE205D43165B3D23BA69DF8D98072D3A00BB2280A2680EFDF35EED7082B6226
runtime: 65,548 bytes / 441 relocations / 0 mismatches against 85B and F8E7
verifier: tmp/recovered_dual/audit_candidate_relocations.py
~~~
These are faults reported for the historical 85B/F8E7 lineage; they do not
establish the cause in another binary. Pair 28 in that lineage uses
accepted DWR3 values and identity corrections for views 34/45, so it does not
depend on skipped/missing generalized correction paths. Other pairs rely on
generated poses and per-view corrections that are incomplete or not executed.

### Replacement direction

Stop modifying the 85B EXE. Build a clean temporary QJS from the accepted
pair-28 owner/capture/envelope contract with these mandatory corrections:

1. allocate at least `0x6000` for a 68-byte view-aware registry, or allocate
   the registry separately;
2. retain `main_view` and `off_view` and preserve stock-first AddRef/Release
   ownership;
3. apply grip lookup in held and attack phases;
4. select the ACT frame from the grip record's `selected_frame` before loading
   the image/layer;
5. use explicit ordered pair-pose and per-view/physical-hand grip records;
6. prove all 224 pair-28 packets byte-equivalent before enabling one new pair;
7. enable only complete pair/view cells atomically; incomplete cells remain
   entirely stock and may never render one custom hand.

### Clean pair28 golden candidate - pending live validation

The replacement direction now has an isolated pair28-only implementation:

~~~text
EXE: C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/dual_weapon_clean_pair28_golden_test_20250716.exe
EXE SHA-256: 6B462C1DFC485C749188BDB361D344B03BFF2AAF1222B47F47574C05FF13FC62
QJS SHA-256: CB62F4B6A8C54279288BD4DEC55051CBA72EDCB40139E08EE58DB75146ABA456
runtime source SHA-256: 5F0A72B4AF2BFC912FAF85F9F3A74839BB245456AF8CCB7D25119855F62172B1
runtime core: 65,292 bytes / SHA-256 B5C63D3B525CC86F6F672E1E092EA0254792D9EDB4B27AF47F981217BE7A1062 / 441 relocations
~~~

It embeds only the accepted pair28 DWR3
`B2B7E5D47793E7D5E58187B878E5E7E566159D27C1E8D1B8B20A53DCBB9B5BCD`.
All other dual states are empty and remain stock. It embeds DWC2
`22F1401096FA19107B4667C7BB04374F96E097C9EC64C244BC0A92A10A040A8C`,
uses 68-byte rows with a `0x6000` state allocation, applies correction lookup
in held and attack, consumes exact `selected_frame`, and applies attack X/Y
corrections.

The golden verifier reports 224 pair28 records, zero transform mismatches,
208 visible cells, 16 intentional hidden cells, zero missing grip keys, 208
exact frame reads, and zero effective X/Y/mirror/rotation/frame mismatches.
The EXE contains one accepted DWR3, one DWC2, one `cps.dll` import, zero stale
bridge operands, one `PUSH 0x6000`, and one 68-byte registry stride.

This is not permission to enable another pair. Live validation must first
confirm the already accepted dagger+sword behavior in both equipment orders,
all held/attack directions, generic suppression, and body occlusion.

### REJECTED - Fresh readable native-slot restart

The pair28-only golden build was an infrastructure test and could never show
other pairs because its DWR3 contains state 9 only. The clean restart therefore
returns to the generalized readable native-slot implementation from commit
`d821668`, with no DWR3, DWC2, compositor, relocation, or envelope blobs.

~~~text
EXE: C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/dual_weapon_fresh_native_slots_test_20250716.exe
EXE SHA-256: 54B821844CE41C63B0752BCF9FD116197E7DCB6284D9B603091BA226A1A5ABC9
QJS SHA-256: D0E1F7217217561899F68E1D8FDF0B210000B970A7BBFD1165F85F946AC3BABF
QJS size: 20,903 bytes / CRLF / UTF-8 without BOM
~~~

The QJS is exactly the committed `d821668` source except for its isolated test
alias. It runs stock equipment setup first, resolves each equipped weapon
through the client item classifier, temporarily loads each item solo, retains
its original SPR/ACT with native AddRef, installs main/off originals in slots
5/6, restores the item fields, and remaps blank dual attack actions 88-95 to
80-87. It also supports off-hand-only equipment. Previous runtime evidence
covered dagger+sword, reversed order, sword+sword, and multiple item views
without item-ID allowlists.

This candidate is a resource-ownership reset, not accepted placement. Test all
weapon-type combinations and off-hand-only for original sprite continuity and
attack visibility. Do not use it to accept X/Y, angle, body occlusion, or draw
order. If resource visibility passes, the next implementation adds a fresh
hilt-based compositor and typed authored tables without reusing 85B data.

Live validation rejected the native-slot rendering strategy: only one original
weapon is drawn. Installing original SPR/ACT resources in slots 5/6 and
remapping actions does not cause the stock renderer to submit two independent
item packets. This result closes native-slot-only rendering. Preserve its
stock-first resource-retention logic, but use a custom two-packet compositor
for dual rendering. The compositor must prepare both hands before suppressing
the stock combined draw; a partial one-hand custom result is forbidden.

### Direct-target custom two-packet candidate - pending live validation

This is the first new EXE after closing native-slot-only rendering. The runtime
owns selected-image capture and final draw, prepares two independent original
item packets, and suppresses stock only after both packets succeed.

~~~text
EXE: C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/dual_weapon_direct_target_custom_compositor_test_20250716.exe
EXE SHA-256: 940F4128F531CDBEF6FB67F588019FC50E0980074C7EE7FCC020DC8F40B09EC8
QJS SHA-256: BF20F01904B6FEB0E0AC2CA5100667189F51D2FD382849D51126966AC2A385E0
runtime core SHA-256: DFC5196D17E206E5C0D77465848159FD62CA801BF168E1D96C4DF72E8150817D
canonical DWR3 SHA-256: CDA6C39AF7CB620FEBD02D6A5A84E9027993904D33BF1DE810CBFD1BE304B38F
canonical DWC2 SHA-256: 4BA59F903EE992217253679D21DF1564EB150B5B62D44ADB5BCF3742A4A6A815
~~~

Unlike rejected relative-delta rigs, metadata bit `0x40` makes the runtime
consume CSV X/Y, final mirror, final angle, source action/frame, visibility,
and draw order directly. Held X/Y is `actor_target`; attack X/Y is
`packet_delta`. The rig contains 1,344 female canonical records: 224 accepted
pair28 records and 1,120 generated/unaccepted guide records for pairs 25, 26,
27, 29, and 30. Reversed mixed orders normalize to their canonical state.

Offline ACT/SPR simulation covers 672 held/attack cells (1,344 hand records)
with zero missing pose keys, zero missing grip keys, and zero matrix mismatches.
Four absent visible generic-axe attack grip keys were added as explicit view-6
identity records. The EXE has one embedded rig and grip table, a `0x6000`
state allocation, 68-byte row stride, one `cps.dll` import, zero stale bridge
operands, and the four required equipment/capture/final-draw/depth hooks.

Only pair28 placement is accepted. Other pairs are visibility/coordinate-domain
tests and must not be promoted from this build. Named axe views remain absent;
use generic axe view 6. Solo/off-hand states 0-5 are empty and remain stock in
this candidate; custom off-hand-only rendering is a later authored cell.

### Headless pose/grip simulator

`tools/dual_weapon_sim/dual_weapon_sim.py` renders ACT/SPR masks from selectable
pair, phase, direction, frame, hand, and expanded views without patching or
launching Ragexe. It writes deterministic PNG plus JSON evidence containing
source action/frame/sprite, transform, grip correction, final center/mirror/
rotation, hashes, and provenance.

~~~text
py tools/dual_weapon_sim/dual_weapon_sim.py smoke
py tools/dual_weapon_sim/dual_weapon_sim.py render --pair 28 --phase attack --direction 6 --frame 3 --main-view 45 --off-view 34 --output <png>
py tools/dual_weapon_sim/dual_weapon_sim.py contact-sheet --pair 26 --phase held --main-view 45 --off-view 45 --output <png>
~~~

The pair28 held smoke gate renders 48 accepted cells with zero pose or grip
misses. Pair26 contact sheets are explicitly classified
`generated_unaccepted`. The simulator reduces live login cycles, but it cannot
promote generated data: the game remains the final acceptance gate for body
contact, channel ownership, occlusion, and device lifecycle.

### Stable and protected

The only production authority is
Scripts/Patches/AllowDualCustomWeaponSprites.qjs, SHA-256
42572E77B1A3EFFE605B97350269B7FAFED02C6DE6ABD67969FC15A4502778C2.
Do not replace it with a temporary all-pair QJS until a complete live matrix is
accepted. The promoted production EXE has documented SHA-256
7DF99320B376E1679F694889E097D79B96713CC891D054ABDC2C5C44FE448BEB.
No matching copy of that EXE is currently present under tmp or the game folder;
the production QJS and documented hash are the preservation authority.

The live-accepted production scope is deliberately narrow:

- 2025-07-16 client;
- female Assassin hand family;
- pair 28, dagger+sword;
- representative view 34 Zeny Knife in physical hand 1;
- representative view 45 Naght Sieger sword in physical hand 0;
- all eight held directions and six held frames;
- all eight attack directions and eight attack frames;
- both originals visible, generic pair suppressed, no intermittent loss;
- accepted direct mirror, D6/7 placement, and character-body occlusion.

The retained physical-role diagnostic EXE
tmp/recovered_dual/pair28_physical_role_fix_test.exe, SHA-256
A82CFA8CF79DBCB7D4A829E545FB2FE090B1BCCE5E3DE1AA60907FB9FF14B9C5,
is the reference for pair-28 view/hand behavior. A82 later live-accepted both
equipment orders through fixed physical-role resource mapping; this extension
is not promoted into the production QJS. Its DWC1 table is keyed by expanded
view and physical hand. It contains dagger views only for hand 1 and
sword views only for hand 0; it has no dagger-hand-0, sword-hand-1, or axe
registration. That absence is data we must author, not infer.

The character-envelope depth helper is also stable and required. Its
1,380-byte blob has SHA-256
E2907B79240E3A9341F84F1F7A58948576C23E2626FE95BC1F482849A4149F80.
It changes only custom weapon vertex Z at 0x00C4A647; it does not affect X/Y,
source frames, mirror, rotation, texture, or draw order. Removing it restores
body occlusion. Treat its bytes and hook contract as immutable during pose
work. Its readable C source, builder, and verifier are not in the clean tree;
recover and restore those provenance files before any semantic envelope change.
Splitting the generated hex into shorter chunks is presentation-only and must
reproduce the exact helper hash.

### Rejected current test

dual_weapon_all_pairs_pair28_direct_anchor_test_20250716.exe, SHA-256
B1301860DA5EE1D189B9B621A76CA66CB185B70BB942D64A520B2F85B00406A1,
is rejected by live validation. Do not promote it, use it as a base, or cite
its static verifier as visual acceptance. It showed original resources but
X/Y, frames, and angles remained wrong outside the calibrated pair-28
resources.

The failure is architectural:

- every dual pair was forced to pair-28 DWR3 state 9;
- pair-28 source actions and source frames were reused for unlike pair types;
- expanded view identity was discarded after ItemToWeaponView;
- current item ACT X/Y, mirror, and rotation were replaced by pair-28 anchors;
- one reference bitmap was substituted into another bitmap's coordinate
  system even though their canvas, baked blade angle, and hilt pixel differ;
- same-type pairs necessarily put one weapon into a physical hand for which no
  registration exists.

Native generic-pair comparison proves that pair-28 source mapping is not
universal. Relative to pair 28, the number of differing records is 56/224 for
pair 25, 94/224 for pair 26, 92/224 for pair 27, 80/224 for pair 29, and
96/224 for pair 30. For example, sword+sword attack direction 0 begins on
source frame 5 while pair 28 uses frame 4. The wrong bitmap is selected before
any X/Y correction is applied.

### Rejected native-exact detour - do not use as the recovery base - 2026-08-30

V1 through V6 moved the experiment away from the documented placement-only
failure. They added strict pose/grip lookup boundaries; a miss then failed the
custom draw closed to the stock generic pair. Those builds do not disprove the
original-resource owner. They are rejected as recovery bases.

V1, SHA-256 AADCD727758985009BC82425E0C0C102949BE1CB892AA6104C07149713984500,
was rejected immediately: login could stall and non-pair-28 originals fell
back to stock. The registration table described retained channel-5 original
item ACTs, but held rendering sometimes selected channel-6 glow ACTs and failed
the strict sprite gate. Pair 28 bypassed that gate, explaining why it survived.

V2 no longer transfers pair-28 poses. Pair 28 remains index-identical and keeps
its accepted live channel selection. Pairs 25, 26, 27, 29, and 30 use their own
native generic-pair source action, source frame, component X/Y, mirror, and
baked source image. Their held and attack art now always comes from the
retained channel-5 original item resources; the live stock channel remains the
packet geometry and depth basis. Expanded views retain their exact view ID and
must pass strict action/frame/layer/sprite registration before stock is
suppressed.

~~~text
EXE: C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/dual_weapon_native_pair_exact_v2_test_20250716.exe
EXE SHA-256: 6F3B882A5A92A90D9B7E5B679E4A92EB465A3A6F4F57258AA6C58F434912D022
QJS SHA-256: CCD9B30CDE4B62C40A4D1C5DEC2A5C6A041330234628BF10433458B94DFE2C11
runtime core: 68106 bytes, 425 relocations, SHA-256 09AEF7D92DA0C89A6E6E20FC7BB9A80B0040649C6AF0035AB0C6E70B2AE99E40
native rig SHA-256: 0323148F4C3EF385D810C15D41B45CF8F4CBFF7CB64F1CE02FC1947D9880A435
view-grip table: 420 records, SHA-256 F99E66F534D0D67B92EF1353D59E2EC49D17E3526EFE4F6E061706B7DF6C8260
~~~

Offline simulation covered 5,824 hand/view packets across complete female
views 1, 2, 6, and 34-47. It reported zero missing lookups, source-frame
mismatches, sprite-contract failures, geometry-bound failures, native-guide
geometry mismatches, or pair-28 index changes. Relocation and custom-import
audits also passed with zero mismatches and zero stale bridge operands.

Pixel reconstruction of the native generic-pair guides is not uniformly high
confidence: average target recall is 0.628 and the minimum is 0.273, with the
weakest rows concentrated in sword+sword and sword+axe attack frames. This EXE
is therefore a live test, not an accepted fix. Test pair 28 first, then pairs
25, 26, 27, 29, and 30 in both equipment orders. Report the first exact
pair/direction/frame failure rather than accepting the build globally.

The decisive earlier checkpoint is
`tmp/recovered_dual/expanded_female_assassin_family_recovery_test.exe`,
SHA-256
`85B03DBAF572031A3A22EAA70FEAB4A4EF4C75D0BDBDA58EC4FF8C9A6128D1BF`.
It retains the all-original resource/compositor path and removes the reversed
sword+dagger family rejection. Its non-pair-28 placement data is still
unaccepted. Resume from that ownership architecture and change only ordered
pair-pose and expanded-view grip data.

### Pair26 state7-only reference-view candidate - pending live validation

The first implementation step freezes the tested 85B EXE itself and replaces
only its single same-size DWR3 blob. The historical 85B QJS snapshot is not
retained, so recompiling reconstructed C is not accepted as byte-equivalent.

~~~text
EXE: C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/dual_weapon_pair26_state7_reference45_test_20250716.exe
EXE SHA-256: F8E7BF788A6D2AC876BFDB097BA2327DCC02039D1B53DDFAC9C92F411831B85D
base EXE SHA-256: 85B03DBAF572031A3A22EAA70FEAB4A4EF4C75D0BDBDA58EC4FF8C9A6128D1BF
replacement DWR3: 6EB250590BF54130167B7AC1D0F1A9AC0192A65F8097A951EDDC9F620AA7D18D
~~~

Only female Assassin state 7 `(2,2)` changes. Its 224 source action/frame,
mirror, rotation, visibility, order, and pair26-native target records are
translated from generic sword view 2 into calibrated reference sword view 45.
The original transform count and 19,512-byte DWR3 size are preserved by
reusing 90 of 112 state7-exclusive transform slots.

Static evidence:

- pair-28 index mismatches: 0;
- pair-28 resolved-transform mismatches: 0;
- non-state7 index mismatches: 0;
- pair26 reference-geometry mismatches: 0;
- view 45/46 DWC2 missing keys: 0;
- 448 held/attack/direction/frame/view simulations, with zero selected-frame
  and effective-geometry mismatches;
- the final EXE changes 787 bytes, all inside the one DWR3 allocation;
- DWC2 remains `22F1401096FA19107B4667C7BB04374F96E097C9EC64C244BC0A92A10A040A8C`;
- envelope remains `E2907B79240E3A9341F84F1F7A58948576C23E2626FE95BC1F482849A4149F80`;
- one `cps.dll` import and zero stale bridge operands.

This is a live-test candidate, not accepted placement. Validate pair28 first,
then sword+sword using views 45 and 46 in both equipment orders across all
held and attack directions. Do not test other pairs as evidence for state 7.
The complete documented coordinate/frame/angle data is in
docs/dual-wield-pose-matrix.csv, SHA-256
99DDD59A41F5FB5BE1E776B7055A2FF0D48719E47B80E6FC48C5D11C4E0A989B.
It contains 224 live_accepted_reference pair-28 rows and 1,120
native_guide_unaccepted rows for pairs 25, 26, 27, 29, and 30. The status
column is mandatory: native guide rows must not be presented as live accepted.

### Required replacement architecture

Retain the known-good resource-owner, capture-owner, direct-mirror, complete
prepare-before-suppress, and character-envelope code. Replace only pose and
weapon registration with two explicit data layers.

The ordered pair-pose key is:

~~~text
family, gender, ordered pair state, phase, direction, target frame,
physical hand
~~~

Each pair-pose record must contain:

~~~text
source action, source frame, target X/Y, target mirror, target rotation,
visibility, draw order
~~~

The expanded-view grip key is:

~~~text
family, gender, expanded weapon view, physical hand, phase, direction,
source action, source frame
~~~

Each grip record must contain:

~~~text
actual selected image/frame, local hilt X/Y, pivot correction,
mirror correction, rotation correction, and any non-unit scale correction
~~~

ACT-layer X/Y normalization is insufficient by itself. The hilt location and
blade orientation may be baked at different pixels inside each SPR canvas.
The runtime must consume the record's selected frame; storing a selected_frame
field but independently rescanning the ACT is invalid.

The equipment registry must retain main_view and off_view. A 68-byte row
requires at least 0x5400 bytes when the registry begins at state+0x1000; round
to 0x6000 or allocate the registry separately. Never restore the rejected
0x5000 allocation with a 68-byte row.

### Local evidence and availability

Present local evidence, useful but not production authority:

- tmp/recovered_dual/pair28_physical_role_fix_test.exe;
- tmp/recovered_dual/dual_weapon_runtime_base.c, SHA-256
  82D8015C5096A75243B419E232DAD406FAFBB0872CA7A4393856890432DF5FAD;
- tmp/recovered_dual/coverage/pair28_view_corrections.bin and CSV, DWC1
  SHA-256 ACEF905085D3D9BADA9E191005B0BF61EF9B838037129EA30E1D625194E3CD55;
- tmp/recovered_dual/coverage/assassin_generic_pose.hex, useful for native
  source mapping but rejected as final hand placement;
- tmp/recovered_dual/dual_weapon_debug.log and
  dual_weapon_signature_debug.log;
- the B130 QJS/C/DWA2 builders as negative evidence only.

The edited Act Editor sources previously supplied under Inputs/DualWeaponRig
are not currently present after cleanup. They must be restored or reattached
before authoring pair placements. Do not reconstruct their accepted values
from screenshots, offline pixel matching, or rejected generated tables. The
documented promoted 7DF EXE is also not currently retained locally.

### Staged implementation plan

1. Freeze the production QJS, DWR3 rig, and envelope-helper hashes. Build
   experiments under a temporary alias only.
2. Restore and version the minimal authoring closure before changing runtime
   behavior: pair-pose exporter/importer, body-guide and hilt validator, asset
   hash manifest, golden verifier, and readable envelope C/builder/verifier.
   The existing tmp/recovered_dual/ActEditorWork/remaining_pairs,
   prepare_remaining_pair_workspaces.py, generate_assassin_generic_pose.py,
   and compile_weapon_coverage.py are local seeds, not clean-checkout
   authority. Recover or reattach the missing user-edited Act Editor inputs.
3. Add a golden pair-28 equivalence verifier. For all 224 records it must
   reproduce the accepted source action/frame/layer/sprite, prepared packet
   X/Y, mirror, rotation, visibility, and order before any new pair is enabled.
4. Publish expanded main_view/off_view safely and fix the registry allocation.
   Prove add-ref/release, collision, relog, and equipment-change behavior
   before altering poses.
5. Calibrate expanded views inside accepted pair 28 first. Keep view 34 and
   view 45 as identity canaries, then validate generic Knife view 1, generic
   sword view 2, dagger views 35-38, and sword views 39-47 in both equipment
   orders. This stage adds grip registration without changing the base pose.
6. Implement the ordered pair-pose table from native generic pair ACT source
   structure and user-authored Act Editor/body-guide placement. Only authored
   data may declare accepted hand placement; generated or pixel-matched rows
   remain Draft and are excluded from runtime.
7. Add female dagger+dagger pair 25 and sword+sword pair 26. These force both
   dagger-hand and both sword-hand registrations and expose missing cross-hand
   data without introducing axes.
8. After pair 25/26 pass, add a live representative axe and author axe+axe
   pair 27, dagger+axe and axe+dagger, and sword+axe and axe+sword as distinct
   ordered states.
9. Add female Shadow Cross as a separate hand-resource family until hashes and
   live tests prove equivalence. Validate Assassin Cross and Guillotine Cross
   against the shared Assassin family rather than assuming it.
10. Solve the male held-source policy for directions 2-5 before enabling any
    male family. Female records must never be copied into male held states.
11. Promote one state/view cell at a time only after the complete live matrix
    passes. Until then, any missing pair-pose or grip record fails the whole
    pair back to stock; never suppress stock after preparing only one hand.

### Verification gates before every handoff

Offline/source gates:

- CRLF-only, UTF-8 without BOM QJS;
- deterministic pose and grip table hashes;
- no missing visible records and no unused selected-frame fields;
- pair-28 golden equivalence with zero packet mismatches;
- actor-row size/allocation bound proof;
- all core relocations resolved;
- one cps.dll import and zero stale bridge operands;
- accepted DWR3 and envelope-helper hashes unchanged.

Live gate for each new pair/family/gender cell:

- both originals visible in both equipment orders;
- correct hilt-to-hand contact, X/Y, frame, mirror, angle, scale, and palette;
- all held and attack directions/frames, including intentional hidden frames;
- no generic duplicate and no intermittent disappearance;
- accepted body occlusion;
- repeated equip/unequip, relog, map change, Alt+Tab/device reset, and clean
  exit;
- unsupported or incomplete states remain entirely stock.

## Promoted production checkpoint - 2026-08-29

After live acceptance, the final diagnostic renderer was promoted verbatim to
`AllowDualCustomWeaponSprites.qjs`; only its exported alias and header date
changed. A promotion rebuild produced the exact accepted EXE hash.

| Artifact/fact | Value |
|---|---|
| Main QJS bytes | 283189 |
| Main QJS SHA-256 | `42572E77B1A3EFFE605B97350269B7FAFED02C6DE6ABD67969FC15A4502778C2` |
| Accepted 2025 EXE bytes | 21650253 |
| Accepted 2025 EXE SHA-256 | `7DF99320B376E1679F694889E097D79B96713CC891D054ABDC2C5C44FE448BEB` |
| Embedded runtime core bytes | 63177 |
| Embedded runtime core SHA-256 | `233F65B298BFEC24AC1E79DF2BE487C4468D2BFDDF69F84314C8B45EBA3FC4A5` |
| Core relocations | 432 |
| Embedded DWR3 rig bytes | 16044 |
| Embedded DWR3 rig SHA-256 | `B2B7E5D47793E7D5E58187B878E5E7E566159D27C1E8D1B8B20A53DCBB9B5BCD` |
| Rig records | 224 |
| Custom bridge audit | one `cps.dll` import, zero stale operands |

The 2026 profile remains fail-closed: `SupportsPose=false`, so selecting the
patch performs no pose writes for that client.

No commit was created during promotion or cleanup.

## View-aware normalization test correction - 2026-08-29

The first temporary view-aware candidate crashed at `0x0182AC47` before its
normalization logic could be evaluated. The recovered COFF extractor serialized
relocations with Python tuple syntax:

~~~text
[(offset, target), ...]
~~~

QuickJS parsed each tuple as a comma expression, so `relocation[0]` and
`relocation[1]` were undefined and all 442 embedded core pointers remained
zero. The crash occurred when the runtime first dereferenced one of those null
string pointers. The extractor now emits JavaScript arrays:

~~~text
[[offset, target], ...]
~~~

The replacement test EXE is
`dual_weapon_viewaware_normalization_relocation_fixed_test_20250716.exe`,
SHA-256
`8D3D25E0FB45D6575DE6A88CC9BB43129D4959C89D15E4121F389105BAFDA2C3`.
Its PE audit resolves all 439 core relocations with zero mismatches, preserves
the accepted DWR3 rig hash, and has one `cps.dll` import with zero stale bridge
operands. This remains a temporary female pair-28 test candidate; it is not the
promoted production checkpoint until live validation passes.

Live validation rejected that relocation-fixed candidate for rendering:

- attack animation remained correct because phase 1 continued to use the
  current item ACT layer;
- held/attack stance broke because phase-0 reference index 0 contained the
  sword pivot while actor-row main type 1 is the dagger, and reference index 1
  contained the dagger pivot while actor-row off type 2 is the sword;
- reversed sword+dagger remained stock because the temporary QJS guard admitted
  only ordered `(1,2)`.

The replacement is
`dual_weapon_pair28_both_orders_stance_fix_test_20250716.exe`, SHA-256
`B94B87AF8C1CF255C02EE9DAAA8F98466827A814D96BDCED277D82A5B8B96C94`.
It indexes the phase-0 reference by base weapon type, not equipment slot, and
maps reversed `(2,1)` to the accepted `(1,2)` pose while swapping only the
authored hand record. Its PE audit resolves all 441 core relocations, preserves
the accepted DWR3 rig hash, and reports zero stale bridge operands. It remains
temporary pending live acceptance.

Live validation also rejected that type-indexed-reference candidate: stance
remained broken. Canonical reference substitution is therefore removed rather
than refined. The next candidate,
`dual_weapon_pair28_orders_known_good_stance_test_20250716.exe`, SHA-256
`6C1C354C6DCA4424EF77ACE231D41A0D6F9311425D8A6D4485A55C9866860D7F`,
uses the accepted item ACT layer directly for stance center, scale, source
frame, mirror, and rotation. Its only runtime behavior added beyond the
accepted direct-mirror path is reversed pair-28 lookup by swapping authored
hand records. It has the accepted EXE byte size, preserves the rig hash,
resolves all 430 core relocations, and has zero stale bridge operands. It is
temporary pending live acceptance.

## Expansion compiler checkpoint - 2026-08-29

The expansion has a deterministic resource/lookup coverage compiler at
tmp/recovered_dual/compile_weapon_coverage.py. It parses the live CP949
datainfo and CLS weapontable.lub tables, matches normalized ACT/SPR resource
names, reproduces runtime layer/frame selection, reads the embedded DWR3 index,
and emits DWC1 per-view corrections. It is authoritative for resource identity,
visibility, and lookup coverage only; it is not an authority for visual hilt
placement. It does not modify any GRF.

The first compiler run intentionally stopped at 104/112 view-34 records. The
eight unresolved slots were hidden-hand attack records; the runtime does not
prepare those hands. The compiler now derives required counts from DWR3
metadata and excludes hidden records exactly like the renderer.

Current deterministic results:

- 45 dual-capable views in weapontable.lub;
- one retained Assassin resource family with 170 ACT files;
- 90 gender/view coverage rows;
- 34 ACT+SPR rows available and 25 held+attack complete;
- 1,696 female pair-28 corrections with zero missing visible records;
- view 34: 96 identity records, all exact zero vectors;
- view 45: 112 identity records, all exact zero vectors;
- correction table SHA-256
  037403F6F2564321FD66BC2C83DCEE1F784FDE94EF19B3318020111435AC316D.

The live-test candidate is
dual_weapon_pair28_weapontable_corrections_test_20250716.exe, SHA-256
D1140EE2A7A8847AECBAB3D7CF3CB73F3D61AFA3CF1CACF66B66C9601F5AF211.
It keeps attack phase unchanged, applies corrections only to phase-0 ACT
X/Y/mirror/rotation, admits both pair-28 orders, and fails closed to stock when
a correction is absent. The accepted DWR3 rig remains byte-identical. Static
gates report 432/432 core relocations resolved, one embedded DWC1 table, one
cps.dll import, and zero stale bridge operands. This candidate is temporary
pending live acceptance.

### Runtime view/hand trace result

The diagnostic EXE and local OutputDebugString collector captured the actual
row and correction keys. The accepted (1,2) row was:

~~~text
mainType=1 offType=2 pair=28 mainView=34 offView=45 swap12=1
~~~

Every correction lookup succeeded; no reason-1 or reason-2 fallback occurred.
The trace proved the earlier table was keyed to logical equipment slots while
the renderer had already swapped the retained resources. DWR3 physical hand 0
draws the sword and physical hand 1 draws the dagger. Reversed (2,1) must
reuse state (1,2) without swapping authored hand transforms.

The same trace captured main=1 off=6 followed by FAIL_FAMILY. Other base pair
types remain generic because the current DWR3 family selector and pose index
contain only pair 28; this is independent of per-view correction lookup.

The regenerated physical-role DWC1 table contains 1,632 records, SHA-256
ACEF905085D3D9BADA9E191005B0BF61EF9B838037129EA30E1D625194E3CD55.
The replacement EXE is
dual_weapon_pair28_physical_role_fix_test_20250716.exe, SHA-256
A82CFA8CF79DBCB7D4A829E545FB2FE090B1BCCE5E3DE1AA60907FB9FF14B9C5.
It preserves the accepted rig, resolves all 431 core relocations, and reports
zero stale bridge operands. Live validation confirmed original sprites, coordinates, frames, and angles
for both dagger+sword equipment orders using representative view 34 in
physical hand 1 and view 45 in physical hand 0. It does not accept generic
Knife or other expanded views. This is the frozen pair-28 physical-role
checkpoint.

### Female Assassin all-pair expansion candidate

The captured FAIL_FAMILY result was addressed by generating canonical states
for pairs 25, 26, 27, 29, and 30 from the native generic pair ACT/SPR assets.
The generator calibrates relative native-pair component deltas against the
accepted pair-28 physical hands instead of replacing pair-28 data. It also
encodes 230 native held records that require source actions 80-87 in transform
metadata.

The expanded DWR3 artifact:

- preserves every accepted pair-28 index;
- contains 1,344 female records, 224 for each canonical pair state;
- adds 1,120 indices and expands the transform table from 108 to 686 entries;
- SHA-256
  0BC46C80E2AB0EFEF829C3B6BDE77631AA697540F2520D22F8173BC03385F298.

DWC2 replaces hand/frame-specific DWC1 keys with source-action/frame/base-type
keys, allowing corrections to be shared safely across pair states. It contains
440 records with zero missing keys, SHA-256
22F1401096FA19107B4667C7BB04374F96E097C9EC64C244BC0A92A10A040A8C.

The live-test EXE is
dual_weapon_female_assassin_all_pairs_test_20250716.exe, SHA-256
EA9FAA9110BD1468FD22C7E4EF42982BAAD2F8C3F5B53BFEC307D8596B218E2D.
Static gates confirm six complete canonical states, unchanged pair-28 data,
434/434 core relocations, one cps.dll import, and zero stale bridge operands.
It is temporary pending live visual acceptance for pairs 25-27 and 29-30.

Live validation rejected the generated non-pair-28 geometry: original sprites
became visible, but coordinates, frames, and angles were incorrect. Sword+sword
reached DUAL_HANDLED with live signature -21,-60; sword+axe used -18,-61;
dagger+dagger used -18,-48. The retained corrected pose CSV contains authored
per-hand geometry only for pair 28, so pixel-match-derived records must not be
described as accepted coordinates for the other pairs.

The same test also exposed an order-sensitive family rejection for
sword+dagger. DWC2 simulation proved every visible accepted pair-28 key exists;
the failure occurred before lookup. The recovery EXE removes that family-order
rejection while retaining pair-specific signature logging:
dual_weapon_family_gate_recovery_test_20250716.exe, SHA-256
85B03DBAF572031A3A22EAA70FEAB4A4EF4C75D0BDBDA58EC4FF8C9A6128D1BF.
It resolves all 441 core relocations and has zero stale bridge operands.
Non-pair-28 geometry remains experimental pending Act Editor authoring.

### REJECTED - All-pair direct reuse of the accepted pair-28 pose

A universal-reuse experiment copied the accepted pair-28 sword+dagger
coordinates, source frames, mirrors, rotations, visibility, and order to all
female Assassin native dual pairs. It proved that those values are not a
universal registration system.

The first implementation had a per-view coverage hole, pair-dependent attack
basis, and a 68-byte registry overflow. The replacement removed the view gate
and passed static PE checks:

~~~text
EXE: dual_weapon_all_pairs_pair28_direct_anchor_test_20250716.exe
SHA-256: B1301860DA5EE1D189B9B621A76CA66CB185B70BB942D64A520B2F85B00406A1
DWA2: 6FDE3CF9CC3CCE614EDFA2C50EC9E8D1444A6D1395ADC138BDC95DFC092D11EB
~~~

Live testing rejected it. Original resources appeared, but X/Y, source frames,
and angles were wrong outside the calibrated view-45 sword in physical hand 0
and view-34 dagger in physical hand 1.

The failure is now closed and must not be retried:

- all pairs were forced to pair-28 DWR3 state 9;
- pair-specific source action/frame mappings were discarded;
- expanded view identity and per-hand registration were discarded;
- current item ACT X/Y/mirror/rotation and local SPR hilt geometry were not
  preserved;
- same-type and axe pairs used physical-hand roles for which no accepted data
  exists;
- static pair-28 equivalence was incorrectly treated as evidence for other
  pair states.

Relative to pair 28, native source mapping differs in 56/224 pair-25 records,
94/224 pair-26 records, 92/224 pair-27 records, 80/224 pair-29 records, and
96/224 pair-30 records. A universal pair-28 anchor table cannot select the
correct bitmap, baked orientation, or hilt. Use the current handoff's
pair-pose plus per-view/per-hand grip architecture instead.

## After-Hit floating-weapon regression and pause - 2026-08-31

The direct-target candidate (canonical DWR3/DWC2
`CDA6C39AF7CB620FEBD02D6A5A84E9027993904D33BF1DE810CBFD1BE304B38F` /
`4BA59F903EE992217253679D21DF1564EB150B5B62D44ADB5BCF3742A4A6A815`) regressed
held/After-Hit (source actions 32-39) for the already-accepted dagger+sword
pose while adding pairs 25-30: attack (80-95) stayed correct, but After-Hit
showed the custom weapon detached from the hand, reported as "floats away
from hand." Confirmed dagger+sword worked correctly before expansion to the
other weapon types began; the regression appeared only after that expansion
work, not before it.

Root cause, confirmed live (`BOH_DWOWN`, 2026-08-31): each After-Hit
occurrence issues four draw calls through the hooked wrapper -- one untagged
combined/body packet (priority tag equals the actor pointer, constant
`stockImage` regardless of pose) and three numbered weapon-priority packets.
Exactly one numbered packet matches the live/ring capture and succeeds (100%
reliable across every captured occurrence, always last of the four); the
other three fall through to the stock trampoline every frame. `prepare_hand`'s
geometry is verified byte-correct against the canonical pose+grip CSV
whenever it runs (`tools/dual_weapon_sim/analyze_direct_target_trace.py`,
zero mismatches across 44 captured rows) -- this is not a coordinate-mode or
formula bug in `prepare_hand`.

Suppressing the three declined packets (returning "handled" instead of
falling through) was tried and rejected: it starves the separate
character-envelope Z-occlusion helper (`BOH_DWZ`,
`DualWeaponCharacterEnvelopeCoreHex`) of the depth samples it builds from
those same stock draws, and it fails closed, hiding the whole character. That
helper's contract (see "Character-envelope depth" above) must not be touched;
any fix needs a mechanism that keeps every stock draw call intact.

Live calibration to re-author the After-Hit pose data directly was attempted
next, since the coordinate math is already proven correct and only the
authored delta might be wrong. Both the numpad calibration keys and a
NumLock-independent arrow-key fallback failed to register in-game
(`ctx->key_state`/`GetAsyncKeyState` returned no edge in either build); a raw
return-value diagnostic to isolate why was proposed but not completed.

Work is paused here at the user's request after a long expansion effort with
repeated live-rejected candidates (see the sections above). Pair 28
dagger+sword, both equipment orders, held and attack, remains live-accepted
in production (`Scripts/Patches/AllowDualCustomWeaponSprites.qjs`) and is
unaffected by any of this: production's hash has not changed during this
entire investigation.

Next steps, if resumed:

- finish the raw `key_state()` diagnostic before any further live calibration
  attempt, or use the headless simulator
  (`tools/dual_weapon_sim/dual_weapon_sim.py`) to iterate without the game;
- do not suppress the three declined per-occurrence packets without first
  understanding exactly which stock draw(s) the character-envelope helper
  depends on;
- consider whether After-Hit needs a draw-order/Z contract distinct from
  attack's, since attack (source actions 88-95) is unaffected by this bug.

## Live-accepted scope

The user confirmed the following complete matrix in game:

| Dimension | Accepted value |
|---|---|
| Client | 2025-07-16 Ragexe 175220998 |
| Hand family/job | female Assassin |
| Pair type | 28, dagger + sword |
| Representative resources | item 1238 and item 13412 |
| Held stance | all 8 directions, 6 frames |
| Attack | all 8 directions, 8 frames |
| Original item sprites | both visible as expected |
| Generic suppression | accepted; no generic+original blink |
| Character occlusion | accepted |
| D6/7 off-hand mirror | accepted |

Unsupported family, gender, pair, phase, or missing-record states fail closed
to the stock renderer. The live-accepted scope must not be described as global
all-job coverage yet.

## Why the implementation works

### Resource ownership

The equipment wrapper executes the stock update first, obtains each equipped
item's complete original SPR/ACT through the client path, restores the stock
dual state, revalidates the actor, and publishes a complete bounded row last.
Temporary solo states are never rendered. Actor invalidation clears ownership
before releasing retained resources.

There is no item-ID, view-ID, job-ID, or filename allowlist in the renderer.
The client weapon classifier provides type 1 (dagger), 2 (sword), or 6 (axe),
and the DWR3 table selects family/gender/pair/phase/direction/frame/hand data.

### Capture-owner compositor

The selected-image hook records actor, animation channel, stock image, and ACT
layer observations in a 128-entry ring. The final wrapper accepts one fresh
owner and consumes sibling/stale weapon draws. It prepares both custom packets
before suppressing stock, so preparation failure falls back safely.

Attack owner channels are:

~~~text
frame:    0 1 2 3 4 5 6 7
channel:  5 5 5 6 6 5 6 6
~~~

Channels 5 and 6 are animation resource channels, never physical hands.

### Direct authored mirror

The final packet bounds are normalized before reversal. The old formula mixed
the target mirror with the stock-layer mirror, inverting directions 4-7.
The accepted core removes two stock-layer XOR instructions:

~~~text
core offsets: 0x7B57, 0x8DA7
old bytes:    33 77 0C
new bytes:    90 90 90
~~~

The output mirror is now the item layer mirror XOR the authored DWR3 bit.

### D6/7 packet-basis proof

Held placement uses:

~~~text
center = stock_packet_center +
         (item_layer + authored_delta - stock_layer) * packet_unit
~~~

Live item/stock capture proved the accepted symmetry:

| Directions | X/Y bracket |
|---|---|
| 0-1 | `(+22, -21)` |
| 2-3 | `(+15, paired-Y)` |
| 4-5 | `(-15, paired-Y)` |
| 6-7 | `(-22, -21)` |

Directions 6-7 preserve `source_frame=0`, `dx=-18`, `dy=-9`, and change only
the off-hand `mirror_xor` from 1 to 0. Replacing those coordinates with
offline grip values was rejected because it collapsed the item into the body.

### Character-envelope depth

At the completed-vertex hook `0x00C4A647`, the helper changes only custom
weapon Z:

~~~text
Znew = min(Zstock, P0(x,y) - four_quanta, P1(x,y) - four_quanta)
~~~

X, Y, RHW, UV, color, packet geometry, item identity, and draw order remain
unchanged. This is the accepted body-occlusion architecture.

## Accepted transform facts

This section is generated from the accepted-only source files; copied
screenshots, rejected rigs, and native-guide rows are not authority.

~~~text
pose source: Inputs/DualWeaponAuthored/poses/female-assassin-pair28.csv
pose SHA-256: 7329786D42A9FBCAA9C0975251349702B434F6251C9023B655469C3B229CC898
grip source: Inputs/DualWeaponAuthored/grips/female-assassin-views34-45.csv
grip SHA-256: 665F2967A18163D452602DFF60A7EFF26DFB59726648A46ECFF7EFCBB4E648E0
pose records: 224 (96 held, 128 attack)
~~~

Physical hand 0 is sword view 45; physical hand 1 is dagger view 34.
Held X/Y values use `actor_target`; attack X/Y values use `packet_delta`.
Draw order is sword 1, dagger 0. Mirror and angle are final authored
targets. `sf` is the item ACT source frame, not the target body frame.

### Held pose

All held rows use `source_action=32+direction` and `source_frame=0`.

#### Main hand - sword view 45

| Dir | Mirror | Angle | F0 X,Y | F1 X,Y | F2 X,Y | F3 X,Y | F4 X,Y | F5 X,Y |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | `90°` | `0,-9` | `0,-10` | `1,-10` | `1,-10` | `-2,-9` | `0,-9` |
| 1 | 0 | `90°` | `1,-9` | `2,-9` | `2,-10` | `1,-11` | `-1,-9` | `2,-9` |
| 2 | 0 | `-70°` | `-62,-18` | `-62,-20` | `-61,-21` | `-61,-22` | `-56,-22` | `-56,-22` |
| 3 | 0 | `-70°` | `-62,-18` | `-62,-20` | `-61,-21` | `-61,-22` | `-56,-22` | `-56,-22` |
| 4 | 1 | `80°` | `28,-17` | `29,-18` | `31,-18` | `31,-19` | `30,-18` | `29,-17` |
| 5 | 1 | `80°` | `28,-17` | `29,-18` | `31,-18` | `31,-19` | `30,-18` | `29,-17` |
| 6 | 1 | `-90°` | `-7,-10` | `-6,-11` | `-8,-12` | `-7,-10` | `-8,-9` | `-7,-9` |
| 7 | 1 | `-90°` | `-7,-10` | `-6,-11` | `-8,-12` | `-7,-10` | `-8,-9` | `-7,-9` |

#### Off hand - dagger view 34

| Dir | Mirror | Angle | X,Y (F0-F5) |
| ---: | --- | --- | --- |
| 0 | 0 | `0°` | `15,-57` |
| 1 | 0 | `0°` | `15,-57` |
| 2 | 0 | `0°` | `-22,-43` |
| 3 | 0 | `0°` | `-22,-43` |
| 4 | 1 | `0°` | `-12,-43` |
| 5 | 1 | `0°` | `-12,-43` |
| 6 | 1 | `0°` | `-51,-57` |
| 7 | 1 | `0°` | `-51,-57` |

### Attack pose

All attack rows use `source_action=80+direction`. Main-hand F6/F7 are
the 16 intentional hidden records; the off hand remains visible.

#### Main hand - sword view 45

| Dir | Mirror | F0 | F1 | F2 | F3 | F4 | F5 | F6 | F7 |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | `3,7,-143°; sf=4` | `3,7,-143°; sf=4` | `-12,-17,37°; sf=4` | `-21,-33,50°; sf=4` | `16,-29,50°; sf=4` | `-15,-31,50°; sf=4` | `80,-42,0°; sf=0; hidden` | `73,-43,0°; sf=0; hidden` |
| 1 | 0 | `3,7,-143°; sf=4` | `3,7,-143°; sf=4` | `-12,-17,37°; sf=4` | `-22,-35,50°; sf=4` | `15,-31,50°; sf=4` | `-15,-31,50°; sf=4` | `80,-42,0°; sf=0; hidden` | `73,-43,0°; sf=0; hidden` |
| 2 | 0 | `-25,-4,109°; sf=0` | `-29,-8,106°; sf=0` | `-19,-13,109°; sf=0` | `54,7,-97°; sf=0` | `45,23,-97°; sf=0` | `39,-10,-97°; sf=0` | `75,42,0°; sf=0; hidden` | `73,39,0°; sf=0; hidden` |
| 3 | 0 | `-26,-4,109°; sf=0` | `-23,-7,106°; sf=0` | `-17,-12,109°; sf=0` | `53,6,-97°; sf=0` | `45,24,-97°; sf=0` | `40,-10,-97°; sf=0` | `75,42,0°; sf=0; hidden` | `73,39,0°; sf=0; hidden` |
| 4 | 1 | `25,-5,-109°; sf=0` | `25,-8,-106°; sf=0` | `18,-12,-109°; sf=0` | `-53,7,97°; sf=0` | `-42,23,97°; sf=0` | `-37,-10,97°; sf=0` | `-75,42,0°; sf=0; hidden` | `-73,39,0°; sf=0; hidden` |
| 5 | 1 | `24,-4,-109°; sf=0` | `25,-9,-106°; sf=0` | `15,-14,-109°; sf=0` | `-56,8,97°; sf=0` | `-44,23,97°; sf=0` | `-39,-9,97°; sf=0` | `-75,42,0°; sf=0; hidden` | `-73,39,0°; sf=0; hidden` |
| 6 | 1 | `-3,7,143°; sf=4` | `-2,6,143°; sf=4` | `-11,0,143°; sf=4` | `22,-36,-50°; sf=4` | `-14,-30,-50°; sf=4` | `16,-33,-50°; sf=4` | `-81,-42,0°; sf=0; hidden` | `-74,-43,0°; sf=0; hidden` |
| 7 | 1 | `-3,7,143°; sf=4` | `-2,6,143°; sf=4` | `-11,0,143°; sf=4` | `24,-36,-50°; sf=4` | `-15,-31,-50°; sf=4` | `18,-34,-50°; sf=4` | `-81,-42,0°; sf=0; hidden` | `-74,-43,0°; sf=0; hidden` |

#### Off hand - dagger view 34

| Dir | Mirror | F0 | F1 | F2 | F3 | F4 | F5 | F6 | F7 |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0 | 0 | `12,0,178°; sf=4` | `13,1,178°; sf=4` | `-7,9,-2°; sf=4` | `8,20,-2°; sf=4` | `42,25,-2°; sf=4` | `7,22,-2°; sf=4` | `9,-5,-2°; sf=4` | `7,-6,-2°; sf=4` |
| 1 | 0 | `12,0,178°; sf=4` | `13,1,178°; sf=4` | `-7,9,-2°; sf=4` | `8,20,-2°; sf=4` | `42,25,-2°; sf=4` | `7,22,-2°; sf=4` | `9,-5,-2°; sf=4` | `7,-6,-2°; sf=4` |
| 2 | 0 | `10,-2,160°; sf=0` | `11,-6,160°; sf=0` | `2,6,151°; sf=0` | `-20,29,151°; sf=0` | `-30,45,151°; sf=0` | `-37,8,151°; sf=0` | `0,3,162°; sf=0` | `1,2,162°; sf=0` |
| 3 | 0 | `10,-2,160°; sf=0` | `11,-6,160°; sf=0` | `2,6,151°; sf=0` | `-20,29,151°; sf=0` | `-30,45,151°; sf=0` | `-37,8,151°; sf=0` | `0,3,162°; sf=0` | `1,2,162°; sf=0` |
| 4 | 1 | `-15,-9,160°; sf=0` | `-12,-8,160°; sf=0` | `-4,6,-148°; sf=0` | `17,29,-148°; sf=0` | `28,45,-148°; sf=0` | `36,8,-148°; sf=0` | `-1,3,-158°; sf=0` | `-2,2,-158°; sf=0` |
| 5 | 1 | `-15,-9,160°; sf=0` | `-15,-13,160°; sf=0` | `-4,6,-148°; sf=0` | `17,29,-148°; sf=0` | `28,45,-148°; sf=0` | `36,8,-148°; sf=0` | `-1,3,-158°; sf=0` | `-2,2,-158°; sf=0` |
| 6 | 1 | `-15,0,-178°; sf=4` | `-15,1,-178°; sf=4` | `8,9,2°; sf=4` | `-5,20,2°; sf=4` | `-42,25,2°; sf=4` | `-6,22,2°; sf=4` | `-9,-5,2°; sf=4` | `-7,-6,2°; sf=4` |
| 7 | 1 | `-15,0,-178°; sf=4` | `-15,1,-178°; sf=4` | `8,9,2°; sf=4` | `-5,20,2°; sf=4` | `-42,25,2°; sf=4` | `-6,22,2°; sf=4` | `-9,-5,2°; sf=4` | `-7,-6,2°; sf=4` |

### Per-view grip corrections

| View | Physical role | Records | dx/dy | mirror_xor | rotation_delta |
|---:|---|---:|---:|---:|---:|
| 34 | Off-hand dagger | 20 | `0 / 0` | `0` | `0°` |
| 45 | Main-hand sword | 28 | `0 / 0` | `0` | `0°` |

Views 34 and 45 are identity canaries: their local weapon geometry
already matches the accepted pair28 pose. A new expanded view requires
authored non-zero grip values when its hilt, pivot, mirror, angle, or
scale differs.


## Every-weapon and Assassin-family expansion

The patch is resource-dynamic for ownership: item 1238 and 13412 are not code
allowlists. They remain the only placement-calibrated representatives.
Loading another original SPR/ACT proves resource availability, not placement
compatibility. Offline inventory found:

- Assassin hand family: 59 item ACT/SPR resources per gender;
- Shadow Cross hand family: 20 item ACT/SPR resources per gender;
- 19 server-resolved dagger/sword resources in each active female family all
  satisfy the accepted item source action/frame contract;
- generic dagger, sword, axe, and pair resources 25-30 exist for both genders;
- no server-resolved item-specific axe resource was present in the extracted
  test set, so axe pairs require a representative live resource;
- `weapontable.lub`, not item names or itemInfo, is authoritative for expanded
  weapon view IDs, ACT/SPR resource suffixes, and expansion-to-base type.

For the calibrated pair-28 item views, attack sources are actions 80-87 and
usually frame 0 or 4; character/stock attack actions are 88-95. Other pair
states have proven frame-5 and target-frame-dependent switches, so each ordered
pair-pose record must own its exact source action/frame. Testing item ACT
visibility at 88-95 remains a false compatibility gate.

### Newly confirmed coverage failures

The production DWR3 index currently contains records only for female
`dual(1,2)`: 96 held records and 128 attack records. Every other ordered dual
state is empty. Consequently:

- two swords `(2,2)` render the stock generic sword pair;
- reversed sword+dagger `(2,1)` has no authored transform table;
- dagger+dagger, axe+axe, dagger+axe, axe+dagger, sword+axe, and axe+sword
  have no authored table and remain stock;
- male and Shadow Cross family records are absent.

A different sword inside the supported `(1,2)` state exposed a second gap:
the item can satisfy the accepted source action/frame contract but still use a
different pivot, mirror, rotation, or grip relationship from item 13412. The
current common transform then draws the original sprite at the wrong hand
position. Source-layer visibility proves availability, not placement
compatibility.

Global item coverage therefore needs a canonical per-expanded-view
normalization keyed by the weapon view returned by the client classifier. Do
not copy the Naght Sieger transform across all swords and call it generalized.

### `weapontable.lub` contract

The live datainfo table is plaintext Lua and defines three distinct layers:

1. `Weapon_IDs`: expanded view identifiers;
2. `WeaponNameTable`: exact class weapon resource suffix for each view;
3. `Expansion_Weapon_IDs`: expanded-view to base weapon type.

Relevant examples:

| View | Symbol | Resource suffix | Base type |
|---:|---|---|---:|
| 25 | dagger + dagger generic pair | generic pair suffix | pair 25 |
| 26 | sword + sword generic pair | generic pair suffix | pair 26 |
| 27 | axe + axe generic pair | generic pair suffix | pair 27 |
| 28 | dagger + sword generic pair | generic pair suffix | pair 28 |
| 29 | dagger + axe generic pair | generic pair suffix | pair 29 |
| 30 | sword + axe generic pair | generic pair suffix | pair 30 |
| 34 | `WEAPONTYPE_Zeny_Knife` | `_1238` | dagger 1 |
| 45 | `WEAPONTYPE_Twin_Edge_B` | `_13412` | sword 2 |
| 46 | `WEAPONTYPE_Twin_Edge_R` | `_13413` | sword 2 |
| 58-61 | named axes | item-specific suffixes | axe 6 |
| 200-206 | Drake axes | `_DRAKEAXE_*` | axe 6 |
| 600-606 | Drake daggers | `_DRAKEDAGGER_*` | dagger 1 |
| 1300-1306 | Drake swords | `_DRAKESWORD_*` | sword 2 |

The current `cls/weapontable.lub` override tables are empty, but future support
must merge `Weapon_IDs_CLS`, `WeaponNameTable_CLS`, and
`Expansion_Weapon_IDs_CLS` when populated.

The equipment hook currently calls `ItemToWeaponView`, validates the positive
result, then discards that expanded view. Its published row retains only the
collapsed main/off types and generic pair 25-30. DWR3 therefore cannot
distinguish view 39 from view 45 or view 1300 even though their resource pivots
may differ.

The generalized architecture must retain `main_view` and `off_view` in the
actor row and compose two tables:

- ordered base-pair pose: family/gender/ordered types/phase/direction/frame/hand,
  including the exact source action/frame;
- per-view normalization: family/gender/expanded view/physical hand and chosen
  source layer/sprite, local hilt/pivot, mirror, rotation, and grip adjustment.

This avoids item-ID allowlists and avoids multiplying the complete 8,064-slot
dense pose key space by every weapon resource.

Client `PCHands.lua` maps jobs as follows:

~~~text
Assassin       -> Assassin hand family
Assassin Cross -> Assassin hand family
Guillotine X   -> Assassin hand family
Shadow Cross   -> Shadow Cross hand family
~~~

Therefore the requested jobs need two hand-resource families, not four
separate renderers. Body/depth still requires live acceptance for every job.

The runtime has nine ordered dual states, because each mixed pair needs both
main/off orders:

~~~text
(1,1) (2,2) (6,6)
(1,2) (2,1)
(1,6) (6,1)
(2,6) (6,2)
~~~

The full dual-only target is therefore:

~~~text
2 hand families x 2 genders x 9 ordered dual states
x (96 held + 128 attack slots) = 8,064 dense key-space slots
~~~

The female item source contract is common across all eight directions for the
known dagger/sword resources. Male attack source actions also have common
frames across all eight directions, but male held item ACTs only share source
frames in directions 0-1 and 6-7. Male directions 2-5 require an authored
cross-action/fallback policy; copying female records is invalid.

The current handoff section supersedes older expansion ordering. Preserve the
accepted reversed sword+dagger order by assigning resources to the same fixed
pair-28 physical roles; do not author a second mirrored pair-28 pose. Add
female pair 25 and pair 26 only after view-aware plumbing is pair-28 golden
equivalent, then author axe pairs, additional families, and male held policy
in the staged order above.

Use expanded weapon view IDs from `weapontable.lub`, not item IDs or display
names. Do not add job-ID branches unless live evidence proves the existing
PCHands family keys insufficient.

## Rejected approaches

- universal pair-28 DWA2 anchors for pair 25-30;
- treating pair-28 static equivalence as acceptance for another pair state;
- inferring physical hand solely from higher/lower base weapon type;
- treating ACT layer-origin normalization as a local SPR hilt anchor;
- packet-registration/no-unit translation;
- stock-layer-relative mirror after bounds normalization;
- D6/7 offline grip-transfer coordinates;
- flat held-position division by an average unit;
- treating channels 5/6 as physical hands;
- native slot installation of original items as hand identity;
- remapping `0x00D36EE4` to solo actions;
- suppressing stock before both custom packets are ready;
- live-layer/native-slot branches that produced one hand or disappearance;
- draw-order/scalar-depth/priority occlusion fixes;
- editing any GRF, changing datafolderfirst, or installing client data files.

## Client-specific native sites

| Purpose | 2025 address |
|---|---:|
| Equipment update | `0x00D403A0` |
| Pair mapper | `0x00D39130` |
| Item classifier | `0x00D8A1D0` |
| ACT frame resolver | `0x0070F4B0` |
| ACT layer resolver | `0x0070F390` |
| Selected-image capture | `0x00605D41` |
| Final draw | `0x00C4A0D0` |
| Completed-vertex depth | `0x00C4A647` |
| Resource AddRef | `0x00A8E800` |
| Resource Release | `0x00A8F910` |

The stock ACT-frame call at `0x00D36EE4` must remain stock.

## Live acceptance required for expansion

For every new family/gender/pair require both originals, correct hand contact,
all expected frames, intentional hidden terminal frames, no generic duplicate,
no disappearance, correct mirror/angle/X/Y/scale/palette, correct body
occlusion, stock fallback states, relog, map change, repeated equipment
changes, Alt+Tab/device reset, and clean exit.

Static syntax/PE checks are necessary but never sufficient to mark a new cell
working.

## Repository handoff

~~~text
branch: main
HEAD: 2265d6c8cf9599143bfa556909f86d4e370ac6d5
production patch: Scripts/Patches/AllowDualCustomWeaponSprites.qjs
production QJS SHA-256: 42572E77B1A3EFFE605B97350269B7FAFED02C6DE6ABD67969FC15A4502778C2
accepted EXE SHA-256: 7DF99320B376E1679F694889E097D79B96713CC891D054ABDC2C5C44FE448BEB
stable pair-28 DWC1 EXE: A82CFA8CF79DBCB7D4A829E545FB2FE090B1BCCE5E3DE1AA60907FB9FF14B9C5
envelope helper SHA-256: E2907B79240E3A9341F84F1F7A58948576C23E2626FE95BC1F482849A4149F80
rejected universal-anchor EXE: B1301860DA5EE1D189B9B621A76CA66CB185B70BB942D64A520B2F85B00406A1
all-original placement baseline EXE: 85B03DBAF572031A3A22EAA70FEAB4A4EF4C75D0BDBDA58EC4FF8C9A6128D1BF
documented pose matrix: docs/dual-wield-pose-matrix.csv / 99DDD59A41F5FB5BE1E776B7055A2FF0D48719E47B80E6FC48C5D11C4E0A989B
next gate: preserve the 85B owner/compositor and recalibrate only pair-pose and per-view grip records
workspace: dual-wield QJS/catalog/tracker/docs changes are unstaged; canonical doc is untracked
authority: current working-tree files and hashes above, not HEAD alone
commit: intentionally not created
~~~

NOTE: the `production QJS SHA-256` value above (`42572E77...`) is stale relative
to the section below — it is also the same stale value hardcoded as
`PRODUCTION_SHA256` inside `tools/dual_weapon_direct_target/build_direct_target_all_pairs_qjs.py`.
The actual current production hash, verified byte-for-byte unchanged before and
after every build this session, is `50DA8C4D3A40BE954630C1583C26DFECA251955C5DA1B32D03F614AAB6A534F8`
(283,189 bytes). Trust that value, not the one above, and always pass
`--base-sha256 50DA8C4D...` explicitly to that builder script.

## Pair 25 (dagger+dagger) attack-phase handoff - 2026-09-01

### Status

**Not live-accepted. Blocked, most likely on incomplete source-art authoring,
not on runtime code.** Pair 28 (dagger+sword, state 9) is untouched and
remains exactly as documented above — every fix below is scoped to state 6
(pair 25) only, and every change was verified byte-for-byte to leave state 9's
rig region and the production QJS untouched. Do not re-litigate pair 28.

### What is proven correct this session (do not re-derive)

1. **`extract_pair25_attack_from_edit.py` is a faithful, bug-free transcription**
   of the source ACT file. Independently re-derived from raw ACT bytes
   (bypassing the script entirely) and diffed against its own CSV output:
   128/128 `(direction, frame, hand)` rows matched exactly, including rotation
   normalization. Also confirmed every one of the 64 `(direction, frame)`
   cells in the ACT file has exactly 4 layers (0=body_guide, 1=pair_guide,
   2=off-hand weapon, 3=main-hand weapon) — no silent wrong-layer indexing is
   possible.
2. **`patch_pair25_attack_into_rig.py`'s rig write is exhaustively correct.**
   Statically decoded all 128 dense-index slots for family=0/gender=0/state=6/
   phase=1 (attack) out of the patched `.dwr3` and diffed every `(dx, dy,
   rotation_delta, metadata)` against the CSV: 128/128 exact. Confirmed the
   96 held-phase (phase=0) slots this same script force-hides are exactly
   `frame<6` per its own loop bound, and that state=9 (pair 28) is
   byte-identical between the source and patched rig across its full 256
   slots (2 phases x 8 directions x 8 frames x 2 hands) — zero cross-talk.
3. **The runtime's live `BOH_DWR APPLY` position math is exact.** After the
   two fixes below, every captured direction (1, 3, 5, 6) and every frame
   within them satisfies `mainCx == stockCx + mainDx` and
   `offCx == stockCx + offDx` to the pixel, with no unit-scale multiplication
   anywhere in the chain. This was checked by hand against live dbgview
   captures, not just statically.
4. **`unit_x`/`unit_y` are not an engine constant.** They are recomputed every
   `prepare_hand` call as `|stock_width| / (stock_image->width * stock_scale_x)`
   (and the Y equivalent) — a ratio between the *current frame's* rotated
   on-screen bounding box for the stock generic icon and its native bitmap
   size. Measured live across directions in a single session: 1461-2633 (in
   `*1000` diagnostic units), a ~78% spread, not a fixed ratio. An earlier fix
   this session that pre-divided authored deltas by a single measured
   constant (1.485/1.529) was consequently wrong for most directions and has
   been fully replaced (see fix #1 below).

### Runtime code fixes made this session (all in
`tmp/recovered_dual/dual_weapon_runtime_pair28_direct_target.c`)

1. **New metadata bit `0x80` — "raw pixel delta."** Inside `prepare_hand`'s
   `metadata & 0x40 && metadata & 0x10` branch (direct-target + attack
   encoding), a new nested check on bit `0x80` skips the `* unit_x` / `* unit_y`
   multiply on `transform->dx`/`dy` entirely, treating them as already-final
   screen pixels (exactly what `pair_guide`-relative ACT deltas are).
   Verified this bit is otherwise completely unused anywhere in the file
   before adding it (`grep -n "0x80"` returned only unrelated `0x8000`
   key-state masks). Purely additive: pair 28's transforms never set this
   bit, so its accepted `else` path (still `* unit_x`/`unit_y`) is byte-for-
   byte unchanged.
2. **Fixed a real bug in that same new branch:** the first version of fix #1
   also skipped scaling `correction->dx`/`dy` (the separate DWC2 per-view
   grip nudge) by `unit_x`/`unit_y`, unlike every sibling branch. Since
   `find_correction` keys on `(view, family, gender, phase, direction,
   source_key, base_type)` with no frame axis, any nonzero correction would
   have produced a frame-varying position error under the old (wrong)
   version. Fixed to `(float)transform->dx + (float)correction->dx * unit_x`
   (transform raw, correction still scaled) — matching every sibling branch's
   convention for `correction`. Confirmed inert for pair 25 specifically: all
   DWC2 records for view 34 (Zeny Knife, dagger, base_type=1) are a pure
   identity table (dx=0, dy=0, mirror_xor=0, rotation_delta=0), so this fix
   has zero live effect on daggers today — it matters for any future pair
   whose correction table is non-identity.
3. **`debug_apply_observation`'s throttle was direction-only, not per-frame.**
   Original gate: one bit per *direction* in `ctx->debug_flags[21 or 22]`
   (combo-family split), so the very first frame logged for a direction
   suppressed the `BOH_DWR APPLY` diagnostic for every later frame of that
   same direction for the rest of the process. Every dbgview capture taken
   earlier this session was therefore blind to frames 1-7's actual applied
   numbers — a real diagnostic gap, not evidence either way about frame
   correctness. Fixed by re-keying the mask on frame instead of direction:
   `combo_flag_index = 30 + direction + (same_type ? 8 : 0)` (16 free bytes,
   confirmed unused — `debug_once` literals stop at 18, `debug_channel_sequence`
   uses 64-135, `debug_family_observation` uses 160-165; `debugFlagsVir` has
   0x100=256 bytes of room before the next allocation), `direction_mask =
   1u << (frame & 7)`. This is the fix that finally surfaced real frame-by-
   frame `APPLY` data and let fix #1/#2 be verified live (see point 3 above).

### Data gap found in the source ACT file (this is very likely the actual
remaining blocker, not code)

Source file:
`tmp/recovered_dual/ActEditorWork/remaining_pairs/pair25_dagger_dagger/EDIT_ME_ATTACK_PAIR25_DAGGER_DAGGER_WITH_BODY_GUIDE.act`

Directly re-verified (not just trusted from a subagent report) by parsing the
ACT and comparing every layer across all 8 attack directions (actions 88-95):

~~~text
direction 0 (action 88): IDENTICAL to direction 1 -- every layer, every one of
    8 frames, including the pair_guide reference layer itself. Not a rounding
    coincidence: rotation values match exactly too.
direction 1 (action 89): IDENTICAL to direction 0.
direction 2 (action 90): unique.
direction 3 (action 91): unique.
direction 4 (action 92): unique from other directions, BUT internally has
    frozen/duplicate frames: main hand f6 == f7 exactly (-76,39,rot0); off
    hand f3 == f4 == f5 exactly (33,-1,rot-160), and f6 == f7 exactly
    (13,-7,rot-160).
direction 5 (action 93): unique from other directions, off hand f3 == f5
    exactly (33,-1,rot-160), f4 differs by 1px only.
direction 6 (action 94): IDENTICAL to direction 7.
direction 7 (action 95): IDENTICAL to direction 6.
~~~

Net: of 8 directions, only 4 (2, 3, 4, 5) have any independently-placed data
at all, and 2 of those 4 (4, 5) have internal frozen-frame gaps on top of
that. Directions 0/1 and 6/7 currently render as literal duplicates of their
pair partner. The user (who did the ACT-editor placement) disputes that this
represents unfinished work and states the placement pass was done for the
full dagger+dagger pair. **Unresolved as of this handoff**: whether the ACT
editor tool itself shows direction 1 placed distinctly from direction 0 (a
tool export/save bug, external to this repo) or shows them identical (an
authoring gap). The user was asked to check the tool's own UI against this
exact file and has not yet reported back. Resolve this before assuming either
"finish the authoring" or "look for a tool bug" is the right next step.

### Build pipeline gotchas hit this session (read before rebuilding)

- **`build_direct_target_all_pairs_qjs.py` hardcodes the patch's *internal*
  identity as module-level constants** `SOURCE_ALIAS =
  "AllowDualCustomWeaponSprites"` / `OUTPUT_ALIAS =
  "AllowDualCustomWeaponSpritesDirectTargetAllPairsTest"`, **independent of
  the `--output` filename you pass it.** The generated file defines a global
  identifier literally named after `OUTPUT_ALIAS` (e.g. `AllowDualCustom
  WeaponSpritesDirectTargetAllPairsTest = function(_) {...}`), and WARP's
  loader resolves a patch by looking for a function matching the *patch ID*
  it was told to run (from `Special.yml`'s key / the profile's `patches:`
  entry / the `Scripts/Patches/<id>.qjs` filename). Stage it under any other
  name and WARP silently finds nothing, writes `Function missing, skipping
  patch '<id>'` to `SkippedPatches.log` at the repo root, and produces a
  100% stock client with **zero** patches applied — this happened once this
  session and looked exactly like "everything regressed, even pair 28,"
  which it was not. Always name the `Special.yml` entry, the
  `Scripts/Patches/*.qjs` filename, and the profile's `patches:` line exactly
  `AllowDualCustomWeaponSpritesDirectTargetAllPairsTest` when using this
  builder script. Check `SkippedPatches.log` (recreated empty on a clean run)
  after every build as a cheap sanity check.
- **`PRODUCTION_SHA256` inside that same script is stale** (`42572E77...`,
  matching the same stale value in this doc's older "Repository handoff"
  block above). Always pass `--base-sha256
  50DA8C4D3A40BE954630C1583C26DFECA251955C5DA1B32D03F614AAB6A534F8`
  explicitly, or the script raises `AssertionError: production QJS SHA-256
  ... != ...` (a safe failure, not a bug -- just remember the override).
- **Calibration overlay enable is a manual post-build hex edit**, not a
  builder flag: after `build_direct_target_all_pairs_qjs.py` runs, grep the
  output for the unique literal `0x38, 0x3C, 256,` (confirm exactly one
  match), and change `256` to `65792`. This is `contextValues[7]`, decoded
  byte-wise (`(value>>>shift)&0xFF` for shift 0/8/16/24, little-endian) into
  `[default_family, minimum_state, reserved[0], reserved[1]]`: `256 = 0x00
  01 00 00` -> `reserved[0]=0` (calibration + magenta overlay box disabled);
  `65792 = 0x00 01 01 00` -> `reserved[0]=1` (enabled). This gate controls
  both the `apply_calibration` call and the magenta reference-box draw.
- **Staging/build/cleanup recipe** (the only sequence that has actually
  worked this session, run from the repo root):

~~~powershell
# 1. compile (pinned x86 toolchain)
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars32.bat" -vcvars_ver=14.29
cl.exe /c /TP /O2 /GS- /Gz /Fo:tmp\recovered_dual\<name>.obj tmp\recovered_dual\dual_weapon_runtime_pair28_direct_target.c

# 2. extract freestanding core constants
py tmp/recovered_dual/build_dual_weapon_authored_core.py tmp/recovered_dual/<name>.obj --out tmp/recovered_dual/<name>_core_constants.qjs --manifest tmp/recovered_dual/<name>_core.json

# 3. rebuild the rig (writes tmp/recovered_dual/female-assassin-pair25-attack-patched.dwr3)
py tmp/recovered_dual/patch_pair25_attack_into_rig.py

# 4. build the candidate qjs -- output name MUST equal the hardcoded alias
py tools/dual_weapon_direct_target/build_direct_target_all_pairs_qjs.py `
    tmp/recovered_dual/<name>_core_constants.qjs `
    tmp/recovered_dual/female-assassin-pair25-attack-patched.dwr3 `
    --core-sha256 <hash of _core_constants.qjs> `
    --rig-sha256 <hash of the .dwr3> `
    --base-sha256 50DA8C4D3A40BE954630C1583C26DFECA251955C5DA1B32D03F614AAB6A534F8 `
    --output tmp/recovered_dual/AllowDualCustomWeaponSpritesDirectTargetAllPairsTest.qjs

# 5. (optional) enable calibration: edit "0x38, 0x3C, 256," -> "0x38, 0x3C, 65792," in that output file

# 6. stage (bash): back up Special.yml, add one temp CustomSpecials entry keyed
#    AllowDualCustomWeaponSpritesDirectTargetAllPairsTest, copy the candidate to
#    Scripts/Patches/AllowDualCustomWeaponSpritesDirectTargetAllPairsTest.qjs,
#    copy "profiles/2025-07-16 PROFILE MAIN.yml" to a temp profile and swap
#    ONLY its "- AllowDualCustomWeaponSprites" line to the same id.
rm -f SkippedPatches.log
./win32/WARP_console.exe -using "profiles/<temp>.yml" -to "<output exe path>"
# verify SkippedPatches.log is empty (touched but 0 bytes) -- if it names the
# patch, the staging name is wrong, not the code.

# 7. restore Special.yml from backup; delete the temp profile, the temp
#    Scripts/Patches file, and SkippedPatches.log; re-verify
#    Scripts/Patches/AllowDualCustomWeaponSprites.qjs is still
#    50DA8C4D3A40BE954630C1583C26DFECA251955C5DA1B32D03F614AAB6A534F8 and
#    `git status --porcelain` matches the pre-existing baseline.
~~~

### Current exact artifact state (hex/binary, verified moments before this
handoff was written)

~~~text
production patch (untouched all session):
  Scripts/Patches/AllowDualCustomWeaponSprites.qjs
  SHA-256: 50DA8C4D3A40BE954630C1583C26DFECA251955C5DA1B32D03F614AAB6A534F8
  283,189 bytes

runtime source (both fixes above applied, current state):
  tmp/recovered_dual/dual_weapon_runtime_pair28_direct_target.c
  SHA-256: 8C08F6D3BC13181B072146ECE190EF4C722F12D9B75CF827B6B2BCA2C5A94A8E
  55,800 bytes

last compiled object from that source (pinned MSVC v14.29, x86, /O2 /GS- /Gz):
  tmp/recovered_dual/dual_weapon_runtime_pair25_framefix.obj
  SHA-256: 325F158780916FBDC57BC6371747FCD10EBBAB8FBCAA0D50158CCEF5A7C07E73
  116,172 bytes

extracted freestanding core (from build_dual_weapon_authored_core.py):
  runtime bytes SHA-256: E2C6AD13EE87BB5F40E5654B8EC129EF8FBD70F8F20DEEE391621274B50CF2E5
  68,364 bytes, 460 relocations (all into .rdata; no .bss dependency), entry_offset=0
  serialized as: tmp/recovered_dual/pair25_framefix_core_constants.qjs
  SHA-256: F19EAEA48F6573D79759F62D89AE3A5B61D4E67B3488019D00FE1794C6367074
  211,575 bytes

patcher scripts (unchanged since the fixes described above):
  tmp/recovered_dual/patch_pair25_attack_into_rig.py
    SHA-256: 915A75A3CC0C6E28DF891588E6FACD665EE8922BA8167B83596F7A2D6C0E9605
  tmp/recovered_dual/extract_pair25_attack_from_edit.py
    SHA-256: 458CC134FFB133F2948FDFAE19D8C2A16A1CF2AAB91514BACDB2F224A5CC8458

extracted pose CSV (128 rows, 8 directions x 8 frames x 2 hands, raw
pair_guide-relative pixel deltas, NOT divided by any unit-scale constant):
  tmp/recovered_dual/pair25_attack_extracted_draft.csv
  SHA-256: 470B981DC785B255A4A53DE0654B9F4A72138BF9738E0696781B1D05D398B527
  21,967 bytes

patched rig (state=6/pair25 attack + held-hide only; state=9/pair28 byte-
identical to its canonical source across all 256 slots):
  tmp/recovered_dual/female-assassin-pair25-attack-patched.dwr3
  source rig SHA-256 (Inputs/DualWeaponAuthored/rigs/female-assassin-canonical.dwr3):
    CDA6C39AF7CB620FEBD02D6A5A84E9027993904D33BF1DE810CBFD1BE304B38F
  output SHA-256: 023140B245158D9ABCC79C5F028E26AF88D827AB5D9E5B7029B701E1390EB4E3
  19,416 bytes; header: family_count=1, state_count=15, index_count=7680,
  transform_count=670 (up from 567 in the source rig -- 103 new deduplicated
  records); 128 attack rows patched, 96 held rows force-hidden.

current test candidate (calibration overlay ENABLED -- contextValues[7]=65792):
  tmp/recovered_dual/AllowDualCustomWeaponSpritesDirectTargetAllPairsTest.qjs
  SHA-256: D7BFC84856AD5175C7E94929ADD051BDD26765DE65D31B42E65BC9B55672B280
  330,058 bytes
  (NOTE: this is the post-calibration-edit hash; build_direct_target_all_pairs_qjs.py's
  own reported output hash for the pre-edit file was BD51793CBA2E465961038CDD6E882516652A99C5A459C822E74B843E24BC3210
  at 330,056 bytes -- the two-byte/hash difference is exactly the "256"->"65792" edit.)

built test EXE currently in the user's hands:
  C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\dual_weapon_pair25_framefix_20250716.exe
  21,669,709 bytes
  Built from the temp-staged candidate above via WARP_console.exe against
  base client 2025-07-16_Ragexe_175220998_clientinfo.exe, full Profile Main
  patch list with only the AllowDualCustomWeaponSprites line swapped.
  SkippedPatches.log was confirmed empty after this build.
~~~

### DWR3/TRANSFORM binary format quick-reference (for continuation without
re-deriving)

~~~text
HEADER = struct.Struct("<4sHBBIII")
    magic(4s)=b"DWR3", schema(H)=3, family_count(B), state_count(B)=15,
    index_count(I), transform_count(I), crc32(I)          -- 20 bytes total
family_bytes: 16 bytes immediately after the header
index table: index_count x u16, dense_index -> transform_index (1-based; 0 = empty)
    starts at offset 20 + family_count*16
transform table: transform_count x TRANSFORM, immediately after the index table
    starts at offset (20 + family_count*16) + index_count*2

TRANSFORM = struct.Struct("<bbBBh")   -- 6 bytes
    dx (s8), dy (s8), flags (u8), metadata (u8), rotation_delta (s16)

dense_index(family, gender, state, phase, direction, frame, hand) =
    ((((((family*2+gender)*15+state)*2+phase)*8+direction)*8+frame)*2+hand)

state per pair (mode==1, from runtime_state_index(mode, main_type, off_type)):
    pair25 -> state 6   (main=1,off=1, dagger+dagger)
    pair26 -> state 7   (2,2, sword+sword)
    pair27 -> state 8   (6,6, axe+axe)
    pair28 -> state 9   (1,2, dagger+sword)  [state 10 for the reversed 2,1 order]
    pair29 -> state 11  (1,6, dagger+axe)
    pair30 -> state 13  (2,6, sword+axe)

flags byte = (source_frame & 0x1F) | ((mirror & 1) << 6)

metadata byte, bit by bit:
    bit 0 (0x01) draw_order
    bits 1-2 (0x02,0x04) acceptance tier, checked as (metadata>>1)&3 against
        ctx->minimum_state in find_transform; below-tier transforms are
        rejected (ATTACK_REASON_TRANSFORM). Pair 28's accepted transforms use
        tier 1 (bit 0x02 set); pair25's new transforms match that.
    bit 3 (0x08) hidden/invisible
    bit 4 (0x10) packet_delta encoding (attack-phase target is a delta from
        the stock packet center; held-phase without this bit is actor_target)
    bit 5 (0x20) also feeds `expected_attack_channel`-style pose gating and
        flips into DWC2 source_key bit 0x40 (find_correction lookup key)
    bit 6 (0x40) direct-target marker (final authored pair coordinates,
        vs. legacy encodings in the else branches of prepare_hand)
    bit 7 (0x80) NEW this session: raw pixel delta -- skip the
        unit_x/unit_y multiply on transform->dx/dy specifically (added for
        pair25; pair 28's transforms never set it, so pair28 is unaffected)

DWC2 CORRECTION = struct.Struct("<HBBBBBBhhBhB")
    view(H), family(B), gender(B), phase(B), direction(B), source_key(B),
    base_type(B), dx(h), dy(h), mirror_xor(B), rotation_delta(h),
    selected_frame(B)
    source_key = (transform->flags & 0x3f) | ((transform->metadata & 0x20) ? 0x40 : 0)
    All view=34 (WEAPONTYPE_Zeny_Knife / item 1238, dagger base_type=1)
    records are a pure identity table (dx=0, dy=0, mirror_xor=0,
    rotation_delta=0) -- confirmed by direct binary dump, not assumption.
~~~

### Calibration overlay -- built in, never confirmed to actually respond

Every build since the "scalefix" candidate (several builds ago, carried
forward unchanged into today's `AllowDualCustomWeaponSpritesDirectTargetAll
PairsTest.qjs`) has `contextValues[7]=65792` (calibration enabled) and the
`BOH_DWR RAWKEYS` diagnostic wired in. Controls: Ctrl held = adjust off-hand,
released = main-hand; Shift held = step 5, released = step 1; NumPad4/6 =
X-/X+; NumPad8/2 = Y-/Y+; NumPad5 = dump current values to
`BOH_DWR CAL ... mainDx=... offDx=...` (final base+delta, clamped to int8).
The code also checks NumLock-off arrow-key alternates (logged as `left=`/`up=`
in `RAWKEYS`, corresponding to VK_LEFT/VK_UP for when physical NumPad4/8
generate those codes instead of VK_NUMPAD4/8).

**Every single `BOH_DWR RAWKEYS` line captured this entire session --
dozens of them, across multiple builds and multiple test sessions -- shows
`n4=0 n6=0 n8=0 n2=0 n5=0 left=0 up=0` with no exceptions.** `shift=32768`
does appear intermittently (correlated with the user holding shift to run),
which proves the underlying `GetAsyncKeyState`-via-IAT-thunk mechanism itself
is live and correctly wired (at minimum for VK_SHIFT). Whether calibration
input specifically is broken, or simply has never been deliberately pressed
during a capture, is **unresolved** -- no capture exists where the user
confirms they pressed a numpad/arrow key during a `dbgview` recording. This
is the cheapest remaining diagnostic: get into an attack pose, tap NumPad4/6/
8/2 a few times (with and without Ctrl), tap NumPad5, and check whether
`RAWKEYS`/`BOH_DWR CAL` ever shows a nonzero value. If it responds, live-
tuning pair25 the same way pair28 was originally tuned (trial-and-error
in-game, not the ACT-editor/extraction pipeline) becomes available and may be
the fastest path to something that actually looks right, independent of
resolving the ACT-editor duplication question above.

### Immediate next steps, in order

1. Resolve whether direction 0/1 and 6/7 duplication (see above) is a tool
   export bug or an authoring gap -- ask the user to check the ACT editor's
   own display for direction 1 against direction 0 in the exact file path
   above. This determines whether the fix is "look at the authoring tool" or
   "finish placing 4 more directions."
2. In parallel, confirm whether the calibration overlay responds to input at
   all (see above) -- a 5-minute live test, not more static analysis.
3. Do not re-attempt the offline-formula route for the untouched directions
   until #1 is answered -- if it's a tool bug, re-authoring will just
   reproduce the same duplicate output.
4. Held phase (phase=0) for pair25 has zero authored data and is currently
   force-hidden by `patch_pair25_attack_into_rig.py`'s own loop -- do not
   start this until attack phase is fully live-accepted across all 8
   directions.
5. Pairs 26/27/29/30 (states 7/8/11/13) have zero authored data of any kind.
   This historical framefix pipeline is not the currently pulled core.
   The current core rejects every pair except 28 before family lookup;
   expanding it requires code and data changes. See the current byte audit.

## Job-sprite compositor investigation and its conclusion - 2026-09-01

A separate line of work this same day investigated whether a fundamentally
different architecture -- computing hand placement from the job/gender body
sprite plus a per-weapon hilt/tip landmark, instead of authoring a full
per-pair pose table -- could eliminate the per-pair authoring cost entirely.
Three hypotheses were tested against the accepted pair-28 attack data
(128 cells). The following is a historical summary. **2026-09-05 erratum:**
independent source parsing did not catch the fitting/validation sign mismatch,
and these tests did not examine a body compositor with separate hand sockets.
The corrected experiment and scope are documented in the
[job-sprite audit](dual-weapon-job-sprite-audit-20260905.md).

1. **Rigid rotation of one fixed hilt/tip landmark per weapon view, onto a
   shared socket.** The tested model still fails. The historical reported
   mean 37.55px / max 106.2px used inconsistent calibration/validation signs and
   is superseded by **mean 31.908px / max 107.055px** across the same 128 cells.
   The narrower radius argument remains sign/convention-independent: for a fixed hand+frame, the
   accepted CSV's own hand-to-anchor distance varies ~6-30px across the 8
   directions, and a rigid rotation can never change a fixed vector's
   magnitude -- this alone rules out the model regardless of getting angle
   sign or mirror order right.
2. **A general kinematic/pivot search** (reach-invariance from `body_guide`,
   a fitted-offset pivot, a rotation-derived angle predictor). All failed:
   per-frame reach coefficient-of-variation across directions ranges 2%-65%
   (not small); the angle from `body_guide` to the hand jumps 90-180°
   erratically between directions instead of sweeping smoothly (rules out a
   simple arm-swings-under-camera-rotation model); a fitted pivot offset
   gives only 5.9%-33.8% variance reduction and needs a different offset
   every frame to work at all (i.e. needs multi-joint kinematics, not a
   single fixed pivot); rotation-derived angle prediction found no
   relationship at all. One corroborated side-finding: the **raw,
   uncorrected** authored ACT animation itself does follow a clean,
   direction-shared, per-frame reach law -- confirmed independently on both
   pair 28's own raw ACT layers and the separate in-progress pair-25 file. It
   is specifically the *correction* applied on top (present at some frames,
   not others) that resisted every model tried.
3. **Regressing the correction itself**
   (`correction(direction,frame,hand) = CSV_hand_absolute -
   raw_ACT_hand_absolute`, rather than modeling absolute position).
   Partially confirmed, independently re-verified byte-for-byte from a
   separate ACT re-parse: 60/128 cells are exactly zero (frames 0-2, always);
   of the 68 nonzero, a direction-pairing pattern
   (`{0,1},{2,3},{4,5},{6,7}`) plus a "both weapons get one shared shift"
   behavior collapses 58 of them into 17 reusable exact vectors, leaving 10
   cells (sword-specific, frames 3-5, direction-pairs `{0,1}`/`{6,7}`)
   genuinely irreducible to sub-pixel exactness. Net: 128 values -> 28
   distinct exact vectors, a real ~4.6x reduction -- but no
   physical/geometric driver was found behind the pairing (reach-correlation
   is weak for the main hand, r=0.505, and essentially absent for the
   off-hand, r=0.081, when reach is measured from `body_guide`; measuring
   from `pair_guide` instead -- the layer actually established as the CSV's
   real anchor, see below -- gives r=0.292/r=0.407 instead; both pairs of
   numbers are real, cite whichever origin is meant). This is a compression
   of pair-28's own already-authored data, not a predictor for a
   not-yet-authored pair.

**Corrected fact, superseding the framing implied by "body_guide" appearing
first in the layer list above:** the accepted CSV's per-cell translation is
authored as a delta against ACT **layer 1 (`pair_guide`)**, not layer 0
(`body_guide`). Directly reproduced from the current files: raw ACT
weapon-layer position vs. `layer1 + CSV_delta` reconstruction is exact in
60/128 cells (mean drift 9.71px, max 35.51px on the rest); vs.
`layer0 + CSV_delta` it is exact in 0/128 cells (mean 34.52px, max 61.4px).
`layer0` (`body_guide`) tracks the torso and has no reliable correlation with
either weapon's position.

**Historical conclusion, corrected 2026-09-05:** these experiments did not find
an automatic fixed-vector or shared-reach model that reproduces the pair28
weapon-center data. Rotation matches the item's baked ACT rotation in 116/128
cells, and mirror matches directly in all 128; these remain observations on
this dataset, not verified rules for every future pair.

The previous assertion that translation necessarily retains the full per-pair
cost was not established. `dual_socket_extract.py` used a shared pair-guide
bitmap origin, not independently measured left/right hand sockets, and the
fixed-view model did not key grips by the actual selected SPR image. Separate
per-hand/per-body-frame sockets plus image-specific hilt/blade landmarks remain
an untested architecture. The 28-vector compression only reproduces already
authored data; it does not itself predict a new pair. Existing native body ACT
samples have one anchor per frame, not two hand sockets. See the linked audit
before treating this investigation as a limitation of all job-body compositors.

**Repository state from this investigation:** `tools/dual_weapon_formats/`
(promoted ACT/SPR/GRF readers, `weapontable.lub` parser, DWR3/DWC2 struct
helpers, the correction-regression analysis and its independent verifier) and
`Inputs/DualWeaponAuthored/sockets/` are committed
(`43ed714`, `009f3e5`, `2b2273a`). This document and the Stage-1 diagnostic
reports (`tools/_stage1_validation_report.json`,
`tools/_stage1_translation_model_v2_report.json`,
`tools/dual_socket_extract.py`, `tools/dual_hilt_fit_validate.py`,
`tools/fit_pivot_offset.py`) are committed in the same range. Production
`AllowDualCustomWeaponSprites.qjs` (pair 28) was not touched by any of this
work. At that historical point no runtime port had started; a `prepare_hand`
v2 based on per-pair translation and observed rotation/mirror was proposed.
That proposal was not proof that other architectures are impossible. Later
readable-compositor and pose-transfer candidates are covered by the current
authority and live-rejection erratum at the top of this document.
