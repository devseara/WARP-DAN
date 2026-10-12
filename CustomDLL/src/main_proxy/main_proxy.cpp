// main_proxy.cpp — Central DllMain + DirectDraw forwarding for boh.dll
// ============================================================================
// This is the sole DllMain entry point. It:
// 1. Initializes the license system (boh_features.h)
// 2. Loads the real DirectDraw from System32 (for ddraw.dll proxy support)
// 3. Calls each feature module's init function
// 4. DirectDraw exports forward to the real System32 ddraw.dll
//
// Feature source files:
//   extended_name.cpp    - EXTN transport + name substitution state
//   player_name_text_bridge.cpp - EXTN/player-name GDI bridge
//   colored_itemname.cpp - DEPRECATED historical renderer; never built
//   fps_ping.cpp          — FPS/Ping overlay (FpsPingOverlay/)
//   npc_name_overlay.cpp  — NPC name overlay (npc_name_overlay/)

#include <windows.h>
#include <cstdio>

// Feature license system
#include "boh_features.h"
#include "dll_integrity/dll_integrity.h"

#if BOH_EXTENDED_NAMES || BOH_PLAYER_NAME_COLORS
#define BOH_HAS_TEXT_VISUAL 1
#else
#define BOH_HAS_TEXT_VISUAL 0
#endif

#if BOH_HAS_TEXT_VISUAL
#include "text_visual/text_visual_bridge.h"
#endif

// ============================================================================
//  DirectDraw forwarding globals
// ============================================================================

HMODULE g_hRealDDraw = nullptr;
FARPROC g_pDirectDrawCreateEx = nullptr;
FARPROC g_pDirectDrawEnumerateExA = nullptr;

// ============================================================================
//  Feature module forward declarations
// ============================================================================

#if BOH_FPS_OVERLAY || BOH_PING_OVERLAY
// fps_ping.cpp (FpsPingOverlay/fps_ping_overlay.cpp + ping.cpp)
BOOL APIENTRY FpsOverlayDllMain(HMODULE module, DWORD reason, LPVOID reserved);
#endif

#if BOH_NPC_NAME_OVERLAY
// npc_name_overlay.cpp (npc_name_overlay/npc_name_overlay.cpp)
BOOL APIENTRY NpcNameOverlayDllMain(HMODULE module, DWORD reason, LPVOID reserved);
#endif

#if BOH_INVENTORY_TABS
// inventory_tabs.cpp (inventory_tabs/inventory_tabs.cpp)
BOOL APIENTRY InvTabsDllMain(HMODULE module, DWORD reason, LPVOID reserved);
#endif

#if BOH_WEAPON_SPRITE
BOOL APIENTRY WeaponSpriteDllMain(HMODULE module, DWORD reason, LPVOID reserved);
#endif

// ============================================================================
//  DllMain — sole entry point, chains to all feature modules
// ============================================================================

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID lpReserved)
{
    // =======================================================================
    //  DLL_PROCESS_DETACH during process termination (lpReserved != nullptr):
    //  The EXE's _cexit() is already in progress.  ANY call we make that
    //  touches CRT state (heap, mutexes, TLS, std:: containers) can trigger
    //  an exception that the C++ VEH (_CxxFrameHandler4) tries to handle —
    //  and the VEH itself crashes with a null this pointer because the CRT
    //  is mid-teardown.  The ONLY safe action is to return immediately.
    //  The OS will reclaim all memory, handles, and threads.
    // =======================================================================
    if (reason == DLL_PROCESS_DETACH && lpReserved != nullptr)
        return TRUE;

    if (reason == DLL_PROCESS_ATTACH && !BohVerifyDllIntegrity(hModule))
        return FALSE;

    const bool textFeaturesEnabled =
#if BOH_HAS_TEXT_VISUAL
        BohLicense::IsEnabled(FEATURE_EXTENDED_NAMES) ||
        BohLicense::IsEnabled(FEATURE_PLAYER_NAME_COLORS);
#else
        false;
#endif
    const bool fpsFeaturesEnabled =
        BohLicense::IsEnabled(FEATURE_FPS_OVERLAY) ||
        BohLicense::IsEnabled(FEATURE_PING_OVERLAY);

    // Explicit DLL unload — safe to run cleanup.
#if BOH_HAS_TEXT_VISUAL
    if (reason == DLL_PROCESS_DETACH && textFeaturesEnabled)
        TextVisualCleanup(false);
#endif

    // Chain only to compiled-in feature modules that are enabled for this build.
    // This keeps a Gepard-safe combined DLL from running disabled modules that
    // would otherwise patch EXE code, IAT entries, or vtables at runtime.
#if BOH_FPS_OVERLAY || BOH_PING_OVERLAY
    if (fpsFeaturesEnabled)
        FpsOverlayDllMain(hModule, reason, lpReserved);
#endif
#if BOH_NPC_NAME_OVERLAY
    if (BohLicense::IsEnabled(FEATURE_NPC_NAME_OVERLAY))
        NpcNameOverlayDllMain(hModule, reason, lpReserved);
#endif
#if BOH_INVENTORY_TABS
    if (BohLicense::IsEnabled(FEATURE_INVENTORY_TABS))
        InvTabsDllMain(hModule, reason, lpReserved);
#endif
#if BOH_WEAPON_SPRITE
    if (BohLicense::IsEnabled(FEATURE_WEAPON_SPRITE))
        WeaponSpriteDllMain(hModule, reason, lpReserved);
#endif

    switch (reason)
    {
    case DLL_PROCESS_ATTACH:
    {
        DisableThreadLibraryCalls(hModule);

        // Load real ddraw.dll from System32 for proxy support
        wchar_t sysPath[MAX_PATH];
        GetSystemDirectoryW(sysPath, MAX_PATH);
        wcscat_s(sysPath, L"\\ddraw.dll");
        g_hRealDDraw = LoadLibraryW(sysPath);
        if (g_hRealDDraw)
        {
            g_pDirectDrawCreateEx = GetProcAddress(g_hRealDDraw, "DirectDrawCreateEx");
            g_pDirectDrawEnumerateExA = GetProcAddress(g_hRealDDraw, "DirectDrawEnumerateExA");
        }

        // Initialize the EXTN/player-name bridge only for builds that enable
        // those text features. Item/enchant-grade colors are QJS-only.
#if BOH_HAS_TEXT_VISUAL
        if (textFeaturesEnabled)
            TextVisualInit(hModule);
#endif
        break;
    }

    case DLL_PROCESS_DETACH:
    {
        // During process termination we already returned above.
        // This path only runs for explicit DLL unload.
        if (g_hRealDDraw)
        {
            FreeLibrary(g_hRealDDraw);
            g_hRealDDraw = nullptr;
        }
        break;
    }
    }
    return TRUE;
}

// ============================================================================
//  DirectDraw export forwarding
// ============================================================================

extern "C" __declspec(dllexport) HRESULT DirectDrawCreateEx(
    GUID* lpGuid, LPVOID* lplpDD, REFIID iid, IUnknown* punkOuter)
{
    if (g_pDirectDrawCreateEx)
        return ((HRESULT (WINAPI *)(GUID*, LPVOID*, REFIID, IUnknown*))
                g_pDirectDrawCreateEx)(lpGuid, lplpDD, iid, punkOuter);
    return E_FAIL;
}

extern "C" __declspec(dllexport) HRESULT DirectDrawEnumerateExA(
    LPVOID lpCallback, LPVOID lpContext, DWORD dwFlags)
{
    if (g_pDirectDrawEnumerateExA)
        return ((HRESULT (WINAPI *)(LPVOID, LPVOID, DWORD))
                g_pDirectDrawEnumerateExA)(lpCallback, lpContext, dwFlags);
    return E_FAIL;
}

// ============================================================================
//  WARP import table exports — no-op stubs
//  Real setup happens in the feature init functions called from DllMain.
// ============================================================================

extern "C" __declspec(dllexport) void ExtNameVisualInit(void) {}
// Deprecated compatibility anchor. It intentionally initializes nothing;
// item/enchant-grade colors are implemented exclusively by QJS EXE patches.
extern "C" __declspec(dllexport) void ColoredItemNameVisualInit(void) {}
extern "C" __declspec(dllexport) void PlayerNameColorVisualInit(void) {}
#if !BOH_WEAPON_SPRITE
// Compatibility anchor for EXEs produced by the older DLL-backed weapon
// patch. The QJS implementation does all work in the EXE and does not import
// this symbol; keeping the no-op export makes the transition non-breaking.
extern "C" __declspec(dllexport) void WeaponSpriteInit(void) {}
#endif
// Other WARP-facing exports are provided only by enabled feature objects:
// FpsPingOverlayInit, NpcNameOverlayInit, InventoryTabsInit,
// and PincodeUIInit/PincodeUIShow.
