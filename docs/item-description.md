# Item Description UI

## Status and scope

The user accepted the initial implementation on **2026-09-16**: “i think its all good for initial implementation”. This is the single implementation, resource, configuration and maintenance reference for the feature.

The accepted scope is the **2025-07-16 Ragexe** patch, the companion Banquet IDUI server module, and generated item-script descriptions. It includes the candidate and equipped-comparison panes, native scrolling, collection artwork, grade/option descriptions, and the clean chibi header. The existing item-title/grade renderer contract remains normative: [item-grade-color-renderer-contract.md](item-grade-color-renderer-contract.md).

The accepted client was `Banquet_ItemDescription_Test_v5_20260916.exe`, SHA-256 `20a407fb61fdac0dc2b7e277b1b8f50d00d84f182743b9ddea3caa7c3804cba2`. User acceptance is separate from automated tests: the latter mock native engine boundaries and do not establish an unrecorded live matrix or support for another client version.

**Card redesign (2026-10-10, not live-accepted).** The user approved a grade-tinted card design and asked for no Original/Compare/Refresh footer. The same change fixes the reported stock-description flash: the old client kept the stock body (and stock geometry) on screen for one server round trip, then swapped. That behavior was intentional in the previous verifier. It also fixes stock children created after activation staying visible over the body. The emitted-code suites pass; live screenshots are still required before this is marked accepted.

## Architecture and ownership

| Layer | Responsibility |
|---|---|
| `Scripts/Patches/ItemDescriptionUI.qjs` | Patch 387; validates native contracts and embeds the freestanding x86 payload |
| `tools/native/item_description.cpp` | Main/comparison lifetime, layout, native UI interactions and bounded drawing |
| Banquet `src/map/item_description.cpp` | Validates the inspected inventory instance and builds read-only snapshots |
| Banquet description DBs | Server-authored effect text and supported predicates |
| Existing client catalog | Numeric ItemId to localized name/resource mapping and native title formatting |

`itemInfo*.lua/lub` supplies catalog metadata and legacy descriptions; it does not own the native window layout. Rendering does not parse Lua or derive identity from server display names. No item/equip script is executed to generate an inspection response.

`item_description.build.dll` is a **build-time link container**, not a deployment DLL. Its code/data is embedded by WARP. The payload has no runtime imports, socket receive detour or runtime executable patching. Existing dependencies selected by the user's WARP profile still apply.

### Native entry points

| Target | Address / contract |
|---|---|
| Main `UIItemCollectionWnd` | ID 12; vtable `0x01032AAC` |
| Equipped `UIItemCollection_ComparisonWnd` | ID 234; vtable `0x01032C5C` |
| Main/comparison draw | `0x008B4200` |
| Main/comparison message | `0x008C18B0` / `0x008C3540` |
| Main/comparison per-frame process | Slot 19 `0x008BAEC0` (both); the manager loop at `0xA44219` calls it every frame. OnDraw runs only for dirty windows and the flag is cleared after the call (`0xA1CE3D`), so request spacing and timeouts live here |
| Main position | `0x008A0E70`; stock positioning subtracts the main width |
| Header underlay | Guarded seven-byte detour at `0x008B438A`, resume `0x008B4391` |
| Native title instructions | `0x008B43CA..0x008B43F6`, preserved against the accepted fixture |
| Owned `CItem` | Window `+0xB8`; numeric ID getter `0x005D98A0` |
| Instance fields | Index `+4`, refine `+0x60`, grade `+0x88`, cards `+0x1C`, option count `+0x98`, packed options `+0x9C` |
| Inventory/equipment right-click | Vtables `0x0103D460` / `0x0103223C`, slot 32 |
| Native `UIScrollBar` | Vtable `0x0102AEF4`; constructor `0x00836870`, draw `0x00856560` |
| Catalog lookup | Manager pointer `0x0159C088`, lookup `0x00A7E780`; name `+0x40`, resource stem `+0x58` |

Native receivers and calling conventions must be preserved. The header detour saves registers/flags, paints only the exact registered ready window, and replays `CMP [EDI+0x1D4],0`. It runs after stock backing and before untouched native art/title drawing. Comparison paint briefly selects the normal skin branch, then restores its real ID. No title span, foreground color or shared TextOut ownership is changed.

The main and equipped panes have independent snapshots, layout, scrollbars and child restoration. Their actual widths plus an 8-pixel gap determine adjacency; the pair is clamped to the viewport. Each pane is at most 360×560. On screens at least 600 pixels wide, both active panes fit side by side; smaller screens can overlap.

Every native message to an owned pane first hands back the stock geometry and children, runs the stock handler, then resumes the card (closing message 5 excepted). Children are re-enumerated on every draw, so one the stock code creates later is recorded and hidden too.

## Packet contract

Shared byte-for-byte header: WARP `tools/native/item_description_wire.hpp` and Banquet `src/common/item_description_wire.hpp`.

| Field | Value |
|---|---|
| Magic / version | `IDUI` (`0x49554449`) / 1 |
| Request / response opcode | `0x0BF8` / `0x0BEF` |
| Request / snapshot size | 96 / 12,416 bytes |
| Snapshot rows | At most 64 rows of 192 bytes, after a 128-byte header |
| Actions | Inspect 1, snapshot 2, compare 3 |
| Scope | Catalog 0, inventory 1 |
| Results | OK 0, invalid 1, stale 2, unavailable 3, throttled 4 |

The high request-token bit distinguishes candidate and equipped views. It grants no authority: both requests must match the actual inventory index, ItemId, identified state, refine, grade, cards and options. The server index is the native client index minus two. Refresh/Compare also carry the accepted semantic fingerprint.

Each player has two fixed watches, each rate-limited to one request per 150 ms. Excess requests are dropped silently before allocating the large response, so the client queues any request issued within 160 ms of that pane's previous one and sends it from OnProcess. The client no longer sends compare (3); the server path remains for compatibility. Item addition/removal, inventory refresh, equip changes, refinement, grading, card insertion and descriptor reload invalidate affected watches. Item replacement, malformed replies and stale responses cannot populate a different pane.

Item Collection and Bestiary share the existing packet fallback through the selected-owner magic registry in `ItemCollectionUI.qjs`. The routing chain preserves AHUI, ASUI, PINC, COUI, BSUI, IDUI and the native unknown-packet fallback; selection order must not steal another module's handler.

## User interface behavior

- **Opening:** an inspectable item takes its final card geometry in the same frame as the native open and shows a loading skeleton until its snapshot arrives. The stock body is never painted first. Reopening the identical instance paints its last accepted snapshot immediately while the server revalidates it.
- **Fallback:** if no reply arrives within 3 s, the pane returns to the stock description. Until a later reply proves the server module, later opens skip the skeleton and keep the stock body until a snapshot arrives. A non-OK reply also restores stock. An unsolicited stale notice (refine, card or bound change) reinspects in place behind the skeleton.
- **Header:** a gradient tinted by the native item grade (none blue, D rose, C amber, B green, A violet, taken from `grade_icon{1..4}.bmp` inks). It has a white medallion under the native 75×100 art, a frosted bar under the native title spans, the type label, and a headline (Weapon ATK, Weapon MATK or Armor DEF) with the refine ATK bonus in yellow. The candidate pane shows an up/down arrow against the equipped pane's base+refine total. It also has a binding chip with an open/closed lock, socket pips (enchant slots in violet), an `Equipped` pill on the comparison pane, and the native grade icon at 2× over the art corner. Native art, name spans and grade colors remain native; no grade label text is drawn.
- **Body:** an info strip (`Lv.`, `Weapon Lv.`, `Weight`), then sections with blue diamond headings and thin dividers: Base Stats (with red/green deltas against the equipped pane), Special Effects, Cards & Enchantments, Card Set Bonuses, Grade, Random Options, Requirements (check/cross), and Trade Information as green/red chips. Numeric tokens in effect text are orange. Every rectangle is clipped by the payload, because the shared fill helper rejects rather than clips negative origins.
- **Components:** each card/enchant slot is one peach panel with a 40×52 thumbnail, the catalog name, the slot line and its own effects. Empty slots are compact strips. Partial panels clip to the scrolling body. Missing collection art falls back to the item icon. Hovering a known component highlights it; clicking or right-clicking opens it through the native component-description route.
- **Grade:** one panel with the current grade and every tier; the active tier is checked, unmet tiers are locked and muted.
- **Scrolling:** each pane owns a normally constructed native `UIScrollBar`, created only when the body overflows; close destroys it and releases its mouse capture. The legacy text viewer's scrollbar is not borrowed.
- **No footer actions:** there is no Original, Compare or Refresh. Unidentified items and unprofiled indexed containers retain stock disclosure and behavior.

## Native resources and alignment

Canonical prefix: `data/texture/유저인터페이스/`. Loose Windows installations may spell the same byte path `À¯ÀúÀÎÅÍÆäÀÌ½º`. Preserve native path bytes, palette data and exact `#FF00FF` color-key pixels.

The audit identified **107 fixed or connected BMPs** with no missing required enumerated asset. The complete measured inventory is [item-description-resources.csv](evidence/item-description-resources.csv). Original game assets are not modified or redeployed by this patch.

| Family below the prefix | Count | Dimensions / role |
|---|---:|---|
| `sysbox_{bg,lu,mu,ru,lm,rm,ld,md,rd}.bmp` | 9 | 14×14 normal frame/background tiles |
| `sysbox_g{1..4}_{lu,mu,ru,lm,rm,ld,md,rd}.bmp` | 32 | 14×14 grade edges; no grade `_bg` asset is required |
| `basic_interface/collection_bg_g{1..4}.bmp` | 4 | Grade illustration backing; 280×120 in maindata, 280×144 in spritedata |
| `grade_enchant/grade_icon{1..4}.bmp` | 4 | 12×12 grade/title assets |
| `basic_interface/sysbox_comparison_*` | 9 | 14×14 stock comparison frame family |
| Normal/comparison `collection_*bg.bmp` | 2 | 280×120 stock header backings |
| Normal/comparison empty/disabled card slots | 4 | 24×24 stock card-strip states |
| `btn_view{,_a,_b}.bmp` | 3 | 42×20 native View states |
| Normal/comparison resize BMPs | 2 | 13×13 art; original child hit area is 16×16 |
| `basic_interface/btn_help_*` | 4 | Normally 20×20; one archive has a 19×19 pressed asset |
| `basic_interface/titlebar_{left,mid,right}.bmp` | 3 | 12×17 title chrome |
| `sys_base_off`, `sys_close_off`, `sys_close_on` | 3 | 11×11 controls |
| `basic_interface/btn_{out,over,press,disable}_{left,mid,right}.bmp` | 12 | 6×20 button slices |
| `scroll0*` / `scroll1*` | 12 | Native vertical/horizontal track and thumb families |
| `basic_interface/dialscr_{up,down,up1,down1}.bmp` | 4 | Alternative scrollbar classes, not the chosen text-viewer scrollbar |

The original text viewer begins at `(91,31)`, and its main art at `(10,11)` is 75×100. The card header is y=0..115 and the info strip y=116..153. The scrolling body runs from y=154 to height−12, so the visible height stays height−166. The native scrollbar sits at x=width−27, and content stops at width−32. The frame is a 1px grade-tone edge with an 11px radius and keyed corners, drawn with fills; the card no longer loads `sysbox_*` or footer `btn_*` BMPs. Native scrollbar, text wrapping, image clipping and component hit rectangles use the same layout coordinates. Text is drawn at 11–13px with a 20px headline. The native text call stores the height raw (`0x546F60`), and only the face is a table index, but sizes other than 11/12 still need live confirmation.

Dynamic artwork uses `item/<resource>.bmp`, `collection/<resource>.bmp`, and separate full card art in `cardBmp/<resource>.bmp`. The audit indexed 29,474 candidate paths; presence in an archive is not proof of runtime selection. The inspected loader gave priority to update, maindata, mapdata, palettedata, spritedata, data and greyworld. Loose-file/skin selection remains controlled by the native resource resolver and current client configuration.

## Server description data

| File in Banquet | Purpose |
|---|---|
| `db/item_description_db.yml` | Entry point and import order |
| `db/item_description_generated.yml` | Generated display records |
| `db/import/item_description_db.yml` | Local manual overrides, loaded last |
| `db/import-tmpl/item_description_db.yml` | Commented setup template, not loaded directly |

Each file has a commented schema header with limits and examples. The generator preserves that header. `Effects` in an override **replaces the complete inherited list**; it does not append. Omitted fields retain previous values. Item and random-option IDs are separate namespaces.

| Record field | Meaning |
|---|---|
| `Id`, `Kind` | Real numeric ID; `Item` (default) or `RandomOption` |
| `Label` | Optional 47-byte label; used for the raw option row when Effects is empty |
| `Rarity` | Optional display rarity, up to 31 UTF-8 bytes; separate from numeric grade |
| `Enchantment` | Classifies a card-backed component without creating gameplay storage |
| `Legacy` | Retains Original notice for remaining undescribed effects |
| `Effects` | At most 64 authored definitions |

An effect has required `Text` (up to 2,048 UTF-8 bytes), optional `Label`, and `Section`: NativeEffects, BaseAttributes, Refine, Grade or CardSet. Supported predicates are `MinRefine`, `MinGrade`, `MaxGrade` and `RequiredCards`; they combine with AND. Equal min/max grade selects one exact tier. RequiredCards applies to the inspected item's slots, including duplicate multiplicity, not a character-wide equipment set. `Unknown: true` does not claim a condition was evaluated as active.

Option placeholders: `{value}`, `{signed_value}`, `{neg_value}`, `{value_div10}` (integer division toward zero), `{value_tenths}` and `{value_hundredths}`. Use the actual option's units. Descriptors do not change mechanics.

The offline generator follows effective pre-renewal item, option and skill YAML imports. It translates supported literal bonuses, skill grants and grade expressions, preserving supported unconditional statements from mixed scripts. Strings, conditional bodies and statements after unknown exits are not promoted to unconditional bonuses. Remaining gaps are reported by ItemId and retain Original.

At initial acceptance, the data covered 1,804 items with static effects, 1,970 with grade effects (overlapping counts), and 258 option entries. Angra Manyu has all 12 base-script effects and four grade previews with `Legacy: false`, including correctly scaled drain bonuses and four skill grants. Apple of Archer has DEX +3 plus exact Rare/Epic/Mythic/Legendary/S ranged-damage tiers of +1/+2/+3/+4/+5%.

## Build, verify and deploy

Prerequisites: Windows, the supported pristine Ragexe, WARP console/profile dependencies, MSVC x86/x64 toolchains, and Python packages `pefile`, `capstone`, `unicorn`, `Pillow` and `PyYAML`. Tool defaults match the local toolchain; compiler/server/source paths are explicit arguments where supported. Run from WARP:

```powershell
.\.venv-target-hud\Scripts\python.exe tools/build_item_description_native.py
.\.venv-target-hud\Scripts\python.exe tools/build_item_description_preview.py --profile "profiles/2025-07-16 PROFILE MAIN.yml" --output Outputs/ItemDescription/verify
.\.venv-target-hud\Scripts\python.exe tools/verify_item_description_release.py Outputs/ItemDescription/verify
.\.venv-target-hud\Scripts\python.exe tools/generate_item_description_data.py --check
.\.venv-target-hud\Scripts\python.exe tools/verify_item_description_data.py
.\.venv-target-hud\Scripts\python.exe tools/verify_item_description_server.py
.\.venv-target-hud\Scripts\python.exe tools/build_item_description_server.py
.\.venv-target-hud\Scripts\python.exe tools/verify_item_grade_color_contract.py --source-only
```

Use a new output directory for each isolated WARP build. `--order before/after` checks shared patch selection; `--lifecycle remove/reapply` checks cleanup. The build probe exists only in the isolated fixture, not as a deployed runtime debug feature.

The release verifier executes the emitted x86 against mocked engine boundaries. Separate artwork, comparison, skin and header suites cover pixel bounds, exact original BMP slices, native scroll input, independent snapshots, capture/lifetimes, native title bytes and the header trampoline. Fixed evidence and small original-art fixtures are under `tools/fixtures/item_description/`; they are verification inputs, not new deployment assets.

The server verifier compiles the real descriptor loader, predicates and row-building code with mocked engine lookups. It checks strict YAML/rollback, bounded output, identity/fingerprints, both watch invalidations, exact grade tiers and Angra's complete script output. Diagnostic test output and real configuration-validation errors are intentional; the shipped renderer has no console/debug logging.

Run the resulting client from the existing game folder. A new server installation needs the matching Banquet module and description DB files. **Existing v3 server/v5 client installations only need regenerated DB data for description edits:** run the generator without `--check`, deploy those DBs if necessary, use `@reloaditemdb`, and reopen the description. No restart or client rebuild is needed for a data-only edit.

`tools/package_item_description_test.py --client <build-directory> --version <package-name> --client-only` packages a verified client and this document. Omit `--client-only` only when matching server build/source verification is current. Existing accepted release archives are historical records and are not rewritten by documentation cleanup.

## Limits and regression checklist

- This patch targets 2025-07-16; it does not enable the 2026 client.
- Comparison shows base values, not complete character damage or scripted final totals. Headline arrows and stat deltas compare the two panes' server base ATK/DEF/MATK and refine ATK rows only.
- With no Original button, legacy-only text is not reachable from the card. Three server strings still say "Original": two Banquet notes in `src/map/item_description.cpp` and the generator's grade note (113 items). Reword them with the next server/data deploy.
- Four native card-backed positions are shared by cards/enchants; five random options remain the gameplay limit.
- Character-dependent effects can still require Original/manual descriptors. At initial acceptance, 113 items retained additional conditional grade fallbacks.
- Options 260/261 contain one-argument HP/SP-drain definitions, while those bonuses require chance and amount. They remain explicitly unavailable rather than inventing gameplay values.
- Snapshot output has a 64-row budget and marks overflow. Arbitrarily long descriptions need a future paging extension.
- Unprofiled storage/shop/trade/book routes retain stock behavior. No complete specialized-window matrix is claimed.

For future changes, test inventory and Alt+Q, two customized copies of the same ID, graded/long titles, empty and multiple occupied slots, cards/enchants/options, forged metadata, both comparison panes, edge dragging, wheel/arrows/thumb capture, component opening, opening without any stock flash, quick successive opens, same-item reopen, server silence fallback, invalidation/reload, relog/map changes/themes and clean exit. Preserve Item Collection, Bestiary, AutoHunt, AutoSupport, pincode and native title/balloon behavior. Initial acceptance does not retroactively mark unrecorded individual vectors as tested.

## Cleanup verification

The post-acceptance cleanup removed obsolete custom-thumb capture code, its unused drag coordinates, the unused blitter allocation, unused locals/imports and temporary authoring scripts. Reserved configuration/state slots retain the established offsets used by accepted fixtures. Verification tools use checked-in fixtures instead of temporary release/audit folders. There is no runtime debug logging; validation errors and test diagnostics remain intentional.

The cleanup EXE has SHA-256 `c7178d3517ca9126fe73b9a830b0122d9320d6798d9b57171709bb8ae1fbe263`. Removing dead code changes its binary layout. The emitted-code comparison confirms exact pixels, text, requests and dimensions against the accepted EXE for default, bound, small-window, scrolling, Original, Compare and paired-pane scenarios. Native title bytes remain unchanged. Full client/peer routing tests, patch-removal checks, server builds, descriptor tests and the 100-check item/grade source gate pass. This is automated parity evidence, not a new claim of live testing.