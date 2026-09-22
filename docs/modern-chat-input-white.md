# White chat input and centered typing

2025-07-16 Ragexe, local WARP `D:/warp/WARP20250716-main`.

The user's requested changes are limited to the bottom chat input:

- White (`#FFFFFF`) native typed text, whisper-recipient text and idle hint.
- Message and recipient edit windows move up 2 pixels (parent height minus 42,
  previously minus 40). Native edit dimensions, text inset, selection and caret
  behavior remain intact. The hint moves up by the same amount.
- Public/PM message indicators render white through a private PNG blitter.
  Their source alpha, cutouts, magenta transparency key and clipping are retained.
  Original PNGs are neither edited nor overwritten. Other controls and artwork
  continue through the original non-tinted blitter.

Only `ModernChatUI.qjs` emits different runtime code. No global text hooks,
item names/identification, chat message colors, send routing, server settings,
Battle Pass/Gacha helpers, or saved user profiles are changed.
The existing v13 descriptor is preserved; `ModernChatUI.Input.v1` adds a private
read-only contract for the new tests.

## Existing-client upgrade

`tools/upgrade_modern_chat_input.py` stages a guarded upgrade of the existing
client instead of replacing unrelated patches with a full-profile reconstruction.
It requires an exact original hash and a fresh WARP-emitted white blitter.
The copied helper has one external call, retargeted to the existing chat's
blend function; every internal branch and memory reference is validated.

It changes five private input constants and the two verified PM/public PNG
call operands. The helper plus test descriptor is appended inside the final
`.xdiff` section's previously zero-filled mapped tail. Existing RVAs and image
size are retained, only the section's raw length grows. The original overlay is
preserved. An exhaustive reverse comparison proves all other original bytes
unchanged. The tool never overwrites its source EXE and emits a JSON edit audit.

The normal WARP patch also produces this behavior for future builds. Restart
an already-open WARP before loading the revised script; saved profiles are not
rewritten by this change.

## Checks and acceptance

`test_modern_chat_input.py` executes actual emitted x86 on supplied public/PM
textures and synthetic alpha/key edge cases. It checks clipping, no texture
mutation, unchanged ordinary artwork, exact white input/hint, raised edit
positions across sizes, and tint scoping. The normal chat layout suite remains
compatible with prior clients. Existing control/font/PM, redraw stress, and
identified/unidentified item-link suites must pass too.

The test uses explicit UI/GDI boundaries, not live typing. In-game acceptance:
type `qweqwe`, uppercase and descenders such as `gyp`, check caret/selection,
switch public/whisper, resize chat, then open Battle Pass and Gacha. Confirm
white readable text/icon and comfortable vertical centering. Never send private
test text or reset gameplay data just to validate UI styling.

Staged builds, before-source copies, the unchanged source profile and test logs
are private under `Outputs/chat-input-20260916/`. No Git publication is implied.

Verification completed on both the guarded existing-client upgrade and a fresh
WARP build: input styling, layout, controls/fonts/PM, 100-update redraw stress,
all chat item-link tests, and the seven combined Battle Pass/Gacha suites.
Standalone Battle Pass and Gacha passed; reversing their selection order gave
the same full-profile EXE. The WARP 57-file preservation guard and font-input
source test passed. No baseline tag/manifest was updated.

Installed after confirming Ragnarok was closed:
`D:/AAARAGNAROK/Ragnarok Online/Ragnarok.exe`, SHA-256
`E60B6C3988CF03659656CDECE2B8192384CA38259DC34A4F6EECCEF99FE1BBB0`.
The verified previous EXE is in
`Outputs/chat-input-20260916/installed-before/Ragnarok.exe`, SHA-256
`8E8435AB558488D5DA4AA1F318A9D3BFB7848E4BA29257279CA4673C62958E60`.
Installation did not start a game/server process or modify PNGs/Lua/player data.
In-game screenshot acceptance remains pending.
