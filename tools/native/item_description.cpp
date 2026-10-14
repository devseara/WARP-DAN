/* 2025-07-16 native Item Description card. Freestanding build-time payload.
 * WARP embeds this image; no runtime DLL or socket/API detour is installed.
 * Main, equipped-comparison and component panes own separate snapshots.
 * Native CItem art/title formatting and unrelated item windows remain native.
 * A pane takes its final geometry when it opens and shows a loading skeleton
 * until its snapshot arrives, so the stock body is never painted first.
 */
#include "item_description_wire.hpp"
namespace w = item_description_wire;
using w::u8; using w::u16; using w::u32; using w::i16;
static_assert(sizeof(void*) == 4, "2025 Ragexe x86 only");
extern "C" void* __cdecl memset(void* dst, int value, unsigned n) { auto p = static_cast<volatile u8*>(dst); while (n--) *p++ = static_cast<u8>(value); return dst; }
extern "C" void* __cdecl memcpy(void* dst, const void* src, unsigned n) { auto d = static_cast<volatile u8*>(dst); auto s = static_cast<const volatile u8*>(src); while (n--) *d++ = *s++; return dst; }

struct Config {
    u32 packet_ctor, packet_send, fill_rect;
    u32 reserved; // Retired blitter word; all ABI offsets stay stable.
    u32 original[53];
    u32 inventory_right, equipment_right;
    u32 enabled;
    u32 comparison_original[53];
    u32 component_original[53];
};
struct Child { void* window; u32 visible; int x, y; };
// Keeps the accepted 204-byte stride; kind/style/x replace the old heading int.
struct Line { int y, row; u8 kind, style; i16 x; char text[192]; };
struct Hit { int x, y, width, height, row; };
struct Shape { int y, h; i16 x, w; u16 kind, row; };
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
    // Appended after the accepted fixture offsets.
    u32 loading;   // Final geometry is shown; the snapshot is not for this request yet.
    u32 deferred;  // Request queued behind the server's 150 ms per-view spacing.
    u32 last_send;
    int headline_kind, headline, headline_bonus;
    int info_level, info_weapon, info_weight;
    unsigned shape_count;
    Shape shapes[256];
};
static_assert(sizeof(Line) == 204 && sizeof(Shape) == 16 && sizeof(State) == 123664, "IDUI state ABI");
extern "C" __declspec(dllexport) Config ItemDescriptionConfig = {};
extern "C" __declspec(dllexport) State ItemDescriptionState = {};
extern "C" __declspec(dllexport) State ItemDescriptionComparisonState = {};
extern "C" __declspec(dllexport) State ItemDescriptionComponentState = {};
static Config& config = ItemDescriptionConfig;
static State* active_state = &ItemDescriptionState;
enum : unsigned { paint_hover = 1, paint_body = 2, paint_bar = 4 };
struct PartialPaint { unsigned regions; int previous, width, height, scroll; void* surface; u32* pixels; };
static PartialPaint partial_paints[3] = {};
// Native open callbacks can recursively open the equipped pane. Scope each
// optimization to its exact receiver; never change shared Lua/text renderers.
static void* native_open_window = nullptr;
static bool stock_body_missing[3] = {};
static u32 destroy_epochs[3] = {};
struct HeaderDrag { void* owner; int x, y; };
static HeaderDrag header_drag = {};
struct NativeOpenScope {
    void* previous;
    explicit NativeOpenScope(void* window) : previous(native_open_window) { native_open_window = window; }
    ~NativeOpenScope() { native_open_window = previous; }
};
#define state (*active_state)
struct ViewScope {
    State* previous;
    explicit ViewScope(State* selected) : previous(active_state) { active_state = selected; }
    ~ViewScope() { active_state = previous; }
};
// A preemptive skeleton is skipped after a server never answered; any valid
// snapshot proves the module and re-enables it.
static u32 server_proven = 0, server_silent = 0;

constexpr int header_bottom = 116, body_top = 154, pane_width = 360, pane_height = 560, pane_gap = 8;
constexpr u32 load_timeout = 3000, request_spacing = 160;
constexpr u32 key = 0xFFFF00FF, white = 0xFFFFFFFF, black = 0xFF000000;
// Text colors are RGB; fills are opaque ARGB.
constexpr u32 ink = 0x4A5263, muted = 0x8C95A6, blue = 0x4C7BD6, orange = 0xE8862E, green = 0x3FA25B,
    red = 0xD9473F, faded = 0xB0B6C2, card_text = 0x80868F, brown = 0xA1907A, yellow = 0xFFE27A;
constexpr u32 rule = 0xFFE3E8F0, sparkle_ink = 0xFFC2CBDA, card_edge = 0xFFFFD6A5, card_hover = 0xFFEEAA45,
    card_top = 0xFFFFF7ED, card_highlight = 0xFFFFF0D8, slot_edge = 0xFFE6EBF3, slot_fill = 0xFFF7F9FC,
    skeleton = 0xFFEDF1F7, skeleton_heading = 0xFFDDE6F5;
// Header hues follow the native grade_enchant/grade_icon{1..4}.bmp inks.
static const u32 tint_top[] = {0xFF6E98D6, 0xFFD8605D, 0xFFE3963F, 0xFF5C9E4A, 0xFF7F73A6};
static const u32 tint_bottom[] = {0xFF9ABAE8, 0xFFEE9179, 0xFFF1BC78, 0xFF8EC47A, 0xFFA99FCB};

struct Style { u8 size, bold; u32 color, accent; };
enum : u8 { t_body, t_heading, t_count, t_plain, t_value, t_muted, t_good, t_bad, t_note,
    t_card_title, t_card_sub, t_card_body, t_tier_name, t_tier_text, t_tier_off_name, t_tier_off,
    t_tier_note, t_chip_label, t_chip_good, t_chip_bad, t_chip_plain, t_style_end };
static const Style styles[] = {
    {12, 0, ink, orange}, {13, 1, blue, 0}, {11, 1, muted, 0}, {12, 0, ink, 0}, {12, 1, ink, 0},
    {12, 0, muted, 0}, {12, 0, green, 0}, {12, 0, red, 0}, {11, 0, muted, 0},
    {13, 1, orange, 0}, {11, 0, muted, 0}, {12, 0, card_text, orange}, {12, 1, ink, 0}, {12, 0, ink, orange},
    {12, 1, faded, 0}, {12, 0, faded, 0}, {11, 0, brown, 0}, {11, 0, muted, 0}, {11, 1, green, 0},
    {11, 1, red, 0}, {11, 1, ink, 0}};
static_assert(sizeof(styles) / sizeof(styles[0]) == t_style_end, "style table");
enum : u8 { k_text = 0, k_heading = 1, k_component_text = 2, k_component_title = 3 };
enum : u16 { s_divider = 1, s_diamond, s_sparkle, s_check, s_cross, s_lock, s_info, s_card, s_slot,
    s_tiers, s_chip_good, s_chip_bad, s_chip_plain, s_art };

static bool comparison_view() { return active_state == &ItemDescriptionComparisonState; }
static bool component_view() { return active_state == &ItemDescriptionComponentState; }
static unsigned pane_index() { return component_view() ? 2 : comparison_view() ? 1 : 0; }
static u32 channel_last_send[2] = {};
static bool comparison_rewatch = false;
static u32 native(unsigned slot) { return component_view() ? config.component_original[slot] : comparison_view() ? config.comparison_original[slot] : config.original[slot]; }
template<class T> static T& field(void* p, unsigned offset) { return *reinterpret_cast<T*>(static_cast<u8*>(p) + offset); }
static State* view_for(void* window) {
    if (window && (window == ItemDescriptionComponentState.owner || field<int>(window, 0x1F8) == 82)) return &ItemDescriptionComponentState;
    return window && (window == ItemDescriptionComparisonState.owner || field<int>(window, 0x1F8) == 0xEA) ? &ItemDescriptionComparisonState : &ItemDescriptionState;
}
static int minimum(int a, int b) { return a < b ? a : b; }
static int maximum(int a, int b) { return a > b ? a : b; }
static int clamp(int n, int low, int high) { return minimum(maximum(n, low), maximum(low, high)); }
static u32 now() { return (*reinterpret_cast<u32(__stdcall**)()>(0x00FC17B0))(); }
static void dirty(void* window) {
    if (window) {
        partial_paints[view_for(window) == &ItemDescriptionComponentState ? 2 : view_for(window) == &ItemDescriptionComparisonState ? 1 : 0].regions = 0;
        field<int>(window, 0x58) = 1;
    }
}
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
static bool digit(char c) { return c >= '0' && c <= '9'; }
static bool alnum(char c) { return digit(c) || (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c == '_'; }
static bool same(const char* a, const char* b) { unsigned i = 0; while (a[i] && a[i] == b[i]) ++i; return a[i] == b[i]; }
static bool starts(const char* a, const char* prefix) { for (unsigned i = 0; prefix[i]; ++i) if (a[i] != prefix[i]) return false; return true; }
// Parses a whole signed integer prefix; decimals are rejected rather than truncated.
static const char* leading_int(const char* s, int& value) {
    unsigned i = 0; bool negative = false;
    if (s[i] == '+' || s[i] == '-') negative = s[i++] == '-';
    if (!digit(s[i])) return nullptr;
    int v = 0; while (digit(s[i]) && v < 100000000) v = v * 10 + (s[i++] - '0');
    if (digit(s[i]) || s[i] == '.') return nullptr;
    value = negative ? -v : v; return s + i;
}
static bool owner(void* window) { return window && state.owner == window && (field<int>(window, 0x1F8) == 12 || field<int>(window, 0x1F8) == 0xEA || field<int>(window, 0x1F8) == 82); }
static int width(void* window) { return field<int>(window, 0x14); }
static int height(void* window) { return field<int>(window, 0x18); }
static void queue_paint(void* window, unsigned regions, int previous = 0) {
    auto& paint = partial_paints[pane_index()];
    // Full invalidations stay authoritative. Input events only queue work; the
    // normal dirty-window transaction updates the manager's cached composition.
    if (state.loading || state.layout_width != width(window)) { dirty(window); return; }
    if (!field<int>(window, 0x58)) {
        paint.regions = 0; paint.previous = previous; paint.width = width(window);
        paint.height = height(window); paint.scroll = state.scroll;
        paint.surface = field<void*>(window, 0x24);
        paint.pixels = paint.surface ? field<u32*>(paint.surface, 0x18) : nullptr;
    } else if (!paint.regions) return;
    if ((regions & paint_hover) && !(paint.regions & paint_hover)) paint.previous = previous;
    paint.regions |= regions; field<int>(window, 0x58) = 1;
}

// Every fill is clipped here: the shared native helper rejects, not clips,
// rectangles with a negative origin.
static int clip_x0 = 0, clip_y0 = 0, clip_x1 = 0x7FFFFFFF, clip_y1 = 0x7FFFFFFF;
struct ClipScope {
    int saved[4];
    ClipScope(int x0, int y0, int x1, int y1) : saved{clip_x0, clip_y0, clip_x1, clip_y1} { clip_x0 = x0; clip_y0 = y0; clip_x1 = x1; clip_y1 = y1; }
    ~ClipScope() { clip_x0 = saved[0]; clip_y0 = saved[1]; clip_x1 = saved[2]; clip_y1 = saved[3]; }
};
static void fill(void* window, int x, int y, int w, int h, u32 color) {
    const int x0 = maximum(x, maximum(0, clip_x0)), y0 = maximum(y, maximum(0, clip_y0));
    const int x1 = minimum(x + w, minimum(width(window), clip_x1)), y1 = minimum(y + h, minimum(height(window), clip_y1));
    if (x1 > x0 && y1 > y0)
        reinterpret_cast<void(__stdcall*)(void*, int, int, int, int, u32)>(config.fill_rect)(window, x0, y0, x1 - x0, y1 - y0, color);
}
static void text(void* window, int x, int y, const char* value, u32 color = ink, int bold = 0, int size = 11) {
    color = ((color & 255) << 16) | (color & 0xFF00) | ((color >> 16) & 255); // RGB palette -> native COLORREF
    if (value && *value) reinterpret_cast<void(__thiscall*)(void*, int, int, const char*, int, int, int, u32, int, int)>(0x00A25A70)
        (window, x, y, value, 0, 0, size, color, bold, 0);
}
static int extent(void* window, const char* value, int size = 11, int bold = 0) {
    if (!value || !*value) return 0;
    return reinterpret_cast<int(__thiscall*)(void*, const char*, int, int, int, int, int)>(0x00A21C90)(window, value, 0, 0, size, bold, 0);
}
static void set_size(void* window, int w, int h) {
    // Native SetSize destroys/reallocates its DIB even for identical dimensions.
    if (width(window) != w || height(window) != h || !field<void*>(window, 0x24))
        reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00A245C0)(window, w, h);
}
extern "C" __declspec(dllexport) int __stdcall ItemDescriptionNativeOpen(void* window) {
    return window && window == native_open_window;
}
extern "C" __declspec(dllexport) void* __fastcall ItemDescriptionNativeText(void* item, void*) {
    static u32 empty_lines[3] = {};
    if (native_open_window && item == static_cast<u8*>(native_open_window) + 0xB8) return empty_lines;
    return reinterpret_cast<void*(__thiscall*)(void*)>(0x006A2A70)(item);
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionSize(void* window, void*, int w, int h) {
    if (window != native_open_window) set_size(window, w, h);
}
static void* capture() { return reinterpret_cast<void*(__thiscall*)(void*)>(0x00A32E00)(reinterpret_cast<void*>(0x0131F4E8)); }
static void end_header_drag(void* window) {
    if (header_drag.owner != window) return;
    if (capture() == window) reinterpret_cast<void(__thiscall*)(void*)>(0x00A482E0)(reinterpret_cast<void*>(0x0131F4E8));
    header_drag.owner = nullptr;
}
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
// Keep scaled pixels, never borrowed resource pointers. Eight bounded entries
// per pane cover card/enchant thumbnails without repeated resolver calls on
// hover. Closing/reopening, a new inspection, or a new catalog invalidates them.
struct Thumbnail { u32 id; int width, height; u32 pixels[40 * 52]; };
struct ArtworkCache { void* catalog; unsigned next; Thumbnail entries[8]; };
static ArtworkCache artwork[3] = {};
static ArtworkCache& artwork_cache() { return artwork[pane_index()]; }
static void clear_artwork() {
    auto& cache = artwork_cache(); cache.catalog = nullptr; cache.next = 0;
    for (auto& entry : cache.entries) entry.id = 0;
}
static const Thumbnail& thumbnail(u32 id) {
    auto& cache = artwork_cache(); auto catalog = *reinterpret_cast<void**>(0x0159C088);
    if (cache.catalog != catalog) { clear_artwork(); cache.catalog = catalog; }
    for (const auto& entry : cache.entries) if (entry.id == id) return entry;
    auto& entry = cache.entries[cache.next++ % 8]; entry.id = id; entry.width = entry.height = 0;
    if (auto texture = item_art(id)) {
        const int sw = field<int>(texture, 0x114), sh = field<int>(texture, 0x118);
        int dw = minimum(sw, 40), dh = maximum(1, sh * dw / sw);
        if (dh > 52) { dh = 52; dw = maximum(1, sw * dh / sh); }
        const auto pixels = field<u32*>(texture, 0x11C);
        for (int y = 0; y < dh; ++y) for (int x = 0; x < dw; ++x)
            entry.pixels[y * dw + x] = pixels[(y * sh / dh) * sw + x * sw / dw];
        entry.width = dw; entry.height = dh;
    }
    return entry;
}
// Nearest-neighbour preserves RO pixel art and the exact magenta color key.
static void blit(void* window, const u32* pixels, int sw, int sh, int x, int y, int dw, int dh) {
    auto surface = field<void*>(window, 0x24); if (!surface || !pixels || sw <= 0 || sh <= 0 || dw <= 0 || dh <= 0) return;
    auto target = field<u32*>(surface, 0x18); const int pitch = field<int>(surface, 4);
    if (!target || pitch < width(window)) return;
    const int top = maximum(0, clip_y0), bottom = minimum(height(window), clip_y1);
    const int left = maximum(0, clip_x0), right = minimum(width(window), clip_x1);
    if (sw == dw && sh == dh) {
        for (int dy = maximum(0, top - y); dy < dh && y + dy < bottom; ++dy)
            for (int dx = maximum(0, left - x); dx < dw && x + dx < right; ++dx) {
                const u32 pixel = pixels[dy * sw + dx];
                if ((pixel & 0xFFFFFF) != 0xFF00FF) target[(y + dy) * pitch + x + dx] = pixel;
            }
        return;
    }
    for (int dy = maximum(0, top - y); dy < dh && y + dy < bottom; ++dy)
        for (int dx = maximum(0, left - x); dx < dw && x + dx < right; ++dx) {
            const u32 pixel = pixels[(dy * sh / dh) * sw + dx * sw / dw];
            if ((pixel & 0xFFFFFF) != 0xFF00FF) target[(y + dy) * pitch + x + dx] = pixel;
        }
}
static void blit_fit(void* window, const u32* pixels, int sw, int sh, int x, int y, int box_w, int box_h) {
    if (sw <= 0 || sh <= 0) return;
    int dw = minimum(sw, box_w), dh = maximum(1, sh * dw / sw);
    if (dh > box_h) { dh = box_h; dw = maximum(1, sw * dh / sh); }
    blit(window, pixels, sw, sh, x + (box_w - dw) / 2, y + (box_h - dh) / 2, dw, dh);
}
static void item_icon(void* window, u32 id, int x, int y, int w, int h) {
    if (id && w == 40 && h == 52) {
        const auto& entry = thumbnail(id);
        blit(window, entry.pixels, entry.width, entry.height, x + (w - entry.width) / 2,
            y + (h - entry.height) / 2, entry.width, entry.height);
        return;
    }
    auto texture = item_art(id); if (!texture) return;
    blit_fit(window, field<u32*>(texture, 0x11C), field<int>(texture, 0x114), field<int>(texture, 0x118), x, y, w, h);
}
static u32 mix(u32 a, u32 b, int n, int total) {
    u32 result = 0xFF000000;
    for (unsigned shift = 0; shift <= 16; shift += 8) {
        const int c = (a >> shift) & 255, d = (b >> shift) & 255;
        result |= static_cast<u32>(c + (d - c) * n / maximum(1, total)) << shift;
    }
    return result;
}
static u32 lift(u32 color, int n, int total = 7) { return mix(color, white, n, total); }
static int corner_inset(int row, int h, int radius) {
    const int dy = row < radius ? radius - 1 - row : row >= h - radius ? row - (h - radius) : 0;
    int inset = 0;
    while (inset < radius && (radius - inset) * (radius - inset) + dy * dy > radius * radius) ++inset;
    return inset;
}
static void rounded(void* window, int x, int y, int w, int h, int radius, u32 top, u32 bottom) {
    radius = minimum(radius, minimum(w, h) / 2); if (w <= 0 || h <= 0) return;
    if (top == bottom && h > radius * 2) {
        // Uniform panels: one fill for the straight middle, per-row corners only.
        for (int row = 0; row < radius; ++row) {
            const int inset = corner_inset(row, h, radius);
            fill(window, x + inset, y + row, w - inset * 2, 1, top);
            fill(window, x + inset, y + h - 1 - row, w - inset * 2, 1, top);
        }
        fill(window, x, y + radius, w, h - radius * 2, top); return;
    }
    for (int row = 0; row < h; ++row) {
        const int inset = corner_inset(row, h, radius);
        fill(window, x + inset, y + row, w - inset * 2, 1, mix(top, bottom, row, h - 1));
    }
}
static void shadow_text(void* window, int x, int y, const char* value, u32 color, u32 shade, int bold = 0, int size = 11) {
    text(window, x, y + 1, value, shade & 0xFFFFFF, bold, size); text(window, x, y, value, color & 0xFFFFFF, bold, size);
}

// Small vector glyphs drawn with clipped fills.
static void diamond(void* window, int x, int y, u32 color) {
    static const u8 rows[] = {1, 3, 5, 7, 5, 3, 1};
    for (int i = 0; i < 7; ++i) fill(window, x + (7 - rows[i]) / 2, y + i, rows[i], 1, color);
}
static void sparkle(void* window, int x, int y, u32 color) {
    fill(window, x + 3, y, 1, 7, color); fill(window, x, y + 3, 7, 1, color); fill(window, x + 2, y + 2, 3, 3, color);
}
static void check(void* window, int x, int y, u32 color) {
    static const u8 dy[] = {3, 4, 5, 4, 3, 2, 1, 0};
    for (int i = 0; i < 8; ++i) fill(window, x + i, y + dy[i], 1, 2, color);
}
static void cross(void* window, int x, int y, u32 color) {
    for (int i = 0; i < 7; ++i) { fill(window, x + i, y + i, 1, 1, color); fill(window, x + 6 - i, y + i, 1, 1, color); }
}
static void lock(void* window, int x, int y, u32 color, u32 background, bool open) {
    fill(window, x, y + 4, 9, 7, color); fill(window, x + 4, y + 6, 1, 3, background);
    fill(window, x + (open ? 5 : 2), y, 5, 1, color);
    fill(window, x + (open ? 9 : 6), y + 1, 1, 3, color);
    if (!open) fill(window, x + 2, y + 1, 1, 3, color);
}
static void info(void* window, int x, int y, u32 color) {
    rounded(window, x, y, 11, 11, 5, color, color); fill(window, x + 5, y + 2, 1, 1, white); fill(window, x + 5, y + 4, 1, 5, white);
}
static void arrow(void* window, int x, int y, u32 color, bool up) {
    for (int i = 0; i < 5; ++i) { const int w = 2 + i * 2; fill(window, x + (10 - w) / 2, up ? y + i : y + 9 - i, w, 1, color); }
    fill(window, x + 3, up ? y + 5 : y, 4, 5, color);
}
static void ring(void* window, int cx, int cy, int r, u32 top, u32 bottom) {
    const auto at = [&](int y) { return mix(top, bottom, clamp(y, 1, header_bottom - 1) - 1, header_bottom - 2); };
    rounded(window, cx - r, cy - r, r * 2, r * 2, r, mix(at(cy - r), white, 1, 9), mix(at(cy + r), white, 1, 9));
    rounded(window, cx - r + 6, cy - r + 6, r * 2 - 12, r * 2 - 12, r - 6, at(cy - r + 6), at(cy + r - 6));
}
static unsigned tone(void* window) { const unsigned g = field<u16>(window, 0x140); return g < 4 ? g : 4; }
static u32 deep_tone(u32 top) { return mix(top, black, 1, 5); }
static u32 edge_tone(u32 top) { return mix(top, deep_tone(top), 1, 2); }

static bool current_identity(void* window);
static bool binding_is_unbound() { return same(state.snapshot.binding, "Unbound"); }
// Header art is drawn beneath the stock CItem illustration/title at the guarded
// native call site. These primitives affect presentation only, never title spans.
extern "C" __declspec(dllexport) void __stdcall ItemDescriptionHeader(void* window) {
    // During native comparison paint the ID is temporarily normalized. Resolve
    // this exact window by its registered owner, not a prior draw's text/color.
    ViewScope context(view_for(window));
    if (!owner(window) || !state.ready || state.force_stock || !config.enabled || !current_identity(window)) return;
    const int w = width(window); const unsigned g = tone(window);
    const u32 top = tint_top[g], bottom = tint_bottom[g], deep = deep_tone(top);
    ClipScope scope(0, 0, w, header_bottom);
    fill(window, 0, 0, w, header_bottom, key);
    rounded(window, 0, 0, w, header_bottom + 24, 11, edge_tone(top), edge_tone(top));
    for (int row = 1; row < header_bottom; ++row) {
        const int inset = row <= 10 ? corner_inset(row - 1, header_bottom + 24, 10) : 0;
        fill(window, 1 + inset, row, w - 2 - inset * 2, 1, mix(top, bottom, row - 1, header_bottom - 2));
    }
    {
        // Faint ornamental rings stay off the rounded corners and the 1px edge.
        ClipScope inner(1, 1, w - 1, header_bottom);
        ring(window, w - 64, 46, 56, top, bottom); ring(window, w - 6, 104, 44, top, bottom); ring(window, 150, 132, 40, top, bottom);
    }
    rounded(window, 10, 14, 77, 102, 7, deep, deep);           // illustration drop shadow
    rounded(window, 8, 9, 79, 104, 7, lift(top, 5), white);    // illustration medallion
    fill(window, 10, 11, 75, 100, white);                      // the native 75x100 art lands here
    // Frosted bar keeps native title colors readable, including a wrapped second span.
    rounded(window, 90, 7, w - 116, 32, 8, white, lift(top, 6));
    // The native 11x11 close child is at (w-16,3); leave 3px on every side.
    rounded(window, w - 19, 0, 17, 17, 6, lift(top, 4), lift(top, 4));
}
static void header_details(void* window) {
    const int w = width(window); const unsigned g = tone(window);
    const u32 top = tint_top[g], deep = deep_tone(top), shade = mix(top, deep, 1, 1), chip = mix(top, deep, 1, 3);
    ClipScope scope(0, 0, w, header_bottom);
    if (g) {
        // Native grade icon only: label text stays owned by the title formatter.
        char path[48]; copy(path, sizeof(path), "grade_enchant\\grade_icon"); char number[8]; integer(number, sizeof(number), g);
        append(path, sizeof(path), number); append(path, sizeof(path), ".bmp");
        if (auto icon = skin_texture(path)) {
            rounded(window, 64, 88, 28, 28, 14, white, white); rounded(window, 66, 90, 24, 24, 12, lift(top, 4), white);
            blit(window, field<u32*>(icon, 0x11C), field<int>(icon, 0x114), field<int>(icon, 0x118), 66, 90, 24, 24);
        }
    }
    if (state.loading) {
        rounded(window, 92, 44, 96, 10, 5, lift(top, 3), lift(top, 3));
        rounded(window, 92, 64, 64, 24, 8, lift(top, 2), lift(top, 2));
        rounded(window, 92, 97, 84, 16, 8, chip, chip);
        return;
    }
    shadow_text(window, 92, 43, state.snapshot.type_label, lift(top, 6), shade, 1);
    if (state.headline_kind) {
        static const char* const labels[] = {"", "Weapon ATK", "Weapon MATK", "Armor DEF"};
        shadow_text(window, 92, 58, labels[state.headline_kind], lift(top, 5), shade);
        char number[16]; integer(number, sizeof(number), state.headline);
        shadow_text(window, 91, 68, number, white, shade, 1, 20);
        int x = 94 + extent(window, number, 20, 1);
        if (state.headline_bonus > 0) {
            char bonus[16]; copy(bonus, sizeof(bonus), "+"); integer(bonus + 1, sizeof(bonus) - 1, state.headline_bonus);
            shadow_text(window, x, 75, bonus, yellow, shade, 1, 13); x += extent(window, bonus, 13, 1) + 6;
        }
        const auto& other = ItemDescriptionComparisonState;
        if (!component_view() && !comparison_view() && other.ready && !other.loading && other.headline_kind == state.headline_kind) {
            const int mine = state.headline + state.headline_bonus, theirs = other.headline + other.headline_bonus;
            if (mine != theirs) arrow(window, x, 77, mine > theirs ? 0xFF7CE08F : 0xFFE5453C, mine > theirs);
        }
    }
    const bool catalog = state.request.scope == w::catalog, unbound = binding_is_unbound();
    const int chip_w = minimum(w - 120, extent(window, state.snapshot.binding) + (catalog ? 16 : 26));
    rounded(window, 92, 97, chip_w, 16, 8, chip, chip);
    if (!catalog) lock(window, 99, 99, white, chip, unbound);
    text(window, catalog ? 100 : 113, 98, state.snapshot.binding, lift(top, 6) & 0xFFFFFF);
    int x = w - 16;
    for (int i = w::card_limit - 1; i >= 0; --i) {
        bool filled = false;
        // Server-classified components exclude forged/created-item metadata.
        for (unsigned r = 0; r < state.snapshot.row_count; ++r) {
            const auto& row = state.snapshot.rows[r];
            if ((row.section == w::cards || row.section == w::enchantments) && row.kind == w::component &&
                row.item_id && row.slot == i + 1 && !(row.flags & w::empty)) filled = true;
        }
        const bool socket = i < state.snapshot.slot_count;
        if (!socket && !filled) continue;
        x -= 14; fill(window, x, 99, 12, 12, white);
        fill(window, x + 2, 101, 8, 8, filled ? 0xFF346DBD : chip);
        if (filled) check(window, x + 2, 101, white);
    }
    if (comparison_view()) {
        const int pill = extent(window, "Equipped", 11, 1) + 16; x -= pill + 6;
        rounded(window, x, 96, pill, 18, 4, 0xFF2FC7A7, 0xFF2FC7A7); text(window, x + 8, 98, "Equipped", 0xFFFFFF, 1);
    }
}

static void close_scrollbar() {
    if (!state.scrollbar_live) return;
    if (capture() == state.scrollbar) reinterpret_cast<void(__thiscall*)(void*)>(0x00A482E0)(reinterpret_cast<void*>(0x0131F4E8));
    // flags=0: the native destructor releases its surface/lists, not inline storage.
    reinterpret_cast<void*(__thiscall*)(void*, int)>(0x0083C2C0)(state.scrollbar, 0);
    state.scrollbar_live = 0;
}
static int visible_height(void* window) { return height(window) - 166; }
static bool scrollable(void* window) { return state.content_height > visible_height(window); }
static void sync_scrollbar(void* window) {
    if (!state.scrollbar_live) {
        reinterpret_cast<void*(__thiscall*)(void*)>(0x00836870)(state.scrollbar);
        state.scrollbar_live = 1;
        field<void*>(state.scrollbar, 0x10) = window;
        field<int>(state.scrollbar, 0xB0) = 48;
    }
    const int visible = visible_height(window);
    if (height(state.scrollbar) != visible) set_size(state.scrollbar, 13, visible);
    field<int>(state.scrollbar, 0x1C) = width(window) - 27;
    field<int>(state.scrollbar, 0x20) = body_top;
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
    if (surface) blit(window, field<u32*>(surface, 0x18), 13, height(state.scrollbar), width(window) - 27, body_top, 13, height(state.scrollbar));
}

// Native std::list children at UIWindow+0x50: sentinel/next/previous/value.
// Restoration only dereferences children still in the current owned list.
// Capture appends children the stock code created after activation, so a late
// text viewer or button can never stay visible over the card body.
static bool capture_children(void* window) {
    auto head = field<void**>(window, 0x50); if (!head) return false;
    auto node = static_cast<void**>(head[0]); unsigned count = 0;
    while (node && node != head && count < 64) {
        auto child = node[2]; if (!child || field<void*>(child, 0x10) != window) return false;
        bool known = false;
        for (unsigned i = 0; i < state.child_count && !known; ++i) known = state.children[i].window == child;
        if (!known && state.child_count < 64) {
            auto& saved = state.children[state.child_count++]; saved.window = child;
            saved.visible = field<u8>(child, 0x28); saved.x = field<int>(child, 0x1C); saved.y = field<int>(child, 0x20);
        }
        ++count; node = static_cast<void**>(node[0]);
    }
    return node == head;
}
static void restore_children(void* window) {
    auto head = field<void**>(window, 0x50); if (!head) return;
    auto node = static_cast<void**>(head[0]); unsigned count = 0;
    while (node && node != head && count < 64) {
        auto child = node[2]; if (!child || field<void*>(child, 0x10) != window) return;
        for (unsigned i = 0; i < state.child_count; ++i) if (state.children[i].window == child) {
            field<u8>(child, 0x28) = static_cast<u8>(state.children[i].visible);
            field<int>(child, 0x1C) = state.children[i].x; field<int>(child, 0x20) = state.children[i].y; break;
        }
        ++count; node = static_cast<void**>(node[0]);
    }
}
static void hide_children(void* window) {
    capture_children(window);
    const auto close = field<void*>(window, 0x208);
    for (unsigned i = 0; i < state.child_count; ++i) {
        auto child = state.children[i].window;
        // Child pointers are borrowed only while native messages are suspended.
        field<u8>(child, 0x28) = child == close ? static_cast<u8>(state.children[i].visible) : 0;
    }
    if (close) { field<int>(close, 0x1C) = width(window) - 16; field<int>(close, 0x20) = 3; }
}
// Release custom interactions/children while keeping the request/snapshot.
// Item switches can retain the surface instead of shrinking and growing it.
static void release_view(void* window, bool keep_surface = false) {
    end_header_drag(window);
    if (!keep_surface) clear_artwork();
    close_scrollbar();
    if (state.ready) {
        restore_children(window); state.child_count = 0; state.ready = 0;
        if (!keep_surface) set_size(window, state.original_width, state.original_height);
    }
    state.pressed = state.hover = 0; dirty(window);
}
static void restore(void* window, bool destroying = false) {
    if (!owner(window)) return;
    release_view(window, destroying);
    state.pending = state.deferred = state.loading = 0;
    auto& missing = stock_body_missing[pane_index()];
    const bool rebuild = missing && !destroying; missing = false;
    if (rebuild) {
        // The optimized open never populated the hidden legacy text/options.
        // Rebuild those once only if a real fallback is needed. A native copy
        // owns its strings, d=1 avoids the stock same-item toggle-close, and
        // f=0 retains the native equipped-comparison refresh (f=1 closes it).
        u8 item[0xB8]; memset(item, 0, sizeof(item));
        reinterpret_cast<void(__thiscall*)(void*)>(0x006A1B20)(item);
        reinterpret_cast<void(__thiscall*)(void*, void*)>(0x006A25F0)(item, static_cast<u8*>(window) + 0xB8);
        NativeOpenScope stock(nullptr);
        reinterpret_cast<int(__thiscall*)(void*, int, int, void*, int, int, int)>(native(37))(window, 0, 24, item, 1, 0, 0);
        reinterpret_cast<void(__thiscall*)(void*)>(0x004F08F0)(item + 0x44);
        reinterpret_cast<void(__thiscall*)(void*)>(0x004F08F0)(item + 0x2C);
    }
    // The other pane's header arrow and stat deltas no longer have a partner.
    State& other = comparison_view() ? ItemDescriptionState : ItemDescriptionComparisonState;
    if (!component_view()) { other.layout_width = 0; if (other.owner) dirty(other.owner); }
}
static void align_pair();
static bool activate(void* window, bool retain_geometry = false) {
    if (state.ready) return true;
    state.child_count = 0;
    if (!capture_children(window)) { state.child_count = 0; return false; }
    if (!retain_geometry) { state.original_width = width(window); state.original_height = height(window); }
    auto renderer = *reinterpret_cast<void**>(0x012515F8);
    int w = pane_width, h = pane_height;
    if (renderer) { w = minimum(w, field<int>(renderer, 0x28) - 32); h = minimum(h, field<int>(renderer, 0x2C) - 32); }
    const auto& other = comparison_view() ? ItemDescriptionState : ItemDescriptionComparisonState;
    if (!component_view() && renderer && other.owner && other.ready && field<u8>(other.owner, 0x28) && field<int>(renderer, 0x28) >= 600)
        w = minimum(w, (field<int>(renderer, 0x28) - 32 - pane_gap) / 2);
    if (w < 280 || h < 240) { state.child_count = 0; return false; }
    set_size(window, w, h); state.ready = 1; state.layout_width = 0;
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
    if (main.ready && other.ready && screen_w >= 280 * 2 + pane_gap + 32) {
        const int pane_w = minimum(pane_width, (screen_w - 32 - pane_gap) / 2);
        if (width(right) != pane_w) { set_size(right, pane_w, height(right)); main.layout_width = 0; dirty(right); }
        if (width(left) != pane_w) { set_size(left, pane_w, height(left)); other.layout_width = 0; dirty(left); }
    }
    const int left_w = width(left), right_w = width(right);
    const int low = screen_w >= left_w + pane_gap + right_w ? left_w + pane_gap : 0;
    const int x = clamp(field<int>(right, 0x1C), low, screen_w - right_w);
    const int y = clamp(field<int>(right, 0x20), 0, screen_h - maximum(height(right), height(left)));
    const int lx = clamp(x - left_w - pane_gap, 0, screen_w - left_w);
    if (field<int>(right, 0x1C) != x || field<int>(right, 0x20) != y)
        reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00874AF0)(right, x, y);
    if (field<int>(left, 0x1C) != lx || field<int>(left, 0x20) != y)
        reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00874AF0)(left, lx, y);
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
// Same instance and inspection, ignoring the per-request token and fingerprint.
static bool same_identity(const w::Request& a, const w::Request& b) {
    w::Request x = a, y = b; x.request_id = y.request_id = 0; x.known_fingerprint = y.known_fingerprint = 0;
    const auto p = reinterpret_cast<const u8*>(&x), q = reinterpret_cast<const u8*>(&y);
    for (unsigned i = 0; i < sizeof(x); ++i) if (p[i] != q[i]) return false;
    return true;
}
static bool snapshot_current() {
    return state.snapshot.magic == w::magic && state.snapshot.result == w::ok && state.snapshot.request_id == state.request.request_id;
}
static bool send_ready() {
    const unsigned channel = comparison_view() || component_view() ? 1 : 0;
    return now() - state.last_send >= request_spacing && now() - channel_last_send[channel] >= request_spacing;
}
static bool transmit() {
    state.deferred = 0;
    auto packet = reinterpret_cast<void*(__cdecl*)()>(config.packet_ctor)();
    if (!packet) { state.pending = 0; return false; }
    state.pending = 1; state.sent_at = state.last_send = now();
    channel_last_send[comparison_view() || component_view() ? 1 : 0] = state.last_send;
    reinterpret_cast<void(__thiscall*)(void*, int, const void*)>(config.packet_send)(packet, sizeof(state.request), &state.request);
    // Existing servers have two throttled/watch channels. Component catalog
    // requests share the comparison channel; revalidate its owned item next so
    // the server's catalog request cannot permanently clear that inventory watch.
    if (component_view()) comparison_rewatch = true;
    return true;
}
// Builds the request for the window's current CItem. A reopened identical
// instance keeps its snapshot on screen while the server revalidates it.
static bool request_view(void* window, bool from_message) {
    if (!owner(window) || !field<u8>(window, 0x28) || !config.enabled) return false;
    if (comparison_view()) comparison_rewatch = false;
    w::Request request{}; request.packet_type = w::request_packet; request.packet_length = sizeof(request);
    request.magic = w::magic; request.version = w::version; request.message = w::inspect;
    const auto scope = component_view() ? w::catalog : from_message ? (comparison_view() ? w::inventory : static_cast<u16>(state.origin_scope)) : state.request.scope;
    if (!read_identity(static_cast<u8*>(window) + 0xB8, request, scope)) return false;
    const bool keep = snapshot_current() && same_identity(request, state.request);
    if (!keep) clear_artwork();
    if (keep && scope == w::inventory) request.known_fingerprint = state.snapshot.fingerprint;
    state.sequence = (state.sequence + 1) & 0x3FFFFFFF; if (!state.sequence) ++state.sequence;
    request.request_id = state.sequence | (component_view() ? 0xC0000000u : comparison_view() ? 0x80000000u : 0);
    if (!w::request_valid(request)) return false;
    state.request = request;
    if (keep) state.snapshot.request_id = request.request_id;
    state.loading = keep ? 0 : 1;
    if (!keep) state.layout_width = 0;
    // The server silently drops a view's request within 150 ms of the last one.
    if (send_ready()) return transmit();
    state.deferred = 1; state.pending = 0;
    return true;
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
extern "C" __declspec(dllexport) int __stdcall ItemDescriptionCustomDraw(void* window) {
    ViewScope context(view_for(window));
    return owner(window) && state.ready && !state.force_stock && config.enabled && current_identity(window);
}
static bool optimize_open(void* window, void* item) {
    if (!config.enabled || server_silent || !item || !field<u8>(window, 0x28)) return false;
    auto renderer = *reinterpret_cast<void**>(0x012515F8);
    if (renderer && (field<int>(renderer, 0x28) < 312 || field<int>(renderer, 0x2C) < 272)) return false;
    w::Request request{};
    return read_identity(item, request, component_view() ? w::catalog : comparison_view() ? w::inventory : static_cast<u16>(state.origin_scope));
}
static void begin_view(void* window, bool retained = false) {
    state.owner = window; state.force_stock = 0; state.scroll = 0;
    if (!request_view(window, true)) {
        if (retained) set_size(window, state.original_width, state.original_height);
        restore(window); return;
    }
    // Take the final geometry now, in the same frame as the native open.
    if (!server_silent || !state.loading) {
        if (!activate(window, retained)) {
            if (retained) set_size(window, state.original_width, state.original_height);
            restore(window); return;
        }
        align_pair();
    }
}

static void scan_snapshot() {
    state.headline_kind = state.headline = state.headline_bonus = 0;
    state.info_level = state.info_weapon = state.info_weight = -1;
    int atk = -1, matk = -1, def = -1, bonus = 0;
    for (unsigned i = 0; i < state.snapshot.row_count; ++i) {
        const auto& row = state.snapshot.rows[i]; int value = 0; const char* rest;
        if (row.kind != w::value || (row.flags & w::unknown)) continue;
        if (row.section == w::core) {
            if (same(row.label, "Weight")) state.info_weight = i;
            else if (same(row.label, "Weapon level")) state.info_weapon = i;
            else if ((rest = leading_int(row.text, value)) && !*rest && value >= 0) {
                if (same(row.label, "Base ATK")) atk = value;
                else if (same(row.label, "Base MATK")) matk = value;
                else if (same(row.label, "Base DEF")) def = value;
            }
        } else if (row.section == w::requirements && same(row.label, "Base level")) state.info_level = i;
        else if (row.section == w::refine && same(row.label, "Refine bonus") && (rest = leading_int(row.text, value)) && same(rest, " ATK")) bonus = value;
    }
    if (atk > 0 || (atk == 0 && matk <= 0)) { state.headline_kind = 1; state.headline = atk; state.headline_bonus = bonus; }
    else if (matk > 0) { state.headline_kind = 2; state.headline = matk; }
    else if (def >= 0) { state.headline_kind = 3; state.headline = def; }
}

static const char* section_name(unsigned section) {
    static const char* names[] = {"", "Base Stats:", "Base Stats:", "Special Effects:", "Base Stats:", "Grade:",
        "Cards & Enchantments:", "Random Options:", "Cards & Enchantments:", "Card Set Bonuses:", "Requirements:",
        "Trade Information:", "Equipment Comparison:"};
    return section < w::section_end ? names[section] : "";
}
static unsigned utf8_next(const char* p, unsigned n, unsigned at) {
    if (at >= n) return n;
    const auto c = static_cast<u8>(p[at]); unsigned size = c < 0x80 ? 1 : c >= 0xC2 && c <= 0xDF ? 2 : c >= 0xE0 && c <= 0xEF ? 3 : c >= 0xF0 && c <= 0xF4 ? 4 : 1;
    if (at + size > n) return at + 1;
    for (unsigned j = 1; j < size; ++j) if ((static_cast<u8>(p[at + j]) & 0xC0) != 0x80) return at + 1;
    return at + size;
}
static void add_line(int x, int y, int row, u8 kind, u8 style, const char* value) {
    if (state.line_count == 512) return;
    auto& line = state.lines[state.line_count++]; line.y = y; line.row = row; line.kind = kind; line.style = style;
    line.x = static_cast<i16>(x); copy(line.text, sizeof(line.text), value);
}
static unsigned add_shape(u16 kind, int x, int y, int w = 0, int h = 0, int row = 0) {
    if (state.shape_count == 256) return 256;
    auto& s = state.shapes[state.shape_count]; s.kind = kind; s.x = static_cast<i16>(x); s.y = y;
    s.w = static_cast<i16>(w); s.h = h; s.row = static_cast<u16>(maximum(0, row));
    return state.shape_count++;
}
static void set_shape_height(unsigned shape, int h) { if (shape < state.shape_count) state.shapes[shape].h = h; }
static int wrap(void* window, int x, int y, int available, const char* value, u8 style, int row, u8 kind, int advance) {
    const auto& s = styles[style];
    if (s.accent) available -= 8; // Bold numeric runs are slightly wider than the measured base face.
    const unsigned n = length(value, 512); unsigned at = 0;
    while (at < n && state.line_count < 512) {
        char candidate[192]; u16 boundaries[192]; unsigned count = 0, next = at;
        while (next < n && value[next] != '\n') {
            const auto after = utf8_next(value, n, next);
            if (after - at >= sizeof(candidate)) break;
            boundaries[count++] = static_cast<u16>(after - at); next = after;
        }
        // Native font measurement is expensive on the game thread. Search UTF-8
        // prefix boundaries, retaining the word-break/oversize-character rules.
        for (unsigned i = at; i < next; ++i) candidate[i - at] = value[i];
        candidate[next - at] = 0;
        unsigned fit = count;
        if (count && extent(window, candidate, s.size, s.bold) > available) {
            unsigned low = 1, high = count;
            while (low < high) {
                const unsigned mid = (low + high + 1) / 2, stop = boundaries[mid - 1];
                const char saved = candidate[stop]; candidate[stop] = 0;
                const bool fits = extent(window, candidate, s.size, s.bold) <= available;
                candidate[stop] = saved;
                if (fits) low = mid; else high = mid - 1;
            }
            fit = low;
        }
        unsigned end = count ? at + boundaries[fit - 1] : utf8_next(value, n, at), last_space = at;
        for (unsigned i = at; i < end; ++i) if (value[i] == ' ') last_space = i;
        if (end < n && value[end] != '\n' && value[end] != ' ' && last_space > at) end = last_space;
        for (unsigned i = at; i < end; ++i) candidate[i - at] = value[i]; candidate[end - at] = 0;
        add_line(x, y, row, kind, style, candidate); y += advance; at = end;
        while (at < n && (value[at] == ' ' || value[at] == '\n')) ++at;
    }
    return y;
}
static const char* display_label(const w::Row& row) {
    if (row.section == w::requirements) {
        if (same(row.label, "Base level")) return "Base Level";
        if (same(row.label, "Equip eligibility")) return "Equipable";
    }
    if (row.section == w::restrictions && same(row.label, "Discard")) return "Drop";
    return row.label;
}
static const char* display_value(const w::Row& row) {
    if (!(row.flags & w::unknown) && row.kind == w::value) {
        if (row.section == w::requirements) {
            // The item database defaults an omitted EquipLevelMin to zero.
            if (same(row.label, "Base level") && same(row.text, "0")) return "Any";
            if (same(row.label, "Equip eligibility")) {
                if (row.flags & w::unmet) return "No";
                if (row.flags & w::active) return "Yes";
            }
        }
        if (row.section == w::restrictions && same(row.text, "Allowed by item policy")) return "Allowed";
    }
    return row.text;
}
static void compose(const w::Row& row, char* value, unsigned capacity) {
    value[0] = 0; int number = 0; const char* rest = leading_int(row.text, number);
    if (row.label[0]) {
        append(value, capacity, display_label(row));
        append(value, capacity, row.section != w::requirements && rest && !*rest ? " " : ": ");
    }
    append(value, capacity, display_value(row));
}
static bool is_note(const w::Row& row) { return row.kind == w::note || (row.flags & w::unknown); }
static int right_edge(void* window) { return width(window) - 32; }
static void heading(void* window, int& y, const char* title, int count = -1, int total = -1) {
    if (y) { add_shape(s_divider, 14, y + 4, right_edge(window) - 10, 4); y += 15; }
    add_shape(s_diamond, 16, y); add_line(28, y, -1, k_heading, t_heading, title);
    if (count >= 0) {
        char number[32]; integer(number, sizeof(number), count);
        if (total >= 0) { char rest[16]; integer(rest, sizeof(rest), total); append(number, sizeof(number), " / "); append(number, sizeof(number), rest); }
        add_line(34 + extent(window, title, 13, 1), y + 2, -1, k_heading, t_count, number);
    }
    y += 22;
}
static void bullet_row(void* window, int& y, unsigned index) {
    const auto& row = state.snapshot.rows[index]; char value[256]; compose(row, value, sizeof(value));
    const bool note = is_note(row), unmet = row.flags & w::unmet, active = row.flags & w::active;
    u16 icon = note ? s_info : unmet ? s_lock : active ? s_check : s_sparkle;
    u8 style = note ? t_note : unmet ? t_muted : t_body;
    if (row.section == w::requirements && !note) { icon = unmet ? s_cross : active ? s_check : s_sparkle; style = unmet ? t_bad : active ? t_good : t_plain; }
    add_shape(icon, icon == s_info ? 15 : icon == s_check ? 15 : 17, y, 0, 0, index);
    y = wrap(window, 30, y, right_edge(window) - 36, value, style, index, k_text, note ? 15 : 17) + 2;
}
static void stat_delta(const w::Row& row, char* delta, unsigned capacity) {
    delta[0] = 0; const auto& other = ItemDescriptionComparisonState;
    if (component_view() || comparison_view() || !other.ready || other.loading || other.headline_kind != state.headline_kind || !state.headline_kind) return;
    static const char* const labels[] = {"", "Base ATK", "Base MATK", "Base DEF"};
    int change = 0;
    if (row.section == w::core && same(row.label, labels[state.headline_kind])) change = state.headline - other.headline;
    else if (row.section == w::refine && same(row.label, "Refine bonus") && state.headline_kind == 1) change = state.headline_bonus - other.headline_bonus;
    if (!change) return;
    copy(delta, capacity, change > 0 ? "(+" : "("); char number[16]; integer(number, sizeof(number), change);
    append(delta, capacity, number); append(delta, capacity, ")");
}
static void stat_row(void* window, int& y, unsigned index) {
    const auto& row = state.snapshot.rows[index];
    if (row.kind != w::value || is_note(row)) { bullet_row(window, y, index); return; }
    char label[64]; copy(label, sizeof(label), row.label);
    if (row.section == w::refine && same(row.label, "Refine bonus")) {
        char number[8]; integer(number, sizeof(number), state.snapshot.refine); copy(label, sizeof(label), "Refine +"); append(label, sizeof(label), number);
    }
    const bool next = row.section == w::refine && starts(row.label, "Next +");
    char delta[24]; stat_delta(row, delta, sizeof(delta));
    const int lw = extent(window, label, 12), vw = extent(window, row.text, 12, 1);
    if (30 + lw + 5 + vw + (delta[0] ? 5 + extent(window, delta, 12) : 0) > right_edge(window) - 6) { bullet_row(window, y, index); return; }
    add_shape(s_sparkle, 17, y, 0, 0, index);
    add_line(30, y, index, k_text, t_plain, label);
    add_line(35 + lw, y, index, k_text, next ? t_muted : t_value, row.text);
    if (delta[0]) add_line(40 + lw + vw, y, index, k_text, delta[1] == '+' ? t_good : t_bad, delta);
    y += 18;
}
static bool component_section(unsigned section) { return section == w::cards || section == w::enchantments || section == w::comparison; }
static void component(void* window, int& y, unsigned index, bool* consumed) {
    const auto& row = state.snapshot.rows[index]; const int right = right_edge(window);
    char value[256];
    if (!row.item_id) {
        // Empty or unknown socket: one compact strip.
        const unsigned panel = add_shape(s_slot, 16, y, right - 16, 0, index);
        copy(value, sizeof(value), row.label); if (row.label[0]) append(value, sizeof(value), "  "); append(value, sizeof(value), row.text);
        const int end = wrap(window, 26, y + 5, right - 34, value, (row.flags & w::empty) ? t_muted : t_note, index, k_component_text, 16);
        set_shape_height(panel, maximum(24, end - y + 4)); y += maximum(24, end - y + 4) + 6; return;
    }
    const unsigned panel = add_shape(s_card, 16, y, right - 16, 0, index);
    add_shape(s_art, 26, y + 9, 40, 52, index);
    const auto name = item_name(row.item_id);
    int ty = wrap(window, 78, y + 7, right - 86, name ? name : "Item", t_card_title, index, k_component_title, 17);
    // Card/enchant names and effects suffice. Keep actual warnings and comparison
    // descriptions, but omit the redundant "Slot N - Installed card" subtitle.
    if (row.section == w::comparison || is_note(row)) {
        copy(value, sizeof(value), row.text);
        ty = wrap(window, 78, ty, right - 86, value, t_card_sub, index, k_component_text, 15) + 2;
    }
    // One image, one name, then the effects owned by this slot.
    for (unsigned j = index + 1; j < state.snapshot.row_count; ++j) {
        const auto& effect = state.snapshot.rows[j];
        if (effect.section != row.section) continue;
        if (effect.kind == w::component || starts(effect.label, "Slot ")) break;
        if (effect.slot && effect.slot != row.slot) continue;
        compose(effect, value, sizeof(value));
        ty = wrap(window, 78, ty, right - 86, value, is_note(effect) ? t_note : (effect.flags & w::unmet) ? t_muted : t_card_body, j, k_component_text, 17);
        consumed[j] = true;
    }
    const int h = maximum(70, ty - y + 6); set_shape_height(panel, h);
    if (state.hit_count < 64) state.hits[state.hit_count++] = {16, y, right - 16, h, static_cast<int>(index)};
    y += h + 8;
}
static void grade_panel(void* window, int& y, bool* consumed) {
    const int right = right_edge(window); const unsigned panel = add_shape(s_tiers, 16, y, right - 16);
    char title[96]; copy(title, sizeof(title), "Grade"); int name_w = 0, title_row = -1;
    for (unsigned i = 0; i < state.snapshot.row_count; ++i) {
        const auto& row = state.snapshot.rows[i]; if (row.section != w::grade || consumed[i]) continue;
        if (same(row.label, "Current grade")) { copy(title, sizeof(title), "Current grade  "); append(title, sizeof(title), row.text); consumed[i] = true; title_row = static_cast<int>(i); }
        else if (row.label[0] && !is_note(row)) name_w = maximum(name_w, extent(window, row.label, 12, 1));
    }
    name_w = minimum(name_w + 14, (right - 56) / 2);
    add_line(26, y + 7, title_row, k_text, t_card_title, title); int ty = y + 30;
    char value[256];
    for (unsigned i = 0; i < state.snapshot.row_count; ++i) {
        const auto& row = state.snapshot.rows[i]; if (row.section != w::grade || consumed[i]) continue;
        consumed[i] = true;
        if (is_note(row)) {
            add_shape(s_info, 26, ty, 0, 0, i); compose(row, value, sizeof(value));
            ty = wrap(window, 42, ty, right - 50, value, t_tier_note, i, k_text, 16); continue;
        }
        const bool on = !(row.flags & w::unmet);
        add_shape((row.flags & w::active) ? s_check : (row.flags & w::unmet) ? s_lock : s_sparkle, 26, ty, 0, 0, i);
        int x = 40;
        if (row.label[0]) { add_line(x, ty, i, k_text, on ? t_tier_name : t_tier_off_name, row.label); x += name_w; }
        ty = wrap(window, x, ty, right - 8 - x, row.text, on ? t_tier_text : t_tier_off, i, k_text, 18);
    }
    set_shape_height(panel, ty - y + 6); y = ty + 14;
}
static void chips(void* window, int& y, unsigned first, bool* consumed) {
    const int right = right_edge(window); int x = 16; bool any = false;
    for (unsigned i = first; i < state.snapshot.row_count; ++i) {
        const auto& row = state.snapshot.rows[i];
        if (row.section != w::restrictions || consumed[i] || row.kind != w::value || is_note(row)) continue;
        char label[64]; copy(label, sizeof(label), display_label(row)); append(label, sizeof(label), ":");
        const char* value = display_value(row);
        const int lw = extent(window, label, 11) + 4, vw = extent(window, value, 11, 1), cw = lw + vw + 18;
        if (cw > right - 16) continue;
        if (x + cw > right && x > 16) { x = 16; y += 24; }
        const bool good = starts(value, "Allowed") || starts(value, "Yes"), bad = starts(value, "No");
        add_shape(good ? s_chip_good : bad ? s_chip_bad : s_chip_plain, x, y, cw, 20, i);
        add_line(x + 9, y + 4, i, k_text, t_chip_label, label);
        add_line(x + 9 + lw, y + 4, i, k_text, good ? t_chip_good : bad ? t_chip_bad : t_chip_plain, value);
        x += cw + 6; consumed[i] = any = true;
    }
    if (any) y += 28;
}
static void layout(void* window) {
    state.line_count = state.hit_count = state.shape_count = 0; int y = 0;
    bool consumed[w::row_limit]{};
    // The info strip and native title already carry these values.
    if (state.info_weight >= 0) consumed[state.info_weight] = true;
    if (state.info_weapon >= 0) consumed[state.info_weapon] = true;
    for (unsigned i = 0; i < state.snapshot.row_count; ++i) {
        const auto& row = state.snapshot.rows[i];
        if ((row.section == w::refine && same(row.label, "Refine level")) ||
            (row.section == w::requirements && same(row.label, "Maximum level"))) consumed[i] = true;
    }
    static const u8 groups[][3] = {{w::core, w::attributes, w::refine}, {w::native_effects, 0, 0}, {w::cards, w::enchantments, 0},
        {w::card_sets, 0, 0}, {w::grade, 0, 0}, {w::random_options, 0, 0}, {w::requirements, 0, 0}, {w::restrictions, 0, 0},
        {w::comparison, 0, 0}};
    for (const auto& group : groups) {
        int first = -1;
        for (unsigned i = 0; i < state.snapshot.row_count && first < 0; ++i) {
            const auto section = state.snapshot.rows[i].section;
            if (!consumed[i] && section && (section == group[0] || section == group[1] || section == group[2])) first = static_cast<int>(i);
        }
        if (first < 0) continue;
        const unsigned lead = group[0];
        if (lead == w::cards) {
            const int used = state.snapshot.card_count + state.snapshot.enchant_count;
            heading(window, y, section_name(lead), used, state.snapshot.slot_count && used <= state.snapshot.slot_count ? state.snapshot.slot_count : -1);
        }
        else if (lead == w::random_options) heading(window, y, section_name(lead), state.snapshot.option_count);
        else heading(window, y, section_name(lead));
        if (lead == w::grade) { grade_panel(window, y, consumed); continue; }
        if (lead == w::restrictions) chips(window, y, first, consumed);
        for (unsigned i = first; i < state.snapshot.row_count; ++i) {
            const auto& row = state.snapshot.rows[i];
            if (consumed[i] || !row.section || (row.section != group[0] && row.section != group[1] && row.section != group[2])) continue;
            consumed[i] = true;
            if (row.kind == w::component || (component_section(row.section) && row.label[0] && starts(row.label, "Slot ")))
                component(window, y, i, consumed);
            else if (lead == w::core) stat_row(window, y, i);
            else bullet_row(window, y, i);
        }
    }
    if (state.snapshot.flags & w::truncated) {
        if (y) y += 4; add_shape(s_info, 15, y); add_line(30, y, -1, k_text, t_note, "Some effects were omitted."); y += 18;
    }
    state.content_height = y + 10; state.layout_width = width(window);
    state.scroll = clamp(state.scroll, 0, state.content_height - visible_height(window));
}
static bool glyph(const Shape& s) { return s.kind >= s_diamond && s.kind <= s_info; }
static void draw_shape(void* window, const Shape& s, int y) {
    // Row glyphs are stored at their text line's y; centre each on that line here.
    static const u8 glyph_offset[] = {0, 0, 5, 4, 4, 4, 3, 2};
    if (glyph(s)) y += glyph_offset[s.kind];
    const auto& row = state.snapshot.rows[s.row < state.snapshot.row_count ? s.row : 0];
    const bool hover = state.hover >= 100 && state.hover - 100 == s.row;
    switch (s.kind) {
    case s_divider:
        rounded(window, s.x, y, 4, 4, 2, rule, rule); fill(window, s.x + 5, y + 1, s.w - 10, 1, rule); rounded(window, s.x + s.w - 4, y, 4, 4, 2, rule, rule); break;
    case s_diamond: diamond(window, s.x, y, 0xFF000000 | blue); break;
    case s_sparkle: sparkle(window, s.x, y, sparkle_ink); break;
    case s_check: check(window, s.x, y, 0xFF000000 | green); break;
    case s_cross: cross(window, s.x, y, 0xFF000000 | red); break;
    case s_lock: lock(window, s.x, y, 0xFFC9CED8, card_top, false); break;
    case s_info: info(window, s.x, y, s.row && row.section == w::grade ? 0xFFC9B79E : 0xFFB5BFD0); break;
    case s_card: case s_tiers:
        // Flat interiors eliminate gradient bands and make hover repaint cheap.
        // Only real component panels highlight; grade rows are never hit targets.
        rounded(window, s.x, y, s.w, s.h, 8, hover && s.kind == s_card ? card_hover : card_edge, hover && s.kind == s_card ? card_hover : card_edge);
        rounded(window, s.x + 1, y + 1, s.w - 2, s.h - 2, 7,
            hover && s.kind == s_card ? card_highlight : card_top, hover && s.kind == s_card ? card_highlight : card_top);
        if (s.kind == s_card) rounded(window, s.x + 8, y + 7, 44, 56, 5, white, white);
        break;
    case s_slot:
        rounded(window, s.x, y, s.w, s.h, 7, slot_edge, slot_edge); rounded(window, s.x + 1, y + 1, s.w - 2, s.h - 2, 6, slot_fill, slot_fill); break;
    case s_chip_good: case s_chip_bad: case s_chip_plain: {
        const u32 edge = s.kind == s_chip_good ? 0xFFCDE9D6 : s.kind == s_chip_bad ? 0xFFF1D2CF : 0xFFDCE2EC;
        const u32 inside = s.kind == s_chip_good ? 0xFFF1FAF4 : s.kind == s_chip_bad ? 0xFFFDF3F2 : 0xFFF6F8FB;
        rounded(window, s.x, y, s.w, s.h, 10, edge, edge); rounded(window, s.x + 1, y + 1, s.w - 2, s.h - 2, 9, inside, inside); break;
    }
    case s_art: if (row.item_id) item_icon(window, row.item_id, s.x, y, s.w, s.h); break;
    }
}
static void draw_line(void* window, const Line& line, int y) {
    const auto& s = styles[line.style < t_style_end ? line.style : 0];
    if (!s.accent) { text(window, line.x, y, line.text, s.color, s.bold, s.size); return; }
    // Numeric tokens ([+-]digits[.digits][%]) take the accent, as in card effects.
    const char* v = line.text; const unsigned n = length(v, sizeof(line.text) - 1); unsigned at = 0; int x = line.x;
    const auto segment = [&](unsigned a, unsigned b, u32 color, int bold) {
        if (b <= a) return; char part[192]; const unsigned count = minimum(b - a, 191);
        for (unsigned i = 0; i < count; ++i) part[i] = v[a + i]; part[count] = 0;
        text(window, x, y, part, color, bold, s.size); x += extent(window, part, s.size, bold);
    };
    for (unsigned i = 0; i < n;) {
        unsigned j = i;
        if (!(i && alnum(v[i - 1]))) {
            if ((v[j] == '+' || v[j] == '-') && j + 1 < n && digit(v[j + 1])) ++j;
            if (j < n && digit(v[j])) {
                while (j < n && digit(v[j])) ++j;
                if (j + 1 < n && v[j] == '.' && digit(v[j + 1])) { ++j; while (j < n && digit(v[j])) ++j; }
                if (j < n && v[j] == '%') ++j;
            } else j = i;
        }
        if (j == i) { ++i; continue; }
        segment(at, i, s.color, s.bold); segment(i, j, s.accent, 1); at = i = j;
    }
    segment(at, n, s.color, s.bold);
}
static void draw_body(void* window, int left, int top, int right, int bottom) {
    ClipScope scope(left, top, right, bottom);
    const int visible_bottom = height(window) - 12;
    for (unsigned i = 0; i < state.shape_count; ++i) {
        const auto& s = state.shapes[i]; const int y = body_top + s.y - state.scroll;
        if (y + maximum(s.h, 16) <= top || y >= bottom) continue;
        // A clipped panel may cross the viewport; glyphs follow their full text line.
        if (glyph(s) ? y >= body_top && y + 16 <= visible_bottom : y + maximum(s.h, 12) > body_top && y < visible_bottom)
            draw_shape(window, s, y);
    }
    for (unsigned i = 0; i < state.line_count; ++i) {
        const auto& line = state.lines[i]; const int y = body_top + line.y - state.scroll;
        if (y < top || y + styles[line.style < t_style_end ? line.style : 0].size + 4 > bottom) continue;
        if (line.x >= left && line.x < right) draw_line(window, line, y);
    }
}
static bool repaint_hover(void* window, int previous, int hovered) {
    // A hover transition changes at most two component panels. Repaint those on
    // the existing native surface instead of dirtying/rebuilding the whole window
    // (native art/title, frame, all text and scrollbar) on the game thread.
    if (state.loading || state.layout_width != width(window)) return false;
    auto surface = field<void*>(window, 0x24);
    if (!surface || !field<u32*>(surface, 0x18) || field<int>(surface, 4) < width(window)) return false;
    bool painted = false;
    for (unsigned i = 0; i < state.hit_count; ++i) {
        const auto& h = state.hits[i];
        if (100 + h.row != previous && 100 + h.row != hovered) continue;
        const int y = body_top + h.y - state.scroll;
        const int top = maximum(body_top, y), bottom = minimum(height(window) - 12, y + h.height);
        if (top >= bottom) continue;
        draw_body(window, h.x, top, h.x + h.width, bottom); painted = true;
    }
    // CSurface+0x1C is the native DIB upload flag (also used by its raw blit).
    // OnDraw returns without native/content rebuilding; the manager still sees
    // the dirty-window transaction and updates any cached parent composition.
    if (painted) field<u32>(surface, 0x1C) |= 1;
    return true;
}
static bool repaint_partial(void* window, unsigned regions, int previous) {
    if (state.loading || state.layout_width != width(window)) return false;
    auto surface = field<void*>(window, 0x24);
    if (!surface || !field<u32*>(surface, 0x18) || field<int>(surface, 4) < width(window)) return false;
    if (regions & paint_body) {
        // The body lies inside the straight frame edges, above the rounded footer.
        // Clear old text/panels while retaining the native title/art and info strip.
        fill(window, 1, body_top, width(window) - 2, visible_height(window), white);
        draw_body(window, 0, body_top, width(window), height(window) - 12);
    } else if (regions & paint_hover) {
        if (!repaint_hover(window, previous, state.hover)) return false;
    }
    if ((regions & (paint_body | paint_bar)) && scrollable(window)) {
        fill(window, width(window) - 27, body_top, 13, visible_height(window), white);
        draw_scrollbar(window);
    }
    field<u32>(surface, 0x1C) |= 1; return true;
}
static void card_frame(void* window) {
    const int w = width(window), h = height(window); const u32 edge = edge_tone(tint_top[tone(window)]);
    ClipScope scope(0, header_bottom, w, h);
    fill(window, 0, header_bottom, w, h - header_bottom, key);
    rounded(window, 0, 0, w, h, 11, edge, edge); rounded(window, 1, 1, w - 2, h - 2, 10, white, white);
}
static void info_strip(void* window) {
    const int w = width(window), y = 124;
    const auto pair = [&](int x, const char* label, const char* value, u32 color) {
        text(window, x, y, label, ink, 1, 12); text(window, x + extent(window, label, 12, 1) + 3, y, value, color, 1, 12);
    };
    const auto pair_width = [&](const char* label, const char* value) { return extent(window, label, 12, 1) + 3 + extent(window, value, 12, 1); };
    const auto& rows = state.snapshot.rows;
    const bool unmet = state.info_level >= 0 && (rows[state.info_level].flags & w::unmet);
    pair(16, "Lv.:", state.info_level >= 0 ? display_value(rows[state.info_level]) : "-", unmet ? red : blue);
    if (state.info_weapon >= 0) pair(w / 2 - pair_width("Weapon Lv.:", rows[state.info_weapon].text) / 2, "Weapon Lv.:", rows[state.info_weapon].text, blue);
    if (state.info_weight >= 0) pair(w - 18 - pair_width("Weight:", rows[state.info_weight].text), "Weight:", rows[state.info_weight].text, blue);
    rounded(window, 14, 145, 4, 4, 2, rule, rule); fill(window, 19, 146, w - 38, 1, rule); rounded(window, w - 18, 145, 4, 4, 2, rule, rule);
}
static void skeleton_body(void* window) {
    const int w = width(window), bottom = height(window) - 12, right = right_edge(window);
    rounded(window, 16, 126, 56, 11, 5, skeleton, skeleton); rounded(window, w / 2 - 40, 126, 80, 11, 5, skeleton, skeleton);
    rounded(window, w - 88, 126, 70, 11, 5, skeleton, skeleton);
    rounded(window, 14, 145, 4, 4, 2, rule, rule); fill(window, 19, 146, w - 38, 1, rule); rounded(window, w - 18, 145, 4, 4, 2, rule, rule);
    int y = body_top + 2;
    for (int section = 0; section < 3 && y + 70 < bottom; ++section) {
        rounded(window, 16, y, 104, 12, 6, skeleton_heading, skeleton_heading); y += 24;
        for (int line = 0; line < 3; ++line) { rounded(window, 30, y, (right - 30) * (9 - line * 2 - section) / 10, 10, 5, skeleton, skeleton); y += 18; }
        y += 16;
    }
}
static bool inside(int x, int y, int left, int top, int w, int h) { return x >= left && y >= top && x < left + w && y < top + h; }
static bool header_space(void* window, int x, int y) {
    return inside(x, y, 2, 2, width(window) - 4, header_bottom - 2) &&
        !inside(x, y, 8, 8, 80, 108) && // Native illustration / card-art actions.
        !inside(x, y, width(window) - 18, 1, 16, 16) && // Native close child.
        !inside(x, y, width(window) - 72, 98, 60, 16); // Passive slot indicators.
}
static bool move_header(void* window, int x, int y) {
    if (header_drag.owner != window) return false;
    if (capture() != window) { header_drag.owner = nullptr; return false; }
    int left = field<int>(window, 0x1C) + x - header_drag.x;
    int top = field<int>(window, 0x20) + y - header_drag.y;
    auto moving = window;
    if (comparison_view() && ItemDescriptionState.owner && ItemDescriptionState.ready) {
        moving = ItemDescriptionState.owner; left += width(window) + pane_gap;
    }
    auto renderer = *reinterpret_cast<void**>(0x012515F8);
    if (renderer) {
        left = clamp(left, 0, field<int>(renderer, 0x28) - width(moving));
        top = clamp(top, 0, field<int>(renderer, 0x2C) - height(moving));
    }
    if (left != field<int>(moving, 0x1C) || top != field<int>(moving, 0x20)) {
        reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00874AF0)(moving, left, top);
        align_pair();
    }
    return true;
}
static int hit(void* window, int x, int y) {
    if (state.loading) return 0;
    if (scrollable(window) && inside(x, y, width(window) - 27, body_top, 13, visible_height(window))) return 6;
    if (y >= body_top && y < height(window) - 12) for (unsigned i = 0; i < state.hit_count; ++i) {
        const auto& h = state.hits[i]; if (inside(x, y - body_top + state.scroll, h.x, h.y, h.width, h.height)) return 100 + h.row;
    }
    return 0;
}
static void inspect_component(int row) {
    if (row < 0 || row >= state.snapshot.row_count || !state.snapshot.rows[row].item_id) return;
    if (!item_node(state.snapshot.rows[row].item_id)) return; // Never open native details for a missing client catalog entry.
    // Native card/combined-detail window 82 has independent custom state.
    u8 item[0xB8]; memset(item, 0, sizeof(item));
    reinterpret_cast<void(__thiscall*)(void*)>(0x006A1B20)(item);
    reinterpret_cast<void(__thiscall*)(void*, u32)>(0x006A6570)(item, state.snapshot.rows[row].item_id);
    field<int>(item, 0) = 6; field<int>(item, 4) = 0; field<u8>(item, 0x5C) = 1;
    const bool existing = ItemDescriptionComponentState.owner && ItemDescriptionComponentState.ready;
    const auto parent = state.owner;
    auto target = reinterpret_cast<void*(__thiscall*)(void*, int)>(0x00A39340)(reinterpret_cast<void*>(0x0131F4E8), 82);
    if (target) {
        reinterpret_cast<int(__thiscall*)(void*, int, int, void*, int, int, int)>(*reinterpret_cast<u32*>(*static_cast<u8**>(target) + 37 * 4))(target, 0, 24, item, 1, 0, 0);
        // Place the independent detail pane next to its source only on first
        // opening; subsequent card clicks preserve the player's dragged position.
        if (!existing && parent && ItemDescriptionComponentState.owner == target && ItemDescriptionComponentState.ready) {
            auto renderer = *reinterpret_cast<void**>(0x012515F8);
            int x = field<int>(parent, 0x1C) - width(target) - pane_gap, y = field<int>(parent, 0x20);
            if (x < 0) x = field<int>(parent, 0x1C) + width(parent) + pane_gap;
            if (renderer) { x = clamp(x, 0, field<int>(renderer, 0x28) - width(target)); y = clamp(y, 0, field<int>(renderer, 0x2C) - height(target)); }
            reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00874AF0)(target, x, y);
        }
    }
    reinterpret_cast<void(__thiscall*)(void*)>(0x004F08F0)(item + 0x44);
    reinterpret_cast<void(__thiscall*)(void*)>(0x004F08F0)(item + 0x2C);
}

extern "C" __declspec(dllexport) int __stdcall ItemDescriptionReceive(const void* packet, unsigned bytes) {
    if (!packet || bytes != sizeof(w::Snapshot)) return 0;
    const auto token = static_cast<const w::Snapshot*>(packet)->request_id;
    ViewScope context((token & 0x40000000u) ? &ItemDescriptionComponentState : (token & 0x80000000u) ? &ItemDescriptionComparisonState : &ItemDescriptionState);
    if (!state.owner || state.force_stock) return 0;
    auto window = state.owner;
    if (!field<u8>(window, 0x28) || !w::snapshot_valid(*static_cast<const w::Snapshot*>(packet), state.request)) return 0;
    const auto& response = *static_cast<const w::Snapshot*>(packet);
    if (!state.pending && !(state.ready && response.result == w::stale)) return 0;
    server_proven = 1; server_silent = 0;
    if (response.result == w::stale && !state.pending) {
        // The server invalidated this watched instance: reinspect in place.
        state.snapshot.request_id = 0;
        if (!request_view(window, false)) restore(window);
        dirty(window); return 1;
    }
    if (response.result != w::ok || !current_identity(window)) { restore(window); return 1; }
    // Re-establishing the comparison watch after a component catalog request
    // normally returns identical bytes. Keep its cached layout and surface.
    if (state.ready && !state.loading && snapshot_current()) {
        const auto a = reinterpret_cast<const u8*>(&state.snapshot), b = reinterpret_cast<const u8*>(&response);
        unsigned i = 0; while (i < sizeof(response) && a[i] == b[i]) ++i;
        if (i == sizeof(response)) { state.pending = 0; return 1; }
    }
    memcpy(&state.snapshot, &response, sizeof(response)); state.pending = 0; state.loading = 0;
    if (!activate(window)) { restore(window); return 0; }
    scan_snapshot(); state.layout_width = 0;
    // The other pane's header arrow and stat deltas compare against this snapshot.
    State& other = comparison_view() ? ItemDescriptionState : ItemDescriptionComparisonState;
    if (!component_view()) { other.layout_width = 0; if (other.owner) dirty(other.owner); }
    align_pair(); dirty(window); return 1;
}
extern "C" __declspec(dllexport) int __fastcall ItemDescriptionMessage(void* window, void*, int a, int message, void* data, int d, int e, int f) {
    ViewScope context(view_for(window));
    if (owner(window) && state.ready && state.scrollbar_live && reinterpret_cast<void*>(a) == state.scrollbar) {
        const int before = state.scroll;
        const int visible = visible_height(window);
        const int delta = message == 7 ? reinterpret_cast<int>(data) : message == 9 ? -visible : message == 10 ? visible : 0;
        state.scroll = clamp(before + delta, 0, state.content_height - visible);
        sync_scrollbar(window);
        if (state.scroll != before) queue_paint(window, paint_body);
        return state.scroll - before; // Native drag uses the actual consumed delta.
    }
    const bool ours = field<int>(window, 0x1F8) == 12 || field<int>(window, 0x1F8) == 0xEA || field<int>(window, 0x1F8) == 82;
    if (ours && comparison_view() && message == 34) {
        if (ItemDescriptionState.ready || state.ready) { align_pair(); return 0; }
        // Without snapshots, preserve stock positioning and its complete fallback.
        return reinterpret_cast<int(__thiscall*)(void*, int, int, void*, int, int, int)>(native(37))(window, a, message, data, d, e, f);
    }
    // The profiled native handlers only change collection content/children for
    // these messages. All other notifications go straight through; releasing on
    // every notification discards the scrollbar/artwork and forces full relayout.
    if (ours && owner(window) && message != 0 && message != 1 && message != 5 && message != 6 &&
        message != 14 && message != 24 && message != 29 && message != 34 && message != 98)
        return reinterpret_cast<int(__thiscall*)(void*, int, int, void*, int, int, int)>(native(37))(window, a, message, data, d, e, f);
    const bool opening = ours && message == 24 && data && config.enabled;
    const bool optimized = opening && optimize_open(window, data);
    const bool retained = optimized && owner(window) && state.ready;
    const unsigned pane = pane_index();
    const u32 epoch = destroy_epochs[pane];
    bool resume = false; int scroll = 0;
    if (ours && owner(window)) {
        // Native messages may rebuild child objects; restore their visibility
        // before the call. Optimized item switches keep the parent surface.
        resume = state.ready && !opening && message != 5; scroll = state.scroll;
        release_view(window, retained);
        if (message == 5) { ++state.sequence; state.owner = nullptr; state.pending = state.deferred = state.loading = 0; }
    }
    if (opening) stock_body_missing[pane] = optimized;
    int result;
    {
        NativeOpenScope scope(optimized ? window : nullptr);
        result = reinterpret_cast<int(__thiscall*)(void*, int, int, void*, int, int, int)>(native(37))(window, a, message, data, d, e, f);
    }
    // Native same-item clicks can close/destroy the pane from inside OnMessage.
    if (destroy_epochs[pane] != epoch) return result;
    if (opening) {
        begin_view(window, retained);
    }
    else if (resume && owner(window)) {
        if (!current_identity(window) && !request_view(window, false)) restore(window);
        else if (activate(window)) { state.scroll = scroll; align_pair(); }
        else restore(window);
    }
    return result;
}
// Per-frame OnProcess: the manager only calls OnDraw for dirty windows and
// clears the flag afterwards, so timeouts and queued sends live here.
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionProcess(void* window, void*) {
    ViewScope context(view_for(window));
    reinterpret_cast<void(__thiscall*)(void*)>(native(19))(window);
    if (!owner(window) || state.force_stock || !field<u8>(window, 0x28)) { end_header_drag(window); return; }
    if (comparison_view() && comparison_rewatch && !request_view(window, false)) { restore(window); return; }
    if (state.deferred && send_ready() && !transmit()) { restore(window); return; }
    if (state.pending && now() - state.sent_at >= load_timeout) {
        state.pending = 0;
        if (state.loading) { if (state.ready && !server_proven) server_silent = 1; restore(window); }
    }
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionDraw(void* window, void*) {
    ViewScope context(view_for(window));
    auto& paint = partial_paints[pane_index()];
    const unsigned regions = paint.regions; paint.regions = 0;
    if (regions && owner(window) && state.ready && !state.force_stock && current_identity(window) &&
        width(window) == paint.width && height(window) == paint.height && ((regions & paint_body) || state.scroll == paint.scroll) &&
        field<void*>(window, 0x24) == paint.surface && paint.surface &&
        field<u32*>(paint.surface, 0x18) == paint.pixels && repaint_partial(window, regions, paint.previous)) return;
    // Resolve a changed native CItem before the header detour can paint it.
    if (owner(window) && state.ready && !state.force_stock && !current_identity(window) && !request_view(window, false)) restore(window);
    align_pair();
    // Comparison retains its real ID outside this synchronous paint. Choosing
    // the normal skin branch changes only header/frame presentation; the exact
    // native CItem formatter and all title color ownership still execute.
    const int native_id = field<int>(window, 0x1F8);
    if (owner(window) && state.ready && comparison_view()) field<int>(window, 0x1F8) = 12;
    reinterpret_cast<void(__thiscall*)(void*)>(native(20))(window);
    field<int>(window, 0x1F8) = native_id;
    if (!owner(window) || !state.ready || state.force_stock) return;
    // We no longer paint the hidden native backing, which used to set this.
    // Direct pixel writes must upload even if native item art/title is empty.
    auto surface = field<void*>(window, 0x24); if (surface) field<u32>(surface, 0x1C) |= 1;
    hide_children(window);
    const int w = width(window), h = height(window), bottom = h - 12;
    card_frame(window);
    header_details(window);
    if (state.loading) { skeleton_body(window); return; }
    if (!state.layout_width || state.layout_width != w) layout(window);
    info_strip(window);
    draw_body(window, 0, body_top, w, bottom);
    if (scrollable(window)) draw_scrollbar(window);
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionDown(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    if (owner(window) && state.ready && header_space(window, x, y) && (!capture() || capture() == window)) {
        state.pressed = 0; header_drag = {window, x, y};
        reinterpret_cast<void(__thiscall*)(void*, void*)>(0x00A4B750)(reinterpret_cast<void*>(0x0131F4E8), window);
        return;
    }
    if (!owner(window) || !state.ready || y < header_bottom) { reinterpret_cast<void(__thiscall*)(void*, int, int)>(native(25))(window, x, y); return; }
    state.pressed = hit(window, x, y);
    if (state.pressed == 6) {
        sync_scrollbar(window);
        const int before = field<int>(state.scrollbar, 0x7C);
        if (field<int>(state.scrollbar, 0x80) && (!capture() || capture() == state.scrollbar))
            reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00858970)(state.scrollbar, x - (width(window) - 27), y - body_top);
        if (before != field<int>(state.scrollbar, 0x7C)) queue_paint(window, paint_bar);
    }
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionMove(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    if (move_header(window, x, y)) return;
    if (!owner(window) || !state.ready) { reinterpret_cast<void(__thiscall*)(void*, int, int)>(native(28))(window, x, y); return; }
    const int hovered = hit(window, x, y), previous = state.hover;
    if (hovered != state.hover) {
        state.hover = hovered;
        if (previous >= 100 || hovered >= 100) queue_paint(window, paint_hover, previous);
    }
    if (state.scrollbar_live && (previous == 6 || hovered == 6 || capture() == state.scrollbar)) {
        const int before = field<int>(state.scrollbar, 0x7C);
        reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x0085A420)(state.scrollbar, x - (width(window) - 27), y - body_top);
        if (before != field<int>(state.scrollbar, 0x7C)) queue_paint(window, paint_bar);
    }
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionUp(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    if (header_drag.owner == window) { end_header_drag(window); state.pressed = 0; return; }
    if (capture() == window) { reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x00880BB0)(window, x, y); return; }
    if (!owner(window) || !state.ready || (y < header_bottom && !state.pressed)) { reinterpret_cast<void(__thiscall*)(void*, int, int)>(native(31))(window, x, y); return; }
    const int pressed = state.pressed; state.pressed = 0;
    if (state.scrollbar_live && (pressed == 6 || capture() == state.scrollbar)) {
        reinterpret_cast<void(__thiscall*)(void*, int, int)>(0x008590E0)(state.scrollbar, x - (width(window) - 27), y - body_top);
        return;
    }
    if (pressed >= 100 && pressed == hit(window, x, y)) inspect_component(pressed - 100);
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionRight(void* window, void*, int x, int y) {
    ViewScope context(view_for(window));
    if (!owner(window) || !state.ready) { reinterpret_cast<void(__thiscall*)(void*, int, int)>(native(32))(window, x, y); return; }
    const int row = hit(window, x, y); if (row >= 100) inspect_component(row - 100);
}
extern "C" __declspec(dllexport) void __fastcall ItemDescriptionWheel(void* window, void*, int delta) {
    ViewScope context(view_for(window));
    if (!owner(window) || !state.ready) { reinterpret_cast<void(__thiscall*)(void*, int)>(native(35))(window, delta); return; }
    const int before = state.scroll;
    if (delta && !state.loading) state.scroll = clamp(state.scroll + (delta > 0 ? -48 : 48), 0, state.content_height - visible_height(window));
    if (state.scroll != before) queue_paint(window, paint_body);
}
extern "C" __declspec(dllexport) void* __fastcall ItemDescriptionDestroy(void* window, void*, int flags) {
    ViewScope context(view_for(window));
    end_header_drag(window);
    ++destroy_epochs[pane_index()];
    if (owner(window)) { restore(window, true); state.owner = nullptr; ++state.sequence; state.force_stock = 0; }
    stock_body_missing[pane_index()] = false;
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
