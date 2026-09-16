/* 2025-07-16 native Item Description body. Freestanding build-time payload.
 * WARP embeds this image; no runtime DLL or socket/API detour is installed.
 * Main and equipped-comparison bodies have independent state and snapshots.
 * Native CItem header/title formatting and unrelated item windows remain native.
 */
#include "item_description_wire.hpp"
namespace w = item_description_wire;
using w::u8; using w::u16; using w::u32;
static_assert(sizeof(void*) == 4, "2025 Ragexe x86 only");
extern "C" void* __cdecl memset(void* dst, int value, unsigned n) { auto p = static_cast<volatile u8*>(dst); while (n--) *p++ = static_cast<u8>(value); return dst; }
extern "C" void* __cdecl memcpy(void* dst, const void* src, unsigned n) { auto d = static_cast<volatile u8*>(dst); auto s = static_cast<const volatile u8*>(src); while (n--) *d++ = *s++; return dst; }

struct Config {
    u32 packet_ctor, packet_send, fill_rect;
    u32 reserved; // Keep configuration offsets stable; the old blitter is unused.
    u32 original[53];
    u32 inventory_right, equipment_right;
    u32 enabled;
    u32 comparison_original[53];
};
struct Child { void* window; u32 visible; int x, y; };
struct Line { int y, row, heading; char text[192]; };
struct Hit { int x, y, width, height, row; };
struct State {
    void* owner;
    u32 sequence, pending, ready, force_stock, origin_scope, sent_at;
    int original_width, original_height, scroll, content_height, layout_width;
    int pressed, hover;
    u32 reserved[3]; // Retired custom-thumb state; native UIScrollBar owns capture.
    unsigned child_count, line_count, hit_count;
    w::Request request;
    w::Snapshot snapshot;
    Child children[64];
    Line lines[512];
    Hit hits[64];
    // Private native UIScrollBar: constructed/destructed normally, composed into
    // this body instead of borrowing the legacy UITextViewer child.
    alignas(4) u8 scrollbar[0xB4];
    u32 scrollbar_live;
};
extern "C" __declspec(dllexport) Config ItemDescriptionConfig = {};
extern "C" __declspec(dllexport) State ItemDescriptionState = {};
extern "C" __declspec(dllexport) State ItemDescriptionComparisonState = {};
static Config& config = ItemDescriptionConfig;
static State* active_state = &ItemDescriptionState;
#define state (*active_state)
struct ViewScope {
    State* previous;
    explicit ViewScope(State* selected) : previous(active_state) { active_state = selected; }
    ~ViewScope() { active_state = previous; }
};
static bool comparison_view() { return active_state == &ItemDescriptionComparisonState; }
static u32 native(unsigned slot) { return comparison_view() ? config.comparison_original[slot] : config.original[slot]; }
template<class T> static T& field(void* p, unsigned offset) { return *reinterpret_cast<T*>(static_cast<u8*>(p) + offset); }
static State* view_for(void* window) {
    return window && field<int>(window, 0x1F8) == 0xEA ? &ItemDescriptionComparisonState : &ItemDescriptionState;
}
static int minimum(int a, int b) { return a < b ? a : b; }
static int maximum(int a, int b) { return a > b ? a : b; }
static int clamp(int n, int low, int high) { return minimum(maximum(n, low), maximum(low, high)); }
static u32 now() { return (*reinterpret_cast<u32(__stdcall**)()>(0x00FC17B0))(); }
static void dirty(void* window) { if (window) field<int>(window, 0x58) = 1; }
static unsigned length(const char* text, unsigned limit = 4096) { unsigned n = 0; if (text) while (n < limit && text[n]) ++n; return n; }
static void copy(char* dst, unsigned capacity, const char* src) {
    if (!capacity) return; unsigned n = minimum(length(src, capacity - 1), capacity - 1);
    for (unsigned i = 0; i < n; ++i) dst[i] = src[i]; dst[n] = 0;
}
static void append(char* dst, unsigned capacity, const char* src) { const auto n = length(dst, capacity); if (n < capacity) copy(dst + n, capacity - n, src); }
static void integer(char* dst, unsigned cap, int value) {
    char temp[16]; unsigned n = 0; bool neg = value < 0; unsigned v = neg ? 0u - static_cast<unsigned>(value) : value;
    do { temp[n++] = '0' + v % 10; v /= 10; } while (v && n < 14);
    unsigned at = 0; if (neg && at + 1 < cap) dst[at++] = '-';
    while (n && at + 1 < cap) dst[at++] = temp[--n]; dst[at] = 0;
}
static bool owner(void* window) { return window && state.owner == window && (field<int>(window, 0x1F8) == 12 || field<int>(window, 0x1F8) == 0xEA); }
static int width(void* window) { return field<int>(window, 0x14); }
static int height(void* window) { return field<int>(window, 0x18); }
static void fill(void* window, int x, int y, int w, int h, u32 color) {
    reinterpret_cast<void(__stdcall*)(void*, int, int, int, int, u32)>(config.fill_rect)(window, x, y, w, h, color);
}
static void text(void* window, int x, int y, const char* value, u32 color = 0x003B4E68, int bold = 0) {
    color = ((color & 255) << 16) | (color & 0xFF00) | ((color >> 16) & 255); // RGB palette -> native COLORREF
    if (value && *value) reinterpret_cast<void(__thiscall*)(void*, int, int, const char*, int, int, int, u32, int, int)>(0x00A25A70)
        (window, x, y, value, 0, 0, 11, color, bold, 0);
}
static int extent(void* window, const char* value) {
    return reinterpret_cast<int(__thiscall*)(void*, const char*, int, int, int, int, int)>(0x00A21C90)(window, value, 0, 0, 11, 0, 0);
}
static void set_size(void* window, int w, int h) { reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00A245C0)(window, w, h); }
static void* capture() { return reinterpret_cast<void*(__thiscall*)(void*)>(0x00A32E00)(reinterpret_cast<void*>(0x0131F4E8)); }
static void* item_node(u32 id) {
    auto manager = *reinterpret_cast<void**>(0x0159C088); if (!manager) return nullptr;
    return reinterpret_cast<void*(__thiscall*)(void*, const u32*)>(0x00A7E780)(static_cast<u8*>(manager) + 8, &id);
}
static const char* native_string(void* p) {
    if (!p) return nullptr;
    return field<u32>(p, 0x14) < 16 ? static_cast<const char*>(p) : *static_cast<const char**>(p);
}
static const char* item_name(u32 id) { auto node = item_node(id); return node ? native_string(static_cast<u8*>(node) + 0x40) : nullptr; }
static void* skin_texture(const char* relative) {
    if (!relative || length(relative, 160) >= 160) return nullptr;
    char path[192]; copy(path, sizeof(path), "\xC0\xAF\xC0\xFA\xC0\xCE\xC5\xCD\xC6\xE4\xC0\xCC\xBD\xBA\\");
    append(path, sizeof(path), relative);
    auto manager = reinterpret_cast<void*(__cdecl*)()>(0x00A90350)(); if (!manager) return nullptr;
    const auto normalized = reinterpret_cast<const char*(__cdecl*)(const char*)>(0x00A9F030)(path);
    if (!normalized || !reinterpret_cast<bool(__thiscall*)(void*, const char*)>(0x00A8E500)(manager, normalized)) return nullptr;
    auto texture = reinterpret_cast<void*(__thiscall*)(void*, const char*)>(0x00A8D4A0)(manager, normalized);
    if (!texture || field<int>(texture, 0x114) <= 0 || field<int>(texture, 0x114) > 1024 ||
        field<int>(texture, 0x118) <= 0 || field<int>(texture, 0x118) > 1024 || !field<void*>(texture, 0x11C)) return nullptr;
    return texture;
}
static void* item_art(u32 id) {
    auto node = item_node(id); if (!node) return nullptr;
    const char* stem = native_string(static_cast<u8*>(node) + 0x58); if (!stem || length(stem, 100) >= 100) return nullptr;
    for (unsigned fallback = 0; fallback < 2; ++fallback) {
        char path[144]; copy(path, sizeof(path), fallback ? "item\\" : "collection\\");
        append(path, sizeof(path), stem); append(path, sizeof(path), ".bmp");
        if (auto texture = skin_texture(path)) return texture;
    }
    return nullptr;
}
// Repeat source pixels without stretching native borders or button caps. Clip
// both dimensions; keyed corners remain transparent on the native window surface.
static void tile(void* window, void* texture, int x, int y, int w, int h, int phase_x = 0, int phase_y = 0) {
    if (!texture || w <= 0 || h <= 0) return;
    auto surface = field<void*>(window, 0x24); if (!surface) return;
    auto target = field<u32*>(surface, 0x18); const int pitch = field<int>(surface, 4);
    auto source = field<u32*>(texture, 0x11C);
    const int sw = field<int>(texture, 0x114), sh = field<int>(texture, 0x118);
    if (!target || !source || pitch < width(window) || sw <= 0 || sh <= 0) return;
    // The original 14x14 white sysbox background is a solid tile. Use its exact
    // decoded pixel with the clipped native fill helper instead of per-pixel
    // modulo work across the entire panel on each repaint.
    if (sw * sh <= 256) {
        bool solid = true;
        for (int i = 1; i < sw * sh; ++i) if (source[i] != source[0]) { solid = false; break; }
        if (solid) { if ((source[0] & 0xFFFFFF) != 0xFF00FF) fill(window, x, y, w, h, source[0]); return; }
    }
    const int first_x = maximum(0, -x), first_y = maximum(0, -y);
    int sy = (first_y + phase_y) % sh;
    for (int dy = first_y; dy < h && y + dy < height(window); ++dy) {
        const auto row = source + sy * sw; int sx = (first_x + phase_x) % sw;
        for (int dx = first_x; dx < w && x + dx < width(window); ++dx) {
            const auto pixel = row[sx];
            if ((pixel & 0xFFFFFF) != 0xFF00FF) target[(y + dy) * pitch + x + dx] = pixel;
            if (++sx == sw) sx = 0;
        }
        if (++sy == sh) sy = 0;
    }
}
static void body_skin(void* window) {
    const int w = width(window), h = height(window);
    auto background = skin_texture("sysbox_bg.bmp");
    void* edge[5]{}; const char* suffix[] = {"lm.bmp", "rm.bmp", "ld.bmp", "md.bmp", "rd.bmp"};
    // Same numeric grade source as native Item Description drawing. Grade skins
    // have edges only: the white body always uses the original sysbox_bg.bmp.
    const auto grade = field<u16>(window, 0x140);
    bool complete = false;
    for (unsigned fallback = 0; fallback < 2 && !complete; ++fallback) {
        char prefix[32]; copy(prefix, sizeof(prefix), "sysbox");
        if (grade && !fallback) { char number[16]; integer(number, sizeof(number), grade); append(prefix, sizeof(prefix), "_g"); append(prefix, sizeof(prefix), number); }
        append(prefix, sizeof(prefix), "_"); complete = true;
        for (unsigned i = 0; i < 5; ++i) {
            char path[48]; copy(path, sizeof(path), prefix); append(path, sizeof(path), suffix[i]); edge[i] = skin_texture(path);
            if (!edge[i] || field<int>(edge[i], 0x114) != 14 || field<int>(edge[i], 0x118) != 14) complete = false;
        }
    }
    if (complete) {
        fill(window, 0, 116, 14, h - 116, 0xFFFF00FF);
        fill(window, w - 14, 116, 14, h - 116, 0xFFFF00FF);
        fill(window, 14, h - 14, w - 28, 14, 0xFFFF00FF);
    }
    bool opaque = background != nullptr;
    if (background) {
        const auto pixels = field<u32*>(background, 0x11C);
        const int count = field<int>(background, 0x114) * field<int>(background, 0x118);
        for (int i = 0; i < count; ++i) if ((pixels[i] & 0xFFFFFF) == 0xFF00FF) { opaque = false; break; }
    }
    if (!opaque) fill(window, 14, 116, w - 28, h - 130, 0xFFFFFFFF);
    if (background) tile(window, background, 14, 116, w - 28, h - 130, 0, 102);
    if (!complete) return; // Keep the original engine frame if a skin is incomplete.
    tile(window, edge[0], 0, 116, 14, h - 130, 0, 102);
    tile(window, edge[1], w - 14, 116, 14, h - 130, 0, 102);
    tile(window, edge[2], 0, h - 14, 14, 14);
    tile(window, edge[3], 14, h - 14, w - 28, 14);
    tile(window, edge[4], w - 14, h - 14, 14, 14);
}
static void blit_fit(void* window, const u32* pixels, int sw, int sh, int x, int y, int box_w, int box_h, int clip_top = 0, int clip_bottom = 0x7FFFFFFF) {
    auto surface = field<void*>(window, 0x24); if (!surface || !pixels || sw <= 0 || sh <= 0) return;
    auto target = field<u32*>(surface, 0x18); const int pitch = field<int>(surface, 4);
    if (!target || pitch < width(window)) return;
    int dw = minimum(sw, box_w), dh = maximum(1, sh * dw / sw);
    if (dh > box_h) { dh = box_h; dw = maximum(1, sw * dh / sh); }
    x += (box_w - dw) / 2; y += (box_h - dh) / 2;
    // Nearest-neighbour preserves RO pixel art and the exact magenta color key.
    for (int dy = maximum(0, maximum(0, clip_top) - y); dy < dh && y + dy < minimum(height(window), clip_bottom); ++dy)
        for (int dx = maximum(0, -x); dx < dw && x + dx < width(window); ++dx) {
            const u32 pixel = pixels[(dy * sh / dh) * sw + dx * sw / dw];
            if ((pixel & 0xFFFFFF) != 0xFF00FF) target[(y + dy) * pitch + x + dx] = pixel;
        }
}
static void item_icon(void* window, u32 id, int x, int y, int w, int h) {
    auto texture = item_art(id); if (!texture) return;
    blit_fit(window, field<u32*>(texture, 0x11C), field<int>(texture, 0x114), field<int>(texture, 0x118), x, y, w, h, 124, height(window) - 42);
}
// Header art is drawn beneath the stock CItem illustration/title at the guarded
// native call site. These primitives affect presentation only, never title spans.
static u32 mix(u32 a, u32 b, int n, int total) {
    u32 result = 0xFF000000;
    for (unsigned shift = 0; shift <= 16; shift += 8) {
        const int c = (a >> shift) & 255, d = (b >> shift) & 255;
        result |= static_cast<u32>(c + (d - c) * n / maximum(1, total)) << shift;
    }
    return result;
}
static void rounded(void* window, int x, int y, int w, int h, int radius, u32 top, u32 bottom) {
    radius = minimum(radius, minimum(w, h) / 2);
    for (int row = 0; row < h; ++row) {
        const int dy = row < radius ? radius - 1 - row : row >= h - radius ? row - (h - radius) : 0;
        int inset = 0;
        while (inset < radius && (radius - inset) * (radius - inset) + dy * dy > radius * radius) ++inset;
        fill(window, x + inset, y + row, w - inset * 2, 1, mix(top, bottom, row, h - 1));
    }
}
static bool current_identity(void* window);
static bool binding_is_unbound() {
    const char value[] = "Unbound";
    for (unsigned i = 0; i < sizeof(value); ++i) if (state.snapshot.binding[i] != value[i]) return false;
    return true;
}
static int binding_width(void* window) { return minimum(width(window) - 120, extent(window, state.snapshot.binding) + 34); }
static void header_details(void* window) {
    text(window, 94, 48, state.snapshot.type_label, 0x005B708A);
    const bool unbound = binding_is_unbound();
    text(window, 113, 75, state.snapshot.binding, state.request.scope == w::catalog ? 0x005B708A : unbound ? 0x004D7768 : 0x00835D78);
    if (comparison_view()) text(window, width(window) >= 360 ? width(window) - 88 : 94, width(window) >= 360 ? 46 : 97, "Equipped", 0x00627D9C);
}
extern "C" __declspec(dllexport) void __stdcall ItemDescriptionHeader(void* window) {
    // During native comparison paint the ID is temporarily normalized. Resolve
    // this exact window by its registered owner, not a prior draw's text/color.
    State* selected = window == ItemDescriptionComparisonState.owner ? &ItemDescriptionComparisonState : &ItemDescriptionState;
    ViewScope context(selected);
    if (!owner(window) || !state.ready || state.force_stock || !config.enabled || !current_identity(window)) return;
    const int w = width(window);
    fill(window, 8, 7, w - 16, 109, 0xFFFFFFFF);
    rounded(window, 8, 7, w - 16, 107, 10, 0xFFD2E3F2, 0xFFE5E1F1);
    rounded(window, 9, 8, w - 18, 105, 9, 0xFFEEF7FF, 0xFFFBF9FE);
    // Quiet name ribbon covers the legacy Collections watermark/divider and
    // leaves the native name at (90,10), including its original wrapped spans.
    rounded(window, 87, 8, w - 112, 31, 7, 0xFFDCEAF6, 0xFFE5EAF7);
    rounded(window, 88, 9, w - 114, 29, 6, 0xFFFAFDFF, 0xFFF5F8FF);
    // The original 75x100 collection image is drawn next at (10,11).
    rounded(window, 9, 10, 77, 102, 5, 0xFFBCD6EA, 0xFFD1CFE8);
    fill(window, 10, 11, 75, 100, 0xFFFFFFFF);
    const bool unbound = binding_is_unbound();
    const int bw = binding_width(window);
    rounded(window, 92, 70, bw, 23, 7, unbound ? 0xFFD4E9DF : 0xFFEADAE7, unbound ? 0xFFD4E9DF : 0xFFEADAE7);
    rounded(window, 93, 71, bw - 2, 21, 6, unbound ? 0xFFF0FAF4 : 0xFFFCF2F8, unbound ? 0xFFEAF6EF : 0xFFF7ECF5);
    // Catalog views describe a template, so they must not imply a bound item.
    if (state.request.scope == w::catalog) {
        fill(window, 100, 76, 8, 11, 0xFF9CAEC2);fill(window, 101, 77, 6, 9, 0xFFF8FBFF);
        fill(window, 102, 80, 4, 1, 0xFFB8C8D8);fill(window, 102, 83, 4, 1, 0xFFB8C8D8);
    } else {
    // A compact native-pixel lock/unlock marker; the full binding label remains text.
    const u32 ink = unbound ? 0xFF729B86 : 0xFFAB839F;
    fill(window, 99, 79, 9, 7, ink);fill(window, 101, 81, 5, 3, unbound ? 0xFFF0FAF4 : 0xFFFCF2F8);
    fill(window, unbound ? 104 : 101, 75, 5, 1, ink);
    fill(window, unbound ? 108 : 105, 76, 1, 4, ink);
    if (!unbound) fill(window, 101, 76, 1, 3, ink);
    }
    if (comparison_view() && w >= 360) {
        rounded(window, w - 95, 42, 77, 20, 6, 0xFFDCEAF6, 0xFFDCEAF6);
        rounded(window, w - 94, 43, 75, 18, 5, 0xFFF6FAFF, 0xFFF6FAFF);
    }
    if (w >= 360 && w - 75 > 92 + bw + 10) {
        // Small, muted Poring accent, kept away from names and binding text.
        const int x = w - 57, y = 79;
        rounded(window, x - 8, y + 19, 45, 7, 3, 0xFFEAF0F9, 0xFFEAF0F9);
        rounded(window, x, y, 29, 25, 11, 0xFFD6CDEB, 0xFFD6CDEB);
        rounded(window, x + 1, y + 1, 27, 23, 10, 0xFFF4EDFC, 0xFFE9DFF5);
        fill(window, x + 8, y + 10, 2, 3, 0xFF8495B4);fill(window, x + 19, y + 10, 2, 3, 0xFF8495B4);
        fill(window, x + 6, y + 14, 4, 2, 0xFFE8CADB);fill(window, x + 20, y + 14, 4, 2, 0xFFE8CADB);
        fill(window, x + 13, y + 15, 4, 1, 0xFFA894B3);
        fill(window, x + 7, y + 5, 4, 2, 0xFFFFFFFF);
        fill(window, x - 16, y - 4, 1, 5, 0xFFC6DCEB);fill(window, x - 18, y - 2, 5, 1, 0xFFC6DCEB);
        fill(window, x + 34, y - 9, 1, 3, 0xFFD5DAEF);fill(window, x + 33, y - 8, 3, 1, 0xFFD5DAEF);
    }
}
static void close_scrollbar() {
    if (!state.scrollbar_live) return;
    if (capture() == state.scrollbar) reinterpret_cast<void(__thiscall*)(void*)>(0x00A482E0)(reinterpret_cast<void*>(0x0131F4E8));
    // flags=0: the native destructor releases its surface/lists, not inline storage.
    reinterpret_cast<void*(__thiscall*)(void*, int)>(0x0083C2C0)(state.scrollbar, 0);
    state.scrollbar_live = 0;
}
static void sync_scrollbar(void* window) {
    if (!state.scrollbar_live) {
        reinterpret_cast<void*(__thiscall*)(void*)>(0x00836870)(state.scrollbar);
        state.scrollbar_live = 1;
        field<void*>(state.scrollbar, 0x10) = window;
        field<int>(state.scrollbar, 0xB0) = 48;
    }
    const int visible = height(window) - 166;
    if (height(state.scrollbar) != visible) set_size(state.scrollbar, 13, visible);
    field<int>(state.scrollbar, 0x1C) = width(window) - 27;
    field<int>(state.scrollbar, 0x20) = 124;
    field<int>(state.scrollbar, 0x80) = maximum(0, state.content_height - visible);
    field<int>(state.scrollbar, 0x84) = state.scroll;
    field<int>(state.scrollbar, 0x98) = maximum(visible, state.content_height);
    field<int>(state.scrollbar, 0x9C) = visible;
}
static void draw_scrollbar(void* window) {
    sync_scrollbar(window);
    // Use the actual native draw, resource resolver and proportional thumb math.
    reinterpret_cast<void(__thiscall*)(void*)>(0x00856560)(state.scrollbar);
    auto surface = field<void*>(state.scrollbar, 0x24);
    if (surface) blit_fit(window, field<u32*>(surface, 0x18), 13, height(state.scrollbar), width(window) - 27, 124, 13, height(state.scrollbar));
}

// Native std::list children at UIWindow+0x50: sentinel/next/previous/value.
// Restoration only dereferences children still in the current owned list.
static bool children(void* window, bool hide) {
    auto head = field<void**>(window, 0x50); if (!head) return false;
    auto node = static_cast<void**>(head[0]); unsigned count = 0;
    while (node && node != head && count < 64) {
        auto child = node[2]; if (!child || field<void*>(child, 0x10) != window) return false;
        if (hide) {
            auto& saved = state.children[count]; saved.window = child;
            saved.visible = field<u8>(child, 0x28); saved.x = field<int>(child, 0x1C); saved.y = field<int>(child, 0x20);
        } else {
            for (unsigned i = 0; i < state.child_count; ++i) if (state.children[i].window == child) {
                field<u8>(child, 0x28) = static_cast<u8>(state.children[i].visible);
                field<int>(child, 0x1C) = state.children[i].x; field<int>(child, 0x20) = state.children[i].y; break;
            }
        }
        ++count; node = static_cast<void**>(node[0]);
    }
    if (node != head) return false;
    if (hide) state.child_count = count;
    return true;
}
static void hide_children(void* window) {
    const auto close = field<void*>(window, 0x208);
    for (unsigned i = 0; i < state.child_count; ++i) {
        auto child = state.children[i].window;
        // Child pointers are borrowed only while native messages are suspended.
        field<u8>(child, 0x28) = child == close ? static_cast<u8>(state.children[i].visible) : 0;
    }
    if (close) { field<int>(close, 0x1C) = width(window) - 16; field<int>(close, 0x20) = 3; }
}
static void restore(void* window) {
    if (!owner(window)) return;
    close_scrollbar();
    if (state.ready) {
        children(window, false); state.child_count = 0; state.ready = 0;
        set_size(window, state.original_width, state.original_height);
    }
    state.pending = 0; state.pressed = state.hover = 0; dirty(window);
}
static bool activate(void* window) {
    if (state.ready) return true;
    if (!children(window, true)) return false;
    state.original_width = width(window); state.original_height = height(window);
    auto renderer = *reinterpret_cast<void**>(0x012515F8);
    int w = 520, h = 560;
    if (renderer) { w = minimum(w, field<int>(renderer, 0x28) - 32); h = minimum(h, field<int>(renderer, 0x2C) - 32); }
    if (w < 280 || h < 240) { state.child_count = 0; return false; }
    set_size(window, w, h); state.ready = 1; state.layout_width = 0; state.scroll = 0;
    if (renderer) {
        field<int>(window, 0x1C) = clamp(field<int>(window, 0x1C), 0, field<int>(renderer, 0x28) - w);
        field<int>(window, 0x20) = clamp(field<int>(window, 0x20), 0, field<int>(renderer, 0x2C) - h);
    }
    hide_children(window); return true;
}
static void align_pair() {
    auto& main = ItemDescriptionState; auto& other = ItemDescriptionComparisonState;
    auto right = main.owner; auto left = other.owner;
    if (!right || !left || !field<u8>(right, 0x28) || !field<u8>(left, 0x28) || (!main.ready && !other.ready)) return;
    auto renderer = *reinterpret_cast<void**>(0x012515F8); if (!renderer) return;
    const int screen_w = field<int>(renderer, 0x28), screen_h = field<int>(renderer, 0x2C);
    if (main.ready && other.ready && screen_w >= 592) {
        const int pane_w = minimum(520, (screen_w - 32) / 2);
        if (width(right) != pane_w) { set_size(right, pane_w, height(right)); main.layout_width = 0; dirty(right); }
        if (width(left) != pane_w) { set_size(left, pane_w, height(left)); other.layout_width = 0; dirty(left); }
    }
    const int left_w = width(left), right_w = width(right);
    const int low = screen_w >= left_w + right_w ? left_w : 0;
    const int x = clamp(field<int>(right, 0x1C), low, screen_w - right_w);
    const int y = clamp(field<int>(right, 0x20), 0, screen_h - maximum(height(right), height(left)));
    const int lx = clamp(x - left_w, 0, screen_w - left_w);
    if (field<int>(right, 0x1C) != x || field<int>(right, 0x20) != y)
        reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00874AF0)(right, x, y);
    if (field<int>(left, 0x1C) != lx || field<int>(left, 0x20) != y)
        reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00874AF0)(left, lx, y);
}
static void restore_pair() {
    for (unsigned i = 0; i < 2; ++i) {
        ViewScope context(i ? &ItemDescriptionComparisonState : &ItemDescriptionState);
        if (state.owner) { restore(state.owner); state.force_stock = 1; ++state.sequence; }
    }
    auto window = ItemDescriptionState.owner;
    if (window) reinterpret_cast<void(__thiscall*)(void*, int, int)>(config.original[4])
        (window, field<int>(window, 0x1C), field<int>(window, 0x20));
}
static bool read_identity(void* item, w::Request& request, u16 scope) {
    if (!item || !field<u8>(item, 0x5C)) return false;
    const auto id = reinterpret_cast<u32(__thiscall*)(void*)>(0x005D98A0)(item);
    if (!id) return false;
    // A positive index outside a profiled inventory/equipment event is an
    // unprofiled container/update, not a template. Preserve its native view.
    if (scope == w::catalog && field<int>(item, 4) >= 2) return false;
    request.item_id = id; request.identified = 1; request.scope = scope;
    if (scope == w::inventory) {
        const int index = field<int>(item, 4), refine = field<int>(item, 0x60), option_count = field<int>(item, 0x98);
        if (index < 2 || index > 65535 || refine < 0 || refine > 255 || option_count < 0 || option_count > 5) return false;
        request.client_index = index; request.refine = static_cast<u16>(refine); request.grade = field<u16>(item, 0x88);
        if (request.grade > 255) return false;
        for (unsigned i = 0; i < 4; ++i) request.cards[i] = field<u32>(item, 0x1C + i * 4);
        request.option_count = static_cast<u8>(option_count);
        for (int i = 0; i < option_count; ++i) request.options[i] = field<w::Option>(item, 0x9C + i * 5);
    }
    return true;
}
static void send_request(void* window, u16 message, bool from_message = false) {
    if (!owner(window) || !field<u8>(window, 0x28) || !config.enabled) return;
    w::Request request{}; request.packet_type = w::request_packet; request.packet_length = sizeof(request);
    request.magic = w::magic; request.version = w::version; request.message = message;
    state.sequence = (state.sequence + 1) & 0x7FFFFFFF; if (!state.sequence) ++state.sequence;
    request.request_id = state.sequence | (comparison_view() ? 0x80000000u : 0);
    const auto scope = from_message ? (comparison_view() ? w::inventory : static_cast<u16>(state.origin_scope)) : state.request.scope;
    if (!read_identity(static_cast<u8*>(window) + 0xB8, request, scope)) return;
    if (!from_message && state.ready && scope == w::inventory) request.known_fingerprint = state.snapshot.fingerprint;
    if (!w::request_valid(request)) return;
    state.request = request; state.pending = 1; state.sent_at = now();
    auto packet = reinterpret_cast<void*(__cdecl*)()>(config.packet_ctor)();
    if (!packet) { state.pending = 0; return; }
    reinterpret_cast<void(__thiscall*)(void*, int, const void*)>(config.packet_send)(packet, sizeof(request), &state.request);
}
static bool current_identity(void* window) {
    w::Request current = state.request;
    for (auto& o : current.options) w::zero(o);
    // Preserve the server fingerprint while comparing only the captured native identity.
    if (!read_identity(static_cast<u8*>(window) + 0xB8, current, state.request.scope)) return false;
    current.request_id = state.request.request_id;
    const auto a = reinterpret_cast<const u8*>(&current), b = reinterpret_cast<const u8*>(&state.request);
    for (unsigned i = 0; i < sizeof(current); ++i) if (a[i] != b[i]) return false;
    return true;
}

static const char* section_name(unsigned section) {
    static const char* names[] = {"", "Core Stats", "Base Attributes", "Special Effects", "Refine", "Grade",
        "Enchantments", "Random Options", "Card Sockets & Effects", "Card Set Bonuses", "Requirements", "Trade Information", "Equipment Comparison"};
    return section < w::section_end ? names[section] : "";
}
static unsigned utf8_next(const char* p, unsigned n, unsigned at) {
    if (at >= n) return n;
    const auto c = static_cast<u8>(p[at]); unsigned size = c < 0x80 ? 1 : c >= 0xC2 && c <= 0xDF ? 2 : c >= 0xE0 && c <= 0xEF ? 3 : c >= 0xF0 && c <= 0xF4 ? 4 : 1;
    if (at + size > n) return at + 1;
    for (unsigned j = 1; j < size; ++j) if ((static_cast<u8>(p[at + j]) & 0xC0) != 0x80) return at + 1;
    return at + size;
}
static void add_line(int& y, int row, int heading, const char* value) {
    if (state.line_count == 512) return;
    auto& line = state.lines[state.line_count++]; line.y = y; line.row = row; line.heading = heading;
    copy(line.text, sizeof(line.text), value); y += heading == 1 ? 24 : heading == 3 ? 22 : 16;
}
static void wrap(void* window, const char* value, int available, int row, int& y) {
    const unsigned n = length(value, 512); unsigned at = 0;
    while (at < n && state.line_count < 512) {
        char candidate[192]; unsigned end = at, last_space = at, next = at;
        while (next < n && value[next] != '\n') {
            const auto after = utf8_next(value, n, next);
            if (after - at >= sizeof(candidate)) break;
            for (unsigned i = at; i < after; ++i) candidate[i - at] = value[i]; candidate[after - at] = 0;
            if (extent(window, candidate) > available && end > at) break;
            end = after; if (value[next] == ' ') last_space = next; next = after;
            if (extent(window, candidate) > available) break;
        }
        if (end == at) end = utf8_next(value, n, at);
        else if (end < n && value[end] != '\n' && last_space > at) end = last_space;
        for (unsigned i = at; i < end; ++i) candidate[i - at] = value[i]; candidate[end - at] = 0;
        add_line(y, row, 0, candidate); at = end;
        while (at < n && (value[at] == ' ' || value[at] == '\n')) ++at;
    }
}
static void row_text(const w::Row& row, char* value, unsigned capacity) {
    value[0] = 0;
    if (row.flags & w::active) append(value, capacity, "[Active] ");
    if (row.flags & w::unmet) append(value, capacity, row.section == w::grade ? "[Inactive] " : "[Not met] ");
    if (row.flags & w::unknown) append(value, capacity, "[Info] ");
    if (row.label[0]) { append(value, capacity, row.label); append(value, capacity, ": "); }
    append(value, capacity, row.text);
}
static void card_wrap(void* window, const char* value, int row, int& y) {
    const auto first = state.line_count;
    wrap(window, value, maximum(90, width(window) - 145), row, y);
    for (unsigned n = first; n < state.line_count; ++n) state.lines[n].heading = 2;
}
static void layout(void* window) {
    state.line_count = 0; state.hit_count = 0; int y = 0;
    bool consumed[w::row_limit]{};
    const int available = maximum(100, width(window) - 70);
    for (unsigned order = 1; order < w::section_end; ++order) {
        const unsigned sec = state.request.message == w::compare ? (order == 1 ? w::comparison : order - 1) : order;
        bool heading = false;
        for (unsigned i = 0; i < state.snapshot.row_count; ++i) {
            const auto& row = state.snapshot.rows[i]; if (row.section != sec || consumed[i]) continue;
            if (!heading) {
                if (y) y += 9;
                char title[96]; copy(title, sizeof(title), section_name(sec));
                if (sec == w::cards || sec == w::enchantments || sec == w::random_options) {
                    char number[16];
                    integer(number, sizeof(number), sec == w::cards ? state.snapshot.card_count : sec == w::enchantments ? state.snapshot.enchant_count : state.snapshot.option_count);
                    append(title, sizeof(title), "  "); append(title, sizeof(title), number);
                    if (sec == w::cards && state.snapshot.slot_count && state.snapshot.card_count <= state.snapshot.slot_count) {
                        integer(number, sizeof(number), state.snapshot.slot_count); append(title, sizeof(title), " / "); append(title, sizeof(title), number);
                    }
                }
                add_line(y, -1, 1, title); heading = true;
            }
            char value[256]{};
            if (row.kind == w::component) {
                add_line(y, i, 3, row.label);
                if (!row.item_id) { wrap(window, row.text, available, i, y); y += 8; continue; }
                const int art_top = y;
                const auto name = item_name(row.item_id);
                card_wrap(window, name ? name : "Item", i, y);
                // One image, one name, then the effects owned by this slot.
                for (unsigned j = i + 1; j < state.snapshot.row_count; ++j) {
                    const auto& effect = state.snapshot.rows[j];
                    if (effect.section != sec) continue;
                    if (effect.kind == w::component) break;
                    if (effect.slot && effect.slot != row.slot) continue;
                    row_text(effect, value, sizeof(value));card_wrap(window, value, j, y);consumed[j] = true;
                }
                if (sec != w::cards && sec != w::enchantments) card_wrap(window, row.text, i, y);
                y = maximum(y, art_top + 100);
                if (state.hit_count < 64) state.hits[state.hit_count++] = {14, art_top, width(window) - 44, y - art_top, static_cast<int>(i)};
                y += 10;
            } else {
                row_text(row, value, sizeof(value)); wrap(window, value, available, i, y); y += 5;
            }
        }
    }
    state.content_height = y + 8; state.layout_width = width(window);
    state.scroll = clamp(state.scroll, 0, state.content_height - (height(window) - 166));
}
static bool inside(int x, int y, int left, int top, int w, int h) { return x >= left && y >= top && x < left + w && y < top + h; }
static int hit(void* window, int x, int y) {
    const int bottom = height(window) - 36;
    if (inside(x, y, 14, bottom, 66, 20)) return 1;
    if (inside(x, y, 86, bottom, 72, 20) && state.request.scope == w::inventory && !comparison_view()) return 2;
    if (inside(x, y, width(window) - 84, bottom, 70, 20)) return 3;
    if (inside(x, y, width(window) - 27, 124, 13, height(window) - 166)) return 6;
    if (y >= 124 && y < height(window) - 42) for (unsigned i = 0; i < state.hit_count; ++i) {
        const auto& h = state.hits[i]; if (inside(x, y - 124 + state.scroll, h.x, h.y, h.width, h.height)) return 100 + h.row;
    }
    return 0;
}
static void button(void* window, int id, const char* label, int x, int y, int w) {
    const char* mode = state.pressed == id ? "press" : state.hover == id ? "over" : "out";
    void* pieces[3]{}; const char* suffix[] = {"_left.bmp", "_mid.bmp", "_right.bmp"};
    bool complete = true;
    for (unsigned i = 0; i < 3; ++i) {
        char path[80]; copy(path, sizeof(path), "basic_interface\\btn_"); append(path, sizeof(path), mode); append(path, sizeof(path), suffix[i]);
        pieces[i] = skin_texture(path);
        if (!pieces[i] || field<int>(pieces[i], 0x114) != 6 || field<int>(pieces[i], 0x118) != 20) complete = false;
    }
    if (complete) {
        tile(window, pieces[0], x, y, 6, 20);
        tile(window, pieces[1], x + 6, y, w - 12, 20);
        tile(window, pieces[2], x + w - 6, y, 6, 20);
    } else {
        fill(window, x, y, w, 20, 0xFFC0C0C0); fill(window, x + 1, y + 1, w - 2, 18, 0xFFFFFFFF);
    }
    text(window, x + maximum(3, (w - extent(window, label)) / 2), y + 4, label);
}
static void inspect_component(int row) {
    if (row < 0 || row >= state.snapshot.row_count || !state.snapshot.rows[row].item_id) return;
    if (!item_node(state.snapshot.rows[row].item_id)) return; // Never open native details for a missing client catalog entry.
    // Native card/combined-detail window 82, outside our adapted vtable.
    u8 item[0xB8]; memset(item, 0, sizeof(item));
    reinterpret_cast<void(__thiscall*)(void*)>(0x006A1B20)(item);
    reinterpret_cast<void(__thiscall*)(void*, u32)>(0x006A6570)(item, state.snapshot.rows[row].item_id);
    field<int>(item, 0) = 6; field<u8>(item, 0x5C) = 1;
    auto target = reinterpret_cast<void*(__thiscall*)(void*, int)>(0x00A39340)(reinterpret_cast<void*>(0x0131F4E8), 82);
    if (target) reinterpret_cast<int(__thiscall*)(void*, int, int, void*, int, int, int)>(*reinterpret_cast<u32*>(*static_cast<u8**>(target) + 37 * 4))(target, 0, 24, item, 0, 0, 0);
    reinterpret_cast<void(__thiscall*)(void*)>(0x004F08F0)(item + 0x44);
    reinterpret_cast<void(__thiscall*)(void*)>(0x004F08F0)(item + 0x2C);
}

extern "C" __declspec(dllexport) int __stdcall ItemDescriptionReceive(const void* packet, unsigned bytes) {
    if (!packet || bytes != sizeof(w::Snapshot)) return 0;
    ViewScope context((static_cast<const w::Snapshot*>(packet)->request_id & 0x80000000u) ? &ItemDescriptionComparisonState : &ItemDescriptionState);
    if (!state.owner || state.force_stock) return 0;
    auto window = state.owner;
    if (!field<u8>(window, 0x28) || !w::snapshot_valid(*static_cast<const w::Snapshot*>(packet), state.request)) return 0;
    const auto& response = *static_cast<const w::Snapshot*>(packet);
    if (!state.pending && !(state.ready && response.result == w::stale)) return 0;
    if (response.result != w::ok || !current_identity(window)) { restore(window); return 1; }
    memcpy(&state.snapshot, &response, sizeof(response)); state.pending = 0;
    if (!activate(window)) { restore(window); return 0; }
    state.layout_width = 0; align_pair(); dirty(window); return 1;
}
extern "C" __declspec(dllexport) int __fastcall ItemDescriptionMessage(void* window, void*, int a, int message, void* data, int d, int e, int f) {
    ViewScope context(view_for(window));
    if (owner(window) && state.ready && state.scrollbar_live && reinterpret_cast<void*>(a) == state.scrollbar) {
        const int before = state.scroll;
        const int visible = height(window) - 166;
        const int delta = message == 7 ? reinterpret_cast<int>(data) : message == 9 ? -visible : message == 10 ? visible : 0;
        state.scroll = clamp(before + delta, 0, state.content_height - visible);
        sync_scrollbar(window); dirty(window);
        return state.scroll - before; // Native drag uses the actual consumed delta.
    }
    const bool ours = field<int>(window, 0x1F8) == 12 || field<int>(window, 0x1F8) == 0xEA;
    if (ours && comparison_view() && message == 34) {
        if (ItemDescriptionState.ready || state.ready) { align_pair(); return 0; }
        // Without snapshots, preserve stock positioning and its complete fallback.
        return reinterpret_cast<int(__thiscall*)(void*, int, int, void*, int, int, int)>(native(37))(window, a, message, data, d, e, f);
    }
    const bool opening = ours && message == 24 && data && config.enabled;
    if (ours && owner(window)) {
        // Native messages may rebuild child objects; release all borrowed state first.
        restore(window);
        if (message == 5) { ++state.sequence; state.owner = nullptr; }
    }
    const int result = reinterpret_cast<int(__thiscall*)(void*, int, int, void*, int, int, int)>(native(37))(window, a, message, data, d, e, f);
    if (opening) {
        state.owner = window; state.force_stock = 0; state.scroll = 0;
        send_request(window, w::inspect, true);
    }
    return result;
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionDraw(void* window, void*) {
    ViewScope context(view_for(window));
    align_pair();
    // Comparison retains its real ID outside this synchronous paint. Choosing
    // the normal skin branch changes only header/frame presentation; the exact
    // native CItem formatter and all title color ownership still execute.
    const int native_id = field<int>(window, 0x1F8);
    if (owner(window) && state.ready && comparison_view()) field<int>(window, 0x1F8) = 12;
    reinterpret_cast<void(__thiscall*)(void*)>(native(20))(window);
    field<int>(window, 0x1F8) = native_id;
    if (!owner(window)) return;
    if (state.pending && now() - state.sent_at >= 5000) state.pending = 0;
    if (!state.ready || state.force_stock) return;
    if (!current_identity(window)) { restore(window); return; }
    hide_children(window);
    const int w = width(window), h = height(window), top = 124, bottom = h - 42;
    body_skin(window);
    header_details(window);
    if (!state.layout_width || state.layout_width != w) layout(window);
    for (unsigned i = 0; i < state.line_count; ++i) {
        const auto& line = state.lines[i]; const int y = top + line.y - state.scroll;
        if (y < top || y + 16 > bottom) continue;
        if (line.heading == 1) { fill(window, 14, y - 1, w - 49, 20, 0xFFDCE5EF); text(window, 19, y + 2, line.text); }
        else {
            const auto& row = state.snapshot.rows[line.row];
            text(window, line.heading == 2 ? 103 : 18, y, line.text, (row.flags & w::unmet) ? 0x00954E50 : (row.flags & w::active) ? 0x004D765A : 0x003B4E68);
        }
    }
    for (unsigned i = 0; i < state.hit_count; ++i) {
        const auto& hit = state.hits[i]; const int y = top + hit.y - state.scroll;
        const auto& row = state.snapshot.rows[hit.row];
        if (row.item_id && y + 100 > top && y < bottom) item_icon(window, row.item_id, 18, y, 75, 100);
    }
    draw_scrollbar(window);
    button(window, 1, "Original", 14, h - 36, 66);
    if (state.request.scope == w::inventory && !comparison_view()) button(window, 2, "Compare", 86, h - 36, 72);
    button(window, 3, state.pending ? "Loading" : "Refresh", w - 84, h - 36, 70);
    if ((state.snapshot.flags & w::truncated) && w >= 430) text(window, 164, h - 30, "Some effects omitted", 0x00856A45);
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionDown(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    if (!owner(window) || !state.ready || y < 116) { reinterpret_cast<void(__thiscall*)(void*, int, int)>(native(25))(window, x, y); return; }
    state.pressed = hit(window, x, y);
    if (state.pressed == 6) {
        sync_scrollbar(window);
        if (field<int>(state.scrollbar, 0x80) && (!capture() || capture() == state.scrollbar))
            reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00858970)(state.scrollbar, x - (width(window) - 27), y - 124);
    }
    dirty(window);
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionMove(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    if (!owner(window) || !state.ready) { reinterpret_cast<void(__thiscall*)(void*, int, int)>(native(28))(window, x, y); return; }
    const int hovered = hit(window, x, y); if (hovered != state.hover) { state.hover = hovered; dirty(window); }
    if (state.scrollbar_live && (hovered == 6 || capture() == state.scrollbar)) {
        reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x0085A420)(state.scrollbar, x - (width(window) - 27), y - 124);
        dirty(window);
    }
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionUp(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    if (!owner(window) || !state.ready || (y < 116 && !state.pressed)) { reinterpret_cast<void(__thiscall*)(void*, int, int)>(native(31))(window, x, y); return; }
    const int pressed = state.pressed; state.pressed = 0;
    if (state.scrollbar_live && (pressed == 6 || capture() == state.scrollbar)) {
        reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x008590E0)(state.scrollbar, x - (width(window) - 27), y - 124);
        dirty(window); return;
    }
    if (pressed != hit(window, x, y)) { dirty(window); return; }
    if (pressed == 1) { restore_pair(); align_pair(); return; }
    if (pressed == 2 && !state.pending) { state.scroll = 0; send_request(window, w::compare); }
    if (pressed == 3 && !state.pending) send_request(window, w::inspect);
    if (pressed >= 100) inspect_component(pressed - 100);
    dirty(window);
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionRight(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    if (!owner(window) || !state.ready) { reinterpret_cast<void(__thiscall*)(void*, int, int)>(native(32))(window, x, y); return; }
    const int row = hit(window, x, y); if (row >= 100) inspect_component(row - 100);
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionWheel(void* window, void*, int delta) {
    ViewScope context(view_for(window));
    if (!owner(window) || !state.ready) { reinterpret_cast<void(__thiscall*)(void*, int)>(native(35))(window, delta); return; }
    if (delta) state.scroll = clamp(state.scroll + (delta > 0 ? -48 : 48), 0, state.content_height - (height(window) - 166)); dirty(window);
}
extern "C" __declspec(dllexport) void* __fastcall ItemDescriptionDestroy(void* window, void*, int flags) {
    ViewScope context(view_for(window));
    if (owner(window)) { restore(window); state.owner = nullptr; ++state.sequence; state.force_stock = 0; }
    return reinterpret_cast<void*(__thiscall*)(void*, int)>(native(0))(window, flags);
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionInventoryRight(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    const auto previous = state.origin_scope; state.origin_scope = w::inventory;
    reinterpret_cast<void(__thiscall*)(void*, int, int)>(config.inventory_right)(window, x, y); state.origin_scope = previous;
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionEquipmentRight(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    const auto previous = state.origin_scope; state.origin_scope = w::inventory;
    reinterpret_cast<void(__thiscall*)(void*, int, int)>(config.equipment_right)(window, x, y); state.origin_scope = previous;
}

extern "C" __declspec(dllexport) void __fastcall ItemDescriptionPosition(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    reinterpret_cast<void(__thiscall*)(void*, int, int)>(native(4))(window, x, y);
    align_pair();
}
