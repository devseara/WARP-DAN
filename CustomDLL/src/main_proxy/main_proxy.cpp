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
//   colored_itemname.cpp - GDI hooks + item colors
//   rune_visual.cpp       — Rune set rendering (RuneVisualDLL/)
//   fps_ping.cpp          — FPS/Ping overlay (FpsPingOverlay/)
//   npc_name_overlay.cpp  — NPC name overlay (npc_name_overlay/)

#include <windows.h>
#include <cstdio>

// Feature license system
#include "boh_features.h"

// ============================================================================
//  DirectDraw forwarding globals (also referenced by colored_itemname.cpp)
// ============================================================================

HMODULE g_hRealDDraw = nullptr;
FARPROC g_pDirectDrawCreateEx = nullptr;
FARPROC g_pDirectDrawEnumerateExA = nullptr;

// ============================================================================
//  Feature module forward declarations
// ============================================================================

// colored_itemname.cpp - GDI hooks + item colors
void ItemColorExtNameInit(HMODULE hModule);
void ItemColorExtNameCleanup(bool isProcessTermination);

// rune_visual.cpp (RuneVisualDLL/boh_rune_visual.cpp)
BOOL APIENTRY RuneVisualDllMain(HMODULE module, DWORD reason, LPVOID reserved);

// fps_ping.cpp (FpsPingOverlay/fps_ping_overlay.cpp + ping.cpp)
BOOL APIENTRY FpsOverlayDllMain(HMODULE module, DWORD reason, LPVOID reserved);

// npc_name_overlay.cpp (npc_name_overlay/npc_name_overlay.cpp)
BOOL APIENTRY NpcNameOverlayDllMain(HMODULE module, DWORD reason, LPVOID reserved);

// inventory_tabs.cpp (inventory_tabs/inventory_tabs.cpp)
BOOL APIENTRY InvTabsDllMain(HMODULE module, DWORD reason, LPVOID reserved);
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

    const bool textFeaturesEnabled =
        BohLicense::IsEnabled(FEATURE_ITEM_COLORS) ||
        BohLicense::IsEnabled(FEATURE_EXTENDED_NAMES);
    const bool fpsFeaturesEnabled =
        BohLicense::IsEnabled(FEATURE_FPS_OVERLAY) ||
        BohLicense::IsEnabled(FEATURE_PING_OVERLAY);

    // Explicit DLL unload — safe to run cleanup.
    if (reason == DLL_PROCESS_DETACH && textFeaturesEnabled)
        ItemColorExtNameCleanup(false);

    // Chain only to compiled-in feature modules that are enabled for this build.
    // This keeps a Gepard-safe combined DLL from running disabled modules that
    // would otherwise patch EXE code, IAT entries, or vtables at runtime.
    if (BohLicense::IsEnabled(FEATURE_RUNE_VISUAL))
        RuneVisualDllMain(hModule, reason, lpReserved);
    if (fpsFeaturesEnabled)
        FpsOverlayDllMain(hModule, reason, lpReserved);
    if (BohLicense::IsEnabled(FEATURE_NPC_NAME_OVERLAY))
        NpcNameOverlayDllMain(hModule, reason, lpReserved);
    if (BohLicense::IsEnabled(FEATURE_INVENTORY_TABS))
        InvTabsDllMain(hModule, reason, lpReserved);
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

        // Initialize item colors + extended names only for builds that enable
        // those text-hook features.
        if (textFeaturesEnabled)
            ItemColorExtNameInit(hModule);
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
extern "C" __declspec(dllexport) void ColoredItemNameVisualInit(void) {}
// RuneVisualInit is exported by rune_visual.obj (boh_rune_visual.cpp)
// FpsPingOverlayInit is exported by fps_ping.obj (fps_ping_overlay.cpp)
// NpcNameOverlayInit is exported by npc_name_overlay.obj (npc_name_overlay.cpp)
// InventoryTabsInit is exported by inventory_tabs.obj (inventory_tabs.cpp)
// WeaponSpriteInit is exported by weapon_sprite.obj (weapon_sprite.cpp)
