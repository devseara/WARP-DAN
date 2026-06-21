// weapon_sprite.cpp - Dual-Wield per-hand weapon sprite tracer + experiments
// ============================================================================
// Target: 2025-07-16 Ragexe 175220998 (32-bit PE, image base 0x00400000,
//         DYNAMICBASE/ASLR OFF -> hardcoded VAs are safe).
//
// GOAL
//   Render each equipped weapon's own (original) sprite when dual-wielding,
//   instead of the client's generic combined dual-wield sprite, and draw the
//   off-hand weapon too.
//
// WHY A TRACER FIRST
//   The latest live DebugView trace showed WeaponTypeFunc and 0x00C58EE0 fire
//   in-game, while DrawWeapon and SpriteResSetter do not. That means the live
//   actor weapon sprite is submitted through the 0x00C58EE0 actor-part
//   dispatcher and its layer-id helpers, not the older DrawWeapon path. This
//   module now traces both paths so we can prove the real switch before making
//   a visual fix.
//
// RECOVERED DrawWeapon CONTRACT (shared call at 0x00D425CE / 0x00D4245D):
//   __thiscall DrawWeapon(this=renderer,            // ecx, from 0x00A75340
//                         arg1 = [char+0x10] body,  // position/scale block
//                         arg2 = [char+0x24C] res,  // weapon sprite resource
//                         arg3 = scale float,
//                         arg4 = 0 (native main hand) | c43230() result)
//
// PHASES (env-gated; safe defaults)
//   BOH_DUALWPN_LOG      (default ON)  : trace pipeline to DebugView
//   BOH_DUALWPN_REPLACE  (default off) : if WeaponTypeFunc returns a combined
//                                        type 25..30, replace with the main /
//                                        off individual view via d8a1d0.
//   BOH_DUALWPN_OFFHAND  (default off) : after the native main-hand draw,
//                                        issue a second DrawWeapon pass to
//                                        prove the synthetic draw is stable.
//   BOH_DUALWPN_LOG_EVERY (default 0)  : if >0, also emit a periodic heartbeat
//                                        every N DrawWeapon calls.
//   BOH_DUALWPN_FORCE_SINGLE_LAYER (default off):
//                                        mode 9 layer 0x58 -> single layer 0x50.
//   BOH_DUALWPN_FORCE_SINGLE_MODE (default off):
//                                        dispatch mode 9 through mode 2 path.
//   BOH_DUALWPN_TRACE_ACTOR_PATHS (default ON):
//                                        trace actor path-builder calls that
//                                        match the current weapon actor.
//   BOH_DUALWPN_TRACE_RESOURCE_KEYS (default ON):
//                                        trace native resource-cache lookup
//                                        results for generic/specific keys.
//   BOH_DUALWPN_TRACE_WEAPON_PATHS (default ON):
//                                        trace native weapon path-builder output.
//   BOH_DUALWPN_PRELOAD_WEAPON_PATHS (default ON):
//                                        load matching item-specific ACT paths
//                                        as soon as native builders produce them.
//   BOH_DUALWPN_ALIAS_RESOURCE_KEYS (default ON):
//                                        if native cache lookup misses a specific
//                                        weapon key, return the preloaded object.
//   BOH_DUALWPN_SYNTH_WEAPON_PATHS (default ON):
//                                        synthesize item ACT paths from the
//                                        actor body path when native weapon
//                                        builders do not fire.
//   BOH_DUALWPN_AUTO_SYNTH_VISUAL (default off):
//                                        enable the skipped resource branch and
//                                        submit a synthesized key only after a
//                                        matching resource object is cached.
//   BOH_DUALWPN_SUPPRESS_NATIVE_SUBMIT (default off):
//                                        suppress native id 80/88 weapon actor
//                                        part submit once original resources
//                                        are cached.
//   BOH_DUALWPN_SYNTH_DRAW (default off):
//                                        draw cached original ACT objects via
//                                        the recovered DrawWeapon contract.
//   BOH_DUALWPN_FORCE_RESOURCE_BRANCH (default off):
//                                        let mode 2/9 fall through the resource
//                                        lookup branch skipped by stock code.
//   BOH_DUALWPN_FORCE_RESOURCE_KEY (default off):
//                                        temporarily submit a specific view key
//                                        through [char+0x24C] during mode 2/9.
// ============================================================================
//
// GHIDRA REVERSE-ENGINEERING FINDINGS (2026-06-22)
// ============================================================================
//
// FUN_00c58ee0 (RenderModeSetter) — actor-part dispatcher, thiscall:
//   void __thiscall FUN_00c58ee0(int *charObj, int mode, char arg)
//
//   param_1[0x1c] = current mode
//   param_1[0x93] = [char+0x24C] resource key  (0x93 * 4 = 0x24C)
//
//   case 2:   // single weapon render mode
//   case 9:   // dual-wield combined render mode
//       (**(code **)(*param_1 + 0x1c))();           // <- C55C30 submit ALWAYS runs first
//       if ((param_1[0x1c] != 9) && (param_1[0x1c] != 2)) {
//           // Resource branch — ONLY for modes other than 2 and 9
//           iVar3 = param_1[0x93];                  // read [char+0x24C]
//           // ... A69EB0 resource cache lookup ...
//           // ... C40AC0 DrawWeapon ...
//       }
//       // ... misc vfunc calls ...
//       (**(code **)(*param_1 + 0x40))();           // vtable+0x40 cleanup
//       break;
//
//   The two JE instructions that implement the mode skip are inside C59168
//   (dispatcher helper called from C58EE0):
//       kSkipResourceJe9 = 0x00C5917A  (0x74 0x52)  JE over branch when mode==9
//       kSkipResourceJe2 = 0x00C5917F  (0x74 0x4D)  JE over branch when mode==2
//
//   Our g_force_resource_branch NOPs both JEs, letting modes 2/9 enter the
//   resource lookup + DrawWeapon path that stock code skips.
//
// WORKING FLAG COMBINATION (verified weapon_9.log):
//   BOH_DUALWPN_AUTO_SYNTH_VISUAL=1        <- NOPs JEs + injects weapon key
//   BOH_DUALWPN_SUPPRESS_NATIVE_SUBMIT=1   <- blocks C55C30 for mode 9
//   BOH_DUALWPN_SYNTH_DRAW=1               <- manual DrawWeapon post-trampoline
//
//   Frame 1: cold cache -> combined sprite (suppress=0)
//   Frame 2: SynthPath loads ACT, alias created, suppress=1, SYNTH_DRAW fires
//   Frame 3+: both main/off cached, suppress=1, SYNTH_DRAW main+off every frame
//
// KNOWN ISSUE: SYNTH_DRAW calls fire but sprites may be invisible. Possible
//   causes: wrong renderer pointer, wrong body coords, layer interference
//   (mode 9 layer 88 vs mode 2 layer 80), or synthetic path loads wrong ACT.
//
// GHIDRA FULL RENDER PIPELINE (2026-06-22)
// ============================================================================
//
// D41DF0 is the MAIN render dispatch — C58EE0 is called FROM it, not from the
// render loop directly. D41DF0 switch(param_2=mode):
//
//   case 2 (single weapon):
//     D72D30(WeaponType) → C58EE0(RenderMode) → A9A7D0(resolve) → C6D9D0(Draw)
//     DrawWeapon ONLY called if item uses arrows ([char+0x134] check)
//
//   case 9 (dual-wield combined):
//     D72D30(WeaponType) → C58EE0(RenderMode) → D5D0D0(float)
//     DrawWeapon ONLY called for weapon types 0xD/0xE (bows/guns)
//
//   For daggers (type 31): DrawWeapon is NEVER called natively.
//
// C55C30 (kActorSubmit1C) is NOT a draw submit — it's an init/configure
// function that sets position, scale, animation frame, and clears counters.
// The actual drawing happens LATER in a renderer batch pass.
//
// C6D9D0 (kDrawWeapon) creates render commands via DA9E50→vfunc+8 with opcode
// 0xE (arrow projectile). Calling it for daggers creates render commands the
// renderer ignores — this is why SYNTH_DRAW produces log lines but no pixels.
//
// 556780 (kSpriteResSetter) is a single-line setter: [char+0x24C] = value.
// This field is the resource key the renderer reads when drawing the weapon
// overlay layer within the actor's ACT. Overwriting it with an individual
// weapon key BEFORE the render batch runs may be the correct approach.
//
// CORRECT APPROACH (hypothesis): instead of suppressing C55C30 + calling
// DrawWeapon, overwrite [char+0x24C] with the individual weapon resource key
// and let the native renderer draw it through the actor ACT pipeline.
//
// ============================================================================

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>
#include <stdint.h>

// Forward: weapon_overlay.cpp
extern "C" bool WeaponOverlayStart(HMODULE);
extern "C" void WeaponOverlayStop();

namespace {

// ---- target addresses (image base 0x00400000, ASLR off) -------------------
static constexpr DWORD kImageBase        = 0x00400000;
static constexpr DWORD kWeaponTypeFunc   = 0x00D72D30; // combined/individual type
static constexpr DWORD kDrawWeapon       = 0x00C6D9D0; // weapon sprite draw
static constexpr DWORD kSpriteResSetter  = 0x00556780; // writes [char+0x24C]
static constexpr DWORD kRenderModeSetter = 0x00C58EE0; // actor-part dispatcher
static constexpr DWORD kActorSubmit1C    = 0x00C55C30; // actor-part submit vfunc
static constexpr DWORD kLayerIdA         = 0x00C430F0; // layer id helper, active state
static constexpr DWORD kLayerIdB         = 0x00C42C90; // layer id helper, normal state
static constexpr DWORD kActorPathBuilder = 0x00D5B8E0; // actor resource path builder
static constexpr DWORD kMainWeaponPathBuilder = 0x00D5A480; // native weapon path builder
static constexpr DWORD kOffWeaponPathBuilder  = 0x00D58FF0; // native offhand path builder
static constexpr DWORD kGetRenderer      = 0x00A75340; // renderer singleton getter
static constexpr DWORD kGetTexMgr        = 0x00A90350; // texture manager getter
static constexpr DWORD kConvPath         = 0x00A9F030; // path -> engine token
static constexpr DWORD kLoadSurface      = 0x00A8D4A0; // texture manager load(token)
static constexpr DWORD kResourceKeyLookup = 0x00A69EB0; // renderer cache key lookup
static constexpr DWORD kSkipResourceJe9  = 0x00C5917A; // JE over [char+0x24C] path
static constexpr DWORD kSkipResourceJe2  = 0x00C5917F; // JE over [char+0x24C] path
static constexpr DWORD kD8A1D0           = 0x00D8A1D0; // item id -> view id
static constexpr DWORD kGlobalObj        = 0x015FA3C0; // 'this' for weapon fns
static constexpr DWORD kRendererGlobal   = 0x01213338; // 'this' for renderer getter

// stolen-byte lengths (whole instructions, >=5) for each entry trampoline
static constexpr SIZE_T kStolenWTF   = 6; // 55 / 8B EC / 83 EC 08
static constexpr SIZE_T kStolenDraw  = 5; // 55 / 8B EC / 6A FF
static constexpr SIZE_T kStolenSet   = 6; // 55 / 8B EC / 8B 45 08
static constexpr SIZE_T kStolenMode  = 6; // 53 / 8B DC / 83 EC 08
static constexpr SIZE_T kStolenSubmit1C = 6; // 55 / 8B EC / 56 / 8B F1
static constexpr SIZE_T kStolenLayerA = 6; // 55 / 8B EC / 8B 4D 08
static constexpr SIZE_T kStolenLayerB = 7; // 55 / 8B EC / 51 / 8B 45 08
static constexpr SIZE_T kStolenPathBuilder = 10; // 55 / 8B EC / 6A FF / 68 imm32
static constexpr SIZE_T kStolenWeaponPathBuilder = 10; // 55 / 8B EC / 6A FF / 68 imm32
static constexpr SIZE_T kStolenResourceLookup = 6; // 55 / 8B EC / 8B 51 10

// ---- module state ---------------------------------------------------------
static HMODULE g_module = nullptr;
static DWORD   g_base   = 0;

static bool  g_unloading = false; // set on DLL_PROCESS_DETACH, hooks bail out
static bool  g_log       = false;  // BOH_DUALWPN_LOG
static bool  g_replace   = false;  // BOH_DUALWPN_REPLACE
static bool  g_offhand   = false;  // BOH_DUALWPN_OFFHAND
static bool  g_force_single_layer = false; // BOH_DUALWPN_FORCE_SINGLE_LAYER
static bool  g_force_single_mode = false;  // BOH_DUALWPN_FORCE_SINGLE_MODE
static bool  g_trace_actor_paths = false;  // BOH_DUALWPN_TRACE_ACTOR_PATHS
static bool  g_trace_resource_keys = false; // BOH_DUALWPN_TRACE_RESOURCE_KEYS
static bool  g_trace_weapon_paths = false; // BOH_DUALWPN_TRACE_WEAPON_PATHS
static bool  g_preload_weapon_paths = false; // BOH_DUALWPN_PRELOAD_WEAPON_PATHS
static bool  g_alias_resource_keys = false; // BOH_DUALWPN_ALIAS_RESOURCE_KEYS
static bool  g_synth_weapon_paths = false; // BOH_DUALWPN_SYNTH_WEAPON_PATHS
static bool  g_auto_synth_visual = false; // BOH_DUALWPN_AUTO_SYNTH_VISUAL
static bool  g_suppress_native_submit = false; // BOH_DUALWPN_SUPPRESS_NATIVE_SUBMIT
static bool  g_synth_draw = false; // BOH_DUALWPN_SYNTH_DRAW
static bool  g_force_resource_branch = false; // BOH_DUALWPN_FORCE_RESOURCE_BRANCH
static bool  g_force_resource_key = false; // BOH_DUALWPN_FORCE_RESOURCE_KEY
static DWORD g_log_every = 0;      // BOH_DUALWPN_LOG_EVERY

static BYTE  g_wtf_stolen[16]  = {};
static BYTE  g_draw_stolen[16] = {};
static BYTE  g_set_stolen[16]  = {};
static BYTE  g_mode_stolen[16] = {};
static BYTE  g_submit_stolen[16] = {};
static BYTE  g_layer_a_stolen[16] = {};
static BYTE  g_layer_b_stolen[16] = {};
static BYTE  g_path_stolen[16] = {};
static BYTE  g_main_path_stolen[16] = {};
static BYTE  g_off_path_stolen[16] = {};
static BYTE  g_res_lookup_stolen[16] = {};
static void* g_wtf_tramp  = nullptr;
static void* g_draw_tramp = nullptr;
static void* g_set_tramp  = nullptr;
static void* g_mode_tramp = nullptr;
static void* g_submit_tramp = nullptr;
static void* g_layer_a_tramp = nullptr;
static void* g_layer_b_tramp = nullptr;
static void* g_path_tramp = nullptr;
static void* g_main_path_tramp = nullptr;
static void* g_off_path_tramp = nullptr;
static void* g_res_lookup_tramp = nullptr;

// last-seen values for de-duplicating high-frequency log lines
static DWORD g_last_wtf_main = 0xFFFFFFFF, g_last_wtf_off = 0xFFFFFFFF, g_last_wtf_ret = 0xFFFFFFFF;
static DWORD g_last_draw_res = 0xFFFFFFFF, g_last_draw_arg4 = 0xFFFFFFFF, g_last_draw_self = 0xFFFFFFFF;
static DWORD g_last_set_char = 0xFFFFFFFF, g_last_set_val = 0xFFFFFFFF;
static DWORD g_last_mode = 0xFFFFFFFF, g_last_mode_char = 0xFFFFFFFF;
static DWORD g_last_layer_a_char = 0xFFFFFFFF, g_last_layer_a_mode = 0xFFFFFFFF, g_last_layer_a_id = 0xFFFFFFFF;
static DWORD g_last_layer_b_char = 0xFFFFFFFF, g_last_layer_b_mode = 0xFFFFFFFF, g_last_layer_b_id = 0xFFFFFFFF;
static DWORD g_last_vtbl_char = 0xFFFFFFFF, g_last_vtbl_mode = 0xFFFFFFFF, g_last_vtbl_submit = 0xFFFFFFFF;
static DWORD g_last_slots_char = 0xFFFFFFFF, g_last_slots_mode = 0xFFFFFFFF;
static DWORD g_last_slot_440 = 0xFFFFFFFF, g_last_slot_444 = 0xFFFFFFFF;
static DWORD g_last_slot_4c4 = 0xFFFFFFFF, g_last_slot_4d4 = 0xFFFFFFFF;
static DWORD g_last_slot_4d8 = 0xFFFFFFFF, g_last_slot_24c = 0xFFFFFFFF;
static DWORD g_last_path_caller = 0xFFFFFFFF, g_last_path_code = 0xFFFFFFFF;
static DWORD g_last_path_mode = 0xFFFFFFFF, g_last_path_char = 0xFFFFFFFF;
static char  g_last_path_text[260] = {};
static DWORD g_last_reskey_char = 0xFFFFFFFF, g_last_reskey_mode = 0xFFFFFFFF;
static DWORD g_last_reskey_generic = 0xFFFFFFFF, g_last_reskey_main = 0xFFFFFFFF;
static DWORD g_last_reskey_off = 0xFFFFFFFF, g_last_reskey_generic_obj = 0xFFFFFFFF;
static DWORD g_last_reskey_main_obj = 0xFFFFFFFF, g_last_reskey_off_obj = 0xFFFFFFFF;
static DWORD g_last_weapon_path_caller = 0xFFFFFFFF, g_last_weapon_path_item = 0xFFFFFFFF;
static DWORD g_last_weapon_path_obj = 0xFFFFFFFF;
static char  g_last_weapon_path_text[260] = {};
static DWORD g_last_alias_key = 0xFFFFFFFF, g_last_alias_obj = 0xFFFFFFFF;
static DWORD g_last_synth_item = 0xFFFFFFFF, g_last_synth_obj = 0xFFFFFFFF;
static char  g_last_synth_path[260] = {};
static DWORD g_last_submit_char = 0xFFFFFFFF, g_last_submit_id = 0xFFFFFFFF;
static DWORD g_last_submit_suppressed = 0xFFFFFFFF;
static DWORD g_last_synth_draw_char = 0xFFFFFFFF, g_last_synth_draw_item = 0xFFFFFFFF;
static DWORD g_last_synth_draw_obj = 0xFFFFFFFF;
static volatile LONG g_draw_count = 0;
static volatile LONG g_reentry = 0; // guards the synthetic second draw
static volatile LONG g_render_depth = 0;
static volatile LONG g_synth_draw_depth = 0;

// most recent dual-wield context captured at WeaponTypeFunc
static DWORD g_ctx_main = 0, g_ctx_off = 0, g_ctx_mainView = 0, g_ctx_offView = 0;
static DWORD g_focus_char = 0, g_focus_mode = 0, g_focus_f260 = 0, g_focus_f4c8 = 0;
static DWORD g_active_char = 0, g_active_mode = 0;
static DWORD g_body_path_char = 0;
static char  g_body_path_text[260] = {};

struct WeaponResourceCacheEntry
{
    DWORD item;
    DWORD view;
    DWORD key;
    DWORD object;
    char path[260];
};

static WeaponResourceCacheEntry g_weapon_cache[8] = {};
static DWORD g_weapon_cache_next = 0;

struct SynthAttemptEntry
{
    DWORD key;
    char path[260];
};

static SynthAttemptEntry g_synth_attempts[12] = {};
static DWORD g_synth_attempt_next = 0;

static DWORD va(DWORD address) { return g_base + (address - kImageBase); }

static DWORD field32(void* base, DWORD offset)
{
    return *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(base) + offset);
}

static void write_field32(void* base, DWORD offset, DWORD value)
{
    *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(base) + offset) = value;
}

// ---- logging: DebugView (OutputDebugStringA) ------------------------------
static void out_line(const char* text)
{
    char buf[600];
    int n = wsprintfA(buf, "[DualWeaponSprites] %s\r\n", text);
    (void)n;
    OutputDebugStringA(buf);
}

static void logf(const char* fmt,
                 DWORD a = 0, DWORD b = 0, DWORD c = 0,
                 DWORD d = 0, DWORD e = 0, DWORD f = 0)
{
    if (!g_log)
        return;
    char msg[560];
    // wsprintfA has no %f; floats are logged as raw 0x bit patterns.
    wsprintfA(msg, fmt, a, b, c, d, e, f);
    out_line(msg);
}

static bool env_flag(const char* name, bool dflt)
{
    char v[16] = {};
    DWORD len = GetEnvironmentVariableA(name, v, sizeof(v));
    if (len == 0 || len >= sizeof(v))
        return dflt;
    return !(v[0] == '0' || v[0] == 'n' || v[0] == 'N' ||
             v[0] == 'f' || v[0] == 'F');
}

static DWORD env_num(const char* name, DWORD dflt)
{
    char v[16] = {};
    DWORD len = GetEnvironmentVariableA(name, v, sizeof(v));
    if (len == 0 || len >= sizeof(v))
        return dflt;
    DWORD out = 0;
    for (DWORD i = 0; i < len && v[i] >= '0' && v[i] <= '9'; ++i)
        out = out * 10 + (DWORD)(v[i] - '0');
    return out;
}

// ---- inline hook helpers (entry trampolines) ------------------------------
static bool patch_jmp(DWORD hook_va, void* target, BYTE* stolen,
                      SIZE_T stolen_len, void** trampoline)
{
    BYTE* site = reinterpret_cast<BYTE*>(va(hook_va));
    CopyMemory(stolen, site, stolen_len);

    BYTE* gate = reinterpret_cast<BYTE*>(VirtualAlloc(
        nullptr, stolen_len + 5, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!gate)
        return false;

    CopyMemory(gate, stolen, stolen_len);
    gate[stolen_len] = 0xE9;
    *reinterpret_cast<int32_t*>(gate + stolen_len + 1) =
        static_cast<int32_t>((site + stolen_len) - (gate + stolen_len + 5));
    FlushInstructionCache(GetCurrentProcess(), gate, stolen_len + 5);

    DWORD old = 0;
    if (!VirtualProtect(site, stolen_len, PAGE_EXECUTE_READWRITE, &old))
        return false;
    site[0] = 0xE9;
    *reinterpret_cast<int32_t*>(site + 1) =
        static_cast<int32_t>(reinterpret_cast<BYTE*>(target) - (site + 5));
    for (SIZE_T i = 5; i < stolen_len; ++i)
        site[i] = 0x90;
    FlushInstructionCache(GetCurrentProcess(), site, stolen_len);
    VirtualProtect(site, stolen_len, old, &old);

    *trampoline = gate;
    return true;
}

static bool patch_nop2(DWORD target_va, BYTE expected0, BYTE expected1)
{
    BYTE* site = reinterpret_cast<BYTE*>(va(target_va));
    if (site[0] != expected0 || site[1] != expected1)
        return false;

    DWORD old = 0;
    if (!VirtualProtect(site, 2, PAGE_EXECUTE_READWRITE, &old))
        return false;
    site[0] = 0x90;
    site[1] = 0x90;
    FlushInstructionCache(GetCurrentProcess(), site, 2);
    VirtualProtect(site, 2, old, &old);
    return true;
}

// ---- native function typedefs ---------------------------------------------
// WeaponTypeFunc: ecx = global, 4 stack args, returns AL, RET 0x10.
typedef DWORD(__thiscall* WeaponTypeFn)(void* glob, DWORD a1, DWORD a2,
                                        DWORD mainItem, DWORD offItem);
// DrawWeapon: ecx = renderer, RET 0x10.
typedef int(__thiscall* DrawWeaponFn)(void* self, DWORD body, DWORD res,
                                      DWORD scale, DWORD arg4);
// SpriteResSetter: ecx = char, RET 4.
typedef void(__thiscall* SetResFn)(void* charObj, DWORD value);
// RenderModeSetter: ecx = char, 2 stack args, RET 8.
typedef void(__thiscall* RenderModeFn)(void* charObj, DWORD mode, DWORD arg);
// Actor submit vfunc at vtable +0x1C: ecx = char, RET 0x0C.
typedef void(__thiscall* Submit1CFn)(void* charObj, DWORD id, DWORD a2, DWORD a3);
// Layer id helpers: ecx = char, 1 stack arg, RET 4.
typedef DWORD(__thiscall* LayerIdFn)(void* charObj, DWORD mode);
// Actor path builder: ecx = global, 5 stack args, RET 0x14.
typedef void*(__thiscall* PathBuilderFn)(void* glob, void* outString,
                                         DWORD code, DWORD f260,
                                         DWORD f4c8, DWORD zero);
// Weapon path builders. These return std::string-like outString values.
typedef void*(__thiscall* MainWeaponPathBuilderFn)(void* glob, void* outString,
                                                   DWORD a2, DWORD a3,
                                                   DWORD a4);
typedef void*(__thiscall* OffWeaponPathBuilderFn)(void* glob, void* outString,
                                                  DWORD a2, DWORD a3,
                                                  DWORD a4, DWORD a5);
typedef void*(__thiscall* GetRendererFn)(void* rendererGlobal);
typedef void*(__thiscall* ResourceKeyLookupFn)(void* manager, DWORD key);
typedef void*(__cdecl* GetTexMgrFn)();
typedef void*(__cdecl* ConvPathFn)(const char* path);
typedef void*(__thiscall* LoadSurfaceFn)(void* manager, void* token);
// d8a1d0: ecx = global, 1 stack arg, RET 4.
typedef int(__thiscall* D8Fn)(void* glob, DWORD itemId);

static int d8a1d0(DWORD itemId)
{
    // Pure item-DB lookup + range gate; safe to call read-only. Not hooked.
    return reinterpret_cast<D8Fn>(va(kD8A1D0))(
        reinterpret_cast<void*>(va(kGlobalObj)), itemId);
}

static DWORD type_key_for_view(DWORD view)
{
    if (view == 0 || view == 0xFFFFFFFF)
        return 0;
    return view * 1000000u;
}

static void* current_resource_manager()
{
    void* renderer = reinterpret_cast<GetRendererFn>(va(kGetRenderer))(
        reinterpret_cast<void*>(va(kRendererGlobal)));
    if (!renderer)
        return nullptr;
    return *reinterpret_cast<void**>(reinterpret_cast<BYTE*>(renderer) + 0xCC);
}

static void* lookup_resource_key(DWORD key)
{
    if (key == 0)
        return nullptr;
    void* manager = current_resource_manager();
    if (!manager)
        return nullptr;
    // Deliberately call the live entry. Once the lookup hook is installed this
    // shows the same alias result the native branch would see.
    return reinterpret_cast<ResourceKeyLookupFn>(va(kResourceKeyLookup))(manager, key);
}

static DWORD view_for_item(DWORD item)
{
    if (item == 0)
        return 0;
    if (item == g_ctx_main)
        return g_ctx_mainView;
    if (item == g_ctx_off)
        return g_ctx_offView;
    int view = d8a1d0(item);
    return (view > 0) ? static_cast<DWORD>(view) : 0;
}

static char lower_ascii(char ch)
{
    return (ch >= 'A' && ch <= 'Z') ? static_cast<char>(ch + ('a' - 'A')) : ch;
}

static bool ends_with_ci(const char* text, const char* suffix)
{
    if (!text || !suffix)
        return false;
    int text_len = lstrlenA(text);
    int suffix_len = lstrlenA(suffix);
    if (suffix_len <= 0 || text_len < suffix_len)
        return false;
    const char* start = text + text_len - suffix_len;
    for (int i = 0; i < suffix_len; ++i)
    {
        if (lower_ascii(start[i]) != lower_ascii(suffix[i]))
            return false;
    }
    return true;
}

static DWORD parse_trailing_item_id(const char* path)
{
    if (!path || !path[0])
        return 0;
    int len = lstrlenA(path);
    int dot = len;
    for (int i = len - 1; i >= 0; --i)
    {
        if (path[i] == '.')
        {
            dot = i;
            break;
        }
    }
    int start = dot;
    while (start > 0 && path[start - 1] >= '0' && path[start - 1] <= '9')
        --start;
    if (start == dot || start == 0 || path[start - 1] != '_')
        return 0;

    DWORD value = 0;
    for (int i = start; i < dot; ++i)
        value = value * 10u + static_cast<DWORD>(path[i] - '0');
    return value;
}

static bool any_arg_matches_view(DWORD view, DWORD a2, DWORD a3, DWORD a4, DWORD a5)
{
    if (view == 0 || view == 0xFFFFFFFF)
        return false;
    return a2 == view || a3 == view || a4 == view || a5 == view;
}

static WeaponResourceCacheEntry* find_cached_weapon_by_key(DWORD key)
{
    if (key == 0)
        return nullptr;
    for (DWORD i = 0; i < 8; ++i)
    {
        if (g_weapon_cache[i].key == key && g_weapon_cache[i].object != 0)
            return &g_weapon_cache[i];
    }
    return nullptr;
}

static WeaponResourceCacheEntry* cached_weapon_for_item(DWORD item)
{
    DWORD view = view_for_item(item);
    DWORD key = type_key_for_view(view);
    return find_cached_weapon_by_key(key);
}

static bool has_cached_current_weapon()
{
    if (g_ctx_main != 0 && cached_weapon_for_item(g_ctx_main))
        return true;
    if (g_ctx_off != 0 && cached_weapon_for_item(g_ctx_off))
        return true;
    return false;
}

static DWORD actor_scale_bits(void* charObj)
{
    float scale = *reinterpret_cast<float*>(reinterpret_cast<BYTE*>(charObj) + 0x58) *
                  *reinterpret_cast<float*>(reinterpret_cast<BYTE*>(charObj) + 0x378);
    DWORD bits = 0;
    CopyMemory(&bits, &scale, sizeof(bits));
    return bits;
}

static void synth_draw_item(void* charObj, DWORD item, const char* tag)
{
    if (!g_synth_draw || !charObj || item == 0 || !g_draw_tramp)
        return;
    WeaponResourceCacheEntry* cached = cached_weapon_for_item(item);
    if (!cached || cached->object == 0)
        return;

    void* renderer = reinterpret_cast<GetRendererFn>(va(kGetRenderer))(
        reinterpret_cast<void*>(va(kRendererGlobal)));
    if (!renderer)
        return;

    DWORD body = reinterpret_cast<DWORD>(reinterpret_cast<BYTE*>(charObj) + 0x10);
    DWORD scale = actor_scale_bits(charObj);

    if (reinterpret_cast<DWORD>(charObj) != g_last_synth_draw_char ||
        item != g_last_synth_draw_item ||
        cached->object != g_last_synth_draw_obj)
    {
        g_last_synth_draw_char = reinterpret_cast<DWORD>(charObj);
        g_last_synth_draw_item = item;
        g_last_synth_draw_obj = cached->object;
        logf("SYNTH_DRAW %s char=%08X item=%u view=%u res=%08X",
             reinterpret_cast<DWORD>(tag), reinterpret_cast<DWORD>(charObj),
             item, cached->view, cached->object);
    }

    reinterpret_cast<DrawWeaponFn>(g_draw_tramp)(
        renderer, body, cached->object, scale, 0);
}

static void synth_draw_current_weapons(void* charObj, DWORD mode)
{
    if (!g_synth_draw || !charObj || (mode != 2 && mode != 9))
        return;
    if (InterlockedCompareExchange(&g_synth_draw_depth, 1, 0) != 0)
        return;

    if (g_ctx_main != 0)
        synth_draw_item(charObj, g_ctx_main, "main");
    if (g_ctx_off != 0)
        synth_draw_item(charObj, g_ctx_off, (g_ctx_main == 0) ? "off-only" : "off");

    InterlockedExchange(&g_synth_draw_depth, 0);
}

static void remember_weapon_resource(DWORD item, DWORD view, DWORD object, const char* path)
{
    if (item == 0 || view == 0 || object == 0)
        return;
    DWORD key = type_key_for_view(view);
    if (key == 0)
        return;

    WeaponResourceCacheEntry* entry = find_cached_weapon_by_key(key);
    if (!entry)
    {
        entry = &g_weapon_cache[g_weapon_cache_next % 8];
        g_weapon_cache_next = (g_weapon_cache_next + 1) % 8;
    }

    entry->item = item;
    entry->view = view;
    entry->key = key;
    entry->object = object;
    lstrcpynA(entry->path, path ? path : "", sizeof(entry->path));
}

static void* load_resource_path(const char* path)
{
    if (!path || !path[0])
        return nullptr;
    void* manager = reinterpret_cast<GetTexMgrFn>(va(kGetTexMgr))();
    if (!manager)
        return nullptr;
    void* token = reinterpret_cast<ConvPathFn>(va(kConvPath))(path);
    if (!token)
        return nullptr;
    return reinterpret_cast<LoadSurfaceFn>(va(kLoadSurface))(manager, token);
}

static const char* find_substr(const char* text, const char* needle)
{
    if (!text || !needle || !needle[0])
        return nullptr;
    int textLen = lstrlenA(text);
    int needleLen = lstrlenA(needle);
    if (needleLen > textLen)
        return nullptr;
    for (int i = 0; i <= textLen - needleLen; ++i)
    {
        bool match = true;
        for (int j = 0; j < needleLen; ++j)
        {
            if (text[i + j] != needle[j])
            {
                match = false;
                break;
            }
        }
        if (match)
            return text + i;
    }
    return nullptr;
}

static void copy_range(char* out, DWORD outSize, const char* begin, const char* end)
{
    if (!out || outSize == 0)
        return;
    out[0] = 0;
    if (!begin || !end || end < begin)
        return;
    DWORD len = static_cast<DWORD>(end - begin);
    if (len >= outSize)
        len = outSize - 1;
    for (DWORD i = 0; i < len; ++i)
        out[i] = begin[i];
    out[len] = 0;
}

static void append_text(char* out, DWORD outSize, const char* add)
{
    if (!out || !add || outSize == 0)
        return;
    DWORD len = lstrlenA(out);
    if (len >= outSize - 1)
        return;
    lstrcpynA(out + len, add, outSize - len);
}

static bool split_actor_body_path(const char* path, char* root, DWORD rootSize,
                                  char* body, DWORD bodySize,
                                  char* gender, DWORD genderSize)
{
    // Body paths look like:
    //   <root>\<body-folder>\<gender>\<body>_<gender>.act
    // In this client <body-folder> is EUC-KR bytes displayed as mojibake.
    static const char kBodyMarker[] = "\\\xB8\xF6\xC5\xEB\\";
    const char* marker = find_substr(path, kBodyMarker);
    if (!marker)
        return false;

    copy_range(root, rootSize, path, marker);
    const char* p = marker + lstrlenA(kBodyMarker);
    const char* slash = p;
    while (*slash && *slash != '\\')
        ++slash;
    if (!*slash)
        return false;
    copy_range(gender, genderSize, p, slash);

    const char* file = slash + 1;
    const char* dot = file + lstrlenA(file);
    while (dot > file && *dot != '.')
        --dot;
    if (*dot != '.')
        dot = file + lstrlenA(file);

    const char* us = dot;
    while (us > file && *us != '_')
        --us;
    if (*us != '_')
        return false;
    copy_range(body, bodySize, file, us);
    return root[0] && body[0] && gender[0];
}

static bool build_weapon_act_path(char* out, DWORD outSize,
                                  const char* root, const char* job,
                                  const char* gender, DWORD item)
{
    if (!out || outSize == 0 || !root || !job || !gender || !root[0] || !job[0] || !gender[0])
        return false;
    char itemText[16];
    wsprintfA(itemText, "%u", item);
    out[0] = 0;
    append_text(out, outSize, root);
    append_text(out, outSize, "\\");
    append_text(out, outSize, job);
    append_text(out, outSize, "\\");
    append_text(out, outSize, job);
    append_text(out, outSize, "_");
    append_text(out, outSize, gender);
    append_text(out, outSize, "_");
    append_text(out, outSize, itemText);
    append_text(out, outSize, ".act");
    return true;
}

static bool same_text(const char* a, const char* b)
{
    if (!a || !b)
        return false;
    return lstrcmpA(a, b) == 0;
}

static bool synth_attempt_seen(DWORD key, const char* path)
{
    for (DWORD i = 0; i < 12; ++i)
    {
        if (g_synth_attempts[i].key == key &&
            lstrcmpA(g_synth_attempts[i].path, path) == 0)
            return true;
    }
    SynthAttemptEntry* entry = &g_synth_attempts[g_synth_attempt_next % 12];
    g_synth_attempt_next = (g_synth_attempt_next + 1) % 12;
    entry->key = key;
    lstrcpynA(entry->path, path ? path : "", sizeof(entry->path));
    return false;
}

static bool try_synth_weapon_path(DWORD item, DWORD view, const char* path)
{
    DWORD key = type_key_for_view(view);
    if (key == 0 || !path || !path[0] || find_cached_weapon_by_key(key))
        return key != 0 && find_cached_weapon_by_key(key) != nullptr;
    if (synth_attempt_seen(key, path))
        return false;

    void* object = load_resource_path(path);
    if (object)
        remember_weapon_resource(item, view, reinterpret_cast<DWORD>(object), path);

    if (g_log)
    {
        bool changed = item != g_last_synth_item ||
                       reinterpret_cast<DWORD>(object) != g_last_synth_obj ||
                       lstrcmpA(path, g_last_synth_path) != 0;
        if (changed)
        {
            g_last_synth_item = item;
            g_last_synth_obj = reinterpret_cast<DWORD>(object);
            lstrcpynA(g_last_synth_path, path, sizeof(g_last_synth_path));

            char msg[640];
            wsprintfA(msg, "SynthPath item=%u view=%u key=%08X load=%08X path=\"%s\"",
                      item, view, key, reinterpret_cast<DWORD>(object), path);
            out_line(msg);
        }
    }
    return object != nullptr;
}

static void synth_cache_for_item(DWORD item)
{
    if (!g_synth_weapon_paths || item == 0 || !g_body_path_text[0])
        return;
    DWORD view = view_for_item(item);
    DWORD key = type_key_for_view(view);
    if (view == 0 || key == 0 || find_cached_weapon_by_key(key))
        return;

    char root[160], body[96], gender[16], path[260];
    if (!split_actor_body_path(g_body_path_text, root, sizeof(root),
                               body, sizeof(body), gender, sizeof(gender)))
        return;

    // Assassin Cross body paths in this client use older base Assassin weapon
    // overlay folders. Keep this as bytes so the source file stays ASCII.
    static const char kAssassin[] = "\xBE\xEE\xBC\xBC\xBD\xC5";
    static const char kAssassinCross[] = "\xBE\xEE\xBD\xD8\xBD\xC5\xC5\xA9\xB7\xCE\xBD\xBA";
    if (same_text(body, kAssassinCross) &&
        build_weapon_act_path(path, sizeof(path), root, kAssassin, gender, item) &&
        try_synth_weapon_path(item, view, path))
        return;

    if (build_weapon_act_path(path, sizeof(path), root, body, gender, item) &&
        try_synth_weapon_path(item, view, path))
        return;

    if (build_weapon_act_path(path, sizeof(path), root, kAssassin, gender, item) &&
        try_synth_weapon_path(item, view, path))
        return;

    if (build_weapon_act_path(path, sizeof(path), root, "shadow_cross", gender, item))
        try_synth_weapon_path(item, view, path);
}

static void synth_cache_current_weapons(void* charObj)
{
    if (!g_synth_weapon_paths || !charObj ||
        g_body_path_char != reinterpret_cast<DWORD>(charObj))
        return;
    synth_cache_for_item(g_ctx_main);
    synth_cache_for_item(g_ctx_off);
}

static void trace_resource_keys(void* charObj, DWORD mode, DWORD genericKey,
                                DWORD mainKey, DWORD offKey)
{
    if (!g_log || !g_trace_resource_keys || (mode != 2 && mode != 9))
        return;

    void* genericObj = lookup_resource_key(genericKey);
    void* mainObj = lookup_resource_key(mainKey);
    void* offObj = lookup_resource_key(offKey);

    if ((DWORD)charObj == g_last_reskey_char &&
        mode == g_last_reskey_mode &&
        genericKey == g_last_reskey_generic &&
        mainKey == g_last_reskey_main &&
        offKey == g_last_reskey_off &&
        (DWORD)genericObj == g_last_reskey_generic_obj &&
        (DWORD)mainObj == g_last_reskey_main_obj &&
        (DWORD)offObj == g_last_reskey_off_obj)
        return;

    g_last_reskey_char = (DWORD)charObj;
    g_last_reskey_mode = mode;
    g_last_reskey_generic = genericKey;
    g_last_reskey_main = mainKey;
    g_last_reskey_off = offKey;
    g_last_reskey_generic_obj = (DWORD)genericObj;
    g_last_reskey_main_obj = (DWORD)mainObj;
    g_last_reskey_off_obj = (DWORD)offObj;

    logf("ResourceKeys char=%08X mode=%u generic=%08X->%08X main=%08X->%08X",
         (DWORD)charObj, mode, genericKey, (DWORD)genericObj,
         mainKey, (DWORD)mainObj);
    logf("ResourceKeys2 char=%08X mode=%u off=%08X->%08X mainItem=%u offItem=%u",
         (DWORD)charObj, mode, offKey, (DWORD)offObj, g_ctx_main, g_ctx_off);
}

static void copy_game_string(void* stringObj, char* out, DWORD outSize)
{
    if (!out || outSize == 0)
        return;
    out[0] = 0;
    if (!stringObj)
        return;

    BYTE* s = reinterpret_cast<BYTE*>(stringObj);
    DWORD len = *reinterpret_cast<DWORD*>(s + 0x10);
    DWORD cap = *reinterpret_cast<DWORD*>(s + 0x14);
    const char* src = (cap >= 0x10) ? *reinterpret_cast<const char**>(s)
                                    : reinterpret_cast<const char*>(s);
    if (!src)
        return;

    if (len >= outSize)
        len = outSize - 1;
    for (DWORD i = 0; i < len; ++i)
    {
        unsigned char ch = static_cast<unsigned char>(src[i]);
        out[i] = (ch < 0x20 || ch == 0x7F || ch == '"') ? '?' : src[i];
    }
    out[len] = 0;
}

static void handle_weapon_path_result(const char* tag, DWORD caller,
                                      void* outString,
                                      DWORD a2, DWORD a3,
                                      DWORD a4, DWORD a5)
{
    char path[260];
    copy_game_string(outString, path, sizeof(path));

    DWORD item = parse_trailing_item_id(path);
    DWORD view = view_for_item(item);
    bool is_act = ends_with_ci(path, ".act");
    bool matches_view = any_arg_matches_view(view, a2, a3, a4, a5);
    bool interesting = (item != 0) || matches_view;
    void* object = nullptr;

    if (is_act && item != 0 && matches_view && g_preload_weapon_paths)
    {
        object = load_resource_path(path);
        if (object)
            remember_weapon_resource(item, view, reinterpret_cast<DWORD>(object), path);
    }

    if (g_log && g_trace_weapon_paths)
    {
        bool changed = caller != g_last_weapon_path_caller ||
                       item != g_last_weapon_path_item ||
                       reinterpret_cast<DWORD>(object) != g_last_weapon_path_obj ||
                       lstrcmpA(path, g_last_weapon_path_text) != 0;
        if (changed)
        {
            g_last_weapon_path_caller = caller;
            g_last_weapon_path_item = item;
            g_last_weapon_path_obj = reinterpret_cast<DWORD>(object);
            lstrcpynA(g_last_weapon_path_text, path, sizeof(g_last_weapon_path_text));

            char msg[720];
            wsprintfA(msg,
                      "WeaponPath%s call=%08X args=%u,%u,%u,%u item=%u view=%u act=%u match=%u load=%08X path=\"%s\"",
                      tag, caller, a2, a3, a4, a5, item, view,
                      is_act ? 1u : 0u, matches_view ? 1u : 0u,
                      reinterpret_cast<DWORD>(object), path);
            out_line(msg);
        }
    }
}

static bool is_actor_path_trace_relevant(DWORD caller, DWORD f260, DWORD f4c8)
{
    if (!g_log || !g_trace_actor_paths || g_focus_char == 0)
        return false;
    if (caller < 0x00D30000 || caller > 0x00D43000)
        return false;
    return f260 == g_focus_f260 && f4c8 == g_focus_f4c8;
}

// ---- hooks ----------------------------------------------------------------
static void* __fastcall ResourceKeyLookupHook(void* manager, void* /*edx*/, DWORD key)
{
    void* object = reinterpret_cast<ResourceKeyLookupFn>(g_res_lookup_tramp)(manager, key);
    if (object || !g_alias_resource_keys)
        return object;

    WeaponResourceCacheEntry* cached = find_cached_weapon_by_key(key);
    if (!cached)
        return nullptr;

    // 0x00A69EB0 is also seen in unrelated manager contexts in this client.
    // Only alias lookups from the renderer resource manager used by 0x00C58EE0.
    if (manager != current_resource_manager())
        return nullptr;

    if (key != g_last_alias_key || cached->object != g_last_alias_obj)
    {
        g_last_alias_key = key;
        g_last_alias_obj = cached->object;
        logf("ResourceAlias key=%08X -> %08X item=%u view=%u",
             key, cached->object, cached->item, cached->view);
    }
    return reinterpret_cast<void*>(cached->object);
}

static DWORD __fastcall WeaponTypeHook(void* glob, void* /*edx*/,
                                       DWORD a1, DWORD a2,
                                       DWORD mainItem, DWORD offItem)
{
    if (g_unloading)
        return reinterpret_cast<WeaponTypeFn>(g_wtf_tramp)(glob, a1, a2, mainItem, offItem);

    DWORD ret = reinterpret_cast<WeaponTypeFn>(g_wtf_tramp)(
        glob, a1, a2, mainItem, offItem);

    int mainView = d8a1d0(mainItem);
    int offView  = (offItem != 0) ? d8a1d0(offItem) : -1;
    g_ctx_main = mainItem; g_ctx_off = offItem;
    g_ctx_mainView = (DWORD)mainView; g_ctx_offView = (DWORD)offView;

    bool changed = (mainItem != g_last_wtf_main) ||
                   (offItem != g_last_wtf_off) ||
                   ((ret & 0xFF) != g_last_wtf_ret);
    if (changed)
    {
        g_last_wtf_main = mainItem; g_last_wtf_off = offItem;
        g_last_wtf_ret = ret & 0xFF;
        logf("WeaponType main=%u off=%u -> type=%u  mainView=%d offView=%d combined=%u",
             mainItem, offItem, ret & 0xFF, (DWORD)mainView, (DWORD)offView,
             ((ret & 0xFF) >= 25 && (ret & 0xFF) <= 30) ? 1u : 0u);
    }

    if (g_replace)
    {
        DWORD baseType = ret & 0xFF;
        int repl = 0;

        if (baseType >= 25 && baseType <= 30)
        {
            // Combined dual-wield type → use main hand's individual view
            repl = (mainView > 0) ? mainView : offView;
        }
        else if (offItem != 0 && baseType >= 1 && baseType <= 24 && mainView > 24)
        {
            // Dual-wield with base class type → use item-specific view from WeaponNameTable
            // e.g. type 1 (SHORTSWORD/_단검) → type 34 (Zeny_Knife/_1238) or 45 (Twin_Edge_B/_13412)
            repl = mainView;
        }

        if (repl > 0)
        {
            if (changed)
                logf("REPLACE type=%u -> view=%d (main=%u view=%d off=%u view=%d)",
                     baseType, repl, mainItem, mainView, offItem, offView);
            return (DWORD)(repl & 0xFF) | (ret & 0xFFFFFF00);
        }
    }
    return ret;
}

static int __fastcall DrawWeaponHook(void* self, void* /*edx*/, DWORD body,
                                     DWORD res, DWORD scale, DWORD arg4)
{
    LONG count = InterlockedIncrement(&g_draw_count);

    bool changed = (res != g_last_draw_res) || (arg4 != g_last_draw_arg4) ||
                   ((DWORD)self != g_last_draw_self);
    bool heartbeat = (g_log_every != 0) && ((DWORD)count % g_log_every == 0);
    if (changed || heartbeat)
    {
        g_last_draw_res = res; g_last_draw_arg4 = arg4;
        g_last_draw_self = (DWORD)self;
        logf("DrawWeapon self=%08X body=%08X res=%08X scaleBits=%08X arg4=%u  n=%u",
             (DWORD)self, body, res, scale, arg4, (DWORD)count);
    }

    int r = reinterpret_cast<DrawWeaponFn>(g_draw_tramp)(self, body, res, scale, arg4);

    // Experimental: prove a synthetic second draw pass is stable. We re-issue
    // the SAME contract (arg4 forced to 0 = native main-hand semantics). This
    // is a stability/feasibility probe; it does not yet resolve the off-hand
    // resource (the tracer output tells us whether/when that becomes available).
    if (g_offhand && g_ctx_off != 0 && InterlockedCompareExchange(&g_reentry, 1, 0) == 0)
    {
        if (changed)
            logf("OFFHAND probe: second DrawWeapon self=%08X res=%08X arg4=0 (main=%u off=%u)",
                 (DWORD)self, res, g_ctx_main, g_ctx_off);
        reinterpret_cast<DrawWeaponFn>(g_draw_tramp)(self, body, res, scale, 0);
        InterlockedExchange(&g_reentry, 0);
    }
    return r;
}

static void __fastcall SetResHook(void* charObj, void* /*edx*/, DWORD value)
{
    if ((DWORD)charObj != g_last_set_char || value != g_last_set_val)
    {
        g_last_set_char = (DWORD)charObj; g_last_set_val = value;
        logf("SetWeaponRes char=%08X [+0x24C]=%08X (ctx main=%u off=%u)",
             (DWORD)charObj, value, g_ctx_main, g_ctx_off);
    }
    reinterpret_cast<SetResFn>(g_set_tramp)(charObj, value);
}

static void __fastcall Submit1CHook(void* charObj, void* /*edx*/,
                                    DWORD id, DWORD a2, DWORD a3)
{
    if (g_unloading) {
        reinterpret_cast<Submit1CFn>(g_submit_tramp)(charObj, id, a2, a3);
        return;
    }
    bool weaponMode = (g_render_depth > 0 &&
                       g_active_char == reinterpret_cast<DWORD>(charObj) &&
                       (g_active_mode == 9) &&
                       (id == 0x50 || id == 0x58));
    bool suppress = g_suppress_native_submit && weaponMode && has_cached_current_weapon();

    if (reinterpret_cast<DWORD>(charObj) != g_last_submit_char ||
        id != g_last_submit_id ||
        (suppress ? 1u : 0u) != g_last_submit_suppressed)
    {
        g_last_submit_char = reinterpret_cast<DWORD>(charObj);
        g_last_submit_id = id;
        g_last_submit_suppressed = suppress ? 1u : 0u;
        logf("Submit1C char=%08X mode=%u id=%u a2=%u a3=%u suppress=%u",
             reinterpret_cast<DWORD>(charObj), g_active_mode,
             id, a2, a3, suppress ? 1u : 0u);
    }

    if (suppress)
        return;

    reinterpret_cast<Submit1CFn>(g_submit_tramp)(charObj, id, a2, a3);
}

static void __fastcall RenderModeHook(void* charObj, void* /*edx*/,
                                      DWORD mode, DWORD arg)
{
    if (g_unloading) {
        reinterpret_cast<RenderModeFn>(g_mode_tramp)(charObj, mode, arg);
        return;
    }

    DWORD effectiveMode = mode;
    DWORD vtbl = *reinterpret_cast<DWORD*>(charObj);
    DWORD submit = *reinterpret_cast<DWORD*>(vtbl + 0x1C);
    DWORD stateFn = *reinterpret_cast<DWORD*>(vtbl + 0xD8);
    DWORD slot440 = field32(charObj, 0x440);
    DWORD slot444 = field32(charObj, 0x444);
    DWORD slot4c4 = field32(charObj, 0x4C4);
    DWORD slot4d4 = field32(charObj, 0x4D4);
    DWORD slot4d8 = field32(charObj, 0x4D8) & 0xFF;
    DWORD slot24c = field32(charObj, 0x24C);
    DWORD f260 = field32(charObj, 0x260);
    DWORD f4c8 = field32(charObj, 0x4C8);
    DWORD mainKey = type_key_for_view(g_ctx_mainView);
    DWORD offKey = type_key_for_view(g_ctx_offView);
    DWORD forcedKey = 0;
    DWORD original24c = slot24c;

    if (mode == 2 || mode == 9)
    {
        g_focus_char = (DWORD)charObj;
        g_focus_mode = mode;
        g_focus_f260 = f260;
        g_focus_f4c8 = f4c8;
        synth_cache_current_weapons(charObj);
        trace_resource_keys(charObj, mode, slot24c, mainKey, offKey);
    }

    if (mode != g_last_mode || (DWORD)charObj != g_last_mode_char)
    {
        g_last_mode = mode; g_last_mode_char = (DWORD)charObj;
        logf("RenderMode char=%08X mode=%u arg=%u  combinedDual=%u",
             (DWORD)charObj, mode, arg, (mode == 9) ? 1u : 0u);
    }

    if ((mode == 2 || mode == 9) &&
        ((DWORD)charObj != g_last_vtbl_char ||
         mode != g_last_vtbl_mode ||
         submit != g_last_vtbl_submit))
    {
        g_last_vtbl_char = (DWORD)charObj;
        g_last_vtbl_mode = mode;
        g_last_vtbl_submit = submit;
        logf("ActorVtbl char=%08X mode=%u vtbl=%08X submit1C=%08X stateD8=%08X arg=%u",
             (DWORD)charObj, mode, vtbl, submit, stateFn, arg);
    }

    if ((mode == 2 || mode == 9) &&
        ((DWORD)charObj != g_last_slots_char ||
         mode != g_last_slots_mode ||
         slot440 != g_last_slot_440 ||
         slot444 != g_last_slot_444 ||
         slot4c4 != g_last_slot_4c4 ||
         slot4d4 != g_last_slot_4d4 ||
         slot4d8 != g_last_slot_4d8 ||
         slot24c != g_last_slot_24c))
    {
        g_last_slots_char = (DWORD)charObj;
        g_last_slots_mode = mode;
        g_last_slot_440 = slot440;
        g_last_slot_444 = slot444;
        g_last_slot_4c4 = slot4c4;
        g_last_slot_4d4 = slot4d4;
        g_last_slot_4d8 = slot4d8;
        g_last_slot_24c = slot24c;
        logf("ActorSlots char=%08X mode=%u +440=%u +444=%u +4C4=%u +4D4=%u",
             (DWORD)charObj, mode, slot440, slot444, slot4c4, slot4d4);
        logf("ActorSlots2 char=%08X mode=%u +24C=%08X +260=%u +4C8=%u +4D8=%u",
             (DWORD)charObj, mode, slot24c, f260, f4c8, slot4d8);
    }

    if (g_force_single_mode && mode == 9)
    {
        effectiveMode = 2;
        logf("FORCE_SINGLE_MODE char=%08X mode=9 -> mode=2 (main=%u off=%u)",
             (DWORD)charObj, g_ctx_main, g_ctx_off);
    }

    if ((g_force_resource_key || g_auto_synth_visual) && (mode == 2 || mode == 9))
    {
        bool autoOnly = !g_force_resource_key && g_auto_synth_visual;
        if (g_ctx_main != 0 && mainKey != 0 &&
            (!autoOnly || find_cached_weapon_by_key(mainKey)))
            forcedKey = mainKey;
        else if (g_ctx_off != 0 && offKey != 0 &&
                 (!autoOnly || find_cached_weapon_by_key(offKey)))
            forcedKey = offKey;

        if (forcedKey != 0 && forcedKey != slot24c)
        {
            write_field32(charObj, 0x24C, forcedKey);
            logf("FORCE_RESOURCE_KEY char=%08X mode=%u +24C=%08X -> %08X",
                 (DWORD)charObj, mode, slot24c, forcedKey);
        }
    }

    DWORD prevChar = g_active_char;
    DWORD prevMode = g_active_mode;
    g_active_char = (DWORD)charObj;
    g_active_mode = mode;
    InterlockedIncrement(&g_render_depth);
    reinterpret_cast<RenderModeFn>(g_mode_tramp)(charObj, effectiveMode, arg);
    InterlockedDecrement(&g_render_depth);
    g_active_char = prevChar;
    g_active_mode = prevMode;

    synth_draw_current_weapons(charObj, mode);

    if (forcedKey != 0 && forcedKey != original24c)
        write_field32(charObj, 0x24C, original24c);
}

static DWORD __fastcall LayerIdAHook(void* charObj, void* /*edx*/, DWORD mode)
{
    if (g_unloading)
        return reinterpret_cast<LayerIdFn>(g_layer_a_tramp)(charObj, mode);
    DWORD id = reinterpret_cast<LayerIdFn>(g_layer_a_tramp)(charObj, mode);
    if ((DWORD)charObj != g_last_layer_a_char ||
        mode != g_last_layer_a_mode ||
        id != g_last_layer_a_id)
    {
        g_last_layer_a_char = (DWORD)charObj;
        g_last_layer_a_mode = mode;
        g_last_layer_a_id = id;
        logf("LayerIdA char=%08X mode=%u -> id=%u (main=%u off=%u)",
             (DWORD)charObj, mode, id, g_ctx_main, g_ctx_off);
    }
    return id;
}

static DWORD __fastcall LayerIdBHook(void* charObj, void* /*edx*/, DWORD mode)
{
    if (g_unloading)
        return reinterpret_cast<LayerIdFn>(g_layer_b_tramp)(charObj, mode);
    DWORD id = reinterpret_cast<LayerIdFn>(g_layer_b_tramp)(charObj, mode);
    bool changed = ((DWORD)charObj != g_last_layer_b_char ||
                    mode != g_last_layer_b_mode ||
                    id != g_last_layer_b_id);
    if (changed)
    {
        g_last_layer_b_char = (DWORD)charObj;
        g_last_layer_b_mode = mode;
        g_last_layer_b_id = id;
        logf("LayerIdB char=%08X mode=%u -> id=%u (main=%u off=%u)",
             (DWORD)charObj, mode, id, g_ctx_main, g_ctx_off);
    }

    if (g_force_single_layer && mode == 9 && id == 0x58)
    {
        if (changed)
            logf("FORCE_SINGLE_LAYER char=%08X mode=9 id=88 -> id=80 (mainView=%u offView=%u)",
                 (DWORD)charObj, g_ctx_mainView, g_ctx_offView);
        return 0x50;
    }
    return id;
}

static void* __fastcall PathBuilderHook(void* glob, void* /*edx*/,
                                        void* outString, DWORD code,
                                        DWORD f260, DWORD f4c8, DWORD zero)
{
    void* ret = reinterpret_cast<PathBuilderFn>(g_path_tramp)(
        glob, outString, code, f260, f4c8, zero);

    DWORD caller = reinterpret_cast<DWORD>(_ReturnAddress()) - 5;
    if (is_actor_path_trace_relevant(caller, f260, f4c8))
    {
        char path[260];
        copy_game_string(outString, path, sizeof(path));
        char root[160], body[96], gender[16];
        if (split_actor_body_path(path, root, sizeof(root),
                                  body, sizeof(body), gender, sizeof(gender)))
        {
            g_body_path_char = g_focus_char;
            lstrcpynA(g_body_path_text, path, sizeof(g_body_path_text));
        }

        DWORD mode = (g_render_depth > 0 && g_active_char == g_focus_char)
            ? g_active_mode
            : g_focus_mode;
        bool changed = caller != g_last_path_caller ||
                       code != g_last_path_code ||
                       mode != g_last_path_mode ||
                       g_focus_char != g_last_path_char ||
                       lstrcmpA(path, g_last_path_text) != 0;
        if (changed)
        {
            g_last_path_caller = caller;
            g_last_path_code = code;
            g_last_path_mode = mode;
            g_last_path_char = g_focus_char;
            lstrcpynA(g_last_path_text, path, sizeof(g_last_path_text));

            char msg[620];
            wsprintfA(msg,
                      "ActorPath call=%08X char=%08X mode=%u code=%u f260=%u f4C8=%u path=\"%s\"",
                      caller, g_focus_char, mode, code, f260, f4c8, path);
            out_line(msg);
        }
    }
    return ret;
}

static void* __fastcall MainWeaponPathHook(void* glob, void* /*edx*/,
                                           void* outString, DWORD a2,
                                           DWORD a3, DWORD a4)
{
    void* ret = reinterpret_cast<MainWeaponPathBuilderFn>(g_main_path_tramp)(
        glob, outString, a2, a3, a4);
    DWORD caller = reinterpret_cast<DWORD>(_ReturnAddress()) - 5;
    handle_weapon_path_result("Main", caller, outString, a2, a3, a4, 0);
    return ret;
}

static void* __fastcall OffWeaponPathHook(void* glob, void* /*edx*/,
                                          void* outString, DWORD a2,
                                          DWORD a3, DWORD a4, DWORD a5)
{
    void* ret = reinterpret_cast<OffWeaponPathBuilderFn>(g_off_path_tramp)(
        glob, outString, a2, a3, a4, a5);
    DWORD caller = reinterpret_cast<DWORD>(_ReturnAddress()) - 5;
    handle_weapon_path_result("Off", caller, outString, a2, a3, a4, a5);
    return ret;
}

// ---- installer ------------------------------------------------------------
static DWORD WINAPI install_thread(LPVOID)
{
    Sleep(150);
    g_base = reinterpret_cast<DWORD>(GetModuleHandleA(nullptr));

    logf("installer start base=%08X log=%u replace=%u offhand=%u every=%u",
         g_base, g_log ? 1 : 0, g_replace ? 1 : 0, g_offhand ? 1 : 0, g_log_every);
    logf("installer flags forceSingleLayer=%u",
         g_force_single_layer ? 1 : 0);
    logf("installer flags forceSingleMode=%u",
         g_force_single_mode ? 1 : 0);
    logf("installer flags traceActorPaths=%u",
         g_trace_actor_paths ? 1 : 0);

    // Skip EXE patching — GDI overlay does not need render hooks.
    // Inline JMPs crash on process exit because the DLL unloads before
    // the EXE's patched code stops executing. Re-enable with caution.
    bool skipHooks = env_flag("BOH_DUALWPN_NO_HOOKS", true);
    if (skipHooks) {
        logf("installer: EXE hooks SKIPPED (BOH_DUALWPN_NO_HOOKS=1)");
    } else {
    logf("installer flags traceResourceKeys=%u forceResourceBranch=%u forceResourceKey=%u",
         g_trace_resource_keys ? 1 : 0,
         g_force_resource_branch ? 1 : 0,
         g_force_resource_key ? 1 : 0);
    logf("installer flags traceWeaponPaths=%u preloadWeaponPaths=%u aliasResourceKeys=%u",
         g_trace_weapon_paths ? 1 : 0,
         g_preload_weapon_paths ? 1 : 0,
         g_alias_resource_keys ? 1 : 0);
    logf("installer flags synthWeaponPaths=%u autoSynthVisual=%u",
         g_synth_weapon_paths ? 1 : 0,
         g_auto_synth_visual ? 1 : 0);
    logf("installer flags suppressNativeSubmit=%u synthDraw=%u",
         g_suppress_native_submit ? 1 : 0,
         g_synth_draw ? 1 : 0);
    logf("installer flags submitHook=%u",
         g_suppress_native_submit ? 1 : 0);

    bool ok1 = patch_jmp(kWeaponTypeFunc, reinterpret_cast<void*>(&WeaponTypeHook),
                         g_wtf_stolen, kStolenWTF, &g_wtf_tramp);
    bool ok2 = patch_jmp(kDrawWeapon, reinterpret_cast<void*>(&DrawWeaponHook),
                         g_draw_stolen, kStolenDraw, &g_draw_tramp);
    bool ok3 = patch_jmp(kSpriteResSetter, reinterpret_cast<void*>(&SetResHook),
                         g_set_stolen, kStolenSet, &g_set_tramp);
    bool ok4 = patch_jmp(kRenderModeSetter, reinterpret_cast<void*>(&RenderModeHook),
                         g_mode_stolen, kStolenMode, &g_mode_tramp);
    bool ok5 = true;
    bool submitHook = g_suppress_native_submit;
    if (submitHook)
        ok5 = patch_jmp(kActorSubmit1C, reinterpret_cast<void*>(&Submit1CHook),
                        g_submit_stolen, kStolenSubmit1C, &g_submit_tramp);
    bool ok6 = patch_jmp(kLayerIdA, reinterpret_cast<void*>(&LayerIdAHook),
                         g_layer_a_stolen, kStolenLayerA, &g_layer_a_tramp);
    bool ok7 = patch_jmp(kLayerIdB, reinterpret_cast<void*>(&LayerIdBHook),
                         g_layer_b_stolen, kStolenLayerB, &g_layer_b_tramp);
    bool ok8 = patch_jmp(kActorPathBuilder, reinterpret_cast<void*>(&PathBuilderHook),
                         g_path_stolen, kStolenPathBuilder, &g_path_tramp);
    bool ok9 = patch_jmp(kMainWeaponPathBuilder, reinterpret_cast<void*>(&MainWeaponPathHook),
                         g_main_path_stolen, kStolenWeaponPathBuilder, &g_main_path_tramp);
    bool ok10 = patch_jmp(kOffWeaponPathBuilder, reinterpret_cast<void*>(&OffWeaponPathHook),
                         g_off_path_stolen, kStolenWeaponPathBuilder, &g_off_path_tramp);
    bool ok11 = patch_jmp(kResourceKeyLookup, reinterpret_cast<void*>(&ResourceKeyLookupHook),
                          g_res_lookup_stolen, kStolenResourceLookup, &g_res_lookup_tramp);
    bool ok12 = true;
    bool ok13 = true;
    if (g_force_resource_branch || g_auto_synth_visual)
    {
        ok12 = patch_nop2(kSkipResourceJe9, 0x74, 0x52);
        ok13 = patch_nop2(kSkipResourceJe2, 0x74, 0x4D);
        logf("installer resource branch patch je9=%u je2=%u",
             ok12 ? 1 : 0, ok13 ? 1 : 0);
    }

    logf("installer done WeaponType=%u DrawWeapon=%u SetRes=%u RenderMode=%u Submit1C=%u LayerA=%u",
         ok1 ? 1 : 0, ok2 ? 1 : 0, ok3 ? 1 : 0,
         ok4 ? 1 : 0, (submitHook && ok5) ? 1 : 0, ok6 ? 1 : 0);
    logf("installer done LayerB=%u ActorPath=%u MainPath=%u OffPath=%u ResourceLookup=%u",
         ok7 ? 1 : 0, ok8 ? 1 : 0, ok9 ? 1 : 0,
         ok10 ? 1 : 0, ok11 ? 1 : 0);

    } // else (!skipHooks)

    WeaponOverlayStart(g_module);

    return 0;
}

static BOOL on_dll_main(HMODULE module, DWORD reason, LPVOID reserved)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        g_module = module;
        DisableThreadLibraryCalls(module);
        g_log       = env_flag("BOH_DUALWPN_LOG", false);
        g_replace   = env_flag("BOH_DUALWPN_REPLACE", false);
        g_offhand   = env_flag("BOH_DUALWPN_OFFHAND", false);
        g_force_single_layer = env_flag("BOH_DUALWPN_FORCE_SINGLE_LAYER", false);
        g_force_single_mode = env_flag("BOH_DUALWPN_FORCE_SINGLE_MODE", false);
        g_trace_actor_paths = env_flag("BOH_DUALWPN_TRACE_ACTOR_PATHS", false);
        g_trace_resource_keys = env_flag("BOH_DUALWPN_TRACE_RESOURCE_KEYS", false);
        g_trace_weapon_paths = env_flag("BOH_DUALWPN_TRACE_WEAPON_PATHS", false);
        g_preload_weapon_paths = env_flag("BOH_DUALWPN_PRELOAD_WEAPON_PATHS", false);
        g_alias_resource_keys = env_flag("BOH_DUALWPN_ALIAS_RESOURCE_KEYS", false);
        g_synth_weapon_paths = env_flag("BOH_DUALWPN_SYNTH_WEAPON_PATHS", false);
        g_auto_synth_visual = env_flag("BOH_DUALWPN_AUTO_SYNTH_VISUAL", false);
        g_suppress_native_submit = env_flag("BOH_DUALWPN_SUPPRESS_NATIVE_SUBMIT", false);
        g_synth_draw = env_flag("BOH_DUALWPN_SYNTH_DRAW", false);
        g_force_resource_branch = env_flag("BOH_DUALWPN_FORCE_RESOURCE_BRANCH", false);
        g_force_resource_key = env_flag("BOH_DUALWPN_FORCE_RESOURCE_KEY", false);
        g_log_every = env_num("BOH_DUALWPN_LOG_EVERY", 0);
        HANDLE t = CreateThread(nullptr, 0, install_thread, nullptr, 0, nullptr);
        if (t)
            CloseHandle(t);
    }
    if (reason == DLL_PROCESS_DETACH)
    {
        g_unloading = true;  // neutralize all hooks immediately
        if (reserved == nullptr)
            WeaponOverlayStop();
    }
    return TRUE;
}

} // namespace

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved)
{
    return on_dll_main(module, reason, reserved);
}

// WARP import-table anchor. The real work happens in DllMain via install_thread.
extern "C" __declspec(dllexport) void WeaponSpriteInit(void)
{
}
