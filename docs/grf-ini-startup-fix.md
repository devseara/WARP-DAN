# DATA.INI archive loader repair

Applied on 2026-10-09 in `D:/warp/latest warp/WARP20250716-main`.

`Scripts/Patches/MultiGRFs.qjs` now explicitly null-terminates the configured
INI filename and takes the final `MapAddrs` result as the full allocation size,
including the following GRF metadata. This prevents the Windows INI API from
reading metadata as part of the filename and prevents subsequent patch
allocations from overwriting the marker. Archive priority is unchanged.

This is the archive-loading startup repair previously reproduced with zero
GRFs loaded and a `queryRegionInfo` missing-Lua-function error. It does not
add Daily Rewards or change the existing UI patches, profile, server or Git
history. Riftlock metadata remains supported in this checkout.

Restart this WARP application before repatching the original clean client with
`GRFsFromIni` selected. Already-patched EXEs do not change automatically.

`tools/test_grfs_from_ini.py` executes the emitted 2025-07-16 loader against
read-only Win32 boundaries. It checks the INI filename, all configured existing
archives in priority order, skipped indexes, intact GRF metadata, and preserved
registers/stack. Evidence and original source backup are under
`Outputs/data-ini-fix-20261009/`. Offline checks are not live gameplay acceptance.
