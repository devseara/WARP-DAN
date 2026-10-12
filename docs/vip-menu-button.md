# VIP main-menu button and crown logo

The 2025-07-16 client now has a VIP crown button immediately after Bestiary in
ROGlobalZeroMenu. Select `VipUI` together with the existing menu/theme patches.
The Settings gear retains its Settings NPC route. VIP can be hidden through
HideNewButtons and restored through ShowNewButtons.

The complete native BMP family is in `Assets/VipUI/menuicon/`. The supplied
booking samples define six 45x41 names, exported as `bt_vip.bmp`,
`bt_vip_disabled.bmp`, `bt_vip_mouseon.bmp`, `bt_vip_new.bmp`,
`bt_vip_new_press.bmp` and `bt_vip_normal.bmp`. They match the sample BMP headers,
24-bit format, magenta transparency, resolution and padding. The base/disabled
aliases retain the normal design, matching the identical supplied samples;
VIP hover retains its highlight. The two new-state assets carry the red N badge,
with a cyan outline on new_press. These are asset variants; no new-notification
behavior is added to VIP. The existing `bt_vip_pressed.bmp` and three
32x34 Classic states remain available for the current menu callbacks. The full
12-file pack also includes `bt_vip_press.bmp` (identical to `bt_vip_pressed.bmp`)
and `bt_vip_old_disabled.bmp` (identical to `bt_vip_old_normal.bmp`). The asset
builder, manifest and patch installer include all 12 BMPs. The source PNG and
exact built-in imagegen prompts are in its `source/` directory. The original
booking samples remain unchanged and are retained under `source/samples/` for
reproducible export. Existing custom
artwork is preserved: the patch installer copies only missing files beside the
client selected as WARP's output under
`data/texture/<UI prefix>/uirenewal/menuicon/`. Applying VipUI runs the
installer automatically and creates the directory if needed. ROGlobalZeroMenu
loads both Renewal and Classic VIP icons from that same directory. The VIP
window's PNG artwork remains in `data/texture/<UI prefix>/vipui/`.

Earlier VIP packages placed menu BMPs under `vipui/menuicon/`. Revision 3
corrects both installation and runtime paths. After updating WARP source,
restart WARP, load the original client/profile, select VipUI and export a fresh
candidate. Existing files in the older directory can remain in place.

The menu supports seven rows when all 25 native buttons, six custom buttons
(including optional Battle Pass) and MENU are visible. Two new seventh-row backgrounds are supplied in
`Assets/ROGlobalZeroMenu/menuicon/` and installed by VipUI. The native child uses
ID 0x3FE, separate from the VIP main and quest windows (0x3FC/0x3FD).

## Matching server change

The launcher sends the existing 24-byte VIPU v4 request on 0x0BFA with action 13
and zero token/price fields. The server checks readiness, action locks, death
and rate limiting, then invokes `VIP Manager::OnUIOpen`. Only this opening
action is tokenless; existing purchases and other actions retain server-issued
token checks. Closing uses the existing VIP native close implementation.

Rebuild the matching Ragnarok `src/map/vip.cpp`, `vip_ui.hpp` and `clif.cpp`
changes. No wire structure, native VIP payload, Battle Pass or Gacha module
changes are needed. Load the original supported client in WARP and export a
separately named candidate using the existing profile with VipUI enabled.
Applying this update to an already patched EXE is not supported.

## Client verification on 2026-10-08

The complete-12 installer, exact hashes against the supplied ZIP, native VIP
payload verifier, 192-placement emitted-menu check, Windows WARP baseline export
and VIP hover/toggle harness passed. Fresh/repeated installation, custom-art
preservation, missing asset repair, texture paths and copy failures are covered.

The combined Battle Pass follow-up also passed the Windows WARP lifecycle and
visibility matrix, both Battle Pass/Gacha selection orders, standalone Battle
Pass and the combined Battle Pass/Gacha/VIP native regression suites. Its native
menu checks cover 384 placements, seven-row sizing and callback lifecycle.

The preservation manifests and accepted tags are unchanged. Current upstream
BattlepassUI and GachaUI already differ from the September baseline; this update
adds the Battle Pass menu route and asset callbacks without changing Gacha.
These offline checks do not establish live in-game visual acceptance. Installed
clients and servers were not replaced or restarted.

Portable client checks, from the WARP root:

```text
node tools/test_vip_asset_install.js <temporary-assets-report.json>
python tools/verify_vip_payload.py
node tools/tests/vip_menu_emit.cjs <original.exe> <temporary-output-directory>
python tools/test_vip_menu.py <temporary-output-directory> --assets-report <temporary-assets-report.json>
```

Python native tests require pefile, unicorn and Pillow. On Windows, run the
updated `tools/verify_menu_patch_lifecycle.py` matrix (including VIP producer
order, hide/show and removal/reapply cases), then `tools/test_vip_hover_toggle.py`
against the newly exported client. Run the matching preserved Battle Pass/Gacha
client suites and live acceptance checks described in
`docs/stable-battlepass-gacha.md` before replacing the working installation.

The asset report is read explicitly as UTF-8 so Windows code pages do not break
verification of the UI prefix. The real WARP export installed all 12 BMPs into
its isolated client data directory, with hashes matching
`vip-menu-icons-complete-12.zip` byte-for-byte.
