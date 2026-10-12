# Name-static patch lifecycle

The name adapters introduced in `ea2e303` must not remain active after `CustomExtName` is removed. This fix addresses the exported zero-target detours diagnosed in [the review](name-static-review-20260908.md), including the additional discovery that the previous `CACHE.getTag(...)` keys were never registered.

The 25 native name adapters now keep their allocations, code, guarded native edits and dispatcher overrides under the selecting patch. Their tags are explicit strings, so WARP can actually identify them. Each invocation uses fresh protocol-install state. `CustomExtName` clears its own partial edits and releases its shared feature contribution if an adapter fails.

Shared EXTN/ICOL transports and text-map code have a separate, address-stable global lifetime for the loaded EXE. They are reused across consumers. Removing one feature recomputes the active feature bits, preserves remaining consumers, and restores the shared frame/text hooks when the last text user leaves. Cached, unreferenced infrastructure can remain allocated in that WARP session; it does not leave the 128-byte native-name protocol enabled. A fresh build without any consumer does not create it. The fixed names-only enabled PE is byte-for-byte identical to the reviewed fresh baseline: `85d802e789d5ebe36b2a04e5a228f1bb6b5f120c1d4a10194993370134b20978`.

All changed name-static headers use the full boxed WARP copyright/GPL/author/date/description format, with tabs in code, CRLF endings and UTF-8 without BOM.

## JuanD RO / AutoCombat and AutoSupport

The inspected JuanD RO source defines `NAME_LENGTH` as `(23 + 1)` in `src/common/mmo.hpp`. AutoCombatUI and AutoSupportUI do not require CustomExtName or item coloring. Keep the stock name layout for that server unless a coordinated server/client name-width migration is explicitly intended.

Restart the already-open WARP process to load the corrected scripts. Load the original `2025-07-16_Ragexe_175220998_clientinfo.exe`, then apply the desired base patches plus AutoCombatUI and AutoSupportUI. Existing corrupt client files require a fresh rebuild; editing QJS source does not rewrite them retroactively. No server, deployed client, or saved user profile was modified by this task.

A separate candidate was built from the user's current recommended-base profile plus only those two UIs, with asset copying disabled for the diagnostic build:

`tmp/name-static-fix-20260908/juand-base-autoui.exe`

SHA-256: `d7a678852bb622335e135b8d60632ac294390acdd021f56cdee7a0c70edab624`.

All 248 previously identified stale native-name hook locations match the original client in that candidate. This is a patch/export check; the candidate was not launched or accepted in-game, and its asset deployment was not tested.

## Regressions

`tools/verify_name_patch_lifecycle.py` copies WARP into a disposable output directory, installs a test-only probe there, uses the real QJS patch-selection/cleanup/ClearPatch APIs, and inspects each exported PE. The checkout's patch catalog and the user's WARP process are untouched. The probe emits a unique marker for every execution to reject stale output. It checks 1,079 guarded native overwrite locations.

Covered cases:

- Enable, disable and export: native name edits and shared frame hook restore to stock.
- Disable/reapply twice: name allocation trampoline and feature state remain valid.
- Inject a failure in the last adapter: preceding native edits roll back.
- Both name/color installation orders, removing either feature: the other remains valid.
- Remove names, then apply only AutoCombatUI and AutoSupportUI: stock name protocol and frame hook remain intact.

The committed pre-fix source fails the same tests, including exported detours to removed code and dangling cached state. Negative-control failures are expected; they are not failures of the fixed build.

Example from the repository root:

```powershell
python tools/verify_name_patch_lifecycle.py --source "2025-07-16_Ragexe_175220998_clientinfo/2025-07-16_Ragexe_175220998_clientinfo.exe" --output tmp/name-lifecycle-check
```

Use `--reference-ref HEAD` before committing to exercise the pre-fix committed sources. `--case ui-after-disable` selects the target UI workflow alone.

The aggregate native-code gate now includes the character rename and 120-vector character footer tests. The original client is supplied explicitly as the footer's `--before` fixture. NPC discovery is conditional on `--npc-overlay`, which should be supplied only when AlwaysShowNpcName is selected:

```powershell
python tools/verify_all_name_packets.py --pe PATH_TO_PATCHED_EXE --before PATH_TO_ORIGINAL_EXE --deps PATH_TO_PYTHON_DEPENDENCIES --output tmp/name-native-check
```

Validation in this task:

- 18/18 canonical-name native execution suites passed.
- All eight lifecycle scenarios passed in the final combined run, including the AutoCombat/AutoSupport workflow.
- AutoSupport UI contract passed against JuanD RO: 134 assets, router v4, ASUI server.
- Item/grade structural source gate: 96 checks passed.
- All eleven 2025 item/grade/label-order PE cases passed.
- Changed QJS syntax, headers, CRLF and no-BOM checks passed.

Evidence remains under `tmp/name-static-fix-20260908/`, especially `suite/summary.json`, `lifecycle/summary.json`, `lifecycle-ui/summary.json`, and `item-matrix-2025/verification.log`. The final combined lifecycle summary contains all eight passing scenarios; the separate UI-only run is retained as additional evidence.

The 2026 source EXE was unavailable. Neither its matrix nor the required in-game screenshot matrix has been completed. The subsequent user clarification focused validation on JuanD RO's stock-name 2025 client and the two UI patches. These results do not label shared rendering or the UI as live-accepted.
