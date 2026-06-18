#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>

namespace {

static constexpr DWORD kImageBase = 0x00400000;
static constexpr DWORD kGlobalRuneMgr = 0x01318A10;
static constexpr DWORD kRuneRefreshHelper = 0x00730B40;
static constexpr DWORD kRuneRefreshCall1 = 0x00CF953F;
static constexpr DWORD kRuneRefreshCall2 = 0x00CF9591;
static constexpr DWORD kEquipPaneDraw = 0x007E1610;
static constexpr DWORD kImageDraw = 0x00A1D260;
static constexpr DWORD kTextDraw = 0x00A25A70;
static constexpr DWORD kCreateSurfaceObject = 0x00560E50;
static constexpr DWORD kWindowResize = 0x00A1CB70;
static constexpr DWORD kEquipPaneClick = 0x007E4B70;
static constexpr DWORD kEquipPaneTooltip = 0x007E4CC0;
static constexpr DWORD kPreviewEquippedGetterCall = 0x007E69D6;
static constexpr DWORD kButtonEquippedGetterCall1 = 0x007E5C12;
static constexpr DWORD kButtonEquippedGetterCall2 = 0x007E5E47;
static constexpr DWORD kButtonEquippedGetterCall3 = 0x007E5E56;

struct ActiveRuneSet {
    DWORD tag = 0;
    DWORD set = 0;
    DWORD ptr = 0;
};

static HMODULE g_module = nullptr;
static DWORD g_base = 0;
static BYTE g_draw_stolen[5] = {};
static BYTE g_image_draw_stolen[8] = {};
static BYTE g_text_draw_stolen[5] = {};
static BYTE g_click_stolen[6] = {};
static BYTE g_tooltip_stolen[6] = {};
static void* g_draw_trampoline = nullptr;
static void* g_image_draw_trampoline = nullptr;
static void* g_text_draw_trampoline = nullptr;
static void* g_click_trampoline = nullptr;
static void* g_tooltip_trampoline = nullptr;
static void* g_surface_overlay_original = nullptr;
static ActiveRuneSet g_active[3] = {};
static DWORD g_surface_object[3] = {};
static DWORD g_surface_width[3] = {};
static DWORD g_surface_height[3] = {};
static DWORD g_original_pane = 0;
static DWORD g_original_parent = 0;
static DWORD g_original_surface = 0;
static DWORD g_original_width = 0;
static DWORD g_original_height = 0;
static bool g_layout_captured = false;
static DWORD g_layout_extra = 0;
static DWORD g_layout_children[4] = {};
static DWORD g_layout_x[4] = {};
static DWORD g_layout_y[4] = {};
static DWORD g_current_draw_pane = 0;
static DWORD g_current_draw_surface = 0;
static DWORD g_interact_ptr = 0;
static DWORD g_interact_row = 0;
static DWORD g_draw_y_offset = 0;
static LONG g_draw_depth = 0;
static bool g_logging_enabled = false;
static bool g_refresh_hooks_enabled = false;
static bool g_visual_hooks_enabled = false;
static LONG g_trace_log_budget = 120;
static LONG g_trace_draw_budget = 30;
static LONG g_trace_cache_budget = 40;
static LONG g_draw_log_budget = 40;
static LONG g_overlay_log_budget = 20;
static LONG g_image_log_budget = 20;
static LONG g_text_log_budget = 20;
static LONG g_interact_log_budget = 40;

static DWORD va(DWORD address)
{
    return g_base + (address - kImageBase);
}

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
    build_log_path(path, sizeof(path), "rune_visual_plugin.log");

    HANDLE file = CreateFileA(
        path,
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);

    if (file == INVALID_HANDLE_VALUE)
        return;

    SYSTEMTIME st;
    GetLocalTime(&st);

    char line[512];
    int len = wsprintfA(
        line,
        "[%04u-%02u-%02u %02u:%02u:%02u] %s\r\n",
        st.wYear,
        st.wMonth,
        st.wDay,
        st.wHour,
        st.wMinute,
        st.wSecond,
        text);

    if (len > 0) {
        DWORD written = 0;
        WriteFile(file, line, static_cast<DWORD>(len), &written, nullptr);
    }

    CloseHandle(file);
}

static void write_trace_line(const char* text)
{
    if (!g_logging_enabled)
        return;

    LONG budget = InterlockedDecrement(&g_trace_log_budget);
    if (budget < 0)
        return;

    char path[MAX_PATH];
    build_log_path(path, sizeof(path), "rune_visual_trace.log");

    HANDLE file = CreateFileA(
        path,
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);

    if (file == INVALID_HANDLE_VALUE)
        return;

    SYSTEMTIME st;
    GetLocalTime(&st);

    char line[512];
    int len = wsprintfA(
        line,
        "[%04u-%02u-%02u %02u:%02u:%02u] %s\r\n",
        st.wYear,
        st.wMonth,
        st.wDay,
        st.wHour,
        st.wMinute,
        st.wSecond,
        text);

    if (len > 0) {
        DWORD written = 0;
        WriteFile(file, line, static_cast<DWORD>(len), &written, nullptr);
    }

    CloseHandle(file);
}

static void write_logf(const char* fmt, DWORD a = 0, DWORD b = 0, DWORD c = 0, DWORD d = 0)
{
    char msg[512];
    wsprintfA(msg, fmt, a, b, c, d);
    write_log_line(msg);
}

static void write_tracef(const char* fmt, DWORD a = 0, DWORD b = 0, DWORD c = 0, DWORD d = 0)
{
    char msg[512];
    wsprintfA(msg, fmt, a, b, c, d);
    write_trace_line(msg);
}

static void write_module_loaded_log()
{
    char path[MAX_PATH];
    DWORD len = GetModuleFileNameA(g_module, path, sizeof(path));
    const char* name = "rune visual DLL";

    if (len > 0 && len < sizeof(path)) {
        name = path;
        for (DWORD i = len; i > 0; --i) {
            if (path[i - 1] == '\\' || path[i - 1] == '/') {
                name = path + i;
                break;
            }
        }
    }

    char msg[256];
    wsprintfA(msg, "%s loaded via normal process startup.", name);
    write_log_line(msg);
}

static bool env_logging_enabled()
{
    char value[16] = {};
    DWORD len = GetEnvironmentVariableA("BOH_RUNE_VISUAL_LOG", value, sizeof(value));
    if (len == 0 || len >= sizeof(value))
        return false;

    return !(value[0] == '0' ||
        value[0] == 'n' || value[0] == 'N' ||
        value[0] == 'f' || value[0] == 'F' ||
        value[0] == 'o' || value[0] == 'O');
}

static bool env_visual_hooks_enabled()
{
    char value[16] = {};
    DWORD len = GetEnvironmentVariableA("BOH_RUNE_VISUAL_STACK", value, sizeof(value));
    if (len == 0 || len >= sizeof(value))
        return false;

    return !(value[0] == '0' ||
        value[0] == 'n' || value[0] == 'N' ||
        value[0] == 'f' || value[0] == 'F' ||
        value[0] == 'o' || value[0] == 'O');
}

static bool env_refresh_hooks_enabled()
{
    char value[16] = {};
    DWORD len = GetEnvironmentVariableA("BOH_RUNE_REFRESH_HOOK", value, sizeof(value));
    if (len == 0 || len >= sizeof(value))
        return false;

    return !(value[0] == '0' ||
        value[0] == 'n' || value[0] == 'N' ||
        value[0] == 'f' || value[0] == 'F' ||
        value[0] == 'o' || value[0] == 'O');
}

static bool patch_call(DWORD call_va, void* target)
{
    BYTE* site = reinterpret_cast<BYTE*>(va(call_va));
    if (site[0] != 0xE8) {
        write_logf("patch_call refused: VA=%08X opcode=%02X", call_va, site[0]);
        return false;
    }

    DWORD old_protect = 0;
    if (!VirtualProtect(site, 5, PAGE_EXECUTE_READWRITE, &old_protect))
        return false;

    intptr_t rel = reinterpret_cast<BYTE*>(target) - (site + 5);
    site[0] = 0xE8;
    *reinterpret_cast<int32_t*>(site + 1) = static_cast<int32_t>(rel);

    FlushInstructionCache(GetCurrentProcess(), site, 5);
    VirtualProtect(site, 5, old_protect, &old_protect);
    return true;
}

static bool patch_jmp(DWORD hook_va, void* target, BYTE* stolen, SIZE_T stolen_len, void** trampoline)
{
    BYTE* site = reinterpret_cast<BYTE*>(va(hook_va));
    CopyMemory(stolen, site, stolen_len);

    BYTE* gate = reinterpret_cast<BYTE*>(VirtualAlloc(nullptr, stolen_len + 5, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE));
    if (!gate)
        return false;

    CopyMemory(gate, stolen, stolen_len);
    gate[stolen_len] = 0xE9;
    *reinterpret_cast<int32_t*>(gate + stolen_len + 1) = static_cast<int32_t>((site + stolen_len) - (gate + stolen_len + 5));
    FlushInstructionCache(GetCurrentProcess(), gate, stolen_len + 5);

    DWORD old_protect = 0;
    if (!VirtualProtect(site, stolen_len, PAGE_EXECUTE_READWRITE, &old_protect))
        return false;

    site[0] = 0xE9;
    *reinterpret_cast<int32_t*>(site + 1) = static_cast<int32_t>(reinterpret_cast<BYTE*>(target) - (site + 5));
    for (SIZE_T i = 5; i < stolen_len; ++i)
        site[i] = 0x90;

    FlushInstructionCache(GetCurrentProcess(), site, stolen_len);
    VirtualProtect(site, stolen_len, old_protect, &old_protect);

    *trampoline = gate;
    return true;
}

static void cache_update(DWORD tag, DWORD set, DWORD mgr)
{
    if (tag == 0)
        return;

    DWORD ptr = 0;
    if (mgr != 0)
        ptr = *reinterpret_cast<DWORD*>(mgr + 0x14);

    if (set == 0 || ptr == 0) {
        for (auto& slot : g_active) {
            if (slot.tag == tag) {
                write_logf("cache remove tag=%u set=%u ptr=%08X", tag, slot.set, slot.ptr);
                LONG budget = InterlockedDecrement(&g_trace_cache_budget);
                if (budget >= 0)
                    write_tracef("cache remove tag=%u set=%u ptr=%08X", tag, slot.set, slot.ptr);
                if (g_interact_ptr == slot.ptr) {
                    g_interact_ptr = 0;
                    g_interact_row = 0;
                }
                slot = {};
            }
        }
        return;
    }

    for (auto& slot : g_active) {
        if (slot.tag == tag) {
            slot.set = set;
            slot.ptr = ptr;
            write_logf("cache update tag=%u set=%u ptr=%08X", tag, set, ptr);
            LONG budget = InterlockedDecrement(&g_trace_cache_budget);
            if (budget >= 0)
                write_tracef("cache update tag=%u set=%u ptr=%08X", tag, set, ptr);
            return;
        }
    }

    for (auto& slot : g_active) {
        if (slot.tag == 0) {
            slot.tag = tag;
            slot.set = set;
            slot.ptr = ptr;
            write_logf("cache add tag=%u set=%u ptr=%08X", tag, set, ptr);
            LONG budget = InterlockedDecrement(&g_trace_cache_budget);
            if (budget >= 0)
                write_tracef("cache add tag=%u set=%u ptr=%08X", tag, set, ptr);
            return;
        }
    }

    g_active[0] = { tag, set, ptr };
    write_logf("cache recycle tag=%u set=%u ptr=%08X", tag, set, ptr);
    LONG budget = InterlockedDecrement(&g_trace_cache_budget);
    if (budget >= 0)
        write_tracef("cache recycle tag=%u set=%u ptr=%08X", tag, set, ptr);
}

static int collect_active(DWORD* out, int max_count)
{
    int count = 0;
    for (const auto& slot : g_active) {
        if (slot.tag != 0 && slot.ptr != 0 && count < max_count)
            out[count++] = slot.ptr;
    }
    return count;
}

static bool is_active_ptr(DWORD ptr)
{
    if (ptr == 0)
        return false;

    for (const auto& slot : g_active) {
        if (slot.ptr == ptr)
            return true;
    }

    return false;
}

static DWORD row_height()
{
    return g_original_height != 0 ? g_original_height : 0x52;
}

static DWORD active_ptr_for_y(DWORD y, DWORD* row_out, DWORD* adjusted_y_out)
{
    DWORD cached[3] = {};
    int count = collect_active(cached, 3);
    if (count <= 0)
        return 0;

    DWORD height = row_height();
    DWORD row = height != 0 ? y / height : 0;
    if (row >= static_cast<DWORD>(count))
        row = static_cast<DWORD>(count - 1);

    if (row_out)
        *row_out = row;
    if (adjusted_y_out)
        *adjusted_y_out = height != 0 ? y - (row * height) : y;

    return cached[row];
}

using RuneRefreshFn = DWORD(__thiscall*)(void* mgr, DWORD tag, DWORD set, DWORD arg3, DWORD arg4);
using EquipPaneDrawFn = void(__thiscall*)(void* self);
using EquipPaneMouseFn = void(__thiscall*)(void* self, DWORD x, DWORD y);
using ImageDrawFn = void(__thiscall*)(void* self, DWORD x, DWORD y, DWORD image, DWORD arg4);
using TextDrawFn = void(__thiscall*)(void* self, DWORD x, DWORD y, DWORD text, DWORD arg4, DWORD arg5, DWORD arg6, DWORD arg7, DWORD arg8, DWORD arg9);
using CreateSurfaceObjectFn = DWORD(__cdecl*)(DWORD width, DWORD height, DWORD visible);
using SurfaceOverlayDrawFn = void(__thiscall*)(void* self, DWORD x, DWORD y, DWORD width, DWORD height, DWORD alpha);
using WindowResizeFn = void(__thiscall*)(void* self, DWORD width, DWORD height);
using WindowSetPosFn = void(__thiscall*)(void* self, DWORD x, DWORD y);

extern "C" void __fastcall surface_overlay_draw_hook(void* self, void*, DWORD x, DWORD y, DWORD width, DWORD height, DWORD alpha);

static bool hook_surface_overlay(DWORD surface)
{
    if (surface == 0)
        return false;

    DWORD* vtable = *reinterpret_cast<DWORD**>(surface);
    if (vtable == nullptr)
        return false;

    DWORD* entry = &vtable[0x40 / sizeof(DWORD)];
    if (*entry == reinterpret_cast<DWORD>(&surface_overlay_draw_hook))
        return true;

    DWORD old_protect = 0;
    if (!VirtualProtect(entry, sizeof(DWORD), PAGE_EXECUTE_READWRITE, &old_protect))
        return false;

    if (g_surface_overlay_original == nullptr)
        g_surface_overlay_original = reinterpret_cast<void*>(*entry);

    *entry = reinterpret_cast<DWORD>(&surface_overlay_draw_hook);
    FlushInstructionCache(GetCurrentProcess(), entry, sizeof(DWORD));
    VirtualProtect(entry, sizeof(DWORD), old_protect, &old_protect);
    write_logf("surface overlay hook installed surface=%08X vtbl=%08X", surface, reinterpret_cast<DWORD>(vtable));
    return true;
}

static DWORD get_surface_object(int index, DWORD width, DWORD height)
{
    if (index < 0 || index >= 3)
        return 0;

    if (g_surface_object[index] != 0 && g_surface_width[index] == width && g_surface_height[index] == height)
        return g_surface_object[index];

    auto create_surface = reinterpret_cast<CreateSurfaceObjectFn>(va(kCreateSurfaceObject));
    DWORD surface = create_surface(width, height, 1);
    if (surface != 0) {
        g_surface_object[index] = surface;
        g_surface_width[index] = width;
        g_surface_height[index] = height;
        write_logf("created surface index=%u w=%u h=%u ptr=%08X", static_cast<DWORD>(index), width, height, surface);
        hook_surface_overlay(surface);
    }
    return surface;
}

static void resize_window(void* self, DWORD width, DWORD height)
{
    auto resize = reinterpret_cast<WindowResizeFn>(va(kWindowResize));
    resize(self, width, height);

    DWORD surface = *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(self) + 0x24);
    hook_surface_overlay(surface);
    write_logf("resize pane self=%08X w=%u h=%u surface=%08X", reinterpret_cast<DWORD>(self), width, height, surface);
}

static void set_window_pos(DWORD wnd, DWORD x, DWORD y)
{
    if (wnd == 0)
        return;

    DWORD* vtable = *reinterpret_cast<DWORD**>(wnd);
    if (vtable == nullptr)
        return;

    auto set_pos = reinterpret_cast<WindowSetPosFn>(vtable[0x10 / sizeof(DWORD)]);
    set_pos(reinterpret_cast<void*>(wnd), x, y);
}

static void capture_layout(DWORD parent)
{
    if (g_layout_captured || parent == 0)
        return;

    static const DWORD offsets[] = { 0xC8, 0xCC, 0xD0, 0xD4 };
    for (int i = 0; i < 4; ++i) {
        DWORD child = *reinterpret_cast<DWORD*>(parent + offsets[i]);
        g_layout_children[i] = child;
        if (child != 0) {
            g_layout_x[i] = *reinterpret_cast<DWORD*>(child + 0x1C);
            g_layout_y[i] = *reinterpret_cast<DWORD*>(child + 0x20);
        }
    }

    g_layout_captured = true;
    write_logf("layout capture parent=%08X c8=%08X cc=%08X", parent, g_layout_children[0], g_layout_children[1]);
    write_logf("layout y c8=%u cc=%u d0=%u d4=%u", g_layout_y[0], g_layout_y[1], g_layout_y[2], g_layout_y[3]);
}

static void apply_layout_extra(DWORD parent, DWORD extra)
{
    if (parent == 0)
        return;

    capture_layout(parent);
    if (!g_layout_captured || g_layout_extra == extra)
        return;

    for (int i = 0; i < 4; ++i) {
        DWORD child = g_layout_children[i];
        if (child != 0)
            set_window_pos(child, g_layout_x[i], g_layout_y[i] + extra);
    }

    g_layout_extra = extra;
    write_logf("layout extra parent=%08X extra=%u", parent, extra);
}

static DWORD call_original_refresh(void* mgr, DWORD tag, DWORD set, DWORD arg3, DWORD arg4)
{
    auto fn = reinterpret_cast<RuneRefreshFn>(va(kRuneRefreshHelper));
    return fn(mgr, tag, set, arg3, arg4);
}

extern "C" DWORD __fastcall rune_refresh_hook(void* mgr, void*, DWORD tag, DWORD set, DWORD arg3, DWORD arg4)
{
    write_tracef("refresh enter mgr=%08X tag=%u set=%u", reinterpret_cast<DWORD>(mgr), tag, set);
    DWORD ret = call_original_refresh(mgr, tag, set, arg3, arg4);
    cache_update(tag, set, reinterpret_cast<DWORD>(mgr));
    write_tracef("refresh exit tag=%u set=%u ret=%08X", tag, set, ret);
    return ret;
}

extern "C" DWORD __fastcall selected_equipped_getter_hook(void* mgr, void*)
{
    write_tracef("selected_getter mgr=%08X interact=%08X row=%u", reinterpret_cast<DWORD>(mgr), g_interact_ptr, g_interact_row);
    if (g_interact_ptr != 0 && is_active_ptr(g_interact_ptr))
        return g_interact_ptr;

    if (!mgr)
        return 0;

    return *reinterpret_cast<DWORD*>(reinterpret_cast<DWORD>(mgr) + 0x14);
}

static void record_interaction(void* self, DWORD y, const char* source, DWORD* adjusted_y)
{
    if (reinterpret_cast<DWORD>(self) != g_original_pane) {
        if (adjusted_y)
            *adjusted_y = y;
        return;
    }

    DWORD row = 0;
    DWORD local_y = y;
    DWORD ptr = active_ptr_for_y(y, &row, &local_y);
    if (ptr != 0) {
        g_interact_ptr = ptr;
        g_interact_row = row;

        LONG budget = InterlockedDecrement(&g_interact_log_budget);
        if (budget >= 0)
            write_logf("interact %s row=%u y=%u ptr=%08X", reinterpret_cast<DWORD>(source), row, y, ptr);
    }

    if (adjusted_y)
        *adjusted_y = local_y;
}

extern "C" void __fastcall equip_pane_click_hook(void* self, void*, DWORD x, DWORD y)
{
    DWORD local_y = y;
    DWORD mgr = *reinterpret_cast<DWORD*>(va(kGlobalRuneMgr));
    DWORD original_ptr = mgr != 0 ? *reinterpret_cast<DWORD*>(mgr + 0x14) : 0;
    record_interaction(self, y, "click", &local_y);

    if (mgr != 0 && g_interact_ptr != 0)
        *reinterpret_cast<DWORD*>(mgr + 0x14) = g_interact_ptr;

    auto original_click = reinterpret_cast<EquipPaneMouseFn>(g_click_trampoline);
    original_click(self, x, local_y);

    if (mgr != 0)
        *reinterpret_cast<DWORD*>(mgr + 0x14) = original_ptr;
}

extern "C" void __fastcall equip_pane_tooltip_hook(void* self, void*, DWORD x, DWORD y)
{
    DWORD local_y = y;
    DWORD mgr = *reinterpret_cast<DWORD*>(va(kGlobalRuneMgr));
    DWORD original_ptr = mgr != 0 ? *reinterpret_cast<DWORD*>(mgr + 0x14) : 0;
    record_interaction(self, y, "tooltip", &local_y);

    if (mgr != 0 && g_interact_ptr != 0)
        *reinterpret_cast<DWORD*>(mgr + 0x14) = g_interact_ptr;

    auto original_tooltip = reinterpret_cast<EquipPaneMouseFn>(g_tooltip_trampoline);
    original_tooltip(self, x, local_y);

    if (mgr != 0)
        *reinterpret_cast<DWORD*>(mgr + 0x14) = original_ptr;
}

extern "C" void __fastcall image_draw_hook(void* self, void*, DWORD x, DWORD y, DWORD image, DWORD arg4)
{
    DWORD original_y = y;
    if (reinterpret_cast<DWORD>(self) == g_current_draw_pane && g_draw_y_offset != 0) {
        y += g_draw_y_offset;

        LONG budget = InterlockedDecrement(&g_image_log_budget);
        if (budget >= 0)
            write_logf("image shift pane=%08X y=%u->%u image=%08X", reinterpret_cast<DWORD>(self), original_y, y, image);
    }

    auto original_image_draw = reinterpret_cast<ImageDrawFn>(g_image_draw_trampoline);
    original_image_draw(self, x, y, image, arg4);
}

extern "C" void __fastcall text_draw_hook(void* self, void*, DWORD x, DWORD y, DWORD text, DWORD arg4, DWORD arg5, DWORD arg6, DWORD arg7, DWORD arg8, DWORD arg9)
{
    DWORD original_y = y;
    if (reinterpret_cast<DWORD>(self) == g_current_draw_pane && g_draw_y_offset != 0) {
        y += g_draw_y_offset;

        LONG budget = InterlockedDecrement(&g_text_log_budget);
        if (budget >= 0)
            write_logf("text shift pane=%08X y=%u->%u text=%08X", reinterpret_cast<DWORD>(self), original_y, y, text);
    }

    auto original_text_draw = reinterpret_cast<TextDrawFn>(g_text_draw_trampoline);
    original_text_draw(self, x, y, text, arg4, arg5, arg6, arg7, arg8, arg9);
}

extern "C" void __fastcall surface_overlay_draw_hook(void* self, void*, DWORD x, DWORD y, DWORD width, DWORD height, DWORD alpha)
{
    DWORD original_y = y;
    if (reinterpret_cast<DWORD>(self) == g_current_draw_surface && g_draw_y_offset != 0) {
        y += g_draw_y_offset;

        LONG budget = InterlockedDecrement(&g_overlay_log_budget);
        if (budget >= 0)
            write_logf("overlay shift surface=%08X y=%u->%u alpha=%u", reinterpret_cast<DWORD>(self), original_y, y, alpha);
    }

    auto original_overlay_draw = reinterpret_cast<SurfaceOverlayDrawFn>(g_surface_overlay_original);
    if (original_overlay_draw)
        original_overlay_draw(self, x, y, width, height, alpha);
}

extern "C" void __fastcall equip_pane_draw_hook(void* self, void*)
{
    auto original_draw = reinterpret_cast<EquipPaneDrawFn>(g_draw_trampoline);
    if (!original_draw || !self) {
        write_tracef("draw skip original=%08X self=%08X", reinterpret_cast<DWORD>(original_draw), reinterpret_cast<DWORD>(self));
        return;
    }

    LONG depth = InterlockedIncrement(&g_draw_depth);
    if (depth != 1) {
        write_tracef("draw reenter depth=%u self=%08X", depth, reinterpret_cast<DWORD>(self));
        original_draw(self);
        InterlockedDecrement(&g_draw_depth);
        return;
    }

    DWORD mgr = *reinterpret_cast<DWORD*>(va(kGlobalRuneMgr));
    DWORD cached[3] = {};
    int count = collect_active(cached, 3);
    LONG drawBudget = InterlockedDecrement(&g_trace_draw_budget);
    if (drawBudget >= 0)
        write_tracef("draw enter self=%08X mgr=%08X count=%u", reinterpret_cast<DWORD>(self), mgr, static_cast<DWORD>(count));

    if (mgr == 0 || count <= 1) {
        if (g_original_pane == reinterpret_cast<DWORD>(self) && g_original_height != 0 && g_original_width != 0) {
            DWORD current_height = *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(self) + 0x18);
            if (current_height != g_original_height)
                resize_window(self, g_original_width, g_original_height);
            apply_layout_extra(g_original_parent, 0);
        }
        original_draw(self);
        if (drawBudget >= 0)
            write_tracef("draw single exit self=%08X count=%u", reinterpret_cast<DWORD>(self), static_cast<DWORD>(count));
        InterlockedDecrement(&g_draw_depth);
        return;
    }

    DWORD original_ptr = *reinterpret_cast<DWORD*>(mgr + 0x14);
    DWORD original_width = *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(self) + 0x14);
    DWORD original_height = *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(self) + 0x18);
    DWORD original_surface = *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(self) + 0x24);
    DWORD row_height = g_original_height != 0 && g_original_pane == reinterpret_cast<DWORD>(self) ? g_original_height : original_height;
    if (row_height == 0)
        row_height = 0x52;

    if (g_original_pane != reinterpret_cast<DWORD>(self)) {
        g_original_pane = reinterpret_cast<DWORD>(self);
        g_original_parent = *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(self) + 0x10);
        g_original_surface = original_surface;
        g_original_width = original_width;
        g_original_height = row_height;
        write_logf("capture pane self=%08X w=%u h=%u surface=%08X", g_original_pane, g_original_width, g_original_height, g_original_surface);
    }

    DWORD stacked_height = row_height * static_cast<DWORD>(count);
    if (original_height != stacked_height)
        resize_window(self, original_width, stacked_height);
    DWORD parent = *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(self) + 0x10);
    if (parent != 0 && *reinterpret_cast<DWORD*>(parent + 0xC4) == reinterpret_cast<DWORD>(self))
        apply_layout_extra(parent, stacked_height - row_height);
    DWORD stacked_surface = *reinterpret_cast<DWORD*>(reinterpret_cast<BYTE*>(self) + 0x24);
    hook_surface_overlay(stacked_surface);

    LONG budget = InterlockedDecrement(&g_draw_log_budget);
    if (budget >= 0)
        write_logf("draw stacked count=%u row_h=%u ptr0=%08X ptr1=%08X", count, row_height, cached[0], cached[1]);

    for (int i = 0; i < count; ++i) {
        *reinterpret_cast<DWORD*>(mgr + 0x14) = cached[i];
        g_current_draw_pane = reinterpret_cast<DWORD>(self);
        g_current_draw_surface = stacked_surface;
        g_draw_y_offset = static_cast<DWORD>(i) * row_height;
        if (drawBudget >= 0)
            write_tracef("draw row=%u ptr=%08X offset=%u", static_cast<DWORD>(i), cached[i], g_draw_y_offset);
        original_draw(self);
        g_draw_y_offset = 0;
        g_current_draw_surface = 0;
        g_current_draw_pane = 0;
    }

    *reinterpret_cast<DWORD*>(mgr + 0x14) = original_ptr;
    if (drawBudget >= 0)
        write_tracef("draw stacked exit self=%08X restored=%08X", reinterpret_cast<DWORD>(self), original_ptr);
    InterlockedDecrement(&g_draw_depth);
}

static DWORD WINAPI install_thread(LPVOID)
{
    Sleep(100);
    g_base = reinterpret_cast<DWORD>(GetModuleHandleA(nullptr));

    write_tracef("installer start base=%08X", g_base);
    write_logf("installer start base=%08X", g_base);

    bool ok1 = false;
    bool ok2 = false;
    bool ok3 = false;
    bool ok4 = false;
    bool ok5 = false;
    bool ok6 = false;
    bool ok7 = false;
    bool ok8 = false;
    bool ok9 = false;
    bool ok10 = false;
    bool ok11 = false;

    if (g_refresh_hooks_enabled)
    {
        ok1 = patch_call(kRuneRefreshCall1, reinterpret_cast<void*>(&rune_refresh_hook));
        ok2 = patch_call(kRuneRefreshCall2, reinterpret_cast<void*>(&rune_refresh_hook));
    }
    else
    {
        write_trace_line("refresh hooks disabled; DLL import only");
    }

    if (g_visual_hooks_enabled)
    {
        ok3 = patch_jmp(kEquipPaneDraw, reinterpret_cast<void*>(&equip_pane_draw_hook), g_draw_stolen, 5, &g_draw_trampoline);
        ok4 = patch_jmp(kImageDraw, reinterpret_cast<void*>(&image_draw_hook), g_image_draw_stolen, 7, &g_image_draw_trampoline);
        ok5 = patch_jmp(kTextDraw, reinterpret_cast<void*>(&text_draw_hook), g_text_draw_stolen, 5, &g_text_draw_trampoline);
        ok6 = patch_jmp(kEquipPaneClick, reinterpret_cast<void*>(&equip_pane_click_hook), g_click_stolen, 6, &g_click_trampoline);
        ok7 = patch_jmp(kEquipPaneTooltip, reinterpret_cast<void*>(&equip_pane_tooltip_hook), g_tooltip_stolen, 6, &g_tooltip_trampoline);
        ok8 = patch_call(kPreviewEquippedGetterCall, reinterpret_cast<void*>(&selected_equipped_getter_hook));
        ok9 = patch_call(kButtonEquippedGetterCall1, reinterpret_cast<void*>(&selected_equipped_getter_hook));
        ok10 = patch_call(kButtonEquippedGetterCall2, reinterpret_cast<void*>(&selected_equipped_getter_hook));
        ok11 = patch_call(kButtonEquippedGetterCall3, reinterpret_cast<void*>(&selected_equipped_getter_hook));
    }
    else
    {
        write_trace_line("visual stack hooks disabled; rune refresh cache only");
    }

    write_logf("installer done refresh1=%u refresh2=%u draw=%u image=%u", ok1 ? 1 : 0, ok2 ? 1 : 0, ok3 ? 1 : 0, ok4 ? 1 : 0);
    write_logf("installer text=%u click=%u tooltip=%u preview=%u", ok5 ? 1 : 0, ok6 ? 1 : 0, ok7 ? 1 : 0, ok8 ? 1 : 0);
    write_logf("installer button=%u/%u/%u", ok9 ? 1 : 0, ok10 ? 1 : 0, ok11 ? 1 : 0);
    write_tracef("installer done r1=%u r2=%u draw=%u image=%u", ok1 ? 1 : 0, ok2 ? 1 : 0, ok3 ? 1 : 0, ok4 ? 1 : 0);
    write_tracef("installer done text=%u click=%u tooltip=%u preview=%u", ok5 ? 1 : 0, ok6 ? 1 : 0, ok7 ? 1 : 0, ok8 ? 1 : 0);
    write_tracef("installer done buttons=%u/%u/%u", ok9 ? 1 : 0, ok10 ? 1 : 0, ok11 ? 1 : 0);
    return 0;
}

static BOOL on_dll_main(HMODULE module, DWORD reason, LPVOID reserved)
{
    (void)reserved;

    if (reason == DLL_PROCESS_ATTACH) {
        g_module = module;
        DisableThreadLibraryCalls(module);
        g_logging_enabled = env_logging_enabled();
        g_refresh_hooks_enabled = env_refresh_hooks_enabled();
        g_visual_hooks_enabled = env_visual_hooks_enabled();
        write_trace_line("boh_rune_visual.dll attach");
        write_module_loaded_log();
        HANDLE thread = CreateThread(nullptr, 0, install_thread, nullptr, 0, nullptr);
        if (thread)
            CloseHandle(thread);
    }

    return TRUE;
}

} // namespace

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID reserved)
{
    return on_dll_main(module, reason, reserved);
}

extern "C" __declspec(dllexport) void RuneVisualInit(void)
{
    write_log_line("RuneVisualInit export resolved.");
}
