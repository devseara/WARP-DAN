# Renewal chat: tab menu and first-use defaults

Target: profiled 2025-07-16 Ragexe. Select **Supplied Renewal Chat UI** in
`D:\warp\WARP20250716-main`. Reload WARP if it was already open, then rebuild
from the original unpatched client using your normal full profile.

Unlock chat, then right-click a docked chat tab for **Delete Tab** and
**Create New Tab**. While locked, right-click does not open the menu or change
the selected tab. Locking between press/release cancels the pending click;
locking an already-open menu blocks both actions. Normal left-click tab
selection still works while locked.
The clicked tab becomes selected before the action. These invoke the existing
native chat actions, including real page/filter records and native save logic.
The last docked tab cannot be deleted; the native maximum includes detached
tabs. Newly created tabs use the native `NewTab_<n>` name. Double-click the
name to rename it; use chat settings to change its message filters.

Hover labels: smiley **Emoticons**, airplane **Send Message**, gear
**Chat Settings**, closed lock **Chat Locked**, open lock **Chat Unlocked**.
The lock label follows the current lock state. Gear tooltips also apply to
detached chat windows. Existing button actions and message drafts are preserved.

Fresh/default layouts are ordered **Main, Battle, Guild, Party, Market**, with
Main first. Existing saved layouts are deliberately not replaced. Defaults are
not reapplied on each draw or login, so deleting or adding a tab remains useful.
Market is a normal/public-chat view, not a new server-side market channel.
Main/Battle keep the filter masks from the existing local preset; Guild and
Party select native guild/party messages. All remain editable in chat settings.

## Default resource and an existing installation

The installer copies this plaintext Lua 5.1 resource, only if missing:

```text
<output EXE directory>/data/LuaFiles514/Lua Files/ChatWndInfo/ModernChatDefaults.lub
```

Its source is `Assets/ModernChatUI/ModernChatDefaults.lub`. Edit the source
before distributing to fresh installations, or edit the destination to change
that installation's first-use defaults. Existing destination resources and
`savedata/ChatWndInfo_U.lua` are never overwritten by WARP.

The client must load the loose data folder (your normal Read Data Folder First
configuration), or this resource must be included at the same path in its GRF.
The `.lub` contains source Lua accepted by the native Lua resource loader.

To intentionally reset an existing layout to these defaults, close the game,
back up/rename `savedata/ChatWndInfo_U.lua`, and restart the newly patched
client. This resets custom tabs/filters, so do not do it while the client runs.
If account-synchronized settings restore a layout, those saved settings still
take precedence. No live saved layout was reset by this source change.

## Native implementation and verification

- Private chat TabCtrl vtable overrides right-down/up (`+0x80/+0x84`), retaining
  RTTI and all native left-click, rename, drag/detach and release callbacks.
- Instance-owned native popup window `0x1A`; list event `0x53` routes selections
  back to the popup, never the legacy chat recipient dropdown. Native list
  mouse-up sends event `0x27` with a null sender, then closes the popup itself.
- Native main event `0x16` selects the clicked page; command event `6` dispatches
  `0xCA` (delete) or `0x176` (create). Owner, index, pane identity and counts are
  rechecked before dispatch; callbacks are consumed once and retired on reuse.
- No right-button mouse capture. Out-of-bounds and mismatched releases cancel;
  layout retires an outside release after the right button is no longer held.
- The native `CanDragWnd` byte at `0x15FAAEC` is zero when locked. Right-down,
  right-up, menu opening and action dispatch all check it; layout clears a
  pending press while locked. An action callback is consumed even if blocked.
- Parent-painted controls publish hover text through native `0xA753D0`, using
  `0xA1EF70` to convert local coordinates; cursor action/pressed animation stays
  native. The gear initializer assigns `UIBitmapButton+0x94` with native string
  routine `0x4F1940`, preserving its stock vtable, hover and click handlers.
- Only the failed/fresh-layout fallback string operand at `0xD649F2` changes.
  The native saved-data loader and subsequent `_F` loader remain untouched.
- Existing `ModernChatUI.v13`, `.Input.v1` and `.Tabs.v1` contracts remain
  unchanged; `.Tooltips.v1` adds an offline test descriptor.

Current validation build: `Outputs/chat-lock-tooltips-20260922/final/Ragnarok-chat-test.exe`.
This seven-UI-only fixture is **not a deployable full-profile game client**.

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn --with lupa python tools/test_modern_chat_tabs.py Outputs/chat-lock-tooltips-20260922/final/Ragnarok-chat-test.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_tooltips.py Outputs/chat-lock-tooltips-20260922/final/Ragnarok-chat-test.exe
uv tool run --from nodejs-wheel node tools/test_modern_chat_asset_install.js
```

The tab suite executes emitted x86, native tab/list hit tests, list mouse-up,
popup forwarding and native main command dispatch. Window allocation/drawing,
refresh and the existing create/delete bodies are explicit test boundaries.
It checks five targets, invalid/mismatched releases, existing capture, stale
selection/owner/pane, last-tab/total-count limits, duplicate callbacks, failure,
popup destruction/reuse and actual Lua 5.1 default-resource evaluation.
Lock tests cover both actions, direct opening, press/release transitions,
lock-during-menu, duplicate callbacks and ordinary locked left selection.
Tooltip tests cover exact labels, edge coordinates at three window sizes,
lock-state changes, moved-window positioning, missing edits/cursor manager,
capture/hidden guards and unchanged drafts. The gear test executes native
string assignment (inline and heap-backed) and the original button hover;
CRT copying, image loading, cursor notification and tooltip painting are
explicit test boundaries. These checks do not replace in-game visual testing.

## Right-click correction (2026-09-22)

The first build incorrectly required `UITabCtrl+0x30 > 0` before handling a
right-click. The native base/TabCtrl constructors leave that field at zero;
native hit testing checks `+0x28 != 0` instead. The previous test fixture
artificially set `+0x30=1`, so direct callback tests missed the live failure.
The corrected handler follows the native `+0x28` check, without changing the
tab's state or taking mouse capture.

The regression now runs actual TabCtrl/base constructors and replays the
native mouse dispatcher (`0xA46940` onward), including actual child-window hit
testing and down/held/up transitions. The root-list lookup and OS cursor are
explicit boundaries. The native-state case reproduced the rejection in the
user's already-patched `Eitr.exe`; the corrected candidate passes it, native
mouse dispatch, and the existing tab/menu suites.

Historical visibility-only candidate (superseded by the popup crash fix below):
`Outputs/chat-tabs-rightclick-fix-20260922/combined/Ragnarok-chat-test.exe`.
Reload WARP and rebuild the normal full-profile client from its clean source
to install this correction. The installed `Eitr.exe` was not overwritten.

## Popup hit-test crash correction (2026-09-22)

The visibility correction exposed a second defect: the popup's private vtable
was copied only through `+0xB0`, while UIWindow has virtual methods through
`+0xD0`. The next UI-manager mouse pass calls the popup's `+0xC8` hit-test slot.
In the reported `Eitr.exe`, the table starts at `0x02202A50` (matching crash
EAX), and that slot contained `0x00000162`, exactly the reported exception IP.
The native caller is `0x00A336F4`, returning to `0x00A336FA` as in the report.

The copy now includes **all** slots through `+0xD0` and the RTTI locator at
`[-1]`, retaining native hit testing, ID, focus and child-traversal methods.
Only the intended destructor and selection-event entries are replaced.
Profile guards pin the extended native entries before patching.

The regression reproduces the exact crash against the installed executable
read-only (`--expect-popup-crash`). The corrected build checks every preserved
vtable slot and executes the real UI-manager root-list traversal, popup/child
hit testing, focus transitions, inside/outside/re-entry and menu selection.
The old root-lookup double did not cover this post-open popup traversal; the
new regression does. Root/child list data are fixtures; factory allocation,
close/destruction and native create/delete bodies remain explicit boundaries.

Historical popup-fix candidate SHA-256:
`7e22daeb428a439de7d8fcec969b53b922a20d97ec98c936f6d65a799d9ac8d5`.
This fixes the reproduced client-side invalid callback; it is not a server
change or a claim of live in-game acceptance. Rebuild from the original clean
client with your normal full profile; do not deploy the seven-UI-only fixture.

Current lock/tooltips candidate SHA-256:
`5e5f86c18b0a63a1c1def42f112b6551a3e623d1ed9f37c4ffa642bdc9de9921`.
It retains the complete popup-vtable correction and passes the same native
root-list hit-testing regression, plus the lock and tooltip checks above.

The asset suite executes the QJS installer with filesystem doubles, including
missing defaults when PNGs already exist, no-overwrite behavior and failures.
Existing chat layout, controls, input, redraw and item-icon suites also cover
the candidate. No installed executable, server or WARP settings were changed.

Still required in game: menu appearance and mouse/keyboard dismissal; delete
an original tab and create/rename a replacement; check its filters; relog to
confirm persistence; resize and detach/redock; verify the five-tab first-use
layout with a backed-up saved layout. Offline tests are not live acceptance.
Also verify no menu opens while locked, it opens after unlocking, all five
hover labels appear and disappear normally, and the lock label changes state.

## Channels, PM history, emoticons and shared UI Theme (2026-09-22)

The New chat input row now has a small slate/white circle immediately left of
the smiley. Its native localized dropdown offers All, Party, Guild, Allies and
Clan, with all five rows visible. It uses stock command `0xEE` and selection
event `0x27`; it does not synthesize chat packets or change PM priority. The
message edit stops before the three separate 24px channel/emoticon/send cells.

The left message icon opens the original PM-recipient dropdown (`0xE1`), above
the input. Native recipient history order, scrolling, selection and the empty
clear-recipient row are retained. An empty history simply focuses the recipient
edit. Picking a recipient changes the destination only; it never sends a draft.
The channel/history/tab menus share native popup ID `0x1A` safely.

The smiley toggles native Emoji List window `0x57`, including an already-open
Alt+L window. A successful native selection/insertion closes it through the
normal deferred window-destruction queue. Invalid/failed selections and the
shop preview flow are unchanged. Normal/recent/favorite grids retain their
original emotion providers and activation gestures.

When **RO Global Zero UI Theme Toggle** is selected with **Supplied Renewal Chat
UI**, chat follows Game Settings > UI Theme immediately. The patch-tree order
places the shared theme provider before chat. Without the theme patch, the
chat patch remains New-only for compatibility. The user's current full saved
profile already selects both patches; no settings/profile changes are needed.

Classic/New dispatch gates cover main/floating paint, edit/pane paint, input,
tab menus, native layout callbacks, clear-key values and docking capacity.
The original main window is resized in place, preserving its bottom anchor,
selected tab, page identities, filters, history and drafts. Native edit geometry,
top tabs, controls and resource names are restored in Classic. New edit colors
are temporary paint overrides when themes are available, so native channel
colors and Classic styling are not overwritten permanently. Floating windows
refresh through their normal overlay callbacks; the bounded observation cache
never dereferences stored stale window pointers.

The shared theme state appends an optional chat-refresh subscriber at `+40`,
without changing prior consumer offsets. Chat publishes this callback at runtime
from its own data block when entering a theme gate. Cross-patch build-time writes
were not durable with the complete saved profile, so registration must not depend
on a cached physical offset or another patch's cached allocation contents. These
are data writes only; no runtime executable-code writes are used.
Native image initializer arguments are copied into bounded patch-owned buffers,
not retained as pointers to temporary native strings.

Verified isolated combined candidate:
`Outputs/chat-channel-theme-20260922/integrated/Ragnarok-chat-test.exe`.
SHA-256: `196a0d20bee0d9ddf299af34c74f34b4cecf40c165bb1017f596c4893faead29`.
This seven-UI-plus-theme fixture is not a replacement for the full game client.

The current user `LastSession.yml` also builds successfully in an isolated
fixture, with its output redirected away from the installed `Eitr.exe`:
`Outputs/chat-channel-theme-20260922/full-integrated/Ragnarok-chat-test.exe`.
SHA-256: `74a2777ad8ca5adb2d75663990ee217cff6a2cbb87bdc5122bacd59905b5d54e`.

Offline checks execute emitted x86 plus native PM/channel construction and
selection, all three emotion providers, the real chat resize/layout routines,
Classic fallbacks, New/Classic resource restoration, saved-theme reads/writes
and repeated native theme toggles. Existing tab crash/lock, tooltip, input,
redraw, item-icon and Gacha capture tests also pass. OS, graphics/resource,
allocation and window-manager boundaries are explicitly mocked in the tests.

Reload WARP and rebuild from the clean source with the normal full profile.
The installed EXE, user WARP settings and saved chat layouts were not changed.
Still required in game: check the circle's placement/colors, all five destinations,
long PM-history scrolling, smiley open/close and selection, theme switching while
typing and with a detached tab, then relog in each saved theme. Offline results
are not a claim of live visual acceptance.

## Tab-name persistence fix (2026-10-09)

The native TabCtrl emits event `0x74` when an in-game rename is committed.
Chat panes also use `0x74` to request a backing clear. The modern event handler
previously consumed both, leaving the visible tab label renamed but its saved
filter-map record unchanged. Logout then wrote the old name to
`savedata/ChatWndInfo_U.lua`.

The handler now distinguishes the main window's TabCtrl sender (`this+0x138`)
from pane clears and forwards a rename to the native parent dispatcher. A small
wrapper around the final Classic/New dispatcher then invokes the native save
routine (`0x8F9D00`) after a nonempty, indexed rename, updating the existing Lua
file immediately. Native loading, tab order, filters, detached records and
normal logout saving remain in use. Cancelled/empty edits, selection changes
and redraws do not write the file. No additional save file is introduced.

The patch verifies the rename producer, native saved-name branch, serializer
and TabCtrl event vtable. It retains the selected dispatcher address explicitly:
WARP's `Exe.GetUint32` reads the original image rather than pending vtable edits.

Rebuild from the clean source with **Supplied Renewal Chat UI** selected after
restarting WARP. Rename a tab again in the new client; previously discarded
names cannot be recovered from the old saved file. No server rebuild is needed.
WARP installation does not overwrite the player's saved Lua file.

`tools/test_modern_chat_rename.py` executes the native edit producer, saved-map
update and Lua writer, then loads the resulting text in a fresh Lua 5.1 VM. It
checks all five tab records, short/long/UTF-8 names, repeated edits, immediate
saves, identical subsequent logout saves, cancellation and filter preservation
in Classic and New themes. File I/O and graphics are explicit test boundaries;
live relog/restart acceptance remains separate. Build and regression evidence
is staged under `Outputs/chat-rename-20261009/`.

## Channel / PM dropdown click-cycle fix (2026-09-22)

The earlier channel/history acceptance above missed a native manager boundary:
the parent-painted button opened popup `0x1A` on mouse-down, then the same
dispatcher cycle's outside-click pass (`0xA46F4C` / close at `0xA46F77`)
immediately dismissed it. The installed `74a2777a...` candidate reproduces this:
one popup is created and closed before mouse-up, although its tooltip works.

Both dropdown buttons now use native internal capture (`0xA4B750`) on press
and open only on release over the same control. A dedicated move wrapper keeps
this button capture out of native window dragging; release clears only our own
capture with `0xA482E0`. A release outside, capture loss, mismatched control or
theme change cancels the action. A new down clears stale press state before
either the New or Classic handler. Unarmed move/release still tail-call the
original main chat handlers. Chat lock does not disable destination selection.
No global input dispatcher, popup dismissal, packet or PM-history storage code
is modified. An empty native PM history still focuses the recipient edit.

The channel and smiley now have a matching 1px slate divider at `width-51`,
aligned with the neighboring toolbar dividers. It is painted directly, without
another texture or changes to user-owned PNGs.

`test_modern_chat_interactions.py` now executes the actual native mouse poll
from `0xA46940` through its capture/down/move/up/outside-dismissal paths. Only
root discovery and hover paint are input-loop boundaries; the dismissal pass
that caused the failure is not mocked. The regression fails the old build and
passes the fixed one. It also checks held clicks, release-outside/edge cases,
different controls, no accidental drag, foreign capture, both lock states,
theme switching mid-press, native channel selection and PM recipient assignment.
`test_modern_chat_ui.py` verifies the added separator pixel and native dragging.

The full-profile build is staged under
`Outputs/chat-dropdown-fix-20260922/final/Ragnarok-chat-test.exe`.
SHA-256: `3ab56e60abc4e1abd66a1e527ba5d7e265589aa9855c5b18af52d1308567f748`.
Full-profile interaction, theme, tab, tooltip and Gacha-capture suites pass;
the standalone build also passes layout/pixels, controls, input and redraw.
Reload WARP and rebuild from the clean source with the normal full profile.
The installed EXE, WARP settings, saved chat layouts and image assets were not
overwritten. Final in-game appearance and mouse interaction still need testing.
