# Modern chat UI v9 - input actions, channel icons and tab fonts

Target: the profiled 2025-07-16 Ragexe. This supersedes the v8 textbox and
text-only tab behavior; native saved page names, filters, order, relocation,
detachment, docking and PM routing remain intact.

## User-visible changes

- The supplied `icon_emotion.png` opens the native Emoji List (Alt+L), matching
  the supplied screenshot. It does not submit the draft. This is not the
  Alt+M emote shortcut editor.
- The supplied `icon_direct.png` paper plane submits once through the stock
  Enter notification. Native command handling, PM recipient, history, input
  clearing and encoded item links remain the stock client's responsibility.
- Both input focus states use neutral translucent gray `0x80404040`, matching
  the settings/lock backing. No `textbox_on.png` or `textbox_off.png` is drawn;
  the supplied files are left untouched. The native edits retain their text,
  selection, IME and blinking caret. Their keyed background becomes the same
  gray, and zero-alpha black GDI caret pixels become opaque black.
- Recipient/message separation stays at x=108; text remains vertically
  centered and horizontally left aligned. Two disjoint 24px controls occupy
  `[width-51,width-27)` and `[width-27,width-3)`, at y=`height-42..height-22`.
  The message edit ends four pixels before those controls.
- Tab icons and labels are centered together, with a four-pixel icon/text gap.
  Main uses `icon_general`, Guild `icon_guild`, Party `icon_party`, and Market
  `icon_chanel`. `icon_pm` is reserved for PM/Whisper, never Battle. The left
  recipient indicator also changes to `icon_pm` when a recipient is entered.
  Battle and other renamed/custom pages remain text-only. Icon lookup uses
  exact case-insensitive native titles, not mutable tab indices.

## WARP configuration

Select **Supplied Renewal Chat UI** (`ModernChatUI`). Its inputs are:

| Input | Default | Scope |
| --- | --- | --- |
| Chat Tab Font | Tahoma | Docked tab labels only |
| Chat Tab Font Size | 12 | 8-16 pixel character height |
| Chat Tab Font Style | Normal | Normal or Bold |

YAML keys are `$modernChatTabFontName`, `$modernChatTabFontSize` and
`$modernChatTabFontStyle`. Font changes require repatching, not editing PNGs.
Rows remain 20px high. Measured labels are centered and clipped inside their
own tab partitions. The chat messages, input font, floating header and other
game UI fonts are not changed. Missing font faces follow Windows substitution.

One private HFONT is cached for the client process lifetime, using the native
surface-DC acquire/release pair (`0x5443C0` / `0x5446F0`). Every draw restores
the previous font, text color and background mode. GDI setup failure falls
back to the previous native 12px label renderer. No FONTAIN/global font table,
shared TextOut hooks, item-color renderer or enchant-grade logic is modified.

## Native action contract

The paper plane focuses `main+0xBC`, remembers it at `main+0xB4`, activates
native chat mode and calls `0x8FC220` with `(edit,6,0xB8,0,0,0)`. The actual
dispatcher reaches the stock submission branch at `0x8FD8E3`. The smiley
focuses the input, then calls the native UI manager factory `0xA39340` with
type `0x57`; that case constructs `UICashEmotionListWnd` via `0x78CE10`.
Both actions guard a missing edit pointer. Only mouse-down invokes them.

Versioned `ModernChatUI.v9` metadata in the patched image exposes the helper
addresses and selected font to the offline verifier, with no runtime file.

## Verification and build profile

The default build uses `Outputs/modern-chat-v9-profile.yml`, derived from the
user's current LastSession, including ClanBodySkins and NativeActJobPreviews.
The older checked-in full profile is not a replacement for that current
selection. A separate Arial/16px/Bold build verifies the alternate settings.
Original session/settings are backed up before console patching under
`Outputs/session-before-modern-chat-v9`.

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py Outputs/modern-chat-v9.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_controls.py Outputs/modern-chat-v9.exe --font Tahoma --size 12 --weight 400
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_chat_item_icons.py Outputs/modern-chat-v9.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_controls.py Outputs/modern-chat-v9-font-16-bold.exe --font Arial --size 16 --weight 700
```

The tests execute emitted x86 and native dispatcher/drag/routing instructions,
with explicit OS, GDI, surface and network boundary doubles. They check stack
and saved registers, every input-control edge, one submission per click,
PM/emoji identity, font caching/measurement/clipping/DC restoration, missing
GDI fallback, all 19 supplied PNGs, tab spacing, native detach/re-dock behavior,
and retained pickup/drop/item-link icons. They do not send game messages.

These checks are not in-game visual acceptance. Reopen the client and check
caret/IME alignment, click the smiley, send public and whisper messages using
the plane, verify item links, then detach and re-dock each native page.

## Deployment and recovery

Both WARP builds completed with no skipped patches; the four verification
commands above passed. The Tahoma/12px/Normal build and its matching `.epi`
and `.secure.txt` were installed as `D:\AAARAGNAROK\Ragnarok Online\Ragnarok.exe`
with the client closed. SHA-256:

`FA2E4F36BA4E9C6E7974CE0357B3237501BE9389450689C030BA67A171E8939F`

Hashes confirm all 19 supplied chat assets and `savedata/ChatWndInfo_U.lua`
were unchanged. Original WARP session selections and installed-client output
destination were restored after testing, with the new default font inputs.

Pre-update executable, both sidecars and saved chat Lua are backed up under
`Outputs/chat-ui-backup-20260914-v9`. The original executable SHA-256 is:

`8F9AAD42F4ECFBC8BC9A8BCBD51E246CE1C299BAA2CECDA41267306CCC8E711B`

To roll back, close the game and restore the executable plus both sidecars
from that folder. Do not replace newer PNGs or saved chat data unnecessarily.
