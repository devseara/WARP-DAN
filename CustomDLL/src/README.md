# BOH Visual DLL Builds

Two packaging modes are supported.

## Combined build

Run `build.bat` to produce `boh.dll`. Select the default `boh.dll` value in
every WARP feature prompt.

## Dedicated builds

Run `build_split.bat` to produce:

| DLL | Features | WARP export |
|-----|----------|-------------|
| `boh_text.dll` | Item colors and extended names | `ColoredItemNameVisualInit`, `ExtNameVisualInit` |
| `boh_npc_names.dll` | Always-show NPC names | `NpcNameOverlayInit` |
| `boh_rune.dll` | Rune visuals | `RuneVisualInit` |
| `boh_fps.dll` | FPS and ping overlays | `FpsPingOverlayInit` |
| `boh_inventory_tabs.dll` | Image inventory tabs | `InventoryTabsInit` |
| `boh_weapon_sprite.dll` | Dual-wield weapon sprite hook | `WeaponSpriteInit` |

Each WARP patch has its own saved DLL-name prompt. The output files may be
renamed as long as the matching filename is entered when patching the client.

Item colors and extended names intentionally remain together in
`boh_text.dll`. Both features intercept the same GDI text APIs, so loading two
independent hook owners would reintroduce ordering and double-hook problems.
Their packet consumers are separate: ICOL is handled by `item_color/`, while
EXTN transport and substitution state live in `extended_name/`.

## Dual-wield weapon sprite debug

Use the dedicated build for this hook:

```bat
build_split.bat
```

Then select `boh_weapon_sprite.dll` in WARP's **Dual-Wield Per-Hand Weapon
Sprites** prompt and place that DLL beside the patched EXE. The combined
`boh.dll` build does not currently export or initialize this hook.

`WeaponSpriteInit` is only an import-table anchor that makes the client load
the DLL. Normal PE import resolution does not call the function. The first
DebugView lines to expect are:

```text
[DualWeaponSprites] boh_weapon_sprite.dll attach
[DualWeaponSprites] installer start ...
[DualWeaponSprites] installer done ...
```

Current environment toggles:

```bat
set BOH_DUALWPN_LOG=1
set BOH_DUALWPN_REPLACE=1
set BOH_DUALWPN_OFFHAND=1
set BOH_DUALWPN_LOG_EVERY=120
set BOH_DUALWPN_FORCE_SINGLE_LAYER=0
set BOH_DUALWPN_FORCE_SINGLE_MODE=0
set BOH_DUALWPN_TRACE_ACTOR_PATHS=1
set BOH_DUALWPN_TRACE_RESOURCE_KEYS=1
set BOH_DUALWPN_TRACE_WEAPON_PATHS=1
set BOH_DUALWPN_PRELOAD_WEAPON_PATHS=1
set BOH_DUALWPN_ALIAS_RESOURCE_KEYS=1
set BOH_DUALWPN_SYNTH_WEAPON_PATHS=1
set BOH_DUALWPN_AUTO_SYNTH_VISUAL=0
set BOH_DUALWPN_SUPPRESS_NATIVE_SUBMIT=0
set BOH_DUALWPN_SYNTH_DRAW=0
set BOH_DUALWPN_FORCE_RESOURCE_BRANCH=0
set BOH_DUALWPN_FORCE_RESOURCE_KEY=0
```

`BOH_DUALWPN_LOG` is on by default. `BOH_DUALWPN_REPLACE` swaps combined
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

`BOH_DUALWPN_TRACE_ACTOR_PATHS=1` is on by default. It logs filtered
`ActorPath` lines from the native actor resource path builder (`0x00D5B8E0`)
when the builder inputs match the current weapon actor's `+260/+4C8` fields.
These lines are meant to separate real weapon paths from the noisy accessory
and head paths seen in earlier global loader probes.

`BOH_DUALWPN_TRACE_RESOURCE_KEYS=1` is on by default. It logs the native
resource-cache results for the current generic key at `[char+0x24C]` and the
item-specific keys derived from the resolved weapon views, such as `45 ->
45000000`.

`BOH_DUALWPN_TRACE_WEAPON_PATHS=1` is on by default. It hooks the native weapon
path builders (`0x00D5A480` and `0x00D58FF0`) and logs lines such as
`WeaponPathMain` / `WeaponPathOff` when a builder output has an item suffix or
matches the current main/offhand view. `BOH_DUALWPN_PRELOAD_WEAPON_PATHS=1`
loads matching item-specific ACT paths immediately via `ConvPath` +
`LoadSurface`. `BOH_DUALWPN_ALIAS_RESOURCE_KEYS=1` lets the renderer resource
lookup return that preloaded object for the specific type key if the native
lookup returns null.

`weapon_7.log` showed the native weapon path builders do not fire in the live
mode 2/9 actor-part route: there were no `WeaponPathMain`, `WeaponPathOff`, or
`ResourceAlias` lines. `BOH_DUALWPN_SYNTH_WEAPON_PATHS=1` is now on by default
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
