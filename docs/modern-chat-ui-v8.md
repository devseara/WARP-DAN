# Modern chat UI v8 - PM recipient and layout corrections

Target: 2025-07-16 Ragexe using the full
`profiles/ragnarok_full_install.yml` profile. Installed target:
`D:\AAARAGNAROK\Ragnarok Online\Ragnarok.exe`.
Installed/validation SHA-256 (identical):
`F11E80F92956D6F78EACA78D02C81EAA323911114931090DF98F895884603567`.

## Requested changes

- Restored the **native whisper recipient field** to the left of the message.
  The v7 removal of the recipient selectors had hidden `main+0xC0`, disabled
  its keyboard focus, and suppressed its parent notifications. Those recipient
  restrictions are removed. The separate receiving-group popup stays hidden.
- Click left of the divider to enter a character name; type the message to its
  right and press Enter. Leave the recipient blank for public chat. Both clicks
  activate native chat mode and preserve `main+0xB4` as its last-focused edit.
  Native recipient history, text getters, IME, and whisper routing are retained.
- The single 20px `textbox_off.png` background remains. Recipient and message
  edits have 16px height and 2px outer vertical padding. The native text/caret
  offset `+0xF4` is zero, producing a 2px internal offset and centering a 12px
  line at bar y+4. Placeholder text uses the same baseline. No text is centered
  horizontally: typed messages and names retain normal left alignment.
- A fixed divider at x=108 separates the recipient field (x=23, width=81) from
  the message field (x=116, width=window width-136). The placeholder begins at
  x=119, matching the native edit's 3px horizontal text inset.
- Bottom tabs share `(window width-60)/page count`, rounded down. They use a
  1px gap and narrow borders. Native hit widths now equal the drawn pitch:
  the old extra pixel per hit region no longer accumulates across the row.
  Tab labels, order, filters, and detach/re-dock behavior are unchanged.
- The reserved settings/lock section has translucent slate-gray fill
  `0x80333753`, matching the supplied textbox's center, a subtle border, and a
  divider. Gear and lock are vertically centered in the 20px row.
- A detached chat's **message child surface** now owns the same `0x80111114`
  translucent fill as its header. After native message drawing and key cleanup,
  transparent pixels become gray without altering foreground or partial-alpha
  pixels. This prevents child composition from removing the body's backing.
  Other UI lists and the main chat message surface are not changed by this fill.

## Checks

Both full-profile builds completed successfully with an empty skipped-patch
log. The installed binary passes the expanded suite. Pre/post-install hashes
are identical for all 19 PNGs and `savedata/ChatWndInfo_U.lua`.

The expanded `tools/test_modern_chat_ui.py` executes the emitted x86 and checks:

- Restored recipient visibility, native focus, and parent-event forwarding;
  recipient/message click regions never begin a window drag.
- Actual native routing instructions `0x8FDC30..0x8FDC98`, including native
  recipient length/text getters, select the whisper dispatcher event `0x0B`
  for a named recipient. Blank recipients and slash commands follow the native
  public/command branch. The network dispatcher is a test double: no messages
  are sent by these tests.
- Every exact tab hit-test boundary agrees with its drawn partition, across
  resized layouts. All five selections and native detach/re-dock checks remain.
- Native move/release, floating move/resize, return-chevron and drag-back
  dispatch, bounded docking capacity, GDI alpha, and all 19 real supplied PNGs.
- Gray pixels throughout the floating child body, preserved message colors,
  the input divider, settings/lock backing, and centered edit layout/inset.

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py 'D:\AAARAGNAROK\Ragnarok Online\Ragnarok.exe'
```

These tests do not replace in-game acceptance of rendering, IME/caret movement,
or delivery to an online character. Reopen the client, enter a recipient name,
send a PM, and check the supplied screenshots against both window states.

## Recovery

Verified pre-v8 backup of the executable, `.epi`, `.secure.txt`, patch source,
and saved chat Lua:

`D:\warp\WARP20250716-main\Outputs\chat-ui-backup-20260914-v8`

Pre-v8 executable SHA-256:
`954BCA13D6DB89521A53DD938ED3835D13C9B94E40A72DF2B4A4C59FF9C526D3`.

Restore executable-side files with the client closed to roll back to v7.
Preserve newer saved chat data and PNGs; this update does not rewrite either.
