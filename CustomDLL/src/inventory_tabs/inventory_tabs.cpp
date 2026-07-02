// Image-Based Inventory Tabs — 2025-07-16 Ragexe
// ============================================================================
// Replaces the inventory window's text tab labels ("Use"/"Eqp"/"Etc"/"Fav")
// with BMP images (tab_pri_%02d.bmp) by overlaying them through the game's OWN
// image-draw pipeline — the exact sequence the storage window already uses.
//
// Technique (Option A, v2 — hooks the TAB CONTROL, not the window):
//   The "Use/Eqp/Etc/Fav" labels are drawn by a separate TAB CONTROL object at
//   [invWnd+0x118] (class vtable 0x0102DD44), whose per-frame draw is
//   vtable[20] = 0x00857910. The inventory WINDOW's own [20] (0x00946DA0) only
//   draws the slot grid — that is why the first version painted over the title.
//
//   Three hooks (all .rdata vtable-entry swaps, VirtualProtect'd writable —
//   same trick rune_visual uses on surface vtables):
//     1. Inventory window [20] (0x00946DA0): capture g_inv_tabctrl =
//        [invWnd+0x118] so we can tell the inventory's tab control apart from
//        any other control sharing class 0x0102DD44. Then run original.
//     2. Tab control [20] (0x00857910): run original (draws the 4 text tabs),
//        then — for the inventory tab control only — overlay
//        tab_pri_{selected+1}.bmp at the control's OWN origin (0,0). Because we
//        draw on the tab control itself, (0,0) lands exactly on the tab strip
//        and the opaque tab graphic covers the text. The real tab control still
//        handles clicks, so tab switching keeps working.
//     3. Tab control [28] (0x0085A170): OnMouseMove. The engine's position math
//        assumes horizontal tabs. We re-show the tooltip at the actual cursor
//        position (control-local → screen via 0x00A1EF70) using our own
//        g_tab_tips[] strings.
//
//   Selected tab index = [tabCtrl+0x7C] (confirmed: cmp [esi+0x7C],ebx in the
//   per-tab draw 0x00847330). tab_pri_01..04 map to selected 0..3.
//
//   The overlay reproduces the storage tab loader (0x008262E0) verbatim:
//       sprintf(buf, fmt, sel+1)   via 0x00529850
//       mgr     = GetTexMgr()       via 0x00A90350
//       conv    = ConvPath(buf)     via 0x00A9F030
//       surface = mgr->Load(conv)   via 0x00A8D4A0 (thiscall)
//       kImageDraw(this,x,y,surf,0) via 0x00A1D260 (thiscall)
//     The format string is built by copying the engine's own
//     "...\basic_interface\tab_itm_%02d.bmp" (0x0102AC48, EUC-KR prefix) and
//     swapping "itm" -> "pri" so the on-disk tab_pri_*.bmp files are used.
//
//   Click alignment + clipping (the BMP is 21x134; the tab control surface is
//   18x217). The click hit-test (0x00848E60) maps mouse-Y by subtracting each
//   tab's height from the array at [tabCtrl+0xCC]; the per-tab draw uses the
//   same array. The BMP's four tab bands are 34/67/100/134 px => heights
//   {34,33,33,34}. We therefore overwrite [tabCtrl+0xCC] so the click regions
//   line up exactly with the drawn image, blank the std::string labels in the
//   vector at [tabCtrl+0xB4] so leftover text cannot stretch the strip, and can
//   optionally draw on the wider parent window surface so the 21px image is not
//   clipped by the 18px control surface.
//
// Env-tunable (no rebuild needed; mirrors how rune_visual was tuned):
//   BOH_INVTABS           0/off -> disable drawing (default ON)
//   BOH_INVTABS_LOG       1/on  -> enable log (default OFF)
//   BOH_INVTABS_SKIP_ORIG 1     -> do NOT call original tab draw (image only)
//   BOH_INVTABS_CLEAR     0/off -> do NOT wipe the text layer (default ON)
//   BOH_INVTABS_BLANK     0/off -> do NOT blank tab labels (default ON)
//   BOH_INVTABS_FITCLICK  0/off -> do NOT override click heights (default ON)
//   BOH_INVTABS_TABH      int   -> uniform per-tab height override (0=use BMP bands)
//   BOH_INVTABS_ONPARENT  1     -> draw on window surface (uncut 21px) (default OFF)
//   BOH_INVTABS_TIPS      0/off -> do NOT show hover tooltips (default ON)
//   BOH_INVTABS_TIP0..3   str   -> override tooltip text per tab
//   BOH_INVTABS_TIPDX/DY  int   -> tooltip offset from cursor (default 10,12)
//   BOH_INVTABS_X / _Y    int   -> draw origin offset (default 0,0)
//   BOH_INVTABS_IDXOFF    int   -> byte offset of selected-tab index (default 0x7C)
//   BOH_INVTABS_FORCEIDX  int   -> force a fixed tab image index (default -1)
//
//   Hover tooltips: the engine's built-in OnMouseMove (0x0085A170) computes the
//   tooltip position from the tab's own geometry — it was written for HORIZONTAL
//   tabs (feeds the vertical tab offset as X and pins Y to controlTop-20), so on
//   our vertical strip every tooltip sticks to the window top. We replace
//   vtable[28] with our own handler that re-shows the tooltip at the cursor
//   position (transformed to screen coords via ClientToScr 0x00A1EF70) using our
//   own g_tab_tips[] strings — we never touch the engine's [0xDC] vector.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include <stdio.h>

#ifndef BOH_INVENTORY_TABS_STATIC_BRIDGES
#define BOH_INVENTORY_TABS_STATIC_BRIDGES 1
#endif

namespace {

static constexpr DWORD kImageBase     = 0x00400000;
static constexpr DWORD kInvWndVtable  = 0x0103D460; // inventory window vtable
static constexpr int   kInvWndSlot    = 20;         // window vtable[20] (slot-grid draw)
static constexpr DWORD kInvWndOrigDraw= 0x00946DA0; // expected original at window [20]
static constexpr DWORD kTabCtrlPtr    = 0x118;      // [invWnd+0x118] = tab control instance
static constexpr DWORD kTabVtable     = 0x0102DD44; // tab control class vtable
static constexpr int   kTabSlot       = 20;         // tab vtable[20] = draw (0x00857910)
static constexpr DWORD kTabOrigDraw   = 0x00857910; // expected original at tab [20]
static constexpr int   kTabMouseSlot  = 28;         // tab vtable[28] = OnMouseMove
static constexpr DWORD kTabMouseOrig  = 0x0085A170; // expected original at tab [28]
static constexpr DWORD kGetTexMgr     = 0x00A90350; // singleton getter (cdecl)
static constexpr DWORD kConvPath      = 0x00A9F030; // path -> token   (cdecl)
static constexpr DWORD kLoadSurface   = 0x00A8D4A0; // mgr->Load(token) thiscall
static constexpr DWORD kImageDraw     = 0x00A1D260; // window->Draw(x,y,surf,a) thiscall
static constexpr DWORD kClearSurface  = 0x00A1CB30; // clear ctrl surface [+0x24] (thiscall, colorKey)
static constexpr DWORD kClearColor    = 0xFFFF00FF; // magenta color key (transparent)
static constexpr DWORD kSprintf       = 0x00529850; // sprintf-like (cdecl, varargs)
static constexpr DWORD kStrAssign     = 0x004F1940; // std::string::assign(ptr,len) thiscall
static constexpr DWORD kHitTest       = 0x00848E60; // tab hit-test(x,y)->index thiscall
static constexpr DWORD kClientToScr   = 0x00A1EF70; // ctrl-local -> screen (this,&x,&y) thiscall
static constexpr DWORD kShowTip       = 0x00A753D0; // tooltip display thiscall(mgr,str,x,y,a,b,c)
static constexpr DWORD kTipMgrPtr     = 0x0121333C; // global -> tooltip manager
static constexpr DWORD kFmtItm        = 0x0102AC48; // "..\\basic_interface\\tab_itm_%02d.bmp"

static HMODULE g_module = nullptr;
static DWORD   g_base = 0;
static void*   g_orig_wnd_draw = nullptr;  // original inventory window [20]
static void*   g_orig_tab_draw = nullptr;  // original tab control [20]
static DWORD   g_inv_tabctrl = 0;          // the inventory's tab control instance
static DWORD   g_inv_wnd = 0;              // the inventory window (for on-parent draw)
static char    g_fmt[160] = {};            // built "tab_pri_%02d.bmp" format
static bool    g_fmt_ready = false;

static bool  g_logging_enabled = false;
static bool  g_draw_enabled = true;
static bool  g_skip_original = false;
static bool  g_clear_surface = true;
static int   g_tab_x = 0;
static int   g_tab_y = 0;
static int   g_index_offset = 0x7C;
static int   g_force_index = -1;
static bool  g_blank_labels = true;        // replace tab labels with " "
static bool  g_fit_click = true;           // override [0xCC] heights to match BMP
static bool  g_on_parent = false;          // draw on window surface (uncut 21px)
static int   g_uniform_h = 0;              // if >0, uniform per-tab height
static int   g_tab_heights[4] = { 34, 33, 33, 34 }; // BMP bands 34/67/100/134
static bool  g_tooltips = true;            // show hover tooltips at the cursor
static char  g_tip_buf[4][48] = {};        // tooltip text storage (env-overridable)
static const char* g_tab_tips[4] = {       // defaults (overwritten from env)
    "Usable", "Equipment", "Miscellaneous", "Favorite" };
static void* g_orig_mousemove = nullptr;   // original tab control [28]
static int   g_tip_dx = 10;                // tooltip x offset from cursor
static int   g_tip_dy = 12;                // tooltip y offset from cursor

static LONG  g_draw_log_budget = 40;
static LONG  g_change_log_budget = 40;
static LONG  g_draw_depth = 0;
static int   g_last_idx = -2;
static volatile LONG g_shutdown = 0;

static DWORD va(DWORD address)
{
    return g_base + (address - kImageBase);
}

// ---------------------------------------------------------------------------
// Logging (env-gated, Win32-only — never use C++ I/O inside hook context)
// ---------------------------------------------------------------------------
static void build_log_path(char* out, DWORD out_size, const char* name)
{
    if (out_size == 0)
        return;
    out[0] = 0;
    DWORD len = GetModuleFileNameA(g_module, out, out_size);
    if (len == 0 || len >= out_size) {
        lstrcpynA(out, name, out_size);
        return;
    }
    for (DWORD i = len; i > 0; --i) {
        if (out[i - 1] == '\\' || out[i - 1] == '/') {
            out[i] = 0;
            break;
        }
    }
    lstrcpynA(out + lstrlenA(out), name, out_size - lstrlenA(out));
}

static void write_log_line(const char* text)
{
    if (!g_logging_enabled)
        return;
    char path[MAX_PATH];
    build_log_path(path, sizeof(path), "inventory_tabs_plugin.log");
    HANDLE file = CreateFileA(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE)
        return;
    SetFilePointer(file, 0, nullptr, FILE_END);
    DWORD written = 0;
    WriteFile(file, text, lstrlenA(text), &written, nullptr);
    WriteFile(file, "\r\n", 2, &written, nullptr);
    CloseHandle(file);
}

static void write_logf(const char* fmt, ...)
{
    if (!g_logging_enabled)
        return;
    char buffer[512];
    va_list args;
    va_start(args, fmt);
    wvsprintfA(buffer, fmt, args);
    va_end(args);
    write_log_line(buffer);
}

// ---------------------------------------------------------------------------
// Env config
// ---------------------------------------------------------------------------
static bool env_truthy(const char* name, bool def)
{
    char v[16] = {};
    DWORD len = GetEnvironmentVariableA(name, v, sizeof(v));
    if (len == 0 || len >= sizeof(v))
        return def;
    return !(v[0] == '0' || v[0] == 'n' || v[0] == 'N' ||
             v[0] == 'f' || v[0] == 'F' || v[0] == 'o' || v[0] == 'O');
}

static int env_int(const char* name, int def)
{
    char v[24] = {};
    DWORD len = GetEnvironmentVariableA(name, v, sizeof(v));
    if (len == 0 || len >= sizeof(v))
        return def;
    int sign = 1; int i = 0; int val = 0; bool any = false;
    if (v[0] == '-') { sign = -1; i = 1; }
    for (; v[i]; ++i) {
        if (v[i] < '0' || v[i] > '9') break;
        val = val * 10 + (v[i] - '0');
        any = true;
    }
    return any ? sign * val : def;
}

// Read an env string into `buf` (falls back to `def`); returns buf.
static const char* env_str(const char* name, const char* def, char* buf, int bufsz)
{
    DWORD len = GetEnvironmentVariableA(name, buf, static_cast<DWORD>(bufsz));
    if (len == 0 || len >= static_cast<DWORD>(bufsz))
        lstrcpynA(buf, def, bufsz);
    return buf;
}

// Build the "tab_pri_%02d.bmp" format by copying the engine's tab_itm format
// (keeps the EUC-KR "유저인터페이스\basic_interface\" prefix intact) and
// replacing the "itm" filename token with "pri".
static void build_format()
{
    const char* src = reinterpret_cast<const char*>(va(kFmtItm));
    int n = 0;
    for (; n < (int)sizeof(g_fmt) - 1 && src[n]; ++n)
        g_fmt[n] = src[n];
    g_fmt[n] = 0;

    for (int i = 0; i + 6 < n; ++i) {
        if (g_fmt[i] == 't' && g_fmt[i+1] == 'a' && g_fmt[i+2] == 'b' &&
            g_fmt[i+3] == '_' && g_fmt[i+4] == 'i' && g_fmt[i+5] == 't' && g_fmt[i+6] == 'm') {
            g_fmt[i+4] = 'p';
            g_fmt[i+5] = 'r';
            g_fmt[i+6] = 'i';
            g_fmt_ready = true;
            break;
        }
    }
    write_logf("format src='%s' built='%s' ready=%u", src, g_fmt, g_fmt_ready ? 1 : 0);
}

// ---------------------------------------------------------------------------
// Engine call typedefs (verified from 0x008262E0 disassembly)
// ---------------------------------------------------------------------------
using SprintfFn      = int  (__cdecl*)(char* buf, const char* fmt, int arg);
using GetTexMgrFn    = void*(__cdecl*)();
using ConvPathFn     = void*(__cdecl*)(const char* path);
using LoadSurfaceFn  = void*(__thiscall*)(void* mgr, void* token);
using ImageDrawFn    = void (__thiscall*)(void* self, int x, int y, void* image, int arg4);
using ClearSurfaceFn = void (__thiscall*)(void* self, DWORD colorKey);
using StrAssignFn    = void*(__thiscall*)(void* str, const char* ptr, int len);
using HitTestFn      = int  (__thiscall*)(void* self, int x, int y);
using ClientToScrFn  = void (__thiscall*)(void* self, int* px, int* py);
using ShowTipFn      = void (__thiscall*)(void* mgr, const char* str, int x, int y, int a4, int a5, int a6);
using MouseMoveFn    = void (__thiscall*)(void* self, int x, int y);
using TabDrawFn      = void (__thiscall*)(void* self);

// Load (or fetch cached) surface for tab image index (0-based -> file N+1).
static void* load_tab_surface(int index)
{
    if (!g_fmt_ready)
        return nullptr;

    char path[176];
    auto sprintf_fn = reinterpret_cast<SprintfFn>(va(kSprintf));
    sprintf_fn(path, g_fmt, index + 1);

    auto get_mgr = reinterpret_cast<GetTexMgrFn>(va(kGetTexMgr));
    void* mgr = get_mgr();
    if (!mgr)
        return nullptr;

    auto conv = reinterpret_cast<ConvPathFn>(va(kConvPath));
    void* token = conv(path);
    if (!token)
        return nullptr;

    auto load = reinterpret_cast<LoadSurfaceFn>(va(kLoadSurface));
    return load(mgr, token);
}

// Number of tabs = size of the std::string vector at [tabCtrl+0xB4]
// (begin=[0xB4], end=[0xB8]; each std::string is 0x18 bytes).
static int read_tab_count(BYTE* s)
{
    DWORD begin = *reinterpret_cast<DWORD*>(s + 0xB4);
    DWORD end   = *reinterpret_cast<DWORD*>(s + 0xB8);
    if (end <= begin) return 0;
    int n = static_cast<int>((end - begin) / 0x18);
    if (n < 0) n = 0;
    if (n > 16) n = 16;
    return n;
}

// Overwrite the per-tab height array at [tabCtrl+0xCC] so the click hit-test
// (0x00848E60) and the layout match the BMP's tab bands exactly.
static void apply_tab_heights(BYTE* s, int n)
{
    DWORD* heights = *reinterpret_cast<DWORD**>(s + 0xCC);
    if (!heights || n <= 0) return;
    for (int i = 0; i < n && i < 8; ++i)
        heights[i] = (g_uniform_h > 0) ? static_cast<DWORD>(g_uniform_h)
                                       : static_cast<DWORD>(g_tab_heights[(i < 4) ? i : 3]);
}

// Assign `text` to element i of the std::string vector whose begin-pointer is
// at [tabCtrl+vec_off], via the engine's std::string::assign (handles SSO/heap
// and grows if needed). [0xB4] = drawn labels, [0xDC] = hover tooltips.
static void set_tab_string(BYTE* s, DWORD vec_off, int i, const char* text)
{
    BYTE* begin = *reinterpret_cast<BYTE**>(s + vec_off);
    if (!begin) return;
    void* str = begin + i * 0x18;
    auto assign = reinterpret_cast<StrAssignFn>(va(kStrAssign));
    assign(str, text, lstrlenA(text));
}

// Replace each tab's drawn label (vector at [0xB4]) with " " so leftover text
// cannot influence sizing (the BMP is drawn over it anyway).
static void blank_tab_labels(BYTE* s)
{
    int n = read_tab_count(s);
    for (int i = 0; i < n && i < 16; ++i)
        set_tab_string(s, 0xB4, i, " ");
}

// Inventory window vtable[20] (0x00946DA0). thiscall: ECX = inventory window.
// Captures the inventory's tab control instance (so the tab hook can tell it
// apart from other controls sharing class 0x0102DD44), then runs original.
extern "C" void __fastcall inv_window_draw_hook(void* self, void* /*edx*/)
{
    if (g_shutdown) return;
    if (self) {
        g_inv_wnd = reinterpret_cast<DWORD>(self);
        __try {
            g_inv_tabctrl = *reinterpret_cast<DWORD*>(
                reinterpret_cast<BYTE*>(self) + kTabCtrlPtr);
        } __except (EXCEPTION_EXECUTE_HANDLER) {}
    }
    if (g_orig_wnd_draw)
        reinterpret_cast<TabDrawFn>(g_orig_wnd_draw)(self);
}

// Tab control vtable[20] (0x00857910). thiscall: ECX = tab control.
// Runs original (draws the 4 text tabs), then overlays tab_pri_{sel+1}.bmp for
// the INVENTORY tab control only, at the control's own origin.
extern "C" void __fastcall tabctrl_draw_hook(void* self, void* /*edx*/)
{
    if (g_shutdown) return;
    LONG depth = InterlockedIncrement(&g_draw_depth);

    if (!g_skip_original && g_orig_tab_draw)
        reinterpret_cast<TabDrawFn>(g_orig_tab_draw)(self);

    if (g_draw_enabled && self &&
        reinterpret_cast<DWORD>(self) == g_inv_tabctrl && depth == 1)
    {
        __try {
            BYTE* s = reinterpret_cast<BYTE*>(self);

            int index = g_force_index;
            if (index < 0)
                index = *reinterpret_cast<int*>(s + g_index_offset);
            if (index < 0) index = 0;
            if (index > 99) index = 99;

            int n = read_tab_count(s);

            // Snapshot the engine's current heights (drives click hit-test) for
            // logging before we overwrite them.
            int oh[4] = { -1, -1, -1, -1 };
            DWORD* heights = *reinterpret_cast<DWORD**>(s + 0xCC);
            if (heights)
                for (int i = 0; i < n && i < 4; ++i) oh[i] = static_cast<int>(heights[i]);

            // (1) Blank labels so leftover text cannot stretch the strip.
            if (g_blank_labels) blank_tab_labels(s);
            // (2) Force per-tab heights to the BMP bands so the click regions
            //     line up exactly with the drawn image.
            if (g_fit_click) apply_tab_heights(s, n);

            void* surface = load_tab_surface(index);

            bool changed = (index != g_last_idx);
            LONG budget = changed ? InterlockedDecrement(&g_change_log_budget)
                                  : InterlockedDecrement(&g_draw_log_budget);
            if (budget >= 0) {
                write_logf("tabdraw self=%08X sel=%d n=%d origH=[%d,%d,%d,%d] pos=(%d,%d) size=(%d,%d) parent=%08X invwnd=%08X surf=%08X onpar=%d",
                    reinterpret_cast<DWORD>(self),
                    *reinterpret_cast<int*>(s + 0x7C), n,
                    oh[0], oh[1], oh[2], oh[3],
                    *reinterpret_cast<int*>(s + 0x1C), *reinterpret_cast<int*>(s + 0x20),
                    *reinterpret_cast<int*>(s + 0x14), *reinterpret_cast<int*>(s + 0x18),
                    *reinterpret_cast<DWORD*>(s + 0x10), g_inv_wnd,
                    reinterpret_cast<DWORD>(surface), g_on_parent ? 1 : 0);
            }
            g_last_idx = index;

            if (surface) {
                auto draw = reinterpret_cast<ImageDrawFn>(va(kImageDraw));
                // Always wipe the tab control surface (removes original text and,
                // in on-parent mode, makes it composite fully transparent).
                if (g_clear_surface) {
                    auto clear = reinterpret_cast<ClearSurfaceFn>(va(kClearSurface));
                    clear(self, kClearColor);
                }
                if (g_on_parent && g_inv_wnd) {
                    // Draw on the wide inventory window surface at the tab
                    // control's position so the full 21px image is not clipped.
                    int cx = *reinterpret_cast<int*>(s + 0x1C);
                    int cy = *reinterpret_cast<int*>(s + 0x20);
                    draw(reinterpret_cast<void*>(g_inv_wnd), cx + g_tab_x, cy + g_tab_y, surface, 0);
                } else {
                    // Draw on the tab control's own surface (origin = tab strip).
                    draw(self, g_tab_x, g_tab_y, surface, 0);
                }
            }
        } __except (EXCEPTION_EXECUTE_HANDLER) {
            write_log_line("exception in tabctrl_draw_hook");
        }
    }

    InterlockedDecrement(&g_draw_depth);
}

// Tab control vtable[28] (0x0085A170) = OnMouseMove. The engine's built-in
// tooltip position math assumes HORIZONTAL tabs (it feeds the tab's vertical
// offset in as the X coordinate and pins Y to controlTop-20), so on our vertical
// strip the box sticks to the window top. We re-show the tooltip at the cursor.
extern "C" void __fastcall tabctrl_mousemove_hook(void* self, void* /*edx*/, int x, int y)
{
    if (g_shutdown) return;
    if (self && reinterpret_cast<DWORD>(self) == g_inv_tabctrl) {
        if (g_tooltips) {
            __try {
                int tab = reinterpret_cast<HitTestFn>(va(kHitTest))(self, x, y);
                if (tab >= 0 && tab < 4 && g_tab_tips[tab] && g_tab_tips[tab][0]) {
                    int sx = x, sy = y;                 // cursor in control-local coords
                    reinterpret_cast<ClientToScrFn>(va(kClientToScr))(self, &sx, &sy);
                    void* mgr = *reinterpret_cast<void**>(va(kTipMgrPtr));
                    if (mgr)
                        reinterpret_cast<ShowTipFn>(va(kShowTip))(
                            mgr, g_tab_tips[tab], sx + g_tip_dx, sy + g_tip_dy, -1, 0, 1);
                }
            } __except (EXCEPTION_EXECUTE_HANDLER) {}
        }
        return; // handled — original only does the mispositioned tooltip
    }
    if (g_orig_mousemove)
        reinterpret_cast<MouseMoveFn>(g_orig_mousemove)(self, x, y);
}

#if defined(_M_IX86)
#pragma comment(linker, "/EXPORT:InventoryTabsWindowDraw=@InventoryTabsWindowDraw@8")
#pragma comment(linker, "/EXPORT:InventoryTabsTabDraw=@InventoryTabsTabDraw@8")
#pragma comment(linker, "/EXPORT:InventoryTabsTabMouseMove=@InventoryTabsTabMouseMove@16")
#endif

extern "C" __declspec(dllexport) void __fastcall InventoryTabsWindowDraw(void* self, void* edx)
{
    inv_window_draw_hook(self, edx);
}

extern "C" __declspec(dllexport) void __fastcall InventoryTabsTabDraw(void* self, void* edx)
{
    tabctrl_draw_hook(self, edx);
}

extern "C" __declspec(dllexport) void __fastcall InventoryTabsTabMouseMove(void* self, void* edx, int x, int y)
{
    tabctrl_mousemove_hook(self, edx, x, y);
}

#if !BOH_INVENTORY_TABS_STATIC_BRIDGES
// Patch one vtable DWORD entry (vtable is in .rdata -> make writable).
static bool patch_vtable_entry(DWORD vtable_va, int slot, void* target, void** out_original)
{
    DWORD* entry = reinterpret_cast<DWORD*>(va(vtable_va) + slot * sizeof(DWORD));

    if (*entry == reinterpret_cast<DWORD>(target))
        return true; // already patched

    DWORD old_protect = 0;
    if (!VirtualProtect(entry, sizeof(DWORD), PAGE_EXECUTE_READWRITE, &old_protect))
        return false;

    if (out_original && *out_original == nullptr)
        *out_original = reinterpret_cast<void*>(*entry);

    *entry = reinterpret_cast<DWORD>(target);
    FlushInstructionCache(GetCurrentProcess(), entry, sizeof(DWORD));
    VirtualProtect(entry, sizeof(DWORD), old_protect, &old_protect);
    return true;
}

// Restore a single vtable entry to its original value
static void restore_vtable_entry(DWORD vtable_va, int slot, void* original)
{
    if (!original)
        return;

    DWORD* entry = reinterpret_cast<DWORD*>(va(vtable_va) + slot * sizeof(DWORD));
    DWORD old_protect = 0;
    if (!VirtualProtect(entry, sizeof(DWORD), PAGE_EXECUTE_READWRITE, &old_protect))
        return;

    *entry = reinterpret_cast<DWORD>(original);
    FlushInstructionCache(GetCurrentProcess(), entry, sizeof(DWORD));
    VirtualProtect(entry, sizeof(DWORD), old_protect, &old_protect);
}

static DWORD WINAPI install_thread(LPVOID)
{
    Sleep(150);
    g_base = reinterpret_cast<DWORD>(GetModuleHandleA(nullptr));
    write_logf("installer start base=%08X draw=%u skip_orig=%u x=%d y=%d idxoff=0x%X forceidx=%d",
        g_base, g_draw_enabled ? 1 : 0, g_skip_original ? 1 : 0,
        g_tab_x, g_tab_y, g_index_offset, g_force_index);

    build_format();
    write_logf("flags onpar=%u blank=%u fitclick=%u tips=%u tabh=%d tip=[%s|%s|%s|%s]",
        g_on_parent ? 1 : 0, g_blank_labels ? 1 : 0, g_fit_click ? 1 : 0,
        g_tooltips ? 1 : 0, g_uniform_h,
        g_tab_tips[0], g_tab_tips[1], g_tab_tips[2], g_tab_tips[3]);

    // 1) Inventory window [20] — capture the tab control instance.
    DWORD* wnd_entry = reinterpret_cast<DWORD*>(va(kInvWndVtable) + kInvWndSlot * sizeof(DWORD));
    bool ok_wnd = false;
    if (*wnd_entry == va(kInvWndOrigDraw)) {
        ok_wnd = patch_vtable_entry(kInvWndVtable, kInvWndSlot,
            reinterpret_cast<void*>(&inv_window_draw_hook), &g_orig_wnd_draw);
    } else {
        write_logf("WARNING window vtable[%d]=%08X expected %08X — skipping window hook",
            kInvWndSlot, *wnd_entry, va(kInvWndOrigDraw));
    }

    // 2) Tab control [20] — the actual tab renderer we overlay onto.
    DWORD* tab_entry = reinterpret_cast<DWORD*>(va(kTabVtable) + kTabSlot * sizeof(DWORD));
    bool ok_tab = false;
    if (*tab_entry == va(kTabOrigDraw)) {
        ok_tab = patch_vtable_entry(kTabVtable, kTabSlot,
            reinterpret_cast<void*>(&tabctrl_draw_hook), &g_orig_tab_draw);
    } else {
        write_logf("WARNING tab vtable[%d]=%08X expected %08X — aborting tab hook",
            kTabSlot, *tab_entry, va(kTabOrigDraw));
    }

    // 3) Tab control [28] — OnMouseMove, to re-position tooltips at the cursor.
    DWORD* mm_entry = reinterpret_cast<DWORD*>(va(kTabVtable) + kTabMouseSlot * sizeof(DWORD));
    bool ok_mm = false;
    if (*mm_entry == va(kTabMouseOrig)) {
        ok_mm = patch_vtable_entry(kTabVtable, kTabMouseSlot,
            reinterpret_cast<void*>(&tabctrl_mousemove_hook), &g_orig_mousemove);
    } else {
        write_logf("WARNING tab vtable[%d]=%08X expected %08X — skipping mousemove hook",
            kTabMouseSlot, *mm_entry, va(kTabMouseOrig));
    }

    write_logf("installer done wnd=%u(orig=%08X) tab=%u(orig=%08X) mm=%u(orig=%08X) tabctrl=%08X",
        ok_wnd ? 1 : 0, reinterpret_cast<DWORD>(g_orig_wnd_draw),
        ok_tab ? 1 : 0, reinterpret_cast<DWORD>(g_orig_tab_draw),
        ok_mm ? 1 : 0, reinterpret_cast<DWORD>(g_orig_mousemove), g_inv_tabctrl);
    return 0;
}
#endif

static BOOL on_dll_main(HMODULE module, DWORD reason, LPVOID reserved)
{
    if (reason == DLL_PROCESS_ATTACH) {
        g_shutdown = 0;
        g_module = module;
        DisableThreadLibraryCalls(module);
        g_logging_enabled = env_truthy("BOH_INVTABS_LOG", false);
        g_draw_enabled    = env_truthy("BOH_INVTABS", true);
        g_skip_original   = env_truthy("BOH_INVTABS_SKIP_ORIG", false);
        g_clear_surface   = env_truthy("BOH_INVTABS_CLEAR", true);
        g_blank_labels    = env_truthy("BOH_INVTABS_BLANK", true);
        g_fit_click       = env_truthy("BOH_INVTABS_FITCLICK", true);
        g_on_parent       = env_truthy("BOH_INVTABS_ONPARENT", false);
        g_tooltips        = env_truthy("BOH_INVTABS_TIPS", true);
        g_uniform_h       = env_int("BOH_INVTABS_TABH", 0);
        g_tab_tips[0]     = env_str("BOH_INVTABS_TIP0", "Usable",        g_tip_buf[0], sizeof(g_tip_buf[0]));
        g_tab_tips[1]     = env_str("BOH_INVTABS_TIP1", "Equipment",     g_tip_buf[1], sizeof(g_tip_buf[1]));
        g_tab_tips[2]     = env_str("BOH_INVTABS_TIP2", "Miscellaneous", g_tip_buf[2], sizeof(g_tip_buf[2]));
        g_tab_tips[3]     = env_str("BOH_INVTABS_TIP3", "Favorite",      g_tip_buf[3], sizeof(g_tip_buf[3]));
        g_tip_dx          = env_int("BOH_INVTABS_TIPDX", 10);
        g_tip_dy          = env_int("BOH_INVTABS_TIPDY", 12);
        g_tab_x           = env_int("BOH_INVTABS_X", 0);
        g_tab_y           = env_int("BOH_INVTABS_Y", 0);
        g_index_offset    = env_int("BOH_INVTABS_IDXOFF", 0x7C);
        g_force_index     = env_int("BOH_INVTABS_FORCEIDX", -1);
        write_log_line("inventory_tabs.dll attach");
#if BOH_INVENTORY_TABS_STATIC_BRIDGES
        g_base = reinterpret_cast<DWORD>(GetModuleHandleA(nullptr));
        g_orig_wnd_draw = reinterpret_cast<void*>(va(kInvWndOrigDraw));
        g_orig_tab_draw = reinterpret_cast<void*>(va(kTabOrigDraw));
        g_orig_mousemove = reinterpret_cast<void*>(va(kTabMouseOrig));
        build_format();
        write_logf("static bridges ready base=%08X draw=%u skip_orig=%u x=%d y=%d idxoff=0x%X forceidx=%d",
            g_base, g_draw_enabled ? 1 : 0, g_skip_original ? 1 : 0,
            g_tab_x, g_tab_y, g_index_offset, g_force_index);
#else
        HANDLE thread = CreateThread(nullptr, 0, install_thread, nullptr, 0, nullptr);
        if (thread)
            CloseHandle(thread);
#endif
    }
    if (reason == DLL_PROCESS_DETACH) {
        g_shutdown = 1;

        // During process termination the OS reclaims everything — do NOT
        // restore vtable entries (target memory may be unmapped).  During
        // explicit DLL unload we MUST restore the original entries.
#if !BOH_INVENTORY_TABS_STATIC_BRIDGES
        const bool isProcessTerm = (reserved != nullptr);
        if (!isProcessTerm) {
            write_log_line("inventory_tabs.dll detach — restoring vtable entries");
            restore_vtable_entry(kInvWndVtable, kInvWndSlot,   g_orig_wnd_draw);
            restore_vtable_entry(kTabVtable,    kTabSlot,       g_orig_tab_draw);
            restore_vtable_entry(kTabVtable,    kTabMouseSlot,  g_orig_mousemove);
        } else {
            write_log_line("inventory_tabs.dll detach — process termination, skipping vtable restore");
        }
#endif
    }
    return TRUE;
}

} // namespace

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved)
{
    return on_dll_main(module, reason, reserved);
}

extern "C" __declspec(dllexport) void InventoryTabsInit(void)
{
    write_log_line("InventoryTabsInit export resolved.");
}
