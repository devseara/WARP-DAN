# DevSeara Battle Pass diff and automatic image deployment

Select **Project Rebirth Battle Pass Window [QJS]** (`BattlepassUI`, author
**DevSeara**) in WARP, choose the output executable, and apply the selected
patches. This automatically creates:

```text
<output EXE directory>/data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/battlepassui/
```

All four parent levels are created explicitly, even if the target has no
`data` folder. All 25 runtime BMPs from `Assets/BattlepassUI/client` are
installed. Existing images are preserved; repeat runs repair missing files
without replacing client-side skin edits. Missing source images are checked
before writes; errors include the affected source/destination path.

The installer runs during direct patch application and remains registered as
the WARP `onApplied` callback. Repeated calls are safe. Test mode does not read
or write asset files. Merely checking the patch in the selection tree does not
write files; deployment accompanies applying the selected diff.

The `.bgra` artwork and `Skin_Names.json` in the WARP asset directory are
build-time inputs, not additional runtime files. Native Battle Pass code,
packets, server dependencies, and the **2025-07-16** target are unchanged.
Project Rebirth project/server branding is retained; the author is DevSeara.

`tools/test_battlepass_asset_install.js` executes the actual QJS installation
function against filesystem boundary doubles, covering a fresh target,
all 25 files, no-overwrite repeat/repair, both lifecycle entry points,
test-mode isolation, missing bundles, and directory/copy errors.

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
