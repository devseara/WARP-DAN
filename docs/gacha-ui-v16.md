# GachaUI v16

Client-only v17 revision: removed the four public-tab description captions;
renamed the Admin heading to "Administrator Control Panel" without the visible
GM-level suffix and aligned every panel paragraph to the same left edge.
Admin authorization is unchanged. Wire v8, the server, NPCs and database remain
compatible and do not require rebuilding or resetting for this text-only update.

Native 760x440 client UI for **2025-07-16 Ragexe**, requiring the matching rAthena
GCHA wire **v8** bridge and v16 mail worker/schema. It remains independent of
Battle Pass and shares only the magic-based custom-packet router.

- Common, Rare, Epic and Legendary rates/names come from the NPC script.
- Text-fitted tabs have centered labels and matching paint/hit/cursor bounds.
- Player balance and per-pull price are **plain text**. No `itembox_000` image.
- Page numbers are centered between the supplied arrow images. Next is enabled
  only when the server reports another record.
- Purchase confirmation shows the quoted price, without repeating player balance.
- Sequential results can say `MAIL` when inventory cannot accept the exact prize.

On application, the patch creates
`<target EXE folder>/data/texture/<client UI prefix>/genericsui/gacha/` and copies
the four bundled arrows from `Assets/GachaUI/`. Reapplying preserves custom images
and fills only missing files. Selecting a checkbox alone does not modify a game
folder; assets are installed when WARP applies the patch to the target executable.

Server configuration: `npc/custom/gacha_zeny.txt` now has `.LegendaryPool`,
`.LegendaryRate`, `.LegendaryName$`, `.LegendaryPity`, `.MailTitle$` and
`.MailMessage$`. The selected default is Legendary 0.10% (item 1161), Epic 1%,
Rare 5%, Common 93.90%; Legendary at 100 and Epic-or-better at 10. Full details,
transactional mail behavior and upgrade instructions are in the server repository's
`doc/gacha_ui_v16.md`.

Run `tools/test_gacha_ui.py`, `test_gacha_v16_layout.py`, `test_gacha_capture.py`,
`test_gacha_surface.py`, `test_packet_0bf6_route.py --expect bpui,gcha`, and the
Node `test_gacha_asset_install.js`. These execute emitted x86 or the actual
installer with explicit boundaries; previews are offline fixtures, not live-game
acceptance screenshots. Shared item/enchant/name renderers are not modified.
