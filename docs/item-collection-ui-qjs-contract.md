# Item Collection QJS contract

## Checkpoint — 2026-09-01

- Client and server source contracts are implemented; live acceptance remains
  required after rebuilding map-server and repatching the client.
- Search is a native `UIEditCtrl` child. No `GetAsyncKeyState`,
  `DispatchMessageA`, recv hook, or DLL input bridge remains.
- Combo-member deposits resolve the owning Combos storage (Storage 11);
  Cards-tab deposits continue to resolve the individual Items storage
  (Storage 10).
- Navigation hides stale payloads before changing row schema. Mutations are
  single-flight and result codes 2–14 have distinct client messages.
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
- Resolution is `ItemId -> CItemInfoMgr -> identified-resource std::string
  at node+0x58 -> collection\%s.bmp`.
- Dynamic 75x100 art is opaque. Missing files use the copied native
  `fallback_question_mark.bmp`; irregular controls use exact `#FF00FF`
  color-key drawing.

### Generated live client data (outside Git)

The 2026-09-01 checkpoint also has generated files in the live Banquet client
tree. They are intentionally not proposed for the WARP or server commits:

- 1,852 `collection\*.bmp` files, all verified as 75x100, 24-bpp BI_RGB;
- 399 canonical `item\<identified-resource>.bmp` card icons, byte-identical
  to the stock unnamed-card icon (SHA-256
  `729E6E133BDB62FE36DBD30C831CCF93F0B76183739ED0AEC45ED9205624E64F`);
- 49 fixed runtime files under `item_collection\`; and
- the CP949-authoritative `SystemEN\itemInfo_prerenewal.lua`, SHA-256
  `C37DF7C36BC31D0135C303DEA4CF7056803671FEE66382F4BCBC7813F5F4F52E`.

Recovery manifests/backups remain under
`_codex_backup\iteminfo-cardbmp-20260831-144358\` and
`_codex_backup\item-card-icons-20260831-153206\`.

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
| 20 | u16 | tab: Cards=0, Combos=1, Totals=2 |
| 22 | u16 | tab-local filter |
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

- Cards: up to 15 rows x 100 bytes. `itemId+0`, `deposited+4 u16`,
  `required+6 u16`, `flags+8`, `depositFee+12`, `withdrawFee+16`,
  `name+20 char[32]`, `bonus+52 char[48]`.
- Combos: up to 2 rows x 400 bytes. Header is 112 bytes:
  `comboId+0`, `flags+4`, `cardCount+8 u16`, `name+12 char[32]`,
  `bonus+44 char[64]`; six member rows x 48 begin at +112.
- Totals: up to 20 rows x 64 bytes: `flags+0`,
  `label+4 char[32]`, `value+36 char[24]`.

Card flags are complete `0x01`, partial `0x02`, can-withdraw `0x04`.
Combo flags are ready `0x01`, active `0x02`, selected `0x04`, and
row-truncated `0x08`.

The Cards browser remains 5x3. Tile shells and selection outlines are drawn
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
`Combos` list. They must not use the normal Cards-tab resolver: the live
database places combo requirements in Storage 11 and individual card entries
in Storage 10, and many ItemIds intentionally exist in both catalogs.

Navigation is schema-pending: changing tab/filter/page/search clears ready and
row-count state before the request is sent, so a 400-byte Combo payload can
never be decoded as 100-byte Cards or 64-byte Totals rows. Mutations are
single-flight until the persistence acknowledgement arrives. Result 1 is
success; error results 2 through 14 have distinct client messages.

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
.\win32\WARP_console.exe -using .\profiles\item_collection_ui_test.yml
.\win32\WARP_console.exe -using .\profiles\item_collection_ui_coexistence_test.yml
```

The FillRect-safe, unified-font, smooth-search, combo-member-action rebuild
produced:

- isolated COUI: 16,155,981 bytes, SHA-256
  `66424245318F459A44D4A55800F1815AC20C3B39DF6602FEB1E9ED15C19D673A`;
- combined PINC/AHUI/COUI: 17,630,029 bytes, SHA-256
  `C489226F02E61923644F35A36249E412B75FDF39509CCF9B9E4FE1405B79DEDD`.

These prove source, allocator, router, and PE integration only. Live Ragexe
acceptance still requires 800x600 and larger layout, all 15 Card count bands,
two full-height Combo groups per page, six-member detail, drag/close/reopen,
all three tabs, missing art, wheel/page bounds, Cards and Combo-member
deposit/withdraw, combo activate/deactivate, selected-member highlighting,
`0/10` and `0/3` progress, grouped Zeny/fees, Zeny refresh, native-UIEditCtrl
typing/debounce, chat-to-search focus transfer, focus cleanup, pending mutation
lockout, rapid tab switching, and coexistence with Auto Hunt and PIN.
