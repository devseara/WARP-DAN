# WARP-DAN: Battle Pass, Chat UI, NPC Dialog and Universal Gacha

WARP patch package by **DevSeara** for the **2025-07-16 Ragexe** client.
This is a focused add-on, not a full WARP distribution. It contains no game
executable, server source, credentials, or personal installation profiles.

**Accepted stable release:** Battle Pass and Gacha were confirmed working by
the user on September 15, 2026. Both repositories are preserved at tag
`stable-battlepass-gacha-2026-09-15`. See the [baseline, checks and restore guide](docs/stable-battlepass-gacha.md)
before developing another feature.

## Included patches

- **Project Rebirth Battle Pass Window [QJS]** (`BattlepassUI`, ID 10003):
  native Battle Pass window and its 25 runtime BMP images. My Stats and Hunter
  show only the canonical character name, without actor-title decorations.
- **Supplied Renewal Chat UI** (`ModernChatUI`, ID 10001): translucent chat,
  movable/detachable/redockable native tabs, PM input, white emoji/send icons,
  hand cursor feedback, configurable tab font, and white/bold selected tabs.
  Includes 19 PNG images.
- **Inline Chat Item Icons** (`ChatItemIcons`, ID 10004): item thumbnails in
  pickup/drop messages and Shift-click item links, preserving native item data.
- **Renewal NPC Dialog UI v3** (`ModernNpcDialog`, ID 10005): Myth of Yggdrasil
  reference styling, rounded frames, light-blue NPC text/choice panels, centered
  choice buttons, and 25 supplied PNGs. Includes the first-paint NPC background
  correction and the 2025 choice-window OK/Cancel fix. See the
  [NPC dialog notes](docs/modern-npc-dialog.md) for scope and verification.
- **Universal Zeny Gacha UI v20** (`GachaUI`, ID 10006): multiple independently
  configured NPC machines; costs, reward pools, rates, pity, history, spending
  rankings, winners and GM99 reset scoped per machine. Native rolling/reveal/
  sequential delivery, item right-click descriptions, 12-slot pages and four
  automatically deployed arrow PNGs. Four tiers, inventory-overflow mail, and
  up to eight Legendary featured items with hidden unused boxes. See the
  [Gacha guide](docs/gacha-ui.md).

The Battle Pass feature requires the matching Project Rebirth server-side BPUI
implementation. Its server source is **not included** in this WARP-only package.
Chat, item icons and NPC dialogs do not require a new server component.
Gacha requires the matching GCHA wire-v9 server bridge, NPCs and mail worker from
[devseara/Ragnarok](https://github.com/devseara/Ragnarok/commit/7b3e48a2dd4c2bcd618e0661389c59e2757c129e).
The [Gacha guide](docs/gacha-ui.md) links the exact server files and SQL setup.

## Install into WARP

The installation diff is based on
[YlenXWalker/WARP20250716-main at 9a10e8b](https://github.com/YlenXWalker/WARP20250716-main/commit/9a10e8b).
Use that compatible WARP baseline or check compatibility with `git apply --check`.
Other WARP forks/client builds are not assumed compatible.

1. Close WARP and back up or commit your WARP working copy.
2. Download/clone this package outside the WARP directory.
3. In PowerShell, set the package path and run the following from your WARP directory:

   ```powershell
   $patchPackage = 'D:\warp\WARP-DAN'
   $installDiff = Join-Path $patchPackage 'install\DevSeara-BattlePass-ChatUI-NPC-Gacha.diff'
   git apply --check -- $installDiff
   # Continue only if the check above succeeds.
   git apply --whitespace=nowarn -- $installDiff
   ```

   The diff installs the scripts, all images, patch registrations, stable IDs,
   CRLF attributes, and the native UI helper export. Exporting the helper does
   **not** enable Auto Combat or Chat UI. Do not copy only the five QJS files:
   their registrations, assets and helper exports are also required.

   If the check fails, do not force it. Check whether these patches are already
   installed or whether your WARP version/local changes differ. The original
   author's current WARP working copy already contains these patches.

4. Restart WARP, select the desired DevSeara patches, load the original
   **2025-07-16** client, choose the output EXE, and apply.

### Upgrade an existing v20 package with the Battle Pass name fix

For a WARP tree installed from package commit `a1a0f7b`, apply:

```powershell
$patchPackage = 'D:\warp\WARP-DAN'
$nameDiff = Join-Path $patchPackage 'install\DevSeara-BattlePass-plain-name-upgrade.diff'
git apply --check -- $nameDiff
# Continue only if the check above succeeds.
git apply --whitespace=nowarn -- $nameDiff
```

This changes only BattlepassUI.qjs. Rebuild from the original client with the
same patch selections. No server/NPC/database change is required. The fresh
combined diff includes this fix; do not apply the incremental diff twice.

### Upgrade an existing Gacha v15 installation to v20

For a WARP tree installed from package commit `144adb2`, use:

```powershell
$patchPackage = 'D:\warp\WARP-DAN'
$upgradeDiff = Join-Path $patchPackage 'install\DevSeara-Gacha-v20-upgrade.diff'
git apply --check -- $upgradeDiff
# Continue only if the check above succeeds.
git apply --whitespace=nowarn -- $upgradeDiff
```

This changes the Gacha client script only; the prior registrations, shared
packet router and four arrow images remain required. Install the matching
wire-v9 map-server/client pair and v16 char-server/mail schema from the server
repository. Do not mix old and new Gacha wire versions. Existing player records
and pity are retained; no Admin reset is needed.
Then apply the Battle Pass plain-name upgrade above to reach the stable release.

### Upgrade an existing Battle Pass/Chat/NPC package to Gacha

For a WARP tree installed using package commit `35ef127`'s
`DevSeara-BattlePass-ChatUI-NPC.diff`, apply only this incremental diff:

```powershell
$patchPackage = 'D:\warp\WARP-DAN'
$upgradeDiff = Join-Path $patchPackage 'install\DevSeara-Gacha-v15-upgrade.diff'
git apply --check -- $upgradeDiff
# Continue only if the check above succeeds.
git apply --whitespace=nowarn -- $upgradeDiff
```

This historical step adds Gacha v15. Then apply `DevSeara-Gacha-v20-upgrade.diff`
above before building the current client. It adds Gacha and its arrow assets, and safely routes Battle Pass/Gacha to
independent handlers. Either feature can still be selected alone. Do not apply
both the fresh combined diff and this upgrade, or force either onto a WARP
tree that already has Gacha. The author's live WARP tree already has v20.

### Upgrade an existing Battle Pass/Chat UI package installation

If you already applied the original `DevSeara-BattlePass-ChatUI.diff` from
package commit `048e704`, use the incremental diff instead of the combined one:

```powershell
$patchPackage = 'D:\warp\WARP-DAN'
$upgradeDiff = Join-Path $patchPackage 'install\DevSeara-NPC-Dialog-upgrade.diff'
git apply --check -- $upgradeDiff
# Continue only if the check above succeeds.
git apply --whitespace=nowarn -- $upgradeDiff
```

Run these commands from your WARP directory, with WARP closed and your changes
backed up or committed. Do not apply both the combined and incremental diffs.
After this historical NPC upgrade, apply the Gacha upgrade above if desired.
The original Battle Pass/Chat UI diff is retained unchanged for reproducibility.
Neither diff should be forced onto a working copy where NPC UI is already
installed. Pulling this package updates the package files; it does not apply
them to a separate WARP installation automatically.

### Automatic client artwork deployment

The assets are copied when the selected WARP diff is **applied**, not just when
its checkbox is ticked. Every missing parent directory is created beside the
chosen output EXE:

```text
<target EXE directory>/data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/battlepassui/
<target EXE directory>/data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/uirenewal/chat/
<target EXE directory>/data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/genericsui/
```

Existing client images are preserved. Reapplying repairs missing images without
overwriting edited skins/icons. The Battle Pass `.bgra` files and
`Skin_Names.json` are WARP build inputs; only the 25 BMPs are deployed.
The legacy chat textbox PNGs stay in the bundle but are not used to draw the
neutral translucent gray message field.
NPC UI can be selected by itself: the installed Chat UI and Auto Combat helper
scripts are required, but their patches do not need to be selected.
The same applies to Gacha. Its four arrow PNGs deploy under `genericsui/gacha` without
overwriting existing images; item icons come from the client's own resources.

## Verification

The package contains source-level installer/default-input regression tests:

```powershell
node tools/test_battlepass_asset_install.js
node tools/test_modern_chat_asset_install.js
node tools/test_modern_chat_font_inputs.js
node tools/test_modern_npc_asset_install.js
node tools/test_gacha_asset_install.js
```

Offline native chat tests require Python, Pillow, pefile, Capstone, and Unicorn:

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_chat_item_icons.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_controls.py path/to/patched.exe --font Arial --size 12 --weight 400
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_npc_dialog.py path/to/patched.exe
```

Use the same font values selected during patching for the controls test.
Installer tests cover fresh target folders, every bundled image, no-overwrite
repeat/repair behavior, test-mode isolation, and file/directory errors.
Real WARP builds verified Battle Pass by itself and the full combined patch
profile, including automatic image deployment and preservation of edited assets.
Offline checks are not a substitute for live testing with your client/server.
NPC v3 passes the native first-paint regression and preserves the accepted v2
choice frames/buttons pixel-for-pixel. Live NPC v3 visual acceptance is still
pending. Run the tests from this package; test tools are not installed by the
WARP installation diffs.

Gacha tests and server requirements are in [the Gacha guide](docs/gacha-ui.md).
Fresh/upgrade installer and feature-routing checks are recorded in
[package verification](docs/gacha-package-verification.md).

## License and attribution

GPL-3.0-or-later; see [LICENSE](LICENSE). WARP and existing native helpers retain
their original authorship and license. DevSeara is credited for these custom
Battle Pass, chat, NPC dialog and Gacha diffs. Project Rebirth server/project names are retained.
