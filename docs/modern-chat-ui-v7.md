# Modern chat UI v7 - translucent skin and native tab docking

Target: 2025-07-16 Ragexe. Rebuilt with the complete
`profiles/ragnarok_full_install.yml` profile; no server-side changes.
Installed target: `D:\AAARAGNAROK\Ragnarok Online\Ragnarok.exe`.
Installed/validation SHA-256 (identical):
`954BCA13D6DB89521A53DD938ED3835D13C9B94E40A72DF2B4A4C59FF9C526D3`.

## Reference and controls

Latest reference: `C:\Users\Vysache\Downloads\2026-08-30 12-27-09.mp4`,
26-35 seconds. Battle is detached, moved/resized, and returned to the bottom
row. This supersedes the earlier request to prohibit tab detachment.

- Unlock using the bottom-right lock. Drag a tab away to detach its real page.
- Move detached windows by their header, and resize from the bottom-right grip.
- The top-right double-chevron returns the page to the main bottom row.
  The native drag-back gesture also remains: release the floating window with
  its lower-left corner over the main window. The client appends returned tabs.
- Drag unoccupied main frame/background to relocate the entire main chat.
  Clicking the textbox only focuses typing; it never starts window dragging.
- Main/Market/Battle/Party/Guild labels, page identities, filters, and message
  transfers remain native. Names/order are not substituted during drawing.

## Appearance and input

Main and floating panels use `0x80111114` (about 50% opaque charcoal) with a
subtle border. Bottom tabs are translucent with centered text-only labels,
matching the latest video. Native GDI message/title text remains opaque.
The gear and lock remain alongside the bottom row.

`textbox_off.png` is now the sole input background in both idle and focused
states. The supplied PNG is not recolored; its own alpha controls transparency.
`textbox_on.png` is no longer loaded by the skin. The native edit owns text,
IME, and blinking caret; foreground contrast samples the sole PNG's center.
The placeholder disappears on focus. Recipient and receiving-group selectors
are hidden, excluded from focus, and prevented from dispatching popups.
The small general/direct icons in the reference are decorative input artwork.

Supplied floating controls: `icon_settings.png`, `btn_min.png` (return), and
`btn_expand.png` (resize grip). Existing client PNGs are copied only if missing;
their artwork and the saved chat Lua are not rewritten by this update.

## Native patch contract

- Main vtable `0x1037F80`; floating chat vtable `0x1037EA8`.
- Private chat TabCtrl vtable retains native click `0x858B90`, captured move
  `0x85A620`, and release `0x859380`. Captured move sends event `0x75`.
- Main event `0x8FC220` forwards selection, detach (`0x75`), and dock (`0x76`).
  Only obsolete top-strip paint (`0x74`) and removed selectors are suppressed.
  Native maps, message copy operations, and saved-page identities stay intact.
- The fixed-width reject branch at `0x8FC637` originally had bytes
  `0F 8F 3C 1E 00 00`. It incorrectly rejected returning tabs because the
  equal-width bottom strip already occupied the available width. A bounded
  replacement admits the new count only if at most 12 pages and each can have
  the layout's minimum 32px width. Native locking and label-width checks remain.
- Floating return is child `+0xDC`, native button ID **0x165**, dispatched by
  `0x9020B0` to main event `0x76`. Child `+0xE4`, ID **0xCA**, deletes a page;
  that button is hidden, not relabeled as return. Tests execute the actual
  native button dispatcher to distinguish these operations.
- Floating draw and button layout are skinned; native move, resize, release,
  gear/filter dialogs, and drag-back detection are retained. Direct legacy
  background overlays are disabled to avoid applying opacity twice.
- Only profiled main/floating clear sites change magenta PUSH immediates to
  transparent zero. Native message draw is finalized only for these two parent
  classes. Edit/focus wrappers remain scoped only to main chat children.
- Each patched instruction/vtable target is checked against the profiled
  original before mutation. QJS remains UTF-8 without BOM, CRLF, tab-indented.

## Verification and limits

Both full-profile builds completed successfully, `SkippedPatches.log` is empty,
and the installed binary passes the suite below. Pre/post-install hashes match
for all 19 client PNGs and `savedata/ChatWndInfo_U.lua`.

The emitted-x86 suite exercises stack and callee-save registers, five tab
selections, resized bottom layout, native tab capture and detach notification,
main frame relocation/release, floating move/resize and saved-position writes,
native floating return dispatch and drag-back docking dispatch, capacity limits,
hidden selectors, focus-only input clicks, both textbox states, and scoped alpha
cleanup. All pixels of all 19 actual PNGs are checked against independent
source-over calculations over clear, opaque, and translucent backgrounds.

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py 'D:\AAARAGNAROK\Ragnarok Online\Ragnarok.exe'
```

These are emulator tests with bounded native UI/OS/map/text-rendering test
doubles, not an in-game visual acceptance. Full detach/dock map/message transfer
is preserved native code, not a fully simulated end-to-end client test.
Reopen/login to check live incoming chat, caret/IME, tab switching, drag-out,
return, settings/lock, and resizing against the reference video.

## Recovery

Verified pre-v7 backup (v6 executable SHA-256
`77C23467C7D41D592C26A65D70BDA5EB237062F3A10A1447A80FBC7A4C2F45F9`):

`D:\warp\WARP20250716-main\Outputs\chat-ui-backup-20260914-v7`

With the client closed, restore the backed-up `Ragnarok.exe`, `.epi`, and
`.secure.txt` to the client root, and source QJS to WARP's `Scripts/Patches`.
Keep newer saved chat data and PNGs; v7 does not modify them. The saved Lua copy
in the backup is optional recovery only, not required to roll back the binary.
