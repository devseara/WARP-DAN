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

`WeaponSpriteInit` only exists to make WARP load the DLL. Runtime setup happens
from `DllMain`, and logs use the `[DualWeaponSprites]` DebugView prefix.

Useful environment toggles:

```bat
set BOH_DUALWEAPON_REPLACE=1
set BOH_DUALWEAPON_SOURCE=auto
set BOH_DUALWEAPON_RENDER_OVERRIDE=1
set BOH_DUALWEAPON_EXTRA_RENDER=0
set BOH_DUALWEAPON_SUPPRESS_NATIVE=0
set BOH_DUALWEAPON_FORCE_SPECIFIC_TYPEKEY=1
set BOH_DUALWEAPON_FORCE_OFFHAND_VISUAL_SLOT=1
set BOH_DUALWEAPON_PATH_TRACE=1
set BOH_DUALWEAPON_RESOURCE_TRACE=1
set BOH_DUALWEAPON_RESOURCE_TRACE_ALL=0
set BOH_DUALWEAPON_RESOURCE_REDIRECT=1
set BOH_DUALWEAPON_RESOURCE_KEY_ALIAS=1
set BOH_DUALWEAPON_NATIVE_EQUIP_REFRESH=0
set BOH_DUALWEAPON_ACTIVE_RESOURCE_SWAP=1
set BOH_DUALWEAPON_DRAW_KEY=typekey
set BOH_DUALWEAPON_CUSTOM_ALIASES=0
set BOH_DUALWEAPON_PROBE=1
set BOH_DUALWEAPON_LOG_EVERY=120
set BOH_DUALWEAPON_ACTION_OFFSET=0x40
set BOH_DUALWEAPON_SKIP_ACTIONS=4,5
```

Keep `BOH_DUALWEAPON_REPLACE=1` while testing normal/default weapon IDs. The
weapon-type hook now feeds the real body/equipment pipeline with a specific
weapon view ID when one is available, such as `45` for Twin Edge B / suffix
`_13412`, instead of preserving the patched client's generic `1`/`2` result.
`auto` prefers a specific main-hand type, then a specific offhand type, then
generic fallbacks.

`BOH_DUALWEAPON_SOURCE` accepts `auto`, `main`, or `off` when replacement is
enabled. `auto` starts with the main-hand lookup type so default client weapon
IDs can be validated without custom Lua aliases hijacking values like `1102`.
DebugView decision logs include `source=...` so the chosen path is visible
during testing.

Leave `BOH_DUALWEAPON_CUSTOM_ALIASES=0` while testing normal/default weapon
IDs. Set it to `1` only when intentionally testing high custom weapon type
aliases from `weapontable.lub`; the weapon-type hook's caller stores the
returned type in `AL`, so custom aliases still must fit in one byte.

`BOH_DUALWEAPON_RENDER_OVERRIDE` enables render-layer intervention for dual
wielding. `BOH_DUALWEAPON_EXTRA_RENDER=0` and
`BOH_DUALWEAPON_SUPPRESS_NATIVE=0` are the safe defaults. Keep the manual
extra-render path opt-in only: the `weapon_16` run showed that submitting
separate `0xC6D9D0` draw calls can surface arrow/effect visuals during attack
stance instead of weapon sprites. When explicitly enabled, DebugView shows
`reason=suppress-native-dual`, followed by `main-render` and `offhand-render`
or `extra-render` draw decisions.

`BOH_DUALWEAPON_FORCE_SPECIFIC_TYPEKEY=1` makes specific weapon lookup results
such as `45` draw as `45000000` instead of reusing the generic-looking native
resource key observed in the actor. This is enabled by default for default
weapon IDs because `weapontable.lub` maps item IDs through weapon view IDs; for
example `13412` is the item suffix for `WEAPONTYPE_Twin_Edge_B`, whose view ID
is `45`.

`BOH_DUALWEAPON_FORCE_OFFHAND_VISUAL_SLOT=1` patches the equipment update at
`0xD3E8B1` from `cmovs ecx, ebx` to `cmovg ecx, ebx`. Native code only fills
the visual slot at actor `+0x454` when the offhand item lookup fails; this patch
fills it for normal positive weapon types too, so the client gets a chance to
load the real offhand visual resource through the native equipment layer.

`BOH_DUALWEAPON_PATH_TRACE=1` hooks the native path builders at `0xD5A480` and
`0xD58FF0`. DebugView should show `path phase=main-path ...` and
`path phase=offhand-path ...` lines with the actual resource path handed to the
sprite loader. Current investigation showed these builders can also be reached
by body/accessory paths, so use them as context rather than final proof. The
render-side call through `0xA9A7D0` at `0xD42406` was identified as the
`IsItemUsingArrow` Lua-wrapper flag check, not a weapon resource path builder.

`BOH_DUALWEAPON_RESOURCE_TRACE=1` hooks the global resource loader at
`0xA8D4A0` and the tiny sprite resource setter at `0x556780`. DebugView
`res-load` lines show the exact GRF-relative path requested at runtime, stamped
with the most recent weapon actor/item context. `res-set` lines show which
object receives the render resource key at `+0x24C`. Set
`BOH_DUALWEAPON_RESOURCE_TRACE_ALL=1` only for short launches when the filtered
trace does not catch the needed path.

`BOH_DUALWEAPON_RESOURCE_REDIRECT=1` is enabled by default. When a dual-wield
context asks the ACT/SPR loader at the observed equipment return site
`0x0070C448` for a generic actor weapon path, the DLL rewrites
`job_gender_generic...spr/.act` to the known default item-specific suffix from
`weapontable.lub`, such as item `13412` -> `job_gender_13412.spr/.act`. The
redirect rejects numeric head/body-style prefixes and falls back to the original
generic file if the specific file is missing. DebugView reports this as
`path-redirect ... from="..." to="..."`.

`BOH_DUALWEAPON_RESOURCE_KEY_ALIAS=1` is enabled by default. If the native
resource manager later asks for a specific resource key such as `45000000` and
the direct lookup misses, the DLL can return the cached object from the targeted
redirect instead. DebugView should show `resource-lookup ... alias-cached-object`
when this path succeeds.

`BOH_DUALWEAPON_NATIVE_EQUIP_REFRESH=0` is disabled by default. During the first
dual-wield render context for an actor/item pair, the DLL calls the client's
native main-hand and offhand equipment resource loaders with the resolved
weapon visual IDs. While those loaders run, redirects are side-specific: the
main loader may redirect to the main item suffix, and the offhand loader may
redirect to the offhand item suffix. The client then stores the loaded resource
objects through its own table writes at `[actor+0x4AC]+4` and `[actor+0x4AC]+0xC`.
DebugView reports this as `native-equip-refresh`, including old/new table slots
and `calledMain`/`calledOff`. Keep this opt-in only: the `weapon_15` run proved
these loaders do change visible resources, but they target the actor visual table
instead of the weapon-only draw slot.

`BOH_DUALWEAPON_ACTIVE_RESOURCE_SWAP=1` is enabled by default. When a redirected
item-specific `.act` load succeeds, the DLL caches the returned resource object
by item ID and writes it into the actor's active resource table during the
dual-wield render context: slot `+4` for main hand and slot `+0xC` for offhand.
DebugView reports the observed table as `active-slots` and the write attempt as
`active-swap`. This is the current test path for cases where `_13412` loads
successfully but the visible actor still renders the older generic resource.

`BOH_DUALWEAPON_NATIVE_RESOURCE_OVERRIDE=1` is enabled by default. During the
native dual-wield draw window, known default item-specific main-hand sprites
temporarily replace the actor resource key at `+0x24C`; for example
Twin Edge B view `45` is submitted as `45000000` instead of the generic
`2000000`. The original resource key is restored in the render tail hook.
DebugView reports this as `reason=native-resource-override`.

`BOH_DUALWEAPON_DRAW_KEY` accepts `typekey`, `item`, or `type`. The default
`typekey` mode mirrors the observed native resource key format, so an offhand
weapon type of `2` draws with resource key `2000000`. During replacement draws
the DLL keeps the actor's real main/offhand item slots, switches the hand flag
for the submitted pass, then restores the actor fields immediately after the
draw call. DebugView `draw-context` lines show the submitted item slots and hand
flag. The replacement calls mirror native argument usage: main-hand draws use
job argument `0`, and offhand draws use the client's `C43230(-1)` result.

The DLL also caches native main-hand resource keys observed during normal
renders. For example, if item `13412` renders alone with resource `2000000`,
that cached native resource is preferred when `13412` later appears as the
offhand. DebugView will report this as
`reason=offhand-sideflag-offslot-cache-context`.

Leave `BOH_DUALWEAPON_ACTION_OFFSET` unset while probing. Once an action offset
and attack values are identified from DebugView, set them so attack frames keep
the client's combined sprite and idle/walk frames use the selected source type.

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
