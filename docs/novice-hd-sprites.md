# Novice HD sprites

Canonical documentation for the male/female Novice artwork, accepted release,
verification, deployment and recovery. This replaces the scattered Novice sections
and per-version README instructions. Renderer implementation details remain in
[HD Job Sprite Previews](hd-job-sprite-previews.md).

## Current accepted release

**V5 is user-accepted and saved to the client's `maindata.grf`.**
The acceptance receipt is
[novice-idle-collar-v5-acceptance.json](../Inputs/HDNovice/records/novice-idle-collar-v5-acceptance.json).
The authoritative release pointer is
[novice-current.json](../Inputs/HDNovice/records/novice-current.json).
Acceptance is tied to exact resource hashes; rebuilding different artwork does
not inherit that acceptance. The receipt records the user's visual approval and
the GRF read-back, without claiming a separate post-v5 in-game capture.

| Item | Current value |
| --- | --- |
| Artwork and review root | `Assets/HDNovice/idle-collar-v5/` |
| Complete distribution | `release/novice-hd-idle-collar-v5.grf` under that root |
| Installed archive | `C:/Users/Administrator/Documents/Ragnarok/Banquet of Heroes/maindata.grf` |
| Recovery checkpoint | `release/novice-v5-idle-collar-work.zip` under that root |
| Coverage | 104 actions / 456 frame uses per sex; 912 total |
| Source coverage | 110 male and 100 female native body poses |
| Pixel format | 2x truecolor SPR with ACT scale 0.5 |
| Native resources | Original heads/hair, anchors, frame order, timing, ranges and sounds retained |
| Costume colors | Accepted default outfit; native PAL clothing-dye recoloring is not implemented |

The current body combines the fuller v2 male build, the localized v4 male first
Combat 2 arm repair, the v3 female closing Combat 4 arm/finger correction, and the
v5 male idle collar registration. Do not reinstate the narrowed v3 male torso.

The distribution contains exactly these four standard body resources:

| Sex | Entry suffix under `data/sprite/인간족/몸통/` | SHA-256 |
| --- | --- | --- |
| Male | `남/초보자_남.spr` | `15672384e1d9ec6ea2f721efc199c7cb5121e9a13c4c56094e9d0662ed9e8cba` |
| Male | `남/초보자_남.act` | `61e2f34da22f4aead664f4ce538c1e73e3e188a43e84cdef7ceb81b4f3cb7ca1` |
| Female | `여/초보자_여.spr` | `0afd828df56e71697b0f409d44fff38f41f23fbfe889f1160ed313b9f5e95035` |
| Female | `여/초보자_여.act` | `088a89ead5b6d1c43f1c50bc2c56efe363291b77296a4b012570c7520543286a` |

Distribution SHA-256:
`a64127e413a1bdeca3baac22e6dcf06fe77403fc6af271bc929e17dd0f4991b7`.
The archive's overall installed hash can change when other jobs are updated;
verify these resource hashes before concluding that the Novice release changed.

## Accepted corrections and preservation rules

V4 restored every male pose to v2 except source pose 68: the first frame of
Combat 2, action 40/41 and its mirrored uses. Its attacking arm crosses the chest
into the original fist. The obsolete hanging hand is removed and only the
trousers previously covered by it are reconstructed. The original neck opening,
lower breastplate/waist, boots and fuller body proportions remain. Before v5,
452 of 456 male frame uses were pixel-identical to v2; the other four used this
localized repair. Female source poses 93–94 retain the sleeve-free crossing arm
and compact curled glove fingers from v3, including Combat 4 frame 8/8.

V5 addresses the idle-versus-walking collar report. The original standing pilot
placed the male idle collar material too high, where the chin covered it. The
correction samples only vertically in a bounded collar region: four HD pixels
(two native pixels) in front, and three HD pixels (one and a half native pixels)
in diagonal/side views. It does not move the native head or narrow the body.
Horizontal coordinates, pixels outside the support and all pixels below canonical
y=80 remain unchanged. Mirrored directions reuse the same corrected pixels with
a verified mirror translation of `(-1, 0)` on the 208x224 body canvas.

Only male idle directions 0, 1, 2, 6 and 7 change, with three native head poses
each: **15 changed frame uses, 897 unchanged from v4**. Every walking/combat
frame, all rear idle frames and both female files remain unchanged. The accepted
standing-v1 source files remain intact; v5 appends corrected idle images to the
pinned v4 pair and changes only the selected idle frame references.

For future edits, use the complete native pose as the movement reference and
inspect the actual shoulder/elbow/wrist ownership and collar pixels. Boolean
head/body overlap and correct ACT anchors alone do not prove anatomical alignment.
Keep the native head separate. Preserve the approved body volume, foot placement,
frame timing and mirror registration. In particular, the curved lower side trim
seen in the earlier male audit also exists in the original costume; it is not
another hand and must not be removed as one.

## Review and verification

Current local review pages, when the Assets/HDNovice server is running on port 8770:

- [Idle versus walking](http://127.0.0.1:8770/idle-collar-v5/idle-walk-review.html)
- [All actions: original / accepted v4 / v5](http://127.0.0.1:8770/idle-collar-v5/full-action-review.html)
- [Collar pixel grids and idle head poses](http://127.0.0.1:8770/idle-collar-v5/pixel-review.html)

Start the local review server from the repository root if needed:

```powershell
python -m http.server 8770 --bind 127.0.0.1 --directory Assets/HDNovice
```

`verification.json` under the current artwork root records independent SPR decoding,
reopened rendering of all 912 frame uses, native metadata preservation and exact
unchanged-frame comparisons. `collar-corrections.json` records the positive
vertical Jacobians, exact selected-pixel correspondence and bounded unchanged
pixels. `mirror-registration.json` proves the canonical/mirrored baseline relation.
`visual-review.json` records direct enlarged-pixel and all 15 idle-head inspections.

Headless Edge rendered 2,736 comparison canvases, played 13 idle/walk sequences
and exercised all 192 direction/head-pose/walk-phase combinations without errors.
The browser proof is `browser-verification.json`. User acceptance is recorded
separately from those automated checks. The recovery receipt confirms an isolated
rebuild produces all four SPR/ACT files byte-for-byte.

## Rebuild, package and save

Run from the repository root with Python, Pillow and NumPy available. Deployment
also uses pefile to verify the installed preview patch. The browser verifier uses
the existing local Playwright runtime and headless Edge paths recorded in its
script; adjust those paths deliberately when moving the workflow to another PC.

Restore the current recovery ZIP to repository-relative paths before rebuilding
on a fresh checkout. Git alone does not include the ignored raster/binary inputs.

```powershell
python -B tools/fix_novice_idle_collar.py paint
python -B tools/fix_novice_idle_collar.py build
python -B tools/fix_novice_idle_collar.py review
python -B tools/fix_novice_idle_collar.py transition_review
node tools/verify_novice_idle_collar_browser.cjs
python -B tools/release_novice_idle_collar.py package
python -B tools/release_novice_idle_collar.py deploy
python -B tools/save_novice_idle_collar.py
```

Do not run the old full-animation `build` or `prepare/import` stages over the
current release. Their accepted-standing override would restore the pre-v5 idle
collar. Use separate revision paths for new artwork and preserve accepted hashes.

The package contains both complete pairs. Deployment changes only the male pair
relative to v4 and verifies all four current resources. It checks the actual
DATA.INI priority, higher-priority/loose-file overrides, expected Novice hashes,
and the installed `NativeActJobPreviews` payload. It does not modify the executable,
DATA.INI or server. Restart the client to reload cached sprites.

The GRF transaction appends the replacements, preserves unrelated table records
and their original compressed bytes, verifies the source did not change during
preparation, and atomically replaces the archive. The v5 installation preserved
18,297 unrelated records. Its receipt is
[novice-idle-collar-v5-installation.json](../Inputs/HDNovice/records/novice-idle-collar-v5-installation.json).
If an application locks the archive, the tool retains a verified pending file and
receipt; release the lock before finishing the transaction. It must not close the
client automatically.

A whole-archive rollback is valid only when the archive still matches the receipt's
`after_sha256`. Use `clan_grf_transaction.rollback` with that exact receipt; its
hash guard prevents overwriting later unrelated updates. When the archive has
changed, prepare a new scoped replacement of the Novice entries instead.

## Source provenance and revision history

| Revision | Outcome and retained evidence |
| --- | --- |
| `standing-v1` | User-accepted male/female visual pilot. Five canonical views plus three mirrors, original heads, generated source and exact prompt retained. Its eight single-frame actions are incomplete for gameplay and must not replace a full job. Some measured boot differences reached 2.5 native pixels. |
| `complete-v1` | Complete 210-pose authoring and 104-action pairs. Rejected for collars, extra arms and alignment defects; pinned source, original templates, prompts and rejection receipt remain. |
| `correction-v2` | 31 measured collar corrections and bounded male pose 57/61 arm repairs. Later arm-ownership defects were identified. Its fuller male build is the preferred baseline retained by v4/v5. |
| `anatomy-v3` | Cross-chest arm and female Combat 4 glove repairs. The male torso became too narrow and was rejected. Female poses 93–94 are retained; other male v3 repaints are not current. |
| `proportions-v4` | Explicitly accepted: restored v2 male proportions, localized pose 68 repair, female v3 pair retained. Later live screenshot exposed the separate male idle collar issue. |
| `idle-collar-v5` | Current accepted release. Corrects only the five affected male idle views while preserving all other v4 artwork. |

Original bodies came from `spritedata.grf`. Native body/head reference files are
pinned under `Assets/HDNovice/standing-v1/native`. The standing artwork and original
full animation sheets were produced with the built-in ImageGen tool; their PNGs
and exact prompts remain in the respective version directories. The active v4
repaint source is `proportions-v4/generated/male68-local-repair.png` with its matching
`.prompt.txt`. The active female source is
`anatomy-v3/generated/pilot-sleeveless.png` with its matching prompt. V5 generates no
new design; it registers existing accepted pixels through deterministic code.

The current ZIP is sufficient to rebuild v5 from its pinned v4 SPR/ACT inputs and
native references. Earlier authoring ZIPs retain the editable source PNGs and
prompts needed to revisit the original outfits or arm repaints. Old ZIPs remain
historical snapshots; their embedded documentation is not the maintained guide.

## Git commit scope

The maintained source set contains only the accepted v5 workflow:

| Files | Purpose |
| --- | --- |
| `tools/novice_hd_common.py` | Shared codecs, native head/body registration, review generation and documentation link. |
| `tools/fix_novice_idle_collar.py` | Deterministic correction and exact frame/metadata verification. |
| `tools/release_novice_idle_collar.py` | Hash-gated package/deployment, client-payload check and acceptance preservation. |
| `tools/save_novice_idle_collar.py` | Recovery packaging and isolated byte-identical rebuild. |
| `tools/novice_hd_idle_collar_review.html`, `tools/novice_hd_idle_walk_review.html` | Maintained visual review surfaces used by the current workflow. |
| `tools/verify_novice_idle_collar_browser.cjs` | Regression validation of all actions and idle/walk transitions. |
| `Inputs/HDNovice/records/novice-current.json` and `novice-idle-collar-v5*.json` | Current release, acceptance, installation and recovery evidence. |
| `Inputs/HDNovice/records/novice-proportions-v4-acceptance.json` | Exact accepted baseline used by v5. |
| This guide, the Novice link in `docs/hd-job-sprite-previews.md`, and the `.gitignore` entry | Canonical documentation and generated-artifact boundary. |

The shared SPR/ACT codecs, GRF writer, transaction helper and native preview patch
are already tracked. V5 no longer imports standing-trial authoring code, old full
animation generators or superseded release scripts. Those experiments and their
historical audit/rejection records remain in the local authoring history and
versioned recovery archives; they are not part of this production commit.

Generated screenshots, pixel dumps, source experiments, SPR/ACT/GRF outputs,
recovery ZIPs and `Outputs/` are outside Git. Retain the verified current GRF and
recovery ZIP separately: committed code/JSON alone cannot recreate authored art.
The source checkpoint rebuilds v5 from its pinned v4 binary inputs. Do not include
unrelated ClanBodySkins, profiles, Settings.yml, CollectionUI or other job changes
from the dirty checkout in this commit.
