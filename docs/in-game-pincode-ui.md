# Stock Pincode UI In-Game

## Scope

`InGamePincodeUI` opens the 2025-07-16 Ragexe's original character-select PIN
window over the active map scene. The player stays in-game. The implementation
is QJS-only and does not use the former Win32 replacement keypad or a custom PIN
DLL.

It is paired with BanquetOfHeroes' `pincode_open` script command and map-server
PIN packet handlers.

## Client Flow

1. Map server sends variable-length packet `0x0BEF` with magic `PINC`, seed,
   account id, and stock PIN state.
2. The map packet dispatcher invokes the QJS-injected handler on the normal
   client update thread.
3. The handler writes the stock PIN globals and reproduces the character-select
   resource/window creation path for window `0xC7` or `0xC8`.
4. Each patch builds a complete magic-gated `0x0BEF` router in memory it owns.
   If the peer patch is selected, its cached handler address is copied into the
   new router before the dispatcher entry is committed. The final registrar
   therefore owns both handler cells; unknown traffic returns to the original
   stock target without cross-patch writes, a recv hook, or a runtime DLL.
5. It also reproduces the scene's post-create events where required:
   - mode `3` dispatches type `6`, id `0x124` to C7, advancing the window into
     its old/new/confirm change phase; that phase submits `0x08BE` directly
   - mode `4` dispatches ids `0x124` and `0xB8` to C8 for first-time setup
6. The original `UISecondPasswordInputWnd` handles mouse input and sends its
   native replies through the currently active map connection:
   - `0x08B8`: check existing PIN
   - `0x08BA`: set new PIN
   - `0x08BE`: change PIN
   - `0x08C5`: request/reopen PIN window
7. BanquetOfHeroes validates the replies and persists set/change operations
   through char-server.

The QJS path handles stock states `0..8`. On the third wrong attempt it shows
the stock attempt-limit message but deliberately omits the character-select
transition, keeping the player on the map.

## AHUI/PINC Coexistence Verification

On 2026-07-31, WARP generated clients in both profile selection orders. Static
PE inspection of each output proved that dispatcher entry `0x00CAD0D0` points to
one self-contained router with all three nonzero/valid destinations:

- exact `AHUI` magic routes to `0x01AD17F0`;
- exact `PINC` magic routes to `0x01ACF530`;
- unknown traffic returns to stock continuation `0x00C9E1DD`.

The order matrix is a static wiring gate. Opening the stock PIN window and using
both Skill pages remain separate live acceptance tests.


## Why the 0x08B9 Handler Is Not Called Directly

The real stock `0x08B9` handler is at `0x00D221E0`; the older research address
`0x00D21210` is an `0x0828` handler on this build. `0x00D221E0` updates PIN
state, but normal window creation is deferred to the character-select scene's
mode dispatcher at `0x00D25333`. Calling the packet handler alone from a map
scene therefore does not display the keypad.

The patch reproduces the deferred stock resource and window-factory calls on
the map update thread instead. This avoids both the missing character-select
scene dispatch and the unsafe foreign-thread UI call used by earlier DLL
experiments.

## Stock UI Anchors

| Address | Purpose |
|---|---|
| `0x00D221E0` | Actual stock `0x08B9` PIN state handler |
| `0x00D25333` | Character-select PIN mode dispatcher |
| `0x008C91D0` | `UISecondPasswordInputWnd` event handler |
| `0x00A90350` | Resource-manager accessor |
| `0x00A9F030` | UI resource lookup |
| `0x00A8D4A0` | UI resource resolver |
| `0x00A4BBF0` | UI resource loader |
| `0x00A39340` | UI window factory |
| `0x00A2E770` | UI window close path |

The patch validates fixed signatures at these anchors before writing anything,
so an unsupported executable fails closed.

## Key Files

- `Scripts/Patches/InGamePincodeUI.qjs`: validates the client, installs the
  `0x0BEF/PINC` main-thread dispatcher, and creates the stock C7/C8 windows.
- `Patches/Special.yml`: exposes the `InGamePincodeUI` patch.
- `profiles/2025-07-16 PROFILE MAIN.yml`: enables the patch in the active full
  profile.

`CustomDLL/src/pincode_ui/pincode_ui.cpp` is retained only as historical source
for the former replacement UI. The active QJS patch does not import or call it.

## Porting Notes

This implementation is tied to the 2025-07-16 Ragexe. Before porting it to a
different client, re-identify the `0x08B9` handler, scene-mode dispatcher,
window IDs, resource helpers, UI manager, PIN globals, and map packet switch
table. Do not carry the fixed addresses forward without new static and runtime
evidence.
