# Angel Clan body skins - accepted release

Updated 2026-09-13. This is the single maintained document for artwork,
SPR/ACT production, the clan runtime patch, validation and deployment.

## Accepted and installed build

| Job | Male | Female | Coverage per sex |
| --- | --- | --- | --- |
| Swordman | V9 | V9 | 104 actions, 456 frame uses |
| Mage | V3 | V10 | 104 actions, 456 frame uses |

The user accepted female Mage V10 after inspecting the front/rear correction.
All four pairs are accepted. The authoritative distribution manifest is
[evidence/clan-sprites-current.json](evidence/clan-sprites-current.json), with
exact resource names, source files and SHA-256 hashes. Installation reads those
pinned files and refuses a changed source or a downgrade of the active correction.

Current distribution:
`Assets/ClanBodySkins/releases/swordman-mage-v4/angel-swordman-mage-v4.grf`.
It contains eight world resources and no generated preview copies. SHA-256:
`e76d8f66ba171f0520c3f08475904f2e7784340f6386b93c3adb2021d12b0a4d`.

Installed target:
`C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/maindata.grf`.
Current archive SHA-256:
`a6b7af09144a0c1490e01001badb29190f71142e2da62d17c9915068148ab627`.
V10 replaced only the female Mage SPR/ACT; 18,277 unrelated records were retained.
The higher-priority `update.grf` no longer shadows the clan world resources.
The earlier deduplication removed 16 verified old clan entries and preserved its
20,405 other entries. DATA.INI, the game executable and server were unchanged.

## Source layout and recovery

Git stores the runtime, generated runtime inputs, current authoring dependency
chain, generic codecs, release tools, tests, manifests and this document.
Artwork and binary distributions are kept under ignored `Assets/ClanBodySkins`.
A fresh checkout requires the saved artwork bundle before rebuilding sprites.

- `Swordman/complete-v9`: accepted complete pairs, source sheets and import plans.
- `Swordman/accepted-walk-v8`: recovered walk inputs preserved by the V9 importer.
- `Mage/male-gait-v3`: accepted male source sheets and complete pair.
- `Mage/female-gait-v10`: accepted complete female pair, fitted front/rear frames,
  landmark diagnostics, acceptance hashes and installation/rollback records.
- `Mage/female-gait-v7` and `Mage/female-gait-v9`: intact complete-pose inputs
  consumed by V10. These are dependencies, not the current release.
- `Mage/walk-repair-v2`, `Mage/female-gait-v6` and `Mage/female-gait-v8`:
  retained inputs for reconstructing earlier stages of the accepted artwork.
- Each job's `native` directory: original body and head SPR/ACT references.

The v4 release directory contains `current-work.zip` and `saved-work.json`.
The ZIP saves pinned exports, selected source art/plans, required baselines,
native references, authoring dependencies, evidence and this document. Every
member is verified against the saved SHA-256 inventory. Review renders and
previous ZIP copies are excluded. Keep durable sources outside `Outputs`.

Obsolete experiment scripts and unique content from superseded packages are
retained in `releases/retired-work.zip`, with a restoration index. They are
removed from the active tools tree. Cleanup only removes packages after every
member is matched to retained loose content or this verified archive; it does
not discard unique artwork. `releases/cleanup-manifest.json` records removed
paths, hashes and the retained locations. Historical evidence remains historical.

## Creating the next job sprite

Acolyte, Archer, Merchant and Thief need original Angel-themed outfits for each
sex. Recoloring stock clothes does not satisfy the design requirement. Keep the
accepted Swordman and Mage files pinned while developing a separate candidate.

1. Extract the original job's complete body and head SPR/ACT. Inventory actions,
   frame counts, speeds, anchors, sound/range metadata, mirrors and layer offsets.
   Use the actual job, sex, action, direction and frame as the pose authority.
2. Create the outfit's eight directional references at one logical scale beside
   native heads. Check front-to-rear width, height, collar position and apparent
   volume. Use spritedata wing views for feather anatomy and directional overlap;
   keep wing roots on the back and the halo center transparent.
3. Draw complete poses over the original frame templates. Track collar, shoulder,
   elbow, glove, hip, knee, ankle and toe positions on visible anatomy. Follow
   native contact phases and limb ownership through crossings. Compare neighboring
   frames with onion skins; a color-cluster center alone is not a joint.
4. Preserve the chosen costume in every pose: stocking trim, thigh volume,
   gauntlets, boot design and dress openings must agree. Do not borrow another
   job's boot artwork to obtain movement metrics. A standing cutout containing
   both legs or clothing around a glove must not be reused as one moving limb.
5. Register source drawings against the native anchors. Correct inconsistent
   volume in the source or continuous frame map; do not hide it with changing ACT
   scale. Check idle-to-walk proportions and all eight directions. Fitted maps
   must remain continuous and free of foldovers; inspect the garment around
   hands/waist as well as the landmark residuals.
6. Export a complete SPR/ACT candidate and review the actual reopened files at
   native timing. Test idle, walking, attack/ready, casting, hit, sitting and death
   using the original ACT action map, including equipment and head alignment.
   A partial idle/walk pilot is never a production body replacement.
7. Pin the approved pair hashes and record user acceptance. Build a review GRF,
   verify archive priority, install within the authorized scope, and reopen the
   client to inspect the installed resource. Update this document and the current
   manifest only for the intended accepted revision.

For repainting, retain prompts and selected source images. Deterministic geometry,
mask, registration and export corrections belong in the existing authoring code.
Do not regenerate the whole costume merely to repair an attachment offset.
Preparation scripts can replace import plans; never run them over accepted art.

## Export and visual checks

The current body pipeline uses SPR 2.0 truecolor, bottom-up ABGR storage, with
4x artwork and ACT scale 0.25. Native heads and equipment remain separate.
Indexed native layer top-left is `(x-width//2, y-height//2)`; mirror before
placement. Preserve ACT anchors, timing, frame order, sounds and ranges.

Reopen the written SPR/ACT and compare every exported bitmap with the independent
`spr_reader.Spr` decoder using `render_native_wing_anatomy.rgba`. Render beside
the same original action/frame on a shared origin; tight crop centering can hide
placement errors. Inspect changed seams at pixel scale, then play all phases at
native timing (75 ms for the current walk). Static sheets alone do not prove gait.

Check dark, black, magenta and checker backgrounds plus alpha-only silhouettes.
Inspect internal gaps as well as outside edges. Remove only confirmed key/matte
pixels; white/gold armor and pale feathers are legitimate details. Zero RGB where
alpha is zero. Premultiply for filtered resampling, or use source-color-preserving
coverage sampling as V10 does. Check cuffs, dress occlusion, wing roots, duplicate
limbs, changing body volume and toe/heel orientation throughout the cycle.

Structural checks support the visual review; they do not override a rejected
silhouette or prove that a correctly placed landmark belongs to the right limb.

## Female Mage V10 implementation

V10 changes only actions 8 and 12: front direction-0 walk and straight-back
direction-4 walk, eight frames each. All other 440 frame uses retain their pixels
and placement. Adjacent rear-diagonal views are unchanged.

The front uses intact V7 complete-pose drawings fitted to consistent front
proportions and the native Mage glove trajectory. The rear fits its complete
walking poses to the rear idle outfit; the previous walking upper body was only
about 83-85% of that reference. Post-fit scale diagnostics are within about 2.5%.
A continuous inverse frame map preserves the dress instead of cutting the torso,
arms and garment into independently moving fragments.

Source colors are preserved with coverage-weighted edge alpha. Sampled Jacobians
are positive (minimum 0.345), and control-point error is below 0.1 native pixel.
Front pixels at world Y >= -22 and rear pixels at Y >= -9 retain the prior lower
stride exactly. Native head anchors and all action metadata are preserved.
[evidence/clan-female-mage-v10.json](evidence/clan-female-mage-v10.json) records
verification and the user's acceptance. Earlier V8/V9 evidence is retained only
as history; neither is the current accepted female source.

Rebuild in a separate checkout restored from `current-work.zip`:

```powershell
python tools/import_full_swordman_art.py --sex male
python tools/import_full_swordman_art.py --sex female
python tools/build_male_mage_gait.py
python tools/build_female_mage_v10.py
python tools/package_female_mage_v10.py
```

The last command verifies the reopened V10 files and recreates the front/rear
viewer and correction ZIP without installing. The standalone V10 package was
previously extracted and rebuilt to the exact pinned SPR/ACT hashes. A changed
rebuild is a candidate until reviewed; production packaging rejects hash drift.

## Runtime and native preview ownership

Select `ClanBodySkins` (local ID 386) and `NativeActJobPreviews` (ID 385) when
rebuilding the profiled 2025-07-16 Ragexe. Equipment and Skill Tree use the same
world pair, applying its ACT scale, mirror, rotation and tint. The clan patch
contains no preview wrappers, `previewPath`, nine UI call rewrites or preview
CACHE coordination. NativeActJobPreviews owns those UI surfaces.

The freestanding x86 clan runtime API is version 2, 40 bytes and ten fields.
Old 48-byte metadata is rejected before allocation. No new client DLL, receive
hook or CustomJobs Lua declaration is needed. QJS has the AutoCombatUI/
AutoSupportUI GPL, author and description banner; QJS and hashed runtime C++
remain CRLF and UTF-8 without BOM.

| Native boundary | Responsibility |
| --- | --- |
| `0xB43AF0` | Body path formatter |
| `0xB42910` | Alternate body path formatter |
| `0xD99150` | Body-job normalization |
| `0xD999D0` | Palette normalization |
| `0xC4A63E` | Completed clan-body quad RHW correction |

All nine UI resource calls and the head formatter remain stock. Resolvers retain
the 24-byte native string ABI, job/sex/weapon/palette semantics and complete-pair
fallback. CFile probes release both the handle and embedded filename. The
bounded 128-entry cache keys complete resource stems with nonblocking exclusion.
The RHW bridge preserves XYZ, UV, color, registers and flags, replays
`8B 45 D8 0B 88 24 01 00 00`, and resumes at `0xC4A647`.

## Clan transport

Angel Clan 6 maps to SkinId 1 through reserved LOOK_BODY2 value 30001. Skin IDs
1-255 use 30001-30255. The adjacent BanquetOfHeroes integration derives this from
`status.clan_id`, preserving real job and normal body style. Its `db/clan_skins.yml`:

```yaml
Header:
  Type: CLAN_SKINS_DB
  Version: 1
Body:
  - ClanId: 6
    SkinId: 1
```

The transport is gated to `PACKETVER_MAIN_NUM == 20250716`. Join/leave, spawn,
movement, appearance updates and map-load self-refresh apply it; character
selection retains the native outfit. Disguise/costume priority and stock fallback
remain intact. Missing either SPR or ACT falls back to native. Use
`@reloadclanskins` after mapping changes; SkinId 0, row removal or empty Body
disables the mapping. This release does not change the server implementation.

Resource paths begin `data/sprite/clan_skins/1/` followed by the exact original
Korean job/sex body path from the manifest. Do not create gameplay jobs or bake
native heads/equipment into these body files. Historical preview entries in
maindata can serve older clients; the current packager does not regenerate them.

## Build, install, backup and rollback

Dependencies: Python 3 with Pillow, NumPy, pefile and keystone-engine; MSVC x86
for runtime rebuilds; Node for QJS checks. Native-preview integration dependencies
are in `tools/requirements-native-act-job-ui.txt`. Original client:
`2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe`,
SHA-256 `ead7c0a316bc6c27705a5a6876daf5093abec31677f3c1af7525c1709b201bff`.

```powershell
python tools/build_clan_skin_runtime.py
python tools/test_clan_skin_runtime.py
node tools/tests/clan_skin_patch_test.cjs
python tools/verify_clan_release_warp.py
python tools/tests/clan_grf_transaction_test.py

# Verify and package all eight pinned world resources.
python tools/release_accepted_clan_sprites.py

# Save and verify artwork and authoring sources.
python tools/save_accepted_clan_work.py

# Install only when deployment is intended.
python tools/release_accepted_clan_sprites.py --install
```

Use `--game "C:/path/to/client"` for an explicit target. Close clients/editors
holding the archives first. The updater verifies higher-priority ownership,
builds beside the target and atomically replaces it, rejecting archives changed
during preparation. It preserves unrelated records and original compressed bytes.

Receipts store exact prior header/length and before/after hashes, allowing exact
rollback without a duplicate full GRF. Rollback refuses a subsequently changed
archive. The current female correction receipt is:

```powershell
python tools/release_accepted_clan_sprites.py --rollback Assets/ClanBodySkins/Mage/female-gait-v10/maindata-v10-transaction.json
```

Use `--finish RECEIPT` if replacement was blocked after preparation. Older v2
maindata/update-dedup receipts remain for history; they are not a shortcut for
rolling back a newer archive. Do not install old review packages over V10.

## Validation and commit scope

[evidence/clan-runtime-v2.json](evidence/clan-runtime-v2.json) records real WARP
exports for clan-only and both orders with NativeActJobPreviews. Runtime/API/
trampoline bytes match generated inputs. Integration preserves stock UI resource
calls and unrelated instructions. x86 tests cover fallback, cache isolation,
collisions, eviction, reentry, bounds, normalizers and cleanup. Transaction tests
cover add/replace/remove preservation, no-op installs and guarded exact rollback.

All four accepted pairs independently decode with 104 actions and 456 frame uses.
V10's 16 changed frames passed silhouette/key, metadata and preservation checks;
the user accepted the installed front/rear result. These are distinct forms of
evidence and are recorded as such.

The scoped commit includes maintained runtime, authoring dependencies, tooling,
tests, manifest/evidence and this document. It excludes local profiles, Settings,
unrelated Bestiary work, binary artwork and generated review/release archives.
Unused experiment code is recoverable from the retired archive. No push is part
of this local commit.
