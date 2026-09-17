// Freestanding x86, 2025-07-16 Ragexe. No DLL/imports or shared text hooks.
// Only this frame owns its input, surface, assets and VIPU snapshot.
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#define EXPORT extern "C" __declspec(dllexport)
#pragma pack(push,1)
struct Benefit { char title[24], line1[80], line2[80]; };
struct QuestItem { u32 id,amount,owned; char name[48]; };
struct Offer { u32 minutes,cost; };
struct Snapshot {
    u16 id,length; u32 magic; u16 version,flags; u32 token,level,percent;
    char player[24],issued[32],expires[32],experience[64],status[96],upgrade[64],membership[96];
    Benefit benefits[10];
    u32 questCost,questLevel;char questStatus[64];QuestItem questItems[3];
    Offer offers[5];
    u32 buffRemaining;char buffPrompt[96];
};
struct Request { u16 id,length; u32 magic; u16 version,action; u32 token;u32 quotedMinutes,quotedCost; };
#pragma pack(pop)
static_assert(sizeof(Snapshot)==2664 && sizeof(Request)==24,"VIPU v4");
struct Api {
    u32 version,vtable,ctor,send;
    void (__stdcall *fit)(void*,const char*,int,int,int,u32);
    void (__stdcall *plain)(void*,const char*,int,int,int,u32);
    void (__thiscall *png)(void*,int,int,void*,int);
    const char* paths[12];
    u32 moduleIat,procIat;
    void (__stdcall *item)(void*,u32,int,int);
    const char* scrollPaths[2]; // Append-only; all existing helper offsets stay fixed.
    const char* buttons[12][4]; // Complete PNGs: out, over, press, off; captions baked in.
    void (__stdcall *describe)(u32); // Private native CItem description adapter.
    const char* purchaseButtons[4];
    void (__stdcall *offerText)(void*,const char*,int,int,int,u32);
    const char* crown;
    void (__stdcall *priceText)(void*,const char*,int,int,int,u32);
};
static_assert(sizeof(Api)==320,"VIP private API with crown membership cards");
EXPORT Api VipApi = {2};
struct State { void* window; int pressed,hover,dragging,hidden,scroll,ready; u32 refresh; Snapshot p;
    u32 timer; u32 (__stdcall *setTimer)(void*,u32,u32,void*); int (__stdcall *killTimer)(void*,u32);
};
EXPORT State VipState = {};
struct QuestState { void* window;int pressed,hover,dragging,mode;
    int itemPressed,rightPressed;u32 itemId,itemToken,rightId,rightToken;
    int selected;Offer chosen;
};
EXPORT QuestState VipQuestState = {};
EXPORT void* VipPortraitCanvas = 0;
static void questHide();
template<typename T> T& at(void* p,int off) { return *reinterpret_cast<T*>(static_cast<u8*>(p)+off); }
static u32 tick() { return (*reinterpret_cast<u32 (__stdcall **)()>(0xFC17B0))(); }
static void dirty(void* w) { if(w) at<int>(w,0x58)=1; }
static void release(void* w) {
    if(w==VipQuestState.window)VipQuestState.itemPressed=VipQuestState.rightPressed=0;
    int& dragging=w==VipQuestState.window?VipQuestState.dragging:VipState.dragging;
    if(dragging) {
        dragging=0;
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880BB0)(w,0,0);
    }
    if(at<void*>((void*)0x131F4E8,0x19C)==w)
        reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);
    (w==VipQuestState.window?VipQuestState.pressed:VipState.pressed)=0;
}
static void send(int action,u32 minutes=0,u32 cost=0) {
    if(!VipState.ready || !VipState.p.token) return;
    Request r={0x0BFA,24,0x55504956,4,static_cast<u16>(action),VipState.p.token,minutes,cost};
    void* transport=reinterpret_cast<void* (__cdecl *)()>(VipApi.ctor)();
    if(transport) reinterpret_cast<void (__thiscall *)(void*,int,const void*)>(VipApi.send)(transport,sizeof(r),&r);
}
static void hide(bool notify) {
    if(notify) send(6);
    questHide();
    if(VipState.window) { release(VipState.window); at<int>(VipState.window,0x28)=0; }
    VipState.hidden=1; VipState.ready=0; VipState.hover=0;
    if(VipState.timer && VipState.killTimer) VipState.killTimer(0,VipState.timer);
    VipState.timer=0;
}
EXPORT void __stdcall VipTick(void*,u32,u32 id,u32) {
    if(!*reinterpret_cast<int*>(0x11E40E8))VipQuestState.rightPressed=0;
    if(id!=VipState.timer || !VipState.window || VipState.hidden || !VipState.ready) return;
    if(!at<int>(VipState.window,0x28)) return;
    send(0);
}
static void startTimer() {
    if(VipState.timer) return;
    if(!VipState.setTimer) {
        void* module=(*reinterpret_cast<void* (__stdcall **)(const char*)>(VipApi.moduleIat))("user32.dll");
        if(!module) return;
        auto resolve=*reinterpret_cast<void* (__stdcall **)(void*,const char*)>(VipApi.procIat);
        VipState.setTimer=reinterpret_cast<u32 (__stdcall *)(void*,u32,u32,void*)>(resolve(module,"SetTimer"));
        VipState.killTimer=reinterpret_cast<int (__stdcall *)(void*,u32)>(resolve(module,"KillTimer"));
    }
    if(VipState.setTimer && VipState.killTimer) VipState.timer=VipState.setTimer(0,0,3000,reinterpret_cast<void*>(VipTick));
}
struct Control { int id,x,y,w,h,action,flag,art; };
static const Control controls[]={
    {1,781,1,15,18,6,0,0},
    {2,122,166,60,18,1,0,1},
    {3,188,166,68,18,2,16,2},
    {4,122,192,81,18,3,0,3},
    {5,209,192,57,18,5,512,4},
    {6,293,296,53,18,4,8,5},
    {7,775,111,13,13,-1,0,10},
    {8,775,346,13,13,-2,0,11},
    {9,288,375,58,18,0,0,6}
};
static void* buttonTexture(const Control& c,int state) {
    if(c.art<0 || c.art>12 || state<0 || state>=4)return 0;
    const char* file=c.art==12?VipApi.purchaseButtons[state]:VipApi.buttons[c.art][state];if(!file)return 0;
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return 0;
    const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(file);if(!path)return 0;
    void* tex=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);
    if(!tex || at<int>(tex,0x114)!=c.w || at<int>(tex,0x118)!=c.h || !at<void*>(tex,0x11C))return 0;
    return tex;
}
static bool activeBenefits() { return (VipState.p.flags&5)==5 && VipState.p.level>0 && VipState.p.level<=10; }
static const int visibleBenefits=5;
// The existing server labels use | between effects. Split only the current
// tier, keeping its configured wording and the unchanged VIPU v4 snapshot.
static int benefitRows(int selected=-1,char* out=0) {
    if(out)out[0]=0;
    if(!activeBenefits())return 0;
    if(VipState.p.flags&1024) {
        // Same fixed snapshot: the server now supplies up to 20 individual
        // current-tier rows, two per legacy Benefit slot. No version bump.
        int count=0;
        for(const auto& entry:VipState.p.benefits) {
            const char* lines[]={entry.line1,entry.line2};
            for(const char* line:lines) {
                if(!line[0])continue;
                if(out && selected==count){int n=0;while(n<79 && line[n]){out[n]=line[n];++n;}out[n]=0;}
                ++count;
            }
        }
        return count;
    }
    const auto& b=VipState.p.benefits[VipState.p.level-1];
    const char* lines[]={b.line1,b.line2};int count=0;
    for(const char* line:lines) {
        int pos=0;
        while(pos<80 && line[pos]) {
            const int start=pos;
            while(pos<80 && line[pos] && line[pos]!='|')++pos;
            int first=start,last=pos;
            while(first<last && (line[first]==' ' || line[first]=='\t'))++first;
            while(last>first && (line[last-1]==' ' || line[last-1]=='\t'))--last;
            if(last>first) {
                if(out && count==selected) {
                    int n=0;while(first<last && n<79)out[n++]=line[first++];out[n]=0;
                }
                ++count;
            }
            if(pos<80 && line[pos]=='|')++pos;
        }
    }
    return count;
}
static int benefitScrollMax() { const int count=benefitRows();return count>visibleBenefits?count-visibleBenefits:0; }
static void clampBenefitScroll() {
    const int limit=benefitScrollMax();
    if(VipState.scroll<0)VipState.scroll=0;
    if(VipState.scroll>limit)VipState.scroll=limit;
}
static bool buffsReady() { return VipState.ready && !VipState.hidden &&
    (VipState.p.flags&513)==513 && !VipState.p.buffRemaining; }
static bool enabled(const Control& c) {
    if(!buttonTexture(c,0))return false; // Missing/mis-sized artwork cannot leave an invisible action.
    if(c.id==1) return true;
    if(!VipState.ready || VipState.hidden) return false;
    if(c.id==2 && (VipState.p.flags&257))return false; // No active VIP or pending payment.
    if((c.id==3 || c.id==4) && !(VipState.p.flags&1))return false; // Store/storage require VIP.
    if(c.id==5 && !buffsReady())return false;
    if(c.id==7)return VipState.scroll>0;
    if(c.id==8)return VipState.scroll<benefitScrollMax();
    return !c.flag || (VipState.p.flags & c.flag)!=0;
}
EXPORT int __stdcall VipHit(int x,int y) {
    if(!VipState.window || VipState.hidden || !at<int>(VipState.window,0x28)) return 0;
    if(VipQuestState.mode) return 0;
    for(const auto& c: controls) {
        if(enabled(c) && x>=c.x && y>=c.y && x<c.x+c.w && y<c.y+c.h) return c.id;
    }
    return 0;
}
static void rect(void* w,int x,int y,int width,int height,u32 color) {
    void* s=at<void*>(w,0x24); if(!s || !at<void*>(s,0x18)) return;
    const int sw=at<int>(s,4),sh=at<int>(s,8);
    if(x<0 || y<0 || width<0 || height<0 || x+width>sw || y+height>sh) return;
    u32* pixels=at<u32*>(s,0x18);
    for(int row=y;row<y+height;++row) for(int col=x;col<x+width;++col) pixels[row*sw+col]=color;
    at<u8>(s,0x1C)=1;
}
static void text(void* w,const char* s,int x,int y,int width,u32 color=0x5A5A5A) { VipApi.fit(w,s,x,y,width,color); }
static void centeredText(void* w,char* value,int x,int y,int width,u32 color=0x5A5A5A) {
    int count=0;while(count<79 && value[count])++count;
    int measured=0;
    do {
        value[count]=0;
        measured=reinterpret_cast<int (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA21C90)(w,value,count,0,12,0,0);
        if(measured<=width)break;
    } while(--count>0);
    if(count>0 && measured>=0 && measured<=width)text(w,value,x+(width-measured)/2,y,width,color);
}
static const char* assetPath(int asset) { return asset==14?VipApi.crown:asset<12?VipApi.paths[asset]:VipApi.scrollPaths[asset-12]; }
static void image(void* w,int asset,int x,int y) {
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)(); if(!mgr) return;
    const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(assetPath(asset)); if(!path) return;
    void* tex=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path); if(!tex) return;
    VipApi.png(w,x,y,tex,0); // private helper retains original opaque surface mode
}
// Source-region UI composition, not a mutation of shared textures. Used for
// live EXP fill and the supplied requirement item box. Buttons use whole PNGs.
static void picture(void* w,int asset,int x,int y,int width,int height,
    int sx,int sy,int sw,int sh,int opacity=255,bool gold=false) {
    void* surface=at<void*>(w,0x24);if(!surface || !at<void*>(surface,0x18))return;
    if(width<=0 || height<=0 || sw<0 || sh<0 || x<0 || y<0 || sx<0 || sy<0 ||
        x+width>at<int>(surface,4) || y+height>at<int>(surface,8))return;
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return;
    const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(assetPath(asset));if(!path)return;
    void* tex=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);if(!tex)return;
    const int tw=at<int>(tex,0x114),th=at<int>(tex,0x118);const u32* src=at<u32*>(tex,0x11C);
    if(asset==14 && sw==0 && sh==0){sw=tw;sh=th;} // Fit original-alpha crown; never rewrite its PNG.
    if(!src || tw<1 || th<1 || tw>4096 || th>4096 || sw<1 || sh<1 || sx+sw>tw || sy+sh>th)return;
    u32* dst=at<u32*>(surface,0x18);const int stride=at<int>(surface,4);
    for(int row=0;row<height;++row)for(int col=0;col<width;++col) {
        u32 s=src[(sy+row*sh/height)*tw+sx+col*sw/width];
        u32& d=dst[(y+row)*stride+x+col];const u32 a=(s>>24)*opacity/255;
        if(!a || (s&0xFFFFFF)==0xFF00FF)continue;
        // Tint only this draw, keeping the supplied strip's shading and alpha.
        // The shared vip_exp texture remains green for every non-ready draw.
        if(gold){const u32 light=(s>>8)&255;s=(s&0xFF000000)|(light<<16)|((light*4/5)<<8)|(light/4);}
        if(a==255){d=s;continue;}
        u32 out=0xFF000000;for(int shift=0;shift<24;shift+=8)
            out|=((((s>>shift)&255)*a+((d>>shift)&255)*(255-a)+127)/255)<<shift;
        d=out;
    }
    at<u8>(surface,0x1C)=1;
}
static void paintButton(void* w,const Control& c,int state) {
    void* surface=at<void*>(w,0x24);if(!surface || !at<void*>(surface,0x18))return;
    if(c.x<0 || c.y<0 || c.x+c.w>at<int>(surface,4) || c.y+c.h>at<int>(surface,8))return;
    void* tex=buttonTexture(c,state);
    if(!tex && state!=0)tex=buttonTexture(c,0); // Artwork-only fallback, never regenerate a caption.
    if(tex)VipApi.png(w,c.x,c.y,tex,0);
}
static bool showExperience() {
    if(!VipState.p.experience[0] || (!VipState.p.level && (VipState.p.flags&5)!=5))return false;
    // Suppress a zero-denominator counter, accepting spaces/commas in server text.
    const char* value=VipState.p.experience;
    while(*value && *value!='/')++value;
    if(!*value)return true; // e.g. Maximum VIP level.
    for(++value;*value;++value) {
        if(*value>='1' && *value<='9')return true;
        if(*value!='0' && *value!=' ' && *value!=',')break;
    }
    return false;
}
static void field(void* w,const char* label,const char* value,int y,bool plain=false) {
    char line[80];int n=0;while(*label && n<79)line[n++]=*label++;
    while(*value && n<79)line[n++]=*value++;line[n]=0;
    if(plain)VipApi.plain(w,line,128,y,224,0x342A26);else text(w,line,128,y,224,0x342A26);
}
// CSession equipment providers D59B90/D800B0: ten inline CItem entries,
// stride F8; +4 identity and +70 view ID. Exact Alt+Q slots: upper 8,
// middle 9, lower 0, garment 2. Costume presence (even view 0) wins.
static const u8* worn(int slot) {
    const u8* normal=reinterpret_cast<const u8*>(0x15FA3C0+0x17D0+slot*0xF8);
    const u8* costume=reinterpret_cast<const u8*>(0x15FA3C0+0x2B30+slot*0xF8);
    return *reinterpret_cast<const u32*>(costume+4)?costume:normal;
}
EXPORT int __stdcall VipPortrait(void* w,int x,int y,int width,int height) {
    void* mode=reinterpret_cast<void* (__thiscall *)(void*)>(0xA75340)((void*)0x1213338);
    if(!mode)return 0;void* world=at<void*>(mode,0xCC);if(!world)return 0;
    void* actor=at<void*>(world,0x2C);if(!actor)return 0;
    if(!VipPortraitCanvas) {
        void* canvas=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4);if(!canvas)return 0;
        reinterpret_cast<void (__thiscall *)(void*,int)>(0x86B950)(canvas,0);
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(canvas,512,512);
        VipPortraitCanvas=canvas; // Private offscreen frame; never registered for input.
    }
    void* canvas=VipPortraitCanvas;
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(canvas,0);
    void* surface=at<void*>(canvas,0x24);if(!surface || !at<void*>(surface,0x18))return 0;
    if(at<int>(surface,4)!=512 || at<int>(surface,8)!=512)return 0;
    rect(canvas,0,0,512,512,0xFFE8EFF9);
    const u8* high=worn(8);const u8* mid=worn(9);const u8* low=worn(0);const u8* robe=worn(2);
    const u32 highId=*reinterpret_cast<const u32*>(high+4),midId=*reinterpret_cast<const u32*>(mid+4),lowId=*reinterpret_cast<const u32*>(low+4);
    const int h=highId?*reinterpret_cast<const int*>(high+0x70):0;
    const int m=midId && midId!=highId?*reinterpret_cast<const int*>(mid+0x70):0;
    const int l=lowId && lowId!=highId && lowId!=midId?*reinterpret_cast<const int*>(low+0x70):0;
    const int r=*reinterpret_cast<const u32*>(robe+4)?*reinterpret_cast<const int*>(robe+0x70):0;
    const int job=reinterpret_cast<int (__thiscall *)(void*)>(0xD5B580)((void*)0x15FA3C0);
    const int sex=reinterpret_cast<int (__thiscall *)(void*)>(0xD84760)((void*)0x15FA3C0);
    if(job<0 || job>65535 || sex<0 || sex>1)return 0;
    // This is the same 19-argument UI character compositor used by Alt+Q.
    // All resources and body/head/garment anchors remain native; no SPR paths guessed.
    u32 display[0x98/4];
    using Build=void* (__thiscall *)(void*,void*,int,int,int,int,int,int,int,int,int,int,int,int,int,int,int,int,int,int);
    reinterpret_cast<Build>(0x7AC210)(display,canvas,256,320,sex,job,job,
        at<u16>(actor,0x4C8),*reinterpret_cast<u16*>(0x15FB278),l,h,m,r,0,
        *reinterpret_cast<int*>(0x160240C),*reinterpret_cast<int*>(0x15FB28C),
        *reinterpret_cast<int*>(0x15FB290),0,0,0);
    reinterpret_cast<void (__thiscall *)(void*,int)>(0x7AC820)(display,0);
    reinterpret_cast<void (__thiscall *)(void*)>(0x79A6A0)(display);
    const u32* src=at<u32*>(surface,0x18);int left=512,top=512,right=-1,bottom=-1;
    for(int row=0;row<512;++row)for(int col=0;col<512;++col)
        if((src[row*512+col]&0xFFFFFF)!=0xE8EFF9) {
            if(col<left)left=col;if(col>right)right=col;if(row<top)top=row;if(row>bottom)bottom=row;
        }
    if(right<left || bottom<top || width<8 || height<8)return 0;
    const int sw=right-left+1,sh=bottom-top+1;int dw=sw,dh=sh;
    if(dw>width-8){dh=dh*(width-8)/dw;dw=width-8;}
    if(dh>height-8){dw=dw*(height-8)/dh;dh=height-8;}
    if(dw<1 || dh<1)return 0;
    void* dest=at<void*>(w,0x24);if(!dest || !at<void*>(dest,0x18))return 0;
    x+=(width-dw)/2;y+=(height-dh)/2;
    if(x<0 || y<0 || x+dw>at<int>(dest,4) || y+dh>at<int>(dest,8))return 0;
    u32* pixels=at<u32*>(dest,0x18);const int stride=at<int>(dest,4);
    for(int row=0;row<dh;++row)for(int col=0;col<dw;++col) {
        const u32 color=src[(top+row*sh/dh)*512+left+col*sw/dw];
        if((color&0xFFFFFF)!=0xE8EFF9)pixels[(y+row)*stride+x+col]=color|0xFF000000;
    }
    at<u8>(dest,0x1C)=1;return 1;
}
static const Control questControls[]={
    {20,341,1,15,18,-3,0,0},
    {21,150,78,28,18,4,8,7},{22,186,78,23,18,-3,0,8},
    {23,128,240,53,18,7,128,5},{24,189,240,43,18,-3,0,9},
    {25,126,296,56,18,-4,0,12},{26,190,296,43,18,-3,0,9},
    {27,150,78,28,18,5,512,7},{28,186,78,23,18,-3,0,8},
    {29,150,78,28,18,7,128,7},{30,186,78,23,18,-5,0,8}
};
static int questRows() {
    for(int i=2;i>=0;--i)if(VipState.p.questItems[i].id)return i+1;
    return 1;
}
static int questHeight(int mode) {
    return (mode==1 || mode==4 || mode==5)?118:mode==3?320:126+questRows()*48;
}
static Control placedQuestControl(const Control& source) {
    Control c=source;
    if(VipQuestState.mode==2 && (c.id==23 || c.id==24))c.y-=(3-questRows())*48;
    return c;
}
// Private renderer entry for offline asset-state regression tests; no packet action.
EXPORT void __stdcall VipPaintButton(void* w,int id,int state) {
    if(!w || state<0 || state>3)return;
    for(const auto& c:controls)if(c.id==id){paintButton(w,c,state);return;}
    for(const auto& c:questControls)if(c.id==id){paintButton(w,c,state);return;}
}
static bool questControl(const Control& c) {
    return VipQuestState.mode && (c.id==20 || (VipQuestState.mode==1?c.id==21 || c.id==22:
        VipQuestState.mode==2?c.id==23 || c.id==24:
        VipQuestState.mode==3?c.id==25 || c.id==26:
        VipQuestState.mode==4?c.id==27 || c.id==28:c.id==29 || c.id==30));
}
static bool offerAllowed(int index) {
    if(index<0 || index>=5 || !VipState.ready || VipState.hidden || (VipState.p.flags&257))return false;
    const auto& offer=VipState.p.offers[index];
    return offer.minutes>0 && offer.minutes<=525600 && offer.cost>0 && offer.cost<=1000000000;
}
static bool purchaseReady() {
    const int index=VipQuestState.selected;if(!offerAllowed(index))return false;
    const auto& offer=VipState.p.offers[index];
    return VipQuestState.chosen.minutes==offer.minutes && VipQuestState.chosen.cost==offer.cost;
}
static bool questEnabled(const Control& c) {
    return buttonTexture(c,0) && (!c.flag || (VipState.p.flags&c.flag)) &&
        (c.id!=25 || purchaseReady()) && (c.id!=27 || buffsReady()) &&
        ((c.id!=23 && c.id!=29) || (VipState.p.flags&165)==165);
}
static int questHit(int x,int y) {
    if(!VipQuestState.window || !at<int>(VipQuestState.window,0x28) || !VipState.ready || VipState.hidden)return 0;
    for(const auto& source:questControls) {
        const auto c=placedQuestControl(source);
        if(questControl(c) && questEnabled(c) && x>=c.x && y>=c.y && x<c.x+c.w && y<c.y+c.h) return c.id;
    }
    if(VipQuestState.mode==3)for(int i=0;i<5;++i)
        if(offerAllowed(i) && x>=6 && x<354 && y>=25+i*48 && y<69+i*48)return 40+i;
    return 0;
}
static int questItemHit(void* w,int x,int y) {
    if(w!=VipQuestState.window || !w || !at<int>(w,0x28) || VipQuestState.mode!=2 ||
        !VipState.ready || VipState.hidden || !(VipState.p.flags&32) || VipQuestState.dragging)return 0;
    for(int i=0;i<3;++i) {
        const int top=31+i*48;
        if(VipState.p.questItems[i].id && x>=13 && x<45 && y>=top && y<top+32)return i+1;
    }
    return 0;
}
static void inspectItem(void* w,int x,int y,int slot,u32 id,u32 token) {
    if(!slot || slot!=questItemHit(w,x,y) || token!=VipState.p.token ||
        id!=VipState.p.questItems[slot-1].id || at<void*>((void*)0x131F4E8,0x19C))return;
    VipApi.describe(id); // Synchronous native copy; no quest request or inventory mutation.
}
static void number(char* out,u32 value) {
    char reverse[24];int n=0;do{reverse[n++]=static_cast<char>('0'+value%10);value/=10;}while(value);
    int p=0;for(int i=n-1;i>=0;--i) {out[p++]=reverse[i];if(i && i%3==0)out[p++]=',';}out[p]=0;
}
static void membershipCard(void* w,int y,bool selected,bool hover,bool on) {
    void* surface=at<void*>(w,0x24);if(!surface || !at<void*>(surface,0x18) ||
        at<int>(surface,4)<354 || y<0 || y+44>at<int>(surface,8))return;
    const int stride=at<int>(surface,4);u32* pixels=at<u32*>(surface,0x18);
    for(int row=0;row<44;++row)for(int col=0;col<348;++col) {
        const int dx=col<7?7-col:col>340?col-340:0;
        const int dy=row<7?7-row:row>36?row-36:0;
        if(dx && dy && dx*dx+dy*dy>49)continue;
        u32 color=on?(hover?0xFF7B7B78:0xFF6D6D6B):0xFF50504F;
        if(selected) {
            const u32 r=255-col*17/347,g=250-col*66/347,b=237-col*106/347;
            color=0xFF000000|(r<<16)|(g<<8)|b;
            // Pale diagonal sheen at the crown, matching the supplied reference.
            if(col+row/2<43 || (col+row/2>=48 && col+row/2<52))color=0xFFFEFCF4;
        }
        pixels[(y+row)*stride+6+col]=color;
    }
    at<u8>(surface,0x1C)=1;
}
static void questDraw(void* w) {
    if(!w || !VipQuestState.mode || !at<int>(w,0x28)) return;
    const int height=questHeight(VipQuestState.mode);
    if(at<int>(w,0x18)!=height)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,360,height);
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    rect(w,0,0,360,height,0xFFBACDE8);rect(w,1,19,358,height-20,0xFFFFFFFF);
    rect(w,1,1,358,17,0xFFDCE9FA);text(w,VipQuestState.mode==4?"VIP Buffs":VipQuestState.mode==3?"Purchase VIP":"VIP Upgrade Quest",8,3,320,0x634529);
    if(VipQuestState.mode==1) text(w,"Do you want to upgrade your VIP?",34,40,304,0x342A26);
    else if(VipQuestState.mode==5) {
        text(w,"Submit these requirements and upgrade your VIP?",22,32,316,0x342A26);
        text(w,"Required items and Zeny will be consumed.",22,52,316,0x7A6555);
    }
    else if(VipQuestState.mode==4) {
        text(w,VipState.p.buffPrompt,22,35,316,0x342A26);
        text(w,"Available once every hour per account.",22,54,316,0x7A6555);
    }
    else if(VipQuestState.mode==3) {
        // Keep the rounded card corners and gaps blended into the white popup.
        rect(w,1,19,358,250,0xFFFFFFFF);
        for(int i=0;i<5;++i) {
            const int y=25+i*48;const bool selected=VipQuestState.selected==i,on=offerAllowed(i);
            membershipCard(w,y,selected,VipQuestState.hover==40+i,on);
            picture(w,14,16,y+8,28,28,0,0,0,0,on?255:110);
            const auto& offer=VipState.p.offers[i];char caption[48],days[24];number(days,offer.minutes/1440);
            int n=0;for(int j=0;days[j];++j)caption[n++]=days[j];
            const char* tail=offer.minutes==1440?" DAY VIP":" DAYS VIP";while(*tail)caption[n++]=*tail++;caption[n]=0;
            VipApi.offerText(w,caption,54,y+15,135,!on?0xA0A0A0:selected?0x355378:0xFFFFFF);
            char price[32];number(price,offer.cost);n=0;while(price[n])++n;price[n++]='z';price[n]=0;
            VipApi.priceText(w,on?price:"Unavailable",193,y+11,148,!on?0xAAAAAA:selected?0x355378:0xFFFFFF);
        }
        text(w,purchaseReady()?"Click Purchase to buy the selected membership.":"Select a VIP duration to purchase.",12,275,338,0x7A6555);
    }
    else {
        for(int i=0;i<3;++i) {
            const auto& item=VipState.p.questItems[i];if(!item.id)continue;
            const int y=25+i*48;
            rect(w,6,y,348,44,0xFFC3D4EC);rect(w,7,y+1,346,42,0xFFF3F7FF);
            image(w,2,13,y+6);
            VipApi.item(w,item.id,13,y+6);
            char amount[24],owned[24];number(amount,item.amount);number(owned,item.owned);
            text(w,amount,59,y+5,58,0x342A26);text(w,item.name,120,y+5,224,0x342A26);
            text(w,"Inventory:",59,y+23,60,0x7A6555);text(w,owned,120,y+23,100,item.owned>=item.amount?0x38793F:0x5858A0);
        }
        char cost[24];number(cost,VipState.p.questCost);
        int end=0;while(cost[end])++end;cost[end]='z';cost[end+1]=0;
        const int shift=(3-questRows())*48;
        text(w,"Zeny required:",12,175-shift,90);text(w,cost,108,175-shift,230,0x342A26);
        text(w,VipState.p.questStatus,12,195-shift,338,0x7A6555);
        text(w,"Cancel closes this window; your quest stays saved.",12,213-shift,338,0x888888);
    }
    for(const auto& source:questControls) if(questControl(source)) {
        const auto c=placedQuestControl(source);
        const bool on=questEnabled(c);
        paintButton(w,c,!on?3:VipQuestState.pressed==c.id?2:VipQuestState.hover==c.id?1:0);
    }
}
static void questHide() {
    if(VipQuestState.window) {release(VipQuestState.window);at<int>(VipQuestState.window,0x28)=0;}
    VipQuestState.mode=0;VipQuestState.hover=0;VipQuestState.selected=-1;
}
static void questFront() {
    if(VipQuestState.mode && VipQuestState.window && at<int>(VipQuestState.window,0x28))
        // Native manager moves an existing root to the END of its draw list.
        // AddTopLevelFront (A2D240) inserts at the beginning, behind older roots.
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA39130)((void*)0x131F4E8,VipQuestState.window);
}
EXPORT void __stdcall VipQuestOpen(int mode) {
    if(!VipState.ready || VipState.hidden || mode<1 || mode>5 || (mode==2 && !(VipState.p.flags&32)) ||
        (mode==3 && (VipState.p.flags&257)) || (mode==4 && !buffsReady()) ||
        (mode==5 && ((VipState.p.flags&165)!=165 || VipQuestState.mode!=2))) return;
    void* w=VipQuestState.window;
    if(!w) {
        w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4);if(!w)return;
        reinterpret_cast<void (__thiscall *)(void*,int)>(0x86B950)(w,0);at<u32>(w,0)=VipApi.vtable;
        at<int>(w,0x2C)=0x3FD;VipQuestState.window=w;
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA2D240)((void*)0x131F4E8,w);
    }
    release(w);VipQuestState.mode=mode;VipQuestState.hover=0;VipQuestState.selected=-1;
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,360,questHeight(mode));
    at<int>(w,0x1C)=at<int>(VipState.window,0x1C)+188;at<int>(w,0x20)=at<int>(VipState.window,0x20)+72;
    at<int>(w,0x28)=1;dirty(w);questFront();
}
EXPORT void __fastcall VipDraw(void* w,void*) {
    if(w==VipQuestState.window) {questDraw(w);return;}
    if(!w || !at<int>(w,0x28) || at<int>(w,0x14)<800 || at<int>(w,0x18)<420) return;
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    rect(w,0,0,800,420,0xFFFFFFFF);
    picture(w,0,0,0,800,420,0,0,736,420);
    text(w,"VIP MEMBERSHIP",20,3,740,0x634529);
    rect(w,12,28,350,367,0xFFF7FAFF);image(w,11,371,28);
    // Cover only the template's marketplace wording, retaining its artwork.
    rect(w,397,47,366,12,0xFFFCF5E8);text(w,"Benefits require active VIP membership.",451,46,312,0x886341);
    rect(w,396,79,370,25,0xFFF2F8FF);text(w,"VIP BENEFITS",544,86,190,0x886341);
    rect(w,20,48,92,166,0xFFE8EFF9);
    VipPortrait(w,20,48,92,166);
    for(int y=54;y<=122;y+=34)rect(w,122,y,234,28,0xFFF1DADB);
    field(w,"Name: ",VipState.p.player,62,true);
    field(w,"VIP Start Date: ",VipState.p.issued,96);
    field(w,"VIP Expiry Date: ",VipState.p.expires,130);
    if((VipState.p.flags&1) && VipState.p.buffRemaining) {
        const u32 secs=VipState.p.buffRemaining>359999?359999:VipState.p.buffRemaining;
        char wait[9];const u32 hrs=secs/3600,mins=secs/60%60,seconds=secs%60;
        wait[0]=static_cast<char>('0'+hrs/10);wait[1]=static_cast<char>('0'+hrs%10);wait[2]=':';
        wait[3]=static_cast<char>('0'+mins/10);wait[4]=static_cast<char>('0'+mins%10);wait[5]=':';
        wait[6]=static_cast<char>('0'+seconds/10);wait[7]=static_cast<char>('0'+seconds%10);wait[8]=0;
        text(w,wait,273,195,80,0x7A6555); // Server snapshot owns readiness; no client-clock unlock.
    }
    text(w,"VIP EXP",160,235,95,0x282828);
    if(showExperience())text(w,VipState.p.experience,24,252,322);
    // The supplied strip includes both fill and empty colors. Preserve its
    // exact green/track pixels while sizing the fill from the server's percent.
    // Gold means full EXP AND a server-authorized upgrade, not level 10's full bar.
    // Stretch opaque interior columns, never the transparent end cap. Both the
    // empty track and colored fill stay exactly four pixels high to their ends.
    picture(w,1,24,272,322,4,104,0,7,4);
    const u32 pct=VipState.p.percent>100?100:VipState.p.percent;
    const bool upgradeReady=pct==100 && (VipState.p.flags&8) && VipState.p.level<10;
    if(pct && showExperience())picture(w,1,24,272,static_cast<int>(pct*322/100),4,2,0,62,4,255,upgradeReady);
    char level[24],caption[40];number(level,VipState.p.level);int n=0;
    const char* prefix="Vip Level : ";while(*prefix)caption[n++]=*prefix++;
    for(int i=0;level[i];++i)caption[n++]=level[i];caption[n]=0;
    text(w,caption,22,299,220,0x282828);
    for(u32 i=0;i<10;++i) {
        const int x=23+static_cast<int>(i)*32;
        rect(w,x,324,28,28,i<VipState.p.level?0xFFDFB355:0xFFD4DFEF);
        rect(w,x+1,325,26,26,0xFFF4F8FF);if(i<VipState.p.level)picture(w,14,x+2,326,24,24,0,0,0,0);
    }
    text(w,VipState.p.upgrade,22,356,328);
    text(w,VipState.p.membership,14,400,345,0x7A6555);
    text(w,VipState.p.status,22,219,330,0x88725A);
    // Remove the template's inactive placeholder cards, including after expiry.
    rect(w,396,109,372,257,0xFFF2F8FF);clampBenefitScroll();
    const int count=benefitRows();
    for(int row=0;row<visibleBenefits && VipState.scroll+row<count;++row) {
        char effect[80];benefitRows(VipState.scroll+row,effect);
        const int y=112+row*48;
        picture(w,11,402,y,364,44,31,84,340,44);
        rect(w,402,y+4,3,35,0xFFDFB355);
        centeredText(w,effect,413,y+15,342,0x5D4C3B);
    }
    rect(w,779,133,5,207,0xFFDDE5F2);
    if(count>visibleBenefits) {
        const int thumb=207*visibleBenefits/count<16?16:207*visibleBenefits/count;
        const int y=133+(207-thumb)*VipState.scroll/(count-visibleBenefits);
        rect(w,779,y,5,thumb,0xFF9DADC8);
    }
    for(const auto& c:controls)paintButton(w,c,!enabled(c)?3:VipState.pressed==c.id?2:VipState.hover==c.id?1:0);
}
EXPORT void __stdcall VipOpen() {
    void* w=VipState.window;
    if(!w) {
        w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4); if(!w) return;
        reinterpret_cast<void (__thiscall *)(void*,int)>(0x86B950)(w,0);
        at<u32>(w,0)=VipApi.vtable;
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,800,420);
        at<int>(w,0x2C)=0x3FC;
        at<int>(w,0x1C)=80; at<int>(w,0x20)=80;
        VipState.window=w;
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA2D240)((void*)0x131F4E8,w);
    }
    release(w); VipState.hidden=0; VipState.hover=0; VipState.scroll=0;
    at<int>(w,0x28)=1; VipState.refresh=tick(); startTimer(); dirty(w);
    // Registration inserts behind existing HUD roots. Raise on every explicit
    // open/reopen so covered Inventory/Equipment menu buttons cannot win clicks.
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA39130)((void*)0x131F4E8,w);
}
EXPORT int __stdcall VipReceive(const Snapshot* p) {
    if(!p || p->id!=0xA1C || p->length!=sizeof(Snapshot) || p->magic!=0x55504956 || p->version!=4 ||
        !p->token || p->level>10 || p->percent>100 || (p->flags&~2047) || p->questLevel>10) return 0;
    if(!(p->flags&2) && (!VipState.ready || VipState.hidden || p->token!=VipState.p.token)) return 0;
    bool changedQuest=VipState.p.token!=p->token || VipState.p.level!=p->level ||
        VipState.p.questLevel!=p->questLevel || VipState.p.questCost!=p->questCost;
    for(int i=0;i<3;++i)if(VipState.p.questItems[i].id!=p->questItems[i].id ||
        VipState.p.questItems[i].amount!=p->questItems[i].amount)changedQuest=true;
    const u8* src=reinterpret_cast<const u8*>(p); u8* dst=reinterpret_cast<u8*>(&VipState.p);
    for(u32 i=0;i<sizeof(Snapshot);++i) dst[i]=src[i];
    // Never hand an unterminated packet string to a native text helper.
    VipState.p.player[23]=VipState.p.issued[31]=VipState.p.expires[31]=0;
    VipState.p.experience[63]=VipState.p.status[95]=VipState.p.upgrade[63]=VipState.p.membership[95]=0;
    for(auto& b:VipState.p.benefits) b.title[23]=b.line1[79]=b.line2[79]=0;
    clampBenefitScroll(); // Refresh preserves position, expiry/content shrink clamps it.
    VipState.p.questStatus[63]=0;for(auto& item:VipState.p.questItems)item.name[47]=0;
    VipState.p.buffPrompt[95]=0;
    VipState.ready=1;
    // QuestActive describes saved data; only QuestOpen (response to Upgrade)
    // asks for the popup. Ordinary roulette/VIP opens show the main card alone.
    if(p->flags&2) {questHide();VipOpen();if(p->flags&64)VipQuestOpen(2);}
    else {
        if(VipQuestState.mode==5 && (changedQuest || (p->flags&165)!=165)) {
            release(VipQuestState.window);
            if((p->flags&37)==37)VipQuestOpen(2);else questHide();
        }
        dirty(VipState.window);dirty(VipQuestState.window);
        if((!(p->flags&32) && VipQuestState.mode==2) || ((p->flags&257) && VipQuestState.mode==3) ||
            (VipQuestState.mode==4 && !buffsReady()))questHide();
        if(VipQuestState.mode==3 && VipQuestState.selected>=0 && !purchaseReady()) {
            VipQuestState.selected=-1;VipQuestState.pressed=0;
        }
    }
    return 1;
}
EXPORT void __fastcall VipDown(void* w,void*,int x,int y) {
    if(w==VipState.window && VipQuestState.mode) {release(w);questFront();return;}
    if(w==VipQuestState.window) {
        release(w);VipQuestState.pressed=questHit(x,y);
        VipQuestState.itemPressed=questItemHit(w,x,y);
        if(VipQuestState.itemPressed) {
            if(at<void*>((void*)0x131F4E8,0x19C)){VipQuestState.itemPressed=0;return;}
            VipQuestState.itemId=VipState.p.questItems[VipQuestState.itemPressed-1].id;
            VipQuestState.itemToken=VipState.p.token;
            reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);
        }
        if(VipQuestState.pressed)reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);
        else if(y>=0 && y<18){VipQuestState.dragging=1;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880AD0)(w,x,y);}
        dirty(w);return;
    }
    release(w); VipState.pressed=VipHit(x,y);
    if(VipState.pressed) reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);
    else if(y>=0 && y<18) {
        VipState.dragging=1;
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880AD0)(w,x,y);
    }
    dirty(w);
}
EXPORT void __fastcall VipUp(void* w,void*,int x,int y) {
    if(w==VipState.window && VipQuestState.mode) {release(w);questFront();return;}
    if(w==VipQuestState.window) {
        const int slot=VipQuestState.itemPressed;const u32 id=VipQuestState.itemId,token=VipQuestState.itemToken;
        const int pressed=VipQuestState.pressed,hit=questHit(x,y);release(w);
        if(slot){inspectItem(w,x,y,slot,id,token);dirty(w);return;}
        if(pressed==hit && hit>=40 && hit<45) {
            VipQuestState.selected=hit-40;VipQuestState.chosen=VipState.p.offers[hit-40];dirty(w);return;
        }
        if(pressed && hit==pressed)for(const auto& c:questControls)if(c.id==hit) {
            if(c.id==23)VipQuestOpen(5);
            else if(c.action==-5 || (c.action==-3 && VipQuestState.mode==5))VipQuestOpen(2);
            else if(c.action==-3)questHide();
            else if(c.action==-4) {if(purchaseReady()){send(8+VipQuestState.selected,VipQuestState.chosen.minutes,VipQuestState.chosen.cost);hide(false);}}
            else {send(c.action);hide(false);}break;
        }
        dirty(w);return;
    }
    int pressed=VipState.pressed,hit=VipHit(x,y); release(w);
    if(!pressed || hit!=pressed) {dirty(w);return;}
    for(const auto& c:controls) if(c.id==hit) {
        if(c.action==-1) --VipState.scroll;
        else if(c.action==-2) ++VipState.scroll;
        else if(c.id==1) hide(true);
        else if(c.id==2) VipQuestOpen(3);
        else if(c.id==5) VipQuestOpen(4);
        else if(c.id==6) {
            if(VipState.p.level>=5 && VipState.p.level<10 && !(VipState.p.flags&32)) {
                send(4);VipState.refresh=tick();hide(false); // Server prepares the one-ticket popup.
            } else VipQuestOpen((VipState.p.flags&32)?2:1);
        }
        else { send(c.action); VipState.refresh=tick(); if(c.action) hide(false); }
        break;
    }
    dirty(w);
}
EXPORT void __fastcall VipRightDown(void* w,void*,int x,int y) {
    VipQuestState.rightPressed=0;
    // Native right-up is only dispatched on the uncaptured route. Never acquire
    // left/drag capture here, or clear capture belonging to another window.
    if(at<void*>((void*)0x131F4E8,0x19C) || VipQuestState.pressed || VipQuestState.itemPressed)return;
    const int slot=questItemHit(w,x,y);if(!slot)return;
    VipQuestState.rightPressed=slot;VipQuestState.rightId=VipState.p.questItems[slot-1].id;
    VipQuestState.rightToken=VipState.p.token;
}
EXPORT void __fastcall VipRightUp(void* w,void*,int x,int y) {
    const int slot=VipQuestState.rightPressed;VipQuestState.rightPressed=0;
    inspectItem(w,x,y,slot,VipQuestState.rightId,VipQuestState.rightToken);
}
EXPORT void __fastcall VipMove(void* w,void*,int x,int y) {
    if(!*reinterpret_cast<int*>(0x11E40E8))VipQuestState.rightPressed=0;
    if(VipQuestState.rightPressed && VipQuestState.rightPressed!=questItemHit(w,x,y))VipQuestState.rightPressed=0;
    if(w==VipQuestState.window)VipQuestState.hover=questHit(x,y);else VipState.hover=VipHit(x,y);dirty(w);
}
EXPORT void __fastcall VipDrag(void* w,void*,int x,int y) {
    if(w==VipQuestState.window?VipQuestState.dragging:VipState.dragging) reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880E00)(w,x,y);
    else VipMove(w,0,x,y);
}
EXPORT void __fastcall VipCursor(void* w,void*,int x,int y) {
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA23470)(w,x,y);
    VipMove(w,0,x,y);
    void* cursor=*reinterpret_cast<void**>(0x121333C);
    if(cursor) reinterpret_cast<void (__thiscall *)(void*,int)>(0xA764A0)(cursor,((w==VipQuestState.window?VipQuestState.hover:VipState.hover) || questItemHit(w,x,y))?2:0);
}
EXPORT void* __fastcall VipDestroy(void* w,void*,int flags) {
    if(w==VipQuestState.window) {questHide();VipQuestState.window=0;return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);}
    hide(false); VipState.window=0; VipState.p.token=0;
    if(VipPortraitCanvas){reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(VipPortraitCanvas,1);VipPortraitCanvas=0;}
    return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);
}
