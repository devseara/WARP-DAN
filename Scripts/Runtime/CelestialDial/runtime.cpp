// Import-free native UIWindow payload for the profiled 2025-07-16 client.
#include "world_environment_wire.hpp"
using namespace world_environment_wire;
#define EXPORT extern "C" __declspec(dllexport)
struct Api { u32 version, vtable, ctor, send; u32* monster_top; };
EXPORT Api CelestialApi = {1};
struct State {
    void* window;
    void* mode;
    void* world;
    u32 cookie, request, sequence, sent, received, frame_tick, retry_tick, pending;
    u32 ready, request_counter, cookie_counter, last_second;
    Snapshot p;
    u32 server_weather, weather_mask, protocol, sent_protocol;
    void* rain_effect;
    void* rain_player;
    u32 rain_generation, rain_received, rain_lease, rain_retry;
    u32 lighting_owned, lighting_original[3], lighting_applied[3];
    u32 flash_generation, flash_tick;
};
EXPORT State CelestialState = {};
// Private per-instance vtable: RTTI plus the 19 profiled CEffect slots.
EXPORT u32 CelestialRainVtable[20] = {};
EXPORT u32 CelestialRainPrimVtable[16] = {};
// MSVC's freestanding floating-point marker; no CRT initialization is required.
extern "C" { int _fltused = 0; }
constexpr int width = 280, height = 98, top = 8, monster_top = 114;
constexpr u32 stale_ms = 90000, resync_ms = 60000, retry_ms = 10000;
template<typename T> static T& at(void* p, int offset) { return *reinterpret_cast<T*>(static_cast<u8*>(p) + offset); }
static u32 tick() { return (*reinterpret_cast<u32 (__stdcall **)()>(0xFC17B0))(); }
static void copy(void* d, const void* s, u32 size) { auto* a=static_cast<volatile u8*>(d);auto* b=static_cast<const u8*>(s);for(u32 i=0;i<size;++i)a[i]=b[i]; }
#include "hud_interaction.inl"
static void hide() {
    releaseHudInput();
    if(CelestialState.window)at<int>(CelestialState.window,0x28)=0;
    if(CelestialApi.monster_top)*CelestialApi.monster_top=24;
}
static void restoreLighting() {
    auto& s=CelestialState;
    if(s.lighting_owned){
        // Restore only our exact last outputs; never overwrite another producer.
        for(int i=0;i<3;++i)if(at<u32>((void*)0x15C57D8,0x38+i*4)==s.lighting_applied[i])
            at<u32>((void*)0x15C57D8,0x38+i*4)=s.lighting_original[i];
        s.lighting_owned=0;
    }
}
EXPORT void __stdcall CelestialReset() {
    resetHud();
    restoreLighting();
    hide();
    CelestialState.mode=CelestialState.world=0;
    CelestialState.cookie=CelestialState.request=CelestialState.sequence=CelestialState.pending=CelestialState.ready=0;
    CelestialState.retry_tick=0;
    CelestialState.server_weather=CelestialState.weather_mask=CelestialState.protocol=CelestialState.sent_protocol=0;
    // The owned effect's update returns false after this reset. Native CWorld
    // then destroys it and CEffect removes its own actor-list entry.
    CelestialState.rain_effect=CelestialState.rain_player=0;
    CelestialState.rain_generation=CelestialState.rain_lease=CelestialState.rain_retry=0;
    CelestialState.flash_generation=CelestialState.flash_tick=0;
    // Monotonic request/cookie counters survive map changes and native destruction.
}
static bool send(u32 now) {
    CelestialState.retry_tick=now;
    void* transport=reinterpret_cast<void* (__cdecl *)()>(CelestialApi.ctor)();
    if(!transport)return false;
    if(++CelestialState.request_counter==0)++CelestialState.request_counter;
    const u16 protocol=CelestialState.protocol?static_cast<u16>(CelestialState.protocol):version;
    Request r={request_id,sizeof(Request),magic,protocol,0,CelestialState.cookie,CelestialState.request_counter,now};
    CelestialState.sent_protocol=protocol;
    CelestialState.request=r.request;CelestialState.sent=now;CelestialState.pending=1;
    reinterpret_cast<void (__thiscall *)(void*,int,const void*)>(CelestialApi.send)(transport,sizeof(r),&r);
    return true;
}
// A 64-bit epoch modulo one day, without a CRT 64-bit division import.
static u32 secondsOfDay(u32 high,u32 low) {
    u32 value=0;
    for(int i=63;i>=0;--i){value=value*2+((i>=32?high>>(i-32):low>>i)&1);if(value>=86400)value-=86400;}
    return value;
}
static u32 currentSeconds(u32 now) {
    const auto& p=CelestialState.p;
    const int offset=static_cast<int>(p.utc_offset_minutes)*60;
    int value=static_cast<int>(secondsOfDay(p.unix_high,p.unix_low))+offset+static_cast<int>((now-CelestialState.received)/1000);
    while(value<0)value+=86400;
    return static_cast<u32>(value)%86400;
}
static void digits(char* s,u32 v,int n) { for(int i=n-1;i>=0;--i){s[i]=static_cast<char>('0'+v%10);v/=10;} }
static void clockText(char* s,u32 seconds) { digits(s,seconds/3600,2);s[2]=':';digits(s+3,seconds/60%60,2);s[5]=':';digits(s+6,seconds%60,2);s[8]=0; }
static void dirty() { if(CelestialState.window)at<int>(CelestialState.window,0x58)=1; }
EXPORT int __stdcall CelestialReceive(const Snapshot* p) {
    auto& s=CelestialState;
    if(!p || p->id!=snapshot_id || p->signature!=magic ||
        !((p->protocol==legacy_version && p->length==sizeof(Snapshot)) || (p->protocol==weather_version && p->length==sizeof(WeatherSnapshot)) ||
          ((p->protocol>=rain_version && p->protocol<=version) && p->length==sizeof(RainSnapshot))) ||
        !s.cookie || !s.mode || !s.world || p->cookie!=s.cookie || !p->sequence ||
        (s.sequence && static_cast<int>(p->sequence-s.sequence)<=0) || (p->flags&~(p->protocol>=version?7:3)) || p->phase>1 || p->local_night>1 ||
        p->local_night!=static_cast<u8>(p->phase && (p->flags&NightEnabled)) ||
        p->utc_offset_minutes < -840 || p->utc_offset_minutes > 840 || p->map_name[15]!=0 ||
        ((p->flags&Scheduled) ? (!p->duration_ms || p->duration_ms>0x7fffffff || p->remaining_ms>0x7fffffff) : (p->duration_ms || p->remaining_ms)))return 0;
    const u32 weather=p->protocol>=weather_version?reinterpret_cast<const WeatherSnapshot*>(p)->weather_mask:0;
    if(weather&~(server_weather_mask|(p->protocol>=rain_version?Rain:0)|(p->protocol>=storm_version?Thunderstorm:0)|
        (p->protocol>=flash_version?LightningFlash:0)))return 0;
    if((weather&Thunderstorm) && !(weather&Rain))return 0;
    if((weather&LightningFlash) && !(weather&Thunderstorm))return 0;
    const RainSnapshot* rain=p->protocol>=rain_version?reinterpret_cast<const RainSnapshot*>(p):0;
    if(rain && (!rain->rain_generation || rain->rain_remaining_ms>300000 ||
        (bool(weather&Rain)!=bool(rain->rain_remaining_ms))))return 0;
    if((weather&Rain) && p->protocol>=version && !(p->flags&ManagedWeather))return 0;
    if((weather&Rain) && p->protocol<version && (p->map_name[0]!='p' || p->map_name[1]!='r' || p->map_name[2]!='t' || p->map_name[3]!='_' ||
        p->map_name[4]!='f' || p->map_name[5]!='i' || p->map_name[6]!='l' || p->map_name[7]!='d' ||
        p->map_name[8]!='0' || p->map_name[9]!='8' || p->map_name[10]!=0))return 0;
    const u32 now=tick();
    // Only the outstanding echoed request may adjust clock latency. Pushes use zero.
    if(p->request && (!s.pending || p->request!=s.request || p->client_tick!=s.sent || now-s.sent>retry_ms))return 0;
    if(!p->request && !s.ready)return 0;
    u32 latency=p->request?(now-s.sent)/2:0;
    if(latency>2000)latency=2000;
    copy(&s.p,p,sizeof(Snapshot));s.sequence=p->sequence;s.received=now-latency;s.ready=1;
    s.server_weather=weather;s.protocol=p->protocol;
    s.rain_generation=rain?rain->rain_generation:0;s.rain_received=now;
    s.rain_lease=rain?(rain->rain_remaining_ms<5000?rain->rain_remaining_ms:5000):0;
    if((weather&LightningFlash) && rain && s.flash_generation!=rain->rain_generation){
        s.flash_generation=rain->rain_generation;s.flash_tick=now;
    }
    if(p->request)s.pending=0;
    s.last_second=0xffffffff;dirty();return 1;
}
static bool member(void* player,void* effect) {
    if(!player || !effect)return false;
    const u32 count=at<u32>(player,0x148);void* head=at<void*>(player,0x144);
    if(!head || count>1024)return false;
    void* node=at<void*>(head,0);
    for(u32 i=0;i<count && node && node!=head;++i,node=at<void*>(node,0))if(at<void*>(node,8)==effect)return true;
    return false;
}
static bool rainActive(u32 now) {
    const auto& s=CelestialState;
    return s.ready && (s.server_weather&Rain) && s.rain_lease && now-s.rain_received<s.rain_lease;
}
EXPORT void __fastcall CelestialWeatherProcess(void* weather,void*) {
    // Profiled native CWeather::Process always recomputes these RGB outputs.
    // This wrapper runs before terrain/model queues consume them, not over UI.
    reinterpret_cast<void (__thiscall *)(void*)>(0xC136A0)(weather);
    auto& s=CelestialState;s.lighting_owned=0;
    const u32 now=tick();
    if(weather!=(void*)0x15C57D8 || !s.ready || !s.mode || !s.world ||
        at<void*>(s.mode,0xCC)!=s.world || now-s.received>=stale_ms)return;
    const bool night=s.p.local_night!=0;
    const bool storm=rainActive(now) && (s.server_weather&Thunderstorm);
    if(!night && !storm)return;
    static const float nightCaps[3]={0.34f,0.39f,0.48f};
    static const float stormCaps[3]={0.72f,0.76f,0.82f};
    static const float flashCaps[3]={0.94f,0.97f,1.0f};
    const u32 age=now-s.flash_tick;
    const float flash=storm && (s.server_weather&LightningFlash) && age<350?
        (age<45?static_cast<float>(age)/45.0f:static_cast<float>(350-age)/305.0f):0.0f;
    // Keep the native address separate from payload-relative addresses so MSVC
    // cannot encode a negative external-address addend in a payload relocation.
    void* volatile channels=weather;
    for(int i=0;i<3;++i){
        float& value=at<float>(channels,0x38+i*4);
        s.lighting_original[i]=at<u32>(channels,0x38+i*4);
        const float cap=night?nightCaps[i]:stormCaps[i];
        if(value>=0.0f && value<=1.0f && value>cap)value=cap;
        if(value>=0.0f && value<=1.0f && flash>0)value+=(flashCaps[i]-value)*flash;
        s.lighting_applied[i]=at<u32>(channels,0x38+i*4);
    }
    s.lighting_owned=1;
}
#include "rain_ground.inl"
#include "sun_shadow.inl"
EXPORT int __fastcall CelestialRainProcess(void* effect,void*) {
    auto& s=CelestialState;
    // Returning false uses CWorld's native destruction path (A6BAE8..A6BB70).
    // Never free/unlink effects here or send actor-wide remove-effect messages.
    if(s.rain_effect!=effect || !rainActive(tick()) || !s.world ||
        at<void*>(s.world,0x2C)!=s.rain_player)return 0;
    const int alive=reinterpret_cast<int (__thiscall *)(void*)>(0xBC4C70)(effect);
    if(!(alive&255))s.rain_effect=0;
    return alive;
}
EXPORT int __fastcall CelestialRainParticles(void* effect,void*) {
    // EF_RAIN_PARTICLE normally uses a lightning bitmap in this build. Replace
    // only this instance's particle step; texture, children and cleanup remain
    // owned by the stock emitter. No shared resource or native vtable is edited.
    const u32 age=at<u32>(effect,0x178);
    if(age>=1000 || age%10)return 1;
    // CPrim type 157 owns four billboard particles at +3E8, stride B4. Its
    // stock renderer selects white for palette 0 and red/amber for 1/2. Its
    // update adds +08 to vertical offset +88 until ground, then fades alpha.
    // Float constants are stored as IEEE-754 bits to retain the CRT-free ABI.
    static const u32 radii[]={0x42340000,0x428C0000,0x42C80000,0x43020000,0x43200000,0x433E0000,0x435C0000,0x43820000}; // 45..260 world units.
    static const u32 heights[]={0xC2A00000,0xC2C00000,0xC2E00000,0xC3000000,0xC3100000,0xC3200000,0xC3300000,0xC3400000}; // -80..-192.
    for(u32 batch=0;batch<12;++batch){
        void* prior=at<void*>(effect,0x11C84);
        reinterpret_cast<void (__thiscall *)(void*,const char*,int)>(0xC0D5B0)(effect,"effect\\boh_rain_prototype.bmp",0);
        void* child=at<void*>(effect,0x11C84);
        if(!child || child==prior || at<void*>(child,0x140)!=effect || at<u32>(child,0x1D0)!=157)continue;
        rainGroundAttach(child);
        at<u32>(child,0x1E4)=72; // Native lifetime caps allocation at roughly 1.2 seconds.
        for(u32 i=0;i<4;++i){
            u32 seed=age*1013904223u+batch*374761393u+i*668265263u+CelestialState.cookie;
            seed=(seed^(seed>>13))*1274126177u;seed^=seed>>16;
            void* p=static_cast<u8*>(child)+0x3E8+i*0xB4;
            at<u16>(p,2)=rainDropAlpha; // Readable rain against bright outdoor terrain.
            at<u16>(p,6)=static_cast<u16>(seed%360);
            at<u32>(p,8)=0x40B00000; // 5.5 world units downward per native tick.
            at<u32>(p,0x14)=radii[(seed>>16)&7];
            at<u8>(p,0x68)=0; // White, never the stock red/amber palettes.
            at<u32>(p,0x80)=(seed&8)?0x40200000:0x40000000; // 2.0 / 2.5 streak size.
            at<u32>(p,0x88)=heights[(seed>>20)&7];
        }
    }
    // CEffect::Process tests this virtual step's AL result before advancing age.
    // The stock dispatcher ends at BC2DE1 with MOV AL,1. The emitter itself is
    // void; forwarding its unspecified EAX retires the parent on its first tick.
    return 1;
}
static void rainFrame(void* player,u32 now) {
    auto& s=CelestialState;
    if(!rainActive(now)){s.rain_effect=s.rain_player=0;return;}
    if(s.rain_effect && s.rain_player==player && member(player,s.rain_effect) &&
        at<u32>(s.rain_effect,0)==reinterpret_cast<u32>(CelestialRainVtable+1))return;
    s.rain_effect=s.rain_player=0;
    if(s.rain_retry && now-s.rain_retry<1000)return;
    s.rain_retry=now;
    // Same CActor factory and zero offset as ZC_NOTIFY_EFFECT2's fallback.
    // Four zero DWORDs are the exact +0.0f argument representation; this payload
    // does not need floating-point operations or a CRT _fltused definition.
    void* effect=reinterpret_cast<void* (__thiscall *)(void*,u32,u32,u32,u32,u32)>(0xC44540)(player,857,0,0,0,0);
    if(!effect)return;
    if(!CelestialRainVtable[1]){
        copy(CelestialRainVtable,reinterpret_cast<void*>(0x1088DE8-4),sizeof(CelestialRainVtable));
        CelestialRainVtable[2]=reinterpret_cast<u32>(&CelestialRainProcess);
        CelestialRainVtable[16]=reinterpret_cast<u32>(&CelestialRainParticles);
    }
    at<u32>(effect,0)=reinterpret_cast<u32>(CelestialRainVtable+1);
    s.rain_effect=effect;s.rain_player=player;
}
static u32 nativeWeather(void* player) {
    // CWeather owns only its ambient effect here; never inspect arbitrary combat
    // effects. The current actor's native list must still contain that exact effect.
    void* weather=reinterpret_cast<void*>(0x15C57D8);
    void* effect=at<void*>(weather,0x44);
    if(!player || !effect || at<void*>(weather,0x10)!=player)return 0;
    const u32 count=at<u32>(player,0x148);
    if(!count)return 0;
    if(count>1024)return Ambient;
    void* head=at<void*>(player,0x144);if(!head)return Ambient;
    void* node=at<void*>(head,0);
    for(u32 i=0;i<count && node && node!=head;++i,node=at<void*>(node,0)){
        if(at<void*>(node,8)!=effect)continue;
        // CEffect::Init stores the supplied effect number at +0x168 (BB418A).
        switch(at<u32>(effect,0x168)){
            case 162:return Snow;
            case 163:return Petals;
            case 333:return Leaves;
            case 515:case 592:return Fog;
            case 229:case 230:case 233:case 516:case 697:case 698:case 945:return Clouds;
            case 297:case 301:return Fireworks;
            default:return Ambient;
        }
    }
    return 0; // Removed/stale effects do not identify the new map's weather.
}
EXPORT void __stdcall CelestialFrame(void* mode) {
    auto& s=CelestialState;const u32 now=tick();
    // This bridge runs only from CGameMode, before native UIWindowMgr drawing.
    if(!mode || at<u32>(mode,0)!=0x10904B8 || !at<void*>(mode,0xCC) || !at<void*>(at<void*>(mode,0xCC),0x2C)) { CelestialReset();return; }
    void* world=at<void*>(mode,0xCC);
    if(s.mode!=mode || s.world!=world || !s.cookie){
        CelestialReset();s.mode=mode;s.world=world;
        if(++s.cookie_counter==0)++s.cookie_counter;
        s.cookie=s.cookie_counter;
        send(now);
    }
    s.frame_tick=now;
    if(s.pending && now-s.sent>=retry_ms){
        s.pending=0;
        if(!s.ready && s.sent_protocol>legacy_version)s.protocol=s.sent_protocol-1;
    }
    if(!s.pending && (s.ready ? now-s.received>=resync_ms && now-s.retry_tick>=retry_ms : now-s.retry_tick>=retry_ms))send(now);
    rainFrame(at<void*>(s.world,0x2C),now);
    if(!s.ready || now-s.received>=stale_ms){hide();return;}
    void* renderer=*reinterpret_cast<void**>(0x12515F8);
    if(!renderer || at<int>(renderer,0x28)<width || at<int>(renderer,0x2C)<height+top){hide();return;}
    const u32 weather=(s.server_weather&~(Rain|Thunderstorm|LightningFlash))|
        (rainActive(now)?(s.server_weather&(Rain|Thunderstorm|LightningFlash)):0)|nativeWeather(at<void*>(s.world,0x2C));
    if(s.weather_mask!=weather){s.weather_mask=weather;dirty();}
    if(!s.window){
        void* w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0x7C);if(!w)return;
        reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1B190)(w,0);
        at<u32>(w,0)=CelestialApi.vtable;s.window=w;
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,width,height);
        at<int>(w,0x2C)=0x3FE; // Separate from Barter (3E9), VIP (3FC/3FD), Gacha (3FB).
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA2D240)((void*)0x131F4E8,w);
    }
    const int x=(at<int>(renderer,0x28)-width)/2;
    if(at<int>(s.window,0x1C)!=x || at<int>(s.window,0x20)!=top){
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA23450)(s.window,x,top);dirty();
    }
    const u32 second=currentSeconds(now);
    if(second!=s.last_second){s.last_second=second;dirty();}
    at<int>(s.window,0x28)=1;
    if(CelestialHudState.pressed && at<void*>((void*)0x131F4E8,0x19C)!=s.window)CelestialHudState.pressed=0;
    if(animateHud(now))dirty();
    if(CelestialApi.monster_top)*CelestialApi.monster_top=86+28*CelestialHudState.progress/1000;
}
static void pixel(int x,int y,u32 color) {
    void* w=CelestialState.window;if(!w)return;void* surface=at<void*>(w,0x24);
    if(!surface || !at<void*>(surface,0x18))return;
    const int sw=at<int>(surface,4),sh=at<int>(surface,8);
    if(x<0 || y<0 || x>=sw || y>=sh)return;
    at<u32*>(surface,0x18)[y*sw+x]=color;
}
static void rect(int x,int y,int w,int h,u32 color) { for(int row=y;row<y+h;++row)for(int col=x;col<x+w;++col)pixel(col,row,color); }
static void text(const char* value,int x,int y,int size,u32 rgb) {
    int n=0;while(value[n] && n<95)++n;
    // Native TextDraw uses COLORREF; alpha is repaired only on this private canvas.
    const u32 color=((rgb&255)<<16)|(rgb&0xff00)|((rgb>>16)&255);
    reinterpret_cast<void (__thiscall *)(void*,int,int,const char*,int,int,int,u32,int,int)>(0xA25A70)(CelestialState.window,x,y,value,n,0,size,color,0,0);
}
static int textWidth(const char* value,int size) {
    int n=0;while(value[n] && n<95)++n;
    return reinterpret_cast<int (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA21C90)(CelestialState.window,value,n,0,size,0,0);
}
static void centered(const char* value,int x,int y,int span,int size,u32 rgb) {
    const int used=textWidth(value,size);text(value,x+(span-used)/2,y,size,rgb);
}
static void panel(int x,int y,int w,int h) {
    rect(x+2,y,w-4,h,0xFF91A3BC);rect(x,y+2,w,h-4,0xFF91A3BC);
    rect(x+1,y+3,w-2,h-6,0xFFF2F4F8);rect(x+3,y+1,w-6,h-2,0xFFF2F4F8);
    rect(x+2,y+3,w-4,12,0xFFE1EAF6);rect(x+3,y+1,w-6,1,0xFFFFFFFF);
}
static u32 shade(u32 a,u32 b,int weight) {
    if(weight<0)weight=0;if(weight>255)weight=255;
    u32 value=0xFF000000;
    for(int shift=0;shift<24;shift+=8)value|=(((((a>>shift)&255)*(255-weight)+((b>>shift)&255)*weight+127)/255)<<shift);
    return value;
}
#include "weather_art.inl"
static bool sunShape(int x,int y) {
    if(x*x+y*y<=144)return true;
    const int ax=x<0?-x:x,ay=y<0?-y:y;
    if(ay>=12 && ay<=24 && ax*3<=25-ay)return true;
    if(ax>=12 && ax<=24 && ay*3<=25-ax)return true;
    const int sum=ax+ay,diff=ax>ay?ax-ay:ay-ax;
    return ax>=6 && ay>=6 && sum>=18 && sum<=35 && diff*3<=37-sum;
}
static bool moonShape(int x,int y) {
    return (x+3)*(x+3)+y*y<=361 && (x-7)*(x-7)+(y+6)*(y+6)>324;
}
static void medallion(bool night,u32 filled) {
    // Native-size artwork: a silver bezel and sky inset surround a much larger,
    // faceted sun or shaded crescent. No fonts, assets or weather APIs are involved.
    for(int y=-35;y<=35;++y)for(int x=-35;x<=35;++x){
        const int d=x*x+y*y;if(d>36*36)continue;
        // 4x4 coverage for both circular bezel edges. Interior artwork is exact.
        if(d>=29*29){
            u32 red=0,green=0,blue=0,covered=0;
            for(int sy=-3;sy<=3;sy+=2)for(int sx=-3;sx<=3;sx+=2){
                const int xx=x*8+sx,yy=y*8+sy,dd=xx*xx+yy*yy;if(dd>34*34*64)continue;
                u32 c=0xFF53677F;
                if(dd<33*33*64)c=shade(0xFFF5FAFF,0xFF91ABC5,(y+34)*255/68);
                if(dd<31*31*64)c=night?0xFF718CAC:0xFFBDA16C;
                if(dd<30*30*64)c=shade(night?0xFF233752:0xFFF0F7FD,night?0xFF596E8D:0xFFBDD8E5,(y+30)*255/60);
                ++covered;red+=(c>>16)&255;green+=(c>>8)&255;blue+=c&255;
            }
            if(covered){
                const u32 a=covered*255/16;void* surface=at<void*>(CelestialState.window,0x24);
                const u32 below=at<u32*>(surface,0x18)[(35+y)*width+140+x],ba=below>>24;
                const u32 outA=a+ba*(255-a)/255;
                u32 c=outA<<24;const u32 rgb=(red/covered<<16)|(green/covered<<8)|(blue/covered);
                for(int shift=0;shift<24;shift+=8)c|=(((((rgb>>shift)&255)*a+((below>>shift)&255)*ba*(255-a)/255)/outA)<<shift);
                pixel(140+x,35+y,c);
            }
            continue;
        }
        u32 color=0xFF53677F;
        if(d<33*33)color=shade(0xFFF5FAFF,0xFF91ABC5,(y+34)*255/68);
        if(d<31*31)color=night?0xFF718CAC:0xFFBDA16C;
        if(d<30*30)color=shade(night?0xFF233752:0xFFF0F7FD,night?0xFF596E8D:0xFFBDD8E5,(y+30)*255/60);
        if(!night && d<28*28){const int halo=x*x+(y+2)*(y+2);if(halo<400)color=shade(color,0xFFFFE9AD,(400-halo)/5);}
        pixel(140+x,35+y,color);
    }
    // Sixty small marks avoid floating point or trig runtime dependencies.
    static const short points[60][2]={
        {0,-32},{3,-32},{7,-31},{10,-30},{13,-29},{16,-28},{19,-26},{21,-24},{24,-21},{26,-19},
        {28,-16},{29,-13},{30,-10},{31,-7},{32,-3},{32,0},{32,3},{31,7},{30,10},{29,13},
        {28,16},{26,19},{24,21},{21,24},{19,26},{16,28},{13,29},{10,30},{7,31},{3,32},
        {0,32},{-3,32},{-7,31},{-10,30},{-13,29},{-16,28},{-19,26},{-21,24},{-24,21},{-26,19},
        {-28,16},{-29,13},{-30,10},{-31,7},{-32,3},{-32,0},{-32,-3},{-31,-7},{-30,-10},{-29,-13},
        {-28,-16},{-26,-19},{-24,-21},{-21,-24},{-19,-26},{-16,-28},{-13,-29},{-10,-30},{-7,-31},{-3,-32}
    };
    // A fixed phase keeps a continuous clean rim; only real progress adds marks.
    for(u32 i=0;i<filled && i<60;++i)rect(139+points[i][0],34+points[i][1],2,2,night?0xFFD6E8FF:0xFFE7B950);
    if(night){
        for(int y=-21;y<=21;++y)for(int x=-24;x<=24;++x){
            const bool ink=moonShape(x,y);
            if(!ink){
                if(moonShape(x-1,y)||moonShape(x+1,y)||moonShape(x,y-1)||moonShape(x,y+1))pixel(140+x,35+y,0xFF172D49);
                continue;
            }
            u32 color=shade(0xFFFAFDFF,0xFF91B4D8,(x+y+24)*255/55);
            const int outer=(x+3)*(x+3)+y*y;
            if(outer>305 && x+y<0)color=0xFFF5FBFF;
            if((x+13)*(x+13)+(y-1)*(y-1)<=5)color=0xFF9CBAD8;
            if((x+10)*(x+10)+(y-10)*(y-10)<=2)color=0xFFB1CBE4;
            pixel(140+x,35+y,color);
        }
        // Small four-point stars balance the crescent without a face or text.
        static const short stars[3][3]={{12,-11,4},{18,3,3},{9,14,2}};
        for(int i=0;i<3;++i){const int sx=140+stars[i][0],sy=35+stars[i][1],r=stars[i][2];
            for(int p=-r;p<=r;++p){pixel(sx+p,sy,0xFFCCAE70);pixel(sx,sy+p,0xFFCCAE70);}
            rect(sx-1,sy-1,3,3,0xFFFFEDBC);pixel(sx,sy,0xFFFFFFF0);
        }
    }else{
        for(int y=-25;y<=25;++y)for(int x=-25;x<=25;++x){
            const bool ink=sunShape(x,y);
            if(!ink){
                if(sunShape(x-1,y)||sunShape(x+1,y)||sunShape(x,y-1)||sunShape(x,y+1))pixel(140+x,35+y,0xFF95692E);
                continue;
            }
            const int d=x*x+y*y;
            u32 color=shade(0xFFFFE7A0,0xFFD4932D,(x+y+30)*255/60);
            if(d<=144){
                color=shade(0xFFFFECA4,0xFFF0B846,(x+y+18)*255/36);
                if(d>=112)color=x+y<0?0xFFFFF0B2:0xFFC28A2B;
                else if(x-y>5)color=shade(color,0xFFE5A83C,55);
                if((x+4)*(x+4)+(y+5)*(y+5)<=8)color=0xFFFFF3BF;
            }
            pixel(140+x,35+y,color);
        }
    }
}
static void weatherText(char* out,u32 mask) {
    static const char* names[]={"Snow","Clouds","Fog","Petals","Leaves","Fireworks","Ambient","Rain","Storm"};
    int first=-1,second=-1,count=0;
    // Managed rain takes display priority while retaining concurrent native weather.
    if(mask&Thunderstorm){first=8;count=1;}
    else if(mask&Rain){first=7;count=1;}
    for(int i=0;i<7;++i)if(mask&(1u<<i)){if(first<0)first=i;else if(second<0)second=i;++count;}
    if(first<0){copy(out,"Clear",6);return;}
    int n=0;const char* a=names[first];while(*a)out[n++]=*a++;
    if(count>1){out[n++]=' ';out[n++]='+';
        if(count==2){out[n++]=' ';a=names[second];while(*a && n<30)out[n++]=*a++;}
        else out[n++]=static_cast<char>('0'+count-1);
    }
    out[n]=0;
}
static void weatherIcon(u32 mask,bool night,int center) {
    const u32 blue=0xFF6888AD;
    if(!mask){
        for(int y=-4;y<=4;++y)for(int x=-4;x<=4;++x)
            if(x*x+y*y<=16 && (!night || (x-2)*(x-2)+(y+2)*(y+2)>12))pixel(center+x,84+y,night?blue:0xFFC9993D);
    }else if(mask&Thunderstorm){
        rect(center-6,79,12,3,blue);
        for(int y=82;y<=89;++y)rect(center-(y-82)/2,y,3,1,0xFFC69A42);
    }else if(mask&Rain){
        rect(center-6,79,12,3,blue);
        for(int i=0;i<3;++i){pixel(center-4+i*4,85,blue);pixel(center-5+i*4,86,blue);pixel(center-5+i*4,87,blue);}
    }else if(mask&Snow){
        for(int i=-5;i<=5;++i){pixel(center+i,84,blue);pixel(center,84+i,blue);}
        for(int i=-3;i<=3;++i){pixel(center+i,84+i,blue);pixel(center-i,84+i,blue);}
    }else if(mask&Fog){
        rect(center-6,80,12,1,blue);rect(center-4,84,11,1,blue);rect(center-7,88,12,1,blue);
    }else if(mask&(Petals|Leaves)){
        for(int y=-5;y<=5;++y)for(int x=-4;x<=4;++x)if(x*x+y*y<24)pixel(center+x,84+y,mask&Petals?0xFFC18BA8:0xFFB59153);
        for(int i=-4;i<=4;++i)pixel(center,84+i,0xFF80674C);
    }else{
        for(int y=-4;y<=4;++y)for(int x=-7;x<=7;++x)
            if((x+3)*(x+3)+y*y<10 || (x-1)*(x-1)+(y+2)*(y+2)<15 || (x-5)*(x-5)+y*y<8)pixel(center+x,84+y,blue);
        rect(center-6,84,12,3,blue);
    }
}
EXPORT void __fastcall CelestialDraw(void* w,void*) {
    auto& s=CelestialState;const u32 now=tick();
    if(w!=s.window || !s.ready || now-s.received>=stale_ms || now-s.frame_tick>1000)return;
    if(at<int>(w,0x14)!=width || at<int>(w,0x18)!=height)return;
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    panel(2,16,276,47);
    centered("WORLD",2,21,103,10,0x66758B);centered(s.p.phase?"Night":"Day",2,35,103,13,0x35435A);
    centered("SERVER TIME",175,21,103,10,0x66758B);
    char clock[9];clockText(clock,currentSeconds(now));centered(clock,175,35,103,13,0x35435A);
    char zone[10]="UTC+00:00";int offset=s.p.utc_offset_minutes;
    if(offset<0){zone[3]='-';offset=-offset;}
    digits(zone+4,static_cast<u32>(offset)/60,2);digits(zone+7,static_cast<u32>(offset)%60,2);centered(zone,175,50,103,10,0x66758B);
    u32 filled=0;char next[96];copy(next,"No scheduled change",20);
    if(s.p.flags&Scheduled){
        const u32 elapsed=now-s.received;
        const u32 remaining=s.p.remaining_ms>elapsed?s.p.remaining_ms-elapsed:0;
        const u32 step=s.p.duration_ms/60?s.p.duration_ms/60:1;
        const u32 left=remaining/step;filled=left<60?60-left:0;
        if(!remaining)copy(next,"Awaiting server phase",22);
        else{
            const char* lead=s.p.phase?"Day in ":"Night in ";u32 n=0;while(lead[n]){next[n]=lead[n];++n;}
            const u32 seconds=(remaining+999)/1000;
            // Native battle timers can exceed 99 minutes; show an explicit hour field.
            if(seconds>=3600){clockText(next+n,seconds>359999?359999:seconds);}
            else{digits(next+n,seconds/60,2);next[n+2]=':';digits(next+n+3,seconds%60,2);next[n+5]=0;}
        }
    }
    panel(2,74,276,21);
    char condition[32];weatherText(condition,s.weather_mask);
    const int conditionX=2+(138-textWidth(condition,11)-20)/2;
    weatherIcon(s.weather_mask,s.p.phase!=0,conditionX+6);
    text(condition,conditionX+20,78,11,0x5B6B80);rect(140,78,1,13,0xFFD0DBE8);centered(next,141,78,137,11,0x5B6B80);
    void* surface=at<void*>(w,0x24);
    if(surface && at<void*>(surface,0x18)){
        u32* pixels=at<u32*>(surface,0x18);
        for(int i=0;i<width*height;++i)if(!(pixels[i]&0xff000000) && (pixels[i]&0xffffff))pixels[i]|=0xff000000;
        animatePanels(surface);
        medallion(s.p.phase!=0,filled);
        medallionWeather(s.weather_mask,s.p.phase!=0);
        at<u8>(surface,0x1C)=1;
        at<u8>(surface,0x28)=1; // Native surface must composite its untouched alpha-zero pixels.
    }
}
EXPORT void* __fastcall CelestialDestroy(void* w,void*,int flags) {
    if(w==CelestialState.window){releaseHudCursors();CelestialReset();CelestialState.window=0;}
    return reinterpret_cast<void* (__thiscall *)(void*,int)>(0xA1B750)(w,flags);
}
