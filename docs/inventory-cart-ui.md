# Native Inventory and Cart UI

`InventoryUI` and `CartUI` target the profiled **2025-07-16 Ragexe**.
Each patch is independently selectable under **STORAGE, INVENTORY AND CART**.
Select `InventoryUI` instead of `ROGlobalZeroInventory`.

The patches use the original `inventoryui` and `cartui` artwork and the shared
`storageui/storagelock.png` control.
The bundled files in `Assets/StorageInventoryUI` retain the supplied bytes.
The asset installer only supplies missing files next to the output EXE; it
preserves custom files already present. Missing or incompatible runtime artwork
leaves the corresponding native window available with its original presentation.

- Inventory: compact searchable grid using the Cart search/dropdown artwork, eight item
  categories on two pages, Favorites, native footer controls and live Zeny/weight.
  Minimum size is 280 x 296 with 30 visible slots; resizing honors the configured
  native maximum (at least the new minimum height).
- Cart: searchable, resizable grid, nine category filters, count/capacity and
  weight, scrolling and the original cart transfer and description actions.
  Minimum size is 280 x 296 with 36 visible slots. Its native item canvases are
  centered on the shadows, and its selection frame uses the same completed
  `inventoryui/selected_bg.png` as Inventory. The footer uses native
  `inventory/icon_weight.bmp` and `btn_resize.bmp` GRF resources.

Pet eggs/accessories use native client predicates;
costume and shadow equipment use item metadata and the original equipment masks.

## Integration boundaries

Each patch embeds an import-free x86 payload built from its own
`Scripts/Runtime/<Feature>/runtime.cpp`. The temporary DLL is a linker container,
not a runtime dependency. Rebuild the payload with its matching
`tools/build_<feature>.py` whenever its C++ source changes.

The window hooks keep a separate filtered view of the original session items.
Selection resolves the original slot and instance identity again before copying
the full native `CItem`. This preserves duplicate item IDs, cards, refinement,
grade and options, and rejects a displayed instance that changed before a click.
Changing a filter or viewport disables item selection until the updated grid has
been drawn, so clicks cannot act on an item that has not yet appeared.
The patches do not rewrite inventory/cart lists or originate transaction
packets. Original client handlers retain transfer amounts, item use, equip,
dragging, item descriptions and server checks.

Cart replaces only its own selector call sites. Inventory's selector
detour has an original-code trampoline and delegates when the custom inventory
is unavailable. Search editors use private virtual tables. Shared item-title and
grade renderers, packet routers, Battle Pass, Gacha and server code are not part
of these patches.

The patch scripts verify the target version, original hook bytes, virtual-table
entries, payload metadata and CRC before installing hooks. Unsupported clients
fail patch validation rather than receiving guessed addresses.

## Complete inventory adaptation (October 13, 2026)

Inventory and Cart search arrows open the same nine-entry menu: All Items,
Usable, Equipment, Miscelleneous, Card, Ammunition, Costume, Shadow Gear and Pet.
The requested spelling is retained. Inventory maps these entries around native
category 6 (Favorites), which remains on its sidebar. Both menus retain typed
search text and prevent item selection through the popup. Search borders and
arrows are sliced from the supplied `cartui/cart_bg.png`; the original assets
remain unchanged. Cart shares Inventory's costume/shadow/pet classification
rules and reads the final Inventory resize limits, including overrides.

The first page is All/Search, Usables, Main equipment, ETC and Cards. The arrow
switches to Ammunition, Costumes, Shadow equipment and Pet accessories/eggs;
Favorites stays visible on both pages. Main equipment excludes costume, shadow
and pet equipment, and ETC excludes ammunition and pet eggs.

The original child controls provide expansion, drop lock/unlock and comparison.
Favorites exposes the original NPC sale-lock and alignment buttons beside
comparison. The original handlers still own the option flags, timed sale-lock
popup and native sort (item type, then decorated title). Sale lock does not
prevent ordinary item use or inspection. The native game handlers enforce sale,
drop and transfer restrictions.

Dragging onto the star or Favorites grid adds a favorite; dropping a favorite
onto a category removes it. The adapter validates the original slot and item
fingerprint, translates the target to the hidden native tab and calls the stock
`0x00938650` handler. That handler owns the `0x0907` request and cancellation;
the adapter does not optimistically mutate the session. Replayed, stale and
out-of-target drops cannot issue another favorite change.

The grid retains native quantities and equipped indication. Original enchant
grade bitmaps 1 through 5 appear at the lower left. `icon_damaged.png` uses the
equipment damage flag; `rent_icon.png` uses the native expiration timestamp at
CItem +0x68, also consumed by Item Description's date formatter. Both badges fit
at the upper right when an item is damaged and rented. Native hover formatting,
refinement, grade, slot text and selected item data remain on the existing title
pipeline; only its conversion from inventory-grid to screen coordinates changes.

The panel reads native Zeny, current/max weight and weight-warning threshold,
with a weight-percentage tooltip. Count includes the native auxiliary lists and
respects CustomInventoryLimit. The native settings retain geometry/minimized
state and the underlying stock category; detailed category/page is retained on
window close/reopen within the same client process. A client restart restores
the corresponding stock category, rather than serializing a new settings format.

Inventory's custom layout now synchronizes the native expanded restore height
at window +0x110 with each non-minimized height. The native settings loader
interprets unequal saved current/restore heights as minimized, so leaving that
field stale caused repeated Alt+E close/reopen cycles to collapse the window.
Before loading existing settings, an expanded current height repairs its stale
restore height. An explicit 17-pixel minimized height retains the original restore
height and the native minimize button's behavior.

The supplied `inventoryui/selected_bg.png` has no right border. The renderer
completes its frame with mirrored pixels from its left edge and corners, without
modifying the original asset. The shadow remains visible inside the frame. Native
24 x 24 item canvases are centered at cell (16, 17), matching the shadow center;
the enchant-grade overlay moves with the item while damage/rental badges retain
their upper-right positions. The bottom-right resize grip uses the original
13 x 13 `btn_resize.bmp` GRF resource instead of a text slash. Its two-pixel
inset follows the window dimensions. A 15 x 15 corner hit area covers both outer
tips of the grip and uses the existing resize handler and size limits.

The required grade, weight and sort BMPs remain native GRF resources. When a GRF
omits `bt_sort_off*.bmp`, the existing sort button uses its available stock sort
art while preserving its command and tooltip. Missing required textures leave
the complete stock inventory available.

## Validation and deployment

Run the matching `tools/test_inventory_ui.py` and
`tools/test_cart_ui.py` against the newly patched EXE, with `--output` pointing to
a private render directory. These execute the emitted x86 with explicit doubles
for OS, fonts, textures and external client services. Their PNGs are emulator
renders, not live game screenshots. Inventory additionally executes the original
favorite-packet handler, sort, expansion/drop/comparison commands, sale-lock popup,
item-hover producer, stock factory and destructor. Texture/font/localization,
item string ownership, network transport and game-mode dispatch are explicit
boundaries. Inventory tests load native BMP bytes from the local Eitr `maindata.grf`.
The factory test executes 16 native settings save/load cycles over several window
heights, repairs a previously mismatched saved pair and checks explicitly minimized
settings. Pixel checks cover all four selection-frame sides and shadow retention;
the native item draw coordinates are checked against the shadow center.
Both suites exercise all nine dropdown entries, duplicate-instance selection,
combined text/category filtering, popup input exclusion and the last menu row
after resizing. Cart additionally checks both resize-grip tips, resized row and
column identity, size limits, weight/grip resources and all selection-frame sides.

Build each patch separately and in both combined selection orders. Run the
existing client regressions, including Battle Pass, Gacha, framed packet routing,
chat and the other installed native UI features. Follow
`docs/stable-battlepass-gacha.md`; do not replace a working installation or update
accepted baseline hashes merely because an offline suite passed.

Live acceptance must check real item artwork, descriptions, duplicate equipment
instances, search while receiving items, category changes, scrolling, transfers
with amount prompts, favorites/lock, reopening windows and the accepted Battle
Pass/Gacha flows. Stage the new client first, preserve the installed EXE/profile
and verify their hashes before any replacement.


## October 13: full search frame, fixed title icons, scoped hand cursor

Inventory and Cart now draw the complete 173 x 18 search frame from
`inventoryui/search.png` (source rectangle 35,11 through 208,29). Three slices
preserve both ends while extending the blank center; the 12-pixel native edit
stays inside the frame. Title bars also use three slices, retaining 17-pixel
ends at every window width. The item-shadow cells remain fixed at 32 pixels.

Both patches bundle the unchanged `battlepassui/Cursor_Hover.bmp`. Their private
26 x 22 alpha surfaces use its exact RGB pixels, with magenta made transparent.
The hand appears over Inventory categories, close/minimize, both filter arrows
and menu rows, Cart close, and both resize grips. It follows a captured resize
outside the panel bounds. Native topmost-window hit testing and capture ownership
keep it off obscured controls and unrelated windows. Each private GPU surface is
released when its panel is destroyed.

Only the three profiled cursor call sites (0xC75165, 0xD26DA0, 0xD27471) are
wrapped; the native/Battle Pass cursor entry at 0xA74410 is untouched. The two
patches register separate Inventory and Cart handler cells in one global tag.
The dispatcher checks Inventory, then Cart, then the original cursor entry.
Selection order and patch-record serialization order do not change the route.
Cleanup zeros a removed handler and removes the shared tag only when both
patches are deselected. Unknown source call-site modifications are rejected. Native 0x560E50 creates the private surface and 0x53EA90 submits it with
screen coordinates, size and ARGB modulation; there is no cursor child window.

`test_inventory_cart_patch.cjs` applies both real QJS modules to an existing PE
in memory, individually and in both orders. `test_inventory_cart_payloads.py`
loads the freshly compiled, relocated payloads into the native emulator against
an existing profiled PE. It executes the Inventory/Cart regression suites and
checks search pixels, resize invariance, cursor pixels, targets, occlusion,
capture and destruction. Allocation, fonts, textures and GPU rendering remain
explicit emulator boundaries. These checks produce no EXE. On this revision the
user requested payloads only; live GPU/cursor appearance still needs checking in
the client they build with WARP. No installed client, profile, Battle Pass/Gacha
source or accepted baseline was replaced.


## Cursor patch conflict correction

The earlier cursor-chain check incorrectly compared the source call bytes with
another patch's pending target. WARP reads the original image while collecting
independent patch records, so selecting Cart before Inventory reported
`Inventory/Cart cursor call mismatch, got E8 A6 F2 DF FF`. Those bytes are the
expected original call to 0xA74410 at 0xC75165.

The two QJS scripts now validate the source calls and put all cursor call writes,
dispatch code and handler cells in `InventoryCartCursorV2`, using WARP's global
tag mechanism. Native Inventory/Cart payloads and Battle Pass/Gacha sources are
unchanged. The QJS test uses the real WARP cache and assembler helpers, original
source reads and separate per-patch/global records. It reproduces the reported
failure from the prior scripts and verifies standalone/combined selections,
reverse serialization, deselection/reselection, and cleanup after a failed
application. `test_inventory_cart_cursor_router.py` executes the emitted x86
routing stubs with Unicorn, including register/flags/stack preservation and
forwarding to the native/Battle Pass entry. All checks are in memory and create
no client EXE. Restart WARP before retrying so it reloads the updated scripts
and clears the previous session's pending patch records.

## Cursor hover regression after the conflict fix

Reopening an existing WARP `BeginTag` removes that tag's previous staged writes.
The conflict fix reopened `InventoryCartCursorV2` to register a handler but wrote
only the handler cell. That erased the dispatcher code and all three call-site
hooks, so the resulting client kept using its original cursor. The hover bitmap
and native Inventory/Cart payloads were still present.

Both scripts now retain the dispatcher bytes and re-emit the entire shared tag
on every registration, route refresh and cleanup: both dispatchers, both handler
cells and all three calls. Addresses stay fixed while either feature is selected.
The QJS fixture now models `BeginTag` replacement, reproduces the missing hooks
from the prior scripts, and checks intermediate selections and repeated route
refreshes as well as both selection orders and removal/reselection. The native
dispatcher and existing hand-pixel/control tests run without writing an EXE.
Restart WARP and rebuild the client to pick up this script-only correction.
