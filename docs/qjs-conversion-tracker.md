# DLL to QJS Conversion Tracker

Target client: `2025-07-16_Ragexe_175220998`  
Policy: static WARP/QJS patches, no runtime `recv` hook, and no custom DLL for a
feature marked QJS-only.

Status meanings:

- `Working`: live client behavior has been confirmed.
- `Implemented, test required`: code and profile wiring are complete, but the
  generated EXE still needs a live visual/runtime pass.
- `Planned`: design exists; implementation has not started.
- `DLL retained`: a behavior-preserving QJS conversion is not currently the
  sensible implementation.

## Feature status

| Feature | Status | Current implementation / next gate |
|---|---|---|
| Dual-wield and off-hand weapon sprites | Working | QJS-only native resource-slot patch; attack animation and off-hand-only behavior confirmed by live testing. |
| Custom code page | Implemented, test required | Base codepage override is QJS-only. The optional UTF-8 character-walking bridge still uses a DLL when explicitly enabled. |
| RO Global Zero Inventory | Working | QJS-only window/tab/tooltip caves, anchored balloons, a reserved row matching ordinary/locked-Personal backgrounds, and a live comma-formatted Zeny/weight panel. Confirmed in game on the 2025-07-16 client. |
| RO Global Zero Basic Information HUD | Implemented, live AP test required | QJS-only compact `UIBasicInfoWnd` branches render a 252x74 composite with the supplied unscaled 194x50 frame, 182px-clipped HP/SP/yellow-AP fills, and an outlined bold Base Level/name matching hovered world names. AP/MAXAP reuse the client stat map populated by `AllowAPBarforAllJobs`, with an authoritative 200 fallback only when MAXAP is absent. A cloned native `UIJobIconButton` child owns the screenshot-proportioned 66x66 `big2` Job icon, clipping, z-order, lifecycle, and Job/gauge hover routing. |
| Always-show NPC names | Working | QJS-only bounded EXTN balloon renderer and static `/shownpcname`, with live-confirmed one-byte persistence in `savedata/shownpcname.dat`. |
| Extended names | Working | QJS-only EXTN ring drain feeds a bounded exact-text map. Mob details use the official `0x0ADF` Group Title/ID row above the independently rendered stock mob name. |
| Player-name colors | Working | QJS-only EXTN exact-text entries apply RGB around matching non-shadow player-name draws and restore the original GDI color afterward. |
| Item-name colors | 2025 live-confirmed; 2026 live validation pending | QJS-only `0x0BDD` ICOL drain, bounded exact item/grade table, anchored slotless/slotted Inventory grammar, conditional native post-grade endpoint gates, and a non-splitting static TextOutW bridge. A matching grade color wins the complete decorated title, grade quantities are omitted, and matched dark draws are suppressed. See the normative renderer contract; do not use split spans or cross-call grade continuation. |
| Fluent emoji | Working (NPC menus) | QJS-only manifest table and EXE-resident GDI+ draw/measure caves support `:shortcode:`, compact `@shortcode@`, and raw Unicode aliases. Compact menu icons, sizing, colors, and mixed text/icon rows are live-confirmed; no custom DLL or API detour is used. |
| Rune visual system | Planned | Translate the existing static bridge handlers to native caves and bake configuration at patch time. |
| FPS overlay | Implemented, test required | QJS-only post-Present cave counts native frames and draws at prompted X/Y coordinates through existing Win32 imports. No D3D proxy or custom DLL. |
| Ping overlay | Implemented, test required | QJS-only `0x0360/0x007F` application RTT capture feeds the shared prompted-position renderer. No ICMP, recv hook or custom DLL. |
| In-game PIN keypad | DLL retained | A QJS-only port requires a full map-session native RO window/control reconstruction. |
| HatEffect world occlusion | Working | `AllHatEffectsWorldDepthOracle.qjs` preserves the original screen-space STR renderer and apparent scale. Live-accepted v4.2 uses Ragnarok's Y-up matrix coefficients for upper-vertex depth and a bounded four-native-quantum contact tolerance. It remains scoped to HatEffects; native world `.str` NPCs retain stock behavior. |

## Fluent emoji checklist

- [x] Parse `manifest.tsv` at WARP time and bake a bounded open-addressed UTF-16 token table into the EXE.
- [x] Preserve canonical `:shortcode:` and compact NPC-menu `@shortcode@` forms, including the original fallback aliases.
- [x] Add raw Unicode manifest aliases without a runtime file parser.
- [x] Resolve the required GDI/GDI+ exports from modules already loaded by the client; add no DLL import.
- [x] Compose below the item-color wrapper and after EXTN substitution/player-color selection.
- [x] Measure segmented text and honor left, center, right, baseline, and bottom GDI alignment.
- [x] Preload each line's images before drawing so missing assets fall back to untouched stock text.
- [x] Copy all 3,145 PNG assets plus manifest/license documentation through the QJS `onApplied` callback.
- [x] Build isolated and EXTN/item/player-color integration EXEs with WARP_console.
- [x] Verify the four TextOutW/GetTextExtentPoint32W surfaces target EXE caves and the output has no BOH/custom DLL import.
- [x] Confirm compact `@shortcode@` rendering and mixed text/icon rows in NPC dialogs and menus with the item-color wrapper enabled.
- [ ] Confirm `:shortcode:` and raw-Unicode rendering in names and item text in game.
- [ ] Confirm alignment, shadow passes, missing-asset fallback, F12, resolution changes, map changes, Alt+Tab, relog, and clean exit.

## Native FPS/Ping overlay checklist

- [x] Replace the `Direct3DCreate9Ex` proxy and layered overlay DLL with a static post-`Present` cave at `0x00543441`.
- [x] Count client presentation frames in bounded EXE-owned state.
- [x] Draw transparent, shadowed ANSI text through stock `GetDC`, `TextOutA`, `SetBkMode`, and `SetTextColor` imports.
- [x] Resolve `ReleaseDC` from the already-loaded `user32.dll` without adding an import or custom DLL.
- [x] Prompt independently for FPS and ping X/Y coordinates; negative values are relative to the client right/bottom edge.
- [x] Route `/fps` and `/ping` to static client-option toggles.
- [x] Capture the stock `CZ_REQUEST_TIME2 (0x0360)` / `ZC_NOTIFY_TIME (0x007F)` RTT at `0x00C9E8F8` after the client's own subtraction.
- [x] Build `Banquet of Heroes_telemetry_qjs_test.exe` and verify both static hook targets, state coordinates, and absence of FPS/Ping DLL imports.
- [ ] Confirm FPS and `MS` values update in game at the selected coordinates.
- [ ] Confirm `/fps`, `/ping`, Game Settings, resolution changes, F12, Alt+Tab, map changes, relog, and clean exit.

## RO Global Zero Inventory checklist

- [x] Remove the inventory DLL import from `ROGlobalZeroInventory`.
- [x] Capture the live inventory window and its tab-control pointer.
- [x] Preserve the original inventory and tab draw handlers.
- [x] Draw the selected `tab_pri_01..04.bmp` state through the native texture manager.
- [x] Blank legacy text labels and align native click heights to `34/33/33/34`.
- [x] Anchor `Consumables`, `Equipment`, `Miscellaneous`, and `Personal` balloons beside each vertical tab.
- [x] Draw `uirenewal/itemui/bg_zeny.bmp` immediately before the native bottom text block.
- [x] Read live Zeny/current-weight/max-weight from the same client globals used by Basic Information.
- [x] Draw the Zeny label/value and native `inventory/icon_weight.bmp` current/max weight.
- [x] Route Zeny and both weight values through the client's bounded comma formatter.
- [x] Reserve one full item row and overpaint its native empty-slot textures without changing the window's painted row count.
- [x] Show the stock `Weight %d%%` balloon while hovering the weight row.
- [x] Disable the compiled inventory module for the next `bohcustoms.dll` rebuild.
- [x] Build an isolated inventory profile and confirm all static byte/vtable guards pass.
- [x] Confirm the isolated EXE has no BOH/custom inventory import and all four caves resolve to native client functions.
- [x] Restore the active combined-DLL filename inputs and build the complete main profile successfully.
- [x] Verify the complete EXE imports 25 `bohcustoms.dll` exports, none belonging to Inventory Tabs, with zero stale bridge operands.
- [x] Generate `Banquet of Heroes_inventory_qjs_test.exe` without overwriting the working game EXE.
- [x] Confirm the four selected-tab images and click regions in game.
- [x] Confirm balloon placement while moving the inventory and across all tested resolutions.
- [x] Confirm the Zeny/weight values update, the weight balloon appears, and the opaque reserved row contains no slots or items.
- [x] Confirm inventory close/reopen, resize, map change, Alt+Tab, and clean client exit with no crashes.
- [x] Confirm live positioning matches the reference screenshots; no QJS constant tuning required.

## RO Global Zero Basic Information HUD checklist

- [x] Confirm the compact stock window is already `220x55` and retain its dragging/input lifecycle while locking Alt+V away from the stock `220x134` renderer.
- [x] Guard `UIBasicInfoWnd::OnDraw` vtable slot 20, mouse vtable slot 28, the exact compact-branch entry bytes, and the Alt+V selector bytes for the 2025-07-16 client.
- [x] Derive the client-codepage texture prefix from an existing `basic_interface` path rather than hardcoding Korean path bytes.
- [x] Draw the transparent-parent `gze_bg_deco.bmp`, `gze_hp_normal_deco.bmp`, and `gze_sp_normal.bmp` composition through the native texture manager.
- [x] Clip the 184px HP/SP fills with the client's native source-rectangle image call and clamp zero/over-maximum values.
- [x] Read live HP/SP, Base Level, class Job ID, and the decoded character name from the same session/global state used by stock Basic Information.
- [x] Draw current/maximum values and independently right-aligned percentages through native text measure/draw functions.
- [x] Resolve the reference-sized `uirenewal/jobicon/big/icon_job_%d.bmp` from the actual class ID so mounted sprite IDs do not select missing icon files.
- [x] Register the patch in `Patches/UI.yml` and `Tables/Patch.yml` with no custom DLL import.
- [x] Build the isolated `ROGlobal Zero BasicInfo Test.exe` with `DataFolderFirst`; all QJS loader, vtable, code-byte, allocation, and PE-write gates pass.
- [x] Build the complete main profile with `ROGlobalZeroInventory` immediately before this patch and confirm the final compact hook still resolves to the new native cave.
- [x] Use the first live capture to reject the opaque `basic_bg_mini.bmp` underlay and identify the stock compact name child at `UIBasicInfoWnd+0xC0` overlapping the custom title.
- [x] Build v2 with a transparent parent, the stock name child moved off-canvas only in compact mode, and title/value font height raised to 14; expanded Alt+V still restores the stock child layout.
- [x] Use the AP-row live capture to identify the separate `0x0095DA30` compact renderer selected for AP-capable Job ID ranges; the original classic hook cannot execute on that path.
- [x] Build v3 with independent guarded caves at `0x0095E65C` (AP-class compact) and `0x0095E69E` (classic compact), returning to their distinct stack-safe epilogues while leaving both expanded renderers stock.
- [x] Trace the Alt+V transition to the guarded `0x0095F809` selector and force it to choose `UIBasicInfoWnd+0xB4` (compact height) for both current states.
- [x] Trace the stock weight-tooltip mouse method at vtable slot 28 and chain it behind a compact-only 52x52 Job-icon hover region using the stock effective-Job/name and tooltip functions.
- [x] Build v4 with the big Job icon, centered HP divider, compact Alt+V lock, and Job-name tooltip; isolated and complete-profile builds plus emitted-hook verification pass.
- [x] Use the v4 live capture to reject the centered `gze_hp_deco.bmp` triangle strip and measure the remaining icon/bar separation against the enlarged native reference.
- [x] Build v5 without the triangle strip and move the Job icon/title pair two pixels toward the HP/SP bars, including the matching hover hitbox; isolated/full-profile builds and emitted-byte verification pass.
- [x] Build v6 by moving only the Job icon and its hover hitbox four additional pixels toward the bars while preserving the native unscaled 194x36 `gze_bg.bmp` draw and all HP/SP geometry; the full EXE differs from v5 at exactly five coordinate bytes.
- [x] Reject v6 before live handoff because moving the icon over the existing gauge would hide four additional fill pixels despite preserving the source texture dimensions.
- [x] Build v7 as a 242x55 composite: 52x52 icon at x=1, unscaled 194x36 gauge at x=48, and full 184px HP/SP fills at x=53 so the gauge's 5px left frame alone overlaps the icon; isolated/full-profile builds and emitted-operand verification pass.
- [x] Use the v7 live capture to prove that assigning `UIBasicInfoWnd+0x14` inside `OnDraw` occurs after the renderer establishes its 220px clip rectangle, truncating the right-aligned percentages.
- [x] Build v8 by guarding and changing the pre-registration factory size call at `0x00A3954C` from width 220 to 242, while removing the late draw-cave width assignment; isolated/full builds confirm `0x00A3954E=242` and the layout routine continues to reuse `[UIBasicInfoWnd+0x14]`.
- [x] Trace the lower Basic Information grid to factory window ID `0x133`: the `0x00A412BF` case creates a 220x197 window, while BasicInfo factory/movement handlers position it directly below the compact HUD.
- [x] Build v9 by returning null from the guarded ID `0x133` factory case (removing both rendering and input) and move the 52x52 Job icon/tooltip hitbox to x=3 for a two-pixel overlap with the HP/SP start at x=53; isolated/full builds and emitted-jump/coordinate verification pass.
- [x] Build v10 by moving only the 52x52 Job icon and its tooltip hitbox to x=8, creating a seven-pixel underlap with the HP/SP fill at x=53 while preserving the native 194x36 gauge and full 184px live-fill geometry; v9-to-v10 isolated comparison differs at exactly five coordinate bytes.
- [x] Build v11 by moving the unchanged 194x36 gauge frame and unchanged 184px HP/SP fills nine pixels left to x=39/x=44, placing both rows beneath the icon's opaque right edge; the icon remains last in parent draw order and the level/name title follows the gauge seam.
- [x] Build v12 by changing the composite z-order rather than adding more hidden underlap: draw the dynamic 52x52 Job icon first, then draw the restored x=48/x=53 gauge and live fills over its right edge. This exposes the intended seven-pixel merged seam while retaining the native 194x36/184px geometry.
- [x] Build v13 from the live v12 visual oracle: retain the restored x=48/x=53 gauge geometry, move the icon to x=14 for a thirteen-pixel fill underlap, and draw the icon last so its shield remains above HP/SP instead of being covered by them.
- [x] Build v14 with a mask-sandwich composite instead of choosing one global z-order: cache and draw the full dynamic Job surface behind the gauge, draw the unchanged gauge/fills, then redraw only the icon's left 47 source columns in front. The icon's native transparency owns the interlock while its final five columns remain behind HP/SP.
- [x] Build v15 from the accepted v14 direction: align the 52px icon at y=0 with the 36px gauge at y=16 so both end on row 51, and restore 50 of 52 icon columns in the foreground so the Job shield owns the overlap while the last two columns retain the interlock.
- [x] Build v16 after the v15 live capture proved that restoring three additional right-edge columns recreated the separated silhouette: retain v15's exact y=0/y=16 bottom alignment, but return to v14's visually proven 47-column foreground interlock.
- [x] Build v17 from source-asset matching against the v16 live capture and reference: retain the 47-column mask sandwich and exact row-51 bottom alignment, but place the icon/tooltip at x=8 so the icon-to-gauge origin gap is the reference-normalized 40px (`48 - 8`) rather than v16's 34px.
- [x] Re-analyze the untouched full-resolution reference after v17 remained visually separated: `basic_bg_mini.bmp` proves the compact parent is 220x55, so the intrinsic 194px gauge belongs at x=26. Restore the native 220px parent, place the 52px icon at x=0, and redraw all 52 icon columns above HP/SP; this creates a 26px frame overlap without resizing either asset.
- [x] Use the rejected v18 live capture to identify the renderer mismatch instead of changing coordinates again: text can overlap because `TextDraw` rasterizes after the image pass, while two color-keyed BMP layers still replace each other pixel-by-pixel wherever the upper image is opaque.
- [x] Build v19 as the first child-control rewrite: preserve HP/SP in the compact parent, hook the then-presumed `UIBasicInfoWnd::OnCreate` slot, allocate/construct/register a real 52x52 `UIJobIconButton`, clone its 54-entry vtable per instance, retain its native deleting destructor/lifecycle, route slot 20 to a child-local dynamic Job renderer, and neutralize only the three Job-specific input overrides.
- [x] Verify both isolated and complete-profile v19 binaries at the emitted PE level: the parent renderers contain no Job-image draw, the child calls the native texture pipeline and `ImageDraw(this,0,0,...)`, `MoveTo` dispatches through `child->vtable[4]`, and `AddChild` runs after final geometry setup.
- [x] Reject v19 after the live client stops responding: static caller reconstruction proves vtable slot 15 is the recurring size/layout callback invoked by `UIWindow::SetWindowSize`, not a one-time `OnCreate`; the hook could append another Job child on every later resize/layout pass.
- [x] Build v20 by restoring `UIBasicInfoWnd` vtable slot 15 to stock and wrapping only the factory's direct `UIWindow::SetWindowSize` call at `0x00A39552`. The wrapper sizes the parent, constructs/registers exactly one child, and preserves the original `ret 8` call contract.
- [x] Use the v20 live capture to confirm stable child rendering and reject the remaining 26px-deep overlap. Match the reference's narrow seam by retaining the 52x52 icon at x=0, moving the unchanged 194x36 gauge to x=44, and widening only the parent clip to 238 so its right edge and percentages remain visible.
- [x] Move the Job-name tooltip from the parent mouse vtable into the child mouse slot 28. Parent dispatch selects the registered child first, so the old parent handler could not observe hover; the child-local handler now hit-tests 0..51 and anchors the native balloon below itself through `ClientToScreen`.
- [x] Use the rescaled v21 capture to align visible rather than nominal texture bounds: move only the native Job child from y=0 to y=1 so its last visible row meets the SP frame baseline while retaining the v21 x=44 gauge origin and 8px horizontal seam.
- [x] Use the clean v22 capture to distinguish the two-pixel decorative tip from the broad lower shield edge. Move the child to y=5 so the broad edge at source row 46 meets the gauge baseline at row 51; the narrow tip remains below the SP frame as in the reference.
- [x] Close the remaining two-pixel transparent contour seam shown by the v23 capture: move only the unchanged gauge/fills from x=44/49 to x=42/47, increasing the icon/frame overlap from 8px to 10px without resizing either asset or changing the accepted child baseline.
- [x] Apply the requested v24 visual adjustment by moving only the registered Job child two pixels down, from y=5 to y=7; retain the x=42/47 gauge/fill seam, native texture sizes, and child-owned tooltip.
- [x] Trace the two blue title dots to the `UIImgButton` children created at `0x00894DF0` and `0x00895180` from the Basic Info setup path at `0x0095E1F9`. Bypass only that creation block through `0x0095E21C`; retain parent dragging and the existing compact Alt+V selector patch.
- [x] Account for the accepted child y=7 baseline: a 52px icon ends on row 58, so the stock 55px classic parent clips its four-row decorative tip. Raise the factory, primary `+0xB4`, and saved `+0x104` compact heights together from 55 to 59 while leaving the AP-class 71px height unchanged.
- [x] Reject the v27 full-image deco experiment: x=89/y=35 placed the upward markers below the divider, and that draw path perturbed the following SP composition, including its lower white edge.
- [x] Align the native 100x5 `gze_hp_deco.bmp` through the proven explicit source-rectangle path at x=89/y=31. Its final source row now lands on divider y=35 while the HP/SP fill positions, dimensions, and textures remain unchanged. Keep the corrected 194x36 `gze_bg_deco.bmp` as a pixel-alignment oracle rather than drawing it beneath the live HP fill.
- [x] Replace the v28 oracle-only wiring with runtime precomposited layers. Load `gze_bg_deco.bmp` for the empty frame, `gze_hp_normal_deco.bmp` for the marker pixels covered by live HP, and `gze_sp_normal_frame.bmp` for the exact frame-white row covered by live SP. Remove the standalone decoration draw entirely; retain the native 194x36, 184x18, and 184x11 dimensions and the accepted coordinates.
- [x] Correct the v29 SP slot from frame-local row 24 to the native row 20. Move the unchanged 184x11 SP fill and its text from panel y=40/39 to y=36/35, restore `gze_sp_normal.bmp`, and leave frame rows 31..35—including the lower white line—owned by `gze_bg_deco.bmp`.
- [x] Confirm the v30 compact HUD placement, icon mapping, bar clipping, divider seam, lower SP line, and text alignment in game against the native reference and the user's current resolution.
- [ ] Confirm repeated Alt+V remains compact, the Job-name tooltip follows hover, dragging works, and HP/SP changes, mount/disguise transitions, map change, relog, Alt+Tab, and clean exit remain stable.
- [x] Connect the compact renderer to the existing all-Job AP stat map (`SP_AP=0xE8`, `SP_MAXAP=0xE9`) instead of duplicating packet state; when MAXAP is absent, preserve current and supply the server overlay's authoritative all-Job `BaseAp: 200` maximum without changing valid native pairs.
- [x] Adopt the supplied 194x50 `gze_bg_ap.bmp`, add the 184x11 AP fill/value/percentage row, and resize the composite to 252x74. Scale screenshot #2's attachment geometry by the 14px icon delta: frame x=56, fill x=61, title x=66, then use the live 300% comparison's final one-pixel right/up correction for the 66px icon at x=1/y=7.
- [x] Add the dedicated 184x11 yellow/gold `gze_ap_normal.bmp` fill while preserving the supplied highlight texture's native gradient.
- [x] Clip HP/SP/AP fills to the frame's measured 182px x=5..186 interior so 100% no longer overwrites the x=187..189 right cap.
- [x] Replace the unreadable title double-strike with one bold white foreground pass and an eight-neighbor one-pixel black outline matching hovered world names; numeric rows remain unchanged.
- [x] Route parent and overlapping Job-child hover regions to `Health Pool`, `Mana Pool`, and `Activity Points` through the native tooltip manager, anchored 16px right and 16px above the live mouse pointer like RO Global Zero Inventory.
- [x] Redirect the native Job child to `uirenewal/jobicon/big2/icon_job_%d.bmp` and resize it to 66x66.
- [ ] Live-confirm AP updates on a non-fourth Job, all three hover labels, the resized Job icon seam, theme switching, Alt+V, dragging, relog, and clean exit.

## Always-show NPC names checklist

- [x] Remove the four NPC overlay DLL imports and DLL filename prompts.
- [x] Preserve the original `0x00C77820` updater before the custom frame pass.
- [x] Guard `CGameMode` vtable `0x010904B8` and world-manager transitions.
- [x] Drain the dispatcher-table EXTN ring without a recv/read-path hook.
- [x] Use a bounded 256-entry GID/balloon/retry table with no runtime heap containers.
- [x] Reuse native balloon factory, actor lookup, setup/projection, and teardown methods.
- [x] Route `/shownpcname` directly to a static client-option cave.
- [x] Build the full profile with zero NPC overlay imports and zero stale bridges.
- [x] Confirm `/shownpcname` and the Game Settings toggle persist across logout and client restart.
- [x] Confirm NPC names during login, map changes, warps, and NPC spawn/despawn.
- [x] Confirm off-screen NPCs do not stack names at viewport edges.
- [x] Confirm `/font` disabled/enabled placement and all tested resolutions.
- [x] Confirm Alt+Tab, client exit, and repeated enable/disable have no crashes.

## Extended names and player-name colors checklist

- [x] Reuse the dispatcher-table `0x0BB7` EXTN ring without a recv/read-path hook.
- [x] Chain the EXTN text-map frame with the original updater and NPC-name frame.
- [x] Keep `CNameInfo` ownership untouched; the dual native ACK-name experiment was rejected after corrupting the client's name/UI object state.
- [x] Support legacy `233/237` and V3 `773/777` EXTN packet layouts.
- [x] Use a bounded exact-text map and guarded static GDI call-site bridges for names and player colors.
- [x] Reject dual ACK-name packets, direct `CNameInfo` mutation and multiline name replacement after live tests exposed corruption, crashes and one-row clipping.
- [x] Put the compact mob-info string in official `0x0ADF.title`, the element icon in `groupId`, and retain the stock mob name in `name`.
- [x] Expand the official 24-byte title through EXTN's exact short-title to long-title mapping.
- [x] Keep the original server-wide `show_mob_info` disabled; use the persisted per-character `@showmobinfo` bitmask.
- [x] Remove `ExtNameVisualInit` and `PlayerNameColorVisualInit` imports.
- [x] Disable EXTN/player-color workers and maps in the combined DLL build.
- [x] Confirm long PC, mob, NPC, portal, party, guild, position and title text in game.
- [x] Confirm player RGB colors, black shadow behavior and color reset in game.
- [x] Confirm login bursts, map changes, warps, F12, Alt+Tab and clean exit.

## Item-name colors checklist

- [x] Remove `ColoredItemNameVisualInit`, `BohTextOutW`, and `BohGetTextExtentPoint32W` imports from the patch.
- [x] Reuse the dispatcher-table `0x0BDD` ICOL block without `recv` or system-API hooks.
- [x] Parse the packet into the bounded 256-entry UTF-8 exact-name/color table used by both profiled clients.
- [x] Parse `_GRADE_<n>_<server-label>` numerically, ignore the server label, and resolve the active client label from patch state.
- [x] Chain after the EXTN/player-color TextOutW bridge regardless of profile order.
- [x] Give a matching grade color precedence over the complete decorated title; the item database is only a fallback.
- [x] Gate the two profiled native post-grade endpoint insertions only while grade coloring is active, so grade plus item reaches TextOut as one exact UTF-16 span; replay exact stock endpoint behavior in item-only mode.
- [x] Keep the TextOut bridge non-splitting and free of cross-call continuation.
- [x] Accept anchored `Name <count> ea.`, `Name: <count> ea.`, and `Name [<slots>]: <count> ea.` Inventory forms.
- [x] Omit the exact Inventory quantity tail from grade-matched titles while retaining the slot suffix.
- [x] Suppress matched dark/shadow draws and restore the HDC color after the one foreground draw.
- [x] Match exact base items after recognized decorations; `Knife` must not match `Zeny Knife`.
- [x] Disable the compiled item-color module for the next combined DLL rebuild.
- [x] Build the full profile and verify the output has no item-color/text-bridge BOH imports.
- [x] Live-confirm the reported 2025 regressions: slotless
      `Angra manyu: 1 ea.` exact color and one grade-owned Item Description
      title instead of independently colored `[Epic]` / `Knife` fragments.
- [ ] Repeat the reported Inventory, Alt+Q, and Item Description checks on the
      2026 client, including quantity omission, unknown glyphs/detached `]`,
      and matched-shadow suppression.
- [ ] Complete the remaining all-surface visual matrix for stock `D/C/B/A`,
      custom label maps, both patch orders, and distinct grade/item colors.
- [x] Confirm color-list refresh, map change, relog, F12, Alt+Tab and clean exit.

The complete non-negotiable behavior and acceptance matrix are in
[`item-grade-color-renderer-contract.md`](item-grade-color-renderer-contract.md).

2025 live acceptance was reported on 2026-07-24 for the full main-profile
artifact SHA-256
`365A40D70865D8992E34473DBBE96BECBDB917CBEAEDD4E49F83FE57A6E21686`;
the reported Item Description grade-precedence and slotless Inventory failures
were fixed. The unchecked items above remain open for the complete 2026 and
all-surface visual matrix.

## HatEffect renderer gates

- [x] Capture a stock SpecialEffect and original HatEffectInfo STR as the visual oracle pair.
- [x] Identify the real SpecialEffect primitive resource-binding and teardown methods.
- [x] Supersede STR rehosting with a HatEffect-scoped normalized-Z bridge that preserves the original compositor and apparent size.
- [x] Require true partial clipping behind opaque RSW geometry; live v4.2 passed behind-wall, contact, floor, size, and zoom gates.
- [x] Preserve native attachment and lifecycle state instead of introducing a parallel `(GID, HatEFID)` registry.
- [x] Apply the renderer correction to all HatEffects for the requested broad compatibility and test coverage.

Prototype evidence for the 2025-07-16 client:

- The rejected v1 carrier prototype changed factory dispatch `0x00AC1450` only for custom EFID `0x154D` while retaining `object+0x04 == 0x154D`. Its stock SpecialEffect `0x925` carrier (`vtable 0x0100B8B8`) used primitive allocator `0x00B1B3B0`, resource binder `0x00AD7D00`, and native teardown `0x006C52B0` / `0x00B1B4B0`.
- `0x00B1B3B0` allocates the same type-2 `CEffectPrim` used by other STR effects. Its render callback `0x00ADA590` submits through `0x00550B10`; flags `5` select queue `renderer+0x1EC`, which stock rendering brackets with `D3DRS_ZENABLE = TRUE` at `0x00553598` and disables after the queue at `0x005539F9`. Global Z-state forcing is therefore neither missing nor a valid next fix.
- The v1 carrier rehosted only HatEFID 3011's original `efst_Flutter_Butterfly\Flutter_Butterfly.str` and suppressed the carrier's unrelated Blast Forge phase only for `object+0x04 == 0x154D`.
- WARP_console loaded v1 and produced a smoke EXE; emitted cave disassembly confirmed the exact EFID guard, stock fallback, original resource path, world factory call, binder call, phase guard, and native return targets.
- The tested smoke EXE and the generated workspace artifact both hash to SHA-256 `C9327D2B1EEAB6CC88903FBD3F10B20DBC9F719A0391EFC4F31A62ABF67C92AB`. The 2026-07-14 live capture shows Flutter Butterfly remaining visible through opaque RSW geometry, which rejects the carrier-class hypothesis.
- The matching 2026-07-14 capture of untouched SpecialEffect `0x925` (`2341`, Blast Forge) shows the stock effect leaking through the same wall. The pair proves that carrier substitution cannot change occlusion because both paths use the shared STR compositor.
- The v2 oracle leaves the native HatEffect constructor `0x00AECB90`, virtual resource loader, EFID and teardown untouched. At post-bind continuation `0x00AECE35`, it writes `-0.01f` only to the EFID `0x154D` child's `CEffectPrim+0x2B4` and replays the displaced `mov ecx,0x01213338`.
- `CEffectPrim+0x2B4` is added to view depth in the STR vertex builders before conversion at `0x00554040`; the stock client uses the same `-0.01f` value at `0x00BB023F`. This is a per-primitive depth experiment, not global D3D state forcing.
- WARP_console built the isolated v2 smoke EXE successfully. Its cave at `0x0171D350` contains the exact EFID guard, `-0.01f` write and return to `0x00AECE3A`; the artifact SHA-256 is `4A6CA2927B8C507CA1CEAE2C7B4A5F415552025B17685C90FA5DA9F345D6AE63`.
- The live full-profile v2 EXE retained the older oracle filename but was rebuilt at 2026-07-14 10:40 and hashes to SHA-256 `9CF92B259250C9DC99A856A5223A5E22800DDEC009331783363752E5AE2B62E3`. Its cave at `0x019CD110` contains the same guarded `-0.01f` write at `0x019CD119`, proving the unchanged leakage is a valid depth-bias result rather than an old-binary test.
- The v2 unchanged-leak result rejects scalar `CEffectPrim` depth bias on the native flags-`0x05` path, so `CustomHatEffectOcclusion.qjs` and its profile/catalog entries were removed. That result did not test the flags-`0x0D` queue.
- The retired `CustomHatEffectAuraOracle.qjs` explored SpecialEffect `200`: factory `0x00ABC660`, class `0x00B02270`, type-0 allocator `0x00B1B430`, bitmap binder `0x00ADA4E0`, submission `0x00ADA090`, and native release `0x00B1B4B0`. A call-site census found no stock type-0 STR binder, so it could only substitute bitmap primitives and was never an STR-compatible host.
- Static registration at `0x00AC41E8` computes every Lua HatEffect runtime ID as `0x98A + HatEFID`; Flutter Butterfly is HatEFID `12`, runtime EFID `0x996`.
- The apparent ring-suppressed aura result was invalid evidence: the bridge tested stale `[EBP+8]`, while `B02CA0` is called without arguments. Consequently `B026F0` was not suppressed and the visible aura did not prove the substituted `parent+0xE4` bitmap children or custom update path.
- Correcting the selector to authoritative parent `+0x04` suppressed the ring but produced no HatEffect. Embedded-GRF mode was excluded: `mapdata.grf`, the exact `nnaa1.bmp` path, and a normal unencrypted 100x100 24-bit asset were present.
- `0x0054B9B0` builds an intermediate scale transform; native `0x00B02E60` later combines rotation and scale through `0x0054C320`. Direct final-matrix stores were therefore not justified. The corrected-layout matrix build also produced no HatEffect and the type-0 aura-host approach is rejected.
- The rejected queue oracle kept the original HatEffect class and STR lifecycle, then changed loaded primitive flags from `0x05` to `0x0D` so submission moved from `renderer+0x1EC` to `renderer+0x210`. The 2026-07-14 live capture still shows Flutter Butterfly fully visible across the same opaque wall, proving queue selection is not the missing occlusion variable. `AllHatEffectsDepthQueueOracle.qjs`, its test profile, and its catalog entry were removed.
- Level-99 SpecialEffect `200` allocates its type-0 aura primitives with flags `0x0D` at `0x00B02715`, and `0x00ADA090` projects each local vertex through `0x00554380`, converts reciprocal depth through `0x00554040`, and submits the resulting 32-byte vertices. The user's stock aura capture shows this path clipping at opaque RSW geometry.
- The HatEffect render methods at `0x00AFE380` and `0x00AFE490` call type-2 STR loop `0x00AD8750` at `0x00AFE41C` and `0x00AFE52B`. That loop dispatches layers to `0x00AD8C40`, which builds screen-space vertices and writes constant normalized `z = 0x38021CC8` at `0x00AD93C5`. This is the concrete source of the through-wall behavior.
- The native sibling loop `0x00AD86D0` has the same `thiscall` receiver, one matrix argument, layer iteration, visibility gates, and `ret 4`, but dispatches to `0x00AD87D0`. That layer builder preserves the STR texture, UV, color, blend, and animation data while calling `0x00554380` at `0x00AD8B62` and `0x00554040` at `0x00AD8B7D` for world-derived vertex depth.
- The 2026-07-14 live world-builder capture is the first true positive occlusion result: Flutter Butterfly is partially clipped by the opaque tower. It also shows every HatEffect STR enlarged severely because `0x00AD87D0` interprets screen-authored pixel quad dimensions as world units. That proves the depth hypothesis but rejects the full builder swap as a behavior-preserving implementation.
- Screen builder `0x00AD8C40` already calls `0x005541B0` at `0x00AD8D91`, which returns actor-derived reciprocal depth in `[EBP-0x64]`; each vertex receives that value at `+0x0C`. The stock path nevertheless writes constant normalized `z = 0x38021CC8` at vertex `+0x08`.
- The v2 `AllHatEffectsWorldDepthOracle.qjs` keeps `0x00AD8750` and all original screen-space X/Y/scale math. The two HatEffect-local calls enter a scoped wrapper, and a five-byte hook at `0x00AD93D4` converts the existing reciprocal depth through native `0x00554040` into vertex `+0x08`. All non-HatEffect uses of `0x00AD8C40` replay the untouched instruction path.
- Full embedded-GRF v2 executable `hateffect_all_screen_size_depth_v2_oracle_full.exe` hashes to `6FCC5112CB6FB546AF0D98B949814803BB0630AA7B0B5BAD3BA3B852F66158DB`. Its scope wrapper is at `0x0181F854`, depth bridge at `0x0181F880`, both HatEffect calls target the wrapper, the bridge calls `0x00554040`, and the custom-IAT audit reports 11 `bohcustoms.dll` imports with zero stale operands. Main profile/settings were restored after the build.
- The v2 live capture passed stock apparent size and true building occlusion, but at distant zoom lower STR layers intersected the floor. The screen builder computes `xmm3 = layerIndex * 1e-5` at `0x00AD9308` and subtracts it from reciprocal depth at `0x00AD93D9`; converting that layer-shifted value made the normalized-Z plane vary by layer instead of preserving the stock shared-Z behavior.
- V3 keeps the original `anchor - xmm3` value in vertex RHW `+0x0C`, reloads the unshifted anchor for normalized Z, adds one native `1e-5` foreground quantum from `0x00FD6AE4`, then calls `0x00554040`. Native world-effect builder `0x00ADBE7D` uses the same quantum positively in its depth-order term, so the correction is bounded to the engine's existing depth granularity rather than an arbitrary large offset.
- Isolated v3 executable `hateffect_all_screen_size_depth_v3_oracle_smoke.exe` hashes to `3B2319C25855A3005C6B1179DD51850B2F325C5718244EFD7F8EC51289750345`. Full embedded-GRF v3 executable `hateffect_all_screen_size_depth_v3_oracle_full.exe` hashes to `E5A0C10919AF6A306D104E6BE1E540B334D6934BFC5F64C8C3616864B29185BD`; its wrapper is at `0x0181F854`, depth bridge at `0x0181F880`, both calls and continuations disassemble correctly, and the audit reports 11 `bohcustoms.dll` imports with zero stale operands. Main profile/settings were restored after the build.
- The v3 live capture fixes the zoom-dependent floor loss and keeps stock size and general building occlusion. A remaining contact case appears when the actor stands immediately beside a wall: because every pixel still shares the actor anchor's Z, the wall can consume most upper HatEffect pixels even though the stock actor sprite remains visible.
- V4 keeps v3 depth for vertices at or below projected actor-anchor Y. For upper vertices it algebraically inverts the native `0x005541B0` Y projection using matrix coefficients `m7/m8`, renderer Y scale/center, anchor screen Y, and vertex screen Y. A native absolute-value/`1e-5` guard falls back to the anchor plane if the projection denominator is degenerate. The resulting reciprocal depth is converted through `0x00554040`; X/Y, RHW, texture interpolation, animation, scale, blend, and lifecycle remain stock.
- The full v4 executable `hateffect_upright_depth_v4_oracle_full.exe` (`37E0DB339C62CB287F555E92519C082BDB7E076EDB3BA92EBD63FC4154302ADF`) is rejected: it crashes on login at `0x0181F8F1` with `ECX=0`. The preceding `mov ecx,[ebp-0x38]` read a compiler local that initially mirrored the projection matrix but was reused before the vertex loop.
- V4.1 reloads the original third builder argument with `mov ecx,[ebp+0x10]`; stock `0x00AD8C63/0x00AD8C6A` proves this is the stable matrix pointer supplied to `0x005541B0`. Isolated artifact `hateffect_upright_depth_v4_1_oracle_smoke.exe` hashes to `A30CF40A41A9EC9293F837C529E6C93114BFC7835964C30C37BF768FC8E75547`. Full embedded-GRF artifact `hateffect_upright_depth_v4_1_oracle_full.exe` hashes to `2A9F52582AE694978116B3CEBB19F1020EB9C03067DA004DA8E47B8420EFA552`; its corrected `0x0181F8EE` load, fault-site dereference, native call/continuations, and XMM preservation disassemble correctly, and the audit reports 11 `bohcustoms.dll` imports with zero stale operands. Main profile/settings were restored after the build.
- The v4.1 live client no longer crashes, but near-wall over-occlusion is unchanged. The user's world `.str` NPC capture shows the same stock behavior, confirming that a genuine world STR carrier alone cannot provide sprite-like contact visibility. V4.1 also used Z-axis coefficients `m7/m8`; Ragnarok world elevation is Y, whose screen-Y/depth coefficients are `m4/m5` at matrix `+0x10/+0x14`.
- V4.2 switches the upper-vertex inverse projection to Y-up `m4/m5` and replaces the single floor epsilon with a bounded contact bias of four native `1e-5` quanta (`3.9999999e-5`). This remains tiny compared with the stock always-on-top Z and is intended to ignore only shallow contact while preserving meaningful behind-wall depth separation. Native world `.str` NPCs are not changed by this HatEffect-scoped oracle.
- Isolated v4.2 artifact `hateffect_yup_contact_depth_v4_2_oracle_smoke.exe` hashes to `C1C66360DB0092FFAAE210500855C90AFB3826059CD100D4D7EFF197506DA2C8`. Full embedded-GRF artifact `hateffect_yup_contact_depth_v4_2_oracle_full.exe` hashes to `7D055E5531DDC4B5F66D7ADF6632C7C9317E00A1ED0772EB0480EDA2A60C049A`; its full bridge disassembles the stable matrix argument, `+0x14/+0x10` coefficients, `0x3827C5AC` contact-bias data at `0x0181F854`, denominator guard, native conversion and stock continuations. The audit reports 11 `bohcustoms.dll` imports with zero stale operands, and main profile/settings were restored.
- Live acceptance passed on 2026-07-14: true partial clipping when genuinely behind geometry, stock apparent size, complete floor visibility at both zoom extremes, and no excessive upper-effect loss while touching walls, buildings, or obstacles.
