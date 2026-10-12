// FPS/Ping Overlay for Ragnarok Online — Gepard-safe, no-D3DX version
// Loaded via WARP CustomDLL.applySpec() as a normal startup import.
// Does NOT hook ws2_32.recv or any system-DLL exports at runtime.
// Hooks D3D9 EndScene by IAT-patching Direct3DCreate9Ex, then vtable patch.
// FPS is measured client-side. Ping is omitted (would require recv hook).
// Frame time in ms is shown as a lag indicator instead.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <stdint.h>
#include <initguid.h>
#include <d3d9.h>
#include <new>

#include "boh_features.h"

#ifndef BOH_FPS_D3D_PROXY
#define BOH_FPS_D3D_PROXY 1
#endif

// ICMP ping (implemented in ping.cpp — separate TU without LEAN_AND_MEAN)
void PingInit();
void PingShutdown();
void PingUpdate();
void PingSetHost(const char* host);
DWORD PingGetResult();
bool PingIsValid();

#pragma comment(lib, "d3d9.lib")
#pragma comment(lib, "user32.lib")
#pragma comment(lib, "gdi32.lib")

// ============================================================================
// State
// ============================================================================

static HMODULE g_hModule = nullptr;
static bool g_initialized = false;
static volatile bool g_shutdown = false;
static HANDLE g_thread = nullptr;
static LONG g_inEndScene = 0;

static IDirect3DDevice9* g_device = nullptr;

// Overlay text resources (GDI bitmap -> D3D9 texture) — currently unused;
// retained for potential future D3D-texture rendering path.
static IDirect3DTexture9* g_tex = nullptr;
static const int TEX_W = 256;
static const int TEX_H = 64;
static HDC g_hdc = nullptr;
static HBITMAP g_hbm = nullptr;
static void* g_bits = nullptr;
static HFONT g_hfont = nullptr;

static UINT g_frameCount = 0;
static UINT g_fps = 0;
static DWORD g_lastFpsTick = 0;

// High-resolution frame timing
static LARGE_INTEGER g_lastFrameQpc = {};
static LARGE_INTEGER g_qpcFreq = {};
static float g_frameMs = 0.0f;

// Overlay config — all settings are hardcoded in LoadConfig()
static volatile LONG g_showFps = TRUE;
static volatile LONG g_showFrameMs = TRUE;
static int g_posX = 1725;
static int g_posY = 50;
static constexpr uint32_t kFpsOverlayOption = 10002;
static constexpr uint32_t kPingOverlayOption = 10003;
static constexpr uintptr_t kRoImageBase = 0x00400000;
static constexpr uintptr_t kGetOption = 0x0068EA70;
static constexpr uintptr_t kSetOption = 0x0068FD50;
static bool g_fpsOptionSynced = false;
static bool g_pingOptionSynced = false;

using FnGetOption = bool (__cdecl*)(uint32_t);
using FnSetOption = bool (__cdecl*)(uint32_t, int);

// Real network latency — measured via D3D9 EndScene frame-time jitter.
// When the server lags, the render thread stalls waiting for packets,
// causing frame-time spikes.  This is a Gepard-safe lag indicator.
// True ICMP/network ping can be added later via IcmpSendEcho if needed.

// Cached GDI resources for the layered window overlay
static HDC g_overlayMemDC = nullptr;
static HBITMAP g_overlayHbm = nullptr;
static void* g_overlayBits = nullptr;
static HFONT g_overlayFont = nullptr;
static HGDIOBJ g_overlayOldBmp = nullptr;   // original bitmap in the DC
static HGDIOBJ g_overlayOldFont = nullptr;  // original font in the DC
static bool g_overlayClassRegistered = false;

// Vtable hook state
static void** g_origVtable = nullptr;
static void* g_origEndScene = nullptr;
static void* g_origReset = nullptr;
static void* g_origDrawPrimitiveUP = nullptr;

// IAT hook state
static void* g_origDirect3DCreate9Ex = nullptr;
static void** g_iatDirect3DCreate9ExEntry = nullptr; // IAT slot we patched
static void* g_origCreateDevice = nullptr;

// DPUP position capture — per-frame buffer, read by npc_name_overlay.cpp
// Architecture: DPUP calls write to g_dpupFrameBuf. EndFrame snapshots the
// count into g_dpupPublished so the overlay thread never sees a reset mid-read.
static const int MAX_DPUP_POSITIONS = 256;
struct DpupCapture { float x, y; DWORD tick; };
static DpupCapture g_dpupFrameBuf[MAX_DPUP_POSITIONS];
static volatile LONG g_dpupFrameWrite = 0;   // producer index (reset each frame)
static volatile LONG g_dpupPublished = 0;    // snapshot for consumer (never reset)
static volatile LONG g_dpupFrameCount = 0;

extern "C" DpupCapture* GetDpupFrameBuf() { return g_dpupFrameBuf; }
extern "C" LONG GetDpupPublished() { return InterlockedCompareExchange(&g_dpupPublished, 0, 0); }
// FrameCount is incremented each frame — consumer uses it to detect new data
extern "C" LONG GetDpupFrameCount() { return InterlockedCompareExchange(&g_dpupFrameCount, 0, 0); }

static void DpupFrameBegin()
{
    g_dpupFrameWrite = 0;
}

static void DpupAddPosition(float x, float y)
{
    LONG idx = InterlockedIncrement(&g_dpupFrameWrite) - 1;
    if (idx >= MAX_DPUP_POSITIONS) return;
    // Deduplicate within same frame (same position within 2px)
    for (LONG i = 0; i < idx; i++) {
        float dx = g_dpupFrameBuf[i].x - x;
        float dy = g_dpupFrameBuf[i].y - y;
        if (dx*dx + dy*dy < 4.0f) return;
    }
    g_dpupFrameBuf[idx].x = x;
    g_dpupFrameBuf[idx].y = y;
    g_dpupFrameBuf[idx].tick = GetTickCount();
}

static void DpupFrameEnd()
{
    // Snapshot the write index BEFORE incrementing frame count.
    // The overlay thread sees frameCount change → reads g_dpupPublished.
    g_dpupPublished = InterlockedCompareExchange(&g_dpupFrameWrite, 0, 0);
    InterlockedIncrement(&g_dpupFrameCount);
}

// ============================================================================
// Utils
// ============================================================================

static void Log(const char* fmt, ...)
{
    (void)fmt;
    return;

    char buf[512];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    OutputDebugStringA("[FpsOverlay] ");
    OutputDebugStringA(buf);
    OutputDebugStringA("\n");
}

static void SetFlag(volatile LONG* flag, bool enabled)
{
    InterlockedExchange(flag, enabled ? TRUE : FALSE);
}

static void LoadConfig()
{
    // All configuration is hardcoded here — no INI file needed.
    // Edit these values and rebuild to change overlay behavior.
    g_showFps     = true;
    g_showFrameMs = true;
    g_posX        = 1725;
    g_posY        = 50;

    Log("Overlay config: ShowFps=%d ShowFrameMs=%d PosX=%d PosY=%d",
        g_showFps, g_showFrameMs, g_posX, g_posY);
}

static uintptr_t RebaseExe(uintptr_t address)
{
    HMODULE exe = GetModuleHandleA(nullptr);
    if (!exe)
        return 0;
    return reinterpret_cast<uintptr_t>(exe) + (address - kRoImageBase);
}

static bool WriteClientOption(uint32_t optionId, bool enabled)
{
    uintptr_t setAddr = RebaseExe(kSetOption);
    if (!setAddr)
        return false;

    __try
    {
        auto setOption = reinterpret_cast<FnSetOption>(setAddr);
        return setOption(optionId, enabled ? 1 : 0);
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        return false;
    }
}

static bool SyncClientOption(
    uint32_t optionId,
    volatile LONG* flag,
    bool featureEnabled,
    bool* synced)
{
    if (!featureEnabled || !synced || *synced)
        return false;

    uintptr_t getAddr = RebaseExe(kGetOption);
    if (!getAddr)
        return false;

    __try
    {
        auto getOption = reinterpret_cast<FnGetOption>(getAddr);
        const bool enabled = getOption(optionId);
        if (!WriteClientOption(optionId, enabled))
            return false;

        SetFlag(flag, enabled);
        *synced = true;
        return true;
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        return false;
    }
}

static void SyncClientOptions()
{
    SyncClientOption(
        kFpsOverlayOption,
        &g_showFps,
        BohLicense::IsEnabled(FEATURE_FPS_OVERLAY),
        &g_fpsOptionSynced);
    SyncClientOption(
        kPingOverlayOption,
        &g_showFrameMs,
        BohLicense::IsEnabled(FEATURE_PING_OVERLAY),
        &g_pingOptionSynced);
}

// ============================================================================
// Overlay text rendering helpers (GDI bitmap -> D3D9 texture)
// ============================================================================

static void DestroyOverlayResources()
{
    // D3D texture path (currently unused)
    if (g_tex)   { g_tex->Release(); g_tex = nullptr; }
    if (g_hfont) { DeleteObject(g_hfont); g_hfont = nullptr; }
    if (g_hbm)   { DeleteObject(g_hbm); g_hbm = nullptr; }
    if (g_hdc)   { DeleteDC(g_hdc); g_hdc = nullptr; }
    g_bits = nullptr;

    // Cached GDI resources for layered window overlay
    // Restore original GDI objects before deleting (MSDN requirement)
    if (g_overlayMemDC)
    {
        if (g_overlayOldFont) SelectObject(g_overlayMemDC, g_overlayOldFont);
        if (g_overlayOldBmp)  SelectObject(g_overlayMemDC, g_overlayOldBmp);
        DeleteDC(g_overlayMemDC);
        g_overlayMemDC = nullptr;
    }
    g_overlayOldFont = nullptr;
    g_overlayOldBmp  = nullptr;
    // Now safe to delete our objects (no longer selected in any DC)
    if (g_overlayFont) { DeleteObject(g_overlayFont); g_overlayFont = nullptr; }
    if (g_overlayHbm)  { DeleteObject(g_overlayHbm);  g_overlayHbm  = nullptr; }
    g_overlayBits = nullptr;
}

static bool CreateOverlayResources(IDirect3DDevice9* dev)
{
    if (g_tex && g_hdc) return true;

    HRESULT hr = dev->CreateTexture(TEX_W, TEX_H, 1, 0,
        D3DFMT_A8R8G8B8, D3DPOOL_SYSTEMMEM, &g_tex, nullptr);
    if (FAILED(hr))
        return false;

    HDC screenDC = GetDC(nullptr);
    g_hdc = CreateCompatibleDC(screenDC);

    BITMAPINFO bmi = {};
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = TEX_W;
    bmi.bmiHeader.biHeight = -TEX_H;
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 32;
    bmi.bmiHeader.biCompression = BI_RGB;

    g_hbm = CreateDIBSection(g_hdc, &bmi, DIB_RGB_COLORS, &g_bits, nullptr, 0);
    SelectObject(g_hdc, g_hbm);

    g_hfont = CreateFontA(15, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
        DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
        DEFAULT_QUALITY, DEFAULT_PITCH | FF_SWISS, "Consolas");
    SelectObject(g_hdc, g_hfont);

    ReleaseDC(nullptr, screenDC);
    return true;
}

// ============================================================================
// D3D9 vtable hook
// ============================================================================

typedef HRESULT (WINAPI *EndScene_t)(IDirect3DDevice9*);
typedef HRESULT (WINAPI *Reset_t)(IDirect3DDevice9*, D3DPRESENT_PARAMETERS*);

#if !BOH_FPS_D3D_PROXY
static void RestoreIat()
{
    if (!g_iatDirect3DCreate9ExEntry || !g_origDirect3DCreate9Ex)
        return;

    DWORD old;
    if (VirtualProtect(g_iatDirect3DCreate9ExEntry, sizeof(void*), PAGE_READWRITE, &old))
    {
        *g_iatDirect3DCreate9ExEntry = g_origDirect3DCreate9Ex;
        VirtualProtect(g_iatDirect3DCreate9ExEntry, sizeof(void*), old, &old);
        Log("IAT restored");
    }
    g_iatDirect3DCreate9ExEntry = nullptr;
    g_origDirect3DCreate9Ex = nullptr;
}

static void RestoreVtable()
{
    if (!g_device || !g_origVtable) return;

    // Spin until render thread is out of EndScene
    while (InterlockedCompareExchange(&g_inEndScene, 0, 0) != 0)
        Sleep(1);

    void** vtable = *(void***)g_device;
    DWORD old;
    if (VirtualProtect(vtable, sizeof(void*) * 50, PAGE_READWRITE, &old))
    {
        if (g_origEndScene) vtable[42] = g_origEndScene;
        if (g_origReset)    vtable[16] = g_origReset;
        VirtualProtect(vtable, sizeof(void*) * 50, old, &old);
    }
    if (g_origDrawPrimitiveUP && g_origVtable)
    {
        void** vt = *(void***)(g_device ? g_device : nullptr);
        if (vt) { DWORD old; VirtualProtect(&vt[83], sizeof(void*), PAGE_READWRITE, &old);
                  vt[83] = g_origDrawPrimitiveUP;
                  VirtualProtect(&vt[83], sizeof(void*), old, &old); }
    }
    g_origEndScene = nullptr;
    g_origReset = nullptr;
    g_origDrawPrimitiveUP = nullptr;
    g_origVtable = nullptr;
}

// DPUP hook — captures name-tag quad positions (2 prims, 32 stride)
static HRESULT WINAPI HookDrawPrimitiveUP(IDirect3DDevice9* dev,
    D3DPRIMITIVETYPE PrimitiveType, UINT PrimitiveCount,
    const void* pVertexStreamZeroData, UINT VertexStreamZeroStride)
{
    static LONG g_dpupDiagCount = 0;
    if (PrimitiveType == D3DPT_TRIANGLESTRIP && PrimitiveCount == 2 &&
        VertexStreamZeroStride == 32 && pVertexStreamZeroData)
    {
        __try {
            const float* v = (const float*)pVertexStreamZeroData;
            float sx = v[0], sy = v[1], rhw = v[3];
            DWORD diffuse = *(const DWORD*)&v[4];  // vertex color
            // Name-tag quads: RHW=1.0, white-ish diffuse (0xFFxxxxxx)
            // UI/glyph quads: RHW=0.1, various colors
            BYTE r = (diffuse >> 16) & 0xFF;
            BYTE g = (diffuse >> 8) & 0xFF;
            BYTE b = diffuse & 0xFF;
            bool isWhite = (r > 200 && g > 200 && b > 200);
            if (sx > 4.0f && sy > 4.0f && rhw > 0.5f && isWhite)
                DpupAddPosition(sx, sy);
        } __except (EXCEPTION_EXECUTE_HANDLER) {}
    }
    if (!g_origDrawPrimitiveUP) return D3D_OK;
    return ((HRESULT (WINAPI*)(IDirect3DDevice9*,D3DPRIMITIVETYPE,UINT,const void*,UINT))
            g_origDrawPrimitiveUP)(dev, PrimitiveType, PrimitiveCount,
                                   pVertexStreamZeroData, VertexStreamZeroStride);
}

static HRESULT WINAPI HookEndScene(IDirect3DDevice9* dev)
{
    InterlockedIncrement(&g_inEndScene);
    if (g_shutdown)
    {
        InterlockedDecrement(&g_inEndScene);
        if (g_origEndScene)
            return ((EndScene_t)g_origEndScene)(dev);
        return S_OK;
    }

    // FPS counter
    g_frameCount++;
    DWORD now = GetTickCount();
    if (!g_lastFpsTick) g_lastFpsTick = now;
    if (now - g_lastFpsTick >= 1000)
    {
        g_fps = g_frameCount;
        g_frameCount = 0;
        g_lastFpsTick = now;
    }

    // Frame time using high-resolution performance counter
    if (!g_qpcFreq.QuadPart)
        QueryPerformanceFrequency(&g_qpcFreq);
    LARGE_INTEGER qpcNow;
    QueryPerformanceCounter(&qpcNow);
    if (g_lastFrameQpc.QuadPart && g_qpcFreq.QuadPart)
    {
        g_frameMs = (float)((qpcNow.QuadPart - g_lastFrameQpc.QuadPart) * 1000.0 / g_qpcFreq.QuadPart);
    }
    g_lastFrameQpc = qpcNow;

    // No D3D drawing — overlay is rendered via layered GDI window
    // to avoid breaking the game's render state

    DpupFrameEnd();  // publish this frame's DPUP positions
    HRESULT hr = ((EndScene_t)g_origEndScene)(dev);
    DpupFrameBegin(); // reset for next frame
    InterlockedDecrement(&g_inEndScene);
    return hr;
}

static HRESULT WINAPI HookReset(IDirect3DDevice9* dev, D3DPRESENT_PARAMETERS* pp)
{
    DestroyOverlayResources();
    return ((Reset_t)g_origReset)(dev, pp);
}

// ============================================================================
// IAT hooking — patch the EXE's import table for Direct3DCreate9Ex
// No memory scanning, no system-DLL inline hooks.
// ============================================================================

typedef HRESULT (WINAPI *CreateDeviceEx_t)(IDirect3D9*, UINT, D3DDEVTYPE, HWND, DWORD, D3DPRESENT_PARAMETERS*, D3DDISPLAYMODEEX*, IDirect3DDevice9Ex**);
typedef HRESULT (WINAPI *Direct3DCreate9Ex_t)(UINT, IDirect3D9**);

static HRESULT WINAPI HookCreateDeviceEx(IDirect3D9* d3d, UINT adapter, D3DDEVTYPE type,
    HWND hWnd, DWORD flags, D3DPRESENT_PARAMETERS* pp, D3DDISPLAYMODEEX* modeEx, IDirect3DDevice9Ex** device)
{
    HRESULT hr = ((CreateDeviceEx_t)g_origCreateDevice)(d3d, adapter, type, hWnd, flags, pp, modeEx, device);
    if (FAILED(hr))
    {
        Log("CreateDeviceEx failed, hr=0x%08X", hr);
        return hr;
    }
    if (!device || !*device)
    {
        Log("CreateDeviceEx returned null device");
        return hr;
    }

    IDirect3DDevice9* dev = *device;
    void** vtable = *(void***)dev;

    if (vtable[42] == (void*)HookEndScene)
    {
        // Already patched — just ensure DPUP is also hooked
        if (vtable[83] != (void*)HookDrawPrimitiveUP)
        {
            DWORD old;
            VirtualProtect(&vtable[83], sizeof(void*), PAGE_READWRITE, &old);
            g_origDrawPrimitiveUP = vtable[83];
            vtable[83] = (void*)HookDrawPrimitiveUP;
            VirtualProtect(&vtable[83], sizeof(void*), old, &old);
            Log("DPUP hooked (late): orig=%p", g_origDrawPrimitiveUP);
        }
        return hr;
    }

    __try
    {
        D3DVIEWPORT9 vp;
        if (SUCCEEDED(dev->GetViewport(&vp)))
        {
            g_device = dev;
            g_origVtable = vtable;

            DWORD old;
            VirtualProtect(vtable, sizeof(void*) * 84, PAGE_READWRITE, &old);
            g_origEndScene = vtable[42];
            g_origReset = vtable[16];
            g_origDrawPrimitiveUP = vtable[83];
            vtable[42] = (void*)HookEndScene;
            vtable[16] = (void*)HookReset;
            vtable[83] = (void*)HookDrawPrimitiveUP;
            VirtualProtect(vtable, sizeof(void*) * 84, old, &old);

            Log("DPUP hooked: orig=%p", g_origDrawPrimitiveUP);
            g_initialized = true;
            Log("Hooked D3D9 device, vtable=%p", vtable);
        }
        else
        {
            Log("GetViewport failed on device %p", dev);
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        Log("Exception in device hook for %p", dev);
    }
    return hr;
}

static HRESULT WINAPI HookDirect3DCreate9Ex(UINT sdk, IDirect3D9** d3d)
{
    HRESULT hr = ((Direct3DCreate9Ex_t)g_origDirect3DCreate9Ex)(sdk, d3d);
    if (SUCCEEDED(hr) && d3d && *d3d)
    {
        IDirect3D9* d3dObj = *d3d;
        void** vtable = *(void***)d3dObj;
        if (vtable[20] == (void*)HookCreateDeviceEx)
        {
            // Already patched (all IDirect3D9 instances share the same vtable)
            return hr;
        }
        DWORD old;
        VirtualProtect(vtable, sizeof(void*) * 25, PAGE_READWRITE, &old);
        g_origCreateDevice = vtable[20];
        vtable[20] = (void*)HookCreateDeviceEx;
        VirtualProtect(vtable, sizeof(void*) * 25, old, &old);
        Log("Hooked IDirect3D9::CreateDeviceEx (index 20), orig=%p", g_origCreateDevice);
    }
    return hr;
}

static bool PatchIAT()
{
    Log("Patching IAT for Direct3DCreate9Ex...");

    HMODULE hClient = GetModuleHandleA(nullptr);
    if (!hClient) return false;

    BYTE* base = (BYTE*)hClient;
    IMAGE_DOS_HEADER* dos = (IMAGE_DOS_HEADER*)base;
    IMAGE_NT_HEADERS* nt = (IMAGE_NT_HEADERS*)(base + dos->e_lfanew);

    DWORD importDirRVA = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT].VirtualAddress;
    if (!importDirRVA) return false;

    IMAGE_IMPORT_DESCRIPTOR* imports = (IMAGE_IMPORT_DESCRIPTOR*)(base + importDirRVA);

    for (int i = 0; imports[i].Name; i++)
    {
        char* dllName = (char*)(base + imports[i].Name);
        if (_stricmp(dllName, "d3d9.dll") != 0)
            continue;

        // INT (Import Name Table) has names/ordinals
        DWORD* intTable = (DWORD*)(base + imports[i].OriginalFirstThunk);
        // IAT (Import Address Table) has the actual pointers that get patched by the loader
        void** iatTable = (void**)(base + imports[i].FirstThunk);

        if (!intTable || !iatTable) continue;

        for (int j = 0; intTable[j]; j++)
        {
            DWORD entry = intTable[j];
            if (entry == 0) break;
            if (entry & IMAGE_ORDINAL_FLAG32)
                continue; // ordinal import, skip

            IMAGE_IMPORT_BY_NAME* nameEntry = (IMAGE_IMPORT_BY_NAME*)(base + entry);
            if (strcmp(nameEntry->Name, "Direct3DCreate9Ex") == 0)
            {
                Log("Found Direct3DCreate9Ex IAT entry at %p", &iatTable[j]);
                g_origDirect3DCreate9Ex = iatTable[j];
                g_iatDirect3DCreate9ExEntry = &iatTable[j];
                DWORD old;
                if (VirtualProtect(&iatTable[j], sizeof(void*), PAGE_READWRITE, &old))
                {
                    iatTable[j] = (void*)HookDirect3DCreate9Ex;
                    VirtualProtect(&iatTable[j], sizeof(void*), old, &old);
                    Log("IAT patched successfully");
                    return true;
                }
            }
        }
    }

    Log("Direct3DCreate9Ex not found in IAT");
    return false;
}

static void Initialize()
{
    LoadConfig();
    if (!PatchIAT())
        Log("IAT patch failed, overlay will not work");
    else
        Log("IAT patch applied, waiting for game to create D3D device...");
}
#else
static HRESULT ProxyDrawPrimitiveUP(
    IDirect3DDevice9Ex* dev,
    D3DPRIMITIVETYPE PrimitiveType,
    UINT PrimitiveCount,
    const void* pVertexStreamZeroData,
    UINT VertexStreamZeroStride)
{
    if (PrimitiveType == D3DPT_TRIANGLESTRIP && PrimitiveCount == 2 &&
        VertexStreamZeroStride == 32 && pVertexStreamZeroData)
    {
        __try {
            const float* v = (const float*)pVertexStreamZeroData;
            float sx = v[0], sy = v[1], rhw = v[3];
            DWORD diffuse = *(const DWORD*)&v[4];
            BYTE r = (diffuse >> 16) & 0xFF;
            BYTE g = (diffuse >> 8) & 0xFF;
            BYTE b = diffuse & 0xFF;
            bool isWhite = (r > 200 && g > 200 && b > 200);
            if (sx > 4.0f && sy > 4.0f && rhw > 0.5f && isWhite)
                DpupAddPosition(sx, sy);
        } __except (EXCEPTION_EXECUTE_HANDLER) {}
    }

    return dev->DrawPrimitiveUP(
        PrimitiveType,
        PrimitiveCount,
        pVertexStreamZeroData,
        VertexStreamZeroStride);
}

static HRESULT ProxyEndScene(IDirect3DDevice9Ex* dev)
{
    InterlockedIncrement(&g_inEndScene);
    if (g_shutdown)
    {
        InterlockedDecrement(&g_inEndScene);
        return dev->EndScene();
    }

    g_frameCount++;
    DWORD now = GetTickCount();
    if (!g_lastFpsTick) g_lastFpsTick = now;
    if (now - g_lastFpsTick >= 1000)
    {
        g_fps = g_frameCount;
        g_frameCount = 0;
        g_lastFpsTick = now;
    }

    if (!g_qpcFreq.QuadPart)
        QueryPerformanceFrequency(&g_qpcFreq);
    LARGE_INTEGER qpcNow;
    QueryPerformanceCounter(&qpcNow);
    if (g_lastFrameQpc.QuadPart && g_qpcFreq.QuadPart)
    {
        g_frameMs = (float)((qpcNow.QuadPart - g_lastFrameQpc.QuadPart) * 1000.0 / g_qpcFreq.QuadPart);
    }
    g_lastFrameQpc = qpcNow;

    DpupFrameEnd();
    HRESULT hr = dev->EndScene();
    DpupFrameBegin();
    InterlockedDecrement(&g_inEndScene);
    return hr;
}

static HRESULT ProxyReset(IDirect3DDevice9Ex* dev, D3DPRESENT_PARAMETERS* pp)
{
    DestroyOverlayResources();
    return dev->Reset(pp);
}

static HRESULT ProxyResetEx(
    IDirect3DDevice9Ex* dev,
    D3DPRESENT_PARAMETERS* pp,
    D3DDISPLAYMODEEX* mode)
{
    DestroyOverlayResources();
    return dev->ResetEx(pp, mode);
}

class D3DDevice9ExProxy : public IDirect3DDevice9Ex
{
public:
    explicit D3DDevice9ExProxy(IDirect3DDevice9Ex* real) : real_(real)
    {
        g_device = real_;
    }

    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppvObj) override
    {
        if (!ppvObj)
            return E_POINTER;
        if (IsEqualGUID(riid, IID_IUnknown) ||
            IsEqualGUID(riid, IID_IDirect3DDevice9) ||
            IsEqualGUID(riid, IID_IDirect3DDevice9Ex))
        {
            *ppvObj = static_cast<IDirect3DDevice9Ex*>(this);
            AddRef();
            return S_OK;
        }
        return real_->QueryInterface(riid, ppvObj);
    }

    ULONG STDMETHODCALLTYPE AddRef() override { return real_->AddRef(); }
    ULONG STDMETHODCALLTYPE Release() override
    {
        ULONG refs = real_->Release();
        if (refs == 0)
        {
            if (g_device == real_)
                g_device = nullptr;
            delete this;
        }
        return refs;
    }

    HRESULT STDMETHODCALLTYPE TestCooperativeLevel() override { return real_->TestCooperativeLevel(); }
    UINT STDMETHODCALLTYPE GetAvailableTextureMem() override { return real_->GetAvailableTextureMem(); }
    HRESULT STDMETHODCALLTYPE EvictManagedResources() override { return real_->EvictManagedResources(); }
    HRESULT STDMETHODCALLTYPE GetDirect3D(IDirect3D9** ppD3D9) override { return real_->GetDirect3D(ppD3D9); }
    HRESULT STDMETHODCALLTYPE GetDeviceCaps(D3DCAPS9* pCaps) override { return real_->GetDeviceCaps(pCaps); }
    HRESULT STDMETHODCALLTYPE GetDisplayMode(UINT iSwapChain, D3DDISPLAYMODE* pMode) override { return real_->GetDisplayMode(iSwapChain, pMode); }
    HRESULT STDMETHODCALLTYPE GetCreationParameters(D3DDEVICE_CREATION_PARAMETERS* pParameters) override { return real_->GetCreationParameters(pParameters); }
    HRESULT STDMETHODCALLTYPE SetCursorProperties(UINT XHotSpot, UINT YHotSpot, IDirect3DSurface9* pCursorBitmap) override { return real_->SetCursorProperties(XHotSpot, YHotSpot, pCursorBitmap); }
    void STDMETHODCALLTYPE SetCursorPosition(int X, int Y, DWORD Flags) override { real_->SetCursorPosition(X, Y, Flags); }
    BOOL STDMETHODCALLTYPE ShowCursor(BOOL bShow) override { return real_->ShowCursor(bShow); }
    HRESULT STDMETHODCALLTYPE CreateAdditionalSwapChain(D3DPRESENT_PARAMETERS* pPresentationParameters, IDirect3DSwapChain9** pSwapChain) override { return real_->CreateAdditionalSwapChain(pPresentationParameters, pSwapChain); }
    HRESULT STDMETHODCALLTYPE GetSwapChain(UINT iSwapChain, IDirect3DSwapChain9** pSwapChain) override { return real_->GetSwapChain(iSwapChain, pSwapChain); }
    UINT STDMETHODCALLTYPE GetNumberOfSwapChains() override { return real_->GetNumberOfSwapChains(); }
    HRESULT STDMETHODCALLTYPE Reset(D3DPRESENT_PARAMETERS* pPresentationParameters) override { return ProxyReset(real_, pPresentationParameters); }
    HRESULT STDMETHODCALLTYPE Present(CONST RECT* pSourceRect, CONST RECT* pDestRect, HWND hDestWindowOverride, CONST RGNDATA* pDirtyRegion) override { return real_->Present(pSourceRect, pDestRect, hDestWindowOverride, pDirtyRegion); }
    HRESULT STDMETHODCALLTYPE GetBackBuffer(UINT iSwapChain, UINT iBackBuffer, D3DBACKBUFFER_TYPE Type, IDirect3DSurface9** ppBackBuffer) override { return real_->GetBackBuffer(iSwapChain, iBackBuffer, Type, ppBackBuffer); }
    HRESULT STDMETHODCALLTYPE GetRasterStatus(UINT iSwapChain, D3DRASTER_STATUS* pRasterStatus) override { return real_->GetRasterStatus(iSwapChain, pRasterStatus); }
    HRESULT STDMETHODCALLTYPE SetDialogBoxMode(BOOL bEnableDialogs) override { return real_->SetDialogBoxMode(bEnableDialogs); }
    void STDMETHODCALLTYPE SetGammaRamp(UINT iSwapChain, DWORD Flags, CONST D3DGAMMARAMP* pRamp) override { real_->SetGammaRamp(iSwapChain, Flags, pRamp); }
    void STDMETHODCALLTYPE GetGammaRamp(UINT iSwapChain, D3DGAMMARAMP* pRamp) override { real_->GetGammaRamp(iSwapChain, pRamp); }
    HRESULT STDMETHODCALLTYPE CreateTexture(UINT Width, UINT Height, UINT Levels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DTexture9** ppTexture, HANDLE* pSharedHandle) override { return real_->CreateTexture(Width, Height, Levels, Usage, Format, Pool, ppTexture, pSharedHandle); }
    HRESULT STDMETHODCALLTYPE CreateVolumeTexture(UINT Width, UINT Height, UINT Depth, UINT Levels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DVolumeTexture9** ppVolumeTexture, HANDLE* pSharedHandle) override { return real_->CreateVolumeTexture(Width, Height, Depth, Levels, Usage, Format, Pool, ppVolumeTexture, pSharedHandle); }
    HRESULT STDMETHODCALLTYPE CreateCubeTexture(UINT EdgeLength, UINT Levels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DCubeTexture9** ppCubeTexture, HANDLE* pSharedHandle) override { return real_->CreateCubeTexture(EdgeLength, Levels, Usage, Format, Pool, ppCubeTexture, pSharedHandle); }
    HRESULT STDMETHODCALLTYPE CreateVertexBuffer(UINT Length, DWORD Usage, DWORD FVF, D3DPOOL Pool, IDirect3DVertexBuffer9** ppVertexBuffer, HANDLE* pSharedHandle) override { return real_->CreateVertexBuffer(Length, Usage, FVF, Pool, ppVertexBuffer, pSharedHandle); }
    HRESULT STDMETHODCALLTYPE CreateIndexBuffer(UINT Length, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DIndexBuffer9** ppIndexBuffer, HANDLE* pSharedHandle) override { return real_->CreateIndexBuffer(Length, Usage, Format, Pool, ppIndexBuffer, pSharedHandle); }
    HRESULT STDMETHODCALLTYPE CreateRenderTarget(UINT Width, UINT Height, D3DFORMAT Format, D3DMULTISAMPLE_TYPE MultiSample, DWORD MultisampleQuality, BOOL Lockable, IDirect3DSurface9** ppSurface, HANDLE* pSharedHandle) override { return real_->CreateRenderTarget(Width, Height, Format, MultiSample, MultisampleQuality, Lockable, ppSurface, pSharedHandle); }
    HRESULT STDMETHODCALLTYPE CreateDepthStencilSurface(UINT Width, UINT Height, D3DFORMAT Format, D3DMULTISAMPLE_TYPE MultiSample, DWORD MultisampleQuality, BOOL Discard, IDirect3DSurface9** ppSurface, HANDLE* pSharedHandle) override { return real_->CreateDepthStencilSurface(Width, Height, Format, MultiSample, MultisampleQuality, Discard, ppSurface, pSharedHandle); }
    HRESULT STDMETHODCALLTYPE UpdateSurface(IDirect3DSurface9* pSourceSurface, CONST RECT* pSourceRect, IDirect3DSurface9* pDestinationSurface, CONST POINT* pDestPoint) override { return real_->UpdateSurface(pSourceSurface, pSourceRect, pDestinationSurface, pDestPoint); }
    HRESULT STDMETHODCALLTYPE UpdateTexture(IDirect3DBaseTexture9* pSourceTexture, IDirect3DBaseTexture9* pDestinationTexture) override { return real_->UpdateTexture(pSourceTexture, pDestinationTexture); }
    HRESULT STDMETHODCALLTYPE GetRenderTargetData(IDirect3DSurface9* pRenderTarget, IDirect3DSurface9* pDestSurface) override { return real_->GetRenderTargetData(pRenderTarget, pDestSurface); }
    HRESULT STDMETHODCALLTYPE GetFrontBufferData(UINT iSwapChain, IDirect3DSurface9* pDestSurface) override { return real_->GetFrontBufferData(iSwapChain, pDestSurface); }
    HRESULT STDMETHODCALLTYPE StretchRect(IDirect3DSurface9* pSourceSurface, CONST RECT* pSourceRect, IDirect3DSurface9* pDestSurface, CONST RECT* pDestRect, D3DTEXTUREFILTERTYPE Filter) override { return real_->StretchRect(pSourceSurface, pSourceRect, pDestSurface, pDestRect, Filter); }
    HRESULT STDMETHODCALLTYPE ColorFill(IDirect3DSurface9* pSurface, CONST RECT* pRect, D3DCOLOR color) override { return real_->ColorFill(pSurface, pRect, color); }
    HRESULT STDMETHODCALLTYPE CreateOffscreenPlainSurface(UINT Width, UINT Height, D3DFORMAT Format, D3DPOOL Pool, IDirect3DSurface9** ppSurface, HANDLE* pSharedHandle) override { return real_->CreateOffscreenPlainSurface(Width, Height, Format, Pool, ppSurface, pSharedHandle); }
    HRESULT STDMETHODCALLTYPE SetRenderTarget(DWORD RenderTargetIndex, IDirect3DSurface9* pRenderTarget) override { return real_->SetRenderTarget(RenderTargetIndex, pRenderTarget); }
    HRESULT STDMETHODCALLTYPE GetRenderTarget(DWORD RenderTargetIndex, IDirect3DSurface9** ppRenderTarget) override { return real_->GetRenderTarget(RenderTargetIndex, ppRenderTarget); }
    HRESULT STDMETHODCALLTYPE SetDepthStencilSurface(IDirect3DSurface9* pNewZStencil) override { return real_->SetDepthStencilSurface(pNewZStencil); }
    HRESULT STDMETHODCALLTYPE GetDepthStencilSurface(IDirect3DSurface9** ppZStencilSurface) override { return real_->GetDepthStencilSurface(ppZStencilSurface); }
    HRESULT STDMETHODCALLTYPE BeginScene() override { return real_->BeginScene(); }
    HRESULT STDMETHODCALLTYPE EndScene() override { return ProxyEndScene(real_); }
    HRESULT STDMETHODCALLTYPE Clear(DWORD Count, CONST D3DRECT* pRects, DWORD Flags, D3DCOLOR Color, float Z, DWORD Stencil) override { return real_->Clear(Count, pRects, Flags, Color, Z, Stencil); }
    HRESULT STDMETHODCALLTYPE SetTransform(D3DTRANSFORMSTATETYPE State, CONST D3DMATRIX* pMatrix) override { return real_->SetTransform(State, pMatrix); }
    HRESULT STDMETHODCALLTYPE GetTransform(D3DTRANSFORMSTATETYPE State, D3DMATRIX* pMatrix) override { return real_->GetTransform(State, pMatrix); }
    HRESULT STDMETHODCALLTYPE MultiplyTransform(D3DTRANSFORMSTATETYPE State, CONST D3DMATRIX* pMatrix) override { return real_->MultiplyTransform(State, pMatrix); }
    HRESULT STDMETHODCALLTYPE SetViewport(CONST D3DVIEWPORT9* pViewport) override { return real_->SetViewport(pViewport); }
    HRESULT STDMETHODCALLTYPE GetViewport(D3DVIEWPORT9* pViewport) override { return real_->GetViewport(pViewport); }
    HRESULT STDMETHODCALLTYPE SetMaterial(CONST D3DMATERIAL9* pMaterial) override { return real_->SetMaterial(pMaterial); }
    HRESULT STDMETHODCALLTYPE GetMaterial(D3DMATERIAL9* pMaterial) override { return real_->GetMaterial(pMaterial); }
    HRESULT STDMETHODCALLTYPE SetLight(DWORD Index, CONST D3DLIGHT9* pLight) override { return real_->SetLight(Index, pLight); }
    HRESULT STDMETHODCALLTYPE GetLight(DWORD Index, D3DLIGHT9* pLight) override { return real_->GetLight(Index, pLight); }
    HRESULT STDMETHODCALLTYPE LightEnable(DWORD Index, BOOL Enable) override { return real_->LightEnable(Index, Enable); }
    HRESULT STDMETHODCALLTYPE GetLightEnable(DWORD Index, BOOL* pEnable) override { return real_->GetLightEnable(Index, pEnable); }
    HRESULT STDMETHODCALLTYPE SetClipPlane(DWORD Index, CONST float* pPlane) override { return real_->SetClipPlane(Index, pPlane); }
    HRESULT STDMETHODCALLTYPE GetClipPlane(DWORD Index, float* pPlane) override { return real_->GetClipPlane(Index, pPlane); }
    HRESULT STDMETHODCALLTYPE SetRenderState(D3DRENDERSTATETYPE State, DWORD Value) override { return real_->SetRenderState(State, Value); }
    HRESULT STDMETHODCALLTYPE GetRenderState(D3DRENDERSTATETYPE State, DWORD* pValue) override { return real_->GetRenderState(State, pValue); }
    HRESULT STDMETHODCALLTYPE CreateStateBlock(D3DSTATEBLOCKTYPE Type, IDirect3DStateBlock9** ppSB) override { return real_->CreateStateBlock(Type, ppSB); }
    HRESULT STDMETHODCALLTYPE BeginStateBlock() override { return real_->BeginStateBlock(); }
    HRESULT STDMETHODCALLTYPE EndStateBlock(IDirect3DStateBlock9** ppSB) override { return real_->EndStateBlock(ppSB); }
    HRESULT STDMETHODCALLTYPE SetClipStatus(CONST D3DCLIPSTATUS9* pClipStatus) override { return real_->SetClipStatus(pClipStatus); }
    HRESULT STDMETHODCALLTYPE GetClipStatus(D3DCLIPSTATUS9* pClipStatus) override { return real_->GetClipStatus(pClipStatus); }
    HRESULT STDMETHODCALLTYPE GetTexture(DWORD Stage, IDirect3DBaseTexture9** ppTexture) override { return real_->GetTexture(Stage, ppTexture); }
    HRESULT STDMETHODCALLTYPE SetTexture(DWORD Stage, IDirect3DBaseTexture9* pTexture) override { return real_->SetTexture(Stage, pTexture); }
    HRESULT STDMETHODCALLTYPE GetTextureStageState(DWORD Stage, D3DTEXTURESTAGESTATETYPE Type, DWORD* pValue) override { return real_->GetTextureStageState(Stage, Type, pValue); }
    HRESULT STDMETHODCALLTYPE SetTextureStageState(DWORD Stage, D3DTEXTURESTAGESTATETYPE Type, DWORD Value) override { return real_->SetTextureStageState(Stage, Type, Value); }
    HRESULT STDMETHODCALLTYPE GetSamplerState(DWORD Sampler, D3DSAMPLERSTATETYPE Type, DWORD* pValue) override { return real_->GetSamplerState(Sampler, Type, pValue); }
    HRESULT STDMETHODCALLTYPE SetSamplerState(DWORD Sampler, D3DSAMPLERSTATETYPE Type, DWORD Value) override { return real_->SetSamplerState(Sampler, Type, Value); }
    HRESULT STDMETHODCALLTYPE ValidateDevice(DWORD* pNumPasses) override { return real_->ValidateDevice(pNumPasses); }
    HRESULT STDMETHODCALLTYPE SetPaletteEntries(UINT PaletteNumber, CONST PALETTEENTRY* pEntries) override { return real_->SetPaletteEntries(PaletteNumber, pEntries); }
    HRESULT STDMETHODCALLTYPE GetPaletteEntries(UINT PaletteNumber, PALETTEENTRY* pEntries) override { return real_->GetPaletteEntries(PaletteNumber, pEntries); }
    HRESULT STDMETHODCALLTYPE SetCurrentTexturePalette(UINT PaletteNumber) override { return real_->SetCurrentTexturePalette(PaletteNumber); }
    HRESULT STDMETHODCALLTYPE GetCurrentTexturePalette(UINT* PaletteNumber) override { return real_->GetCurrentTexturePalette(PaletteNumber); }
    HRESULT STDMETHODCALLTYPE SetScissorRect(CONST RECT* pRect) override { return real_->SetScissorRect(pRect); }
    HRESULT STDMETHODCALLTYPE GetScissorRect(RECT* pRect) override { return real_->GetScissorRect(pRect); }
    HRESULT STDMETHODCALLTYPE SetSoftwareVertexProcessing(BOOL bSoftware) override { return real_->SetSoftwareVertexProcessing(bSoftware); }
    BOOL STDMETHODCALLTYPE GetSoftwareVertexProcessing() override { return real_->GetSoftwareVertexProcessing(); }
    HRESULT STDMETHODCALLTYPE SetNPatchMode(float nSegments) override { return real_->SetNPatchMode(nSegments); }
    float STDMETHODCALLTYPE GetNPatchMode() override { return real_->GetNPatchMode(); }
    HRESULT STDMETHODCALLTYPE DrawPrimitive(D3DPRIMITIVETYPE PrimitiveType, UINT StartVertex, UINT PrimitiveCount) override { return real_->DrawPrimitive(PrimitiveType, StartVertex, PrimitiveCount); }
    HRESULT STDMETHODCALLTYPE DrawIndexedPrimitive(D3DPRIMITIVETYPE Type, INT BaseVertexIndex, UINT MinVertexIndex, UINT NumVertices, UINT startIndex, UINT primCount) override { return real_->DrawIndexedPrimitive(Type, BaseVertexIndex, MinVertexIndex, NumVertices, startIndex, primCount); }
    HRESULT STDMETHODCALLTYPE DrawPrimitiveUP(D3DPRIMITIVETYPE PrimitiveType, UINT PrimitiveCount, CONST void* pVertexStreamZeroData, UINT VertexStreamZeroStride) override { return ProxyDrawPrimitiveUP(real_, PrimitiveType, PrimitiveCount, pVertexStreamZeroData, VertexStreamZeroStride); }
    HRESULT STDMETHODCALLTYPE DrawIndexedPrimitiveUP(D3DPRIMITIVETYPE PrimitiveType, UINT MinVertexIndex, UINT NumVertices, UINT PrimitiveCount, CONST void* pIndexData, D3DFORMAT IndexDataFormat, CONST void* pVertexStreamZeroData, UINT VertexStreamZeroStride) override { return real_->DrawIndexedPrimitiveUP(PrimitiveType, MinVertexIndex, NumVertices, PrimitiveCount, pIndexData, IndexDataFormat, pVertexStreamZeroData, VertexStreamZeroStride); }
    HRESULT STDMETHODCALLTYPE ProcessVertices(UINT SrcStartIndex, UINT DestIndex, UINT VertexCount, IDirect3DVertexBuffer9* pDestBuffer, IDirect3DVertexDeclaration9* pVertexDecl, DWORD Flags) override { return real_->ProcessVertices(SrcStartIndex, DestIndex, VertexCount, pDestBuffer, pVertexDecl, Flags); }
    HRESULT STDMETHODCALLTYPE CreateVertexDeclaration(CONST D3DVERTEXELEMENT9* pVertexElements, IDirect3DVertexDeclaration9** ppDecl) override { return real_->CreateVertexDeclaration(pVertexElements, ppDecl); }
    HRESULT STDMETHODCALLTYPE SetVertexDeclaration(IDirect3DVertexDeclaration9* pDecl) override { return real_->SetVertexDeclaration(pDecl); }
    HRESULT STDMETHODCALLTYPE GetVertexDeclaration(IDirect3DVertexDeclaration9** ppDecl) override { return real_->GetVertexDeclaration(ppDecl); }
    HRESULT STDMETHODCALLTYPE SetFVF(DWORD FVF) override { return real_->SetFVF(FVF); }
    HRESULT STDMETHODCALLTYPE GetFVF(DWORD* pFVF) override { return real_->GetFVF(pFVF); }
    HRESULT STDMETHODCALLTYPE CreateVertexShader(CONST DWORD* pFunction, IDirect3DVertexShader9** ppShader) override { return real_->CreateVertexShader(pFunction, ppShader); }
    HRESULT STDMETHODCALLTYPE SetVertexShader(IDirect3DVertexShader9* pShader) override { return real_->SetVertexShader(pShader); }
    HRESULT STDMETHODCALLTYPE GetVertexShader(IDirect3DVertexShader9** ppShader) override { return real_->GetVertexShader(ppShader); }
    HRESULT STDMETHODCALLTYPE SetVertexShaderConstantF(UINT StartRegister, CONST float* pConstantData, UINT Vector4fCount) override { return real_->SetVertexShaderConstantF(StartRegister, pConstantData, Vector4fCount); }
    HRESULT STDMETHODCALLTYPE GetVertexShaderConstantF(UINT StartRegister, float* pConstantData, UINT Vector4fCount) override { return real_->GetVertexShaderConstantF(StartRegister, pConstantData, Vector4fCount); }
    HRESULT STDMETHODCALLTYPE SetVertexShaderConstantI(UINT StartRegister, CONST int* pConstantData, UINT Vector4iCount) override { return real_->SetVertexShaderConstantI(StartRegister, pConstantData, Vector4iCount); }
    HRESULT STDMETHODCALLTYPE GetVertexShaderConstantI(UINT StartRegister, int* pConstantData, UINT Vector4iCount) override { return real_->GetVertexShaderConstantI(StartRegister, pConstantData, Vector4iCount); }
    HRESULT STDMETHODCALLTYPE SetVertexShaderConstantB(UINT StartRegister, CONST BOOL* pConstantData, UINT BoolCount) override { return real_->SetVertexShaderConstantB(StartRegister, pConstantData, BoolCount); }
    HRESULT STDMETHODCALLTYPE GetVertexShaderConstantB(UINT StartRegister, BOOL* pConstantData, UINT BoolCount) override { return real_->GetVertexShaderConstantB(StartRegister, pConstantData, BoolCount); }
    HRESULT STDMETHODCALLTYPE SetStreamSource(UINT StreamNumber, IDirect3DVertexBuffer9* pStreamData, UINT OffsetInBytes, UINT Stride) override { return real_->SetStreamSource(StreamNumber, pStreamData, OffsetInBytes, Stride); }
    HRESULT STDMETHODCALLTYPE GetStreamSource(UINT StreamNumber, IDirect3DVertexBuffer9** ppStreamData, UINT* pOffsetInBytes, UINT* pStride) override { return real_->GetStreamSource(StreamNumber, ppStreamData, pOffsetInBytes, pStride); }
    HRESULT STDMETHODCALLTYPE SetStreamSourceFreq(UINT StreamNumber, UINT Setting) override { return real_->SetStreamSourceFreq(StreamNumber, Setting); }
    HRESULT STDMETHODCALLTYPE GetStreamSourceFreq(UINT StreamNumber, UINT* pSetting) override { return real_->GetStreamSourceFreq(StreamNumber, pSetting); }
    HRESULT STDMETHODCALLTYPE SetIndices(IDirect3DIndexBuffer9* pIndexData) override { return real_->SetIndices(pIndexData); }
    HRESULT STDMETHODCALLTYPE GetIndices(IDirect3DIndexBuffer9** ppIndexData) override { return real_->GetIndices(ppIndexData); }
    HRESULT STDMETHODCALLTYPE CreatePixelShader(CONST DWORD* pFunction, IDirect3DPixelShader9** ppShader) override { return real_->CreatePixelShader(pFunction, ppShader); }
    HRESULT STDMETHODCALLTYPE SetPixelShader(IDirect3DPixelShader9* pShader) override { return real_->SetPixelShader(pShader); }
    HRESULT STDMETHODCALLTYPE GetPixelShader(IDirect3DPixelShader9** ppShader) override { return real_->GetPixelShader(ppShader); }
    HRESULT STDMETHODCALLTYPE SetPixelShaderConstantF(UINT StartRegister, CONST float* pConstantData, UINT Vector4fCount) override { return real_->SetPixelShaderConstantF(StartRegister, pConstantData, Vector4fCount); }
    HRESULT STDMETHODCALLTYPE GetPixelShaderConstantF(UINT StartRegister, float* pConstantData, UINT Vector4fCount) override { return real_->GetPixelShaderConstantF(StartRegister, pConstantData, Vector4fCount); }
    HRESULT STDMETHODCALLTYPE SetPixelShaderConstantI(UINT StartRegister, CONST int* pConstantData, UINT Vector4iCount) override { return real_->SetPixelShaderConstantI(StartRegister, pConstantData, Vector4iCount); }
    HRESULT STDMETHODCALLTYPE GetPixelShaderConstantI(UINT StartRegister, int* pConstantData, UINT Vector4iCount) override { return real_->GetPixelShaderConstantI(StartRegister, pConstantData, Vector4iCount); }
    HRESULT STDMETHODCALLTYPE SetPixelShaderConstantB(UINT StartRegister, CONST BOOL* pConstantData, UINT BoolCount) override { return real_->SetPixelShaderConstantB(StartRegister, pConstantData, BoolCount); }
    HRESULT STDMETHODCALLTYPE GetPixelShaderConstantB(UINT StartRegister, BOOL* pConstantData, UINT BoolCount) override { return real_->GetPixelShaderConstantB(StartRegister, pConstantData, BoolCount); }
    HRESULT STDMETHODCALLTYPE DrawRectPatch(UINT Handle, CONST float* pNumSegs, CONST D3DRECTPATCH_INFO* pRectPatchInfo) override { return real_->DrawRectPatch(Handle, pNumSegs, pRectPatchInfo); }
    HRESULT STDMETHODCALLTYPE DrawTriPatch(UINT Handle, CONST float* pNumSegs, CONST D3DTRIPATCH_INFO* pTriPatchInfo) override { return real_->DrawTriPatch(Handle, pNumSegs, pTriPatchInfo); }
    HRESULT STDMETHODCALLTYPE DeletePatch(UINT Handle) override { return real_->DeletePatch(Handle); }
    HRESULT STDMETHODCALLTYPE CreateQuery(D3DQUERYTYPE Type, IDirect3DQuery9** ppQuery) override { return real_->CreateQuery(Type, ppQuery); }
    HRESULT STDMETHODCALLTYPE SetConvolutionMonoKernel(UINT width, UINT height, float* rows, float* columns) override { return real_->SetConvolutionMonoKernel(width, height, rows, columns); }
    HRESULT STDMETHODCALLTYPE ComposeRects(IDirect3DSurface9* pSrc, IDirect3DSurface9* pDst, IDirect3DVertexBuffer9* pSrcRectDescs, UINT NumRects, IDirect3DVertexBuffer9* pDstRectDescs, D3DCOMPOSERECTSOP Operation, int Xoffset, int Yoffset) override { return real_->ComposeRects(pSrc, pDst, pSrcRectDescs, NumRects, pDstRectDescs, Operation, Xoffset, Yoffset); }
    HRESULT STDMETHODCALLTYPE PresentEx(CONST RECT* pSourceRect, CONST RECT* pDestRect, HWND hDestWindowOverride, CONST RGNDATA* pDirtyRegion, DWORD dwFlags) override { return real_->PresentEx(pSourceRect, pDestRect, hDestWindowOverride, pDirtyRegion, dwFlags); }
    HRESULT STDMETHODCALLTYPE GetGPUThreadPriority(INT* pPriority) override { return real_->GetGPUThreadPriority(pPriority); }
    HRESULT STDMETHODCALLTYPE SetGPUThreadPriority(INT Priority) override { return real_->SetGPUThreadPriority(Priority); }
    HRESULT STDMETHODCALLTYPE WaitForVBlank(UINT iSwapChain) override { return real_->WaitForVBlank(iSwapChain); }
    HRESULT STDMETHODCALLTYPE CheckResourceResidency(IDirect3DResource9** pResourceArray, UINT32 NumResources) override { return real_->CheckResourceResidency(pResourceArray, NumResources); }
    HRESULT STDMETHODCALLTYPE SetMaximumFrameLatency(UINT MaxLatency) override { return real_->SetMaximumFrameLatency(MaxLatency); }
    HRESULT STDMETHODCALLTYPE GetMaximumFrameLatency(UINT* pMaxLatency) override { return real_->GetMaximumFrameLatency(pMaxLatency); }
    HRESULT STDMETHODCALLTYPE CheckDeviceState(HWND hDestinationWindow) override { return real_->CheckDeviceState(hDestinationWindow); }
    HRESULT STDMETHODCALLTYPE CreateRenderTargetEx(UINT Width, UINT Height, D3DFORMAT Format, D3DMULTISAMPLE_TYPE MultiSample, DWORD MultisampleQuality, BOOL Lockable, IDirect3DSurface9** ppSurface, HANDLE* pSharedHandle, DWORD Usage) override { return real_->CreateRenderTargetEx(Width, Height, Format, MultiSample, MultisampleQuality, Lockable, ppSurface, pSharedHandle, Usage); }
    HRESULT STDMETHODCALLTYPE CreateOffscreenPlainSurfaceEx(UINT Width, UINT Height, D3DFORMAT Format, D3DPOOL Pool, IDirect3DSurface9** ppSurface, HANDLE* pSharedHandle, DWORD Usage) override { return real_->CreateOffscreenPlainSurfaceEx(Width, Height, Format, Pool, ppSurface, pSharedHandle, Usage); }
    HRESULT STDMETHODCALLTYPE CreateDepthStencilSurfaceEx(UINT Width, UINT Height, D3DFORMAT Format, D3DMULTISAMPLE_TYPE MultiSample, DWORD MultisampleQuality, BOOL Discard, IDirect3DSurface9** ppSurface, HANDLE* pSharedHandle, DWORD Usage) override { return real_->CreateDepthStencilSurfaceEx(Width, Height, Format, MultiSample, MultisampleQuality, Discard, ppSurface, pSharedHandle, Usage); }
    HRESULT STDMETHODCALLTYPE ResetEx(D3DPRESENT_PARAMETERS* pPresentationParameters, D3DDISPLAYMODEEX* pFullscreenDisplayMode) override { return ProxyResetEx(real_, pPresentationParameters, pFullscreenDisplayMode); }
    HRESULT STDMETHODCALLTYPE GetDisplayModeEx(UINT iSwapChain, D3DDISPLAYMODEEX* pMode, D3DDISPLAYROTATION* pRotation) override { return real_->GetDisplayModeEx(iSwapChain, pMode, pRotation); }

private:
    IDirect3DDevice9Ex* real_;
};

static HRESULT WrapDeviceEx(IDirect3DDevice9Ex* real, IDirect3DDevice9Ex** out)
{
    if (!out)
        return E_POINTER;
    *out = nullptr;
    if (!real)
        return D3DERR_INVALIDCALL;

    D3DDevice9ExProxy* proxy = new (std::nothrow) D3DDevice9ExProxy(real);
    if (!proxy)
    {
        real->Release();
        return E_OUTOFMEMORY;
    }
    *out = proxy;
    Log("Created D3D device proxy: real=%p proxy=%p", real, proxy);
    return S_OK;
}

static HRESULT WrapDevice9(IDirect3DDevice9* realBase, IDirect3DDevice9** out)
{
    if (!out)
        return E_POINTER;
    if (!realBase)
        return D3DERR_INVALIDCALL;

    IDirect3DDevice9Ex* realEx = nullptr;
    if (SUCCEEDED(realBase->QueryInterface(IID_IDirect3DDevice9Ex, (void**)&realEx)) && realEx)
    {
        realBase->Release();
        IDirect3DDevice9Ex* proxy = nullptr;
        HRESULT wrapHr = WrapDeviceEx(realEx, &proxy);
        *out = proxy;
        return wrapHr;
    }

    *out = realBase;
    return S_OK;
}

class D3D9ExProxy : public IDirect3D9Ex
{
public:
    explicit D3D9ExProxy(IDirect3D9Ex* real) : real_(real) {}

    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void** ppvObj) override
    {
        if (!ppvObj)
            return E_POINTER;
        if (IsEqualGUID(riid, IID_IUnknown) ||
            IsEqualGUID(riid, IID_IDirect3D9) ||
            IsEqualGUID(riid, IID_IDirect3D9Ex))
        {
            *ppvObj = static_cast<IDirect3D9Ex*>(this);
            AddRef();
            return S_OK;
        }
        return real_->QueryInterface(riid, ppvObj);
    }

    ULONG STDMETHODCALLTYPE AddRef() override { return real_->AddRef(); }
    ULONG STDMETHODCALLTYPE Release() override
    {
        ULONG refs = real_->Release();
        if (refs == 0)
            delete this;
        return refs;
    }

    HRESULT STDMETHODCALLTYPE RegisterSoftwareDevice(void* pInitializeFunction) override { return real_->RegisterSoftwareDevice(pInitializeFunction); }
    UINT STDMETHODCALLTYPE GetAdapterCount() override { return real_->GetAdapterCount(); }
    HRESULT STDMETHODCALLTYPE GetAdapterIdentifier(UINT Adapter, DWORD Flags, D3DADAPTER_IDENTIFIER9* pIdentifier) override { return real_->GetAdapterIdentifier(Adapter, Flags, pIdentifier); }
    UINT STDMETHODCALLTYPE GetAdapterModeCount(UINT Adapter, D3DFORMAT Format) override { return real_->GetAdapterModeCount(Adapter, Format); }
    HRESULT STDMETHODCALLTYPE EnumAdapterModes(UINT Adapter, D3DFORMAT Format, UINT Mode, D3DDISPLAYMODE* pMode) override { return real_->EnumAdapterModes(Adapter, Format, Mode, pMode); }
    HRESULT STDMETHODCALLTYPE GetAdapterDisplayMode(UINT Adapter, D3DDISPLAYMODE* pMode) override { return real_->GetAdapterDisplayMode(Adapter, pMode); }
    HRESULT STDMETHODCALLTYPE CheckDeviceType(UINT Adapter, D3DDEVTYPE DevType, D3DFORMAT AdapterFormat, D3DFORMAT BackBufferFormat, BOOL bWindowed) override { return real_->CheckDeviceType(Adapter, DevType, AdapterFormat, BackBufferFormat, bWindowed); }
    HRESULT STDMETHODCALLTYPE CheckDeviceFormat(UINT Adapter, D3DDEVTYPE DeviceType, D3DFORMAT AdapterFormat, DWORD Usage, D3DRESOURCETYPE RType, D3DFORMAT CheckFormat) override { return real_->CheckDeviceFormat(Adapter, DeviceType, AdapterFormat, Usage, RType, CheckFormat); }
    HRESULT STDMETHODCALLTYPE CheckDeviceMultiSampleType(UINT Adapter, D3DDEVTYPE DeviceType, D3DFORMAT SurfaceFormat, BOOL Windowed, D3DMULTISAMPLE_TYPE MultiSampleType, DWORD* pQualityLevels) override { return real_->CheckDeviceMultiSampleType(Adapter, DeviceType, SurfaceFormat, Windowed, MultiSampleType, pQualityLevels); }
    HRESULT STDMETHODCALLTYPE CheckDepthStencilMatch(UINT Adapter, D3DDEVTYPE DeviceType, D3DFORMAT AdapterFormat, D3DFORMAT RenderTargetFormat, D3DFORMAT DepthStencilFormat) override { return real_->CheckDepthStencilMatch(Adapter, DeviceType, AdapterFormat, RenderTargetFormat, DepthStencilFormat); }
    HRESULT STDMETHODCALLTYPE CheckDeviceFormatConversion(UINT Adapter, D3DDEVTYPE DeviceType, D3DFORMAT SourceFormat, D3DFORMAT TargetFormat) override { return real_->CheckDeviceFormatConversion(Adapter, DeviceType, SourceFormat, TargetFormat); }
    HRESULT STDMETHODCALLTYPE GetDeviceCaps(UINT Adapter, D3DDEVTYPE DeviceType, D3DCAPS9* pCaps) override { return real_->GetDeviceCaps(Adapter, DeviceType, pCaps); }
    HMONITOR STDMETHODCALLTYPE GetAdapterMonitor(UINT Adapter) override { return real_->GetAdapterMonitor(Adapter); }
    HRESULT STDMETHODCALLTYPE CreateDevice(UINT Adapter, D3DDEVTYPE DeviceType, HWND hFocusWindow, DWORD BehaviorFlags, D3DPRESENT_PARAMETERS* pPresentationParameters, IDirect3DDevice9** ppReturnedDeviceInterface) override
    {
        HRESULT hr = real_->CreateDevice(Adapter, DeviceType, hFocusWindow, BehaviorFlags, pPresentationParameters, ppReturnedDeviceInterface);
        if (SUCCEEDED(hr) && ppReturnedDeviceInterface && *ppReturnedDeviceInterface)
            hr = WrapDevice9(*ppReturnedDeviceInterface, ppReturnedDeviceInterface);
        return hr;
    }
    UINT STDMETHODCALLTYPE GetAdapterModeCountEx(UINT Adapter, CONST D3DDISPLAYMODEFILTER* pFilter) override { return real_->GetAdapterModeCountEx(Adapter, pFilter); }
    HRESULT STDMETHODCALLTYPE EnumAdapterModesEx(UINT Adapter, CONST D3DDISPLAYMODEFILTER* pFilter, UINT Mode, D3DDISPLAYMODEEX* pMode) override { return real_->EnumAdapterModesEx(Adapter, pFilter, Mode, pMode); }
    HRESULT STDMETHODCALLTYPE GetAdapterDisplayModeEx(UINT Adapter, D3DDISPLAYMODEEX* pMode, D3DDISPLAYROTATION* pRotation) override { return real_->GetAdapterDisplayModeEx(Adapter, pMode, pRotation); }
    HRESULT STDMETHODCALLTYPE CreateDeviceEx(UINT Adapter, D3DDEVTYPE DeviceType, HWND hFocusWindow, DWORD BehaviorFlags, D3DPRESENT_PARAMETERS* pPresentationParameters, D3DDISPLAYMODEEX* pFullscreenDisplayMode, IDirect3DDevice9Ex** ppReturnedDeviceInterface) override
    {
        HRESULT hr = real_->CreateDeviceEx(Adapter, DeviceType, hFocusWindow, BehaviorFlags, pPresentationParameters, pFullscreenDisplayMode, ppReturnedDeviceInterface);
        if (SUCCEEDED(hr) && ppReturnedDeviceInterface && *ppReturnedDeviceInterface)
            hr = WrapDeviceEx(*ppReturnedDeviceInterface, ppReturnedDeviceInterface);
        return hr;
    }
    HRESULT STDMETHODCALLTYPE GetAdapterLUID(UINT Adapter, LUID* pLUID) override { return real_->GetAdapterLUID(Adapter, pLUID); }

private:
    IDirect3D9Ex* real_;
};

typedef HRESULT (WINAPI *Direct3DCreate9ExReal_t)(UINT, IDirect3D9Ex**);

static Direct3DCreate9ExReal_t ResolveDirect3DCreate9Ex()
{
    static Direct3DCreate9ExReal_t fn = nullptr;
    if (fn)
        return fn;

    HMODULE d3d9 = GetModuleHandleA("d3d9.dll");
    if (!d3d9)
        d3d9 = LoadLibraryA("d3d9.dll");
    if (d3d9)
        fn = (Direct3DCreate9ExReal_t)GetProcAddress(d3d9, "Direct3DCreate9Ex");
    return fn;
}

#if defined(_M_IX86)
#pragma comment(linker, "/EXPORT:BohDirect3DCreate9Ex=_BohDirect3DCreate9Ex@8")
#endif

extern "C" __declspec(dllexport) HRESULT WINAPI BohDirect3DCreate9Ex(
    UINT SDKVersion,
    IDirect3D9Ex** ppD3D)
{
    if (!ppD3D)
        return E_POINTER;
    *ppD3D = nullptr;

    Direct3DCreate9ExReal_t realFn = ResolveDirect3DCreate9Ex();
    if (!realFn)
        return D3DERR_NOTAVAILABLE;

    IDirect3D9Ex* real = nullptr;
    HRESULT hr = realFn(SDKVersion, &real);
    if (FAILED(hr) || !real)
        return hr;

    D3D9ExProxy* proxy = new (std::nothrow) D3D9ExProxy(real);
    if (!proxy)
    {
        real->Release();
        return E_OUTOFMEMORY;
    }

    *ppD3D = proxy;
    Log("Created D3D9Ex proxy: real=%p proxy=%p", real, proxy);
    return hr;
}

static void Initialize()
{
    LoadConfig();
    ResolveDirect3DCreate9Ex();
    Log("D3D proxy mode initialized; waiting for static WARP bridge call");
}
#endif

// ============================================================================
// Layered GDI window overlay — no D3D interaction, completely safe
// ============================================================================

static HWND g_overlayWnd = nullptr;

static void UpdateOverlayWindow()
{
    if (!g_overlayWnd || !IsWindow(g_overlayWnd)) return;
    if (!g_showFps && !g_showFrameMs) return;

    // One or two lines depending on which toggles are active
    int w = 90;
    int lineH = 16;
    int lines = (g_showFps ? 1 : 0) + (g_showFrameMs ? 1 : 0);
    int h = lines * lineH;

    HDC screenDC = GetDC(nullptr);
    if (!screenDC) return;

    // Lazily create cached GDI resources
    if (!g_overlayMemDC)
    {
        g_overlayMemDC = CreateCompatibleDC(screenDC);
        if (!g_overlayMemDC) { ReleaseDC(nullptr, screenDC); return; }

        BITMAPINFO bmi = {};
        bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
        bmi.bmiHeader.biWidth = w;
        bmi.bmiHeader.biHeight = -(lineH * 2);  // always allocate for 2 lines
        bmi.bmiHeader.biPlanes = 1;
        bmi.bmiHeader.biBitCount = 32;
        bmi.bmiHeader.biCompression = BI_RGB;

        g_overlayHbm = CreateDIBSection(g_overlayMemDC, &bmi, DIB_RGB_COLORS, &g_overlayBits, nullptr, 0);
        if (!g_overlayHbm || !g_overlayBits)
        {
            DeleteDC(g_overlayMemDC); g_overlayMemDC = nullptr;
            ReleaseDC(nullptr, screenDC); return;
        }
        g_overlayOldBmp = SelectObject(g_overlayMemDC, g_overlayHbm);

        g_overlayFont = CreateFontA(14, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS,
            DEFAULT_QUALITY, DEFAULT_PITCH | FF_SWISS, "Consolas");
        if (!g_overlayFont)
        {
            SelectObject(g_overlayMemDC, g_overlayOldBmp);  // restore original
            g_overlayOldBmp = nullptr;
            DeleteObject(g_overlayHbm);  g_overlayHbm  = nullptr;
            DeleteDC(g_overlayMemDC);    g_overlayMemDC = nullptr;
            g_overlayBits = nullptr;
            ReleaseDC(nullptr, screenDC); return;
        }
        g_overlayOldFont = SelectObject(g_overlayMemDC, g_overlayFont);
    }

    // Clear to transparent black (full 2-line bitmap)
    memset(g_overlayBits, 0, w * lineH * 2 * 4);

    // Draw text
    SetBkMode(g_overlayMemDC, TRANSPARENT);
    SetTextColor(g_overlayMemDC, RGB(255, 255, 255));  // white text

    int top = 1;
    if (g_showFps)
    {
        char line[32];
        snprintf(line, sizeof(line), "FPS %u", g_fps);
        RECT rc = { 3, top, w - 3, top + 14 };
        DrawTextA(g_overlayMemDC, line, -1, &rc, DT_NOCLIP | DT_SINGLELINE);
        top += lineH;
    }
    if (g_showFrameMs)
    {
        char line[32];
        if (PingIsValid())
            snprintf(line, sizeof(line), "PING %u", PingGetResult());
        else
            snprintf(line, sizeof(line), "MS  %.1f", g_frameMs);
        RECT rc = { 3, top, w - 3, top + 14 };
        DrawTextA(g_overlayMemDC, line, -1, &rc, DT_NOCLIP | DT_SINGLELINE);
    }

    // Fix alpha on the used portion: any non-black pixel gets full alpha
    DWORD* pix = (DWORD*)g_overlayBits;
    int totalPixels = w * h;
    for (int i = 0; i < totalPixels; i++)
    {
        if (pix[i] & 0x00FFFFFF)
            pix[i] = pix[i] | 0xFF000000;
        else
            pix[i] = 0;
    }

    POINT srcPos = { 0, 0 };
    SIZE size = { w, h };
    BLENDFUNCTION blend = { AC_SRC_OVER, 0, 255, AC_SRC_ALPHA };
    // Pass NULL for pptDst so UpdateLayeredWindow does NOT override position
    UpdateLayeredWindow(g_overlayWnd, screenDC, nullptr, &size, g_overlayMemDC, &srcPos, 0, &blend, ULW_ALPHA);

    ReleaseDC(nullptr, screenDC);
}

static DWORD WINAPI OverlayThread(LPVOID)
{
    // Wait for game window — try exact title first, then fall back to
    // enumerating visible windows owned by the current process.
    HWND gameWnd = nullptr;
    const char* title = "Banquet of Heroes: Ragnarok Online";

    for (int i = 0; i < 300 && !g_shutdown; i++)
    {
        // Primary: exact title match
        gameWnd = FindWindowA(nullptr, title);
        if (gameWnd)
        {
            DWORD pid = 0;
            GetWindowThreadProcessId(gameWnd, &pid);
            if (pid == GetCurrentProcessId())
                break;
            gameWnd = nullptr;
        }
        Sleep(100);
    }

    // Fallback: if the title didn't match (private server, renamed window, etc.),
    // enumerate visible top-level windows owned by this process.
    if (!gameWnd || !IsWindow(gameWnd))
    {
        DWORD myPid = GetCurrentProcessId();
        struct EnumCtx { DWORD pid; HWND hwnd; char title[256]; };
        EnumCtx ctx = { myPid, nullptr, "" };
        EnumWindows([](HWND h, LPARAM lp) -> BOOL {
            EnumCtx* c = (EnumCtx*)lp;
            DWORD pid = 0;
            GetWindowThreadProcessId(h, &pid);
            if (pid == c->pid && IsWindowVisible(h))
            {
                char buf[256];
                GetWindowTextA(h, buf, sizeof(buf));
                // Prefer a window with a non-empty title
                if (buf[0])
                {
                    c->hwnd = h;
                    strcpy_s(c->title, buf);
                    return FALSE;  // stop enumeration
                }
                if (!c->hwnd)
                    c->hwnd = h;  // fallback if no titled window found
            }
            return TRUE;
        }, (LPARAM)&ctx);
        if (ctx.hwnd)
        {
            gameWnd = ctx.hwnd;
            Log("Found game window via fallback enumeration: %p (title=\"%s\")", gameWnd, ctx.title);
        }
    }

    if (!gameWnd || !IsWindow(gameWnd))
    {
        Log("Could not find game window");
        return 0;
    }

    Log("Found game window: %p", gameWnd);

    // Create layered overlay window — register class once
    if (!g_overlayClassRegistered)
    {
        WNDCLASSA wc = {};
        wc.lpfnWndProc = DefWindowProcA;
        wc.hInstance = g_hModule;
        wc.lpszClassName = "FpsOverlayWnd";
        if (!RegisterClassA(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
        {
            Log("Failed to register window class (err=%d)", GetLastError());
            return 0;
        }
        g_overlayClassRegistered = true;
    }

    g_overlayWnd = CreateWindowExA(
        WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_NOACTIVATE,
        "FpsOverlayWnd", "",
        WS_POPUP,
        0, 0, 90, 32,
        nullptr, nullptr, g_hModule, nullptr);

    if (!g_overlayWnd)
    {
        Log("Failed to create overlay window");
        return 0;
    }

    Log("Overlay window created: %p (size 90x32)", g_overlayWnd);

    // Update position and content
    int loopCount = 0;
    while (!g_shutdown)
    {
        loopCount++;
        SyncClientOptions();
        if (IsWindow(gameWnd) && IsWindow(g_overlayWnd))
        {
            // Real network ping via ICMP (once per second)
            PingUpdate();

            // Only show when game window is focused/active (use PID check, not title substring)
            HWND fg = GetForegroundWindow();
            bool gameActive = false;
            if (fg)
            {
                DWORD fgPid = 0;
                GetWindowThreadProcessId(fg, &fgPid);
                gameActive = (fgPid == GetCurrentProcessId());
            }

            bool visible = (g_showFps || g_showFrameMs) && gameActive;
            if (visible)
            {
                int lines = (g_showFps ? 1 : 0) + (g_showFrameMs ? 1 : 0);
                int winH = lines * 16;
                SetWindowPos(g_overlayWnd, HWND_TOPMOST, g_posX, g_posY, 90, winH,
                    SWP_NOACTIVATE | SWP_SHOWWINDOW);
                UpdateOverlayWindow();
            }
            else
            {
                ShowWindow(g_overlayWnd, SW_HIDE);
            }
        }
        else if (!IsWindow(gameWnd))
        {
            Log("Loop %d: game window closed, exiting overlay thread", loopCount);
            break;
        }
        else
        {
            Log("Loop %d: window invalid gameWnd=%d overlay=%d", loopCount,
                IsWindow(gameWnd), IsWindow(g_overlayWnd));
        }
        Sleep(250);  // 4Hz polling — was 50ms (20Hz), reduced to minimize CPU wakeups
        if (g_shutdown)
            break;  // DllMain is tearing us down — exit cleanly without touching windows
    }

    if (!g_shutdown && g_overlayWnd && IsWindow(g_overlayWnd))
        DestroyWindow(g_overlayWnd);
    g_overlayWnd = nullptr;
    return 0;
}

// ============================================================================
// DLL entry
// ============================================================================

BOOL APIENTRY DllMain(HMODULE hModule, DWORD reason, LPVOID)
{
    switch (reason)
    {
    case DLL_PROCESS_ATTACH:
        g_hModule = hModule;
        DisableThreadLibraryCalls(hModule);
        Log("DLL_PROCESS_ATTACH: module=%p", hModule);
        Initialize();
        g_thread = CreateThread(nullptr, 0, OverlayThread, nullptr, 0, nullptr);
        break;

    case DLL_PROCESS_DETACH:
        g_shutdown = true;
        PingShutdown();
        if (g_thread)
        {
            DWORD waitResult = WaitForSingleObject(g_thread, 3000);
            if (waitResult == WAIT_TIMEOUT)
            {
                Log("WARNING: Overlay thread did not exit within 3s — "
                    "skipping window/vtable cleanup to avoid use-after-free");
                CloseHandle(g_thread);
                g_thread = nullptr;
                // Thread may still be running.  Do NOT destroy g_overlayWnd
                // or restore the vtable — the thread could be using them.
                // The OS will reclaim everything on process exit.
#if !BOH_FPS_D3D_PROXY
                RestoreIat();
#endif
                DestroyOverlayResources();
                break;
            }
            CloseHandle(g_thread);
            g_thread = nullptr;
        }
#if !BOH_FPS_D3D_PROXY
        RestoreIat();
        RestoreVtable();
#endif
        DestroyOverlayResources();
        if (g_overlayWnd && IsWindow(g_overlayWnd))
            DestroyWindow(g_overlayWnd);
        g_overlayWnd = nullptr;
        if (g_overlayClassRegistered)
            UnregisterClassA("FpsOverlayWnd", g_hModule);
        break;
    }
    return TRUE;
}

// Export for WARP import table
extern "C" __declspec(dllexport) void FpsPingOverlayInit() {}

static LONG ToggleFlag(volatile LONG* flag)
{
    LONG current = InterlockedCompareExchange(flag, 0, 0);
    return InterlockedExchange(flag, current ? FALSE : TRUE);
}

extern "C" __declspec(dllexport) void ToggleFpsOverlay()
{
    if (!BohLicense::IsEnabled(FEATURE_FPS_OVERLAY))
        return;
    const LONG enabled = ToggleFlag(&g_showFps);
    WriteClientOption(kFpsOverlayOption, enabled != FALSE);
}

extern "C" __declspec(dllexport) void TogglePingOverlay()
{
    if (!BohLicense::IsEnabled(FEATURE_PING_OVERLAY))
        return;
    const LONG enabled = ToggleFlag(&g_showFrameMs);
    WriteClientOption(kPingOverlayOption, enabled != FALSE);
}

extern "C" __declspec(dllexport) void SetFpsPingOverlayOption(
    uint32_t optionId,
    int enabled)
{
    if (optionId == kFpsOverlayOption &&
        BohLicense::IsEnabled(FEATURE_FPS_OVERLAY))
    {
        SetFlag(&g_showFps, enabled != 0);
        WriteClientOption(optionId, enabled != 0);
        g_fpsOptionSynced = true;
        return;
    }

    if (optionId == kPingOverlayOption &&
        BohLicense::IsEnabled(FEATURE_PING_OVERLAY))
    {
        SetFlag(&g_showFrameMs, enabled != 0);
        WriteClientOption(optionId, enabled != 0);
        g_pingOptionSynced = true;
    }
}

// Backward-compatible combined toggle for older import specs.
extern "C" __declspec(dllexport) void ToggleOverlay()
{
    ToggleFlag(&g_showFps);
    ToggleFlag(&g_showFrameMs);
}
