// 2025-07-16: private skin around UIExchangeWnd's native trade state machine.
// No packet, inventory, currency balance, or shared item renderer writes.
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
extern "C" void* __cdecl memset(void*,int,unsigned int);
#pragma function(memset)
extern "C" void* __cdecl memset(void* p,int value,unsigned int n){auto* d=static_cast<volatile u8*>(p);while(n--)*d++=static_cast<u8>(value);return p;}
#define EXPORT extern "C" __declspec(dllexport)
struct Api {
    u32 version,vtable,editVtable;
    void (__stdcall *text)(void*,const char*,int,int,int,u32);
    void (__thiscall *png)(void*,int,int,void*,int);
    const char* paths[21];
};
static_assert(sizeof(Api)==104,"TradeUI API v1");
EXPORT Api TradeApi={1};
struct State {void* window;void* editor;int hover,pressed,dragging;u32 ready;};
EXPORT State TradeState={};
static void* textures[21];
static char numeric[32];
template<typename T>T& at(void* p,int n){return *reinterpret_cast<T*>(static_cast<u8*>(p)+n);}
static int length(const char* s){int n=0;while(s && s[n] && n<127)++n;return n;}
static const char* str(void* p,int n){return at<u32>(p,n+20)<16?static_cast<char*>(p)+n:at<const char*>(p,n);}
static void append(char* d,const char* s){int n=length(d);for(int i=0;s && s[i] && n<127;++i)d[n++]=s[i];d[n]=0;}
static void number(char* out,u32 v,bool commas=true){char t[20];int n=0,k=0;do{if(commas && k && k%3==0)t[n++]=',';t[n++]=static_cast<char>('0'+v%10);v/=10;++k;}while(v);while(n)*out++=t[--n];*out=0;}
EXPORT u32 __stdcall TradeFormat(const char* raw,char* out,u32 limit){
    u32 value=0;for(int i=0;raw && raw[i] && i<127;++i){if(raw[i]==',')continue;if(raw[i]<'0' || raw[i]>'9'){out[0]=0;return 0;}u32 d=raw[i]-'0';if(value>limit/10 || (value==limit/10 && d>limit%10)){value=limit;break;}value=value*10+d;}
    out[0]=0;if(raw && *raw)number(out,value);return value;
}
static int digits(const char* s,int end){int n=0;for(int i=0;i<end && s[i];++i)if(s[i]>='0' && s[i]<='9')++n;return n;}
static int position(const char* s,int count){if(!count)return 0;for(int i=0;s[i];++i)if(s[i]>='0' && s[i]<='9' && !--count)return i+1;return length(s);}
static void dirty(){if(TradeState.window)at<int>(TradeState.window,0x58)=1;}
static bool ownReady(void* w){return at<u32>(w,0xCC)!=0 || at<u32>(w,0xD4)!=0;}
static bool bothReady(void* w){return at<u32>(w,0xCC) && at<u32>(w,0xD0) && !at<u32>(w,0xD8);}
static void sync(){
    void* w=TradeState.window;void* e=TradeState.editor;
    if(!w || !e || ownReady(w) || at<void*>(w,0xC0)!=e || at<void*>((void*)0x131F4E8,0x1A0)!=e)return;
    void* input=*reinterpret_cast<void**>(0x159B80C);if(!input)return;
    const char* raw=str(input,0x34);char formatted[128];TradeFormat(raw,formatted,1000000000u);
    bool equal=length(raw)==length(formatted);for(int i=0;equal && formatted[i];++i)equal=raw[i]==formatted[i];
    if(!equal){int a=digits(raw,at<int>(input,0x50)),b=digits(raw,at<int>(input,0x54));at<int>(input,0x50)=0;at<int>(input,0x54)=length(raw);
        reinterpret_cast<void (__thiscall *)(void*,const char*)>(0xA6EA10)(input,formatted);
        at<int>(input,0x50)=position(formatted,a);at<int>(input,0x54)=position(formatted,b);at<int>(e,0x58)=1;dirty();}
}
// Only the two UIExchangeWnd submission call sites use this adapter. Stock
// validation and numeric conversion receive digits; other editors are untouched.
EXPORT const char* __fastcall TradeNumeric(void* edit,void*){
    sync();const char* raw=reinterpret_cast<const char* (__thiscall *)(void*)>(0x8210A0)(edit);
    char tmp[128];u32 value=TradeFormat(raw,tmp,1000000000u);number(numeric,value,false);return numeric;
}
static void layout(void* w){
    if(at<int>(w,0x14)!=548 || at<int>(w,0x18)!=428)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,548,428);
    for(int o=0xB4;o<=0xBC;o+=4){void* b=at<void*>(w,o);if(b)at<int>(b,0x28)=0;}
    if(void* b=at<void*>(w,0x118))at<int>(b,0x28)=0;
    if(void* e=at<void*>(w,0xC0)){
        TradeState.editor=e;at<u32>(e,0)=TradeApi.editVtable;at<int>(e,0x88)=13;
        at<int>(e,0x8C)=1;at<int>(e,0x90)=255;at<int>(e,0x94)=255;at<int>(e,0x98)=255;at<u32>(e,0xA8)=0x998D32;
        if(at<int>(e,0x14)!=140)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA1CB70)(e,140,16);
        at<int>(e,0x1C)=34;at<int>(e,0x20)=352;at<int>(e,0x28)=ownReady(w)?0:1;
    }
}
static bool assets(){
    static const int widths[]={548,262,262,262,262,262,262,132,132,56,56,56,56,44,44,44,44,44,44,44,44};
    static const int heights[]={428,355,355,355,355,355,355,10,10,18,18,18,18,18,18,18,18,18,18,18,18};
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return false;
    for(int i=0;i<21;++i){const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(TradeApi.paths[i]);if(!path)return false;
        void* t=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);
        if(!t || at<int>(t,0x114)!=widths[i] || at<int>(t,0x118)!=heights[i] || !at<void*>(t,0x11C))return false;textures[i]=t;
    }return true;
}
EXPORT void* __fastcall TradeConstruct(void* w,void*){
    // The registered exchange factory already allocates 0x14C bytes. The stock
    // UIExchangeWnd needs 0x13C, and consumes the same native trade messages.
    if(!assets())return reinterpret_cast<void* (__thiscall *)(void*)>(0x9CD970)(w);
    reinterpret_cast<void* (__thiscall *)(void*)>(0x88DA00)(w);at<u32>(w,0)=TradeApi.vtable;
    TradeState.window=w;TradeState.editor=0;TradeState.hover=TradeState.pressed=TradeState.dragging=0;TradeState.ready=1;return w;
}
EXPORT void __fastcall TradeCreate(void* w,void*,int x,int y){reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x8A6900)(w,x,y);TradeState.ready=2;layout(w);}
// CUI's factory expects a newer class: virtual slot 53 initializes it, then
// +B4/+B5/+D4 are read as CUI flags. UIExchangeWnd has only 53 slots and uses
// those fields for child pointers and trade state. Its private factory branch
// must perform the legacy lifecycle and skip ALL of those modern-only reads.
EXPORT void __fastcall TradeInitialize(void* w,void*,u32 id){
    at<u32>(w,0x2C)=id;
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,548,428);
    TradeCreate(w,0,548,428);
    void* screen=*reinterpret_cast<void**>(0x12515F8);
    int x=screen?(at<int>(screen,0x28)-548)/2:0,y=screen?(at<int>(screen,0x2C)-428)/2:0;
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x874AF0)(w,x>0?x:0,y>0?y:0);
}
EXPORT void __fastcall TradeProcess(void* w,void*){if(TradeState.ready==2){layout(w);sync();dirty();}}
EXPORT void __fastcall TradeEditDraw(void* e,void*){
    sync();
    // +F4 is VERTICAL padding: stock OnDraw sets text/caret Y (+B4) to F4+2.
    // Width-based padding pushed the entire number below this 16px editor.
    // Keep native horizontal positioning, selection and scrolling intact.
    at<int>(e,0xF4)=0;
    reinterpret_cast<void (__thiscall *)(void*)>(0x824FC0)(e);
}
static int event(void* w,void* sender,u32 message,u32 a,u32 b,u32 c,u32 d){return reinterpret_cast<int (__thiscall *)(void*,void*,u32,u32,u32,u32,u32)>(0x8C0EA0)(w,sender,message,a,b,c,d);}
static void action(void* w,int id){
    if(id==1 && !ownReady(w)){sync();event(w,0,6,0xB8,0,0,0);}
    else if(id==2 && bothReady(w))event(w,0,6,0xE6,0,0,0);
    else if(id==3)event(w,0,6,0xB9,0,0,0);
    else if(id==4){at<u8>(w,0x11C)=!at<u8>(w,0x11C);dirty();}
}
EXPORT int __fastcall TradeEditEvent(void* e,void*,void* sender,u32 msg,u32 a,u32 b,u32 c,u32 d){
    if(e==TradeState.editor && msg==0){if(TradeState.window)action(TradeState.window,1);return 1;}
    return reinterpret_cast<int (__thiscall *)(void*,void*,u32,u32,u32,u32,u32)>(0x82C4E0)(e,sender,msg,a,b,c,d);
}
EXPORT int __fastcall TradeEvent(void* w,void*,void* sender,u32 msg,u32 a,u32 b,u32 c,u32 d){
    int result=event(w,sender,msg,a,b,c,d);if(w==TradeState.window && TradeState.ready==2){layout(w);dirty();}return result;
}
static void png(void* w,int i,int x,int y){TradeApi.png(w,x,y,textures[i],0);}
static void text(void* w,const char* s,int x,int y,int width,u32 color=0x333333){TradeApi.text(w,s,x,y,width,color);}
static void rows(void* w,int list,int px){
    void* head=at<void*>(w,list);if(!head)return;void* node=at<void*>(head,0);
    for(int row=0;row<10 && node && node!=head;++row,node=at<void*>(node,0)){
        void* item=static_cast<u8*>(node)+8;int y=29+row*32;
        reinterpret_cast<void (__thiscall *)(void*,int,int,void*,int,int)>(0x8711A0)(w,px+14,y,item,0,0);
        // Preserve the stock CItem title/refine/card/grade producer and color.
        reinterpret_cast<void (__thiscall *)(void*,int,int,void*,int,int,int,int)>(0x8972C0)(w,px+54,y+10,item,0,0,12,1);
    }
}
static bool inside(int x,int y,int bx,int by,int width,int height){return x>=bx && y>=by && x<bx+width && y<by+height;}
EXPORT int __stdcall TradeHit(int x,int y){if(inside(x,y,14,385,44,18))return 1;if(inside(x,y,246,385,56,18))return 2;if(inside(x,y,490,385,44,18))return 3;if(inside(x,y,198,410,160,14))return 4;return 0;}
static int button(int base,int id,bool enabled){return base+(enabled?(TradeState.pressed==id?3:TradeState.hover==id?2:1):0);}
EXPORT void __fastcall TradeDraw(void* w,void*){
    layout(w);sync();reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);png(w,0,0,0);
    png(w,at<u32>(w,0xCC)?3:1,8,24);png(w,at<u32>(w,0xD0)?6:4,278,24);
    char title[128]="Trade : ";append(title,str(w,0xF0));int level=at<short>(w,0x10C);if(at<u32>(w,0x108)>0){append(title," Lv");char n[20];number(n,level>0?level:0,false);append(title,n);}text(w,title,14,3,520);
    rows(w,0xE0,8);rows(w,0xE8,278);
    char n[20];number(n,*reinterpret_cast<u32*>(0x15FF5B0));if(ownReady(w) || !at<void*>(w,0xC0))text(w,n,174-length(n)*6,354,142,0x998D32);
    number(n,*reinterpret_cast<u32*>(0x15FF5B4));text(w,n,444-length(n)*6,354,142,0x998D32);
    png(w,button(13,1,!ownReady(w)),14,385);png(w,button(9,2,bothReady(w)),246,385);png(w,button(17,3,true),490,385);
    // The ss PNG has a ten-pixel checkbox followed by its native strip. Clip it
    // to the checkbox and draw the translated label separately.
    static u32 saved[122*10];auto* pixels=at<u32*>(at<void*>(w,0x24),0x18);
    for(int y=0;y<10;++y)for(int x=0;x<122;++x)saved[y*122+x]=pixels[(413+y)*548+208+x];
    png(w,at<u8>(w,0x11C)?8:7,198,413);
    for(int y=0;y<10;++y)for(int x=0;x<122;++x)pixels[(413+y)*548+208+x]=saved[y*122+x];
    text(w,"Screenshot Trade",213,411,150,0x4444DD);
}
EXPORT void __fastcall TradeDown(void* w,void*,int x,int y){
    TradeState.hover=TradeState.pressed=TradeHit(x,y);dirty();if(TradeState.pressed){reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);return;}
    if(y<20){TradeState.dragging=1;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880AD0)(w,x,y);}
}
EXPORT void __fastcall TradeUp(void* w,void*,int x,int y){
    int pressed=TradeState.pressed;TradeState.pressed=0;
    if(TradeState.dragging){TradeState.dragging=0;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880BB0)(w,x,y);}
    if(at<void*>((void*)0x131F4E8,0x19C)==w)reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);
    if(pressed && pressed==TradeHit(x,y))action(w,pressed);dirty();
}
static void oldPoint(int& x,int& y){if(y>=29 && y<349 && ((x>=8 && x<270)||(x>=278 && x<540))){x=x<278?30:310;y=21+(y-29)/32*30;}else{x=0;y=0;}}
EXPORT void __fastcall TradeMove(void* w,void*,int x,int y){TradeState.hover=TradeHit(x,y);dirty();oldPoint(x,y);reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x8BA250)(w,x,y);}
EXPORT void __fastcall TradeRight(void* w,void*,int x,int y){oldPoint(x,y);reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x8BB400)(w,x,y);}
EXPORT void __fastcall TradeDrop(void* w,void*,int x,int y,void* item){if(inside(x,y,8,24,262,320) && !ownReady(w))reinterpret_cast<void (__thiscall *)(void*,int,int,void*)>(0x896110)(w,30,30,item);}
EXPORT void* __fastcall TradeDestroy(void* w,void*,int flags){if(w==TradeState.window){TradeState.window=TradeState.editor=0;TradeState.ready=0;}return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x892910)(w,flags);}
