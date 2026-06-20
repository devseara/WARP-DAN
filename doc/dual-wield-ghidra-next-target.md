# Dual Wield Weapon Sprite Ghidra Handoff

## Current goal

Make dual wield and offhand weapon rendering use the original per-item weapon
sprites, not the client's combined/generic dual wield sprites.

Expected example:

- Right hand Naght Sieger, offhand empty: Naght Sieger sprite
- Right hand Naght Sieger, offhand knife: Naght Sieger sprite plus knife sprite

Current runtime hook can identify the right resources:

- Main Naght Sieger resource/type: 45
- Offhand knife resource/type: 34

But the live result has still shown generic dual wield sprites, missing head
state, headgear artifacts, and bow/arrow effects. That means the unresolved
part is not item lookup. It is the native draw context, render mode, or
character render slot binding used when drawing weapon resources.

## Confirmed native path from Ghidra

Single-hand render path:

1. `0x00D422D1` calls `WeaponTypeFunc`.
2. Return at `0x00D422D6` must remain a real weapon view/type, not boolean.
3. `0x00D5D0D0` calculates weapon float/position properties.
4. `0x00D8A1D0(mainItem)` resolves an individual view ID.
5. Code formats the key string around `0x00D423A1`.
6. `0x00A9A7D0(key)` resolves the resource and binds it into `[char+0x24C]`.
7. Native draw pushes `[char+0x24C]` and calls `DrawWeapon`.

Second caller:

1. `0x00D4252E` calls `WeaponTypeFunc`.
2. Return at `0x00D42533` is used as boolean only.
3. Boolean controls render mode `ECX = hasOffhand ? 9 : 2`.
4. Then `0x00C58EE0(char, ECX, arg)` sets render mode/state.

The hook now only booleanizes the second caller return at `0x00D42533`.
The first caller return at `0x00D422D6` stays the real replacement type.

## Latest clean test configuration

The latest DLL should attach with these important flags:

- `extraRender=1`
- `suppressNative=0`
- `forceNativeDrawBranch=0`
- `forceOffhandVisual=0`
- `nativeResourceOverride=0`
- `nativeEquipRefresh=0`
- `drawHook=1`
- `drawRewrite=1`

This intentionally removes the unsafe native state forcing that previously
patched shared character slots and could remove head/headgear state.

## What Ghidra should find next

If this clean test still fails, please inspect these targets in this order.

### 1. Exact DrawWeapon argument contract

Address: `0x00C6D9D0`

Find what each argument really means:

- `this` / renderer pointer
- character/body pointer currently passed as `char + 0x10`
- resource pointer/value
- scale float
- final integer currently treated as job class

Important question:

Is the final integer actually a job class, weapon layer, action, draw mode, or
sprite attachment slot? Passing the looked-up value `4013` caused bow/arrow
behavior, so the meaning is probably not "safe character job for all weapon
draws". Native main hand appears to use `0`.

### 2. Native caller setup immediately before DrawWeapon

Address range: around `0x00D4240E` through `0x00D4245D`

Recover the exact pushes/register values used by the native single-hand call:

- Which pointer is passed for character/body?
- Which scale value is passed?
- Which integer is pushed after scale?
- Which fields are read from character before the call?
- Is `[char+0x4D0]` read by DrawWeapon, or is it only external state?

The synthetic offhand pass should copy this contract exactly, then only swap
the item/resource/hand side fields that are definitely weapon-specific.

### 3. Resource binding side effects of `0x00A9A7D0`

Address: `0x00A9A7D0`

Find all writes caused by resolving key `"45"`/`"34"` style weapon resources.

Known write:

- `[char+0x24C]` through the sprite resource setter chain

Need to know:

- Does it also set a layer index, ACT pointer, SPR pointer, attach/bone slot,
  current action frame, or resource owner?
- Does it depend on global "currently resolving character" state?
- Is `0x00556780` only one setter in a larger binding sequence?

If resource resolver sets more than `[char+0x24C]`, our synthetic pass needs a
native helper call to bind the offhand resource instead of only writing dword
fields manually.

### 4. Render mode state set by `0x00C58EE0`

Address: `0x00C58EE0`

The second caller passes mode `9` when offhand has a weapon and mode `2`
otherwise. Determine exactly what mode `9` changes.

Need to know:

- Does mode `9` force the combined/generic dual wield ACT/SPR path?
- Does mode `9` change head/body layer visibility?
- Is there a nearby mode that means "single hand weapon draw with offhand
  equipped"?
- Can mode `2` be used while offhand is equipped without breaking animation?

If mode `9` always selects combined sprites, then the DLL should allow native
main-hand single sprite rendering under mode `2`, then draw offhand separately.

### 5. Character weapon/head render slots

Known fields currently touched:

- `[char+0x440]`: main item
- `[char+0x444]`: offhand item
- `[char+0x24C]`: current weapon resource pointer/value
- `[char+0x4D0]`: current hand/side flag candidate

Need Ghidra to identify the real layout around:

- weapon resource slot
- shield/offhand resource slot, if any
- head/headgear resource slots
- current draw layer or body part index
- hand side or attachment side

The repeated missing head/headgear artifacts strongly suggest one of the
patched fields is shared with body part/layer state or we are drawing weapon
resources under a head/body layer index.

## Evidence from `weapon_33.log`

The hook reached the intended resources:

- First render caller returned replacement `45` for main Naght Sieger.
- Native draw saw resource `45`.
- Synthetic offhand render attempted resource `34`.

The failure was visual state:

- Two arrow effects were spawned.
- Character head disappeared again.

Interpretation:

Resource lookup is solved enough for the next step. The next proof needed is
the exact native `DrawWeapon` context and all side effects required to bind a
weapon resource to the correct hand/layer without corrupting head/body state.
