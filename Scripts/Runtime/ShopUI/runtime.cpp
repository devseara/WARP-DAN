// Isolated 2025-07-16 NPC Buy/Sell UI. No inventory writes or result hooks.
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#define EXPORT extern "C" __declspec(dllexport)
#pragma pack(push,1)
struct BuyOffer { u32 id,price,discount; u8 type; u16 view; u32 location; };
struct SellOffer { u16 index; u32 price,overcharge; };
#pragma pack(pop)
static_assert(sizeof(BuyOffer)==19 && sizeof(SellOffer)==10,"2025 native shop packets");
struct Api {
    u32 version,vtable,ctor,send;
    void (__stdcall *text)(void*,const char*,int,int,int,u32);
    void (__stdcall *item)(void*,u32,int,int);
    void (__stdcall *describe)(u32);
    const char* (__stdcall *name)(u32,u32);
    void (__thiscall *png)(void*,int,int,void*,int);
    u32 keysIat;
    const char* paths[21];
};
static_assert(sizeof(Api)==124,"ShopUI API v1");
EXPORT Api ShopApi={1};
EXPORT u32 ShopIconIdentified=1;
struct Offer { u32 id,stock,index,price,basePrice,refine,identified,fingerprint; };
struct Choice { u32 recipe,quantity; };
struct State {
    void* window;u32 active,mode,count,catalogScroll,chosen,cartScroll,cartCount,pending;
    int hover,pressed,dragging,mouseX,mouseY,right;u32 rightId,epoch,rightEpoch,sentAt;
    Offer offers[4096];Choice cart[100];char status[128];int scrollGrab;
    u32 showAmounts;
};
EXPORT State ShopState={};
struct Hit {int x,y,w,h;u32 id,amount,refine,index,price,identified,fingerprint;};
static Hit itemHits[80];static int itemHitCount;
static void* textures[21];static bool escapeHeld;
template<typename T>T& at(void* p,int o){return *reinterpret_cast<T*>(static_cast<u8*>(p)+o);}
static void append(char* d,const char* s){int n=0;while(d[n] && n<126)++n;for(int i=0;s && s[i] && n<126;++i)d[n++]=s[i];d[n]=0;}
static void number(char* d,u32 n,bool comma=false){char tmp[20];int k=0;do{if(comma && k && (k+1)%4==0)tmp[k++]=',';tmp[k++]=static_cast<char>('0'+n%10);n/=10;}while(n);for(int i=0;i<k/2;++i){char c=tmp[i];tmp[i]=tmp[k-i-1];tmp[k-i-1]=c;}tmp[k]=0;append(d,tmp);}
static void status(const char* s){ShopState.status[0]=0;append(ShopState.status,s);}
static void dirty(){if(ShopState.window)at<int>(ShopState.window,0x58)=1;}
static bool key(int code){return ShopApi.keysIat && ((*reinterpret_cast<short (__stdcall **)(int)>(ShopApi.keysIat))(code)&0x8000)!=0;}
static bool contains(int x,int y,int bx,int by,int w,int h){return x>=bx && y>=by && x<bx+w && y<by+h;}
static bool selling(){return ShopState.mode==0xC7;}
// Look up the exact inventory slot, never aggregate equal ItemIds. Same list and
// inline CItem layout as native CSession::GetItemByIndex (D5AA40).
EXPORT void* __stdcall ShopInventory(u32 index){
    void* session=reinterpret_cast<void*>(0x15FA3C0);u32 count=at<u32>(session,0x16F4);
    void* head=at<void*>(session,0x16F0);if(!head || count>10000)return 0;
    void* node=at<void*>(head,0);
    for(u32 i=0;i<count && node && node!=head;++i,node=at<void*>(node,0))if(at<u32>(node,12)==index)return static_cast<u8*>(node)+8;
    return 0;
}
static u32 itemId(void* item){
    u32 length=at<u32>(item,0x3C),n=0;if(!length || length>10)return 0;
    auto* s=at<u32>(item,0x40)<16?reinterpret_cast<const char*>(static_cast<u8*>(item)+0x2C):at<const char*>(item,0x2C);
    if(!s)return 0;for(u32 i=0;i<length;++i){if(s[i]<'0' || s[i]>'9' || n>(0xFFFFFFFFu-static_cast<u32>(s[i]-'0'))/10)return 0;n=n*10+s[i]-'0';}return n;
}
static u32 fingerprint(void* item){
    // Ignore quantity, string allocation addresses and padding. Identity fields
    // include ItemId, refine, identification, cards, grade, equip and options.
    u32 h=2166136261u;auto mix=[&](u32 n){h=(h^n)*16777619u;};
    mix(itemId(item));mix(at<u32>(item,0x60));mix(at<u8>(item,0x5C));
    for(int i=0;i<4;++i)mix(at<u32>(item,0x1C+i*4));
    mix(at<u16>(item,0x88));mix(at<u8>(item,0x74));
    u32 count=at<u32>(item,0x98);if(count>5)return 0;mix(count);
    for(u32 i=0;i<count*5;++i)mix(at<u8>(item,0x9C+i));return h;
}
static bool sellItem(void* item){return item && at<u32>(item,0x10)>0 && at<u32>(item,0x10)<=0x7FFFFFFF && !(at<u8>(item,0x74) && *reinterpret_cast<u8*>(0x1600553));}
static Offer recipe(u32 i){
    Offer r={};if(i>=ShopState.count)return r;r=ShopState.offers[i];
    if(selling()){void* item=ShopInventory(r.index);if(!sellItem(item) || fingerprint(item)!=r.fingerprint)r.stock=0;else r.stock=at<u32>(item,0x10);}
    return r;
}
static const char* infoString(u32 id,int offset){
    void* mgr=*reinterpret_cast<void**>(0x159C088);if(!mgr)return 0;
    void* node=reinterpret_cast<void* (__thiscall *)(void*,const u32*)>(0xA7E780)(static_cast<u8*>(mgr)+8,&id);if(!node)return 0;
    void* s=static_cast<u8*>(node)+offset;u32 n=at<u32>(s,16);if(!n || n>512)return 0;
    return at<u32>(s,20)<16?static_cast<const char*>(s):at<const char*>(s,0);
}
EXPORT const char* __stdcall ShopResource(u32 id){return infoString(id,ShopIconIdentified?0x58:0x1C);}
EXPORT const char* __stdcall ShopName(u32 id,u32 identified){return infoString(id,identified?0x40:4);}
static void focusChoice();
static bool multiply(u32 a,u32 b,u32& result){if(b && a>0x7FFFFFFFu/b)return false;result=a*b;return true;}
static bool total(u32& value){value=0;for(u32 i=0;i<ShopState.cartCount;++i){u32 n;auto c=ShopState.cart[i];auto r=recipe(c.recipe);if(!c.quantity || c.quantity>30000 || !r.id || c.quantity>r.stock || !multiply(r.price,c.quantity,n) || n>0x7FFFFFFFu-value)return false;value+=n;}return true;}
static bool canBuy(){u32 n;return ShopState.active && !ShopState.pending && ShopState.cartCount && total(n) && (selling() || n<=*reinterpret_cast<u32*>(0x15FBA90));}
static bool send(const void* p,u32 length){void* t=reinterpret_cast<void* (__cdecl *)()>(ShopApi.ctor)();if(!t)return false;reinterpret_cast<void (__thiscall *)(void*,int,const void*)>(ShopApi.send)(t,length,p);return true;}
static void release(){
    void* w=ShopState.window;if(!w)return;
    if(ShopState.dragging==1)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880BB0)(w,0,0);
    ShopState.dragging=0;
    if(at<void*>((void*)0x131F4E8,0x19C)==w)reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);
    ShopState.pressed=0;
}
static void hide(bool notify,bool cleanup=false){
    bool finish=ShopState.active && (notify || cleanup);
    if(notify && ShopState.active){u16 op=0x9D4;send(&op,2);}
    release();ShopState.active=ShopState.pending=ShopState.cartCount=0;ShopState.right=0;++ShopState.epoch;itemHitCount=0;
    if(ShopState.window)at<int>(ShopState.window,0x28)=0;
    // Stock Buy/Sell/Cancel sends CGameMode message 0x28. Its profiled branch
    // clears the NPC-shop flag (+0x24C) and closes stock shop/dialog windows.
    // Keep this cleanup after custom trades too; do not patch the shared mode.
    if(finish){void* mode=*reinterpret_cast<void**>(0x121333C);if(mode)reinterpret_cast<void (__thiscall *)(void*,int,int,int,int,int)>(at<u32*>(mode,0)[6])(mode,0x28,0,0,0,0);}
}
static bool assets(){
    static const int widths[]={619,172,172,172,32,32,152,44,44,44,44,44,44,44,44,32,161,619,44,44,44};
    static const int heights[]={410,4,1,6,32,32,19,18,18,18,18,18,18,18,18,32,18,410,18,18,18};
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return false;
    for(int i=0;i<21;++i){
        const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(ShopApi.paths[i]);if(!path)return false;
        void* t=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);
        if(!t || at<int>(t,0x114)!=widths[i] || at<int>(t,0x118)!=heights[i] || !at<void*>(t,0x11C))return false;textures[i]=t;
    }return true;
}
EXPORT int __stdcall ShopReceive(const u8* p){
    if(!p)return 0;u16 op=*reinterpret_cast<const u16*>(p),len=*reinterpret_cast<const u16*>(p+2);
    if((op!=0xB77 && op!=0xC7) || len<4 || len>40960)return 0;
    u32 stride=op==0xB77?sizeof(BuyOffer):sizeof(SellOffer);if((len-4)%stride)return 0;u32 count=(len-4)/stride;if(count>4096)return 0;
    for(u32 i=0;i<count;++i){
        if(op==0xB77){auto* r=reinterpret_cast<const BuyOffer*>(p+4+i*stride);if(!r->id || r->discount>0x7FFFFFFF)return 0;for(u32 j=0;j<i;++j)if(reinterpret_cast<const BuyOffer*>(p+4+j*stride)->id==r->id)return 0;}
        else {auto* r=reinterpret_cast<const SellOffer*>(p+4+i*stride);if(r->index<2 || r->index>32767 || r->overcharge>0x7FFFFFFF)return 0;for(u32 j=0;j<i;++j)if(reinterpret_cast<const SellOffer*>(p+4+j*stride)->index==r->index)return 0;}
    }
    if(!assets()){hide(false);return 0;}
    void* w=ShopState.window;
    if(!w){w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4);if(!w)return 0;reinterpret_cast<void (__thiscall *)(void*,int)>(0x86B950)(w,0);at<u32>(w,0)=ShopApi.vtable;
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,619,410);at<int>(w,0x2C)=0x3EA;at<int>(w,0x1C)=30;at<int>(w,0x20)=40;ShopState.window=w;
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA2D240)((void*)0x131F4E8,w);ShopState.showAmounts=1;}
    release();ShopState.mode=op;ShopState.count=0;
    for(u32 i=0;i<count;++i){Offer r={};
        if(op==0xB77){auto* a=reinterpret_cast<const BuyOffer*>(p+4+i*stride);r.id=a->id;r.price=a->discount;r.basePrice=a->price;r.stock=30000;r.identified=1;}
        else {auto* a=reinterpret_cast<const SellOffer*>(p+4+i*stride);void* item=ShopInventory(a->index);if(!sellItem(item))continue;r.id=itemId(item);r.fingerprint=fingerprint(item);if(!r.id || !r.fingerprint)continue;
            r.index=a->index;r.price=a->overcharge;r.basePrice=a->price;r.stock=at<u32>(item,0x10);r.refine=at<u32>(item,0x60);r.identified=at<u8>(item,0x5C)?1:0;}
        ShopState.offers[ShopState.count++]=r;
    }
    ShopState.active=1;ShopState.pending=ShopState.catalogScroll=ShopState.chosen=ShopState.cartScroll=ShopState.cartCount=0;
    ShopState.hover=ShopState.right=0;ShopState.mouseX=ShopState.mouseY=-1;++ShopState.epoch;itemHitCount=0;
    status(ShopState.count?"Select an item to add it to the list.":"No items available.");escapeHeld=key(27);at<int>(w,0x28)=1;dirty();
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA39130)((void*)0x131F4E8,w);return 1;
}
static void buy(){
    if(!canBuy()){status("Check the quantity, inventory and Zeny.");dirty();return;}
    u8 p[604];*reinterpret_cast<u16*>(p)=selling()?0xC9:0xC8;u32 off=4;
    for(u32 i=0;i<ShopState.cartCount;++i){auto c=ShopState.cart[i];auto r=recipe(c.recipe);
        if(selling()){*reinterpret_cast<u16*>(p+off)=static_cast<u16>(r.index);*reinterpret_cast<u16*>(p+off+2)=static_cast<u16>(c.quantity);off+=4;}
        else {*reinterpret_cast<u16*>(p+off)=static_cast<u16>(c.quantity);*reinterpret_cast<u32*>(p+off+2)=r.id;off+=6;}
    }
    *reinterpret_cast<u16*>(p+2)=static_cast<u16>(off);ShopState.pending=1;
    if(!send(p,off)){ShopState.pending=0;status("Unable to send. Reopen the shop.");dirty();return;}
    // Standard NPC trade is one submission per session. Preserve stock result
    // handling (00CA/00CB), including Barter's independent 00CA observer.
    hide(false,true);
}
static void removeChoice(u32 i){if(i>=ShopState.cartCount)return;for(u32 j=i;j+1<ShopState.cartCount;++j)ShopState.cart[j]=ShopState.cart[j+1];--ShopState.cartCount;if(ShopState.chosen>=ShopState.cartCount)ShopState.chosen=ShopState.cartCount?ShopState.cartCount-1:0;}
static void add(u32 index){
    if(ShopState.pending || index>=ShopState.count || !recipe(index).stock)return;
    for(u32 i=0;i<ShopState.cartCount;++i)if(ShopState.cart[i].recipe==index){ShopState.chosen=i;focusChoice();return;}
    if(ShopState.cartCount==100){status("The list is full (100 entries).");return;}
    ShopState.chosen=ShopState.cartCount;ShopState.cart[ShopState.cartCount++]={index,1};focusChoice();status("Quantity: + / -. Shift: 10, Ctrl: 100.");
}
static void quantity(bool plus){
    if(ShopState.pending || !ShopState.cartCount)return;auto& c=ShopState.cart[ShopState.chosen];auto r=recipe(c.recipe);u32 limit=r.stock<30000?r.stock:30000,step=key(17)?100:key(16)?10:1;
    if(plus)c.quantity=c.quantity+step>limit?limit:c.quantity+step;else if(c.quantity>step)c.quantity-=step;else removeChoice(ShopState.chosen);
}
struct Clip {int x,y,w,h;};
static Clip clip={0,0,619,410};
static const Clip catalogPane={42,24,353,350},cartPane={421,55,182,260};
static int min(int a,int b){return a<b?a:b;}
static int max(int a,int b){return a>b?a:b;}
static int cartHeight(u32){return 93;}
static int catalogHeight(){return ShopState.count?static_cast<int>((ShopState.count+1)/2)*70-4:0;}
static int cartHeight(){return static_cast<int>(ShopState.cartCount)*98+44;}
static int scrollMax(bool cart){return max(0,(cart?cartHeight():catalogHeight())-(cart?cartPane.h:catalogPane.h));}
static void clampScroll(){ShopState.catalogScroll=min(ShopState.catalogScroll,scrollMax(false));ShopState.cartScroll=min(ShopState.cartScroll,scrollMax(true));}
static void focusChoice(){
    int y=0;for(u32 i=0;i<ShopState.chosen;++i)y+=cartHeight(i)+5;
    int h=cartHeight(ShopState.chosen),scroll=ShopState.cartScroll;
    if(y<scroll || h>cartPane.h)scroll=y;else if(y+h>scroll+cartPane.h)scroll=y+h-cartPane.h;
    ShopState.cartScroll=min(max(0,scroll),scrollMax(true));
}
static void scrollBy(bool cart,int delta){u32& offset=cart?ShopState.cartScroll:ShopState.catalogScroll;offset=min(max(0,static_cast<int>(offset)+delta),scrollMax(cart));itemHitCount=0;ShopState.right=0;dirty();}
static bool intersect(int x,int y,int w,int h){return x<clip.x+clip.w && x+w>clip.x && y<clip.y+clip.h && y+h>clip.y;}
static u32* pixels(){return at<u32*>(at<void*>(ShopState.window,0x24),0x18);}
static void rect(int x,int y,int w,int h,u32 color){
    int x2=min(x+w,clip.x+clip.w),y2=min(y+h,clip.y+clip.h);x=max(x,clip.x);y=max(y,clip.y);auto* p=pixels();
    for(int yy=y;yy<y2;++yy)for(int xx=x;xx<x2;++xx)p[yy*619+xx]=color;
}
static void panel(int x,int y,int w,int h,u32 fill=0xFFF8FAFD,u32 border=0xFFBACAE0){rect(x,y,w,h,border);rect(x+1,y+1,w-2,h-2,fill);}
static void border(int x,int y,int w,int h,u32 color){rect(x,y,w,1,color);rect(x,y+h-1,w,1,color);rect(x,y,1,h,color);rect(x+w-1,y,1,h,color);}
// The shared native item blitter does not clip. Partially visible primitives
// are drawn at a safe staging location on the real native surface, then copied
// through this pane's bounds. Restore the staging pixels before compositing.
// This preserves native font/surface handles and never changes shared helpers.
static u32 stageSave[192*40],stageDraw[192*40];
static void primitive(int op,u32 id,const char* s,int x,int y,int w,int h,u32 color=0){
    if(!intersect(x,y,w,h))return;
    bool stage=x<clip.x || y<clip.y || x+w>clip.x+clip.w || y+h>clip.y+clip.h;
    if(stage && (w>192 || h>40))return;
    auto* p=pixels();
    if(stage)for(int yy=0;yy<h;++yy)for(int xx=0;xx<w;++xx){stageSave[yy*w+xx]=p[yy*619+xx];stageDraw[yy*w+xx]=x+xx>=0 && x+xx<619 && y+yy>=0 && y+yy<410?p[(y+yy)*619+x+xx]:0;}
    if(stage)for(int yy=0;yy<h;++yy)for(int xx=0;xx<w;++xx)p[yy*619+xx]=stageDraw[yy*w+xx];
    const int dx=stage?0:x,dy=stage?0:y;
    if(op==0)ShopApi.text(ShopState.window,s,dx,dy,w,color);
    else if(op==1)ShopApi.png(ShopState.window,dx,dy,textures[id],0);
    else ShopApi.item(ShopState.window,id,dx,dy);
    if(stage){
        for(int yy=0;yy<h;++yy)for(int xx=0;xx<w;++xx){stageDraw[yy*w+xx]=p[yy*619+xx];p[yy*619+xx]=stageSave[yy*w+xx];}
        for(int yy=max(0,clip.y-y);yy<min(h,clip.y+clip.h-y);++yy)for(int xx=max(0,clip.x-x);xx<min(w,clip.x+clip.w-x);++xx)p[(y+yy)*619+x+xx]=stageDraw[yy*w+xx];
    }
}
static void text(const char* s,int x,int y,int width,u32 color=0x915F46){primitive(0,0,s,x,y,width,16,color);}
static int textWidth(const char* s){int n=0;while(s[n] && n<127)++n;return reinterpret_cast<int (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA21C90)(ShopState.window,s,n,0,11,0,0);}
static void aligned(const char* s,int x,int y,int w,bool center,u32 color=0xB98361){int used=min(textWidth(s),w);text(s,x+(w-used)/(center?2:1),y,used,color);}
static void image(int i,int x,int y){primitive(1,i,0,x,y,at<int>(textures[i],0x114),at<int>(textures[i],0x118));}
// Nine-slice horizontally so the same 172px card art also fits the 182px cart.
static void slice(int id,int x,int y,int w){
    auto* t=textures[id];int sw=at<int>(t,0x114),sh=at<int>(t,0x118);auto* source=at<u32*>(t,0x11C);auto* dest=pixels();
    for(int yy=max(0,clip.y-y);yy<min(sh,clip.y+clip.h-y);++yy)for(int xx=max(0,clip.x-x);xx<min(w,clip.x+clip.w-x);++xx){
        int sx=xx<3?xx:xx>=w-3?sw-w+xx:3+(xx-3)*(sw-6)/(w-6);u32 c=source[yy*sw+sx],a=c>>24;u32& d=dest[(y+yy)*619+x+xx];
        if(a==255)d=c;else if(a){u32 rb=(((c&0xFF00FF)*a+(d&0xFF00FF)*(255-a))>>8)&0xFF00FF,g=(((c&0xFF00)*a+(d&0xFF00)*(255-a))>>8)&0xFF00;d=0xFF000000|rb|g;}
    }
}
static void card(int x,int y,int h,int w=172){slice(1,x,y,w);for(int i=max(4,clip.y-y);i<min(h-6,clip.y+clip.h-y);++i)slice(2,x,y+i,w);slice(3,x,y+h-6,w);}
static void mini(int id,const char* caption,int x,int y,int w=20,bool enabled=true){u32 color=!enabled?0xFFF0F0F0:ShopState.pressed==id && ShopState.hover==id?0xFFB7D5FA:ShopState.hover==id?0xFFD9EAFF:0xFFF3F7FD;panel(x,y,w,20,color);aligned(caption,x+1,y+3,w-2,true,enabled?0xAD7D58:0xA4A4A4);}

static void name(char* s,const Offer& r){s[0]=0;if(r.refine && r.identified){append(s,"+");number(s,r.refine);append(s," ");}const char* n=ShopApi.name(r.id,r.identified);if(n && n[0])append(s,n);else if(!r.identified)append(s,"Unidentified item");else{append(s,"Item #");number(s,r.id);}}
static void icon(const Offer& r,u32 amount,int x,int y){
    if(!intersect(x,y,32,32))return;
    image(4,x,y);ShopIconIdentified=r.identified;primitive(2,r.id,0,x,y,32,32);
    if(itemHitCount<80){int left=max(x,clip.x),top=max(y,clip.y);itemHits[itemHitCount++]={left,top,min(x+32,clip.x+clip.w)-left,min(y+32,clip.y+clip.h)-top,r.id,amount,r.refine,r.index,r.price,r.identified,r.fingerprint};}
}
static Hit* itemHit(int x,int y){for(int i=itemHitCount-1;i>=0;--i)if(contains(x,y,itemHits[i].x,itemHits[i].y,itemHits[i].w,itemHits[i].h))return &itemHits[i];return 0;}
static void describe(const Hit& h){
    if(!selling()){ShopIconIdentified=1;ShopApi.describe(h.id);return;}
    void* item=ShopInventory(h.index);if(!item || fingerprint(item)!=h.fingerprint)return;
    // Pass the real instance to stock item description: preserve identification,
    // refine, grade, cards and options instead of fabricating a template CItem.
    void* wnd=reinterpret_cast<void* (__thiscall *)(void*,int)>(0xA39340)((void*)0x131F4E8,12);if(!wnd)return;
    auto table=at<void**>(wnd,0);reinterpret_cast<void (__thiscall *)(void*,int,int,void*,int,int,int)>(table[37])(wnd,0,24,item,0,0,0);
}
static void tooltip(){
    Hit* h=itemHit(ShopState.mouseX,ShopState.mouseY);if(!h)return;
    Offer r={};r.id=h->id;r.refine=h->refine;r.identified=h->identified;
    char title[128],line[128],cost[128];name(title,r);line[0]=cost[0]=0;append(line,"Quantity: ");number(line,h->amount,true);
    append(cost,selling()?"Sell price: ":"Price: ");number(cost,h->price,true);append(cost," z each");
    int x=ShopState.mouseX+14,y=ShopState.mouseY+20;if(x+250>615)x=365;if(y+53>380)y=ShopState.mouseY-58;
    panel(x,y,250,53,0xFFFFFFDE,0xFF8C847B);text(title,x+5,y+4,240,0x292929);text(line,x+5,y+19,240,0x292929);text(cost,x+5,y+34,240,0x292929);
}
static void price(u32 amount,int x,int y,int w){x+=(w-161)/2;image(16,x,y);char label[128];label[0]=0;number(label,amount,true);aligned(label,x+17,y+2,139,false);}
struct Scroll {int x,y,h,max,position,thumb,thumbY;};
static Scroll bar(bool cart){Clip p=cart?cartPane:catalogPane;Scroll b={cart?605:398,p.y,p.h,scrollMax(cart),static_cast<int>(cart?ShopState.cartScroll:ShopState.catalogScroll),0,0};int track=b.h-22;b.thumb=max(22,track*p.h/(p.h+b.max));b.thumbY=b.y+11+(b.max?b.position*(track-b.thumb)/b.max:0);return b;}
static void scrollbar(bool cart){
    auto b=bar(cart);if(!b.max)return;panel(b.x,b.y,10,b.h,0xFFE3EAFA,0xFFBAC9E7);panel(b.x,b.thumbY,10,b.thumb,0xFF9EB6DF,0xFF849ECE);
    for(int i=0;i<2;++i){int y=i?b.y+b.h-11:b.y;panel(b.x,y,10,11,0xFFD7E5FA,0xFFA9BFDF);for(int row=0;row<3;++row)rect(b.x+4-row,y+(i?6-row:3+row),1+row*2,1,0xFF6685BE);}
}

EXPORT int __stdcall ShopHit(int x,int y){
    if(!ShopState.active)return 0;
    if(contains(x,y,600,1,17,16))return 1;
    if(contains(x,y,516,351,44,18))return 2;
    if(contains(x,y,464,351,44,18) && canBuy())return 3;
    if(selling() && contains(x,y,41,385,165,20))return 4;
    if(ShopState.pending)return 0;
    for(int i=0;i<2;++i){auto b=bar(i!=0);if(b.max && contains(x,y,b.x,b.y,10,b.h))return (i?20:10)+(y<b.y+11?2:y>=b.y+b.h-11?3:0);}
    if(contains(x,y,catalogPane.x,catalogPane.y,catalogPane.w,catalogPane.h)){
        int top=catalogPane.y-ShopState.catalogScroll;
        for(u32 i=0;i<ShopState.count;i+=2){for(u32 j=0;j<2 && i+j<ShopState.count;++j)if(recipe(i+j).stock && contains(x,y,42+j*179,top,172,66))return 1000+i+j;top+=70;}
    }
    if(contains(x,y,cartPane.x,cartPane.y,cartPane.w,cartPane.h)){
        int top=cartPane.y-ShopState.cartScroll;
        for(u32 i=0;i<ShopState.cartCount;++i){if(contains(x,y,cartPane.x,top,182,93)){
            if(contains(x,y,589,top+4,12,13))return 20000+i;
            if(contains(x,y,518,top+42,20,20))return 10000+i*2;
            auto c=ShopState.cart[i];if(contains(x,y,576,top+42,20,20) && c.quantity<30000 && c.quantity<recipe(c.recipe).stock)return 10001+i*2;
        }top+=98;}
    }return 0;
}
EXPORT void __fastcall ShopDraw(void* w,void*){
    if(w!=ShopState.window || !ShopState.active || at<int>(w,0x14)!=619 || at<int>(w,0x18)!=410)return;
    if(!assets())return;
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);itemHitCount=0;clip={0,0,619,410};image(selling()?17:0,0,0);clampScroll();
    text(selling()?"Sell Items":"Item Shop",7,2,300,0x674623);mini(1,"x",600,0,17);
    char label[128];clip=catalogPane;int y=catalogPane.y-ShopState.catalogScroll;
    for(u32 row=0;row<ShopState.count;row+=2){if(y>=clip.y+clip.h)break;
        if(y+66>clip.y)for(u32 j=0;j<2 && row+j<ShopState.count;++j){u32 i=row+j;auto r=recipe(i);int x=42+j*179;card(x,y,66);
            bool selected=false;for(u32 k=0;k<ShopState.cartCount;++k)if(ShopState.cart[k].recipe==i)selected=true;if(selected)border(x,y,172,66,0xFF8BAADB);
            icon(r,selling()?r.stock:1,x+6,y+5);name(label,r);text(label,x+44,y+(selling() && ShopState.showAmounts?7:13),120);
            if(selling() && ShopState.showAmounts){label[0]=0;append(label,"x");number(label,r.stock,true);text(label,x+44,y+23,120,0x958A85);}
            price(r.price,x,y+42,172);
        }y+=70;
    }
    clip=cartPane;y=cartPane.y-ShopState.cartScroll;
    for(u32 i=0;i<ShopState.cartCount;++i){if(y>=clip.y+clip.h)break;if(y+93>clip.y){auto c=ShopState.cart[i];auto r=recipe(c.recipe);int x=cartPane.x;card(x,y,93,182);
        icon(r,c.quantity,x+6,y+6);name(label,r);text(label,x+44,y+9,119);
        label[0]=0;number(label,r.price,true);append(label," z each");text(label,x+44,y+24,128,0x958A85);
        panel(589,y+4,12,13);text("x",592,y+4,7,0xAD7D58);
        text("Quantity",x+7,y+45,88,0x967E6F);mini(10000+i*2,"-",518,y+42,20,!ShopState.pending);
        panel(542,y+42,30,20,0xFFFFFFFF);label[0]=0;number(label,c.quantity);aligned(label,544,y+45,26,true);
        mini(10001+i*2,"+",576,y+42,20,!ShopState.pending && c.quantity<30000 && c.quantity<r.stock);
        u32 cost=0;if(c.quantity<=r.stock && multiply(r.price,c.quantity,cost))price(cost,x,y+69,182);else text("Inventory changed",x+7,y+70,168,0x6566BA);
    }y+=98;}
    if(y<clip.y+clip.h && y+44>clip.y){card(cartPane.x,y,44,182);image(5,cartPane.x+6,y+6);text("Select an item",cartPane.x+46,y+17,129,0xAF9D92);}
    clip={0,0,619,410};scrollbar(false);scrollbar(true);
    u32 sum=0;bool valid=total(sum);image(6,436,324);label[0]=0;if(valid)number(label,sum,true);else append(label,"Check items");append(label," z");aligned(label,474,328,108,false);
    int state=canBuy()?(ShopState.hover==3?(ShopState.pressed==3?2:1):0):3;
    if(selling()){image(18+(state<3?state:0),464,351);if(state==3){auto* p=pixels();for(int yy=351;yy<369;++yy)for(int xx=464;xx<508;++xx){u32 c=p[yy*619+xx];u32 a=(((c>>16)&255)+((c>>8)&255)+(c&255))/3;p[yy*619+xx]=0xFF000000|(a<<16)|(a<<8)|a;}}}
    else image(7+state,464,351);
    state=ShopState.hover==2?(ShopState.pressed==2?2:1):0;image(11+state,516,351);
    if(selling()){panel(41,388,11,11,0xFFFFFFFF);if(ShopState.showAmounts){rect(44,391,5,5,0xFF7A93B7);}text("Toggle Item Amount",57,387,147,0xAB8873);}
    else {label[0]=0;append(label,"Zeny: ");number(label,*reinterpret_cast<u32*>(0x15FBA90),true);text(label,41,388,155,0xAB8873);}
    const char* message=valid && !selling() && sum>*reinterpret_cast<u32*>(0x15FBA90)?"Not enough Zeny.":ShopState.status;
    aligned(message,209,388,393,false,0x97857C);tooltip();
}
static void dragScroll(int y){bool cart=ShopState.dragging==3;auto b=bar(cart);int travel=b.h-22-b.thumb;u32& offset=cart?ShopState.cartScroll:ShopState.catalogScroll;if(travel>0)offset=min(max(0,y-b.y-11-ShopState.scrollGrab),travel)*b.max/travel;itemHitCount=0;ShopState.right=0;dirty();}
EXPORT void __fastcall ShopDown(void* w,void*,int x,int y){
    if(w!=ShopState.window || !ShopState.active)return;release();ShopState.hover=ShopState.pressed=ShopHit(x,y);
    int hit=ShopState.pressed;
    if(hit)reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);
    if(hit==10 || hit==20){auto b=bar(hit==20);ShopState.dragging=hit==20?3:2;ShopState.scrollGrab=y>=b.thumbY && y<b.thumbY+b.thumb?y-b.thumbY:b.thumb/2;dragScroll(y);}
    else if(!hit && y>=0 && y<18){ShopState.dragging=1;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880AD0)(w,x,y);}dirty();
}
EXPORT void __fastcall ShopUp(void*,void*,int x,int y){
    int hit=ShopHit(x,y),pressed=ShopState.pressed,drag=ShopState.dragging;release();if(drag>1 || !hit || hit!=pressed){dirty();return;}
    if(hit==1 || hit==2){hide(true);return;}if(hit==3)buy();
    else if(hit>=20000){removeChoice(hit-20000);clampScroll();}
    else if(hit>=10000){ShopState.chosen=(hit-10000)/2;quantity((hit&1)!=0);clampScroll();}
    else if(hit>=1000)add(hit-1000);
    else if(hit==4)ShopState.showAmounts=!ShopState.showAmounts;
    else if(hit==12 || hit==13 || hit==22 || hit==23)scrollBy(hit>=20,(hit%10==2?-1:1)*44);
    itemHitCount=0;ShopState.right=0;dirty();
}
EXPORT void __fastcall ShopMove(void*,void*,int x,int y){if(ShopState.dragging>1){dragScroll(y);return;}int hit=ShopHit(x,y);bool changed=x!=ShopState.mouseX || y!=ShopState.mouseY || hit!=ShopState.hover;ShopState.mouseX=x;ShopState.mouseY=y;ShopState.hover=hit;auto* h=itemHit(x,y);if(!h || (selling()?h->index:h->id)!=ShopState.rightId)ShopState.right=0;if(changed)dirty();}
EXPORT void __fastcall ShopDrag(void* w,void*,int x,int y){if(ShopState.dragging==1)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880E00)(w,x,y);else ShopMove(w,0,x,y);}
EXPORT void __fastcall ShopCursor(void* w,void*,int x,int y){
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA23470)(w,x,y);ShopMove(w,0,x,y);
    bool escape=key(27);if(escape && !escapeHeld && ShopState.active)hide(true);escapeHeld=escape;
    void* c=*reinterpret_cast<void**>(0x121333C);if(c)reinterpret_cast<void (__thiscall *)(void*,int)>(0xA764A0)(c,(ShopState.hover || itemHit(x,y))?2:0);
}
EXPORT void __fastcall ShopRightDown(void*,void*,int x,int y){ShopState.right=0;if(!ShopState.active || at<void*>((void*)0x131F4E8,0x19C))return;auto* h=itemHit(x,y);if(h){ShopState.right=1;ShopState.rightId=selling()?h->index:h->id;ShopState.rightEpoch=ShopState.epoch;}}
EXPORT void __fastcall ShopRightUp(void*,void*,int x,int y){auto* h=itemHit(x,y);bool inspect=ShopState.right && ShopState.rightEpoch==ShopState.epoch && h && (selling()?h->index:h->id)==ShopState.rightId;ShopState.right=0;if(inspect)describe(*h);}
EXPORT void __fastcall ShopWheel(void*,void*,int delta){
    if(!ShopState.active || ShopState.pending || !delta)return;
    if(contains(ShopState.mouseX,ShopState.mouseY,42,24,366,350))scrollBy(false,delta>0?-44:44);
    else if(contains(ShopState.mouseX,ShopState.mouseY,421,55,194,260))scrollBy(true,delta>0?-44:44);
}
EXPORT void* __fastcall ShopDestroy(void* w,void*,int flags){hide(false);ShopState.window=0;for(int i=0;i<21;++i)textures[i]=0;return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);}

