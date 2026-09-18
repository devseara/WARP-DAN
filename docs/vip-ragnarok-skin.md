# Readable compact VIP design — September 18, 2026

The native main window is 460x362, matching the approved compact size. The latest
approved 1412x1114 raster `Assets/VipUI/vip_design.png` is an unmodified
source-region atlas for the blue/silver frame, title, gold emblems, information
icons, EXP bar, level slots and lower panels. The small winged VIP emblem sits
immediately left of the membership message. Benefit cards have a gold crown
and left-aligned live labels.

The button PNGs are drawn directly at their native dimensions by
`tools/render_vip_readable_buttons.py`, not reduced from the mockup. All 15
controls have four complete PNG states with centered, readable captions. Main
actions are 128x22, main Upgrade/Refresh 60x20. See [button geometry](vip-ui-buttons.md).

Every sample account field is erased before drawing server-owned values: name,
dates, status, EXP, crowns, requirements, benefits and Zeny. Main live text is
bounded 11px regular; the canonical name uses a private 11px regular UTF-8/GDI
helper. Start date is RGB #238B35, expiry #C93636, labels navy. Live client
fonts are used, not rasterized sample text. The existing native Alt+Q character
compositor keeps costume priority and fits within the private portrait surface.

Purchase, upgrade confirmation, ticket/item requirements, submit confirmation
and buffs confirmation use nine-sliced matching frame/title chrome and a gold
emblem. Membership offers retain blue bevels and gold selection. All popups are
centered over the parent with unchanged dimensions and updated readable PNGs.

Only private VIP code/artwork changes. VIPU v4 packet sizes, quotes, cooldowns,
permissions, capture/modal ownership and server behavior are unchanged. The
append-only private API is 372 bytes; old member offsets are unchanged. The
compiled payload has no imports. A compiler relocation-container DLL is only
a build artifact: no DLL is installed or required by the client.

WARP now bundles 60 new button PNGs plus the approved atlas. Applying Native
VIP UI automatically creates `data/texture/<client UI prefix>/vipui` beside the
output EXE and copies all 63 required images when missing. Existing artwork
is never overwritten by ordinary builds; missing files are repaired. Merely
toggling the checkbox does not create the folder. The output EXE and resource
folder must travel together.

The filename cleanup removes `readable_` from all 60 button files and renames
the atlas to `vip_design.png`, without changing any image bytes. Only the atlas,
membership crown, item-box background, and 60 button states are bundled.
Old designs and unused compatibility PNGs are archived outside the active
VIP folders. An updated client is required; old EXEs keep their old references.
The saved `VIP UI Main.yml` profile is unchanged. No server, account, database,
Battle Pass or Gacha settings are changed.

Verification runs emitted x86 offline: all 60 button states, hit bounds, missing
art guards, five popup modes, 0..10 crowns, four-row scrolling, stale/malformed
requests, purchase safeguards and portrait ABI. Both combined BP/Gacha and
saved-profile candidates are tested. The installer is exercised on actual
temporary Windows directories for first install, repeat and partial repair.
Offline previews have an empty portrait because no live actor is present.
Final in-game fonts, sprites and scaling still need visual acceptance before
replacing the working executable.

The older `render_vip_ragnarok_skin.py` is a legacy exporter, not a way to
reproduce the approved atlas. Keep the new atlas at exactly 1412x1114.

## Interaction fixes — September 18

No artwork or window dimensions changed. The countdown is now painted last at
y168 in a 14px cell: the membership background previously covered its lower
pixels. Clipped benefit rows expose their complete bounded text through the
native hover tooltip, following the current scroll position.

Upgrade Yes and ticket requests now serialize behind refresh acknowledgements
and the server's 300ms gate. The parent stays visible while waiting; duplicate
requests, automatic mutation retries and stale queued requirements are blocked.
All changes are private to the VIP client payload. No server changes or restart
are required. The previous approved design and assets remain intact.
