# WARP Patch Ecosystem — Comprehensive Knowledge Map

> Generated 2026-06-09 from deep analysis of 178 QJS patches, 9 YAML patch trees,
> and all shared infrastructure modules. Target client: **2025-07-16 Ragexe**.

---

## 1. TECHNIQUE TAXONOMY

Every patch uses one (or a combination) of these binary modification techniques:

### 1.1 Pattern Scan + Hex Byte Patch (~60% of patches — simplest, most reliable)

**How it works:**
1. Call `Exe.FindHex(pattern)` or `Exe.FindHexN(pattern)` to locate target code
2. Verify the address is correct (not in data section, matches expected bytes)
3. Overwrite bytes with `Exe.SetHex()`, `Exe.SetNOPs()`, `Exe.SetJMP()`, etc.
4. Use `Exe.SetInt32/SetInt16/SetInt8` for address/value replacement

**Common patterns:**
- **JZ → JMP**: Change a conditional jump to unconditional (bypass langtype gating)
- **JNZ → NOP**: Remove a conditional jump entirely
- **PUSH imm → PUSH newval**: Change a hardcoded constant
- **CMP reg, old → CMP reg, new**: Change a comparison threshold
- **Zeroing strings**: NOP out txt file references so they never load

**Example patches:**
- `AlwaysAscii.qjs`: NOP out conditional jump after langtype comparison
- `NoNagle.qjs`: Replace socket() call with wrapper that sets TCP_NODELAY
- `HKLMtoHKCU.qjs`: Replace all HKEY_LOCAL_MACHINE with HKEY_CURRENT_USER
- `IncrZoom.qjs`: Replace float constants for zoom limits
- `FixArrowsCharset.qjs`: Replace arrow key charset offsets
- `RemoveMaxNumbersLimit.qjs`: NOP the damage number cap check

### 1.2 Pattern Scan + Code Cave Injection (AutoHook) (~20% of patches)

**How it works:**
1. Find hook point in original code
2. Call `Exe.Allocate(size)` to get `[phyAddr, virAddr]` in DIFF section
3. Build replacement x86 code using the macro DSL:
   - `FP_START`, `FP_STOP` — function prologue/epilogue
   - `MOV`, `PUSH`, `CALL`, `JMP`, `CMP`, `TEST`, `JE`, `JNE`, `JMP`, `RETN`
   - `Filler(idx)` — placeholder resolved by `SetFillTargets` or `SwapFillers`
   - `ALLWC`, `POS2WC`, `NEG2WC` — wildcard/match-any patterns
4. Call `AutoHook(hookAddr, code, args)` which:
   - Writes the code cave
   - Resolves all Fillers (addresses, offsets)
   - Patches the original hook point with JMP to cave
   - Builds the JMP-back trampoline

**The AutoHook abstraction:**
```javascript
const parts = [codePart1, codePart2, ...];
const [resolvedOffsets, allocSize] = MapAddrs(parts);
const args = {
    allocSize,
    localVals: { 1: someAddress },     // Filler(N) = address
    localTgts: { '2,1': _label },      // Filler(2,1) = offset to label in part 2
    targets: { 1: externalAddr },      // Filler(N) = absolute target for CALL/JMP
    preProc: someFunction,             // transform code before writing
    postProc: someFunction             // transform code after resolution
};
AutoHook(hookAddr, parts, args);
```

**Example patches using AutoHook:**
- `CloseCutinOnEsc.qjs`: Swap ESC key check in UIWindowMgr::ProcessPushButton
- `CustomEnchantGradeLabels.qjs`: Replace hardcoded [D]/[C]/[B]/[A] labels
- `EnableProxy.qjs`: Divert connect() to custom proxy function
- `ReturnToLogin.qjs`: Change disconnection behavior
- `CustomBarterZenySep.qjs`: Intercept zeny value in Barter window
- `FixLatestNCWin.qjs`: Fix misaligned character creation window
- `RestoreSongsEffect.qjs`: Reconstruct bard/dancer songs via LandProtector code
- `BookingButtonGuide.qjs`: Reuse Booking button for custom guide packet

### 1.3 Import Table Modification (~5% of patches)

**CustomDLL — Full PE Import Table Rebuild:**

The `CustomDLL.qjs` module is a complete PE import table builder:
1. `CustomDLL.mergeSpec(dllSpec)` — CACHE-based dedup across all callers
2. `GetImpTable(skipDll?)` — parse existing import directory
3. Build new string table, entry table, and directory table in allocated space
4. `Exe.SetDirAddr(D_Import, newTable)` + `Exe.SetDirSize(D_Import, newSize)`
5. `Exe.SetHex(allocAddr, strings + entries + table)` — write the new import table

**Key design insight:** WARP can run the generic `CustomDLL` patch AND dedicated patches
that also call `CustomDLL.applySpec` in the same session. Without `mergeSpec`, whichever
runs last would rebuild the import table with only ITS DLLs, silently dropping earlier ones.
`mergeSpec` accumulates all DLLs from all callers into one merged spec.

**CustomPacketDispatch — Dispatcher Table Entry Replacement:**

A newer, more surgical approach for routing custom packets to shared memory blocks:
1. Locate the packet dispatcher switch table (0xCAA2E0 virtual on 07-16)
2. Verify target entry points to the default handler (meaning the packet is unused by stock code)
3. Allocate a handler stub + route-specific shared transport
4. Write the handler stub (x86 machine code as hex string)
5. Patch the dispatcher table entry to point to the new handler
6. Handler copies packet data from the stock buffer into the shared block, then continues

`ICOL` and `HATF` use the legacy 4096-byte single slot. `ICOL` packets keep
the legacy name table first and may append an `ICL2` typed trailer for
ItemId-first item colors and numeric grade records. `EXTN` uses a 1024-slot
ring (`16-byte header + 1024 * 1024-byte slots`) so initial-login, warp, and
view-entry bursts remain available until the QJS frame consumers run.

**Current routes (07-16):**
| Route | Packet ID | Magic | Purpose |
|-------|-----------|-------|---------|
| ICOL  | 0x0BDD    | 0x49434F4C | Item colors; legacy names plus optional `ICL2` ItemId trailer |
| EXTN  | 0x0BB7    | 0x4558544E | Extended character names (1024-slot ring) |
**Custom patch import behavior:**
- `CustomDLL.qjs`: Generic DLL adder (user provides DLLSpec.yml)
- `CustomRuneSystem.qjs`: QJS-only multiple equipped Rune Sets; no custom DLL import
- `CustomExtName.qjs`: QJS-only bounded EXTN exact-text map; no custom DLL import
- `CustomPlayerNameColor.qjs`: QJS-only exact player-name color scope; no custom DLL import
- `CustomColoredItemName.qjs`: QJS-only bounded ICOL renderer; no custom DLL import. Producer hooks prefer `ICL2` ItemId records where `CItem*` is available, then fall back to exact legacy ItemName matching for old servers and text-only surfaces. Anchored matching covers stock slotless/slotted Inventory quantity forms. A matching grade color conditionally coalesces the native post-grade endpoint and owns the complete decorated title; Inventory quantity tails are omitted for grade matches, and matched dark draws are suppressed. The normative contract is `docs/item-grade-color-renderer-contract.md`.
- `FpsOverlay.qjs`: QJS-only post-Present frame counter and prompted-position static GDI renderer
- `AlwaysShowNpcName.qjs`: QJS-only bounded EXTN table, native balloon frame cave, and static `/shownpcname` toggle
- `ROGlobalZeroInventory.qjs`: QJS-only native inventory layout, tabs, tooltips, and Zeny/weight panel
- `PingOverlay.qjs`: QJS-only stock `0x0360/0x007F` RTT capture and prompted-position shared renderer

### 1.4 String / Data Table Replacement (~10% of patches)

**Techniques:**
- `Exe.FindText("string")` → locate text reference in binary
- `Exe.AddText("newstring")` → add string to data section, returns `[phys, vir]`
- `Exe.SetInt32(pushAddr + offset, newStringVir)` → update PUSH reference
- Zero-out filename strings to prevent loading (NoCameraLock, NoMapInfo, etc.)

**Example patches:**
- `CustomAuraSprites.qjs`: Replace ring_blue.tga → aurafloat.tga filenames
- `CustomMissingLauncherMsg.qjs`: Swap blank error string with custom message
- `HideBuildInfo.qjs`: NULLify build date/time format strings
- `CustomPath.qjs`: Common function to replace file paths (used by ~25 patches)
- `TranslateClient.qjs`: Replace all hardcoded Korean strings with translations

### 1.5 Lua-Based Systems (~5% of patches)

These are the most architecturally sophisticated patches. They replace hardcoded C++ logic
with Lua function calls, enabling server-side customization.

**CustomSkills (3 sub-patches in one file):**
- `CustomPlayerSkills`, `CustomHomunSkills`, `CustomMerceSkills`
- All three are the same function (`CustomSkills`) parameterized by `CustomSkills.Data`
- Find the skill ID checker function (different per version)
- Replace with Lua C API call: `IsPlayerSkill(id)` / `IsHomunSkill(id)` / `IsMercenarySkill(id)`
- Uses `LUA.createCaller("funcName", "d>d", EAX, EAX)` to generate call wrapper
- SkillInfo Lua files loaded once, shared via CACHE tag 'CSK'

**CustomJobs (11-phase 0716 rewrite — 2,200+ lines):**
- Phase 3: Expand palette/head table capacities from stock limits to MaxJob (10000)
- Phase 4: Expand bounds check in GetJobNameByClassAndGender
- Phase 5/5b: Fix convert_job_to_trans_or_baby subtraction for custom job IDs
- Phase 5c: Baby sprite scaling for custom jobs (DRUID_B, KARNOS_B)
- Phase 6: Null resource pointer check in CalcDirectionFromDelta (prevents crash)
- Phase 6b: Suppress "Resource File Loading fail" chat spam
- Phase 7: Lua-based display name override via PCNames table (2 wrapper functions)
- Phase 8: Fix GetJobSpriteIndex range check
- Phase 9c: Entry-level PCNames hook on GetJobSpriteIndex (intercept at function entry)
- Phase 10: Extend is_job_id_in_range from [4332,4349] to [4332,MaxJob]
- Phase 11: Init-time Lua table population via direct Lua C API + cj_loadfile (GRF-aware)
  - Populates PCPaths and PCPals tables for custom job sprites/palettes
  - Registers `cj_loadfile` Lua function (uses CFile::Open for disk+GRF loading)
  - Loads 7 JobInfo Lua files: PCIds, PCPaths, PCPals, PCHands, PCImfs, PCNames, PCFuncs

**Key architectural insight in CustomJobs Phase 11:**
The `cj_loadfile` function is a GRF-aware replacement for Lua's `dofile()`. It uses the
client's own `CFile::Open` (which checks BOTH loose files AND GRF archives) to load
.lua/.lub files. This means custom job definitions work whether the files are loose in
the data folder OR packed inside a GRF — no need for DataFolderFirst.

**Other Lua-based patches:**
- `CustomAura.qjs`: Server-driven EFID model via AuraInfo.lub lookup
- `CustomHomuns.qjs`: Custom homunculus types via ReqJobName Lua function
- `AddLuaOverrides.qjs`: llchrisll's lua override system

### 1.6 Manual Code Cave (No AutoHook) — FpsOverlay/PingOverlay

The FpsOverlay and PingOverlay patches use a completely manual approach to code cave
construction, building x86 machine code byte-by-byte in JavaScript:

```javascript
const b = [];
b.push(0x8B, 0x7D, 0x08);  // MOV EDI, [EBP+8]
// ... build entire handler as raw byte array
let hs = '';
for (let i = 0; i < b.length; i++)
    hs += ' ' + (b[i] < 0x10 ? '0' : '') + b[i].toString(16).toUpperCase();
Exe.SetHex(cavePhy, hs);
Exe.SetJMP(suffixStart, caveVir, 0);
```

**Why?** The documented 0xC8598E2C crash pattern occurs when AutoHook relocates
conditional branches (Jcc instructions) in certain hook contexts. By building the
entire cave manually and avoiding AutoHook entirely, the FPS/ping patches avoid
this crash. The trade-off is significantly more complex code.

**Current native telemetry architecture (2026-07-13):**
1. Prompt independently for FPS and ping X/Y positions; negative coordinates
   are relative to the client right/bottom edge.
2. Share a reference-counted EXE state block and post-`Present` cave at
   `0x00543441`.
3. Count client frames with `GetTickCount`, format bounded decimal text, and
   draw transparent shadowed text through stock Win32 imports.
4. Route `/fps` and `/ping` to static client-option toggles through the shared
   slash-command dispatcher.
5. Capture ping from the stock application exchange: `0x0360` saves the send
   tick at `CGameMode+0x274`, and `0x007F` calculates the RTT before the cave
   copies EAX at `0x00C9E8F8`.
6. No custom DLL, D3D proxy, COM-vtable mutation, ICMP or recv hook remains.

### 1.7 Registry / Config Manipulation

Some patches don't modify the binary at all:
- `HKLMtoHKCU.qjs`: Registry key path string replacement
- Various patches that read/write CACHE without binary changes

---

## 2. SHARED INFRASTRUCTURE

### 2.1 CACHE System

The CACHE module provides in-session state persistence with reference counting.
Critical for multi-patch coordination:

| CACHE Key | Purpose | Users | Cleanup Behavior |
|-----------|---------|-------|-----------------|
| `CIS` | Case-insensitive search shared function | InsensitiveStorageSearch, InsensitiveShopSearch | Auto-clean tag when last user removed |
| `CSK` | Custom skill Lua loaders | CustomPlayerSkills, CustomHomunSkills, CustomMerceSkills | Auto-clean tag when last user removed |
| `PACKET` | Encryption key values | CustomFirstKey, CustomSecondKey, CustomThirdKey | No tag clean, no dealloc |
| `MBAR` | Mob HP bar sizes | ResizeMobBar (4 sub-patches) | No tag clean, no dealloc |
| `NBV` | New button visibility | HideNewButtons, ShowNewButtons | Dealloc after tag clean |
| `ImpInfo` | Import table data | CustomDLL + all applySpec callers | N/A |
| `ImpInfo.OldDir` | Original import directory (diagnostics) | CustomDLL | N/A |
| `CustomPacketDispatch.Routes` | Active dispatcher routes | CustomExtName, CustomColoredItemName, etc. | N/A |
| `CustomDLL.MergedSpec` | Accumulated DLL specs | All CustomDLL users | N/A |
| `FpsOverlay.SlashCmdInstalled` | Whether /fps hook is active | FpsOverlay, PingOverlay | N/A |

### 2.2 CACHE Reference Counting Pattern

```javascript
// Setup (done once in Initializer):
Cache.setup('CIS', 'CaseInsensFn', { cleanTag_after_userDel: false });

// On apply:
const noPrevUsers = !CACHE.hasUsers(cacheKey);
CACHE.addUser(cacheKey, patchName);
if (noPrevUsers) {
    Exe.ActivateGlobal();
    Exe.BeginTag(CACHE.getTag(cacheKey));
    // ... inject shared code ...
    Exe.EndTag();
    Exe.SetActivePatch(patchName);
}

// On cleanup:
CACHE.delUser(cacheKey, patchName);
// Tag auto-removed when last user is gone
```

This pattern is used by: CaseInsensitiveSearch, CustomSkills, CustomEncKeys, ResizeMobBar, NewButtonVisibility.

### 2.3 DLL Loading Patterns

**Explicit DLL-backed features:**
`boh.dll` and the split DLLs remain legacy build artifacts. QJS-only item
colors, extended names, overlays, and inventory features no longer load them.
Only patches explicitly documented as DLL-backed should add one; no visual
patch currently does (`CustomRuneSystem` became QJS-only on 2026-10-08; its
DLL source was removed on 2026-10-09).

| Dedicated DLL | Export Function | Used By |
|---------------|-----------------|---------|
| `boh_npc_names.dll` | `NpcNameOverlayInit`, `NpcNameOverlayFrame` | Legacy AlwaysShowNpcName implementation; no longer imported |
| `boh_rune.dll` | `RuneVisualInit` | Retired 2026-10-09: source removed, `BOH_RUNE_VISUAL` rejected; never deploy |
| `boh_fps.dll` | `FpsPingOverlayInit` | Legacy FpsOverlay implementation; no longer imported |
| `boh_inventory_tabs.dll` | `InventoryTabsInit` | ROGlobalZeroInventory (legacy; no longer imported) |

QJS-only text, name, item-color, overlay, inventory, and rune patches do not call
`CustomDLL`, prompt for a custom DLL filename, or add custom PE imports.

### 2.4 Safety & Backup Modules (2026-06-08)

**SAFETY module:**
- Section-boundary validation: ensures writes fall within CODE or DIFF sections
- Dry-run mode: counts writes without applying them
- Pattern ambiguity detection: warns when `FindHexN` returns multiple matches
- Safe wrappers in AllFuncs.qjs: `SetHexSafe`, `FindHexUnique`, `VerifyBytes`

**EXEBACKUP module:**
- Creates timestamped backup of source EXE before any modifications
- Uses `System.Copy` for binary-safe copy
- Backup path: `<src>.warp_backup_<ISO-timestamp>.exe`

### 2.5 ROC (RO Client) Module

Initialized in `Initializer.qjs` via `ROC.load()`. Provides:
- `ROC.HasFP` — whether the client uses frame pointer (`push ebp; mov ebp, esp`)
- `ROC.FullVer` — Visual C++ version (14.29 for 07-16)
- `ROC.Post2010` — client build date > 2010
- `ROC.findImports()` — locates import table functions
- `ROC.GetModHandle` / `ROC.GetProcAddr` — IAT addresses for runtime DLL loading
- `ROC.Version` — maps to `Exe.Version`

### 2.6 Other Support Modules

- **DGRF**: GRF file manager — `DGRF.RefAddr` (where data.grf path is PUSHed)
- **WINMGR**: Window manager utilities
- **LANGTYPE**: Language/service type detection
- **SRVRTYPE**: Server type detection
- **LUA**: Lua C API helpers — `LUA.createCaller`, `LUA.addLoaders`, `LUA.finalize`
- **PACKET**: Packet encryption key detection — `PACKET.KS_Type` (Pusher/Mover/Obfuscate)
- **MBAR**: Mob HP bar utilities
- **FONTAIN**: Font utilities
- **WINMKR**: Window marker utilities
- **SSN**: Session utilities

---

## 3. PATCH DEPENDENCY GRAPH

### 3.1 Explicit `needs:` Dependencies (from YAML)

| Patch | Requires |
|-------|----------|
| EnableCustomFonts | FixFontsCharset |
| NoPassEncr | UseOldLogin |
| CancelToLogin | RestoreLoginWindow |
| CustomFirstKey | NoEncrForLC |
| CustomSecondKey | NoEncrForLC |
| CustomThirdKey | NoEncrForLC |

### 3.2 Mutex Groups (mutually exclusive — pick one)

| Group | Options |
|-------|---------|
| Camera Angles | LowCamAngle, MediumCamAngle, HighCamAngle |
| Zoom Out | Zoom25Percent, Zoom50Percent, Zoom75Percent, ZoomMax |
| Login Mode | RestoreLoginWindow, UseSSOLogin, UseOldLogin |
| Chat Repeat | UnlimitedChatRepeat, LimitedChatRepeat |
| Roulette Visibility | HideRoulette, ShowRoulette |
| Shared Body Palettes | BodyPalMF, BodyPalUnisex |
| Shared Head Palettes | HeadPalMF, HeadPalUnisex |
| Multiple GRFs | GRFsFromIni, GRFsEmbedded |
| Auto Follow | NoAutoFollow, DecrAFDelay |
| Resurrect Button | HideResButton, ShowResButton |
| Walk Delay | NoWalkDelay, CustomWalkDelay |
| MessageBox | MsgBox2Beep, ShowMsgIcon, NoMsgBox |
| Enable Icon | RestoreIcon, CustomIcon |
| License Screen | HideLicense, ShowLicense |
| Doram Creation | CustomCharCreateSecond, NoDoramCreation |

### 3.3 Implicit / Runtime Dependencies

- **Any packet-color/ext-name patch** → CustomPacketDispatch must be loaded
- **Any DLL-adding patch** → CustomDLL module must be available
- **CaseInsensitiveSearch users** → CaseInsensitiveSearch.qjs must be loaded
- **CustomSkills users** → Lua module must be available, SkillInfo lua files must exist
- **CustomJobs** → JobInfo Lua files (PCIds, PCPaths, etc.) must exist in data folder or GRF
- **FpsOverlay + EnableUnknCmds** → EnableUnknCmds must be applied BEFORE FpsOverlay in patch order

### 3.4 Conflicts

- **OfficialPal** ↔ **CustomJobs** (officially incompatible)
- **NoPacketEncr** ↔ **CustomEncKeys** (mutually exclusive — use one approach or the other)
- **NoPassEncr** + **UseSSOLogin** (conflict — SSO login has its own encryption)
- **CustomDLL 2014-2017 clients**: Import table bugs prevent movement, so CustomDLL was historically disabled for those builds

---

## 4. PATTERN LIBRARY

### 4.1 Common x86 Code Patterns (WARP Macro DSL)

```
FP_START         → 55 8B EC        (push ebp; mov ebp, esp)
FP_STOP          → 8B E5 5D        (mov esp, ebp; pop ebp)
PUSH(imm)        → 68 xx xx xx xx  (push imm32)
PUSH_EAX         → 50              (push eax)
PUSH_R           → 51/52/etc       (push reg)
PUSH_0           → 6A 00           (push 0)
PUSH_STR("str")  → 68 xx xx xx xx  (push addr) + string bytes + JMP over
CALL(addr)       → E8 rel32        (call near)
CALL([addr])     → FF 15 xx xx xx xx (call dword ptr [mem])
JMP(addr)        → E9 rel32        (jmp near)
JE(offset)       → 0F 84 rel32     (je near)
JNE(offset)      → 0F 85 rel32     (jne near)
JZ/JNZ(offset)   → 74/75 xx        (short jump)
MOV(reg, reg)    → 8B xx           (mov r32, r/m32)
MOV(reg, [mem])  → 8B xx xx xx xx xx
CMP(reg, imm)    → 81 F8/83 F8     (cmp r32, imm32/imm8)
TEST(reg, reg)   → 85 C0           (test eax, eax)
ADD(reg, imm)    → 83 C0 xx        (add r32, imm8)
RETN(n)          → C2 xx xx        (retn n)
RETN()           → C3              (retn)
NOPs(n)          → 90 repeated     (nop sled)
ALL00            → 00 00 00 00     (zero dword placeholder)
```

**Wildcard operators for pattern matching:**
```
ALLWC            → ?? ?? ?? ??     (match any 4 bytes)
POS2WC           → 0x????          (match any 2 bytes at position)
POS3WC           → 0x??????        (match any 3 bytes at position)
POS4WC           → 0x????????      (match any 4 bytes at position)
NEG2WC           → -0x????         (match negative displacement, 2 bytes)
WC               → 0x?             (match 1 byte — short jump offset)
WCp              → 0x??            (match 2 bytes — for optional pattern variations)
```

### 4.2 Common Target Functions/Sites

| Virtual Address (07-16) | Function / Purpose |
|-------------------------|-------------------|
| 0x015E8198 | Packet buffer base |
| 0x00CAA2E0 | Packet dispatcher switch table |
| 0x00C9E1DD | Packet dispatch main loop return |
| 0x00CAA2B7 | Packet dispatch default handler |
| 0x015fb30c | Male hair palette table |
| 0x015fb318 | Female hair palette table |
| 0x00D5BB40 | GetJobSpriteIndex |
| 0x00D5A1F0 | GetJobNameByClassGender |
| 0x00D5A480 | GetJobName |

### 4.3 Known Magic Values (Shared Memory Blocks)

| Magic | ASCII | Block Purpose |
|-------|-------|---------------|
| 0x49434F4C | "ICOL" | Item color data block |
| 0x4558544E | "EXTN" | Extended name data block |

### 4.4 WARP-specific Section References

- `CODE` section: main executable code (.text section)
- `DIFF` section: WARP-added section for code caves and allocated data
- `D_Import`: PE Import Directory (for `SetDirAddr`/`SetDirSize`)
- `D_Text`: user-facing text input dialog type
- `D_InFile`: file path input dialog type
- `D_Hex`: hex value input dialog type

---

## 5. ARCHITECTURAL INSIGHTS

### 5.1 Evolution of Patch Patterns

**Generation 1 — Direct Address Patching (oldest):**
- Patches use hardcoded virtual addresses (no pattern scan)
- Fragile across client versions
- Example: some older patches with fixed addresses

**Generation 2 — Pattern-Scanned Patches (current standard):**
- Use `Exe.FindHex` with wildcards (ALLWC, POS2WC, etc.)
- Match across multiple compiler versions via wildcards
- The dominant pattern in the codebase

**Generation 3 — AutoHook with Fillers (advanced):**
- Code caves with automatic relocation resolution
- The `Filler`/`SwapFillers`/`SetFillTargets` system
- Handles address resolution automatically

**Generation 4 — Shared Infrastructure (newest):**
- CACHE-based multi-user coordination
- Reference-counted shared code caves
- Dispatcher-table based packet routing (avoids ws2_32.recv hooks)
- Manual machine code construction (avoids AutoHook relocation bugs)

### 5.2 Recurring Design Patterns

**Pattern 1: The "Find + Verify + Write" Triad**
```javascript
const addr = Exe.FindHex(pattern);  // Find
if (addr < 0) throw Error("...");   // Verify
Exe.SetHex(addr, replacement);      // Write
```
Used by ~80% of all patches. The SAFETY module adds `FindHexUnique` (throws on multiple
matches) and `SetHexSafe` (validates section boundaries) as drop-in replacements.

**Pattern 2: Langtype Bypass**
Many patches simply change conditional jumps after langtype/service-type comparisons
to unconditional jumps, enabling features on all langtypes:
```javascript
// Find: CMP [g_serviceType], 5; JZ skip
// Replace: JZ → JMP (skip the skip — always execute the feature code)
```

Used by: EnableWho, EnableShowName, AlwaysAscii, CallKoreaClientInfo, PlainTextDesc,
ReadTxtFile, AlwaysOfficialBG, ShowButton, OpenToServiceSelect, DeleteCharWithEmail,
NoHelpMsg, GuildBrackets, LoadKrExtSettings, and many more.

**Pattern 3: String Zeroing**
To prevent a file from loading, zero out its filename in the binary:
```javascript
// Find the PUSH reference to "filename.txt"
// Write 00 bytes over the filename string
```
Used by: NoSkillChatter, NoSwearFilter, NoBGMAudio, NoCameraLock, NoMapInfo,
DisableIndoorRSW.

**Pattern 4: User Input with GetUserInput**
```javascript
const value = Exe.GetUserInput('$varName', D_Text, "Title", "Prompt", defaultValue, options);
if (value === false) Cancel("No value specified");
```
Used by ~70 patches. The `$varName` persists in WARP settings. `D_Text`, `D_Hex`,
`D_InFile`, `D_Number` specify the input type.

**Pattern 5: The \_ (underscore) Logging Convention**
```javascript
const _ = `${patchName} (ModuleName)`;
$$(_, 1.1, `Doing step one`);
$$(_, 2.1, `Doing step two`);
```
The `_` variable serves as a hierarchical logger tag. `$$` writes to both the log file
and console. Convention: `<Section>.<Subsection>.<Step>` numbering.

### 5.3 Anti-Patterns and Gotchas

1. **AutoHook + Conditional Branches**: The 0xC8598E2C crash occurs when AutoHook
   relocates code containing Jcc instructions. The FpsOverlay patch's entire manual
   code cave approach exists to avoid this. New patches should prefer simple SetHex
   for small changes, or manual SetHex + SetJMP for complex caves.

2. **Import Table Race Condition**: If two patches both call `CustomDLL.applySpec`
   without `mergeSpec`, the second one silently drops the first one's DLLs.
   Always use `CustomDLL.applySpec` (not raw `GetImpTable` + `SetDirAddr`).

3. **Client Version Assumptions**: The `Exe.Version` property maps to compiler version
   (6=VC6, 9=VC9, 10=VC10, 11=VC11, 14=VC14.16/VC14.29), not client version.
   Patches that check `Exe.Version` without also checking `Exe.BuildDate` can
   misidentify clients.

4. **EF BB BF (UTF-8 BOM)**: QJS files with BOM cause load errors. All files must
   start with `/*`, not `EF BB BF`.

5. **LF vs CRLF**: Windows line endings are mandatory for .qjs files.

6. **new Date()**: Does not exist in QuickJS environment. Use `System.LocalTime.toISOString()`.

7. **Undefined Values**: Passing `undefined` to `Exe.FindHexN` crashes. Always normalize
   with `from ?? 0`, `to ?? Exe.FileSize`.

8. **BinFile is Read-Only**: Use `System.Copy()` and `System.Delete()` for file operations.

9. **console.error is Unconfirmed**: Use `console.warn` or `console.info` instead.

### 5.4 Patches That Push Boundaries

**CustomJobs.qjs (2,200+ lines)** — The most complex single patch:
- 11 phases of binary modification
- Direct Lua C API calls (bypasses broken CLua wrapper)
- Custom `cj_loadfile` function using client's CFile::Open for GRF-aware loading
- MSVC SSO (Small String Optimization) manipulation for std::string writes
- Entry-level function hooks that completely replace original logic
- Table capacity expansion with trampoline-based PUSH redirection
- Multiple coordinated hooks across 4+ distinct functions

**FpsOverlay.qjs** — Manual x86 code cave:
- Complete byte-level machine code construction
- Manual rel32 offset computation
- IAT-based indirect calls (CreateFileA, CloseHandle)
- Slash-command parsing with CMP+JNE chain
- Sentinel file IPC mechanism for DLL communication
- Avoids AutoHook to prevent the 0xC8598E2C crash

**CustomPacketDispatch.qjs** — Dispatcher table manipulation:
- Direct modification of the packet dispatcher switch table
- Template-based handler stub generation
- Shared memory blocks with magic-number validation
- Mirror mode for diagnostic packet copying (preserves stock handler)

**CustomDLL.qjs** — Complete PE import table rebuild:
- Parses existing import directory
- Constructs new tables with merged DLL specs
- Handles import by ordinal AND by name
- String table alignment (2-byte padding for odd-length names)
- CACHE-based dedup across multiple patch callers

---

## 6. PATCH CATEGORY SUMMARY

### Network (Network.yml)
- **Encryption**: CustomEncKeys (3 keys), DisableEncr (3 disable modes)
- **Connection**: NoNagle, EnableProxy, SendMD5Hash, SendClientFlags
- **HTTP**: EnableHttpEmblem, CustomMerchantURL

### Data (Data.yml)
- **Lua files**: CustomItemInfoLub, CustomAchieveLub, CustomMonSizeEffLub, etc. (~20 path overrides)
- **Protection**: NoGGuard, RestoreCpsDll
- **GRF**: MultiGRFs, DataFolderFirst
- **Quality**: IncrMapQuality, IncrViewID, No3DBoneLimit, EnableEffectTool
- **Text**: PlainTextDesc, TranslateClient, AlwaysAscii, MsgStrings, QuestDisplay
- **Misc**: CustomSSQuality, HideBuildInfo, NoCameraLock, NoMapInfo, FixArrowsCharset

### Client (Client.yml)
- **HP Bars**: ResizePlayerBar, ResizeMobBar (4 sub-patches)
- **Effects**: DisableEffect (3 sub-patches), RestoreSongsEffect
- **Slash Commands**: EnableSlashCmd (3 sub-patches)
- **Chat**: NoSkillChatter (2 sub-patches), ResizeBox (4 sub-patches), ChatRepeat (2 modes)
- **Shop**: CashShop (3 sub-patches), EquipPreview (3 sub-patches)
- **Camera**: IncrCamAngle (3 levels), IncrZoom (4 levels)
- **Login**: LoginMode (3 modes)
- **Sleep**: CustomSleep (2 sub-patches)

### UI (UI.yml)
- **Buttons**: ShowButton, ResButtonVis, RouletteVis, NewButtonVisibility, HideGameWindows
- **Fonts**: CustomFont (11 sub-patches), EnableCustomFonts, FixFontsCharset
- **Windows**: HideWorldView, HideItemba, HideProbabilityUI, DisableDoram, RestoreBattlegroundUI
- **Chat**: FixChatAt, GuildBrackets, NoSwearFilter, RestoreChatFocus, NoHourly
- **Search**: InsensitiveStorageSearch, InsensitiveShopSearch
- **NPC**: CloseCutinOnEsc, NpcDialogueScrolling, FixSelectMenuReset/Width/Height
- **Character**: CustomInventoryLimit, CustomVendingLimit, DeleteCharWithEmail
- **Display**: TildeForMatk, MoveUpItemCount, CustomFadeDelay, RelativeDelay4CharDel
- **Overlay**: FpsOverlay, PingOverlay, LoadGRFOnSlashCmd
- **Icons**: EnableFlagEmotes, EnableFlagAnimation, EnableNoticeMails
- **Fixes**: FixSkillbarReset, FixLatestNCWin, AllowShortcutsInWine
- **Special**: CustomBarterZenySep, CustomEnchantGradeLabels, ReduceExpensiveUIRender
- **Rune**: CustomRuneSystem

### Character (Character.yml)
- **Sprites**: OfficialPal, NoGMSprite, ShowBGEmblem, RestoreModelCulling, Intravision
- **Skills**: AllowSkillSpam, CustomQSDelay
- **Party**: AllowPL2Leave, AllowGuildInClan, CustomAutoFollow (2 modes)
- **Combat**: ShowGvGDamage
- **Aura**: CustomAuraSprites, CustomAuraLimits
- **Chat Color**: 6 chat color customization sub-patches
- **Cheat Check**: SkipInFriendList, SkipInGuildList
- **Walk**: NoWalkDelay, CustomWalkDelay

### Env (Env.yml)
- **Registry**: HKLMtoHKCU
- **Admin**: NoAdminNeeded, IgnoreDebugger
- **Window**: EnableSysMenu, UseMiniTitle, CustomWinTitle, BorderlessFSW
- **Launcher**: No1and1Arg, IgnoreAccArg
- **Multi-client**: NoMultiWindow
- **Resolution**: CustomMinResolution
- **Plugins**: LoadClientPlugins
- **Lighting**: DisableIndoorRSW
- **Icon**: RestoreIcon, CustomIcon
- **Priority**: Idle2NormalPriority, Normal2HighPriority

### Sound (Sound.yml)
- Enable44kHzAudio, AutoMute, NoBGMAudio

### Window (Window.yml) / Special (Special.yml)
- **Buttons**: HideNewButtons, ShowNewButtons
- **Char Create**: CustomNewCharNameHeight, IncrNewCharHairs, CustomCharCreateId, CustomCharCreateSecond
- **Doram**: NoDoramCreation
- **Friend/Party**: CustomPartyLimit, NoAdvAgencyInParty
- **Equip**: NoEquipSwap, NoEquipWinTitle, DisableEquipAttrButton
- **Exp Bars**: CustomBarLimits, ShowExpNumbers
- **Return**: DisConnToLogin, CancelToLogin
- **Show Button**: ShowReplayBtn, ShowCancelBtn, ShowRegisterBtn, SNSButtonURL, BookingButtonGuide
- **Name Limits**: NoCharnameLimit, NoUsernameLimit, NoPasswordLimit
- **License**: HideLicense, ShowLicense
- **Trait**: DisableTraitStatusButton, HideTraitStatusButton
- **Special**: CustomShields, CustomJobs, CustomHomuns, AddLuaOverrides, AllowAPBarforAllJobs, RemoveMaxNumbersLimit
- **Custom Skills**: CustomPlayerSkills, CustomHomunSkills, CustomMerceSkills
- **Packet Color/Name**: CustomExtName, CustomColoredItemName

---

## 7. QUICK REFERENCE: COMMON PATCH OPERATIONS

| What you want to do | Which patches to enable | Dependencies |
|--------------------|------------------------|--------------|
| English server basics | UseOldLogin, NoEncrForLC, NoPassEncr, MsgStrings, QuestDisplay, PlainTextDesc, CallKoreaClientInfo, LoadKrExtSettings, TranslateClient, AlwaysAscii, FixChatAt, GuildBrackets, NoHourly, NoHelpMsg, HideBuildInfo, CancelToLogin | CancelToLogin needs RestoreLoginWindow |
| Multiple GRFs | GRFsFromIni | None |
| Custom jobs | CustomJobs, IncrViewID | JobInfo Lua files required |
| Custom skills | CustomPlayerSkills | SkillInfo Lua files required |
| Custom items (colors) | CustomColoredItemName | No custom DLL; server 0x0BDD ICOL support required; ItemId-first `ICL2` records with exact ItemName fallback |
| Extended names and player colors | CustomExtName, CustomPlayerNameColor | No custom DLL; server 0x0BB7 EXTN support required |
| Colored enchant-grade item titles | CustomColoredItemName, CustomColoredEnchantGradeName | Server numeric `_GRADE_<n>_*` ICOL entries; conditional native endpoint gate makes grade color override the complete decorated title without cross-call state |
| Custom enchant-grade label words | CustomEnchantGradeLabels | `Inputs/enchant_grade.yml`; otherwise the renderer uses stock D/C/B/A |
| Rune system | CustomRuneSystem | No custom DLL; server sends one rune refresh per active set |
| FPS/Ping overlay | FpsOverlay, PingOverlay | No custom DLL; QJS-only post-Present renderer |
| Case-insensitive search | InsensitiveStorageSearch, InsensitiveShopSearch | CaseInsensitiveSearch shared module |
| Camera improvements | MediumCamAngle, Zoom75Percent | None |
| Packet encryption control | CustomFirstKey + CustomSecondKey + CustomThirdKey OR NoPacketEncr + NoEncrForLC | CustomKeys need NoEncrForLC |
| Disable protection | NoGGuard | None |
| Window improvements | EnableSysMenu, CustomWinTitle | None |
| Anti-lag | NoNagle, AllowSkillSpam, RestoreModelCulling | None |
| Custom fonts | CustomFontName + CustomFontHeight + FixFontsCharset | FixFontsCharset needed for non-Korean |
| Custom aura (server-driven) | CustomAura (EFID model) | AuraInfo.lub required |
| Custom aura (sprite only) | CustomAuraSprites | None |
| Extended hairstyles | Allow65kHairs / IncrHairs | Compatible with CustomJobs |
| No admin needed | HKLMtoHKCU, NoAdminNeeded | None |
| Battlegrounds | RestoreBattlegroundUI, ShowBGEmblem, ShowGvGDamage | None |
| Disable Doram | NoDoramCreation, DisableDoram | None |

---

## 8. FILE SIZE COMPLEXITY TIERS

| Tier | Lines | Patches |
|------|-------|---------|
| Massive (>1000) | 2,200 | CustomJobs.qjs |
| Very Large (500-1000) | ~800 | CustomSkills.qjs, FpsOverlay.qjs, CaseInsensitiveSearch.qjs |
| Large (300-500) | ~400 | IncrHairs.qjs, CustomEncKeys.qjs, CustomAura.qjs, CustomDLL.qjs, CustomPacketDispatch.qjs |
| Medium (150-300) | ~200 | CustomFont.qjs, MultiGRFs.qjs, CustomExpBars.qjs, EnableSlashCmd.qjs, CustomEnchantGradeLabels.qjs |
| Small (50-150) | ~100 | Most other patches |
| Tiny (<50) | ~30 | Simple hex patches (NoHelpMsg, AlwaysAscii, etc.) |
