// Freestanding x86, 2025-07-16 Ragexe. No DLL/imports or shared text hooks.
// Only this frame owns its input, surface, assets and VIPU snapshot.
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#define EXPORT extern "C" __declspec(dllexport)
#pragma pack(push,1)
struct Benefit { char title[24], line1[80], line2[80]; };
struct QuestItem { u32 id,amount,owned; char name[48]; };
struct Snapshot {
    u16 id,length; u32 magic; u16 version,flags; u32 token,level,percent;
    char player[24],issued[32],expires[32],experience[64],status[96],upgrade[64],membership[96];
    Benefit benefits[10];
    u32 questCost,questLevel;char questStatus[64];QuestItem questItems[3];
};
struct Request { u16 id,length; u32 magic; u16 version,action; u32 token; };
#pragma pack(pop)
static_assert(sizeof(Snapshot)==2524 && sizeof(Request)==16,"VIPU v2");
struct Api {
    u32 version,vtable,ctor,send;
    void (__stdcall *fit)(void*,const char*,int,int,int,u32);
    void (__stdcall *plain)(void*,const char*,int,int,int,u32);
    void (__thiscall *png)(void*,int,int,void*,int);
    const char* paths[12];
    u32 moduleIat,procIat;
    void (__stdcall *item)(void*,u32,int,int);
};
EXPORT Api VipApi = {2};
struct State { void* window; int pressed,hover,dragging,hidden,scroll,ready; u32 refresh; Snapshot p;
    u32 timer; u32 (__stdcall *setTimer)(void*,u32,u32,void*); int (__stdcall *killTimer)(void*,u32);
};
EXPORT State VipState = {};
struct QuestState { void* window;int pressed,hover,dragging,mode; };
EXPORT QuestState VipQuestState = {};
static void questHide();
template<typename T> T& at(void* p,int off) { return *reinterpret_cast<T*>(static_cast<u8*>(p)+off); }
static u32 tick() { return (*reinterpret_cast<u32 (__stdcall **)()>(0xFC17B0))(); }
static void dirty(void* w) { if(w) at<int>(w,0x58)=1; }
static void release(void* w) {
    int& dragging=w==VipQuestState.window?VipQuestState.dragging:VipState.dragging;
    if(dragging) {
        dragging=0;
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880BB0)(w,0,0);
    }
    if(at<void*>((void*)0x131F4E8,0x19C)==w)
        reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);
    (w==VipQuestState.window?VipQuestState.pressed:VipState.pressed)=0;
}
static void send(int action) {
    if(!VipState.ready || !VipState.p.token) return;
    Request r={0x0BFA,16,0x55504956,2,static_cast<u16>(action),VipState.p.token};
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
struct Control { int id,x,y,w,h,action,flag; const char* label; };
static const Control controls[]={
    {1,714,2,18,16,6,0,"X"},
    {2,122,164,67,22,1,0,"Apply VIP"},
    {3,194,164,75,22,2,16,"Open Store"},
    {4,122,192,91,22,3,0,"Open Storage"},
    {5,218,192,73,22,5,1,"VIP Buffs"},
    {6,240,294,62,22,4,8,"Upgrade"},
    {7,709,56,16,20,-1,0,"^"},
    {8,709,372,16,20,-2,0,"v"},
    {9,244,374,58,22,0,0,"Refresh"}
};
static bool enabled(const Control& c) {
    if(c.id==1) return true;
    if(!VipState.ready || VipState.hidden) return false;
    if(c.id==7) return VipState.scroll>0;
    if(c.id==8) return VipState.scroll<4;
    return !c.flag || (VipState.p.flags & c.flag)!=0;
}
EXPORT int __stdcall VipHit(int x,int y) {
    if(!VipState.window || VipState.hidden || !at<int>(VipState.window,0x28)) return 0;
    if(VipQuestState.mode) return 0;
    for(const auto& c: controls) if(enabled(c) && x>=c.x && y>=c.y && x<c.x+c.w && y<c.y+c.h) return c.id;
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
static void image(void* w,int asset,int x,int y) {
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)(); if(!mgr) return;
    const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(VipApi.paths[asset]); if(!path) return;
    void* tex=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path); if(!tex) return;
    VipApi.png(w,x,y,tex,0); // private helper retains original opaque surface mode
}
static const Control questControls[]={
    {20,338,2,18,16,-3,0,"X"},
    {21,120,76,48,22,4,8,"Yes"},{22,180,76,48,22,-3,0,"No"},
    {23,106,238,74,22,7,128,"Upgrade"},{24,188,238,66,22,-3,0,"Cancel"}
};
static bool questControl(const Control& c) {
    return VipQuestState.mode && (c.id==20 || (VipQuestState.mode==1?c.id==21 || c.id==22:c.id==23 || c.id==24));
}
static int questHit(int x,int y) {
    for(const auto& c:questControls) if(questControl(c) && (!c.flag || (VipState.p.flags&c.flag)) &&
        x>=c.x && y>=c.y && x<c.x+c.w && y<c.y+c.h) return c.id;
    return 0;
}
static void number(char* out,u32 value) {
    char reverse[24];int n=0;do{reverse[n++]=static_cast<char>('0'+value%10);value/=10;}while(value);
    int p=0;for(int i=n-1;i>=0;--i) {out[p++]=reverse[i];if(i && i%3==0)out[p++]=',';}out[p]=0;
}
static void questDraw(void* w) {
    if(!w || !VipQuestState.mode || !at<int>(w,0x28)) return;
    const int height=VipQuestState.mode==1?118:270;
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    rect(w,0,0,360,height,0xFFBACDE8);rect(w,1,19,358,height-20,0xFFFFFFFF);
    rect(w,1,1,358,17,0xFFDCE9FA);text(w,"VIP UPGRADE QUEST",8,3,320,0x634529);
    if(VipQuestState.mode==1) text(w,"Do you want to upgrade your VIP?",34,40,304,0x342A26);
    else {
        for(int i=0;i<3;++i) {
            const auto& item=VipState.p.questItems[i];if(!item.id)continue;
            const int y=25+i*48;
            rect(w,6,y,348,44,0xFFC3D4EC);rect(w,7,y+1,346,42,0xFFF3F7FF);
            rect(w,12,y+5,34,34,0xFFD3DFF2);rect(w,13,y+6,32,32,0xFFEEF4FF);
            VipApi.item(w,item.id,13,y+6);
            char amount[24],owned[24];number(amount,item.amount);number(owned,item.owned);
            text(w,amount,59,y+5,58,0x342A26);text(w,item.name,120,y+5,224,0x342A26);
            text(w,"In bag:",59,y+23,50,0x7A6555);text(w,owned,110,y+23,90,item.owned>=item.amount?0x38793F:0x5858A0);
        }
        char cost[24];number(cost,VipState.p.questCost);
        text(w,"Zeny required:",12,175,90);text(w,cost,108,175,230,0x342A26);
        text(w,VipState.p.questStatus,12,195,338,0x7A6555);
        text(w,"Cancel closes this window; your quest stays saved.",12,213,338,0x888888);
    }
    for(const auto& c:questControls) if(questControl(c)) {
        const bool on=!c.flag || (VipState.p.flags&c.flag);
        u32 color=on?0xFFDFECFD:0xFFEAECEF;
        if(on && VipQuestState.hover==c.id)color=0xFFC6DFFA;
        if(on && VipQuestState.pressed==c.id)color=0xFFB4CEEA;
        rect(w,c.x,c.y,c.w,c.h,0xFFBDCAE0);rect(w,c.x+1,c.y+1,c.w-2,c.h-2,color);
        text(w,c.label,c.x+5,c.y+4,c.w-10,on?0x886341:0x999999);
    }
}
static void questHide() {
    if(VipQuestState.window) {release(VipQuestState.window);at<int>(VipQuestState.window,0x28)=0;}
    VipQuestState.mode=0;VipQuestState.hover=0;
}
EXPORT void __stdcall VipQuestOpen(int mode) {
    if(!VipState.ready || VipState.hidden || (mode!=1 && mode!=2) || (mode==2 && !(VipState.p.flags&32))) return;
    void* w=VipQuestState.window;
    if(!w) {
        w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4);if(!w)return;
        reinterpret_cast<void (__thiscall *)(void*,int)>(0x86B950)(w,0);at<u32>(w,0)=VipApi.vtable;
        at<int>(w,0x2C)=0x3FD;VipQuestState.window=w;
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA2D240)((void*)0x131F4E8,w);
    }
    release(w);VipQuestState.mode=mode;VipQuestState.hover=0;
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,360,mode==1?118:270);
    at<int>(w,0x1C)=at<int>(VipState.window,0x1C)+188;at<int>(w,0x20)=at<int>(VipState.window,0x20)+72;
    at<int>(w,0x28)=1;dirty(w);
}
EXPORT void __fastcall VipDraw(void* w,void*) {
    if(w==VipQuestState.window) {questDraw(w);return;}
    if(!w || !at<int>(w,0x28) || at<int>(w,0x14)<736 || at<int>(w,0x18)<420) return;
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    rect(w,0,0,736,420,0xFFFFFFFF); image(w,0,0,0);
    text(w,"VIP MEMBERSHIP",20,3,680,0x634529);
    rect(w,12,28,296,367,0xFFF7FAFF); rect(w,320,28,408,367,0xFFF1F5FC);
    text(w,"VIP BENEFITS",452,36,160,0x402A18);
    text(w,"Additional level bonuses; membership must be active.",331,399,390,0x878787);
    // A membership badge uses supplied art; no invented player sprite paths.
    rect(w,20,48,92,166,0xFFE8EFF9);
    for(int y=60;y<186;y+=21) rect(w,25,y,82,1,0xFFF7FAFF);
    text(w,"VIP",51,97,50,0x88611F); image(w,3,53,121);
    text(w,(VipState.p.flags&1)?"ACTIVE":"INACTIVE",36,170,72,(VipState.p.flags&1)?0x4B783F:0x858585);
    for(int y=54;y<=122;y+=34) rect(w,122,y,180,28,0xFFF1DADB);
    text(w,"NAME",128,55,168,0x54464D);
    VipApi.plain(w,VipState.p.player,128,68,168,0x342A26);
    text(w,"ISSUED",128,89,168,0x54464D); text(w,VipState.p.issued,128,102,168,0x342A26);
    text(w,"EXPIRATION",128,123,168,0x54464D); text(w,VipState.p.expires,128,136,168,0x342A26);
    text(w,"VIP EXP",124,235,95,0x282828); text(w,VipState.p.experience,24,252,275);
    rect(w,24,272,274,7,0xFFDDE5F5);
    const u32 pct=VipState.p.percent>100?100:VipState.p.percent;
    rect(w,24,272,static_cast<int>(pct*274/100),7,0xFF5CB78A);
    text(w,"VIP LEVEL",22,299,75,0x282828);
    for(u32 i=0;i<10;++i) {
        rect(w,23+static_cast<int>(i)*27,326,23,25,0xFFD4DFEF);
        rect(w,24+static_cast<int>(i)*27,327,21,23,0xFFF4F8FF);
        if(i<VipState.p.level) image(w,3,25+static_cast<int>(i)*27,332);
    }
    text(w,VipState.p.upgrade,22,356,280);
    text(w,VipState.p.membership,14,400,304,0x7A6555);
    text(w,VipState.p.status,22,219,282,0x88725A);
    if(VipState.scroll<0 || VipState.scroll>4) VipState.scroll=0;
    for(int i=0;i<6;++i) {
        const auto& b=VipState.p.benefits[i+VipState.scroll]; int y=58+i*55;
        rect(w,328,y,373,50,0xFFE2E8F8);
        rect(w,328,y,3,50,(VipState.p.flags&1) && VipState.p.level==static_cast<u32>(i+VipState.scroll+1)?0xFFDFB355:0xFFCFD9EE);
        text(w,b.title,338,y+4,354,0x88611F);
        text(w,b.line1,338,y+19,354,0x5D4C3B);
        text(w,b.line2,338,y+33,354,0x6F665F);
    }
    rect(w,714,81,5,285,0xFFDDE5F2); rect(w,713,81+VipState.scroll*48,7,93,0xFFA8B9D9);
    for(const auto& c:controls) {
        const bool on=enabled(c); u32 col=on?0xFFDFECFD:0xFFEAECEF;
        if(on && VipState.hover==c.id) col=0xFFC6DFFA;
        if(on && VipState.pressed==c.id) col=0xFFB4CEEA;
        rect(w,c.x,c.y,c.w,c.h,0xFFBDCAE0); rect(w,c.x+1,c.y+1,c.w-2,c.h-2,col);
        if(c.id==3 && on) image(w,VipState.pressed==c.id?6:VipState.hover==c.id?5:4,c.x+4,c.y+2);
        if(c.id==6) image(w,!on?10:VipState.pressed==c.id?9:VipState.hover==c.id?8:7,c.x+3,c.y+2);
        // Button labels are rendered only once, consistently with click bounds.
        if((c.id!=3 || !on) && c.id!=6) text(w,c.label,c.x+(c.w<20?3:5),c.y+4,c.w-(c.w<20?6:10),on?0x886341:0x999999);
    }
}
EXPORT void __stdcall VipOpen() {
    void* w=VipState.window;
    if(!w) {
        w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4); if(!w) return;
        reinterpret_cast<void (__thiscall *)(void*,int)>(0x86B950)(w,0);
        at<u32>(w,0)=VipApi.vtable;
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,736,420);
        at<int>(w,0x2C)=0x3FC;
        at<int>(w,0x1C)=80; at<int>(w,0x20)=80;
        VipState.window=w;
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA2D240)((void*)0x131F4E8,w);
    }
    release(w); VipState.hidden=0; VipState.hover=0; VipState.scroll=0;
    at<int>(w,0x28)=1; VipState.refresh=tick(); startTimer(); dirty(w);
}
EXPORT int __stdcall VipReceive(const Snapshot* p) {
    if(!p || p->id!=0xA1C || p->length!=sizeof(Snapshot) || p->magic!=0x55504956 || p->version!=2 ||
        !p->token || p->level>10 || p->percent>100 || (p->flags&~255) || p->questLevel>10) return 0;
    if(!(p->flags&2) && (!VipState.ready || VipState.hidden || p->token!=VipState.p.token)) return 0;
    const u8* src=reinterpret_cast<const u8*>(p); u8* dst=reinterpret_cast<u8*>(&VipState.p);
    for(u32 i=0;i<sizeof(Snapshot);++i) dst[i]=src[i];
    // Never hand an unterminated packet string to a native text helper.
    VipState.p.player[23]=VipState.p.issued[31]=VipState.p.expires[31]=0;
    VipState.p.experience[63]=VipState.p.status[95]=VipState.p.upgrade[63]=VipState.p.membership[95]=0;
    for(auto& b:VipState.p.benefits) b.title[23]=b.line1[79]=b.line2[79]=0;
    VipState.p.questStatus[63]=0;for(auto& item:VipState.p.questItems)item.name[47]=0;
    VipState.ready=1;
    if(p->flags&2) {questHide();VipOpen();if(p->flags&32)VipQuestOpen(2);}
    else {dirty(VipState.window);dirty(VipQuestState.window);if(!(p->flags&32) && VipQuestState.mode==2)questHide();}
    return 1;
}
EXPORT void __fastcall VipDown(void* w,void*,int x,int y) {
    if(w==VipQuestState.window) {
        release(w);VipQuestState.pressed=questHit(x,y);
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
    if(w==VipQuestState.window) {
        const int pressed=VipQuestState.pressed,hit=questHit(x,y);release(w);
        if(pressed && hit==pressed)for(const auto& c:questControls)if(c.id==hit) {
            if(c.action==-3)questHide();else {send(c.action);hide(false);}break;
        }
        dirty(w);return;
    }
    int pressed=VipState.pressed,hit=VipHit(x,y); release(w);
    if(!pressed || hit!=pressed) {dirty(w);return;}
    for(const auto& c:controls) if(c.id==hit) {
        if(c.action==-1) --VipState.scroll;
        else if(c.action==-2) ++VipState.scroll;
        else if(c.id==1) hide(true);
        else if(c.id==6) VipQuestOpen((VipState.p.flags&32)?2:1);
        else { send(c.action); VipState.refresh=tick(); if(c.action) hide(false); }
        break;
    }
    dirty(w);
}
EXPORT void __fastcall VipMove(void* w,void*,int x,int y) {
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
    if(cursor) reinterpret_cast<void (__thiscall *)(void*,int)>(0xA764A0)(cursor,(w==VipQuestState.window?VipQuestState.hover:VipState.hover)?2:0);
}
EXPORT void* __fastcall VipDestroy(void* w,void*,int flags) {
    if(w==VipQuestState.window) {questHide();VipQuestState.window=0;return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);}
    hide(false); VipState.window=0; VipState.p.token=0;
    return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);
}
