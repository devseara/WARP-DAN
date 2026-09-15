# Gacha v15 package verification — September 15, 2026

This package was assembled from the tested v15 Gacha implementation. The
matching server source is pinned in [the Gacha guide](gacha-ui.md). No live
server/database/game files, executables, credentials or personal profiles are
included in this repository update.

## Installation diffs

| Use case | Diff | Required starting point |
| --- | --- | --- |
| Fresh installation | `DevSeara-BattlePass-ChatUI-NPC-Gacha.diff` | Compatible WARP commit `9a10e8b` |
| Add Gacha to the preceding package | `DevSeara-Gacha-v15-upgrade.diff` | WARP with package `35ef127`'s combined Battle Pass/Chat/NPC diff installed |

Both `git apply --check` and actual application succeeded in separate clean
verification trees. All 109 installer paths match between fresh and upgraded
trees. QJS and artwork were compared byte-for-byte; text metadata was compared
after newline normalization. All five published QJS files match the installed
scripts and have CRLF/no-BOM encoding. Existing historical diffs are unchanged.

SHA-256:

- Fresh diff: `0572482CBEC75A5F3FD63310D0C72E791899516CE9572D4C7095C63905561565`
- Upgrade diff: `5AB3F747095686F85C856D6E1020E80EF8E8DE6347FD31920EBF3AF31B6D9E37`

The upgrade changes only patch registration/attributes, the native opcode
router and Battle Pass route integration, plus the new Gacha script/artwork.
Battle Pass and Gacha retain distinct handlers and server features.

## Clean WARP builds and native checks

The freshly installed tree successfully patched the original 2025-07-16 client
in four configurations: Gacha alone, Battle Pass alone, Gacha then Battle Pass,
and the complete package (Battle Pass, Gacha, Chat, NPC Dialog and Chat Item Icons).
Actual dispatcher tests passed for all four, including fallback behavior,
register preservation and Gacha's empty initial NPC open/close/reopen.

Actual WARP application created the target data folder chain and deployed all
four arrow PNGs with matching hashes in every Gacha-selected build. All five
Node installer/input suites passed: Battle Pass assets, Chat assets, Chat font
inputs, NPC assets and the new Gacha asset installer. Gacha covers no-overwrite
repeat/repair, test-mode isolation, missing assets and directory/copy failures.

The complete-package client also passed native item mouse-capture crash and
cached-surface regressions, including the stable 760x440 tiled presentation
across History, pagination, Admin and other tabs.

The full emitted Gacha client regression passed: bounded/malformed snapshots,
quotes/confirmation/cancellation, twelve sequential reveal/delivery steps,
timer lifecycle, native item descriptions, title-only dragging, paginated data
and arrow states, configurable text, fitted buttons, GM controls, per-machine
reset wording, fitted custom machine headings, stale-session rejection and
canonical centered winner names without hover popups.

These are offline/native-boundary checks, not new live-game screenshots or
live purchases. Installation into another server/client fork still requires
matching protocol/build compatibility and live acceptance. Generated game
executables, test profiles and local logs are intentionally not published.
