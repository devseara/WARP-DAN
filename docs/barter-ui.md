# Barter UI

Optional WARP patch **Barter UI (asset-based cards)** (`BarterUI`), for the
2025-07-16 Ragexe client. Restart WARP after installing updated scripts, retain
the existing patch selections, and add this patch. Build to a new EXE for testing.
No server rebuild, NPC rewrite, SQL migration or reward configuration change is
needed.

## Appearance and controls

- Original `barter/bg_buy.png` background at 619 × 410, with the supplied
  `box_top`, `box_mid`, `box_bot`, `item_main_bg`, `item_sell_bg`, `slot_box1` and
  `total_price` PNGs. Each item price uses the original 161 × 18
  `barter/itembox_00.png`, centered without scaling, including its baked-in Zeny
  icon. Shortage text sits below the price and above the card's bottom border.
  Buy, Cancel and the total stay inside the right panel.
- Two catalog columns with a vertical scrollbar. Select a card to add one unit
  to the Buying List; selecting it again scrolls to that existing entry.
- Buying List entries stack vertically, each with its own requirements, quantity
  and price. The mouse wheel, scroll arrows and draggable thumb scroll either
  list. Total, action buttons and panel title remain fixed.
- Requirements use one row of five for 1–5 materials, and two rows of five for
  6–10. Cards grow only when the second row is needed. Each quantity has its own
  line below the full 32px icon, with the original oval shadow asset. Extra
  material slots remain empty. Both lists support the full ten-item maximum;
  unexpectedly longer server lists are retained and accessible in the cart.
- Quantity controls: + / −, Shift for ten, Ctrl for one hundred. Reducing a
  quantity to zero removes that entry. Quantity is bounded by stock and 30,000.
- Hover for the client item name, quantity/required amount and inventory count.
  Right-click an item to open its native description. The server decides which
  inventory items can actually be consumed, including equipment/refine rules.
- Buy submits the entire buying list. Buy and list edits are disabled while a
  request is pending; requests are never automatically retried. Cancel, X and
  Escape close the shop. A failed purchase leaves the list available to edit.
- At most 100 different outputs per purchase, matching the server's duplicate
  output restriction. Remove an existing output before choosing another recipe
  for that same item.

The 44 × 18 buttons are the supplied PNGs, without scaling or replacement text:

| State | Buy | Cancel |
| --- | --- | --- |
| Normal | `genericsui/buy_out.png` | `genericsui/cancel_out.png` |
| Hover | `genericsui/buy_over.png` | `genericsui/cancel_over.png` |
| Pressed | `genericsui/buy_press.png` | `genericsui/cancel_press.png` |
| Disabled | `genericsui/buy_off.png` | `genericsui/cancel_off.png` |

Cancel remains enabled while waiting for a purchase. `cancel2_off.png` belongs
to a different 56-pixel button and is deliberately not paired with these states.

## Assets and installation

The 17 unchanged source PNGs are bundled under `Assets/BarterUI/`; their hashes
are recorded in `Assets/BarterUI/sha256.json`. Applying the patch copies **missing**
files beside the target EXE under `data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/`, preserving all
existing files, including customized generic buttons. Existing game files and
GRFs are not rewritten. Deploy those asset folders with the new EXE if the
destination client does not already contain them.

All required images are checked by the native window before opening, including
their original dimensions. If an image cannot be loaded, the complete original
barter receiver opens the stock UI instead of an unusable custom window.

## Isolation and protocol

This is an independent frame with private state, item hit boxes, text/icon/PNG
adapters and a cloned native frame vtable. Reusing patch-time helper emitters
does not enable their corresponding patches. No shared helper source, menu icon,
Lua file, DATA.INI loader, Battle Pass, Gacha, VIP, ChatUI, Daily Rewards or server
file is changed.

Only these packet dispatch entries change; their original targets and complete
native receive arms are verified before patching:

| Packet | Role | Original receive arm |
| --- | --- | --- |
| `0B78` | Ordinary barter catalog, 31-byte records | `00CA14EC` |
| `0B79` | Expanded catalog, 36-byte records and 12-byte materials | `00CA14FD` |
| `00CA` | Observe the result of this frame's pending purchase, then always run the original result handler | `00CA10EC` |

Outbound packets remain `0B0F` / `0B12` for ordinary barter and `0B57` / `0B58`
for expanded barter. The ordinary purchase inventory-index field is zero; the
current rAthena server resolves requirements from the recipe's shop index rather
than that field. The server validates affordability, eligible materials, stock,
weight and inventory capacity. Arithmetic is checked before constructing a
purchase. No prices, item IDs, quantities, sample recipes or rewards are invented
by the patch.

Catalog parsing validates the whole native receive buffer before changing state.
The local bound is 40,960 bytes and 1,400 records; packet size remains subject to
the server and native transport limits. Requirement lists are retained in full.
Unknown or unsupported layouts delegate to the original handler. No `0BF4`,
`0BF6`, custom feature receiver or global text hook is replaced. The existing
`CustomBarterZenySep` selection remains compatible; the new surface also formats
zeny with commas locally.

The read-only inventory view uses the profiled `CSession` at `015FA3C0`, list
`+16F0`, count `+16F4`, node payload `+8`, and CItem's numeric resource string
`+2C`, amount `+10`, refine `+60`. Native code at `D5AA40`, `D5ACB0`, `D5CE30`
and `811A70` establishes these offsets. It does not write to inventory objects.

## Build and validation

`python tools/build_barter_ui.py` builds the freestanding x86 payload with MSVC
`/W4 /WX` and no imports, and emits `Inputs/BarterUI/runtime.bin` and metadata.
WARP checks payload metadata, bounds, relocations and CRC before emitting code.

Run:

```text
node tools/test_barter_assets.cjs
python tools/test_barter_ui.py <staged-client.exe> --output <evidence-directory>
```

The v3 native suite executes the emitted x86 through the actual on-disk packet
dispatch entries. It covers both catalog formats and purchase encodings,
scrolling and thumb dragging, the five/six-material layout boundary, all ten
material slots, clipped icons and counts, fixed panel chrome, stock updates,
inventory reads, item descriptions, button art/state selection, duplicate clicks,
arithmetic overflow, fallback, Escape, destruction and stale input. OS/font/texture/network boundaries
are simulated; purchases never reach a live server. Render evidence uses the
original PNGs and client item BMPs.

Partially visible text, PNGs and item icons are staged on the existing native
surface before compositing through pane bounds. This keeps the original surface
handles and avoids passing negative/out-of-bounds coordinates to the native
item blitter. The staging area is restored before any clipped pixels are copied.
There is no shared render hook or change to another UI's clipping behavior.

Displayed inventory Zeny is read from the existing 2025-07-16 profile's
`015FBA90` address, also used by `ROGlobalZeroInventory`; it is never written.

Run the existing combined-client checks for ChatUI, DATA.INI, Daily Rewards,
Battle Pass, Gacha and VIP before releasing a new client. The older preservation
manifest already reports BattlepassUI/GachaUI differences from later accepted
updates; do not rewrite that baseline to silence it. Compare protected sources
against the task's starting hashes as well as running their native suites.

Keep the installed EXE until in-game acceptance confirms opening both shop types,
buying a low-value item, insufficient-material/zeny feedback, close/reopen,
map change/relog and the existing menu UIs. Offline rendering is not a live-game
screenshot or proof of live server behavior.
