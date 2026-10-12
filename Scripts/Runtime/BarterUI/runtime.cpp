// Independent, import-free 2025-07-16 barter surface. Server recipes and native
// barter packets remain authoritative; no inventory, prices or item data writes.
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#define EXPORT extern "C" __declspec(dllexport)
#pragma pack(push,1)
struct Normal { u32 id;u8 type;u32 stock,currency,amount,weight,index;u16 view;u32 location; };
struct Expanded { u32 id;u16 type;u32 stock,weight,index,zeny;u16 view;u32 location,count,refine; };
struct Material { u32 id;u16 refine;u32 amount;u16 type; };
#pragma pack(pop)
static_assert(sizeof(Normal)==31 && sizeof(Expanded)==36 && sizeof(Material)==12,"2025 barter wire layout");
struct Api {
    u32 version,vtable,ctor,send;
    void (__stdcall *text)(void*,const char*,int,int,int,u32);
    void (__stdcall *item)(void*,u32,int,int);
    void (__stdcall *describe)(u32);
    const char* (__stdcall *name)(u32);
    void (__thiscall *png)(void*,int,int,void*,int);
    u32 keysIat;
    const char* paths[17];
};
static_assert(sizeof(Api)==108,"BarterUI API v3");
EXPORT Api BarterApi={3};
struct Choice { u32 recipe,quantity; };
// A maximum-sized native receive buffer can hold fewer than 1400 recipes.
// Keep every requirement in the original bounded byte buffer, never truncate it.
struct State {
    void* window;u32 active,mode,count,catalogScroll,chosen,cartScroll,cartCount,pending;
    int hover,pressed,dragging,mouseX,mouseY,right;u32 rightId,epoch,rightEpoch,sentAt;
    u32 offsets[1400];Choice cart[100];u8 packet[40960];char status[128];int scrollGrab;
};
EXPORT State BarterState={};
struct Hit { int x,y,w,h;u32 id,amount,refine;int required; };
static Hit itemHits[160];static int itemHitCount;
static void* textures[17];
static bool escapeHeld;
template<typename T>T& at(void* p,int o){return *reinterpret_cast<T*>(static_cast<u8*>(p)+o);}
static void copy(void* d,const void* s,u32 n){auto* out=static_cast<volatile u8*>(d);auto* in=static_cast<const u8*>(s);for(u32 i=0;i<n;++i)out[i]=in[i];}
static void append(char* d,const char* s){int n=0;while(d[n] && n<126)++n;for(int i=0;s && s[i] && n<126;++i)d[n++]=s[i];d[n]=0;}
static void number(char* d,u32 n,bool comma=false){char tmp[20];int k=0;do{if(comma && k && (k+1)%4==0)tmp[k++]=',';tmp[k++]=static_cast<char>('0'+n%10);n/=10;}while(n);for(int i=0;i<k/2;++i){char c=tmp[i];tmp[i]=tmp[k-i-1];tmp[k-i-1]=c;}tmp[k]=0;append(d,tmp);}
static void status(const char* s){BarterState.status[0]=0;append(BarterState.status,s);}
static void dirty(){if(BarterState.window)at<int>(BarterState.window,0x58)=1;}
static u32 tick(){return (*reinterpret_cast<u32 (__stdcall **)()>(0xFC17B0))();}
static bool key(int code){return BarterApi.keysIat && ((*reinterpret_cast<short (__stdcall **)(int)>(BarterApi.keysIat))(code)&0x8000)!=0;}
static bool contains(int x,int y,int bx,int by,int w,int h){return x>=bx && y>=by && x<bx+w && y<by+h;}
static Expanded recipe(u32 i){
    Expanded r={};if(i>=BarterState.count)return r;
    auto* p=BarterState.packet+BarterState.offsets[i];
    if(BarterState.mode==0xB79)copy(&r,p,sizeof(r));
    else {auto* n=reinterpret_cast<const Normal*>(p);r.id=n->id;r.type=n->type;r.stock=n->stock;r.weight=n->weight;r.index=n->index;r.view=n->view;r.location=n->location;r.count=n->currency && n->amount?1:0;}
    return r;
}
static Material material(u32 i,u32 m){
    Material r={};if(i>=BarterState.count)return r;
    auto* p=BarterState.packet+BarterState.offsets[i];
    if(BarterState.mode==0xB79){if(m<reinterpret_cast<const Expanded*>(p)->count)copy(&r,p+sizeof(Expanded)+m*sizeof(Material),sizeof(r));}
    else if(!m){auto* n=reinterpret_cast<const Normal*>(p);r.id=n->currency;r.amount=n->amount;}
    return r;
}
// Read only the profiled CSession inventory list. CItem: numeric resource string
// +2C, amount +10, refine +60. Amounts are informational; server checks equipped,
// bound, cards and refine preferences before taking any materials.
EXPORT u32 __stdcall BarterOwned(u32 id,u32 refine){
    void* session=reinterpret_cast<void*>(0x15FA3C0);u32 count=at<u32>(session,0x16F4);
    void* head=at<void*>(session,0x16F0);if(!head || count>10000)return 0;
    void* node=at<void*>(head,0);u32 total=0;
    for(u32 i=0;i<count && node && node!=head;++i,node=at<void*>(node,0)){
        auto* item=static_cast<u8*>(node)+8;u32 length=at<u32>(item,0x3C),n=0;
        if(!length || length>10)continue;
        auto* str=at<u32>(item,0x40)<16?reinterpret_cast<const char*>(item+0x2C):at<const char*>(item,0x2C);
        if(!str)continue;
        bool valid=true;for(u32 j=0;j<length;++j){if(str[j]<'0' || str[j]>'9' || n>(0xFFFFFFFFu-static_cast<u32>(str[j]-'0'))/10){valid=false;break;}n=n*10+str[j]-'0';}
        if(valid && n==id && (!refine || at<u32>(item,0x60)>=refine)){
            const u32 amount=at<u32>(item,0x10);if(amount>0x7FFFFFFF)continue;
            total=amount>0xFFFFFFFFu-total?0xFFFFFFFFu:total+amount;
        }
    }
    return total;
}
static void focusChoice();
static bool multiply(u32 a,u32 b,u32& result){if(b && a>0x7FFFFFFFu/b)return false;result=a*b;return true;}
static bool total(u32& value){
    value=0;
    for(u32 i=0;i<BarterState.cartCount;++i){u32 n;auto c=BarterState.cart[i];auto r=recipe(c.recipe);
        if(!c.quantity || !r.id || (r.stock!=0xFFFFFFFF && c.quantity>r.stock) || !multiply(r.zeny,c.quantity,n) || n>0x7FFFFFFFu-value)return false;
        value+=n;for(u32 j=0;j<r.count;++j)if(!multiply(material(c.recipe,j).amount,c.quantity,n))return false;
    }
    return true;
}
static bool canBuy(){u32 n;return BarterState.active && !BarterState.pending && BarterState.cartCount && total(n);}
static bool send(const void* p,u32 length){void* t=reinterpret_cast<void* (__cdecl *)()>(BarterApi.ctor)();if(!t)return false;reinterpret_cast<void (__thiscall *)(void*,int,const void*)>(BarterApi.send)(t,length,p);return true;}
static void release(){
    void* w=BarterState.window;if(!w)return;
    if(BarterState.dragging==1)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880BB0)(w,0,0);
    BarterState.dragging=0;
    if(at<void*>((void*)0x131F4E8,0x19C)==w)reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);
    BarterState.pressed=0;
}
static void hide(bool notify){
    if(notify && BarterState.active){u16 op=BarterState.mode==0xB79?0xB58:0xB12;send(&op,2);}
    release();BarterState.active=BarterState.pending=BarterState.cartCount=0;BarterState.right=0;++BarterState.epoch;itemHitCount=0;
    if(BarterState.window)at<int>(BarterState.window,0x28)=0;
}
static bool assets(){
    static const int widths[]={619,172,172,172,32,32,152,44,44,44,44,44,44,44,44,32,161};
    static const int heights[]={410,4,1,6,32,32,19,18,18,18,18,18,18,18,18,32,18};
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return false;
    for(int i=0;i<17;++i){
        const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(BarterApi.paths[i]);if(!path)return false;
        void* t=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);
        if(!t || at<int>(t,0x114)!=widths[i] || at<int>(t,0x118)!=heights[i] || !at<void*>(t,0x11C))return false;
        textures[i]=t;
    }
    return true;
}
// Validate the whole packet before touching the active shop. Unknown/missing
// artwork falls back to the complete original native barter implementation.
EXPORT int __stdcall BarterReceive(const u8* p){
    if(!p)return 0;u16 op=*reinterpret_cast<const u16*>(p),len=*reinterpret_cast<const u16*>(p+2);
    if((op!=0xB78 && op!=0xB79) || len<4 || len>40960)return 0;
    u32 count=0,off=4;
    if(op==0xB78){if((len-4)%sizeof(Normal))return 0;count=(len-4)/sizeof(Normal);}
    else {if(len<8)return 0;count=*reinterpret_cast<const u32*>(p+4);off=8;}
    if(count>1400)return 0;
    for(u32 i=0;i<count;++i){
        if(off>len)return 0;
        if(op==0xB78){if(len-off<sizeof(Normal))return 0;auto* r=reinterpret_cast<const Normal*>(p+off);if(!r->id || r->index>65535)return 0;off+=sizeof(Normal);}
        else {if(len-off<sizeof(Expanded))return 0;auto* r=reinterpret_cast<const Expanded*>(p+off);off+=sizeof(Expanded);
            if(!r->id || r->index>65535 || r->count>(len-off)/sizeof(Material))return 0;
            for(u32 j=0;j<r->count;++j){auto* m=reinterpret_cast<const Material*>(p+off+j*sizeof(Material));if(!m->id || !m->amount)return 0;}
            off+=r->count*sizeof(Material);
        }
    }
    if(off!=len)return 0;
    if(!assets()){hide(false);return 0;}
    void* w=BarterState.window;
    if(!w){
        w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4);if(!w)return 0;
        reinterpret_cast<void (__thiscall *)(void*,int)>(0x86B950)(w,0);at<u32>(w,0)=BarterApi.vtable;
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,619,410);
        at<int>(w,0x2C)=0x3E9;at<int>(w,0x1C)=30;at<int>(w,0x20)=40;BarterState.window=w;
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA2D240)((void*)0x131F4E8,w);
    }
    release();copy(BarterState.packet,p,len);BarterState.mode=op;BarterState.count=count;
    off=op==0xB79?8:4;
    for(u32 i=0;i<count;++i){BarterState.offsets[i]=off;off+=op==0xB79?sizeof(Expanded)+recipe(i).count*sizeof(Material):sizeof(Normal);}
    BarterState.active=1;BarterState.pending=BarterState.catalogScroll=BarterState.chosen=BarterState.cartScroll=BarterState.cartCount=0;
    BarterState.hover=BarterState.right=0;BarterState.mouseX=BarterState.mouseY=-1;++BarterState.epoch;itemHitCount=0;
    status(count?"Select an item to add it to the buying list.":"This shop has no items available.");
    escapeHeld=key(27);at<int>(w,0x28)=1;dirty();reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA39130)((void*)0x131F4E8,w);return 1;
}
EXPORT void __stdcall BarterResult(const u8* p){
    if(!p || *reinterpret_cast<const u16*>(p)!=0xCA || !BarterState.active || !BarterState.pending)return;
    BarterState.pending=0;
    if(!p[2]){
        for(u32 i=0;i<BarterState.cartCount;++i){auto c=BarterState.cart[i];auto* r=BarterState.packet+BarterState.offsets[c.recipe];
            u32& stock=*reinterpret_cast<u32*>(r+(BarterState.mode==0xB79?6:5));if(stock!=0xFFFFFFFF)stock=stock>c.quantity?stock-c.quantity:0;
        }
        BarterState.cartCount=BarterState.chosen=BarterState.cartScroll=0;status("Purchase complete.");
    }else status("Purchase failed. Check the server message.");
    dirty();
}
static void buy(){
    if(!canBuy())return;u8 p[1404];u16 op=BarterState.mode==0xB79?0xB57:0xB0F;*reinterpret_cast<u16*>(p)=op;u32 off=4;
    for(u32 i=0;i<BarterState.cartCount;++i){auto c=BarterState.cart[i];auto r=recipe(c.recipe);*reinterpret_cast<u32*>(p+off)=r.id;
        if(op==0xB57){*reinterpret_cast<u32*>(p+off+4)=r.index;*reinterpret_cast<u32*>(p+off+8)=c.quantity;off+=12;}
        else {*reinterpret_cast<u32*>(p+off+4)=c.quantity;*reinterpret_cast<u16*>(p+off+8)=0;*reinterpret_cast<u32*>(p+off+10)=r.index;off+=14;}
    }
    *reinterpret_cast<u16*>(p+2)=static_cast<u16>(off);BarterState.pending=1;BarterState.sentAt=tick();
    if(!send(p,off)){BarterState.pending=0;status("Unable to send purchase. Please reopen the shop.");}else status("Waiting for the server...");dirty();
}
static void add(u32 index){
    if(BarterState.pending || index>=BarterState.count)return;auto r=recipe(index);if(!r.stock)return;
    for(u32 i=0;i<BarterState.cartCount;++i){
        if(BarterState.cart[i].recipe==index){BarterState.chosen=i;focusChoice();return;}
        if(recipe(BarterState.cart[i].recipe).id==r.id){status("Remove the other recipe for this item first.");return;}
    }
    if(BarterState.cartCount==100){status("The buying list is full (100 items).");return;}
    BarterState.chosen=BarterState.cartCount;BarterState.cart[BarterState.cartCount++]={index,1};focusChoice();
    status("Use + / - to change quantity. Shift: 10, Ctrl: 100.");
}
static void quantity(bool plus){
    if(BarterState.pending || !BarterState.cartCount)return;auto& c=BarterState.cart[BarterState.chosen];auto r=recipe(c.recipe);
    u32 step=key(17)?100:key(16)?10:1,limit=r.stock<30000?r.stock:30000;
    if(plus)c.quantity=c.quantity+step>limit?limit:c.quantity+step;
    else if(c.quantity>step)c.quantity-=step;
    else {for(u32 i=BarterState.chosen;i+1<BarterState.cartCount;++i)BarterState.cart[i]=BarterState.cart[i+1];--BarterState.cartCount;if(BarterState.chosen && BarterState.chosen>=BarterState.cartCount)--BarterState.chosen;}
}
// Pixel geometry matches the accepted 619x410 preview. Each pane clips its own
// content; footer, total, action buttons and Buying List caption never scroll.
struct Clip {int x,y,w,h;};
static Clip clip={0,0,619,410};
static const Clip catalogPane={42,24,353,350},cartPane={421,55,182,260};
static int min(int a,int b){return a<b?a:b;}
static int max(int a,int b){return a>b?a:b;}
// One row for 1-5 requirements; add the second row only for 6-10.
static int materialRows(u32 n){return max(1,static_cast<int>((n+4)/5));}
static int offerHeight(u32 i){return 155+44*(materialRows(min(recipe(i).count,10))-1);}
static int rowHeight(u32 i){return max(offerHeight(i),i+1<BarterState.count?offerHeight(i+1):0);}
static int cartHeight(u32 i){return 173+44*(materialRows(recipe(BarterState.cart[i].recipe).count)-1);}
static int catalogHeight(){int n=0;for(u32 i=0;i<BarterState.count;i+=2)n+=rowHeight(i)+7;return max(0,n-7);}
static int cartHeight(){int n=0;for(u32 i=0;i<BarterState.cartCount;++i)n+=cartHeight(i)+7;return n+44;}
static int scrollMax(bool cart){return max(0,(cart?cartHeight():catalogHeight())-(cart?cartPane.h:catalogPane.h));}
static void clampScroll(){BarterState.catalogScroll=min(BarterState.catalogScroll,scrollMax(false));BarterState.cartScroll=min(BarterState.cartScroll,scrollMax(true));}
static void focusChoice(){
    int y=0;for(u32 i=0;i<BarterState.chosen;++i)y+=cartHeight(i)+7;
    int h=cartHeight(BarterState.chosen),scroll=BarterState.cartScroll;
    if(y<scroll || h>cartPane.h)scroll=y;else if(y+h>scroll+cartPane.h)scroll=y+h-cartPane.h;
    BarterState.cartScroll=min(max(0,scroll),scrollMax(true));
}
static void scrollBy(bool cart,int delta){u32& offset=cart?BarterState.cartScroll:BarterState.catalogScroll;offset=min(max(0,static_cast<int>(offset)+delta),scrollMax(cart));itemHitCount=0;BarterState.right=0;dirty();}
static bool intersect(int x,int y,int w,int h){return x<clip.x+clip.w && x+w>clip.x && y<clip.y+clip.h && y+h>clip.y;}
static u32* pixels(){return at<u32*>(at<void*>(BarterState.window,0x24),0x18);}
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
    if(op==0)BarterApi.text(BarterState.window,s,dx,dy,w,color);
    else if(op==1)BarterApi.png(BarterState.window,dx,dy,textures[id],0);
    else BarterApi.item(BarterState.window,id,dx,dy);
    if(stage){
        for(int yy=0;yy<h;++yy)for(int xx=0;xx<w;++xx){stageDraw[yy*w+xx]=p[yy*619+xx];p[yy*619+xx]=stageSave[yy*w+xx];}
        for(int yy=max(0,clip.y-y);yy<min(h,clip.y+clip.h-y);++yy)for(int xx=max(0,clip.x-x);xx<min(w,clip.x+clip.w-x);++xx)p[(y+yy)*619+x+xx]=stageDraw[yy*w+xx];
    }
}
static void text(const char* s,int x,int y,int width,u32 color=0x915F46){primitive(0,0,s,x,y,width,16,color);}
static int textWidth(const char* s){int n=0;while(s[n] && n<127)++n;return reinterpret_cast<int (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA21C90)(BarterState.window,s,n,0,11,0,0);}
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
static void mini(int id,const char* caption,int x,int y,int w=20,bool enabled=true){u32 color=!enabled?0xFFF0F0F0:BarterState.pressed==id && BarterState.hover==id?0xFFB7D5FA:BarterState.hover==id?0xFFD9EAFF:0xFFF3F7FD;panel(x,y,w,20,color);aligned(caption,x+1,y+3,w-2,true,enabled?0xAD7D58:0xA4A4A4);}
static void name(char* s,u32 id,u32 refine=0){s[0]=0;if(refine){append(s,"+");number(s,refine);append(s," ");}const char* n=BarterApi.name(id);if(n && n[0])append(s,n);else{append(s,"Item #");number(s,id);}}
static void compact(char* s,u32 n){s[0]=0;if(n>=1000000){number(s,n/1000000);append(s,"m");}else if(n>=10000){number(s,n/1000);append(s,"k");}else number(s,n);}
static void icon(u32 id,u32 amount,u32 refine,int x,int y,bool required){
    if(!intersect(x,y,32,32))return;
    image(required?15:4,x,y);primitive(2,id,0,x,y,32,32);
    if(itemHitCount<160){int left=max(x,clip.x),top=max(y,clip.y);itemHits[itemHitCount++]={left,top,min(x+32,clip.x+clip.w)-left,min(y+32,clip.y+clip.h)-top,id,amount,refine,required?1:0};}
}
static Hit* itemHit(int x,int y){for(int i=itemHitCount-1;i>=0;--i)if(contains(x,y,itemHits[i].x,itemHits[i].y,itemHits[i].w,itemHits[i].h))return &itemHits[i];return 0;}
static void tooltip(){
    Hit* h=itemHit(BarterState.mouseX,BarterState.mouseY);if(!h)return;
    char title[128],line[128],owned[128];line[0]=owned[0]=0;name(title,h->id,h->refine);append(line,h->required?"Required: ":"Quantity: ");number(line,h->amount,true);
    if(h->required){append(owned,"In inventory: ");number(owned,BarterOwned(h->id,h->refine),true);}
    int x=BarterState.mouseX+14,y=BarterState.mouseY+20,height=h->required?53:38;if(x+250>615)x=365;if(y+height>380)y=BarterState.mouseY-height-5;
    panel(x,y,250,height,0xFFFFFFDE,0xFF8C847B);text(title,x+5,y+4,240,0x292929);text(line,x+5,y+19,240,0x292929);if(h->required)text(owned,x+5,y+34,240,0x292929);
}
static void price(u32 amount,int x,int y,int w){
    // Center the original 161x18 asset without scaling its baked-in Zeny icon.
    x+=(w-161)/2;image(16,x,y);
    char label[128];label[0]=0;number(label,amount,true);aligned(label,x+17,y+2,139,false);
}
static bool shortMaterials(u32 index,u32 quantity){auto r=recipe(index);for(u32 i=0;i<r.count;++i){auto m=material(index,i);u32 needed;if(!multiply(m.amount,quantity,needed) || BarterOwned(m.id,m.refine)<needed)return true;}return false;}
static void materials(u32 index,u32 quantity,int x,int y,u32 limit){
    auto r=recipe(index);char label[128];int step=r.count>4?32:36;
    for(u32 i=0;i<r.count && i<limit;++i){int iy=y+(i/5)*44;if(iy+44<=clip.y || iy>=clip.y+clip.h)continue;
        auto m=material(index,i);u32 needed=0;bool ok=multiply(m.amount,quantity,needed);int ix=x+(i%5)*step;
        icon(m.id,ok?needed:0xFFFFFFFF,m.refine,ix,iy,true);compact(label,needed);if(!ok){label[0]=0;append(label,"!");}
        aligned(label,ix,iy+33,32,true,ok && BarterOwned(m.id,m.refine)>=needed?0x668850:0x6566BA);
    }
    if(!r.count)text("No materials needed",x,y+9,156,0x958A85);
}
struct Scroll {int x,y,h,max,position,thumb,thumbY;};
static Scroll bar(bool cart){Clip p=cart?cartPane:catalogPane;Scroll b={cart?605:398,p.y,p.h,scrollMax(cart),static_cast<int>(cart?BarterState.cartScroll:BarterState.catalogScroll),0,0};int track=b.h-22;b.thumb=max(22,track*p.h/(p.h+b.max));b.thumbY=b.y+11+(b.max?b.position*(track-b.thumb)/b.max:0);return b;}
static void scrollbar(bool cart){
    auto b=bar(cart);if(!b.max)return;panel(b.x,b.y,10,b.h,0xFFE3EAFA,0xFFBAC9E7);panel(b.x,b.thumbY,10,b.thumb,0xFF9EB6DF,0xFF849ECE);
    for(int i=0;i<2;++i){int y=i?b.y+b.h-11:b.y;panel(b.x,y,10,11,0xFFD7E5FA,0xFFA9BFDF);for(int row=0;row<3;++row)rect(b.x+4-row,y+(i?6-row:3+row),1+row*2,1,0xFF6685BE);}
}
EXPORT int __stdcall BarterHit(int x,int y){
    if(!BarterState.active)return 0;
    if(contains(x,y,600,1,17,16))return 1;
    if(contains(x,y,516,351,44,18))return 2;
    if(contains(x,y,464,351,44,18) && canBuy())return 3;
    if(BarterState.pending)return 0;
    for(int i=0;i<2;++i){auto b=bar(i!=0);if(b.max && contains(x,y,b.x,b.y,10,b.h))return (i?20:10)+(y<b.y+11?2:y>=b.y+b.h-11?3:0);}
    if(contains(x,y,catalogPane.x,catalogPane.y,catalogPane.w,catalogPane.h)){
        int top=catalogPane.y-BarterState.catalogScroll;
        for(u32 i=0;i<BarterState.count;i+=2){int h=rowHeight(i);for(u32 j=0;j<2 && i+j<BarterState.count;++j)if(recipe(i+j).stock && contains(x,y,42+j*179,top,172,h))return 1000+i+j;top+=h+7;}
    }
    if(contains(x,y,cartPane.x,cartPane.y,cartPane.w,cartPane.h)){
        int top=cartPane.y-BarterState.cartScroll;
        for(u32 i=0;i<BarterState.cartCount;++i){int h=cartHeight(i);if(contains(x,y,cartPane.x,top,182,h)){
            if(contains(x,y,518,top+h-50,20,20))return 10000+i*2;
            auto c=BarterState.cart[i];if(contains(x,y,576,top+h-50,20,20) && c.quantity<30000 && c.quantity<recipe(c.recipe).stock)return 10001+i*2;
        }top+=h+7;}
    }
    return 0;
}
EXPORT void __fastcall BarterDraw(void* w,void*){
    if(w!=BarterState.window || !BarterState.active || at<int>(w,0x14)!=619 || at<int>(w,0x18)!=410)return;
    if(!assets())return;
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);itemHitCount=0;clip={0,0,619,410};image(0,0,0);clampScroll();
    text("Barter",7,2,300,0x674623);mini(1,"x",600,0,17);
    char label[128];clip=catalogPane;int y=catalogPane.y-BarterState.catalogScroll;
    for(u32 row=0;row<BarterState.count;row+=2){int h=rowHeight(row);if(y>=clip.y+clip.h)break;
        if(y+h>clip.y)for(u32 j=0;j<2 && row+j<BarterState.count;++j){u32 i=row+j;auto r=recipe(i);int x=42+j*179;card(x,y,h);
            bool selected=false;for(u32 k=0;k<BarterState.cartCount;++k)if(BarterState.cart[k].recipe==i)selected=true;
            if(selected)border(x,y,172,h,0xFF8BAADB);
            icon(r.id,1,r.refine,x+7,y+6,false);name(label,r.id,r.refine);text(label,x+46,y+12,118);
            label[0]=0;if(r.stock==0xFFFFFFFF)append(label,"x1");else{append(label,"Stock: ");number(label,r.stock,true);}text(label,x+46,y+26,118,0x958A85);
            text(r.count>10?"Required items (more in list)":"Required items",x+7,y+51,158,0x9A8982);materials(i,1,x+7,y+67,10);price(r.zeny,x+7,y+h-38,156);
            if(!r.stock)text("Sold out",x+7,y+h-18,158,0x6566BA);else if(shortMaterials(i,1))text("Not enough materials",x+7,y+h-18,158,0x6566BA);
        }y+=h+7;
    }
    clip=cartPane;y=cartPane.y-BarterState.cartScroll;
    for(u32 i=0;i<BarterState.cartCount;++i){int h=cartHeight(i);if(y>=clip.y+clip.h)break;if(y+h>clip.y){auto c=BarterState.cart[i];auto r=recipe(c.recipe);int x=cartPane.x;card(x,y,h,182);
        icon(r.id,c.quantity,r.refine,x+7,y+6,false);name(label,r.id,r.refine);text(label,x+46,y+12,129);
        label[0]=0;append(label,"Receive x");number(label,c.quantity,true);text(label,x+46,y+26,129,0x958A85);
        text("Required items",x+7,y+51,160,0x9A8982);materials(c.recipe,c.quantity,x+7,y+67,r.count);
        text("Quantity",x+7,y+h-44,88,0x967E6F);mini(10000+i*2,"-",518,y+h-50,20,!BarterState.pending);
        panel(542,y+h-50,30,20,0xFFFFFFFF);label[0]=0;number(label,c.quantity);aligned(label,544,y+h-47,26,true);
        mini(10001+i*2,"+",576,y+h-50,20,!BarterState.pending && c.quantity<30000 && c.quantity<r.stock);
        u32 cost=0;if(multiply(r.zeny,c.quantity,cost))price(cost,x+7,y+h-25,168);else text("Amount too large",x+7,y+h-23,168,0x6566BA);
    }y+=h+7;}
    if(y<clip.y+clip.h && y+44>clip.y){card(cartPane.x,y,44,182);image(5,cartPane.x+6,y+6);text("Select an item",cartPane.x+46,y+17,129,0xAF9D92);}
    clip={0,0,619,410};scrollbar(false);scrollbar(true);
    u32 sum=0;bool valid=total(sum);image(6,436,324);label[0]=0;if(valid)number(label,sum,true);else append(label,"Too many");append(label," z");aligned(label,474,328,108,false);
    int state=canBuy()?(BarterState.hover==3?(BarterState.pressed==3?2:1):0):3;image(7+state,464,351);
    state=BarterState.hover==2?(BarterState.pressed==2?2:1):0;image(11+state,516,351);
    label[0]=0;append(label,"Zeny: ");number(label,*reinterpret_cast<u32*>(0x15FBA90),true);text(label,41,388,155,0xAB8873);
    const char* message=BarterState.pending && tick()-BarterState.sentAt>10000?"Awaiting server response; reopen the shop if needed.":BarterState.status;
    aligned(message,202,388,400,false,0x97857C);tooltip();
}
static void dragScroll(int y){bool cart=BarterState.dragging==3;auto b=bar(cart);int travel=b.h-22-b.thumb;u32& offset=cart?BarterState.cartScroll:BarterState.catalogScroll;if(travel>0)offset=min(max(0,y-b.y-11-BarterState.scrollGrab),travel)*b.max/travel;itemHitCount=0;BarterState.right=0;dirty();}
EXPORT void __fastcall BarterDown(void* w,void*,int x,int y){
    if(w!=BarterState.window || !BarterState.active)return;release();BarterState.hover=BarterState.pressed=BarterHit(x,y);
    int hit=BarterState.pressed;
    if(hit)reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);
    if(hit==10 || hit==20){auto b=bar(hit==20);BarterState.dragging=hit==20?3:2;BarterState.scrollGrab=y>=b.thumbY && y<b.thumbY+b.thumb?y-b.thumbY:b.thumb/2;dragScroll(y);}
    else if(!hit && y>=0 && y<18){BarterState.dragging=1;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880AD0)(w,x,y);}dirty();
}
EXPORT void __fastcall BarterUp(void*,void*,int x,int y){
    int hit=BarterHit(x,y),pressed=BarterState.pressed,drag=BarterState.dragging;release();if(drag>1 || !hit || hit!=pressed){dirty();return;}
    if(hit==1 || hit==2){hide(true);return;}if(hit==3)buy();
    else if(hit>=10000){BarterState.chosen=(hit-10000)/2;quantity((hit&1)!=0);clampScroll();}
    else if(hit>=1000)add(hit-1000);
    else if(hit==12 || hit==13 || hit==22 || hit==23)scrollBy(hit>=20,(hit%10==2?-1:1)*44);
    itemHitCount=0;BarterState.right=0;dirty();
}
EXPORT void __fastcall BarterMove(void*,void*,int x,int y){if(BarterState.dragging>1){dragScroll(y);return;}int hit=BarterHit(x,y);bool changed=x!=BarterState.mouseX || y!=BarterState.mouseY || hit!=BarterState.hover;BarterState.mouseX=x;BarterState.mouseY=y;BarterState.hover=hit;auto* h=itemHit(x,y);if(!h || h->id!=BarterState.rightId)BarterState.right=0;if(changed)dirty();}
EXPORT void __fastcall BarterDrag(void* w,void*,int x,int y){if(BarterState.dragging==1)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880E00)(w,x,y);else BarterMove(w,0,x,y);}
EXPORT void __fastcall BarterCursor(void* w,void*,int x,int y){
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA23470)(w,x,y);BarterMove(w,0,x,y);
    bool escape=key(27);if(escape && !escapeHeld && BarterState.active)hide(true);escapeHeld=escape;
    void* c=*reinterpret_cast<void**>(0x121333C);if(c)reinterpret_cast<void (__thiscall *)(void*,int)>(0xA764A0)(c,(BarterState.hover || itemHit(x,y))?2:0);
}
EXPORT void __fastcall BarterRightDown(void*,void*,int x,int y){BarterState.right=0;if(!BarterState.active || at<void*>((void*)0x131F4E8,0x19C))return;auto* h=itemHit(x,y);if(h){BarterState.right=1;BarterState.rightId=h->id;BarterState.rightEpoch=BarterState.epoch;}}
EXPORT void __fastcall BarterRightUp(void*,void*,int x,int y){auto* h=itemHit(x,y);bool inspect=BarterState.right && BarterState.rightEpoch==BarterState.epoch && h && h->id==BarterState.rightId;BarterState.right=0;if(inspect)BarterApi.describe(h->id);}
EXPORT void __fastcall BarterWheel(void*,void*,int delta){
    if(!BarterState.active || BarterState.pending || !delta)return;
    if(contains(BarterState.mouseX,BarterState.mouseY,42,24,366,350))scrollBy(false,delta>0?-44:44);
    else if(contains(BarterState.mouseX,BarterState.mouseY,421,55,194,260))scrollBy(true,delta>0?-44:44);
}
EXPORT void* __fastcall BarterDestroy(void* w,void*,int flags){hide(false);BarterState.window=0;for(int i=0;i<17;++i)textures[i]=0;return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);}
