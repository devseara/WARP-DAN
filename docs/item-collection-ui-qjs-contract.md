# Item Collection UI contract and maintenance guide

Last updated: 2026-09-23. This is the single documentation source for the
Collection client, artwork, layout, protocol, build, verification, and deployment.
Runtime resource lists and coordinates are defined in `Scripts/Patches/ItemCollectionUI.qjs`;
menu integration is in `Scripts/Patches/ROGlobalZeroMenu.qjs`.

## Current behavior and ownership

- Target: 2025-07-16 Ragexe, 32-bit; 760x540 native `UIFrameWnd`, ID `0x3F3`.
- The real native menu child uses ID `0x3F4`; Auto Hunt retains `0x3F2`.
  `NewButtonVis.customRoute("Item Collection")` and `publishCustomButton`
  publish the request/visibility cells. The supported opener is the menu button.
- The map server owns validation, storage mutation, Zeny, persistence,
  collection progress, combo activation, revisioning, and snapshots.
- QJS renders snapshots and forwards explicit actions. No DLL, recv hook,
  message-loop detour, or collection-rule duplication is introduced.
- Search is a native `UIEditCtrl`; the tabs are Items, Combo Collections,
  and Total Bonuses. Existing item art and collection behavior are retained.
- Shared `ItemCollectionUI.nativeFrameV1` primitives retain their original
  implementation. Collection-only panel and text helpers own this skin,
  so Bestiary and other consumers are not restyled through shared callbacks.

The old diagnostics still name `/itemcollection`, but the current source has no
corresponding command-registration token. The legacy source verifier's slash-opener
assertion already fails on the pre-redesign baseline; this work does not add or
claim to repair that opener.

## Bestiary visual theme

Collection uses Bestiary's cool blue-white palette with the chibi Poring collector.
The original blue native title strip and readable stock font are retained.

| Surface | Color |
|---|---|
| Window body | `#F8FBFE` |
| Panels / borders | `#FFFFFF` / `#C5D1DC` |
| Normal button / selected button | `#F4F7FB` / `#DDEBFC` |
| Selected button highlight / selection outline | `#CCE1FB` / `#829ECA` |
| Main text / secondary text | `#254267` / `#243648` |
| Headings / muted text | `#426A9A` / `#75849B` |
| Progress / track | `#93B8E4` / `#EAF1F9` |
| Alternate row / hovered dropdown row | `#F3F7FD` / `#DDEBFC` |

`FillRect` writes ARGB pixels. Native `TextDraw` consumes BGR COLORREF;
`emitCollectionText` and `emitCollectionCenteredText` perform the same conversion
as Bestiary without changing the exported `emitText` ABI. Runtime labels are never
baked into button images. The earlier warm ivory/rose prototype is superseded.

## Native menu and hover label

The native `UIButton` retains stock drawing, hit testing, ownership, destruction,
visibility, theme refresh, menu recreation, and map-change layout repair. New UI
is 45x41; Classic is 32x34. Native active states are normal, mouse-on, and pressed.
The control occupies the next available menu slot after Auto Hunt when visible.

The active names are:

```text
bt_itemcollection_poring_{normal,mouseon,pressed}.bmp
bt_itemcollection_poring_old_{normal,mouseon,pressed}.bmp
```

Ten older `bt_itemcollection*.bmp` names remain compatibility assets. The installed
`update.grf` contains the old `bt_itemcollection_normal.bmp`, SHA-256
`F1237E65831FE93588EEF6DE114AB8C4D3218A17BA185358DB1CCE4FE54E5CBE`.
Replacing only the loose image at that name did not update the user's menu.
The six distinct Poring filenames avoid that packed-resource collision without
changing global loose-file/GRF priority. They were checked against every archive
in the installed DATA.INI priority list.

The existing `Item Collection` text uses native `ClientToScreen(0x00A1EF70)` and
`ShowTooltip(0x00A753D0)`, anchored at child-local `(0,-20)` above the icon.
The former right-side `width+16` placement is removed. Native tooltip styling,
visibility guards, receiver, nonvolatile registers, and `RET 8` are preserved.

## Native small close X

The close control loads the client's original resources, at native 11x11 size:

```text
basic_interface\sys_close_off.bmp  # normal
basic_interface\sys_close_on.bmp   # hover and pressed
```

Draw, hover, mouse-down, and mouse-up share `[744,3,755,14)` bounds. A release
outside the X cancels closing; adjacent title-bar pixels retain native dragging.
Close clears native edit focus and popup state, then hides the existing frame.
The prior 16x16 Quest UI close images are retained only as source references.
`Images/CollectionUI/source/native_close/sys_close_{off,on}.png` are lossless
preview decodes of the 11x11 indexed BMPs from installed `maindata.grf`; runtime
loads the original native names. No custom X is generated or scaled.

## Runtime resources

Fixed pack root:
`data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\item_collection\`.
Menu states deploy to:
`data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\uirenewal\menuicon\`.
The byte prefix `C0 AF C0 FA C0 CE C5 CD C6 E4 C0 CC BD BA` represents
`유저인터페이스` in CP949 and is surfaced as the Latin-1 directory above locally.

There are **65 Collection runtime files and 16 menu files**. The patch creates
needed subdirectories and copies the explicit `Assets`/`MenuAssets` lists.
The asset-copy choice defaults enabled and is persisted. Native close resources
come from the installed client skin and are not duplicated into the runtime pack.

All pack BMPs are 24-bpp uncompressed Windows `BI_RGB`. Irregular icons and
controls use exact `#FF00FF`; body, title, loading frame, and collection art are
opaque. The generated source PNG retains real alpha until final compilation.

| Asset family under `Images/CollectionUI` | Size / role |
|---|---|
| `chrome/title_bar_760.bmp` | 760x17; source `title_bar_470.bmp`, preserve x=0..59 and x=385..469, repeat x=60..384 |
| `chrome/bg_collection.bmp` | 760x523; `#F8FBFE` interior with blue-gray borders |
| `chrome/poring_small.bmp`, `poring_large.bmp` | 28x30 header / 108x116 Total Bonuses mascot |
| `chrome/buttons/btn_{out,over,press,disable}_{left,mid,right}.bmp` | 12 slices, each 6x20; runtime text |
| `chrome/loading.bmp` | Opaque 166x124 NOW LOADING safety frame |
| `chrome/nowloading.act`, `nowloading.spr` | Preserved animation sources; not instantiated by the runtime frame |
| `icons/icon_collection.bmp`, `badge_locked.bmp`, `badge_complete.bmp` | 16x16 title and semantic icons |
| `icons/category_*.bmp` | 15 families, 16x16 All / 24x24 item types; retained, not drawn by the text-only dropdown |
| `menuicon/bt_itemcollection*.bmp` | Six active Poring states and ten compatibility files, 45x41 / 32x34 |
| `reused/` | Stock source controls and missing-art fallback; provenance below |

Dynamic art resolves without a manual ItemId table:

```text
ItemId -> CItemInfoMgr -> identified-resource std::string at node+0x58
       -> collection\<identified-resource>.bmp
       -> item\<identified-resource>.bmp
       -> reused\artwork\fallback_question_mark.bmp
```

Collection art is drawn opaque at native 75x100. The stock item icon is centered
when collection art is absent. Dynamic art is never renamed or copied by the
fixed-skin builder, and render hooks do not parse itemInfo.lua.

## Layout

All coordinates are window-local pixels. The frame fits an 800x600 client with
20-pixel horizontal and 30-pixel vertical clearance. Scale is 1.

| Region | X, Y | Width x height |
|---|---|---|
| Title / body | 0,0 / 0,17 | 760x17 / 760x523 |
| Summary / footer | 8,24 / 8,508 | 744x32 / 744x24 |
| Browser / detail | 8,89 / 538,89 | 522x414 / 214x414 |
| Summary label / progress | 18,31 / 160,35 | 132x18 / 360x9 |
| Search edit / button | 548,31 / 718,31 | 170x18 / 26x18 |
| Items / Combos / Totals tabs | 8,62 / 116,62 / 248,62 | 108x23 / 132x23 / 108x23 |
| Category dropdown | 360,62 | 170x23; 15 popup rows, 18 pixels each |
| Header mascot / heading / caption | 539,56 / 574,59 / 574,73 | Mascot 28x30 |
| Totals mascot / caption | 591,192 / 548,324 | 108x116 / caption width 194 |
| Selected name / art | 548,99 / 607,126 | 194x18 / 75x100 |
| Metadata / bonus / fee | 548,236 / 548,292 / 548,365 | 194x42 / 194x64 / 194x18 |
| Deposit / Deposit All / Withdraw | 553,422 / 553,446 / 553,470 | 184x20 each |
| Native close X | 744,3 | 11x11 |

Items use a 5x3 grid: first art `(18,132)`, column pitch 96, row pitch 131.
Each shell starts five pixels before art X at `Y=114+row*131`, size 85x130;
selection outline is 87x132. Progress/count band is immediately below art.
Filters begin at `(13,92)`, width 96, pitch 101, height 20.
Combos use two groups at `Y=119+index*181`, each 177 pixels high; up to five
full-size member artworks are visible with a `+1 more` indicator for the sixth.
The detail pane lists all six. Quantity controls preserve the original hitboxes.
The scrollbar track is Y=128..480; the 24-pixel thumb travels to Y=456.
Panel corners use two-pixel steps through the existing clipped fill helper.

## Empty results and loading

The selection resolver tests row count before its decrementing loops. Zero-row
Ready results cannot underflow ECX and scan beyond the bounded payload.
Pending navigation draws `chrome/loading.bmp` at `(179,234)`; retained ACT/SPR
sources are not instantiated into the QJS-owned frame lifecycle.

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

The legacy source verifier contains audits of helper save/restore and
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

## Asset provenance and authoring

`reused/` contains 44 byte-identical stock-source BMPs copied on 2026-08-31.
The extraction used `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\maindata.grf`,
then SHA-256 `43E4237A7426F0CE4F93C666E650F6E03D46652743E4728375E29610F8B77BF8`.
This hash is historical provenance, not a claim about the current mutable GRF.

| Staged family | Files | Original source | Native format | State and text notes |
|---|---:|---|---|---|
| `buttons/generic/` | 12 | `maindata.grf::data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\basic_interface\btn_{out,over,press,disable}_{left,mid,right}.bmp` | Each tile is 6x20, 24-bpp RGB BMP | Original stock reference only; current runtime uses Collection-owned chrome/buttons. |
| `close/` | 4 | `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\uirenewal\questui\btn_close_{normal,mouseon,pressed,disabled}.bmp` | 16x16, 24-bpp RGB BMP | Quest UI reference only; current runtime uses the native 11x11 basic_interface close X. |
| `search/` | 5 | `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\uirenewal\questui\searchbar_bg.bmp` and `btn_searchbar_{normal,_mouseon,pressed,disabled}.bmp` | Field 121x18; buttons 26x18; 24-bpp RGB BMP | Blank search field plus complete magnifier-button family. The source hover filename intentionally contains the double underscore: `btn_searchbar__mouseon.bmp`. |
| `scrollbar/` | 14 | Track/thumb: `maindata.grf::data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\lapine\scrollbar_*.bmp`; arrows: loose `uirenewal\questui\btn_scroll_arrow_{up,down}.bmp` | Track caps 9x9, track middle 9x3; all thumb slices 9x3; arrows 9x12; 24-bpp RGB BMP | Tileable track plus complete out/over/press thumb states. Arrow bitmaps are icon-only and have one visual state each. |
| `steppers/` | 6 | `maindata.grf::data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\cashshop\btn_{plus,minus}_{normal,over,press}.bmp` | 19x8, 24-bpp RGB BMP | Complete three-state plus/minus family; no disabled state. |
| `currency/icon_zeny.bmp` | 1 | `maindata.grf::data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\basic_interface\rodexsystem\renewal\icon_zeny.bmp` | 28x25, 24-bpp RGB BMP | Icon-only Zeny bag/coin; no embedded label. |
| `status/badge_complete.bmp` | 1 | `maindata.grf::data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\achievement_re\badge_complete.bmp` | 20x30, 24-bpp RGB BMP | Completion ribbon icon with no embedded text. |
| `artwork/fallback_question_mark.bmp` | 1 | `maindata.grf::data\texture\유저인터페이스\collection\사과.bmp` (local path display: `...\collection\»ç°ú.bmp`) | 75x100, 24-bpp RGB BMP | Native question-mark collection artwork. Only the staged filename was normalized; pixel bytes are unchanged. Do not confuse it with `collection\apple_.bmp`, which is the real Apple artwork. |


The 15 category icons use native representative resources: Poring Card, Knife,
Cotton Shirt, Guard, Poring Hat, Muffler, Sandals, Rosary, Red Potion, Jellopy,
Arrow, Poring Egg, Beginner's Shadow Armor, and Battle Manual Box, plus the
original All icon. Card, Headgear, Ammo, Shadow, and Cash were losslessly converted
from palette BMP to 24-bpp BI_RGB. They define no membership or rewards.
The All source icon predates the new Poring title icon.

The previous supplied menu set came from `Downloads\New folder` on 2026-09-01.
Its filenames are retained for compatibility, but current pixels are generated
from `Images/CollectionUI/source/poring_collector.png`. `source/menuicon/` stages
the ten compatibility states; `menuicon/` also contains six distinct active names.

The master was generated with the built-in imagegen tool on 2026-09-23; no
fallback API/CLI was used. The compiler bounds alpha, resamples the original,
and converts the exterior to exact magenta only at final BMP output. Hover is
brighter, pressed is darker and shifts down one pixel, and disabled is grayscale.
The 16x16 title icon and two window mascots share the same source.

### Exact artwork prompt

Use case: stylized-concept. Asset type: a single production game-menu icon for Ragnarok Online's Item Collection, also reused as a tiny window mascot. Create one super-cute chibi pink Poring collector cuddling a compact deep dusty-blue collection album with cream pages, gold book-corner protectors, and a small golden diamond clasp. The Poring has a plump teardrop blob silhouette, two dark dot eyes, tiny happy mouth, rosy cheeks, and a soft white highlight. A single ivory collection card peeks out of the album. The album and Poring form one compact coherent shape. Style: authentic early-2000s Ragnarok Online inventory/menu sprite, hand-pixeled feel, crisp dark brown outer contour, small stepped shading clusters, warm cream highlights, pink/blue/gold colors. Friendly, cute, modest detail and readable even at 32 pixels. Composition: one centered isolated icon filling most of a square canvas with clear empty margins; all parts visible. Transparent background with real alpha, absolutely no checkerboard, no ground plane, no cast shadow outside the silhouette, no glow. No text, no letters, no UI panel, no border frame, no additional icons. This is for 45x41 and 32x34 game buttons, so prioritize chunky clean silhouette and very simple features.

## Build, preview, and verification

Run from the repository root. Python examples use the available local PE-analysis
venv; another environment with `pefile` and `unicorn` can run the same verifiers.

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\tools\build_collection_ui_assets.ps1
powershell.exe -ExecutionPolicy Bypass -File .\tools\verify_collection_ui_assets.ps1
powershell.exe -ExecutionPolicy Bypass -File .\tools\preview_collection_chibi.ps1
.\win32\WARP_console.exe -using "profiles\2025-07-16 PROFILE MAIN.yml"
.\.venv-target-hud\Scripts\python.exe tools\verify_item_collection_menu_button.py <built.exe> --check-hover
.\.venv-target-hud\Scripts\python.exe tools\verify_item_collection_close.py <built.exe>
```

The main asset builder calls `build_collection_chibi_assets.ps1` before rendering
its contact sheet. That compiler creates the mascot, Collection-owned controls,
compatibility states, and six uniquely named active menu states.
`build_item_collection_menu_buttons.ps1` alone validates/copies only the ten staged
compatibility states. Use the main or chibi builder for a complete rebuild.

`preview/chibi-items.png` and `preview/chibi-bonuses.png` are offline production-asset
layout previews with illustrative names/counts/bonuses, not live screenshots.
`preview/contact-sheet.png` is also generated. The source and compiler are retained;
local previews, executables, packages, and recovery backups need not be committed.

Available focused build profiles:

- `profiles/item_collection_ui_coexistence_test.yml`: Collection, Auto Hunt, PINC.
- `profiles/item_collection_ui_menu_order_test.yml`: Collection before menu.
- `profiles/item_collection_ui_menu_reverse_order_test.yml`: reversed requested order.

Menu profiles include AutoSupport and RO Global theme dependencies. WARP console
can exit successfully despite a patch error; require no `Patch Error` or `Tool Error`
in the build log, then verify the emitted PE. Earlier forward/reverse builds were
byte-identical; the final cool-theme full profile was rebuilt and checked separately.

### Verified final revision

- Full current main-profile build completed without patch errors.
- 106 BMPs validated: dimensions, 24-bpp BI_RGB, native title preservation,
  blue-white body, exact color keys, 44 reused sources, and all menu states.
- All 65 Collection and 16 menu runtime files matched source bytes after deployment.
- Six active Poring names were absent from all installed DATA.INI archives.
- Native tooltip execution passed 16 cases across both menu sizes, two positions,
  visible/hidden buttons, and valid/null tooltip managers, preserving its ABI.
- Native close execution passed 13 cases covering exact bounds, hover, click,
  outside-release cancellation, title dragging, nonvolatile registers, and `RET 8`.
- QJS syntax, CRLF-only UTF-8 without BOM, and scoped diff checks passed.

The legacy `tools/verify_item_collection_ui.ps1 -SourceOnly` remains a known failing
gate: its slash-opener assertion already fails on the pre-redesign source.
Documentation references in that verifier now point here; its unrelated stale
assertions were not bypassed. Do not describe the entire legacy suite as passing.

Live visual acceptance remains pending. Check New/Classic menu switching, hover,
press/click, close/reopen, map changes, the native small X, all three Collection
tabs, search/category/filter behavior, scrolling, selection, and quantity/actions.
Static PE checks and offline previews do not establish live rendering acceptance.

## Installed build and recovery

Final EXE SHA-256:
`0A05D46EA8A3E17B4AF7DD85E7B796408A01A5C43B2F60CE7821469F45D5811C`.

The verified previous `ItemCollectionChibi.exe` in
`C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes` was updated in place,
along with the 81 listed runtime assets. The prior EXE hash was
`09D9AC6A9270D5E56401E7307E763BF629B88413902FFAF563655667E1C30A01`.
Every replaced file was backed up before installation; no server or GRF was modified.

Local-only artifacts under `Outputs/ItemCollectionCool/`:

- `client/ItemCollectionCool.exe` and `ItemCollectionCool-review.zip`.
- `install-manifest.json`, `installed-manifest.json`, and build/asset logs.
- `installed-backup/`: previous installed EXE and replaced files.

Restart the installed client to use the revised code and resource names. Recovery
uses the exact relative paths and prior hashes in `installed-manifest.json`; restore
those backed-up files while the client is closed. Keep unrelated client data intact.

Historical 2026-09-01 dynamic-art work generated 1,852 75x100 collection BMPs and
399 stock card-icon fallbacks outside Git. The matching itemInfo source hash was
`C37DF7C36BC31D0135C303DEA4CF7056803671FEE66382F4BCBC7813F5F4F52E`;
those resources are independent of this skin and are not included in the commit.
