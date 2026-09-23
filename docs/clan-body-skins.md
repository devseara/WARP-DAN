# Angel Clan sprites

Updated 2026-09-24. This is the single maintained clan guide. Detailed release,
acceptance and installation evidence belongs in JSON records, not separate guides.

## Current installed release

`first-jobs-archer-walk-v12` is installed in
`C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/maindata.grf`.
It contains six first jobs, both sexes: 24 world resources, 1,248 actions and
5,472 frame uses. Each pair retains all 104 native actions and 456 frame uses.
The user authorized installation; live visual acceptance of these latest
corrections is pending. Earlier design approvals remain historical evidence.

| Job | Current source under Assets/ClanBodySkins |
| --- | --- |
| Swordman | neck-motion-correction-v1/swordman/assets |
| Mage | neck-motion-correction-v1/mage/assets |
| Acolyte | shoulder-motion-v2/acolyte/assets |
| Archer | archer-shoulder-v3/archer/assets |
| Merchant | neck-motion-correction-v1/merchant/assets |
| Thief | neck-motion-correction-v1/thief/assets |

The authoritative source paths and hashes are in
[clan-sprites-current.json](../Inputs/ClanBodySkins/records/clan-sprites-current.json).
[The V11 receipt](../Inputs/ClanBodySkins/records/clan-sprites-v11-installation.json)
records the combined head/neck and diagonal-shoulder update, including Thief's
first installation. [The V12 receipt](../Inputs/ClanBodySkins/records/clan-sprites-v12-installation.json)
records the subsequent four-resource Archer replacement. The other twenty clan
resources are unchanged from V11. Both transactions preserved unrelated records
and their compressed bytes. No executable or server changes were made.

The original investigation and source pins are retained in
[clan-all-jobs-motion-audit.json](../Inputs/ClanBodySkins/records/clan-all-jobs-motion-audit.json)
and [clan-neck-motion-correction.json](../Inputs/ClanBodySkins/records/clan-neck-motion-correction.json).
Historical drawings, calibration, approvals and older reports remain in the saved
asset bundles. Version names alone do not prove a file is unused.

## Correction method and validation

- Keep the native head track. Correct the costume's actual collar/body placement
  before restoring an altered ACT anchor. Hair touching a shoulder is not proof
  that the neck is attached, and an inferred palette centroid is not a reviewed
  anatomical landmark.
- Swordman and Acolyte use their own native skin palette only inside an inspected
  dark collar aperture, with a bounded continuation of at most two game pixels.
  Bright collar rims and armor highlights remain intact. Misplaced collars need
  registration first; adding skin elsewhere does not fix them.
- Mage rear collars and male Thief neck caps are fitted beneath native heads.
  Mage's horizontal correction moves the whole pose to avoid bending the robe.
  Female Merchant and male Thief retain their original idle/walk sole planes.
- Archer retains native head anchors. Bow corrections preserve all 144 inspected
  grip regions. Non-walking actions are unchanged by the shoulder follow-up.
- Acolyte diagonals 1/3/5/7 and all eight Archer walking directions use one coherent
  collar-attached shoulder/mantle surface per view. It translates with the native
  neck track without frame-dependent resizing. A connected minimum-error seam
  joins it to each frame's moving arms. Archer profiles use a higher join below
  the pauldron so the fixed surface does not cross a bending elbow.
- Pixels below each join retain the preceding frame's arm, hand, lower-costume
  and foot artwork. V11 changed 112 diagonal frame uses across four pairs; V12
  changed 56 additional Archer frames in directions 0/2/4/6 and preserved those
  diagonals. Do not stabilize shoulders by freezing the hands or moving the feet.

Independent SPR decoding, reopened pixel comparisons, native head rendering,
frame counts, timing, ranges and sounds pass. No new major detached fragments
were found. V11's browser check covered 2,208 action-boundary frames and all 96
walking loops. V12 rechecked both complete Archer pairs: 368 boundary frames,
16 walking loops and 128 rigid-surface/lower-region comparisons. The detail
strips and representative full poses were inspected. These results do not claim
manual pixel certification of every action or live in-game acceptance.

Current reviewer, served from `Assets/ClanBodySkins`:
`archer-shoulder-v3/review.html`. It contains all six jobs and links to the exact
SPR/ACT pairs. Older reviewers are historical; use the current path when judging
the installed Archer. Compare native, previous and corrected frames at one world
origin, with heads toggled and dark/checker/magenta backgrounds as needed.

## Source storage and recovery

Git contains the correction/audit code, required helpers, tests, pinned records
and this guide. Artwork, native references, previews, GRFs and ZIPs stay under
ignored `Assets/ClanBodySkins`, outside disposable `Outputs`.

Restore these bundles into the repository root in order:

1. `releases/first-jobs-neck-shoulders-v11/current-work.zip`.
2. `releases/first-jobs-archer-walk-v12/current-work-delta.zip`.

Both paths are relative to `Assets/ClanBodySkins`. Keep both: the delta excludes
unchanged artwork. V12's `recovery-parent.json` pins the required parent archive
hash, and each release's `saved-work.json` records ZIP verification. The bundles
contain the frozen source pairs, native references, calibration, code and release
evidence needed to reproduce these corrections. Their guides are release-time
snapshots; this committed file is the maintained guide.

Do not delete required earlier pairs merely because their appearance was replaced.
The neck builder consumes the frozen September 23 inventory; the diagonal fix
consumes those neck-correction pairs; Archer V3 consumes the installed V11 pairs
pinned in `archer-shoulder-v3/source-pins.json`. The old artwork remains a build
input. Review PNGs can be regenerated instead of copied into every ZIP.

## Rebuild and review

Use a separate restored workspace when reproducing a release. Dependencies for
artwork tools are Python 3, Pillow and NumPy. The browser verifier uses Node,
Playwright and Edge at the local paths declared at the top of its script.
Runtime build dependencies are separate and listed below.

Only rebuild the prerequisites if their pinned outputs need restoration:

```powershell
python tools/correct_clan_neck_registration.py build
python tools/fix_clan_shoulders.py build
```

Rebuild the latest Archer follow-up from V11's immutable source pins:

```powershell
python tools/fix_clan_shoulders.py build --job archer --direction 0 --direction 2 --direction 4 --direction 6 --work Assets/ClanBodySkins/archer-shoulder-v3 --revision shoulder-v3 --sources Assets/ClanBodySkins/archer-shoulder-v3/source-pins.json
python tools/fix_clan_shoulders.py verify --job archer --direction 0 --direction 1 --direction 2 --direction 3 --direction 4 --direction 5 --direction 6 --direction 7 --work Assets/ClanBodySkins/archer-shoulder-v3 --revision shoulder-v3 --sources Assets/ClanBodySkins/archer-shoulder-v3/source-pins.json
python tools/review_clan_neck_correction.py --work Assets/ClanBodySkins/archer-shoulder-v3 --sources Assets/ClanBodySkins/archer-shoulder-v3/release-files.json --topology-baseline Assets/ClanBodySkins/archer-shoulder-v3/source-pins.json
```

The reviewer reconstructs lossless PNG differences and checks them against the
reopened exports. Omit `--job` after recovery to regenerate all preview PNGs;
add `--job archer` for an incremental Archer refresh. Serve the asset root and
run the browser check in another terminal:

```powershell
python -m http.server 8808 --bind 127.0.0.1 --directory Assets/ClanBodySkins
node tools/verify_clan_shoulder_release_browser.cjs --work=archer-shoulder-v3 archer
```

Frozen calibration includes `collar-calibration.json`,
`acolyte-walk-collars.json` and `archer-bow-grips.json` under the neck-correction
work directory. Inspect any proposed replacement landmark against the native
pixels before enabling it. Preserve original frame order, mirror axes and action
semantics; Archer group 4 is combat-ready, 5 unarmed, 10 bow and 11 dagger.

A deliberate art/code change creates a new candidate and new output hashes.
Do not silently rebind an existing acceptance, source pin or installation record.
Technical checks, deployment authorization and visual acceptance are distinct.

## Package, install and roll back

The installed V12 maindata contains the combined result. For another archive,
apply the V11 full package first and then the V12 Archer-only update:

- `releases/first-jobs-neck-shoulders-v11/angel-first-jobs-neck-shoulders-v11.grf`
- `releases/first-jobs-archer-walk-v12/angel-archer-walk-v12.grf`

Run against the saved expected source hashes:

```powershell
python tools/tests/clan_grf_transaction_test.py
python tools/release_archer_walk_followup.py prepare
python tools/release_archer_walk_followup.py install
python tools/release_archer_walk_followup.py archive
```

`release_clan_neck_shoulders.py` provides the same stages for the V11 base. Close
applications holding the archive before installation. The shared transaction
checks expected replaced resources, complete pairs, update.grf precedence and
payload hashes, then atomically replaces the verified pending archive. Reopen
the client to inspect the installed art. The latest installation verified all
24 payloads, four changed Archer resources and twenty unchanged clan resources.

Receipts describe the archive at transaction time. They retain the original
header/length and hashes for exact rollback without another complete GRF copy.
Rollback refuses an archive changed afterward; earlier receipts cannot undo
later unrelated updates. Use the current matching receipt:

```powershell
python tools/release_accepted_clan_sprites.py --rollback Assets/ClanBodySkins/releases/first-jobs-archer-walk-v12/maindata-transaction.json
```

Use `--finish RECEIPT` only for a verified pending replacement. Preserve receipts,
source pins and recovery dependencies. Commit only scoped clan code, records and
this document; exclude binary artwork, generated archives, local profiles,
Settings and unrelated feature work.

## Producing a job sprite

1. Use that job and sex's original SPR/ACT as a locked drawing canvas, not just a
   visual example. Inventory every action, frame, timing, mirror and attachment.
2. Fit the approved original Angel outfit to front, diagonal, side and rear views
   at one logical scale with native heads. Preserve body volume and costume details.
3. Trace the original anatomy on a separate outfit layer at the same origin. The
   design changes the clothes, not the pose or bone lengths. Track visible collar,
   shoulder, glove, hip, knee, ankle and toe positions. Compare adjacent frames with
   onion skins; preserve leg ownership and toe/heel contact through crossings.
4. Keep arms, dress and legs anatomically connected. Do not reuse a cutout containing
   both feet or clothing around a glove as one moving limb. Motion references from
   another job must not replace this job's boot or costume artwork.
5. Keep one logical drawing scale across directions and actions. Do not resize each
   pose to its bounding box; bent and crouched poses naturally occupy less height.
   ACT anchors are relative attachment points, not anatomical neck landmarks: inspect
   head/collar contact in sitting, bent poses and every rear action. Preserve native
   metadata; correct misplaced anatomy in the outfit pixels before export.
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

The V11/V12 changes are sprite-resource corrections; they do not modify these
runtime hooks. Runtime or shared-renderer changes require fresh live validation.
