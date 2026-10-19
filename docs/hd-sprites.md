# HD sprites: current release, workflow and roadmap

Updated 2026-10-19. This is the single maintained guide for standard HD jobs,
Novice and their mounted artwork/combat integration. Historical release receipts
and machine evidence are records, not competing instructions. Clan runtime and
GrayMap retain their separate feature specifications linked below.

## Current release and acceptance

Target game directory: `C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes`.
Actual client: `2025-07-16_Ragexe_175220998_clientinfo_patched.exe`.
Local server source/runtime: `C:/Users/Administrator/Documents/GitHub/BanquetOfHeroes`.

| Surface | Current state |
| --- | --- |
| Novice + six first jobs, both sexes | 14 installed HD body pairs; October 12 inventory records 1,456 actions and 6,384 uses. Inventory is format coverage, not visual acceptance. |
| Unmounted female Mage | Installed V16, 104 actions / 456 uses / 204 body images, ACT2.4 / SPR2.0, native head separate. Retain its final project and pixel recipe. |
| Mounted female Mage/Fox body | V45 final, based on V44 R3; 104 actions / 448 uses. Preparation has48 phases with fixed Fox paw-contact regions, moving joints and no global scale animation. Installation authorized for testing; complete live acceptance remains open. |
| Mounted Knife1201 | Existing dedicated pair installed. User reports it appears at the hand but the grip still needs improvement. |
| Client death + GrayMap correction | V49 installed for live testing from the exact V47 executable; mounted corpse/GrayMap live acceptance is pending. No body, Knife or server change. |
| New Knife and standard Rod/Staff grips | V50 is the current review candidate; Candidate=true in Act workspace. V48 is superseded. Neither is accepted, exported or installed. |
| Corpse terrain cutoff | V49 loads the correct Fox corpse, but its native reversed-depth rows still sink behind terrain. V50 contains a scoped client correction, offline verified and not installed. |

| Pinned runtime / resource | SHA-256 |
| --- | --- |
| Previous live V47 client | `17f8e579cd0a54f1d043e43a216041ade391088d00223d864cc8e15f8c09f891` |
| V49 death + GrayMap client | `a01c93ff5e2ef491fadb29a7bf4e0bae05eae4c6130301c643f8c34eb9b9d9e5` |
| Installed map-server (V47 lifecycle) | `fde5da407fabc63552bb85fb0cb29b1bc5ad3a9c72b39a5fd23c4ce6a4f87054` |
| Mounted body ACT | `9169e79984c933896843fbb717a5720a0730cb53890dc8e6cd8a2231c77161f7` |
| Mounted body SPR | `c4a813042471194e04f6cd6e8739351b0ae74a40613827d686739f80eefbf4ce` |
| Installed Knife ACT | `491d4c64e592b6955edac41d7e21d98e1ca736b36d1fe0edff1f831727edf953` |
| Installed Knife SPR | `8438b23046c583642c6f764c78b5dd4ed506bbd0d5b7318e113732619dab8482` |

Current transaction/checkpoint: `Outputs/mage-death-graymap-v49-r2/installation/`.
`release.json` is authoritative for installation status; `installed-verification.json`
records readback, GrayMap atlas, unchanged GRFs/DLLs and independent release signing.
Never infer live appearance from these offline results. The previous V47 paired
client/signing rollback remains in `Outputs/mage-mounted-death-v47/release/`.

The October19 read-only capture again found A65F0, All_Riding=1 and the **unmounted**
body pair in slot0 while the client hash was17f8. This reproduces the reported
corpse defect and establishes that the server persistence worked; the missing
client death-resource correction caused the unchanged corpse.
Evidence: `Outputs/cleanup-20261019/live-death.json` and
`docs/evidence/mage-death-graymap-v49-20261019/`.

### Design authority and editable sources

User-pinned costume reference:
`Assets/HDFirstJobs/animation-audit-v1/female-mage-armor-contract-v42/references/accepted-design-user.png`,
SHA-256 `28434f8d3f60caddb170985e092b9beb6c677190bd5bbb855192d272aa8239c6`.
Preserve its silver chest armor, exact central emblem, collar/cape, skin-colored
midriff, gloves, boots and textured shading. Pose approval never authorizes a
costume redesign. Older pink/silver experiments and revision labels do not
supersede this image. Do not substitute a generic clasp for the emblem.

Paths below are relative to `Assets/HDFirstJobs/animation-audit-v1/`:

| Purpose | Retained source |
| --- | --- |
| Installed unmounted body | `female-mage-grounded-preparation-v16/mage-grounded-final.actproj` + `pixel-recipe-final.json` |
| Unmounted design study | `female-mage-complete-fit-v2/` |
| Original native body reference | `female-mage-complete-style-v1/native-reference.actproj` |
| Approved mounted source | `female-mage-proportion-redraw-v44/mage-fox-proportion-v44-r3.actproj` (SHA `18d2374b98a8bcbb0ef9dfff75368575feb0e04643fd3a2cc241b2a57738254a`) |
| Installed mounted editable pair source | `female-mage-mounted-attachments-v45/mage-fox-equipped-v45-final.actproj`, recipes, masks and `candidate-manifest.json` |
| Unaccepted grip authoring | `female-mage-grip-death-v50/knife-gripping.actproj`, `rod-gripping.actproj`, masks, recipes, palm landmarks and all-action renders; prior V48 retained as comparison |
| Native rendering helper | `female-mage-fox-complete-v15/workspace-render.exe` (active dependency; retain despite obsolete surrounding experiments) |

A GRF stores runtime SPR/ACT files. It cannot recover editable masks, named
layers, source ownership, recipes or the original generation references. Keep
these authoritative sources outside the game archive.

### Current remaining review

- After approval and installation of V50, verify mounted death/revive and map/relog transitions
  in the real client. Confirm the Fox corpse resource, head registration and
  unchanged unmounted/male deaths. New native execution tests cover24 cases;
  filename/file-loading boundaries are explicit doubles, not GPU acceptance.
- Review the V50 Knife/Rod grips against the accepted body. The old224-point
  opaque-body check falsely accepted a rear boot and fist edges as palms. Use
  the inspected anatomical landmarks and composed fingers instead.
- V50 has218 visible grip uses plus6 naturally occluded direct-rear preparation
  slots. Rod/Wand/Staff1601–1609 share native `롯드` artwork; item-specific staff
  skins retain fallback and are not claimed supported. Casting keeps native
  weapon hiding. Export only after user acceptance through Act workspace.
- Unmounted V16's historical Melee3 line residue in A88/A89/A94/A95 F0 remains
  an open source-art issue; avoid presenting format roundtrips as its correction.

[Current grip/corpse candidate](http://127.0.0.1:8771/animation-audit-v1/female-mage-grip-death-v50/review.html).

### V50 review: complete weapon coverage and corpse clipping

The October19 live read of V49 confirmed A64F0, All_Riding=1, body slot0 using
`여우마법사_여`, and CPlayer+0x9C=1. The source corpse raster is intact. Native
reversed depth computes `z-0.16*(row-anchorY)`; above-anchor rows go behind
terrain. FloorSafeSpriteDepth's earlier reversed-path exclusion left this
unhandled. Do not redraw or vertically shift the corpse to hide this error.

V50's review client adds a bridge at0xC40FA6 that clamps both row offsets to
at least zero only for mounted female Mage, visible/body job2 and actions64–71.
Other reversed actors, living actions and the existing shadow hooks stay native.
24 actual native RHW-production cases and17 fallback/path controls pass; fresh
WARP exports match the bridge, and both weather patch orders pass existing depth
regression. `build_mage_corpse_depth.py` and `verify_mage_corpse_depth.py` reproduce
the correction. The matching FloorSafeSpriteDepth source includes this scope.
**Live terrain acceptance remains pending; V49 is still installed.**

V50 grip masks cover the actual front-finger volume instead of a4x4 texture
notch. The ready Rod is upright; attacks retain the established near-side wrist
arc. Act workspace renders104 actions /448 uses per weapon, across all8 views,
plus448 installed-baseline comparisons. Each candidate has218 visible uses and
230 hidden uses, including6 naturally occluded rear-ready phases. All224 native
noncombat/hidden frames are pixel-identical. Across all896 candidate renders,
body/head pixels outside the weapon regions remain exact, no body scale changes
occur, and hilt registration remains within one output pixel. Enlarged per-phase
glove boards cover preparation and all three melee groups. Casting keeps native
weapon hiding; standard Rod/Staff1601–1609 only, not every item-specific skin.

The separate combined review EXE is
`Outputs/mage-grip-death-v50/client/client.exe` (SHA-256
`450a77797d53038298dcf9d145405542d6dcdda11b88f9ffd3276dc21db2ff28`).
It preserves GrayMap and all unrelated mapped bytes, with the corpse-depth and
standard Rod routing changes. Its game weapon pairs are deliberately unexported.
The active MountedMageAttachments QJS remains on the installed Knife-only
feature; the Rod expansion is frozen beside the candidate. No live EXE, GRF or
server file was replaced during V50. Current reports are in
`Outputs/mage-grip-death-v50/` and the compact source-controlled evidence packet.
Long per-frame traces are summarized in Git with counts/examples and SHA-256 pins;
the complete captured packets remain under `Outputs/mage-style-commit/full-evidence/`.

## Runtime contract and diagnosis

`AllowAllRidingCombat` (WARP ID392) changes only the four profiled mount input
branches at C8D6E3, C8D9D5, C8DF7D and C8F7E9. Existing packet, cooldown, target,
movement and busy-state processing stays native. `SC_ALL_RIDING` / EFST613 is
not a Dragon option bit. Default jobs retain their own mounts.

Banquet's `all_riding_combat` defaults0. The local test override is1 in
`conf/import/battle_conf.txt`. The shared PC policy controls conditional NoAttack,
all three skill restrictions and death persistence. Preserve native Peco/Dragon
behavior. The base server feature is committed as e7347b5; mounted-death persistence is
committed as 38d01de and passes32 isolated production-loop cases. Do not mix binary/config states
or restart login/char-server for a client-resource correction.

`MountedMageAttachments` (ID393) is scoped to mounted female Mage using live
visible class+0x25C=2, body job+0x4C8=2, sex+0x260=0 and mount byte+0x2CC=1.
The getter field+0x2C0 is0 in the captured actor and cannot identify this job.

| Actual native path | Required behavior |
| --- | --- |
| 6043E8 -> D36ED0 head selection | Neutral directional head for combat groups4/5/9/10/11/12; body keeps native action/frame. |
| 6043B7 and6044D9 headgear guards | Same neutral head selection/phase basis. |
| 605170 attachment | Preserve moving body anchor minus selected head anchor. |
| D3EA1B appearance load | Use incoming weapon parameters; cached+440 can still be0 on spawn. |
| D40465 equipment /604328 draw | Load dedicated Knife; allow main-weapon slot5. Slot6 is slash effect, slot7 shield. |
| D3E340 mount setter | Native flag/shield refresh, plus scoped weapon reload on actual mount/dismount change. |
| D41DF0 death handler -> calls D41E90 and D41EE2 | Native action3 normalizes the job to unmounted Mage; scoped wrappers pass Fox-Mage4130 to both native ACT/SPR producers. |

The old D36676 hook modified robe/accessory drawing, not main head selection.
V46 restored it and targeted the actual compositor. V47 fixed server persistence
and mount-transition reload but missed the separate death-resource handler.
V49 includes that handler correction without promoting unaccepted grip artwork.
Do not redraw the corpse or change head anchors to compensate for wrong resource
selection. Keep these prior failures as diagnostic evidence.

Resource roots in `maindata.grf`:
- Body: `data/sprite/인간족/몸통/여/여우마법사_여.{act,spr}`.
- Knife: `data/sprite/인간족/여우마법사/여우마법사_여_단검.{act,spr}`.
- Native head9 is in `palettedata.grf`; native Mage weapon/`롯드` references are
  in `spritedata.grf`. V48's proposed `여우마법사_여_롯드` files are not installed.

The active embedded order is dual_weapon_male_assets, update, maindata, mapdata,
palettedata, spritedata, data, greyworld (all `.grf`). DATA.INI alone does not
establish the actual loader order. Standard HD uses normal Korean body stems
at2x/.5; Angel uses `data/sprite/clan_skins/1/` at4x/.25. Separate inventories
and sources; neither namespace proves the other complete.

### GrayMap and zoom compatibility

On October19 the profile selected GrayMap, but the installed V47 EXE had no
`/graymap` string and all four terrain-option calls were stock. V49 adds the
existing import-free GrayMap payload, chains the original slash dispatcher,
and deploys only `data/texture/graymap/cells.tga`. Master starts disabled;
`/graymap` toggles it. See [GrayMap feature specification](graymap.md).
The incremental builder normalizes an absent PE overlay to empty bytes when
checking preservation; no overlay is added or removed.

Retain the accepted `UniformSpriteRHW` / `FloorSafeSpriteDepth` runtime
([contract](sprite-quad-depth.md)). Weather state at02570A38 owns0256AA00–02576018;
no reopened allocation may place instructions in it. The depth fix lives in
`.rhwfix` at02577000. Incremental updates append separate owned sections and
verify all unrelated mapped bytes/imports. No new receive hook is involved.

### Maintained tooling and verification

- Client source: `Scripts/Patches/AllowAllRidingCombat.qjs`,
  `MountedMageAttachments.qjs`; native input/profile and patch tables.
- Existing-client builders: `build_mounted_mage_attachments.py` (Knife + death),
  `build_existing_graymap_client.py` (chained GrayMap),
  `build_mage_mount_grip_client_v48.py` (unaccepted Rod expansion only).
- Act authoring: `build_mage_gripping_weapons_v48.py`, `review_mage_grips_v48.py`.
- Generated Mage QJS template:
  `Scripts/Runtime/MountedMageAttachments/patch.qjs.in`. Regenerate through the
  builder; preserve tabs, CRLF and UTF-8 without BOM. Banners are76 columns with
  closing asterisks aligned in column76. `verify_qjs_patch_style.py` checks all
  three affected patches and the template. These rules also live in `AGENTS.md`.
- Current installer: `tools/release_mage_mount_client.py prepare|install|verify`.
  It hashes the actual target, guards closure, backs up EXE/atlas/signing,
  verifies all GRFs unchanged, signs and independently scans the paired release.
- Tests: `verify_mage_death_dispatch.py`, `verify_mage_mount_compositor.py`,
  `verify_mage_mount_lifecycle.py`, `verify_mage_grip_client_v48.py`,
  `verify_graymap.py`, `verify_graymap_colors.py`, `verify_sprite_depth_live_state.py`.
  Use candidate parameters; preserve historical reports when a verifier has an
  older default output directory. Live readback: `inspect_mage_mounted_live.py`.
- Keep shared codecs, transaction/signing services, first-job/Novice baselines,
  native preview/clan renderer tools and their requirements. Superseded version
  installers are archived reproduction material, not maintained entrypoints.

The V49 combined candidate passes24 actual death-dispatch cases,448 composed
head/anchor cases,448 unchanged body/weapon cases,224 native weapon attachments,
816 synthetic short-headgear guard/phase cases, full native single-weapon mount
transitions, GrayMap producer/style/UI execution and depth/weather regression.
GPU/file/item boundaries are documented in the reports; these do not accept
costume, grip anatomy or live death rendering.

## Artwork and Act workspace contract

Use each job/sex's complete native frames as locked pose references. Preserve
native action order, per-action frame counts, sounds, speeds, anchors, the opaque
32-byte frame blocks, mirror/origin rules and tail data. The corrected workspace
codec preserves those blocks through load, copy, undo and export.

Store editable body, upper/lower arm, hand, garment, mask and mount layers in a
separate `.actproj`. Export only the validated paired game files. Use original
head/weapon/shield/falcon/cart references as overlays; keep them separate in the
game unless the native resource itself combines them.

The validated Act workspace build used for this release is in
`GRFEditor-main/build/act-workspace/20261012-111129/`.
Its `App/GrfCL.exe` supplies inspect/render/apply/import/export through the same
editing service as the GUI. Use the full portable build with its matching DLLs.
Keep JSON recipes, artwork ownership and source pins with every editable project.

Built-in image generation supplies candidate artwork; the actual workspace
service owns fitting, masks, pixel edits, transforms, anchors and exports.
Do not claim external imagegen was the workspace API-key provider. The build
used for V16 is 20261012-111129 (20 workspace tests and 113 security checks at
that build). Generated artwork still requires native-pose and pixel review.
Production rules:

1. Name and inspect actual source shoulder/elbow/wrist/hand, collar/hip/knee/toe
   pixels. A hip trim or palette cluster can masquerade as a hand. Source art
   controls and native destination controls are distinct.
2. Keep one logical scale per job/view and native registration. Preserve volume
   between idle/walk/attack/cast; derive canvas bounds from complete poses and
   equipment, especially mounts. Do not independently centre tight crops.
3. Use complete native poses, onion skins and coherent costume construction.
   A generated sheet is candidate art, not validated animation. Do not continue
   a standing-part deformation when its anatomy visibly fails.
4. Define complete cloth/limb ownership, including shaded/gold hems. Hidden hands
   still need a complete arm beneath the torso. Never globally erase pale/gold
   pixels to hide an ownership defect.
5. Use premultiplied filtering and zero RGB only under zero alpha. Reopen SPR/ACT
   independently at a fixed origin. Native indexed placement uses
   `(x-width//2, y-height//2)`, with mirror before placement.
6. Review every action/view/frame, loop wrap, both sexes, contrast backgrounds,
   equipment and UI. Mark one output pixel per grid square. Ask for a marked
   region if the user's target is ambiguous; the Mage cape incident showed why
   fixing a nearby hem is not sufficient.
7. Component/anchor/format passes do not validate visible anatomy. Record source
   checks, browser checks, user approval and post-install live evidence separately.

Normal HD exports use 2x truecolor art and ACT scale 0.5; Angel clan assets retain
their distinct established 4x/0.25 contract. Never transplant one stream's scale
into the other. Native PAL clothing-dye recolouring is not automatically supplied
by a truecolor outfit; validate/default-scope palettes explicitly.

## HD preview renderer

For the profiled 2025-07-16 client, NativeActJobPreviews (ID 385) applies ACT scale,
mirror, rotation and tint on native Equipment and Skill Tree persistent surfaces.
It uses the same world resource paths, head offsets and frame selection. Camera
zoom cannot repair wrong ACT scale. The retired generated HDJobSpritePreviews
(old ID 384) and `data/sprite/hd_job_ui` pack are not the current renderer.

Maintained sources: `tools/native/native_act_job_ui.cpp`,
`tools/native/native_act_job_ui.qjs.in`, `Scripts/Patches/NativeActJobPreviews.qjs`.
The static QJS bridge needs no new receive hook or generated sprite preview pack.
Renderer changes require source/build checks plus Alt+Q/Alt+S standing/seated,
dragging, close/reopen, job/sex/scale/mirror and head/equipment live checks.

```powershell
python tools/build_native_act_job_ui.py --check
python tools/verify_native_act_job_ui.py
python tools/verify_native_act_job_ui_warp.py
```

These are runtime-change gates, not commands to regenerate accepted artwork.
Old Monk-high/normal-Monk aliases belong to the isolated native-act UI fixture;
they do not prove production 2-2 Monk resources are HD in this active loader.

## Refreshed 2-1 / 2-2 native inventory

The October 12 audit re-read all 28 planned native pairs in the actual local
`spritedata.grf`. All SPR/ACT hashes and counts still match the earlier inventory.
[Action/source matrix](../Inputs/HDFirstJobs/second-jobs-mount-plan-20261012.json)
includes every eight-direction action block and its timing/frame counts.
No second-job HD artwork or mounted-combat code was created in this request.

### 2-1

| Job | Native body stem | Stored sprites M / F | Frame uses M / F |
| --- | --- | ---: | ---: |
| Knight | `기사` | 112 / 108 | 456 / 456 |
| Wizard | `위저드` | 120 / 116 | 456 / 448 |
| Hunter | `헌터` | 124 / 116 | 456 / 456 |
| Priest | `프리스트` | 132 / 106 | 456 / 456 |
| Blacksmith | `제철공` | 116 / 120 | 456 / 456 |
| Assassin | `어세신` | 120 / 120 | 456 / 456 |

12 body sets, 1,410 stored sprites, 1,393 ACT-referenced poses and 5,464 uses.

### 2-2

| Job | Native body stem | Stored sprites M / F | Frame uses M / F |
| --- | --- | ---: | ---: |
| Crusader | `크루세이더` | 111 / 112 | 456 / 456 |
| Sage | `세이지` | 114 / 112 | 456 / 456 |
| Bard | `바드` | 120 / — | 456 / — |
| Dancer | `무희` | — / 122 | — / 456 |
| Monk | `몽크` | 120 / 118 | 456 / 456 |
| Alchemist | `연금술사` | 114 / 124 | 456 / 456 |
| Rogue | `로그` | 109 / 114 | 456 / 448 |

12 body sets, 1,390 stored sprites, 1,387 referenced poses and 5,464 uses.
Bard is male and Dancer female. All 24 main sets have 104 actions; female Wizard
and female Rogue have 448 frame uses. Preserve these counts rather than forcing
456. Standard second jobs total **2,780 referenced poses / 10,928 uses**.
Transcendent, baby, costume/alternate and third/fourth jobs are separate scope.

## Mount production roadmap

Use each job's default mount: Novice/Poring, Swordman/Peco, Mage/Fox,
Archer/Ostrich, Acolyte/Alpaca, Merchant/Boar and Thief/Cerberus.
The female Mage/Fox pilot is installed for testing, with the open gates above.
Other mounted jobs have not passed this pilot's artwork/combat acceptance.

### Track A: native combat Peco bodies

Start with Knight and Crusader Peco, both sexes. Native combined rider/mount
resources are already present:

| Set | Stem | Stored M / F | Uses M / F | Cast frames per direction |
| --- | --- | ---: | ---: | ---: |
| Knight Peco | `페코페코_기사` | 69 / 69 | 448 / 448 | 5 |
| Crusader Peco | `신페코크루세이더` | 94 / 94 | 456 / 456 | 6 |

Four sets add 307 referenced poses and 1,808 uses. With standard second jobs the
source scope is **28 sets / 3,087 referenced poses / 12,736 uses**. Older Crusader
Peco aliases also exist; confirm the actual client-selected new/legacy path and
mount/dismount job IDs before drawing or packaging.

Native mounted action blocks retain combat groups 4/5/10/11 (actions 32-47 and
80-95): 6/5/9/8 frames per direction in both Peco families. Casting is group 12,
actions 96-103, with the counts above. Group labels alone do not establish the
selected sword/spear/shield state; capture the client's actual dispatcher with
each equipment/skill combination. Preserve held frames and native timing while
the server owns ASPD, cast time, damage, cooldown and movement validity.

Implementation sequence:

1. Trace mount/dismount resource requests on the target client; pin native body,
   heads, weapon/shield files, palette state and all action/frame counts. Compare
   mounted and unmounted head/weapon anchors; derive a canvas that includes tail,
   beak, feet and equipment without per-frame shrinking.
2. Build an editable mounted project with mount rear/legs, rider torso, arm/hand,
   cloak and mount foreground ownership. Use the complete mounted native pose as
   the locked action overlay; the approved unmounted HD outfit supplies style.
   Preserve native game decomposition: the stock Peco body is combined, so export
   the matching combined body pair while keeping authoring layers editable.
3. Knight M/F pilot: all eight idle/walk views, then sword/spear normal attack,
   attack-ready/recovery, one targeted skill and one cast-time skill. Check hand
   grips, saddle contact, head bob, Peco toe/heel contact and cloak occlusion.
4. Complete all native mounted actions and both sexes, then Crusader M/F including
   shield handling, cast start/hold/release, cancel/recover, hit and death. Retain
   native mount/dismount transitions and ready-to-idle continuity.
5. Fixed-origin pixel/loop review, equipment and Alt+Q/Alt+S, mount/dismount,
   relog/map change and signed-GRF release gate. Never call an idle/walk mount
   pilot complete when its combat/casting coverage is missing.

### Track B: cosmetic mounts

Complete and live-accept the current female Mage/Fox death, grip, all actions,
head/gear, mount/dismount and map/relog behavior before expanding other jobs.
Reuse each accepted unmounted outfit; draw missing seated anatomy against its
own native mount and use Knight/Crusader only as motion references. Keep all
new jobs review-only until their complete eight-view/action/equipment gates pass.

## Second-job production order and acceptance gates

1. **Design gate:** create the 12 2-1 standing previews first (M/F for six jobs),
   with front, diagonal, side and rear native-head views. Preserve recognizable
   original job costume/materials and job/sex differences. Approve designs before
   expanding animation; pin native sources and outfit source points.
2. **Motion pilot:** Knight M/F full eight-view idle/walk plus sitting, pickup,
   hit/death, sword/spear attacks and cast. Exercise native gear/head registration,
   volume and toe/heel contact. The approved base then feeds Track A Peco work.
3. **Complete 2-1 batches:** Knight/Priest (armor, saddle preparation, robe/cast),
   Hunter/Blacksmith (bow/falcon and tool/cart attachments), Assassin/Wizard
   (dual-hand ownership, weapon states, rear/profile cast poses). Use short
   coherent sheets or individual difficult hand/cloth poses; no per-frame scale fit.
4. **2-2 design then motion batches:** Crusader/Monk (shield/punch and Peco),
   Rogue/Alchemist (crouch, dagger/bow, throw and summon poses), Sage plus
   Bard/Dancer (casting, book/staff, instruments/whip and performances).
5. **Per-pair completion gate:** all original actions and source-specific counts,
   metadata/head/equipment/palette checks, same-origin original/HD loops and pixel
   grids, ownership/alpha/seam checks and source/export hashes. Both required
   sexes must be complete; Bard/Dancer use their native gender split.
6. **Release gate:** explicitly list the completed pair batch and any exceptions,
   user-review exact exports, backup/read back the two-resource pairs, preserve
   other resources, regenerate/sign the Riftlock release, then collect in-game
   feedback before declaring live acceptance. Archive the editable projects,
   recipes, frozen references, proof and transaction/signing recovery checkpoint.

These are work stages, not a delivery-date promise. The next artwork deliverable
is the 12 2-1 design previews plus the Knight motion pilot, followed by native
Peco combat/casting. The 2-1/2-2 roadmap remains future work; the current mounted pilot is female Mage/Fox.

## Angel clan runtime contract (separate resource stream)


For profiled 2025-07-16 Ragexe, select `ClanBodySkins` (ID 386) and
`NativeActJobPreviews` (ID 385). NativeActJobPreviews owns Equipment/Skill Tree
rendering from the same world SPR/ACT; ClanBodySkins has no generated preview
copies or duplicate UI hooks. No new client DLL, receive hook or CustomJobs Lua
entry is required. The clan runtime API is version 2, 40 bytes/ten fields.

| Native boundary | Purpose |
| --- | --- |
| 0xB43AF0 / 0xB42910 | Body path formatters |
| 0xD99150 / 0xD999D0 | Body-job / palette normalization |

Preserve the 24-byte native string ABI, job/sex/weapon/palette semantics, complete-
pair fallback, all nine native UI resource calls and the stock head formatter.
CFile probes release handles and embedded filenames; the cache is bounded to 128
resource stems with nonblocking exclusion. The former clan-only RHW bridge at
0xC4A63E was removed on 2026-10-12; uniform RHW for every sprite is now
`UniformSpriteRHW` (see [sprite-quad-depth.md](sprite-quad-depth.md)). QJS and hashed runtime
C++ use CRLF/UTF-8 without BOM; the existing banner documents ownership and purpose.

Angel Clan 6 maps to SkinId 1 through reserved LOOK_BODY2 value 30001. IDs 1-255 use
30001-30255. BanquetOfHeroes derives this from `status.clan_id` through
`db/clan_skins.yml` (CLAN_SKINS_DB version 1, ClanId 6 / SkinId 1), gated to
`PACKETVER_MAIN_NUM == 20250716`. Spawn, movement, join/leave and map-load refresh
apply it; character selection remains native. Disguise/costume priority and stock
fallback remain intact. `@reloadclanskins` reloads the mapping; SkinId 0 or removal
disables it. Resource stems are the exact Korean job/sex paths under
`data/sprite/clan_skins/1/`. Missing either SPR or ACT falls back to native.

## Runtime verification

For runtime changes, dependencies include pefile, keystone-engine and MSVC x86;
native-preview dependencies are in `tools/requirements-native-act-job-ui.txt`.
Run the existing source, runtime and patch checks, then verify in the client:

```powershell
python tools/build_clan_skin_runtime.py
python tools/test_clan_skin_runtime.py
node tools/tests/clan_skin_patch_test.cjs
python tools/verify_clan_release_warp.py
```

The historical clan V11/V12 changes are sprite-resource corrections; they do not modify these
runtime hooks. Runtime or shared-renderer changes require fresh live validation.

## Storage and cleanup policy

The October19 cleanup reclaimed **16.06 GiB**. It removed superseded female-Mage editable experiments and
old candidate exports after pinning the five authoritative installed/current
projects. All current source directories, accepted outfit references, native
reference projects, recipes, source images and rendered review evidence remain.
No deployed game asset is removed. Unrelated UI/Clan/Novice source trees remain.

Six historical whole-GRF backups are replaced with verified `scoped-rollback.zip`
files containing the exact replaced/removed resources and a list of additions
to remove on rollback. The newest full GRF backup remains. Historical manifests
and signatures are evidence, not files to restore over a newer release. Restore
only scoped resources through a fresh guarded transaction and re-sign.

Cleanup manifest: `Assets/HDFirstJobs/cleanup-history/20261019/manifest.json`.
It records deleted paths, sizes, hashes, protected source pins and reclaimed bytes.
`retired-tools-and-doc.zip` contains nine obsolete pending tools, both prior
HD/mounted guides and35 superseded evidence files with original paths, verified
byte-for-byte before deletion. Current runtime evidence is consolidated into
`docs/evidence/mage-death-graymap-v49-20261019/validation.json`.
The October12 recovery ZIP remains for earlier retired tools/inputs.

Git's index was empty at the start of this cleanup. Pending source fixes and
unrelated Settings/UI/profile changes are not disposable assets. Do not reset
or stage the repository wholesale. Use `tools/cleanup_hd_work.py plan` for a
new inspected plan; its historical apply transaction is intentionally not reusable
without a fresh checkpoint. Do not delete source projects merely because SPR/ACT
exports are in a GRF. Preserve current authoring and release rollback first.

### Pending-change cleanup boundary

Retain active QJS patches, patch IDs/catalog/profile registrations, shared builders,
installers and regression tests. These are required source for the installed fixes
and current review candidate; being uncommitted does not make them disposable.
Only obsolete evidence/intermediate outputs may be retired after checking active
dependencies and preserving a verified recovery copy. Recovery ZIPs do not
replace the maintained patch/tool sources. Superseded V48 evidence is archived;
current combat/V49/V50 evidence remains active.
