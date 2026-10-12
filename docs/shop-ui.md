# NPC Buy and Sell UI

`ShopUI` replaces the standard NPC Buy and Sell item lists on **2025-07-16 Ragexe** with a 619 x 410 window using the original Barter and genericsui PNGs. The existing NPC Buy/Sell chooser remains. This is an optional patch, independent of `BarterUI`, and requires no server changes.

## Enable and use

Restart WARP after updating its files and select **NPC Buy and Sell UI (asset-based cards)**. Keep your other patch selections and patch your original supported client. Copy the output EXE and its installed `data` assets together when moving it to another game folder.

- The two-column catalog and buying/selling list scroll independently. Use the mouse wheel, scrollbar arrows, or draggable thumb.
- Click a catalog card to add it. Click an already selected card to bring its entry into view.
- Use **+ / -** to change quantity. Hold **Shift** for 10 or **Ctrl** for 100. Decreasing to zero removes the entry; its **x** also removes it. The displayed number is not a keyboard input.
- Buy quantities are capped at 30,000 per item. Sell quantities also cannot exceed that inventory stack. At most 100 different entries can be submitted together.
- Hover over an item icon for its name, quantity and unit price; right-click it for the stock item description. Sell descriptions use the actual inventory instance, including cards, refine, grade, identification and options.
- **Toggle Item Amount** shows/hides quantities in the sell catalog.
- **Buy / Sell** submits once and closes the shop, as the standard NPC transaction ends that shop session. The client retains its original success/failure messages. Reopen the NPC to trade again.
- **Cancel**, the title-bar **x**, and **Escape** close the shop. No trade is sent by these controls.

All prices come from the server: the discounted buy price and the overcharged sell price. The server continues to validate price, inventory, weight, capacity and payment. The client does not award items or Zeny. Equal item IDs in different sellable inventory slots stay separate, and the patch rechecks each instance before a sale.

## Artwork

The patch bundles 21 original PNGs in `Assets/ShopUI`. The missing-only installer copies them to `data/texture/<client UI folder>/barter` and `genericsui` beside the patched EXE. It never overwrites existing artwork or edits GRFs or `DATA.INI`. The asset hash manifest is `Assets/ShopUI/sha256.json`.

The backgrounds are `bg_buy.png` and `bg_sell.png`; compact cards use `box_top/mid/bot`, `item_main_bg` and `slot_box1`. Price fields use the original **`barter/itembox_00.png`**, with its Zeny icon. Buy, Sell and Cancel use the original button states. There is no supplied `sell_off.png`, so disabled Sell is rendered in grayscale from `sell_out.png`.

If any required texture is unavailable or has an incompatible size when the server sends the shop list, the patch delegates to the stock shop window.

## Native implementation and isolation

Source: `Scripts/Runtime/ShopUI/runtime.cpp`; patch: `Scripts/Patches/ShopUI.qjs`; payload and metadata: `Inputs/ShopUI/runtime.bin` and `runtime.json`. Build with `python tools/build_shop_ui.py` using MSVC x86 and Python `pefile`. The freestanding payload has no imports and is embedded directly in the client; no runtime DLL is installed.

The patch validates the supported native code, payload checksum, relocation bounds and original dispatch entries before writing. Only these two original packet dispatch entries are replaced:

| Packet | Entry address | Original handler | Purpose |
| --- | --- | --- | --- |
| `0B77` | `00CACEF0` | `00CA10CA` | NPC buy list, 19-byte item records |
| `00C7` | `00CAA430` | `00CA10DB` | Sellable inventory list, 10-byte records |

Receiver adapters preserve registers and flags, then return to `00C9E1DD` when handled or resume the complete original arm on fallback. The frame has its own cloned vtable and ID `0x3EA`. Drawing helpers, item-resource lookup and text layout are private to this frame; no shared renderer is replaced.

Buy requests use native `00C8` with 16-bit quantities and 32-bit item IDs. Sell requests use `00C9` with 16-bit inventory indices and quantities. Cancel sends `09D4`. After a trade or cancellation the patch invokes the original CGameMode message `0x28`, preserving stock NPC/shop state cleanup; the verified native branch at `00C8760F` clears the mode's shop flag at `+0x24C`.

The stock `00CA`/`00CB` result paths are untouched. Barter's `0B78`, `0B79` and `00CA` hooks are untouched. Other patches' source, dispatch entries, archives, client settings and server files are outside this patch's scope.

The inventory layout is profiled from this client: linked list at session `015FA3C0 + 16F0`, count at `+16F4`, inline CItem at node `+8`, and inventory index at CItem `+4`. Sell entries retain an identity fingerprint over item ID, identification, refine, cards, grade, equip/protection and options. A changed or missing instance prevents submission until the list is refreshed. These offsets are version-specific; the patch must be re-profiled for another client.

## Verification

- `node tools/test_shop_assets.cjs` checks bundled assets and fresh, existing and partial installations, including no-overwrite and test-mode behavior.
- `python tools/test_shop_ui.py <patched.exe> --output <folder>` executes emitted x86 in Unicorn against bounded native/OS interfaces. It checks dispatch, server prices, packets, separate stacks, stale inventory, item descriptions, quantities, totals, clipping, scrolling, texture states, fallback and stock close-command invocation. It saves renders drawn by the compiled UI code using original assets.
- Build and test both patch orders with `BarterUI`, and run the existing Chat, Daily Rewards, Battle Pass, Gacha, VIP and DATA.INI regression checks on the complete client.

These are offline checks, not a live server session. Before deployment, test Buy, Sell, Cancel and reopening the NPC in-game, including multiple entries, quantities, insufficient Zeny, inventory limits and separate equipment instances. The stock server remains responsible for accepting or rejecting every transaction.
