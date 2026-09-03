# AutoSupport UI assets

Target client: 2025-07-16.

All feature-owned runtime art is deployed under:

    data/texture/�����������̽�/autosupport/

The source tree mirrors that target beneath `Assets/AutoSupportUI/autosupport`.
The settings pages begin from the supplied RO Global AutoHunt assets so their
native dimensions and control alignment remain unchanged. The Player page owns
`setting_player/bg_player_autosupport.bmp` and never loads the AutoHunt
namespace.

## Menu icons

The AutoSupport menu child loads six dedicated heart/healing-cross pixel-art
states from `autosupport/menuicon`:

- New UI: 45x41 normal, mouse-on, and pressed BMPs.
- Classic UI: 32x34 old-normal, old-mouse-on, and old-pressed BMPs.

The icons were generated with the built-in image tool from the stock AutoHunt
state frames, then reduced with nearest-neighbor sampling and normalized to the
client's magenta color key.

## Deployment

`AutoSupportUI.qjs` exposes the saved `$copyAutoSupportAssets` option. Its
`onApplied` callback creates the target directories and copies the explicit
107-file manifest with `System.Copy`.

Validate with:

    python tools/verify_autosupport_ui_contract.py
    .\win32\WARP_console.exe -using profiles/autosupport_ui_test.yml
    .\win32\WARP_console.exe -using profiles/autosupport_ui_asset_copy_test.yml
