// Presentation-only state. The WENV/weather state and wire layout are unchanged.
struct HudApi { void (__thiscall *cursorFallback)(void*); const char* cursors[2]; };
EXPORT HudApi CelestialHudApi = {};
struct HudState {
    u32 collapsed, pressed, progress, from, target, started, duration, moving;
    void* cursorSurfaces[2];
    u32 retry[2];
};
EXPORT HudState CelestialHudState = {0,0,1000,1000,1000};
// The spare word keeps compiler-generated one-past pointers inside the payload.
static u32 panelPixels[width*height+1];
static bool circleContains(int x,int y) { x-=140;y-=35;return x*x+y*y<=34*34; }
static bool hudVisible(void* w) {
    const auto& s=CelestialState;const u32 now=tick();
    return w && w==s.window && at<int>(w,0x28) && s.ready && now-s.received<stale_ms && now-s.frame_tick<=1000;
}
static void releaseHudInput() {
    CelestialHudState.pressed=0;
    if(CelestialState.window && at<void*>((void*)0x131F4E8,0x19C)==CelestialState.window)
        reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);
}
static void releaseHudCursors() {
    for(int i=0;i<2;++i)if(void* surface=CelestialHudState.cursorSurfaces[i]){
        CelestialHudState.cursorSurfaces[i]=0;
        reinterpret_cast<void* (__thiscall *)(void*,int)>(at<u32*>(surface,0)[0])(surface,1);
    }
}
static void resetHud() {
    releaseHudInput();
    auto& h=CelestialHudState;
    h.progress=h.from=h.target=h.collapsed?0:1000;h.moving=0;
}
static bool animateHud(u32 now) {
    auto& h=CelestialHudState;if(!h.moving)return false;
    const u32 age=now-h.started;
    if(age>=h.duration){h.progress=h.target;h.moving=0;return true;}
    const u32 left=1000-age*1000/h.duration;
    const int eased=1000-static_cast<int>(left*left*left/1000000);
    h.progress=static_cast<u32>(static_cast<int>(h.from)+(static_cast<int>(h.target)-static_cast<int>(h.from))*eased/1000);
    return true;
}
EXPORT void* __fastcall CelestialHit(void* w,void*,int x,int y) {
    if(!hudVisible(w))return 0;
    return circleContains(x-at<int>(w,0x1C),y-at<int>(w,0x20))?w:0;
}
EXPORT void __fastcall CelestialDown(void* w,void*,int x,int y) {
    if(!hudVisible(w) || !circleContains(x,y))return;
    CelestialHudState.pressed=1;
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);
}
EXPORT void __fastcall CelestialMove(void*,void*,int,int) { /* Never drag the HUD. */ }
EXPORT void __fastcall CelestialUp(void* w,void*,int x,int y) {
    const bool pressed=CelestialHudState.pressed!=0;
    const bool captured=at<void*>((void*)0x131F4E8,0x19C)==w;
    releaseHudInput();
    if(!pressed || !captured || !hudVisible(w) || !circleContains(x,y))return;
    auto& h=CelestialHudState;const u32 now=tick();animateHud(now);
    h.collapsed=!h.collapsed;h.from=h.progress;h.target=h.collapsed?0:1000;h.started=now;
    const u32 distance=h.from>h.target?h.from-h.target:h.target-h.from;
    h.duration=450*distance/1000;if(!h.duration)h.duration=1;h.moving=1;
    at<int>(w,0x58)=1;
}
static void* hudCursor(int index) {
    auto& h=CelestialHudState;if(h.cursorSurfaces[index])return h.cursorSurfaces[index];
    const u32 now=tick();if(h.retry[index] && now-h.retry[index]<5000)return 0;h.retry[index]=now;
    if(!CelestialHudApi.cursors[index])return 0;
    void* manager=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!manager)return 0;
    const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(CelestialHudApi.cursors[index]);if(!path)return 0;
    void* texture=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(manager,path);
    const int cursorHeight=index?21:22;
    if(!texture || at<int>(texture,0x114)!=26 || at<int>(texture,0x118)!=cursorHeight || !at<void*>(texture,0x11C))return 0;
    void* surface=reinterpret_cast<void* (__cdecl *)(int,int,int)>(0x560E50)(26,cursorHeight,0);if(!surface)return 0;
    h.cursorSurfaces[index]=surface;u32* dest=at<u32*>(surface,0x18);
    if(!dest){releaseHudCursors();return 0;}
    const u32* source=at<u32*>(texture,0x11C);
    for(int i=0;i<26*cursorHeight;++i){const u32 rgb=source[i]&0xffffff;dest[i]=rgb==0xff00ff?0:0xff000000|rgb;}
    at<u8>(surface,0x28)=1;at<u8>(surface,0x1C)=1;return surface;
}
EXPORT void __fastcall CelestialCursorDraw(void* receiver,void*) {
    void* w=CelestialState.window;
    if(hudVisible(w) && *reinterpret_cast<void**>(0x12515F8)){
        void* manager=(void*)0x131F4E8;void* captured=at<void*>(manager,0x19C);
        const bool pressed=CelestialHudState.pressed && captured==w;
        const int x=*reinterpret_cast<int*>(0x11E40D4),y=*reinterpret_cast<int*>(0x11E40D8);
        if((!captured || pressed) && circleContains(x-at<int>(w,0x1C),y-at<int>(w,0x20)) &&
            (pressed || reinterpret_cast<void* (__thiscall *)(void*,int,int)>(0xA336D0)(manager,x,y)==w)){
            if(void* surface=hudCursor(pressed?1:0)){
                reinterpret_cast<void (__thiscall *)(void*,int,int,int,int,u32)>(0x53EA90)(surface,x,y,26,pressed?21:22,0xffffffff);
                return;
            }
        }
    }
    if(CelestialHudApi.cursorFallback)CelestialHudApi.cursorFallback(receiver);
}
static void animatePanels(void* surface) {
    const u32 progress=CelestialHudState.progress;if(progress>=1000)return;
    u32* dest=at<u32*>(surface,0x18);copy(panelPixels,dest,width*height*sizeof(u32));
    for(int i=0;i<width*height;++i)dest[i]=0;
    if(!progress)return;
    // Scale all panel pixels toward the medallion center, including the strip.
    for(int y=0;y<height;++y)for(int x=0;x<width;++x){
        const int sx=140+(x-140)*1000/static_cast<int>(progress),sy=35+(y-35)*1000/static_cast<int>(progress);
        if(sx<0 || sy<0 || sx>=width || sy>=height)continue;
        const u32 color=panelPixels[sy*width+sx],alpha=(color>>24)*progress/1000;
        if(alpha)dest[y*width+x]=(alpha<<24)|(color&0xffffff);
    }
}
