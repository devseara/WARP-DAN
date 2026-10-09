# Gepard Custom DLL Static Conversion Plan

Scope: custom DLL backed features that still work today but violate the stricter
Gepard rule because the DLL writes code, IAT entries, vtables, or system exports
after process start. Weapon sprite work is intentionally excluded.

Rule of thumb for every conversion:

- Keep the current working behavior as the oracle.
- Move hook installation from DLL runtime into WARP patch time.
- Let DLLs expose passive exports that are called by EXE caves or wrapper imports.
- DLLs may read client state, call original EXE functions by rebased VA, own
  windows/threads/resources, and call real Win32/D3D APIs.
- DLLs must not call `VirtualProtect` to modify executable/import/vtable memory,
  allocate trampoline gateways, restore stolen bytes, or hook `ws2_32.recv`.

## Current Status

| Feature | DLL | Current problem | Conversion status |
|---|---|---|---|
| AlwaysShowNpcName | None | Former DLL frame renderer | Converted again: bounded QJS-only EXTN table and native balloon frame cave at `0x00C7642D` |
| InGamePincodeUI | `boh_pincode_ui.dll` | None | Already strict-safe |
| CustomExtName / CustomPlayerNameColor | None | Former DLL maps and global GDI text matching | Converted: bounded EXTN exact-text map plus WARP-time GDI call-site caves; mob title/name rows stay stock-owned |
| CustomColoredItemName | None | Former passive GDI wrappers | Converted: QJS-only bounded ICOL legacy-name table plus ICL2 ItemId table, anchored slotless/slotted Inventory grammar, conditional native post-grade endpoint gates, and one EXE-resident title bridge. Producer hooks prefer ItemId where CItem is available. Grade color wins a complete decorated title, grade-matched Inventory quantities are omitted, and matched dark draws are suppressed. See the normative renderer contract. |
| FpsOverlay / PingOverlay | None | Former D3D proxy, layered window and ICMP worker | Converted again: QJS-only post-Present renderer plus stock application-packet RTT capture |
| ROGlobalZeroInventory | None | Former DLL-owned draw/input handlers | Converted again: pure-QJS native caves, renewal tooltips, and Zeny underlay |
| CustomRuneSystem visuals | None | Former DLL handlers behind WARP-time call/prologue/surface bridges | Converted again: QJS-only native caves; OnDraw call-site row shifts replace the global DrawBitmap/TextOut prologues and CDCBitmap vtable slot |

### Final extended-name findings (2026-07-13)

- Keep official name packets stock-sized and send exactly one ACK-name packet
  per entity. Sending both `0x0A30` and `0x0ADF` for one mob corrupts the
  client's name/UI state and eventually crashes its object-list traversal.
- Do not write Ragexe's internal `CNameInfo` strings from the frame cave. Their
  ownership and update lifetime are not stable at that point in this build.
- The mob name render target is effectively single-line. Embedded newlines and
  additional `TextOutW` rows are clipped even when their extents are measured.
- The supported two-row mob layout is the stock `0x0ADF` structure:
  `groupId` selects the element icon, `title` owns the compact information row,
  and `name` owns the mob-name row.
- `title` is limited to `NAME_LENGTH`. The EXTN exact-text map therefore keys
  on the same truncated title and substitutes the 128-byte long title only at
  the static GDI call sites.
- Keep `conf/battle/monster.conf:show_mob_info` at `0`; the persisted
  per-character `@showmobinfo` bitmask controls ID, HP, percentage, level,
  element/element level, and race.
- Live validation passed long entity fields, player RGB/shadow/reset behavior,
  initial-login bursts, map changes, warps, F12, Alt+Tab, and clean exit.

## Text DLL: Item Colors + Extended Names (historical)

Superseded: item colors and extended names now use QJS-only EXE-resident
tables and text bridges. The design below is retained only as conversion
history and is non-normative. Do not restore its DLL wrappers, split spans,
substring matching, continuation state, or shadow behavior. Current item and
grade behavior is defined exclusively by
`docs/item-grade-color-renderer-contract.md`.

Working behavior:

- Transport is already on dispatcher-table routes:
  - `0x0BB7 -> EXTN` ring.
  - `0x0BDD -> ICOL` single-slot block; legacy ItemName records may be
    followed by an `ICL2` ItemId/numeric-grade trailer.
- Runtime risk is in `item_color/colored_itemname.cpp`:
  - `InstallTextOutHook`, `InstallExtTextOutHook`, `InstallDrawTextHook`,
    `InstallDrawTextExHook`, `InstallGetTextExtentHook`.
  - Historical `recv` fallback and trampoline builder.

Capstone/import findings for `2025-07-16`:

| API | IAT | Direct call sites | Import thunk |
|---|---:|---|---:|
| `TextOutW` | `0x00FC10DC` | `0x005476C7` | `0x00DBA690` |
| `GetTextExtentPoint32W` | `0x00FC112C` | `0x0054758D` | `0x00DBA66C` |
| `TextOutA` | `0x00FC10D8` | `0x00556B41`, `0x00556C64` | `0x00DBA696` |

`ExtTextOutW`, `DrawTextW`, and `DrawTextExW` are not imported by this client.
Keep their current logic available internally only if live testing proves another
module loads them dynamically, but do not hook system exports.

Fix design:

- Add passive exports to `boh_text.dll`:
  - `BohTextOutW`
  - `BohGetTextExtentPoint32W`
  - Optional `BohTextOutA` for the two ANSI sites.
- WARP patch imports those exports and rewrites the direct call operands and/or
  import thunks above to call the BOH wrappers.
- The wrappers call the real GDI APIs through normal `GetProcAddress` resolved
  function pointers. They do not patch GDI.
- Compile out or delete the runtime `recv` fallback for strict builds. Packet
  data must come only from dispatcher shared blocks.

Implementation checklist:

- [x] Split text hook functions into wrapper exports with the same signatures as
      the target GDI APIs.
- [x] Replace `g_orig*` trampoline calls with real GDI function pointers.
- [x] Add `CustomTextRenderStatic.qjs` or update `CustomExtName` /
      `CustomColoredItemName` to install static wrappers.
- [x] Patch `0x005476C7` and `0x0054758D` first; add thunk patches if testing
      shows thunk callers.
- [x] Remove strict-build access to `PacketSource=recv`, `HookRecv`, and
      `BuildTrampolineFor`.
- [x] Live-test extended names, player colors, NPC forwarding, F12 reload,
      login/map transitions, Alt+Tab and clean exit. Item-color validation remains separate.

## FPS/Ping DLL

Superseded on 2026-07-13: `FpsOverlay.qjs` and `PingOverlay.qjs` no longer
import `boh_fps.dll`. The original COM proxy design below is retained only as
historical context.

Current QJS-only design:

- `0x0054343E` is the stock `IDirect3DDevice9::Present` call and
  `0x00543441` is the guarded six-byte post-call store replaced at WARP time.
- The shared cave replays `mov [esi+0x68c],eax`, counts frames with the stock
  `GetTickCount` IAT, obtains the client HWND from the renderer object, and
  draws transparent shadowed text after `Present` through existing GDI/User32
  imports.
- `ReleaseDC` is resolved once with the existing `GetModuleHandleA` and
  `GetProcAddress` imports. No PE import or DLL is added.
- FPS and ping have separate `D_VecI16` X/Y prompts. Negative X/Y values use
  client width/height, matching `MoveShopIcon` semantics.
- The 2025-07-16 client saves its `CZ_REQUEST_TIME2 (0x0360)` send tick at
  `0x00C82D32` / `CGameMode+0x274`. Its stock `0x007F` handler calculates
  `GetTickCount() - savedTick` at `0x00C9E8F2`; the ping cave copies that EAX
  value at `0x00C9E8F8`. No Winsock or recv surface is touched.

Current validation:

- [x] QJS syntax, CRLF and no-BOM checks.
- [x] WARP console build with independent saved FPS/Ping coordinates.
- [x] Static disassembly confirms both caves and original-instruction replay.
- [x] Output imports no BOH/FPS/Ping DLL export.
- [ ] Live-test position, toggles, RTT updates, resize, Alt+Tab and exit.

Current problem:

- `fps_ping_overlay.cpp` runtime-patches:
  - EXE IAT entry for `Direct3DCreate9Ex`.
  - `IDirect3D9::CreateDeviceEx` vtable slot `20`.
  - `IDirect3DDevice9` vtable slots `EndScene=42`, `Reset=16`,
    `DrawPrimitiveUP=83`.

Static findings:

| Surface | Address |
|---|---:|
| `Direct3DCreate9Ex` IAT | `0x00FC1C1C` |
| Import thunk | `0x00DBD97D` |
| Call sites to thunk | `0x00542C3A`, `0x0056478A`, `0x00564D0A` |

Recommended fix design:

- Do not statically patch D3D COM vtables. Return proxy COM objects instead.
- WARP imports `BohDirect3DCreate9Ex` and patches the three call sites, or the
  thunk, to call that export.
- `BohDirect3DCreate9Ex` calls the real `Direct3DCreate9Ex`, wraps the returned
  `IDirect3D9Ex`, and intercepts `CreateDeviceEx`.
- The wrapped device intercepts `EndScene`, `Reset`, and optionally
  `DrawPrimitiveUP` through normal COM method dispatch, not vtable mutation.
- The overlay thread/layered window and ICMP ping code can stay. ICMP uses
  `IcmpSendEcho`, not `ws2_32.recv`.

Implementation checklist:

- [x] Add minimal COM wrappers for `IDirect3D9Ex` and `IDirect3DDevice9Ex`.
- [x] Preserve reference counting and `QueryInterface` correctly.
- [x] Move current `HookEndScene` / `HookReset` bodies into wrapper methods.
- [x] Remove `PatchIAT`, `VirtualProtect` vtable writes, and restore logic from the strict path.
- [x] Add WARP static D3D wrapper patch using the addresses above.
- [ ] Live-test `/fps`, `/ping`, Alt+Tab, device reset, resolution change, and exit.

Fallback option:

- A static frame bridge plus layered window can show FPS/frame-ms without D3D
  wrapping, but it loses exact EndScene timing and reset awareness. Prefer COM
  proxy if keeping current behavior matters.

## Inventory Tabs DLL

Superseded on 2026-07-12: `ROGlobalZeroInventory.qjs` now owns the inventory
window capture, tab draw, mousemove tooltip, and Zeny-underlay handlers directly
as static native caves. It does not import `InventoryTabsInit` or any inventory
DLL exports. The address inventory and calling-convention notes below remain the
reverse-engineering basis for the QJS implementation.

Current problem:

- Runtime `.rdata` vtable entry swaps:
  - Inventory window draw slot.
  - Tab control draw slot.
  - Tab control mousemove slot.

Static findings:

| Slot | Vtable entry | Original target |
|---|---:|---:|
| Inventory window `vtable[20]` | `0x0103D4B0` | `0x00946DA0` |
| Tab control `vtable[20]` | `0x0102DD94` | `0x00857910` |
| Tab control `vtable[28]` | `0x0102DDB4` | `0x0085A170` |

Fix design:

- WARP imports new passive exports:
  - `InventoryTabsWindowDraw`
  - `InventoryTabsTabDraw`
  - `InventoryTabsTabMouseMove`
- WARP allocates one EXE cave per vtable entry and writes the cave VA into the
  vtable entry on disk.
- Each cave preserves the original thiscall ABI and calls the matching DLL
  export.
- The DLL export calls the original EXE target by hardcoded/rebased VA instead
  of using `g_orig_*` captured from runtime vtable entries.
- `InventoryTabsInit` should only load config/build format; no install thread.

Implementation checklist:

- [x] Refactor hook bodies to exported passive functions.
- [x] Replace `g_orig_wnd_draw`, `g_orig_tab_draw`, and `g_orig_mousemove` with
      original VAs from the table above.
- [x] Replace the former static bridge loader with `ROGlobalZeroInventory` native caves.
- [x] Verify vtable entries before writing, then write cave VAs.
- [ ] Live-test tab image overlay, click regions, tooltips, on-parent mode, and exit.

## Rune Visual DLL

Original DLL problem (historical):

- Runtime direct call patches:
  - `0x00CF953F`, `0x00CF9591` -> `rune_refresh_hook`.
  - `0x007E69D6`, `0x007E5C12`, `0x007E5E47`, `0x007E5E56` ->
    `selected_equipped_getter_hook`.
- Runtime prologue JMP hooks:
  - `0x007E1610` equip pane draw, steal 5.
  - `0x00A1D260` image draw, steal 7.
  - `0x00A25A70` text draw, steal 5.
  - `0x007E4B70` equip pane click, steal 6.
  - `0x007E4CC0` equip pane tooltip, steal 6.
- Runtime surface vtable mutation inside `hook_surface_overlay`.

Capstone sanity:

- Refresh sites are direct `E8` calls to `0x00730B40`.
- Selected-equipped getter sites are direct `E8` calls to `0x0072F140`.
- Prologue hook byte counts match the existing DLL comments/code.

Superseded design (2026-06): WARP-time call/prologue/surface bridges into
passive `boh_rune.dll` exports through its IAT.

Current QJS-only design (2026-10-09, `CustomRuneSystem.qjs`; the DLL source
was removed and `BOH_RUNE_VISUAL` is retired):

- No DLL import, IAT bridge, or `StaticPatchRefresh` hook. All handlers are
  EXE caves with a state block (0x60 header + 255 x 12-byte cache entries) in
  the WARP diff section (`.xdiff`, RWX).
- The cache follows the BanquetOfHeroes map-server multi-set sync
  (`doc/rune_tablet.txt` 6.): `0x0bd7 <0> <cat> <0>` drops every cached set of
  a tag and compacts, `0x0bd7 <0> <cat> <id>` appends or updates by set
  object. Set objects are built from the lubs and updated in place by the list
  packets (`0x00730CF0`), so the pointers stay valid.
- `$runeVisibleRows` (1-4, default 3) rows are drawn from a scroll position;
  OnWheel (`+0x8C`, entry `0x010231B8`, stock stub `0x005A8AF0`) moves it one
  row, clamped, and invalidates the pane. UIWindowMgr sends hover and wheel to
  the same window (`0x00A46B41`, `0x00A46B66`).
- Unequip: `0x007E67EA` returns the hovered row when the pane sent message
  `0x158`, otherwise the set of a `UIRuneSet_Info` sender (vtable `0x010239AC`,
  `+0x7C`; it owns the Equip/Unequip buttons and forwards their clicks); `0x007E685F` (10 bytes,
  `E8 rel32` + 5 NOPs) stores the set ID and ORs `0x8000` into the category, so
  the server removes only that set.
- Button state: `0x007E5C12/5E47/5E56` (ESI = `UIRuneSet_Info`) return its set while it is
  cached, else 0, so the button shows Unequip exactly for an equipped selection.
- RTTI ownership: `0x007E1610`/`0x007E4CC0` are `UIEquipRuneSetWnd` OnDraw
  (`+0x50`) and OnMouseHover (`+0x70`) in vtable `0x0102312C`. `0x007E4B70`
  is `UIRuneSystem_tagListWnd +0x64` (vtable `0x01023204`), not an equip-pane
  click. `0x00FD5CE4` is the shared `CDCBitmap` vtable. Each hooked handler
  has exactly one reference, its vtable entry, so the caves patch
  `0x0102317C`, `0x0102319C`, and `0x01023268` instead of stealing prologues.
- All row geometry OnDraw emits goes through nine direct sites: DrawBitmap
  `0x007E1673/169B/1723/18E8`, TextOut `0x007E17D5/17FA/1878/189D`, and the
  locked-rune `CDCBitmap +0x40` call at `0x007E1757` (rewritten
  `56 E8 rel32`). Row Y shifts happen there, so the global `0x00A1D260` and
  `0x00A25A70` prologues and `0x00FD5D24` stay stock for every other UI.
  The hover gets a row-local Y, so its two tooltip placements
  (`0x00A1EF70` LocalToScreen at `0x007E4D17`/`0x007E4E00`) add the hovered
  row's offset back for the stacked pane.
- Layout capture is reset per pane instance; children are re-read from
  `UIRuneSystemWnd +0xC8..+0xD4` and moved only when they match the captured
  pointer and have drifted from stock Y + extra.

Implementation checklist:

- [x] Keep the existing equip guard patch; it is already WARP-time static.
- [x] Port refresh cache, getter, draw stacking, layout, and hover/tag-list
      routing to native caves; verify every original byte before writing.
- [x] WARP_console build: only the intended `.text`/`.rdata` sites change and
      no import is added, standalone and with the main profile.
- [x] Unicorn emulation of every cave through the patched EXE's own call sites
      and vtable entries (`tools/test_custom_rune_system.py`, 11 tests; 1, 3 and
      4 rows, standalone and with the main profile).
- [ ] Live-test rune equip, multiple active sets, draw stacking, wheel
      scrolling, hover/click routing, Equip/Unequip button, pane and button
      unequip, relog, and exit.

## Generic CustomDLL / Plugin Loading

`CustomDLL.applySpec` is a static PE import-table rewrite and can be acceptable
when every imported DLL is audited. The generic `CustomDLL` patch and
`LoadClientPlugins` remain unsuitable for strict profiles because they create an
arbitrary DLL loading surface. Strict profiles should use only dedicated patches
with fixed export lists.

## Conversion Order

1. Text DLL static GDI wrappers. Done and file-verified.
2. Inventory tabs static vtable caves. Done and file-verified.
3. FPS/Ping D3D COM proxy. Done and file-verified; live D3D reset smoke remains.
4. Rune visuals. Converted to QJS-only native caves and file/emulation
   verified; live multi-set acceptance remains.

The strict profile is `profiles/2025-07-16 GEPARD SAFE.yml`. It intentionally
does not include the dual-wield / weapon sprite patch.
