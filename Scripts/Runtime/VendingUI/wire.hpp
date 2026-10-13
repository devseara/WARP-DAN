// VendingUI v1. Currency zero is Zeny; UINT32_MAX is Cash Points.
#ifndef VENDING_UI_WIRE_HPP
#define VENDING_UI_WIRE_HPP
typedef unsigned int uint32_t;
typedef unsigned short uint16_t;
typedef unsigned char uint8_t;
namespace vending_ui_wire {
constexpr uint32_t magic=0x49554E56;
constexpr uint32_t cash=0xFFFFFFFFu;
constexpr uint16_t version=1, snapshot_id=0x0BF3, request_id=0x0BF8;
constexpr unsigned max_rows=200, max_history=16;
enum Mode : uint16_t { Closed, Currency, Setup, Owner, Buyer, Error };
enum Action : uint16_t { SelectCurrency=1, Cancel, Refresh };
#pragma pack(push,1)
struct Request {uint16_t opcode,length;uint32_t magic;uint16_t version,action;uint32_t nonce,arg,owner,shop,reserved;};
struct Row {
    uint32_t item,index,amount,price;
    uint8_t identified,refine,grade,type;
    uint32_t cards[4];
    uint8_t options[25];
    uint8_t pad[3];
};
struct History {uint32_t item,amount,total,time;char buyer[24];};
struct Header {
    uint16_t opcode,length;uint32_t magic;uint16_t version,mode;
    uint32_t nonce,owner,shop,currency,balance,max_price;
    uint16_t max_slots,count,history_count,tax;
    char title[80],owner_name[24],currency_name[48],message[96];
};
#pragma pack(pop)
static_assert(sizeof(Request)==32 && sizeof(Row)==64 && sizeof(History)==40 && sizeof(Header)==292,"VendingUI v1 sizes");
}
#endif
