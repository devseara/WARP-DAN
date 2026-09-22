# Readable VIP artwork and buttons

The native main window is 460x362. Its frame/icons use the unchanged approved
`vip_design.png` (1412x1114). As of September 22, all controls use the same
four blank Gacha-style backgrounds, nine-sliced with two-pixel borders.
Captions, headings, prices and status text use the native 11px regular font
used by Membership active. The control bounds below remain unchanged; the
prefixes are control names, not current resource filenames.

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

The four shared files are `button_out.png`, `button_over.png`,
`button_press.png`, and `button_off.png` (51x20), copied unchanged from Gacha's
pull-button skins. Normal captions use Gacha's blue-gray COLORREF 0x7D6045;
disabled captions use 0xA0A0A0. Keep the source dimensions when editing.
Only the seven currently referenced images are bundled. The old per-control
caption PNGs and unused notice board have been removed from the asset folder;
the historical exporter remains available for restoring older clients.
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
`data/texture/<client UI prefix>/vipui` beside the output EXE. It copies all 7
required images only if missing, preserving customized existing artwork and
repairing partial folders. Keep this resource folder with the output EXE if
moving it. Fully restart the client after editing images.
Select **Native VIP UI** and build the client to install all four button-state
PNGs automatically; no separate button patch or manual image generation is
needed. Selecting the checkbox without building does not write any images.
The other three required PNGs are `vip_design.png`, `membership_crown.png`,
and the user's supplied 19x19 `item_main_bg.png`, unchanged.
Quest item boxes scale the same box to 32x32. Main-window earned crowns are
drawn over each level slot separately. The renderer trims transparent padding
(alpha below 32), caches those bounds, and aspect-fits the actual crown into
the 17x17 inner box using 4x4 premultiplied-alpha sampling. It never edits the
original PNG. Purchase-card crowns use the same fitting rule.
The notice is native text only; `board_txt.png` is no longer loaded or installed.
The blue frame behind the level/slots/quest text is removed. The EXP track and
fill are gold at every percentage; this does not grant upgrade permission.
Retired API slots, including slot 0, stay null. All offsets
and the 372-byte API / 2664-byte VIPU v4 snapshot remain unchanged.

The filename cleanup requires rebuilding the client; an older EXE still refers
to the old names/layout. Back up existing images before a one-time migration,
including older files whose names collide with the newly renamed buttons.
Ordinary WARP builds preserve custom files and never prune arbitrary images.
The September 22 local cleanup moved 61 unused PNGs from each of the WARP and
installed-game VIP folders into `Outputs/vip-assets-cleanup-20260922`, outside
both active asset folders. Older client rollback may require restoring those
images along with its executable. Asset inventory/installer tests now reject
unused images in the WARP bundle; the installer still preserves custom files
already present in other users' game directories.
