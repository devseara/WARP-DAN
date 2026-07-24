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

4. **Matched dark/shadow passes are suppressed.**
   If an item or grade title matches and the original HDC color is a dark
   shadow layer (all RGB channels are at most `0x20`), the bridge restores the
   HDC color and returns `TRUE` without calling the downstream `TextOutW`.
   This is required for Inventory/hover text and Item Description titles and
   is also the consistent rule for the other intercepted item-title surfaces.
   A shadow must never be preserved, recolored, or redrawn.

5. **Foreground color is scoped to one call.**
   A foreground match sets the selected COLORREF, draws exactly once, and
   restores the original HDC color before returning. Color state must not leak
   to later UI text.

6. **There is no continuation state.**
   Never carry a grade color, pointer, length, HDC, coordinate, or timestamp
   from one draw call into another. The native endpoint gate is controlled
   only by the shared grade-mode flag; it does not infer a relationship
   between draw calls. Alt+Q wrapping and adjacent UI labels must be resolved
   from the current span only.

7. **Base-item matching is exact.**
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

8. **Client patch state controls visible grade labels.**
   `_GRADE_<n>_<server-label>` is parsed by numeric grade. The textual server
   suffix is ignored.

   - `CustomEnchantGradeLabels` disabled: grades 1-4 resolve to `D`, `C`, `B`,
     and `A`.
   - `CustomEnchantGradeLabels` enabled: the same numeric grades resolve
     through the exact configured `Inputs/enchant_grade.yml` map.

9. **Patch order cannot affect behavior.**
   The grade-color mode and active label registry are runtime configuration
   owned by the item-color patch. Selecting the companion patches before or
   after `CustomColoredItemName` must produce the same effective state.

10. **Other text owners remain isolated.**
    Exact EXTN entity-name spans and complete Fluent Emoji tokens bypass item
    matching. The item renderer must not consume, recolor, or suppress them.

## Patch responsibilities

| Patch | Responsibility |
|---|---|
| `CustomColoredItemName` | Owns the bounded ICOL table, exact item matching, conditional native post-grade endpoint gates, non-splitting TextOut bridge, foreground color scoping, quantity omission, and matched-shadow suppression. |
| `CustomColoredEnchantGradeName` | Enables numeric grade-entry lookup and gives a matching grade color precedence over the complete decorated title. |
| `CustomEnchantGradeLabels` | Replaces the client formatter labels and publishes that exact numeric label map to the item renderer. It is the only switch that activates custom label words. |

## Item identity and `itemInfo.lua`

The current `0x0BDD` wire format and ICOL table are name-keyed. The final
Inventory/Equipment, ground, Alt+Q, and Item Description draw paths do not all
expose an item ID; the Item Description `UITransBalloonText` path contains
formatted text, length, color, and style only.

`identifiedDisplayName` from `itemInfo.lua` can therefore be used by tooling
or the server as a one-time canonical-name validation and alias source, but it
must not be parsed from Lua inside a render hook. It would not repair native
title fragmentation, and duplicate display names remain ambiguous.

A future ID-first renderer requires a versioned `0x0BDD` schema carrying item
IDs plus scoped hooks at every upstream item-object producer. Until that
protocol migration is implemented end to end, the required runtime fallback
is the bounded exact-name grammar in this document. Substring matching is
never an acceptable substitute.

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
- drawing or recoloring a matched black outline/shadow;
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
| Item color only | `Knife` | `Knife`, green, one foreground draw, no dark draw |
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
- no black shadow for a matched title;
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
- **2026-02-19:** static source/final-PE and patch-order matrix pass; live
  visual acceptance remains pending.

Run the checked-in static gate with:

```powershell
.\.venv\Scripts\python.exe tools\verify_item_grade_color_contract.py --source-only
```

When patched client artifacts are available, pass each artifact to the same
tool as documented by `--help`, then complete the live screenshot matrix.
