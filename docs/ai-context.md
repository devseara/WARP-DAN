# rAthena AI Context — Banquet of Heroes

## Server
- **rAthena branch**: BanquetOfHeroes (custom fork)
- **Client date**: 2025-07-16
- **Packet version**: 20250716 (`src/custom/defines_pre.hpp`)
- **Build OS**: Windows
- **Compiler**: MSVC (Visual Studio, from `.pdb` and build artifacts)

## Important folders
- `src/map/` — Map server: `clif.cpp`, `script.cpp`, `atcommand.cpp`, `pc.cpp`
- `src/char/` — Char server
- `src/login/` — Login server
- `src/common/` — Shared code: `mmo.hpp`, `packets.hpp`
- `db/` — Item DB (`item_db_*.yml`), mob DB, skill DB
- `npc/` — NPC scripts
- `doc/` — Documentation, script commands, packet notation

## RE Notes
- **Client exe**: `2025-07-16_Ragexe_175220998_unpacked_clientinfo.exe`
- **Known packet obfuscation**: Disabled (`PACKET_OBFUSCATION` commented out in `src/config/packets.hpp`)
- **Tools**: Ghidra, IDA, x32dbg/x64dbg

### Stable Client Offsets (2025-07-16 Ragexe)

| Address | Function / Purpose | Notes |
|---------|-------------------|-------|
| `0x005470F0` | `SetTextColor` wrapper | `push [ebp+8]; push [ecx]; call [gdi32.SetTextColor]; ret 4`. Stable hook target. |
| `0x005470F8` | Direct `SetTextColor` caller | Not hover path |
| `0x00556B19` | Direct `SetTextColor` caller | Not hover path |
| `0x00556C3E` | Direct `SetTextColor` caller | Not hover path |
| `0x00DBA68A` | Direct `SetTextColor` caller | Not hover path |
| `0x00865230` | Item info panel builder (`FUN_00865230`) | `thiscall`; `0xd630a9` arg is style ptr for `FUN_008448b0`. Patching this directly crashes. |
| `0x008448b0` | Style/text renderer | Called by item info builder; not the hover tooltip path |
| `0x008A0C81` | Right-click context menu | Fires on right-click, NOT hover |
| `0x00547110` | Rich/colored text renderer | Calls `0x00547600` for segments; default segment color from `[EDI+0x14]` |
| `0x00547600` | Text segment renderer | **DO NOT hook by overwriting `[EBP+0x18]`** — crashes after char select (`0xC0000005` at `0xC8598E2C`) |
| `0x00A27A30` | Color push wrapper (called by 8 sites) | `[ebp+4]` is the correct way to read caller return address. `[esp+0x14]` reads saved `ebx` — WRONG. |

### Stable WARP Hooks (8 call sites to `0x005470F0` wrapper)

| Caller Address | Default Color | Notes |
|----------------|---------------|-------|
| `0x00A27882` | Red (`0x000000FF`) | Stable |
| `0x00A278D2` | Green (`0x0000FF00`) | Stable |
| `0x00A279A3` | Blue (`0x00FF0000`) | Stable |
| `0x00A279F3` | Yellow (`0x00FFFF00`) | Stable |
| `0x00A27AA9` | Magenta (`0x00FF00FF`) | **CRITICAL**: Hooks BOTH item hover name AND UI button tooltips. Unconditional write ONLY — conditional branches cause delayed crashes. |
| `0x00A27B0C` | Cyan (`0x0000FFFF`) | Stable |
| `0x00A27C8B` | Purple (`0x00800080`) | Stable |
| `0x00A27CAE` | Olive (`0x00808000`) | Stable |
| `0x00A27BDD` | Orange | **LEFT UNHOOKED** (Weight/Zeny display) |

### Critical Crash Knowledge

1. **CustomDLL is not globally forbidden anymore**: The old crash note came from a failed helper/HTTP/extended-name experiment, not a permanent rule. The final Rune System patch proved `CustomDLL.applySpec()` can safely add a normal startup-loaded DLL on the 2025-07-16 client when the DLL hooks stable local client/UI code. For packet/GDI features like extended names, the risk is duplicate hook ownership and packet desync, not CustomDLL itself.

2. **Conditional color at `0x00A27AA9` crashes**: Any conditional branch inside an `AutoHook` helper at this site causes delayed crashes (`0xC0000005` at `0xC8598E2C`). The unconditional `mov [esp+4], COLOR` pattern is proven stable. Root cause: `AutoHook` with `isCall:true` may perform relocations that assume a linear code path.

3. **Alternative for `0x00A27AA9`**: Hook the three CALL sites to `0x00A27A30` directly (`0x0082666A`, `0x009AA080`, `0x009AA178`) instead of hooking inside `0x00A27A30`. Each caller gets its own helper with a different color. This avoids conditional branching inside the helper.

## Current Extended Name Setup (2026-06-01)

This is the single supported extended-name setup going forward. We are dropping the runtime `ws2_32.recv` path to keep the client closer to the Rune System model and safer for Gepard-style restrictions.

- **Only WARP patch to select**: `CustomExtName`.
- **What `CustomExtName` does**: installs the static `RecvStrip0BB6` EXE patch, then adds a user-named visual DLL through `CustomDLL.applySpec()`, mirroring `CustomRuneSystem`.
- **No runtime recv**: Do not use `CustomExtNameVisualDLL` in profiles, and do not use `PacketSource=recv` for Banquet extnames.
- **Visual DLL role**: `boh_extname_visual.dll` owns GDI text substitution and reads the WARP `EXTN` shared block. It should not install a runtime `ws2_32.recv` hook.
- **Packet source config**: `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\ddraw_proxy.ini` uses:
  ```ini
  [CustomItemColors]
  PacketSource=shared
  DebugLog=0
  ```
- **Logging default**: DLL logging is intentionally quiet to prevent render-loop lag. Enable with `DebugLog=1` or `BOH_EXTNAME_VISUAL_LOG=1` only while debugging.
- **Server packet**: `0x0BB7` is a separate side packet with `packetLength` and `magic = 0x4558544E` (`EXTN`). Current packed size is 233 bytes.
- **Stock packet rule**: Official spawn/idle/walk packets must keep stock `NAME_LENGTH` 24-byte names. Do not expand those packets to `SPAWN_NAME_LENGTH` when custom extended names are enabled.
- **Feature gates**: `feature.custom_extended_name_packet: on` and `feature.custom_item_color_packet: on` send both custom side packets (`0x0BB7` extname + `0x0BB6` item colors) through the same static/shared client path.
- **Map-change result**: `@warp` / `@mapmove` works when custom packets are stripped before the stock parser sees them, `0x0BB7` has `packetLength + EXTN`, and official packets stay stock-sized.
- **Gepard-safe direction**: This is the Gepard-oriented path. It is not injector-style DLL injection; the visual DLL is a normal startup import.
- **Rune DLL safety note**: `CustomRuneSystem` uses a normal startup import with a user-selected DLL filename and local UI hooks. That is much closer to Gepard-safe than a runtime network hook. No WARP/DLL approach is guaranteed against Gepard integrity policy until tested, but the risky extname part was the runtime `ws2_32.recv` hook, not the CustomDLL import mechanism itself.
- **Static stub status**: `WARP0716-main/Scripts/Patches/RecvStrip0BB6.qjs` is the required transport underneath `CustomExtName` and was updated for the current 233-byte `0x0BB7` length+`EXTN` packet.
- **Log archive**: The noisy pre-quiet log is `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh_extname_visual.before-quiet-log.20260601-174445.log`.

## Current Color Patch Setup

| Component | Purpose | Location |
|-----------|---------|----------|
| WARP `CustomItemColors.qjs` | Sets magenta default at `0x00A27AA9` | `WARP0716-main/Scripts/Patches/` |
| `boh_extname_visual.dll` | Hooks GDI text APIs and reads `0x0BB7` data from WARP shared `EXTN` blocks; no runtime recv mode for Banquet extnames | `WARP0716-main/CustomItemColorsDLL/ddraw_proxy.cpp` |
| Server `db/item_color_db.yml` | Server database mapping item name substrings to colors | `BanquetOfHeroes/db/item_color_db.yml` |

### How it works
1. WARP patch hooks 8 call sites to `0x005470F0`. All but `0x00A27AA9` are NO-OP (jump to wrapper without changing color). `0x00A27AA9` forces magenta.
2. `ZC_ITEM_COLOR_LIST` (0x0BB6) is active on login and via `@itemcolorreload` under `feature.custom_item_color_packet: on`.
3. WARP `CustomExtName` strips `0x0BB7` in the EXE static recv path and writes the payload into the shared `EXTN` block. The DLL polls that block and never needs a runtime `ws2_32.recv` hook.
4. Parsed colors go into `g_colorMap`; parsed extended names go into `g_extNameMap` / `g_extPartyMap` / `g_extGuildMap` / `g_extPositionMap`.
5. GDI hooks (`TextOutW`, `ExtTextOutW`, `DrawTextW`, `DrawTextExW`) check if rendered text contains any substring from `g_colorMap`. If yes, `SetTextColor(hdc, customColor)` before the real API call.
6. The game draws text **twice**: once in black (`origColor=0x00000000`) as a shadow/outline, then again in white (`origColor=0x00FFFFFF`) as the main text. The DLL must **skip the shadow layer** to avoid bold/overlapping appearance.
7. **Draw order varies by UI context**:
   - Balloon tooltip: Shadow FIRST, Main SECOND → simple skip-black works
   - Equipment list: Main FIRST (via `TextOutW`), Shadow SECOND (via `ExtTextOutW`) → shadow would overwrite colored main if skipped
   - Description panel: Shadow FIRST, Main SECOND → simple skip-black works
   - **Fix**: Smart sequence tracking — if a text was colored in the current sequence, subsequent black calls for the same text are also colored (to prevent overwrite).

### Hot-Reload — Development Fallback

**File-based fallback**: If no `0x0BB6` packets have been received, the DLL can still load from `item_colors.txt` (not used in production). The DLL checks file modification time every ~60 frames. Press **F12** for manual reload.

**Packet-based (historical / if re-enabled)**: Colors arrive via `0x0BB6` from the server. Current live config has color packets off; extended names use the named DLL `recv()` path for `0x0BB7`.

### Hot-Reload — Debugging History (What We Learned)

1. **C++ exceptions in hook context are FATAL**: `std::ifstream`, `std::getline`, `std::stoul` all throw internally. When called from inside `HookTextOutW`, C++ exception unwinding fails because the caller (client) doesn't have our CRT's exception frame. Result: `0xe06d7363` crash.
   - **Lesson**: NEVER use C++ standard library I/O or string parsing inside a hooked Windows API. Use Win32 APIs only.

2. **`try/catch(...)` is not enough**: Even wrapping in C++ `try/catch` doesn't help because the exception unwinding itself is what crashes. The crash happens during stack unwinding, not during the throw.
   - **Lesson**: Use Win32-only code in hooks. No C++ exceptions possible = no crash.

3. **Map swap after successful load**: The old code did `g_colorMap.clear(); LoadColorMap();`. If `LoadColorMap` threw, the map was empty and all colors lost.
   - **Fix**: Load into a `newMap` first, then `g_colorMap = std::move(newMap)` only after successful parse.

4. **`GetAsyncKeyState & 1` is unreliable**: The transition bit gets consumed by other callers.
   - **Fix**: Use `& 0x8000` (currently pressed) with manual debounce.

### Known Limitations
- **Substring matching**: `"Knife"` also colors `"Combat Knife"`. Use short distinctive names (e.g., `"Angra"` instead of `"Angra Manyu"`).
- **Exact match doesn't work**: Game renders item names with extra formatting (slot counts, trailing spaces, or split across multiple `TextOutW` calls).
- **Server-side control exists**: Custom packet `0x0BB6` provides server-side color control. `@itemcolorreload` and `itemcolorreload()` script command broadcast updates to all online players.

### Text Rendering Detail — Shadow Layer

The game draws most text **twice per frame**:
1. **Shadow layer**: `origColor=0x00000000` (black), offset slightly — creates outline/shadow effect
2. **Main text layer**: `origColor=0x00FFFFFF` (white) or other intended color

**If the DLL colors the shadow layer too**, the shadow becomes the same color as the text, creating a **bold/overlapping/blobby** appearance.

**Fix (simple)**: Check `GetTextColor(hdc)` before applying custom color. Skip if `== 0x00000000` (black shadow).

**Problem**: Draw order varies by UI context:
- Balloon tooltip / description panel: Shadow FIRST, Main SECOND → skip-black works perfectly
- Equipment list / inventory rows: Main FIRST (via `TextOutW`), Shadow SECOND (via `ExtTextOutW`) → skipping the shadow leaves black text overwriting the colored main

**Fix (smart)**: Sequence tracking. When a text is colored, mark it. If a subsequent black call for the **same text** arrives in the same sequence, color it too (it's a shadow that would otherwise overwrite the main).

Confirmed in log:
```
[TO]  [Trident] origColor=0x00E0E0E0 matched=YES applied=YES  ← main via TextOutW, colored
[ETO] [Trident] origColor=0x00000000 matched=YES applied=YES  ← shadow via ExtTextOutW, smart-colored
```

## AI Assistant Notes

### Rune System Multi-Active UI Finding (2025-07-16 Client)

- The server can keep multiple Rune Sets active, but the official client equipped pane is single-slot.
- Client `CRuneSystemMgr + 0x14` is the one equipped Rune Set pointer. Getter `0x0072F140` is `mov eax, [ecx+0x14]; ret`.
- `UIEquipRuneSetWnd` render function `0x007E1610` calls `0x0072F140` and draws only one `bg_runeequip.bmp` panel. If the pointer is null it draws `bg_runeequip_empty.bmp`.
- `UIRuneSystemWnd` init/create function `0x007E0240` allocates exactly one `UIEquipRuneSetWnd` (`0x7c` bytes), stores it at `[this+0xC4]`, positions it at `(0x11B, 0x52)`, and sizes it once. The `UIEquipRuneSetWnd` vtable `0x0102312C` only has constructor/destructor/init refs plus this one parent allocation path.
- The multi-row Rune Set list renderer is `0x007E1CC0` (with related row helper `0x007E1B20`). It draws `bg_runeset_list.bmp` and each visible row with `list_runeset_item_%d_%d.bmp`, checking active state through `0x0072F1E0`. This is why the left/list area can represent multiple active sets, while the center equipped pane cannot stack them.
- Packet handler path for `ZC_REFRESH_ENABLE_RUNE2` uses `0x00730B40`, which writes that single pointer. Sending multiple active sets through this packet cycles the vanilla pointer, so a custom client cache is needed to remember every server-confirmed active set.
- `ZC_ONLOG_ENABLE_RUNE` marks individual Rune/Set state, but does not create multiple equipped panels by itself.
- Practical server behavior: send active Rune Set refreshes for each server-active set, and let the WARP visual stacking patch cache those refreshes. The vanilla pointer can still "last packet wins"; the extra panes read the custom cache.
- Experimental WARP patch added in `WARP0716-main/Scripts/Patches/RuneSetVisualStacking.qjs` with UI entry `RuneSystem -> Stack active Rune Sets visually`.
  - Hooks parent init at `0x007E0347` and creates two extra `UIEquipRuneSetWnd` children at `(0x11B, 0xA4)` and `(0x11B, 0xF6)`, below the original `(0x11B, 0x52)` pane. `bg_runeequip.bmp` is 283x82, so these Y offsets stack exactly.
  - Hooks `UIEquipRuneSetWnd` getter call sites `0x007E1646`, `0x007E4CEF`, and `0x007E4DA6`.
  - Original pane still returns the official `CRuneSystemMgr+0x14` pointer. Extra panes read custom cached active-set slots populated from the server refresh handler and skip the original pointer, so pane 2/3 show the other active sets.
  - Current cache wrapper hooks refresh call sites `0x00CF953F` and `0x00CF9591`, then calls the original helper `0x00730B40`.
  - Dry-run applied cleanly with `WARP_console.exe`; byte inspection confirmed init, refresh-wrapper, and getter hooks land correctly.

### What Works (Keep Doing This)
- **WARP `CustomExtName` + renameable visual DLL**: Current live extended-name path. WARP owns static packet stripping; the DLL owns visual substitution.
- **Packet-based extended-name delivery**: `0x0BB7` includes `packetLength + EXTN`, is intercepted by the static EXE recv patch, and is stripped before the stock client parser sees it.
- **Historical color hooks**: WARP can force magenta default at `0x00A27AA9`; DLL color override logic remains in the source, but live color packets are currently off.
- **Substring matching in DLL**: Use short distinctive names (e.g., `"Angra"` instead of `"Angra Manyu"`). First match wins.
- **Smart shadow detection**: Sequence tracking handles draw-order variation across UI contexts (equipment list shadows drawn after main text, balloon shadows drawn before).

### What Does NOT Work (Don't Try Again)
- **Duplicate GDI/recv hook DLLs**: Do not run a standalone `extname.dll`, `ddraw.dll` proxy, and/or static recv stub together. Only one module should own text rendering hooks and custom packet stripping; live owner is `boh_extname_visual.dll`.
- **Conditional branches in `AutoHook` at `0x00A27AA9`**: Any `cmp/je` that skips `mov [esp+4], COLOR` causes delayed crash at `0xC8598E2C`.
- **Hooking `0x00547600` by overwriting `[EBP+0x18]`**: Crashes after character select.
- **Exact name matching in DLL**: Game renders item names with extra formatting (slot counts, spaces, split `TextOutW` calls).
- **Direct color patch via `FUN_00865230` style pointer**: The `0xd630a9` arg is a style ptr, not a raw color. Overwriting it crashes.
- **Coloring the shadow layer**: The game draws text twice (black shadow + main text). Coloring both layers makes text look bold/overlapping. Must skip `origColor == 0x00000000`.
- **Not restoring `SetTextColor`**: Changing HDC color without restoring it leaks the custom color to subsequent text draws on the same HDC. Always `SetTextColor(hdc, oldColor)` after `TextOutW`.

### Server-Side Item Color Controller

Implemented server-side control via custom packet `ZC_ITEM_COLOR_LIST` (0x0BB6). Current live config keeps `feature.custom_item_color_packet: on`.

**Architecture:**
1. **`db/item_color_db.yml`** — Server database mapping item name substrings to colors
2. **`src/map/item_color.cpp`** — YAML DB loader (`YamlDatabase` subclass) + packet builder
3. **`src/map/packets.hpp`** — Packet struct definition:
   ```cpp
   struct PACKET_ZC_ITEM_COLOR_LIST {
       uint16 packetType;   // 0x0BB6
       uint16 packetLength;
       uint32 count;
       // entries: uint16 nameLen, char name[nameLen], uint32 color
   };
   ```
4. **Sent on login when feature is enabled** — `clif_item_color_list(sd)` called in `pc.cpp` after `clif_authok`
5. **`@itemcolorreload`** — atcommand (also accessible as `@reload itemcolordb`)
6. **`itemcolorreload()`** — script command

**Commands:**
- `@itemcolorreload` — Reloads DB and broadcasts `0x0BB6` to all online players
- `itemcolorreload()` — Same, callable from NPC scripts

**Client-side (implemented in visual DLL source, color path currently disabled):**
- `boh_extname_visual.dll` currently intercepts `0x0BB7` for extended names.
- `0x0BB6` color parsing remains in the source for future re-enable, but live server config keeps color packets off.
- No file writing is needed in the live extname path.

### Open Questions / Future Work
- **Item ID-based coloring**: Would require hooking earlier than `TextOutW` (e.g., inventory builder `FUN_00865230`) where item struct is still available.
- **Exact match fix**: Needs logging to see actual rendered strings, then normalization (strip `[N]`, trim spaces).

### File Reference
| File | Path |
|------|------|
| WARP patcher | `C:\Users\Administrator\Documents\GitHub\WARP0716-main` |
| WARP patch script | `WARP0716-main/Scripts/Patches/CustomItemColors.qjs` |
| WARP live profile | `WARP0716-main/profiles/2025-07-16 PROFILE MAIN.yml` |
| DLL source | `WARP0716-main/CustomItemColorsDLL/ddraw_proxy.cpp` |
| DLL build script | `WARP0716-main/CustomItemColorsDLL/build_extname_visual.bat` |
| DLL config sample | `WARP0716-main/CustomItemColorsDLL/ddraw_proxy.ini.sample` |
| Client color database | `WARP0716-main/CustomItemColorsDLL/item_colors.txt` |
| Server color database | `BanquetOfHeroes/db/item_color_db.yml` |
| Server color loader | `BanquetOfHeroes/src/map/item_color.cpp` |
| Server color header | `BanquetOfHeroes/src/map/item_color.hpp` |
| Server packet definition | `BanquetOfHeroes/src/map/packets.hpp` |
| Server packet config | `BanquetOfHeroes/src/custom/defines_pre.hpp` |
| Server packet structs | `BanquetOfHeroes/src/map/packets_struct.hpp` |
| Server item send logic | `BanquetOfHeroes/src/map/clif.cpp` (clif_additem, clif_item_equip) |

## Extended Name Packet (0x0BB7)

Custom server-to-client side packet that sends extended display names, guild, party, and position info alongside the standard 24-byte name packets (0x0A30/0x0ADF/etc.). WARP `CustomExtName` strips/parses `0x0BB7` in the static EXE recv path and writes it to the shared `EXTN` block; `boh_extname_visual.dll` then substitutes names during GDI text rendering.

### Packet Structure (`PACKET_ZC_EXT_NAME`)

```cpp
struct PACKET_ZC_EXT_NAME {
    uint16 packetType;           // 0x0BB7
    uint16 packetLength;         // sizeof(PACKET_ZC_EXT_NAME), currently 233
    uint32 magic;                // 0x4558544E ('EXTN')
    uint32 gid;
    char shortName[NAME_LENGTH];     // 24 bytes — truncated name (as sent in 0x0a30)
    char name[DISPLAY_NAME_LENGTH];  // 31 bytes — extended display name
    char party_name[DISPLAY_NAME_LENGTH];      // extended party name
    char guild_name[DISPLAY_NAME_LENGTH];      // extended guild name
    char position_name[DISPLAY_NAME_LENGTH];   // extended guild position name
    char party_name_short[NAME_LENGTH];
    char guild_name_short[NAME_LENGTH];
    char position_name_short[NAME_LENGTH];
    uint8 type;                  // 0=PC, 1=MOB, 2=NPC
} __attribute__((packed));       // Total: 233 bytes
```

`packetLength + EXTN` are required so the DLL can distinguish a real complete custom packet from partial TCP data during login/map changes. This is what fixed the old `@warp` / `@mapmove` stuck behavior together with keeping official packets stock-sized.

### Entity Type Handling

## Rune System Integration Notes (2026-05-31)

- Imported the base Rune System source into `BanquetOfHeroes` (DB YMLs, SQL upgrade, NPC script, map-server source hooks, packet structs/db registrations).
- Implemented multi-active Rune Set server logic:
  - `map_session_data::runeactivated_data` is now a vector (multiple active sets).
  - Added `feature.max_active_runesets` battle config knob (default `3`).
  - Rune bonus/status calculation loops all active runesets.
  - Rune UI login sync sends the first active set to the client while the server keeps all active sets.
- Added missing map-server lifecycle/save/load glue:
  - `do_init_rune()` / `do_final_rune()` in map startup/shutdown.
  - `rune_save(sd)` in `chrif_save`.
  - `rune_load(sd)` and `clif_onlogenable_rune(sd)` in player login flow.
- Added rune packet plumbing for 2023-08-02+ and reward packets for 2024-10-01+:
  - `clif_packetdb.hpp` registrations.
  - `packets_struct.hpp` packet definitions.
  - `clif.cpp` rune handlers (open UI, book/set info, activate, upgrade, enable/disable, decomposition, rewards).
- Added schema tables to `sql-files/main.sql`:
  - `runes`
  - `runes_book`

### Important behavior note
- Server now supports multiple active Rune Sets, but stock clients may still present a single-active UI. Client-side bypass/UX requires a dedicated executable patch (WARP/QJS) for the specific Ragexe build.
- WARP patch added in `WARP0716-main/Scripts/Patches/AllowMultipleRuneSets.qjs`.
  - WARP UI group: `RuneSystem` / patch: `AllowMultipleRuneSets`.
  - Target message: `MSI_RUNESYSTEM_EQUIP_PUTERR` (`0xFD4` on 2025-07-16 Ragexe).
  - Target branch: file offset `0x3E5CAC`, VA `0x007E68AC`; changes `JZ` (`0x74`) to `JMP` (`0xEB`) after `test eax,eax`, skipping the client-side "Please remove the equipped Rune Set." guard.
  - Verified with `win32/WARP_console.exe` temporary session; patched byte became `0xEB`.

| Type | `name` field | `party_name` | `guild_name` | `position_name` |
|------|-------------|--------------|--------------|-----------------|
| **PC (0)** | `display_name` | Party name | Guild name | Guild position / Clan name |
| **MOB (1)** | `display_name` | HP exact + % | Level + Race | Mob ID |
| **NPC (2)** | `display_name` | — | — | — |

### Mob Info (`showmobinfo` flags → packet fields)

| Bit | Info | Packet Field | Format |
|-----|------|-----------|--------|
| 1 | HP exact | `party_name` | `HP:1109/1109` |
| 2 | HP % | `party_name` | `100%` (appended to exact if both) |
| 4 | Mob ID | `position_name` | `#1052` |
| 8 | Level | `guild_name` | `Lv.24` |
| 32 | Race | `guild_name` | `Insect` (appended with ` | ` if level also) |

### Client-Side DLL Substitution

`boh_extname_visual.dll` reads `0x0BB7` data from the shared `EXTN` block populated by WARP `CustomExtName`, validates `packetLength + EXTN`, parses it, and builds a composite extended name:

- **Mobs**: `display_name + " | " + party_name + " | " + guild_name + " | " + position_name`
- **PCs**: `shortName + " " + display_name + " [" + party + "] {" + guild + "} (" + position + ")"`

Then it hooks `TextOutW`, `ExtTextOutW`, `DrawTextW`, `DrawTextExW` to substitute `shortName` with `composite` when rendering text.

**Anti-clipping measures:**
- `ExtTextOutW`: passes `NULL` for `pRect` when text is substituted
- `DrawTextW`/`DrawTextExW`: expands `RECT.right` by text width difference, clears clip region, removes ellipsis flags

### Server Functions

| Function | File | Purpose |
|----------|------|---------|
| `clif_extended_name()` | `src/map/clif.cpp:10863` | Main dispatcher; accepts `src` for per-player mob info |
| `clif_extended_name_pc()` | `src/map/clif.cpp:10906` | PC: display_name + party/guild/position |
| `clif_extended_name_mob()` | `src/map/clif.cpp:10941` | MOB: display_name + showmobinfo via helper |
| `clif_extended_name_mob_info()` | `src/map/clif.cpp:10863` | Builds HP/level/race/ID strings into packet |
| `clif_extended_name_npc()` | `src/map/clif.cpp:10965` | NPC: display_name only |

### Key Design Decisions

1. **`clif_spawn` skips BL_MOB**: Mob stats are viewer-specific (per `showmobinfo` flags). Sending in `clif_spawn` with `src=nullptr` would overwrite the rich packet sent by `clif_name`.

2. **Composite name in DLL, not server**: Server sends raw fields; DLL decides separator style (`" | "` for mobs, brackets for PCs). This keeps server protocol clean and allows client-side visual customization.

3. **`DISPLAY_NAME_LENGTH` (31) per field**: Each individual field is capped at 30 chars + null. The composite string has no hard limit — `std::wstring` grows as needed.

### Client-Side Implementations

**Current architecture (named visual DLL):**

| Approach | File | How |
|----------|------|-----|
| **CustomExtName + visual DLL** | `WARP0716-main/Scripts/Patches/CustomExtName.qjs` + `WARP0716-main/CustomItemColorsDLL/ddraw_proxy.cpp` | Single supported path. WARP installs static recv stripping and adds the renameable visual DLL as a startup import. The DLL polls shared `EXTN`; no runtime recv hook. |

**Historical approaches (superseded for extended names):**
- The old HTTP helper experiment failed because it did not safely own packet stripping and GDI substitution together. This does not mean named CustomDLL imports are bad; the live `boh_extname_visual.dll` path proves they are fine when there is one packet/GDI owner.
- The old `ddraw.dll` proxy/runtime recv architecture worked earlier, but is no longer the supported Banquet extname path.
- `CustomExtNameVisualDLL.qjs` is kept only as historical/debug code and should not be selected in profiles.

### File Reference

| File | Path |
|------|------|
| Server packet definition | `BanquetOfHeroes/src/map/packets.hpp` |
| Server `clif_extended_name` | `BanquetOfHeroes/src/map/clif.cpp` |
| Server `clif_extended_name` declaration | `BanquetOfHeroes/src/map/clif.hpp` |
| DLL source | `WARP0716-main/CustomItemColorsDLL/ddraw_proxy.cpp` |
| DLL build script | `WARP0716-main/CustomItemColorsDLL/build_extname_visual.bat` |
| DLL config sample | `WARP0716-main/CustomItemColorsDLL/ddraw_proxy.ini.sample` |
| WARP extname patch (only one to select) | `WARP0716-main/Scripts/Patches/CustomExtName.qjs` |
| WARP static recv helper | `WARP0716-main/Scripts/Patches/RecvStrip0BB6.qjs` |
| WARP live profile | `WARP0716-main/profiles/2025-07-16 PROFILE MAIN.yml` |

## Related Projects
- **WARP0716-main**: `C:\Users\Administrator\Documents\GitHub\WARP0716-main`
  - Client patcher for 2025-07-16 Ragexe
  - `CustomItemColorsDLL/` — source for `boh_extname_visual.dll`
  - `Scripts/Patches/CustomItemColors.qjs` — color WARP patch script
  - `Scripts/Patches/CustomExtName.qjs` — single supported extname patch; installs static recv helper and adds the renameable visual DLL
  - `Scripts/Patches/RecvStrip0BB6.qjs` — static recv helper used by `CustomExtName`
  - `profiles/2025-07-16 PROFILE MAIN.yml` — live profile (includes `CustomExtName` and `CustomRuneSystem`)

---

## Two-Client Setup

The user maintains **two client installations**:

| Client | Path | Gepard | Packet Interception | WARP Patches |
|--------|------|--------|---------------------|--------------|
| **Banquet client** | `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes` | Target-safe path | WARP static recv stub + shared `EXTN` block | `CustomExtName` + `CustomRuneSystem` |

### Current Working Setup

Use one path for both normal testing and Gepard-oriented builds: WARP `CustomExtName` installs static recv stripping in the EXE and adds the renameable visual DLL as a normal startup import. The DLL uses `PacketSource=shared` and polls `EXTN`; it does not hook runtime `ws2_32.recv`.

### Architecture

```
Server sends stock spawn/idle/walk packets + separate 0x0BB7 side packet
         |
WARP static recv patch receives TCP stream in EXE path
         |
Validates/fixes custom packet transport and writes complete 0x0BB7 to EXTN shared block
         |
Strips complete 0x0BB7 before stock client parser sees it
         |
Caches extended names by gid/shortName
         |
GDI hooks substitute stock short names with composite extended names
```

### Key Addresses (2025-07-16 Ragexe)

| Address | Purpose |
|---------|---------|
| `0x00FC17D4` | `ws2_32.recv` IAT entry |
| `0x015C5A18` | Cached `recv` function pointer global |
| `0x00C145BC` | Actual `recv` call site (`call eax` via cached pointer) |
| `0x00DBA7AA` | `recv` thunk (`jmp [0x00FC17D4]`) — exists but not directly called |

### Critical Risks — Prevention Checklist (Already Applied)

| # | Risk | Prevention |
|---|------|------------|
| 1 | **GDI Hook Collision** | Only one DLL hooks GDI/recv at a time. For the live no-Gepard client, that owner is `boh_extname_visual.dll`. |
| 2 | **Race Condition in `CheckSharedBlock()`** | `CRITICAL_SECTION g_sharedBlockCS` added around all shared block logic |
| 3 | **False Positive in `FindSharedBlock()`** | Separate magic DWORDs (`ICOL`/`EXTN`) + ready flag sanity check |
| 4 | **Buffer Overrun in `ParseExtNamePacket()`** | Validate `packetLength`, `EXTN` magic, and 233-byte struct size before parsing |
| 5 | **Packet Format Mismatch** | Current `0x0BB7` size is 233 bytes, not the old 227-byte layout |
| 6 | **Map Growth / Memory Bloat** | All maps capped at 5000 entries |

### File Reference (Optional/Future Gepard Plan)

| File | Path |
|------|------|
| WARP static recv patch script | `WARP0716-main/Scripts/Patches/RecvStrip0BB6.qjs` |
| Stub generator | `WARP0716-main/tools/generate_recv_stub.py` |

This is not the current no-Gepard Banquet client path.

## Failed Approach: Proxy DLL + HTTP Polling (2025-07-16 Client)

**Date**: May 2026

### What Was Attempted
Tried to replace the working `ddraw.dll` proxy + `recv()` hook architecture with:
1. A **renamable helper DLL** (`boh_client.dll`) containing GDI hooks + WinInet HTTP polling
2. A **proxy DLL** (`netapi32.dll` / `winmm.dll` / `ddraw.dll`) that loads the helper via `LoadLibraryW` and forwards system API exports
3. **WARP CustomDLL patch** to inject the helper into the IAT
4. **Server-side HTTP endpoints** (`/itemcolors/get`, `/extnames/get`) for dynamic color updates

### Why It Failed

#### 1. Old CustomDLL Helper Attempt
- The old helper attempt used CustomDLL to load a separate client helper during an HTTP/proxy experiment.
- The result was an unstable client, but the later Rune System patch proved the failure was not a blanket `CustomDLL` incompatibility.
- Current rule: `CustomDLL.applySpec()` is acceptable for a focused startup-loaded DLL with stable local hooks. For extended-name/custom-packet work, the client still needs a packet stripper and exactly one GDI hook owner.

#### 2. Proxy DLL Approach (`netapi32.dll`, `winmm.dll`, `ddraw.dll`)
After the old helper attempt failed, tried loading the helper via proxy DLLs:

| Proxy | Exports Needed | Outcome |
|-------|---------------|---------|
| `netapi32.dll` | `Netbios` only | Game imports `netapi32` but calls multiple exports (not just `Netbios`). Missing exports → "entry point not found" crashes. |
| `winmm.dll` | `timeGetTime`, `timeBeginPeriod`, etc. | Game imports `winmm` but calls `waveOutRestart`, `waveOutPrepareHeader`, etc. via `binkw32.dll`/`Mss32.dll` shims. Missing exports → "entry point not found" crashes. |
| `ddraw.dll` | `DirectDrawCreateEx`, `DirectDrawEnumerateExA` | Forwards both exports correctly and is the safest proxy surface because the game imports only these two exports. The old session could not isolate proxy behavior from the larger failed helper/HTTP experiment. |

**Key Lesson**: Proxy DLLs only work if you forward **EVERY export** the game (or any shim DLL) calls. Missing even one export causes immediate "entry point not found" fatal error. For system DLLs like `netapi32` (100+ exports) or `winmm` (150+ exports), this is impractical.

`ddraw.dll` is the safest because the game only imports 2 exports (`DirectDrawCreateEx`, `DirectDrawEnumerateExA`).

#### 3. HTTP Polling (WinInet)
- `boh_client.dll` implemented `InternetOpenW` → `InternetConnectW` → `HttpOpenRequestW` → `HttpSendRequestW` polling loop in a background thread.
- **Problem 1**: HTTP polling alone doesn't solve the **packet desync issue**. If the server sends custom packets and the client has no `recv()` stripper for them, the stock packet parser desyncs.
- **Problem 2**: Even with a proxy DLL loading a no-hooks helper (`ENABLE_HOOKS 0`), that experiment still produced a broken client. Could not isolate whether the helper, hooks, proxy path, or modified EXE state was at fault.

### Server-Side Mitigation Added

To make custom packets opt-in (so vanilla clients don't break), added a server-side flag:

| File | Change |
|------|--------|
| `src/map/pc.hpp` | `bool custom_packets_enabled` in `map_session_data::state` |
| `src/map/pc.cpp` | Initialized to `false` on player connect |
| `src/map/item_color.cpp` | `clif_item_color_list` returns early if flag is `false` |
| `src/map/clif.cpp` | `clif_extended_name` returns early if flag is `false` |
| `src/map/atcommand.cpp` | New `@custompackets [on\|off]` command toggles the flag |

Players with a custom client can type `@custompackets on` to receive `0x0BB6`/`0x0BB7`. Vanilla clients are unaffected.

Current live Banquet config uses feature gates instead: `feature.custom_extended_name_packet: on` and `feature.custom_item_color_packet: on`.

### Current Working Replacement (Confirmed 2026-06-01)

The live no-Gepard client no longer uses the old `ddraw.dll` proxy or static recv stub. It uses one named DLL owner:

| Component | Status | Notes |
|-----------|--------|-------|
| `boh_extname_visual.dll` | OK | Startup import added by `CustomExtName`; installs GDI hooks and polls shared `EXTN` |
| WARP static recv path | OK | Strips validated `0x0BB7` packets before the stock parser sees them |
| WARP `CustomExtName.qjs` patch | OK | Single supported patch; installs `RecvStrip0BB6` and adds the renameable visual DLL |
| Server `0x0BB7` packet | OK | Separate side packet with `packetLength + EXTN`; official packets stay stock-sized |

### Recommendations for Future Work

1. **For extended-name handling**: Use only WARP `CustomExtName`.
2. **For packet delivery**: WARP static patch (`RecvStrip0BB6.qjs`) writes custom packet data to a shared memory block; the visual DLL polls the shared memory block with no runtime `recv()` hook.
3. **HTTP polling is not viable** as a standalone solution because it doesn't solve the packet stripping problem. It could be used as a **secondary** update mechanism, but primary delivery must still be a custom packet with a stripper.
4. **Renamable DLL is now proven viable**. The live extname path uses `boh_extname_visual.dll`; safety depends on it being the single packet/GDI owner.
5. **Server-side `@custompackets` toggle is worth keeping**. It makes the server robust against vanilla clients connecting. Always default to `off`.

## Rune System Multi-Active Work Notes

**Date**: May 31, 2026

### Current Client Finding
- `RuneSetVisualStacking.qjs` was installed in the live 2025-07-16 client.
- The crash report after login pointed into `UIWindow::SetPos` at `0x00A1CBB3`, where the client calls virtual callbacks through the pane vtable.
- The WARP visual stacking patch was hardened to stop calling `UIWindow::SetPos` for extra rune panes. It now registers the extra panes, reasserts the `UIEquipRuneSetWnd` vtable, and writes the position/size fields directly from the original equipped pane.
- A WARP console dry-run against a test output succeeded, and the generated hook no longer calls `0x00A1CB70` for the extra panes.
- Follow-up crash while opening the Rune tab occurred at `0x007E1757` inside `UIEquipRuneSetWnd::Draw`: `mov eax, [ecx]` after `ecx = [pane+0x24]`.
- Root cause: avoiding `UIWindow::SetPos` left the pane's internal position object (`+0x24`) null. The draw code uses that object when drawing locked/disabled rune book overlays.
- Fix: `RuneSetVisualStacking.qjs` now calls `0x00560E50` directly to create the position object and stores it at `[pane+0x24]`, still avoiding the dangerous `SetPos` virtual callback chain.
- The live patched EXE was re-WARPed after backing up the previous file as `2025-07-16_Ragexe_175220998_clientinfo_patched.before-rune-posobj-fix.exe`.
- Follow-up UI issue: server logs confirmed both Rune Sets were active and `ZC_REFRESH_ENABLE_RUNE`/`ZC_ONLOG_ENABLE_RUNE` were sent, but the client UI still only trusted the vanilla single equipped pointer.
- Root cause: the previous extra-pane getter enumerated client Rune Set objects by `[set+0x0C]`, but that flag behaves like "set exists/activated/loaded", not "server says this set is equipped".
- Fix: `RuneSetVisualStacking.qjs` now wraps the two client refresh call sites at `0x00CF953F` and `0x00CF9591`, caches every server-confirmed active Rune Set pointer, and draws extra panes from that cache while skipping the vanilla pointer shown by the original pane.
- Verified WARP output: refresh call sites now target wrapper `0x0171FED1`, draw/tooltip getter call sites target cache-aware getter `0x01720018`.
- Live EXE was locked during replacement, so a side-by-side test binary was produced at `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\2025-07-16_Ragexe_175220998_clientinfo_patched_rune_cache.exe`. Backup of the locked live EXE was created as `2025-07-16_Ragexe_175220998_clientinfo_patched.before-rune-cache-fix.exe`.
- Added temporary client-side debug logging to `RuneSetVisualStacking.qjs`.
  - Log file path: `rune_visual_debug.log` in the client working directory.
  - Refresh logs capture `tag`, `set`, manager pointer, selected Rune Set pointer, basic set fields, book vector range, and cache slots.
  - Getter logs capture pane id, manager pointer, vanilla/original pointer, returned draw pointer, basic set fields, book vector range, and cache slots. Getter logging is capped at the first 200 calls to avoid unbounded file growth.
  - Side-by-side debug binary produced at `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\2025-07-16_Ragexe_175220998_clientinfo_patched_rune_debug.exe` because the live EXE was locked for writing.

### Current Server Finding
- Rune bonus scripts call `getupgrade_rune()`.
- The original helper always returned `sd->runeactivated_data[0].upgrade`, which is wrong for multi-active rune sets because every set after the first can read the first set's upgrade.
- Added per-script rune bonus context on `map_session_data`:
  - `rune_bonus_context`
  - `rune_bonus_tag`
  - `rune_bonus_set`
  - `rune_bonus_upgrade`
- `rune_active_bonus()` now sets that context around each active set's script before calling `run_script()`.
- `getupgrade_rune()` now returns the active context upgrade while a rune script is running, and falls back to the first active set only outside rune script context.

### Debug Added
- `rune_active_bonus()` now logs:
  - active set count, owned set count, and book count
  - each inspected active rune set
  - missing rune DB/set DB conditions
  - missing or empty scripts
  - applied scripts with tag, set, required amount, activated books, and upgrade
  - skipped scripts when not enough books are active
  - per-set applied/skipped summary

### Build Verification
- Normal map-server build compiled but could not overwrite `map-server.exe` because it was locked by the running server.
- A second build using a throwaway `OutDir` completed successfully with 0 warnings and 0 errors.

## Final Rune System Client Integration (2026-06-01)

### Final Working Architecture

- The final client solution is a single WARP patch plus a normal startup-loaded DLL.
- WARP patch:
  - Repository: `C:\Users\Administrator\Documents\GitHub\WARP0716-main`
  - Patch UI: `Rune System -> Custom Rune System`
  - Script: `Scripts/Patches/CustomRuneSystem.qjs`
  - Main profile: `profiles\2025-07-16 PROFILE MAIN.yml` includes `CustomRuneSystem` and `$runeVisualDLLName = boh_rune_visual.dll`.
  - `LastSession.yml` is restored to the live client target and also includes `CustomRuneSystem`, so new GUI/console builds should add the real DLL import without manual repair.
  - It replaces the older separate `AllowMultipleRuneSets`, `RuneSetVisualStacking`, and `RuneSetVisualTracer` patch entries.
- DLL:
  - Source: `WARP0716-main/RuneVisualDLL/boh_rune_visual.cpp`
  - Build script: `WARP0716-main/RuneVisualDLL/build.bat`
  - Export required by the import table: `RuneVisualInit`
  - Runtime log: `rune_visual_plugin.log` beside the client executable.

### What The Single WARP Patch Does

1. Skips the stock client guard that shows `MSI_RUNESYSTEM_EQUIP_PUTERR` / "Please remove the equipped Rune Set."
   - 2025-07-16 Ragexe branch: file offset `0x3E5CAC`, VA `0x007E68AC`
   - Patch changes the guard branch from `JZ` to `JMP` so equip requests reach the server.
2. Prompts for the Rune visual DLL filename.
   - Default filename: `boh_rune_visual.dll`
   - Filename is configurable so the DLL can be renamed at patch time.
3. Reuses `CustomDLL.applySpec()` internally to add that DLL to the PE import table.
   - If `CustomRuneSystem` runs by itself, it can add the Rune visual DLL through the shared `CustomDLL.applySpec()` helper.
   - In the current Banquet profiles, generic `CustomDLL` is also selected for `cps.dll`, so `Inputs/DLLSpec.yml` must include both `cps.dll` and `boh_rune_visual.dll`.
   - The DLL is loaded by the Windows loader during normal process startup, not injected after launch.

### CustomDLL Import Merge Fix

- Important: the live Banquet client also needs `cps.dll` for encrypted GRF/data access. Do not remove or overwrite that import.
- A bug was found where multiple patches using the CustomDLL import-table builder could clobber each other:
  - Generic `CustomDLL` adds `cps.dll`.
  - `CustomRuneSystem` adds `boh_rune_visual.dll`.
  - Before the fix, whichever CustomDLL consumer ran last could overwrite the earlier import request.
- Fix in `WARP0716-main/Scripts/Patches/CustomDLL.qjs`:
  - `CustomDLL.applySpec()` now calls `CustomDLL.mergeSpec()`.
  - `CustomDLL.mergeSpec()` keeps one cumulative DLL spec for the WARP run.
  - DLL names are merged case-insensitively, and function imports are merged by name or ordinal.
- Verification after the fix:
  - `profiles/2025-07-16 PROFILE MAIN.yml` and `LastSession.yml` include both `CustomDLL` and `CustomRuneSystem`.
  - The real player-facing target is `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\Banquet of Heroes.exe`.
  - Do not use `2025-07-16_Ragexe_175220998_clientinfo_patched.exe` as the final target unless the launcher/player workflow is intentionally changed to launch that file.
  - The visible tracked profile `WARP0716-main/profiles/20250716.yml` was updated to the same working target/options so normal WARP profile patching does not depend on the ignored local profile name.
  - `WARP0716-main/.gitignore` now unignores `profiles/2025-07-16 PROFILE MAIN.yml` so GitHub Desktop can show it.
  - `WARP0716-main/Inputs/DLLSpec.yml` must include both `cps.dll` and `boh_rune_visual.dll`. The generic `CustomDLL` pass can become the final import-table write, so this spec is the safest source of truth for preserving GRF encryption and adding Rune visuals.
  - `$runeVisualDLLName` is `boh_rune_visual.dll` exactly. Avoid the old typo `boh_run_visual.dll`.
  - A validation build and the live EXE both had real PE imports for `cps.dll` and `boh_rune_visual.dll`.
  - Re-running `win32/WARP_console.exe -using "profiles/2025-07-16 PROFILE MAIN.yml"` also preserved both imports, so future builds from the main profile should not need manual repair.
  - Re-running `win32/WARP_console.exe -using "profiles/20250716.yml"` also preserved both imports after `Inputs/DLLSpec.yml` was updated, so the visible GitHub Desktop profile is safe for normal patching.
  - The 2025-07-16 Rune equip guard bytes were verified as `EB 20 6A 00`.
- Live backup made before replacing the fixed client:
  - `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\2025-07-16_Ragexe_175220998_clientinfo_patched.before-cps-rune-import-20260601-094323.exe`

### Current Patching Checklist

- Open GitHub Desktop on `C:\Users\Administrator\Documents\GitHub\WARP0716-main` when reviewing WARP profile changes.
- Normal visible profile to use: `profiles/20250716.yml`.
- Optional explicit main profile: `profiles/2025-07-16 PROFILE MAIN.yml`.
- Both profiles should output to `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\Banquet of Heroes.exe`.
- `Inputs/DLLSpec.yml` must keep:
  - `cps.dll` with `compress` and ordinal `1`.
  - `boh_rune_visual.dll` with `RuneVisualInit`.
- After patching, verify the target EXE imports both DLLs. If only `cps.dll` is present, Rune visuals will not load.

### What The DLL Does

- Hooks only local Rune UI/client functions for the 2025-07-16 client.
- Does not hook `recv`, `ws2_32`, or packet network APIs.
- Does not use `CreateRemoteThread`, manual mapping, or runtime DLL injection.
- Caches server-confirmed active Rune Sets from the existing client Rune refresh path.
- Resizes the official equipped Rune Set pane and stacks active Rune Sets visually.
- Makes hover, middle preview, and the bottom Equip/Unequip button row-aware.
- Confirmed final behavior:
  - Multiple active Rune Sets stack visually in the equipped pane.
  - Hover/click on each equipped row updates the middle preview to the correct Rune Set.
  - Active rows show `Unequip`; inactive list rows show `Equip`.

### Key DLL Hook Addresses (2025-07-16 Ragexe)

| Address | Purpose |
|---------|---------|
| `0x00CF953F` | Rune refresh call site 1 |
| `0x00CF9591` | Rune refresh call site 2 |
| `0x007E1610` | `UIEquipRuneSetWnd::Draw` |
| `0x00A1D260` | Image draw hook used for row Y offset |
| `0x00A25A70` | Text draw hook used for row Y offset |
| `0x007E4B70` | Equipped pane click handler |
| `0x007E4CC0` | Equipped pane tooltip/hover handler |
| `0x007E69D6` | Middle preview equipped-set getter call |
| `0x007E5C12` | Button update equipped-set getter call 1 |
| `0x007E5E47` | Button update equipped-set getter call 2 |
| `0x007E5E56` | Button update equipped-set getter call 3 |

### Gepard / Anti-Cheat Notes

- This Rune System solution is the cleanest current approach for Gepard-style restrictions because it does not use a runtime `recv` hook and does not inject a DLL into an already-running process.
- The DLL is a visible, normal import-table DLL loaded by Windows at process startup.
- It is not "DLL injection" in the common anti-cheat sense of `CreateRemoteThread + LoadLibrary`, manual mapping, or hiding a module.
- Honest caveat: no assistant can guarantee Gepard will never flag it. If Gepard validates executable hashes, modified code bytes, PE import tables, or unknown DLL filenames, it may still block the patched client or DLL.
- Correct operational approach is to whitelist/sign/allow the patched client and Rune visual DLL with the server's Gepard configuration rather than trying to hide or bypass the anti-cheat.

### Cleanup Notes

- Obsolete experimental WARP scripts were removed from the final patch list:
  - `AllowMultipleRuneSets.qjs`
  - `RuneSetVisualStacking.qjs`
  - `RuneSetVisualTracer.qjs`
- The old `Inputs/RuneVisualDLLSpec.yml` is no longer required because `CustomRuneSystem.qjs` prompts for the DLL filename directly.
- Build scratch files (`RuneVisualDLL/build/`, `.obj`, checkpoints, `_rune_disasm/`) are not part of the final clean source.

## Extended Name Final Working State (2026-06-01)

- `@warp` / `@mapmove` is confirmed working with `feature.custom_extended_name_packet: on`.
- Single supported client path is WARP `CustomExtName` -> static `RecvStrip0BB6` EXE patch + renameable visual DLL import.
- `CustomExtNameVisualDLL` should not be selected in profiles anymore; it was the runtime recv experiment path.
- Use `PacketSource=shared`, never runtime `PacketSource=recv`, for Banquet extnames.
- The same path handles both custom packets: `0x0BB6` item colors and `0x0BB7` extended names.
- `boh_extname_visual.dll` owns GDI substitution and reads `0x0BB7` data from the WARP `EXTN` shared block. It should not install a runtime `recv` hook in the supported setup.
- Official spawn/idle/walk packets stay stock 24-byte names. Never expand official packet name fields to extended sizes as a shortcut.
- DLL logs are intentionally quiet by default (`DebugLog=0`) to avoid render-loop lag. Enable only for debugging.
- Current copied artifacts:
  - `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\Banquet of Heroes.exe`
  - `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh_extname_visual.dll`
  - `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\ddraw_proxy.ini`
  - `C:\Users\Administrator\Documents\GitHub\BanquetOfHeroes\map-server.exe`

---

## Gepard Owner Guidance - Custom DLL / WARP Static Patch Audit (2026-06-03)

### Reason for this note
The Gepard owner specifically said the client recv/read code around the screenshot must not be patched because Gepard Shield uses it. The old Banquet wording called the WARP `RecvStrip0BB6` path "Gepard-safe," but that was too strong. Correct wording is: no runtime `ws2_32.recv` hook, but still a static EXE patch in the recv/read path. Do not call it Gepard-safe unless the Gepard owner approves that exact region.

### Current rule
- Do not use runtime `ws2_32.recv` hooks.
- Do not rely on DLL injection into an already-running process.
- A normal startup import DLL such as `boh.dll` is cleaner than injection, but it still needs allow-list/sign/approval if Gepard checks import tables or unknown DLL names.
- Static EXE patches also need approval. The safer direction is to move custom packet interception away from the recv/read call-site and into packet-dispatch table entries that the stock client already reaches after reading a complete packet.

### Sensitive / old recv-strip path
Old helper: `WARP0716-main/Scripts/Patches/RecvStrip0BB6.qjs`

What it does:
- Resolves `ws2_32.recv` from the IAT.
- Finds the cached recv function pointer used by the client connection object.
- Patches recv call-site loads to route through an allocated stub.
- The stub copies `0x0BB6` item colors into `ICOL` and `0x0BB7` extended names into `EXTN`, then strips those packets from the TCP buffer.

Conclusion:
- This avoids a runtime recv hook, but it still modifies the static recv/read path. Treat it as legacy and not Gepard-approved.

### Packet dispatcher region found in the 2025-07-16 client
Read-only reverse engineering of:
`C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\Banquet of Heroes.exe`

Dispatcher core:
```text
00C9E1EA: call 00C147D0        ; read complete packet into global packet buffer
00C9E20C: call 00C144B0        ; get packet id
00C9E29C: movsx eax, word ptr [ebp - 0x44c0]
00C9E2A3: add eax, -0x73
00C9E2A6: cmp eax, 0xBC2
00C9E2B1: jmp dword ptr [eax*4 + 00CAA2E0]
```

Important constants:
```text
Packet buffer:      015E8198
Switch table base:  00CAA2E0
Packet id range:    0073..0C35
Default handler:    00CAA2B7
Main loop return:   00C9E1DD
```

Known dispatch table entries:
```text
0x01F3 -> table 00CAA8E0 -> handler 00CA64A0
0x0A3B -> table 00CACA00 -> handler 00CA904A
0x0B0D -> table 00CACD48 -> handler 00CA9AE7
0x0BB6 -> table 00CACFEC -> default 00CAA2B7
0x0BB7 -> table 00CACFF0 -> default 00CAA2B7
0x0BDD -> table 00CAD088 -> default 00CAA2B7, variable length metadata
```

Packet length reader:
```text
00C147D0 reads packet id, calls metadata lookup 00AA7B00.
If metadata returns type=1, length is fixed from metadata.
If metadata returns type=0, length is variable and taken from packet bytes 2..3.
```

Metadata registration examples found by scanning calls to `00A9FF30`:
```text
0x0BB6: args [1, 0x12, 0x12, 0x0BB6] -> fixed 18 bytes
0x0BB7: args [1, 0x5E, -1, 0x0BB7]  -> variable length, min 0x5E
0x0BDD: args [0, 0x04, -1, 0x0BDD]  -> variable length, min 4
```

### Recommended custom packet path for approval
Ask the Gepard owner whether this region is acceptable instead of recv:

1. Patch dispatcher table entry only, not the recv/read call-site.
2. Keep `0x0BB7` for extended names because the client already registers it as variable-length and default-unhandled.
3. Move item colors away from `0x0BB6`, because the client registers `0x0BB6` as fixed 18 bytes while Banquet sends a variable list.
4. Use a default/unhandled variable-length id such as `0x0BDD` for item colors, then update the server header to match.
5. Allocated WARP stubs copy validated packets from the complete packet buffer `015E8198` into `EXTN` / `ICOL` shared blocks, then jump back to `00C9E1DD` without calling the default unknown-packet flush path.

This is still an EXE patch, but it is not a recv hook and not the recv/read path shown in the Gepard warning screenshot. It should be submitted as an explicit candidate region for approval, not represented as guaranteed safe.

### Server impact if item colors move to 0x0BDD
Current server item color packet:
```text
BanquetOfHeroes/src/map/packets.hpp
DEFINE_PACKET_HEADER(ZC_ITEM_COLOR_LIST, 0x0bb6)
```

Current format is variable-length:
```text
uint16 packetType;
uint16 packetLength;
uint32 count;
entries: uint16 nameLen, char name[nameLen], uint32 color
```

Because stock `0x0BB6` is fixed 18 bytes in the client metadata, dispatcher-level handling should either:
- change item colors to a variable default packet id such as `0x0BDD`, or
- redesign item colors as one fixed 18-byte packet per item if `0x0BB6` must be kept.

The cleaner route is `0x0BDD`.

### Extended names
Current server extended-name side packet is compatible with dispatcher-level handling:
```text
BanquetOfHeroes/src/map/packets.hpp
DEFINE_PACKET_HEADER(ZC_EXT_NAME, 0x0bb7)
```

`0x0BB7` is variable-length in client metadata and currently default-unhandled in the dispatcher table. Candidate table patch:
```text
0x0BB7 table entry: 00CACFF0 -> custom EXTN shared-block handler
```

### Item colors
Current `boh.dll` GDI layer can already read the `ICOL` shared block. Transport should change from recv-strip to dispatcher-table copy.

Candidate table patch:
```text
0x0BDD table entry: 00CAD088 -> custom ICOL shared-block handler
```

Server change needed:
```text
DEFINE_PACKET_HEADER(ZC_ITEM_COLOR_LIST, 0x0bdd)
```

### Rune system
Rune is a different risk profile from extname/item-color recv stripping.

WARP patch:
```text
WARP0716-main/Scripts/Patches/CustomRuneSystem.qjs
```

EXE-side guard found in live patched client:
```text
007E68AA: test eax, eax
007E68AC: jmp 007E68CE      ; originally short JZ, patched to JMP
007E68C4: push 0x0FD4       ; MSI_RUNESYSTEM_EQUIP_PUTERR branch
```

Meaning:
- This is not the recv/read path.
- It is a small Rune UI/gameplay guard change so the equip request can continue.
- `CustomRuneSystem` also adds `boh.dll` as a normal startup import through the WARP CustomDLL import-table builder.

Runtime note for `boh.dll` rune visuals:
- `RuneVisualInit` is the startup import export.
- Source contains optional runtime UI hooks/call patches around these addresses:
  - `00CF953F`, `00CF9591` rune refresh call hooks
  - `007E1610` equip pane draw
  - `00A1D260` image draw
  - `00A25A70` text draw
  - `007E4B70` equip pane click
  - `007E4CC0` tooltip
  - `007E69D6`, `007E5C12`, `007E5E47`, `007E5E56` selected-equipped getter calls
- These are UI/render hooks, not network recv hooks, but they still need Gepard owner approval if enabled.

### Hat effects
The original flags-`0x05` STR carrier/depth-bias experiments and the type-0 aura
host are retired. The flags-`0x0D` queue oracle also failed live.
`AllHatEffectsWorldDepthOracle.qjs` v4.2 is the current test-only option-2 oracle:
it preserves original HatEffect STR objects and their screen-space sizing, but
replaces the screen renderer's constant normalized Z with native world-derived
depth. V4 keeps floor-side vertices on the minimally biased v3 anchor plane and
reconstructs upright world depth for upper vertices.

Known static patch points:
```text
0x0A3B dispatch call: 00CA9051 -> wrapper
Special-effect switch table: 00AFBB00, low EFID 700..991 entries -> Lua HatEffectInfo resolver
Special-effect parser: 00D059A0
Remove-effect parser: 00D00090
```

Status:
- The rejected prototypes were static EXE patches, not recv hooks or DLL injection.
- Stock SpecialEffect `0x925`, a HatEffect STR rehosted in that carrier, and the original flags-`0x05` HatEffect primitive with native `-0.01f` depth bias all leaked through the same opaque RSW wall.
- The type-0 SpecialEffect-200 aura host had no STR binder. Its apparent ring-suppressed result used stale `[EBP+8]`, so `B026F0` was never actually suppressed and the visible aura did not validate the substituted children. Authoritative parent-`+0x04` and corrected-matrix revisions produced no HatEffect; that architecture is rejected.
- `0x0054B9B0` builds only an intermediate scale transform. Native `0x00B02E60` combines rotation and scale through `0x0054C320`, so the custom direct-final-matrix inference was unsupported.
- Lua HatEffect runtime IDs are `0x98A + HatEFID`. The rejected queue hook at `0x00AECE35` changed only loaded primitive flags `0x05 -> 0x0D`; the user's 2026-07-14 capture still shows Flutter Butterfly across opaque geometry. Its patch/profile/catalog wiring was removed.
- Level-99 SpecialEffect `200` allocates type-0 aura primitives with flags `0x0D` and renders them through `0x00ADA090`, which runs `0x00554380` projection and `0x00554040` depth conversion for each 32-byte vertex. Its live capture clips at the same opaque wall, so the decisive difference is vertex generation rather than queue selection.
- Generic HatEffect render methods call type-2 loop `0x00AD8750` at `0x00AFE41C` and `0x00AFE52B`. Its layer builder `0x00AD8C40` manually creates screen-space vertices and hardcodes normalized `z = 0x38021CC8` at `0x00AD93C5`, explaining why original HatEffects render in front of RSW depth.
- Native loop `0x00AD86D0` is calling-convention and lifecycle compatible with `0x00AD8750`, but dispatches layers to world builder `0x00AD87D0`. That path retains STR texture/UV/color/blend data and invokes projection `0x00554380` plus depth conversion `0x00554040`.
- The 2026-07-14 live world-builder result partially clips Flutter Butterfly behind an opaque tower, proving the depth path. It also enlarges every STR because screen-authored pixel dimensions become world units, so redirecting the complete layer builder is rejected.
- `0x005541B0`, called by the original screen builder at `0x00AD8D91`, already returns actor reciprocal depth in `[EBP-0x64]`; the builder stores it in vertex `+0x0C` while independently forcing vertex `+0x08` to the constant near Z.
- The v2 oracle leaves X/Y, screen scale, animation, texture, UV, color, blend, and submission on `0x00AD8750`. Its two HatEffect calls enter a scoped wrapper; only inside that scope, the `0x00AD93D4` hook converts the existing reciprocal depth with `0x00554040` and writes normalized vertex Z. Other screen-STR users retain the original path.
- Full embedded-GRF artifact `hateffect_all_screen_size_depth_v2_oracle_full.exe` hashes to `6FCC5112CB6FB546AF0D98B949814803BB0630AA7B0B5BAD3BA3B852F66158DB`. Wrapper `0x0181F854` and depth bridge `0x0181F880` disassemble correctly; the audit reports 11 custom imports and zero stale bridge operands.
- The v2 live capture passed partial building clipping and stock size, but distant zoom caused lower STR layers to be occluded by the floor. The cause is the screen builder's `layerIndex * 1e-5` subtraction at `0x00AD9308/0x00AD93D9`: v2 converted the layer-shifted RHW into normalized Z, unlike the stock renderer's one shared constant Z plane.
- V3 preserves `anchor - layerBias` in vertex RHW `+0x0C`, reloads the unshifted reciprocal actor anchor for vertex Z, adds the native `1e-5` quantum at `0x00FD6AE4`, and converts it through `0x00554040`. Native world-effect builder `0x00ADBE7D` positively applies the same quantum to depth ordering.
- Isolated v3 artifact `hateffect_all_screen_size_depth_v3_oracle_smoke.exe` hashes to `3B2319C25855A3005C6B1179DD51850B2F325C5718244EFD7F8EC51289750345`. Full embedded-GRF artifact `hateffect_all_screen_size_depth_v3_oracle_full.exe` hashes to `E5A0C10919AF6A306D104E6BE1E540B334D6934BFC5F64C8C3616864B29185BD`; wrapper `0x0181F854`, bridge `0x0181F880`, native conversion call and both continuations disassemble correctly. The audit reports 11 custom imports and zero stale bridge operands.
- The v3 live result fixes zoom-dependent floor clipping and preserves stock size/general wall occlusion, but a wall immediately beside the actor can still consume most upper HatEffect pixels because all vertices share the actor anchor's depth.
- V4 leaves vertices at/below projected anchor Y on the v3 plane. For upper vertices it computes `rhw' = rhw * (m8*(y-cy)-m7*sy)/(m8*(anchorY-cy)-m7*sy)`, the algebraic inverse of native `0x005541B0` projection along world Z, then calls `0x00554040`. It deliberately leaves vertex RHW and all screen/texture fields stock to avoid scale or interpolation changes. A native absolute mask and `1e-5` comparison guard the denominator and fall back to the anchor plane if it is degenerate.
- Full v4 artifact `hateffect_upright_depth_v4_oracle_full.exe` (`37E0DB339C62CB287F555E92519C082BDB7E076EDB3BA92EBD63FC4154302ADF`) is rejected. It crashes on login at `0x0181F8F1` with `ECX=0` because `0x0181F8EE` loaded the matrix from reused compiler local `[EBP-0x38]`.
- V4.1 uses stable original argument `[EBP+0x10]`, the same matrix pointer copied by stock `0x00AD8C63/0x00AD8C6A` and passed to `0x005541B0`. Isolated artifact `hateffect_upright_depth_v4_1_oracle_smoke.exe` hashes to `A30CF40A41A9EC9293F837C529E6C93114BFC7835964C30C37BF768FC8E75547`. Full embedded-GRF artifact `hateffect_upright_depth_v4_1_oracle_full.exe` hashes to `2A9F52582AE694978116B3CEBB19F1020EB9C03067DA004DA8E47B8420EFA552`; the corrected matrix load is at `0x0181F8EE`, and the audit reports 11 custom imports with zero stale bridge operands.
- V4.1 is stable live but does not improve near-wall over-occlusion. Native world `.str` NPCs exhibit the same behavior, proving this is a world-STR depth characteristic rather than a HatEffect attachment/lifecycle defect. The v4.1 inverse projection also selected Z-axis coefficients; Ragnarok elevation is the second/Y coordinate.
- V4.2 uses matrix `+0x10` screen-Y and `+0x14` depth coefficients for Y-up inverse projection. Both ground and upper paths receive a four-quantum `3.9999999e-5` reciprocal-depth contact tolerance, deliberately bounded far below the stock constant-near-Z renderer. The patch remains scoped to the two HatEffect render calls and does not alter native world `.str` NPCs.
- Isolated v4.2 artifact `hateffect_yup_contact_depth_v4_2_oracle_smoke.exe` hashes to `C1C66360DB0092FFAAE210500855C90AFB3826059CD100D4D7EFF197506DA2C8`. Full embedded-GRF artifact `hateffect_yup_contact_depth_v4_2_oracle_full.exe` hashes to `7D055E5531DDC4B5F66D7ADF6632C7C9317E00A1ED0772EB0480EDA2A60C049A`; the full bridge, contact data, stable matrix load, Y-up coefficients, guards, native conversion and continuations disassemble correctly. The audit reports 11 custom imports and zero stale bridge operands.
- V4.2 passed live acceptance on 2026-07-14: true behind-wall partial clipping, stock apparent size, no floor loss at zoom extremes, and no excessive upper-effect loss while touching walls, buildings, or obstacles.

### Single DLL direction
Preferred deployment shape if approved:
```text
boh.dll
  - ExtNameVisualInit
  - RuneVisualInit
  - shared ICOL/EXTN polling
  - GDI text hooks for item color + extended names
  - optional Rune UI hooks
```

Keep one DLL owner instead of separate `boh_extname_visual.dll` and `boh_rune_visual.dll`. It is a normal startup import, not an injected DLL, but still must be allowed by anti-cheat policy.

### Short owner-facing question draft
"We were told not to patch the recv/read code path around the Gepard-used region. We found an alternate client packet-dispatch table at `00CAA2E0` after the client has already read a complete packet. Can we patch only default/unhandled dispatcher table entries (`0x0BB7` at `00CACFF0`, and item color moved to variable id `0x0BDD` at `00CAD088`) to copy custom packet payloads into shared blocks, while leaving the recv/read call-site untouched? Rune uses a separate UI guard at `007E68AC` plus a normal startup import `boh.dll`; can that be allow-listed too?"

---

## Dispatcher Transport Implementation Update (2026-06-03)

### Status
Implemented the first WARP dispatcher-table transport attempt for Banquet custom packets. This supersedes the legacy `RecvStrip0BB6` transport for the active `CustomExtName` patch.

### WARP changes
- New helper: `WARP0716-main/Scripts/Patches/CustomPacketDispatch.qjs`.
- `CustomExtName.qjs` now calls `CustomPacketDispatch.install()` instead of `RecvStrip0BB6.install()`.
- `CustomExtName` still adds the renameable startup import DLL, default `boh.dll`, via the existing `CustomDLL.applySpec()` flow.
- `Patches/Special.yml` now labels this as dispatcher transport, not Gepard-safe and not legacy static recv.

### Client dispatcher behavior
The original dispatcher dry run used two 74-byte handlers plus two 4096-byte
single-slot blocks:
```text
0x0BDD -> ICOL shared block
0x0BB7 -> EXTN shared block
```

As of 2026-06-15, ICOL remains a 4096-byte single slot, while EXTN allocates a
72-byte handler plus a 32,784-byte ring block (`16 + 128 * 256`). The historical
addresses below only document the first transport validation; regenerated
clients use newly allocated addresses.

Dry-run output verification from `Outputs/dispatcher_transport_test.exe`:
```text
packet 0BDD: table 00CAD088 -> 0171FBE0
packet 0BB7: table 00CACFF0 -> 0171FC60
packet 0BB6: table 00CACFEC -> 00CAA2B7  ; left stock/default
ICOL block: 0171FCE0 magic=49434F4C ready=0 length=0
EXTN block: 01720CE0 magic=4558544E ready=0 length=0
```

Handler logic:
```text
validate packet id
read variable packet length from packet bytes 2..3
ICOL: require min length and max 4092, copy to payload, set length and ready=1
EXTN: require 233..252 bytes, copy to slot (writeSequence & 127), then publish
      by incrementing writeSequence
jump back to packet loop at 00C9E1DD
```

### Item color packet ID change
Server item colors were moved from `0x0BB6` to server->client `0x0BDD` because this client's receive metadata registers `0x0BB6` as fixed 18 bytes. `0x0BDD` is default/unhandled on the client receive dispatcher and variable-length in client metadata.

Server updates:
```text
BanquetOfHeroes/src/map/packets.hpp
DEFINE_PACKET_HEADER(ZC_ITEM_COLOR_LIST, 0x0bdd)
```

The DLL accepts both the new and old IDs for compatibility:
```text
ITEM_COLOR_PACKET_ID        = 0x0BDD
ITEM_COLOR_PACKET_ID_LEGACY = 0x0BB6
```

### Built artifacts / validation
- WARP console dry run succeeded:
  ```text
  win32\WARP_console.exe -using LastSession.yml -to Outputs\dispatcher_transport_test.exe
  ```
- YAML validation passed for `Patches/Special.yml`, `profiles/2025-07-16 PROFILE MAIN.yml`, and `profiles/20250716.yml`.
- QJS syntax check passed by copying `.qjs` to temporary `.js` files and running `node --check`.
- Combined `boh.dll` rebuilt successfully from `CustomDLL/CustomItemColorsDLL/build_extname_visual.bat`.
- Server compile was not run because `MSBuild`/`vswhere` was not available on PATH/discoverable from this shell.

### Important caveats
- This is still a static EXE patch and still needs Gepard owner approval if we want to call it safe. It does not patch the recv/read call-site and does not install a runtime `ws2_32.recv` hook.
- `0x0BDD` is present in rAthena's client->server packet database as `clif_parse_guild_alliance_message`, but direction is separate. Our use is server->client, and the 2025-07-16 client receive dispatcher has no handler for it.
- Do not enable the old `RecvStrip0BB6` helper together with `CustomPacketDispatch`.

### Build/Deploy Follow-up (2026-06-03)
After the initial note above, full solution build succeeded with Visual Studio 18 MSBuild:
```text
MSBuild rAthena.sln /p:Configuration=Release /p:Platform=x64 /m
Build succeeded. 0 warnings, 0 errors.
```

Rebuilt server artifact:
```text
C:\Users\Administrator\Documents\GitHub\BanquetOfHeroes\map-server.exe
LastWriteTime: 2026-06-03 21:29
```

Prepared client-side test artifacts without overwriting the live EXE:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\Banquet of Heroes_dispatcher_transport.exe
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\Banquet of Heroes_dispatcher_transport.exe.secure.txt
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\Banquet of Heroes_dispatcher_transport.epi
```

Updated live shared DLL because the new parser must accept `0x0BDD`:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.dll
```

Backup made before overwriting the DLL:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.before-dispatcher.20260603-212948.dll
```

### Live EXE Follow-up (2026-06-03)
Because the rebuilt map-server now sends item colors as `0x0BDD`, the old live EXE would no longer be paired correctly while `feature.custom_item_color_packet: on`. The dispatcher build was copied over the live EXE after making a backup.

Live client now updated:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\Banquet of Heroes.exe
```

Backup before overwrite:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\Banquet of Heroes.before-dispatcher.20260603-213101.exe
```

A separate named test copy also remains:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\Banquet of Heroes_dispatcher_transport.exe
```

### WARP Dispatcher Split Cleanup (2026-06-05)
The Gepard owner approved the dispatcher-table region used for the custom packet transport. Current WARP direction:
- Keep `CustomPacketDispatch.qjs` as the shared static dispatcher-table helper.
- Split the UI into separate selectable patches:
  - `CustomExtName` installs only `0x0BB7 -> EXTN`.
  - `CustomColoredItemName` installs only `0x0BDD -> ICOL`.
- Both patches may add the same normal startup import for the shared visual DLL, recommended `boh.dll`, using `ExtNameVisualInit`. `CustomDLL.mergeSpec` deduplicates the import when both patches are selected.
- Do not use runtime `ws2_32.recv` hooks, DLL injection, or the legacy `RecvStrip0BB6` recv/read-path patch for these features.
- `0x0BB6` should remain stock/default in the dispatcher table; item colors use server->client `0x0BDD`.

### BOH visual DLL fix (2026-06-05)
After splitting `CustomExtName` and `CustomColoredItemName`, the WARP dispatcher can allocate `ICOL` and `EXTN` shared blocks independently instead of adjacent. The live `boh.dll` must not require `EXTN - ICOL == 4096` anymore. Updated `CustomDLL/CustomItemColorsDLL/ddraw_proxy.cpp` so shared mode accepts either/both blocks and stores the probes independently.

Also disabled custom item-color application on `DrawTextW`/`DrawTextExW`, and only allows item color on unclipped `ExtTextOutW`. This keeps hover/balloon text colored while avoiding the item-description title/shadow overlap artifact.

Deployed rebuilt combined DLL to:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.dll
```
Backup made:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.before-independent-shared.20260605-114649.dll
```

### Item description color filter follow-up (2026-06-05)
Item colors were still appearing on the item-description title because the title can use plain `TextOutW`/unclipped `ExtTextOutW`, not only `DrawTextW`/`DrawTextExW`. Added a region-based item-description detector in `CustomDLL/CustomItemColorsDLL/ddraw_proxy.cpp`: when marker text such as `Item Description`, `Item Collection`, `Item Stat`, `Item ID:`, `Compound on:`, or `Weight:` is seen, nearby item-description panel coordinates are treated as stock-only for item color. Shop list and hover/balloon text remain eligible for color outside that region.

Built new combined `boh.dll`. Live replacement was blocked because the patched client process had the DLL loaded, so a pending DLL was staged and a hidden watcher was started to swap it after the client closes:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.pending-item-desc-filter.dll
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh_swap_item_desc_filter.20260605-115307.log
```

### Item color render debug logging (2026-06-05)
Added budgeted render decision logs to `CustomDLL/CustomItemColorsDLL/ddraw_proxy.cpp` for the item-description overlap issue. Logs emit `[ICOLOR:TextOutW]`, `[ICOLOR:ExtTextOutW]`, `[ICOLOR:DrawTextW]`, `[ICOLOR:DrawTextExW]`, and `[IDESC]` marker lines with hook/action, coordinates, rect, current text color, shadow flag, item-description-region flag, matched item name, target item color, and text preview.

Deployed debug build to live game folder and enabled:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.dll
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\ddraw_proxy.ini
```
Current diagnostic INI:
```ini
[CustomItemColors]
PacketSource=shared
DebugLog=1
```
Old `boh_extname_visual.log` was rotated if present. Ask user to reproduce once, close client, then inspect/send:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh_extname_visual.log
```

### Item description overlap root cause (2026-06-05)
Render debug showed the item-description title overlap was caused by item-color late-shadow recoloring, not by packet transport or DrawText. Example from the trace:
```text
[ICOLOR:TextOutW] action=color ... xy=91,11 ... text="Andre Card"
[ICOLOR:ExtTextOutW] action=color ... xy=91,11 ... text="Andre Card"
[ICOLOR:TextOutW] action=skip-shadow ... xy=90,10 ... text="Andre Card"
[ICOLOR:ExtTextOutW] action=color-late-shadow ... xy=90,10 ... text="Andre Card"
```
The colored late shadow produced the duplicate/overlapping colored letters. Body markers like `[Item Collection]`, `Compound on:`, `Weight:`, and `Item ID:` were on a different HDC from the title, so HDC/region filtering was unreliable for the title.

Fix applied: removed late-shadow recoloring from item-color hooks. This keeps the normal black shadow pass and colors only the main text. Rebuilt and deployed:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.dll
```
Debug logging returned to off:
```ini
[CustomItemColors]
PacketSource=shared
DebugLog=0
```
Rotated debug trace:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh_extname_visual.before-no-late-shadow.20260605-120357.log
```

### Item description title skip (2026-06-05)
After removing colored late-shadow, the detail title still showed a black offset shadow because the main title itself was still being custom-colored. Added `LooksLikeItemDescriptionTitle(...)` to skip item-coloring when text exactly matches the colored item name and is drawn in the detail-title local coordinate slot observed in traces (`x=80..180`, `y=0..24`, no rect). Wired this into `TextOutW` and `ExtTextOutW` so shop rows and hover labels remain colored while item-detail title rendering is left to stock.

Deployed rebuilt DLL:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.dll
```
Debug remains off in:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\ddraw_proxy.ini
```
Backup made with prefix:
```text
boh.before-desc-title-skip.*.dll
```

### TextOut/ExtTextOut double-color root fix (2026-06-05)
Screenshot after late-shadow removal showed item detail title stayed black and shop/list text still looked overlapped. Root hypothesis: `TextOutW` internally calls `ExtTextOutW`, and both hooks were applying item-color logic to the same draw. Added `g_textOutPassthroughDepth` TLS guard. When `HookTextOutW` calls original `TextOutW` or manually calls `ExtTextOutW` for substituted text, nested `HookExtTextOutW` now calls the original ExtTextOutW directly and skips all color/substitution logic. Also restored detail-title color eligibility by removing the previous title-coordinate skip from the active path.

Built new `boh.dll`; live client had DLL locked, so staged pending file and watcher:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.pending-textout-guard.dll
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh_swap_textout_guard.20260605-121446.log
```
After the user closes the running patched client, watcher should copy pending DLL over live `boh.dll` and write success/failure to that log.

### Black shadow suppression for colored item names (2026-06-05)
User wanted the black shadow/duplicate removed, not merely changed from colored to black. Applied explicit suppression in `HookTextOutW` and `HookExtTextOutW`: when text matches a custom item color and the current GDI color is a shadow/black layer, the hook returns success without calling the original draw. Main colored text still renders normally. This should remove black overlap in shop rows and item-detail title while preserving colored names.

Deployed rebuilt DLL:
```text
C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.dll
```
Backup:
```text
boh.before-shadow-suppress.20260605-121842.dll
```
Debug remains off:
```ini
[CustomItemColors]
PacketSource=shared
DebugLog=0
```

### Final item-color rendering behavior (2026-06-05)
Confirmed by user as finally working after black shadow suppression. Final behavior for `boh.dll` item colors:
- Keep `TextOutW` -> `ExtTextOutW` reentrancy guard (`g_textOutPassthroughDepth`) so nested `ExtTextOutW` does not double-apply item-color logic when `TextOutW` internally draws through it.
- Do not use the previous detail-title coordinate skip as the primary fix; the title should remain color-eligible.
- Suppress black/shadow draws for custom-colored item names in both `HookTextOutW` and `HookExtTextOutW` by returning success without calling the original draw when `customColor != CLR_INVALID && isShadowLayer`.
- Main colored text still renders; black duplicate/shadow overlap is removed in shop rows and item description title.
- Runtime packet source remains shared-only, no recv hook:
  ```ini
  [CustomItemColors]
  PacketSource=shared
  DebugLog=0
  ```
- Final deployed DLL:
  ```text
  C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.dll
  ```
- Cleanup target after success: remove obsolete `boh.before-*`, `boh.pending-*`, `boh_extname_visual.before-*`, and `boh_swap_*` artifacts from the game folder, keeping only active `boh.dll` and `ddraw_proxy.ini`.

### BOH visual DLL cleanup completed (2026-06-05)
Final confirmed working state after item-color black/shadow suppression:
- Active combined normal-startup DLL is `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\boh.dll`.
- Active config is `C:\Users\Administrator\Documents\Ragnarok\Banquet of Heroes\ddraw_proxy.ini` with `PacketSource=shared` and `DebugLog=0`.
- Obsolete game-folder artifacts were removed: `boh.before-*`, `boh.pending-*`, `boh_extname_visual.before-*`, `boh_swap_*`, and related temporary BOH visual logs.

## Skill Tree FPS Fix — repaint-on-change gate (2026-07-17)

**Validated source**: [Bourgeon Skill Tree RE at `a96c403`](https://github.com/Stingor/Bourgeon/blob/a96c4037c1fe227281400084b1f34f2695441c29/docs/skill_tree_re.md) and its [implemented gate](https://github.com/Stingor/Bourgeon/blob/a96c4037c1fe227281400084b1f34f2695441c29/src/plugins/skill_tree_tweaks.cc).

**Measured root cause**: `UINewSkillListWnd::DrawContent` (`0x00977E80`) rebuilds the entire immediate-mode Skill Tree render-node list every frame. On a full modern tab, external live timing measured approximately 9–15 ms per call. The grid loop (`0x00975730`) repeatedly creates texture keys, looks up cached textures, and calls `GetSkillInfoAt` (`0x00976230`), which linearly re-walks and copies a skill node for each node already being iterated. That makes the hot path O(n²) plus repeated allocation/cache-lock churn.

**Local 2025-07-16 EXE proof** (`SHA-256 EAD7C0A316BC6C27705A5A6876DAF5093ABEC31677F3C1AF7525C1709B201BFF`):

| Evidence | VA / bytes | Meaning |
|---|---|---|
| `UINewSkillListWnd` vtable slot `+0x50` | `0x0103F6B0 = 0x00977E80` | The sole absolute reference to DrawContent; the gate can be scoped to this one class. |
| Render-node clear | `0x00977EBE: E8 6D 4C 0A 00` | Returning before the original function preserves the previous frame's nodes. |
| Compact/list body | call `0x009750D0` at `0x00978160` | Both view modes are handled by the same DrawContent. |
| Modern/grid body | call `0x00975730` at `0x00978280` | The measured expensive grid path. |
| Avatar body | call `0x00974700` at `0x00978287` | Preserved; external live removal recovered no FPS. |
| Dirty clear | `0x0097828C: C6 86 71 02 00 00 00` | The original paint consumes `this+0x271`. |
| Dirty producers | `0x009785C1`, `0x009786D2`, `0x009787D6`, `0x00978E9A`, `0x0097950E` | Skill action, hover, scroll/relayout, and view-toggle paths request a repaint. |
| Skill-point source | `0x015FB9FC` | Read by the native skill rebuild/render path and watched by the gate. |

**Implemented fix**: `Scripts/Patches/ReduceExpensiveUIRender.qjs` allocates a 36-byte snapshot and a static x86 code cave, then changes only vtable slot `0x0103F6B0`. The wrapper calls the untouched original DrawContent on first use or when any render input changes: object identity, native dirty byte, width, height, hovered skill, active tab, scroll row, point availability, or current skill-point level. An unchanged frame returns before the native render-node clear, so retained geometry stays visible without rebuilding the grid.

The wrapper is a build-time EXE patch, not a DLL/runtime patcher. It preserves nonvolatile `ESI`, calls the original `__thiscall` with `ECX=this`, snapshots post-paint state, and fails closed during patching unless the verified vtable and DrawContent contract bytes match.

**Removed misdiagnosis**: the animated class avatar is real per-frame work but was measured as negligible. The production patch now restores the original `UIDisplayCharacter::Draw` prologue and avatar-frame calculation rather than disabling previews globally or forcing frame zero. It also retains the prior recovery guards for experimental RealDraw `ret`, factory `AddChild` NOPs, and level-text skips.

**Runtime acceptance gate**: open a full modern Skill Tree tab, confirm idle FPS returns to the client cap, then verify hover, wheel scroll, tab changes, view toggle, level-up/reserved points, resize, close/reopen, avatar-at-interaction, icons, names, and level labels all repaint correctly. This live render/FPS check remains required because static analysis proves control flow and state coverage, not presentation timing on the target machine.

## 2026-06-07 FPS/Ping Overlay — Working Architecture

### Overview
Added an in-game FPS + frame-time overlay via WARP patch + startup-loaded DLL. The overlay renders as a layered GDI window (not D3D) in the top-right corner. No `ws2_32.recv` hook — Gepard-safe design.

### Components
| File | Purpose |
|------|---------|
| `WARP0716-main/Scripts/Patches/FpsPingOverlay.qjs` | Adds `fps_ping_overlay.dll` as startup import via `CustomDLL.applySpec()` |
| `WARP0716-main/Scripts/Patches/FpsPingOverlaySlashCmd.qjs` | Hooks `GetNoParamTalkType` suffix to intercept `/fps` and `/ping` |
| `WARP0716-main/CustomDLL/FpsPingOverlay/fps_ping_overlay.cpp` | DLL: layered GDI overlay, D3D9 vtable hook for FPS counting, QPC frame timing |
| `WARP0716-main/Inputs/DLLSpec.yml` | Must include `fps_ping_overlay.dll` with export `FpsPingOverlayInit` |

### Architecture
- **IPC**: Sentinel files — `/fps` creates `fps_overlay.toggle`, `/ping` creates `ping_overlay.toggle`. DLL polls (50ms) and atomically opens+deletes via `FILE_FLAG_DELETE_ON_CLOSE`.
- **Code cave**: Hooks `GetNoParamTalkType` at TT_UNKNOWN suffix. Uses CMP BYTE PTR + JNE for character checks. All IAT calls use indirect `CALL([iat])` (FF 15) — NEVER direct CALL to IAT entry.
- **EnableUnknCmds compatibility**: Unmatched path emits `XOR EAX,EAX; ADD tgtReg,1` (matching EnableUnknCmds suffix). Matched paths emit `ADD tgtReg,2` (caller DEC→non-zero→OR→-1 suppresses chat pass-through).
- **Separate toggles**: `/fps` toggles FPS line only, `/ping` toggles frame-time (MS) line only. F12 toggles both.
- **Frame timing**: Uses `QueryPerformanceCounter` for sub-millisecond precision. The "MS" label shows frame render time (~16.7ms at 60 FPS), NOT network ping (no `recv` hook).

### Critical Crash Knowledge
1. **`0xC8598E2C`** — Conditional branches in AutoHook code caves cause delayed crashes. Fix: hardcode all code paths (no if/else choosing different byte sequences).
2. **`0x00FC1238`** — Direct CALL to IAT entry (E8) crashes on DEP-enabled systems. Fix: use indirect `CALL([iat])` (FF 15).
3. **`0x017225F1`** — Replacing CALL with JMP changes stack layout (no return address pushed). Fix: use suffix hook, not call-site hook.
4. **DWORD vs BYTE** — `XOR(EAX, [EDI])` reads 4 bytes, not 1. Use `CMP(BYTE_PTR, [EDI], imm)` for byte comparisons.

### Profile Requirements
- `EnableUnknCmds` must be applied BEFORE `FpsOverlay` / `PingOverlay` (positions 276, 337, 338)
- `CustomDLL` patch must be active for DLL import
- `Inputs/DLLSpec.yml` must list `boh.dll` with `FpsPingOverlayInit` export

### Working State (2026-06-07 FINAL)
- **No AutoHook**: Cave built with manual byte encoding + `Exe.SetHex` + `Exe.SetJMP`. All JNE/JE/JMP offsets computed as `targetVA - (caveVir + offset + 4)`.
- **No conditional byte emission**: All code paths emit the same instruction sequence (unconditional).
- **Indirect IAT calls**: `CALL([CreateFileA])` and `CALL([CloseHandle])` use `FF 15` (not `E8`).
- **Sign-extension fix**: `PUSH 0x80` must use `imm32` (`68 80 00 00 00`), not `imm8` (`6A 80`), because `0x80` sign-extends to `0xFFFFFF80`.
- **`ADD tgtReg,2`**: Matched commands suppress chat pass-through (caller DEC→non-zero→OR→-1).
- **`ADD tgtReg,1`**: Unmatched commands follow EnableUnknCmds behavior.
- **DLL merged into `boh.dll`**: `FpsPingOverlayInit` export, compiled with `/DDllMain=FpsOverlayDllMain`, called from `ddraw_proxy.cpp` DllMain.
- **Separate toggles**: `/fps` → `fps_overlay.toggle` (toggles FPS line), `/ping` → `ping_overlay.toggle` (toggles frame-time line).
- **Frame time, not ping**: "MS" shows frame render time (~16.7ms at 60 FPS). True network ping requires ICMP or packet-dispatcher-based RTT measurement (not yet implemented).

### Files (FINAL)
| File | Purpose |
|------|---------|
| `Scripts/Patches/FpsOverlay.qjs` | DLL loader + full slash-command cave (standalone) |
| `Scripts/Patches/PingOverlay.qjs` | Thin wrapper → delegates to `FpsOverlay.installSlashCmd` |
| `CustomDLL/build.bat` | Combined `boh.dll` build (ddraw_proxy + boh_rune_visual + fps_ping_overlay) |
| `CustomDLL/FpsPingOverlay/fps_ping_overlay.cpp` | Overlay rendering + sentinel polling |
| `Inputs/DLLSpec.yml` | `boh.dll` with `ExtNameVisualInit`, `RuneVisualInit`, `FpsPingOverlayInit` |

# RO Global Zero Inventory — AI Context

**2026-07-12 update:** the DLL-backed Option A implementation documented below
has been superseded by a pure-QJS static implementation in
`Scripts/Patches/ROGlobalZeroInventory.qjs`. It retains the native texture,
surface, hit-test, coordinate-conversion, and tooltip calls, but emits the
handlers directly into EXE caves. It also anchors renewal balloons beside the
four vertical tabs and draws `uirenewal/itemui/bg_zeny.bmp` immediately before
the native bottom text block. A follow-up reserves one full item row and
overpaints its native empty-slot textures while leaving the window's painted
row count unchanged. The reservation stays white normally and switches to the
sampled `itemwin_mid_lock` background `#DEE7FF` only when Personal tab index 3
and native lock flag `0x01600553` are active. `FillRect` takes COLORREF byte
order, so that rendered RGB value is encoded as `0x00FFE7DE`. It reads the same live globals as Basic Information: Zeny
`0x015FBA90`, maximum weight `0x015FBA9C`, and current weight `0x015FBAA0`.
Hovering the weight row uses the stock `Weight %d%%` tooltip format. The older
DLL notes remain as reverse-engineering history. Zeny, current weight, and
maximum weight use the native bounded number formatter at `0x00A94870`, with
weight composed afterward as `"%s / %s"`.

**Goal:** Replace inventory text labels ("Use"/"Eqp"/"Etc"/"Fav") with BMP images
(`tab_pri_01-04.bmp`, 21×134px) from the ROZ Global UI renewal system.

**Target:** 2025-07-16 Ragexe client  
**Status:** IMPLEMENTED (Option A, 2026-06-14) — DLL overlay via inventory `vtable[20]` hook; compiles + exports clean. Needs one live tuning pass for tab strip X/Y.  
**Last updated:** 2026-06-14 (Option A: `inventory_tabs` module in `boh.dll`)

> The earlier `BLOCKED` note applied only to the *vtable-repurposing* technique
> (pointing the inventory vtable at storage's image methods → crash/transparent).
> Option A does NOT repurpose storage methods: it calls the inventory window's
> OWN original `[20]` first, then overlays the tab BMP through the engine's own
> image-draw pipeline. See "Option A Implementation" below.

## Root Cause

The Banquet client's **inventory window class** (`vtable 0x0103D460`) was compiled from source
code that never included image tab support. Storage has it because it's a different C++ class
(`vtable 0x0102A338`). The inventory class stores data at different memory offsets — patching
its vtable to use storage's methods causes crashes or transparency. QJS can't patch .rdata
(WARP CODE-only restriction). The ROZ Global EXE is a different build entirely (can't compare).

## Key Addresses

| VA | Name | Hook Safe? |
|----|------|-----------|
| `0xA9ED30` | MsgStr | Yes |
| `0x864690` | AddTab | Yes |
| `0x008262E0` | Tab BMP Loader (works for storage, not inventory) | Yes |
| `0x00A25A70` | kTextDraw | Yes |
| `0x00A245C0` | vtable[1] shared text method | Yes |
| `0x00A1B787` | SetupTabPane | **NO** (anti-tamper) |
| `0x0093F350` | Inventory tab creation code | **NO** (anti-tamper) |
| `0x0103D460` | Inventory window vtable | Runtime-patchable |
| `0x0102A338` | Storage window vtable | Runtime-patchable |
| `0x0102AC48` | Format string "tab_itm_%02d.bmp" (old 2020 format) | Runtime-patchable |
| `0x00A1D260` | kImageDraw (called by BMP loader) | Read-only |
| `0x00A8D4A0` | CreateSurfaceObject | Read-only |

## Inventory Memory Layout

- `[invWnd+0x1C]` = **X position** (screen coordinates) — confirmed working
- `[invWnd+0x20]` = **Y position** (screen coordinates) — confirmed working
- `[invWnd+0x14]` = width
- `[invWnd+0x18]` = height
- `[invWnd+0x80]` = window type flag (0=itm,1=cmd,2=que,3=item)
- `[invWnd+0x04]` = parent pane pointer
- `[invWnd+0x118]` = tab control pointer
- `[tabCtrl+0x04]` = invWnd back-reference

## Vtable Comparison

| Entry | Inventory (0103D460) | Storage (0102A338) | Parent (0103C7B8) |
|-------|---------------------|--------------------|--------------------|
| [0] | 0x00936700 (ctor) | 0x0081B460 (ctor) | 0x009360A0 (ctor) |
| [1] | 0x00A245C0 (shared) | 0x00A245C0 (shared) | 0x00A245C0 (shared) |
| [15] | 0x0093F100 (text-only) | 0x005A77C0 (image-capable) | 0x0093A750 |
| [18] | 0x00944230 | 0x005A77D0 | 0x005A77D0 |
| [19] | 0x0094E520 | 0x005A8A20 | 0x005A8A20 |
| [20] | 0x00946DA0 (own per-frame draw) | 0x008262E0 (BMP loader) | 0x00944240 |

## BMP Loader (0x008262E0) — CONFIRMED disassembly (2026-06-14)

Full, reproducible recipe (verified against the 2025-07-16 Ragexe). All four
helper calls and their calling conventions are confirmed:

```
mov edi, ecx                     ; this = window
mov eax, [edi+0x80]              ; flag (0=itm,1=cmd,2=que,3=item); else draw nothing
mov eax, [edi+0x30]; inc eax     ; selected tab index + 1
push eax; push <fmt>; lea buf;   ; fmt: 0x102AC48/AC78/ACA8/ACD8
call 0x00529850                  ; sprintf(buf, fmt, tab+1)   [cdecl varargs]
call 0x00A90350 -> esi           ; GetTexMgr() singleton      [cdecl, no args]
push buf; call 0x00A9F030 -> eax ; ConvPath(buf)              [cdecl, 1 arg]
mov ecx, esi; push eax;
call 0x00A8D4A0 -> eax           ; mgr->LoadSurface(token)    [thiscall]
push 0; push eax; push 0; push 0; mov ecx, edi;
call 0x00A1D260                  ; kImageDraw(this, x=0, y=0, surf, 0) [thiscall]
```

Format strings (EUC-KR `유저인터페이스\basic_interface\` prefix):
- `0x0102AC48` = `tab_itm_%02d.bmp`  (flag 0)
- `0x0102AC78` = `tab_cmd_%02d.bmp`  (flag 1)
- `0x0102ACA8` = `tab_que_%02d.bmp`  (flag 2)
- `0x0102ACD8` = `tab_item_%02d.bmp` (flag 3, storage — WORKS)

Key insight: the loader draws ONE image (the selected-tab graphic) at window
origin, not four separate tab buttons. So the inventory overlay loads
`tab_pri_{selected+1}.bmp` and draws it at the tab strip origin.

Inventory `[20]=0x00946DA0` is NOT a no-op: it is the inventory's own per-frame
draw (SEH function) that itself loops `kImageDraw` using fmt `0x1027D24`. It is
the correct, per-frame, correct-context overlay point (confirmed by approach 26
turning the window transparent when it was replaced).

## Approaches Tried

| # | Approach | Result |
|---|----------|--------|
| 1 | Win32 SysTabControl32 | Not a Win32 control |
| 2-4 | GDI TextOutW/ExtTextOutW/DrawTextW hooks | Tab labels don't use GDI |
| 5-6 | kTextDraw hook | Tab labels use unknown render path |
| 7-8 | Window enumeration | No inventory HWND (D3D surface) |
| 9-11 | GDI overlay + subclass | BMPs visible, flicker, wrong position |
| 12-14 | AddTab hook + vtable dump | Discovered vtable structure |
| 15-17 | Naked MsgStr EDI hook | Captures invWnd, found X=+0x1C Y=+0x20 |
| 18-20 | Hook SetupTabPane | Anti-tamper crash |
| 21 | PostMessage BMP loader call | Inventory transparent |
| 22-24 | Vtable method calls | No GetPos/GetRect found |
| 25 | Full invWnd memory dump | Confirmed position offsets |
| 26 | Patch vtable[20] only | Inventory transparent |
| 27 | Patch vtable[15]+[18]+[19]+[20] | Crash |
| 28 | Patch vtable[15]+[20] | Crash |
| 29 | Format string patch + vtable[20] | Inventory transparent |
| 30-31 | WS_EX_LAYERED / GDI overlay | Works but flickers |

## BMP Files

`data/texture/유저인터페이스/basic_interface/`:
- `tab_pri_01-04.bmp` — inventory (target)
- `tab_item_01-08.bmp` — storage (working)
- `tab_itm_01-04.bmp` — copies from tab_pri
- `tab_prc_01-04.bmp` — character
- `tab_prq_01-04.bmp` — quest
- `tab_prim_01-04.bmp` — item mall

## Files Modified This Session

- `CustomDLL/SkinVisualDLL/skin_visual.cpp` — main dev file (many iterations)
- `CustomDLL/CustomItemColorsDLL/ddraw_proxy.cpp` — GDI skin tab integration (reverted)
- `CustomDLL/RuneVisualDLL/boh_rune_visual.cpp` — kTextDraw diagnostics (reverted)
- `CustomDLL/build.bat` — added BOH_COMBINED_SKIN, comctl32, msimg32, oleacc, advapi32
- `tools/dump_vtable.py` — vtable comparison script (earlier session)
- `tools/find_ui_position.py` — vtable method analysis (earlier session)

(Historical note: on 2026-06-14 the predecessor implementation became a DLL
loader for the `inventory_tabs` module. That approach was later superseded by
the current pure-QJS `ROGlobalZeroInventory.qjs` implementation.)

## Option A Implementation (2026-06-14)

New DLL module `CustomDLL/src/inventory_tabs/inventory_tabs.cpp`, compiled into
`boh.dll` (export `InventoryTabsInit`, DllMain renamed `InvTabsDllMain`, chained
from `main_proxy.cpp`).

How it works:
1. Install thread patches inventory `vtable[20]` entry (VA `0x0103D4B0`) from
   `0x00946DA0` to our thiscall hook. The vtable is `.rdata`, so the entry is
   `VirtualProtect`-ed writable (same trick rune_visual uses on surface vtables).
   Aborts safely if the slot does not hold `0x00946DA0` (wrong client).
2. The hook calls the ORIGINAL `0x00946DA0(this)` first (purely additive — no
   transparency), then reproduces the storage loader recipe with the inventory
   `this`, using a `tab_pri_%02d.bmp` format built by copying `0x0102AC48` and
   swapping `itm`→`pri` (keeps the exact EUC-KR directory prefix).
3. Draws `kImageDraw(this, X, Y, surface, 0)`.

Env tuning (no rebuild needed — mirrors rune_visual's iterative workflow):
`BOH_INVTABS` (0/off disables), `BOH_INVTABS_LOG=1` (writes
`inventory_tabs_plugin.log` next to the DLL), `BOH_INVTABS_SKIP_ORIG=1`,
`BOH_INVTABS_X`/`_Y` (tab strip origin, default 0,0), `BOH_INVTABS_IDXOFF`
(selected-tab byte offset, default `0x30`), `BOH_INVTABS_FORCEIDX`.

WARP: `Scripts/Patches/ROGlobalZeroInventory.qjs` (formerly registered `InventoryTabsInit`
via `CustomDLL.applySpec`), UI entry under `CustomUI` in `Patches/UI.yml`,
export added to `Inputs/DLLSpec.yml`, feature bit `BOH_INVENTORY_TABS` in
`boh_features.h`. Analysis tool: `tools/disasm_invtabs.py`.

Remaining work (needs the live client — cannot be done from static analysis):
- Confirm tab strip X/Y (start with `BOH_INVTABS_LOG=1`, read window pos
  `[invWnd+0x1C]/+0x20`, set `BOH_INVTABS_X/_Y`).
- Confirm the inventory selected-tab field offset (default `0x30` from storage;
  log neighbors if the wrong image shows).
- Verify `tab_pri_01-04.bmp` exist under `data/texture/유저인터페이스/basic_interface/`.

## Path Forward (alternatives if Option A needs it)

1. **D3D Present() hook** — render BMPs as textured quads (infra already exists in
   `fps_ping_overlay.cpp`: EndScene/DrawPrimitiveUP/Reset vtable hooks).
2. **Source-level fix** — requires client source code.
3. **ROZ-compatible client build** — find a client with compiled-in image tab support.

---

## NPC Name Overlay (Always Show NPC Names)

### Goal
Make NPC names always visible above their heads (not just on mouse hover), using the game's own rendering pipeline for correct 3D-to-screen positioning.

**2026-07-12 QJS-only update:** `AlwaysShowNpcName.qjs` no longer imports
`boh_npc_names.dll`. It drains the static EXTN ring into a 256-entry fixed
`(GID, balloon, retry-frame)` table, guards the `CGameMode` vtable/world
manager, and calls the native factory `0x00C714B0`, actor lookups
`0x00A69EB0/0x00A69FA0`, setup/projection `0x00C6D1D0`, and teardown
`0x00A447D0` from EXE caves. `/shownpcname` now targets a static option-toggle
cave through `CustomSlashCommand.targetVir`. The four former NPC overlay
imports are absent from the generated client. Option 10001 is mirrored to the
one-byte `savedata/shownpcname.dat` sidecar through the client's existing
`CreateFileA`/`ReadFile`/`WriteFile`/`CloseHandle` imports. This avoids adding
the synthetic option to the native command-registration list; detouring that
registration call interfered with the label renderer and must not be restored.

### What NOT to do (from commit e4c57e2d)
- **DO NOT** NOP the 6 "gates" in `AlwaysShowNpcName.qjs`. The gates are string-pool management code, NOT visibility checks. NOPing them causes crashes.
- **DO NOT** use a GDI layered window (`npc_name_overlay.cpp`) to draw NPC names manually. It cannot get correct per-NPC screen coordinates and draws all names in a static list at the top-left corner.

### Correct Approach: Hook the Balloon Updater
The game already has robust 3D-to-screen projection for name balloons. Hook the per-frame updater and force it to draw for every NPC.

#### Key Classes and Functions

| Address | Symbol / Purpose | Notes |
|---------|-----------------|-------|
| `0x010904B8` | `CGameMode` vftable | Identified via RTTI |
| `0x00C63570` | `CGameMode` constructor | Build the class |
| `0x01213338` | `CGameMode` global instance | Set during `CModeMgr::SwitchMode` |
| `0x00A69EB0` | `GetActorByGID` | `thiscall`; takes world manager in `ECX`, GID in arg |
| `0x00C714B0` | Balloon factory | Creates `UINameBalloonText` or `UIVerticalNameBalloonText` |
| `0x00C6D1D0` | Balloon updater (actor ptr) | Called by factory; sets up balloon for a specific actor |
| `0x00C77820` | **Per-frame balloon updater** | **HOOK TARGET**. Reads `hoverGID`, calls `UpdateBalloonPos` if non-zero |
| `0x00C72CE0` | `UpdateBalloonPos` / draw | Does the actual 3D-to-screen projection and renders the balloon |
| `0x00818250` | `UINameBalloonText` constructor | Horizontal name balloon |
| `0x00C63CE0` | `UIVerticalNameBalloonText` constructor | Vertical name balloon (e.g., for CJK) |

#### CGameMode Layout (relevant offsets)

| Offset | Field | Size | Notes |
|--------|-------|------|-------|
| `+0xCC` | World Manager pointer | 4 bytes | Passed to `GetActorByGID` in `ECX` |
| `+0x2AC` | Balloon instance pointer | 4 bytes | `UINameBalloonText*` or `UIVerticalNameBalloonText*` |
| `+0x2D8` | `hoverGID` | 4 bytes | GID of the entity currently under the mouse. **0 = no hover** |

#### How `0xC77820` works (balloon updater logic)
```cpp
// Pseudo-code from disassembly
mov eax, [ebx+0x2AC]      // load balloon pointer
test eax, eax
je skip                   // no balloon instance -> skip
mov edx, [ebx+0x2D8]      // load hoverGID
test edx, edx
je skip                   // hoverGID == 0 -> skip (this is the "hover gate")
mov ecx, [ebx+0xCC]       // load world manager
call UpdateBalloonPos     // 0xC72CE0 — does 3D projection + draw
```

#### Recommended Hook Strategy
1. **Install a trampoline hook** at `0x00C77820` using `patch_jmp` (same technique as `boh_rune_visual.cpp`).
2. In the hook:
   - Call the original function first (let it handle normal hover behavior).
   - Read `hoverGID` from `[CGameMode+0x2D8]`.
   - If `hoverGID == 0` (no hover):
     - Iterate through all NPCs in the world (or a known NPC list).
     - For each NPC:
       - Temporarily write the NPC's GID into `[CGameMode+0x2D8]`.
       - Call the original updater (`0xC77820`) so the game draws that NPC's name at its correct screen position.
       - Restore `hoverGID` back to 0.
3. **Why this works**: You are reusing the game's existing `UpdateBalloonPos` (3D projection + sprite rendering). No manual coordinate math needed.

#### Reference Implementation Pattern
See `CustomDLL/src/rune_visual/boh_rune_visual.cpp`:
- `patch_jmp(target_va, &hook_fn, stolen_bytes, steal_len, &trampoline)` — steals bytes and installs trampoline.
- Hook calls `trampoline()` to run original logic, then adds custom behavior.

#### WARP / DLL Integration
- Build the hook into `boh.dll` (or the existing NPC overlay DLL).
- Load the DLL via `CustomDLL` or `CustomPacketDispatch` in the WARP patch (same mechanism as the old `npc_name_overlay.cpp`).
- No WARP hex patches needed — the hook is runtime memory modification done by the DLL.

### Files / Tools Used in Analysis
- `tools/analyze_npc_name.py` — Disassembled the 6 gates from `AlwaysShowNpcName.qjs`; proved they are string-pool code.
- `tools/find_name_classes.py` — RTTI scan for `UINameBalloonText`, `UIVerticalNameBalloonText`.
- `tools/trace_name_balloon.py` — Traced vftable -> constructor -> callers -> factory.
- `tools/dis_balloon_callers.py` — Disassembled factory (`0xC714B0`) and updater (`0xC6D1D0`).
- `tools/trace_up.py` — Traced call chain from `0xC6D1D0` up to `0xC77820`.
- `tools/find_2d8_refs.py` — Found all `[reg+0x2D8]` (hoverGID) and `[reg+0x2AC]` (balloon ptr) references.
- `tools/find_mode_global.py` — Located `CGameMode` vftable, constructor, and global instance at `0x1213338`.
- `tools/find_world_global.py` — Verified world manager pointer chain through `CGameMode`.
- `tools/d.py` (formerly `dis.py`) — Quick Capstone disassembly helper.

### WORKING v6 Implementation (2026-06-13 FINAL)

After 50+ build iterations, the multi-balloon approach is confirmed working. Architecture:

#### Gepard-safe conversion (2026-06-30)

The runtime DLL trampoline at `0xC77820` has been superseded for Gepard builds.
`AlwaysShowNpcName.qjs` now patches the single direct caller
`0x00C7642D -> 0x00C77820` on disk to call a WARP code cave. The cave calls the
original updater first, then calls imported `NpcNameOverlayFrame(gameMode)` from
`boh_npc_names.dll`. The DLL no longer calls `VirtualProtect`, allocates a
gateway, restores stolen bytes, or writes EXE code at runtime.

NPC discovery no longer requires `boh_text.dll`/GDI hooks in strict profiles:
`AlwaysShowNpcName.qjs` installs the dispatcher-table EXTN route for `0x0BB7`,
and `boh_npc_names.dll` drains that shared ring from `NpcNameOverlayFrame`.
Remaining approval surfaces for Gepard are static EXE patch locations, not
runtime hooks: frame caller `0x00C7642D`, dispatcher table base `0x00CAA2E0`,
and `0x0BB7` entry `0x00CACFF0`.

```
Hook at 0xC77820 (5-byte trampoline, vtable guard)
  → Creates one UINameBalloonText per NPC via factory (0xC714B0)
  → Each frame: swaps NPC balloon into CGameMode+0x2AC
  → Calls 0xC6D1D0 (BalloonActorSetup) — sets text + positions
  → Game's UI renders all balloons natively
  → Balloons auto-removed when NPC despawns
```

#### Key addresses (2025-07-16 Ragexe)
| VA | Symbol | Notes |
|----|--------|-------|
| `0xC77820` | PerFrameUpdater | Hook target, steal 5 bytes |
| `0xC6D1D0` | BalloonActorSetup | Sets text from actor+0x110 AND positions |
| `0xC714B0` | BalloonFactory | Creates UINameBalloonText |
| `0xA69EB0` | GetActorByGID | Returns actor for GID |
| `0x010904B8` | CGameMode vftable | Vtable guard |

#### CGameMode offsets
`+0xCC`=worldMgr, `+0x2AC`=balloon slot, `+0x2C4`=state flag, `+0x2C8`=state flag2, `+0x2D8`=hoverGID

#### Trampoline MUST steal exactly 5 bytes
Function prologue: `push ebp`(1) + `mov ebp,esp`(2) + `push -1`(2) = 5 bytes.
Next is `push 0xF20711` (SEH cookie, 5 bytes). 7 bytes cuts into immediate → crash.

#### Vtable guard (CRITICAL)
`0xC77820` is called for ALL game modes. Must verify `*(DWORD*)this == 0x010904B8`.

#### Crash bugs fixed
1. 7-byte trampoline → 5 bytes
2. No vtable guard → login crash
3. OnHoverEntity type-0x2D gate skips NPCs → use 0xC6D1D0 directly
4. `actor+0xA8=0` causes UpdateBalloonPos default path → bypassed by 0xC6D1D0's internal positioning
5. Byte patches (cmovne→mov cl,2) causing C++ exceptions → removed all EXE patches
6. State flag suppression missing → hover balloon destroyed

#### Known limitations
- Names follow NPCs off-camera (RO loads entities ~30 tiles, camera ~15 tiles)
- Uses game's default balloon appearance
- No off-screen detection possible with available data

#### Hover/persistence/drag fixes (2026-06-14)
Root cause of "must hover first", "name only stays a second", and "name drags
across the screen when walking away":
- `BalloonActorSetup` (`0xC6D1D0`) takes the balloon text from `[actor+0x110]`,
  which is a pointer into the client's interned name pool (`CGameMode+0x160`).
  `0x5A1460` looks the pointer up in that pool; if it is not a valid pool entry
  the function bails at `0x00C6D25D` (`je 0xc6d97e`) — **no text AND no position
  update**. So an un-interned NPC shows nothing and, once it stops being updated,
  its balloon freezes at a stale screen position (the "drag").
- The name pool entry is only created when the client receives the regular name
  packet `0x0ADF` (`ZC_ACK_REQNAMEALL_NPC`). The server sent that for NPCs **only
  on hover** (`clif_name`), never when the NPC entered view — `clif_getareachar_unit`
  / `clif_spawn` handled `BL_MOB` (`clif_name(sd,bl,SELF)`) but not `BL_NPC`.
- Raw `char*` injection into `[actor+0x110]` does NOT work (pool lookup fails →
  empty balloon). The name must be interned through the game's own packet path.

Fix = server + client:
- **Server** (`BanquetOfHeroes/src/map/clif.cpp`): send the NPC name on view and
  on spawn so the client interns it without a hover.
  - `clif_getareachar_unit` `BL_NPC`: added `clif_name( sd, bl, SELF );` (mirrors `BL_MOB`).
  - `clif_spawn`: `BL_NPC` now uses `clif_name( bl, bl, AREA )` (sends `0x0ADF`
    + `0x0BB7`); other non-mob types keep `clif_extended_name`. `0x0BB7` stays
    gated by `feature.custom_extended_name_packet`; `0x0ADF` is a stock packet,
    so vanilla clients are unaffected (they still only draw the balloon on hover).
- **Client** (`CustomDLL/src/npc_name_overlay/npc_name_overlay.cpp`):
  - When `GetActorByGID` (`0xA69EB0`, with `0xA69FA0` fallback) returns null
    (NPC out of range / despawned), the balloon is now destroyed via the engine's
    deferred-delete `0xA447D0` (`this = UIWindowMgr @ 0x0131F4E8`) and recreated
    when the NPC returns. Previously balloons were only `erase()`d from `g_bal`
    without destroying the engine object, so they kept rendering at a stale
    position (drag). Stale entries dropped from `g_nam` are destroyed the same way.
  - Removed the per-frame `if (*mainSlot == 0) fnFact(mainSlot)` that created a
    fresh balloon every frame before the first hover (orphaned on restore →
    stray floating balloons).
  - `0xA447D0` = clear focus refs at `+0x3d4/+0x3d8/+0x3dc/+0x1b8/+0x4f1d4`, then
    push the balloon onto the UI manager's pending-destroy list (`+0x184` via
    `0xA1A830`); freed safely at the manager's next cleanup pass.

#### NPC-only filter + EXTN race + diagnostics (2026-06-14b)
Two more user-reported symptoms and their root causes:

1. **"mobs/players/elementals/mercenaries behave the same" (persist after hover).**
   `0xC77820` has two hover-balloon slots: `+0x2AC` (flag `+0x2C4`) and `+0x2B0`
   (flag `+0x2C8`), both for hover GID `+0x2D8`. Flag == 0 -> update/reposition
   the balloon then set flag = 1; flag != 0 -> destroy it (`0xA447D0`). The hover
   detector resets the flag to 0 while the cursor is over an entity. The hook was
   forcing both flags to 0 **every frame**, so the engine's hover balloon for the
   last-hovered entity of **any** type never got destroyed and stayed on screen.
   - **Fix:** removed the two flag-forcing writes. The engine now destroys hover
     balloons normally for every type. NPC always-on still works because it comes
     from our own per-NPC balloons (`g_bal`), and `g_nam` is filtered to `type==2`
     (NPC) only — independent of these flags. `savedMain` is captured *after*
     `orig()`, so there is no dangling-pointer crash (the old "suppression" crash
     note applied to the pre-multi-balloon design).

2. **"some NPCs work, some don't" (random).** Extended names (`0x0BB7`, magic
   `EXTN`) arrive in a WARP-allocated **single-slot** shared buffer
   (`[id][ready@+4][len@+8][packet@+12]`). **Two** modules in `boh.dll` were both
   finding it and both clearing `ready@+4`: `item_color/colored_itemname.cpp`
   (`CheckSharedBlock` -> `ParseExtNamePacket`) and `npc_name_overlay` (`PollExtn`,
   250 ms). Whoever polled first consumed and cleared the slot, so each NPC's
   packet reached only one module at random.
   - **Fix:** `item_color` is now the **sole** consumer; `ParseExtNamePacket`
     calls `extern "C" void NpcOverlay_OnExtName(gid,type,name)` (defined in
     `npc_name_overlay.obj`, resolved at link time within `boh.dll`). The overlay
     dropped `FindShared`/`ParseExtn`/`PollExtn`; `g_nam` is now filled only via
     that callback (`type==2`). Note: `g_nam`'s string value is **not** used for
     rendering (text comes from the game via `[act+0x110]`); only the GID set
     matters. `clif_extended_name` only emits `0x0BB7` for `BL_PC`(0)/`BL_MOB`(1)/
     `BL_NPC`(2); `BL_ELEM/MER/HOM/PET` send nothing.

3. **Diagnostics (historical).** The temporary per-NPC `DiagSet` and periodic
   `[SUMMARY]` logging were used to diagnose actor lookup, name interning, and
   EXTN delivery. They were removed after the transport and rendering fixes, so
   the current overlay does not create `npc_name_overlay.log` or perform
   per-frame diagnostic file I/O.

4. **Delayed discovery after entering view (2026-06-15).** The sole EXTN
   consumer still called `CheckSharedBlock()` only from `TextOutW` /
   `ExtTextOutW` render hooks (roughly every 60 qualifying calls). Logs showed
   `hc` increasing immediately while `extn` remained zero for 15+ seconds, then
   crawled upward one NPC at a time. The overlay was correct once it received a
   GID; delivery was coupled to unrelated UI text rendering.
   - `item_color` now starts a dedicated shared-block drain worker and polls
     every 2 ms, independently of GDI rendering.
   - `CustomPacketDispatch` now gives EXTN a lock-free 128-slot ring:
     `[magic][writeSequence][RING][capacity=128]`, followed by 256-byte slots
     containing `[length][packet]`. The x86 dispatcher writes the packet first,
     then increments `writeSequence` as the publish step.
   - The DLL drains every published sequence in order and copies each slot to a
     local buffer before parsing. It logs `[SHARED:overflow]` if it ever falls
     more than 128 packets behind.
   - Legacy single-slot EXTN blocks are still recognized and drained, but remain
     best-effort. To receive the no-loss burst behavior, regenerate the patched
     client EXE from a clean input with the updated WARP scripts; replacing only
     `boh.dll` improves polling latency but cannot undo the old producer's
     overwrite behavior.
   - DLL detach now stops the drain worker before the NPC overlay module tears
     down, preventing callbacks into feature state during shutdown.

#### Files
| File | Status |
|------|--------|
| `CustomDLL/src/npc_name_overlay/npc_name_overlay.cpp` | v6 multi-balloon (FINAL) |
| `CustomDLL/src/item_color/colored_itemname.cpp` | Sole EXTN consumer + 2 ms ring drain worker |
| `Scripts/Patches/CustomPacketDispatch.qjs` | EXTN 128-slot ring producer; ICOL/HATF unchanged |
| `Scripts/Patches/AlwaysShowNpcName.qjs` | DLL registration, `/shownpcname` command, and Game Settings bridge (no gate NOPs) |
| `Patches/Client.yml` | Updated description |
| `CustomDLL/src/boh.dll` | Combined DLL with NpcNameOverlayInit export |

#### Extended-name module split + optional DLL packaging (2026-06-15)

- EXTN transport, ring draining, parsing, maps, and text substitution moved from
  `item_color/colored_itemname.cpp` to `extended_name/extended_name.cpp`.
- ICOL and EXTN now have independent consumers and worker lifecycles. An absent
  shared block is probed once and does not leave a 2 ms scan loop running.
- `build.bat` still creates the backward-compatible combined `boh.dll`.
  `build_split.bat` additionally creates `boh_text.dll`, `boh_npc_names.dll`,
  `boh_rune.dll`, `boh_fps.dll`, and `boh_inventory_tabs.dll`.
- Every WARP visual feature now has its own saved DLL filename prompt. Choosing
  `boh.dll` everywhere preserves the combined setup. Choosing the dedicated
  names isolates unrelated modules.
- Item colors and extended names stay together in `boh_text.dll` because both
  use the same GDI hook owner. Their packet handling is still separated.
- NPC forwarding no longer requires a link-time dependency. The EXTN module
  resolves exported `NpcOverlay_OnExtName` dynamically, so combined and split
  packaging both work.
- Fixed the dropped-card `@showmobinfo` symptom. The server correctly puts mob
  info in the MOB fields of 0x0BB7; the client was matching a mob short name as
  an arbitrary substring, so `Poring Card` matched `Poring`. MOB replacement is
  now exact-nameplate-only. Player/NPC exact replacement and player chat
  replacement remain supported.
- `extended_name/extended_name_test.cpp` covers the `Poring` versus
  `Poring Card` regression and player chat replacement.

#### `/shownpcname` and `/font` option handling (2026-06-15)

- `/shownpcname` is a custom client option with TALKTYPE ID `10001`. The slash
  command calls `ToggleNpcNameOverlay`, while the Game Settings ON/OFF row calls
  `SetNpcNameOverlayOption(10001, enabled)`.
- The Game Settings bridge in `AlwaysShowNpcName.qjs` must call the DLL only
  when `[CUIOptionItem+0xF8] == 10001`. All native options, especially `/font`,
  must continue directly through the client's original callback. Pre-writing a
  native option in the DLL prevents the native TALKTYPE handler from observing
  the state transition and running its normal update path.
- NPC balloon placement mirrors the native client's `/font` state once per
  frame. The authoritative disassembly is in `UpdateBalloonPos` at `0xC72CE0`:
  `push 0x5C; call 0x68EA70`. Therefore the correct
  `kNameAboveHeadOption` is **`0x5C`**, not `0x40`.
- Using `0x40` made the overlay read an unrelated option that remained enabled,
  so NPC names appeared permanently overhead even though the `/font` UI toggle
  changed normally. Correcting the constant to `0x5C` restores immediate
  above/below switching without intercepting or rewriting `/font`.
- After this correction, both `build_split.bat` and `build.bat` build cleanly.
  Deploying the rebuilt `boh_npc_names.dll` is sufficient for the split setup;
  no EXE repatch is needed for this constant-only DLL fix.

## TODO: Depth-Occluded Lua-Driven HatEffect Renderer

Status: backlog / renderer research. This is feasible, but it is a substantial
renderer-rehosting project rather than a packet-remapping patch.

Goal: support custom HatEffect STR resources that remain attached to actors but
are hidden correctly by buildings, walls, and other world geometry, matching
the depth behavior of native special effects.

Recommended design:

1. The server sends a custom packet containing the operation, actor GID, and a
   custom effect ID.
2. WARP's approved packet dispatcher copies messages into a dedicated ring
   buffer owned by the HatEffect renderer module.
3. A dedicated DLL, preferably `boh_hat_effects.dll`, consumes the ring without
   sharing or racing another custom DLL's transport.
4. A client Lua registry maps each custom effect ID to its STR resource and
   metadata such as X/Y/Z offsets, scale, looping, and attachment behavior.
5. The DLL keeps active instances keyed by `(GID, effect ID)`, resolves the
   actor, and creates, updates, or destroys the attached visual as needed.
6. The STR must be hosted in the client's native world effect pipeline
   (`CRagEffect` / `CEffectPrim` or an equivalent world render pass using the
   scene depth buffer). A generic `EndScene` overlay will not provide correct
   world occlusion.

Prototype before building the full data-driven system:

1. Hard-code one `resourceFileName` STR.
2. Load it through a native special-effect primitive or equivalent world object.
3. Attach it to one actor.
4. Verify partial occlusion behind RSW buildings and walls.
5. Verify looping and cleanup on actor despawn, map change, device reset, and
   DLL detach.
6. Add the packet, ring transport, and Lua registry only after the occlusion
   proof succeeds.

Scope and constraints:

- Existing `hatEffectID = X` entries should continue using stock `0x01F3`
  special effects. The new renderer targets custom `resourceFileName` entries.
- Packet remapping, actor-position changes, HatEffect marker changes, the
  flags-`0x05` carrier/depth-bias path, flags-`0x0D` queue selection, and
  model-culling changes did not produce true world occlusion. V4.2's scoped
  normalized-Z bridge passed the live wall, contact, floor, size, and zoom gates.
- Avoid broad Direct3D state forcing and HUD-style rendering.
- Review the static dispatcher patch and runtime render hooks for
  anti-cheat/Gepard compatibility.
- Packet handling should be event-driven. Cache Lua/resource resolution,
  maintain only active instances, avoid scanning every actor or effect each
  frame, cap active effects, and remove instances promptly during lifecycle
  transitions.

Confidence: high for the build-specific 2025-07-16 QJS patch after live v4.2
validation. It retains the native HatEffect objects, attachment, resources, and
lifecycle, so no custom packet/ring transport or parallel actor registry is
required for this renderer correction.

# ROZ Global UI Renewal Port - Investigation

**Investigated:** 2026-06-15

**Source assets:**
`C:\Gravity\RagnarokZero\data\texture\유저인터페이스\uirenewal`

**Target client:**
`2025-07-16_Ragexe_175220998_clientinfo_patched.exe`

## Initial conclusion

The ROZ UI renewal can be ported in stages. It is not one dormant feature that
can be enabled with a single flag, but several components are already compiled
into the target client and use compatible resource names. Those components can
start as data-only overrides. Larger windows need additive, class-specific DLL
hooks similar to `inventory_tabs`; only the full quest and dialog redesigns
approach a UI reconstruction project.

The source tree contains 731 files in these groups:

| Group | Files | Port character |
|---|---:|---|
| `basicinfo` | 11 | Existing classes plus layout work |
| `chat` | 32 | Partial direct compatibility; full layout needs hooks |
| `dialog` | 14 | New layout and button-state work |
| `expbar` | 10 | Additive overlay / Basic Info integration |
| `itemui` | 1 | Simple inventory overlay candidate |
| `jobicon` | 230 | Existing job-icon consumers; path/size mapping needed |
| `mapname` | 2 | Simple overlay candidate |
| `menuicon` | 244 | Strong data-only compatibility |
| `playergage` | 6 | Existing gauge classes; renderer adaptation needed |
| `questdialog` | 17 | Existing dialog/scroll controls; mapping needed |
| `questui` | 160 | Existing quest classes, but substantial re-layout |
| Other/root | 4 | Level-up and small specialized interfaces |

`ROZ Global.exe` is the 4.9 MB patch client/launcher, not the game renderer. Its
embedded paths are under `PatchClient\LuaFiles514`. The actual game executable
is `C:\Gravity\RagnarokZero\Ragexe.exe`, which is protected by Themida and
cannot be used for a normal static code comparison without a runtime dump.

## Confirmed target-client clues

The target executable already contains the following compatible classes and
resource paths:

| Component | Target implementation | Evidence |
|---|---|---|
| Basic HP/SP bar frame | `UIBarGraph`, vtable `0x0102B6B8`, draw slot 20 `0x0084F9E0` | Directly loads `basic_interface\gze_bg.bmp`; the ROZ tree contains the same `gze_bg.bmp` name |
| Basic Info window | `UIBasicInfoWnd`, vtable `0x0103E35C` | Existing WARP `CustomExpBars` and new-button patches already locate and modify this UI |
| Player gauge | `UIPlayerGage`, vtable `0x0102BD78`; `UIBarGraphPlayer`, vtable `0x0102B508` | Existing actor gauge objects can host the ROZ `playergage` visuals |
| Menu icons | `UIMenuIconWnd`, vtable `0x010281B0`, draw slot 20 `0x00814150` | Loads `menu_icon\bg_menu.tga` and formats `bt_%s.bmp`, `bt_%s_press.bmp`, `bt_%s_new.bmp`, and `bt_%s_new_press.bmp`; matching ROZ files exist |
| Chat | `UINewChatWnd`, vtable `0x01037F80`, draw slot 20 `0x008F3340` | Loads `basic_interface\chatmode_on/off.bmp` and `lock/unlock_dragwnd.bmp`; matching ROZ files exist |
| Level-up notice | `UINotifyLevelUpWnd`, vtable `0x01034834`, create slot 15 `0x008AA270` | Builds `basic_interface\lv_up_off.bmp` and `lv_up_on.bmp`; ROZ filenames are exact matches |
| Quest scrollbar | `UIZeroQuestScrollBar`, vtable `0x0102B340`, draw slot 20 `0x00858070` | Directly loads the five `UIRenewal\questui\btn_scroll_*` images found in the ROZ tree |
| Quest windows | `CUIRenewQuestUI`, vtable `0x01049DB0`; `UIRenewQuestWnd`, vtable `0x01021588` | Full quest UI logic already exists, but currently loads older `Renew_QuestUI` layouts and filenames |
| Job icons | `UIJobIconButton`, vtable `0x01010D50` | Other consumers format `renewalparty\icon_jobs_%d.bmp`; the ROZ set supplies three sizes using `icon_job_%d.bmp` |
| Adventurer agency | Existing `UIRegisterPartyWnd` draw path near `0x007859A0` | Directly loads `UIadventurerAgency\bg_agency_admit.bmp`, an exact ROZ path/name match |

## Feasibility tiers

### Tier 1 - data-only prototypes

These should be tested before writing another DLL:

1. Copy `uirenewal\menuicon` assets into the target
   `유저인터페이스\menu_icon` path. The current renderer already requests the
   compatible base, pressed, new, and background filenames.
2. Override `basic_interface\gze_bg.bmp` with
   `uirenewal\basicinfo\gze_bg.bmp`. This changes only the existing HP/SP bar
   frame, not the whole Basic Info layout.
3. Override `basic_interface\chatmode_on.bmp`,
   `chatmode_off.bmp`, `lock_dragwnd.bmp`, and `unlock_dragwnd.bmp`.
4. Place `lv_up_off.bmp` and `lv_up_on.bmp` in `basic_interface`.
5. Copy the five quest scrollbar files into
   `UIRenewal\questui`.
6. Copy `bg_agency_admit.bmp` into `UIadventurerAgency`.

These tests are reversible loose-file overrides and require no EXE repatch.

### Tier 2 - dedicated DLL hooks

Create a separate `boh_ui_renewal.dll` with independent feature switches.
Follow the inventory-tabs pattern: verify the expected original vtable entry,
swap only that class method, call the original where appropriate, and draw
through the client's texture manager and `kImageDraw`.

Good first DLL targets:

1. Whole Basic Info background (`basic_bg.bmp` / `basic_bg_mini.bmp`) plus
   control repositioning.
2. Image-based HP/SP fills and the separate base/job EXP bars.
3. Player gauge images through `UIPlayerGage` / `UIBarGraphPlayer`.
4. Inventory zeny background through the existing inventory-window hook.
5. Map-name background through the existing map-name display path.
6. Job-icon format redirection with an explicit mapping for the 31x31, 38x38,
   and 52x52 sets.

Cache resolved surfaces and instance pointers. Do not perform filesystem scans,
image decoding, or broad UI-object searches each frame.

### Tier 3 - substantial re-layout

- The full 592x435 quest interface uses a different background, search field,
  combo box, tabs, category buttons, list selection backgrounds, and detail
  pane. Existing quest data and classes are reusable, but control creation,
  positions, and state wiring must be adapted.
- The complete chat renewal introduces a 600x24 edit-box background and a new
  set of add/delete/option/send/resize controls. Several old names are
  compatible, but the whole interface is not a texture-path swap.
- The renewed NPC/main-quest dialog uses large scene backgrounds and four-state
  90x34 buttons. It needs a dedicated `UISayDialogWnd` adaptation.

## Recommended order

1. Build and test a loose-file compatibility pack for Tier 1.
2. Prototype `basic_bg.bmp` in a new `boh_ui_renewal.dll`, because
   `UIBasicInfoWnd`, `UIBarGraph`, and the existing WARP patches provide strong
   anchors.
3. Add player gauge, EXP bars, zeny, map name, and job icons as independent
   switches after the Basic Info prototype is stable.
4. Treat the full quest UI as its own project after the reusable control and
   image-button helpers are proven.

Do not copy the entire `uirenewal` directory and expect it to activate. The
target client only requests a small subset of those paths today; the rest need
path redirection, control repositioning, or new draw/state hooks.
