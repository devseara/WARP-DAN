// 2025-07-16 Ragexe: private UINotifyItemObtainWnd display queue.
// Own pixels only. Native code retains ownership of every CItem and string.
typedef unsigned int u32;
typedef unsigned char u8;
#define EXPORT extern "C" __declspec(dllexport)
struct Api { u32 message, draw, tick, destroy; };
EXPORT Api LootApi = {};
static_assert(sizeof(Api)==16,"Loot API v1");
enum { MaxRows=5, MaxWidth=1024, RowHeight=32, RowStep=36, Lifetime=7000, Fade=3000 };
struct Row { u32 born, width; u32 pixels[MaxWidth*RowHeight]; };
struct State { void* owner; u32 count, pending, closing; u32 order[MaxRows]; };
EXPORT State LootState = {};
EXPORT Row LootRows[MaxRows] = {};
template<class T> static T& at(void* p,int off) { return *reinterpret_cast<T*>(static_cast<u8*>(p)+off); }
static u32 now() { return (*reinterpret_cast<u32 (__stdcall **)()>(0xFC17B0))(); }
static void reset(void* w) { LootState.owner=w; LootState.count=LootState.pending=LootState.closing=0; }
static void bind(void* w) { if(LootState.owner!=w)reset(w); }
static void dirty(void* w) { at<int>(w,0x58)=1; }
static void size(void* w,int width,int height) {
    if(at<int>(w,0x14)!=width || at<int>(w,0x18)!=height)
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,width,height);
}
static int screen(int off,int fallback) {
    void* r=*reinterpret_cast<void**>(0x12515F8);
    if(!r)return fallback;
    int v=at<int>(r,off);return v>=200 && v<=16384?v:fallback;
}
static int rowWidth(void* w) {
    int n=at<int>(w,0x14), limit=screen(0x28,800)-20;
    if(limit>MaxWidth)limit=MaxWidth;
    if(n<270)n=270;
    return n>limit?limit:n;
}
static void position(void* w) {
    const int h=screen(0x2C,600);
    int y=h/3, limit=h-(MaxRows*RowStep-4)-10;
    if(y>limit)y=limit;
    if(y<10)y=10;
    at<int>(w,0x1C)=10;at<int>(w,0x20)=y;
    at<u32>(w,0x38)=at<u32>(w,0x40)=255;
}
EXPORT void __fastcall LootPosition(void* w,void*,int,int) { position(w); }
static void expire(u32 time) {
    u32 out=0;
    for(u32 i=0;i<LootState.count;++i) {
        const u32 slot=LootState.order[i];
        if(time-LootRows[slot].born<Lifetime)LootState.order[out++]=slot;
    }
    LootState.count=out;
}
static void layout(void* w) {
    int width=270;
    for(u32 i=0;i<LootState.count;++i)if(static_cast<int>(LootRows[LootState.order[i]].width)>width)
        width=LootRows[LootState.order[i]].width;
    const int limit=screen(0x28,800)-20;
    if(width>limit)width=limit;
    size(w,width,LootState.count?LootState.count*RowStep-4:RowHeight);
    position(w);dirty(w);
}
static void capture(void* w) {
    size(w,rowWidth(w),RowHeight);
    void* surface=at<void*>(w,0x24);
    if(!surface || !at<void*>(surface,0x18))return;
    const int width=at<int>(surface,4),height=at<int>(surface,8);
    if(width<1 || width>MaxWidth || height!=RowHeight)return;
    u32* pixels=at<u32*>(surface,0x18);
    // Native color-key clear lets black GDI text remain distinguishable from
    // untouched transparent corners, before capturing the complete stock draw.
    for(int i=0;i<width*height;++i)pixels[i]=0x00FF00FF;
    reinterpret_cast<void (__thiscall *)(void*)>(LootApi.draw)(w);
    const u32 time=now();expire(time);
    u32 slot=MaxRows;
    for(u32 n=0;n<MaxRows && slot==MaxRows;++n) {
        bool used=false;
        for(u32 i=0;i<LootState.count;++i)if(LootState.order[i]==n)used=true;
        if(!used)slot=n;
    }
    if(slot==MaxRows)slot=LootState.order[MaxRows-1];
    if(LootState.count<MaxRows)++LootState.count;
    for(u32 i=LootState.count-1;i>0;--i)LootState.order[i]=LootState.order[i-1];
    LootState.order[0]=slot;
    Row& row=LootRows[slot];row.born=time;row.width=width;
    for(int i=0;i<width*height;++i) {
        u32 p=pixels[i];
        if((p&0xFFFFFF)==0xFF00FF)p=0;
        else if(!(p>>24))p|=0xFF000000; // Stock GDI text has zero alpha.
        row.pixels[i]=p;
    }
    at<u8>(surface,0x1C)=1;
    layout(w);
}
EXPORT int __fastcall LootMessage(void* w,void*,int a,int message,int c,int d,int e,int f) {
    bind(w);
    if(message==0x24) { // The native producer follows this with CItem message 0x22.
        LootState.pending=1;size(w,rowWidth(w),RowHeight);
    }
    const int result=reinterpret_cast<int (__thiscall *)(void*,int,int,int,int,int,int)>(LootApi.message)(w,a,message,c,d,e,f);
    if(message==0x22 && LootState.pending) {
        LootState.pending=0;capture(w);
    }
    position(w);
    return result;
}
EXPORT void __fastcall LootDraw(void* w,void*) {
    bind(w);
    if(!LootState.count) {
        if(LootState.pending)reinterpret_cast<void (__thiscall *)(void*)>(LootApi.draw)(w);
        return;
    }
    void* surface=at<void*>(w,0x24);
    if(!surface || !at<void*>(surface,0x18))return;
    const int width=at<int>(surface,4),height=at<int>(surface,8);
    if(width<1 || width>MaxWidth || height<1 || height>MaxRows*RowStep)return;
    u32* pixels=at<u32*>(surface,0x18);
    for(int i=0;i<width*height;++i)pixels[i]=0;
    const u32 time=now();
    for(u32 i=0;i<LootState.count;++i) {
        const Row& row=LootRows[LootState.order[i]];
        const u32 age=time-row.born;
        const u32 alpha=age>=Lifetime?0:age<=Lifetime-Fade?255:(Lifetime-age)*255/Fade;
        const int n=row.width<static_cast<u32>(width)?row.width:width;
        for(int y=0;y<RowHeight && static_cast<int>(i*RowStep)+y<height;++y)
            for(int x=0;x<n;++x) {
                const u32 p=row.pixels[y*row.width+x];
                pixels[(i*RowStep+y)*width+x]=(p&0xFFFFFF)|(((p>>24)*alpha/255)<<24);
            }
    }
    at<u8>(surface,0x1C)=1;at<u8>(surface,0x28)=1;
}
EXPORT void __fastcall LootTick(void* w,void*) {
    bind(w);if(LootState.closing)return;
    const u32 old=LootState.count;expire(now());
    if(old!=LootState.count)layout(w);
    else if(LootState.count)layout(w); // Respond to viewport width changes too.
    if(!LootState.count && !LootState.pending) {
        LootState.closing=1;
        // The native manager removes its singleton and defers destruction safely.
        reinterpret_cast<void (__thiscall *)(void*,int)>(0xA2E770)((void*)0x131F4E8,0x3A);
    }
}
EXPORT void* __fastcall LootDestroy(void* w,void*,int flags) {
    if(LootState.owner==w)reset(0);
    return reinterpret_cast<void* (__thiscall *)(void*,int)>(LootApi.destroy)(w,flags);
}
