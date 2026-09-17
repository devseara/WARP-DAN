# Editable VIP button images

These PNG files are the complete buttons used by the VIP client, including text.
Edit them in `data/texture/<client UI prefix>/vipui`, keep their dimensions, save
as PNG, and fully restart Ragnarok. Artwork-only edits do not require WARP or a
server restart. WARP's missing-file installer preserves existing custom images.

| Filename prefix | Size | Button |
| --- | --- | --- |
| applyvip | 60 x 18 | Apply VIP |
| openstore | 68 x 18 | Open Store |
| openstorage | 81 x 18 | Open Storage |
| vipbuffs | 57 x 18 | VIP Buffs |
| upgrade | 53 x 18 | Main and quest Upgrade |
| purchase | 56 x 18 | Buy the selected membership duration |
| refresh | 58 x 18 | Refresh |
| yes | 28 x 18 | Confirm upgrade quest or hourly buffs |
| no | 23 x 18 | Decline confirmation |
| cancel | 43 x 18 | Close quest or purchase popup |
| close | 15 x 18 | X on main and popup |
| scroll_top | 13 x 13 | Scroll up |
| scroll_bot | 13 x 13 | Scroll down |

Each prefix has four states: `_out.png` = normal, `_over.png` = hover,
`_press.png` = pressed, `_off.png` = disabled. Exception: normal arrow filenames
are `scroll_top.png` and `scroll_bot.png` (no `_out`). There are 52 button PNGs.

The client paints no separate text or border on these controls. Changing the
image changes its whole appearance, not the action or server permission.
Upgrade uses the same blue skin as Apply VIP/Open Store. Upgrade, Yes, No,
Cancel and X have four pixels of horizontal padding around their visible text;
their labels are vertically centered. Confirmation/action pairs are centered
in the popup with eight pixels between buttons. Click bounds match the images.
Refresh also uses that rounded blue skin in all four states, with a centered
caption. Its existing 58x18 size/click area is unchanged, so replacing only
`refresh_out/over/press/off.png` needs a client restart, not a WARP/server rebuild.
Apply VIP is enabled only without active membership or a pending payment. It
opens the five-duration picker; Purchase is enabled only after a valid selection.
Selecting a duration or closing the popup never purchases. Open Store and Open
Storage require active VIP. Store also requires the server's shop permission.
These rules refresh from membership snapshots, not the retained VIP level.
VIP Buffs also requires server-confirmed hourly eligibility. Its compact popup
reuses `yes_*`, `no_*` and `close_*` images. No new artwork is required. No/X
only closes the popup; Yes requests the server-owned buff claim. The cooldown
timer is separate text beside VIP Buffs, never painted over its button PNG.
Alpha transparency is supported; pure magenta remains the native color key.
Disabled arrows are expected when the active benefit card fits without scrolling.

The other used UI PNGs are `background.png`, `vip_exp.png`, `item_main_bg.png`,
`membership_crown.png` and `vip_status_bg.png`. The crown is shared by duration
cards and earned level slots (none at level zero). Keep its transparent alpha;
it is fitted into 28px / 24px boxes by the client. `star_on.png` remains bundled
for recovery but is not rendered. EXP still uses a private ready-state gold tint.
Level crowns and benefit visibility still follow server snapshots.

Migration note: old `openstore_out/over/press.png` files were 66 x 18 skin strips.
This version needs their complete 68 x 18 replacements and the matching new
client together. Back up old artwork; do not let an older client use these new
full-label store images. After migration, keep custom edits at the listed sizes.
