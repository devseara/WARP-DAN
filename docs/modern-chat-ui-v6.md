# Modern chat UI v6 — supplied PNGs and fixed bottom tabs

Target: 2025-07-16 Ragexe, full `profiles/ragnarok_full_install.yml` profile.
Installed executable: `D:\AAARAGNAROK\Ragnarok Online\Ragnarok.exe`.
SHA-256: `77C23467C7D41D592C26A65D70BDA5EB237062F3A10A1447A80FBC7A4C2F45F9`.

## Reported v5 defects and corrections

- Native `UITabCtrl` captured mouse movement at `0x85A620` sends parent event
  `0x75`, which detaches the selected page at `0x8FC354`. The chat-only vtable
  slot `+0x6C` now returns with the original eight-byte argument cleanup. The
  parent also rejects `0x75`. This applies in both lock states. Native selection
  `+0x64` / `0x858B90`, hover `+0x70`, and other windows' shared vtable remain
  unchanged. Event `0x74` remains suppressed to prevent obsolete magenta paint.
- Native `ImageDraw` / `0xA1D260` delegates to `0x53F140`, which copies pixels
  without source-over compositing. The v5 GDI finalizer then made transparent
  PNG pixels with nonzero RGB opaque. Chat images now use a local, clipped,
  straight-alpha compositor. Zero-alpha pixels preserve the destination;
  partial-alpha pixels blend correctly, including over translucent input.
  PNG files and cached source pixels are not modified.
- Input textures start at x=3 and extend to width-3. Their three-pixel end caps
  are preserved during horizontal resizing. The inactive image remains the
  supplied semitransparent dark blue; the active image remains the supplied
  opaque light/white PNG, as explicitly requested by the user.
- Chat edit controls retain native text/caret handling but no stock fill or
  border. Foreground contrast samples the center of `textbox_on.png`: dark text
  on the supplied light image, light text if the user later darkens that file.
  Restart the client after editing a PNG so its texture cache reloads it.
- `CanDragWnd=1` now shows `icon_lock_off.png`; zero shows `icon_lock_on.png`.
  The lock still controls native window dragging, but never tab detachment.
- Asset installation copies only missing PNGs. Existing client-folder images
  are user-owned and are no longer overwritten by subsequent WARP builds.

## Saved chat pages

Restored five docked (`TabState="On"`) records, physically and numerically
ordered Main, Market, Battle, Party, Guild. Main was missing from the latest
saved file and was restored with its prior normal/system options (1, 4–14).
Market, Battle, Party and Guild retain their latest filter options; Party's
enabled option1 is preserved. Detached positions are reset to zero.

Battle's existing 25 filter options are all disabled. The UI correction does
not redefine server routing or silently enable filters; use the gear to select
the messages wanted on that page.

## Verification

Full-profile validation build and installed build both completed without patch
errors. `SkippedPatches.log` is empty. The installed build passes:

```powershell
uv run --with pillow --with pefile --with capstone --with unicorn python tools/test_modern_chat_ui.py 'D:\AAARAGNAROK\Ragnarok Online\Ragnarok.exe'
```

The tests execute emitted x86, checking stack/nonvolatile-register preservation,
five page identities, selected-page positioning, three resized layouts, input
state selection, transparent GDI edits, native event forwarding, both lock
states, blocked detach, and scoped vtable changes. Every pixel of all 19 actual
PNGs is compared against an independent source-over implementation over clear,
opaque and translucent backgrounds. The dark-image contrast test changes only
emulator memory, never the user's image. Client PNG hashes remain identical to
the supplied originals after deployment.

No in-game visual acceptance is claimed. Reopen/login and verify incoming chat,
five tab switches, attempted tab dragging, active typing, gear/lock, and resize.
These automated tests do not reproduce the complete live client compositor or
its input/window manager.

## Rollback

Verified backup of the pre-v6 executable, `.epi`, `.secure.txt`, source QJS and
saved chat Lua:

`D:\warp\WARP20250716-main\Outputs\chat-ui-backup-20260914-v6`

With the client closed, copy the three executable-side files into the client
root, `ChatWndInfo_U.lua` into `savedata`, and `ModernChatUI.qjs` into WARP's
`Scripts/Patches`. This rollback restores the reported v5 behavior and the
four-record/detached configuration; it is recovery, not a visually accepted UI.
