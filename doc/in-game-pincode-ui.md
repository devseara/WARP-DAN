# In-Game Pincode UI

## Scope

This client-side patch lets the map server open a mouse-only PIN keypad while
the player is already in-game. It is paired with the BanquetOfHeroes
`pincode_open` script command and map-server packet handlers.

## Client Flow

1. Map server sends variable-length packet `0x0BEF` with magic `PINC`.
2. `Scripts/Patches/InGamePincodeUI.qjs` routes that packet to
   `bohcustoms.dll!PincodeUIShow`.
3. `CustomDLL/src/pincode_ui/pincode_ui.cpp` creates a child window inside the
   Ragnarok game window, using the native pincode art from
   `data/texture/.../basic_interface`.
4. The user enters PIN digits with the mouse.
5. The DLL encrypts the PIN with the same seed shuffle used by the client and
   sends normal pincode reply packets through WARP-allocated sender stubs:
   `0x08B8` check, `0x08BA` set new, or `0x08BE` change.

## Key Files

- `Scripts/Patches/InGamePincodeUI.qjs` installs the `0x0BEF/PINC` dispatcher
  route and native packet sender stubs.
- `CustomDLL/src/pincode_ui/pincode_ui.cpp` owns the Win32 keypad UI, pincode
  encryption, state transitions, and button rendering.
- `CustomDLL/src/build.bat` compiles `pincode_ui.cpp` into the combined
  `boh.dll`/`bohcustoms.dll`.
- `Patches/Special.yml` exposes the `InGamePincodeUI` patch.

## Assets

The keypad loads loose BMP files through the normal client data tree:

- Background: `2ndpassword_bg.bmp`
- Digits: `%d-a.bmp`, `%d-b.bmp`, `%d-c.bmp`
- Reset: `reset-a.bmp`, `reset-b.bmp`, `reset-c.bmp`
- Change: `btn_e_change_a.bmp`, `btn_e_change_b.bmp`, `btn_e_change_c.bmp`
- Cancel: `btn_cancel2_normal.bmp`, `btn_cancel2_over.bmp`,
  `btn_cancel2_press.bmp`
- Confirm: `btn_big_ok.bmp`

## Debugging

Debug output is intentionally off by default.

- DLL debug: set `PINCODE_UI_DEBUG` to `1` in `pincode_ui.cpp`.
- WARP route debug: set `debugPincodeRoute` to `true` in
  `InGamePincodeUI.qjs`, then reapply the WARP patch.

Keep both off for production, otherwise DebugView and server logs become noisy.
