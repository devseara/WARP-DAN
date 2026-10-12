# Modern chat UI v13 - incremental redraw repair

Target: 2025-07-16 Ragexe, local WARP `D:/warp/WARP20250716-main`.

## Cause and change

The native chat pane sends its parent event `0x74` before repainting. Stock
main chat clears the old message rectangle in response. Modern chat v12
discarded that notification along with obsolete header painting. Its pane
uses alpha composition, so transparent pixels in the next frame preserve
the previous parent pixels, leaving old glyphs behind during rapid updates.

V13 handles `0x74` from a visible native message pane belonging to main chat.
It restores just that pane's rectangle to `PanelFill` (`0x80111114`) before
native composition. The private helper checks ownership/type/visibility,
skips negative-position hidden pages and empty rectangles, clips to actual
parent surface dimensions, and marks the surface dirty. It neither resizes
the surface nor changes its alpha mode or cached textures. Other obsolete
header notifications remain suppressed; other native events are forwarded.

Only `ModernChatUI.qjs` runtime code changes. There are no server, drop-rate,
announcement, chat-history, item identification, shared compositor, Battle
Pass, Gacha, asset or saved-profile changes. Floating chat keeps its native
clear handler. The `ModernChatUI.v13` offline descriptor retains the v12
font/control fields and appends the private `restorePaneBacking` address.

## Verification

`tools/test_modern_chat_redraw.py` executes the real native pane renderer,
clear function, dirty traversal and alpha compositor. GDI glyph output and
item-link positioning are explicit test doubles. With `--expect-bug`, the
previous client reproduces a stale yellow glyph after a shorter replacement
message; restoring its parent backing is the diagnostic control.

The fixed-client test compares 100 incremental updates against freshly
cleared references, with varying lengths/colors, scrolling and empty history.
It also checks clipping, hidden/foreign/wrong-type senders, absent surfaces,
unchanged chrome, calling conventions and unchanged cached-texture state.
Existing modern chat layout/control and chat item tests remain required,
as do the protected Battle Pass/Gacha regression gates.

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_redraw.py Outputs/chat-redraw-20260916/combined/Ragnarok-chat-test.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py Outputs/chat-redraw-20260916/combined/Ragnarok-chat-test.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_controls.py Outputs/chat-redraw-20260916/combined/Ragnarok-chat-test.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_chat_item_icons.py Outputs/chat-redraw-20260916/combined/Ragnarok-chat-test.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/verify_stable_features.py --manifest docs/stable-battlepass-gacha.json --installed --client Outputs/chat-redraw-20260916/combined/Ragnarok-chat-test.exe
```

## Deployment scope

The requested change is applied to local WARP only. The rebuilt full-profile
client remains staged in `Outputs/chat-redraw-20260916/combined/` for testing;
the installed `Ragnarok.exe` is not replaced and no Git push is performed.
The pre-change source copy is under `Outputs/chat-redraw-20260916/before-source/`.
The accepted Battle Pass/Gacha restore point remains immutable.

Verification completed: redraw stress/scope, chat layout, controls/fonts,
all 13 chat item tests, seven combined Battle Pass/Gacha suites, and standalone
Battle Pass/Gacha suites passed. Reversed feature selection produced the exact
same combined executable. WARP's 57-file preservation guard passed. The font
input source regression passed using the available V8 runtime (Node is not on
PATH). No live acceptance is implied by these offline results.

Staged combined/reversed SHA-256:
`A3916282E87137D8C287088FB854F0F01981682046E2F28AF87B82BF15085E4F`.
Installed client remains:
`F470E8067FE1EC2BF87A3EF92D973B36FD90E6ADF5B4E372C65053D078698156`.

In-game acceptance is still required: rapid kills with announcements and item
pickups, manual scroll/tab changes, resize and detached chat; also confirm
identified/unidentified item hover and right-click behavior remains correct.
