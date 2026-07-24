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
| CustomColoredItemName | None | Former passive GDI wrappers | Converted: QJS-only bounded exact ICOL table, anchored slotless/slotted Inventory grammar, conditional native post-grade endpoint gates, and one EXE-resident title bridge. Grade color wins a complete decorated title, grade-matched Inventory quantities are omitted, and matched dark draws are suppressed. See the normative renderer contract. |
| FpsOverlay / PingOverlay | None | Former D3D proxy, layered window and ICMP worker | Converted again: QJS-only post-Present renderer plus stock application-packet RTT capture |
| ROGlobalZeroInventory | None | Former DLL-owned draw/input handlers | Converted again: pure-QJS native caves, renewal tooltips, and Zeny underlay |
| CustomRuneSystem visuals | `boh_rune.dll` | Runtime call/JMP patches and dynamic surface vtable swap | Converted: WARP-time call/prologue/surface bridges |

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
  - `0x0BDD -> ICOL` single-slot block.
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

Current problem:

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

Fix design:

- WARP owns all call/JMP patching and builds static trampolines/caves in the EXE.
- DLL exports passive handlers:
  - `RuneRefreshHook`
  - `RuneSelectedEquippedGetter`
  - `RuneEquipPaneDrawBridge`
  - `RuneImageDrawBridge`
  - `RuneTextDrawBridge`
  - `RuneEquipPaneClickBridge`
  - `RuneEquipPaneTooltipBridge`
  - `RuneSurfaceOverlayDraw`
- For call replacements, the EXE cave can call the DLL export directly. The DLL
  may call the original helper by rebased VA.
- For prologue hooks, the WARP cave must provide the original-byte trampoline
  equivalent statically, then call the DLL export with enough context to choose
  before/original/after behavior.

Surface overlay resolution:

- `CreateSurfaceObject` calls constructor `0x0053C6A0`.
- The constructor assigns the final surface vtable `0x00FD5CE4`.
- The overlay draw slot is `0x00FD5D24`, with original target `0x0053F560`.
- WARP writes a static `FF 25 [RuneSurfaceOverlayDraw IAT]` cave VA into that
  vtable entry on disk. The DLL no longer mutates surface vtables at runtime.

Implementation checklist:

- [x] Implement WARP static call bridges for refresh and selected getter sites.
- [x] Implement static prologue trampoline builder for the five prologue hooks.
- [x] Refactor DLL hook functions to consume explicit original/trampoline entry
      points from EXE caves.
- [x] Resolve and remove the dynamic surface vtable mutation.
- [x] Keep the existing equip guard patch; it is already WARP-time static.
- [ ] Live-test rune equip, multiple active sets, draw stacking, click routing,
      tooltip routing, refresh, and exit.

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
4. Rune static bridges. Done and file-verified, including the static surface
   overlay vtable entry.

The strict profile is `profiles/2025-07-16 GEPARD SAFE.yml`. It intentionally
does not include the dual-wield / weapon sprite patch.
