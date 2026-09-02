# Item Collection QJS contract

## Checkpoint — 2026-09-02

- Client and server source contracts are implemented; live acceptance remains
  required after rebuilding map-server and repatching the client.
- Search is a native `UIEditCtrl` child. No `GetAsyncKeyState`,
  `DispatchMessageA`, recv hook, or DLL input bridge remains.
- Combo-member deposits resolve the owning Combos storage (Storage 11);
  Items-tab deposits continue to resolve the individual Items storage
  (Storage 10).
- The first tab is now a general Items catalog. Its dropdown selects All, Card,
  Weapon, Armor, Shield, Headgear, Garment, Shoes, Accessory, Consumable, Etc,
  Ammo, Pet, Shadow, and Cash without changing the 5x3 browser geometry.
- Schema-changing navigation hides stale payloads. Same-page item/combo SELECT
  keeps the current rows visible and updates local focus immediately, removing
  the brief selection flicker. Mutations remain single-flight.
- Empty filter results exit selection resolution before its decrementing loop.
  This fixes the Combo Collections -> Ready access violation at `0x01C6F8E7`
  when `rowCount=0` and a prior combo ID was still cached.
- Snapshot-pending pages draw the supplied 166x124 `chrome/loading.bmp`
  NOW LOADING frame instead of request text. The supplied ACT/SPR pair is
  staged and deployed as the authoritative animation source.
- A native Item Collection menu child occupies control-row column two beside
  Auto Hunt in both RO Global New UI and Classic UI. Six active BMP states,
  hit testing, tooltip, reopen, visibility, and either patch order are gated.
- The scrollbar supports wheel paging, arrow clicks, track page-up/down, and
  pointer-local thumb dragging. Its 24-pixel thumb is clamped to Y=128..456 and
  cannot overlap the down arrow beginning at Y=480.
- The isolated and AHUI/PINC coexistence builds below pass source, router,
  allocator, native-edit construction, and PE integration gates.

## Ownership and opener

- Client patch: `Scripts/Patches/ItemCollectionUI.qjs`.
- Target: 2025-07-16 Ragexe, 32-bit.
- Native host: 760x540 `UIFrameWnd`, opened with `/itemcollection`.
- The map server owns validation, storage mutation, Zeny, persistence,
  collection progress, combo activation, revisioning, and all snapshots.
- The QJS client renders snapshots and forwards explicit actions. It contains
  no collection rules and installs no DLL, recv hook, or API detour.

## Asset paths

- Fixed chrome and controls:
  `data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\item_collection\`.
- Dynamic art:
  `data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\collection\<identified-resource>.bmp`.
- Stock icon fallback:
  `data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\item\<identified-resource>.bmp`.
- Resolution is `ItemId -> CItemInfoMgr -> identified-resource std::string
  at node+0x58 -> collection\%s.bmp`.
- Dynamic 75x100 art is opaque. If it is absent, the renderer centers the
  item's stock icon; only then does it use `fallback_question_mark.bmp`.
  Irregular controls use exact `#FF00FF` color-key drawing.
- The WARP asset-copy choice defaults to enabled and is persisted. The patch
  creates the `item_collection` icon directory and copies all 15 category
  BMPs, the loading BMP, and its ACT/SPR source pair. It also copies six Item
  Collection menu states into
  `uirenewal\menuicon`; source verification requires every deployed file.

### Generated live client data (outside Git)

The 2026-09-01 checkpoint also has generated files in the live Banquet client
tree. They are intentionally not proposed for the WARP or server commits:

- 1,852 `collection\*.bmp` files, all verified as 75x100, 24-bpp BI_RGB;
- 399 canonical `item\<identified-resource>.bmp` card icons, byte-identical
  to the stock unnamed-card icon (SHA-256
  `729E6E133BDB62FE36DBD30C831CCF93F0B76183739ED0AEC45ED9205624E64F`);
- 67 fixed runtime files under `item_collection\`, including 15 native
  category icons plus `loading.bmp`, `nowloading.act`, and
  `nowloading.spr`; and
- ten user-approved New/Classic Item Collection menu-button BMPs under
  `uirenewal\menuicon` (six active states plus four compatibility aliases); and
- the CP949-authoritative `SystemEN\itemInfo_prerenewal.lua`, SHA-256
  `C37DF7C36BC31D0135C303DEA4CF7056803671FEE66382F4BCBC7813F5F4F52E`.

Recovery manifests/backups remain under
`_codex_backup\iteminfo-cardbmp-20260831-144358\` and
`_codex_backup\item-card-icons-20260831-153206\`.

## Native menu button

Item Collection publishes a menu bridge containing its toggle request and a
shared visibility cell. `ROGlobalZeroMenu` creates a real native `UIButton`
child in the second permanent control-row column, immediately beside Auto
Hunt. New UI uses 45x41 normal/mouse-on/pressed states; Classic uses 32x34
states. Both retain stock draw, tooltip, child ownership, hit testing,
destruction, theme refresh, menu close/reopen, and map-change layout repair.

The button child uses ID `0x3F4`; Auto Hunt retains `0x3F2`, and the Item
Collection top-level frame moved to `0x3F3`. An indirect request cell permits
Item Collection and RO Global Menu to be selected in either order. The two
order profiles produce byte-identical PEs. Show/Hide New Buttons recognizes
the same shared visibility cell when its bridge is available.

The ten user-approved button files are staged verbatim under
`Images/CollectionUI/source/menuicon`. The build script validates dimensions,
24-bpp BI_RGB format, and copies them byte-for-byte; it does not redraw or
transform the supplied art. The native child selects normal, mouse-on, and
pressed for each theme.

If WARP is applied to an already-patched full client, the build-time CACHE
handshake may no longer exist even though the native optional button and Item
Collection toggle still do. ItemCollectionUI therefore has a unique-signature
fallback that reconnects the request/visibility cells. Ambiguous matches are a
hard error. For an existing binary, `tools/fix_item_collection_menu_route.py`
creates a separate repaired EXE and never overwrites its input.

The 2026-09-02 supplied EXE had request cell `0x01C60F8C=0` and a valid
toggle at `0x01C83060`. The repaired copy changes only that route, the
visibility byte, and PE checksum. `verify_item_collection_menu_button.py`
confirms the repaired indirect target begins with `PUSHFD/PUSHAD`.

## Empty-filter crash gate and loading state

The selection resolver used a decrementing `ECX` loop after clamping the
maximum row count, but did not reject zero. A Ready filter with no matching
combos retained a local parent combo ID, entered the loop with `ECX=0`,
underflowed to `0xFFFFFFFF`, and scanned 400-byte rows beyond the payload.
The injected sequence now performs `TEST ECX,ECX / JE selection_done`
before either the 100-byte Item or 400-byte Combo loop.

The loading UI uses the opaque 166x124 BMP safety frame at logical
`(179,234)`. Native ACT/SPR construction is intentionally not introduced into
the QJS-owned frame lifecycle; the supplied sources are retained and deployed
without mutation.

## Category dropdown

The previous/next selector is replaced by a text-only 170x23 choice field and
a 15-row white popup contained within the left browser pane, matching the
Reputation and Game Settings controls. Every item family occupies exactly one
row; there are no category icons or row dividers. The selected or hovered row
uses the stock light-blue choice highlight. The popup renders after
browser/detail content so it remains an overlay.

Category labels must use the native renderer's NUL-terminated mode. Passing a
fixed character count crosses into adjacent EXE-resident strings and produces
the repeated diagonal labels seen in the rejected first dropdown build.

An open popup owns the first mouse-down, matching the established Reputation
and Auto Hunt choice behavior. A row selection closes the popup and sends one
COUI navigation request; an outside click closes and is consumed so it cannot
activate the grid underneath. Tab changes and window close clear dropdown
state, and dropdown interaction releases native search focus.

Target-client RTTI confirms `UIReputeWnd` at vtable `0x00FE16BC` with draw
slot 20 at `0x005EB730`, plus `UIComboBoxEx` (`0x0102C810`) and
`UIComboBoxV2Wnd` (`0x0102CFF8`). The patch does not instantiate those child
classes without a complete constructor, message, and destructor profile; the
QJS-owned popup keeps the existing frame lifecycle and static bridge boundary.

### Shared text callback crash gate

The reported access violation did not execute Item Collection code. The native
Game Settings combo measured text through the shared extent bridge, whose
`findWide` helper called cached lookup address `0x019DA6D0`; that allocation
was all zero because its owner patch had been deselected in a later WARP GUI
apply. The proven-bad live EXE has SHA-256
`4CFC925D4F245E91243628BAFF26578DF502B1F620C1C010A56C91D1FA3516CE`.

Shared ExtName, Fluent Emoji, ItemColor, grade-config, static-refresh, and
cross-layer reapply state is now reusable only while its recorded owner patch
is selected. The emoji-only minimal state also publishes the missing lookup
stub through `lookupVir`, the field consumed by `buildFindWide`.

`tools/verify_shared_text_bridge_callbacks.py` follows the final PE from the
native extent call to `findWide` and rejects an empty or invalid lookup target.
The focused regression profile is
`profiles/item_collection_ui_renderer_coexistence_test.yml`.

## COUI v1 request

Client packet `0x0BF8`, fixed 64 bytes, little-endian:

| Offset | Type | Field |
|---:|---|---|
| 0 | u16 | packet ID |
| 2 | u16 | length = 64 |
| 4 | u32 | `COUI` = `0x49554F43` |
| 8 | u16 | version = 1 |
| 10 | u16 | message: OPEN=1, NAVIGATE=3, MUTATE=4, RESYNC=6 |
| 12 | u32 | request ID |
| 16 | u32 | known revision |
| 20 | u16 | tab: Items=0, Combos=1, Totals=2 |
| 22 | u16 | packed filter: progress low byte, Items category high byte |
| 24 | u16 | zero-based page |
| 26 | u16 | action: select=1, deposit=2, deposit-all=3, withdraw=4, activate=5, deactivate=6 |
| 28 | u32 | item/combo target ID |
| 32 | u32 | quantity |
| 36 | char[28] | NUL-terminated ASCII search query (27 characters maximum) |

The search field is a native `UIEditCtrl` child owned by the Item Collection
`UIFrameWnd`. Clicking it invokes the stock
`UIWindowMgr::SetFocusEdit` path, transfers focus away from chat, and inherits
the client's caret, selection, keyboard/IME routing, Backspace, and held-key
repeat. The QJS draw helper reads the value through `UIEditCtrl::GetText`,
copies at most 27 bytes into the fixed query buffer, and submits after a 250 ms
quiet period. Clicking any other collection control or closing/destructing the
window clears native edit focus. The complete 28-byte buffer is copied into
every COUI request.

The category byte is 0 All, 1 Card, 2 Weapon, 3 Armor, 4 Shield, 5 Headgear,
6 Garment, 7 Shoes, 8 Accessory, 9 Consumable, 10 Etc, 11 Ammo, 12 Pet,
13 Shadow, and 14 Cash. Combos and Totals always send category 0. Progress
filters remain 0 All, 1 Missing/Incomplete, 2 Partial/Ready, and
3 Completed/Active, preserving the frozen COUI v1 request size.

## COUI v1 snapshot

Server packet `0x0BEF`, maximum 1556 bytes. Common header is 56 bytes:

| Offset | Type | Field |
|---:|---|---|
| 0..19 | | packet ID, length, magic, version, message=2, request ID, revision |
| 20 | u16 | tab |
| 22 | u16 | filter |
| 24 | u16 | page |
| 26 | u16 | page count |
| 28 | u16 | row count |
| 30 | u16 | capabilities |
| 32 | u32 | current count |
| 36 | u32 | total count |
| 40 | u32 | selected ID |
| 44 | u32 | Zeny |
| 48 | u32 | mutation result |
| 52 | u32 | reserved |

Capabilities are enabled `0x01`, items `0x02`, combos `0x04`,
account-bound `0x08`, storage-ready `0x10`, multiple-storages `0x20`,
and snapshot-truncated `0x40`.
`STORAGE_READY` gates card deposit/withdraw controls on both the Cards and
Combos tabs. Combo browsing, activation state, and Totals remain available
from cached collection/SQL state.

Payload at offset 56:

- Items: up to 15 rows x 100 bytes. `itemId+0`, `deposited+4 u16`,
  `required+6 u16`, `flags+8`, `depositFee+12`, `withdrawFee+16`,
  `name+20 char[32]`, `bonus+52 char[48]`.
- Combos: up to 2 rows x 400 bytes. Header is 112 bytes:
  `comboId+0`, `flags+4`, `cardCount+8 u16`, `name+12 char[32]`,
  `bonus+44 char[64]`; six member rows x 48 begin at +112.
- Totals: up to 20 rows x 64 bytes: `flags+0`,
  `label+4 char[32]`, `value+36 char[24]`.

Item flags are complete `0x01`, partial `0x02`, can-withdraw `0x04`;
the authoritative category occupies bits 8..11 (`0x00000F00`).
Combo flags are ready `0x01`, active `0x02`, selected `0x04`, and
row-truncated `0x08`.

The Items browser remains 5x3. Tile shells and selection outlines are drawn
in a complete first pass; names, full 75x100 art, badges, and the count band
are drawn in a second pass. This prevents a later row background from
overpainting an earlier row's deposited/required count. The Combos browser
uses two 177-pixel groups per page and draws each visible member's complete
75x100 art; six-member groups retain the explicit `+1 more` summary while the
detail pane lists all six members.

Each required-card line in the Combo detail pane is independently selectable.
The client retains both the stable parent combo ID and the selected member item
ID. Quantity, Deposit, Deposit All, and Withdraw target the member item ID;
Activate/Deactivate continues to target the combo ID. Combo-member mutations
reuse the same silent-storage transaction and save acknowledgement as Cards.
The client preserves the selected combo/member when the mutation snapshot
returns, even though the request target was an item ID.

Combo-tab card actions resolve the storage that owns the member through its
`Combos` list. They must not use the normal Items-tab resolver: the live
database places combo requirements in Storage 11 and individual card entries
in Storage 10, and many ItemIds intentionally exist in both catalogs.

Navigation is schema-pending: changing tab/filter/page/search clears ready and
row-count state before the request is sent, so a 400-byte Combo payload can
never be decoded as 100-byte Cards or 64-byte Totals rows. Mutations are
single-flight until the persistence acknowledgement arrives. Result 1 is
success; error results 2 through 14 have distinct client messages.
`NAVIGATE + SELECT` is the deliberate exception: it preserves the current
same-page payload while the clicked local selected index changes immediately.
The authoritative snapshot still confirms selection, but no blank loading
frame is inserted between the click and response. Schema-changing navigation
shows the NOW LOADING BMP until the authoritative snapshot arrives.

## Typography and numeric formatting

- Every collection label uses the stock direct-`TextDraw` pair `selector=0`,
  `height=11`. This is the same call ABI used by the native Inventory Zeny
  panel visible beside Game Settings. The previous `selector=1`, `height=12`
  pair selected a different, visibly smaller client font path.
- Only semantic headings use the native bold flag: window title, selected
  item/combo title, combo-group title, section headings, and the Total Bonuses
  heading. Buttons, statuses, values, counts, footer text, and body copy use
  regular weight, matching the Game Settings heading/option split.
- Zeny and deposit/withdraw fees are formatted client-side with comma groups.
  The formatter accepts one `uint32`, builds backward in a fixed 16-byte local
  buffer, and can emit at most 13 visible characters (`4,294,967,295`). It is
  locale-independent, uses no unbounded `sprintf`, and changes no COUI field.

## Renderer safety and x86 ABI

`FillRect` is `stdcall(window,x,y,width,height,color)`. It preserves
`EBX`/`ESI`/`EDI`/`EBP`, rejects null targets, negative origins, and
non-positive width/height before its `DEC/JNZ` loops. It clips horizontal
writes to `surfaceWidth - x` and vertical writes to `windowHeight - y`.
Progress widths are additionally clamped to their logical bar width.

The scrollbar rail spans Y=128..480 and the 24-pixel thumb travels exactly
328 pixels, ending at Y=456. Mouse-down on the thumb stores the pointer offset
without entering native window capture; mouse-move clamps visual thumb Y;
mouse-up rounds the final position to one page and sends at
most one navigation request. Track clicks page toward the pointer, arrows keep
their existing one-page behavior, and wheel paging is unchanged. Thumb and
arrow hitboxes are disjoint.

The source verifier audits every injected helper's save/restore or
`PUSHAD`/`POPAD` contract. Its paint oracle requires zero writes for `0/10`
and `0/3` progress and verifies right/bottom edge clipping, including
`x=759,width=10` and `y=539,height=10` in the 760x540 surface.

## Shared dispatcher

`AutoCombatUI.qjs`, `InGamePincodeUI.qjs`, and
`ItemCollectionUI.qjs` publish one canonical
`SharedPacket0BEF.Router.v3`. Its four cells are AHUI, PINC, COUI, and the
stock fallback. Legacy v2 state is migrated without dropping live handler
cells. Patch selection order must not change routing.

COUI snapshots are accepted only for the currently outstanding request and
must not regress the last accepted request or revision. A regressing snapshot
for the current request may update only a nonzero mutation error; it cannot
replace tab, page, selection, counts, or payload.

## Verification

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\tools\verify_item_collection_ui.ps1
powershell.exe -ExecutionPolicy Bypass -File .\tools\build_item_collection_menu_buttons.ps1
.\win32\WARP_console.exe -using .\profiles\item_collection_ui_test.yml
.\win32\WARP_console.exe -using .\profiles\item_collection_ui_coexistence_test.yml
.\win32\WARP_console.exe -using .\profiles\item_collection_ui_renderer_coexistence_test.yml
.\win32\WARP_console.exe -using .\profiles\item_collection_ui_menu_order_test.yml
.\win32\WARP_console.exe -using .\profiles\item_collection_ui_menu_reverse_order_test.yml
python .\tools\verify_shared_text_bridge_callbacks.py .\tmp\item_collection_ui_renderer_coexistence_test.exe
python .\tools\verify_item_collection_menu_button.py .\tmp\item_collection_ui_menu_order_test.exe
python .\tools\verify_item_collection_menu_button.py .\tmp\item_collection_ui_menu_reverse_order_test.exe
python .\tools\fix_item_collection_menu_route.py <patched.exe> --output <fixed.exe>
```

The all-item dropdown, asset-deployment, stock-icon-fallback, FillRect-safe,
unified-font, smooth-search, combo-member-action rebuild produced:

- isolated COUI: 16,166,221 bytes, SHA-256
  `1A1FB6B4E6C2492DE7580A8CA19D4291F35F8CBDF126DF44E9C2D1DC62D92F25`;
- combined PINC/AHUI/COUI: 17,640,269 bytes, SHA-256
  `349FA086DE50CEDB86D87936AEA6D2DE9F54B40CD28F49AF09C387607755F3A2`;
- renderer/PINC/AHUI/COUI: 21,507,917 bytes, SHA-256
  `D2F0F3D6F8F510D75E5CEC9BFA94DEECB2615B612AF496F43C95DD8305E2BBD0`;
- either menu selection order: 17,659,725 bytes, identical SHA-256
  `872AC821F45FE09F6C8D6B16FB7DF7135B2CD8DC355B5A5C7B4352DB26BE5B72`.

These prove source, allocator, router, and PE integration only. Live Ragexe
acceptance still requires 800x600 and larger layout, all 15 Item count bands,
two full-height Combo groups per page, six-member detail, drag/close/reopen,
all three tabs, all 15 item categories, collection-art and stock-item-icon
fallbacks, wheel/page bounds, Items and Combo-member
deposit/withdraw, combo activate/deactivate, selected-member highlighting,
`0/10` and `0/3` progress, grouped Zeny/fees, Zeny refresh, native-UIEditCtrl
typing/debounce, chat-to-search focus transfer, focus cleanup, pending mutation
lockout, rapid tab switching, and coexistence with Auto Hunt and PIN.
Live menu acceptance must cover New/Classic switching, both custom buttons,
hover/press/click, close/reopen, map change, and Show/Hide. Scrollbar acceptance
must cover thumb drag, both track directions, arrows, wheel, first/last page,
and no item-selection flicker.
