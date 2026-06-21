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
   Ragnarok game window, using the native pincode art from the client's
   GRF-aware file system.
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

The keypad first loads BMPs through the client's native `CFile::Open` path,
using GRF-relative paths under:

`texture/<user interface>/basic_interface`

That means it follows the GRFs already mounted by the client. With
`GRFsFromIni`, the order comes from the live `DATA.INI`; with `GRFsEmbedded`,
the order comes from the embedded list baked into the patched EXE. The expected
Banquet order is:

```ini
[Data]
0=update.grf
1=maindata.grf
2=mapdata.grf
3=palettedata.grf
4=spritedata.grf
5=data.grf
6=greyworld.grf
```

If native loading fails, the DLL falls back to the older extracted-file search
under the client folder. The assets used are:

- Background: `2ndpassword_bg.bmp`
- Digits: `%d-a.bmp`, `%d-b.bmp`, `%d-c.bmp`
- Reset: `reset-a.bmp`, `reset-b.bmp`, `reset-c.bmp`
- Confirm: `btn_big_ok.bmp`, `btn_big_ok_a.bmp`, `btn_big_ok_b.bmp`
- Change: `btn_big_change.bmp`, `btn_big_change_a.bmp`,
  `btn_big_change_b.bmp`
- Cancel: `btn_big_cancel.bmp`, `btn_big_cancel_a.bmp`,
  `btn_big_cancel_b.bmp`

`btn_cancel2_*` exists in the GRF, but it is `56x20`; stretching it into the
pincode panel's `100x20` button slot makes it look unlike the original panel.
The original-size pincode buttons are the `btn_big_*` family.

## Native Findings

The first implementation tried to call the stock pincode UI directly from the
map-server session, but the native pincode paths are char-session oriented:

| Address | Purpose | Result |
|---------|---------|--------|
| `0x00D221E0` | Native `0x08B9` pincode handler | No UI from the live map session; crashes with invalid char-session context |
| `0x00D21210` | Direct pincode window opener reached by the `0x0828` branch | Returned without showing UI in-game |
| `0x00A31A30` | Native UI element creator | Returned without showing UI in-game |
| `0x00FC1628` | Early suspected char-session global | False positive; live value resolved to a system DLL address |

`0x0BD0` is registered by this client as an 8-byte fixed-length packet, so the
final trigger uses default-unhandled variable-length packet `0x0BEF` with magic
`PINC`.

The PIN encoding is the stock seed-based digit shuffle: build digits `0..9`,
iterate `i = 1..9`, update `seed = 0x881234 + seed * 0x3498`, swap `tab[i]`
with `tab[seed % (i + 1)]`, then send `tab[digit]` for each entered digit.

## Porting Notes

This implementation is tied to the 2025-07-16 Ragexe. Before reusing it for
another client date, re-check:

- `0x0BEF` packet-table availability
- map packet dispatcher layout
- packet sender helper pattern used by `InGamePincodeUI.qjs`
- native `CFile` addresses used by the DLL asset loader
- pincode BMP paths and button dimensions

## Debugging

Debug output is intentionally off by default.

- DLL debug: set `PINCODE_UI_DEBUG` to `1` in `pincode_ui.cpp`.
- WARP route debug: set `debugPincodeRoute` to `true` in
  `InGamePincodeUI.qjs`, then reapply the WARP patch.

Keep both off for production, otherwise DebugView and server logs become noisy.
