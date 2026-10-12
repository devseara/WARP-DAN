#include <cstdio>
#include <map>
#include <map/packets.hpp>
struct PacketRow { int size; const char* handler; };
static std::map<int, PacketRow> rows;
#define packetdb_addpacket(cmd, length, func, ...) rows[(cmd)] = {int(length), #func}
static void populate() {
#include <map/clif_packetdb.hpp>
#include <map/clif_shuffle.hpp>
}
int main() {
    populate();
    for (const auto& row : rows) std::printf("%04x\t%d\t%s\n", row.first, row.second.size, row.second.handler);
}
