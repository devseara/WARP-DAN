# Gepard Safe Runtime Checklist

Scope: strict no-runtime-hook client builds. This means no DLL may modify EXE code, import tables, vtables, or system DLL exports after process start. Normal PE startup imports are allowed only for audited DLLs that do not patch runtime code.

## Allowed Baseline

- `AlwaysShowNpcName.qjs`
  - Static WARP-time frame bridge at `0x00C7642D` calls the original `0x00C77820` updater, then a guarded native cave.
  - Installs the dispatcher-table `0x0BB7` EXTN ring for NPC discovery, not the recv/read path.
  - QJS-only fixed state owns at most 256 `(GID, balloon, retry-frame)` entries and calls the native factory/setup/projection pipeline.
  - No NPC-name DLL import, runtime patch API, networking hook, or heap container is used.
- `InGamePincodeUI.qjs`
  - Static dispatcher-table route for `0x0BEF/PINC`.
  - Loads `boh_pincode_ui.dll` by normal startup import.
  - DLL creates its own Win32 keypad UI and calls WARP-provided packet sender stubs.
  - No `ws2_32.recv`, no runtime EXE patching, no IAT/vtable/prologue patching.
- `CustomExtName.qjs` / `CustomPlayerNameColor.qjs`
  - Static dispatcher-table route for the `0x0BB7/EXTN` ring.
  - A QJS-only frame cave drains into a bounded exact-text map; WARP-time GDI
    call-site caves expand matching names/titles and scope player RGB changes.
  - Mob information uses the stock `0x0ADF` title/groupId/name layout.
  - No `CNameInfo` mutation, text DLL, networking hook, runtime patch API, or heap map.
- `CustomColoredItemName.qjs`
  - Static dispatcher-table route for `0x0BDD/ICOL`.
  - A QJS-only bounded exact-name table, anchored slotless/slotted Inventory
    grammar, two conditional native post-grade endpoint gates, and one
    EXE-resident `TextOutW` bridge apply item colors, give matching grade
    colors precedence over complete decorated titles, omit grade-matched
    Inventory quantities, and suppress matched dark draws.
  - No text DLL, extent/alignment splitter, runtime hook, or API detour is
    used. See `docs/item-grade-color-renderer-contract.md`.
- `ROGlobalZeroInventory.qjs`
  - Adds no inventory DLL import; all handlers are emitted into EXE caves.
  - WARP-time caves replace the inventory/tab draw and mousemove vtable entries,
    reserve the final item row, and draw the Global Zero Zeny/weight footer.
  - Calls only verified native client rendering, tooltip, and number-format APIs.
- `FpsOverlay.qjs` / `PingOverlay.qjs`
  - QJS-only static cave replaces the post-`Present` store at `0x00543441` and
    draws FPS/ping text through existing Win32 IATs.
  - Independent prompted X/Y coordinates support right/bottom-relative values.
  - Ping copies the client's stock `0x0360/0x007F` RTT result at `0x00C9E8F8`.
  - No D3D proxy, custom DLL, ICMP worker, Winsock import, or recv hook.
- `CustomRuneSystem.qjs`
  - Keeps the static equipped-set guard patch.
  - Loads `boh_rune.dll` by normal startup import.
  - WARP-time call/prologue/surface bridges cover refresh, selected getter,
    draw/image/text/click/tooltip, and surface overlay entry `0x00FD5D24`.
  - Dedicated `boh_rune.dll` imports only basic loader/logging WinAPI and does
    not carry patch/trampoline/recv primitives.

## Excluded From Strict Gepard Profiles

- `RecvStrip0BB6`: touches the `ws2_32.recv` / recv-read path.
- `NoNagle`, `EnableProxy`: rewrite Winsock call flow.
- `LoadClientPlugins`, generic `CustomDLL`: arbitrary DLL loading surface.
- `IgnoreDebugger`, `SkipCheatCheck`, `DisableProtect/NoGGuard`: anti-cheat-hostile semantics.
- Dual-wield / weapon sprite patch and `boh_weapon_sprite.dll`: intentionally
  excluded because the patch is not working yet.

## Build Checklist

- [x] Use `profiles/2025-07-16 GEPARD SAFE.yml` as the starting profile.
- [x] QJS-only name, item-color, overlay, PIN, and inventory patches require
      no custom DLL. Deploy `boh_rune.dll` only when explicitly selecting
      `CustomRuneSystem`.
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
- Item-grade endpoint gates: 2025 `0x008A062A` / `0x008A082D`; 2026
  `0x008DA74A` / `0x008DA94D`.
- Inventory vtable entries: `0x0103D4B0`, `0x0102DD94`, `0x0102DDB4`.
- Telemetry post-Present bridge: `0x00543441`; application RTT capture:
  request tick `0x00C82D32`, response subtraction `0x00C9E8F2`, capture
  `0x00C9E8F8`.
- Rune call sites: `0x00CF953F`, `0x00CF9591`, `0x007E69D6`, `0x007E5C12`,
  `0x007E5E47`, `0x007E5E56`.
- Rune prologues: `0x007E1610`, `0x00A1D260`, `0x00A25A70`, `0x007E4B70`,
  `0x007E4CC0`.
- Rune surface vtable entry: `0x00FD5D24`.
