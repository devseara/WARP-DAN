# Dual-Wield Weapon Sprite — Master Reference
## 2026-06-22 | Target: 2025-07-16 Ragexe 175220998
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

Body ACT `어쌔신크로스_남.act` has no individual weapon layers. Weapon sprites are baked into the body ACT — no separate weapon ACT files exist in this client.

## WeaponNameTable (weapontable.lub)

Types 1-24 are base weapon categories. Types 25-30 are combined dual-wield. Types 31+ are per-item specific.

| Weapon | Type | Suffix | Exists in ACT? |
|--------|------|--------|:---:|
| SHORTSWORD (generic) | 1 | `_단검` | YES |
| SHORTSWORD_SHORTSWORD | 25 | `_단검_단검` | YES |
| Zeny_Knife | 34 | `_1238` | NO |
| Naght Sieger (Twin Edge B) | 45 | `_13412` | NO |

D72D30 returns base type 1 for dagger+dagger instead of specific 34/45.

---

# 3. KEY ADDRESSES

## Render Pipeline

| Address | Symbol | Purpose |
|---------|--------|---------|
| 0x00D41DF0 | MainRenderDispatch | Orchestrator — calls C58EE0, D72D30, etc. |
| 0x00C58EE0 | RenderModeSetter | Actor-part dispatcher (thiscall: ecx=charObj) |
| 0x00D72D30 | WeaponTypeFunc | Returns weapon type from (mainItem, offItem) |
| 0x00C6D9D0 | DrawWeapon | **Arrow/bow ONLY** — never called for daggers |
| 0x00C55C30 | ActorSubmit1C | Init/configure function — NOT a draw submit |
| 0x00C5917A | SkipResourceJe9 | JE 0x52 over resource branch (mode==9) |
| 0x00C5917F | SkipResourceJe2 | JE 0x4D over resource branch (mode==2) |
| 0x00A69EB0 | ResourceKeyLookup | Renderer cache key→object lookup |
| 0x00556780 | SpriteResSetter | `[char+0x24C] = value` |
| 0x00D95500 | Combiner | (mainItem, offItem) → combined type 25-30 |
| 0x00D8A1D0 | ItemToType | itemId → weapon type |
| 0x00D5A480 | MainWeaponPathBuilder | Native weapon ACT path builder |
| 0x00D58FF0 | OffWeaponPathBuilder | Native offhand ACT path builder |

## Character Object Fields

| Offset | Content |
|--------|---------|
| +0x10 | World position (3× float: x, y, z) |
| +0x1C | Current render mode (2=single, 9=dual-wield) |
| +0x24C | Resource key (set by 556780) |
| +0x440 | Main hand item ID |
| +0x444 | Offhand item ID |
| +0x4C8 | Code/class type |

---

# 4. GHIDRA DECOMPILATION

## C58EE0 — RenderModeSetter

```c
void __thiscall FUN_00c58ee0(int *charObj, int mode, char arg) {
    case 2:   // single weapon
    case 9:   // dual-wield combined
        (**(code **)(*param_1 + 0x1c))();  // ← C55C30 init ALWAYS first
        if ((param_1[0x1c] != 9) && (param_1[0x1c] != 2)) {
            // Resource branch — ONLY for modes other than 2/9
            iVar3 = param_1[0x93];  // read [char+0x24C]
            // A69EB0 lookup → C40AC0 angle calc
        }
        (**(code **)(*param_1 + 0x40))();
        break;
}
```

## D41DF0 — Main Render Dispatch

```c
case 9:
    D72D30();   // WeaponTypeFunc
    C58EE0();   // RenderModeSetter
    // C6D9D0 DrawWeapon ONLY for weapon types 0xD/0xE (bows/guns)

case 2:
    D72D30();   // WeaponTypeFunc
    C58EE0();   // RenderModeSetter
    A9A7D0();   // resource resolve
    // C6D9D0 DrawWeapon ONLY if item uses arrows
```

## C55C30 — Init Function (NOT a draw)

Sets position, scale, animation frame. Drawing happens later in render batch.

## C6D9D0 — DrawWeapon

Creates render commands via DA9E50 → vfunc+8 with opcode 0xE (arrow projectile).
Never called for daggers natively. Manual calls create wrong render commands.

---

# 5. EXHAUSTED APPROACHES

| # | Approach | Result |
|---|----------|--------|
| 1 | Mode remap 9→2 | Attack frames vanish |
| 2 | Type replace 1→34/45 | No visual change (ACT lacks layers) |
| 3 | Offhand slot zero ([char+0x444]=0) | No change |
| 4 | Mode + type combined | Generic stance, vanish on attack |
| 5 | SYNTH_DRAW (DrawWeapon) | Arrow-only opcode, ignored |
| 6 | Resource branch NOP | Only sets rotation angle |
| 7 | FORCE_RESOURCE_KEY | [char+0x24C] unused for mode 2/9 |
| 8 | Path hook intercept | No separate weapon paths |
| 9 | D3D EndScene drawing | State conflicts, loading/Alt+F4 only |
| 10 | GDI layered overlay | Window tracking + crash issues |
| 11 | MRU cache | Empty at draw time (async load) |
| 12 | QJS JLE→JMP | Generic sprites, attack breaks |
| 13 | Call-site hook | Space allocation failed |
| 14 | Guard bypass | Crashes — not meant for dual-wield |
| 15 | Combiner intercept | Shared slot fillers broken |
| 16-18 | All env-flag combinations | No change |

---

# 6. WORKING PIPELINE (weapon_9.log)

Flags: `AUTO_SYNTH_VISUAL=1, SUPPRESS_NATIVE_SUBMIT=1, SYNTH_DRAW=1`

| Frame | What happens |
|-------|-------------|
| 1 | Cold cache — combined sprite shows (suppress=0) |
| 2 | SynthPath loads ACT, alias created, suppress=1, SYNTH_DRAW fires |
| 3+ | Both cached, suppress=1, main+off SYNTH_DRAW every frame |

SYNTH_DRAW calls fire but sprites invisible — DrawWeapon is arrow-only.

---

# 7. DLL FILES

| File | Purpose |
|------|---------|
| `CustomDLL/src/weapon_sprite/weapon_sprite.cpp` | 11 EXE inline hooks + tracer |
| `CustomDLL/src/weapon_sprite/weapon_overlay.cpp` | GDI layered window test |
| `Scripts/Patches/AllowDualCustomWeaponSprites.qjs` | QJS DLL import shim |
| `tmp/build_wpn.bat` | Standalone DLL build script |

---

# 8. REMAINING OPTIONS

1. **Modify body ACT** — add `_1238` / `_13412` weapon layers
2. **Fix GDI overlay** — crash fix + game-window binding
3. **Accept limitation** — this client bakes weapon sprites into body ACT
