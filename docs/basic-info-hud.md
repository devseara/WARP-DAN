# Circular Basic Info HUD

Implemented October 18, 2026 for the approved 280×70 preview, using the user's
`basicinfoui` artwork. This updates the existing **RO Global Zero Basic
Information HUD** patch (`ROGlobalZeroBasicInfo`) for the July 16, 2025 client.

The panel shows the decoded character name, a circular class icon, a base/job
level badge, and labeled HP, SP and AP with current/maximum values and percentage.
HP uses the supplied red gradient at a displayed 25% or below, otherwise green.
SP is blue and AP orange. Long names are shortened with an ellipsis; unusually
large values use a smaller font within the value column. Progress uses a 64-bit
intermediate to avoid overflow with large HP values.

HP/SP remain bound to the native session globals. AP/MAXAP use the existing
`AllowAPBarforAllJobs` status map, retaining the existing maximum-200 fallback
only when native MAXAP is absent. The icon resolves exact supplied job art,
then a class-lineage alias, then the circular Novice fallback. The native child
refreshes with parent draws so its base/job level badge updates on level-up.

The existing Classic UI forwarding, native title-control policy, Alt+V compact
behavior, child lifecycle, and Job/gauge tooltip routing are retained. The only
change to the shared theme patch is the Basic Info width, from 252 to 280.

## Applying

Restart WARP from `D:/warp/WARP DAN LATEST/WARP-DAN`, load the existing client
profile, and rebuild with **RO Global Zero Basic Information HUD** and its
existing **RO Global Zero UI Theme** / **Allow AP Bar for all Jobs** selections.
No server compilation or database changes are needed.

The patch copies `Inputs/BasicInfoUI/assets` beside the output EXE into
`data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/eitr_basicinfo`. Keep that folder with the client
and retain the existing data-folder-first patch. The source `basicinfoui`
folder is not overwritten. Forty-nine supplied PNGs are packaged byte-for-byte;
four additional strips repeat the original one-pixel gradients to 213 pixels
for one cropped draw per bar. To regenerate the package:

```text
python tools/build_basic_info_assets.py "<path-to-basicinfoui>"
```

The HUD privately allocates the existing exported PNG source-over and pixel
finalization helpers, plus a bounded crop routine. No shared renderer hooks or
helper source files are modified, and using these builders does not enable
Modern Chat or Auto Combat. This preserves transparent PNG overlays and repairs
the zero alpha produced by native text drawing.

## Validation and limits

`Outputs/basic-info-revision-20261018` contains backups, source/asset hashes,
an isolated WARP build, its diagnostic contract, emulator renders and results.
`tools/test_basic_info_hud.py` executes the emitted x86, including PNG blending,
gauge cropping and text-alpha finalization. Tests cover both compact branches,
zero/full/over-max/low HP, large HP/SP, missing AP maximum, long UTF-8 names,
class aliases, live level changes, tooltip overlap, factory dimensions and the
changed Basic Info section of repeated theme transitions. Resource loading,
font rasterization, clear and OS calls are explicit test boundaries.

This is offline validation, not live in-game acceptance. The installed client
EXE is preserved; the isolated test EXE is not a replacement for the full user
profile. Unrelated feature suites were not rerun. Current hashes are compared
before/after; existing differences from the older Battle Pass/Gacha acceptance
manifest are retained, not rewritten.
