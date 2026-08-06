# Item and Enchant-Grade Color Renderer Contract

This document is normative for the QJS-only item/grade renderer. Historical
`boh_text.dll`, substring-matching, split-span, grade-continuation, and
"smart shadow" notes elsewhere are non-normative and must not be used to
change the current renderer.

The contract applies to:

- `CustomColoredItemName`
- `CustomColoredEnchantGradeName`
- `CustomEnchantGradeLabels`
- `ExtNameTextStatic` composition with the item renderer
- every shared `TextOutW` surface used by those patches

Target clients are the profiled 2025-07-16 and 2026-02-19 Ragexe builds.

## Non-negotiable rendering invariants

1. **Enchant-grade color wins the complete decorated title.**
   When `CustomColoredEnchantGradeName` is enabled and the leading grade token
   resolves to an ICOL grade entry, that grade color owns the entire visible
   decorated title: grade token, exact base item name, and slot suffix. An item
   database color must never overwrite any part of that title.

2. **The native grade boundary is coalesced before drawing.**
   The stock item-title builder normally appends a fragment endpoint
   immediately after formatting `[Grade] `. When grade coloring is enabled,
   the two verified post-grade endpoint sites are gated so the grade token and
   following item title reach the renderer as one original UTF-16 span. When
   grade coloring is disabled, each gate executes the exact stock endpoint
   operation.

   The `TextOutW` bridge must never split an incoming span or synthesize an
   additional draw. This preserves both brackets, the separator, card-slot
   text, client alignment, clipping, and Alt+Q layout.

3. **Inventory quantity is not part of a grade-colored title.**
   For a grade-matched inventory label ending in the exact stock form
   `: <digits> ea.` or ` <digits> ea.`, the renderer shortens only the draw
   count so the quantity tail is omitted. The source buffer is not modified.
   `[Epic] Knife [3]: 1 ea.` therefore renders as `[Epic] Knife [3]`.

4. **Window-title shadows are suppressed; item-balloon outlines remain stock.**
   If an item or grade title matches and the original HDC color is a dark layer
   (all RGB channels are at most `0x20`), Inventory/Alt+Q rows and Item
   Description titles restore the HDC color and return `TRUE` without drawing.
   A semantic item-balloon scope is the explicit exception: restore the
   original dark COLORREF and draw the same current span/count exactly once so
   hover and ground labels retain their native outline. Never recolor it.

5. **Foreground color is scoped to one call.**
   A foreground match sets the selected COLORREF, draws exactly once, and
   restores the original HDC color before returning. Color state must not leak
   to later UI text.

6. **ItemId-aware producers own duplicate display names.**
   Inventory/drop balloon producers select item color directly from the ICL2
   ItemId table while they still have a live `CItem*`; their non-dark HDC
   foreground must be preserved. Persistent-title surfaces are different:
   the profiled Alt+Q builders discard the formatter COLORREF output and cache
   only the generated text, while Item Description passes the title through a
   segmented renderer. The native formatter must therefore register its exact
   generated title together with the grade/ItemId-selected COLORREF, and a
   matching dynamic record must own the final `TextOutW` foreground. A matching
   enchant-grade color remains the only override over ItemId color. Window
   title dark passes remain suppressed; semantic item balloons retain stock
   outlines.

7. **There is no continuation state.**
   Never carry a grade color, pointer, length, HDC, coordinate, or timestamp
   from one draw call into another. The native endpoint gate is controlled
   only by the shared grade-mode flag; it does not infer a relationship
   between draw calls. Alt+Q wrapping and adjacent UI labels must be resolved
   from the current span only.

8. **Base-item matching is exact.**
   Strip only client-owned canonical decorations while matching:

   - one leading `[Label] ` grade token;
   - an optional `+<digits> ` refine prefix;
   - an optional numeric slot suffix ` [<digits>]`;
   - one of the complete Inventory forms:
     `Name <digits> ea.`, `Name: <digits> ea.`, or
     `Name [<slots>]: <digits> ea.`.

   The remaining base item must match an ICOL entry exactly. `Knife` must not
   color `Zeny Knife`. A slotless item such as `Angra manyu: 1 ea.` must still
   resolve to the exact `Angra manyu` ICOL record.

   Stock Alt+Q can wrap one producer-derived title into two independent
   `TextOutW` spans. After exact matching fails, each current span may match
   only an anchored prefix or suffix of a dynamic title registered by the
   native `CItem` formatter. Legacy packet-name entries, middle substrings,
   coordinates, timers, and cross-draw continuation remain forbidden.

9. **Client patch state controls visible grade labels.**
   `_GRADE_<n>_<server-label>` is parsed by numeric grade. The textual server
   suffix is ignored.

   - `CustomEnchantGradeLabels` disabled: grades 1-4 resolve to `D`, `C`, `B`,
     and `A`.
   - `CustomEnchantGradeLabels` enabled: the same numeric grades resolve
     through the exact configured `Inputs/enchant_grade.yml` map.

10. **Patch order cannot affect behavior.**
   The grade-color mode and active label registry are runtime configuration
   owned by the item-color patch. Selecting the companion patches before or
   after `CustomColoredItemName` must produce the same effective state.

11. **Other text owners remain isolated.**
    Exact EXTN entity-name spans and complete Fluent Emoji tokens bypass item
    matching. The item renderer must not consume, recolor, or suppress them.

## Patch responsibilities

| Patch | Responsibility |
|---|---|
| `CustomColoredItemName` | Owns the optional bounded ICOL legacy-name table, bounded ICL2 ItemId table, native `CItem*` title-formatter bridge, bounded exact rendered-title recognition ring, current-span-only wrapped Alt+Q matching, conditional native post-grade endpoint gates, non-splitting TextOut bridge, foreground color scoping, quantity omission, window-title shadow suppression, and native item-balloon outlines. |
| `CustomColoredEnchantGradeName` | Enables numeric grade-entry lookup and gives a matching grade color precedence over the complete decorated title. |
| `CustomEnchantGradeLabels` | Replaces the client formatter labels and publishes that exact numeric label map to the item renderer. It is the only switch that activates custom label words. |

## Item identity and `itemInfo.lua`

The `0x0BDD` wire format is backward-compatible. The packet begins with an
optional legacy `ItemName` table for explicitly configured old-client
fallbacks, then may append an `ICL2` trailer:

```text
u32 magic      = 'ICL2'
u16 version    = 2
u16 recordSize = 12
u32 count
records[count] = { u8 kind, u8 flags, u16 reserved, u32 key, u32 rgb }
```

`kind = 0` is an item color keyed by authoritative `ItemId`. `kind = 1` is a
numeric enchant-grade color keyed by grade number. Producer hooks that still
have a live `CItem*` must prefer the ID table. An entry containing only
`ItemId` and `Color` must color Inventory hover, ground titles, persistent
Alt+Q equipment rows, and Item Description titles without a configured name.
`ItemName` remains accepted solely as an explicit compatibility fallback.

The profiled Inventory and Equipment title producers construct `CItem` as an
inline EBP-frame local (`[ebp-0x138]` and `[ebp-0x230]`, respectively). The
bridge must use `LEA` to pass the address of that local as the native
`ItemIdGetter` `this` pointer. `MOV ecx,[ebp-offset]` is forbidden: it treats
the first `CItem` field as a pointer and crashes when hover rendering calls the
getter. The ground-title producer already passes a real `CItem*` argument and
must not apply the inline-local rule.

`ItemTooltipShow` is a native `thiscall`. Its producer bridge must preserve the
incoming `ECX` before calling the packet drain, grade lookup, ItemId getter, or
name lookup, and restore that exact receiver immediately before tail-jumping
to the stock function. A balanced bridge stack is not sufficient if `ECX` is
clobbered; the stock tooltip constructor dereferences it on every hover.

The profiled native item-title formatter receives `CItem*` as arg1 and a base
title COLORREF output as arg2. It also produces title text and segment
boundaries through its remaining output arguments. Its bridge must execute the
exact displaced seven-byte prologue through a trampoline, run the complete
stock formatter, then select a matching numeric grade first and ItemId second.
This producer is the shared identity point for persistent Alt+Q rows and Item
Description titles.

Do not assume that writing arg2 alone colors these surfaces. The 2026 Alt+Q
builders at `0x00996950`, `0x00996AF0`, and `0x00996C90` call the formatter,
then discard its COLORREF local and retain only the generated title string.
Item Description consumes the formatter outputs through the segmented title
renderer. The final `TextOutW` bridge must therefore apply the COLORREF stored
with the exact CItem-derived dynamic title.

For exact final-draw ownership without server names, each ItemId-aware producer
registers the exact byte span emitted by the client itself. The normal title
formatter records `[start,*cursor)`; Inventory/Equipment hover and ground
producers record their already formatted label and bounded length. Dynamic
records are distinct from legacy packet-name records: their color was selected
from a live `CItem*`, so they own the matching final foreground and shadow
suppression. Semantic Inventory/drop balloon scopes continue to preserve their
already-applied native foreground instead of recoloring it by text, and retain
their original dark outline.

The recognition cache is bounded and deduplicated. Packet names occupy at most
the first 224 entries; native titles use the remaining bounded tail and a
32-entry replacement ring once the table is full. No pointer, length, HDC,
coordinate, timer, or grade continuation survives a draw. Window-title dark
passes are suppressed. A non-dark dynamic title uses its stored CItem-derived
COLORREF; a semantic balloon preserves its producer foreground and stock dark
outline. This is what
keeps green ItemId 1201 and gold ItemId 1202 distinct even though both are
displayed as `Knife`.

Final text-only surfaces with no profiled `CItem*` producer may still use an
explicit legacy `ItemName`. Matching remains exact and anchored; this is not
permission to use substring matching. The server must not synthesize
`ItemName` from rAthena `item_db`, because capitalization and localization can
differ from `itemInfo.lua` (`Angra Manyu` versus `Angra manyu`).

`identifiedDisplayName` from `itemInfo.lua` can be used by tooling or the
server as a one-time canonical-name validation and alias source, but it must
not be parsed from Lua inside a render hook. Lua parsing would not repair
native title fragmentation, and duplicate display names remain ambiguous.

## Forbidden implementations

Do not reintroduce any of these:

- separate grade-prefix and item-suffix `TextOutW` calls;
- suppressing arbitrary title endpoints instead of the two profiled,
  grade-guarded post-formatter endpoints;
- `GetTextExtentPoint32W`, `GetTextAlign`, or `SetTextAlign` title splitting;
- a stack local shared between a character count and a `SIZE` structure;
- cross-call grade continuation or timing heuristics;
- substring item matching;
- trusting the server label inside `_GRADE_<n>_<server-label>`;
- drawing or recoloring a matched Inventory/Alt+Q/Item Description shadow;
- suppressing or recoloring a semantic item balloon's original dark outline;
- including `: <digits> ea.` in a grade-colored draw span;
- DLL imports or runtime API detours for item/grade coloring.

## Required regression vectors

Use deliberately different colors for the item and grade records so precedence
cannot pass accidentally:

| ICOL record | Test color |
|---|---|
| `Knife` | green |
| `Zeny Knife` | cyan |
| `Angra manyu` | red |
| grade 2 | magenta |

Expected results:

| Configuration | Input draw text | Expected visible text and color |
|---|---|---|
| Item color only; window title | `Knife` | `Knife`, green, one foreground draw, no dark draw |
| Item color only; ICL2 ID only | item ID `1201`, visible `Knife` | `Knife`, green from ItemId with no legacy ItemName |
| Item color only; duplicate display name | item ID `1202`, visible `Knife [4]` | hover, Alt+Q, and Item Description title gold; never ItemId 1201 green |
| Item color only; ID-only alias | item ID `1599`, client-visible `Angra manyu`, server `Angra Manyu` | complete title red without a configured ItemName |
| Item color only; ID-only headgear | item ID `5374`, visible `Gigantic Majestic Goat` | persistent Alt+Q row and Item Description title purple |
| Item color only; wrapped Alt+Q | producer title `Gigantic Majestic Goat`, two current draw spans | both anchored title fragments purple; adjacent UI text remains stock |
| Item balloon outline | colored hover/ground title | colored center plus original native dark outline |
| Item color only; slotless Inventory | `Angra manyu: 1 ea.` | complete label red from the exact `Angra manyu` record |
| Item color only; slotted Inventory | `Knife [3]: 1 ea.` | complete label green from the exact `Knife` record |
| Grade colors; stock labels | `[C] Knife` | complete title magenta |
| Grade colors; custom labels | `[Epic] Knife` | complete title magenta |
| Grade colors; custom labels | `[Epic] Knife [3]` | complete title including `[3]` magenta |
| Grade colors; custom labels | `[Epic] Knife [3]: 1 ea.` | `[Epic] Knife [3]` magenta; no quantity draw |
| Item color only | `Zeny Knife` | complete exact name cyan; never the `Knife` color |
| Grade colors | `[Epic] Zeny Knife` | complete decorated title magenta |

Every vector must also assert:

- no unknown UTF-16 units;
- no detached or separately colored `]`;
- no overlapping or duplicated span;
- no black shadow for a matched Inventory/Alt+Q/Item Description title;
- the original native dark outline is retained for a matched semantic item
  balloon;
- the original HDC color is restored;
- no custom DLL import is introduced.

The slotless and slotted Inventory vectors must additionally assert that the
entire suffix grammar is consumed. `Angra manyu` must not match a longer
unrelated item, and `Knife` must not match `Zeny Knife`.

## Acceptance matrix

Run the vectors for both target clients across:

- stock grade labels and custom grade labels;
- item-only mode and item-plus-grade mode;
- distinct item and grade colors;
- ICL2 ItemId-only packets, legacy `ItemName` packets, and mixed packets;
- every ordering of `CustomColoredItemName`,
  `CustomColoredEnchantGradeName`, and `CustomEnchantGradeLabels`;
- Inventory hover, Inventory/Equipment rows, Alt+Q, Item Description title,
  and ground-item title surfaces.

Static source/disassembly verification is mandatory, but it is not sufficient
to mark the renderer visually confirmed. The Inventory quantity, Alt+Q title,
and Item Description shadow checks require live screenshots on both clients.
The final-PE gate must also verify both conditional post-grade endpoint gates;
a PE with only the TextOut bridge is an incomplete and failing build.

### Recorded acceptance

- **2025-07-16:** live-confirmed by the user on 2026-07-24 with
  `2025-07-16_Ragexe_175220998_item_grade_fixed.exe`, SHA-256
  `365A40D70865D8992E34473DBBE96BECBDB917CBEAEDD4E49F83FE57A6E21686`.
  This confirms the reported Item Description grade-precedence and slotless
  Inventory color regressions are fixed in the full main-profile build.
- **2026-02-19:** the current ItemId item-color vector was live-confirmed by
  the user on 2026-07-31 with
  `roid_20260219_item_color_dual_weapon_v11.exe` / deployed `roid.exe`,
  SHA-256
  `80A8C8F37E7F74961CC30184862EF1EEDA6AB9BC0E0047EC6964F359753E5FA0`.
  The accepted surfaces are Inventory/Equipment, one-line and wrapped Alt+Q,
  Item Description, hover balloon, and ground-item title. The accepted behavior
  includes ID-only records, duplicate display-name separation, exact selected
  colors, suppression of window-title dark passes, and retention of the stock
  semantic item-balloon outline.

  This is a scoped acceptance of the current 2026 item-color/stock-label
  vector. It does not replace the required live matrix for enchant-grade
  colors, custom grade labels, both patch orders, or the other target client.
  The executable name includes the separately selected dual-weapon patch; this
  checkpoint does not change that patch's documented visual status.

Run the checked-in static gate with:

```powershell
.\.venv\Scripts\python.exe tools\verify_item_grade_color_contract.py --source-only
```

When patched client artifacts are available, pass each artifact to the same
tool as documented by `--help`, then complete the live screenshot matrix.
