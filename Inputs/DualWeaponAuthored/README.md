# Dual-weapon authored source closure

This directory is the clean, non-ignored authority for authored dual-weapon
data. Generated pixel matches, native-guide estimates, rejected DWR3/DWC2
tables, and temporary EXEs are not accepted inputs.

## Accepted content

- `poses/female-assassin-pair28.csv`: 224 live-accepted pair28 records
  (96 held and 128 attack, including 16 intentional hidden terminal cells).
- `grips/female-assassin-views34-45.csv`: the 48 accepted/identity grip keys
  for Zeny Knife view 34 and Naght Sieger view 45.
- `accepted-act/female-assassin-pair28-attack-body-guide.act` and `.spr`: the
  only recovered user-edited Act Editor pair. Their hashes are pinned in
  `manifest.json`.

## Missing content

- The user-edited pair28 held authoring ACT was not recovered.
- No non-pair28 pose or per-view hilt/grip ACT has been authored and imported.
- Existing files formerly under `tmp/recovered_dual/ActEditorWork` were
  generated starting points and are not accepted.

## Historical resource-fix build policy (2026-09-05)

The request to restore original dual/off-hand sprites is implemented by the
readable compositor in CustomDLL/DualWeapon/compositor.c. Its builder embeds
the versioned canonical DWR3 and DWC2 in
Inputs/DualWeaponRuntime/compositor.dwcp. It verifies both hands before
suppressing a combined packet.

The non-pair28 canonical records are enabled as **unaccepted placement data** to
exercise original-resource replacement. This supersedes the earlier rule that
kept all such records stock. Their acceptance labels have not been promoted:
resource-selection emulation is not a live placement acceptance. Missing native
ACT/SPR source cells still fall back entirely to stock.

Pair28's exact legacy family retains the existing renderer and depth core.
The new fallback renderer is built from checked-in source; it does not consume
documentation CSVs or deleted tmp/recovered_dual files. See
docs/dual-weapon-resource-fix-20260905.md for current evidence and limitations.

## Native coordinate correction (2026-09-05)

The previous `rigs/female-assassin-pair28-derived.dwr3` experiment was rejected
in live testing and is no longer consumed by the runtime builder. Its raw ACT
centers were incorrectly treated as native coordinates and rounded to integers.
The historical generation script is retained with an explicit rejection label.

`tools/build_dual_weapon_native_basis.py` generates
`CustomDLL/DualWeapon/native_basis.h` from the unchanged embedded legacy pair28
rig and the active GRF assets. The native loader subtracts ceil(imageExtent/2)
from raw ACT centers, and native C40C20 adds one pixel to the second packet
endpoints. The new code reconstructs that accepted pair28 basis from the current
native packet. Off-only held view34/45 selects the matching physical hand;
view34/view34 uses the original dagger images with their native solo registration.
The latter is a reference-preserving transfer, not independently authored hilt data.

The DWCP also retains the unchanged canonical DWR3/DWC2 for the existing paths.
Pair28 continues through its existing legacy renderer. Solo off-hand attack80
keeps its distinct timeline; other weapon pairs remain visually unaccepted.
See `docs/dual-weapon-native-coordinate-fix-20260905.md` for native execution
proof and the current live acceptance status.

## Historical all-class candidate (2026-09-05)

That historical candidate source and payload resolved all 23
single-weapon classes. The owner checks the active requested Lua suffix against
both retained ACT/SPR names before publishing. The compositor requires the
female Assassin resource family, uses exact source cells from the native pair28
basis, and preserves the legacy core only for actual views45/34 and their reverse.
The earlier estimated canonical poses and DWC2 corrections are no longer used by
the generalized C path; their byte blobs remain in the payload to preserve its
layout. Native solo off-hand non-held behavior remains the inherited path.

The user-accepted reference EXE `0bb06dbc...4509` is backed up. Extension EXE
`91b16900...edeb8` is now installed at the user's request, but has no new live
placement acceptance. Missing weapon families,
per-image grip registration, and native80/dual88 carrier selection remain open.
The source coordinate documentation contains weapon-relative transforms, not a
complete set of anatomical hand sockets for every job/type/frame. See
[the all-type status](../../docs/dual-weapon-all-types-20260905.md).

## Current supported classes (2026-09-05)

At the user's request, current QJS and runtime restrict original dual/off-hand
composition to base classes1(dagger),2(one-handed sword),6(one-handed axe).
Custom views resolving to those classes remain eligible. Both resource owner
and compositor enforce this set; the other20 single-weapon classes use stock.
The original-resource suffix guards and accepted native coordinate basis remain.
The rebuilt EXE `c2e857e3...eeb02` is installed and backed up; this does not add
live acceptance for axe placement. No missing mace assets or all-type attack
carrier changes are planned in this scope. See
[the current scope and evidence](../../docs/dual-weapon-supported-types-20260905.md).

## Pixel grips and generic blade axes (2026-09-05)

The input is `grips/female-assassin-pixel-landmarks.json`, compiled into `CustomDLL/DualWeapon/grip_profile.h`. It pins exact source hashes, 68 selected weapon-image hilt/tip records across 17 non-Drake views, body contact pixels, and generic pair28 blade-axis points. The legacy pair-guide socket CSV is not anatomical hand data. The [palm-centered implementation](../../docs/dual-weapon-grip-placement-20260905.md) was rejected and superseded by the edge-contact policy below. Historical sections above do not define current hand ownership or installed-build acceptance.

## Old motion and pixel-edge contacts (2026-09-05)

The palm-centered `95674dba` placement was rejected for hand overlap and changed attack motion. The current compositor retains the old reference attack trajectory and angles, with anatomical equipment slots. Held32 uses `CustomDLL/DualWeapon/held_edge_contacts.h`, generated from opaque-pixel boundary contact. The mask scope, proof, regeneration steps and live-acceptance limit are documented in [the edge-contact report](../../docs/dual-weapon-edge-contacts-20260905.md). The offline `--measure-contacts` payload is never an installable runtime.

Male Assassin family remains research-only. The [male asset audit and design](../../docs/dual-weapon-male-assassin-research-20260905.md) identifies separate source-image, visibility and body-contact requirements. Existing female annotations must not be relabeled as male data.
