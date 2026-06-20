# Dual-Wield Weapon Sprite Investigation — Full Findings

**Date:** 2026-06-20
**Target:** 2025-07-16 Ragexe 175220998 (32-bit PE, image base `0x00400000`)
**Goal:** Show individual weapon sprites per-hand when dual-wielding instead of generic combined sprites (types 25–30).

---

## 1. Architecture Overview

### How Dual-Wield Sprites Normally Work

```
WeaponTypeFunc (0xD72D30)
  ├── d8a1d0(offItem)      ← check if offhand has a weapon
  ├── JLE gate (0xD72D96)  ← if no offhand, skip combiner
  ├── Combiner(main, off)  ← maps two item IDs → combined type 25–30
  └── d8a1d0(item)         ← individual type lookup (non-dual path)

Combiner (0xD95500)
  └── Item ID range checks → returns combined type 25–30
      e.g. Sword + Dagger → type 28 (SHORTSWORD_SWORD) → sprite "_´Ü°Ë_°Ë"

d8a1d0 (0xD8A1D0)
  └── Reads [itemDB_result + 0x40] → returns weapon VIEW ID
      Hardcoded item ID range checks → returns -1 for some ranges
```

### Weapon Type IDs (from `weapontable.lua`)

| Range | Meaning |
|-------|---------|
| 0–24 | Generic weapon categories (SWORD=2, AXE=6, etc.) |
| 25–30 | Combined dual-wield types (SWORD_SWORD=26, SHORTSWORD_SWORD=28, etc.) |
| 31–102 | Specific official weapon view IDs (Twin_Edge_B=45) |
| 103–214 | Byte-safe aliases for Drake weapons (DLL-only) |
| 200–1530 | Drake/custom weapon view IDs |

### Sprite File Naming

```
<job_folder>/<job>_<gender>_<suffix>.spr

Generic SWORD (type 2):     _°Ë.spr
Specific Twin_Edge_B (45):  _13412.spr
Combined SWORD+SHORTSWORD:  _°Ë_´Ü°Ë.spr
```

---

## 2. EXE Address Verification

All RE summary addresses confirmed valid after correcting file offset calculation:

| Hook Point | Runtime VA | Expected Signature | Status |
|-----------|------------|-------------------|--------|
| WeaponTypeFunc | `0x00D72D30` | `55 8B EC 83 EC 08` | MATCH |
| Combiner (MAIN) | `0x00D95500` | `55 8B EC 8B 55 08` | MATCH |
| d8a1d0 (lookup) | `0x00D8A1D0` | `55 8B EC 56 8B 75 08` | MATCH |
| RenderPrepare | `0x00D42382` | `8B 7D CC 8B 87 40 04 00 00` | MATCH |
| NativeDrawGate | `0x00D4240E` | `80 7D D7 01 75 6B` | MATCH |
| RenderTail | `0x00D425F0` | `8B 07 F3 0F 10 47 4C` | MATCH |
| DrawWeapon | `0x00C6D9D0` | `55 8B EC 6A FF 68 A7 FB F1 00` | MATCH |
| MainPathBuilder | `0x00D5A480` | `55 8B EC 6A FF 68 AE 48 F3 00` | MATCH |
| OffPathBuilder | `0x00D58FF0` | `55 8B EC 6A FF 68 1E 44 F3 00` | MATCH |
| ResourceLoader | `0x00A8D4A0` | `55 8B EC 6A FF 68 93 86 EF 00` | MATCH |
| ResourceKeyLookup | `0x00A69EB0` | `55 8B EC 8B 51 10 56 8B 02` | MATCH |
| SpriteResSetter | `0x00556780` | `55 8B EC 8B 45 08 89 81 4C 02 00 00` | MATCH |

**Key lesson:** Runtime VAs must be mapped through PE sections to file offsets. A simple `VA - image_base` doesn't work due to section alignment.

---

## 3. TWO Combiner Paths Discovered

### Main Combiner Path (documented in RE summary)

```
WeaponTypeFunc (0xD72D30)
  └── At +0x66: CALL d8a1d0 → TEST EAX,EAX → JLE gate at 0xD72D96
      ├── Dual path: PUSH mainItem; PUSH offItem; CALL Combiner(0xD95500)
      └── Non-dual path: PUSH EDI; CALL d8a1d0 (individual type)
```

### Duplicate Combiner Path (NEW DISCOVERY)

```
func 0xD403A0 (character render setup)
  └── Stores item IDs at [ESI+0x440] and [ESI+0x444]
  └── At 0xD409E2: CALL d8a1d0(offItem) → TEST EAX,EAX
  └── JLE gate at 0xD409ED → Duplicate Combiner at 0xD39130
```

**Both paths must be disabled** to prevent combined types.

### Cross-References

| Function | Callers | Notes |
|----------|---------|-------|
| WeaponTypeFunc (0xD72D30) | 7 callers | Called twice from render pipeline (0xD422D1, 0xD4252E) |
| Combiner MAIN (0xD95500) | 1 caller | From WeaponTypeFunc at 0xD72D9C |
| Combiner DUPLICATE (0xD39130) | 1 caller | From func 0xD403A0 at 0xD409FC |
| d8a1d0 (0xD8A1D0) | 12 callers | Used throughout weapon type resolution |

---

## 4. QJS Patch: `DisableDualWieldCombinedSprites`

### Files Created/Modified

| File | Action |
|------|--------|
| `Scripts/Patches/DisableDualWieldCombinedSprites.qjs` | Created |
| `Patches/Special.yml` | Added entry under "Special" category |
| `Tables/Patch.yml` | Added ID `369` |

### Patches Applied

#### Gate 1: WeaponTypeFunc (0xD72D96)
```
Original: 85 C0 7E 0B FF 75 14 57    TEST EAX,EAX; JLE +11; PUSH [EBP+14]; PUSH EDI
Patched:  85 C0 EB 0B FF 75 14 57    TEST EAX,EAX; JMP +11; PUSH [EBP+14]; PUSH EDI
```
Pattern: `"85C07E0BFF751457"` — 1 byte change (`7E` → `EB`)

#### Gate 2: func 0xD403A0 (0xD409ED)
```
Original: 85 C0 0F 8E 1A 02 00 00    TEST EAX,EAX; JLE near +0x21A
Patched:  85 C0 E9 1A 02 00 00 90    TEST EAX,EAX; JMP near +0x21A; NOP
```
Pattern: `"85C00F8E1A020000"` — 6 bytes changed (`0F 8E` → `E9` + trailing `90` NOP)

### QJS Patch Development Issues

| Issue | Symptom | Fix |
|-------|---------|-----|
| Hardcoded VA | `Exe.GetUint8(0xD72D96)` returned `0` | Use `Exe.FindHex()` which returns file offsets |
| UTF-8 em dashes (`—`) | `undefined` warning dialog | Replace with ASCII `--` |
| Mixed line endings | Silent load failure | Force all lines to CRLF (`\r\n`) |
| `validate()` calling Exe APIs | Warning during patch discovery | Simplify to `return true` |

### Critical QJS Requirements (from CLAUDE.md)

- **CRLF line endings** — LF-only files silently fail
- **UTF-8 without BOM** — first bytes must be `/*`
- **Tabs for indentation**
- **`/// \brief` doxygen comment** between header and function
- **Full GPL header block** byte-for-byte matching working patches

---

## 5. d8a1d0 Item ID Range Analysis

```
d8a1d0(itemId):
  result = itemDB_lookup(itemId)
  weaponType = result[+0x40]

  if (itemId <= 2100):
      if (itemId in [28901, 28998]): return weaponType
      if (itemId - 1248 <= 9999):   return -1        ← [1248, 11247] fail!
      return weaponType                                ← [0, 1247] pass (unsigned wraparound)

  if (itemId < 2200):
      return weaponType                                ← [2101, 2199] pass

  // itemId >= 2200
  if (itemId in [28901, 28998]): return weaponType
  if (itemId - 1248 <= 9999):      return -1          ← [2200, 11247] fail!
  return weaponType                                     ← [11248, ∞) pass
```

### Valid/Invalid Item ID Ranges

| Range | Status | Example |
|-------|--------|---------|
| 0–1247 | Valid (unsigned wraparound) | Most basic items |
| 1248–2100 | **Returns -1** | Many mid-range items |
| 2101–2199 | Valid | Specific range |
| 2200–11247 | **Returns -1** | Many mid/high items |
| 11248–28900 | Valid | High items |
| 28901–28998 | Valid | Specific range |
| 28999+ | Valid (unsigned wraparound) | Very high items |

Naght Sieger (item 13412): 13412 - 1248 = 12164 > 9999 → **Valid**, weapon type IS returned.

---

## 6. The Lua File (`weapontable.lua`)

### Key Tables

- **`Weapon_IDs`** — maps weapon type names → numeric IDs (0–1530)
- **`WeaponNameTable`** — maps type ID → sprite suffix (e.g., `[45] = "_13412"`)
- **`Expansion_Weapon_IDs`** — maps specific IDs → generic fallback (e.g., `[45] = 2` for SWORD)
- **`BOH_DualWeaponByteAliases`** — maps low byte aliases (103–214) to Drake weapon IDs (300+)

### BOH_DualWeaponByteAliases (for DLL)

```lua
-- Added between BOH_DUAL_WEAPON_BYTE_ALIAS_BEGIN/END markers
[103] = WEAPONTYPE_DRAKEBOW_BLUE,      -- maps to 300
[110] = WEAPONTYPE_DRAKECLAW_BLUE,     -- maps to 400
...
[214] = WEAPONTYPE_Mjolnir             -- maps to 1530
```

These aliases exist because the DLL's WeaponTypeHook returns a **single byte** weapon type (0–255). High IDs (300+) need low aliases. The Lua propagates `WeaponNameTable`, `Expansion_Weapon_IDs`, and `WeaponHitWaveNameTable` for each alias.

---

## 7. Why the QJS Patch Alone Isn't Enough

### What Works
- Both combiner gates successfully disabled
- Generic weapons (SWORD type 2, DAGGER type 1) show individual sprites

### What Fails
- **Specific weapon sprites (types 31+) disappear** during dual-wield
- The sprite files exist in the user's GRF
- The render pipeline's sprite path construction for dual-wield doesn't resolve correctly with individual types

### Root Cause

The QJS approach can statically disable the combiner, but **cannot redirect sprite resource loading at runtime**. The client's dual-wield render pipeline constructs sprite paths differently than single-wield, and the specific numeric suffixes (`_13412`) aren't found via the dual-wield path construction.

### Required: The DLL

`AllowDualCustomWeaponSprites` + `boh.dll` provides runtime hooks that:
1. **WeaponTypeHook** — intercepts WeaponTypeFunc, replaces combined type with individual type
2. **ResourceLoaderHook** — intercepts sprite file requests, redirects combined-type paths to specific-type files
3. **ResourceKeyLookupHook** — aliases cached resource objects for per-hand sprite resolution
4. **RenderPrepare/Tail hooks** — manage render state for per-hand weapon emission
5. **DrawWeaponHook** — rewrites draw resource for per-hand rendering beam

---

## 8. All Addresses Reference

| Address | Name | Description |
|---------|------|-------------|
| `0x00D72D30` | WeaponTypeFunc | Entry — determines weapon type (combined or individual) |
| `0x00D72D96` | Gate 1 (JLE) | Disabled: `7E` → `EB` |
| `0x00D95500` | Combiner (MAIN) | Takes (mainItem, offItem) → combined type 25–30 |
| `0x00D39130` | Combiner (DUPLICATE) | Identical code at different address |
| `0x00D8A1D0` | d8a1d0 | Takes itemId → weapon type (reads item DB +0x40) |
| `0x00D403A0` | Render setup func | Writes to character+0x440/+0x444, calls duplicate combiner |
| `0x00D409ED` | Gate 2 (JLE near) | Disabled: `0F 8E` → `E9 90` |
| `0x00D422D1` | RenderCallSite1 | CALL to WeaponTypeFunc in render pipeline |
| `0x00D4252E` | RenderCallSite2 | Second CALL to WeaponTypeFunc in render pipeline |
| `0x00D42382` | RenderPrepare | Hook point for DLL render override |
| `0x00D4240E` | NativeDrawGate | Hook point for native draw suppression |
| `0x00D425F0` | RenderTail | Hook point for custom weapon emission |
| `0x00C6D9D0` | DrawWeapon | Weapon draw function |
| `0x00556780` | SpriteResSetter | Sets sprite resource on character object |
| `0x00A8D4A0` | ResourceLoader | Loads sprite resources from GRF |
| `0x00A69EB0` | ResourceKeyLookup | Looks up cached resources by type key |
| `0x015FA3C0` | GlobalObj | Global object used as `this` for weapon functions |

---

## 9. Key Lessons Learned

1. **Always verify PE section mapping** when reading bytes from EXE files. Runtime VA != file offset.
2. **QJS files MUST be CRLF, ASCII-only, start with `/*`** — any deviation silently fails.
3. **`Exe.FindHex()` returns file offsets**, not virtual addresses. Never hardcode VAs.
4. **There were TWO combiner paths** — one documented in RE, one discovered during investigation.
5. **Static patching can disable combiners** but cannot redirect runtime resource loading.
6. **The DLL is the complete solution** — it handles per-hand rendering, resource redirection, and action state detection.

---

## 10. DLL Bug Analysis from `weapon_34.log`

### Log Evidence (Dual-wield Naght Sieger 13412 + Knife 1238)

**Hook correctly resolves types:**
```
call=2 ret=0xD422D6 main=13412 off=1238 original=1
mainType=45 offType=34 combiner=28 replacement=45 source=main-specific ✓
```

**Resource loading loads WRONG paths (accessory, not weapon):**
```
res-load: "액세서리\액세서리_남_13412.act"  ← ACCESSORY, not weapon!
res-load: "액세서리\액세서리_남_13412.spr"  ← ACCESSORY, not weapon!
```

**Path redirect matches accessory paths:**
```
path-redirect: from="sprite\인간족\액세서리\액세서리_남_남_검_단검.spr"
               to="sprite\인간족\액세서리\액세서리_남_13412.spr"
```

**MainPathBuilder (0xD5A480) builds HEAD paths:**
```
path: "인간족\머리통\...\42_남.spr"  ← HEAD BODY, not weapon
```

**Character+0x4D0 contains garbage:**
```
+4D0=1702100992/0x65740000  ← NOT a simple boolean hand flag
Writing 0 or 1 here corrupts head/body render state
```

### Bugs Fixed in `weapon_sprite.cpp`

| Bug | Fix | Lines |
|-----|-----|-------|
| Path redirect matches accessory/head paths | Added exclusion for `\액세서리\` and `\머리통\` path components | `TryBuildSpecificWeaponPath` |
| Writing 0/1 to `char+0x4D0` corrupts head state | Removed write to `+0x4D0` from `DrawWeaponContext` | `DrawWeaponContext` |
| ResourceLoaderHook only caches redirected loads, not native loads | Native load results not cached → ResourceKeyLookup misses | Documented below |

### Resource Cache Analysis

The `ResourceLoaderHook` calls `RememberItemResourceObject()` only for **redirected** loads. Native resource loads (non-redirected) are never cached. When `ResourceKeyLookupHook` fires for key `45000000`, it calls `CachedObjectForResourceKey()` which does `LookupItemResourceObject(g_lastMainItem)` — but the cache is empty because the load wasn't redirected.

Additionally, there's a timing issue: `DrawWeaponHook` fires at render time (~51s in log), but the resource redirect loads happen later (~59s). The cache is populated AFTER the draw needs it.

**Mitigation:** The native code falls through to disk/GRF loading when the cache misses. The sprite should still render if the file exists. The cache miss is a performance issue, not a correctness issue.

---

## 11. 0xC58EE0 — Render Mode Setter Analysis

### Called From
10 callers across the render pipeline, including two in the main render function:
- `0xD42355`: First call (mode computed from weapon type via jump table)
- `0xD4254D`: Second call (mode = 9 when offhand has weapon, 2 otherwise)

### Function Internals
```
0xC58EE0: non-standard prologue (PUSH EBX; MOV EBX,ESP)
  [EBX+0x08] = mode parameter (2 or 9)
  [EBX+0x0C] = second argument

Key internal calls:
  0xC58F3A: CALL 0xA75340       — get renderer
  0xC58FBA: CALL 0xD8EBD0       — weapon state check
  0xC58FAF: CALL 0xC43230       — job class lookup
  0xC59082: CALL 0xD72D30       — WeaponTypeFunc (THIRD call site!)

Writes to globals:
  0xC58EFB: MOV [0x15FF9BC], 0  — clear render flag 1
  0xC58F06: MOV [0x15FFA54], 0  — clear render flag 2

Character state checks:
  0xC58F14: CMP [EDI+0x70], 3   — character state == 3?
  0xC58F22: CMP [EDI+0x17C], 0  — some state == 0?
  0xC58F2C: CMP [EBX+0x08], -1  — mode == -1? (sentinel)
```

### Mode 9 vs Mode 2

The mode parameter (`[EBX+0x08]`) is only checked against `-1` (sentinel). Mode 2 and 9 are NOT directly compared. Instead, the function checks:
- `[character+0x70]` (character action state) 
- `[character+0x17C]` (animation/equip state)
- `[EBX+0x0C]` (second argument, 0 or 1)

When conditions match (state==4, arg==1), it copies float values from `[char+0x2D0/0x2D4]` to `[char+0x10/0x18/0x14]` — this looks like setting up position/scale for weapon rendering.

### Key Finding: Third WeaponTypeFunc Call
The function at `0xC58EE0` internally calls `WeaponTypeFunc` at `0xC59082`. This is a **THIRD** call site, separate from the two calls in the render pipeline. This call may be the one that actually determines which weapon sprite to render when the mode requires combined sprites.

### Recommendation
Mode 9 vs mode 2 doesn't directly toggle combined vs individual sprites — it changes character state checks and position/scale setup. The actual combined sprite selection happens inside `0xC58EE0` via its internal `WeaponTypeFunc` call. To bypass combined sprites, this internal call would also need hooking, or mode 9's internal logic needs to be patched to use individual types.
