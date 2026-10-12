# BOH Visual DLL Builds

Two packaging modes are supported.

## Combined build

Run `build.bat` to produce `boh.dll`. If your client imports
`bohcustoms.dll`, copy or rename the output DLL to `bohcustoms.dll`.

`build.bat` links the `dll_integrity` module and seals the DLL after link. The
sealed DLL verifies its on-disk SHA-256 before any feature module is initialized.
The digest slot itself is zeroed for the canonical hash, so renaming
`boh.dll` to `bohcustoms.dll` does not invalidate the seal. Any byte edit to the
sealed DLL makes `DllMain` return `FALSE` and the client will fail the import
load instead of running modified feature code.

The self-check is intentionally Gepard-friendly: it opens and reads its own DLL,
uses an in-module SHA-256 implementation, and does not allocate executable
memory, rewrite code, patch imports, install hooks, scan processes, or contact
the network. Treat it as a local tamper tripwire. For real external enforcement,
send the generated `boh.dll.sha256` manifest and final renamed DLL hash to the
Gepard owner for whitelist/protection review.

For strict Gepard builds, keep the combined build limited to non-hook modules.
The checked-in `customer_features.h` may reflect a customer/runtime feature set;
do not treat it as proof of strict Gepard compliance. Item and enchant-grade
colors cannot be enabled in this DLL; they are implemented exclusively by the
QJS patches documented in `../../docs/item-grade-color-renderer-contract.md`.
The rune visual module is retired the same way (`BOH_RUNE_VISUAL` must stay 0):
`CustomRuneSystem` is QJS-only and `boh_rune.dll` is no longer built.
Do not enable extended names, FPS/ping, inventory tabs, or other
runtime-hook modules unless the anti-cheat owner has approved that specific
runtime memory behavior.

## Dedicated builds

Run `build_split.bat` to produce:

| DLL | Features | WARP export |
|-----|----------|-------------|
| `boh_text.dll` | Extended names and player-name colors | `ExtNameVisualInit`, `PlayerNameColorVisualInit` |
| `boh_npc_names.dll` | Always-show NPC names | `NpcNameOverlayInit`, `NpcNameOverlayFrame` |
| `boh_fps.dll` | FPS and ping overlays | `FpsPingOverlayInit` |
| `boh_inventory_tabs.dll` | Image inventory tabs | `InventoryTabsInit` |
| `boh_weapon_sprite.dll` | Dual-wield custom renderer host | `WeaponSpriteInit` |
| `boh_pincode_ui.dll` | In-game PIN keypad | `PincodeUIInit`, `PincodeUIShow` |

Each WARP patch has its own saved DLL-name prompt. The output files may be
renamed as long as the matching filename is entered when patching the client.

Only `boh_npc_names.dll` and `boh_pincode_ui.dll` are currently part of the
strict Gepard-safe runtime set. The NPC DLL depends on the WARP-time static
frame bridge and EXTN dispatcher ring installed by `AlwaysShowNpcName`; it does
not install a runtime trampoline. The other dedicated visual DLLs are isolated
for debugging and deployment control, but they still perform runtime
hooks/patches.

`item_color/colored_itemname.cpp` and the `BOH_ITEM_COLORS` feature bit are
deprecated historical artifacts. They implement the obsolete DLL continuation
and shadow renderer and are non-authoritative. Both build scripts reject
`BOH_ITEM_COLORS=1`; `gen_license.py` cannot enable it. Do not restore this
module or use `ColoredItemNameVisualInit` to implement item/grade colors.

Item and enchant-grade colors are exclusively QJS-time EXE patches. Their
normative precedence, exact-span, quantity-tail, and shadow-suppression rules
are in `../../docs/item-grade-color-renderer-contract.md`.

`boh_text.dll` now uses `text_visual/player_name_text_bridge.cpp` only for EXTN
substitution and player-name colors. Those remaining features still share the
same GDI wrapper surface. The `ColoredItemNameVisualInit` export remains a
no-op compatibility anchor for already-patched clients; it does not enable an
item renderer.

## Dual-wield weapon sprite DLL experiments (retired)

This DLL renderer host is not a production feature. Direct GRF inspection
proved that actor SPR/ACT arrays are parallel resource channels rather than
hand anchors. Item ACTs expose ordinary single-hand geometry; stock dual
actions use precomposed bitmaps containing both weapons.

The supported implementation is the static
`AllowDualCustomWeaponSprites.qjs` patch. It preserves the known-working fc9
resource sequence: retain the off-hand item pair, run the stock `mainOnly`
setup last so its original pair remains in slot 5, then transfer only the
retained off-hand pair into slot 6. A successful split never replays the stock
`current(main, off)` setup, because that path restores the generic combined
resources. A four-way actor/four-resource ownership registry and guarded
action/layer fallbacks prevent stale or foreign records from receiving custom
placement. A renderer actor can be adopted after an ownership miss only when
both live ACTs have the transparent action-88/frame-0 signature of the
individual 13412/1238 resources; the visible stock combined ACT is rejected.

Exact absolute independent-hand idle/attack geometry exists only for the male
Shadow Cross main 13412/off 1238 profile. Generic Knife/Sword assets and other
unprofiled pairs do not have solved independent-hand geometry. Do not ship
`BOH_WEAPON_SPRITE=1`, the layered overlay, or any native probe flag below as
part of the supported implementation. They remain historical reverse-
engineering instrumentation.

### Historical debug notes

For this setup, `bohcustoms.dll` is already used by the combined build for the
other BOH features. Keep the weapon renderer in a dedicated DLL with a unique
import name, for example `rename.dll`:

```bat
build_split.bat
copy /y boh_weapon_sprite.dll "...\rename.dll"
```

Then select `rename.dll` in WARP's **Dual-Wield Per-Hand Weapon Sprites**
prompt and place that DLL beside the patched EXE. The combined build has
`BOH_WEAPON_SPRITE=0` so `bohcustoms.dll` does not also start a second weapon
overlay/state-hook owner.

If you intentionally want one combined DLL to own the weapon renderer too, set
`BOH_WEAPON_SPRITE=1` in `customer_features.h`, rebuild `boh.dll`, and use the
same combined DLL name in the WARP prompt.

The native hook route is no longer the default.
`docs/dual-wield-original-weapon-sprites.md` is the canonical status and
handoff: the DLL route remains retired, the production QJS is fail-closed, and
the female Assassin pair-28 v4 owner build is only a scoped test checkpoint.
Earlier tracing found that this client's dagger weapon visuals can be baked into
body ACT layers, item-specific `_1238` / `_13412` layers may be absent for a
tested Assassin Cross body, and `DrawWeapon` is an arrow/projectile path for
this case. The DLL now starts as a custom-renderer host:

```bat
set BOH_DUALWPN_NO_HOOKS=1
set BOH_DUALWPN_OVERLAY=1
set BOH_DUALWPN_STATE_HOOKS=1
set BOH_DUALWPN_PLACEMENT_TRACE=1
```

`BOH_DUALWPN_NO_HOOKS=1` is the default and skips the old native
replacement/draw/resource experiments.
`BOH_DUALWPN_OVERLAY=1` starts the layered-window renderer. The overlay window
is owned by the game window, hides while the game is inactive or minimized, and
stays hidden until the read-only state hooks report an in-game dual/offhand
actor render. It decodes loose ACT+SPR pairs, pre-composes ACT actions 32..39
into ARGB weapon frames, and can still decode loose SPR frames as a raw fallback.
`BOH_DUALWPN_PLACEMENT_TRACE=1` also traces the native generic weapon holder so
DebugView can show the correctly placed generic layer's caller, part id, frame
arg, and position/scale fields. Until actor screen coordinates are fed in, the
overlay still draws the exact main/offhand weapon pair from the current actor
state with configurable anchor offsets.

`WeaponSpriteInit` is only an import-table anchor that makes the client load
the DLL. Normal PE import resolution does not call the function. The first
DebugView lines to expect are:

```text
[DualWeaponSprites] attach
[DualWeaponSprites] installer start ...
[DualWeaponSprites] installer done ...
```

Current environment toggles:

```bat
set BOH_DUALWPN_NO_HOOKS=1
set BOH_DUALWPN_OVERLAY=1
set BOH_DUALWPN_STATE_HOOKS=1
set BOH_DUALWPN_PLACEMENT_TRACE=1
set BOH_DUALWPN_LOG=0
set BOH_DUALWPN_REPLACE=0
set BOH_DUALWPN_OFFHAND=0
set BOH_DUALWPN_LOG_EVERY=120
set BOH_DUALWPN_FORCE_SINGLE_LAYER=0
set BOH_DUALWPN_FORCE_SINGLE_MODE=0
set BOH_DUALWPN_TRACE_ACTOR_PATHS=0
set BOH_DUALWPN_TRACE_RESOURCE_KEYS=0
set BOH_DUALWPN_TRACE_WEAPON_PATHS=0
set BOH_DUALWPN_PRELOAD_WEAPON_PATHS=0
set BOH_DUALWPN_ALIAS_RESOURCE_KEYS=0
set BOH_DUALWPN_SYNTH_WEAPON_PATHS=0
set BOH_DUALWPN_AUTO_SYNTH_VISUAL=0
set BOH_DUALWPN_SUPPRESS_NATIVE_SUBMIT=0
set BOH_DUALWPN_SYNTH_DRAW=0
set BOH_DUALWPN_FORCE_RESOURCE_BRANCH=0
set BOH_DUALWPN_FORCE_RESOURCE_KEY=0
set BOH_DUALWPN_HIDE_INACTIVE=1
set BOH_DUALWPN_STATE_TTL_MS=120000
set BOH_DUALWPN_SPR_SCALE=1
set BOH_DUALWPN_FRAME_MS=180
set BOH_DUALWPN_ANCHOR_X=0
set BOH_DUALWPN_ANCHOR_Y=30
set BOH_DUALWPN_HAND_GAP=24
set BOH_DUALWPN_ACT_START=32
set BOH_DUALWPN_ACT_END=39
set BOH_DUALWPN_MAIN_ACT=
set BOH_DUALWPN_OFF_ACT=
set BOH_DUALWPN_MAIN_SPR=
set BOH_DUALWPN_OFF_SPR=
set BOH_DUALWPN_ALLOW_FALLBACK_SPR=0
```

`BOH_DUALWPN_MAIN_ACT` and `BOH_DUALWPN_OFF_ACT` may point to absolute or
client-folder-relative loose `.act` files; the renderer loads the matching
`.spr` beside each ACT. If unset, it reads `DATA.INI` or embedded GRF names,
walks GRFs in priority order, finds matching `_13412` / `_1238` ACT+SPR pairs,
and decompresses them in memory before falling back to loose `data\sprite`
searches. `BOH_DUALWPN_ACT_START` and `BOH_DUALWPN_ACT_END` choose the ACT
action band to pre-compose; `32..39` is the first verified weapon-bearing range
from the offline preview.
`BOH_DUALWPN_STATE_TTL_MS` controls how long the overlay keeps the last valid
dual/offhand actor state alive; this defaults to `120000` so short render-state
bursts do not look like flicker. `BOH_DUALWPN_FRAME_MS` controls the proof
animation cadence.
Unrelated Drake fallback sprites are disabled by default; enable them only with
`BOH_DUALWPN_ALLOW_FALLBACK_SPR=1` when deliberately testing the overlay layer.
`BOH_DUALWPN_STATE_HOOKS=1` installs only the minimal read-only WeaponType and
RenderMode hooks required to feed actor item state into the overlay.
`BOH_DUALWPN_PLACEMENT_TRACE=1` adds the read-only `C55C30` native generic
weapon holder trace. The old native replacement/draw/resource experiments still
remain off by default. Set state hooks to `0` only when proving the overlay
thread starts without any EXE hooks; with state hooks off, heartbeats are
expected but weapon drawing cannot work.

Native probe flags are opt-in. `BOH_DUALWPN_REPLACE` swaps combined
dual-wield types `25..30` for an individual main/offhand view when available.
`BOH_DUALWPN_OFFHAND` is a stability probe that issues a second `DrawWeapon`
call after the native draw. Leave both experiment toggles off until the attach
and installer lines are visible.

The current live-render trace point is the actor-part layer helper, not
`DrawWeapon`. DebugView should show `LayerIdB` lines. In this client, mode 2
submits layer id `80` (`0x50`) and mode 9 submits layer id `88` (`0x58`).
`BOH_DUALWPN_FORCE_SINGLE_LAYER` and `BOH_DUALWPN_FORCE_SINGLE_MODE` are off by
default. The force-layer probe did not change the generic visual, and the
force-mode probe made the main/dual-hand sprite disappear while the offhand
remained. Keep both off unless intentionally reproducing those proofs.

`BOH_DUALWPN_TRACE_ACTOR_PATHS=1` logs filtered
`ActorPath` lines from the native actor resource path builder (`0x00D5B8E0`)
when the builder inputs match the current weapon actor's `+260/+4C8` fields.
These lines are meant to separate real weapon paths from the noisy accessory
and head paths seen in earlier global loader probes.

`BOH_DUALWPN_TRACE_RESOURCE_KEYS=1` logs the native
resource-cache results for the current generic key at `[char+0x24C]` and the
item-specific keys derived from the resolved weapon views, such as `45 ->
45000000`.

`BOH_DUALWPN_TRACE_WEAPON_PATHS=1` hooks the native weapon
path builders (`0x00D5A480` and `0x00D58FF0`) and logs lines such as
`WeaponPathMain` / `WeaponPathOff` when a builder output has an item suffix or
matches the current main/offhand view. `BOH_DUALWPN_PRELOAD_WEAPON_PATHS=1`
loads matching item-specific ACT paths immediately via `ConvPath` +
`LoadSurface`. `BOH_DUALWPN_ALIAS_RESOURCE_KEYS=1` lets the renderer resource
lookup return that preloaded object for the specific type key if the native
lookup returns null.

`weapon_7.log` showed the native weapon path builders do not fire in the live
mode 2/9 actor-part route: there were no `WeaponPathMain`, `WeaponPathOff`, or
`ResourceAlias` lines. `BOH_DUALWPN_SYNTH_WEAPON_PATHS=1` can be used
to synthesize an item ACT path from the actor body path, using the actor's root
and gender plus known Assassin-family fallbacks that exist in `spritedata.grf`.
`BOH_DUALWPN_AUTO_SYNTH_VISUAL=1` patches the skipped mode 2/9 resource branch,
but it only submits a specific key through `[char+0x24C]` after a synthesized
ACT path has loaded into a non-null object.

`weapon_8.log` proved the synthesized ACT objects and resource aliases work,
but the visible sprite still stayed generic. That means `[char+0x24C]` is too
late for this actor-part route. `weapon_9.log` proved the direct-draw fallback
is unsafe: `BOH_DUALWPN_SUPPRESS_NATIVE_SUBMIT=1` plus
`BOH_DUALWPN_SYNTH_DRAW=1` produced `Submit1C ... suppress=1` followed by
`SYNTH_DRAW main/off ...`, and the live client regressed to arrow artifacts,
missing character frames while attacking, and post-attack movement lock. Leave
both flags off unless intentionally reproducing that failure.

`BOH_DUALWPN_FORCE_RESOURCE_BRANCH=1` and `BOH_DUALWPN_FORCE_RESOURCE_KEY=1`
are off by default. Together they are the next visual probe: let mode 2/9 fall
through the resource branch the stock handler normally skips, and temporarily
submit a specific view key through `[char+0x24C]`. Do not enable them unless
the `ResourceKeys` trace shows the specific key already resolves, or a
`ResourceAlias key=... -> ...` / nonzero `SynthPath load=...` line proves this
build has supplied the missing object. The auto-synth path already performs the
same visual probe in a guarded way, so leave the manual force flags off unless
intentionally reproducing the old failure mode.

`weapon_5.log` showed that `ActorPath` is only building the body ACT path for
the current actor, while `+440/+444` hold the main/offhand item IDs and `+24C`
stays at `001E8480` across main-only, dual-wield, and offhand-only states.
`weapon_6.log` then showed the derived specific keys are still null in the
native renderer cache (`45 -> 45000000`, `34 -> 34000000`), so this build adds
the narrower weapon-path preload/cache probe before any forced visual branch is
enabled.

## Extended-name behavior

The server's `@showmobinfo` setting is carried in the mob fields of the
extended-name packet. It does not change unrelated atcommands. On the client,
mob substitution is limited to an exact nameplate match. For example, `Poring`
can become `Poring | HP: ...`, but `Poring Card` is left untouched.

Run the focused regression test from a Visual Studio x86 command prompt:

```bat
cl.exe /nologo /O2 /MT /EHa /I. ^
  extended_name\extended_name_test.cpp extended_name\extended_name.cpp ^
  /Fe:extended_name_test.exe /link kernel32.lib user32.lib
extended_name_test.exe
```
