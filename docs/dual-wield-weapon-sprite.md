# Dual-Wield Original Weapon Sprite Contract

## Status

**Visual status: NOT WORKING. The split-layer architecture is superseded.**

## Definitive architectural conclusion (2026-07-27)

The user's observation is proven: during dual-wield stance and attack, both
original item sprites can overlap on one hand because both individual item
ACTs are primary/right-hand-authored. Moving one item resource from channel 5
to channel 6 does not turn channel 6 into a native left-hand anchor.

The stock client does not render its correct two-hand pose as two independent
weapon layers:

- stock ACT5 contains one precomposed bitmap with both generic weapons already
  drawn in their final hand positions;
- stock ACT6 is the auxiliary weapon glow/trail resource, not the off-hand;
- individual item and generic-single ACTs use their visible attack art in
  actions 80..87;
- their actions 88..103 are transparent, while the generic dual ACT5 has
  populated actions 88..95;
- item 13412 action 80 frame 0 is `(0,-84,index=0,mirror=0)` and item 1238 is
  `(-7,-70,index=0,mirror=0)`: both are primary-hand poses;
- item 1238 idle directions 34..37 are transparent.

Therefore there is no reusable native dual-hand placement handler that can be
enabled for arbitrary original item sprites. The visible two-hand information
is authored into the pixels of each stock generic dual frame. It is not stored
as independent main/off-hand ACT transforms.

The GRF-derived component-table experiment does not change this limitation.
It attempts to decompose a separately authored composite bitmap into two
translated single-weapon sprites. Many attack frames have poor component
coverage, and a rigid X/Y/mirror/rotation transfer cannot reconstruct clipping,
redrawing, or deformation baked into the stock image. It can produce:

- two original sprites on the same hand;
- severely displaced weapons;
- only a fraction of the off-hand weapon;
- a transparent/disappearing off-hand when the selected item frame has no art.

The static verifier's `SOURCE PASS`, `ASSET PASS`, and
`DUAL-WEAPON CONTRACT PASS` prove the implemented hook and the ACT/SPR topology.
They do **not** prove visual correctness. Live screenshots have rejected the
current compositor, so a verifier pass must not be reported as a working fix.

Build `92C381B4846AE659D6FB78BDE3A3F3FD343EFE3A3F44EA968251805CFE03D93F`
was rejected because its failed geometry query deliberately left channel 6 on
transparent action 88..95, making the off-hand disappear. The deployed test
client was rolled back to
`9B272C39E64826654D6D4089A139609379D752F2D3D9DDC0DB2CF76A17AB278D`;
that rollback prevents the new disappearance regression but still has the
same-hand overlap and is not accepted as fixed.

### Valid implementation choices

1. Keep the stock generic ACT5 composite. This is the only existing asset path
   with exact native two-hand placement, but it cannot display both original
   item silhouettes.
2. Author real off-hand/dual assets for every supported item, job, gender,
   direction, action, and frame. Pair-specific precomposed assets can reproduce
   stock clipping and ordering exactly, but require additional artwork.
3. Build a dedicated runtime compositor that loads original item art and
   applies job/gender/class/pose-specific off-hand transforms, masks, clipping,
   and ordering. Item IDs select artwork only; they must never be eligibility
   gates or pose-table keys. Automatically derived poses remain approximate
   unless the missing off-hand artwork is authored.

No further coordinate-only build should be presented as an exact fix. A new
renderer/compositor architecture must be proven offline and then accepted
live across Assassin, Assassin Cross, Guillotine Cross, and Shadow Cross,
both genders, all directions, and classifier-approved weapon pairs.

## Historical investigation

The remainder of this document records the investigation that led to the
superseded split-layer implementation. Statements describing that architecture
as “corrected” are historical and do not override the definitive conclusion
above.

The reported regression is confirmed.

Commit `fc9bddb6c0156f6411d5ea80f58f183f6a00852c` displayed original
weapon art because its resource hook accepted every item for which the
client's native item-to-weapon lookup returned a positive view. It did not
gate resource loading on an item ID, gender, or job.

The regressed equipment experiment changed that sequence to:

```text
stock current(main, off)
offAsMain -> capture/AddRef off slot 5
mainOnly  -> capture/AddRef main slot 5
stock current(main, off) again
release stock slots 5/6
rewrite the four captured pointers
```

The second stock-current call is the direct regression. It re-entered the
native dual combiner, reinstalled the generic precomposed resource, and
mutated loader/cache state beyond the four raw vector pointers. Added
capture-validation failures also returned through a stock-current replay.
The stale executable supplied for testing contains this sequence.

The clean-client comparator later proved that the effective Shadow Cross job
is `4013`, not the previously assumed `4254`. More importantly, multiple
classified pairs—including 1201/1102 and the user's actual 13412/1201
equipment—install distinct ACT5 and ACT6 resources. Item/view IDs, gender,
and job are therefore diagnostics only, not compositor eligibility gates.

The corrected 2025 architecture separates three decisions:

1. Native weapon classification controls whether original resources load.
2. The same classifier-approved update retains that actor's composite ACT5;
   ACT6 is retained only for ownership symmetry and is not a hand anchor.
3. The native item-pair mapper and generic slot-1 loader supply each weapon
   type's job/gender-specific single-weapon coordinate baseline.

A registry or native-layer miss keeps original item art and never falls back
to the stock generic composite. A dual channel-6 miss deliberately keeps the
blank item action 88..95 instead of drawing its primary-hand-authored action
on the wrong hand.

Live front/back idle and attack screenshots remain the final acceptance gate.
Static disassembly and ACT/SPR verification prove the selected code and data
paths but cannot replace an in-game render test.

## Stock and original resource proof

The profiled client's equipment updater stores its two arguments at actor `+0x440` and
`+0x444` on the 2025 client. In the stock dual path it passes the second item
to the native item-to-weapon function, obtains a combined pair view, and loads
generic resources into render channels 5 and 6.

The live male Shadow Cross GRF assets prove that these are different resource
families:

| Resource | ACT actions 88..95 | SPR images |
|---|---|---:|
| item 13412 | transparent | 6 |
| item 1238 | transparent | 4 |
| generic dagger+sword | populated | 16 |

The offline generic action 88 frame 0 contains one layer whose bitmap already
contains both weapon silhouettes. That proves why an offline-only analysis
cannot recover two hands from that file.

The clean client supplied by the user exposed different live resources:

```text
main=1201 off=1102 job=4013 gender=1
spr5=54CB0B20 spr6=54CB3018
act5=4C4E9128 act6=4C4E9790
ACT5 action88/frame0/layer0=(-11,-110,index=0,mirror=0)
```

The distinct SPR and ACT pointers prove that native channels 5 and 6 survive
as independent resources, but the male/female traces and GRF filename match
prove they are not two hand channels. ACT5's bitmap contains both weapon
silhouettes in every idle and attack frame. ACT6 matches the `*_검광`
weapon-glow/trail ACT; its later visibility is an effect, not an off-hand
coordinate. Every ACT frame still has one layer and no hidden anchor records.

The individual item ACTs contain visible attacks at actions 80..87. Loading
each item through the stock single-item path and remapping 88..95 to those
actions is why `fc9bddb` showed the originals.

## Why the old commit still placed both weapons on one hand

Actor SPR/ACT members are parallel render channels:

```text
SPR[channel] <-> ACT[channel]
```

They are not implicit right/left-hand anchors. Both individual weapon ACTs are
primary-hand-authored. For example:

| Asset/action/frame | X | Y | index | mirror |
|---|---:|---:|---:|---:|
| 13412 action 80 frame 0 | 0 | -84 | 0 | 0 |
| 1238 action 80 frame 0 | -7 | -70 | 0 | 0 |

The action/frame routine at `0x00D36ED0` applies its special remapping only
when the render channel is 1..4; weapon channels 5 and 6 perform normal ACT
lookup. Their absolute coordinates cannot be copied onto original item layers
because generic and item sprites have different bitmap origins, and ACT5 and
ACT6 also have different coordinate origins. The transferable value is the
displacement from the live, job/gender-specific generic single-weapon source
layer to the live composite component target.

Consequently, every classifier-approved dual split restores original art,
retains the clean client's native dual ACT pair, and obtains generic
single-weapon baselines by native weapon type rather than item ID.

## Corrected equipment hook

The hook always runs the requested stock update first, preserving native actor
state and ownership side effects. For a classified dual-weapon pair it then
reproduces the working `fc9bddb` sequence:

1. rejects a zero off-hand;
2. classifies the off item through the client's native item-to-weapon
   function;
3. classifies a nonzero main item through the same function;
4. invokes the stock updater with the off-hand item as the sole main item;
5. captures and retains only that off-hand SPR/ACT pair from slot 5 with the
   native AddRef;
6. invokes the native main-only setup as the final stock call, leaving the
   real main-hand pair natively owned in slot 5;
7. releases any resources in slot 6 and transfers the retained off-hand pair
   into slot 6;
8. restores the real main/off item fields and publishes ownership.

The successful dual path never replays the stock `(main, off)` update after
the main-only setup, because that would reinstall the generic combined
resource and mutate native cache state. Replaying the exact requested stock
state is reserved for an intermediate-load failure, after retained references
have been released.

The off-hand-only branch follows the same retain-and-transfer principle: it
retains the off item from the single-item slot-5 load, runs the native
off-only setup, releases slots 5 and 6, leaves slot 5 empty, and transfers the
retained pair to slot 6. Shields and other non-weapon items remain on the
stock path because the native classifier rejects them.

No exact item, gender, or job comparison is permitted to decide whether
original resources load.

## Patch-owned resource registry

Stock combined weapons also populate channels 5 and 6, so item IDs and live
slot-pointer equality alone do not prove that a generalized split succeeded.

After a successful dual transfer, the equipment hook publishes a 52-byte
record in a 4096-set, four-way associative table:

```text
actor
SPR[5]
ACT[5]
SPR[6]
ACT[6]
retained stock ACT[5]
retained stock ACT[6]
generic single main ACT
generic single off ACT
native combined dual type
native main single type
native off single type
effective native job
```

The record is invalidated before the actor's next equipment update. The four
ways prevent an ordinary actor-hash collision from immediately discarding an
active split. Invalidating, replacing, or collision-evicting a row releases
all four retained ACT references before reuse. The actor key is published
last, after all eight resource pointers, so the action hook cannot observe a
partially initialized capability.

The generalized action fallback is deliberately independent of this registry.
If lookup misses or a full set evicts the actor, the bridge validates the live
slot and re-runs the native off/main item classifiers. Main-hand and
off-hand-only resources still use `88..95 -> 80..87`; a dual channel-6 miss
does not remap, so it cannot reappear on the primary hand. Registry loss
cannot select the stock generic resource.

ACT5/ACT6 are AddRef'd immediately after the requested stock dual update and
before any single-item call can release them. This occurs for every pair whose
main and off values both pass the native item-to-weapon classifier. The action
bridge resolves the renderer actor's row and requires all four current
original-art pointers to match before it can query either retained native ACT,
so a stale or foreign renderer cannot consume the placement oracle.

On the 2025 client, the hook then calls native `D39130(item, 0)` for each
hand and passes the returned generic weapon type to `D3F4F0`. That loader
selects resources from the live actor's job and gender and installs the
generic single-weapon pair in slot 1. The hook retains the two ACT baselines
while preserving and restoring the previous slot-1 SPR/ACT owners and actor
weapon-type field. The patch contains no item, view, job, gender, direction,
or frame allowlist.

## Action and geometry paths

For every successfully split weapon pair, idle actions remain in `32..39`
and dual attacks use item actions `80..87`. The ACT5 component record selects
the exact source frame that pixel-registers to each precomposed hand component
and embeds its expected generic source sprite index.

Before remapping either original item ACT, the action bridge queries retained
composite ACT5 at the requested action/frame, validates its live sprite index,
and resolves both component records from the dense GRF-derived pose table.
ACT6 visibility is intentionally ignored because that resource is glow/trail
animation.

The dense table is keyed by gender, native combined type 25..30, idle/attack
phase, direction, and frame. Each record contains component weapon class,
expected combined and generic source sprite indexes, component-local center,
and the exact generic source action/frame.
Mixed pairs select the component matching the current weapon class;
same-class pairs use first-component/main and second-component/off ownership.
Item IDs and view IDs are absent from the table. Assassin/Assassin Cross,
Guillotine Cross, and Shadow Cross each use a separately derived complete
gender/type table because their body and weapon attack patterns are not
interchangeable.

If native ACT6 has sprite index `-1`, stock is not proving that the off-hand is
absent. The generic pair remains baked into ACT5 in every frame; ACT6 merely
adds a glow/trail in the later frames where it becomes visible. Replacing ACT5
with one original item removes both baked silhouettes, so both component
anchors must come from ACT5.

For every frame, the component-local center is added to the live ACT5 layer
transform. This is derived from the actual generic dual SPR silhouette, not
from ACT6 or another animation frame.

The pose generator reads every relevant ACT/SPR from `spritedata.grf`, checks
the native dual topology, derives the two silhouettes, and emits a fixed-size
classifier-wide payload. The QJS build decodes that payload and the verifier
round-trips it byte-for-byte. The derivation is class/gender/direction/frame
based; adding a new item ID never requires a pose entry.

After selecting a component, the action bridge queries the retained generic
main or off ACT at the record's exact source action/frame and validates the
returned layer and sprite index. This query is essential: the client gives the
composite ACT and generic single ACT different live loader translations.

The final layer bridge requires the same original-item ACT capability, copies
all 36 bytes of the selected original-item layer into patch-owned scratch
storage, and applies:

```text
live target = live composite ACT5 outer transform + component-local center
final X/Y = rendered original-item X/Y + live target X/Y - live generic source X/Y
final mirror = rendered original-item mirror XOR live target mirror XOR live source mirror
final rotation = normalize(rendered original-item rotation + live target rotation - live source rotation)
```

The native loader shift varies by resource and action frame. A raw-GRF
target-minus-source delta therefore cannot cancel the live translation; that
was the source of the observed 14–32 pixel off-hand displacement. Subtracting
the queried live generic source from the queried live composite target keeps
both operands in renderer coordinates. Sprite index, color, scale, type,
width, and height remain item-authored. Rotation is transferred with the same
live target-minus-source rule.

## Profiled sites

| Contract | 2025-07-16 | 2026-02-19 |
|---|---:|---:|
| equipment updater | `0x00D403A0` | `0x00DB2840` |
| ACT-frame call | `0x00D36EE4` | `0x00DA90F4` |
| final ACT-layer call | `0x00605CD9` | `0x006418C9` |
| item-to-weapon function | `0x00D8A1D0` | `0x00E19530` |
| item-pair to generic weapon type | `0x00D39130` | not yet profiled |
| generic slot-1 weapon loader | `0x00D3F4F0` | not yet profiled |
| item database | `0x015FA3C0` | `0x01732638` |
| actor gender | `+0x260` | `+0x260` |
| actor job resolver | `0x00C43230` | `0x00CABFA0` |
| SPR vector | `+0x4AC` | `+0x4B4` |
| ACT vector | `+0x4B8` | `+0x4C0` |

## Verification

Source and live-GRF contract:

```powershell
.\.venv\Scripts\python.exe tools\verify_dual_weapon_sprite_contract.py `
  --exe "Outputs\dual_weapon_debugview_20250716.exe" `
  --grf "D:\Programs\Games\Ragnarok\02_client\Banquet of Heroes\spritedata.grf"
```

Static executable checks must confirm:

1. the three stock sites target separate patch-owned hooks;
2. the equipment hook calls the native item classifier for off and main;
3. the off-hand-only transfer path is present;
4. a successful split publishes actor, four installed pointers, native
   ACT5/ACT6, two generic single baselines, the three native weapon types, and
   effective job in a 52-byte ownership row;
5. every classifier-approved dual pair retains native ACT5 and ACT6 with
   AddRef, without item/view/gender/job gates;
6. the equipment hook calls the generic type mapper and slot-1 loader twice,
   then restores the previous slot-1 owners and actor weapon type;
7. the action bridge queries the native composite current action and the
   retained per-hand generic source action/frame, validates both sprite
   indexes, and publishes their live X/Y/mirror/rotation transforms;
8. ACT6 is never consumed as a hand layer; every ACT5 frame validates its
   sprite index and uses the matching gender/type/phase/direction/frame
   component record;
9. the final-layer bridge requires the matching split ACT capability and
   applies live composite-target minus live generic-source X/Y, mirror parity,
   and rotation to the original item layer;
10. ownership and baseline misses never draw a dual off-hand with a
    primary-hand-authored fallback action.

Live acceptance:

1. 13412 main + 1201 off, front/back idle;
2. all eight attack directions, especially rear-facing frames;
3. repeat attack-direction coverage for Assassin, Assassin Cross, Guillotine
   Cross, and Shadow Cross; cover both genders where matching assets exist;
4. ordinary Knife + Sword displays both original item sprites with native
   channel-5/6 hand placement;
5. off-hand-only Knife and Sword each remain visible;
6. equip/unequip, map change, relog, Alt+Tab, and clean exit;
7. no corruption after repeated equipment changes.

The generic Knife/Sword checks prove resource selection and visibility.
Independent-hand placement is proven by comparing the clean client's
composite ACT5 silhouettes against the patched original-item result.
Eligibility is classifier-wide; new item IDs do not require source changes or
their own geometry profile.

Until those screenshots and lifecycle checks pass, visual status is
"implementation verified; live acceptance pending."
