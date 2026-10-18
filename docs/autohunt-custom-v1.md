# Custom AutoHunt UI v1

The AutoCombat UI patch asks for the language first, then one of these saved
design choices:

- **RO Global AutoHunt UI**: the existing 470×346 native layout and default for
  profiles without a saved design.
- **Custom AutoHunt UI v1**: the 760×520 Command panel, using the neutral Item
  Description palette, a left sidebar, named skill/item rows, native icons, and
  server-supplied inventory quantities. Intended viewport: at least 800×600.

The menu button and `/autohunt` open or close settings. The top-right close
button and footer Close hide only settings. Starting and stopping remain on
the existing draggable, animated AutoCombat/AutoPotion floating icons.

The Command layout now applies to all seven tabs. Overview groups core behavior
and return rules, with the complete original Basic list under Advanced settings.
Combat and Buff items show configured slots plus an empty registration row;
Show empty slots exposes all eight without changing slot IDs. Recovery and
Movement use named icon rows with live quantities, and Loot groups collection
categories alongside weight/return rules, with equipment filters and priority
on its secondary page. These are existing server settings, without mockup-only
profile presets or additional stop rules.

All categories and their existing pages remain available, including the
eight attack slots, eight support slots, healing/status skills, HP/SP potion
slots, loot filters and priorities, teleport/return methods, eight buff-item
slots, Basic/Monster scrolling, and Reset. Clicking a slot or dragging a native
skill/item to it uses the original registration handler. Delay fields open the
existing server-owned input dialog; slider values, validation, rejection, and
persistence use the original handlers too. Changes save as the server accepts
them; there is no additional Save action or client-only profile database.

The configured rental/account-timer/AP/unlimited policy is unchanged. The
header displays the existing server session status. This UI revision does not
introduce voucher item IDs, time purchases, or automatic item consumption.

## Data and native contracts

This targets the original **2025-07-16 Ragexe** ABI guarded by
`AutoCombatUIStatic.verifyNativeContracts`. It changes only the settings frame's
draw/down/move/up/wheel vtable callbacks. The floating controller, packet router,
receiver, scalar sender, and destructor remain the existing implementations.
The wheel wrapper delegates to the original handler on scrollable pages;
native window capture supports dragging the Basic/Monster scrollbar thumbs.
Settings input maps are rebuilt from the current tab/page and
scroll state for each event; they never depend on a previous draw.

The existing AHUI snapshot already carries quantities: buff flags bits 16–31,
potion `reserved` at row +14, and item movement `entryLevel` at row +4. These
are server inventory totals saturated at 65,535, not estimated client counts.
The existing server omits unavailable/zero-count items; those slots consequently
show as unregistered/empty. Quantities refresh on the existing snapshot cadence.

Skill resources use the supplied native icon keys. Item artwork resolves the
numeric ItemId through the profiled native item catalog (+0x58 identified
resource, including SSO/heap strings), then loads the normal `item/*.bmp`.
No runtime Lua parsing, custom icon pack, shared text-renderer change, or server
protocol extension is needed.

`tools/native/autohunt_custom_v1.cpp` is compiled into an import-free x86
build container and serialized as `Inputs/AutoUI/custom-v1.bin` plus metadata.
WARP validates the header, CRC, relocations, exports, and configuration size,
then embeds the image in the output EXE. The build container is never deployed.
There is no runtime DLL, receive hook, runtime code patching, or gameplay logic
in this module. Language pointers use the existing late code-page initializer
and native font selector. Truncation respects UTF-8 and the supported DBCS
character boundaries. Private payload ABI 2 has a 620-byte configuration.

The window uses an opaque surface like Item Description. Native GDI text clears
glyph alpha, so enabling per-pixel composition made text fade or disappear.
English now uses the stock automatic font selector and its locale size adjustment;
explicit translated faces receive the equivalent height adjustment. Native RO
Global gauge/thumbnail/arrow/scrollbar/checkbox bitmaps are loaded at their real
dimensions, including the original background rail crops.

## Build and verification

```powershell
.\.venv-target-hud\Scripts\python.exe tools/build_autohunt_custom_v1.py
.\.venv-target-hud\Scripts\python.exe tools/build_autohunt_custom_v1.py --check
node tools/verify_auto_ui_options.cjs
.\.venv-target-hud\Scripts\python.exe tools/build_autohunt_ui.py --output Outputs/AutoHuntCustomV1/my-build --design "Custom AutoHunt UI v1"
.\.venv-target-hud\Scripts\python.exe tools/verify_autohunt_custom_v1.py Outputs/AutoHuntCustomV1/my-build
```

Use a new build output directory. `--profile` builds a copy of an existing
profile, `--language` selects a supported language, and `--support` includes
AutoSupport in an isolated coexistence build. These commands do not edit the
saved main profile or deploy over the game installation. An optional `--game`
path on the verifier loads the installed native BMPs for emulated previews.

On a RiftLock-enforced server, sign the final EXE **after** putting it in the
complete game folder and finishing all asset changes. Each rebuilt EXE needs
a matching `riftlock-assets-v1.txt` / `riftlock-release.sig` pair; copying the
EXE alone leaves the previous release signature stale. Close the game and GRF
Editor, then use **Tools → Sign Riftlock Client** in GRF Editor or the server's
`tools/riftlock_release.py --game-root "<game folder>" --client-exe autohunt.exe`.

The verifier executes the emitted custom renderer and the real generated AHUI
handlers in Unicorn. Only native engine/packet boundaries are mocked. It checks
ABI preservation, real item resolver paths, displayed quantities, tab/page
input mapping, registration/drag payloads, delay dialogs, slider endpoints and
capture, sparse slot identity, Overview context restoration, all pickup modes,
loot dropdown ownership, scrolling, Reset, and close/session isolation. It also
executes the stock font selector and reproduces the zero-alpha glyph behavior
with actual Windows GDI on an offscreen 32-bit DIB.
The PNG previews are emulated rendering with sample snapshots, not live game
screenshots.

On 2026-10-18 (Asia/Manila), the user confirmed the deployed English full-profile
build was tested and working across all tabs, including fonts, native controls,
and item quantities. Accepted EXE SHA-256:
`14a83697748eb70d9fb3ef16bbdc4be278438b536ec70272c4bf6b6a1e1bbcea`.
This user-reported acceptance is recorded separately from the automated checks
in `docs/evidence/autohunt-custom-v1-20261018.json`; it does not accept other
builds or languages.

For future builds, live validation should cover drag/reopen/close, both floating icons,
registration and delays on every skill page, potion and healing sliders,
changing quantities after item use, all loot controls, Basic/Monster scrolling,
teleport/return registration, Reset, relog/map changes, and the selected language.
