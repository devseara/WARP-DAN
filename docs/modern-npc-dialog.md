# Renewal NPC Dialog UI v3

WARP patch by **DevSeara**, registered as `ModernNpcDialog` (ID 10005), for the
profiled **2025-07-16 Ragexe** only. Install using the combined or upgrade diff
in the [package instructions](../README.md); restart WARP before selecting
**Renewal NPC Dialog UI** and applying your chosen patches to an original client.

## Appearance and scope

The design reference is Myth of Yggdrasil, using the supplied screenshots and
original button artwork. NPC text and choice panels are light blue (`#EEF7FF`),
with rounded pale-blue/white frames and a white footer. Choice-list OK and Close
buttons are centered as a pair, separated by 10 pixels.

Native text, script colors, item links, selection, scrolling, keyboard/mouse
handling, cursor callbacks and actions remain in place. No server changes or
DLL are required. The Close-labeled artwork also represents native Cancel;
the original Cancel action is retained.

The existing Apply buttons in Equipment/New Skills and Preview buttons in the
native Emotion/Item Collection lists are also reskinned. These exceptions match
the exact button and owning window; their other controls and frames are unchanged.
The patch does not add actions to windows that do not already contain them.

## Automatic artwork installation

Applying the selected patch creates missing parent folders beside the output
EXE and installs the 25 PNGs from `Assets/ModernNpcDialog` into:

```text
data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/genericsui/
```

Existing destination files, including customized artwork, are never overwritten.
Reapplying repairs missing files. Required source images are checked before any
copying; missing sources and directory/copy failures report errors. WARP test
mode does not access or install assets.

| Native button | PNG prefix | Dimensions |
| --- | --- | --- |
| Apply | `apply` | 44×18 |
| Buy | `buy` | 44×18 |
| Sell | `sell` | 44×18 |
| Preview (`btn_view.bmp`) | `chance` | 66×18 |
| Close / Cancel | `clos` | 44×18 |
| X | `cls_x` | 9×9 |
| Next | `next2` | 44×18 |
| OK | `ok` | 44×18 |

Normal/hover/pressed states use the corresponding supplied images. X reuses its
hover image when pressed. Buy and OK include disabled artwork; `sell_off.png`
is optional and not bundled. Other missing disabled images, missing runtime
PNGs or incorrect image dimensions fall back to stock button drawing. Native
button dimensions follow the supplied image dimensions.

The separate blank `genericsui/button` and frame-slice `genericsui/winbox` packs
are not used or bundled. The complete labeled PNGs and rounded NPC reference
define this implementation.

## Native implementation

The patch verifies original bytes before replacing four vtable draw slots
(offset `+0x50`):

- `UISayDialogWnd`: table `0x1033094`, stock draw `0x8B5F30`.
- `UIChooseWnd`: table `0x103316C`, stock draw `0x8B30D0`.
- `UIChoose3Wnd`: table `0x104ADE0`, stock draw `0x8B30D0`.
- `UIBitmapButton`: table `0x1029820`, stock draw `0x823E10`.

The 2025 `UIChoose3Wnd` variant shares creation/drawing with the base choice
window but has its own table and event handler. Both variants are covered;
their selection, scrolling and OK/Cancel actions are retained.

The NPC middle is a separate text child at parent `+0xB4`. Its native draw
(`0x807630`) clears the cached canvas using COLORREF at child `+0x8C`.
v3 verifies the full ten-byte instruction at `0x8AE357`, then changes its
initialization operand at `0x8AE35D` from gray `0xFFF2F2F2` to `0xFFFFF7EE`.
Native COLORREF conversion produces BGRA `0xFFEEF7FF`, so the middle is blue
before its first layout/paint, without waiting for the parent draw. The accepted
v2 choice-frame and button rendering is unchanged.

The bitmap-button hook checks the exact owner table before reading its bounded
resource basename, supports native small-string and heap storage, and composes
PNG alpha over clipped parent pixels. Unrelated controls use their stock draw.
No shared TextOut/item/enchant-grade renderer or input callback is replaced.

`AutoCombatUI.nativeHelpers` and `ModernChatUI.nativeHelpers` supply the native
canvas/PNG builders. Both scripts and exports must be installed, but neither
Auto Combat nor Chat UI needs to be selected. The installation diffs include
these dependencies; exporting helpers does not enable either feature.

## Verification and acceptance

Run from the package folder:

```powershell
node tools/test_modern_npc_asset_install.js
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_npc_dialog.py path/to/patched.exe
```

The installer test covers all 25 images, directory creation, repeat/repair,
preservation of edited files, optional Sell disabled artwork, test-mode isolation
and explicit errors. The native regression executes emitted x86 with documented
UI boundary doubles, including actual NPC creation and the first child draw at
three sizes, both choice variants, centered button spacing, exact PNG pixels,
clipping, all button states, owner scopes, string storage and missing resources.
It also checks native mouse capture/hover/release, action IDs, hand cursor,
outside-release cancellation, disabled cancellation and unchanged callbacks.

The optional `--accepted-v2 path/to/previous.exe` compares both choice variants
and all OK/Close button states pixel-for-pixel against the accepted v2 client.
The v3 first-paint test fails on the previous gray initialization and passes
on v3. Chat layout, controls and inline item-icon regression tests also passed
on the combined v3 build. Fresh and incremental package installations are
checked separately against the compatible WARP baseline.

**Live v3 visual acceptance remains pending.** Offline tests and generated frame
previews are not running-game screenshots. After restarting the client, verify
NPC text/Next/Close, both choice dialogs and their keyboard/mouse behavior;
then check Buy/Sell, Apply, Preview and X where those native buttons exist.
Confirm that the shop/preview layout accommodates the supplied button widths.
