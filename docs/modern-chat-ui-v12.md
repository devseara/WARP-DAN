# Modern chat UI v12 - white/bold selected tab

Target: profiled 2025-07-16 Ragexe. The selected docked tab now uses bright
white (`#FFFFFF`) and bold weight 700. Inactive tabs retain gray (`#C7C7C7`)
and the configured Normal/Bold weight. All labels use the configured family
and size. Native tab names, spacing, selection, filters and detach/dock are
unchanged, as are the input, controls and floating headers.

Selection comes directly from the native TabCtrl's current index at `+0x7C`
on every draw; it is not inferred from the label, tab order or mouse hover.
The existing selected border/background remains. No tab icons are restored.

## Font/rendering contract

- The label helper is `thiscall(text,left,cellWidth,selected)` / `ret 16`.
  The private font getter is `stdcall(selected)` / `ret 4`.
- A 20-byte private cache stores the configured HFONT at +0, GDI measurement
  and output functions at +4/+8, initialization flag at +12, and bold HFONT
  at +16. At most two fonts are created once per client process. If the base
  style is already Bold, both states reuse one handle.
- Measure the currently selected font, then center and clip its actual width
  inside the existing tab partition. Bold never uses the normal font's width.
- Every draw restores the previous HDC font, text color and background mode.
  No global font tables or shared TextOut/item/enchant renderer hooks change.
- If GDI setup fails, the existing native 12px fallback remains; the selected
  label still becomes white, though custom font weight is unavailable there.
- WARP's style prompt now explicitly describes the inactive tabs; the selected
  tab is always bold. Default size 8 and accepted Normal/default choices remain.

`ModernChatUI.v12` provides the versioned offline helper contract.

## Verification

The deployment build uses the user's current complete LastSession unchanged
(Arial/12/Normal). An additional Arial/8/Bold build exercises the shared-bold
handle path at the minimum configurable size.

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_controls.py Outputs/modern-chat-v12.exe --font Arial --size 12 --weight 400
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_controls.py Outputs/modern-chat-v12-bold-8.exe --font Arial --size 8 --weight 700
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py Outputs/modern-chat-v12.exe
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_chat_item_icons.py Outputs/modern-chat-v12.exe
```

The tests execute both label states, narrow/long labels, private font caching,
DC restoration, and actual native tab clicks followed by complete patched tab
draws. Only the clicked page becomes white/bold; changing selection clears
the previous highlight. Existing cursor/pressed animation, PM/send/emoji,
layout, detach/dock and inline-item-icon regressions are retained. OS/GDI and
network boundaries are explicit doubles; live screenshot acceptance is still
needed after reopening the client.

## Deployment and recovery

Both WARP builds completed with no skipped patches. All four binary test
commands passed, as did the actual font-input source regression through the
available V8 runner (Normal/defaults, Bold, cancellation and invalid values).

Installed the current Arial/12/Normal build and matching `.secure.txt` with
the client closed. `Ragnarok.epi` was already absent from the game folder;
the new optional patch metadata remains in `Outputs/modern-chat-v12.epi`.
Installed `Ragnarok.exe` SHA-256:

`0CB7FD721D1CB92249ECAEFA945CE5D56C9A393C8EDA8093C3A5C1D8BAB76195`

All 19 PNGs and saved chat Lua are unchanged. Original WARP session/settings
were restored byte-for-byte after testing; no user font input was changed.

The previous executable, existing secure sidecar and saved chat Lua are backed up under
`Outputs/chat-ui-backup-20260914-v12`. Previous executable SHA-256:

`241611E54F19C7F0181B8776F6122AE8D44FF082F344C32D2B67D00246247B62`

To roll back, close the game and restore the executable and secure sidecar.
Keep newer PNGs and saved chat data unless a separate rollback is intended.
