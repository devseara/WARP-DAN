// Isolated, import-free VendingUI for 2025-07-16 Ragexe. Server-authoritative VNUI.
#include "wire.hpp"
typedef unsigned int u32;typedef unsigned short u16;typedef unsigned char u8;
#define EXPORT extern "C" __declspec(dllexport)
using namespace vending_ui_wire;
extern "C" void* __cdecl memcpy(void*,const void*,unsigned int);
extern "C" void* __cdecl memset(void*,int,unsigned int);
#pragma function(memcpy, memset)
extern "C" void* __cdecl memcpy(void* d,const void* s,unsigned int n){auto* out=static_cast<volatile u8*>(d);auto* in=static_cast<const volatile u8*>(s);while(n--)*out++=*in++;return d;}
extern "C" void* __cdecl memset(void* d,int c,unsigned int n){auto* out=static_cast<volatile u8*>(d);while(n--)*out++=static_cast<u8>(c);return d;}
struct Api {
    u32 version,vtable,ctor,send;
    void (__stdcall *text)(void*,const char*,int,int,int,u32);
    void (__stdcall *item)(void*,u32,int,int);
    void (__stdcall *describe)(u32);
    const char* (__stdcall *name)(u32,u32);
    void (__thiscall *png)(void*,int,int,void*,int);
    u32 keysIat,editVtable;void (__stdcall *caption)(void*,const char*,int,int,int,u32);const char* paths[31];
};
static_assert(sizeof(Api)==172,"Vending API with 31 assets");
EXPORT Api VendingApi={1};
EXPORT u32 VendingIconIdentified=1;
struct Choice {u32 row,quantity,price;};
struct State {
    void* window;void* editor;u32 active,pending,count,chosenCount,catalogScroll,sideScroll,cartScroll;
    int hover,pressed,mouseX,mouseY,dragging,editing;u32 right,epoch,rightEpoch,rightItem;
    Header header;Row rows[max_rows];History history[max_history];Choice chosen[16];char title[80],status[128];
    int scrollGrab;u32 confirming,currencyChoice;
    void* confirmWindow;int dragX,dragY;u32 offered[max_rows];
    void* amountWindow;void* amountEditor;u32 askingAmount,amountRow,amountEpoch,itemDragRow,itemDragEpoch;
    char amountError[96];
    char amountInput[16];
};
EXPORT State VendingState={};
// The visible quote and our own live store have independent lifetimes. Sales
// keep updating this cache while another vendor (or its confirmation) is open.
struct OwnerStore {
    u32 valid,browsing,owner,count,catalogScroll,sideScroll;
    Header header;Row rows[max_rows];History history[max_history];u32 offered[max_rows];
};
static OwnerStore ownerStore={};
struct ItemHit {int x,y,w,h;Row row;};
static ItemHit hits[64];static int hitCount;
static const ItemHit* itemHit(int x,int y){for(int i=hitCount-1;i>=0;--i)if(x>=hits[i].x && y>=hits[i].y && x<hits[i].x+hits[i].w && y<hits[i].y+hits[i].h)return hits+i;return 0;}
static void* textures[31];static bool escapeHeld;
static void* paintWindow;static int paintWidth=590,paintHeight=450;
template<typename T>T& at(void* p,int o){return *reinterpret_cast<T*>(static_cast<u8*>(p)+o);}
static int min(int a,int b){return a<b?a:b;}static int max(int a,int b){return a>b?a:b;}
static void copy(void* dst,const void* src,u32 size){auto* d=static_cast<u8*>(dst);auto* s=static_cast<const u8*>(src);for(u32 i=0;i<size;++i)d[i]=s[i];}
static int length(const char* s,int cap=127){int n=0;while(s && s[n] && n<cap)++n;return n;}
static void textCopy(char* dst,const char* src,int cap){int n=min(length(src,cap-1),cap-1);for(int i=0;i<n;++i)dst[i]=src[i];dst[n]=0;}
static void append(char* dst,const char* src){int n=length(dst);textCopy(dst+n,src,128-n);}
static void number(char* dst,u32 n,bool comma=true){char s[20];int k=0;do{if(comma && k && (k+1)%4==0)s[k++]=',';s[k++]=static_cast<char>('0'+n%10);n/=10;}while(n);for(int i=0;i<k/2;++i){char c=s[i];s[i]=s[k-i-1];s[k-i-1]=c;}s[k]=0;append(dst,s);}
static bool contains(int x,int y,int bx,int by,int w,int h){return x>=bx && y>=by && x<bx+w && y<by+h;}
// Native card interiors: one shared layout drives painting and hit testing.
struct ItemControls {int closeX,closeY,minusX,plusX,stepsY;};
static const ItemControls setupControls={154,5,128,148,28},buyControls={124,4,97,117,28};
static int controlsHit(u32 i,const ItemControls& b,int x,int y,int mouseX,int mouseY){
    if(contains(mouseX,mouseY,x+b.closeX,y+b.closeY,13,13))return 4000+i;
    if(contains(mouseX,mouseY,x+b.minusX,y+b.stepsY,16,16))return 6000+i*2;
    if(contains(mouseX,mouseY,x+b.plusX,y+b.stepsY,16,16))return 6001+i*2;return 0;
}
static bool key(int code){return VendingApi.keysIat && ((*reinterpret_cast<short (__stdcall **)(int)>(VendingApi.keysIat))(code)&0x8000)!=0;}
static void dirty(){if(VendingState.window)at<int>(VendingState.window,0x58)=1;if(VendingState.confirmWindow)at<int>(VendingState.confirmWindow,0x58)=1;if(VendingState.amountWindow)at<int>(VendingState.amountWindow,0x58)=1;}
static void status(const char* s){textCopy(VendingState.status,s,128);dirty();}
static const char* nativeString(void* obj,int offset){return at<u32>(obj,offset+20)<16?static_cast<const char*>(obj)+offset:at<const char*>(obj,offset);}
static const char* infoString(u32 id,int offset){void* mgr=*reinterpret_cast<void**>(0x159C088);if(!mgr)return 0;void* node=reinterpret_cast<void* (__thiscall *)(void*,const u32*)>(0xA7E780)(static_cast<u8*>(mgr)+8,&id);if(!node)return 0;void* s=static_cast<u8*>(node)+offset;u32 n=at<u32>(s,16);return n && n<512?nativeString(s,0):0;}
EXPORT const char* __stdcall VendingResource(u32 id){return infoString(id,VendingIconIdentified?0x58:0x1C);}
EXPORT const char* __stdcall VendingName(u32 id,u32 identified){return infoString(id,identified?0x40:4);}
static void name(char* out,const Row& r){out[0]=0;if(r.refine && r.identified){append(out,"+");number(out,r.refine,false);append(out," ");}const char* s=VendingApi.name(r.item,r.identified);if(s && *s)append(out,s);else{append(out,"Item #");number(out,r.item,false);}}
static bool send(const void* p,u32 len){void* t=reinterpret_cast<void* (__cdecl *)()>(VendingApi.ctor)();if(!t)return false;reinterpret_cast<void (__thiscall *)(void*,int,const void*)>(VendingApi.send)(t,len,p);return true;}
static void request(u16 action,u32 arg=0){Request r={request_id,sizeof(Request),magic,version,action,VendingState.header.nonce,arg,VendingState.header.owner,VendingState.header.shop,0};if(!send(&r,sizeof(r)))status("Unable to send. Reopen the store.");}

// Native edit focus stays private to this frame. The original input manager
// owns text/IME/paste/selection; formatting maps its selection by digit count.
static int digitCount(const char* s,int end){int n=0;for(int i=0;i<end && s[i];++i)if(s[i]>='0' && s[i]<='9')++n;return n;}
static int digitPosition(const char* s,int count){if(!count)return 0;for(int i=0;s[i];++i)if(s[i]>='0' && s[i]<='9' && !--count)return i+1;return length(s);}
EXPORT u32 __stdcall VendingFormat(const char* raw,char* formatted,u32 limit){u32 value=0;for(int i=0;raw[i] && i<127;++i)if(raw[i]>='0' && raw[i]<='9'){u32 d=raw[i]-'0';if(value>limit/10 || (value==limit/10 && d>limit%10)){value=limit;break;}value=value*10+d;}formatted[0]=0;if(*raw)number(formatted,value);return value;}
static void syncEdit(){
    auto& s=VendingState;if(!s.editor || !s.editing || at<void*>((void*)0x131F4E8,0x1A0)!=s.editor)return;
    void* input=*reinterpret_cast<void**>(0x159B80C);if(!input)return;
    const char* raw=nativeString(input,0x34);if(!raw)return;
    if(s.editing==-1){textCopy(s.title,raw,80);return;}
    u32 index=static_cast<u32>(s.editing-1);if(index>=s.chosenCount)return;
    char formatted[128];u32 value=VendingFormat(raw,formatted,s.header.max_price);s.chosen[index].price=value;
    bool same=length(raw)==length(formatted);for(int i=0;same && formatted[i];++i)if(raw[i]!=formatted[i])same=false;
    if(!same){
        int a=digitCount(raw,at<int>(input,0x50)),b=digitCount(raw,at<int>(input,0x54));
        // A6EA10 replaces the selection, then INSERTS at the caret. Select the
        // complete old value first; calling it with an empty selection duplicates
        // the formatted price on every draw. Keep the editor/IME owner unchanged.
        at<int>(input,0x50)=0;at<int>(input,0x54)=length(raw);
        reinterpret_cast<void (__thiscall *)(void*,const char*)>(0xA6EA10)(input,formatted);
        at<int>(input,0x50)=digitPosition(formatted,a);at<int>(input,0x54)=digitPosition(formatted,b);
    }
    dirty();
}
static void syncAmountInput(){
    auto& s=VendingState;if(!s.askingAmount || !s.amountEditor || at<void*>((void*)0x131F4E8,0x1A0)!=s.amountEditor)return;
    void* input=*reinterpret_cast<void**>(0x159B80C);if(!input)return;const char* raw=nativeString(input,0x34);bool same=length(raw,15)==length(s.amountInput,15);
    for(int i=0;same && i<15 && raw[i];++i)if(raw[i]!=s.amountInput[i])same=false;
    if(!same){textCopy(s.amountInput,raw,16);s.amountError[0]=0;dirty();}
}
EXPORT void __fastcall VendingEditDraw(void* edit,void*){if(edit==VendingState.editor)syncEdit();else if(edit==VendingState.amountEditor)syncAmountInput();reinterpret_cast<void (__thiscall *)(void*)>(0x824FC0)(edit);}
static void endEdit(){auto& s=VendingState;if(!s.editor)return;syncEdit();if(at<void*>((void*)0x131F4E8,0x1A0)==s.editor)reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B760)((void*)0x131F4E8,0);at<int>(s.editor,0x28)=0;s.editing=0;dirty();}
static void* makeEditor(void* parent){
    void* e=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0x11C);if(!e)return 0;
    reinterpret_cast<void* (__thiscall *)(void*)>(0x817DA0)(e);at<u32>(e,0)=VendingApi.editVtable;
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA1B780)(parent,e);at<int>(e,0x8C)=1;return e;
}
static void edit(int field,int x,int y,int width){
    auto& s=VendingState;endEdit();if(s.pending || s.header.mode!=Setup)return;
    void* e=s.editor;if(!e){e=makeEditor(s.window);if(!e)return;s.editor=e;}
    s.editing=field;at<int>(e,0x88)=field==-1?79:20;
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA1CB70)(e,width,17);at<int>(e,0x1C)=x;at<int>(e,0x20)=y;
    char value[128]={};if(field==-1)textCopy(value,s.title,80);else number(value,s.chosen[field-1].price);
    reinterpret_cast<void (__thiscall *)(void*,const char*)>(0x8303F0)(e,value);at<int>(e,0x28)=1;
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B760)((void*)0x131F4E8,e);at<int>(e,0x58)=1;dirty();
}
static void release(){auto& s=VendingState;void* w=s.dragging==8?s.amountWindow:s.dragging==4?s.confirmWindow:s.window;if(w && (s.dragging==1 || s.dragging==4 || s.dragging==8))reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880BB0)(w,0,0);s.dragging=0;s.pressed=0;void* capture=at<void*>((void*)0x131F4E8,0x19C);if(capture && (capture==s.window || capture==s.confirmWindow || capture==s.amountWindow))reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);}
static void closeConfirm(){auto& s=VendingState;if(s.dragging==4 || (s.confirmWindow && at<void*>((void*)0x131F4E8,0x19C)==s.confirmWindow))release();s.confirming=0;if(s.confirmWindow)at<int>(s.confirmWindow,0x28)=0;dirty();}
static void closeAmount(){auto& s=VendingState;if(s.dragging==8 || (s.amountWindow && at<void*>((void*)0x131F4E8,0x19C)==s.amountWindow))release();if(s.amountEditor){if(at<void*>((void*)0x131F4E8,0x1A0)==s.amountEditor)reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B760)((void*)0x131F4E8,0);at<int>(s.amountEditor,0x28)=0;}s.askingAmount=0;s.amountError[0]=0;s.hover=s.pressed=0;if(s.amountWindow)at<int>(s.amountWindow,0x28)=0;dirty();}
static void hide(){hitCount=0;endEdit();release();closeConfirm();closeAmount();VendingState.active=VendingState.pending=0;VendingState.right=0;++VendingState.epoch;if(VendingState.window)at<int>(VendingState.window,0x28)=0;}
static void rememberOwnerScroll(){auto& s=VendingState;if(ownerStore.valid && s.active && s.header.mode==Owner){ownerStore.catalogScroll=s.catalogScroll;ownerStore.sideScroll=s.sideScroll;}}
static void showSnapshot(){
    auto& s=VendingState;s.active=1;s.pending=s.confirming=s.currencyChoice=s.chosenCount=0;
    s.hover=s.pressed=s.right=0;s.mouseX=s.mouseY=-1;++s.epoch;
    textCopy(s.title,s.header.mode==Setup?"My Store":s.header.title,80);status(s.header.message);escapeHeld=key(27);
    at<int>(s.window,0x28)=1;dirty();reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA39130)((void*)0x131F4E8,s.window);
}
static void restoreOwner(){
    auto& s=VendingState;if(!ownerStore.valid || !s.window)return;
    hide();copy(&s.header,&ownerStore.header,sizeof(Header));s.count=ownerStore.count;
    copy(s.rows,ownerStore.rows,s.count*sizeof(Row));copy(s.offered,ownerStore.offered,s.count*sizeof(u32));
    copy(s.history,ownerStore.history,s.header.history_count*sizeof(History));
    s.catalogScroll=ownerStore.catalogScroll;s.sideScroll=ownerStore.sideScroll;s.cartScroll=0;showSnapshot();
}
static void finishBrowsing(){hide();ownerStore.browsing=0;restoreOwner();}
static void closeOwnStore(){u16 p=0x12E;if(send(&p,2)){ownerStore.valid=ownerStore.browsing=0;hide();}}
// Invoked only by the native walk-request branch and shop-open request branch.
// Keep the owner immobile even between remote quotes, without shared flags.
EXPORT int __stdcall VendingBlocksWalk(){auto& s=VendingState;return ownerStore.valid || (s.active && s.window && at<int>(s.window,0x28)!=0);}
EXPORT void __stdcall VendingSwitchShop(){rememberOwnerScroll();ownerStore.browsing=1;if(VendingState.active && VendingState.header.mode==Buyer)hide();if(!VendingState.active)restoreOwner();}
static void* makeWindow(int id,int width,int height,int x,int y){
    void* w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4);if(!w)return 0;
    reinterpret_cast<void (__thiscall *)(void*,int)>(0x86B950)(w,0);at<u32>(w,0)=VendingApi.vtable;
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,width,height);at<u8>(at<void*>(w,0x24),0x28)=1;at<int>(w,0x2C)=id;at<int>(w,0x1C)=x;at<int>(w,0x20)=y;
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA2D240)((void*)0x131F4E8,w);return w;
}
static bool assets(){
    static const int widths[]={590,590,410,175,175,175,144,144,161,161,161,161,161,161,44,44,44,66,66,66,66,66,66,44,44,44,170,44,44,44,44};
    static const int heights[]={450,450,450,70,70,70,52,80,18,18,18,18,18,18,18,18,18,18,18,18,18,18,18,18,18,18,65,18,18,18,18};
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return false;
    for(int i=0;i<31;++i){const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(VendingApi.paths[i]);if(!path)return false;void* t=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);if(!t || at<int>(t,0x114)!=widths[i] || at<int>(t,0x118)!=heights[i] || !at<void*>(t,0x11C))return false;textures[i]=t;}return true;
}
EXPORT int __stdcall VendingReceive(const u8* packet){
    auto* h=reinterpret_cast<const Header*>(packet);if(!packet || h->opcode!=snapshot_id || h->length<8 || h->magic!=magic)return 0;
    if(h->length<sizeof(Header) || h->version!=version || h->mode>Error || h->count>max_rows || h->history_count>max_history || h->max_slots>16 || h->max_price>0x7FFFFFFF || h->length!=sizeof(Header)+h->count*sizeof(Row)+h->history_count*sizeof(History))return 1;
    auto& s=VendingState;if(h->mode==Closed){
        // Our own store can close while a remote quote remains open. Its late
        // acknowledgement must not dismiss that unrelated quote/confirmation.
        if(ownerStore.owner && h->owner==ownerStore.owner){ownerStore.valid=0;if(ownerStore.browsing && (!s.active || s.header.mode==Buyer))return 1;}
        ownerStore.browsing=0;hide();return 1;
    }
    if(h->mode==Error){if(ownerStore.browsing && (!s.active || s.header.mode==Owner))finishBrowsing();s.pending=0;release();closeConfirm();closeAmount();char msg[97];copy(msg,h->message,96);msg[96]=0;status(msg);return 1;}
    auto* rows=reinterpret_cast<const Row*>(packet+sizeof(Header));
    for(u32 i=0;i<h->count;++i){if(h->mode!=Currency && (!rows[i].item || rows[i].index<2 || !rows[i].amount || rows[i].amount>30000 || rows[i].price>h->max_price))return 1;for(u32 j=0;j<i;++j)if(rows[j].index==rows[i].index)return 1;}
    if(!assets())return 1;void* w=s.window;
    if(!w){w=makeWindow(0x3EB,590,450,30,40);if(!w)return 1;s.window=w;}
    auto* history=packet+sizeof(Header)+h->count*sizeof(Row);
    if(h->mode==Owner){
        rememberOwnerScroll();bool preserve=ownerStore.valid && ownerStore.header.shop==h->shop && ownerStore.owner==h->owner;
        // Retain original cart-index slots, including sales received while browsing.
        if(!preserve){ownerStore.count=ownerStore.catalogScroll=ownerStore.sideScroll=0;}
        for(u32 i=0;i<ownerStore.count;++i)ownerStore.rows[i].amount=0;
        for(u32 i=0;i<h->count;++i){u32 j=0;while(j<ownerStore.count && ownerStore.rows[j].index!=rows[i].index)++j;if(j<ownerStore.count)ownerStore.rows[j]=rows[i];else if(ownerStore.count<max_rows){ownerStore.offered[j]=rows[i].amount;ownerStore.rows[j]=rows[i];++ownerStore.count;}}
        copy(&ownerStore.header,h,sizeof(Header));ownerStore.header.title[79]=ownerStore.header.owner_name[23]=ownerStore.header.currency_name[47]=ownerStore.header.message[95]=0;
        copy(ownerStore.history,history,h->history_count*sizeof(History));for(u32 i=0;i<h->history_count;++i)ownerStore.history[i].buyer[23]=0;
        ownerStore.owner=h->owner;ownerStore.valid=1;if(!ownerStore.browsing || (s.active && s.header.mode==Owner))restoreOwner();return 1;
    }
    rememberOwnerScroll();if(h->mode==Buyer)ownerStore.browsing=1;else memset(&ownerStore,0,sizeof(ownerStore));
    hide();copy(s.rows,rows,h->count*sizeof(Row));s.count=h->count;for(u32 i=0;i<s.count;++i)s.offered[i]=s.rows[i].amount;
    copy(&s.header,h,sizeof(Header));s.header.title[79]=s.header.owner_name[23]=s.header.currency_name[47]=s.header.message[95]=0;
    copy(s.history,history,h->history_count*sizeof(History));for(u32 i=0;i<h->history_count;++i)s.history[i].buyer[23]=0;
    s.catalogScroll=s.sideScroll=s.cartScroll=0;showSnapshot();return 1;
}
static bool total(u32& sum){sum=0;auto& s=VendingState;for(u32 i=0;i<s.chosenCount;++i){auto c=s.chosen[i];if(c.row>=s.count || !c.quantity || c.quantity>s.rows[c.row].amount || c.quantity>30000 || (c.price && c.quantity>0x7FFFFFFFu/c.price))return false;u32 value=c.price*c.quantity;if(value>0x7FFFFFFFu-sum)return false;sum+=value;}return true;}
static bool ready(){u32 sum;auto& s=VendingState;return s.active && !s.pending && s.chosenCount && total(sum) && (s.header.mode==Setup?length(s.title,79)>0:sum<=s.header.balance);}
static void showConfirm(){
    auto& s=VendingState;if(!ready())return;endEdit();release();void* w=s.confirmWindow;
    if(!w){w=makeWindow(0x3EC,320,151,at<int>(s.window,0x1C)+135,at<int>(s.window,0x20)+145);if(!w){status("Unable to open confirmation.");return;}s.confirmWindow=w;}
    s.confirming=1;s.right=0;hitCount=0;s.hover=s.pressed=0;at<int>(w,0x28)=1;dirty();
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA39130)((void*)0x131F4E8,w);
}
static int confirmHit(int x,int y){if(!VendingState.confirming)return 0;if(contains(x,y,180,124,44,18))return ready()?5:0;if(contains(x,y,234,124,44,18))return 6;return 0;}
static void submit(){
    auto& s=VendingState;endEdit();if(!ready())return;u8 data[85+16*8]={};u32 len;
    if(s.header.mode==Setup){*reinterpret_cast<u16*>(data)=0x1B2;copy(data+4,s.title,80);data[84]=1;len=85;for(u32 i=0;i<s.chosenCount;++i){auto c=s.chosen[i];*reinterpret_cast<u16*>(data+len)=static_cast<u16>(s.rows[c.row].index);*reinterpret_cast<u16*>(data+len+2)=static_cast<u16>(c.quantity);*reinterpret_cast<u32*>(data+len+4)=c.price;len+=8;}}
    else{*reinterpret_cast<u16*>(data)=0x801;*reinterpret_cast<u32*>(data+4)=s.header.owner;*reinterpret_cast<u32*>(data+8)=s.header.shop;len=12;for(u32 i=0;i<s.chosenCount;++i){auto c=s.chosen[i];*reinterpret_cast<u16*>(data+len)=static_cast<u16>(c.quantity);*reinterpret_cast<u16*>(data+len+2)=static_cast<u16>(s.rows[c.row].index);len+=4;}}
    *reinterpret_cast<u16*>(data+2)=static_cast<u16>(len);s.pending=1;if(!send(data,len)){s.pending=0;status("Unable to send. Reopen the store.");}else if(s.header.mode==Buyer)finishBrowsing();else status("Opening store...");dirty();
}
static void reveal(u32 i){auto& s=VendingState;int y=s.header.mode==Setup?(i/2)*70:i*52,h=s.header.mode==Setup?70:52,view=s.header.mode==Setup?280:208;u32& offset=s.header.mode==Setup?s.catalogScroll:s.cartScroll;if(y<static_cast<int>(offset))offset=y;else if(y+h>static_cast<int>(offset)+view)offset=y+h-view;}
static u32 remaining(u32 row);
static bool canAdd(u32 row){auto& s=VendingState;if(!s.active || s.pending || (s.header.mode!=Setup && s.header.mode!=Buyer) || row>=s.count || !remaining(row))return false;for(u32 i=0;i<s.chosenCount;++i)if(s.chosen[i].row==row)return true;return s.chosenCount<(s.header.mode==Setup?s.header.max_slots:16u);}
static void addQuantity(u32 row,u32 amount){auto& s=VendingState;if(!amount || !canAdd(row) || amount>remaining(row))return;for(u32 i=0;i<s.chosenCount;++i)if(s.chosen[i].row==row){s.chosen[i].quantity+=amount;reveal(i);dirty();return;}s.chosen[s.chosenCount++]={row,amount,s.header.mode==Setup?0:s.rows[row].price};reveal(s.chosenCount-1);dirty();}
static const char* amountText(){syncAmountInput();return VendingState.amountInput;}
static void acceptAmount(){
    auto& s=VendingState;if(!s.askingAmount)return;if(s.amountEpoch!=s.epoch || !canAdd(s.amountRow)){closeAmount();return;}
    u32 n=0;const char* raw=amountText();bool valid=*raw!=0;
    for(int i=0;valid && raw[i];++i){if(i>=5 || raw[i]<'0' || raw[i]>'9'){valid=false;break;}n=n*10+raw[i]-'0';}
    u32 available=remaining(s.amountRow);if(!valid || !n || n>available){char b[128]="Enter an amount from 1 to ";number(b,available);append(b,".");textCopy(s.amountError,b,96);dirty();return;}
    u32 row=s.amountRow;closeAmount();addQuantity(row,n);
}
// Native UIManager::Enter (A2E270) sends event 0 to the focused edit.
// UIEditCtrl::OnMessage (82C4E0) otherwise clears its global input at
// 82CFC7 before the next cursor poll. Consume only this private amount edit's
// submit event, validate the live buffer, and keep invalid input editable.
EXPORT int __fastcall VendingEditEvent(void* edit,void*,void* sender,u32 event,u32 a,u32 b,u32 c,u32 d){
    auto& s=VendingState;
    if(edit==s.amountEditor && event==0){
        if(s.active && s.askingAmount && at<void*>((void*)0x131F4E8,0x1A0)==edit)acceptAmount();
        return 0;
    }
    return reinterpret_cast<int (__thiscall *)(void*,void*,u32,u32,u32,u32,u32)>(0x82C4E0)(edit,sender,event,a,b,c,d);
}
static void dropItem(u32 row){
    auto& s=VendingState;if(!canAdd(row))return;u32 available=remaining(row);if(available==1){addQuantity(row,1);return;}
    endEdit();void* w=s.amountWindow;if(!w){w=makeWindow(0x3ED,280,173,at<int>(s.window,0x1C)+155,at<int>(s.window,0x20)+150);if(!w){status("Unable to open amount dialog.");return;}s.amountWindow=w;}
    void* e=s.amountEditor;if(!e){e=makeEditor(w);if(!e){at<int>(w,0x28)=0;status("Unable to open amount input.");return;}s.amountEditor=e;}
    s.askingAmount=1;s.amountRow=row;s.amountEpoch=s.epoch;s.amountError[0]=0;textCopy(s.amountInput,"1",16);s.hover=s.pressed=s.right=0;hitCount=0;
    at<int>(e,0x88)=10;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA1CB70)(e,98,21);at<int>(e,0x1C)=63;at<int>(e,0x20)=79;
    reinterpret_cast<void (__thiscall *)(void*,const char*)>(0x8303F0)(e,"1");at<int>(e,0x28)=1;at<int>(w,0x28)=1;
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA39130)((void*)0x131F4E8,w);reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B760)((void*)0x131F4E8,e);
    void* input=*reinterpret_cast<void**>(0x159B80C);if(input){at<int>(input,0x50)=0;at<int>(input,0x54)=1;}dirty();
}
static int amountHit(int x,int y){if(!VendingState.askingAmount)return 0;if(contains(x,y,172,146,44,18))return 7;if(contains(x,y,224,146,44,18))return 8;return 0;}
static bool itemDropTarget(int x,int y){return VendingState.header.mode==Setup?contains(x,y,29,133,353,280):VendingState.header.mode==Buyer && contains(x,y,421,179,144,208);}
static void remove(u32 i){auto& s=VendingState;if(i>=s.chosenCount)return;endEdit();for(u32 j=i;j+1<s.chosenCount;++j)s.chosen[j]=s.chosen[j+1];--s.chosenCount;dirty();}
static void quantity(u32 i,bool up){auto& s=VendingState;if(i>=s.chosenCount)return;endEdit();auto& c=s.chosen[i];u32 step=key(17)?100:key(16)?10:1;if(up)c.quantity=min(s.rows[c.row].amount,c.quantity+step);else if(c.quantity<=step)remove(i);else c.quantity-=step;dirty();}

struct Clip {int x,y,w,h;};
static Clip clip={0,0,590,450};
static Clip catalogPane={29,133,353,280};
static Clip sidePane(){return VendingState.header.mode==Setup?Clip{432,178,134,224}:VendingState.header.mode==Owner?Clip{421,174,150,240}:Clip{421,179,150,208};}
static bool intersect(int x,int y,int w,int h){return x<clip.x+clip.w && x+w>clip.x && y<clip.y+clip.h && y+h>clip.y;}
static u32* pixels(){return at<u32*>(at<void*>(paintWindow,0x24),0x18);}
static void rect(int x,int y,int w,int h,u32 color){auto* p=pixels();for(int yy=max(clip.y,y);yy<min(clip.y+clip.h,y+h);++yy)for(int xx=max(clip.x,x);xx<min(clip.x+clip.w,x+w);++xx)p[yy*paintWidth+xx]=color;}
static void panel(int x,int y,int w,int h,u32 fill=0xFFF4F8FF,u32 border=0xFFBDCEEB){rect(x,y,w,h,border);rect(x+1,y+1,w-2,h-2,fill);}
// Private clipping on the actual native surface, following BarterUI's staging
// technique. Native PNG/text/item helpers remain unchanged for every other UI.
static u32 stageSave[250*80],stageDraw[250*80];
static void primitive(int op,u32 id,const char* value,int x,int y,int w,int h,u32 color=0){
    if(!intersect(x,y,w,h))return;
    bool staged=x<clip.x || y<clip.y || x+w>clip.x+clip.w || y+h>clip.y+clip.h;
    if(staged && (w>250 || h>80))return;
    auto* p=pixels();
    if(staged){
        for(int yy=0;yy<h;++yy)for(int xx=0;xx<w;++xx){stageSave[yy*w+xx]=p[yy*paintWidth+xx];stageDraw[yy*w+xx]=x+xx>=0 && x+xx<paintWidth && y+yy>=0 && y+yy<paintHeight?p[(y+yy)*paintWidth+x+xx]:0;}
        for(int yy=0;yy<h;++yy)for(int xx=0;xx<w;++xx)p[yy*paintWidth+xx]=stageDraw[yy*w+xx];
    }
    int dx=staged?0:x,dy=staged?0:y;
    if(op==0)VendingApi.text(paintWindow,value,dx,dy,w,color);
    else if(op==1)VendingApi.png(paintWindow,dx,dy,textures[id],0);
    else VendingApi.item(paintWindow,id,dx,dy);
    if(staged){
        for(int yy=0;yy<h;++yy)for(int xx=0;xx<w;++xx){stageDraw[yy*w+xx]=p[yy*paintWidth+xx];p[yy*paintWidth+xx]=stageSave[yy*w+xx];}
        for(int yy=max(0,clip.y-y);yy<min(h,clip.y+clip.h-y);++yy)for(int xx=max(0,clip.x-x);xx<min(w,clip.x+clip.w-x);++xx)p[(y+yy)*paintWidth+x+xx]=stageDraw[yy*w+xx];
    }
}
static void text(const char* value,int x,int y,int width,u32 color=0x947D65){primitive(0,0,value,x,y,width,16,color);}
static void rightText(const char* value,int x,int y,int width){int used=reinterpret_cast<int (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA21C90)(paintWindow,value,length(value),0,11,0,0);used=min(width,used);text(value,x+width-used,y,used);}
static void image(int i,int x,int y){primitive(1,i,0,x,y,at<int>(textures[i],0x114),at<int>(textures[i],0x118));}
static void fadedButton(int i,int x,int y){image(i,x,y);auto* p=pixels();for(int yy=y;yy<y+18;++yy)for(int xx=x;xx<x+44;++xx){u32 c=p[yy*paintWidth+xx],out=0xFF000000;for(int shift=0;shift<24;shift+=8)out|=((((c>>shift)&255)*45+((0xFFF5FFFF>>shift)&255)*55)/100)<<shift;p[yy*paintWidth+xx]=out;}}
static void mini(int hit,const char* label,int x,int y,int w=16,int h=16){panel(x,y,w,h,VendingState.pressed==hit?0xFFB2CCF0:VendingState.hover==hit?0xFFD7E6FA:0xFFF4F8FF);text(label,x+4,y+1,w-6);}
static void drawControls(u32 i,const ItemControls& b,int x,int y){mini(4000+i,"x",x+b.closeX,y+b.closeY,13,13);mini(6000+i*2,"-",x+b.minusX,y+b.stepsY);mini(6001+i*2,"+",x+b.plusX,y+b.stepsY);}
static int buttonState(int id){return VendingState.hover==id?(VendingState.pressed==id?2:1):0;}
static void icon(const Row& r,int x,int y,bool small=false){
    int size=small?24:32;if(!r.item || !intersect(x,y,size,size))return;
    int hx=max(x,clip.x),hy=max(y,clip.y);if(hitCount<64)hits[hitCount++]={hx,hy,min(x+size,clip.x+clip.w)-hx,min(y+size,clip.y+clip.h)-hy,r};
    VendingIconIdentified=r.identified;
    if(!small){primitive(2,r.item,0,x,y,32,32);return;}
    // The bag's art has a 28px icon well. Center a 24px rendering inside it.
    auto* p=pixels();for(int yy=0;yy<32;++yy)for(int xx=0;xx<32;++xx){stageSave[yy*32+xx]=p[yy*paintWidth+xx];p[yy*paintWidth+xx]=0;}
    VendingApi.item(paintWindow,r.item,0,0);
    for(int yy=0;yy<32;++yy)for(int xx=0;xx<32;++xx){stageDraw[yy*32+xx]=p[yy*paintWidth+xx];p[yy*paintWidth+xx]=stageSave[yy*32+xx];}
    for(int yy=max(0,clip.y-y);yy<min(24,clip.y+clip.h-y);++yy)for(int xx=max(0,clip.x-x);xx<min(24,clip.x+clip.w-x);++xx){u32 c=stageDraw[(yy*32/24)*32+xx*32/24];if(c)p[(y+yy)*paintWidth+x+xx]=c;}
}
static void price(u32 value,int color,int x,int y,bool show=true){image(8+color%6,x,y);if(show){char b[128]={};number(b,value);rightText(b,x+23,y+2,132);}}
static u32 remaining(u32 row){auto& s=VendingState;u32 amount=s.rows[row].amount;for(u32 i=0;i<s.chosenCount;++i)if(s.chosen[i].row==row)amount-=s.chosen[i].quantity;return amount;}
static u32& scrollOffset(bool side){auto& s=VendingState;return side?(s.header.mode==Buyer?s.cartScroll:s.sideScroll):s.catalogScroll;}
static int scrollMax(bool side){auto& s=VendingState;if(s.header.mode==Currency)return side?0:max(0,s.count*40-240);if(!side)return max(0,((s.header.mode==Setup?s.chosenCount:s.count)+1)/2*70-280);int height=s.header.mode==Setup?(s.count+3)/4*32:s.header.mode==Owner?s.header.history_count*80:s.chosenCount*52;return max(0,height-sidePane().h);}
static void clampScroll(){catalogPane=VendingState.header.mode==Currency?Clip{181,102,216,240}:Clip{29,133,353,280};for(int i=0;i<2;++i)scrollOffset(i!=0)=min(scrollOffset(i!=0),scrollMax(i!=0));}
static void scrollBy(bool side,int delta){endEdit();u32& offset=scrollOffset(side);offset=min(max(0,static_cast<int>(offset)+delta),scrollMax(side));hitCount=0;VendingState.right=0;dirty();}
struct Scroll {int x,y,h,max,position,thumb,thumbY;};
static Scroll bar(bool side){auto p=side?sidePane():catalogPane;Scroll b={side?574:VendingState.header.mode==Currency?402:388,p.y,p.h,scrollMax(side),static_cast<int>(scrollOffset(side)),0,0};int track=b.h-22;b.thumb=max(22,track*p.h/(p.h+b.max));b.thumbY=b.y+11+(b.max?b.position*(track-b.thumb)/b.max:0);return b;}
static void scrollbar(bool side){auto b=bar(side);if(!b.max)return;panel(b.x,b.y,10,b.h,0xFFE3EAFA,0xFFBAC9E7);panel(b.x,b.thumbY,10,b.thumb,0xFF9EB6DF,0xFF849ECE);for(int i=0;i<2;++i){int y=i?b.y+b.h-11:b.y;panel(b.x,y,10,11,0xFFD7E5FA,0xFFA9BFDF);for(int row=0;row<3;++row)rect(b.x+4-row,y+(i?6-row:3+row),1+row*2,1,0xFF6685BE);}}
EXPORT int __stdcall VendingHit(int x,int y){
    auto& s=VendingState;if(!s.active || s.askingAmount)return 0;clampScroll();
    if(s.header.mode==Currency){
        if(contains(x,y,353,354,44,18) || contains(x,y,395,78,15,16))return 2;if(s.pending)return 0;
        if(contains(x,y,299,354,44,18) && s.currencyChoice<s.count)return 30;
        auto b=bar(false);if(b.max && contains(x,y,b.x,b.y,10,b.h))return 10+(y<b.y+11?2:y>=b.y+b.h-11?3:0);
        if(contains(x,y,181,102,216,240)){u32 row=(y-102+s.catalogScroll)/40;if(row<s.count)return 1000+row;}return 0;
    }
    if(s.confirming)return 0;
    if(contains(x,y,342,426,44,18) && s.header.mode!=Buyer && s.header.mode!=Owner)return 2;if(contains(x,y,495,427,44,18) && s.header.mode==Buyer)return 2;
    if(s.pending)return 0;if(s.header.mode==Owner && contains(x,y,464,427,66,18))return 3;if((s.header.mode==Setup && contains(x,y,270,426,66,18)) || (s.header.mode==Buyer && contains(x,y,443,427,44,18)))return ready()?3:0;
    if(s.header.mode==Setup && contains(x,y,99,5,213,35))return 4;
    for(int i=0;i<2;++i){auto b=bar(i!=0);if(b.max && contains(x,y,b.x,b.y,10,b.h))return (i?20:10)+(y<b.y+11?2:y>=b.y+b.h-11?3:0);}
    if(contains(x,y,catalogPane.x,catalogPane.y,catalogPane.w,catalogPane.h)){
        u32 count=s.header.mode==Setup?s.chosenCount:s.count;
        for(u32 i=0;i<count;++i){int xx=29+(i%2)*178,yy=133+(i/2)*70-s.catalogScroll;
            if(s.header.mode==Setup){int hit=controlsHit(i,setupControls,xx,yy,x,y);if(hit)return hit;if(contains(x,y,xx+5,yy+49,160,18))return 5000+i;}
            else if(s.header.mode!=Owner && contains(x,y,xx,yy,175,70))return 1000+i;
        }
    }
    auto side=sidePane();if(!contains(x,y,side.x,side.y,side.w,side.h))return 0;
    if(s.header.mode==Setup){for(u32 i=0;i<s.count;++i)if(remaining(i) && contains(x,y,432+(i%4)*34,178+(i/4)*32-s.sideScroll,32,32))return 1000+i;}
    else if(s.header.mode==Buyer)for(u32 i=0;i<s.chosenCount;++i){int yy=179+i*52-s.cartScroll,hit=controlsHit(i,buyControls,421,yy,x,y);if(hit)return hit;}return 0;
}
static void drawConfirm(void* w){
    if(!VendingState.confirming || !assets())return;paintWindow=w;paintWidth=320;paintHeight=151;clip={0,0,320,151};
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    panel(0,0,320,151,0xFFFFFFFF,0xFF94A9C7);panel(1,1,318,19,0xFFDCEBFA,0xFFB2C6DF);text("Confirm Deal",15,3,280,0x604A32);
    text("Below is the total cost:",11,29,292,0x393939);u32 sum=0;char b[128]={};if(total(sum))number(b,sum);append(b," ");append(b,VendingState.header.currency_name);text(b,11,51,294,0x393939);text("Press OK to confirm.",11,76,292,0x393939);
    rect(1,112,318,38,0xFFF4F8FC);image(ready()?28+buttonState(5):27,180,124);image(23+buttonState(6),234,124);
    auto* paint=pixels();for(int i=0;i<paintWidth*paintHeight;++i)if(paint[i])paint[i]|=0xFF000000;
}
static void drawAmount(void* w){
    auto& s=VendingState;if(!s.askingAmount || s.amountEpoch!=s.epoch || s.amountRow>=s.count)return;
    paintWindow=w;paintWidth=280;paintHeight=173;clip={0,0,280,173};reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    panel(0,0,280,173,0xFFFFFFFF,0xFF94A9C7);panel(1,1,278,20,0xFFDCEBFA,0xFFB2C6DF);text(s.header.mode==Setup?"Amount to vend":"Amount to buy",7,3,266,0x604A32);
    const auto& r=s.rows[s.amountRow];VendingIconIdentified=r.identified;primitive(2,r.item,0,14,31,32,32);
    char b[128];name(b,r);text(b,54,32,213,0x393939);b[0]=0;append(b,"Available: ");number(b,remaining(s.amountRow));text(b,54,51,213);
    text("Amount",12,82,45,0x393939);panel(62,78,100,23);text(amountText(),67,81,90,0x393939);
    if(s.amountError[0])text(s.amountError,12,109,256,0x4141BD);
    rect(1,135,278,37,0xFFF4F8FC);image(28+buttonState(7),172,146);image(23+buttonState(8),224,146);
    auto* paint=pixels();for(int i=0;i<paintWidth*paintHeight;++i)if(paint[i])paint[i]|=0xFF000000;
}
EXPORT void __fastcall VendingDraw(void* w,void*){
    if(w==VendingState.amountWindow){drawAmount(w);return;}
    if(w==VendingState.confirmWindow){drawConfirm(w);return;}
    paintWindow=w;paintWidth=590;paintHeight=450;
    auto& s=VendingState;if(w!=s.window || !s.active || at<int>(w,0x14)!=590 || at<int>(w,0x18)!=450 || !assets())return;
    hitCount=0;clampScroll();syncEdit();clip={0,0,590,450};reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    if(s.header.mode==Currency){
        panel(175,75,240,302,0xFFFFFFFF,0xFF94A9C7);panel(176,76,238,20,0xFFDCEBFA,0xFFB2C6DF);text("List",186,79,180,0x604A32);mini(2,"x",395,78,15);clip=catalogPane;
        for(u32 i=0;i<s.count;++i){int y=102+i*40-s.catalogScroll;if(!intersect(181,y,216,40))continue;bool selected=i==s.currencyChoice;if(selected)rect(181,y,216,40,0xFF729AE8);const auto& r=s.rows[i];const char* label=r.index==0?"Zeny":r.index==cash?"Cash Points":VendingApi.name(r.item,1);icon(r,184,y+4);text(label?label:"Item currency",224,y+13,169,selected?0xFFFFFF:0x604A32);}
        clip={0,0,590,450};scrollbar(false);rect(176,348,238,28,0xFFF4F8FC);image(28+buttonState(30),299,354);image(23+buttonState(2),353,354);
        auto* paint=pixels();for(int i=0;i<590*450;++i)if(paint[i])paint[i]|=0xFF000000;return;
    }
    image(s.header.mode==Buyer?1:0,0,0);if(s.header.mode==Owner){image(2,0,0);rect(409,153,177,267,0xFFF5FFFF);VendingApi.caption(w,"Sales History",409,156,173,0x88634D);}
    char b[128];if(s.editing!=-1)VendingApi.caption(w,s.header.mode==Currency?"Choose Store Currency":s.title,99,17,213,0x88634D);
    if(s.header.mode!=Currency){b[0]=0;append(b,"Currency: ");append(b,s.header.currency_name);text(b,29,117,232);}
    clip=catalogPane;
    u32 count=s.header.mode==Setup?s.chosenCount:s.count;
    for(u32 i=0;i<count;++i){int x=29+(i%2)*178,y=133+(i/2)*70-s.catalogScroll;bool setup=s.header.mode==Setup;if(!intersect(x,y,175,70))continue;
        Row r=setup?s.rows[s.chosen[i].row]:s.rows[i];image(3,x,y);
        if(s.header.mode==Currency){const char* label=r.index==0?"Zeny":r.index==cash?"Cash Points":VendingApi.name(r.item,1);text(label?label:"Item currency",x+45,y+11,124);icon(r,x+5,y+7);b[0]=0;append(b,"Balance: ");number(b,r.amount);text(b,x+7,y+50,156);continue;}
        bool sold=s.header.mode==Owner && !r.amount;if(sold)r.amount=s.offered[i];
        if(setup){r.amount=s.chosen[i].quantity;r.price=s.chosen[i].price;}
        icon(r,x+5,y+7);name(b,r);text(b,x+45,y+10,setup?104:121);b[0]=0;append(b,"x");number(b,r.amount);text(b,x+45,y+28,setup?72:120);
        price(r.price,1+i%5,x+5,y+49,!setup || s.editing!=static_cast<int>(i+1));
        if(setup)drawControls(i,setupControls,x,y);
        else if(sold)image(26,x,y);
    }
    clip=sidePane();
    if(s.header.mode==Setup){
        for(u32 i=0;i<s.count;++i){u32 qty=remaining(i);int x=432+(i%4)*34,y=178+(i/4)*32-s.sideScroll;if(!qty || !intersect(x,y,32,32))continue;Row r=s.rows[i];r.amount=qty;icon(r,x,y-2);b[0]=0;number(b,qty);text(b,x+12,y+18,22);}
    }else if(s.header.mode==Owner){
        for(u32 i=0;i<static_cast<u32>(max(3,s.header.history_count));++i){int y=174+i*80-s.sideScroll;if(!intersect(425,y,144,80))continue;image(7,425,y);if(i>=s.header.history_count)continue;const auto& h=s.history[i];Row r={};r.item=h.item;r.identified=1;r.amount=h.amount;icon(r,431,y+6,true);b[0]=0;number(b,h.total);if(!s.header.currency)append(b," z");text(b,470,y+14,92);text(h.buyer,434,y+39,132);b[0]=0;append(b,"x");number(b,h.amount);append(b," sold");text(b,434,y+56,132);}
    }else if(s.header.mode==Buyer){
        for(u32 i=0;i<static_cast<u32>(max(4,s.chosenCount));++i){int y=179+i*52-s.cartScroll;if(!intersect(421,y,144,52))continue;if(i>=s.chosenCount)continue;image(6,421,y);auto c=s.chosen[i];Row r=s.rows[c.row];r.amount=c.quantity;icon(r,427,y+6,true);name(b,r);text(b,460,y+7,80);drawControls(i,buyControls,421,y);b[0]=0;append(b,"x");number(b,c.quantity);text(b,460,y+30,53);}
    }
    clip={0,0,590,450};scrollbar(false);if(s.header.mode!=Currency)scrollbar(true);
    if(s.header.mode==Setup){image(17+buttonState(3),270,426);image(23+buttonState(2),342,426);}
    else if(s.header.mode==Owner)image(20+buttonState(3),464,427);
    else if(s.header.mode==Buyer){u32 sum=0;b[0]=0;if(total(sum))number(b,sum);else append(b,"Too large");rightText(b,475,395,81);if(ready())image(14+buttonState(3),443,427);else fadedButton(14,443,427);image(23+buttonState(2),495,427);}
    else if(s.header.mode==Currency){panel(412,148,176,301,0xFFF4FFFF);text("Select a currency",428,163,146);text("Prices are per item.",428,193,145);text("One currency per store.",428,211,145);image(23+buttonState(2),342,426);}
    if(s.header.mode==Setup){b[0]=0;number(b,*reinterpret_cast<u32*>(0x15FB2D4));append(b," / ");number(b,*reinterpret_cast<u32*>(0x15FB2D8));text(b,418,433,70);b[0]=0;number(b,*reinterpret_cast<u32*>(0x15FB2DC));append(b," / ");number(b,*reinterpret_cast<u32*>(0x15FB2E0));rightText(b,490,433,90);}
    rect(26,427,230,19,0xFFF4FFFF);b[0]=0;append(b,s.header.mode==Buyer?"Store Owner: ":"Sales tax: ");if(s.header.mode==Buyer)append(b,s.header.owner_name);else{number(b,s.header.tax/100,false);append(b,".");if(s.header.tax%100<10)append(b,"0");number(b,s.header.tax%100,false);append(b,"%");}text(b,28,431,225);
    if(s.status[0]){panel(29,91,356,21,0xFFFFFFDE);text(s.status,34,94,345,0x393939);}
    if(!s.confirming && !s.askingAmount && s.dragging!=6 && s.dragging!=7)if(const auto* hit=itemHit(s.mouseX,s.mouseY)){int x=min(s.mouseX+14,335),y=s.mouseY>380?s.mouseY-57:s.mouseY+18;panel(x,y,250,53,0xFFFFFFDE);name(b,hit->row);text(b,x+5,y+4,240,0x292929);b[0]=0;append(b,"Quantity: ");number(b,hit->row.amount);text(b,x+5,y+20,240,0x292929);b[0]=0;append(b,"Each: ");number(b,hit->row.price);append(b," ");append(b,s.header.currency_name);text(b,x+5,y+36,240,0x292929);}
    if(s.dragging==7 && s.itemDragEpoch==s.epoch && s.itemDragRow<s.count){
        if(itemDropTarget(s.mouseX,s.mouseY)){int x=s.header.mode==Setup?29:421,y=s.header.mode==Setup?133:179,wid=s.header.mode==Setup?353:144,h=s.header.mode==Setup?280:208;rect(x,y,wid,2,0xFF6E98D1);rect(x,y+h-2,wid,2,0xFF6E98D1);rect(x,y,2,h,0xFF6E98D1);rect(x+wid-2,y,2,h,0xFF6E98D1);}
        const auto& r=s.rows[s.itemDragRow];VendingIconIdentified=r.identified;primitive(2,r.item,0,min(558,max(0,s.mouseX-16)),min(418,max(0,s.mouseY-16)),32,32);
    }
    auto* paint=pixels();for(int i=0;i<590*450;++i)if(paint[i])paint[i]|=0xFF000000;
}
static void dragScroll(int y){auto& s=VendingState;bool side=s.dragging==3;auto b=bar(side);int travel=b.h-22-b.thumb;if(travel>0)scrollOffset(side)=min(max(0,y-b.y-11-s.scrollGrab),travel)*b.max/travel;hitCount=0;s.right=0;dirty();}
static bool titleHit(int x,int y){auto& s=VendingState;if(s.header.mode==Currency)return contains(x,y,175,75,240,21);return contains(x,y,0,0,410,117) || contains(x,y,405,148,185,26);}
EXPORT void __fastcall VendingDown(void* w,void*,int x,int y){
    auto& s=VendingState;if(!s.active || (w!=s.window && w!=s.confirmWindow && w!=s.amountWindow))return;
    void* modal=s.askingAmount?s.amountWindow:s.confirming?s.confirmWindow:0;if(modal && w!=modal){reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA39130)((void*)0x131F4E8,modal);return;}
    endEdit();release();s.dragX=s.mouseX=x;s.dragY=s.mouseY=y;s.hover=s.pressed=w==s.amountWindow?amountHit(x,y):w==s.confirmWindow?confirmHit(x,y):VendingHit(x,y);
    if(s.pressed)reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);
    if(s.pressed==10 || s.pressed==20){auto b=bar(s.pressed==20);s.dragging=s.pressed==20?3:2;s.scrollGrab=y>=b.thumbY && y<b.thumbY+b.thumb?y-b.thumbY:b.thumb/2;dragScroll(y);}
    else if(s.pressed==4)s.dragging=5; // click edits the sign; a drag moves the store.
    else if(s.pressed>=1000 && s.pressed<1000+static_cast<int>(s.count) && (s.header.mode==Setup || s.header.mode==Buyer)){s.dragging=6;s.itemDragRow=s.pressed-1000;s.itemDragEpoch=s.epoch;}
    else if(!s.pressed && (w==s.amountWindow || w==s.confirmWindow?y>=0 && y<20:titleHit(x,y))){s.dragging=w==s.amountWindow?8:w==s.confirmWindow?4:1;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880AD0)(w,x,y);}dirty();
}
EXPORT void __fastcall VendingUp(void* w,void*,int x,int y){
    auto& s=VendingState;if(!s.active || (w!=s.window && w!=s.confirmWindow && w!=s.amountWindow) || (s.askingAmount && w!=s.amountWindow) || (s.confirming && w!=s.confirmWindow))return;
    int hit=w==s.amountWindow?amountHit(x,y):w==s.confirmWindow?confirmHit(x,y):VendingHit(x,y),pressed=s.pressed,drag=s.dragging;u32 row=s.itemDragRow,epoch=s.itemDragEpoch;bool captured=at<void*>((void*)0x131F4E8,0x19C)==w;release();
    if(drag==6 || drag==7){if(drag==7 && captured && epoch==s.epoch && itemDropTarget(x,y))dropItem(row);dirty();return;}
    if((drag && drag!=5) || !hit || hit!=pressed){dirty();return;}
    if(hit==1 || hit==2){if(s.header.mode==Owner){closeOwnStore();return;}if(s.header.mode==Buyer){finishBrowsing();return;}if(s.header.mode==Setup || s.header.mode==Currency)request(Cancel);hide();return;}
    if(hit==3){if(s.header.mode==Owner)closeOwnStore();else if(s.header.mode==Buyer)showConfirm();else submit();}
    else if(hit==5){closeConfirm();submit();}
    else if(hit==6)closeConfirm();
    else if(hit==7)acceptAmount();
    else if(hit==8)closeAmount();
    else if(hit==30 && s.header.mode==Currency && s.currencyChoice<s.count){s.pending=1;request(SelectCurrency,s.rows[s.currencyChoice].index);}
    else if(hit==4)edit(-1,103,15,205);
    else if(hit>=6000)quantity((hit-6000)/2,(hit&1)!=0);
    else if(hit>=5000){u32 i=hit-5000;int editY=184+(i/2)*70-s.catalogScroll;if(editY<133 || editY+17>413){s.catalogScroll=(i/2)*70;clampScroll();editY=184+(i/2)*70-s.catalogScroll;}edit(i+1,57+(i%2)*178,editY,132);}
    else if(hit>=4000)remove(hit-4000);
    else if(hit>=1000 && s.header.mode==Currency){s.currencyChoice=hit-1000;dirty();}
    else if(hit==12 || hit==13 || hit==22 || hit==23)scrollBy(hit>=20,(hit%10==2?-1:1)*(hit>=20?32:70));clampScroll();dirty();
}
EXPORT void __fastcall VendingMove(void* w,void*,int x,int y){auto& s=VendingState;if(s.dragging==2 || s.dragging==3){dragScroll(y);return;}if((s.askingAmount && w!=s.amountWindow) || (s.confirming && w!=s.confirmWindow))return;
    if(s.dragging==6 || s.dragging==7){if(s.itemDragEpoch!=s.epoch){release();return;}if(x-s.dragX>4 || s.dragX-x>4 || y-s.dragY>4 || s.dragY-y>4)s.dragging=7;s.mouseX=x;s.mouseY=y;s.hover=0;dirty();return;}
    int hit=w==s.amountWindow?amountHit(x,y):w==s.confirmWindow?confirmHit(x,y):VendingHit(x,y);if(hit!=s.hover || x!=s.mouseX || y!=s.mouseY){s.hover=hit;s.mouseX=x;s.mouseY=y;dirty();}}
EXPORT void __fastcall VendingDrag(void* w,void*,int x,int y){
    auto& s=VendingState;if(s.dragging==2 || s.dragging==3)dragScroll(y);
    else if(s.dragging==1 || s.dragging==4 || s.dragging==8)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880E00)(w,x,y);
    else if(s.dragging==5 && (x-s.dragX>3 || s.dragX-x>3 || y-s.dragY>3 || s.dragY-y>3)){s.dragging=1;s.pressed=0;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880AD0)(w,s.dragX,s.dragY);reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880E00)(w,x,y);}
    else VendingMove(w,0,x,y);
}
EXPORT void __fastcall VendingCursor(void* w,void*,int x,int y){
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA23470)(w,x,y);VendingMove(w,0,x,y);
    auto& s=VendingState;bool esc=key(27);if(esc && !escapeHeld && s.active){
        // Esc dismisses a visited quote; an active own store remains available.
        // Only Close Store ends vending, which the server requires before walking.
        if(s.askingAmount)closeAmount();else if(s.dragging==6 || s.dragging==7)release();else if(s.confirming)closeConfirm();else if(s.header.mode==Buyer)finishBrowsing();
        else if(s.header.mode!=Owner){if(s.header.mode==Setup || s.header.mode==Currency)request(Cancel);hide();}
    }
    escapeHeld=esc;void* mode=*reinterpret_cast<void**>(0x121333C);if(mode)reinterpret_cast<void (__thiscall *)(void*,int)>(0xA764A0)(mode,s.active && (s.hover || s.dragging==7)?2:0);
}
EXPORT void __fastcall VendingWheel(void*,void*,int delta){auto& s=VendingState;if(!s.active || s.pending || s.confirming || s.askingAmount || s.dragging==6 || s.dragging==7 || !delta)return;if(s.mouseX>=412){auto p=sidePane();if(contains(s.mouseX,s.mouseY,p.x,p.y,174,p.h))scrollBy(true,delta>0?-32:32);}else if(contains(s.mouseX,s.mouseY,catalogPane.x,catalogPane.y,catalogPane.w+17,catalogPane.h))scrollBy(false,delta>0?-70:70);}
EXPORT void* __fastcall VendingDestroy(void* w,void*,int flags){if(w==VendingState.amountWindow){closeAmount();VendingState.amountWindow=VendingState.amountEditor=0;return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);}if(w==VendingState.confirmWindow){closeConfirm();VendingState.confirmWindow=0;return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);}hide();memset(&ownerStore,0,sizeof(ownerStore));VendingState.window=VendingState.editor=0;for(int i=0;i<31;++i)textures[i]=0;return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);}

// Reconstruct the same CItem fields as stock 0B3D at D0A2B4..D0A3CA.
// The item-info window copies the instance synchronously before its destruction.
EXPORT void __stdcall VendingDescribe(const Row* row){
    if(!row || !row->item)return;u8 item[0xF8];
    reinterpret_cast<void* (__thiscall *)(void*)>(0x6A1B20)(item);
    at<u32>(item,0)=row->type;at<u32>(item,4)=row->index;at<u32>(item,0x10)=row->amount;
    at<u32>(item,0x14)=at<u32>(item,0x18)=row->price;at<u8>(item,0x5C)=row->identified;at<u32>(item,0x60)=row->refine;
    reinterpret_cast<void (__thiscall *)(void*,u32)>(0x6A6570)(item,row->item);
    copy(item+0x1C,row->cards,16);at<u16>(item,0x88)=row->grade;
    u32 count=0;for(int i=0;i<5;++i)if(*reinterpret_cast<const u16*>(row->options+i*5)){copy(item+0x9C+count*5,row->options+i*5,5);++count;}
    at<u32>(item,0x98)=count;
    void* wnd=reinterpret_cast<void* (__thiscall *)(void*,int)>(0xA39340)((void*)0x131F4E8,12);
    if(wnd){auto table=at<void**>(wnd,0);reinterpret_cast<void (__thiscall *)(void*,int,int,void*,int,int,int)>(table[37])(wnd,0,24,item,0,0,0);}
    reinterpret_cast<void (__thiscall *)(void*)>(0x5A4300)(item);
}
EXPORT void __fastcall VendingRightDown(void*,void*,int x,int y){auto& s=VendingState;s.right=0;if(!s.active || s.pending || s.confirming || s.askingAmount || at<void*>((void*)0x131F4E8,0x19C))return;if(const auto* h=itemHit(x,y)){s.right=1;s.rightEpoch=s.epoch;s.rightItem=h->row.index;}}
EXPORT void __fastcall VendingRightUp(void*,void*,int x,int y){auto& s=VendingState;const auto* h=itemHit(x,y);bool show=s.active && s.right && s.rightEpoch==s.epoch && h && h->row.index==s.rightItem;s.right=0;if(show)VendingDescribe(&h->row);}
