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
//   BOH_DUALWPN_LOG      (default off) : trace pipeline to DebugView
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
//   BOH_DUALWPN_TRACE_ACTOR_PATHS (default off):
//                                        trace actor path-builder calls that
//                                        match the current weapon actor.
//   BOH_DUALWPN_TRACE_RESOURCE_KEYS (default off):
//                                        trace native resource-cache lookup
//                                        results for generic/specific keys.
//   BOH_DUALWPN_TRACE_WEAPON_PATHS (default off):
//                                        trace native weapon path-builder output.
//   BOH_DUALWPN_PRELOAD_WEAPON_PATHS (default off):
//                                        load matching item-specific ACT paths
//                                        as soon as native builders produce them.
//   BOH_DUALWPN_ALIAS_RESOURCE_KEYS (default off):
//                                        if native cache lookup misses a specific
//                                        weapon key, return the preloaded object.
//   BOH_DUALWPN_SYNTH_WEAPON_PATHS (default off):
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
//   BOH_DUALWPN_NO_HOOKS (default ON):
//                                        skip all EXE inline hooks; use the DLL
//                                        as a custom renderer host only.
//   BOH_DUALWPN_OVERLAY (default ON):
//                                        start the layered-window renderer
//                                        harness from weapon_overlay.cpp.
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
// DEAD-END FLAG COMBINATION (verified weapon_9.log):
//   BOH_DUALWPN_AUTO_SYNTH_VISUAL=1        <- NOPs JEs + injects weapon key
//   BOH_DUALWPN_SUPPRESS_NATIVE_SUBMIT=1   <- blocks C55C30 for mode 9
//   BOH_DUALWPN_SYNTH_DRAW=1               <- manual DrawWeapon post-trampoline
//
//   Frame 1: cold cache -> combined sprite (suppress=0)
//   Frame 2: SynthPath loads ACT, alias created, suppress=1, SYNTH_DRAW fires
//   Frame 3+: both main/off cached, suppress=1, SYNTH_DRAW main+off every frame
//
// Result: SYNTH_DRAW calls fire, but C6D9D0 is an arrow/projectile path for
// this case. It creates the wrong render command and regressed attack/movement
// state. Do not use this route as a fix.
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
// Renderer pivot: keep native hooks opt-in for read-only investigation, and use
// this DLL as the host for a custom renderer. The current harness is a layered
// window; the next renderer step is decoding SPR/ACT frames and positioning
// them from actor screen coordinates.
//
// ============================================================================

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <intrin.h>
#include <stdint.h>

#include "boh_features.h"

// Forward: weapon_overlay.cpp
extern "C" bool WeaponOverlayStart(HMODULE);
extern "C" void WeaponOverlayStop();
extern "C" void WeaponOverlayUpdateState(DWORD charObj, DWORD mode,
                                          DWORD mainItem, DWORD offItem,
                                          DWORD mainView, DWORD offView);
extern "C" void WeaponOverlayClearState();

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
static constexpr DWORD kMainWeaponPathBuilder = 0x00D5A480; // GetJobName (MISLABELED: job/body-name helper, NOT a weapon path builder; verified vs 07-16 fn table)
static constexpr DWORD kOffWeaponPathBuilder  = 0x00D58FF0; // adjacent job/name helper (MISLABELED: NOT an offhand path builder)
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
static constexpr DWORD kWeaponLoader     = 0x00D3F4F0; // weapon sprite loader (vtable +0x58)
static constexpr DWORD kWeaponSetup      = 0x00D3E850; // weapon setup (vtable +0x50, calls D3F4F0)
static constexpr DWORD kWeaponLoaderSlots[5] = { // .rdata vtable +0x58 slots holding D3F4F0
    0x01093BA0, 0x01093C9C, 0x01093D98, 0x01094400, 0x01094868
};
static constexpr DWORD kWeaponSetupSlots[5] = { // .rdata vtable +0x50 slots holding D3E850
    0x01093B98, 0x01093C94, 0x01093D90, 0x010943F8, 0x01094860
};

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
static bool  g_overlay_renderer = true; // BOH_DUALWPN_OVERLAY
static bool  g_state_hooks = true; // BOH_DUALWPN_STATE_HOOKS
static bool  g_placement_trace = true; // BOH_DUALWPN_PLACEMENT_TRACE
static DWORD g_log_every = 0;      // BOH_DUALWPN_LOG_EVERY
static bool  g_native_bind = false; // BOH_DUALWPN_NATIVE_BIND (D3F4F0 per-hand swap)

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

static bool g_wtf_hooked = false, g_draw_hooked = false, g_set_hooked = false;
static bool g_mode_hooked = false, g_submit_hooked = false;
static bool g_layer_a_hooked = false, g_layer_b_hooked = false;
static bool g_path_hooked = false, g_main_path_hooked = false;
static bool g_off_path_hooked = false, g_res_lookup_hooked = false;
static DWORD g_wloader_slot_old[5] = {}; // original D3F4F0 vtable slot values
static DWORD g_wsetup_slot_old[5] = {};  // original D3E850 vtable slot values
static bool  g_wloader_hooked = false;
static bool  g_wsetup_hooked  = false;
static DWORD g_last_bind_char = 0xFFFFFFFF, g_last_bind_main = 0xFFFFFFFF, g_last_bind_off = 0xFFFFFFFF, g_last_bind_type = 0xFFFFFFFF;

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
static DWORD g_last_submit_mode = 0xFFFFFFFF, g_last_submit_a2 = 0xFFFFFFFF;
static DWORD g_last_submit_a3 = 0xFFFFFFFF, g_last_submit_x = 0xFFFFFFFF;
static DWORD g_last_submit_y = 0xFFFFFFFF, g_last_submit_z = 0xFFFFFFFF;
static DWORD g_last_submit_frame = 0xFFFFFFFF, g_last_submit_scale = 0xFFFFFFFF;
static DWORD g_last_submit_caller = 0xFFFFFFFF, g_last_submit_part = 0xFFFFFFFF;
static DWORD g_last_submit_part2 = 0xFFFFFFFF;
static DWORD g_last_synth_draw_char = 0xFFFFFFFF, g_last_synth_draw_item = 0xFFFFFFFF;
static DWORD g_last_synth_draw_obj = 0xFFFFFFFF;
static volatile LONG g_draw_count = 0;
static volatile LONG g_reentry = 0; // guards the synthetic second draw
static volatile LONG g_render_depth = 0;
static volatile LONG g_synth_draw_depth = 0;

// most recent dual-wield context captured at WeaponTypeFunc
static DWORD g_ctx_main = 0, g_ctx_off = 0, g_ctx_mainView = 0, g_ctx_offView = 0;
static void* g_bind_charObj = nullptr;   // cached by D3F4F0_VHook, used by WeaponTypeHook for deferred remap
static bool  g_bind_done = false;        // dedup: only fire deferred remap once per equip
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

static void log_alwaysf(const char* fmt,
                        DWORD a = 0, DWORD b = 0, DWORD c = 0,
                        DWORD d = 0, DWORD e = 0, DWORD f = 0)
{
    char msg[560];
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
    {
        VirtualFree(gate, 0, MEM_RELEASE);
        return false;
    }
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

static void restore_patch(DWORD hook_va, const BYTE* stolen,
                          SIZE_T stolen_len, bool hooked)
{
    if (!hooked || !stolen || stolen_len == 0)
        return;

    BYTE* site = reinterpret_cast<BYTE*>(va(hook_va));
    DWORD old = 0;
    if (!VirtualProtect(site, stolen_len, PAGE_EXECUTE_READWRITE, &old))
        return;
    CopyMemory(site, stolen, stolen_len);
    FlushInstructionCache(GetCurrentProcess(), site, stolen_len);
    VirtualProtect(site, stolen_len, old, &old);
}

static void restore_all_patches()
{
    restore_patch(kWeaponTypeFunc, g_wtf_stolen, kStolenWTF, g_wtf_hooked);
    restore_patch(kDrawWeapon, g_draw_stolen, kStolenDraw, g_draw_hooked);
    restore_patch(kSpriteResSetter, g_set_stolen, kStolenSet, g_set_hooked);
    restore_patch(kRenderModeSetter, g_mode_stolen, kStolenMode, g_mode_hooked);
    restore_patch(kActorSubmit1C, g_submit_stolen, kStolenSubmit1C, g_submit_hooked);
    restore_patch(kLayerIdA, g_layer_a_stolen, kStolenLayerA, g_layer_a_hooked);
    restore_patch(kLayerIdB, g_layer_b_stolen, kStolenLayerB, g_layer_b_hooked);
    restore_patch(kActorPathBuilder, g_path_stolen, kStolenPathBuilder, g_path_hooked);
    restore_patch(kMainWeaponPathBuilder, g_main_path_stolen,
                  kStolenWeaponPathBuilder, g_main_path_hooked);
    restore_patch(kOffWeaponPathBuilder, g_off_path_stolen,
                  kStolenWeaponPathBuilder, g_off_path_hooked);
    restore_patch(kResourceKeyLookup, g_res_lookup_stolen,
                  kStolenResourceLookup, g_res_lookup_hooked);
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

// forward decl for deferred remap (defined later in native-bind section)
static void call_real_weapon_loader(void* charObj, int weaponType);

static DWORD __fastcall WeaponTypeHook(void* glob, void* /*edx*/,
                                       DWORD a1, DWORD a2,
                                       DWORD mainItem, DWORD offItem)
{
    if (g_unloading)
        return 0;  // process exiting — bail, don't touch trampoline

    DWORD ret = reinterpret_cast<WeaponTypeFn>(g_wtf_tramp)(
        glob, a1, a2, mainItem, offItem);

    int mainView = d8a1d0(mainItem);
    int offView  = (offItem != 0) ? d8a1d0(offItem) : -1;
    g_ctx_main = mainItem; g_ctx_off = offItem;
    g_ctx_mainView = (DWORD)mainView; g_ctx_offView = (DWORD)offView;

    // Forward to overlay renderer (zero-charObj, D72D30 doesn't have charObj)
    if (mainItem != g_last_wtf_main || offItem != g_last_wtf_off) {
        WeaponOverlayUpdateState(0, 9, mainItem, offItem, (DWORD)mainView, (DWORD)offView);
    }

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
        // a1/a2 diagnostic: does either carry the actor (loader charObj)? If so we
        // can key the per-hand views per-character instead of a flaky global.
        logf("WeaponType glob=%08X a1=%08X a2=%08X",
             reinterpret_cast<DWORD>(glob), a1, a2);
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
    DWORD activeMode = (g_render_depth > 0 &&
                        g_active_char == reinterpret_cast<DWORD>(charObj))
        ? g_active_mode
        : g_focus_mode;
    bool weaponMode = (g_render_depth > 0 &&
                       g_active_char == reinterpret_cast<DWORD>(charObj) &&
                       (g_active_mode == 9) &&
                       (id == 0x50 || id == 0x58));
    bool tracePlacement = g_placement_trace &&
                           (activeMode == 2 || activeMode == 9) &&
                           (id == 0x50 || id == 0x58);
    DWORD caller = reinterpret_cast<DWORD>(_ReturnAddress()) - 5;
    bool suppress = g_suppress_native_submit && weaponMode && has_cached_current_weapon();

    if (reinterpret_cast<DWORD>(charObj) != g_last_submit_char ||
        activeMode != g_last_submit_mode ||
        id != g_last_submit_id ||
        a2 != g_last_submit_a2 ||
        a3 != g_last_submit_a3 ||
        (suppress ? 1u : 0u) != g_last_submit_suppressed)
    {
        g_last_submit_char = reinterpret_cast<DWORD>(charObj);
        g_last_submit_mode = activeMode;
        g_last_submit_id = id;
        g_last_submit_a2 = a2;
        g_last_submit_a3 = a3;
        g_last_submit_suppressed = suppress ? 1u : 0u;
        logf("Submit1C char=%08X mode=%u id=%u a2=%u a3=%u suppress=%u",
             reinterpret_cast<DWORD>(charObj), activeMode,
             id, a2, a3, suppress ? 1u : 0u);
    }

    if (suppress)
        return;

    reinterpret_cast<Submit1CFn>(g_submit_tramp)(charObj, id, a2, a3);

    if (tracePlacement)
    {
        DWORD x = field32(charObj, 0x10);
        DWORD y = field32(charObj, 0x14);
        DWORD z = field32(charObj, 0x18);
        DWORD partId = field32(charObj, 0x34);
        DWORD partId2 = field32(charObj, 0x38);
        DWORD frameOrArg = field32(charObj, 0x6C);
        DWORD scale = field32(charObj, 0x58);
        if (reinterpret_cast<DWORD>(charObj) != g_last_submit_char ||
            activeMode != g_last_submit_mode ||
            id != g_last_submit_id ||
            caller != g_last_submit_caller ||
            x != g_last_submit_x ||
            y != g_last_submit_y ||
            z != g_last_submit_z ||
            partId != g_last_submit_part ||
            partId2 != g_last_submit_part2 ||
            frameOrArg != g_last_submit_frame ||
            scale != g_last_submit_scale)
        {
            g_last_submit_char = reinterpret_cast<DWORD>(charObj);
            g_last_submit_mode = activeMode;
            g_last_submit_id = id;
            g_last_submit_caller = caller;
            g_last_submit_x = x;
            g_last_submit_y = y;
            g_last_submit_z = z;
            g_last_submit_part = partId;
            g_last_submit_part2 = partId2;
            g_last_submit_frame = frameOrArg;
            g_last_submit_scale = scale;
            char msg[640];
            wsprintfA(msg,
                      "NativeWeaponPart caller=%08X char=%08X mode=%u submitId=%u a2=%u a3=%u part=%u/%u frameArg=%u pos=%08X,%08X,%08X scale=%08X main=%u off=%u",
                      caller, reinterpret_cast<DWORD>(charObj), activeMode, id,
                      a2, a3, partId, partId2, frameOrArg, x, y, z, scale,
                      g_ctx_main, g_ctx_off);
            out_line(msg);
        }
    }
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
    DWORD overlayMain = slot440;
    DWORD overlayOff = slot444;
    DWORD overlayMainView = overlayMain ? (DWORD)d8a1d0(overlayMain) : 0;
    DWORD overlayOffView = overlayOff ? (DWORD)d8a1d0(overlayOff) : 0;
    DWORD mainKey = type_key_for_view(g_ctx_mainView);
    DWORD offKey = type_key_for_view(g_ctx_offView);
    DWORD forcedKey = 0;
    DWORD original24c = slot24c;

    if (mode == 2 || mode == 9)
    {
        if (g_overlay_renderer && g_state_hooks)
        {
            WeaponOverlayUpdateState((DWORD)charObj, mode, overlayMain,
                                     overlayOff, overlayMainView,
                                     overlayOffView);
        }
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

// ---- native per-hand weapon bind (D3F4F0 vtable hook) ---------------------
// D3F4F0 (__thiscall: ecx=charObj, stack=weaponType, ret 4) loads the weapon
// sprite handles into the char object, using ONE type for BOTH hands -> dual
// wield shows the combined sprite. We swap the 5 actor vtable slots (+0x58)
// for a shim that re-drives the native loader twice so each hand resolves to
// its own item's sprite. Equip-time only, never per frame.
//   main handle  = *( *(char+0x4AC) + 4 )
//   offhand slot = (*(int**)(char+0x4B8))[1]
//   type [char+0x438]   main item [char+0x440]   off item [char+0x444]
typedef void (__thiscall* WeaponLoaderFn)(void* charObj, int weaponType);

static void call_real_weapon_loader(void* charObj, int weaponType)
{
    reinterpret_cast<WeaponLoaderFn>(va(kWeaponLoader))(charObj, weaponType);
}

// ---- D3E850 vtable hook (weapon setup, +0x50) ----------------------------
// D3E850(charObj, jobCode, p3, weaponType, p5, itemId, p7..p11, p12)
// It writes [char+0x438]=weaponType, [char+0x444]=itemId, then calls D3F4F0.
// This hook fires BEFORE D3F4F0 and populates g_ctx from the real item IDs
// so the D3F4F0_VHook 2-pass remap has the per-hand types ready.
typedef void (__thiscall* WeaponSetupFn)(void* charObj,
    int jobCode, void* p3, int weaponType, int p5,
    int itemId, int p7, int p8, int p9, int p10, int p11, void* p12);

static void call_real_weapon_setup(void* charObj,
    int jobCode, void* p3, int weaponType, int p5,
    int itemId, int p7, int p8, int p9, int p10, int p11, void* p12)
{
    reinterpret_cast<WeaponSetupFn>(va(kWeaponSetup))(
        charObj, jobCode, p3, weaponType, p5,
        itemId, p7, p8, p9, p10, p11, p12);
}

static void __fastcall D3E850_VHook(void* charObj, void* /*edx*/,
    int jobCode, void* p3, int weaponType, int p5,
    int itemId, int p7, int p8, int p9, int p10, int p11, void* p12)
{
    if (g_unloading) return;
    if (!g_unloading && g_native_bind && charObj) {
        DWORD mainItem = field32(charObj, 0x440);
        DWORD offItem  = static_cast<DWORD>(itemId);
        g_ctx_main = mainItem;
        g_ctx_off  = offItem;
        g_ctx_mainView = mainItem ? static_cast<DWORD>(d8a1d0(mainItem)) : 0;
        g_ctx_offView  = offItem  ? static_cast<DWORD>(d8a1d0(offItem))  : 0;
    }
    call_real_weapon_setup(charObj, jobCode, p3, weaponType, p5,
                           itemId, p7, p8, p9, p10, p11, p12);
}

// ---- D3F4F0 vtable hook (weapon loader, +0x58) ---------------------------
static void __fastcall D3F4F0_VHook(void* charObj, void* /*edx*/, int weaponType)
{
    DWORD vhookCaller = reinterpret_cast<DWORD>(_ReturnAddress());
    void* vhookRetSlot = _AddressOfReturnAddress();
    if (g_unloading || !g_native_bind || charObj == nullptr) {
        if (!g_unloading)
            call_real_weapon_loader(charObj, weaponType);
        return;
    }

    // Cache the FIRST charObj only — D3F4F0 fires on multiple actor parts
    // (weapon, body, head).  Only the first one seen in a session is the
    // weapon loader; caching later ones would target body/head and corrupt
    // hairstyle/appearance.
    if (!g_bind_charObj) {
       g_bind_charObj = charObj;
       g_bind_done = false;
    }

    // Per-hand TYPES. Primary source = the views captured at WeaponTypeFunc
    // (D72D30), which runs with the live main/off items right before this
    // loader. Fallback = char item fields (frequently 0 on the loader object).
    DWORD ctxMain = g_ctx_main, ctxOff = g_ctx_off;
    int   mainType = static_cast<int>(g_ctx_mainView);
    int   offType  = static_cast<int>(g_ctx_offView);
    if (mainType <= 0) { DWORD it = field32(charObj, 0x440); mainType = it ? d8a1d0(it) : 0; }
    if (offType  <= 0) { DWORD it = field32(charObj, 0x444); offType  = it ? d8a1d0(it) : 0; }
    // Dual = both hands have distinct individual types.  g_ctx is now
    // populated by D3E850_VHook (vtable +0x50) which fires BEFORE us,
    // so the WeaponType combined-range gate is unnecessary.
    bool  dual = mainType > 0 && offType > 0 && mainType != offType;

    // Decision lines (deduped vs per-frame spam): source values, resolved types,
    // and a loader-object field window to locate items if g_ctx is unavailable.
    bool logNow = g_log &&
        (reinterpret_cast<DWORD>(charObj) != g_last_bind_char ||
         ctxMain != g_last_bind_main || ctxOff != g_last_bind_off ||
         static_cast<DWORD>(weaponType) != g_last_bind_type);
    if (logNow) {
        g_last_bind_char = reinterpret_cast<DWORD>(charObj);
        g_last_bind_main = ctxMain;
        g_last_bind_off  = ctxOff;
        g_last_bind_type = static_cast<DWORD>(weaponType);
        logf("VHook char=%08X type=%u ctxM=%u ctxO=%u mT=%u oT=%u",
             reinterpret_cast<DWORD>(charObj), static_cast<DWORD>(weaponType),
             ctxMain, ctxOff, static_cast<DWORD>(mainType),
             static_cast<DWORD>(offType));
        logf("VHook f440=%u f444=%u f448=%u f44C=%u dual=%u",
             field32(charObj, 0x440), field32(charObj, 0x444),
             field32(charObj, 0x448), field32(charObj, 0x44C),
             dual ? 1u : 0u);
        // Scan the loader object for the test items (13412 main / 1238 off) to
        // locate their offset here. If neither appears, the per-hand items are
        // NOT on this object and must come from the combiner/per-char capture.
        __try {
            for (DWORD off = 0; off <= 0x600; off += 4) {
                DWORD v = field32(charObj, off);
                if (v == 13412u || v == 1238u)
                    logf("VHook scan char=%08X off=%03X val=%u",
                         reinterpret_cast<DWORD>(charObj), off, v);
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {}
    }

    // Unconditional caller capture — identify upstream combiner
    {
        static DWORD lastCaller = 0;
        if (vhookCaller != lastCaller) {
            lastCaller = vhookCaller;
            logf("VHook caller=%08X", vhookCaller);
            __try {
                DWORD* sp = reinterpret_cast<DWORD*>(vhookRetSlot);
                for (int i = 0; i < 200; ++i)
                    if (sp[i] == 13412u || sp[i] == 1238u)
                        logf("VHook stk[+%03X]=%u", i * 4, sp[i]);
            } __except (EXCEPTION_EXECUTE_HANDLER) {}
        }
    }

    if (!dual) {
        call_real_weapon_loader(charObj, weaponType);
        return;
    }

    // 2-pass remap. SEH-guarded purely as insurance against an unexpected
    // object layout; the gate above already makes a fault improbable.
    bool  ok = false;
    int   phase = 0;
    DWORD offHandle = 0;
    __try {
        call_real_weapon_loader(charObj, offType);          // PASS 1: off-hand
        phase = 1;
        DWORD* offArr = *reinterpret_cast<DWORD**>(
            reinterpret_cast<BYTE*>(charObj) + 0x4B8);
        if (offArr != nullptr) {
            offHandle = offArr[1];
            offArr[1] = 0;                                   // shield keeper
            call_real_weapon_loader(charObj, mainType);      // PASS 2: main
            phase = 2;
            offArr = *reinterpret_cast<DWORD**>(
                reinterpret_cast<BYTE*>(charObj) + 0x4B8);
            if (offArr != nullptr)
                offArr[1] = offHandle;                       // restore keeper
            write_field32(charObj, 0x438, static_cast<DWORD>(weaponType));
            ok = true;
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER) {
        ok = false;
    }

    if (!ok) {
        if (phase >= 1)
            call_real_weapon_loader(charObj, weaponType);
        if (logNow)
            logf("VHook remap FAILED phase=%u", static_cast<DWORD>(phase));
        return;
    }

    if (logNow)
        logf("VHook remap OK char=%08X mainT=%u offT=%u offHandle=%08X",
             reinterpret_cast<DWORD>(charObj), static_cast<DWORD>(mainType),
             static_cast<DWORD>(offType), offHandle);
}

// ---- D3E850 vtable slot swapper ------------------------------------------
static void install_weapon_setup_vhook()
{
    DWORD expected = va(kWeaponSetup);
    int patched = 0;
    for (int i = 0; i < 5; ++i) {
        DWORD* slot = reinterpret_cast<DWORD*>(va(kWeaponSetupSlots[i]));
        DWORD oldProt = 0;
        if (!VirtualProtect(slot, sizeof(DWORD), PAGE_READWRITE, &oldProt)) {
            log_alwaysf("NativeBind: Setup VirtualProtect failed slot=%08X",
                        reinterpret_cast<DWORD>(slot));
            continue;
        }
        if (*slot != expected) {
            log_alwaysf("NativeBind: Setup slot=%08X holds %08X != expected %08X, SKIP",
                        reinterpret_cast<DWORD>(slot), *slot, expected);
            VirtualProtect(slot, sizeof(DWORD), oldProt, &oldProt);
            continue;
        }
        g_wsetup_slot_old[i] = *slot;
        *slot = reinterpret_cast<DWORD>(&D3E850_VHook);
        VirtualProtect(slot, sizeof(DWORD), oldProt, &oldProt);
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(DWORD));
        ++patched;
    }
    g_wsetup_hooked = (patched > 0);
    log_alwaysf("NativeBind: installed setup vhook on %u/5 slots -> %08X",
                static_cast<DWORD>(patched),
                reinterpret_cast<DWORD>(&D3E850_VHook));
}

static void restore_weapon_setup_vhook()
{
    if (!g_wsetup_hooked) return;
    DWORD hookAddr = reinterpret_cast<DWORD>(&D3E850_VHook);
    for (int i = 0; i < 5; ++i) {
        if (g_wsetup_slot_old[i] == 0) continue;
        DWORD* slot = reinterpret_cast<DWORD*>(va(kWeaponSetupSlots[i]));
        DWORD oldProt = 0;
        if (!VirtualProtect(slot, sizeof(DWORD), PAGE_READWRITE, &oldProt)) continue;
        if (*slot == hookAddr) *slot = g_wsetup_slot_old[i];
        VirtualProtect(slot, sizeof(DWORD), oldProt, &oldProt);
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(DWORD));
        g_wsetup_slot_old[i] = 0;
    }
    g_wsetup_hooked = false;
}

// ---- D3F4F0 vtable slot swapper ------------------------------------------
static void install_weapon_loader_vhook()
{
    DWORD expected = va(kWeaponLoader);
    int patched = 0;
    for (int i = 0; i < 5; ++i) {
        DWORD* slot = reinterpret_cast<DWORD*>(va(kWeaponLoaderSlots[i]));
        DWORD oldProt = 0;
        if (!VirtualProtect(slot, sizeof(DWORD), PAGE_READWRITE, &oldProt)) {
            log_alwaysf("NativeBind: VirtualProtect failed slot=%08X",
                        reinterpret_cast<DWORD>(slot));
            continue;
        }
        if (*slot != expected) {
            log_alwaysf("NativeBind: slot=%08X holds %08X != expected %08X, SKIP",
                        reinterpret_cast<DWORD>(slot), *slot, expected);
            VirtualProtect(slot, sizeof(DWORD), oldProt, &oldProt);
            continue;
        }
        g_wloader_slot_old[i] = *slot;
        *slot = reinterpret_cast<DWORD>(&D3F4F0_VHook);
        VirtualProtect(slot, sizeof(DWORD), oldProt, &oldProt);
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(DWORD));
        ++patched;
    }
    g_wloader_hooked = (patched > 0);
    log_alwaysf("NativeBind: installed vtable hook on %u/5 slots -> %08X",
                static_cast<DWORD>(patched),
                reinterpret_cast<DWORD>(&D3F4F0_VHook));
}

static void restore_weapon_loader_vhook()
{
    if (!g_wloader_hooked)
        return;
    DWORD hookAddr = reinterpret_cast<DWORD>(&D3F4F0_VHook);
    for (int i = 0; i < 5; ++i) {
        if (g_wloader_slot_old[i] == 0)
            continue;
        DWORD* slot = reinterpret_cast<DWORD*>(va(kWeaponLoaderSlots[i]));
        DWORD oldProt = 0;
        if (!VirtualProtect(slot, sizeof(DWORD), PAGE_READWRITE, &oldProt))
            continue;
        if (*slot == hookAddr)                   // only undo our own write
            *slot = g_wloader_slot_old[i];
        VirtualProtect(slot, sizeof(DWORD), oldProt, &oldProt);
        FlushInstructionCache(GetCurrentProcess(), slot, sizeof(DWORD));
        g_wloader_slot_old[i] = 0;
    }
    g_wloader_hooked = false;
}

// ---- installer ------------------------------------------------------------
static DWORD WINAPI install_thread(LPVOID)
{
    Sleep(150);
    g_base = reinterpret_cast<DWORD>(GetModuleHandleA(nullptr));

    log_alwaysf("installer start base=%08X log=%u replace=%u offhand=%u every=%u",
                g_base, g_log ? 1 : 0, g_replace ? 1 : 0,
                g_offhand ? 1 : 0, g_log_every);
    logf("installer flags forceSingleLayer=%u",
         g_force_single_layer ? 1 : 0);
    logf("installer flags forceSingleMode=%u",
         g_force_single_mode ? 1 : 0);
    logf("installer flags traceActorPaths=%u",
         g_trace_actor_paths ? 1 : 0);
    log_alwaysf("installer flags placementTrace=%u",
                g_placement_trace ? 1 : 0);

    // Skip old mutating native experiments. The overlay still needs the
    // read-only state feed, and placement trace can hook C55C30 for evidence.
    bool skipHooks = env_flag("BOH_DUALWPN_NO_HOOKS", true);
    bool stateHooks = g_overlay_renderer && g_state_hooks;
    log_alwaysf("installer flags noHooks=%u overlay=%u stateHooks=%u",
                skipHooks ? 1 : 0, g_overlay_renderer ? 1 : 0,
                stateHooks ? 1 : 0);
    if (g_overlay_renderer && !stateHooks)
        log_alwaysf("state feed OFF: BOH_DUALWPN_STATE_HOOKS=0; overlay can heartbeat but cannot draw actor weapons");
    if (skipHooks) {
        log_alwaysf("installer: experiment hooks SKIPPED (BOH_DUALWPN_NO_HOOKS=1)");
        if (stateHooks)
        {
            bool ok1 = patch_jmp(kWeaponTypeFunc,
                                 reinterpret_cast<void*>(&WeaponTypeHook),
                                 g_wtf_stolen, kStolenWTF, &g_wtf_tramp);
            bool ok4 = patch_jmp(kRenderModeSetter,
                                  reinterpret_cast<void*>(&RenderModeHook),
                                  g_mode_stolen, kStolenMode, &g_mode_tramp);
            bool ok5 = true;
            if (g_placement_trace)
                ok5 = patch_jmp(kActorSubmit1C,
                                reinterpret_cast<void*>(&Submit1CHook),
                                g_submit_stolen, kStolenSubmit1C,
                                &g_submit_tramp);
            g_wtf_hooked = ok1;
            g_mode_hooked = ok4;
            g_submit_hooked = g_placement_trace && ok5;
            log_alwaysf("installer done StateWeaponType=%u StateRenderMode=%u StateSubmit1C=%u",
                        ok1 ? 1 : 0, ok4 ? 1 : 0,
                        g_submit_hooked ? 1 : 0);
        }
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
         (g_suppress_native_submit || g_placement_trace) ? 1 : 0);

    bool ok1 = patch_jmp(kWeaponTypeFunc, reinterpret_cast<void*>(&WeaponTypeHook),
                         g_wtf_stolen, kStolenWTF, &g_wtf_tramp);
    bool ok2 = patch_jmp(kDrawWeapon, reinterpret_cast<void*>(&DrawWeaponHook),
                         g_draw_stolen, kStolenDraw, &g_draw_tramp);
    bool ok3 = patch_jmp(kSpriteResSetter, reinterpret_cast<void*>(&SetResHook),
                         g_set_stolen, kStolenSet, &g_set_tramp);
    bool ok4 = patch_jmp(kRenderModeSetter, reinterpret_cast<void*>(&RenderModeHook),
                         g_mode_stolen, kStolenMode, &g_mode_tramp);
    bool ok5 = true;
    bool submitHook = g_suppress_native_submit || g_placement_trace;
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

    g_wtf_hooked = ok1;
    g_draw_hooked = ok2;
    g_set_hooked = ok3;
    g_mode_hooked = ok4;
    g_submit_hooked = submitHook && ok5;
    g_layer_a_hooked = ok6;
    g_layer_b_hooked = ok7;
    g_path_hooked = ok8;
    g_main_path_hooked = ok9;
    g_off_path_hooked = ok10;
    g_res_lookup_hooked = ok11;

    logf("installer done WeaponType=%u DrawWeapon=%u SetRes=%u RenderMode=%u Submit1C=%u LayerA=%u",
         ok1 ? 1 : 0, ok2 ? 1 : 0, ok3 ? 1 : 0,
         ok4 ? 1 : 0, (submitHook && ok5) ? 1 : 0, ok6 ? 1 : 0);
    logf("installer done LayerB=%u ActorPath=%u MainPath=%u OffPath=%u ResourceLookup=%u",
         ok7 ? 1 : 0, ok8 ? 1 : 0, ok9 ? 1 : 0,
         ok10 ? 1 : 0, ok11 ? 1 : 0);

    } // else (!skipHooks)

    // All EXE hooks (inline + vtable) permanently removed.
    // But WeaponTypeHook is safe — it returns 0 on g_unloading and
    // its inline patch is restored by the OS on process exit.
    // It populates g_ctx which the overlay reads for per-hand items.

    if (!g_wtf_hooked) {
        g_wtf_hooked = patch_jmp(kWeaponTypeFunc,
                                 reinterpret_cast<void*>(&WeaponTypeHook),
                                 g_wtf_stolen, kStolenWTF, &g_wtf_tramp);
        log_alwaysf("WeaponType feed hook=%u", g_wtf_hooked ? 1u : 0u);
    }

    if (g_overlay_renderer)
        WeaponOverlayStart(g_module);
    else
        log_alwaysf("installer: overlay renderer disabled");

    return 0;
}

static BOOL on_dll_main(HMODULE module, DWORD reason, LPVOID reserved)
{
    if (reason == DLL_PROCESS_ATTACH)
    {
        if (!BohLicense::CheckAndLog(FEATURE_WEAPON_SPRITE, L"weapon_sprite"))
            return FALSE;

        g_module = module;
        DisableThreadLibraryCalls(module);
        out_line("attach");
        g_log       = true;   // env_flag("BOH_DUALWPN_LOG", false);
        g_replace   = false;  // env_flag("BOH_DUALWPN_REPLACE", false);
        g_offhand   = false;  // env_flag("BOH_DUALWPN_OFFHAND", false);
        g_force_single_layer = false;
        g_force_single_mode = false;
        g_trace_actor_paths = false;
        g_trace_resource_keys = false;
        g_trace_weapon_paths = false;
        g_preload_weapon_paths = false;
        g_alias_resource_keys = false;
        g_synth_weapon_paths = false;
        g_auto_synth_visual = false;
        g_suppress_native_submit = false;
        g_synth_draw = false;
        g_force_resource_branch = false;
        g_force_resource_key = false;
        g_overlay_renderer = true;   // HARDCODED — env vars broken
        g_state_hooks = false;       // no inline hooks → no crash
        g_placement_trace = false;
        g_log_every = 0;
        g_native_bind = false;       // no vtable hooks → no crash
        HANDLE t = CreateThread(nullptr, 0, install_thread, nullptr, 0, nullptr);
        if (t)
            CloseHandle(t);
    }
    if (reason == DLL_PROCESS_DETACH)
    {
        g_unloading = true;
        WeaponOverlayStop();
        WeaponOverlayClearState();
        // No hooks to restore — zero patching, zero crashes.
        return TRUE;
    }
    return TRUE;
}

} // namespace

// State poller called from overlay thread.  Reads weapon state directly
// from game memory — no hooks, no crashes.
extern "C" DWORD poll_weapon_state()
{
    // Quick re-read of cached character
    static DWORD lastChar = 0;
    static DWORD lastItems[2] = {0, 0};

    if (lastChar) {
        __try {
            DWORD m = *reinterpret_cast<DWORD*>(lastChar + 0x440);
            DWORD o = *reinterpret_cast<DWORD*>(lastChar + 0x444);
            DWORD mode = *reinterpret_cast<DWORD*>(lastChar + 0x1C);
            if (m != lastItems[0] || o != lastItems[1]) {
                lastItems[0] = m; lastItems[1] = o;
                char buf[128];
                sprintf_s(buf, "poll: char=%08X mode=%u items=%u/%u", lastChar, mode, m, o);
                OutputDebugStringA(buf);
                WeaponOverlayUpdateState(lastChar, mode, m, o,
                    m ? static_cast<int>(reinterpret_cast<int(*)(DWORD)>(0x00D8A1D0)(m)) : 0,
                    o ? static_cast<int>(reinterpret_cast<int(*)(DWORD)>(0x00D8A1D0)(o)) : 0);
            }
        } __except(EXCEPTION_EXECUTE_HANDLER) {
            lastChar = 0;
        }
        return 1;
    }

    // Approach: read the global object used by D72D30 (0x015FA3C0).
    // D72D30 is called with (glob, a1, a2, mainItem, offItem) — the items
    // are passed from the character render dispatch.  Try to find a char*
    // in the global's nearby fields, then read items from there.
    // Fallback: try well-known Ragnarok globals for player character.
    DWORD glob = 0x015FA3C0;
    DWORD found = 0;
    __try {
        // Try offsets 0x00-0x200 in the global for something that looks
        // like a character pointer (heap address in 0x0C000000-0x60000000)
        DWORD* g = reinterpret_cast<DWORD*>(glob);
        for (int off = 0; off < 0x200; off += 4) {
            DWORD candidate = g[off/4];
            if (candidate < 0x0C000000 || candidate > 0x60000000) continue;
            __try {
                DWORD v0 = *reinterpret_cast<DWORD*>(candidate + 0x440);
                DWORD v1 = *reinterpret_cast<DWORD*>(candidate + 0x444);
                if ((v0 == 13412 && v1 == 1238) || (v0 == 1238 && v1 == 13412)) {
                    lastChar = candidate;
                    lastItems[0] = v0; lastItems[1] = v1;
                    found = candidate;
                    break;
                }
            } __except(EXCEPTION_EXECUTE_HANDLER) {}
        }
    } __except(EXCEPTION_EXECUTE_HANDLER) {}

    if (!found) {
        // Fallback: try reading the player object from a known Ragnarok global.
        // In many clients, the local player pointer is near the renderer globals.
        // Try 0x015FA3C0 + 0x?? as direct player pointer.
        static const DWORD knownGlobs[] = {
            0x015FA3C0, 0x01213338, 0x012291C0, 0x015FB9A4,
            0x015FB9C8, 0x015FFD78, 0x015FF9BC, 0x015FFA54
        };
        for (int gidx = 0; gidx < 8 && !found; ++gidx) {
            __try {
                DWORD candidate = *reinterpret_cast<DWORD*>(knownGlobs[gidx]);
                if (candidate < 0x0C000000 || candidate > 0x60000000) continue;
                DWORD v0 = *reinterpret_cast<DWORD*>(candidate + 0x440);
                DWORD v1 = *reinterpret_cast<DWORD*>(candidate + 0x444);
                if ((v0 == 13412 && v1 == 1238) || (v0 == 1238 && v1 == 13412)) {
                    lastChar = candidate;
                    lastItems[0] = v0; lastItems[1] = v1;
                    found = candidate;
                }
            } __except(EXCEPTION_EXECUTE_HANDLER) {}
        }
    }

    if (found) {
        char buf[128];
        sprintf_s(buf, "poll: FOUND char at %08X items=%u/%u", found, lastItems[0], lastItems[1]);
        OutputDebugStringA(buf);
    }
    return found ? 1 : 0;
}

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved)
{
    return on_dll_main(module, reason, reserved);
}

// WARP import-table anchor. The real work happens in DllMain via install_thread.
extern "C" __declspec(dllexport) void WeaponSpriteInit(void)
{
}
