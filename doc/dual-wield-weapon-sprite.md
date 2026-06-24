# Dual-Wield Weapon Sprite — Final Reference
## 2026-06-25 | Target: 2025-07-16 Ragexe 175220998
## Banquet of Heroes | Assassin Cross | Naght Sieger (13412) + Zeny Knife (1238)

---

# 1. GOAL

Render per-item weapon sprites when dual-wielding, instead of generic combined sprites.

| Hand | Item | Expected | Actual |
|------|------|----------|--------|
| Main | Naght Sieger (13412) | `_13412.spr` (type 45) | Generic combined |
| Offhand | Zeny Knife (1238) | `_1238.spr` (type 34) | Never renders |

---

# 2. ROOT CAUSE

Body ACT `어쌔신크로스_남.act` has no individual weapon layers. The native body
renderer (C55C30 → render batch) draws generic `_단검_단검` layers baked into the
ACT file. Independent weapon ACT/SPR files exist in `spritedata.grf` (extracted to
`tmp/dual_weapon_exact` — 142 `.act` + 142 `.spr`) but are not loose under the
client `data/` folder. The native pipeline's weapon sprite loader (`D3F4F0`)
successfully loads per-hand sprites into `[char+0x4AC]+4` and `[char+0x4B8][1]`,
but the renderer reads from a **different object** (the body render part) which
has its own generic ACT pointer at `[part+0x108]`.

## WeaponNameTable (weapontable.lub)

| Weapon | Type | Suffix |
|--------|------|--------|
| SHORTSWORD (generic) | 1 | `_단검` |
| SHORTSWORD_SHORTSWORD | 25 | `_단검_단검` |
| Zeny_Knife | 34 | `_1238` |
| Naght Sieger (Twin Edge B) | 45 | `_13412` |

## Expansion_Weapon_IDs (weapontable_f.lub)

`GetRealWeaponId` (called by `D5DDB0` in D72D30) remaps specific types back to base:
- `34 → 1` (Zeny_Knife → SHORTSWORD)
- `45 → 2` (Twin_Edge_B → SWORD)

---

# 3. KEY ADDRESSES

## Render Pipeline

| Address | Symbol | Purpose |
|---------|--------|---------|
| 0x00D41DF0 | MainRenderDispatch | Orchestrator — calls C58EE0, D72D30 |
| 0x00C58EE0 | RenderModeSetter | Actor-part dispatcher (thiscall: ecx=charObj) |
| 0x00D72D30 | WeaponTypeFunc | Returns weapon type; calls D95500 + D5DDB0(GetRealWeaponId) |
| 0x00C55C30 | ActorSubmit1C | Init/configure — reads `[part+0x108]` ACT pointer |
| 0x00D95500 | Combiner | (mainItem, offItem) → combined type 25-30 |
| 0x00D5DDB0 | GetRealWeaponId | Lua call remapping specific types → base |
| 0x00D8A1D0 | ItemToType | itemId → weapon type |
| 0x00D3E850 | WeaponSetup | vtable +0x50 — sets up charObj fields, calls D3F4F0 |
| 0x00D3F4F0 | WeaponSpriteLoader | vtable +0x58 — loads sprites into `[char+0x4AC]`/`[char+0x4B8]` |
| 0x00A8D4A0 | ResourceLoader | ACT/SPR resource load |
| 0x00D5A480 | GetJobName | MISLABELED — not a weapon path builder |
| 0x00D58FF0 | job/name helper | MISLABELED — not an offhand path builder |

## Character Object Fields

| Offset | Content |
|--------|---------|
| +0x1C | Current render mode (2=single, 9=dual-wield) |
| +0x260 | Gender (sprite path building) |
| +0x438 | Weapon type for BOTH hands (set by D3F4F0) |
| +0x440 | Main hand item ID (RENDER object only — 0 on loader object) |
| +0x444 | Offhand item ID (RENDER object only — 0 on loader object) |
| +0x4AC | Ptr to main-weapon struct; **main handle = `*(*(char+0x4AC)+4)`** |
| +0x4B8 | Ptr to sprite array; **offhand handle = `(*(int**)(char+0x4B8))[1]`** |
| +0x4CC | Job/class code (sprite path building) |
| +0x4DC | Offhand weapon X offset |
| +0x4E0 | Offhand weapon Y offset |

## Global Object

| Address | Purpose |
|---------|---------|
| 0x015FA3C0 | `this` for D72D30 + hundreds of weapon/item functions |

---

# 4. GHIDRA DECOMPILATION

## D41DF0 — Main Render Dispatch

```c
case 9:  // dual-wield
    C43230();  D72D30();  C58EE0();
    // C6D9D0 DrawWeapon ONLY for types 0xD/0xE (bows/guns)

case 2:  // single weapon
    C43230();  D72D30();  C58EE0();  A9A7D0();
    // C6D9D0 ONLY if item uses arrows
```

## C58EE0 — RenderModeSetter

```c
case 2: case 9:
    (**(code **)(*param_1 + 0x1c))();   // C55C30 init
    if (mode != 9 && mode != 2) {
        // Resource branch — SKIPPED for modes 2/9
    }
    (**(code **)(*param_1 + 0x40))();   // next vfunc
```

## D3E850 — Weapon Setup (vtable +0x50)

```c
void __thiscall D3E850(charObj, jobCode, p3, weaponType, p5, itemId, ...) {
    charObj[0x4CC] = jobCode;
    charObj[0x438] = weaponType;   // ← TYPE 42 (Saber) comes from CALLER
    charObj[0x444] = itemId;       // ← offhand item from caller
    D8A1D0(itemId);
    (**(code **)(*charObj + 0x58))(charObj[0x438]);  // calls D3F4F0
}
```

## D3F4F0 — Weapon Sprite Loader (vtable +0x58)

```c
void __thiscall D3F4F0(charObj, weaponType) {
    charObj[0x438] = weaponType;
    offPath = D5A1F0(buf, job[0x4CC], gender[0x260], &type[0x438]);
    D3D7C0(1, offPath);                        // → [char+0x4B8][1]
    mainPath = D5A480(buf, job[0x4CC], gender[0x260], &type[0x438]);
    *(*(char+0x4AC)+4) = A8D4A0(mainPath);    // → [char+0x4AC]+4
}
```

## D5DDB0 — GetRealWeaponId (called by D72D30)

```c
D5DDB0(type) {
    memmove(buf, "GetRealWeaponId", 15);
    A9A7D0(...);  // Lua dispatch → Expansion_Weapon_IDs[34]=1, [45]=2
    return expandedType;
}
```

## D3D7C0 — Generic Sprite Array Loader

```c
void __thiscall D3D7C0(charObj, slot) {
    spriteArray = *(charObj + 0x4B8);
    A8F910();                          // clean old
    handle = A8D4A0(path);
    spriteArray[slot] = handle;        // store
    if (slotCount > 1 && spriteArray[1] != 0) {
        charObj[0x4DC] = deltaX;      // offhand position calc
        charObj[0x4E0] = deltaY;
    }
}
```

## D3DA70 — Batch Sprite Loader (9 slots)

Calls D3D7C0 for slots 0-8 (all weapon/equipment sprites). Called during character construction.

## VTable Layout (base 0x01093B48, 5 actor vtables)

| Offset | Slot Example | Function |
|--------|-------------|----------|
| +0x1C | 0x01093B64 | C55C30 — init/submit |
| +0x40 | 0x01093B88 | (render-related vfunc) |
| +0x50 | 0x01093B98 | D3E850 — weapon setup |
| +0x58 | 0x01093BA0 | D3F4F0 — weapon sprite loader |

---

# 5. EXHAUSTED APPROACHES

## Native Pipeline Hacks (1-18)

| # | Approach | Result |
|---|----------|--------|
| 1-18 | Mode remaps, type replaces, SYNTH_DRAW, resource branch, path hooks, combiner intercepts, QJS patching, etc. | No per-item sprites visible |

## QJS D95500 Patch (19)

Patched Combiner to return type 34. Failed: D5DDB0 remaps 34→1 via `GetRealWeaponId`.

## QJS D95500 + D5DDB0 NOP (20)

NOPped `GetRealWeaponId` call at 0x00D72DB1. Failed: D72D30 has further type remapping.

## VTable Hook on D3F4F0 (21)

Swapped 5 vtable slots. D3F4F0 hook did 2-pass per-hand remap. **Sprites loaded correctly** (handles validated non-zero). Failed: body ACT compositor reads from different object — per-hand sprites loaded but invisible. Vtable hooks caused hairstyle corruption (hooked body/head parts too) and Alt+F4 crash.

## VTable Hook on D3E850 (22)

Swapped +0x50 slots to capture itemId before D3F4F0. Same problems: body/head corruption, crash.

## Overlay Renderer (23)

GDI layered window draws per-hand weapon sprites. WeaponTypeHook feeds item state. Sprites visible but float (no actor position data). State hooks needed for positioning → same inline hook crash.

## Zero-Hook Memory Polling (24)

Scan for character object to read item slots. Failed: items at +0x440/+0x444 only on RENDER object, not loader object; scanner couldn't find it. D72D30 global (0x015FA3C0) doesn't hold character pointer.

---

# 6. LESSONS LEARNED

1. **Weapon sprites ARE independent** from body ACT. D3F4F0 loads per-item `.spr` files via `B433B0 → A8D4A0`. Handles are valid and non-zero.

2. **Body ACT always wins.** The renderer (C55C30 → render batch) composites the body ACT which has baked generic weapon layers. D3F4F0's handles are in a different object.

3. **Inline hooks crash on Alt+F4.** The game's cleanup path calls through patched JMP instructions during process exit. The `g_unloading` bailout doesn't help — the JMP target is in DLL memory being freed.

4. **Vtable hooks corrupt appearance.** D3F4F0 (+0x58) is on 5 actor vtables including body/head parts. Hooking all 5 loads weapon sprites into body parts.

5. **D5DDB0 = GetRealWeaponId.** Expansion_Weapon_IDs remaps specific types → base types. Patching upstream of this is futile.

6. **WARP QJS API traps:** `$$()` is progress-only (not input), `SetHex` queues writes (GetUint8 reads originals without reflect=true), YAML `[...]` at line start is flow sequence.

---

# 7. FINAL VERDICT

**Per-hand weapon sprites CANNOT be achieved via native pipeline modifications alone.** The body ACT compositing is architecturally separate from the weapon sprite loader. Three options remain:

1. **Modify body ACT files** — inject `_1238` / `_13412` weapon layers into `어쌔신크로스_남.act`. Zero code changes, zero hooks, zero crashes. Requires ACT editor tooling.

2. **Custom renderer with state hooks** — the overlay draws correct sprites but floats without actor position. Accept Alt+F4 crash as cosmetic on process exit.

3. **Accept limitation** — stock generic combined sprites for dual-wield.

---

# 8. DLL FILES

| File | Purpose |
|------|---------|
| `CustomDLL/src/weapon_sprite/weapon_sprite.cpp` | Hooks, state tracking, poller |
| `CustomDLL/src/weapon_sprite/weapon_overlay.cpp` | GDI layered custom renderer |
| `Scripts/Patches/AllowDualCustomWeaponSprites.qjs` | QJS DLL import shim |
| `tools/dual_weapon_act_preview.py` | Offline ACT+SPR renderer |
| `tmp/dual_weapon_exact/` | Extracted weapon ACT/SPR files |
