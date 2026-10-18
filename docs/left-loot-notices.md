# Left-side item-obtained notices

`LeftLootNotices` (personal patch ID 10009) supports the 2025-07-16 Ragexe.
It displays at most five native item-obtained notices at the left edge. Newest
goes first; a sixth pickup evicts the oldest. Each notice lasts seven seconds
and fades during its final three seconds. Each pickup remains a distinct row.

The stack is 10 pixels from the left and starts one third down the viewport,
clamped to keep five rows on screen. Rows are 32 pixels tall with a 4-pixel gap.
Native measured text width is retained, with a 270-pixel minimum, bounded by
the viewport and a 1024-pixel maximum. Native clipped-text rendering handles
long decorated names. No new art files are required.

## Ownership and boundaries

Only five slots in the native `UINotifyItemObtainWnd` vtable at `0x0103274C`
change: destruction, position, timer, draw and message dispatch. All eleven
native pickup producers continue their existing `0x4C`, `0x24`, `0x22` message
sequence. The native message handler runs once. After `0x22` copies the CItem,
the original popup draw renders its native skin, item icon and formatted title
into its own DIB. The queue retains bounded pixel snapshots, never shallow
copies of CItems, strings, inventory entries or resource objects.

The native singleton remains owned by the UI manager. Expiry uses the existing
type `0x3A` close path, with deferred destruction. The destructor clears queue
ownership before calling the original destructor once. Unsigned elapsed-time
arithmetic handles GetTickCount wrap. No custom timers, threads, packets,
server changes, chat hooks or shared title-renderer hooks are introduced.

The window remains a root window (`parent+0x10 == 0`, `+0x78 == 0`). The native
manager renders its DIB directly through `0x53EA90` / `0x53F290`, which respects
the surface alpha flag at `+0x28`. Its child-only opaque texture path is not
used. No shared renderer change is needed for fading.

## Build and focused validation

Build `Scripts/Runtime/LeftLootNotices/runtime.cpp` with
`python tools/build_left_loot_notices.py --api-size 16`. The import-free x86
payload and metadata go in `Inputs/LeftLootNotices/`. The patch checks its CRC,
version, client, exports, relocations and native sites before hooking.

`tools/test_left_loot_notices.py` executes the compiled payload in Unicorn
with controlled native boundaries. It tests queue order, limits, fade, expiry,
clock wrap, ownership, surfaces and calling conventions. These checks do not
replace an in-game visual check of the installed client.

`tools/stage_left_loot_notices.py` applies the actual QJS patch to a staged copy
of the current client. It verifies preservation of existing bytes outside the
five vtable pointers and required PE allocation metadata, including the prior
weather/announcement placement fix, imports and overlay.
