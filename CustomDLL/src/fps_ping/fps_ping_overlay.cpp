// FPS/Ping Overlay for Ragnarok Online — Gepard-safe, no-D3DX version
// Loaded via WARP CustomDLL.applySpec() as a normal startup import.
// Does NOT hook ws2_32.recv or any system-DLL exports at runtime.
// Hooks D3D9 EndScene by IAT-patching Direct3DCreate9Ex, then vtable patch.
// FPS is measured client-side. Ping is omitted (would require recv hook).
// Frame time in ms is shown as a lag indicator instead.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdio.h>
#include <d3d9.h>

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
        LoadConfig();
        if (!PatchIAT())
            Log("IAT patch failed, overlay will not work");
        else
            Log("IAT patch applied, waiting for game to create D3D device...");
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
                DestroyOverlayResources();
                break;
            }
            CloseHandle(g_thread);
            g_thread = nullptr;
        }
        RestoreVtable();
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
    ToggleFlag(&g_showFps);
}

extern "C" __declspec(dllexport) void TogglePingOverlay()
{
    ToggleFlag(&g_showFrameMs);
}

// Backward-compatible combined toggle for older import specs.
extern "C" __declspec(dllexport) void ToggleOverlay()
{
    ToggleFlag(&g_showFps);
    ToggleFlag(&g_showFrameMs);
}
