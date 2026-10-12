# DevSeara Battle Pass diff and automatic image deployment

Select **Battle Pass** (`BattlepassUI`, author
**DevSeara**) in WARP, choose the output executable, and apply the selected
patches. This automatically creates:

```text
<output EXE directory>/data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/battlepassui/
```

All parent levels are created explicitly, even if the target has no `data`
folder. All 25 runtime BMPs and four button PNGs from
`Assets/BattlepassUI/client` are installed. The 12 menu BMPs from
`Assets/BattlepassUI/menuicon` and seventh-row backgrounds `bg_m7.tga` and
`bg_o7.tga` are installed in the sibling `uirenewal/menuicon/` directory.
Existing images are preserved; repeat runs repair missing files
without replacing client-side skin edits. Missing source images are checked
before writes; errors include the affected source/destination path.

Checking Battle Pass in the selection tree runs its `onSelected` installer as
soon as an output EXE path is available. It creates the menu folder and all 12
icons automatically, along with the window artwork and row backgrounds. If no
output has been chosen yet, selection defers file creation until patch export.
The installer also runs during direct patch application and remains registered
as WARP's `onApplied` callback, so changing the output after selection installs
the assets beside the final output EXE. Repeated calls preserve existing images
and repair missing files. Test mode does not read or write asset files.

The `.bgra` artwork and `Skin_Names.json` in the WARP asset directory are
build-time inputs, not additional runtime files. The **2025-07-16** target,
BPUI packet protocol and matching server dependency are unchanged.
Project Rebirth project/server branding is retained; the author is DevSeara.

`tools/test_battlepass_asset_install.js` executes the actual QJS installation
function against filesystem boundary doubles, covering a fresh target,
all 43 files, no-overwrite repeat/repair, both lifecycle entry points,
test-mode isolation, missing bundles, and directory/copy errors.

## Battle Pass menu shield (2026-10-08)

When `BattlepassUI` and `ROGlobalZeroMenu` are selected, a native Battle Pass
button appears after VIP, or in the next available custom-button slot when VIP
is absent. It uses child ID `0x3FF`, independent of the Battle Pass window
`0x3F8`, and reuses the existing native toggle, refresh negotiation and timer.
`@battlepassui` continues to work. `HideNewButtons` and `ShowNewButtons` include
the label **Battle Pass**. The optional producer may precede or follow the menu;
removing it clears its indirect callback. Six custom buttons plus 25 native
commands and MENU still fit the existing seven-row maximum.

The generated gold shield/crossed-swords emblem, red gem and white **BP** text
match the VIP pixel-art style. The set contains eight 45x41 Renewal BMPs and
four 32x34 Classic BMPs, all 24-bit with magenta color-key transparency:

- Renewal: `bt_battlepass.bmp`, `_disabled`, `_mouseon`, `_new`, `_new_press`,
  `_normal`, `_press` and `_pressed`.
- Classic: `bt_battlepass_old_disabled.bmp`, `_mouseon`, `_normal`, `_pressed`.

`_press` is an exact alias of `_pressed`; Classic `_disabled` aliases Classic
`_normal`. Red-N new-state variants are included for asset compatibility; the
current callback uses normal, mouseon and pressed states. No notification logic
is added. The original transparent PNGs, exact built-in imagegen prompts and
booking BMP header samples are in `Assets/BattlepassUI/menuicon/source/`.
Regenerate the BMPs, manifest and review sheets with
`python tools/build_battlepass_menu_buttons.py`.

The real WARP menu exports are exercised by
`tools/verify_menu_patch_lifecycle.py` and `tools/test_battlepass_menu.py`.
The latter checks 384 compact placements and hit tests, both themes, six actual
installed texture paths, seven-row sizing, child recreation, callback ABI,
native close/reopen, timer lifetime and first-open BPUI v1-to-v7 negotiation.
These offline checks do not establish live in-game visual acceptance. Reload
WARP and export a fresh candidate from the original client to use the update.

On 2026-09-14, a real console build with **only BattlepassUI selected** into
`Outputs/DevSeara-BattlePass-verify-20260914-101404` created the initially absent
data tree and installed all 25 BMPs with hashes matching the bundle. A second
build with the user's full patch profile preserved a customized target skin
and also installed all 19 chat PNGs. No patches were skipped. Its executable
SHA-256 was `0CB7FD721D1CB92249ECAEFA945CE5D56C9A393C8EDA8093C3A5C1D8BAB76195`,
byte-identical to the previously tested v12 full-profile binary. WARP session
and settings were restored byte-for-byte; the installed game was not modified.

`Outputs/DevSeara-BattlePass.diff` is the Git update diff for this existing
WARP working copy. It is not a standalone binary diff for another client
version or a complete WARP distribution. The selectable WARP diff remains
`Scripts/Patches/BattlepassUI.qjs`; retain the existing bundled WARP assets.
Reload WARP to refresh the author and description if it was already open.
The update diff base is local commit `215e0c2e793fbe8c7bccca443b37658a26659846`.
