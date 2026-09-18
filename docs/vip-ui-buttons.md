# Readable VIP artwork and buttons

The native main window is 460x362. Its frame/icons use the unchanged approved
`vip_design.png` (1412x1114); all interactive controls use full native-size
PNG files with centered captions. No button is scaled or labeled at runtime.

| Main filename prefix | Native x,y | Width,height |
| --- | --- | --- |
| main_close | 439,3 | 18,18 |
| applyvip | 153,120 | 128,22 |
| openstore | 289,120 | 128,22 |
| openstorage | 153,145 | 128,22 |
| vipbuffs | 289,145 | 128,22 |
| main_upgrade | 164,252 | 60,20 |
| refresh | 164,320 | 60,20 |
| scroll_top | 439,268 | 10,10 |
| scroll_bot | 439,328 | 10,10 |

| Popup filename prefix | Size | Use |
| --- | --- | --- |
| close | 15x18 | Popup X |
| yes | 28x18 | Confirmation |
| no | 23x18 | Decline |
| upgrade | 53x18 | Requirement submission |
| cancel | 43x18 | Close popup |
| purchase | 56x18 | Buy selected duration |

Every prefix has `_out.png`, `_over.png`, `_press.png`, and `_off.png` files:
60 complete PNGs. `tools/render_vip_readable_buttons.py` deterministically draws
these controls with centered Tahoma Regular captions: 12px main, 11px popup.
Disabled captions stay readable charcoal. Keep exact dimensions when editing.
Missing/mis-sized normal artwork disables its action; invalid optional states
fall back to normal. Alpha and the native magenta color key remain supported.
All five popup modes use the matching blue/silver frame and gold VIP emblem.

Apply VIP requires inactive membership and no pending payment. Store/storage
require active VIP; Store additionally requires permission. Buffs requires
server-confirmed eligibility and no cooldown. `Buffs: HH:MM:SS` sits at y168,
below the right action column, in a reserved 14px cell with dark navy text. It is
drawn after every atlas/background patch so no lower glyph pixels are erased.
Upgrade and EXP
readiness remain server-authoritative. Purchase requires an explicit duration
selection and echoes the server's quote; selection or canceling never pays.
Upgrade confirmations keep the parent visible while a single request waits for
the server reply. Other actions are disabled while pending; Close stays usable.
See [request sequencing and tooltip behavior](vip-ui.md).

When Native VIP UI is applied during a WARP build, its installer creates
`data/texture/<client UI prefix>/vipui` beside the output EXE. It copies all 63
required images only if missing, preserving customized existing artwork and
repairing partial folders. Keep this resource folder with the output EXE if
moving it. Fully restart the client after editing images. Filenames have no
`readable_` prefix: for example `applyvip_out.png` and `main_upgrade_over.png`.
The other three required PNGs are `vip_design.png`, `membership_crown.png`, and
`item_main_bg.png`. Retired artwork is no longer bundled. Old private API slots
are null rather than removed, preserving all runtime offsets.

The filename cleanup requires rebuilding the client; an older EXE still refers
to the old names/layout. Back up existing images before a one-time migration,
including older files whose names collide with the newly renamed buttons.
Ordinary WARP builds preserve custom files and never prune arbitrary images.
