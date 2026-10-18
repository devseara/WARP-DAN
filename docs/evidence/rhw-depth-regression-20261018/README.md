# Zoom warping: missing universal sprite renderer fixes

Read-only audit on 2026-10-18. Audited `main`:
`8eb2a2199ee92d050333abee1f5d87d04f4aa8d4`.

The installed signed client
`2025-07-16_Ragexe_175220998_clientinfo_patched.exe`, SHA-256
`5d1d4faf3065a27655e9404357af8beb697ede907959fa9c39ccc15aba3cbc36`,
does not contain the universal RHW or floor-safe depth corrections. The older
2026-10-12 MAIN release, SHA-256
`bb3094171ac7969474753d5865d43c647d1fa74178681fae8c1c9f66ebf0b640`,
contains both. `audit.json` pins the actual bytes and branch membership.

| Site | Current signed client | Older fixed release |
| --- | --- | --- |
| `0x00C4A5B1` | `F3 0F 10 55 E0` (stock bottom RHW reload) | `0F 1F 44 00 00` (uniform RHW) |
| `0x00C40F9F` | `F3 0F 5C 6D 1C` (stock depth) | Jump to character floor-safe cave |
| `0x00C49FEE` | Stock shadow depth calculation | Jump to floor-safe shadow cave |

## Commit and QJS history

- [e84d442e](https://github.com/YlenXWalker/WARP20250716-main/commit/e84d442e623ad19d9a134f9d065511da265d9ec7)
  adds `UniformSpriteRHW.qjs`, `FloorSafeSpriteDepth.qjs`, their verifiers,
  documentation and profile/catalog entries. It also removes the old
  ClanBodySkins-only perspective bridge and its generator/verification plumbing.
- [388e5c3d](https://github.com/YlenXWalker/WARP20250716-main/commit/388e5c3d5f4141c28c52e39db7560b933551ba88)
  merges that feature into `release/riftlock-main-20261012-idui-v2`.
- Neither commit is an ancestor of audited `main`. Its active source and MAIN
  profile lack both patches. The later sprite-doc commit `7f52d498` did not
  merge the renderer implementation.
- `7a9ad7ae` assigns ID388 to GrayMap, and `552116a7` assigns ID389 to
  CelestialDial. Those are the historical IDs of UniformSpriteRHW and
  FloorSafeSpriteDepth respectively. A restoration needs distinct unused IDs;
  do not overwrite either current feature's registration.

Exact historical source copies are under `historical-e84d442e/` in this folder.
They are evidence copies, not newly installed active patches.

## Why the symptom returns

The stock quad emitter assigns different RHW values to its top and bottom
vertices. Perspective-correct texture sampling then moves padded HD artwork
inside the screen rectangle as zoom changes. Native head rectangles and padded
body rectangles move differently. UniformSpriteRHW keeps the same top-edge RHW
for all vertices while preserving XY/UV/color/Z and the native alpha-sort key.
FloorSafeSpriteDepth separately prevents below-anchor character and shadow
rows sinking into the floor at close zoom.

The current client still jumps from `0x00C4A63E` to `0x019860F0`. Its cave
matches the legacy `Inputs/ClanBodySkins/perspective.bin` payload exactly.
That code explicitly checks `sprite\clan_skins\<1..255>\` and excludes native
heads and standard job resources. The standard HD female Mage and her Fox
therefore do not receive that older correction.

## Next implementation

Port the complete feature and old-clan-bridge removal onto current main;
allocate unused IDs and select both patches in the actual current profile.
Preserve GrayMap/Celestial weather and the dual-weapon Z hook. Run the original
signature, patch-order and cave-emulation gates against the current build,
check final deployed native bytes, refresh paired Riftlock signing, and repeat
live zoom/head-contact/floor/wall checks. Existing sprite art need not be
regenerated for this missing-renderer-patch regression.

During the audit the checkout was changed externally from main to
`feat/sprite-quad-depth`; reflog confirms that checkout. This audit did not
checkout, merge, reset, stash or change active QJS/game assets/signatures.
