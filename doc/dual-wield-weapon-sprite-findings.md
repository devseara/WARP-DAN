# Dual-Wield Weapon Sprite DLL — Dead End Findings (2026-06-21)

## Goal
Show specific per-hand weapon sprites (e.g., Twin Edge B `_13412.spr`) instead of generic combined type sprites for Assassin Cross dual-wield on 2025-07-16 Ragexe 175220998.

## Architecture
- DLL: `bohcustoms.dll` (weapon_sprite.cpp, ~5700 lines)
- 12 hooks installed on the EXE's render pipeline
- Key hooks: WeaponTypeFunc (0xD72D30), RenderPrepare (0xD42382), DrawWeapon (0xC6D9D0), ResourceLoader (0xA8D4A0), ResourceKeyLookup (0xA69EB0), Path builders (0xD5A480, 0xD58FF0)

## The Blocking Problem: Async Sprite Loading

The custom `.spr` (e.g., `_13412.spr`) loads **2-3 seconds AFTER the draw call**. Root cause:

1. Native game loads weapon sprites lazily via `ResourceLoaderHookImpl` (0xA8D4A0)
2. Our path-redirect intercepts and changes path to `_13412.spr`
3. BUT this happens on a DIFFERENT code path that fires after the draw
4. By the time the sprite is cached in MRU, the draw call already used the generic sprite

## What We Tried

### 1. MRU Fallback Cache (FAILED)
- Added 4-entry MRU fallback to survive 32-slot main cache eviction
- Problem: cache was EMPTY when draw fired — sprite hadn't loaded yet
- Log: `custom-cache spr=0x6D600A00` at 18.076s, but draw was at 14.776s

### 2. Typekey Return Fix (PARTIAL)
- `ResolveMainDrawResource` returned raw SPR pointer which `IsPlausibleStableWeaponResource` rejected (max 255M)
- Fixed to return typekey instead (e.g., 45000000)
- This fixed the "main-target-invalid" fallback path

### 3. Native Equip Refresh (FAILED)
- Enabled `g_nativeEquipRefreshEnabled = true`
- `CallNativeEquipLoad` triggers native equip load which loads NATIVE type sprites
- BUT `ResourceLoaderHookImpl` doesn't fire — native loader uses cached sprites, bypassing our hook
- Path captured during refresh is for WRONG type (body part 13, not weapon type 45)
- `EagerLoadSpecificWeaponSprite` never successfully loads anything

### 4. Path Hook Capture + Eager Load (FAILED)
- Path hooks capture generic path during native equip refresh
- `TryBuildSpecificWeaponPathForItem` redirects to specific path
- BUT the captured path is for body type (13), not weapon type (45)
- Resulting specific path `_13_13412.spr` doesn't exist

## What Works
- Resource redirect DOES work — `path-redirect` lines show `_13412.spr` loading correctly
- MRU cache IS populated when redirect fires
- Active resource swap DOES write to character resource table
- Head-bug was fixed (typekey return fix eliminated the corrupt fallback path)

## What Remains Broken
- **Specific weapon sprites**: Only generic sprites show because the custom `.spr` loads too late
- **Arrows on attack**: Extra-render pass draws offhand with attack animation showing arrows
- **Alt+F4 crash**: Fixed with __try/__except around RestorePatchedBytes in DllMain detach

## Key Insight
The native render pipeline fires draw calls BEFORE the resource loader loads sprites. The resource loader is lazy and fires on a separate code path. There is NO synchronous way to force the specific sprite to load before the draw without fundamentally restructuring the render pipeline.

## Potential Solutions (Unattempted)
1. **Preload all specific sprites at DLL attach**: Load every known specific weapon `.spr` at startup
2. **Modify the path IN-PLACE in the path hook**: Write redirected path into the game string buffer before native loader reads it (risky — buffer overflow potential)
3. **Hook an earlier render stage**: Find a hook point that fires before the path builder, trigger eager load there
4. **Use a completely different approach**: Instead of DLL hooks, use QJS byte-patching to modify the WeaponNameTable or sprite suffix mapping directly in the EXE
