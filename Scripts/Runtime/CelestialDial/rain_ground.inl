// Copyright (c) 2026 WARP contributors - Licensed under GNU GPL
// Private rain primitives: ground contact, splashes, ripples and wet glints.
// This is a cosmetic surface layer; it does not render scene reflections.
#ifndef CELESTIAL_RAIN_GROUND_INL
#define CELESTIAL_RAIN_GROUND_INL

struct RainVec { float x,y,z; };
struct RainUv { float u0,u1,v0,v1; };
constexpr u16 rainDropAlpha=220;
static bool rainFloor(float x,float z,float& y,bool walkable=true) {
    if(!CelestialState.world)return false;
    void* ground=at<void*>(CelestialState.world,0x28);if(!ground)return false;
    const int gw=at<int>(ground,8),gh=at<int>(ground,12);
    const float scale=at<float>(ground,16);
    if(gw<=0 || gh<=0 || gw>4096 || gh>4096 || !(scale>=1 && scale<=100))return false;
    void* resource=at<void*>(ground,4);if(!resource)return false;
    const int w=at<int>(resource,0x110),h=at<int>(resource,0x114);
    void* cells=at<void*>(resource,0x11C);
    if(!cells || w!=gw*2 || h!=gh*2)return false;
    const float gx=x/(scale*0.5f)+static_cast<float>(gw),gz=z/(scale*0.5f)+static_cast<float>(gh);
    if(!(gx>=0 && gz>=0 && gx<w-1 && gz<h-1))return false;
    const int ix=static_cast<int>(gx),iz=static_cast<int>(gz);
    void* cell=static_cast<u8*>(cells)+(iz*w+ix)*20;
    const u32 type=at<u32>(cell,16)&0x7fffffff;
    if(type>6 || (walkable && !(0x5Du&(1u<<type))))return false;
    const float a=at<float>(cell,0),b=at<float>(cell,4),c=at<float>(cell,8),d=at<float>(cell,12);
    if(!(a>-32000 && a<32000 && b>-32000 && b<32000 && c>-32000 && c<32000 && d>-32000 && d<32000))return false;
    const float fx=gx-ix,fz=gz-iz;
    y=(a+(b-a)*fx)*(1-fz)+(c+(d-c)*fx)*fz;
    return true;
}
static u32 rainTexture(const char* name) {
    return reinterpret_cast<u32 (__thiscall *)(void*,const char*,int,int,int,int)>(0x568760)((void*)0x125161C,name,0,1,0,0);
}
static bool rainOwnPrim(void* child) {
    return child && rainActive(tick()) && at<void*>(child,0x140)==CelestialState.rain_effect &&
        CelestialState.rain_effect && at<u32>(child,0x1D0)==157;
}
EXPORT int __fastcall CelestialRainGroundProcess(void* child,void*) {
    if(!rainOwnPrim(child))return 0;
    // Same native simulation-count gate as CPrim::Process; no wall-clock physics.
    if(!*reinterpret_cast<u32*>(0x1602AA4))return 1;
    for(int i=0;i<4;++i){
        void* p=static_cast<u8*>(child)+0x3E8+i*0xB4;if(!at<u8>(p,0))continue;
        const float radius=at<float>(p,0x14);const int angle=at<u16>(p,6)%360;
        const float dx=radius*reinterpret_cast<float*>(0x1250A88)[angle];
        const float dz=radius*reinterpret_cast<float*>(0x124FF40)[angle];
        at<float>(p,0x7C)=dx;at<float>(p,0x84)=dz;
        float floor=0;
        if(!rainFloor(at<float>(child,0x10)+dx,at<float>(child,0x18)+dz,floor)){at<u8>(p,0)=0;continue;}
        const float contact=floor-at<float>(child,0x14);
        float& dropY=at<float>(p,0x88);
        if(dropY<contact){dropY+=at<float>(p,8);if(dropY>contact)dropY=contact;}
        else{
            const u16 alpha=at<u16>(p,2);
            at<u16>(p,2)=alpha>12?static_cast<u16>(alpha-12):0;
            if(!at<u16>(p,2))at<u8>(p,0)=0;
        }
        ++at<u32>(p,0xC);
    }
    return ++at<u32>(child,0x1E0)<=at<u32>(child,0x1E4)?1:0;
}
static void rainQuad(void* child,void* renderer,int& count,u32 texture,u32 alpha,
                     RainVec a,RainVec b,RainVec c,RainVec d) {
    if(!texture || texture==0xffffffff || count>=128 || !alpha)return;
    void* saved=at<void*>(child,0x144);const u32 size=at<u32>(child,0x204);
    u32 current=texture;at<void*>(child,0x144)=&current;at<u32>(child,0x204)=1;
    // CPrim::queueQuad copies the texture handle and vertices into native queues.
    // World-coordinate mode avoids adding the primitive's local origin twice.
    using Submit=void (__thiscall *)(void*,int*,u32,RainVec,RainVec,RainVec,RainVec,void*,int,int,int,u32,u32,u32,RainUv,int);
    reinterpret_cast<Submit>(0xB7C4E0)(child,&count,alpha,a,b,c,d,renderer,0,0,1,210,227,240,{0,1,0,1},1);
    at<void*>(child,0x144)=saved;at<u32>(child,0x204)=size;
}
static void rainPatch(void* child,void* renderer,int& count,u32 texture,u32 alpha,float x,float z,float radius) {
    RainVec v[4]={{x-radius,0,z-radius},{x+radius,0,z-radius},{x+radius,0,z+radius},{x-radius,0,z+radius}};
    float low=32000,high=-32000;
    for(int i=0;i<4;++i){
        if(!rainFloor(v[i].x,v[i].z,v[i].y))return;
        if(v[i].y<low)low=v[i].y;if(v[i].y>high)high=v[i].y;
        v[i].y-=0.08f; // Small Y-up separation, not an always-on-top depth override.
    }
    if(high-low>4)return; // No puddle sheets across cliffs or steep ramps.
    rainQuad(child,renderer,count,texture,alpha,v[0],v[1],v[2],v[3]);
}
EXPORT void __fastcall CelestialRainGroundDraw(void* child,void*,void* renderer) {
    if(!rainOwnPrim(child) || !renderer)return;
    // Replay the two stock CPrim render eligibility gates, including /effect.
    if(!(reinterpret_cast<int (__thiscall *)(void*)>(0xD9D020)((void*)0x15FA3C0)&255) ||
       !(reinterpret_cast<int (__thiscall *)(void*)>(0xB7F8D0)(child)&255))return;
    const u32 streak=at<void*>(child,0x144)?at<u32>(at<void*>(child,0x144),0):0;
    const u32 ring=rainTexture("effect\\boh_rain_ripple.bmp"),sheen=rainTexture("effect\\boh_rain_wet.bmp");
    void* mode=CelestialState.mode;void* camera=mode?at<void*>(mode,0xD0):0;
    int angle=camera?static_cast<int>(at<float>(camera,0x30)):0;
    angle%=360;if(angle<0)angle+=360;
    const float rx=reinterpret_cast<float*>(0x124FF40)[angle],rz=reinterpret_cast<float*>(0x1250A88)[angle];
    int count=0;
    for(int i=0;i<4;++i){
        void* p=static_cast<u8*>(child)+0x3E8+i*0xB4;if(!at<u8>(p,0))continue;
        const float x=at<float>(child,0x10)+at<float>(p,0x7C),z=at<float>(child,0x18)+at<float>(p,0x84);
        const float y=at<float>(child,0x14)+at<float>(p,0x88);float floor=0;if(!rainFloor(x,z,floor))continue;
        const u32 alpha=at<u16>(p,2);
        if(y<floor-0.01f){
            const float w=1.1f,streakTop=y-7.0f,bottom=y+1.5f;
            rainQuad(child,renderer,count,streak,alpha,{x-rx*w,streakTop,z-rz*w},{x+rx*w,streakTop,z+rz*w},
                     {x+rx*w,bottom,z+rz*w},{x-rx*w,bottom,z-rz*w});
        }else{
            const float spread=1.4f+static_cast<float>(alpha<rainDropAlpha?rainDropAlpha-alpha:0)*0.020f;
            rainPatch(child,renderer,count,ring,alpha,x,z,spread);
            if(alpha>112)rainPatch(child,renderer,count,ring,alpha/2,x,z,0.45f);
        }
    }
    // Only the newest child draws the stable local sheen layer; no per-child overdraw.
    if(at<void*>(CelestialState.rain_effect,0x11C84)==child){
        void* player=CelestialState.rain_player;if(!player)return;
        const int gx=static_cast<int>(at<float>(player,0x10)/30),gz=static_cast<int>(at<float>(player,0x18)/30);
        for(int i=0;i<24;++i){
            const int ix=gx+(i%6)*2-5,iz=gz+(i/6)*2-3;
            const u32 seed=static_cast<u32>(ix)*374761393u+static_cast<u32>(iz)*668265263u;
            const float x=ix*30.0f+static_cast<float>(seed%17),z=iz*30.0f+static_cast<float>((seed>>8)%17);
            // Stable, broad wet patches avoid the former sawtooth sparkle/pulse.
            const u32 alpha=100+((seed>>12)%24);
            rainPatch(child,renderer,count,sheen,alpha,x,z,8.0f+static_cast<float>((seed>>16)&3));
        }
    }
}
static void rainGroundAttach(void* child) {
    if(!CelestialRainPrimVtable[1]){
        copy(CelestialRainPrimVtable,reinterpret_cast<void*>(0x1088C48-4),sizeof(CelestialRainPrimVtable));
        CelestialRainPrimVtable[2]=reinterpret_cast<u32>(&CelestialRainGroundProcess);
        CelestialRainPrimVtable[4]=reinterpret_cast<u32>(&CelestialRainGroundDraw);
    }
    at<u32>(child,0)=reinterpret_cast<u32>(CelestialRainPrimVtable+1);
}
#endif
