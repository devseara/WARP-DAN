# DevSeara chat diff and automatic image deployment

Update (2026-09-22): the installer also supplies the first-use five-tab Lua
resource, without replacing saved layouts. The updated executable is required
for the new right-click tab menu; see [chat tabs](modern-chat-tabs.md).

In WARP, select **Supplied Renewal Chat UI** (`ModernChatUI`, author
**DevSeara**), choose the target/output executable, then apply the selected
patches. No separate image-copy checkbox or manual folder creation is needed.
The diff targets the **2025-07-16** client; its native rendering contract remains
v12, including the white/bold selected tab.

The installer uses the output executable's directory, not the original/source
client's directory or the WARP installation directory. It explicitly creates
each missing parent of:

```text
<output EXE directory>/data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/uirenewal/chat/
```

All 19 PNGs are supplied in `Assets/ModernChatUI`. Missing destination images
are copied automatically. Existing PNGs, including user-recolored icons and
textboxes, are never overwritten. Reapplying repairs missing images without
replacing the other files. The legacy textbox PNGs remain in the supplied pack
for compatibility but are not used to draw the message field.

Before writing, the installer checks that every needed source image exists.
Missing bundles and folder/copy failures report the full affected path. WARP
test mode performs no asset reads or writes. Copying happens when the selected
diff is applied; merely ticking a patch during selection does not write files.

`Inline Chat Item Icons` (`ChatItemIcons`) is also credited to DevSeara. Its
pickup/drop/item-link thumbnails use the client's native item resources and do
not require an extra item-image pack. Battle Pass folder deployment is covered
by its separate update diff and `docs/battlepass-ui-asset-install.md`.

## Verification

`tools/test_modern_chat_asset_install.js` executes the actual QJS installer with
filesystem boundary doubles. It checks the fresh five-level directory chain,
all 19 images, output-path selection, no-overwrite repeat/repair behavior,
test-mode isolation, missing bundles, and directory/copy errors.

On 2026-09-14, a real WARP console build into the initially empty
`Outputs/DevSeara-ChatUI-verify-20260914-100824` directory created the complete
data tree. All 19 installed PNG hashes matched the bundle. A second build
preserved a deliberately customized white `icon_emotion.png`. Neither build
skipped patches. The user's WARP session/settings were restored byte-for-byte;
the installed game executable and images were not changed.

The installation change does not alter native hooks or require replacing an
already-patched v12 game executable. It takes effect on the next WARP patch
application. Reload WARP if it was open to refresh its author metadata.

The generated `Outputs/DevSeara-ChatUI.diff` is a Git update diff for this WARP
working copy, not a standalone binary patch for an arbitrary Ragexe or a full
WARP installation. The selectable WARP diffs remain the registered `.qjs`
scripts above; keep their existing bundled assets with the WARP folder.
Its base is local commit `215e0c2e793fbe8c7bccca443b37658a26659846`.
