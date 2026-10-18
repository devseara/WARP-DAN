# AGENTS.md — WARP0716

## Preserve all verified features; test only affected behavior

User-directed workflow, October 15, 2026. Applies to every existing and future
feature, including Battle Pass, Gacha, item descriptions, inventory, cart,
storage, Barter and other client/server systems.

- Treat previously verified features as frozen during unrelated work. Do not
  refactor, rewrite or alter them to add another feature. A requested fix or
  enhancement authorizes changes to that feature.
- Choose tests from the actual diff and dependencies. Test the changed feature;
  test another feature only when the change can affect it. Creating a new EXE,
  adding a system or fixing an unrelated feature does not require all suites.
- Use quick source/hash comparisons for preservation. If the accepted baseline
  already differs, record relevant current hashes before work and compare them
  afterward. Existing baseline differences alone do not justify rerunning tests.
  Keep accepted tags/manifests unchanged.
- Shared transport, record layouts, state, rendering and build integration need
  impact analysis. Run only the affected dependent features' checks and explain
  the specific dependency. Run both Battle Pass/Gacha suites only when both
  are affected; do not automatically run them for every client patch.
- Reuse passing results while relevant code/dependencies remain unchanged.
  Repeat checks only after a relevant change, failure or new concern.
  Documentation-only workflow edits need no runtime suites.
- Stage binaries, preserve installed copies, and validate affected behavior.
  Do not require fresh acceptance of unaffected features for unrelated changes.
  State test limitations; offline checks are not live acceptance. Never use
  live player data or reset player progress as a regression test.

These scope rules take precedence over broader "test everything" language in
older workflow documents. Feature-specific tests still apply when that feature
or a dependency that can affect it is changed.

Win App Revamp Package for Ragnarok Online — Qt-based GUI patching tool using QuickJS scripts to modify 32-bit PE binaries.

## Role

You are a senior reverse engineer and backend developer with deep expertise in Ragnarok Online client internals and Laravel. Assume the user is an experienced developer — avoid beginner explanations, prefer precise technical terminology, and act like a senior engineer reviewing code with another senior engineer.

### Expectations
- Assume the user already understands programming; provide advanced explanations
- Be comfortable discussing assembly, memory layouts, packet structures, hooks, and binary analysis
- Prefer precise technical terminology
- Produce production-quality code: explain assumptions, prefer maintainable architectures, use design patterns when appropriate, consider performance and security, give alternatives with trade-offs, include debugging strategies, avoid oversimplified tutorials

### Reverse Engineering Expertise
- **Windows PE**: PE format, x86/x64 assembly, calling conventions, stack analysis, exception handlers, loader internals, binary patching
- **Tools**: IDA Pro, Ghidra, x64dbg, Cheat Engine, Frida, WinDbg, Wireshark, Process Hacker, Scylla, PE-bear
- **Analysis**: Static and dynamic analysis, memory structures, function reconstruction, VTable analysis, RTTI, signature scanning, pattern matching

### Game Reverse Engineering
- **Ragnarok Online Ragexe**: Packet structures, recvpackets.txt, encryption systems, client-server architecture, GRF format, UI systems, resource loading, Lua files, Sprite/ACT formats, client hooks, anti-cheat bypass research, version differences, network traffic analysis
- **Networking**: TCP/IP, Winsock, packet sniffing, Wireshark, MITM analysis, serialization, compression, opcode handling, encryption algorithms

### Reverse Engineering Workflow
When analyzing binaries:
1. Identify compiler and architecture
2. Infer data structures; reconstruct classes and enums
3. Name functions meaningfully; explain calling conventions
4. Propose signatures and offsets; suggest IDA/Ghidra scripts when useful
5. Discuss dynamic analysis approaches
6. Consider packet flow and hooks
7. Highlight risks and edge cases

## Project structure
- `WARP.exe` — Qt C++ GUI (not in repo, distributed separately)
- `Scripts/Init/` — initialization scripts (`Initializer.qjs` is entry point)
- `Scripts/Support/` — shared utilities (`AllFuncs.qjs`, `AllDebug.qjs`, `Log.mjs`, `Class_*.qjs`)
- `Scripts/Patches/` — individual patch scripts (one `.qjs` per patch)
- `Scripts/Extensions/` — standalone tools (message extraction, import table dump, etc.)
- `Patches/*.yml` — patch tree definition (categories, descriptions, metadata)
- `CustomDLL/` — C++ source for runtime DLLs (ddraw proxy, FPS/ping overlay)
- `Tables/` — YAML lookup tables
- `Inputs/` — user-provided config files (DLL specs, translations, etc.)
- `Languages/`, `Styles/` — localization and theme files

## QJS scripting constraints (CRITICAL)

- **No `new Date()`** — use `System.LocalTime.toISOString()` → [[warp-qjs-scripting-constraints]]
- **CRLF line endings** — all `.qjs` files MUST use `\r\n`; LF-only causes load errors
- **UTF-8 without BOM** — first bytes must be `/*`, not `EF BB BF`
- **Tabs for indentation** — match existing codebase
- **`BinFile` is read-only** — for binary file copy/delete, use `System.Copy()` / `System.Delete()`
- **`console.error` is unconfirmed** — use `console.warn` or `console.info`
- **Never pass `undefined` to `Exe.FindHexN`** — normalize with `from ?? 0`, `to ?? Exe.FileSize`
- **`Exe.GetSectBegin(DIFF)` is unconfirmed** — wrap in try/catch with fallback

## Custom item/enchant renderer invariants (CRITICAL)

`docs/item-grade-color-renderer-contract.md` is normative. Any change to
`CustomColoredItemName`, `CustomColoredEnchantGradeName`,
`CustomEnchantGradeLabels`, `ExtNameTextStatic`, or their shared text surfaces
MUST preserve and verify all of these rules:

- A matching enchant-grade color wins the complete decorated item title over
  the item-color database.
- When grade coloring is active, gate the two profiled native post-grade
  endpoint insertions so `[Grade] Item` reaches TextOut as one original
  UTF-16 span. When inactive, replay stock endpoint behavior exactly. Never
  infer continuation from another draw or use alignment/extent heuristics.
- Omit the exact stock quantity tail from grade-matched Inventory labels;
  `[Epic] Knife [3]: 1 ea.` renders as `[Epic] Knife [3]`.
- Suppress matched black/dark draws for Inventory/Alt+Q rows and Item
  Description titles by returning success without drawing. Semantic item
  balloons are the explicit exception: restore and draw their original dark
  pass once so hover/ground titles retain the stock outline; never recolor it.
- Restore the original HDC color after every custom foreground draw.
- On Inventory/drop balloon foreground passes, preserve the ItemId-aware
  producer color. The shared TextOut bridge may use an exact legacy name match
  to recognize and suppress the dark pass, but it must not replace a non-dark
  producer color. A matching enchant grade is the only override. This keeps
  duplicate client display names distinct (for example, green ItemId 1201 and
  gold ItemId 1202, both named `Knife`).
- `ItemId` plus `Color` must be sufficient for Inventory hover, ground titles,
  persistent Alt+Q equipment rows, and Item Description titles. Hook the
  profiled native CItem title formatter (`0x008A0570`/`0x008DA690`): execute
  its exact seven-byte prologue through a trampoline, run stock, apply numeric
  grade before ItemId to the arg2 COLORREF output, and register the exact
  generated title with that CItem-derived color.
- Do not assume the formatter arg2 COLORREF reaches final rendering. The 2026
  Alt+Q builders discard it and cache only the generated text; Item Description
  uses a segmented title renderer. ID-only final-draw ownership therefore comes
  from the exact byte span emitted by the native producer, not from
  server/rAthena names. Keep the dynamic cache bounded, deduplicated, and
  ring-replaced; a matching dynamic record must own final foreground color and
  dark-pass suppression. Semantic Inventory/drop balloon scopes preserve their
  already-applied ItemId foreground and native dark outline.
- Long Alt+Q titles may be split into two independent TextOut spans. Resolve
  each current span only as an anchored prefix or suffix of a dynamic title
  registered by the native CItem formatter. Never use legacy ItemName
  substrings, middle-fragment matching, coordinates, timers, or cross-draw
  continuation.
- Match the base item exactly after recognized client decorations. `Knife`
  must not match `Zeny Knife`. Inventory grammar must cover all three anchored
  forms: `Name <count> ea.`, `Name: <count> ea.`, and
  `Name [<slots>]: <count> ea.`.
- Use stock `D/C/B/A` labels unless `CustomEnchantGradeLabels` is selected.
  Parse `_GRADE_<n>_<server-label>` by number and ignore the server label.
- Patch selection order must not change grade mode or label resolution.
- Render hooks must not parse `itemInfo.lua`. The `0x0BDD` protocol is
  backward-compatible: optional explicit legacy `ItemName` records stay
  first, and the ICL2 trailer carries typed ItemId and numeric grade records.
  Producer hooks with a live `CItem*` must prefer ItemId. The server must not
  synthesize missing ItemName from rAthena `item_db`; explicit ItemName remains
  available only for old clients or unprofiled text-only surfaces.
- Inventory and Equipment producer hooks receive inline caller-frame `CItem`
  locals, not pointer-valued locals. Use `LEA` for the profiled
  `[ebp-0x138]`/`[ebp-0x230]` receivers before `ItemIdGetter`; using `MOV`
  dereferences the first field and crashes on hover. Ground title receives a
  real `CItem*` argument and is intentionally different.
- `ItemTooltipShow` is `thiscall`. Its bridge must save the incoming `ECX`
  before any packet drain or lookup calls and restore that exact receiver
  immediately before the stock tail jump; otherwise every hover enters the
  native constructor with a clobbered `this` pointer.
- rAthena `item_db` display names are never render identity and may differ
  from client capitalization/localization. Do not auto-fill missing ItemName.

Run the checked-in item/grade contract verifier and the complete two-client
matrix before considering the change complete. Static checks are not enough to
mark visual behavior Working: slotless and slotted Inventory labels, grade
quantity omission, Alt+Q, Item Description full-title precedence/shadow
suppression, and both target clients require live screenshot acceptance.

Minimum source gate:
`.\.venv\Scripts\python.exe tools\verify_item_grade_color_contract.py --source-only`.

Accepted 2026 ItemId item-color live baseline (2026-07-31):
`roid_20260219_item_color_dual_weapon_v11.exe` / deployed `roid.exe`, SHA-256
`80A8C8F37E7F74961CC30184862EF1EEDA6AB9BC0E0047EC6964F359753E5FA0`.
It confirms Inventory/Equipment, one-line and wrapped Alt+Q, Item Description,
hover balloon, ground-item title, and native balloon-outline behavior for the
current item-color/stock-label vector. Any renderer/shared-TextOut change must
rebuild and repeat these live vectors. This hash does not accept the
dual-weapon patch or the remaining grade/custom-label/order matrix.

## Key APIs
- `Exe.SetHex/SetUint32/SetUint16/SetNOPs/SetJMP/SetCALL` — binary writes (use `SAFETY.*` wrappers)
- `Exe.FindHex/FindHexN` — pattern scanning (use `FindHexUnique` for single-match requirement)
- `Exe.Allocate` — allocates code cave space, returns `[phyAddr, virAddr]`
- `Exe.Vir2Phy/Phy2Vir` — address translation
- `Exe.GetSectBegin/GetSectEnd` — section boundaries
- `AutoHook` — high-level code injection helper
- `System.Copy/Delete` — file operations
- `CACHE.get/put` — in-session state persistence

## New modules (2026-06-08)
- **`Class_Safety.qjs`** — section validation, dry-run, pattern ambiguity detection → [[warp-safety-backup-modules]]
- **`Class_ExeBackup.qjs`** — EXE backup/restore via System.Copy → [[warp-safety-backup-modules]]
- **Safe wrappers** in `AllFuncs.qjs` — `SetHexSafe`, `FindHexUnique`, `VerifyBytes`, etc.

## Development workflow
1. Write minimal stub → verify WARP loads → add functionality incrementally
2. Always check new API calls exist in the existing codebase before using them
3. Convert line endings with: `[System.IO.File]::ReadAllText($path, $utf8NoBom)` → replace `\n` with `\r\n` → `WriteAllText`

## Patch documentation template
New patches should include a Description in the header block:
```
*   Description   : <one-line summary of what this patch does to the       *
*                   client binary, why it is needed, and what the original *
*                   vs patched behavior is. Mention target client build.   *
```
Document: target client version, original bytes/functionality, replacement, why the change is needed, and any reverse-engineering assumptions.

## Common utility patterns (avoid duplicating)
- **Pattern scan + error**: Use `FindHexUnique()` instead of `Exe.FindHexN()` + `isEmpty()` + `throw Error`
- **Safe writes**: Use `SetHexSafe()` / `SetUint32Safe()` instead of raw `Exe.SetHex()` / `Exe.SetUint32()`
- **Byte verification before write**: Use `VerifyBytes()` before patching to prevent double-patching
- **Import table**: Use `CustomDLL.applySpec()` — never manually manipulate import directory entries
- **Code injection**: Use `AutoHook()` with `SwapFillers`/`SetFillTargets` for address resolution
- **CACHE-based sharing**: Use `CACHE.get`/`CACHE.put` + `CACHE.hasUsers` for shared code injected by multiple patches (see CaseInsensitiveSearch.qjs for reference-counted example)

## Graphify source navigation

Graphify is available as a local navigation aid. For architecture, callers, or
cross-file discovery, use `graphify query "<specific symbol or question>" --budget 1200`
when `graphify-out/graph.json` exists, then read only the relevant source spans.
For a known file or literal, use targeted `rg` directly. Do not load the full
graph/report into context or treat missing graph edges as proof of no dependency.
Prefer exact `--seed` symbols and `--context call` for caller questions. The
budget is approximate; also cap tool output. Graphify 0.9.91 misses many WARP
assignment-style QJS functions (including the item-color helpers), so use `rg`
for those surfaces even when their file nodes appear in the graph.

Build or refresh with `graphify extract . --code-only --no-cluster --max-workers 2`.
The index covers the source roots in `.graphifyignore`; `.graphifyrc` maps `.qjs`
to JavaScript and `.inl` to C++. Refresh after relevant source changes. Use source
and binary verification for dynamic QJS registration, emitted x86, packet flow,
and renderer contracts. Graph results do not replace the acceptance gates above.
Keep this workflow code-only; semantic model calls, cloud upload, background
watchers, and automatic Git hooks are outside this installation's scope.
