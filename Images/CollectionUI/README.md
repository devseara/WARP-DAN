# Card Collection UI assets

Production bitmap pack for the accepted white Banquet of Heroes collection UI.

Fixed chrome and controls deploy to
`data\texture\À¯ÀúÀÎÅÍÆäÀÌ½º\item_collection\`. Dynamic 75x100 item
art remains in the existing `collection\<identified-resource>.bmp`
namespace and is never copied or renamed by this patch.

## Target

- Native logical window: 760×540.
- Fits an 800×600 client with 20 px horizontal and 30 px vertical clearance.
- All dynamic collection artwork is drawn 1:1 at 75×100.
- Game assets are 24-bpp, uncompressed `BI_RGB` BMPs.
- Exact `#FF00FF` is the color key for irregular controls/icons. Opaque body, title, and card art are never color-keyed.

## Collection-owned assets

| Asset | Size | Purpose |
|---|---:|---|
| `chrome/title_bar_760.bmp` | 760×17 | Approved AutoHunt title bar, extended only through its repeat-safe center. |
| `chrome/bg_collection.bmp` | 760×523 | White opaque body with native blue-gray edge. |
| `icons/icon_collection.bmp` | 16×16 | Title icon. |
| `icons/badge_locked.bmp` | 16×16 | Missing-card semantic overlay. |
| `icons/badge_complete.bmp` | 16×16 | Completed-card semantic overlay. |

Rebuild these assets with:

```powershell
powershell.exe -ExecutionPolicy Bypass -File .\tools\build_collection_ui_assets.ps1
```

The build also writes `preview/contact-sheet.png` and validates every BMP as 24-bpp RGB.

## Reused assets

`reused/` contains byte-identical copies of stock controls selected for production use:

- blank four-state, horizontally tileable generic buttons;
- four-state close button;
- search edit background and four-state magnifier button;
- scrollbar track/thumb/arrows;
- three-state plus/minus steppers;
- Zeny icon;
- optional native completion ribbon;
- native 75×100 missing-art fallback.

`reused/PROVENANCE.md` records the exact loose/GRF source for every copied file. Button text such as Deposit, Withdraw, Activate Bonus, Submit, tabs, and filters is deliberately not baked into BMPs.

## Runtime contract

Card art is resolved without a manual image table:

```text
ItemId
  -> CItemInfoManager
  -> identified resource stem
  -> collection\<resource>.bmp
```

Use `reused/artwork/fallback_question_mark.bmp` only when the resolved collection artwork is missing. Draw real collection art as an opaque 75×100 image because artwork may legitimately contain magenta. Use color-key drawing only for irregular controls and semantic badges.

The shell is shared by Cards, Combo Collections, and Total Bonuses. All labels, progress, panel/card borders, selection, status pills, counts, fees, Zeny values, and bonuses remain runtime-rendered for localization and authoritative state updates.

See `layout.yml` for coordinates and `asset-manifest.yml` for the loading contract.
