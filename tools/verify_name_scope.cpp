#include <cstdio>
#include <cassert>
#include <cstring>
#include <cstddef>
#include <map>
#include <map/packets.hpp>
struct PacketRow { int size; const char* handler; };
static std::map<int, PacketRow> rows;
#define packetdb_addpacket(cmd, length, func, ...) rows[(cmd)] = {int(length), #func}
static void populate() {
#include <map/clif_packetdb.hpp>
#include <map/clif_shuffle.hpp>
}
static_assert(CHARACTER_NAME_LENGTH == 128);
static_assert(GUILD_NAME_LENGTH == 128);
static_assert(PARTY_NAME_LENGTH == 128);
static_assert(MOB_NAME_LENGTH == 128);
static_assert(NPC_DISPLAY_NAME_LENGTH == 128);
static_assert(PET_NAME_LENGTH == 128);
static_assert(HOMUNCULUS_NAME_LENGTH == 128);
static_assert(MERCENARY_NAME_LENGTH == 128);
static_assert(ELEMENTAL_NAME_LENGTH == 128);
static_assert(CLIENT_SERVICE_NAME_LENGTH == 24);
static_assert(SERVER_LABEL_LENGTH == 24 && AUCTION_SEARCH_TEXT_LENGTH == 24);
static_assert(sizeof(PACKET_ZC_ACK_CHANGE_GUILD_POSITIONINFO_sub) == 40);
static_assert(sizeof(PACKET_ZC_POSITION_ID_NAME_INFO) == 564);
static_assert(BATTLEGROUND_NAME_LENGTH == 24);
static_assert(CLAN_NAME_LENGTH == 24);
static_assert(GUILD_POSITION_NAME_LENGTH == 24);
static_assert(ENTITY_TITLE_LENGTH == 24);
static_assert(NPC_TITLE_LENGTH == 128);
static_assert(STORAGE_NAME_LENGTH == 24);
static_assert(CASTLE_NAME_LENGTH == 24);
static_assert(SCRIPT_LABEL_LENGTH == 24);
static_assert(SCRIPT_TOKEN_LENGTH == 24);
static_assert(NPC_NAME_LENGTH == 50 && EVENT_NAME_LENGTH == 77);
static_assert(sizeof(s_storage_table::name) == 24);
static_assert(sizeof(guild_position::name) == 24);
static_assert(sizeof(clan::name) == 24 && sizeof(clan::master) == 24);
static_assert(sizeof(PACKET_CZ_DYNAMICNPC_CREATE_REQUEST) == 26);
static_assert(sizeof(PACKET_CZ_REQ_EXPEL_GROUP_MEMBER) == 134);
static_assert(sizeof(PACKET_CZ_MACRO_USER_REPORT_REQ) == 241);
static_assert(offsetof(PACKET_CZ_MACRO_USER_REPORT_REQ, ReportType) == 138);
static_assert(offsetof(PACKET_CZ_MACRO_USER_REPORT_REQ, ReportMessage) == 140);
static_assert(sizeof(PACKET_ZC_MACRO_USER_REPORT_ACK) == 138);
static_assert(offsetof(PACKET_ZC_MACRO_USER_REPORT_ACK, Status) == 134);
static_assert(sizeof(PACKET_ZC_CLANINFO) == 74);
static_assert(sizeof(packet_bgqueue_register) == 28);
static_assert(sizeof(packet_bgqueue_ack) == 27);
static_assert(sizeof(packet_bgqueue_update_info) == 30);
static_assert(sizeof(packet_bgqueue_revoke_req) == 26);
static_assert(sizeof(packet_bgqueue_battlebegins) == 50);
static_assert(sizeof(packet_bgqueue_battlebegin_ack) == 51);

int main() {
    populate();
    const int contracts[][2] = {{0x0a16,26},{0x0103,134},{0x0be2,241},{0x0be3,138},
        {0x08d7,28},{0x08d8,27},{0x08d9,30},{0x08da,26},{0x08db,27},
        {0x08dc,26},{0x08dd,27},{0x08de,27},{0x08df,50},{0x08e0,51},{0x08e1,51}};
    for (const auto& c : contracts) {
        if (rows.at(c[0]).size != c[1]) {
            std::fprintf(stderr,"FAIL %04x got %d expected %d\n",c[0],rows.at(c[0]).size,c[1]);
            return 1;
        }
    }
    std::fprintf(stderr,"PASS scoped names: compiled structures and %zu effective packet contracts\n",sizeof(contracts)/sizeof(contracts[0]));
    for (const auto& row : rows) std::printf("%04x\t%d\t%s\n", row.first, row.second.size, row.second.handler);
}
