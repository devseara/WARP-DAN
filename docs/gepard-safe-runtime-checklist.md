# Gepard Safe Runtime Checklist

Scope: strict no-runtime-hook client builds. This means no DLL may modify EXE code, import tables, vtables, or system DLL exports after process start. Normal PE startup imports are allowed only for audited DLLs that do not patch runtime code.

## Allowed Baseline

- `AlwaysShowNpcName.qjs`
  - Static WARP-time frame bridge at `0x00C7642D` calls the original `0x00C77820` updater, then calls `NpcNameOverlayFrame(gameMode)` through the imported DLL IAT.
  - Installs the dispatcher-table `0x0BB7` EXTN ring for NPC discovery, not the recv/read path.
  - Loads `boh_npc_names.dll` by normal startup import.
  - DLL drains the EXTN ring and renders native game balloons when called by the bridge.
  - No DLL-side `VirtualProtect`, trampoline install, EXE code writes, IAT/vtable patching, or `ws2_32.recv`.
- `InGamePincodeUI.qjs`
  - Static dispatcher-table route for `0x0BEF/PINC`.
  - Loads `boh_pincode_ui.dll` by normal startup import.
  - DLL creates its own Win32 keypad UI and calls WARP-provided packet sender stubs.
  - No `ws2_32.recv`, no runtime EXE patching, no IAT/vtable/prologue patching.
- `CustomExtName.qjs` / `CustomColoredItemName.qjs`
  - Static dispatcher-table routes for `0x0BB7/EXTN` and `0x0BDD/ICOL`.
  - Loads `boh_text.dll` by normal startup import.
  - WARP-time bridges redirect the known `TextOutW` and
    `GetTextExtentPoint32W` call/thunk surfaces to passive DLL exports.
  - Strict text DLL has no `VirtualAlloc`, `FlushInstructionCache`,
    `ws2_32`, `recv`, `HookRecv`, or `InstallRecvHook` binary tokens.
- `ROGlobalZeroInventory.qjs`
  - Adds no inventory DLL import; all handlers are emitted into EXE caves.
  - WARP-time caves replace the inventory/tab draw and mousemove vtable entries,
    reserve the final item row, and draw the Global Zero Zeny/weight footer.
  - Calls only verified native client rendering, tooltip, and number-format APIs.
- `FpsOverlay.qjs` / `PingOverlay.qjs`
  - Loads `boh_fps.dll` by normal startup import.
  - WARP-time bridge patches the `Direct3DCreate9Ex` thunk at `0x00DBD97D`.
  - DLL wraps returned D3D COM objects instead of patching IAT/vtables.
  - `boh_fps.dll` may import Winsock resolver helpers for ping, but does not
    import or hook `recv`.
- `CustomRuneSystem.qjs`
  - Keeps the static equipped-set guard patch.
  - Loads `boh_rune.dll` by normal startup import.
  - WARP-time call/prologue/surface bridges cover refresh, selected getter,
    draw/image/text/click/tooltip, and surface overlay entry `0x00FD5D24`.
  - Dedicated `boh_rune.dll` imports only basic loader/logging WinAPI and does
    not carry patch/trampoline/recv primitives.

## Excluded From Strict Gepard Profiles

- `RecvStrip0BB6`: touches the `ws2_32.recv` / recv-read path.
- `CustomExtNameVisualDLL`: historical/debug-only visual DLL path.
- `NoNagle`, `EnableProxy`: rewrite Winsock call flow.
- `LoadClientPlugins`, generic `CustomDLL`: arbitrary DLL loading surface.
- `IgnoreDebugger`, `SkipCheatCheck`, `DisableProtect/NoGGuard`: anti-cheat-hostile semantics.
- Dual-wield / weapon sprite patch and `boh_weapon_sprite.dll`: intentionally
  excluded because the patch is not working yet.

## Build Checklist

- [x] Use `profiles/2025-07-16 GEPARD SAFE.yml` as the starting profile.
- [x] Build/deploy dedicated DLLs beside the patched EXE:
      `boh_npc_names.dll`, `boh_pincode_ui.dll`, `boh_text.dll`,
      `boh_inventory_tabs.dll`, `boh_fps.dll`, and `boh_rune.dll`.
- [x] Do not use `boh.dll` / `bohcustoms.dll` for Gepard unless a separate
      combined build is audited with all runtime-hook features disabled.
- [x] Keep the dual-wield / weapon sprite patch out of strict profiles.
- [x] Run `tools/gepard_safe_audit.ps1` before packaging.
- [ ] Seal custom combined DLL builds with `CustomDLL/seal_dll.py` and keep the
      generated SHA-256 manifest with the release artifacts.
- [ ] Live-smoke UI behavior in client: item/ext names, inventory tabs,
      `/fps`, `/ping`, rune stacking, NPC names, PIN UI.
- [ ] Send the final patch list, DLL list, static patch surfaces, and sealed DLL
      SHA-256 manifest to the Gepard owner for whitelist review.

## Required Runtime Properties

- No runtime hook trampoline installation in enabled DLLs.
- No writes to EXE `.text`, `.rdata`, import thunks, or Direct3D/system DLL vtables.
- No `ws2_32.recv` hook, no recv cache rewrite, no socket-buffer stripping.
- No arbitrary plugin folder loading.
- No debugger/protection bypass patches in production profiles.

## Static Surfaces To Disclose

- NPC frame call bridge: `0x00C7642D`.
- Dispatcher table: `0x00CAA2E0`, including EXTN `0x0BB7`, ICOL `0x0BDD`,
  PINC `0x0BEF`.
- Text wrappers: `0x005476C7`, `0x0054758D`, `0x00DBA690`, `0x00DBA66C`.
- Inventory vtable entries: `0x0103D4B0`, `0x0102DD94`, `0x0102DDB4`.
- D3D thunk: `0x00DBD97D`; call sites remain `0x00542C3A`, `0x0056478A`,
  `0x00564D0A`.
- Rune call sites: `0x00CF953F`, `0x00CF9591`, `0x007E69D6`, `0x007E5C12`,
  `0x007E5E47`, `0x007E5E56`.
- Rune prologues: `0x007E1610`, `0x00A1D260`, `0x00A25A70`, `0x007E4B70`,
  `0x007E4CC0`.
- Rune surface vtable entry: `0x00FD5D24`.
