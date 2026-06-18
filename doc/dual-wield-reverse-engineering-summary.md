# Dual-Wield Weapon Sprite RE Summary

**Target:** 2025-07-16 Ragexe 175220998 (32-bit PE, image base 0x00400000)  
**Goal:** Show individual weapon sprites per hand when dual-wielding (Assassin) instead of the combined WEAPONTYPE_*_* sprite (types 25-30).

---

## 1. How Dual-Wield Sprites Work

### Weapon Type IDs (from `weapontable.lua`)
```
0-24:   Generic weapon categories (SHORTSWORD=1, SWORD=2, AXE=6, etc.)
25-30:  Combined dual-wield types (SHORTSWORD_SHORTSWORD=25, SWORD_SWORD=26, etc.)
31+:    Specific weapon view IDs (Twin_Edge_B=45, which maps to sprite suffix "_13412")
```

The `Expansion_Weapon_IDs` table maps specific IDs (31+) → generic categories as fallback.

### Sprite File Naming
Constructed as: `<job_folder>/<job>_<gender>_<sprite_suffix>.spr`
- Generic SWORD (type 2): `_검.spr`
- Specific Twin_Edge_B (type 45): `_13412.spr`
- Combined SHORTSWORD_SWORD (type 28): `_단검_검.spr`

The combined sprite file shows BOTH weapons drawn together as a single unit. There is NO separate offhand render pass for dual-wield in the client architecture.

### The Combiner Function
At `0x00D95500` — takes two item IDs, classifies each into weapon categories by ID range (0x44C-0x47D for swords, 0x3458-0x34BC for shortswords, 0x7A120+ for customs), returns a combined type 25-30. Only ONE caller at `0x00D72D9C`.

---

## 2. Call Chain

```
0x00D422D1: CALL 0xD72D30 → combined type determination function
    │
    ├── ECX = 0x15FA3C0 (global object)
    ├── arg3 = main item ID ([ESP+0x0C])
    ├── arg4 = off item ID  ([ESP+0x10])
    │
    └── returns AL = weapon type (combined 25-30 for dual-wield)
            stored at [EBP-0x29] in caller
```

### Function at 0xD72D30 (weapon type determination)
- Entry: `55 8B EC 83 EC 08` (PUSH EBP; MOV EBP,ESP; SUB ESP,8)
- Prologue: 6 bytes stolen by trampoline
- At `0x00D72D8D`: `CALL 0xD8A1D0` — checks if offhand has weapon
- At `0x00D72D96`: `JLE 0xD72DA3` — if no offhand weapon, skip combiner (non-dual path)
- Dual path: `CALL 0xD95500` (combiner) → combined type
- Non-dual path: `CALL 0xD8A1D0(EDI)` → individual type
- Has jump table for types 0-25 at `0x00D72FC4`
- Returns via `RET 0x10` (cleans 4 stack args)

### d8a1d0 (weapon type lookup) at 0x00D8A1D0
- __thiscall: ECX=0x15FA3C0, stack=[itemId], RET 4
- Calls `0x006A2BD0(itemId)` → reads `[result+0x40]` → weapon type
- Checks item ID ranges, returns -1 for customs, weapon type for standards

### Caller function (around 0x00D42286)
After `CALL 0xD72D30` returns:
1. Combined type stored at `[EBP-0x29]`
2. `CALL 0xD5D0D0` — weapon property calculation (not sprite render)
3. `CALL d8a1d0(main_item)` at 0x00D42396 → main hand INDIVIDUAL type
4. Main hand sprite path constructed at 0x00D423A1-0x00D423CF
5. `CALL 0xD9CF80` at 0x00D4248E — offhand check (GUARD 1)
6. `CMP [EDI+0x4D0], 1` at 0x00D4249B — state flag (GUARD 2)
7. Offhand render at 0x00D424A7-0x00D424DC — **NEVER REACHED for dual-wield**

**Critical finding:** Guards 1-2 block the offhand render path. The combined sprite handles everything. The offhand render path at 0x00D424A7 is for a DIFFERENT feature (likely non-dual-wield shields or special weapons). Forcing it open crashes (CALL through null vtable pointer).

---

## 3. What We Tried

### QJS Patches (all failed)
| Approach | Result |
|----------|--------|
| JLE→JMP at 0x00D72D96 (DisableDualWieldCombinedSprites) | Shows generic individual sprites for idle/walk, weapons disappear during attack. `item:0` for dual-wield. |
| Two-hook: combiner intercept + render redirect (PerHandWeaponSprites) | Shared slot Fillers broken in raw hex context. Rel32 offset calculation wrong. Crash. |
| Guard bypass + offhand render hook (OffhandWeaponSprite) | Guards NOP'd, but offhand path crashes — not meant for dual-wield. |
| Call-site hook (TraceDualWieldPipeline) | Space allocation failed. |

### C++ DLL (boh.dll module)
| Approach | Result |
|----------|--------|
| Call-site hook at 0x00D422D1 | Crashes — stack misalignment. |
| Function-entry hook at 0x00D72D30 with trampoline | **STABLE.** No crash. |
| Replaced combined type with `d8a1d0(offItem)` | Shows generic individual sprites during idle/walk. Weapons disappear during attack (same as JLE→JMP). |

---

## 4. DLL Hook Architecture (Working)

### Hook Point
Function entry at `0x00D72D30`. First 5 bytes (`55 8B EC 83 EC 08`) replaced with `JMP WeaponTypeHook`. Trampoline built via `VirtualAlloc` — executes displaced bytes + JMPs to body at `0xD72D30+6`.

### Stack Layout at Hook Entry
```
[ESP+0x00] = return address (to 0xD422D6, pushed by CALL at 0x00D422D1)
[ESP+0x04] = arg1
[ESP+0x08] = arg2
[ESP+0x0C] = mainItem (arg3)
[ESP+0x10] = offItem  (arg4)
ECX = 0x15FA3C0
EBP = caller's frame pointer → [EBP-0x34] = character object
```

### Hook Logic
```
1. Save offItem from [ESP+0x10] → g_savedOffItem
2. Save character object from [EBP-0x34] → g_savedCharObj (for action probe)
3. CALL g_origTramp → original function runs → RET 0x10 back to us
4. Check combined type range [25, 30]:
   a. If in range: CALL d8a1d0(g_savedOffItem) → individual type → use as return
   b. If not: keep original combined type
5. Adjust ESP (sub esp, 16) and RET 16 to match original caller's expectation
```

### Return Stack Fix
After trampoline's RET 0x10: ESP = entry_ESP + 0x10. Original return addr at [entry_ESP] = [ESP-0x10]. Need `sub esp, 0x10; ret 0x10` to return correctly (pops return addr from [entry_ESP] and cleans 16 bytes of original args). Actually uses: `sub esp, 16; ret 16`.

---

## 5. Key Addresses

| Address | Name | Description |
|---------|------|-------------|
| 0x00D72D30 | WeaponTypeFunc | Entry — determines weapon type (combined or individual) |
| 0x00D95500 | Combiner | Takes (mainItem, offItem) → combined type 25-30 |
| 0x00D8A1D0 | d8a1d0 | Takes itemId → weapon type (reads from item DB) |
| 0x00D422D1 | CallSite | CALL to 0xD72D30 from caller function |
| 0x00D422D6 | ReturnAddr | Instruction after CALL — where function returns to |
| 0x00D42396 | MainHandSprite | CALL d8a1d0(mainItem) — main hand individual sprite lookup |
| 0x00D4248E | OffhandGuard1 | CALL 0xD9CF80 — first guard for offhand render |
| 0x00D4249B | OffhandGuard2 | CMP [EDI+0x4D0],1 — second guard |
| 0x00D424B7 | OffhandRender | CALL 0xC43230 — offhand weapon type lookup (never reached) |
| 0x00D5D0D0 | RenderProp | Weapon property calculator (NOT sprite renderer) |
| 0x15FA3C0 | GlobalObj | Global object used as `this` for weapon functions |
| 0x100E158 | FormatStr | Format string `"d>b"` (not a full sprite path) |

---

## 6. Remaining Challenges

### A. Generic vs Specific Sprites
`d8a1d0()` returns the weapon CATEGORY (type 2=SWORD), not the specific view ID (type 45=Twin_Edge_B). The specific sprite lookup happens LATER in the pipeline via `Expansion_Weapon_IDs` Lua table and sprite path construction. Our hook operates BEFORE that step. Result: both hands show generic weapon sprites, not the item's specific sprite.

### B. Attack Animations
Individual weapon types (0-24) don't have `.spr` files with dual-wield attack animation frames for Assassin-class jobs. The sprite files simply don't exist in the GRF data. When the character attacks, the weapon sprite can't be found → weapon disappears.

**Proposed fix:** Detect the character's action state (idle/walk vs attack). Skip type replacement during attack frames (keep combined type → attack animation works). Use individual type only during idle/walk.

### C. Action State Detection
The DLL reads the character object from `[EBP-0x34]` at hook entry. A probe function (`WriteProbe`) writes candidate action offsets (+1C, +20, +24, +28, +40, +44, +48) to `boh_action_probe.log` every N calls. The user needs to test with different actions (idle, walk, attack) to identify which offset changes — that's the action state.

### D. Per-Hand Different Sprites
Even with action detection, both hands would show the SAME individual type (the offhand's) because our hook returns ONE type. To show DIFFERENT sprites per hand, we need to intercept at a DIFFERENT level — either:
1. Sprite file loading (hook `ResMgr::Get` or GRF file access) to redirect combined-type requests to individual-type files per-hand
2. Or add a NEW offhand render pass (duplicate the main hand's d8a1d0 + sprite path construction for the offhand item)

### E. The Client Architecture Limitation
RO was NOT designed for per-hand individual weapon sprites during dual-wield. The combined sprite is a single file containing both weapons. Fixing this properly requires either:
- Deep engine modification (adding render passes)
- Sprite data creation (hundreds of .spr files)
- Lua data remapping (simplest but limited)

---

## 7. Files Modified

| File | Status |
|------|--------|
| `CustomDLL/src/weapon_sprite/weapon_sprite.cpp` | Working — function-entry hook with action probe |
| `CustomDLL/src/boh_features.h` | Modified — added FEATURE_WEAPON_SPRITE |
| `CustomDLL/src/customer_features.h` | Modified — added BOH_WEAPON_SPRITE=1 |
| `CustomDLL/src/main_proxy/main_proxy.cpp` | Modified — added WeaponSpriteDllMain forward decl + call |
| `CustomDLL/src/build.bat` | Modified — added step [10/10] for weapon_sprite compile + link |
| `doc/warp-qjs-architecture-proposal.md` | WARP QJS improvements spec |
| Various QJS patch files in `Scripts/Patches/` | Failed experiments, can be cleaned |
