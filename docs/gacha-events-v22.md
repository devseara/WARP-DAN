# GachaUI v22

Native 2025-07-16 client patch, on `feature/gacha-ui-redesign`. Matching server
configuration/deployment instructions are in rAthena `doc/gacha-events-v22.md`.
Server map **and char** builds plus the additive ticket receipt migration are
required. Do not install just the client and expect ticket payment to work.

All dedicated Gacha UI artwork lives in `data/texture/<UI prefix>/gachaui/`:

- `banner_<MachineID>.png`: default 140x60 sidebar artwork (1 Prontera, 2 Payon).
  Set `.BannerImage$ = "autumn-2026.png";` in the NPC to load a custom PNG
  basename from this folder. No client repatch is needed for later changes.
  Missing/oversized art retains the fallback icon and clickable caption.
  Filenames are limited to 63 ASCII letters/digits/underscore/dash/dot, `.png`,
  without folders or `..`. `.BannerText$` overrides the caption (empty uses
  `.MachineName$`). `.WindowTitle$` and `.BannerHeading$` edit the title bar and
  sidebar heading. Matching map/client builds are required once.
- `common.png`, `rare.png`, `epic.png`, `legendary.png`: supplied rarity boxes.
- `button_<controlID>_<out|over|press|off>.png`: exact-size native button skins.
  Captions remain native text for fitting, localization and Motion on/off.
- `currency_<zeny|ticket>_<out|selected|off>.png`: currency widget skins.
- `zeny.png`: the user's original `marketui/itembox_00.png`, copied unchanged.
  Its 13x13 blue-Z region at (5,2) is drawn at runtime. A standalone replacement
  icon up to 26x26 is also supported; no resampling alters the tiny artwork.
- `rarity_star.png` and four `arrow_*.png` state images.

The installer copies missing assets only, never overwrites customized artwork.
Keep all 94 packaged images with the patch. `tools/export_gacha_assets.py`
exports deterministic native-style skins and copies the supplied Zeny art
unchanged; it also preserves existing output files. Item images are excluded:
rewards, tickets, featured items and rolling icons always resolve through the
normal client item database and `item` resources, with no `gachaui/item_*`
override. Changing an item does not require copying artwork into `gachaui`.
Images remain centered by their actual bitmap size within each box.

The compact, right-aligned wallet row above pulls shows icons and actual Zeny
and inventory ticket counts on one baseline, right-aligned within their boxes,
without currency-name captions. Icons remain on the left.
Both backgrounds are white by default, with a pale-gold fill and gold border
for the selected currency or a held currency button. Press feedback does not
change the server-owned payment choice; releasing outside cancels the click.
Skins are 136x24 (Zeny) and 104x24 (ticket). The pity block starts level with
Base rates; a configured countdown is red beneath it inside the header. Counts are
not virtual converted balances. Each x1/x5/x10 button uses server-supplied
affordability for the selected currency. Prices, cutoff and eligibility are
rechecked by the server. Missing/invalid metadata cannot enable ticket input.

Motion on/off and Skip Reveal have fitted native button skins. Motion off
keeps the boxes visible without cosmetic item cycling, then displays confirmed
rewards together. Skip sends immediately, even while a slot reply is pending;
the new sequence rejects the superseded response. The server processes all
remaining slots in one bounded operation with per-slot payment/checkpoint
safety and no animation delay. Network/storage time still applies. Batch flag
4096 prevents additional client slot requests; completion flag 2048 paints the
successful completion message green. Remaining animated slots otherwise
continue across deliveries.
Rolling and completion text follow the user's exact wording; completion also
shows a RODEX notice for queued mail. Revealed images support safe left/right
inspection; empty slots cannot be clicked. Previously revealed cards remain
visible during Skip. Errors retain red styling.

GCHA v9 framing is unchanged, with separate metadata message 10 and appended
actions 11/12/13. Wallet refreshes do not replace cards, dismiss confirmation,
reset animation or send purchases. Countdown is relative to server time and
locally locks pulls at zero. Per-banner ticket ID/name/end date, prices and
separate Zeny/ticket pity are script/server-owned.

Validation: `test_gacha_asset_install.js`, `test_gacha_events.py`, the existing
Gacha UI/banner/capture/surface/layout/featured suites, BPUI name and framed
router tests, standalone features and reverse patch order. Offline native x86
tests are not live gameplay acceptance. Keep builds staged until accepted;
the immutable September 15 tag/manifests and restore files remain unchanged.
