# Equipment UI redesign contract

Target client: 2025-07-16 (`Exe.BuildDate === 20250716`).
## Current production contract

The current patch selection enables General, Costume, Title, and Damage
Indicator rail states, the 280x240 main-window size, main-row geometry,
matching hit geometry, the draw-epilogue tiled-surface lock, safe legacy-tab
hiding, footer relocation, native mode switching, and the docked Swap child.
The stock four-tab child is still constructed and added to its native parent
before `SetVisible(false)` is dispatched through its vtable; ownership and
destruction therefore remain stock. The renewal rail re-exposes native modes
0 through 3 without replacing their page objects or event handlers. General
provider indices 0 through 9, render-coordinate indices, and
both profiled picker results remain native and unpermuted. This preserves the
live-confirmed head order: Apple of Archer in upper head, Sunglasses in middle
head, and Romantic Leaf in lower head. Pseudo iteration 10 alone translates
its provider argument to native ammunition slot 15 and draws it at the footer
arrow circle, then exits before the synthetic row can use stock name/overlay
coordinates. Both slot pickers now select native slot 15 at the footer cell before the
stock body-only vertical prefilter, without rewriting their result-object
contract. The centered avatar, rail hover labels,
and rail click bridge are selected. Costume uses the native mode event and
retains the native `View Costumes` checkbox/configuration packet. Swap remains
the native child, provider, tooltip, interaction, and packet owner; only its
frame, background, item coordinates, and matching pick geometry are redesigned.


The `RedesignedEquipmentWindow` patch owns the profiled Alt+Q constructor,
equipment-row renderer, equipment-slot hover and click pickers, resource
redirects, runtime background layers, native mode bridge, rail tooltip bridge,
footer-control coordinates, and asset deployment. It does not replace native
item identity, tooltip construction, drag/drop handlers, equip/unequip packets,
swap packets, or the shared item-name text bridge.

### Stable item tooltip anchor (2026-10-14; live verification pending)

The native item picker already uses 35px rows starting at y=29. Its tooltip
anchor still divided by 24 and advanced by 26, so moving inside one equipment
slot could move the same item balloon between several positions. The anchor
now uses the picker's row formula, with x=56/225 and y=9+35*row. The footer
ammunition cell has a fixed y=171 anchor and retains x=120. Native item
selection, label formatting, color bridges and tooltip calls are unchanged.
The actual emitted coordinate code passes 4,368 positions across both columns,
all five rows, normal/expanded widths, vertical offsets and the Arrow cell.
`tools/verify_equipment_tooltip_anchor.py` reads an existing client and executes
the patch in memory; it creates no game EXE and does not establish live acceptance.

The supplied assets are copied to:

`data/texture/<client UI prefix>/uirenewal/equipmentui`

The Equipment body uses the original assets directly at runtime:

- `bg.png` (`280x240`) is the window background at `(0,0)`.
- `bg_primary.png` (`245x202`) is the local General body at `(34,17)`.
- `bg_primary2.png` (`245x202`) is the viewed-character and Costume body at `(34,17)`; its baked caption is `Secondary`.
- `bg_empty.png` (`1x1`, transparent) suppresses slot artwork while the native Title or Damage Indicator page owns the body.
- `menu_primary_tabs.png`, `menu_costume_tabs.png`, `menu_title.png`, and
  `menu_damage.png` are the four selected rail states at `(0,17)`. The
  unique General/Costume names avoid stale two-icon entries in loaded GRFs.
- The Title medal and Damage impact glyphs use the approved generated source normalized into the existing pale periwinkle pixel palette.
- `bg_swap.png` (`102x240`) is the native Equipment Swap child at `(280,0)` when open.
- `ibox_shadow.png` (`32x32`) replaces the stock drag-compatible `item_invert.bmp` overlay.
- `swapr_out.png`, `swapr_over.png`, and `swapr_press.png` retain the native Swap apply-button states.
- `icon_falcon.png` and `icon_peco.png` occupy the shared native mount-status cell only while their corresponding option bit is active.
- `icon_cart.png` occupies the Cart-status cell only while the native Cart state is present.

No `bg_primary_legacy_body.png` or `bg_secondary_legacy_body.png` resource is
referenced. The generated composite files were removed from the patch assets.

The patch resizes both native factories to 280x240: the local-character
`UIEquipWnd` stored at the window manager's `+0x1E0`, and the viewed-character
instance stored at `+0x3FC`. Leaving the second factory at its stock 167-pixel
height clips the lower accessory rows even though the redirected body is
240 pixels tall. The patch also clears both profiled sources of the inherited
20-pixel tab/content offset: `UIEquipWnd+0xF4` in the constructor and the
initializer's separate height delta. The runtime body
continues to draw at `(34,17)`, while normal item origins now land two pixels
inside the PNG cells, overlays land fourteen pixels inside them, and native hit
rows start at the PNG cell boundary. The native drag-compatible slot pass keeps
its stock `UIEquipWnd+0xB8/+0xBC/+0xC0` compatibility state and draw loop, but
uses `ibox_shadow.png` at renewal cell origins `(56,29)/(225,29)` and
`(56,64+35n)/(225,64+35n)` instead of the legacy `(4,25)/(248,25)` and
26-pixel grid. The legacy horizontal four-tab child remains constructed and
parent-owned, then is hidden through `SetVisible(false)`. General and Costume
retain their custom Equipment bodies; Title and Damage Indicator select
`bg_empty.png`, allowing their stock children to own the page without slot-art
bleed-through. The native Title list moves from `(3,39)` to `(34,39)` and uses width 243.
Keeping Y=39 preserves the native selected-title header row above the list.
That bold header uses the same renewal bounds, X=34 and width 243, so its
centered text aligns with the list rather than the legacy full-window center. Three complete native Damage Indicator cards are shown at `x=34+64n`: `34`,
`98`, and `162`. Five native choices are exposed through two stable scrollbar
positions. Rendering and hit testing both map the logical page start to
`2*scrollPosition`: position 0 shows `Default`/`Enhanced`/`New Number`, and
position 1 shows `New Number`/`8 Bit`/`Empty`. The native maximum remains
`max(choiceCount-4,0)` while the visible capacity is 3, avoiding the
unreachable center position and every partially clipped card. The three native
64x92 card states are retained without cropping:
`damage_card.bmp`, `damage_card_hover.bmp`, and
`damage_card_selected.bmp`. Their native dotted rectangular edge pixels are
preserved. Normal cards remain quiet, hover uses the lavender state, and only
the selected card uses the green state. Every label foreground/shadow pass is
centered inside the same 64-pixel column, with the selected label using a
12-pixel font. This preserves the profiled layout and its visible dotted card
separators while keeping all four checkboxes and cards aligned clear of the rail.
`UIEquipWnd+0x134` remains the native Damage scrollbar but is initialized at
`x=34`, `y=153`, and `width=parentWidth-34`, keeping both arrows and the
track inside the content body instead of underneath the rail.

All four selected rails are drawn at the profiled Equipment epilogue
`0x008B3687`, after the stock mode-specific parent pass and the
`UIEquipWnd+0x124` draw. This keeps every inactive and selected icon visible
immediately when Alt+Q opens; drawing any rail only at the earlier body hook
allows native page rendering to cover otherwise valid cells.

The native character preview is pinned to primary-canvas X=156 instead of the
resizable parent-window midpoint. Expanding the parent to 382 pixels for Swap
therefore cannot move the avatar away from the renewal shadow. Mouse movement
over the four local-character rail cells shows `General Equipment`,
`Costume Equipment`, `Title`, and `Damage Indicator` through the stock
coordinate conversion and tooltip manager. Their tooltip origin replays the
native control offset `(mouseX-16, mouseY-13)` and native control flags, which
places the dark balloon above the cursor like stock item hover. The cells
dispatch notification `0x16` with native modes 0 through 3 to the profiled
Equipment mode handler. Viewed-character windows retain only the stock-supported
General/Costume modes. No replacement Costume, Title, or Damage page is
fabricated by the rail bridge.

The four-cell upper bound is decimal 153 and must use the imm32 encoding
`CMP EAX,0x99` (`3D 99 00 00 00`). The shorter `83 F8 99` form sign-extends
`0x99` to `-103`, causing every positive mouse Y to fall through to stock and
making the entire renewal rail appear non-clickable.

The five native action controls highlighted in the live screenshot retain their
original objects and event handlers. Their Y coordinates change from 167 to the
footer baseline at 220; the ability control's separate data-backed Y coordinate
is changed by the same rule. The legacy `btn_off` artwork is hidden, but its
stock Equipment click notification `0x06` with control ID `0xF8` remains the
release owner. Active Falcon
(option bit `0x10`) or Peco/Riding (`0x20`) state draws the matching supplied
icon in the shared mount cell. Native Cart presence draws `icon_cart.png` in the
next cell at `(170,191)`. The stock 30x20 `btn_items_off`/`btn_items_on` child
(native control ID `0xF9`) is placed at `(167,171)` while Cart is active in its
constructor and both native runtime layout paths. This centers the button over
the 24x22 Cart base horizontally while placing its bottom edge immediately
above the Cart icon at `y=191`. When Cart is inactive, the same native
condition moves the control to `y=410`, outside the Equipment window, removing
both its artwork and hit target while retaining the native child object and
handler. The constructor always assigns the stock message `0xED` tooltip to
that child, even when Cart is initially inactive, so later Cart activation
restores the original `Cart Items [Alt+W]` native balloon without adding a
custom tooltip renderer. Parent-owned status areas retain the `Release Falcon`,
`Release Pecopeco`, and `Release Cart` balloons and stock `0xF8` release
dispatch; the Cart-conditioned Items child retains its stock `0xF9`
interaction.

The status renderer, footer click bridge, and mouse-hover bridge use rel32 near
conditional exits for their stock fallbacks. These caves exceed the signed
8-bit branch range; shortening those exits to rel8 wraps their destinations
back into allocation data and causes an access violation on ordinary hover.

Only the two legacy item-name draw sites that service the ten main rows are
suppressed. Native item sprites are moved onto the five-by-two renewal grid.
In General mode, stock provider arguments 0 through 9, render-coordinate
indices, and both native picker results remain unchanged. With the inherited
20-pixel offset cleared, that native order aligns directly with the PNG cells.
The renderer loop extends from ten to eleven iterations; pseudo iteration 10
alone retrieves native ammunition slot 15 and uses item coordinates
`(117,191)`. After that fixed item draw, the synthetic row jumps to the native
item cleanup instead of running stock name/status/empty-overlay drawing with an
eleventh-row coordinate pointer. The separate legacy ammunition preview at
`0x008B35AF` now jumps directly to its native cleanup/control continuation at
`0x008B3603`; this removes the width-relative Arrow copy that moved when Swap
expanded the parent. The hover picker and the independent `0x0089E460`
click/double-click/drag picker test the complete `(117,191)..(141,215)` footer
arrow-circle bounds at their common initialization point and return native
index 15 before the stock body-only Y prefilter can reject the footer. Their
non-Arrow paths replay the exact overwritten initialization and resume stock at
the original `UIEquipWnd+0xF4` load. The native item balloon
text is retained as render identity and formatted as `Unequip %s` only inside
that footer cell. The native center-column balloon anchor no longer reads the
expanded parent width: its local X remains `120` before stock screen-coordinate
conversion, matching the closed 280-pixel primary canvas when Swap expands the
parent to 382 pixels. Costume mode retains its stock ten-iteration renderer and
native indices.

The stock Costume-only `equipwin_special.bmp` body is skipped so it cannot
cover `bg_primary2.png` or draw a duplicate character. `UIEquipWnd+0xDC` and
`UIEquipWnd+0xE0` are the native 80x12 `Show Equip` and `View Costumes`
checkboxes, not replacement Equipment panels. Their stock mode-dependent
visibility and event ownership are retained. This restores the client
configuration packet that updates the character's saved costume-view flag and
lets the server re-run its native costume look update. Native Costume item
retrieval and interaction remain active in the redesigned main body.

Equipment Swap remains the native child and packet owner, but opens docked at
`(280,0)` with size `102x240`, expanding the parent to `382x240`. Closing it
restores `280x240`. Its stock background and character/text preview are
replaced by `bg_swap.png`; the ten native item sprites use the two five-row
columns in stock identity order: `[8,0,1,2,3]` and `[9,4,5,6,7]`. No native
slot is substituted with ammunition. The hover, click, and drag pickers return
the same identities from matching geometry. The Swap child retains the native
lifecycle mode, item-provider selection, and tooltip selection owned by the
parent. Costume mode is passed through unchanged rather than forging a Costume
Swap child into the General dataset. Swap item and overlay origins sit two pixels inside the PNG cell boundaries at
X 14/60 and Y 31/66/101/136/171; picker rectangles remain aligned to the full
cells. The apply button remains native at `(31,220)` with the supplied
`swapr_*` states.

The patch is incompatible with `NoEquipSwap` and `NoEquipWinTitle`. Any future
change to `CustomColoredItemName`, `ExtNameTextStatic`, or shared TextOut
surfaces must repeat the normative item-grade renderer gates and live Alt+Q
acceptance matrix.
