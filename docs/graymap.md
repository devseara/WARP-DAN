# Runtime GrayMap — 2025-07-16

Select **Runtime gray terrain (/graymap) [Experimental]** (`GrayMap`, ID 388).
Apply it after `ROGlobalZeroUITheme` when that patch is selected. The incremental
builder supports an already-installed theme/settings wrapper.

The client starts with the original map. `/graymap` toggles the master state.
**Game Settings → Graphics** has a compact native panel:

| Control | Behavior |
| --- | --- |
| Gray Map | Same master flag as `/graymap`; off restores stock terrain and scenery |
| Cell Grid | Thin square-cell borders on/off; subtle shading remains |
| Hide Scenery | Map trees/buildings/scenery hidden while Gray is on |
| Preset | Tactical (accepted default), Classic gray, High contrast, Warm stone, Custom |
| Walkable | Color for walkable cells; opens the in-game RGB editor |
| Blocked | Color for blocked cells and walls; opens the same editor |

Each control occupies a separate 32px row. Labels are bold, and switches,
dropdown and swatches align at page X150 with the native Graphics fields.
Hovering a label or control shows its explanation through the native tooltip
manager; opening a popup, clicking or scrolling dismisses owned help.

Grid and Hide default on. Palette, preset, custom color slots, Grid and Hide save
in `savedata/graymap.bin` beside the EXE. Master GrayMap always starts disabled.
The file is versioned and length/range checked; invalid records use defaults.
Actors, skills, items, collision and original map resources retain native ownership.

The user accepted the default reference-style floor/grid/blocked appearance on
2026-10-16. The user confirmed palette updates in the initial UI, then reported modal
pauses, held mouse input and footer overlap. The replacement in-game controls,
scrolling and texture-quality recovery subsequently passed user acceptance.
The user confirmed the six-row alignment and working hover tooltips on the
Riftlock-signed release `1792121464`, also on 2026-10-16. The accepted EXE SHA-256
is `3767fff7ffec4b779a4031facb60f204961792102d2044f0f1ac2ea5feac83ba`.
This accepts the reported DX9 client behavior; it does not establish the full
DX7, device-reset and multi-map matrix below.

## Rendering and profile

Supported input is the profiled x86 PE32/linker-14.29 2025-07-16 client. Original
SHA-256: `ead7c0a316bc6c27705a5a6876daf5093abec31677f3c1af7525c1709b201bff`.
Exact original terrain/scenery/vtable bytes are checked before writing.

The atlas is a deterministic 512×256 TGA, not a replacement map. Its 32 variants
cover all 16 combinations of four walkable/blocked GAT cells, with and without
grid lines. Uniform light blue-gray floors, thin lines and continuous dark
obstacles with faint diagonal shading follow the supplied reference. The source is `Assets/GrayMap/cells.tga`; reproduce it
with `tools/build_graymap_atlas.py`. WARP copies it beside the target EXE as
`data/texture/graymap/cells.tga`. No map GRF is edited and no custom DLL is used.

| Native surface | V2 behavior while Gray is on |
| --- | --- |
| Ground vtable entries `0x0104D51C` / `0x0104D520` | Capture the current ground receiver; query the native cached texture loader once per terrain pass |
| Terrain option calls `0x00A64331` / `0x00A64508` | Select single-texture vertices and omit the separate lightmap pass; preserve the actual saved option |
| Renderer option calls `0x0055D8DF` / `0x005530AE` | Make DX9/DX7 consume the same single-texture queue while Gray is enabled |
| Terrain submits `0x00A645ED`, `0x00A63D67`, `0x00A6487E` | Apply atlas to temporary polygons, preserving geometry, alpha and fog/specular data |
| Scenery spans `0x00A7B2F4` / `0x00A7B40A` | Gate only map scene-list drawing; keep native skip/renderer-load branch targets intact |
| Settings create entry `0x01047DB8` | Chain the current constructor, append six native rows, a scrollbar and bounded popup children on the Graphics page |

GND surfaces cover 2×2 GAT cells. World bounds and the native ground scale locate
those cells in the read-only resource GAT array (`+0x110` width, `+0x114` height,
`+0x11C` cells, 20-byte stride/type at +16). Local server mapping treats GAT
0/2/3/4/6 as walkable and 1/5 as blocked. Unknown/out-of-range cells are dark;
unavailable ground metadata uses a neutral fallback. This is the client base
GAT, not dynamic server obstruction state. Vertical terrain sides use dark tiles.
UVs follow source world X/Z, with half-texel insets to prevent atlas bleeding.
Their V endpoints are inverted for the profiled native texture upload so the
logical GAT mask and grid rows are sampled in the intended orientation.

`CTexMgr::Get` at `0x00568760` is a five-argument thiscall (`RET 14h`), matching
the stock `grid.tga` call. Re-querying its cache per pass lets native map/device
lifetime own texture recreation. Missing texture falls back to v1 solid gray.
Atlas polygons remain in the native terrain queue (`0x800`). Both texture lookup
and material bridges preserve the producer's live SSE state. No shared actor,
GDI, device vtable, network hook or runtime code modification is installed.

Off mode delegates to the original terrain getter/queue, ground methods and
scenery draw target, with original arguments. Map-owned resources are not
changed. Settings lookups never execute `/graymap`; child deletion clears its
cached pointer. Cleanup unregisters the slash callback before WARP releases code.

## Palette payload

`Scripts/Runtime/GrayMap/colors.cpp` is offline source for an import-free x86
payload. `tools/build_graymap_colors.py` compiles it to `Assets/GrayMap/colors.bin`
and records source/payload hashes. The temporary DLL is only a relocation
container used by the build tool; it is never shipped or loaded by the client.
QJS validates CRC/version/export/relocation bounds and embeds all code/data at
patch time. No runtime IAT/code changes or custom DLL are needed.

On palette changes the client generates a 512×256 BGRA atlas in memory and calls
the native texture upload interface (slot 8, seven arguments, RET 1Ch). DX9 uses
`0x56A5C0` (`CTextureDX9` vtable `0xFD7160`); DX7 uses `0x53BBA0` (vtable
`0xFD5BF0`). Hardware cache keys use their distinct DX9 +12C/+130 and DX7 +128
layouts. No signed asset is rewritten. Generation runs once per palette revision;
upload runs only for a revision, texture or hardware-handle change. The default
runtime pixels must match the accepted file atlas exactly, including row order.

The preset field reuses the native Graphics arrow bitmap at `0x1045CB4`
(`basic_interface/txtbox_btn_a.bmp`), native text rendering and the stock gray
border/blue list highlight. A bounded 182x94 native child draws the list above the field. Selection,
clicking the preset field again, or scrolling dismisses it. The RGB editor uses
a separate 350x238 child. Neither popup spans the Graphics page or forces the
bitmap alpha flag, so its background cannot erase unrelated controls. There are no `TrackPopupMenu`,
`ChooseColor`, auxiliary UI threads or nested message loops.

The in-game RGB editor offers three 256-step gradient sliders, decimal channel
values, live map preview, 16 custom swatches, Apply and Cancel. Right-click a
swatch to store the preview color. Apply persists; Cancel or clicking the active color swatch again restores
the original palette, preset and custom swatches. Palette generation/upload
runs on revision changes and frame callbacks always return to the engine.

Each mouse-down uses the original UI manager capture method (`0xA4B750`);
mouse-up releases only that exact capture (`0xA32E00` / `0xA482E0`) before any
selection or popup action. Left/right release, drag-out and destruction all
clear owned capture. No gameplay mouse flags or movement state are changed.

Graphics content scrolls through a 272px viewport, with a 152px range, side
arrows, draggable proportional thumb and wheel callbacks. Original native
children retain their X/height and ownership; only Y and visibility change.
Partially clipped controls are hidden from drawing and hit-testing, keeping
all content above the fixed footer. Gray, Grid and Hide use the Effects tab's real 34x15 CUICheckBox controls.
Construction follows stock 0x9E0F89: CUIButtonImage base 0x983C90, state vtable
0x1042C70, boolean +F8 and empty callback at +100. The native 0x9A1AC0 renderer
uses GameSettingsUI/toggle_off.bmp and toggle_on.bmp with the stock off/on/off/off
state mapping. Each control independently toggles its flag; RTTI and native
destruction are retained. Each compact switch sits in the aligned control column.
All six labels use native bold text.
Six GrayMap rows live at Y232/264/296/328/360/392,
so scrolling to the bottom reveals all settings without compressing labels.
The viewport, overlays and per-instance Graphics vtable clone are owned by
that settings page and cleaned up through its native destructor.

Row and switch cursor callbacks preserve the default native cursor path
(`0xA23470`). Native `0xA1EF70` converts child coordinates to screen coordinates;
`0xA753D0` shows copied/wrapped text using the tooltip manager at `0x121333C`.
Dismissal through `0xA753A0` requires matching manager, tooltip pointer and
timestamp, so another UI producer's replacement tooltip is preserved.

Scrolling, popup dismissal and palette UI changes call the Graphics page's
native UpdateSurface virtual (slot 38): `9AC860 -> A1EDD0 -> A23360`. This
invalidates the entire settings root and visible descendants, so the native
compositor clears its cached surface before drawing controls at new positions.
Writing only leaf +58 flags leaves old labels and dismissed popups in the
parent cache. Page teardown suppresses this traversal because sibling pages
may already be destroyed.

`tools/reproduce_graymap_scroll_ghost.py` executes matched old/new wheel,
reverse-thumb-drag and popup-dismiss events, real native root lookup and
recursive invalidation, then the native compositor's root OnDraw gate. `tools/reproduce_graymap_popup_bounds.py` compares the old
full-page alpha-forced source with the bounded menu and verifies all five text
rows fit its bitmap. The
old build skips root clearing in all three cases; the fixed build replays it.
The renderer boundary is mocked; live visual acceptance remains separate.

Atlas loading now requests `CTexMgr::Get(path,0,1,0,0)`: no global texture-size
reduction and no mipmaps. The native 0x5685A0 no-scale gate and 0x569B58 DX9
mip-level gate are covered by `verify_graymap_texture_options.py`. All tested
size divisors (1, 2, 4) retain 512x256; both auto-mip capability states request
one level. These gates are separate from the native Trilinear sampler setting.
The upload also requires the exact GrayMap cache filename, no-scale flag and
full dimensions. A scaled/shared fallback is rejected before any upload.

The persisted native Texture Resolution value was found at TEXTUREMODE=0 during
the reported map degradation. Recovery restores only that value to the earlier
working backup's 2, retaining the original file and every other option. This is
a one-time recovery; the atlas no longer depends on that setting afterward.

The Graphics scrollbar now uses the stock UIScrollBar constructor 0x836870,
vtable 0x102AEF4 and renderer 0x856560, including scroll0* native skin artwork.
The original thumb-size virtual computes 157px for a 272px/424px viewport/content
ratio; arrows are 13px and thumb travel is 89px. Existing scoped input callbacks
retain the accepted scroll range and mouse-release behavior.

Grid lines derive from Walkable +33 per channel; blocked hatch adds +2. Both
clamp at 255. The native terrain/scenery off paths remain unchanged.

## Build and verification

Use Python with `pefile`, `unicorn` and `Pillow`, the distributed
`win32/WARP_console.exe`, and x86 MSVC for regenerating the palette payload.
The build tools create isolated fixtures under the requested output directory.

Also run `tools/verify_graymap_colors.py <build>` for emitted-x86 palette/menu/dialog,
Cancel, malformed preference records, restart persistence and upload-cache checks.

```powershell
.\.venv-target-hud\Scripts\python.exe tools\build_graymap_atlas.py
.\.venv-target-hud\Scripts\python.exe tools\build_graymap_colors.py
.\.venv-target-hud\Scripts\python.exe tools\build_graymap.py --output Outputs\GrayMap-tests\basic
.\.venv-target-hud\Scripts\python.exe tools\build_graymap.py --output Outputs\GrayMap-tests\remove --lifecycle remove
.\.venv-target-hud\Scripts\python.exe tools\build_graymap.py --output Outputs\GrayMap-tests\reapply --lifecycle reapply --peers before
.\.venv-target-hud\Scripts\python.exe tools\verify_graymap.py Outputs\GrayMap-tests\basic Outputs\GrayMap-tests\remove Outputs\GrayMap-tests\reapply
```

The palette builder discovers the installed x86 MSVC toolchain through
`VCToolsInstallDir` or `vswhere`. Use `--msvc-bin <directory>` to select a
matched x86 `cl.exe`/`link.exe` pair explicitly. Its runtime container is only
a build intermediate. Rebuilding the WARP-style source-header cleanup retained
payload SHA-256 `42407250c2d1feb75b3075e1fe97b4dca9145d0644273d96fd07c9ccf2f7c3f9`.

For an existing patched client whose GrayMap hook sites are still stock:

```powershell
.\.venv-target-hud\Scripts\python.exe tools\build_existing_graymap_client.py --source "C:\path\existing-client.exe" --output Outputs\GrayMap-incremental
.\.venv-target-hud\Scripts\python.exe tools\verify_graymap.py Outputs\GrayMap-incremental
```

The incremental builder chains the existing command dispatcher, preserves all
prior section contents outside the declared hooks, preserves imports and overlay,
and repairs WARP section-header growth. It builds only; installation/signing is
a separate transaction. To upgrade a v1 deployment, use its verified pre-GrayMap
backup as the build baseline, check the live EXE still matches the v1 receipt,
and retain a separate backup of the deployed v1 files. Do not stack blind patches.

Unicorn executes the actual WARP-emitted code: 15 terrain off/on/off vectors plus
78 material/scenery/settings vectors per active build. Checks include all atlas
masks, GAT type mapping, UVs/alpha/SSE preservation, source-data immutability,
exact stock submissions after off, scoped scenery ABI, settings lifecycle and
click boundaries, command coexistence, removal/reapplication and import identity.
Projection, native allocation and GPU/UI boundaries are mocked. These tests do
not establish pixels, input hit-testing in the live client, or performance.

### Startup crash regression, 2026-10-16

The first V2 scenery hook overwrote the eight-byte span at `0x00A7B2F9`,
including `MOV EAX,[g_renderer]` at `0x00A7B2FC`. The native culling branch at
`0x00A7B2E1` independently jumps to `0x00A7B2FC`. Culled objects therefore
entered the middle of the replacement CALL operand, eventually decoded a CALL
at `0x00A7B303`, and attempted to execute `0x35B7C2FB`. This exactly matches
both the user's crash and the captured first-chance execute AV.

Corrected JMP bridges start earlier, at `0x00A7B2F4` and `0x00A7B40A`, keeping
the original renderer-load instructions and native branch targets intact. The
original draw call sees its original stack depth/alignment. Native traversal
tests now cover culled, ordinary and transparent objects with Gray/Hide on and
off. `tools/reproduce_graymap_scenery_crash.py` reproduces the exact old bad
target and verifies the corrected skip path. Subsequent live testing reached
the map successfully; broader relog/map coverage remains a separate gate.

### Black-terrain regression, 2026-10-16

The live snapshot confirmed a loaded 512×256 atlas, valid transformed vertices
and UVs in the single-texture terrain queue, plus saved lightmap option 1 and
combined-texture capability 1. The producer-local option override emitted
32-byte vertices, but the renderer still selected its combined 40-byte batch.
The atlas polygons were never drawn, leaving the black background visible.

The correction applies the same GrayMap-local override to the DX9 consumer's
option read at `0x0055D8DF` and DX7 at `0x005530AE`. Off mode delegates both
reads to the original getter; the saved graphics option is unchanged.
`tools/reproduce_graymap_render_path.py` demonstrates the old consumer mismatch
and the corrected queue selection. The expanded tests execute both native
consumer branches with saved lightmaps on/off and Gray on/off. The user later
confirmed visible grid/blocked areas and accepted the reference-style correction.

### Reference-style atlas correction, 2026-10-16

The user's comparison screenshot showed false dark cells repeated throughout
walkable floor, light squares inside blocked areas, and missing thin grid lines.
That pattern matches vertically inverted atlas sampling: the intended all-open
grid tile aliases a mixed blocked-cell variant from the opposite atlas row.
The corrected V endpoints preserve logical cell order in the native upload.

The floor now uses one uniform color and thin grid lines; blocked tiles have
no light cell borders or checker motif, so adjacent blocked cells form continuous
dark regions. `tools/verify_graymap_atlas.py` checks 128 mask/cell samples through
the profiled native V orientation, checks open-floor uniformity and dark-region
continuity, and rejects the previous binary/atlas combination. Its optional
preview is a CPU material-sampling regression, not an in-game screenshot.
The native bridge and renderer code remain byte-identical to the preceding fix.
The user subsequently accepted the corrected reference-style floor and blocked
regions, followed by the palette controls, scrolling and texture-quality fix.

## Live acceptance and release

Test the same camera position in a field, town, indoor map and uneven terrain.
Compare original → gray/grid/hidden → original screenshots; exercise each control,
map changes, relog and Alt-Tab/device reset in the supported DX7/DX9 configurations.
Check GAT alignment, dark-cell orientation, scenery restoration, actors/effects,
settings layout and frame time. Do not mark V2 Working before those checks pass.

Regenerate/sign the Riftlock manifest for the changed EXE and new loose atlas.
Verify the installed asset manifest with the unmodified native manifest generator,
verify the paired release signature, and retain rollback copies of the prior
EXE/manifest/signature plus the prior atlas state. Signing keys stay outside outputs.
