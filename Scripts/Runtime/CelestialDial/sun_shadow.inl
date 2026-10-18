// Copyright (c) rAthena Dev Teams - Licensed under GNU GPL
// For more information, see LICENCE in the main folder
// Bounded directional scenery-shadow pass for prt_fild08. Native meshes stay immutable.

struct ShadowState {
    u32 active, invalid, frame, actors, vertices;
    float view[12], inverse[9], direction_x, direction_z;
    void* sprite_actor;
    u32 sprite_frame, sprites;
};
EXPORT ShadowState CelestialShadowState = {};
struct SpriteShadow { u32 header[10], vertices[32]; };
// Native queues retain only frame-local references; the original object pools persist.
// These private rows are reused on the next frame, after native queue consumption.
EXPORT SpriteShadow CelestialSpriteShadows[128] = {};
static bool sunny() {
    const auto& s=CelestialState;
    return s.ready && !s.p.phase && tick()-s.received<stale_ms &&
        !(s.weather_mask&(Rain|Thunderstorm|Snow|Clouds|Fog)) &&
        s.p.map_name[0]=='p' && s.p.map_name[1]=='r' && s.p.map_name[2]=='t' && s.p.map_name[3]=='_' &&
        s.p.map_name[4]=='f' && s.p.map_name[5]=='i' && s.p.map_name[6]=='l' && s.p.map_name[7]=='d' &&
        s.p.map_name[8]=='0' && s.p.map_name[9]=='8' && !s.p.map_name[10];
}
static bool shadowView(const float* m) {
    auto& s=CelestialShadowState;
    const float a=m[0],b=m[3],c=m[6],d=m[1],e=m[4],f=m[7],g=m[2],h=m[5],i=m[8];
    const float det=a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g);
    if(!(det>0.000001f || det<-.000001f))return false;
    const float k=1.0f/det;
    const float inverse[9]={(e*i-f*h)*k,(c*h-b*i)*k,(b*f-c*e)*k,
        (f*g-d*i)*k,(a*i-c*g)*k,(c*d-a*f)*k,
        (d*h-e*g)*k,(b*g-a*h)*k,(a*e-b*d)*k};
    copy(s.view,m,sizeof(s.view));copy(s.inverse,inverse,sizeof(inverse));
    u32 progress=30;
    const auto& p=CelestialState.p;
    if((p.flags&Scheduled) && p.duration_ms){
        const u32 elapsed=tick()-CelestialState.received;
        const u32 remaining=p.remaining_ms>elapsed?p.remaining_ms-elapsed:0;
        const u32 step=p.duration_ms/120?p.duration_ms/120:1;
        const u32 left=remaining/step;progress=left<120?120-left:0;
    }
    const int angle=30+static_cast<int>(progress);
    const int distance=static_cast<int>(progress)-60;
    const float slope=.35f+static_cast<float>(distance<0?-distance:distance)/60.0f;
    s.direction_x=reinterpret_cast<const float*>(0x124FF40)[angle]*slope;
    s.direction_z=reinterpret_cast<const float*>(0x1250A88)[angle]*slope;
    return true;
}
static bool shadowGround(float* world,bool billboard=false) {
    auto& s=CelestialShadowState;
    float floor=0;
    if(!rainFloor(world[0],world[2],floor,false))return false;
    const float origin_x=world[0],origin_z=world[2],source_y=world[1];
    for(int i=0;i<4;++i){
        const float drop=floor-source_y;
        // Sprite rectangles can include transparent padding below the actor's
        // floor. Project that complete plane so alpha keeps the silhouette joined.
        if(!(drop>=(billboard?-128.0f:-2.0f) && drop<=700.0f))return false;
        world[0]=origin_x+s.direction_x*drop;world[2]=origin_z+s.direction_z*drop;
        if(!rainFloor(world[0],world[2],floor,false))return false;
    }
    world[1]=floor-.12f;return true;
}
EXPORT void __fastcall CelestialShadowProject(void* renderer,void*,const float* vertex,const float* matrix,void* output) {
    auto& s=CelestialShadowState;
    // Always initialize the native scratch vertex, even if this shadow is clipped.
    reinterpret_cast<void (__thiscall *)(void*,const float*,const float*,void*)>(0x554380)(renderer,vertex,matrix,output);
    if(!s.active)return;
    if(++s.vertices>24000){s.invalid=1;return;}
    float camera[3];
    for(int i=0;i<3;++i)camera[i]=vertex[0]*matrix[i]+vertex[1]*matrix[i+3]+vertex[2]*matrix[i+6]+matrix[i+9]-s.view[i+9];
    float world[3];
    for(int i=0;i<3;++i)world[i]=s.inverse[i*3]*camera[0]+s.inverse[i*3+1]*camera[1]+s.inverse[i*3+2]*camera[2];
    if(!shadowGround(world)){s.invalid=1;return;}
    reinterpret_cast<void (__thiscall *)(void*,const float*,const float*,void*)>(0x554380)(renderer,world,s.view,output);
}
EXPORT void __fastcall CelestialShadowSubmit(void* renderer,void*,void* object,u32 flags) {
    auto& s=CelestialShadowState;
    if(s.active){
        if(s.invalid || !object)return;
        void* vertices=at<void*>(object,0);const u32 count=at<u32>(object,4);
        if(!vertices || !count || count>12000)return;
        // These are fresh native frame-pool vertices from the second mesh pass.
        // Keep UVs/texture alpha so tree leaves cast their actual cutout silhouette.
        for(u32 i=0;i<count;++i)at<u32>(vertices,i*32+16)=0x28000000u;
        flags=1; // Stock depth-sorted alpha queue, preserving the material texture.
    }
    reinterpret_cast<void (__thiscall *)(void*,void*,u32)>(0x550B10)(renderer,object,flags);
}
EXPORT void __fastcall CelestialShadowActor(void* actor,void*,const float* matrix,u32 flags) {
    const u32 table=at<u32>(actor,0);
    const u32 original=table==0x104D420?0xA59C30:0xA59D20;
    reinterpret_cast<void (__thiscall *)(void*,const float*,u32)>(original)(actor,matrix,flags);
    auto& s=CelestialShadowState;
    if(s.active || !sunny() || !matrix || (table!=0x104D420 && table!=0x104D450))return;
    const u32 frame=CelestialState.frame_tick;
    if(s.frame!=frame){s.frame=frame;s.actors=s.vertices=0;}
    if(s.actors>=32 || s.vertices>=24000 || !CelestialState.world)return;
    void* player=at<void*>(CelestialState.world,0x2C);if(!player)return;
    const float dx=at<float>(actor,0x58)-at<float>(player,0x10),dz=at<float>(actor,0x60)-at<float>(player,0x18);
    if(!(dx*dx+dz*dz<700.0f*700.0f) || !shadowView(matrix))return;
    ++s.actors;s.active=1;s.invalid=0;
    // Avoid advancing native tree-fade state twice in one frame.
    const u8 fading=at<u8>(actor,0x154);at<u8>(actor,0x154)=0;
    reinterpret_cast<void (__thiscall *)(void*,const float*,u32)>(original)(actor,matrix,flags);
    at<u8>(actor,0x154)=fading;s.active=0;
}
EXPORT void __fastcall CelestialPlayerShadowDraw(void* actor,void*,const float* matrix) {
    auto& s=CelestialShadowState;
    void* previous=s.sprite_actor;s.sprite_actor=0;
    if(sunny() && matrix && shadowView(matrix))s.sprite_actor=actor;
    // Run the complete native player draw exactly once, including all existing bridges.
    reinterpret_cast<void (__thiscall *)(void*,const float*)>(0xD3A220)(actor,matrix);
    s.sprite_actor=previous;
}
EXPORT void __fastcall CelestialSpriteShadowSubmit(void* renderer,void*,void* object,u32 flags,void* actor,u32 caller,u32 parent_caller) {
    reinterpret_cast<void (__thiscall *)(void*,void*,u32)>(0x550B10)(renderer,object,flags);
    auto& s=CelestialShadowState;
    if(!object || !actor || actor!=s.sprite_actor || !sunny() || at<u32>(object,4)!=4)return;
    // Exclude stock ground-shadow helpers; their ellipses remain native-owned.
    if((caller>=0xC49D20 && caller<0xC4A0D0) ||
        (caller==0xC4A6C5 && parent_caller>=0xC49D20 && parent_caller<0xC4A0D0))return;
    if(s.sprite_frame!=CelestialState.frame_tick){s.sprite_frame=CelestialState.frame_tick;s.sprites=0;}
    if(s.sprites>=128)return;
    void* input=at<void*>(object,0);if(!input)return;
    const float scale_x=at<float>(renderer,4),scale_y=at<float>(renderer,8);
    if(!(scale_x>.0001f || scale_x<-.0001f) || !(scale_y>.0001f || scale_y<-.0001f))return;
    // HD/native layers carry render-only per-vertex depth corrections. Reusing
    // their RHW as physical distance separates the head's cast shadow. Derive
    // every layer from the same actor billboard plane; leave stock depth intact.
    const float depth=at<float>(actor,0x10)*s.view[2]+at<float>(actor,0x14)*s.view[5]+
        at<float>(actor,0x18)*s.view[8]+s.view[11];
    if(!(depth>.001f && depth<1000000.0f))return;
    const float rhw=1.0f/depth;
    auto& row=CelestialSpriteShadows[s.sprites];copy(row.header,object,sizeof(row.header));
    copy(row.vertices,input,sizeof(row.vertices));row.header[0]=reinterpret_cast<u32>(row.vertices);
    for(int v=0;v<4;++v){
        void* output=row.vertices+v*8;
        const float camera[3]={(at<float>(output,0)-at<int>(renderer,0x30))/(scale_x*rhw)-s.view[9],
            (at<float>(output,4)-at<int>(renderer,0x34))/(scale_y*rhw)-s.view[10],1.0f/rhw-s.view[11]};
        float world[3];
        for(int i=0;i<3;++i)world[i]=s.inverse[i*3]*camera[0]+s.inverse[i*3+1]*camera[1]+s.inverse[i*3+2]*camera[2];
        if(!shadowGround(world,true))return;
        reinterpret_cast<void (__thiscall *)(void*,const float*,const float*,void*)>(0x554380)(renderer,world,s.view,output);
        at<u32>(output,16)=(at<u32>(output,16)>>24)*56/255<<24;
    }
    ++s.sprites;
    reinterpret_cast<void (__thiscall *)(void*,void*,u32)>(0x550B10)(renderer,&row,1);
}
EXPORT __declspec(naked) void CelestialSpriteSubmitBridge() {
    __asm {
        xor eax,eax
        cmp dword ptr [ebp+4],0C4A6C5h
        jne no_parent
        mov eax,dword ptr [ebp]
        mov eax,dword ptr [eax+4]
    no_parent:
        push eax
        push dword ptr [ebp+4]
        push dword ptr [ebp-28h]
        push dword ptr [esp+20]
        push dword ptr [esp+20]
        call CelestialSpriteShadowSubmit
        ret 8
    }
}
