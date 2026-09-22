Gacha v22 editable images

Copy this folder to data/texture/<UI prefix>/gachaui. WARP installs missing
images only and preserves your replacements. Do not delete old shared assets.

banner_1.png = Prontera / machine 1; banner_2.png = Payon / machine 2.
Set .BannerImage$ in gacha_zeny.txt to any custom PNG filename in this folder
(max 140x60). Empty uses banner_<MachineID>.png. Filenames: max 63 ASCII
letters/digits/underscore/dash/dot; .png extension; no folders or double dots.
.WindowTitle$ edits the title bar; .BannerHeading$ edits the sidebar heading.
.BannerText$ edits each caption; empty uses .MachineName$.
common/rare/epic/legendary.png = original rarity boxes (36x35).
rarity_star.png = 9x9 star; arrows use arrow_on/off_left/right.png.
zeny.png = original user-supplied marketui/itembox_00.png (161x18); the client
draws its blue Z region without changing the file. Standalone <=26px icons work.
Item images are NOT included here. Rewards, featured items, tickets and rolling
icons always use the normal client item database and item resources. Changing
an item does not require adding or replacing any item_* file in gachaui.

Button backgrounds: button_<ID>_<out|over|press|off>.png.
Keep the original dimensions. Captions are native text, not baked into images.
1 Close; 2 Last Pull; 3 Prizes; 4 History; 5 Spenders; 6 Legendary Winners;
9 Admin; 10 Pull x1; 11 Pull x5; 12 Pull x10; 13 Reset This Machine;
20 Cancel; 21 Confirm; 22 Reset; 23 Cancel Reset; 35 Banner Back;
36 Banner Next; 39 Motion on/off; 40 Skip Reveal.
Currency backgrounds: currency_zeny_*.png (136x24),
currency_ticket_*.png (104x24); states out, selected, off.
These compact widgets show only the icon and balance, with no name caption.
Default backgrounds are white; selection and mouse press use gold highlighting.

Sources/configuration and test instructions: docs/gacha-events-v22.md in WARP
and doc/gacha-events-v22.md in rAthena. This artwork alone does not enable
ticket payment: the matching client, map/char server and SQL upgrade are needed.
