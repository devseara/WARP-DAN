# TradeUI — 2025-07-16 Ragexe

Select **PLAYER TRADE → Trade UI (two panels and comma Zeny input)** in WARP.
Use the original supported client as the input and retain your other selected
patches. WARP does not need recompiling. This patch does not change the server or
require a server rebuild.

The window uses the original 548×428 `tradeui` artwork with ten item positions
on each side, Send/Receive panels, server-confirmed OK overlays, generic OK and
Cancel buttons, the Trade button, and the native Screenshot Trade option.
The partner name and level come from native trade state. Item sprites, amounts,
decorated names and item information use the original client CItem routines.

Zeny updates while typing: `1000` → `1,000`, `1000000` → `1,000,000`.
The private editor preserves the native caret/selection position while replacing
the complete formatted value. Enter performs the same first confirmation as OK;
it never also presses Trade. The native offer validation receives digits without
commas. The original one-billion per-entry client limit is retained, along with
the native balance clamp and server validation.

The editable amount uses native left alignment and keeps both digits and the
caret inside its 140×16 field. UIEdit `+F4` is vertical padding, not horizontal
alignment: stock OnDraw adds 2 and stores the text/caret Y in `+B4`. The earlier
width-based padding drew `5,555` at Y=105, below the field. TradeEditDraw now
keeps `+F4=0` (Y=2), retains live comma formatting, and lets the original editor
handle horizontal positioning, selection and scrolling.

Inventory drag-and-drop keeps the native item identity and native stack amount
dialog. Only the Send panel accepts a drop. Right-click maps each displayed item
back to its original native row. The title bar keeps native window dragging.
Trade is available only after both server-ready flags arrive, and repeated OK or
Trade submissions remain gated by native pending flags. Cancellation and the
final trade use stock GameMode actions and stock packets.

## Assets

21 unchanged source PNGs are bundled in `Assets/TradeUI`, with `sha256.json`.
After applying the patch, WARP installs missing files under:

```
<patched EXE directory>/data/texture/<native UI prefix>/tradeui/
<patched EXE directory>/data/texture/<native UI prefix>/genericsui/
```

Existing files are preserved. Copy the output `data` folder with the EXE when
moving it elsewhere. If runtime assets are missing or have incompatible sizes,
the exchange factory uses the original client window instead of displaying an
incomplete custom window. Ensure your normal client data/GRF loading settings
include these assets.

## Implementation and native evidence

`Scripts/Patches/TradeUI.qjs` validates the build date, payload CRC, original
instructions and vtable slots before installing the import-free payload.

| Native location | Purpose |
| --- | --- |
| `0x009C8FA0` | Registered exchange factory's constructor call; existing allocation is 0x14C bytes |
| `0x009A8A7A` → `0x009A8B5F` | Private-vtable creation branch; initializes the legacy frame and skips CUI-only slot 53 and field reads |
| `0x0088DA00` / `0x01031EDC` | Native UIExchangeWnd constructor and 53-slot vtable; required object size is 0x13C |
| `0x008A6900` | Stock controls and initial session-offer lists |
| `0x008C0EA0` | Stock offer, ready, confirmation and cancellation state machine |
| `0x008C0FD1`, `0x008C11AC` | Trade-only text retrieval call sites; adapters remove display commas before stock numeric validation |
| `0x00CA1D39` | Original incoming 0x00EC ready packet; finds window 0x271B and dispatches messages 0x33/0x34 |
| `0x00896110` | Stock single/stack item drop handling and quantity dialog |
| `0x008711A0`, `0x008972C0` | Unmodified native CItem sprite/amount and decorated name drawing |
| `0x00824FC0`, `0x0082C4E0` | Stock editor drawing/event functions; private editor intercepts Enter before native input clearing |
| `0x00A6EA10` | Real native selection deletion and insertion for comma formatting |

The factory selects the already-present UIExchangeWnd implementation, whose
native session data and messages match this client, and assigns private window
and edit vtables. Unrelated UI vtables and packet routes remain untouched. The
new surface replaces only layout/drawing/input presentation; it retains the
native transaction state machine. Native item-name functions are called as-is;
no shared name, grade, tooltip or TextOut hook is modified.

The initial build crashed when a deal opened: the native CUI factory called
virtual slot 53 at `0x009A8A8B` (stack return `0x009A8A91`), beyond the legacy
53-entry vtable. Merely extending the table would still be incorrect: the
following CUI code reads `+B4/+B5/+D4` as flags, while UIExchangeWnd uses those
offsets for child pointers and trade state. The corrected factory branch matches
only TradeUI's exact private vtable, sets window ID `0x271B`, runs native control
creation through TradeCreate, applies the layout and centers the window, then
returns through the native factory epilogue. Every other vtable, including the
missing-asset modern fallback, follows the displaced instructions and the full
stock CUI initialization path.

## Build and checks

Build the payload with `tools/build_trade_ui.py` using 32-bit MSVC and Python
`pefile`. It is compiled with `/W4 /WX`, linked without imports, and packed with
relocations, a CRC and source/payload hashes into `Inputs/TradeUI`.

`tools/test_trade_ui.py <patched.exe> --output <directory>` executes the emitted
x86 native factory, registration lookup, allocation, original frame/control
constructors and OnCreate, layout/formatting, native Enter dispatch, native confirmation
handler, incoming ready-packet arm, real text insertion and editor inset setup.
It covers repeated submits, pre-ready Trade gating, single/stack native drops,
all ten rows on both sides, repeated destruction/reopen and calling conventions.
The factory regression reproduces the original crash on the previous client.
Fallback and unrelated-window cases execute the stock slot-53 dispatch and
position/size/theme continuation, with modern artwork setup as an explicit
boundary. External graphics/font/database/OS functions and hidden BMP resource
pixels/dimensions are also test boundaries. Its screenshots
are **offline render evidence, not screenshots from a running game**.

`node tools/test_trade_asset_install.js` checks original hashes, missing-only
installation, existing custom artwork, test mode and filesystem failures.

`tools/test_trade_zeny_input.py <patched.exe>` executes the original UIEdit
GetText, OnDraw and slot55 layout. It captures only final graphics calls and
asserts the formatted number and caret fit inside the field. It covers native
progressive insertion, deletion, paste, comma handling, selection, focus loss,
the one-billion limit and digits-only submission. The previous client fails
its first case at `(3,105)`; the corrected client draws at `(3,2)`. Offline
previews now composite the editor's rendered child surface instead of adding
a separate sample amount that could conceal a native drawing defect.

The staged combined profile adds TradeUI to the existing 155-patch Vending
profile. Its compatibility run includes the 19 existing UI checks, TradeUI,
and the separate native Zeny input regression.
The stable-feature manifest already reports BattlepassUI.qjs and GachaUI.qjs as
changed against its older accepted baseline. This task leaves both byte-identical
to the pre-task copies and does not update that baseline or deploy the client.

Live two-player acceptance is still required: compare offering/one-ready/both-
ready states with the approved design; drag a stack in each direction; test
Zeny typing, paste, caret editing, Enter/OK, cancel, final Trade and screenshot
capture. No real items or currency were traded during offline validation.
