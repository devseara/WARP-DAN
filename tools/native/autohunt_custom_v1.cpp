/* Custom AutoHunt UI v1, 2025-07-16 Ragexe x86.
 * Build-time image only: WARP embeds and relocates this code into the EXE.
 * Settings, drag payloads, input dialogs and persistence use the existing AHUI
 * handlers. This module owns only its window's presentation and hit geometry.
 */
using u8 = unsigned char;
using u16 = unsigned short;
using u32 = unsigned int;
static_assert(sizeof(void*) == 4, "Ragexe x86 ABI");
extern "C" void* __cdecl memset(void* d, int v, unsigned n) { auto p = static_cast<volatile u8*>(d); while (n--) *p++ = static_cast<u8>(v); return d; }
extern "C" void* __cdecl memcpy(void* d, const void* s, unsigned n) { auto p = static_cast<volatile u8*>(d); auto q = static_cast<const volatile u8*>(s); while (n--) *p++ = *q++; return d; }

// Pointer arrays and offsets are written by AutoCombatUI.qjs after relocation.
struct Config {
    u32 abi, state, fill, down, move, up, initializer, font, blit, item_resolver, icon_format;
    u32 rows[9]; // monsters, attack, support, healing, recovery, buffs, potions, movement, movement icon keys
    u32 icons[4]; // attack, support, healing, recovery
    const char* tabs[7]; const char* headings[7]; const char* subtitles[7];
    const char* basic[10]; const char* prefixes[4]; const char* suffixes[4];
    const char* potion[4]; const char* categories[4]; const char* choices[6];
    const char* labels[31];
    const char* controls[23];
    u32 text_charset, scalar_sender, wheel;
    const char* custom[21];
};
static_assert(sizeof(Config) == 620, "Custom UI config ABI 2");
extern "C" __declspec(dllexport) Config AutoHuntCustomConfig = {};
static Config& c = AutoHuntCustomConfig;
enum Label { Title, Reset, Close, Normal, NormalHint, Attack, Support, Heal, Status,
    RegisterItem, RegisterSkill, Seconds, Use, Weight, Weapon, Armor, OptionsSuffix,
    FightFirst, LootFirst, ReturnTown, ReturnHint, Continue, ContinueHint, BuffReturnHint,
    DelayHint, RejectSkill, RejectItem, StatusPotion, AllMonsters, Teleport, Priority };
enum Control { HpGauge, SpGauge, LootGauge, HpThumb, SpThumb, Left, LeftOver, LeftPressed,
    Right, RightOver, RightPressed, ScrollUp, ScrollDown, ScrollTrack, ThumbUp, ThumbMid,
    ThumbDown, CheckOn, CheckOff, DropdownArrow, RailHealing, RailPotion, RailLoot };
enum Custom { HuntSetup, MonsterSelection, CombatSkills, RecoveryRules, LootRules, MovementEscape,
    BuffItems, CoreBehavior, StopReturn, Advanced, General, CollectLoot, ReturnWeight, BuffReturn,
    Siegfried, AutoSaved, CollectCategories, InventoryFull, ShowEmpty, HideEmpty, EquipmentFilters };
template<class T> static T& at(void* p, unsigned o) { return *reinterpret_cast<T*>(static_cast<u8*>(p) + o); }
static u32& state(unsigned o) { return *reinterpret_cast<u32*>(c.state + o); }
static u8* row(unsigned index, unsigned slot) { return reinterpret_cast<u8*>(c.rows[index] + slot * (index == 0 ? 40 : 48)); }
static int minimum(int a, int b) { return a < b ? a : b; }
static int maximum(int a, int b) { return a > b ? a : b; }
static int clamp(int x, int lo, int hi) { return maximum(lo, minimum(x, hi)); }
constexpr u32 white = 0xFFFFFFFF, ink = 0x4A5263, blue = 0x4C7BD6, muted = 0x737D8F,
    orange = 0xE8862E, green = 0x3FA25B, red = 0xD9473F, rule = 0xFFE3E8F0, tint = 0xFFEDF1F7;
static bool painting;
static const unsigned nav_order[] = {0, 2, 1, 3, 4, 5, 6};
static int font_size(int size) { return c.font == 0 ? size : size + 3; }
static void fill(void* w, int x, int y, int width, int height, u32 color) {
    if (!painting) return;
    const int x0 = clamp(x, 0, 760), y0 = clamp(y, 0, 520);
    const int x1 = clamp(x + width, 0, 760), y1 = clamp(y + height, 0, 520);
    if (x1 > x0 && y1 > y0) reinterpret_cast<void(__stdcall*)(void*, int, int, int, int, u32)>(c.fill)(w, x0, y0, x1 - x0, y1 - y0, color);
}
static __declspec(noinline) void text(void* w, int x, int y, const char* s, u32 color = ink, int size = 12, int bold = 0, int available = -1) {
    if (!painting || !s || !*s) return;
    char bounded[256]; unsigned ends[128], count = 0, bytes = 0;
    const unsigned cp = reinterpret_cast<unsigned(__cdecl*)(unsigned)>(0x00A6F060)(c.text_charset);
    while (s[bytes] && count < 125 && bytes < 248) {
        const u8 lead = static_cast<u8>(s[bytes]); unsigned length = 1;
        if (cp == 65001) length = lead < 0x80 ? 1 : lead < 0xE0 ? 2 : lead < 0xF0 ? 3 : 4;
        else if ((cp == 932 && ((lead >= 0x81 && lead <= 0x9F) || (lead >= 0xE0 && lead <= 0xFC))) ||
                 ((cp == 936 || cp == 949 || cp == 950) && lead >= 0x81 && lead <= 0xFE)) length = 2;
        bool complete = true; for (unsigned k = 0; k < length; ++k) if (!s[bytes + k]) { complete = false; break; }
        if (!complete || bytes + length > 248) break;
        for (unsigned k = 0; k < length; ++k) bounded[bytes + k] = s[bytes + k];
        bytes += length; ends[count++] = bytes;
    }
    bounded[bytes] = 0;
    const int limit = available < 0 ? 744 - x : available;
    auto width = [&](const char* value) { return reinterpret_cast<int(__thiscall*)(void*, const char*, int, int, int, int, int)>(0x00A21C90)(w, value, 0, c.font, font_size(size), bold, 0); };
    if(limit<=0)return;
    if (width(bounded) > limit || s[bytes]) {
        do { if (count) --count; bytes = count ? ends[count - 1] : 0; bounded[bytes] = '.'; bounded[bytes+1] = '.'; bounded[bytes+2] = '.'; bounded[bytes+3] = 0; } while (count && width(bounded) > limit);
    }
    const u32 colorref = (color & 255) << 16 | (color & 0xFF00) | color >> 16;
    reinterpret_cast<void(__thiscall*)(void*, int, int, const char*, int, int, int, u32, int, int)>(0x00A25A70)(w, x, y, bounded, 0, c.font, font_size(size), colorref, bold, 0);
}
static void paragraph(void* w,int x,int y,const char* s,int width,u32 color=muted,int size=11,int lines=2) {
    if(!painting||!s)return;
    const unsigned cp=reinterpret_cast<unsigned(__cdecl*)(unsigned)>(0x00A6F060)(c.text_charset);
    for(int line=0;*s&&line<lines;++line){
        if(line==lines-1){text(w,x,y,s,color,size,0,width);break;}
        char buffer[256];unsigned n=0,cut=0,space=0;
        while(s[n]&&n<248){
            const u8 lead=static_cast<u8>(s[n]);unsigned len=1;
            if(cp==65001)len=lead<0x80?1:lead<0xE0?2:lead<0xF0?3:4;
            else if((cp==932&&((lead>=0x81&&lead<=0x9F)||(lead>=0xE0&&lead<=0xFC)))||((cp==936||cp==949||cp==950)&&lead>=0x81&&lead<=0xFE))len=2;
            bool complete=true;for(unsigned j=0;j<len;++j)if(!s[n+j])complete=false;if(!complete||n+len>248)break;
            if(s[n]==' ')space=n;
            for(unsigned j=0;j<len;++j)buffer[n+j]=s[n+j];n+=len;buffer[n]=0;
            if(reinterpret_cast<int(__thiscall*)(void*,const char*,int,int,int,int,int)>(0x00A21C90)(w,buffer,0,c.font,font_size(size),0,0)>width)break;
            cut=n;
        }
        if(s[n]&&space&&space<=cut)cut=space;
        if(!cut)return;buffer[cut]=0;text(w,x,y,buffer,color,size,0,width);s+=cut;while(*s==' ')++s;y+=18;
    }
}
static void number(void* w, int x, int y, unsigned value, u32 color = blue, const char* prefix = "") {
    char buffer[32]; unsigned n = 0; while (prefix[n] && n < 12) { buffer[n] = prefix[n]; ++n; }
    char digits[12]; unsigned d = 0; do { digits[d++] = static_cast<char>('0' + value % 10); value /= 10; } while (value && d < 10);
    while (d) buffer[n++] = digits[--d]; buffer[n] = 0; text(w, x, y, buffer, color);
}
static void box(void* w, int x, int y, int width, int height, u32 background = white, u32 edge = rule) {
    fill(w, x, y, width, height, edge); fill(w, x + 1, y + 1, width - 2, height - 2, background);
}
static void* texture(const char* path) {
    if (!painting || !path) return nullptr;
    void* manager = reinterpret_cast<void*(__cdecl*)()>(0x00A90350)(); if (!manager) return nullptr;
    auto converted = reinterpret_cast<void*(__cdecl*)(const char*)>(0x00A9F030)(path); if (!converted) return nullptr;
    return reinterpret_cast<void*(__thiscall*)(void*, void*)>(0x00A8D4A0)(manager, converted);
}
static void bitmap(void* w, Control control, int x, int y) {
    if (void* surface = texture(c.controls[control]))
        reinterpret_cast<void(__stdcall*)(void*, void*, int, int)>(c.blit)(w, surface, x, y);
}
static void crop(void* w, Control control, int x, int y, int sx, int sy, int width, int height) {
    if (void* surface = texture(c.controls[control]))
        reinterpret_cast<void(__thiscall*)(void*, int, int, void*, int, int, int, int, int, int)>(0x00A1D2B0)(w, x, y, surface, 0, 0, sx, sy, width, height);
}
static void check(void* w, int x, int y, bool on) {
    bitmap(w, on ? CheckOn : CheckOff, x, y);
}
static void icon(void* w, int x, int y, const char* key) {
    box(w, x - 4, y - 4, 32, 32);
    if (!painting || !key || !*key) return;
    char path[192];
    reinterpret_cast<int(__cdecl*)(char*, const char*, ...)>(0x00529850)(path, reinterpret_cast<const char*>(c.icon_format), key);
    void* manager = reinterpret_cast<void*(__cdecl*)()>(0x00A90350)(); if (!manager) return;
    auto converted = reinterpret_cast<void*(__cdecl*)(const char*)>(0x00A9F030)(path); if (!converted) return;
    auto surface = reinterpret_cast<void*(__thiscall*)(void*, void*)>(0x00A8D4A0)(manager, converted); if (!surface) return;
    reinterpret_cast<void(__stdcall*)(void*, void*, int, int)>(c.blit)(w, surface, x, y);
}
static void item_icon(void* w, int x, int y, u32 id) {
    const char* key = painting && id ? reinterpret_cast<const char*(__stdcall*)(u32)>(c.item_resolver)(id) : nullptr;
    icon(w, x, y, key);
}

struct Rect { int x, y, w, h; bool contains(int px, int py) const { return px >= x && py >= y && px < x + w && py < y + h; } };
// Temporary logical context lets summary controls reuse the exact stock handlers.
// Only tab/page/scroll are restored; settings and server packets retain ownership.
struct Mapping { Rect area, original; unsigned kind; int tab, page, scroll; };
static Mapping mappings[96], drag_map;
static unsigned mapping_count;
static bool dragging_slider, suppress_up, overview_advanced, show_skill_empty, show_buff_empty;
static int hover_x = -1, hover_y = -1;
static unsigned remembered_pickup;
struct Scrollbar { int x, top, bottom, thumb_top, thumb_height, travel; unsigned offset, maximum; };
static Scrollbar scrollbar;
static bool dragging_scroll;
static int scroll_grab;
static char percentage_tip[12]; // Native tooltip storage remains valid through its later draw.
static void map(Rect area, Rect original, unsigned kind = 0, int tab = -1, int page = -1, int scroll = -1) { if (mapping_count < 96) mappings[mapping_count++] = {area, original, kind, tab, page, scroll}; }
static void point(Rect area, int x, int y, unsigned kind = 0, int tab = -1, int page = -1, int scroll = -1) { map(area, {x, y, 1, 1}, kind, tab, page, scroll); }
static void translate(const Mapping& m, int x, int y, int& ox, int& oy) {
    ox = m.original.x + clamp(x - m.area.x, 0, m.area.w - 1) * (m.original.w - 1) / maximum(m.area.w - 1, 1);
    oy = m.original.y + clamp(y - m.area.y, 0, m.area.h - 1) * (m.original.h - 1) / maximum(m.area.h - 1, 1);
}
static const Mapping* hit(int x, int y) { for (unsigned i = mapping_count; i; --i) if (mappings[i-1].area.contains(x, y)) return &mappings[i-1]; return nullptr; }
static void label_check(void* w, const char* label, int x, int y, bool on, int ox, int oy, int width = 530, int tab = -1, int page = -1, int scroll = -1) {
    check(w, x, y, on); text(w, x + 22, y - 2, label, ink, 12, 0, width - 25); point({x - 3, y - 4, width, 24}, ox, oy, 0, tab, page, scroll);
}
static void slider(void* w, int x, int y, unsigned value, unsigned limit, int ox, int oy, int old_width, int old_right = 0, bool sp = false) {
    // Preserve native pixel dimensions, gauge clipping and thumb travel.
    const int tx = x + 21, ty = y + 5, right = tx + old_width + 7, travel = old_width - 14;
    const Rect left_rect{x, y, 14, 20}, right_rect{right, y, 14, 20};
    const bool pressed = state(116) != 0;
    bitmap(w, left_rect.contains(hover_x, hover_y) ? pressed ? LeftPressed : LeftOver : Left, x, y);
    bitmap(w, right_rect.contains(hover_x, hover_y) ? pressed ? RightPressed : RightOver : Right, right, y);
    const Control rail = limit == 90 ? RailLoot : state(4) == 2 ? RailHealing : RailPotion;
    crop(w, rail, tx, ty, limit == 90 ? 132 : rail == RailHealing ? 56 : 36, limit == 90 ? 117 : rail == RailHealing ? 120 : 123, old_width, 9);
    const int position = minimum(value, limit) * travel / limit;
    crop(w, limit == 90 ? LootGauge : sp ? SpGauge : HpGauge, tx, ty, 0, 0, position + 7, 9);
    bitmap(w, sp ? SpThumb : HpThumb, tx + position, y + 2);
    point(left_rect, ox - 14, oy + 2, 3);
    map({tx, y, old_width, 20}, {ox, oy, travel + 1, 1}, 1);
    point(right_rect, old_right ? old_right : ox + old_width + 2, oy + 2, 3);
    number(w, right + 24, y + 1, value); text(w, right + 47, y + 1, "%");
}
static void scroll_control(void* w, unsigned offset, unsigned max_scroll, int top, int bottom) {
    const int track = bottom - top - 3, height = maximum(18, track * 5 / maximum(5, max_scroll + 5));
    scrollbar = {722, top, bottom, top + 3 + static_cast<int>(minimum(state(offset), max_scroll)) * (track - height) / maximum(1, max_scroll), height, track - height, offset, max_scroll};
    bitmap(w, ScrollUp, 722, top); bitmap(w, ScrollDown, 722, bottom);
    for (int y = top + 3; y < bottom; y += 3) crop(w, ScrollTrack, 722, y, 0, 0, 7, minimum(3, bottom - y));
    bitmap(w, ThumbUp, 722, scrollbar.thumb_top);
    for (int y = scrollbar.thumb_top + 3; y < scrollbar.thumb_top + height - 3; y += 3) crop(w, ThumbMid, 722, y, 0, 0, 7, minimum(3, scrollbar.thumb_top + height - 3 - y));
    bitmap(w, ThumbDown, 722, scrollbar.thumb_top + height - 3);
    point({716,top-5,19,14},459,95); point({716,bottom-4,19,15},459,301);
    point({716,top+9,19,bottom-top-13},0,0,4);
}
static void nav(void* w) {
    for (int i = 0; i < 7; ++i) { const unsigned tab=nav_order[i];const int y = 125 + i * 44; if (state(4) == tab) box(w, 9, y, 128, 35, tint); text(w, 22, y + 9, c.tabs[tab], state(4) == tab ? blue : ink); }
    fill(w, 146, 109, 1, 370, rule);
}
static void basic(void* w) {
    const unsigned masks[] = {0, 0, 0, 0, 1u << 7, 1u << 8, 1u << 9, 1u << 10, 1u << 0, 1u << 2};
    const unsigned values[] = {156, 160, 164, 56};
    for (unsigned i = 0; i < 5; ++i) {
        const unsigned option = minimum(state(124), 5) + i; const int y = 176 + i * 48, old_y = 123 + i * 38;
        const bool on = option == 0 ? state(36) == 2 : option == 1 ? state(36) == 1 : option == 2 ? state(60) != 0 : option == 3 ? state(56) != 0 : (state(28) & masks[option]) != 0;
        if (option < 4 && option != 1) {
            label_check(w, c.prefixes[option], 169, y, on, 30, old_y, 310);
            box(w, 496, y - 4, 47, 23); number(w, 503, y - 1, state(values[option])); text(w, 550, y - 1, c.suffixes[option]);
            const int old_x[] = {151, 151, 284, 251}; point({496, y - 4, 47, 23}, old_x[option] + 3, old_y);
            if (option == 0) text(w, 191, y + 19, c.labels[NormalHint], muted, 11);
        } else label_check(w, c.basic[option], 169, y, on, 30, old_y);
        fill(w, 166, y + 35, 552, 1, rule);
    }
    scroll_control(w, 124, 5, 174, 423);
}
static void overview(void* w) {
    if (overview_advanced) { basic(w); return; }
    fill(w, 169, 175, 565, 1, rule);
    text(w, 170, 194, c.custom[CoreBehavior], blue, 13, 1, 265);
    text(w, 463, 194, c.custom[StopReturn], blue, 13, 1, 270);
    label_check(w, c.labels[Normal], 170, 234, state(36) != 1, 30, 278, 275, 2, 1);
    text(w, 192, 278, c.labels[Attack], blue, 12, 0, 240); point({168,272,276,30},0,0,11);
    text(w, 192, 322, c.labels[Support], blue, 12, 0, 240); point({168,316,276,30},0,0,12);
    check(w, 170, 368, state(40) != 2); text(w, 192, 366, c.custom[CollectLoot], ink, 12, 0, 245); point({167,364,276,26},0,0,10);
    label_check(w, c.custom[ReturnWeight], 464, 234, (state(132)&4)!=0, 50,225,266,4,2);
    number(w, 486, 257, state(128)); text(w, 515, 257, "%", muted);
    label_check(w, c.custom[BuffReturn], 464, 302, state(52)!=0,30,278,266,6);
    label_check(w, c.custom[Siegfried], 464, 368, (state(28)&4)!=0,30,275,266,0,-1,5);
    fill(w, 450, 191, 1, 212, rule);
    text(w, 170, 429, c.custom[AutoSaved], muted, 11);
}
static void monsters(void* w) {
    label_check(w, "", 170, 170, (state(64) & 1) != 0, 30, 100);
    text(w, 194, 167, c.labels[AllMonsters]);
    const unsigned scroll = minimum(state(144), 15);
    for (unsigned i = 0; i < 5; ++i) {
        const unsigned index = scroll + i; if (index >= state(76)) break;
        const int y = 210 + i * 43;
        label_check(w, reinterpret_cast<const char*>(row(0, index) + 8), 170, y, (state(64) & (1u << (index + 1))) != 0, 30, 138 + i * 38);
        fill(w, 166, y + 29, 552, 1, rule);
    }
    scroll_control(w, 144, clamp(static_cast<int>(state(76))-5,0,15), 172, 423);
}
static void skill_row(void* w, u8* r, const char* key, int index, int ox, int oy, int y) {
    const u32 id = at<u16>(r, 0); icon(w, 176, y + 3, id ? key : nullptr);
    text(w, 218, y, id ? reinterpret_cast<const char*>(r + 12) : c.labels[RegisterSkill], ink, 12, 0, 340);
    if (id) number(w, 577, y + 1, at<u16>(r, 2), blue, "Lv ");
    box(w, 657, y - 1, 55, 25); text(w, 664, y + 2, reinterpret_cast<const char*>(r + 36)); text(w, 721, y + 3, c.labels[Seconds]);
    point({168, y - 3, 405, 32}, ox, oy, 2); point({657, y - 1, 55, 25}, ox, oy + 36);
    fill(w, 168, y + 34, 566, 1, rule); (void)index;
}
static unsigned select_slots(unsigned group,bool all,unsigned* slots) {
    unsigned n=0,empty=8;
    for(unsigned i=0;i<8;++i){if(all||(group<3?at<u16>(row(group,i),0):at<u32>(row(group,i),0)))slots[n++]=i;else if(empty==8)empty=i;}
    if(!all&&empty<8)slots[n++]=empty;return n;
}
static void skills(void* w) {
    const unsigned page = clamp(state(8), 1, 3);
    unsigned slots[8]={0,1,2,3,4,5,6,7};
    const unsigned count = page == 3 ? 4 : select_slots(page,show_skill_empty,slots);
    for (unsigned displayed = 0; displayed < count; ++displayed) {
        const unsigned i=slots[displayed];
        u8* r = page == 1 ? row(1, i) : page == 2 ? row(2, i) : i == 0 ? row(3, 0) : row(4, i - 1);
        const char* key = reinterpret_cast<const char*>(page == 1 ? c.icons[0] + i * 32 : page == 2 ? c.icons[1] + i * 32 : i == 0 ? c.icons[2] : c.icons[3] + (i - 1) * 32);
        const int ox = page == 3 ? i == 0 ? 226 : 307 + (i - 1) * 50 : 108 + (i % 4) * 77;
        const int oy = page == 3 ? 133 : 132 + (i / 4) * 74;
        skill_row(w, r, key, i, ox, oy, 168 + displayed * 37);
    }
    if (page == 1) label_check(w, c.labels[Normal], 169, 467, state(36) != 1, 30, 278);
    if(page!=3){text(w,510,118,c.custom[show_skill_empty?HideEmpty:ShowEmpty],blue,11,0,220);point({506,114,228,23},0,0,14);}
    if (page == 3) { text(w, 169, 341, c.labels[Heal], blue); slider(w, 170, 368, state(108), 100, 56, 158, 135, 200); }
}
static void item_name(void* w, const char* name, unsigned quantity, int y) {
    text(w,218,y,name,ink,12,0,330);
    if(!painting)return;
    const int width=reinterpret_cast<int(__thiscall*)(void*,const char*,int,int,int,int,int)>(0x00A21C90)(w,name,0,c.font,font_size(12),0,0);
    number(w,218+minimum(width,330)+12,y,quantity,blue,"x ");
}
static void buffs(void* w) {
    unsigned slots[8];const unsigned count=select_slots(5,show_buff_empty,slots);
    for (unsigned displayed = 0; displayed < count; ++displayed) {
        const unsigned i=slots[displayed];
        auto r = row(5, i); const u32 id = at<u32>(r, 0);
        const int y = 168 + displayed * 37;
        item_icon(w, 176, y + 3, id);
        if(id)item_name(w,reinterpret_cast<const char*>(r+12),at<u32>(r,8)>>16,y);else text(w,218,y,c.labels[RegisterItem],muted);
        box(w, 657, y - 1, 55, 25); text(w, 664, y + 2, reinterpret_cast<const char*>(r + 36)); text(w, 721, y + 3, c.labels[Seconds]);
        point({168, y - 3, 405, 32}, 108 + (i % 4) * 77, 121 + (i / 4) * 74, 2);
        point({657, y - 1, 55, 25}, 108 + (i % 4) * 77, 157 + (i / 4) * 74);
        fill(w, 168, y + 34, 566, 1, rule);
    }
    text(w,510,118,c.custom[show_buff_empty?HideEmpty:ShowEmpty],blue,11,0,220);point({506,114,228,23},0,0,15);
    label_check(w, c.labels[ReturnTown], 169, 467, state(52) != 0, 30, 278);
}
static void potions(void* w) {
    if (state(12) != 1) { text(w, 170, 183, c.labels[StatusPotion], blue); return; }
    for (unsigned i = 0; i < 4; ++i) {
        auto r = row(6, i); const u32 id = at<u32>(r, 0); const int y = 178 + i * 73;
        const int old_x = i % 2 == 0 ? 21 : 247, old_y = i < 2 ? 89 : 200;
        item_icon(w, 176, y + 3, id);
        if(id)item_name(w,reinterpret_cast<const char*>(r+16),at<u16>(r,14),y);else text(w,218,y,c.labels[RegisterItem],muted);
        text(w, 218, y + 23, c.potion[i], muted, 11);
        point({168, y - 4, 405, 33}, old_x + 180, old_y + 70, 2);
        check(w, 711, y + 7, (at<u32>(r, 8) & 1) != 0); point({700, y, 30, 27}, old_x + 190, old_y + 5);
        slider(w, 390, y + 28, at<u16>(r, i < 2 ? 4 : 6), 100, old_x + 15, old_y + 72, 135,0,i>=2);
        fill(w, 168, y + 63, 566, 1, rule);
    }
}
static void movement(void* w) {
    for (unsigned i = 0; i < 4; ++i) {
        auto r = row(7, i); const u32 id = at<u32>(r, 0); const bool is_item = i % 2 == 0; const int y = 182 + i * 66;
        if (is_item) item_icon(w, 176, y, id); else icon(w, 176, y, id ? reinterpret_cast<const char*>(c.rows[8] + i * 32) : nullptr);
        if(id&&is_item)item_name(w,reinterpret_cast<const char*>(r+12),at<u16>(r,4),y);
        else {text(w,218,y,id?reinterpret_cast<const char*>(r+12):c.labels[is_item?RegisterItem:RegisterSkill],ink,12,0,340);if(id)number(w,578,y,at<u16>(r,4),blue,"Lv ");}
        text(w, 218, y + 22, c.labels[i < 2 ? Teleport : ReturnTown], muted, 11);
        const int old_x = i % 2 == 0 ? 156 : 302, old_y = i < 2 ? 125 : 220;
        point({168, y - 4, 405, 35}, old_x, old_y, 2);
        check(w, 711, y + 5, (at<u32>(r, 8) & 1) != 0); point({700, y, 30, 25}, old_x - 20, old_y + 8);
        fill(w, 168, y + 51, 566, 1, rule);
    }
}
static void loot(void* w) {
    if(state(16)!=2){
        text(w,170,190,c.custom[CollectCategories],blue,13,1,265);
        text(w,450,190,c.custom[InventoryFull],blue,13,1,282);
        const int old_x[]={38,147,244,365};
        for(int i=0;i<4;++i)label_check(w,c.categories[i],170,235+i*45,(state(68)&(1u<<i))!=0,old_x[i]+3,292,266);
        text(w,450,223,c.labels[Weight],muted,11);
        slider(w,450,249,state(128),90,132,155,205);
        label_check(w,c.custom[ReturnWeight],450,298,(state(132)&4)!=0,50,225,282,4,2);
        paragraph(w,472,323,c.labels[ReturnHint],258);
        check(w,450,378,(state(132)&8)!=0);paragraph(w,472,376,c.labels[Continue],258,ink,12,3);point({447,374,285,57},50,280,0,4,2);
        paragraph(w,472,436,c.labels[ContinueHint],258);
        fill(w,437,190,1,231,rule);return;
    }
    for (int i = 0; i < 2; ++i) {
        const int y = 190 + i * 49;
        label_check(w, c.labels[i == 0 ? Weapon : Armor], 170, y, (state(132) & (1u << i)) != 0, 60, 208 + i * 22, 300,4,1);
        box(w, 501, y - 5, 115, 25); text(w, 508, y - 2, c.choices[minimum(state(136 + i * 4), 5)],ink,12,0,90);bitmap(w,DropdownArrow,599,y+2);text(w, 623, y - 2, c.labels[OptionsSuffix]);
        point({501, y - 5, 115, 25}, 210, 208 + i * 22,0,4,1);
    }
    fill(w,168,278,566,1,rule);text(w,170,297,c.labels[Priority],blue,13,1);
    label_check(w,c.labels[FightFirst],170,335,state(44)==0,50,139);
    label_check(w,c.labels[LootFirst],170,384,state(44)==1,50,172);
    const unsigned popup = state(168); if (popup < 1 || popup > 2) return;
    const int top = popup == 1 ? 213 : 260, old_top = popup == 1 ? 218 : 120;
    box(w, 501, top, 115, 6 * 24 + 2);
    for (int i = 0; i < 6; ++i) { if (state(136 + (popup - 1) * 4) == static_cast<u32>(i)) fill(w, 502, top + 1 + i * 24, 113, 24, tint); text(w, 508, top + 4 + i * 24, c.choices[i]); point({502,top+1+i*24,113,24},210,old_top+i*17+3,0,4,1); }
}
static void layout(void* w, bool draw) {
    painting = draw; mapping_count = 0; scrollbar.maximum=0;
    nav(w);
    const unsigned tab = minimum(state(4), 6);
    text(w, 169, 116, c.custom[tab], blue, 13, 1,tab==2||tab==6?330:565);
    if(tab==0){text(w,169,145,c.custom[overview_advanced?Advanced:General],muted,11,0,300);text(w,510,145,c.custom[overview_advanced?General:Advanced],blue,11,0,222);point({506,140,228,25},0,0,13);}
    else if(tab!=2&&tab!=3&&tab!=4)text(w,169,141,c.subtitles[tab],muted,11,0,565);
    if (tab == 0) overview(w); else if (tab == 1) monsters(w); else if (tab == 2) skills(w); else if (tab == 3) potions(w); else if (tab == 4) loot(w); else if (tab == 5) movement(w); else buffs(w);
    // Footer buttons map to the unchanged, server-authoritative legacy handlers.
    point({17,487,60,24}, 12, 330); point({681,487,60,24},430,330);
    point({728,5,24,23},461,8);
}
static void dirty(void* w) { at<u32>(w,0x58)=1; }
static bool subpage(void* w,int x,int y) {
    if (y < 140 || y >= 163 || x < 168 || x >= 734) return false;
    const unsigned tab=state(4); if (tab < 2 || tab > 4) return false;
    const unsigned count=tab==2?3:2,index=minimum(static_cast<unsigned>((x-168)*count/566),count-1);
    state(tab==2?8:tab==3?12:16)=index+1; state(168)=0; dirty(w); return true;
}
extern "C" __declspec(dllexport) void __fastcall AutoHuntCustomDraw(void* w,void*) {
    if(c.abi!=2||!c.state) return;
    if(c.initializer) reinterpret_cast<void(__cdecl*)()>(c.initializer)();
    painting=true;
    reinterpret_cast<void(__thiscall*)(void*,u32)>(0x00A1CB30)(w,white);
    // Native GDI text does not retain per-pixel alpha. Match Item Description's
    // opaque text surface; alpha composition makes native glyphs disappear.
    if(void* surface=at<void*>(w,0x24))at<u8>(surface,0x28)=0;
    // Rounded white frame and the neutral Item Description header gradient.
    for(int y=0;y<520;++y){const int inset=y<5||y>=515?5:y<9||y>=511?2:0;fill(w,inset,y,760-inset*2,1,0xFF6389C1);fill(w,inset+1,y,758-inset*2,1,white);}
    for(int y=1;y<34;++y){const unsigned r=110+(154-110)*y/34,g=152+(186-152)*y/34,b=214+(232-214)*y/34;fill(w,y<6?5:1,y,y<6?750:758,1,0xFF000000|r<<16|g<<8|b);}
    text(w,17,9,c.labels[Title],0xFFFFFF,13,1);text(w,735,7,"x",0xFFFFFF,14,1);
    text(w,20,52,reinterpret_cast<const char*>(c.state+184),orange,15,1);
    text(w,20,80,c.subtitles[0],muted,11);fill(w,1,108,758,1,rule);
    layout(w,true);
    const unsigned tab=state(4);
    if(tab>=2&&tab<=4){const unsigned count=tab==2?3:2,page=state(tab==2?8:tab==3?12:16);for(unsigned i=0;i<count;++i){const int x=168+i*566/count,width=566/count-5;box(w,x,140,width,23,page==i+1?tint:white);const char* label=tab==2?c.labels[Attack+i]:tab==3?c.labels[i==0?Heal:Status]:c.custom[i==0?General:EquipmentFilters];text(w,x+7,144,label,blue,11,0,width-14);}}
    fill(w,1,482,758,1,rule);box(w,17,487,60,24);text(w,25,492,c.labels[Reset]);box(w,681,487,60,24);text(w,692,492,c.labels[Close]);
    if(state(112)){box(w,210,215,400,85,white,0xFF4C7BD6);text(w,226,238,c.labels[state(148)>=56?RejectItem:RejectSkill],red);}
}
static void legacy(void* w,u32 handler,const Mapping* m,int x,int y) {
    const u32 tab=state(4),skill=state(8),potion=state(12),looting=state(16),scroll=state(124);
    if(m){if(m->tab>=0)state(4)=m->tab;if(m->page>=0)state(state(4)==2?8:state(4)==3?12:16)=m->page;if(m->scroll>=0)state(124)=m->scroll;}
    reinterpret_cast<void(__thiscall*)(void*,int,int)>(handler)(w,x,y);
    // For ordinary mappings the stock handler may intentionally change a page.
    if(m&&(m->tab>=0||m->page>=0||m->scroll>=0)){state(4)=tab;state(8)=skill;state(12)=potion;state(16)=looting;state(124)=scroll;}
}
static void end_scroll(void* w) {
    if(dragging_scroll){
        void* manager=reinterpret_cast<void*>(0x0131F4E8);
        if(reinterpret_cast<void*(__thiscall*)(void*)>(0x00A32E00)(manager)==w)reinterpret_cast<void(__thiscall*)(void*)>(0x00A482E0)(manager);
        dragging_scroll=false;
    }
}
static void scroll_to(void* w,int y) {
    state(scrollbar.offset)=clamp(y-scroll_grab-scrollbar.top-3,0,scrollbar.travel)*scrollbar.maximum/maximum(1,scrollbar.travel);dirty(w);
}
extern "C" __declspec(dllexport) void __fastcall AutoHuntCustomDown(void* w,void*,int x,int y) {
    end_scroll(w);dragging_slider=false;suppress_up=false;hover_x=x;hover_y=y;
    layout(w,false);
    if(state(112)){state(112)=0;suppress_up=true;dirty(w);return;}
    if(x>=9&&x<137&&y>=125&&y<433){const unsigned slot=(y-125)/44;if(slot<7){state(4)=nav_order[slot];state(168)=0;state(116)=0;suppress_up=true;dirty(w);return;}}
    if(subpage(w,x,y)){suppress_up=true;return;}
    if(y>=0&&y<34&&x>=0&&x<728){reinterpret_cast<void(__thiscall*)(void*,int,int)>(0x00880AD0)(w,x,y);return;}
    int ox=-1,oy=-1;const Mapping* m=hit(x,y);
    if(m&&m->kind>=10){
        suppress_up=true;state(168)=0;
        if(m->kind==10){if(state(40)!=2)remembered_pickup=minimum(state(40),1);const unsigned next=state(40)==2?remembered_pickup:2;reinterpret_cast<void(__stdcall*)(u32,u32,u32)>(c.scalar_sender)(20,next,0);}
        else if(m->kind==11||m->kind==12){state(4)=2;state(8)=m->kind-10;}
        else if(m->kind==13)overview_advanced=!overview_advanced;
        else if(m->kind==14)show_skill_empty=!show_skill_empty;
        else if(m->kind==15)show_buff_empty=!show_buff_empty;
        dirty(w);return;
    }
    if(m&&m->kind==4){
        suppress_up=true;if(!scrollbar.maximum)return;
        dragging_scroll=true;scroll_grab=y>=scrollbar.thumb_top&&y<scrollbar.thumb_top+scrollbar.thumb_height?y-scrollbar.thumb_top:scrollbar.thumb_height/2;
        reinterpret_cast<void(__thiscall*)(void*,void*)>(0x00A4B750)(reinterpret_cast<void*>(0x0131F4E8),w);scroll_to(w,y);return;
    }
    dragging_slider=m&&m->kind==1;if(dragging_slider)drag_map=*m;if(m)translate(*m,x,y,ox,oy);
    legacy(w,c.down,m,ox,oy);
}
extern "C" __declspec(dllexport) void __fastcall AutoHuntCustomMove(void* w,void*,int x,int y) {
    hover_x=x;hover_y=y;dirty(w);
    if(dragging_scroll){scroll_to(w,y);return;}
    if(at<u8>(w,0x38)!=0xFF){reinterpret_cast<void(__thiscall*)(void*,int,int)>(0x00880CB0)(w,x,y);return;}
    if(!state(116))dragging_slider=false;
    layout(w,false);int ox=-1,oy=-1;const Mapping* m=dragging_slider?&drag_map:hit(x,y);
    if(m&&m->kind==2){reinterpret_cast<void(__thiscall*)(void*,int,int)>(0x00880CB0)(w,x,y);return;}
    if(m&&m->kind>=4){reinterpret_cast<void(__thiscall*)(void*,int,int)>(0x00880CB0)(w,x,y);return;}
    if(m)translate(*m,x,y,ox,oy);legacy(w,c.move,m,ox,oy);
    // The legacy handler computes tooltip anchors in its logical coordinates.
    // Publish the same percentage at the actual cursor after it updates state.
    if(m&&(m->kind==1||m->kind==3)){
        unsigned value=0;const unsigned tab=state(4);
        if(tab==2)value=state(108);else if(tab==4)value=state(128);else if(tab==3){const unsigned slot=(m->original.x>200?1:0)+(m->original.y>220?2:0);value=at<u16>(row(6,slot),slot<2?4:6);}
        char* tip=percentage_tip;unsigned n=0;char digits[10];unsigned d=0;do{digits[d++]=static_cast<char>('0'+value%10);value/=10;}while(value&&d<10);while(d)tip[n++]=digits[--d];tip[n++]='%';tip[n]=0;
        void* manager=*reinterpret_cast<void**>(0x0121333C);if(manager){int sx=x+10,sy=y-24;reinterpret_cast<void(__thiscall*)(void*,int*,int*)>(0x00A1EF70)(w,&sx,&sy);reinterpret_cast<void(__thiscall*)(void*,const char*,int,int,int,int,int)>(0x00A753D0)(manager,tip,sx,sy,-1,0,1);}
    }
}
extern "C" __declspec(dllexport) void __fastcall AutoHuntCustomUp(void* w,void*,int x,int y) {
    if(dragging_scroll){scroll_to(w,y);end_scroll(w);suppress_up=false;return;}
    if(suppress_up){suppress_up=false;return;}
    if(at<u8>(w,0x38)!=0xFF){dragging_slider=false;reinterpret_cast<void(__thiscall*)(void*,int,int)>(0x00880BB0)(w,x,y);return;}
    if(!state(116))dragging_slider=false;
    layout(w,false);int ox=-1,oy=-1;const Mapping* m=dragging_slider?&drag_map:hit(x,y);if(m)translate(*m,x,y,ox,oy);dragging_slider=false;
    if(m&&m->kind>=4)return;
    legacy(w,c.up,m,ox,oy);
}
extern "C" __declspec(dllexport) void __fastcall AutoHuntCustomWheel(void* w,void*,int direction) {
    if(state(4)==0&&!overview_advanced)return;
    reinterpret_cast<void(__thiscall*)(void*,int)>(c.wheel)(w,direction);
}
