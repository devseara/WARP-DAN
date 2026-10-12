# HD sprites: installed state, workflow and roadmap

Updated 2026-10-12. This is the one maintained HD Sprite document. Previous
revision narratives and retired scripts/inputs are in the verified
[cleanup archive](../Assets/HDFirstJobs/cleanup-history/20261012/retired-hd-sprite-work.zip).
Artwork, editable projects, review pages and release backups remain intact.

## Current installed state

Target: `C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/maindata.grf`.
The refreshed [installed inventory](../Inputs/HDFirstJobs/installed-hd-bodies-20261012.json)
reads back 14 pairs / 28 resources: Novice and the six first jobs, both sexes,
with 1, 456 actions and 6,384 frame uses. Coverage is not live visual acceptance.

**Female Mage V16 is installed for live testing.** The selected design is gallery
#6 (`female-mage-complete-fit-v2`), including its proportions, chest panels and
textured shading. Subsequent silver-armor redesign experiments are superseded.
The complete pair has 104 actions, 456 frame uses and204 stored body sprites.
Gameplay output is one body layer per frame in ACT 2.4 / SPR 2.0, at scale 0.5;
native head assets remain separate. V14 preparation was accepted, then rear
boot contact was reopened and corrected in V16. V16 deployment was explicitly
authorized for live testing; full live acceptance remains open.

| Installed item | SHA-256 |
| --- | --- |
| `maindata.grf` | `a8c8b2c924f1df7cebbb07f36497edff5a1c75b9d4d5e374383e60813e226ac8` |
| `data/sprite/인간족/몸통/여/마법사_여.spr` | `b964720835013284d491acb796dd39e1ffdc26d5b7f623919a2f1622fb3072f1` |
| `data/sprite/인간족/몸통/여/마법사_여.act` | `841bf4ad96a9b0c69451a9848bbbf1948115e327ec91e402268f5ca5c22e9ff8` |

[Pair record](../Inputs/HDFirstJobs/female-mage-grounded-v16.json),
[installation receipt](../Inputs/HDFirstJobs/female-mage-grounded-v16-installation.json),
and [release verification](../Assets/HDFirstJobs/releases/female-mage-grounded-v16-20261012/installed-verification.json)
pin the bytes. The release preserved 18,321 unrelated GRF records and 26 other HD
resources. Riftlock signing and independent manifest rescan passed. The sprite
installation did not modify the client EXE, DATA.INI, other GRFs or server policy.

## Open defects and next work

1. **Live zoom head/body drift:** normal/close screenshots show approximately
   10-12 close-capture pixels of upward head displacement relative to the torso
   after torso alignment. This is a photographic estimate, not an engine trace.
   All 24 idle anchors match native and body origins are integral, but static
   validity does not establish runtime correctness. A deeper collar alone does
   not explain the two captures. Isolate runtime scaling/attachment handling
   before changing art. [Zoom evidence](http://127.0.0.1:8771/animation-audit-v1/female-mage-zoom-registration-audit/review.html).
2. **Melee3 residue:** A88/A89/A94/A95 F0 have a detached line above the head
   (15-16 pixels at alpha>=16, maximum alpha184-187). This source defect survived
   the lossless export. [Audit proof](http://127.0.0.1:8771/animation-audit-v1/female-mage-v14-compatibility-audit/review.html).
3. **Remaining acceptance:** live zoom, anatomy and equipped weapon/shield
   behavior are not signed off. All 456 body rasters round-trip exactly, are
   nonempty, and preserve metadata; these format checks do not prove pose quality.

Resolve zoom registration before expanding mounts. Keep design #6; do not apply
a blind global head shift or substitute another design. Existing runtime patch
work, including `UniformSpriteRHW.qjs`, is outside this cleanup. Its presence is
not recorded here as a validated fix. Client root cause and the live-accepted
`UniformSpriteRHW`/`FloorSafeSpriteDepth` fixes: [sprite-quad-depth.md](sprite-quad-depth.md).

## Editable source and proof

Paths below are under `Assets/HDFirstJobs/animation-audit-v1/`.

| Purpose | Location |
| --- | --- |
| Installed V16 editable source | `female-mage-grounded-preparation-v16/mage-grounded-final.actproj` |
| Final workspace renders | `female-mage-grounded-preparation-v16/rendered-final/` |
| Installed gameplay pair | `female-mage-grounded-preparation-v16/candidate/mage-female.{spr,act}` |
| Final pixel recipe | `female-mage-grounded-preparation-v16/pixel-recipe-final.json` |
| Correction audit and sole measurements | `female-mage-grounded-preparation-v16/correction-audit-final.json`, `sole-verification.json` |
| Native reference | `female-mage-complete-style-v1/native-reference.actproj` |
| Selected design #6 | `female-mage-complete-fit-v2/` |
| Previous V14 editable source | `female-mage-design6-workspace-v14/` |
| Installed idle audit | `female-mage-live-idle-head-audit/` |
| Zoom captures and measurements | `female-mage-zoom-registration-audit/` |

V16 changes 20 rear preparation frames; 436 remain identical to V14. Both sole
rows match native in all 24 A34-A37 frames. Boots move without resampling; short
plain-shaft joins were rebuilt with workspace pixels. The central tabard and
all pixels above canvas y340 are preserved. `rendered-all/` is an intermediate
V16 attempt; use `rendered-final/` and `mage-grounded-final.actproj`.
[Installed V16 review](http://127.0.0.1:8771/animation-audit-v1/female-mage-grounded-preparation-v16/review.html).

## Release and rollback

Release: `Assets/HDFirstJobs/releases/female-mage-grounded-v16-20261012/`.
Keep `accepted/`, `before/`, `maindata.grf.before`, `maindata-transaction.json`,
`release.json`, `installed-verification.json` and signature/manifest logs together.
The prior pair, full archive and matching Riftlock manifest/signature are backed
up. Never overwrite subsequent unrelated changes with an old whole-file backup.
A scoped rollback requires the current archive to match its receipt's after hash.

Maintained entrypoint: `tools/release_mage_grounded_v16.py`; shared release
service: `tools/hd_sprite_release.py`. Verify without regenerating artwork:

```powershell
python -B tools/release_mage_grounded_v16.py verify
```

This checks installed payloads, other HD resources, signature and independent
manifest. Do not rerun prepare/install for an already installed release. Future
revisions need a new release directory and receipt. Close client/editor before
external saves; preserve unrelated records, regenerate/sign Riftlock, read back
and test live. Signing keys stay outside packages. Installation failure restores
the coherent archive plus matching manifest/signature checkpoint.

Historical layered ACT 2.5/SPR 2.1 output had disappearing-frame reports. The
adopted single-layer ACT 2.4/SPR 2.0 format matches the prior working contract;
the exact engine failure mechanism or a sprite-index limit was not proved.


### Which GRF wins

The active classic-NPC client embeds this archive order:

1. `dual_weapon_male_assets.grf`
2. `update.grf`
3. `maindata.grf`
4. `mapdata.grf`
5. `palettedata.grf`
6. `spritedata.grf`
7. `data.grf`
8. `greyworld.grf`

Neither higher-priority archive nor loose `data/` files overrides the 28 standard
HD resources. `spritedata.grf` and `palettedata.grf` contain native lower-priority
copies. `jobs00.grf` contains separate clan assets but is absent from this active
embedded list. DATA.INI lists update/main/sprite/data, but the embedded loader
is the active authority for this EXE. [Archive discovery](../Assets/HDFirstJobs/releases/female-mage-grounded-v16-20261012/archive-discovery.json)
records the checked archives and resource hashes.

### Standard HD and Angel clan sprites are separate

| Stream | Paths and scale | Current evidence |
| --- | --- | --- |
| Standard HD jobs + Novice | Normal Korean body stems; 2x RGBA art / ACT scale 0.5 | Installed inventory above; female Mage V16 update |
| Angel clan outfits | `data/sprite/clan_skins/1/`; established 4x art / ACT scale 0.25 | `first-jobs-archer-walk-v12` manifest, 24 tracked resources, independently still matching maindata |
| Native previews | NativeActJobPreviews draws the same world resources in Alt+Q/Alt+S | Renderer source and tests below |

[Clan source manifest](../Inputs/ClanBodySkins/records/clan-sprites-current.json)
and [V12 installation receipt](../Inputs/ClanBodySkins/records/clan-sprites-v12-installation.json)
remain valid for that separate namespace. V16 did not update clan Mage artwork.
The clan release name never identifies the standard-HD release.

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

## Mount status and roadmap

Use each job's default mount: Novice/Poring, Swordman/Peco, Mage/Fox,
Archer/Ostrich, Acolyte/Alpaca, Merchant/Boar, Thief/Cerberus. Verify the actual
resource path on the target client; do not replace every job with Peco artwork.

Retained prototype folders: `first-job-mount-hd-v1`, `female-mage-fox-mount-v3`,
`female-mage-fox-workspace-v4`, `female-mage-fox-native-combat-v5`, all under
`animation-audit-v1/`. No complete mounted set or cosmetic-combat feature is
installed. Fox tongue removal was requested; head/collar and tail ownership
need validation. Generated attack/cast gestures were rejected. Reuse original
Mage melee/casting poses, include preparation/recovery, and compare native
Knight/Paladin Peco melee. After the zoom fix, show first-job/Novice examples
before expanding all jobs.

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

### Track B: cosmetic/all-job mounts with combat

This is a separate client/server feature as well as artwork. The actual Banquet
source currently rejects skills under `SC_ALL_RIDING` in `src/map/skill.cpp:889`
and `status.cpp:2294`; `db/re/status.yml` sets All_Riding `NoAttack: true`.
The same restriction is visible in upstream [skill.cpp](https://github.com/rathena/rathena/blob/master/src/map/skill.cpp)
and [status.yml](https://github.com/rathena/rathena/blob/master/db/re/status.yml).
Native Peco skill state uses `OPTION_RIDING`, which differs from this cosmetic
status; [skill-db state documentation](https://github.com/rathena/rathena/blob/master/doc/skill_db.txt)
documents the distinction.

Plan this branch explicitly:

1. Choose the first cosmetic mount/class combination and exact mounted resource
   path by live file/action tracing; a useful casting pilot is the accepted
   female Mage outfit. Inventory all affected class/sex variants. The existence
   of 104 ACT slots does not prove real mounted attack/cast art exists in them.
2. Profile the 2025-07-16 client's attack/skill input gates and mounted action
   selection. Prove packet creation, cast start/cancel/end and return-to-mounted-
   idle under a disabled-by-default feature flag. Use static profiled bridges,
   original-byte checks and the existing QJS safety/rebuild process.
3. Add an explicit server policy/allowlist for permitted combat mount modes.
   Review NoAttack and every cast check together; retain normal resource, target,
   range, cooldown, status and movement checks. Do not globally weaken unrelated
   riding, map or skill restrictions. This request plans that work; it does not
   enable it or alter server balance.
4. Author genuine rider attack and cast-start/hold/release/cancel poses on the
   selected mount references, with complete limb and cloth ownership. Preserve
   supported native action contracts or document the exact dispatcher/resource
   changes; do not fill missing sequences with a frozen idle frame.
5. Verify unmounted combat remains unchanged, mounted normal/skill damage occurs
   once, cast cancellation works, attack/cast recovery returns correctly, and
   unsupported mounts stay blocked. Test both sexes, eight views, equipment,
   mount/dismount, relog, map change, UI and Riftlock signing/connection.

Track A and cosmetic prototypes have distinct gates. Track B proceeds only after its client,
server-policy and complete-action prototype gate is satisfied.

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
Peco combat/casting. No future sprite or feature is included in the installed V16 pair.

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

## Active tooling and recovery

Retain `first_job_hd_sprites.py` (frozen baseline), `audit_hd_next_jobs.py`
(native inventory), `release_mage_grounded_v16.py`, `hd_sprite_release.py`, and
shared codecs, GRF transaction, runtime and renderer dependencies. The immutable
`accepted-v1.json`, current inventory/pair/installation records, second-job plan
and documentation manifest remain active. Novice sources and receipts remain
in `Inputs/HDNovice/records/`. Historical acceptance is not latest deployment.

48 one-off authoring, rejected-rig, proof and superseded release scripts,
14 superseded Mage inputs and one obsolete build log were removed from active
folders after byte-for-byte ZIP verification. Some scripts worked for their
revision but hardcode old paths or rewrite accepted outputs/docs; they are
historical reproduction material rather than maintained entrypoints.

[Recovery ZIP](../Assets/HDFirstJobs/cleanup-history/20261012/retired-hd-sprite-work.zip)
retains original relative paths, plus the previous guide/inventory and edited
entrypoint. [Manifest](../Assets/HDFirstJobs/cleanup-history/20261012/manifest.json)
records hashes and removed paths. Restore selected historical files at their
recorded paths if needed; do not blindly rerun old installers. Prior documentation
recovery archives remain. Art, projects, recipes, reviews and all GRF/signing
backups were retained. Runtime patches/profiles and unrelated work were untouched.
