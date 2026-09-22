# Renewal NPC Dialog UI (DevSeara)

Select **Renewal NPC Dialog UI** (`ModernNpcDialog`, ID 10005) in WARP.
Reload WARP if it was already open when the patch was installed. Targets the
profiled **2025-07-16 Ragexe** only; other builds are rejected. Apply to an
original client using the rest of your usual selected patches.

The design reference is **Myth of Yggdrasil**, using the user's supplied
screenshots, PNGs, and `2026-09-14 12-07-30.mp4`. Its rounded frame, button
styling, and spacing are the visual baseline. Per the user's explicit color
request, both NPC text and choice panels are light blue (`#EEF7FF`).

The NPC text and choice windows gain rounded pale-blue/white frames, light-blue
content panels, and a white footer. Choice-list OK and
Close buttons are centered as a pair with a 10px gap. Native NPC text, script
colors, item links, selection, scrolling, keyboard handling, events, packets,
and cursor callbacks are retained. No server changes or DLL are needed.

## Supplied artwork

The 25 original PNGs are bundled under `Assets/ModernNpcDialog`. Applying the
diff creates this path beside the **output executable**, then copies missing
images only:

```text
data/texture/À¯ÀúÀÎÅÍÆäÀÌ½º/genericsui/
```

Existing destination files are never overwritten, including user-edited PNGs.
Reapplying repairs missing files. The source pack is checked before copying;
missing required files and directory/copy failures report errors. Test mode
does not access assets. The unused duplicate `buy_ouy.png` is not bundled.

| Existing native button | Supplied PNG prefix | Size |
| --- | --- | --- |
| Apply | `apply` | 44×18 |
| Buy | `buy` | 44×18 |
| Sell | `sell` | 44×18 |
| Preview (`btn_view.bmp`) | `chance` | 66×18 |
| Close / Cancel | `clos` | 44×18 |
| X | `cls_x` | 9×9 |
| Next | `next2` | 44×18 |
| OK | `ok` | 44×18 |

Out/over/press artwork follows the native normal/hover/pressed states. X uses
its supplied hover image when pressed because there is no separate pressed
image. Buy and OK include disabled artwork. `sell_off.png` is optional; other
missing disabled images fall back to the original disabled rendering. Missing
or incorrectly sized runtime PNGs also fall back to the original button.
Native button dimensions are updated to the supplied image dimensions once.
No extra Apply, Preview, or X action is invented in windows that lack it.

Ordinary NPC dialogs do not contain Apply or Preview. At the user's request,
the existing Apply buttons in Equipment/New Skills and Preview buttons in the
native Emotion/Item Collection lists are also reskinned. These are exact
button-and-owner exceptions: their other controls and frames remain unchanged.

The separately supplied `genericsui/button` folder contains blank three-slice
and nine-slice stretchable button backgrounds. `genericsui/winbox` contains
window-frame slices, including 17px top strips and 3px/28px bottom variants.
They were inspected but are not used by this patch; the complete labeled PNGs
and the supplied rounded NPC screenshots define this implementation.

## Native implementation and safeguards

Only four vtable draw slots (+0x50) are replaced:

- `UISayDialogWnd`: table `0x1033094`, original draw `0x8B5F30`.
- `UIChooseWnd`: table `0x103316C`, original draw `0x8B30D0`.
- `UIChoose3Wnd`: table `0x104ADE0`, original draw `0x8B30D0`.
- `UIBitmapButton`: table `0x1029820`, original draw `0x823E10`.

Both original frame draws call the stock tiled-frame routine `0x871340`.
Replacement frames use native canvas pixels with transparent rounded corners.
Choice child positions are updated through native SetPos `0xA23450`; list
dimensions, selected index (+0x94), first visible row (+0x98), and events are
not changed. Background RGB changes dirty the cached list (+0x58) once.

The 2025 `UIChoose3Wnd` variant has its own vtable and event handler, despite
sharing `UIChooseWnd` Create (`0x8A3FC0`), draw, and child layout. Its constructor
assigns the table at `0xA3C7DF`. v2 handles its frame and button ownership while
preserving event handler `0x8BE590`, selection, and native OK/Cancel actions.

The NPC text area is a separate child at parent +0xB4. Native draw `0x807630`
clears its canvas using COLORREF at +0x8C, so changing only the parent panel
cannot recolor it. v2 updates that field to `0xFFFFF7EE`, which native
`CSurface::Clear` converts to BGRA `0xFFEEF7FF`, and dirties the child once.
The shared text draw functions, script colors, and text content are unchanged.

v3 also changes the NPC-only initialization operand at `0x8AE35D` from
`0xFFF2F2F2` to `0xFFFFF7EE`, after verifying its full ten-byte MOV instruction.
This initializes the child background before text layout and its first draw,
instead of relying only on the parent-paint update. The choice frame/button
builders and their colors are unchanged from the accepted v2 appearance.

The bitmap-button hook first checks the exact owning-window vtable, then the
bounded normal-resource basename. Unrelated controls tail-call stock before
reading their resource path. It handles both native std::string SSO and heap
storage (+0xBC), checks path length, texture availability/dimensions, and
preserves registers and stack cleanup. PNG transparency is composited over
clipped parent pixels. Every native input/event/cursor slot is unchanged.

Apply's real resources were traced in Equipment Create `0x8A4B30` and New
Skills Create `0x976D70`; Preview's extensionless `btn_view` resource is joined
with `.bmp` in Emotion Create `0x86ABD0` and Item Collection Create `0x8A7770`.
These stock parent tables are `0x103223C`, `0x103F660`, `0x104B070`, and
`0x1032AAC`, respectively. Custom replacement windows with different tables
are intentionally not matched.

The existing `AutoCombatUI.nativeHelpers` and newly exported
`ModernChatUI.nativeHelpers` supply canvas/PNG code. Their scripts must be
installed, but neither UI patch has to be selected. Merely exporting helpers
does not change Chat UI. No shared TextOut/item/enchant-grade sink is patched.

## Verification and remaining acceptance

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_npc_dialog.py <patched.exe>
node tools/test_modern_npc_asset_install.js
```

The emitted x86 is exercised with explicit native UI boundary doubles:
responsive frames, centered buttons, native list color/state, exact PNG alpha
pixels, clipping, normal/hover/press/disabled states, exact owner scopes,
SSO/heap paths, missing resources, unchanged callbacks, actual native mouse
capture/hover/release, action IDs, hand cursor, outside-release cancellation,
and disabled-button cancellation. The installer test executes the actual QJS
onApplied function with filesystem doubles, including repeat/repair and errors.

Live acceptance is still required: open NPC text/Next/Close and choice dialogs,
exercise keyboard and mouse selection, then check Buy/Sell, Apply, Preview,
and X where those existing native buttons are available. Confirm the native
shop/preview layout accommodates the supplied button widths. An offline PNG
frame preview is not a screenshot of a running game.

For v1 on 2026-09-14, the full selected-patch build and a separate NPC-only build
completed with no skipped patches. Both passed the native NPC test suite;
all 25 deployed asset hashes matched the bundle in both output folders. The
standalone build confirms that selecting Chat UI/Auto Combat is not required.
The user's LastSession.yml and Settings.yml were restored byte-for-byte.
The installed game executable was not replaced. Full test output:
`Outputs/modern-npc-dialog-v1-20260914-113815/Ragnarok.exe`, SHA-256
`B31C3498EA08EEBE17147F1D8A94A87CA7AA5EED5BA784F0AC11613A033FD9EF`.

### v2 regression correction

The user's subsequent v1 installation (SHA-256
`16638501F77EEA6352BC573ED96D517C782187102C8CAE295DE0C23EDB870C34`) reproduced
the missed-variant bug offline: `UIChoose3Wnd` still had the stock frame and
its OK button fell back to `stock-button`. The original tests used only the
base choice vtable and did not execute the NPC child canvas draw. They were
expanded to cover both real choice vtables, normal/hover/pressed OK/Cancel,
the actual NPC text child draw, exact COLORREF conversion, state preservation,
and one-time invalidation. v2's full-profile build passed these regressions.

v2 output: `Outputs/modern-npc-dialog-v2-20260914/Ragnarok.exe`, SHA-256
`4818D84C14DED28EB18FF97AB9667945FACD047AB03110A8E9857AAD761E7A59`.
Live visual confirmation in the corrected client remains required.

With Ragnarok closed, v2 was installed to
`D:/AAARAGNAROK/Ragnarok Online/Ragnarok.exe`. The EXE, EPI, and secure metadata
all match the tested output hashes. The previous three files were backed up
and verified under `Outputs/modern-npc-dialog-v2-20260914/installed-before/`.
All 25 existing game PNGs were checked and left untouched. LastSession.yml and
Settings.yml were restored byte-for-byte. Chat layout, controls, and inline
item-icon regression suites passed using the user's current Century Gothic
12px Normal chat setting. Restart an already-open WARP before future patching
so it loads the v2 script instead of its cached v1 copy.

### v3: NPC middle panel, with accepted choices unchanged

The user accepted the light-blue choice window, but reported that the NPC
dialogue's middle area remained gray. The latest installed v2 client had hash
`2AAE551AA08A333A938AFEA5D20E030E865574A4937134F759D6D77E5C77C3E3`.
It still initialized the text child as gray in native `UISayDialogWnd::Create`
(`0x8AE2E0`), even though the parent draw later attempted to recolor it.

A new regression executes that actual Create routine and the first native
child draw without first painting the parent. It fails on the gray constructor
value in v2 and passes in v3. The test covers three sizes and preserves native
child dimensions, offsets, and text width. `--accepted-v2 <old.exe>` additionally
compares both choice variants and every OK/Close button state against the
accepted old client: frames, button pixels, and spacing are identical.

The latest full-profile v3 test build completed with no skipped patches:
`Outputs/modern-npc-dialog-v3-20260914/Ragnarok.exe`, SHA-256
`20F382C027F657EBE9EBCA4FA8A25C8AF00A83833C1302232A943561AD5FAE1B`.
This is an offline first-paint regression result, not live visual acceptance.

With Ragnarok closed, the v3 EXE and its matching EPI/secure metadata were
installed and hash-verified in `D:/AAARAGNAROK/Ragnarok Online`. The preceding
client set is preserved under `Outputs/modern-npc-dialog-v3-20260914/installed-before/`.
The current LastSession.yml and Settings.yml were restored byte-for-byte;
existing image files were not changed. Chat layout, current Century Gothic
12px Normal controls, and inline item-icon regressions passed. Relaunch the
client to inspect the NPC text middle area; the accepted choice pane remains
unchanged. Reload WARP before a future patch application to load v3.

`Outputs/DevSeara-ModernNpcDialog.diff` is a local WARP update diff based on
commit `ec77bbc016710fd261b6f946939a0558e42de7a8`, not a standalone binary patch
for arbitrary clients. It includes the new script, 25 PNGs, registration,
helper export, tests, and this document; existing AutoCombatUI/ModernChatUI
helper implementations remain required.

The patch was added to the local WARP folder. Publishing it to WARP-DAN is a
separate action; the previously published Battle Pass/Chat package is unchanged.
