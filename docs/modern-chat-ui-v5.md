# Modern chat UI v5 — 2025-07-16 client

Superseded by [v6](modern-chat-ui-v6.md) after user screenshots exposed native
tab detachment and PNG transparent-RGB handling defects. The current supplied
active PNG is light/white, intentionally retained at the user's request.

Reference: user screenshots and `C:\Users\Vysache\Videos\2026-09-14 04-36-52.mp4`.

## Changes

- Main pane: charcoal background, fine rounded frame; native message list and scrollbar.
- Input at `height - 42`: supplied `textbox_off.png` when idle and `textbox_on.png` when active.
- Hide the separate `dialog_mid.bmp` image and remove the light-gray fill from chat edit controls. Keep native text/caret handling.
- Tabs at `height - 20`: rounded native-surface buttons, dynamic widths shared by painting and hit testing. Settings and lock occupy the right end of this row.
- Preserve actual native tab names and filter records, instead of replacing labels by array position. The deployed saved-data IDs order the pages Main, Market, Battle, Party, Guild; each page's existing filter options are unchanged.
- Suppress obsolete parent paint notification `0x74`, which clears the former top strip with magenta.
- After message/edit/tab/main rendering, remove RGB `FF00FF` and restore alpha for zero-alpha GDI text pixels. Preserve nonzero PNG alpha.
- Message-list and edit wrappers check that the parent is the profiled chat window. Chat tabs use an instance-owned vtable, so `ROGlobalZeroInventory` can retain its separate shared-tab renderer without overwriting chat paint.

## Validation

Build the complete existing profile (not a reduced patch list):

```powershell
.\win32\WARP_console.exe -using .\profiles\ragnarok_full_install.yml
```

Check its output for `Patch Error`; this console can return exit code zero even when a patch fails.

Run `tools/test_modern_chat_ui.py <exe>` with `pefile`, `capstone` and `unicorn` installed. It executes emitted x86 hooks against bounded native UI test doubles and asserts stack/nonvolatile-register preservation, selected-page layout, resizes, input resource choice, transparent edit fills, GDI foreground visibility, magenta cleanup, native notification forwarding and lock hit boundaries. This is not in-game visual acceptance.

## Assets and limitations

The 19 original assets are copied unchanged from `Assets/ModernChatUI` to the client's `data/texture/<UI prefix>/uirenewal/chat` directory. The supplied Market/Battle/Party/Guild icons are colored speech bubbles, unlike the merchant/swords/people/shield in the reference video; no replacement artwork is fabricated.

Native filters and server channel routing are not redefined. In the supplied saved configuration, Battle has all 25 filter options disabled. That page remains empty until its desired filters are enabled through the gear. Main retains its enabled normal/system filters.

## Rollback

Pre-v5 executable, `.epi`, `.secure.txt` and `ChatWndInfo_U.lua` are saved in:

`D:\AAARAGNAROK\Ragnarok Online\chat-ui-backup-20260914-v5`

With the client closed, copy those executable-side files back to the client root and `ChatWndInfo_U.lua` back into `savedata`. The source snapshot before v5 is `Outputs/ModernChatUI-before-v5.qjs.bak`.

Visual acceptance still requires an in-game session: incoming messages visible, five tab transitions without magenta, active typing on the dark input texture, bottom position after resizing, native settings and lock clicks.

## Installed build

- Executable: `D:\AAARAGNAROK\Ragnarok Online\Ragnarok.exe`
- SHA-256: `1E01559196FD685F82FC42AA68DEB8DA5B02E62B6242C80EE349C2D5477968B8`
- Full-profile WARP build: no patch errors.
- Emitted-x86 checks against this installed executable: PASS.
- No in-game visual acceptance claimed; the user must log in before that check.
