# RO Global Zero Menu Assets

The menu patch uses complete row-specific backgrounds rather than drawing a
cropped portion of one fixed-height image.

Sources:

- menuicon/bg_menu_357x322.tga: supplied 357x322 New UI frame.
- menuicon/bg_menu_old.tga: supplied 220x184 Classic UI frame.
- menuicon/bt_autohunt*.bmp: supplied New and Classic Auto Hunt button states.

Generated runtime backgrounds:

- bg_m1.tga through bg_m6.tga: width 357, height rows * 61 + 17.
- bg_o1.tga through bg_o6.tga: width 220, height rows * 43 + 12.

Regenerate with tools/render_roglobalzero_menu_backgrounds.py. The generator
preserves the complete top and bottom caps and resizes only the center band.
ROGlobalZeroMenu.qjs selects one complete image from the live visible-control
count. Copy the generated files and button states to
data/texture/<basic-interface>/uirenewal/menuicon in the client data tree.