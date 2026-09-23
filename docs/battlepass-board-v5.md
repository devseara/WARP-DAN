# Gacha-style Battle Pass board

Target: 2025-07-16 Ragexe, 32-bit. `BattlepassUI` now uses a private 920x560
renderer with compact native 11px text, four Gacha/VIP-style button states,
text-only navigation and identical featured-style item boxes on both tracks.
Normal Rewards and Premium Rewards show up to six item boxes in every level
cell. Empty item slots are omitted, but every level's outer box stays visible.
Unreached levels, including their item icons and headings, are grayed out and
cannot be selected or claimed. Hover names/quantities and read-only right-click
item details remain available. Selection is cleared safely on future pages or
level resets, and only reached cells may be auto-selected on a new page.
The entire Premium row is also gray/unselectable without the server Premium
flag. Cosmetic status text cannot unlock it. Hover/inspection remains active;
losing Premium clears a Premium selection safely.
A green outline selects Normal; a gold outline selects
Premium. The selected level heading follows that color. A blue, tilted CLAIMED
stamp is drawn entirely inside the confirmed level/track cell, with no new art
files or shared font hooks. Sending a claim never creates an optimistic stamp.

Pages: Quests (three daily plus three weekly), Mission (existing difficulty
missions), Rewards (five levels, both tracks), My Stats. All gameplay data,
progress, costs and claim eligibility remain server-owned.
Rewards Back/Next buttons and their hitboxes stay inside the header with 2px
vertical padding. Long configured titles are clipped before the buttons.
The Mission selection table labels its columns Difficulty, Count, EXP and
Status. The last column shows availability or the server's cooldown timer;
the same aligned header and row layout apply to monster and item missions.

The append-only BPUI v5 board extends v4 to 7256 bytes. The existing 0x0BF9
requests are 16 bytes; action 19 submits an objective period token and action
20 requests a reward-grid page. The shared framed 0x0BF6 router still keeps
Battle Pass and Gacha independent. Legacy server replies remain understood;
the daily/weekly board requires the paired updated server.
BPUI v6 appends ten 72-byte sixth-item entries after the entire v5 packet
(Normal levels 1..5, then Premium), for 7976 bytes total. Capability bit 1024
negotiates v6; old clients keep exact v1-v5 layouts. A v5 reply clears the
sixth-item cache. New clients do not offer a six-item claim until the full
v6 data is available, and oversized configurations cannot be claimed.
BPUI v7 appends 2624 bytes of presentation text (27 labels, six Track Information
lines, eight Rules lines, each 64 bytes), for 10600 bytes total; capability bit
2048 negotiates it. The server reads these from the `NATIVE UI TEXT` block in
`npc/custom/Ragnarok/Battlepass/battlepass.txt` on refresh. Window/banner/season,
Status/Level/EXP, tier names/headings, reward labels and My Stats captions are
editable. Empty text intentionally hides a line. Text fields are bounded and
terminated, with the existing native width clipping. V6 downgrade clears the
text extension; v5 downgrade clears it and sixth items. Legacy clients keep
exact original sizes. Text never changes server progression or eligibility.
The Mission selection instruction is `.UIMissionHint$` (95 bytes or empty to
hide). Capability 4096 permits the existing v4+ hint field at offset 2776 to
carry it while no mission is active. Active Where to Hunt prose is unchanged;
servers without that capability retain the client's original instruction.
No additional packet size/version or shared text-renderer changes are needed.

Item names and images resolve through the native ItemId resource helpers.
No item-specific artwork is bundled. Hovering hunt/collection targets and
reward items shows their names; paired right-button down/up opens item details.
On Mission, only the monster preview shows a hover label; mission text and
map rows do not. Collection missions retain right-click inspection on the
small item icon without showing a Mission hover label.
Monster art is only in the active hunt mission preview, using the native
Bestiary sprite fitter. The character card uses the exact VIP Alt+Q compositor,
including equipment and costumes, with private scratch storage.

The parent surface stays in the native opaque mode throughout its lifetime,
as Gacha does. The actual window is exactly 920x560 with no spare cursor margin;
the stock cursor renders independently. Never enable surface alpha after its
opaque GPU tiles have been cached, or zero-alpha GDI text and overlapping tiles
can expose the scene behind the board.

Where to Hunt displays up to five native `map/<mapname>.bmp` thumbnails (24x24),
map names and spawn counts together. Resources come from the client's data/GRFs,
not new bundled artwork. Map tokens are bounded and allow only letters, digits,
underscore and `@`; missing/invalid resources leave the text visible. Native
BMP pixels are opaque except for the magenta color key. The private renderer
payload is format v4/API 80 bytes with 7728 bytes of board storage. The stable
Board.v5 diagnostic marker still addresses the unchanged prefix and API.

Only reviewed helper emitters are shared with VIP/Bestiary; selecting those
patches is not required. No shared item-name renderer or actor-name hook changes.
PNG buttons install beside the selected output EXE into `battlepassui`, without
overwriting existing client-side skin edits. Legacy BMP assets remain for
compatibility; they are not used as navigation icons by the new renderer.

Build payload: `uv run --with pefile python tools/build_battlepass_ui.py`.
The builder extracts the VIP portrait from its source and compiles the existing
Bestiary fitter; runtime has no imports or external DLL. Relocations, CRC,
exports, packet size and native entry signatures are checked before patching.

Offline checks include `test_battlepass_board.py`,
`test_battlepass_plain_name.py`, `test_battlepass_monster.py`,
`test_vip_portrait.py --battlepass`, and `test_battlepass_asset_install.js`.
`test_battlepass_surface.py` additionally executes the actual window creation
and stock GPU-tile cache/presentation (use `--expect-bug` on the old board
build). `test_battlepass_mission.py` checks monster-only hover, native map
resource keys, all five rows and malformed/missing-resource fallbacks.
`test_battlepass_rewards.py` checks v6 negotiation, six-item delivery metadata,
empty level boxes without empty item slots, both highlight colors, grayed future
levels, reached-only selection/claims across paging and resets, clipped
server-confirmed stamps, sixth-item tooltips/inspection (including locked
levels) and duplicate/oversize/downgrade/malformed guards.
Rendered fixtures deliberately double live sprite/resource boundaries and are
not screenshots of a running game. Final live acceptance remains required.
`test_battlepass_text.py` checks v7 negotiation/configured labels on all tabs,
blank/oversized/malformed text and downgrade behavior, actual-value separation,
and Premium acquire/revoke/gray/selection/tooltip guards.
