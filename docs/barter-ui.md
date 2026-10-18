# Barter UI

Optional WARP patch **Barter UI (asset-based cards)** (`BarterUI`), for the
2025-07-16 Ragexe client. Restart WARP after installing updated scripts, retain
the existing patch selections, and add this patch. Build to a new EXE for testing.
The base UI works with guaranteed native Barter rewards. Crafting rates and
outcome totals require the matching server changes; rebuild/restart the map
server and repatch the client together. This enhancement adds no SQL migration.

## Appearance and controls

- The top-left title uses the opening NPC's display name, for example `Ashra`,
  for both ordinary and expanded barter shops. A script may retain its existing
  `close2; callshop "DonateShopUsables";` flow: the internal shop key is not the
  title. Direct barter NPC clicks are supported too. Long names are fitted
  before the close button. If the native name cache has no resolved name, the
  title falls back to `Barter`, never the previous window's title.
- The first `#` and all following text are hidden from the title: `Ashra#1`,
  `Ashra#2`, and `Ashra#usables` display as `Ashra`. Full NPC names and IDs remain
  intact for script references and shop identity. A name beginning with `#`
  has no visible prefix and uses the `Barter` fallback.
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
does not enable their corresponding patches. The BRTR crafting envelope adds one handler to the existing shared 0BF6 router.
Battle Pass/Gacha gameplay, menu icons, Lua, DATA.INI, VIP, ChatUI and Daily
Rewards are unchanged.

Only these packet dispatch entries change; their original targets and complete
native receive arms are verified before patching:

| Packet | Role | Original receive arm |
| --- | --- | --- |
| `0B78` | Ordinary barter catalog, 31-byte records | `00CA14EC` |
| `0B79` | Expanded catalog, 36-byte records and 12-byte materials | `00CA14FD` |
| `00CA` | Observe the result of this frame's pending purchase, then always run the original result handler | `00CA10EC` |

The v5 catalog bridges pass the dispatcher's original `EDI` (`CGameMode*`).
Native dialog packets retain the NPC GID at `+2DC`, including both `close2`
branches at `CBAF62` and `CBAFD9`. Two local observers at `C789B2` and `C8BF2E`
record the native `0090` contact GID and its game context before replaying
`MOV EAX,90`; registers, flags, packet bytes and native sends are preserved.
This covers direct barter NPCs that do not update the dialog GID. A changed
dialog GID supersedes the recorded contact; closing the barter clears it.

The title is copied once per accepted catalog from the native name cache
(`CGameMode+160`, map head `+164`, node key `+10`, string `+18`, resolved flag
`+AC`). Inline and heap strings up to 127 bytes are supported. Lookup walks at
most 64 tree nodes, never allocates or sends a name query, and does not run
during drawing. Cache memory and NPC/game objects remain unmodified. The
installer verifies the native dialog/contact/cache instructions before using
this build-specific layout. No global send or actor-name rendering hook is used.

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
Unknown or unsupported native catalog layouts delegate to the original handler.
No `0BF4` receiver or global text hook is replaced. `0BF6` retains independently
registered BPUI/GCHA handlers and adds BRTR through the same owned router. The existing
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

The v5 native suite executes the emitted x86 through the actual on-disk packet
dispatch entries. It covers both catalog formats and purchase encodings,
NPC dialog/contact title selection, both contact bridges with original register
and flag preservation, catalog refresh, inline/heap names, long-name clipping,
missing-name fallback, cached drawing and close/reopen name changes,
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

Validate the changed Barter behavior and its packet-routing dependency. Use
`tools/test_barter_crafting_ui.py` for emitted native rate/outcome handling and
`tools/test_barter_packet_route.py` for protocol ownership, absent-feature/stock
fallback and register preservation. Check standalone and both combined patch
orders. Reuse accepted evidence for unchanged features; do not rerun unrelated
Battle Pass/Gacha gameplay suites. Preserve accepted manifests and compare
unrelated files against starting hashes.

Keep the installed EXE until in-game acceptance confirms opening both shop types,
buying a low-value item, insufficient-material/zeny feedback, close/reopen,
map change/relog and the existing menu UIs. Offline rendering is not a live-game
screenshot or proof of live server behavior.

## Crafting chance (v5)

Set `Rate: 20` and optionally `Announce: true` on a server Barter listing.
Missing Rate is 100%; missing Announce is false. Each requested unit is a separate
attempt. Materials, Zeny, stock and weekly quota are consumed even on random
failure. Effect 154 accompanies success and 155 failure; bulk outcomes are
summarized per listing. The buying list uses `Attempts xN` below 100%, and the
completed status reports the actual successful and failed totals.

Both catalog and buying-list cards show `Rate: N%` at the top right. The palette
runs from 100% green through 80% light green, 60% yellow-green, 50% orange,
40–30% deeper orange, 25–10% red, and <=5% deep red. Text uses the private Barter
renderer; shared description rendering is unchanged.

BRTR v1 uses magic `0x52545242` at offset 4 in the framed 0BF6 envelope. A 12-byte
header contains opcode, length, magic, version=1 and kind. Kind 1 has a native
catalog FNV-1a fingerprint (u32), count (u16), reserved zero (u16), followed by
12-byte rows: index (u32), item ID (u32), percent (u16), reserved zero (u16).
Kind 2 has success and failure counts (u32 each). Exact lengths, versions, row
identities and totals are validated. New native catalogs reset all rates to 100%
for compatibility with legacy guaranteed servers; mismatched metadata is ignored.

Use the matching server and client together before enabling Rate below 100%.
See the server `doc/barter-crafting.md` for the complete YAML example and limits.
