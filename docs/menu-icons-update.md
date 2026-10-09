# VIP and Battle Pass menu update — 2026-10-08

This update adds dedicated VIP and Battle Pass buttons to ROGlobalZeroMenu for
the original 2025-07-16 Ragexe. It contains the complete 12-file VIP crown and
12-file Battle Pass shield sets, with Renewal and Classic states, source PNGs,
art prompts, manifests and reproducible BMP exporters.

Selecting **BattlepassUI** automatically creates its menu icons and window
artwork beside the chosen output EXE. If the output is not selected yet, file
creation is deferred until patch export. Applying the patch also repairs missing
files at the final output location. Existing custom artwork is preserved.
Applying **VipUI** installs all 12 VIP icons automatically.

Both sets use `data/texture/<UI prefix>/uirenewal/menuicon/`. Select
**ROGlobalZeroMenu** with the existing menu/theme dependencies to display the
buttons. VIP follows Bestiary; Battle Pass follows VIP when it is enabled.
HideNewButtons/ShowNewButtons support both labels. Two seventh-row backgrounds
are included. The Settings gear keeps its Settings function.

## Install into current WARP

The patch is based on
[YlenXWalker/WARP20250716-main e401705](https://github.com/YlenXWalker/WARP20250716-main/commit/e401705bb68aad058ab934745c9b845cbd2193a9).
That full WARP version already supplies the native VIP and Battle Pass windows,
runtime payloads, shared native helpers and registrations required by this
update. The older September WARP-DAN package alone is not this prerequisite.

Close WARP, preserve local edits, and run from the compatible full WARP folder:

```powershell
$menuPackage = 'D:\warp\WARP-DAN'
$menuDiff = Join-Path $menuPackage 'install\DevSeara-VIP-BattlePass-menu.diff'
git apply --check -- $menuDiff
# Continue only when the check succeeds.
git apply --whitespace=nowarn -- $menuDiff
```

The author's current WARP working folder already contains this update. Do not
apply it a second time. On another checkout, a failed check means the version or
local edits need review; do not force it. Reopen WARP and export a fresh candidate
from the original client with the desired patches selected.

The matching server update is in
[devseara/Ragnarok](https://github.com/devseara/Ragnarok): `src/map/vip.cpp`,
`src/map/vip_ui.hpp` and `src/map/clif.cpp`. It accepts VIPU v4 action 13 as a
tokenless, read-only open request and keeps existing purchase token checks,
account/action locks and rate limiting. The Battle Pass button reuses its
existing native toggle and BPUI protocol; no Battle Pass server change is needed.

## Published files and validation

- `install/DevSeara-VIP-BattlePass-menu.diff` is the complete Git binary update.
- `updates/vip-battlepass-menu/files/` contains the 67 source, artwork, document
  and test files for review, with a sibling hash manifest and base/result trees.
  These are an overlay for full WARP, not a standalone WARP application.
- The September root package, installation chain, accepted manifest and restore
  tag remain intact. New menu source is in the update directory above.
- Unrelated local announcement, Barter, settings and private profile changes are
  excluded. No game/server executable is included.

Validate the published bytes and, optionally, reconstruct the installation in a
temporary Git index without changing a WARP working tree:

```powershell
python tools/verify_menu_icon_package.py
python tools/verify_menu_icon_package.py --warp D:/warp/WARP20250716-main
```

The original current-WARP implementation passed the real WARP lifecycle and
visibility matrix, both Battle Pass/Gacha selection orders, standalone Battle
Pass, 384 native Battle Pass menu placements, 192 VIP menu placements, texture
path checks, all asset installer checks and the combined BP/Gacha/VIP native
regression suites. The actual Battle Pass selection callback also created all
12 icons through WARP's filesystem APIs before patch application.

Run the included tests from the updated full WARP tree. Native checks require
the supported original client and Python with Pillow, pefile, Capstone and
Unicorn; the asset installer checks use Node.js. Live in-game visual acceptance
remains pending. Publishing this source does not replace or restart clients or
servers and does not modify player data.
