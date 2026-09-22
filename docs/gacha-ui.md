# GachaUI v8 — DevSeara

Native 760x440 Zeny Gacha window adapted from the supplied Myth of Yggdrasil
video. Select **Zeny Gacha UI with Pity** (`GachaUI`, patch 10006). This patch
requires the matching GCHA map-server bridge and NPC; it is not script-only.

## v8: centered winner names without hover popup (September 15)

Removed the duplicate name-hover strip and its state/cursor handler. Winner
names are centered horizontally in their yellow card strips using the measured
width of the fitted UTF-16 text. Canonical SQL names still use the private GDI
path, without admin/guild decorations. Top Spenders alignment is unchanged.
The v7 History surface-cache repair is retained. Client-only, same GCHA wire v4;
no server, SQL, asset or NPC changes. Installation details and backup:
`Outputs/gacha-ui-v8-20260915/DEPLOYMENT.md`.

## v7: History surface-cache repair (September 15)

Client-only; retains wire v4 and the installed v6 server. The shared PNG
compositor set the parent CSurface alpha-mode byte at +0x28. Gacha's first
opaque draw had already allocated six <=256px textures. Switching that byte
when History first drew its arrows made native 0x53F290 upload the whole
760x440 image to every small cached tile; 0x53EA90 then drew those textures
at the same origin. The result was a shrunken/overlapping window even though
the CPU canvas and window dimensions remained correct.

A Gacha-only wrapper now preserves the parent's original surface mode around
PNG compositing. Arrow alpha blending and the dirty flag remain intact.
No shared Chat/NPC drawing code, geometry, server, data, or protocol changes.
`tools/test_gacha_surface.py --expect-bug <old-exe>` reproduces the v6 native
upload/draw mismatch; normal mode verifies unchanged cached-tile rectangles
across History, pages 1/2/5/10 and all other tabs. It executes the real native
surface cache and traversal with only GPU texture APIs doubled. CPU-only
previews did not cover this boundary and were insufficient to catch v6.

Builds and installation status: `Outputs/gacha-ui-v7-20260915/DEPLOYMENT.md`.
Restart Ragnarok after replacing the client. No map-server restart is needed.

## v6: canonical names and ten-page History (September 15)

Requires matching GCHA wire **v4** client/server; earlier wire versions are
rejected. Packet sizes remain unchanged. In History, offset 668 carries page
1–10; browse request `count` carries the requested page (0 opens page 1).
For rolling messages, offset 668 retains its existing delay-ms meaning.

- Top Spenders and Grand Winners resolve the current `char.name` with a
  `char_id` join. Deleted characters show “Deleted character”; historical
  log text is never substituted for a missing canonical name.
- A private Gacha-only surface/font/GDI path draws and measures those exact
  UTF-8 names. Native actor tooltip rendering is not used. This prevents EXTN
  admin/guild decoration without editing or disabling the shared renderer.
  Hovering a name shows the private plain-name strip below the cards.
- Spender cards have no item-icon inset. The outer light-blue card remains.
- History exposes the newest 100 rewards, ten per page, ordered by log id.
  This is individual reward history, not ten grouped purchase batches.
  Both arrows and a page number are displayed; left is disabled on page 1,
  right on page 10. Empty pages remain accessible. Rapid page changes bypass
  the duplicate-view cache; requests are bounded on the server and client.
- The four supplied `arrow_{off,on}_{left,right}.png` files are bundled in
  `Assets/GachaUI`. Selecting the patch creates the target executable's
  `data/texture/<UI prefix>/genericsui` directory and copies missing files,
  preserving any existing customized files.

Builds, tests, offline previews and deployment status:
`Outputs/gacha-ui-v6-20260915/DEPLOYMENT.md`. No SQL migration, NPC modification,
price/pool/pity change or Git push. Independent Battlepass support is retained.
Live game acceptance still requires restarting both matching executables.

## Historical v5: sequential delivery and native capture crash fix

Requires matching **GCHA wire v3** client and map-server. Packet sizes and SQL
schema are unchanged; v1/v2 protocol peers are rejected. Update both together.

- Pull x1/x5/x10 resolves one slot at a time. Confirmation has no RNG, Zeny
  charge or hidden reward IDs. First reveal is scheduled after 1020ms; each
  subsequent slot waits 220ms after the prior delivery acknowledgement (plus
  network time and rounding to the 100ms UI timer). Unrevealed slots keep cycling.
- Action 6 carries the exact next slot index in `count`. Server deadline,
  index and in-flight checks reject early, skipped and repeated steps. Each
  valid step rechecks capacity, Zeny, proximity and locks before its own RNG
  and payment. There is no up-front charge or delivery of the whole batch.
- Message 7 reveals that slot's real icon, name and rarity before the matching
  inventory packet is queued. Message 6 follows successful delivery, pity and
  history writes and schedules the next slot. Message 4 ends the last step.
  All three use the same server-owned row ItemId; future rows have zero IDs.
  In messages 5/6/7, flags bits 16–31 are revealed count, row_count is total
  pulls, and reserved offset 668 is the next delay in milliseconds.
- Closing/cancelling/disconnecting preserves completed deliveries and leaves
  remaining pulls uncharged, with no future RNG. A delivery failure refunds
  only that slot; prior delivered items and pity remain. No automatic retries.
  History/ranking transactions cover only the newly delivered slot, avoiding
  duplicate batch logs. Existing normal server-save/crash limitations remain.
- The reported client crash at **00A46B1C**, ECX=0, was reproduced on v4 using
  the real native capture branch. Item right-down had acquired native left-drag
  capture; that branch never sends right-up and a later left-down cleared the
  owner immediately before the manager dereferenced it. Item inspection now
  tracks same-slot right presses without acquiring or releasing capture. It
  respects foreign capture and cancels on outside release/pointer departure
  or a fresh snapshot. Native left-button controls and title dragging retain
  their capture behavior. No shared item-description renderer is changed.

Builds and offline previews: `Outputs/gacha-ui-v5-20260914/`. See its
`DEPLOYMENT.md` for installation status and verified hashes. No SQL migration,
NPC price/pool/pity change or Git push is part of v5. Tests use explicit native
and SQL boundary doubles; live visual/inventory/relog acceptance is still needed.

The matching full-profile client, map-server, map-server-generator and Debug
symbols were installed September 15 after fresh stopped-process confirmation.
Installed hashes match the tested builds. Previous files are hash-verified in
`Outputs/gacha-ui-v5-20260914/rollback-20260915/`. Restart the server and game
manually for live acceptance; no processes were restarted by this update.

## Historical v4: interaction, delivery timing and names

Requires the matching **GCHA wire v2** server; update client and map-server
together. Old v1 clients/servers deliberately do not accept the new protocol.

- Correct native right-down/up slots are **32/33**, dispatched at A46ECD/A46F32.
  The old 26/32 pairing could never complete the same-icon click. Slot 26 now
  remains stock; tests enter the actual manager's indirect calls, not just the
  private functions. Featured, prize, history and delivered icons open native
  item descriptions. No shared item-description renderer is changed.
- Confirmation starts cosmetic reels with **no reward IDs, RNG, payment or
  inventory mutation**. They run 800 + 220 × count milliseconds. Cycling stops
  before sending the one-use completion action. The server enforces its own
  minimum deadline and repeats the complete preflight before RNG/payment/items.
  Final results appear immediately, with no second post-delivery animation.
  Closing/cancelling/reopening before completion spends nothing and cannot
  reroll a known prize because no outcome existed. A missing completion is
  never retried automatically; close/reopen after a network timeout.
- Pull controls are drawn/hit-tested only on Zeny Gacha. Information tabs do
  not show disabled placeholders. Server quotes also require the main view.
- Pending responses preserve the current frame/button colors. Confirmation
  remains visible until its reply, removing the stale-background/waiting-label
  flash. The normal hover/pressed feedback remains.
- Full character names have independent 128-byte packet fields. Winners use
  the full colored card strip; spenders use the full card width. Native hover
  exposes the complete name if it is too long to fit. The two Gacha SQL name
  columns are widened to VARCHAR(127) for this extended-name server.

Wire v2: request remains 32 bytes; snapshot is **3472 bytes**. Existing fields
keep their offsets; 12 × 128-byte names are appended at 1936. Message 5 starts
rolling; reserved offset 668 carries duration; action 6 requests completion.
Message 4 is final/delivered and must not start a client animation.

`Outputs/gacha-ui-v4-20260914/` contains the minimal/full-profile clients, Debug
map-server and map-server-generator builds, offline previews, `rollback/`
binary backups and `database-backup/` complete dumps of the two Gacha tables.
Name migration preserved all 214 log rows and the existing spender row.
The matching full-profile client, map-server and map-server-generator are now
installed. Client SHA-256:
`C038DC4952540CA04B42C51844F90A4E8C3954D96511831FE42EDDFD6F759740`.
Map-server SHA-256:
`1762AEB209ECF9A51576497D81DEC41D924BE2871D2BBF770C49AB00D901A74E`.
WARP settings/session were restored. No game/server processes were restarted
and no player Zeny was spent by testing. No Git push was performed.

The real `gacha_ui.cpp` process is tested by `tools/test_gacha_server.cpp`
against explicit SQL/native boundaries: no early rewards, early/repeated
completion, cancellation/reopen, post-roll inventory/trade/lock/proximity
changes, refunds/pity, rapid tabs, full names and logging failure. Both server
projects compile. Full-profile client suites cover Gacha, actual BPUI/GCHA
routing, Chat UI, chat controls/item icons and NPC dialogs. Live acceptance
still requires reopening the server/game and testing in-game.

## Historical v3: NPC-open routing fix

The live v2 executable contained Gacha code but its installed 0x0BF6 dispatcher
still pointed to Battlepass. Both patches independently wrote the same slot;
WARP's patch-record serialization could select either write. Their fallback
reads referenced the original stock handler, not the other feature. This made
the Gacha NPC appear to do nothing with no server error. Earlier tests called
the private Gacha receiver directly and therefore missed the actual routing bug.

`AutoCombatUI.nativeHelpers.registerPacket0BF6` now owns one global, tagged
dispatcher with separate BPUI and GCHA handler cells. Each feature registers only
its own handler. They remain independent windows, protocols, scripts and reward
systems; neither handler processes the other feature's data. Unrelated stock
messages retain the original fallback. Known custom messages for an unselected
feature are ignored safely. The existing 0x0BEF route is not changed.

Rebuild from the original client with the updated `AutoCombatUI.qjs`,
`BattlepassUI.qjs` and `GachaUI.qjs` together. Selecting AutoCombatUI is not
required. No server rebuild, database change or service restart is needed for
this routing fix; the game client must be closed before replacing its EXE.

`tools/test_packet_0bf6_route.py` tests the installed native dispatcher at
0x00CAD0EC: Gacha only, Battlepass only, both patch orders, and the full user
profile. The Gacha suite also now enters via that dispatcher, including the real
empty initial snapshot and fresh-session reopening. The original broken live
binary fails the new routing regression check.

## UI and resources

Light-blue/white frame, draggable title, server-priced x1/x5/x10 pulls,
confirmation modal, rolling then result reveal, 12 prize/result slots, personal
history, top spenders and Grand winners. The header shows server-owned Grand
and Major+ counters. Defaults are Grand within 100, Major-or-better within 10;
edit these in the server NPC, not in WARP. Grand resets both counters.

Historical v2 behavior (superseded by v4's roll-before-delivery flow above):

- Unopened cards cycle centered cosmetic icons every 100ms. They do not draw
  their reward icon, name, quantity or rarity before their reveal deadline.
- An 800ms lead-in is followed by one reveal every 220ms (first card at 1.02s,
  all 10 at 3.00s, rounded to the next UI timer tick). Icon/name/rarity appear
  together. Pull and browse controls remain disabled during the roll; X works.
- Cosmetic frames are independent of result IDs. `RollIcons` in the patch is
  only an animation palette, not the prize pool or odds. The server still owns
  the rewards and pays them immediately; inventory/chat may show deliveries
  while the cosmetic animation runs, as in the reference video.
- Right-click a featured or revealed item icon to open the stock item
  description. Works in results, prizes, personal history and Grand winners.
  Rolling/empty icons, ranking names, modal/pending states and cancelled clicks
  cannot open a reward early. Already revealed cards remain inspectable while
  later cards finish rolling.
- Right down/up must target the same icon slot. Fresh snapshots, closing and
  dragging cancel the click and release owned capture. Inspection sends no
  purchase request and never changes the server's pity, Zeny or rewards.

That v2 update was client-only and retained GCHA wire version 1: no new SQL, script
change or server rebuild is required for these two UI features.

The frame/cards/buttons are rendered by private native code. No new PNG folder,
DLL or WebView is required. Item icons use the existing client's ItemId lookup,
identified resource name and item BMP loader. Custom items still need correct
client itemInfo/resources; absent artwork safely leaves its icon area blank.

## Supported target and patch contract

Target: original `2025-07-16_Ragexe_175220998_clientinfo.exe` (20250716).
Apply from the original executable, together with the existing patch selection;
do not stack this onto an already patched executable. Other builds are rejected.

Original behavior has no GCHA window. The patch allocates a private native
UIFrameWnd vtable/state and registers its GCHA receiver in the globally owned
0x0BF6 dispatcher. BPUI and GCHA have distinct handler cells and a stock-message
fallback. 0x0BEF routing, global cursor behavior and shared item/name text
renderers are not replaced. The normal packet serializer sends 0x0BF8 requests.
`AutoCombatUI.nativeHelpers` provides shared assembler/native definitions;
AutoCombatUI itself does not need to be selected.

Profiled native boundaries include frame construction/destruction, draw,
mouse-down/up/captured movement, text metrics, item resources and cursor setter.
Private right-button vtable slots 32/33 use the existing mesitemicon description
path: construct an identified CItem, open native window 12, synchronously send
message 24, then destroy the temporary CItem. No shared description renderer is
patched. Native constructor/destructor and stock dispatch bytes are guarded.
Target-byte/vtable guards fail closed if their profiled contracts differ.
The cloned vtable retains its RTTI prefix. Only the title drags; release outside
a button cancels it. Timers are 100ms Windows UI-thread callbacks, stopped on
close/destruction. They redraw only for reveal/timeout work, not network polling.

Current wire version 3: `GCHA` magic 0x41484347; 32-byte request; 3472-byte snapshot;
12 rows of 96 bytes beginning at offset 672; pity fields at offsets 1824–1935;
full character names at 1936–3471.
Receiver bounds versions, lengths, row counts/tiers, views and pity denominators.
Server quotes are required for purchases; pending controls block double clicks;
timeouts never automatically retry a purchase. Hidden windows ignore late
updates. The `GachaUI.v5` marker locates an offline test contract, not an API
for third-party clients.

## Server and staged outputs

Server: `D:/AAARAGNAROK/rAthena/Ragnarok`.
Full configuration, SQL installation and runtime limitations:
`D:/AAARAGNAROK/rAthena/Ragnarok/doc/gacha_ui.md`.
NPC: `npc/custom/gacha_zeny.txt`; missing prize 40003 replaced with 501 (Red Potion).

`Outputs/gacha-ui-v2-20260914/` contains:

- `Gacha-test.exe`: minimal isolated test client, **not** the player's full setup.
- `combined/Ragnarok-gacha-test.exe`: test build from the saved current WARP
  selection plus GachaUI; existing client files were not replaced.
- `gacha-offline.png` and `gacha-offline-{rolling,rolling-next,stopping,revealed}.png`:
  offline rendered previews with actual client item artwork, **not** screenshots
  of a live server session.
- `reference/`: video frames extracted between 2 and 6 seconds for timing review.

The earlier v1 output directory retains its initial server Debug build.

`Outputs/gacha-ui-v3-20260914/` contains the corrected full-profile client in
`combined/Ragnarok-gacha-test.exe`, plus Gacha-only, Battlepass-only and both-order
routing test builds. The v1/v2 client builds predate the routing fix; do not use
them for deployment.

The verified v3 full-profile client was installed to
`D:/AAARAGNAROK/Ragnarok Online/Ragnarok.exe` after confirming Ragnarok was closed.
SHA-256: `70CFCCB191D13B1959B72B91B10770B5C9EF2E04D4ACB2EAAA033B1A694E83C3`.
The previous EXE was copied and hash-verified first at
`Outputs/gacha-ui-v3-20260914/client-backup/Ragnarok.before-routing-fix.exe`.
The installed file also passed the actual-dispatcher open/close/reopen regression
test offline. No services were stopped or restarted. Live NPC acceptance remains
for the user to confirm after reopening the game.

`LastSession.yml` and `Settings.yml` were restored after test builds.
The routing build does not import SQL or restart services.
No Gacha changes were pushed to GitHub by this update.

## Verification

```
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_packet_0bf6_route.py Outputs/gacha-ui-v5-20260914/combined/Ragnarok-gacha-test.exe --expect bpui,gcha
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_gacha_ui.py Outputs/gacha-ui-v5-20260914/combined/Ragnarok-gacha-test.exe --game "D:/AAARAGNAROK/Ragnarok Online"
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_gacha_capture.py Outputs/gacha-ui-v5-20260914/combined/Ragnarok-gacha-test.exe
```

Tests execute emitted x86 with explicit native/Windows transport/font/resource
boundary doubles. They cover bounded rendering and strings, malformed snapshots,
server quote/confirmation wire fields, double-click gating, sequential reveal,
title dragging, outside release, native hand cursor, late replies and actual
timer start/stop helpers. Real client GRFs can supply artwork without game writes.
v2 adds actual emitted-code tests for outcome-independent animated frames,
atomic reveal at every x1/x5/x10 boundary, timer wrap/failure/empty results,
click/capture cancellation, and CItem identity/identified flag/message/lifetime
at the native description-window boundary, including failed window creation.
They do not simulate a live socket, GPU driver, server database or character save.

Server `tools/test_gacha_pity.cpp` tests the actual shared configuration/tier and
quote methods, including exact base odds and 1000 worst-case sequential pulls.
Full Debug map-server compilation succeeded. In-game visual acceptance and live
DB/inventory/relog verification remain required before deployment acceptance.
