# WARP-DAN upstream integration — 2026-10-18

Integrated YlenXWalker/WARP20250716-main through
`2d31611f0f632278a49d33feedefd3912655577c` into the working WARP-DAN tree
at `26ac5a0344a2e73beb045d71f8a27d4181d79511`, with the user's approved
compatibility resolutions.

The repositories originally had separate Git histories. The local full import
matches upstream `ad803cb99d0b247d0af3336761f5e3b37902c154` in 6,388 common
files (two different common files, 176 local-only files, no upstream-only
files). That content baseline defines the 16-commit upstream delta; this is
not a replacement of WARP-DAN with an upstream snapshot. The integration
commit retains both histories as parents for subsequent merges.

## Resolutions and preservation

- Combined `.gitattributes` rules, retaining Inventory/Cart/Vending rules.
- Shared `0x0BF6` dispatch retains BPUI, GCHA, stock fallback and BRTR cells
  at offsets 0/4/8/12 and appends WENV at 16. Cache version is v3. Existing
  diagnostic descriptor fields retain their offsets; weather-aware tests
  read the appended field. Unknown packets retain the stock fallback;
  packets for an unselected known feature are ignored.
- Existing ClanBodySkins profiles retain their original perspective payload.
  UniformSpriteRHW owns the universal correction when selected. Its install
  and cleanup refresh an already selected ClanBodySkins patch, so either
  selection order works and removing the universal patch restores the legacy
  bridge. The legacy payload and its build/verifier tools are retained.
- All saved deployment profiles, loose monster-HUD textures and
  `Outputs/.gitkeep` are retained, including files removed by upstream cleanup.
  LastSession and private deployment profiles are not published or replaced.
- Original AutoHunt/AutoSupport layouts remain the defaults. Their original
  window-toggle code is byte-identical for the same arguments; 90 AutoCombat
  and 91 AutoSupport existing helper functions are source-identical after
  newline normalization. Shared allocation, assembly, canvas and text helpers
  used by current custom features are unchanged.
- Current HUD, item description, inventory/cart/storage, Daily Rewards,
  Barter, Battle Pass and Gacha feature implementations are retained. The
  shared packet router is the intentionally changed dependency.
- The accepted `stable-battlepass-gacha-2026-09-15` tag/manifests are untouched.
  The historical guard already reports changes in BattlepassUI/GachaUI from
  later accepted work; the same result is retained, not hidden by rebaselining.

## Local verification

Twenty isolated WARP exports passed, including a copy of the current
160-patch profile. No installed game EXE or player data was used as an output.

- Shared packet routing: four standalone features, both combined selection
  orders, and the full current profile; selected/absent handlers, foreign and
  malformed packets, and register preservation.
- Clan legacy bridge: exact payload and stock continuation, both universal-fix
  selection orders, removal restoring the legacy bridge, and current profile.
- Universal sprite patch signature/registry gates and floor-depth emulation
  with weather in both orders.
- Original Auto UI geometry and byte-identical default toggle emitters; new
  AutoHunt/AutoSupport native UI handlers, hit geometry, quantities, settings
  calls and Windows GDI alpha behavior; language/options and asset-copy checks.
- Weather native lifecycle, packet validation, compatibility versions,
  rendering/particle/ground paths in standalone and both framed-peer orders.
- Monster HUD behavior, clipping, labels, protocol and resources with weather
  in both orders.
- GrayMap native checks: 15 producer vectors and 78 style vectors.
- Riftlock C++ receive/framing tests, protocol/verifier checks and the emitted
  buffered/raw reader bridges from a fresh isolated build.
- Diff/format/registry checks and preservation comparisons. Unrelated feature
  gameplay suites were not rerun.

Private local evidence is under `Outputs/upstream-sync-20261018/` in the
working installation, including hashes, build logs, manifests and native
check receipts. Generated client EXEs and private profiles are excluded from
Git. Upstream evidence files describe upstream tests, not additional local
live acceptance.

These are offline build/native checks, not an in-game guarantee. Restart WARP
and reload the original source EXE before using the updated scripts. New
features remain optional; CelestialDial needs matching server-side WENV
integration before use. This update does not install or configure that server
module, deploy a client EXE, rebuild the server, or change player data.
