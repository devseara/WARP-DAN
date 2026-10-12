/* Shared IDUI v1 contract. Copied byte-for-byte into Banquet src/common.
 * Native client payload is freestanding x86; this header requires no CRT.
 * Values are display snapshots, never executable scripts or client authority.
 */
#ifndef BOH_ITEM_DESCRIPTION_WIRE_HPP
#define BOH_ITEM_DESCRIPTION_WIRE_HPP
namespace item_description_wire {
using u8 = unsigned char;
using u16 = unsigned short;
using i16 = short;
using u32 = unsigned int;
using i32 = int;
using u64 = unsigned long long;
constexpr u32 magic = 0x49554449; // IDUI
constexpr u16 version = 1, request_packet = 0x0bf8, response_packet = 0x0bef;
constexpr u16 inspect = 1, snapshot = 2, compare = 3;
constexpr u16 catalog = 0, inventory = 1;
constexpr u32 ok = 0, invalid = 1, stale = 2, unavailable = 3, throttled = 4;
constexpr unsigned row_limit = 64, card_limit = 4, option_limit = 5;
enum Section : u16 { core = 1, attributes, native_effects, refine, grade,
    enchantments, random_options, cards, card_sets, requirements, restrictions,
    comparison, section_end };
enum Kind : u16 { value = 0, effect = 1, component = 2, note = 3 };
enum RowFlag : u16 { active = 1, unmet = 2, unknown = 4, empty = 8 };
enum SnapshotFlag : u32 { truncated = 1, has_legacy = 2, identified = 4, equipped = 8 };
#pragma pack(push, 1)
struct Option { i16 id, value; u8 param; };
struct Request {
    u16 packet_type, packet_length;
    u32 magic;
    u16 version, message;
    u32 request_id, item_id, client_index;
    u16 scope, refine, grade;
    u8 identified, reserved0;
    u32 cards[card_limit];
    Option options[option_limit];
    u8 option_count;
    u16 reserved1;
    u64 known_fingerprint;
    u32 reserved2[3];
};
struct Row {
    u16 section, kind;
    u32 item_id;
    u16 flags, slot;
    i32 numeric_value;
    char label[48], text[128];
};
struct Snapshot {
    u16 packet_type, packet_length;
    u32 magic;
    u16 version, message;
    u32 request_id, revision, result, item_id, client_index;
    u16 scope, refine, grade, row_count;
    u16 card_count, enchant_count, option_count, slot_count;
    u32 flags;
    u64 fingerprint;
    u32 reserved;
    char binding[32], type_label[32];
    Row rows[row_limit];
};
#pragma pack(pop)
static_assert(sizeof(Option) == 5 && sizeof(Request) == 96, "IDUI request ABI");
static_assert(sizeof(Row) == 192 && sizeof(Snapshot) == 12416, "IDUI snapshot ABI");
template<class T> inline void zero(T& value) {
    auto p = reinterpret_cast<u8*>(&value);
    for (unsigned i = 0; i < sizeof(T); ++i) p[i] = 0;
}
inline bool request_valid(const Request& r) {
    if (r.packet_type != request_packet || r.packet_length != sizeof(Request) ||
        r.magic != magic || r.version != version || !r.request_id || !r.item_id ||
        (r.message != inspect && r.message != compare) || r.scope > inventory ||
        r.option_count > option_limit || r.identified > 1 || r.refine > 255 ||
        r.grade > 255 || r.reserved0 || r.reserved1 ||
        r.reserved2[0] || r.reserved2[1] || r.reserved2[2]) return false;
    if (r.scope == catalog && (r.client_index || r.refine || r.grade ||
        r.option_count || r.known_fingerprint || r.message == compare)) return false;
    if (r.scope == inventory && (r.client_index < 2 || r.client_index > 65535)) return false;
    for (unsigned i = 0; i < card_limit; ++i) if (r.scope == catalog && r.cards[i]) return false;
    for (unsigned i = 0; i < option_limit; ++i)
        if ((r.scope == catalog || i >= r.option_count) &&
            (r.options[i].id || r.options[i].value || r.options[i].param)) return false;
    return true;
}
inline bool terminated(const char* text, unsigned capacity) {
    for (unsigned i = 0; i < capacity; ++i) if (!text[i]) return true;
    return false;
}
inline bool snapshot_valid(const Snapshot& s, const Request& r) {
    if (s.packet_type != response_packet || s.packet_length != sizeof(Snapshot) ||
        s.magic != magic || s.version != version || s.message != snapshot ||
        s.request_id != r.request_id || s.item_id != r.item_id ||
        s.client_index != r.client_index || s.scope != r.scope || s.result > throttled ||
        !s.revision || s.reserved || s.row_count > row_limit ||
        s.card_count > card_limit || s.enchant_count > card_limit ||
        s.option_count > option_limit || s.slot_count > card_limit ||
        (s.flags & ~(truncated | has_legacy | identified | equipped)) ||
        !terminated(s.binding, sizeof(s.binding)) || !terminated(s.type_label, sizeof(s.type_label))) return false;
    if (s.result != ok) return s.row_count == 0;
    if (s.scope == inventory && (s.refine != r.refine || s.grade != r.grade)) return false;
    for (unsigned i = 0; i < s.row_count; ++i) {
        const auto& row = s.rows[i];
        if (row.section < core || row.section >= section_end || row.kind > note ||
            (row.flags & ~(active | unmet | unknown | empty)) || row.slot > option_limit ||
            !terminated(row.label, sizeof(row.label)) || !terminated(row.text, sizeof(row.text))) return false;
        if (row.kind == component && !row.item_id && !(row.flags & empty)) return false;
    }
    return true;
}
} // namespace item_description_wire
#endif
