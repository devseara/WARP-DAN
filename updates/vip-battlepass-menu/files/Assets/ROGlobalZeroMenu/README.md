# RO Global Zero Menu assets

Target client: 2025-07-16.

The New UI menu uses complete row-specific backgrounds. Classic UI suppresses
the custom full-panel background and sizes its parent to the icon grid.

## Runtime assets

- menuicon/bg_m1.tga through bg_m7.tga: New UI backgrounds, width 357 and
  height rows * 61 + 17.
- menuicon/bg_menu_357x322.tga: source art for the New UI row generator.
- menuicon/bg_o1.tga through bg_o7.tga: Classic row backgrounds retained for
  stock resource selection; the custom Classic draw path is suppressed.
- menuicon/bg_menu_old.tga: source Classic frame retained by the generator.
- menuicon/bt_autohunt_normal.bmp, bt_autohunt_mouseon.bmp, and
  bt_autohunt_pressed.bmp: native New UI Auto Hunt states.
- menuicon/bt_autohunt_old_normal.bmp, bt_autohunt_old_mouseon.bmp, and
  bt_autohunt_old_pressed.bmp: native Classic Auto Hunt states.
- Item Collection contributes a ten-file user-approved New/Classic set from
  `Images/CollectionUI/menuicon/`; its asset-copy callback deploys all aliases
  into this runtime namespace while the native child consumes six states.

Regenerate row backgrounds with tools/render_roglobalzero_menu_backgrounds.py.
The generator preserves the complete top and bottom caps and resizes only the
center band.

## Runtime contract

The menu has 25 native command entries in five columns. Its height is:

    ceil((visible native commands + visible custom buttons + MENU) / 5)

Auto Hunt, Item Collection, AutoSupport, Bestiary, VIP and Battle Pass are real native UIButton children
appended after the compact native-command count. They fill unused columns in
the last native row before another row is allocated and compact again when an
earlier custom button is hidden. MENU remains a counted bottom-right occupant,
which preserves the close, hidden warp/teleport, and reopen surface invariant.
All custom buttons use stock UIButton drawing, hit testing, hover, pressed
states, and child-tree ownership.

Battle Pass is an optional `BattlepassUI` producer after VIP. Its 12 shield-icon
BMPs are supplied in `Assets/BattlepassUI/menuicon/` and automatically copied to
the shared runtime menu directory. Both VIP and Battle Pass install the seventh
row backgrounds, preserving any existing client-side images. The maximum is
seven rows with all 25 native commands, six custom controls and MENU visible.

On create, reopen, and post-MakeWindow paths, ROGlobalZeroMenu reapplies layout
and refreshes the WindowManager rectangle without replaying native OnCreate.
The New MENU normal icon has a parent-canvas fallback drawn with the native
clipped UIWindow compositor. Classic uses its native toggle and draws no custom
full-panel background.
