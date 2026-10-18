# Storage UI revision â€” October 13, 2026

The 2025-07-16 `StorageUI` patch now implements the approved 312-pixel-wide
preview. Reload WARP before applying it so all three UI scripts use the same
cursor router. This revision builds only the import-free Storage payload;
the user builds the client in WARP.

## Appearance and input

- `storageui/search.png` is drawn complete at its original size. The native
  editor uses a private draw override and fits inside the frame; it no longer
  covers the border or dropdown with the gray stock edit background.
- `refine_order_null`, `refine_order_down`, and `refine_order_up` use their exact
  supplied pixels. They select original order, highest refine first, and lowest
  refine first. Equal refine levels retain session order.
- List and seven-column block views repeat original 32-pixel background rows.
  Native 24-pixel item canvases are centered on those cells. Native grade, card,
  quantity and description rendering is retained. Hover uses the completed
  `inventoryui/selected_bg.png` frame; tooltip anchors follow the displayed cell.
- Quantity labels fit inside their 32-pixel cells through 30000, including
  three-digit stacks previously covered by the next cell. Native black text and
  its white outline remain. This applies to personal and guild storage, in list
  and block views, without changing the stored amount or transfer behavior.
- The grip changes height from 445 to 701 pixels in 32-pixel rows. Width remains
  312. A diagonal drag cannot widen the window or scale its shadows.
- Scroll controls are drawn and hit-tested only when the filtered view exceeds
  the available rows. Search, category changes and resizing clamp the scroll.
- Title X, footer Close, lock, refine order, list/block, sidebar tabs, dropdown
  entries, scroll controls and grip use the original Battle Pass hand bitmap.
  It respects occluding windows and releases its private surface on destruction.
- Native tab tooltips read Search, Usable, Weapon, Armor, ETC, Card, Ammunition,
  Costume, Shadow Gear, Pet and Cash. Refine hover reads `Sort Refine`.
  The transfer lock reads `Lock Storage Transfers` or `Unlock Storage Transfers`.
  View hover describes the destination: `Change to List` in block view and
  `Change to Block` in list view. Item tooltips retain the native CItem path.
- Sidebar and dropdown expose All Items, Usable, Weapon, Armor, Miscelleneous,
  Card, Ammunition, Costume, Shadow Gear, Pet and Cash. The newer artwork's
  unsupported Sticker row is omitted for this client.
- Weapon and Armor filters use the native item kinds `5` and `4`, respectively.
  This corrects their reversed contents in both sidebar/dropdown selection and
  list/block view. Knife belongs to Weapon; headgear and armor belong to Armor.

The lock defaults to unlocked and is local to this Storage session. It blocks
new item drags, Shift-right-click withdrawal, deposits and pending native deposit
events; ordinary right-click inspection remains available. It does not alter
server permissions, passwords or character data. This implements the suggested
transfer-lock interpretation of the requested lock/unlock control.

Custom control clicks have a separate capture/release path. They cannot enter
the stock window drag handler with an uninitialized drag mode. Queued commands
from hidden stock child controls are discarded. Intentional closes use the native
close event once while awaiting destruction; native server refresh/count and
destruction events remain active. Reopening resets the private state.

## Compatibility and verification

Inventory, Cart and Storage use `StorageInventoryCartCursorV3`. Each standalone
script can create the route. Opening a WARP tag replaces previous writes, so
every registration and removal re-emits all dispatcher bytes, handler cells and
three cursor calls. Fallback order is Inventory â†’ Cart â†’ Storage â†’ the original
native/Battle Pass entry. The Inventory and Cart payload files are unchanged.

`tools/test_inventory_cart_patch.cjs` tests every ordered subset, intermediate
selection, refresh, deselection/reselection and failed-apply cleanup using actual
WARP cache/assembler code and immutable original-source reads. The resulting
stubs pass 2,400 x86 routing scenarios, including registers, flags and stack.

`tools/test_storage_payload.py` relocates the current payload into emulator
memory over an existing profiled client. It checks exact artwork pixels, fixed
shadows, item coordinates, native factory/children/destructor, stale-item identity,
search/categories, refine sorting, scrolling, vertical resizing, cursor bitmap
pixels/capture/occlusion, rapid tab sequences, hidden-child command suppression,
close/reopen, native withdrawal/deposit and amount-dialog paths, and transfer
locking. OS, font, texture and game-mode boundaries are explicit test doubles.
The original CItem copy and relevant native client handlers execute as x86.

Asset installer tests preserve existing custom artwork and copy only missing
files. No asset pixels were changed. Accepted Battle Pass/Gacha sources, shared
renderers, server files, client EXEs, deployment profiles and Inventory/Cart
payloads retain their before-work hashes. Pre-existing stable-feature guard
differences remain unchanged; the accepted manifests were not updated.

Offline checks cannot establish live visual/gameplay acceptance. After building
in WARP, check rapid tab switching, reopen without relog, amount dialogs and
server-driven updates in the game. No client EXE was generated or deployed here.
