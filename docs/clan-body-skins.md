# Angel Clan sprites

Updated 2026-09-17. This is the single maintained clan guide: accepted assets,
sprite production, runtime ownership, packaging and recovery.

## Current release

| Job | Male | Female | Complete source under Assets/ClanBodySkins |
| --- | --- | --- | --- |
| Swordman | V9 | V9 | Swordman/complete-v9 |
| Mage | V3 | V10 | Mage/male-gait-v3; Mage/female-gait-v10 |
| Acolyte | V2 | V2 | Acolyte/registration-v2 |
| Archer | V5 | V5 | Archer/complete-v5 |

All eight pairs are complete and installed, each with 104 actions and 456 frame
uses. Swordman, Mage, Acolyte and Archer are accepted. Archer V5, including its
corrected bow animation, was accepted by the user on 2026-09-17; the four accepted
SPR/ACT hashes match maindata.grf and the V7 distribution GRF.

- Installed archive: `C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/maindata.grf`.
- Distribution: `Assets/ClanBodySkins/releases/swordman-mage-acolyte-archer-v7/angel-swordman-mage-acolyte-archer-v7.grf`.
- Recovery bundle: the same release directory's `current-work.zip`, verified by `saved-work.json`.
- Next jobs: Merchant and Thief. Their approved designs/native references are saved.

V7 contains sixteen world resources. It replaced only Archer's four V4 files,
preserving the other 18,283 records and their compressed bytes; maindata remains
18,287 records. update.grf has no overrides for these resources. No executable or
server change was needed.

Machine-read records live under `Inputs/ClanBodySkins/records`, outside documentation.
[clan-sprites-current.json](../Inputs/ClanBodySkins/records/clan-sprites-current.json)
pins the source files and resources;
[clan-sprites-v7-installation.json](../Inputs/ClanBodySkins/records/clan-sprites-v7-installation.json)
contains the installed hashes and latest rollback evidence. Keep active records
referenced by manifests and build tools. Superseded Archer pilot reports were
retired into the ignored V5 cleanup record after dependency checks.

## Archer V5 bow correction

Accepted and installed on 2026-09-17. `Archer/complete-v5/user-review.json` pins
both approved SPR/ACT pairs; the release manifest enforces those hashes.

V4 had complete action coverage but incorrect bow anatomy: the female draw arm
hung down in several firing frames, a male raised pose pointed overhead, and rear
arm/cape occlusion hid the draw and release. A populated ACT is not proof of motion.
V5 redraws 24 unique bow poses for actions 80-87, covering all eight directions and
72 frame uses per sex. Every other body/head render (384 per sex) is identical to
V4. Timing and the native nine-frame order remain intact, including hold frames.

For Archer, group 4 is combat-ready, group 5 is unarmed attack, group 10 is bow,
and group 11 is dagger. Confirm this against the actual native body and weapon
ACTs; the [weapon lookup](https://github.com/vthibault/roBrowser/blob/master/src/DB/Jobs/WeaponAction.js)
and [character action mapping](https://github.com/vthibault/roBrowser/blob/master/src/Renderer/Entity/EntityAction.js)
provide corroborating client-source references. Generic numbered attack labels
previously concealed this distinction; the Archer reviewer now names these actions.

`Archer/complete-v5` holds the selected sheets, native bow references, measured
neck/grip coordinates, source pins, exported pairs and review. Use original complete
poses as templates, preserve the approved costume, and inspect both hands with the
actual bow overlay. Use one scale per canonical view; make only continuous fitting
corrections with a positive Jacobian. Redraw an incorrect forearm instead of forcing
a fit that folds pixels. Keep unchanged actions as exact baseline images.

```powershell
python tools/fix_archer_bow_animation.py rebuild
python tools/fix_archer_bow_animation.py review
python tools/angel_job_pipeline.py --job archer --stage review --revision v5 --work Assets/ClanBodySkins/Archer/complete-v5
python tools/angel_job_pipeline.py --job archer --stage package --revision v5 --work Assets/ClanBodySkins/Archer/complete-v5
```

`bow-review.html` plays original/V4/V5 with native heads and an optional bow overlay.
`full-action-review.html` includes all 104 actions. The 144 changed frames pass neck
contact, clipping and connected-alpha checks; all 768 other renders are identical.
Selected sheets use alpha floor 16 and explicitly inspected empty registration
gutters to remove generated annotation residue. The importer refuses exclusions
that touch the connected body; it never removes white armor by color.

`Archer-v5-SPR-ACT-work.zip` reproduces all four export hashes in an isolated rebuild.
The combined V7 recovery also includes dependencies declared by each build-spec,
including native bow SPR/ACTs. Evidence is in `clan-archer-v5.json`, the V5 verification
JSONs and `clan-sprites-v7-installation.json`. No executable/runtime changes are needed.

## Required Archer baselines

V5 replaces only bow actions in `Archer/complete-v4`. V4 was built from the full
artwork in `Archer/complete-v1` and preserves the accepted V3 idle, sitting and
front-walk frames in `Archer/alignment-v3`. These are rebuild inputs, not disposable
version duplicates. Retain their SPR/ACT pairs, source art, landmarks and JSON pins.

When reconstructing V4 itself, use `angel_job_pipeline.py --job archer --stage build`
then `build_full_archer_set.py build`. If selected source artwork changes, run
`build_full_archer_set.py audit` and inspect/update the collar landmarks first.
Normal V5 rebuilds use the pinned V4 pair and the commands above.

## Sources and recovery

Git stores code, runtime inputs, tests, manifests and this guide. Artwork and GRFs
are ignored under `Assets/ClanBodySkins`. Restore `current-work.zip` at the repository
root before rebuilding from a fresh checkout. Keep durable sources outside `Outputs`.
The bundle includes selected artwork, native references, required older inputs,
acceptance records and authoring tools, with a SHA-256 inventory for every member.

Required older inputs remain even when their appearance was superseded:

- Swordman V9 uses `Swordman/accepted-walk-v8`.
- Male Mage V3 uses `Mage/walk-repair-v2`; female V10 uses complete V7/V9 pose inputs.
  Retained V6/V8 and other source plans allow reconstruction of earlier stages.
- Acolyte V2 uses V1's exact SPR/ACT baseline and the registration landmarks in
  `Acolyte/registration-v2/build-spec.json`. `Acolyte/complete-v1` holds the costume drawings.
- Each job's `native` and `design` directories contain original SPR/ACT references,
  approved designs and provenance. Keep these for Archer, Merchant and Thief too.

Old experiments are recoverable from `releases/retired-work.zip` and its cleanup
manifest. Remove duplicate output only after verifying retained copies. Version
numbers and filenames alone do not prove a file is unused.

Repository cleanup on 2026-09-17 removed six superseded Archer report files from
`Inputs/ClanBodySkins/records` and 2,276 old generated review files (63.9 MiB).
`Archer/complete-v5/cleanup.json` retains exact report contents/hashes and the
cleanup inventory; it is included in the recovery bundle. Current V5 reviewers,
accepted pairs, native references and all declared build inputs remain available.

Commit the authoring tools, release guards/tests, current manifest, Archer V5
record, V7 installation receipt and this guide. Keep artwork, GRFs, recovery ZIPs
and generated previews under the ignored `Assets/ClanBodySkins` directory. Local
WARP settings, unrelated profile edits and other feature investigations are not
part of the sprite release. `Outputs/.gitkeep` preserves the empty output folder.

For subsequent jobs, `review_angel_job_design.py` is the reusable partial-design
reviewer. Review pilots separately; `angel_job_pipeline.py` and the release guard
require all 104 native actions, 456 frame uses and zero stock fallback per sex.

## Producing a job sprite

1. Use that job and sex's original SPR/ACT as the pose authority. Inventory every
   action, frame, timing, mirror and attachment before drawing.
2. Fit the approved original Angel outfit to front, diagonal, side and rear views
   at one logical scale with native heads. Preserve body volume and costume details.
3. Draw complete animation poses over the original templates. Track visible collar,
   shoulder, glove, hip, knee, ankle and toe positions. Compare adjacent frames with
   onion skins; preserve leg ownership and toe/heel contact through crossings.
4. Keep arms, dress and legs anatomically connected. Do not reuse a cutout containing
   both feet or clothing around a glove as one moving limb. Motion references from
   another job must not replace this job's boot or costume artwork.
5. Register artwork with stable sequence scale. ACT anchors are relative attachment
   points, not anatomical neck landmarks: inspect the visible head/collar contact,
   including sitting, bent poses and every rear action. Preserve native metadata
   unless correcting a verified attachment defect.
6. Reopen the exported SPR/ACT and review all actions for both sexes and eight
   directions: idle, walk, sit, pickup, hit, attacks/ready, cast, standby and death.
   Compare the same native action/frame at the same origin and native timing.
7. Record approval against exact SPR/ACT hashes, then package and install the approved
   files. Keep technical verification, user acceptance and live-client results distinct.

Use spritedata wing anatomy for every view; verify root attachment and shoulder
occlusion in motion. Keep the halo center transparent. Inspect internal gaps and
outer edges on dark, black, magenta, checker and alpha backgrounds. Remove only
confirmed background residue, preserving pale armor and feather highlights.

The export format is SPR 2.0 truecolor, bottom-up ABGR, with 4x artwork and ACT scale
0.25. Heads and equipment remain separate. Native indexed layer top-left is
`(x-width//2, y-height//2)`; mirror before placement. Verify written pixels against
`spr_reader.Spr` / `render_native_wing_anatomy.rgba`. Zero RGB under zero alpha and
use premultiplied or coverage-aware filtering. Do not hide changing body volume
with per-frame ACT scaling. Static sheets and passing landmarks alone do not prove
correct animation.

Prepare the next job only in a new candidate directory:

```powershell
python tools/prepare_mage_pose_set.py --job archer
# Draw/import the selected sheets recorded in generation-records.json.
python tools/import_angel_job_art.py --job archer --generated C:/path/to/selected-images
python tools/angel_job_pipeline.py --job archer --stage build
python tools/angel_job_pipeline.py --job archer --stage review
python tools/angel_job_pipeline.py --job archer --stage package
```

The shared preparer retains its historical filename and refuses an existing art
plan. Preserve prompts and selected images. Generate one reference-dependent sheet
at a time, then verify pose/grid fidelity and transparency before importing it.
Use deterministic registration fixes for coordinate defects instead of repainting
the approved costume. A partial idle/walk pilot is never a production replacement.

## Rebuilding accepted artwork

Run in a separate checkout restored from the current work bundle. A changed export
is a new candidate; the release packager rejects hashes that differ from approval.

```powershell
python tools/import_full_swordman_art.py --sex male
python tools/import_full_swordman_art.py --sex female
python tools/build_male_mage_gait.py
python tools/build_female_mage_v10.py
python tools/package_female_mage_v10.py
python tools/fit_acolyte_necks.py
python tools/angel_job_pipeline.py --job acolyte --stage review --revision v2 --work Assets/ClanBodySkins/Acolyte/registration-v2
python tools/angel_job_pipeline.py --job acolyte --stage package --revision v2 --work Assets/ClanBodySkins/Acolyte/registration-v2
```

Female Mage V10 corrects front/rear walking (actions 8/12) using continuous complete-
pose fitting around the dress and hands; the other 440 frame uses and native anchors
are preserved. Acolyte V2 changes body-root translation and primary head anchors
only: both SPR files remain byte-identical to V1. Its 912-frame audit checks visible
head/body contact and translation-only body changes. The reviewer must render each
pair's head using its own ACT anchors; a shared stock-head overlay hides corrections.

## Runtime contract

For profiled 2025-07-16 Ragexe, select `ClanBodySkins` (ID 386) and
`NativeActJobPreviews` (ID 385). NativeActJobPreviews owns Equipment/Skill Tree
rendering from the same world SPR/ACT; ClanBodySkins has no generated preview
copies or duplicate UI hooks. No new client DLL, receive hook or CustomJobs Lua
entry is required. The clan runtime API is version 2, 40 bytes/ten fields.

| Native boundary | Purpose |
| --- | --- |
| 0xB43AF0 / 0xB42910 | Body path formatters |
| 0xD99150 / 0xD999D0 | Body-job / palette normalization |
| 0xC4A63E | Completed clan-body quad RHW correction; resumes at 0xC4A647 |

Preserve the 24-byte native string ABI, job/sex/weapon/palette semantics, complete-
pair fallback, all nine native UI resource calls and the stock head formatter.
CFile probes release handles and embedded filenames; the cache is bounded to 128
resource stems with nonblocking exclusion. The RHW bridge preserves XYZ/UV/color,
registers and flags and replays `8B 45 D8 0B 88 24 01 00 00`. QJS and hashed runtime
C++ use CRLF/UTF-8 without BOM; the existing banner documents ownership and purpose.

Angel Clan 6 maps to SkinId 1 through reserved LOOK_BODY2 value 30001. IDs 1-255 use
30001-30255. BanquetOfHeroes derives this from `status.clan_id` through
`db/clan_skins.yml` (CLAN_SKINS_DB version 1, ClanId 6 / SkinId 1), gated to
`PACKETVER_MAIN_NUM == 20250716`. Spawn, movement, join/leave and map-load refresh
apply it; character selection remains native. Disguise/costume priority and stock
fallback remain intact. `@reloadclanskins` reloads the mapping; SkinId 0 or removal
disables it. Resource stems are the exact Korean job/sex paths under
`data/sprite/clan_skins/1/`. Missing either SPR or ACT falls back to native.

## Package, install and validate

Dependencies: Python 3 with Pillow, NumPy, pefile and keystone-engine; MSVC x86 for
runtime builds; Node for QJS checks. Native preview dependencies are listed in
`tools/requirements-native-act-job-ui.txt`. For runtime changes, run:

```powershell
python tools/build_clan_skin_runtime.py
python tools/test_clan_skin_runtime.py
node tools/tests/clan_skin_patch_test.cjs
python tools/verify_clan_release_warp.py
```

For an accepted sprite release:

```powershell
python tools/tests/clan_grf_transaction_test.py
python tools/release_accepted_clan_sprites.py
python tools/release_accepted_clan_sprites.py --install
python tools/save_accepted_clan_work.py
```

Use `--game C:/path/to/client` to target another client. Close applications holding
the archives. The installer verifies complete male/female pairs, acceptance hashes
and update.grf precedence before mutation; it preserves unrelated records and
replaces the verified pending archive atomically. Reopen the client for live review.

The installation receipt stores the old header/length and hashes for exact rollback
without another full GRF copy. Rollback refuses any archive changed afterward:

```powershell
python tools/release_accepted_clan_sprites.py --rollback Assets/ClanBodySkins/releases/swordman-mage-acolyte-archer-v7/maindata-transaction.json
```

Use `--finish RECEIPT` only to finish a verified pending replacement. Preserve older
receipts as history; they cannot roll back newer archive changes. Stage only clan
code, records and this guide when committing. Exclude local profiles, Settings,
unrelated work, binary artwork and generated review/release archives.
