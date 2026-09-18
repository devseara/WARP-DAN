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
    const char* design;
    void (__stdcall *infoText)(void*,const char*,int,int,int,u32);
    void (__stdcall *infoPlain)(void*,const char*,int,int,int,u32);
    void (__stdcall *statusText)(void*,const char*,int,int,int,u32);
    void (__stdcall *bodyText)(void*,const char*,int,int,int,u32);
    const char* mainButtons[2][4]; // Readable main Upgrade and X; popup sizes unchanged.
};
static_assert(sizeof(Api)==372,"Append-only readable VIP API");
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
// Private request sequencing; no wire/schema or server cooldown changes.
// phase: 0 idle, 1 queued behind refresh, 2 sent once, 3 delayed reply.
struct Interaction {
    int phase,action;u32 token,level,questLevel,questCost;
    QuestItem items[3];
    u32 pollSent,lastReply,sentAt;int pollPending,notice;
    char benefit[80];
};
EXPORT Interaction VipInteraction = {};
static void questHide();
static void pumpUpgrade();
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
static bool send(int action,u32 minutes=0,u32 cost=0) {
    if(!VipState.ready || !VipState.p.token) return false;
    Request r={0x0BFA,24,0x55504956,4,static_cast<u16>(action),VipState.p.token,minutes,cost};
    void* transport=reinterpret_cast<void* (__cdecl *)()>(VipApi.ctor)();
    if(!transport)return false;
    if(!action) {
        if(VipInteraction.pollPending || tick()-VipInteraction.lastReply<350)return false;
        VipInteraction.pollPending=1;VipInteraction.pollSent=tick();
        VipState.refresh=VipInteraction.pollSent;
    }
    reinterpret_cast<void (__thiscall *)(void*,int,const void*)>(VipApi.send)(transport,sizeof(r),&r);
    return true;
}
static void hide(bool notify) {
    if(notify) send(6);
    questHide();
    if(VipState.window) { release(VipState.window); at<int>(VipState.window,0x28)=0; }
    VipState.hidden=1; VipState.ready=0; VipState.hover=0;
    VipInteraction.phase=VipInteraction.pollPending=VipInteraction.notice=0;
    if(VipState.timer && VipState.killTimer) VipState.killTimer(0,VipState.timer);
    VipState.timer=0;
}
EXPORT void __stdcall VipTick(void*,u32,u32 id,u32) {
    if(!*reinterpret_cast<int*>(0x11E40E8))VipQuestState.rightPressed=0;
    if(id!=VipState.timer || !VipState.window || VipState.hidden || !VipState.ready) return;
    if(!at<int>(VipState.window,0x28)) return;
    pumpUpgrade();
    if(VipInteraction.phase)return;
    if(VipInteraction.pollPending && tick()-VipInteraction.pollSent>=10000) {
        VipInteraction.pollPending=0; // Only a read-only refresh can be retried.
    }
    // Keep 3-second polling even while a confirmation is open: this renews
    // the server's 120-second token and keeps eligibility current. Once Yes
    // queues an action, the phase guard above suppresses every further poll.
    if(tick()-VipState.refresh>=3000)send(0);
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
    if(VipState.setTimer && VipState.killTimer) VipState.timer=VipState.setTimer(0,0,100,reinterpret_cast<void*>(VipTick));
}
struct Control { int id,x,y,w,h,action,flag,art; };
static const int mainWidth=460,mainHeight=362;
static const int mainInfoFont=11,mainBodyFont=11;
static constexpr int X(int x){return x*mainWidth/1412;}
static constexpr int Y(int y){return y*mainHeight/1114;}
static const Control controls[]={
    {1,439,3,18,18,6,0,14},
    {2,153,120,128,22,1,0,1}, {3,289,120,128,22,2,16,2},
    {4,153,145,128,22,3,0,3}, {5,289,145,128,22,5,512,4},
    {6,164,252,60,20,4,8,13},
    {7,439,268,10,10,-1,0,10}, {8,439,328,10,10,-2,0,11},
    {9,164,320,60,20,0,0,6}
};
static void* designTexture() {
    if(!VipApi.design)return 0;
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return 0;
    const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(VipApi.design);if(!path)return 0;
    void* tex=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);
    return tex && at<int>(tex,0x114)==1412 && at<int>(tex,0x118)==1114 && at<void*>(tex,0x11C)?tex:0;
}
static void* buttonTexture(const Control& c,int state) {
    if(c.art<0 || c.art>14 || state<0 || state>=4)return 0;
    const char* file=c.art>=13?VipApi.mainButtons[c.art-13][state]:c.art==12?VipApi.purchaseButtons[state]:VipApi.buttons[c.art][state];if(!file)return 0;
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return 0;
    const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(file);if(!path)return 0;
    void* tex=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);
    if(!tex || at<int>(tex,0x114)!=c.w || at<int>(tex,0x118)!=c.h || !at<void*>(tex,0x11C))return 0;
    return tex;
}
static bool activeBenefits() { return (VipState.p.flags&5)==5 && VipState.p.level>0 && VipState.p.level<=10; }
static const int visibleBenefits=4;
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
    if(!designTexture() || !buttonTexture(c,0))return false; // No invisible actions without valid artwork.
    if(c.id==1) return true;
    if(!VipState.ready || VipState.hidden) return false;
    if(VipInteraction.phase)return false;
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
// Private VIP chrome. All coordinates, capture bounds and packet actions stay
// with their existing controls; colors here affect only this window's surface.
static u32 shade(u32 first,u32 last,int pos,int extent) {
    u32 value=0xFF000000;
    for(int shift=0;shift<24;shift+=8) {
        const int a=(first>>shift)&255,b=(last>>shift)&255;
        value|=static_cast<u32>(a+(b-a)*pos/extent)<<shift;
    }
    return value;
}
static void gradient(void* w,int x,int y,int width,int height,u32 top,u32 bottom) {
    if(height<2){rect(w,x,y,width,height,top);return;}
    for(int row=0;row<height;++row)rect(w,x,y+row,width,1,shade(top,bottom,row,height-1));
}
static void panel(void* w,int x,int y,int width,int height,u32 fill=0xFFF7FAFF,u32 edge=0xFFAFBED5) {
    rect(w,x,y,width,height,edge);
    rect(w,x+1,y+1,width-2,height-2,0xFFFFFFFF);
    rect(w,x+2,y+2,width-4,height-4,fill);
    rect(w,x+2,y+height-2,width-3,1,0xFFDCE5F1);
}
static void picture(void*,int,int,int,int,int,int,int,int,int,int=255,bool=false);
static void chrome(void* w,int width,int height) {
    // Nine-slice the approved outer frame; never stretch baked demo content.
    rect(w,0,0,width,height,0xFFF4FCFF);
    picture(w,15,0,0,8,20,0,0,14,77);
    picture(w,15,8,0,width-16,20,500,0,800,77);
    picture(w,15,width-8,0,8,20,1398,0,14,77);
    picture(w,15,0,20,5,height-28,0,100,9,940);
    picture(w,15,width-5,20,5,height-28,1403,100,9,940);
    picture(w,15,0,height-8,8,8,0,1106,14,8);
    picture(w,15,8,height-8,width-16,8,20,1106,1370,8);
    picture(w,15,width-8,height-8,8,8,1398,1106,14,8);
    picture(w,15,6,2,27,16,13,7,106,65);
}
static void text(void* w,const char* s,int x,int y,int width,u32 color=0x5A5A5A) { VipApi.fit(w,s,x,y,width,color); }
static const char* assetPath(int asset) { return asset==15?VipApi.design:asset==14?VipApi.crown:asset<12?VipApi.paths[asset]:VipApi.scrollPaths[asset-12]; }
static void image(void* w,int asset,int x,int y) {
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)(); if(!mgr) return;
    const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(assetPath(asset)); if(!path) return;
    void* tex=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path); if(!tex) return;
    VipApi.png(w,x,y,tex,0); // private helper retains original opaque surface mode
}
// Source-region UI composition, not a mutation of shared textures. Used for
// live EXP fill and the supplied requirement item box. Buttons use whole PNGs.
static void picture(void* w,int asset,int x,int y,int width,int height,
    int sx,int sy,int sw,int sh,int opacity,bool gold) {
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
static void designPatch(void* w,int x,int y,int width,int height,int sx,int sy,int sw,int sh) {
    picture(w,15,X(x),Y(y),X(x+width)-X(x),Y(y+height)-Y(y),sx,sy,sw,sh);
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
static void field(void* w,const char* label,const char* value,int y,u32 color,bool plain=false) {
    const int x=X(545),width=X(1345)-x;
    const int measured=reinterpret_cast<int (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA21C90)(w,label,0,0,mainInfoFont,0,0);
    VipApi.infoText(w,label,x,y,width,0x30170C);
    if(measured<0 || measured>=width)return;
    (plain?VipApi.infoPlain:VipApi.infoText)(w,value,x+measured,y,width-measured,color);
}
static bool queuedUpgradeValid() {
    const auto& q=VipInteraction;const auto& p=VipState.p;
    if(!VipState.ready || VipState.hidden || q.token!=p.token || q.level!=p.level ||
        q.questLevel!=p.questLevel || q.questCost!=p.questCost)return false;
    if(q.action==4) {if((p.flags&13)!=13 || p.level>=10)return false;}
    else if(q.action==7) {if((p.flags&165)!=165)return false;}
    else return false;
    for(int i=0;i<3;++i)if(q.items[i].id!=p.questItems[i].id || q.items[i].amount!=p.questItems[i].amount)return false;
    return true;
}
static void pumpUpgrade() {
    auto& q=VipInteraction;if(!q.phase)return;
    const u32 now=tick();
    if(q.phase==1) {
        if(!queuedUpgradeValid()) {q.phase=0;q.notice=1;dirty(VipState.window);return;}
        // The server starts its 300ms gate when it receives Refresh. Waiting
        // 350ms AFTER its reply remains safe even with network latency/jitter.
        if(q.pollPending) {
            if(now-q.pollSent>=10000){q.phase=3;dirty(VipState.window);}
            return;
        }
        if(now-q.lastReply<350)return;
        if(!send(q.action)){q.phase=3;dirty(VipState.window);return;}
        q.phase=2;q.sentAt=now;questHide();dirty(VipState.window);
    } else if(q.phase==2 && now-q.sentAt>=10000) {
        q.phase=3;dirty(VipState.window); // Never resend a state-changing request.
    }
}
static void queueUpgrade(int action) {
    if(VipInteraction.phase)return;
    auto& q=VipInteraction;const auto& p=VipState.p;
    q.action=action;q.token=p.token;q.level=p.level;q.questLevel=p.questLevel;q.questCost=p.questCost;
    for(int i=0;i<3;++i)q.items[i]=p.questItems[i];
    q.phase=1;q.notice=0;
    // Release the confirmation immediately, but keep the parent visible and
    // disabled until the server opens its authoritative result. Close cancels
    // an unsent queue; it does not undo an already-sent server operation.
    questHide();pumpUpgrade();dirty(VipState.window);
}
static void benefitTooltip(void* w,int x,int y) {
    if(w!=VipState.window || !w || !VipState.ready || VipState.hidden ||
        !at<int>(w,0x28) || VipQuestState.mode || VipState.dragging || VipState.pressed ||
        VipInteraction.phase || at<void*>((void*)0x131F4E8,0x19C))return;
    for(int row=0;row<visibleBenefits;++row) {
        const int top=Y(838+row*51);
        if(x<X(735) || x>=X(735)+X(586) || y<top || y>=top+Y(44))continue;
        char* value=VipInteraction.benefit;const int count=benefitRows(VipState.scroll+row,value);
        if(VipState.scroll+row>=count || !value[0])return;
        const int width=reinterpret_cast<int (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA21C90)(w,value,0,0,mainBodyFont,0,0);
        if(width<=X(1310)-X(821))return; // No redundant tooltip for a fitted row.
        void* manager=*reinterpret_cast<void**>(0x121333C);if(!manager)return;
        int tx=x+10,ty=y-24;
        reinterpret_cast<void (__thiscall *)(void*,int*,int*)>(0xA1EF70)(w,&tx,&ty);
        // Existing native tooltip window copies/wraps the complete bounded text.
        // Last flag 0 bypasses character-name substitution; no global hook.
        reinterpret_cast<void (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA753D0)(manager,value,tx,ty,-1,0,0);
        return;
    }
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
    if(width==X(322) && height==Y(423)){dh=height*3/4;dw=sw*dh/sh;}
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
    return !VipInteraction.phase && buttonTexture(c,0) && (!c.flag || (VipState.p.flags&c.flag)) &&
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
    panel(w,6,y,348,44,0xFFF4FAFF,selected?0xFFD4AC48:0xFFACBFE3);
    gradient(w,9,y+3,342,38,selected?0xFFFFF9DF:on?0xFFF4FBFF:0xFFF4F5F7,
        selected?0xFFF2D994:on?(hover?0xFFD8E9FF:0xFFE4EFFC):0xFFE6E9ED);
    if(selected)rect(w,8,y+4,2,36,0xFFDCA935);
}
static void questDraw(void* w) {
    if(!w || !VipQuestState.mode || !at<int>(w,0x28)) return;
    const int height=questHeight(VipQuestState.mode);
    if(at<int>(w,0x18)!=height)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,360,height);
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    chrome(w,360,height);
    text(w,VipQuestState.mode==4?"VIP Buffs":VipQuestState.mode==3?"Purchase VIP":"VIP Upgrade Quest",38,3,296,0x30170C);
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
        rect(w,5,20,350,250,0xFFF4FCFF);
        for(int i=0;i<5;++i) {
            const int y=25+i*48;const bool selected=VipQuestState.selected==i,on=offerAllowed(i);
            membershipCard(w,y,selected,VipQuestState.hover==40+i,on);
            picture(w,14,16,y+8,28,28,0,0,0,0,on?255:110);
            const auto& offer=VipState.p.offers[i];char caption[48],days[24];number(days,offer.minutes/1440);
            int n=0;for(int j=0;days[j];++j)caption[n++]=days[j];
            const char* tail=offer.minutes==1440?" DAY VIP":" DAYS VIP";while(*tail)caption[n++]=*tail++;caption[n]=0;
            VipApi.offerText(w,caption,54,y+15,135,!on?0x929292:selected?0x355378:0x634529);
            char price[32];number(price,offer.cost);n=0;while(price[n])++n;price[n++]='z';price[n]=0;
            VipApi.priceText(w,on?price:"Unavailable",193,y+11,148,!on?0x929292:selected?0x355378:0x634529);
        }
        text(w,purchaseReady()?"Click Purchase to buy the selected membership.":"Select a VIP duration to purchase.",12,275,338,0x7A6555);
    }
    else {
        for(int i=0;i<3;++i) {
            const auto& item=VipState.p.questItems[i];if(!item.id)continue;
            const int y=25+i*48;
            panel(w,6,y,348,44,0xFFF3F7FF);
            rect(w,7,y+4,2,36,0xFFDFB355);
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
    if(!VipState.ready || VipState.hidden || VipInteraction.phase || mode<1 || mode>5 || (mode==2 && !(VipState.p.flags&32)) ||
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
    at<int>(w,0x1C)=at<int>(VipState.window,0x1C)+(mainWidth-360)/2;
    at<int>(w,0x20)=at<int>(VipState.window,0x20)+(mainHeight-questHeight(mode))/2;
    at<int>(w,0x28)=1;dirty(w);questFront();
}
EXPORT void __fastcall VipDraw(void* w,void*) {
    if(w==VipQuestState.window) {questDraw(w);return;}
    if(!w || !at<int>(w,0x28) || at<int>(w,0x14)<mainWidth || at<int>(w,0x18)<mainHeight) return;
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    rect(w,0,0,mainWidth,mainHeight,0xFFF4FCFF);
    if(!designTexture())return;
    picture(w,15,0,0,mainWidth,mainHeight,0,0,1412,1114);
    // Erase EVERY example-data region with blank slices from the same artwork.
    // The approved file is a skin atlas, never the source of character/account state.
    designPatch(w,40,110,322,423,45,110,6,423);
    VipPortrait(w,X(40),Y(110),X(322),Y(423));
    designPatch(w,532,118,815,46,1320,118,6,46);
    designPatch(w,532,204,815,47,1320,204,6,47);
    designPatch(w,532,293,815,48,1320,293,6,48);
    field(w,"Name: ",VipState.p.player,Y(124),0x30170C,true);
    field(w,"VIP Start Date: ",VipState.p.issued,Y(211),0x358B23);
    field(w,"VIP Expiry Date: ",VipState.p.expires,Y(300),0x3636C9);
    // Whole native-size PNG buttons replace the mockup's illustrative faces.
    designPatch(w,440,360,895,172,1340,360,6,172);
    designPatch(w,1340,7,69,63,1250,7,6,63);
    designPatch(w,498,772,195,68,460,772,6,68);
    designPatch(w,498,980,195,68,450,980,6,68);
    designPatch(w,390,550,982,47,20,600,6,47);
    const char* status=VipInteraction.phase==1?"Preparing upgrade request...":
        VipInteraction.phase==2?"Upgrade sent. Waiting for server...":
        VipInteraction.phase==3?"Reply delayed. Close and reopen VIP.":
        VipInteraction.notice?"Requirements changed. Review Upgrade again.":VipState.p.status;
    VipApi.infoText(w,status,X(395),Y(565),X(978),0x30170C);
    designPatch(w,180,653,1050,28,1160,653,40,28);
    const u32 pct=VipState.p.percent>100?100:VipState.p.percent;
    const bool upgradeReady=pct==100 && (VipState.p.flags&8) && VipState.p.level<10;
    if(pct && showExperience())picture(w,15,X(180),Y(653),static_cast<int>(pct*X(1050)/100),Y(681)-Y(653),210,653,670,28,255,upgradeReady);
    designPatch(w,400,691,800,40,30,691,6,40);
    if(showExperience())VipApi.statusText(w,VipState.p.experience,X(80),Y(696),X(1255),0x30170C);
    char level[24],caption[40];number(level,VipState.p.level);int n=0;
    const char* prefix="VIP Level : ";while(*prefix)caption[n++]=*prefix++;
    for(int i=0;level[i];++i)caption[n++]=level[i];caption[n]=0;
    designPatch(w,30,784,447,56,490,784,6,56);
    VipApi.infoText(w,caption,X(35),Y(800),X(425),0x30170C);
    designPatch(w,30,847,645,80,25,847,5,80);
    for(u32 i=0;i<10;++i) {
        const int x=X(35+static_cast<int>(i)*63);
        picture(w,15,x,Y(851),X(59),Y(74),i<VipState.p.level?33:349,851,59,74);
    }
    designPatch(w,28,938,641,42,25,938,5,42);
    VipApi.bodyText(w,VipState.p.upgrade,X(35),Y(952),X(635),0x30170C);
    designPatch(w,20,1069,1370,36,1300,1069,6,36);
    VipApi.bodyText(w,VipState.p.membership,X(25),Y(1076),X(1330),0x30170C);
    // Remove every sample benefit, including when membership expires.
    designPatch(w,733,835,603,204,725,835,6,204);clampBenefitScroll();
    const int count=benefitRows();
    for(int row=0;row<visibleBenefits && VipState.scroll+row<count;++row) {
        char effect[80];benefitRows(VipState.scroll+row,effect);
        const int y=Y(838+row*51),height=Y(44),x=X(735),width=X(586);
        picture(w,15,x,y,width,height,735,838,586,44);
        picture(w,15,x+X(72),y+1,width-X(80),height-2,1220,844,4,30);
        // Fit live labels to the compact cards without overlapping adjacent rows.
        int length=0;while(length<79 && effect[length])++length;
        int cut=length,measured=0;
        const int textX=X(821),textWidth=X(1310)-textX;
        do {measured=reinterpret_cast<int (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA21C90)(w,effect,cut,0,mainBodyFont,0,0);if(measured<=textWidth)break;}while(--cut>0);
        if(cut>0 && measured>=0 && measured<=textWidth) {
            effect[cut]=0;
            VipApi.bodyText(w,effect,textX,y+(height-mainBodyFont)/2,textWidth,0x30170C);
        }
    }
    rect(w,X(1359),Y(864),2,Y(143),0xFFDDE5F2);
    if(count>visibleBenefits) {
        const int track=Y(143),thumb=track*visibleBenefits/count<6?6:track*visibleBenefits/count;
        const int y=Y(864)+(track-thumb)*VipState.scroll/(count-visibleBenefits);
        rect(w,X(1359),y,2,thumb,0xFF9DADC8);
    }
    for(const auto& c:controls)paintButton(w,c,!enabled(c)?3:VipState.pressed==c.id?2:VipState.hover==c.id?1:0);
    // Paint AFTER every atlas patch. The membership-background patch starts
    // at y178 and used to erase the lower pixels of this y169 countdown.
    if((VipState.p.flags&1) && VipState.p.buffRemaining) {
        const u32 secs=VipState.p.buffRemaining>359999?359999:VipState.p.buffRemaining;
        char wait[16]="Buffs: ";const u32 hrs=secs/3600,mins=secs/60%60,seconds=secs%60;
        wait[7]=static_cast<char>('0'+hrs/10);wait[8]=static_cast<char>('0'+hrs%10);wait[9]=':';
        wait[10]=static_cast<char>('0'+mins/10);wait[11]=static_cast<char>('0'+mins%10);wait[12]=':';
        wait[13]=static_cast<char>('0'+seconds/10);wait[14]=static_cast<char>('0'+seconds%10);wait[15]=0;
        rect(w,289,168,128,14,0xFFF4FCFF);
        VipApi.statusText(w,wait,289,168,128,0x30170C);
    }
}
EXPORT void __stdcall VipOpen() {
    void* w=VipState.window;
    if(!w) {
        w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4); if(!w) return;
        reinterpret_cast<void (__thiscall *)(void*,int)>(0x86B950)(w,0);
        at<u32>(w,0)=VipApi.vtable;
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,mainWidth,mainHeight);
        at<int>(w,0x2C)=0x3FC;
        at<int>(w,0x1C)=20; at<int>(w,0x20)=20;
        VipState.window=w;
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA2D240)((void*)0x131F4E8,w);
    }
    release(w); VipState.hidden=0; VipState.hover=0; VipState.scroll=0;
    VipInteraction.phase=VipInteraction.pollPending=VipInteraction.notice=0;
    at<int>(w,0x28)=1; VipState.refresh=tick(); startTimer(); dirty(w);
    // Registration inserts behind existing HUD roots. Raise on every explicit
    // open/reopen so covered Inventory/Equipment menu buttons cannot win clicks.
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA39130)((void*)0x131F4E8,w);
}
EXPORT int __stdcall VipReceive(const Snapshot* p) {
    if(!p || p->id!=0xA1C || p->length!=sizeof(Snapshot) || p->magic!=0x55504956 || p->version!=4 ||
        !p->token || p->level>10 || p->percent>100 || (p->flags&~2047) || p->questLevel>10) return 0;
    if(!(p->flags&2) && (!VipState.ready || VipState.hidden || p->token!=VipState.p.token)) return 0;
    VipInteraction.pollPending=0;VipInteraction.lastReply=tick();
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
    if(!(p->flags&2) && VipInteraction.phase==1 && !queuedUpgradeValid()) {
        VipInteraction.phase=0;VipInteraction.notice=1;
    }
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
    else if(y>=0 && y<Y(67)) {
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
            else if(c.action==4 || c.action==7)queueUpgrade(c.action);
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
                queueUpgrade(4); // Server prepares the one-ticket popup.
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
    // Slot 30 runs the stock tooltip reset above, then updates our hint. Moving
    // away, changing rows, closing, or opening a modal cannot retain stale text.
    benefitTooltip(w,x,y);
}
EXPORT void* __fastcall VipDestroy(void* w,void*,int flags) {
    if(w==VipQuestState.window) {questHide();VipQuestState.window=0;return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);}
    hide(false); VipState.window=0; VipState.p.token=0;
    if(VipPortraitCanvas){reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(VipPortraitCanvas,1);VipPortraitCanvas=0;}
    return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags);
}
