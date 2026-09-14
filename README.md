# WARP-DAN: Battle Pass and Chat UI

WARP patch package by **DevSeara** for the **2025-07-16 Ragexe** client.
This is a focused add-on, not a full WARP distribution. It contains no game
executable, server source, credentials, or personal installation profiles.

## Included patches

- **Project Rebirth Battle Pass Window [QJS]** (`BattlepassUI`, ID 10003):
  native Battle Pass window and its 25 runtime BMP images.
- **Supplied Renewal Chat UI** (`ModernChatUI`, ID 10001): translucent chat,
  movable/detachable/redockable native tabs, PM input, white emoji/send icons,
  hand cursor feedback, configurable tab font, and white/bold selected tabs.
  Includes 19 PNG images.
- **Inline Chat Item Icons** (`ChatItemIcons`, ID 10004): item thumbnails in
  pickup/drop messages and Shift-click item links, preserving native item data.

The Battle Pass feature requires the matching Project Rebirth server-side BPUI
implementation. Its server source is **not included** in this WARP-only package.
Chat and item icons do not require a new server component.

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
   $installDiff = Join-Path $patchPackage 'install\DevSeara-BattlePass-ChatUI.diff'
   git apply --check -- $installDiff
   # Continue only if the check above succeeds.
   git apply --whitespace=nowarn -- $installDiff
   ```

   The diff installs the scripts, all images, patch registrations, stable IDs,
   CRLF attributes, and the native UI helper export. Exporting the helper does
   **not** enable Auto Combat. Do not copy only the three QJS files: their
   registrations and helper export are also required.

   If the check fails, do not force it. Check whether these patches are already
   installed or whether your WARP version/local changes differ. The original
   author's current WARP working copy already contains these patches.

4. Restart WARP, select the desired DevSeara patches, load the original
   **2025-07-16** client, choose the output EXE, and apply.

The assets are copied when the selected WARP diff is **applied**, not just when
its checkbox is ticked. Every missing parent directory is created beside the
chosen output EXE:

```text
<target EXE directory>/data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/battlepassui/
<target EXE directory>/data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/uirenewal/chat/
```

Existing client images are preserved. Reapplying repairs missing images without
overwriting edited skins/icons. The Battle Pass `.bgra` files and
`Skin_Names.json` are WARP build inputs; only the 25 BMPs are deployed.
The legacy chat textbox PNGs stay in the bundle but are not used to draw the
neutral translucent gray message field.

## Verification

The package contains source-level installer/default-input regression tests:

```powershell
node tools/test_battlepass_asset_install.js
node tools/test_modern_chat_asset_install.js
node tools/test_modern_chat_font_inputs.js
```

Offline native chat tests require Python, Pillow, pefile, Capstone, and Unicorn:

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_chat_item_icons.py path/to/patched.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_controls.py path/to/patched.exe --font Arial --size 12 --weight 400
```

Use the same font values selected during patching for the controls test.
Installer tests cover fresh target folders, every bundled image, no-overwrite
repeat/repair behavior, test-mode isolation, and file/directory errors.
Real WARP builds verified Battle Pass by itself and the full combined patch
profile, including automatic image deployment and preservation of edited assets.
Offline checks are not a substitute for live testing with your client/server.

## License and attribution

GPL-3.0-or-later; see [LICENSE](LICENSE). WARP and existing native helpers retain
their original authorship and license. DevSeara is credited for these custom
Battle Pass and chat diffs. Project Rebirth server/project names are retained.
