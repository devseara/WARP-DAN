# Modern chat UI v11 - accepted defaults and native button cursor

Target: profiled 2025-07-16 Ragexe. Native chat actions, text-only tabs and
private font rendering are unchanged from v10.

## Normal/default input fix

The style and size prompts omitted `saveDefault: true`. WARP can return false
for a default-valued selection without that option, which the patch treated
as cancellation. Both prompts now accept and save their defaults, matching
the existing font-family prompt. Normal maps to weight 400; Bold to 700.
An actual Cancel still cancels, with an explicit cancellation message.
Size 8 remains the default, with the existing 8-16 validation.

The deployment profile preserves the user's current Arial/12 choice and
other selected patches/inputs, changing Bold to the requested Normal. An
additional full-profile smoke build uses Tahoma/8/Normal, all three defaults.

## Cursor behavior

- Only the main chat vtable's native cursor callback (`+0x78`) is replaced.
  It receives window-local coordinates from native hit-tested dispatch.
- Smiley and send use their existing `[width-51,width-3)` input cells, at
  y=`[height-42,height-22)`. Lock uses `[width-18,width-10)`, at
  y=`[height-20,height)`. No click action, capture or layout code is changed.
- These regions request native `cursors.act` action 2 through `0xA764A0`,
  exactly as stock buttons do. The native cursor renderer reads the left
  button state at `0x11E40E4` and advances the hand's pressed frames.
- Leaving a control uses the original `0xA23470` callback (normal cursor).
  Hidden chat, captured window/tab drags and unavailable input edits do not
  request the hand. Both locked and unlocked states retain button feedback.
- Other windows and native settings buttons keep their own callbacks.
  No global cursor draw hook, cursor sprite replacement or cursor overlay is
  added; the existing Battlepass cursor implementation is left unchanged.

Profile checks verify the callback, native setter, stock hand selection and
pressed-animation branch before patching. `ModernChatUI.v11` metadata adds
the cursor callback address to the offline contract.

## Verification

`tools/test_modern_chat_font_inputs.js` evaluates the actual `getTabFont`
source with an explicit GetUserInput boundary double. It covers all defaults,
Normal with non-default family/size, Bold, actual cancellation and invalid
values. It can run through `node tools/test_modern_chat_font_inputs.js` or an
available JavaScript runner calling `verifyChatFontInputs(source)`.

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_controls.py Outputs/modern-chat-v11.exe --font Arial --size 12 --weight 400
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_controls.py Outputs/modern-chat-v11-defaults.exe --font Tahoma --size 8 --weight 400
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py Outputs/modern-chat-v11.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_chat_item_icons.py Outputs/modern-chat-v11.exe
```

The cursor tests execute the emitted callback and actual native setter,
checking resized region edges, up/down input states, lock states, leaving the
controls, missing edits, hidden chat and capture. Repeated hover must not
restart animation. A native cursor-renderer instruction slice verifies its
up/pressed frame selection with an explicit ACT-frame-count boundary double.
Existing font/DC, layout, native PM/send/emoji, detach/dock and item-icon
regressions remain. No game message is sent by tests. WARP GUI interaction
and in-game screenshot acceptance are not claimed by these offline checks.

## Deployment and recovery

Both full-profile builds completed with empty skipped-patch logs. The four
binary test commands and the JavaScript input regression passed. The latter
ran through the available V8 JavaScript runner; no Node installation was needed.

Installed the Arial/12/Normal build and matching `.epi`/`.secure.txt` with
the client closed. Installed `Ragnarok.exe` SHA-256:

`241611E54F19C7F0181B8776F6122AE8D44FF082F344C32D2B67D00246247B62`

All 19 chat PNGs (including the previously updated white `icon_emotion.png`)
and saved chat Lua were unchanged. Original session selections and output
destination were restored, changing only the saved font style to Normal.
Restart WARP to reload the updated input code, and reopen the game to check
the native hand feedback visually.

The previous executable, both sidecars and saved chat Lua are backed up at
`Outputs/chat-ui-backup-20260914-v11`. Previous executable SHA-256:

`B16C7C9A941B5EB3F41BF85AEA9D959BE193C4FFD27D776EFE8619FC26D3140A`

To roll back, close the game and restore the executable plus both sidecars.
Keep newer PNGs and saved chat data unless a separate rollback is intended.
