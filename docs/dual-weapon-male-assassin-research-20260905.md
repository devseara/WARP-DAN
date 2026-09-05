# Male Assassin family implementation research — 2026-09-05

Status: research and original-asset previews complete; male support is **not
implemented or enabled**. The installed client remains the female Assassin
Cross [old-motion / edge-contact build](dual-weapon-edge-contacts-20260905.md),
SHA-256 `4e23389333cd873e3f136b48a67aa20f95d648c8a254318b6630b4266858636c`.
Drake views remain excluded. This work did not rebuild or restart the server.

## Conclusion

Use male generic dual ACT/SPR as the animation reference, with separate male
body contacts and original-item source-image records. The existing native
packet compositor is a viable mechanism; the female rig and contact tables
are not reusable male pose data. Enabling gender 1 alone cannot work.

The audit resolves all 17 in-scope originals under the male Assassin weapon
prefix. Nine have no visible held layer in directions 2–5. These are actual
negative sprite indices, not a missed archive or a coordinate offset. All 17
single-weapon ACTs also have no visible dual88–95 layers: custom weapons must
be composed from profiled held32/solo80 source images against the generic
dual timeline, as a deliberate source-selection operation.

## Reproducible local evidence

[Audit script](../tools/audit_male_assassin_dual_weapon.py),
[full resource/cell/hash report](evidence/dual-weapon-male-assassin-assets-20260905.json),
[animated original generic overlays](../Outputs/dual_weapon_male_research/review.html),
and [native rectangle records](../Outputs/dual_weapon_male_research/native-projections.json).

The script reads loose files and all four active DATA.INI archives in priority
order. There were **no unreadable archives**. It pins the source archive,
byte count and SHA-256 of each resolved ACT/SPR; it checks every layer in
held32, solo80 and dual88, and inventories every original SPR image and the
actions that reference it. Input ACT versions are 2.4/2.5. The script explicitly
rejects newer ACT versions instead of using an incompatible offset parser.

The previews execute the installed 2025 x86 rectangle producer at `0x00C40C20`
on the parsed native-normalized layers. There are 864 distinct projected
layers across the five body candidates and two weapon prefixes. All eight
directions and every held/dual-attack frame are shown; a common viewport bounds
the complete trajectory so upright swords are not clipped. Previews use the
original generic pair 28 art, not an unimplemented male custom compositor.
They omit heads, effects and GPU occlusion and use 150 ms inspection timing.
Candidate job-to-resource mappings have **not** been verified in a live male
actor; file presence and a plausible overlay are not a native dispatch trace.

### Body profiles

All five candidates have 104 actions. In each direction they contain 6 held32
frames, 9 solo80 frames and 8 dual88 frames. Each inspected body frame has one
unnamed ACT anchor, not two identified hand attachment points.

| Candidate | Exact stem under `data/sprite/인간족/몸통/남/` | SPR image count |
| --- | --- | ---: |
| Assassin | `어세신_남` |120 |
| Assassin high variant | `어세신_h_남` |120 |
| Assassin Cross | `어쌔신크로스_남` |115 |
| Guillotine Cross | `길로틴크로스_남` |120 |
| Shadow Cross | `shadow_cross_남` |112 |

Only Assassin and the high variant have equal ACT hashes; their SPR hashes
still differ. No two listed bodies have equal SPR hashes. Separate body pixel
landmarks are required unless measured equivalence is established. The report
also inventories 32 base/alternate/costume/riding ACT paths without enabling
them. Shadow Chaser is a different family and is excluded.

### Weapon profiles and the exact missing cells

The male Assassin prefix is
`data/sprite/인간족/어세신/어세신_남_`.
The separate Shadow Cross prefix is
`data/sprite/인간족/shadow_cross/shadow_cross_남_`.

| Asset result | Views |
| --- | --- |
| All held directions visible in the male Assassin single ACT |1,2,6,36,38,44,45,46 |
| All six held frames have negative image indices in directions 2–5 |34,35,37,39,40,41,42,43,47 |
| Assassin original ACT/SPR resolved |All 17 views |
| Shadow Cross original ACT/SPR resolved |16; view 47 `프리스트의검` is absent at that exact prefix |

For the 16 shared views, **both ACT and SPR bytes are identical between the two
male weapon prefixes**. This permits a shared immutable weapon-image profile
keyed by verified content; it does not establish shared body contacts or the
live resolver's fallback behavior for missing Shadow Cross view 47.

Zeny Knife 1238/view 34 is the useful counterexample:

- Held actions 34–37, frames 0–5: one layer, `sprite_index=-1`, zero scale.
  Advancing the held frame cannot find a visible image in these directions.
- Solo actions 82–85: frames 0/1 are empty; frames 2–8 contain visible art.
- Its four indexed images are20 × 28,25×14,25 × 25 and9×15. The last is a small
  partial blade, used only in actions 82–85. It is not interchangeable with a
  full hilt-bearing image. [Original image sheet](../Outputs/dual_weapon_male_research/male-zeny-original-images.png).
- Blue Twin Edge 13412/view 45 has six images and valid held layers in all 48
  cells. Zeny and Twin Edge therefore cannot share a universal source-frame
  fallback despite being valid weapon resources.

All 1,088 male Assassin single-weapon dual cells (17 × 8 × 8) have negative image
indices. All six native generic pair ACT/SPR sets 25–30 resolve under both male
prefixes. These combined sprites carry the authored dual poses; an individual
original weapon ACT does not acquire those poses by selecting action88.

The normal original suffix `_검광` exists for only generic views 1/2/6 in each
male prefix; 14 custom suffixes are absent. The live native resolver's selected
trail resource must be retained/verified, rather than assuming every item has
its own named trail file.

The male/female comparison also rejects a universal image remap: all 17 ACT
hashes differ; 15 views share no identical dimension/RGBA image signature.
Views 37/41 each share only one signature, which does not accept their timelines.

## Why the existing documentation is insufficient for male coordinates

The earlier [implementation roadmap](dual-wield-original-weapon-sprites.md)
already says to solve the male held-source policy for directions 2–5 and not to
copy female rows. That warning is supported by the raw data above. The current
`build_dual_weapon_native_basis.py` explicitly filters the embedded rig to
family 0/gender 0 and reference views 45/34. `grip_profile.h` and
`held_edge_contacts.h` describe the female Assassin Cross body. They are not
generic job-independent hand coordinates.

ACT layers encode image selection, translation, mirroring, scale and rotation
separately; the loader resolves dimensions from the selected SPR image. ACT
also has a separate per-frame anchor list. None of that provides two semantic
grip sockets automatically. [GRF Editor's primary loader implementation](https://github.com/Tokeiburu/GRFEditor/blob/main/GRF/FileFormats/ActFormat/ActConverter.cs).
The general [ACT format research](https://github.com/rdw-archive/RagnarokFileFormats/blob/master/ACT.MD)
is useful for the structure, but contains open questions about coordinate
semantics; the observed 2025 native producer remains the authority here.

The QJS owner already reads `ActorGender=0x260` and publishes it at registry
row `+0x38`. The C compositor rejects `row->gender!=0`, accepts only the female
Assassin weapon prefix, and compares both body ACT/SPR filenames against the
exact female Assassin Cross name. These checks must become profile selection,
not be removed. Rejection currently preserves the stock path.

## Recommended implementation

1. **Start with male Assassin Cross.** Capture its actual body ACT/SPR,
   original hand resources, native carrier pair, channel5/6 packets and
   action/frame values using the existing live inspector. Begin with
   Zeny/Twin Edge, swapped, Zeny/Zeny and each off-only. This resolves native
   dispatch and which visible generic blade belongs to each equipment slot.
2. **Author a male generic reference.** Overlay the original generic pairs on
   that exact body, as in the research GIFs. Record anatomical hand roles,
   per-role visibility, source-image identity, angle, mirror and attack
   trajectory for all 48 held and 64 dual cells. The rear-facing generic art
   shows less of the weapons: do not force both whole weapons visible or infer
   main/off from screen-left/screen-right. Preserve authored hidden/detached
   attack art and native depth ordering.
3. **Separate source selection from the target pose.** Use an explicit
   `(weapon content, phase, direction, frame, hand role) -> source action,
   source frame, layer, image kind/index, visible/hidden` record. A visible
   target must name a real hilt-bearing or deliberately partial source image
   from that original SPR. Empty held cells need an authored alternate source
   or a justified hidden role; neither frame0 nor an arbitrary modulo is a
   valid fallback. The9-frame solo source and 8-frame dual target require a
   deliberate map, not matching frame numbers.
4. **Measure male hand seams.** Review opaque fist masks and original weapon
   hilt/tip pixels for each selected image. Reuse the edge-contact computation
   and native projection mathematics, with new male inputs. Preserve the male
   generic attack trajectory; held boundary adjustment must not pull slash
   art into the palm. Do not copy the female anatomical role table.
5. **Select an immutable profile at resource publication.** Key it by gender,
   exact body ACT/SPR identity and verified weapon family/content. A profile
   owns phase dimensions, role map, reference trajectory, source records and
   contact records. Reuse the existing actor-owned registry, resource lifetime
   handling and channel dispatch. Keep the 60-byte owner ABI stable or version
   an extension explicitly. Avoid filename scans, pixel searches or mutable
   last-draw coordinates in the hot render path. Validate resource fingerprints
   at load/generation and selected layer/image identity at use.
6. **Validate before widening the gate.** Execute the compiled x86 on every
   visible/hidden cell, all 17 originals in both roles, 9 class pairs, identical
   resources, swaps, off-only, two zooms, mirroring and actor rotation. Exercise
   stale body/source records, missing trails and unsupported views. Prepare
   both hands before suppressing the current stock packet. Repeat owner,
   relocation and page-protection gates, then live-test held, attack, transitions
   and native occlusion. Keep the accepted female build in the regression set.
7. **Extend exact body profiles.** Add Assassin, high variant and Guillotine
   Cross after their live resource identities and hand pixels are measured.
   Share verified male weapon content where identical. Treat Shadow Cross's
   body and missing view 47 separately. Costumes/riding variants remain outside
   the selector until independently profiled. Keep classes 1/2/6 and the current
   non-Drake view scope.

## Other implementation routes

| Route | Practical consequence |
| --- | --- |
| Compiled pose/contact/source tables with existing native draw hooks | Recommended. Original palettes and item identity stay intact; finite data replaces per-frame heuristics. Requires deliberate visibility and native-depth acceptance. |
| Generate per-item/per-hand male ACT resources offline | Makes source-image/pose mapping inspectable in an ACT editor. Still needs a resolver/draw path for two original resources, exact job profiles and versioned generated assets. Can be useful authoring output from the same records. |
| Bake weapons into every job body's ACT/SPR | Couples equipment combinations to body assets, palettes and costumes;17 originals already yield 289 ordered dual pairs per body. Hides the missing-resource problem in generated assets and requires a new body-resource selector. |
| Global XY correction, female mirroring or deleting the gender gate | Cannot repair negative indices, partial images, different timelines or hand visibility. The audited source cells disprove these approaches. |

Yes, weapons can be drawn as layers attached to the job pose; the recommended
compositor already provides that mechanism. The missing information is the male
per-hand/source/visibility profile, not another universal coordinate formula.
The research artifacts are ready for that implementation; they are not a claim
that male original weapons have been live-tested.
