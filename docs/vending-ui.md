# VendingUI and Extended Vending

For **2025-07-16 Ragexe**, implemented in `D:\warp\WARP DAN LATEST\WARP-DAN`.
Restart WARP, select **Vending UI (market storefront and item currencies)**, and
patch the original client together with your existing patch selections.

The client uses the original `marketui` PNGs at their native 590 × 450 size:

- Seller setup: canopy and editable sign, two columns of listings, a cart-item
  pane, per-item price fields and quantity controls. Drag a cart item from
  **Sellable Items** onto the storefront slots to add it. Typing `1000000` displays
  `1,000,000`; editing, selection and paste preserve numeric values and caret
  positions. Prices clamp to the server's `vending_max_value`.
- Buyer: storefront and buying bag with centered item icons, `x35` quantities,
  total and Buy/Cancel. Drag a shop item onto **Buying List** to add it.
  Buy opens **Confirm Deal** with the total and currency.
  Only OK in that dialog sends the purchase; Cancel/Escape keeps the selection.
- Item clicks do not add or buy anything. Dragging a stack with more than one
  available item opens **Amount to vend** or **Amount to buy**, using a native
  input. Enter an amount and press OK/Enter; Cancel/Escape leaves the selection
  unchanged. A single available item adds directly. Repeated drags add to the
  existing row and can use only the remaining unselected quantity. Zero, invalid
  and excessive amounts are rejected. Dropping outside the destination, losing
  mouse capture or receiving a replacement shop snapshot cancels the operation.
  The server's vending-slot and stock limits still apply.
- Owner: remaining stock, depleted cards with the original `tag_sold.png`, and
  the last 16 sales. Sold cards retain their original slots for this open store
  session, including while browsing other vendors. They reset when your own
  store closes or a new own-store session starts.
- Eight listings fit without a scrollbar. Additional listings use the same
  scrollbar appearance and drag/arrow/wheel behavior as BarterUI. The cart,
  buying bag and history also scroll when their contents exceed the view.
  The Vending skill's server-side slot limit still applies.
- The store sign is centered and bold. Item hover shows name, quantity and
  unit price without the right-click instruction line.
- Currency selection uses a compact **List** dialog with item icons and a
  highlighted row. Click a row, then **OK**; Cancel exits without choosing.
- Drag the List title, storefront sign/canopy, or sidebar heading to move the
  window. Clicking the setup sign edits it; dragging the sign moves the store.
  Confirm Deal and the amount prompt have their own native frames and can be
  moved independently. Dragging an item does not move the storefront.
- Walking is blocked while VendingUI is visible or your own store is active.
  After both are closed, the original native movement checks apply. Clicking
  another vendor closes the previous buyer window and its confirmation before
  requesting the new shop.
  This replaces the shop being browsed; it does not close your own active store.
- Your own stock, SOLD cards, history and scroll positions are kept separately
  from the vendor you are browsing. Incoming own-store sales do not interrupt
  the remote buying list or confirmation. Cancel/Escape from the buying list,
  or submitting a confirmed purchase, returns to your latest owner view.
  While waiting for another vendor's response, your owner controls remain
  available. Only your own **Close Store** button sends a store-close request.
- Escape leaves your own active store window open. When visiting another shop
  while vending, Escape closes the visited shop and returns to your own store.
  For a player who is not vending, Escape dismisses the buyer window and removes
  its movement lock. Only **Close Store** ends your own vending so you can walk.
  Escape also cancels setup/currency selection, including while editing a price or title.
  If Confirm Deal is open, the first Escape dismisses only that confirmation.
  The first Escape also cancels an amount prompt or an item drag in progress.
- Each selected setup/buying card keeps its remove button inside the top-right
  corner and its minus/plus buttons inside the right side. Drawing and clicking
  use the same button coordinates.
- The reference layout keeps eight empty setup slots, four buying slots with
  the original plus artwork, and three sales-history cards. Setup shows the
  native cart count/capacity and weight/capacity; an empty buying list has a
  disabled Buy button. Item names, quantities, prices, and titles stay dynamic.
- Shift + quantity button changes 10; Ctrl changes 100. Right-click an item for
  its native description, including refine, cards, options and enchant grade.

Selecting VendingUI and applying the patch automatically creates the asset
folders beside the output EXE, using the same installation pattern as BarterUI.
All 31 bundled images are copied only when missing under the target EXE's
`data/texture/<client UI prefix>/marketui` and `genericsui` directories.
Existing artwork is preserved. If the output EXE is moved to the game folder,
copy its generated `data` folder too. The patch changes no other UI's code or assets.

## Required server installation

The matching implementation is already in the local server checkout at
`D:\AAARAGNAROK\Ragnarok`. The portable source patch is
`server/Extended-Vending-VendingUI.diff`; it excludes unrelated Daily Rewards
edits that were already present in that checkout. It is adapted for the current
server from the supplied Lilith / Easycore `Extended_Vending_V3.01.diff`.
Do not apply both diffs. Do not apply the packaged diff again to the already
modified local server checkout.

For the VPS, inspect/apply the source patch to its matching checkout:

```sh
git apply --check Extended-Vending-VendingUI.diff
git apply Extended-Vending-VendingUI.diff
```

Before starting the new server binary, apply
`sql-files/upgrades/2026-10-12-extended-vending.sql` **once to the game database**.
It adds `vendings.extended_vending_item` without deleting stores or player data.
If an older Extended Vending installation already supplied that column, inspect
the schema first: this implementation needs an unsigned 32-bit column, with
`0` for Zeny, `4294967295` for Cash Points, and actual IDs for item currencies.
The new server requires this column even with the UI disabled, because autotrade
save/load includes it. Fresh databases use the updated `sql-files/main.sql`.

Rebuild the map-server on the VPS. A script reload does not install C++ changes.
Deploy the matching patched client and server together, then restart map-server.
Windows server EXEs in the local test output are offline build evidence, not
Linux VPS binaries. No running server, database or installed client was replaced.

`conf/import/battle_conf.txt` imports `conf/import/extended_vending.txt`:

```text
vending_ui: on
extended_vending: on
extended_vending_cash: on
```

Use the normal **Vending skill**, choose the store currency, select cart items,
enter the title/prices/quantities, then press **Open Store**. This UI applies to
player vending. NPC ShopUI and BarterUI are separate patches.

## Editing currencies

Edit `db/item_vending_db.yml` in the server. The initial choices are Zeny, Cash
Points, TCG Card, Mithril Coin, Silver Coin and Copper Coin. The four item names
already exist in both server modes. Add or remove entries using item AegisNames:

```yaml
Header:
  Type: ITEM_VENDING_DB
  Version: 1
Body:
  - Item: TCG_Card
    Tax: 0
  - Item: Mithril_Coin
    Tax: -1
```

`Tax: -1` uses `vending_tax`; `0` disables tax; `250` means 2.50%.
`vending_tax_min` is measured in the selected currency's units. An optional
`db/import/item_vending_db.yml` overrides/adds entries by AegisName; remove a
currency from the base list to stop offering it. Reboot or reload the item DB
after changing currencies, with existing stores considered before removing one.

One currency applies to the whole store. Cash uses **Cash Points**, not Kafra
Points. Item payments use identified, plain, unbound, non-rental inventory stacks;
decorated/equipped currency items are excluded. Buyer funds and goods capacity,
seller currency capacity and weight, per-item stack limits and tax are checked
on the server before payment. Same-account Cash trades are rejected. Autotrade
restores the store currency. Native Zeny-only market searches omit non-Zeny
stores because that packet has no currency field.

## Implementation and validation

This patch uses a private, versioned `VNUI` envelope on server-to-client `0x0BF3`.
Other payloads on that opcode follow the original native receive arm. Requests
use the existing `0x0BF8` CustomUI transport with an isolated magic and fixed
32-byte framing. Battle Pass/Gacha `0x0BF6`, Daily Rewards `0x0BF4`, their state
and their native helpers remain unchanged. Opening, purchasing and closing use
the original vending request packets `0x01B2`, `0x0801` and `0x012E`.
The private movement wrapper replaces only the call at `0xC8F852` in the native
walk-request branch. It returns the stock blocking result while this window is
visible or the own-store cache is active, and otherwise tail-calls the original
helper at `0xC86150`. Other calls to that shared helper are untouched. A separate wrapper at `0xC8E636` disposes
the old buyer quote before the native `0x0130` request and replays its original
opcode load. Both sites have exact instruction-byte guards. The own-title
comparison at `0xC8E5F9` is stock again: owner access no longer relies on a title
which the server broadcasts only to nearby players (`AREA_WOS`). Native `0x0121`
still owns the cart summary; VendingUI reads its four values at `0x15FB2D4`.

Client sources and reproducible payload builder:

- `Scripts/Patches/VendingUI.qjs`
- `Scripts/Runtime/VendingUI/runtime.cpp` and `wire.hpp`
- `tools/build_vending_ui.py` → `Inputs/VendingUI/runtime.bin` / `runtime.json`
- `tools/test_vending_ui.py` and `tools/test_vending_asset_install.js`

The QJS validates the target date, native receive route, edit/frame vtables,
profiled instruction bytes, payload framing and CRC before installing its
private code and vtables. The runtime has no DLL imports. Only this window's
native edit draw wrapper formats its price input. The alpha surface mode is
initialized before the first texture upload and is not toggled during drawing.

The latest October 12 layout/dragging, owner/buyer lifecycle, Escape and item-control refinements are
client-only: restart WARP and repatch the original client with VendingUI, or use the staged
`Eitr-Vending-Enter-20261012.exe` under `Outputs/vending-enter-20261012`.
A server already running the matching
VNUI module needs no recompile or additional SQL for these refinements.

The earlier `Outputs/vending-exact-20261012/preview` directory contains all three
reference views rendered by that layout build's actual x86 drawing code, with
its bundled PNGs and client item BMPs.
It also includes selected buying and confirmation views. These are offline
renderer captures with example server data and native font/window boundaries,
not screenshots captured in a running game. Live testing remains required.

The duplicate-price fix selects the complete old input before calling the
native insertion routine at `0xA6EA10`. Previously it inserted `5,555` at the
caret into the existing `5555`, which compounded during redraws. Regression
checks now execute the original selection deletion, insertion and string code;
only external CRT memory copying is substituted in that test.

The quantity Enter fix handles event 0 in the private amount editor's vtable
slot 37. Native `UIManager::Enter` (`0xA2E270`) sends this event to the focused
editor; the original `UIEditCtrl` handler (`0x82C4E0`) clears the input through
`0xA70950` before cursor polling. The private handler reads and validates the
amount first, consumes the event, and preserves invalid input for correction.
Other editor messages and price/title editor behavior still use the original
handler. Cursor polling no longer submits quantities. Both selling and buying
use this path, including typing 15 when exactly 15 remain without an intervening
redraw. Enter only selects the quantity; purchase confirmation remains explicit.

Amount, currency selection and purchase confirmation use the supplied
`genericsui/ok_out.png`, `ok_over.png` and `ok_press.png` artwork. A disabled
purchase confirmation uses `ok_off.png`. These four unchanged 44x18 PNGs are
bundled with VendingUI and installed by WARP with the existing missing-only rule.

Offline checks exercise emitted x86, exact native request packets, title/price
editing and caret preservation, all UI modes, pane clipping and scrollbar drag,
depleted-slot retention, currency OK/Cancel, purchase confirmation, item-instance
description fields, malformed snapshots, duplicate submission and asset install
preservation. Owner/buyer lifecycle checks also cover a sale during confirmation,
switching remote shops, restoring updated SOLD/history/scroll state, Cancel,
Escape, confirmed purchases, server-side own closure and late acknowledgements,
failed remote requests, movement locking and frame destruction.
Escape checks cover keeping the owner's management window open, returning from
a visited shop with updated stock/history/scroll, non-vendor movement restoration
and opening another shop, confirmation dismissal, setup editing and held-key
repeat suppression. Button checks compare
rendered borders, every clickable corner and adjacent outside pixels. A fresh
WARP build also verifies that all 31 installed assets match their bundled hashes.
Drag checks exercise captured down/move/up events, click/jitter rejection,
destination bounds, native selection replacement in the amount editor,
invalid/over-stock input, single items, repeated drags, slot limits, capture
loss, changed snapshots, amount cancellation and background own-store sales.
The quantity dialog does not send a purchase or open-store request.
The Enter regression executes the real native manager dispatch, edit event and
input-clearing code. It reproduces the old blank-field/range-error failure and
checks both modes, exact available stock, invalid amounts remaining editable,
late hidden-editor events, unchanged stock editor handling and no premature
purchase packet. Button checks compare all four states against the supplied PNGs.
The combined test client has 155 selected patches; the existing
ChatUI, VIP, Battle Pass, Gacha, Daily Rewards, ShopUI, BarterUI, packet-routing
and DATA.INI checks also passed. Server tests compile and execute the production
payment module and current preserved-feature harnesses with explicit offline
SQL/network boundaries. Current map-server, map-server-generator and char-server
builds are staged under `Outputs/vending-ui-20261012/preserved-final/server`.

The accepted September feature manifests already reported newer source before
this work; they were not rewritten. The new shared server integration was
reviewed separately and regression-tested. **Live acceptance remains pending:**
check the native edit/caret, all store views, item details, two-account payments,
tax, sold-out stock, close/reopen and autotrade after applying the SQL and matching
server/client builds. Offline rendering is not an in-game screenshot.

No commit, push, database migration or live deployment was performed.
