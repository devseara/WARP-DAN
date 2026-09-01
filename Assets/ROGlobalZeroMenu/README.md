# RO Global Zero Menu assets

Target client: 2025-07-16.

The New UI menu uses complete row-specific backgrounds. Classic UI suppresses
the custom full-panel background and sizes its parent to the icon grid.

## Runtime assets

- menuicon/bg_m1.tga through bg_m6.tga: New UI backgrounds, width 357 and
  height rows * 61 + 17.
- menuicon/bg_menu_357x322.tga: source art for the New UI row generator.
- menuicon/bg_o1.tga through bg_o6.tga: Classic row backgrounds retained for
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

The menu has 25 native command entries in five columns. Its height is always:

    ceil(visible native commands / 5) + 1 permanent control row

The permanent row prevents close, hidden warp/teleport, and reopen from
constructing a shorter surface. Auto Hunt and Item Collection are real native
UIButton children in the first and second control-row columns. The native MENU
toggle retains the last slot. Both custom buttons use stock UIButton drawing,
hit testing, hover, pressed states, and child-tree ownership.

On create, reopen, and post-MakeWindow paths, ROGlobalZeroMenu reapplies layout
and refreshes the WindowManager rectangle without replaying native OnCreate.
The New MENU normal icon has a parent-canvas fallback drawn with the native
clipped UIWindow compositor. Classic uses its native toggle and draws no custom
full-panel background.
