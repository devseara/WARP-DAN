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
| Always-show NPC names | Planned | Patch the native NPC nameplate visibility path first; use a bounded native balloon table only if EXTN names require it. |
| Extended names | Planned | Replace DLL maps with a bounded EXE table fed by the existing `0x0BB7` dispatcher route. |
| Player-name colors | Planned | Convert together with Extended Names; current color policy depends on EXTN state. |
| Item-name colors | Planned | Feed a bounded item-ID/color table from `0x0BDD` and patch semantic item UI draw sites. |
| Rune visual system | Planned | Translate the existing static bridge handlers to native caves and bake configuration at patch time. |
| FPS overlay | Planned | Replace the D3D proxy with a native frame counter and client text draw callback. |
| Ping overlay | Planned | Prefer application-level packet RTT; exact threaded ICMP behavior remains DLL-backed. |
| In-game PIN keypad | DLL retained | A QJS-only port requires a full map-session native RO window/control reconstruction. |
| HatEffect world occlusion | Renderer research planned | Rehost original HatEffectInfo STR resources as real `CRagEffect`/`CEffectPrim` world primitives; packet remap and bucket changes are rejected approaches. |

## Renewal inventory checklist

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
- [ ] Confirm the four selected-tab images and click regions in game.
- [ ] Confirm balloon placement at every inventory screen position and resolution.
- [ ] Confirm the Zeny/weight values update, the weight balloon appears, and the opaque reserved row contains no slots or items.
- [ ] Confirm inventory close/reopen, resize, map change, Alt+Tab, and client exit.
- [ ] Tune only the QJS constants if live positioning differs from the reference screenshots.

## HatEffect renderer gates

- [ ] Capture a stock SpecialEffect and original HatEffectInfo STR as the visual oracle pair.
- [ ] Identify the real SpecialEffect primitive resource-binding and teardown methods.
- [ ] Rehost one original STR in a genuine world primitive without the HatEffect STR renderer.
- [ ] Require true partial clipping behind opaque RSW geometry before generalizing.
- [ ] Add bounded `(GID, HatEFID)` attachment and lifecycle state.
- [ ] Preserve stock `hatEffectID` behavior and rehost only custom `resourceFileName` entries.
