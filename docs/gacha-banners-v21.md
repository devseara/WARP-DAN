# GachaUI v21: banners, rarity cards and editable images

Target: 2025-07-16 Ragexe. Development branch: `feature/gacha-ui-redesign`.
The existing native content is shifted 160px for selectable machine banners;
the frame is 920x440. This is an intentional Gacha-only layout update. BPUI,
VIP versions and shared packet/text helpers are unchanged. The original
`stable-battlepass-gacha-2026-09-15` tag and manifests must remain intact.

## Editable images

All nine dedicated PNGs are installed without overwriting custom files into
`data/texture/<UI-prefix>/gachaui/`, alongside any operator banner images:

| File | Use |
| --- | --- |
| `common.png`, `rare.png`, `epic.png`, `legendary.png` | Supplied 36x35 rarity boxes |
| `arrow_off_left.png`, `arrow_off_right.png` | Disabled page arrows |
| `arrow_on_left.png`, `arrow_on_right.png` | Enabled page arrows |
| `banner_1.png` | 140x60 artwork for the existing Zeny machine |
| `banner_<MachineID>.png` | Optional 140x60 artwork for additional machines |

Machine names are native text over the bottom quarter, not baked into artwork.
Missing/oversized banner files fall back to a featured item and machine name.
Normal item icons still use the game's `item` artwork. Buttons, window/card
panels and stars are native drawing, not hidden PNGs. No old files are removed.
All labeled controls have measured Tahoma 12px text plus 14px horizontal padding;
the title-bar close glyph and icon-only page arrows keep their native bounds.

The supplied banner was created using the built-in image generator, then packed
to 140x60 with `tools/prepare_gacha_banner.ps1` (no source overwrite). Prompt:

> Use case: stylized-concept. Asset type: tiny selectable sidebar banner in a classic Ragnarok Online style white native game Gacha UI. Generate ONE original landscape illustration, aspect ratio 7:3, intended to be displayed at only 140 by 60 pixels. Warm autumn fantasy town with a central small stone clocktower, orange foliage framing the sides, soft golden sunlight, pale cream sky, inviting hand-painted 2D MMORPG background aesthetic. Broad readable shapes and attractive gold-orange colors at thumbnail size. Fill the canvas edge to edge. No people, no lettering, no numbers, no logos, no watermark, no border, no UI widgets. The bottom quarter will have a native text label overlaid, so keep the main clocktower and foliage readable above it. Deliver a single banner illustration, not a mockup, no surrounding webpage or screen.

## Server contract and behavior

Use the matching rAthena Gacha banner update. Public machines opt in through
`gacharegister` in NPC `OnInit`, with the same 24 arguments as `gachaui`. Do not
register restricted NPCs. The existing machine is registered; the example NPC
remains unloaded. Pools, rates, quantities, cost, pity and delivery are unchanged.
Five banners per page, at most 64 machines. Selection is blocked while pending,
in a confirmation, or rolling. Server-owned fresh sessions prevent old quotes
from being used on a different machine. NPC access proximity remains enforced.

GCHA wire v9 sizes and offsets remain intact (32/3788 bytes). Message 9 is a
separate bounded catalog; actions 9/10 select/page it. Old clients ignore it.
The catalog never replaces reward/quote state. Row flag 8 is inventory NEW:
absent immediately before this character receives that reward; not lifetime
ownership. Final mailed cards do not retain NEW. Only Last Pull shows it.

Cards show quantity and gray/green/violet/gold tiers with 1/2/3/4 stars. Winner
cards keep centered private plain character names instead of a quantity line.
Remaining unrevealed icons keep cycling during delivery and acknowledgment;
revealed cards stop. A separate animation epoch never changes server timing.
MAIL/FREE/PITY markers remain, with no new purchase or randomization requests.

## Offline validation

Run the current `test_gacha_ui.py`, `test_gacha_banners.py`, `test_gacha_capture.py`,
`test_gacha_surface.py`, `test_gacha_featured.py`, `test_gacha_v16_layout.py`,
`test_packet_0bf6_route.py --expect bpui,gcha`, `test_battlepass_plain_name.py`
against the staged combined client. `test_gacha_asset_install.js` checks all PNGs,
no-overwrite repairs and failures. Native tests execute emitted x86 and use
isolated API/transport boundaries; they are not live-game acceptance.

Keep the strict old source manifest (expected to flag intentional Gacha edits).
Do not refresh its hashes. Stage matching builds, preserve installed files and
obtain live acceptance of Gacha and Battle Pass before publishing a new baseline.
