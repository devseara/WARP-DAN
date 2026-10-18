# Custom AutoSupport UI v1

AutoSupport asks for its language, then **RO Global AutoSupport UI** (the default
470x346 layout) or **Custom AutoSupport UI v1** (the 760x520 Command panel).
The custom panel matches Custom AutoHunt's Item Description palette, opaque
native text surface and readable font sizing. Its top-right close button loads
the stock `basic_interface/sys_close_off.bmp` and `sys_close_on.bmp` resources.

Overview groups the existing core and return settings, with all nine Basic
options under Advanced settings. Party selects the player AutoSupport follows;
it does not select autonomous monster targets. Combat, Recovery, Loot, Movement
and Buff items retain every existing ASUI setting and secondary page, including
the status recovery item. Real skill/item icons and live inventory quantities
use the existing native resources and ASUI snapshot. Configured skill and buff
slots compact visually; Show empty slots exposes all eight without renumbering
server slots. AutoSupport's support-first priority and master/session rejection
messages remain intact.

The settings window closes independently. The original floating icons still
start and stop AutoHunt, AutoSupport and AutoPotion. No server behavior, timer
policy, packet protocol, receive hook or runtime DLL is added.

`tools/native/autosupport_custom_v1.cpp` compiles into the import-free
`Inputs/AutoUI/support-custom-v1.bin` build-time image. Its ASV1 header uses
private ABI 1 and a 648-byte configuration. QJS validates the image and embeds
it in the client. Native source and metadata line endings are pinned to LF;
the QJS patch remains UTF-8 without BOM and CRLF.

```powershell
.\.venv-target-hud\Scripts\python.exe tools/build_autosupport_custom_v1.py --check
.\.venv-target-hud\Scripts\python.exe tools/build_auto_ui_language.py --check
node tools/verify_auto_ui_options.cjs
.\.venv-target-hud\Scripts\python.exe tools/build_autohunt_ui.py --output Outputs/AutoSupportCustomV1/example --support --support-design "Custom AutoSupport UI v1"
.\.venv-target-hud\Scripts\python.exe tools/verify_autosupport_custom_v1.py Outputs/AutoSupportCustomV1/example
```

For an already-patched 2025-07-16 client, use the isolated upgrade tool instead
of reapplying the complete patch profile. First build an English legacy template
with both original layouts. `tools/upgrade_autosupport_custom_v1.py` locates the
unique AutoSupport constructor, derives its existing state/vtable addresses,
and compares all eight legacy drawing/input helpers after relocation. It rejects
unknown or already-upgraded clients. A new `.asv1` section contains the renderer;
only five settings vtable slots and four constructor sizing immediates change
inside existing sections. All other existing section bytes, including sprite
and mounted-Mage fixes, must compare exactly. ASLR must already be disabled and
the PE must have section-header room.

`--feature autohunt` applies the same guarded upgrade to the existing AutoCombat
window, appending `.ahv1`. It validates exact caption/resource spans, writable
snapshot buffers, all eight legacy helpers and the scalar sender separately.
This handles full-profile allocations without assuming one shared address
offset. An existing `.asv1` section remains byte-for-byte unchanged. AutoCombat's
diagnostic layout context is metadata only and does not change either renderer.

```powershell
.\.venv-target-hud\Scripts\python.exe tools/build_autohunt_ui.py --output Outputs/AutoSupportCustomV1/legacy --support --design "RO Global AutoHunt UI"
.\.venv-target-hud\Scripts\python.exe tools/upgrade_autosupport_custom_v1.py "C:/path/client.exe" --template Outputs/AutoSupportCustomV1/legacy --output Outputs/AutoSupportCustomV1/upgrade
.\.venv-target-hud\Scripts\python.exe tools/verify_autosupport_custom_v1.py Outputs/AutoSupportCustomV1/upgrade --game "C:/path/game"
```

The verifier executes the actual emitted renderer and preserved ASUI handlers.
It covers all tabs, master selection, skill and status-item registration, delay
dialogs, thresholds, quantities, loot filters/actions, movement, all nine Basic
options, native scroll capture, rejection messages and close/session isolation.
Windows GDI reproduces the zero-alpha text issue separately. Rendered previews
use sample snapshots and are not live game acceptance.

Back up the requested EXE and the existing RiftLock manifest/signature before
installing. Close clients and GRF Editor, then generate and independently verify
a matching RiftLock release for that exact EXE and the installed assets. The
folder's active signature is tied to the EXE selected for signing.

Profile Main now saves `$autoCombatUIDesign: Custom AutoHunt UI v1` and
`$autoSupportUIDesign: Custom AutoSupport UI v1`. Loading the saved inputs
directly selects both custom designs. Other saved inputs and patch order are
preserved.

The 2026-10-18 upgrade evidence is in
`docs/evidence/autosupport-custom-v1-20261018.json`. The user confirmed the
AutoSupport build `5c1c8075c7cddea2dc7f2672f1387a03c54ee4418e890d96df33e25d127cafec`
was tested and working in-game. The subsequent combined EXE with both Custom v1
UIs retains that exact `.asv1` section; its automated UI checks are recorded
separately from live acceptance. The pre-existing full ASUI contract test's saved
main-profile ordering assertion remains outside this change; the original and
custom isolated coexistence builds are checked independently.
