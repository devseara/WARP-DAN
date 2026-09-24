# First-job HD sprites and next-job plan

## Accepted release

**First jobs V1 is user-accepted as of 2026-09-25.** Acceptance follows the
installed all-job bundle and the user's instruction to document the accepted
versions and commit. This freezes the current artwork; cleanup must not change
its pixels or reopen resolved visual decisions.

| Job | Male accepted version | Female accepted version |
| --- | --- | --- |
| Swordman | complete-v1 + localized collar 55 | complete-v1 + native-position glove/cuff 84 |
| Mage | casting V3, including the side collar and repaired 98-101 sequence | Pending — native remains installed |
| Archer | complete-v1 | complete-v1 |
| Acolyte | complete-v1 | complete-v1 |
| Merchant | complete-v1 | complete-v1 |
| Thief | complete-v1 | complete-v1 |
| Novice | Existing accepted v5 preserved | Existing accepted v5 preserved |

The first-job acceptance covers **11 body pairs, 1,144 actions, 5,016 frame
uses and 1,279 authored poses**. Each pair has 104 actions and 456 frame uses.
Both Novice pairs remain byte-identical to their separately accepted v5 release.

[accepted-v1.json](../Inputs/HDFirstJobs/accepted-v1.json) is the only maintained
first-job input record. It pins all 26 installed SPR/ACT files with full SHA-256
hashes, identifies their component versions, records acceptance and the female
Mage exception, and points to the frozen sources and recovery data.
Acceptance is the user's confirmation of these deployed versions; the agent's
source, export and browser checks are recorded separately from live-client
observation.

Installed archive:

    C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\maindata.grf

Accepted archive SHA-256:
`8e182c06538ade5d9ec7028548939d7b89786604b16701df8fb69d0e050e1dc9`.

The deployment added 20 resources for the ten pairs that were still missing.
Male Mage V3 and the four accepted Novice files were already present. Read-back
and DATA.INI priority checks verified all 26 files, with 18,301 existing records
preserved. Native heads, female Mage, clan outfits, DATA.INI and executables
were unchanged. Reopen the archive in GRF Editor after an external save and
restart the client when loading changed sprite resources.

## Female Mage exception

Female Mage has **88 of 112 HD poses**; 24 remain unfinished. The user explicitly
chose to keep her pending until complete. Her intended design remains the
original costume rendered in the selected HD style. Do not substitute the
conservative-upscale experiment, promote wrong-facing source sheets, or
silently mix incomplete HD animation with native fallback frames.

The 24 missing poses are 21-28 and 45-60: side walking, sitting, pickup and
early combat poses. Retained source art and generation history are under
`Assets/HDFirstJobs/complete-v1/mage/`. This exception does not block planning
the next jobs, and it is not an acceptance of female Mage's unfinished artwork.

## Frozen files, verification and recovery

The accepted artifact root is `Assets/HDFirstJobs/accepted-v1/`:

| Path | Purpose |
| --- | --- |
| `resources/<job>/<sex>/body.spr/.act` | Exact accepted exports, including preserved Novice |
| `paint/<job>/<sex>/<index>.png` | 1,279 final 2x body canvases |
| `native/` | Pinned original body and head SPR/ACT inputs |
| `source-plan.json` | Canonical pose placement and source hashes |
| `release/first-jobs-accepted-v1.grf` | Verified standalone distribution of all 26 resources |
| `review.html` | Original/accepted comparison with all actions and frame stepping |
| `verification/` | Exact rebuild, export, installed-resource and browser results |
| `recovery/before-first-jobs-v1.grf` | Effective resources before the all-job save |
| `recovery/installation-receipt.json` | Exact archive transaction and rollback metadata |
| `second-jobs-native-inventory.json` | Read-only inventory used for the next-job plan |

The maintained workflow is intentionally small:

| File | Responsibility |
| --- | --- |
| [first_job_hd_sprites.py](../tools/first_job_hd_sprites.py) | Verify, reproduce, package, review and reinstall the frozen release |
| [first_job_hd_review.html](../tools/first_job_hd_review.html) | Shared original/accepted animation viewer |
| [verify_first_job_hd_sprites.cjs](../tools/verify_first_job_hd_sprites.cjs) | Browser regression checks and playback |

It reuses the existing Novice/common SPR/ACT codecs and GRF transaction helper.
No conservative-filter experiment, per-correction exporter or separate
standing-review tool is needed for the accepted release.

From the repository root:

```powershell
python -B tools/first_job_hd_sprites.py verify --installed
python -B tools/first_job_hd_sprites.py build
python -B tools/first_job_hd_sprites.py package
python -B tools/first_job_hd_sprites.py review
node tools/verify_first_job_hd_sprites.cjs
```

`build` writes only to `accepted-v1/rebuilt/` and rejects any SPR/ACT byte
difference from the accepted hashes. `verify` checks native/source/resource
pins, independently decodes truecolor SPR data, replays all 5,016 frames, and
verifies native ACT timing, sounds, ranges and anchors. `--installed` additionally
checks the game archive and loading priority. `package` must reproduce the
accepted distribution byte-for-byte.

The viewer is available at
[accepted-v1/review.html](http://127.0.0.1:8771/accepted-v1/review.html) while the
existing server runs. To restart it:

    python -m http.server 8771 --bind 127.0.0.1 --directory Assets/HDFirstJobs

The browser checker uses the locally bundled Playwright and Edge. Its paths/URL
can be overridden with `FIRST_JOB_PLAYWRIGHT_MODULE`, `FIRST_JOB_EDGE_PATH` and
`FIRST_JOB_REVIEW_URL`. Python requires Pillow and NumPy.

Reinstallation is a deliberate separate action:

    python -B tools/first_job_hd_sprites.py deploy

It writes only the 26 pinned resources, checks higher-priority and loose-file
overrides, uses an atomic GRF transaction, and creates a new receipt rather than
overwriting the acceptance receipt. It never closes a client or editor.

A whole-archive rollback using `clan_grf_transaction.rollback` is valid only
while the archive matches that receipt's `after_sha256`. The accepted receipt
restores the state before the all-job save, which already included Mage V3 and
Novice v5. Use a new scoped restoration if unrelated archive changes occurred.

Git contains the compact acceptance record, maintained tools and this document.
Large artwork and binaries remain ignored. The portable recovery bundle is
`Assets/HDFirstJobs/accepted-v1/recovery/first-jobs-accepted-v1-recovery.zip`;
restore its repository-relative contents before using a fresh checkout without
the local assets. Its separate receipt records the archive hash and verified
entry count.

## Cleanup and retained lessons

The 12 previous tool/template versions and eight old input records were
archived before cleanup in
`Assets/HDFirstJobs/history/pre-acceptance-workflow.zip`. Eleven obsolete tool
files and all eight old input files were removed; the remaining viewer template
was replaced with the accepted-release viewer. The accepted input record
consolidates scope, provenance and recovery pointers. Historical art directories
remain available, including the incomplete female Mage sources.

The cleanup rebuild matched all 22 first-job export files byte-for-byte; the
26-resource distribution and installed GRF were preserved. The browser verifies
all accepted pairs and labels native female Mage as pending. This is preservation
of the accepted result, not another round of visual changes.

Carry these rules into the next job families:

- Use complete native frames as geometry references. A native ACT anchor does
  not correct a misplaced collar, wrong hand or front-facing body painted into
  an image. Native facing can change within an action.
- Use visible alpha (at least 128) for collar and sole geometry. In Mage V2,
  alpha>0 fringe selected y=98 instead of the real collar at y=114, placing a
  held neckline 16 HD pixels too low. V3 uses the consistent visible boundary.
- Encoding crops are different: they retain every alpha pixel and compensate
  the origin exactly. Do not indiscriminately replace codec crop bounds with
  anatomical thresholds.
- Inspect actual wrists, knuckles, cuff boundaries and head/neck seams on the
  original. Preserve width and limb volume; avoid whole-body reshaping to fix
  one attachment. Use small native-detail crops when whole-frame generation
  misreads a hand.
- Inspect every animation frame and mirrored use, including held lead-in
  frames. Nonzero alpha overlap, endpoint-only browser checks or small
  contact sheets do not establish correct visible anatomy.
- Use the redrawn HD finish. The conservative upscale and simulated QJS
  filtering were comparison studies, not the selected production method.

## Next scope: 2-1 and 2-2 jobs

Planning only: no second-job artwork, GRF changes or server changes have been
started. The 2026-09-25 inventory read the actual local `spritedata.grf` and found
every main SPR/ACT pair below. The resource stem lives under
`data/sprite/인간족/몸통/<sex>/<stem>_<sex>`.

### 2-1 family

| Job | Native stem | Stored sprites M/F | Frame uses M/F |
| --- | --- | ---: | ---: |
| Knight | 기사 | 112 / 108 | 456 / 456 |
| Wizard | 위저드 | 120 / 116 | 456 / 448 |
| Hunter | 헌터 | 124 / 116 | 456 / 456 |
| Priest | 프리스트 | 132 / 106 | 456 / 456 |
| Blacksmith | 제철공 | 116 / 120 | 456 / 456 |
| Assassin | 어세신 | 120 / 120 | 456 / 456 |

This is 12 main body sets, 1,410 stored sprites (1,393 referenced by ACT) and
5,464 frame uses.

### 2-2 family

| Job | Native stem | Stored sprites M/F | Frame uses M/F |
| --- | --- | ---: | ---: |
| Crusader | 크루세이더 | 111 / 112 | 456 / 456 |
| Sage | 세이지 | 114 / 112 | 456 / 456 |
| Bard | 바드 | 120 / — | 456 / — |
| Dancer | 무희 | — / 122 | — / 456 |
| Monk | 몽크 | 120 / 118 | 456 / 456 |
| Alchemist | 연금술사 | 114 / 124 | 456 / 456 |
| Rogue | 로그 | 109 / 114 | 456 / 448 |

This is 12 main body sets, 1,390 stored sprites (1,387 referenced by ACT) and
5,464 frame uses. Bard is male
and Dancer female, consistent with the
[official class-gender reference](https://renewal.playragnarok.com/gameguide/howtoplay_basicsystem02.aspx).

Both families total **24 main body sets, 2,800 stored sprites, 2,780
ACT-referenced poses and 10,928 frame uses**. All have 104 actions, but female Wizard and female Rogue have 448 frame
uses. Preserve these source counts; do not force the first-job count of 456.

### Mounted variants and dependencies

Inventory also found Knight Peco (`페코페코_기사`) and Crusader Peco
(`신페코크루세이더`), both sexes: four extra body sets, 326 source poses and
1,808 frame uses. Knight Peco has 448 frame uses per sex; Crusader Peco has 456.
Only 307 of the 326 stored mount sprites are referenced by ACT. Treat these
as a separate mount milestone, bringing the planned total to 28 sets and
12,736 frame uses. Confirm the live client's new/legacy Crusader
Peco selection before authoring; old Peco and cosmetic-mount files also exist.

Standard non-transcendent 2-1/2-2 bodies are the primary scope. Transcendent,
baby/alternate, costume and cash-shop mount variants are not implicitly added.
Native weapons, shields, carts, falcons, headgear and heads remain separate
assets: validate their composition with the new bodies rather than redrawing
them into a body SPR.

### Work order and acceptance gates

1. **First deliverable: 2-1 standing previews.** Prepare male/female previews
   for all six classes at front, side and rear views, with the native head
   attached and original costume/palette retained. Pin the original resources,
   frame inventories and named neck, wrist and sole landmarks before drawing.
2. **Knight male/female motion pilot.** Complete one eight-direction walk and
   representative sitting, weapon, hit and casting actions first. Check held
   frames, weapon/shield grips, head/helmet fit and stable foot contact before
   scaling the workflow to every class. Keep Peco work separate.
3. **Complete 2-1 in small batches:** Knight/Priest, then Hunter/Blacksmith,
   then Assassin/Wizard. Prioritize armor/robe consistency, bow and tool grips,
   dual-weapon ownership, and rear/profile casting respectively. Author at most
   eight coherent poses per sheet; use four or isolated details for complex
   hands and overlaps.
4. **2-2 standing previews, then motion:** Crusader/Monk, Rogue/Alchemist,
   then Sage plus Bard/Dancer. Pay particular attention to shields and punching,
   crouch/throw poses, casting, instruments, whips and performance animations.
5. **Full per-class review:** every native action, direction and frame with
   unchanged heads and expected equipment. Use shared-origin original/HD
   comparisons, body-only inspection, pixel grids, contrast backgrounds and
   animated/onion-skin checks. Pin each reviewed source and export. Incomplete
   pairs stay explicitly pending.
6. **Mounted milestone:** verify rider/head/weapon registration and gait for
   both Knight and Crusader Peco pairs, including mount/dismount transitions.
7. **Batch deployment and acceptance:** independently reopen the full SPR/ACT
   sets, verify source-specific frame counts and native metadata, prepare
   recovery data, then save the explicitly listed completed batch. State the
   entire installed scope and every pending exception. Obtain the user's
   in-game feedback before freezing the next accepted version.

These are proposed stages, not a schedule commitment. The native inventory is
ready; the next implementation step is the twelve 2-1 standing previews.
