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
| Always-show NPC names | Working | QJS-only bounded EXTN balloon renderer and static `/shownpcname`, with live-confirmed one-byte persistence in `savedata/shownpcname.dat`. |
| Extended names | Working | QJS-only EXTN ring drain feeds a bounded exact-text map. Mob details use the official `0x0ADF` Group Title/ID row above the independently rendered stock mob name. |
| Player-name colors | Working | QJS-only EXTN exact-text entries apply RGB around matching non-shadow player-name draws and restore the original GDI color afterward. |
| Item-name colors | Working | QJS-only `0x0BDD` ICOL drain, bounded UTF-8 substring/grade table, static TextOutW color bridge, dark-shadow suppression and grade-label continuation; confirmed across item windows and client transitions. |
| Rune visual system | Planned | Translate the existing static bridge handlers to native caves and bake configuration at patch time. |
| FPS overlay | Implemented, test required | QJS-only post-Present cave counts native frames and draws at prompted X/Y coordinates through existing Win32 imports. No D3D proxy or custom DLL. |
| Ping overlay | Implemented, test required | QJS-only `0x0360/0x007F` application RTT capture feeds the shared prompted-position renderer. No ICMP, recv hook or custom DLL. |
| In-game PIN keypad | DLL retained | A QJS-only port requires a full map-session native RO window/control reconstruction. |
| HatEffect world occlusion | Renderer research planned | Rehost original HatEffectInfo STR resources as real `CRagEffect`/`CEffectPrim` world primitives; packet remap and bucket changes are rejected approaches. |

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
- [x] Parse the packet into a bounded 512-entry UTF-8 substring/color table (enough for the maximum 4092-byte wire packet).
- [x] Convert `_GRADE_<n>_<label>` sentinels into grade-label matches.
- [x] Chain after the EXTN/player-color TextOutW bridge regardless of profile order.
- [x] Preserve dark-shadow suppression, GDI color restoration, and adjacent grade-name continuation.
- [x] Disable the compiled item-color module for the next combined DLL rebuild.
- [x] Build the full profile and verify the output has no item-color/text-bridge BOH imports.
- [x] Confirm normal item-name colors in inventory, equipment, storage, cart and shop lists.
- [x] Confirm grade labels and split/wrapped grade-name continuation in Alt+Q and hover balloons.
- [x] Confirm item-detail description/title text is not incorrectly recolored.
- [x] Confirm color-list refresh, map change, relog, F12, Alt+Tab and clean exit.

## HatEffect renderer gates

- [ ] Capture a stock SpecialEffect and original HatEffectInfo STR as the visual oracle pair.
- [ ] Identify the real SpecialEffect primitive resource-binding and teardown methods.
- [ ] Rehost one original STR in a genuine world primitive without the HatEffect STR renderer.
- [ ] Require true partial clipping behind opaque RSW geometry before generalizing.
- [ ] Add bounded `(GID, HatEFID)` attachment and lifecycle state.
- [ ] Preserve stock `hatEffectID` behavior and rehost only custom `resourceFileName` entries.
