# Modern chat UI v10 - text-only tabs and white smiley

Target: profiled 2025-07-16 Ragexe. This supersedes the icon tabs and 12px
default in v9; the native input actions, tab partitions and movement are unchanged.

- All chat tab labels are text-only, centered without the previous 19px icon
  advance. The tab texture lookup and icon-draw path are removed, including
  for PM/Whisper or renamed pages. The separate PM **input indicator** remains.
- The smiley uses the supplied `btn_emote2.png`, whose visible pixels have the
  same `#E5F2FF` white as the send, settings and lock assets. No PNG is edited.
  Its 12x12 size, position, hit region and native Alt+L Emoji List action remain.
- WARP's Chat Tab Font Size prompt, cancellation default and checked-in full
  profile now default to **8**. The allowed 8-16 range and configurable font
  family/Normal/Bold remain. The current user session is built as Arial/8/Bold,
  preserving its Arial/Bold selection and every other patch/input selection.

The private tab-label helper now uses `thiscall(text,left,cellWidth)` and
`ret 12`; its versioned offline contract is `ModernChatUI.v10`. Private font
caching, measurement, clipping and DC restoration are retained. No shared
TextOut hooks, global font tables or item/enchant renderer are changed.

## Checks

Build profile: `Outputs/modern-chat-v10-profile.yml`, derived from the current
user session with only its font-size input changed. Original session/settings
are saved under `Outputs/session-before-modern-chat-v10` and restored after
console patching, with size 8 retained in LastSession.

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_controls.py Outputs/modern-chat-v10.exe --font Arial --size 8 --weight 700
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py Outputs/modern-chat-v10.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_chat_item_icons.py Outputs/modern-chat-v10.exe
```

These execute patched x86 with explicit native/OS boundary doubles. They
check text-only centering and partitions, white control pixels, font settings
and DC restoration, PM/Enter/Emoji actions, native detach/dock and item icons.
In-game visual acceptance of the smaller text is still required.

## Deployment and recovery

The build completed with an empty skipped-patch log, and all three suites
passed. Installed `Ragnarok.exe` plus its matching `.epi` and `.secure.txt`
with the client closed. Installed SHA-256:

`B8782AEDF0E9EDDD47848269AC5CC33F0B861CEC07E2BF50D9772AF3E79169B3`

All 19 chat asset hashes and `savedata/ChatWndInfo_U.lua` are unchanged.
The previous executable, both sidecars and saved chat Lua are backed up in
`Outputs/chat-ui-backup-20260914-v10`. Previous executable SHA-256:

`676A95C8B1C89FCD82DD7D6EDE047B93DC4884A3A8ADEAEAB36B523DAF6E9D0D`

To roll back, close the game and restore the executable and both sidecars.
Preserve any newer PNGs and saved chat data.
