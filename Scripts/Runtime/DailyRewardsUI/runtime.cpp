// Freestanding x86 native frame, profiled for 2025-07-16 Ragexe.
#include "daily_rewards_wire.hpp"
using namespace daily_rewards_wire;
using u8 = unsigned char;
#define EXPORT extern "C" __declspec(dllexport)
struct Api {
    u32 version, vtable, ctor, send;
    void (__stdcall *text)(void*, const char*, int, int, int, u32);
    void (__stdcall *item)(void*, u32, int, int);
    void (__stdcall *describe)(u32);
    u32 moduleIat, procIat;
    void (__stdcall *center)(void*, const char*, int, int, int, u32);
    int (__thiscall *monster)(void*,u32,int,int,int,int,int);
};
static_assert(sizeof(Api) == 44, "DRUI native API v2");
EXPORT Api DailyApi = {2};
struct State {
    void* window; u32 sequence, pending, sent, received, timer, rollStart;
    int visible, ready, tab, pressed, hover, dragging, rolling, right;
    u32 rightItem, rightSequence;
    Snapshot p;
    u32 (__stdcall *setTimer)(void*,u32,u32,void*);
    int (__stdcall *killTimer)(void*,u32);
    Item attendanceExtra[7][5];
    int selectedDay, motionOff, mouseX, mouseY;
    Item sixthRoll;
    RerollInfo reroll;
    u32 backgroundRefresh, drawnResetMinute;
};
EXPORT State DailyState = {};
// Cosmetic state never supplies an award, claim or outbound item ID.
struct Animation {
    u32 epoch, frame, random[6], icons[6], count, ids[max_roll_pool], revealed;
};
EXPORT Animation DailyAnimation = {};
// Active GachaUI timing: gacha_ui.hpp first_reveal_ms/next_reveal_ms.
constexpr u32 spin_ms=100, first_reveal_ms=1020, next_reveal_ms=220;
static u32 randomIcon(u32& value) {
    value^=value<<13;value^=value>>17;value^=value<<5;return value;
}
static void addRollIcon(u32 id) {
    if(!id || DailyAnimation.count>=max_roll_pool)return;
    for(u32 i=0;i<DailyAnimation.count;++i)if(DailyAnimation.ids[i]==id)return;
    DailyAnimation.ids[DailyAnimation.count++]=id;
}
static void spinFrame(u32 now) {
    auto& a=DailyAnimation;
    const u32 frame=(now-a.epoch)/spin_ms;
    if(a.frame==frame)return;
    a.frame=frame;
    if(!a.count)return;
    for(u32 i=0;i<(DailyState.p.protocol>=six_reward_version?6u:5u);++i){
        // Independent streams; distinct simultaneous icons when the pool allows.
        // Duplicate configured ItemIds are collapsed for animation only.
        const u32 first=i/a.count*a.count, previous=a.icons[i];
        u32 index=randomIcon(a.random[i])%a.count;
        for(u32 tries=0;tries<a.count;++tries){
            const u32 id=a.ids[index];bool used=false;
            for(u32 j=first;j<i;++j)if(a.icons[j]==id)used=true;
            if(!used && (id!=previous || a.count==1)){a.icons[i]=id;break;}
            index=(index+1)%a.count;
            if(tries+1==a.count){
                // A small pool can leave only this card's previous icon free.
                for(u32 j=0;j<a.count;++j){
                    bool taken=false;for(u32 k=first;k<i;++k)if(a.icons[k]==a.ids[j])taken=true;
                    if(!taken){a.icons[i]=a.ids[j];break;}
                }
            }
        }
    }
}
static void startRoll(u32 now) {
    auto& a=DailyAnimation;a.epoch=now;a.frame=0xFFFFFFFF;a.revealed=0;
    for(u32 i=0;i<6;++i){
        a.random[i]=(now^(DailyState.sequence*0x9E3779B9u))+(i+1)*0x85EBCA6Bu;
        if(!a.random[i])a.random[i]=i+1;
        a.icons[i]=0;
    }
    spinFrame(now);
}
struct Box { int x,y,w,h;u32 id;const char* name;u32 amount; };
static Box items[64]; static int itemCount;
template<typename T> T& at(void* p, int off) { return *reinterpret_cast<T*>(static_cast<u8*>(p)+off); }
static u32 tick() { return (*reinterpret_cast<u32 (__stdcall **)()>(0xFC17B0))(); }
static u32 resetMinute(u32 now) {
    const u32 elapsed=(now-DailyState.received)/1000,remaining=DailyState.p.reset_remaining;
    return (remaining>elapsed?remaining-elapsed:0)/60;
}
static void dirty() { if (DailyState.window) at<int>(DailyState.window,0x58)=1; }
static void copy(void* target,const void* source,u32 size) { auto* d=static_cast<volatile u8*>(target); auto* s=static_cast<const u8*>(source);for(u32 i=0;i<size;++i)d[i]=s[i]; }
static void clear(void* target,u32 size) { auto* d=static_cast<volatile u8*>(target);for(u32 i=0;i<size;++i)d[i]=0; }
static void append(char* s,const char* v) { int n=0;while(s[n] && n<126)++n;for(int i=0;v[i] && n<126;++i)s[n++]=v[i];s[n]=0; }
static void number(char* s,u32 value) { char b[12];int n=0;do{b[n++]=static_cast<char>('0'+value%10);value/=10;}while(value);b[n]=0;for(int i=0;i<n/2;++i){char a=b[i];b[i]=b[n-i-1];b[n-i-1]=a;}append(s,b); }
static void rect(int x,int y,int width,int height,u32 color) {
    void* w=DailyState.window;if(!w)return;void* s=at<void*>(w,0x24);if(!s || !at<void*>(s,0x18))return;
    int sw=at<int>(s,4),sh=at<int>(s,8);if(x<0 || y<0 || width<0 || height<0 || x+width>sw || y+height>sh)return;
    u32* pixels=at<u32*>(s,0x18);for(int row=y;row<y+height;++row)for(int col=x;col<x+width;++col)pixels[row*sw+col]=color;
    at<u8>(s,0x1C)=1;
}
static void panel(int x,int y,int w,int h,u32 color=0xFFF7FCFF,u32 edge=0xFFD4DFE9) {
    rect(x+2,y,w-4,h,edge);rect(x,y+2,w,h-4,edge);
    rect(x+1,y+3,w-2,h-6,color);rect(x+3,y+1,w-6,h-2,color);
}
static void grayIcon(int x,int y) {
    void* s=at<void*>(DailyState.window,0x24);if(!s || !at<void*>(s,0x18))return;
    const int sw=at<int>(s,4),sh=at<int>(s,8);if(x<0 || y<0 || x+34>sw || y+34>sh)return;
    u32* pixels=at<u32*>(s,0x18);
    for(int row=y;row<y+34;++row)for(int col=x;col<x+34;++col){u32& p=pixels[row*sw+col];u32 l=(((p>>16)&255)*3+((p>>8)&255)*6+(p&255))/10;p=0xFF000000|(l<<16)|(l<<8)|l;}
}
static bool stampInk(int x,int y){
	if(x<0 || y<0 || x>=88 || y>=26)return false;
	// Private code-drawn stamp: no image asset, texture mode change or global font hook.
	const int cx=x<4?4-x:x>83?x-83:0,cy=y<4?4-y:y>21?y-21:0;
	if(cx*cx+cy*cy>16)return false;
	if(x<2 || x>=86 || y<2 || y>=24)return true;
	if(y<6 || y>=20 || x<3 || x>=85)return false;
	static const u8 glyphs[7][7]={
		{14,17,16,16,16,17,14},{16,16,16,16,16,16,31},
		{14,17,17,31,17,17,17},{31,4,4,4,4,4,31},
		{17,27,21,21,17,17,17},{31,16,16,30,16,16,31},
		{30,17,17,17,17,17,30}
	};
	const int col=(x-3)%12,letter=(x-3)/12;
	return col<10 && (glyphs[letter][(y-6)/2]&(16>>(col/2)))!=0;
}
static void claimedStamp(void* w,int x,int y){
	void* surface=at<void*>(w,0x24);if(!surface || !at<void*>(surface,0x18))return;
	const int stride=at<int>(surface,4);if(x<0 || y<0 || x+96>stride || y+133>at<int>(surface,8))return;
	u32* pixels=at<u32*>(surface,0x18);
	// Rotate -18 degrees with 2x2 coverage, strictly inside this one 96px cell.
	for(int row=36;row<95;++row)for(int col=1;col<95;++col){
		int coverage=0;for(int sy=1;sy<=3;sy+=2)for(int sx=1;sx<=3;sx+=2){
			const int dx=col*4+sx-48*4,dy=row*4+sy-65*4;
			const int u=(dx*974-dy*317)/1024+44*4,v=(dx*317+dy*974)/1024+13*4;
			if(u>=0 && v>=0 && stampInk(u/4,v/4))++coverage;
		}
		if(!coverage)continue;const u32 alpha=coverage*48,ink=0x4F80CA;
		u32& dst=pixels[(y+row)*stride+x+col];u32 result=0xFF000000;
		for(int shift=0;shift<24;shift+=8)result|=(((((ink>>shift)&255)*alpha+((dst>>shift)&255)*(255-alpha)+127)/255)<<shift);
		dst=result;
	}
	at<u8>(surface,0x1C)=1;
}
static void text(const char* s,int x,int y,int width,u32 color=0x56504A) { DailyApi.text(DailyState.window,s,x,y,width,color); }
static void opaqueFooter() {
    // GDI text can clear alpha in its text rectangle. This footer is opaque;
    // preserve its RGB/text and the frame's rounded outside corner pixels.
    void* surface=at<void*>(DailyState.window,0x24);if(!surface || !at<void*>(surface,0x18))return;
    const int stride=at<int>(surface,4);if(stride<920 || at<int>(surface,8)<720)return;
    u32* pixels=at<u32*>(surface,0x18);
    for(int y=682;y<720;++y)for(int x=y==719?2:1;x<(y==719?918:919);++x)pixels[y*stride+x]|=0xFF000000;
    at<u8>(surface,0x1C)=1;
}
static void center(const char* s,int x,int y,int width,u32 color=0x56504A) { DailyApi.center(DailyState.window,s,x,y,width,color); }
static void button(int id,const char* caption,int x,int y,int w,int h,bool enabled=true) {
    panel(x,y,w,h,!enabled?0xFFE7E9EC:DailyState.pressed==id?0xFFBDD7EF:DailyState.hover==id?0xFFEAF6FF:0xFFDDEDFC);
    center(caption,x+4,y+(h-11)/2,w-8,enabled?0x63412C:0x919191);
}
static void reward(const Item& r,int x,int y,bool gray=false) {
    if(!r.id)return;
    panel(x,y,34,34,0xFFE7EDF8);DailyApi.item(DailyState.window,r.id,x+1,y+1);
    if(gray)grayIcon(x,y);
    if(itemCount<64)items[itemCount++]={x,y,34,34,r.id,r.name,r.amount};
    char amount[128];amount[0]=0;number(amount,r.amount);center(amount,x,y+25,34,gray?0x909090:0x5A5A5A);
}
static bool contains(int x,int y,int bx,int by,int w,int h){return x>=bx && y>=by && x<bx+w && y<by+h;}
// Background reads retain the last confirmed appearance. Input still uses the
// strict pending guard, so a quiet refresh cannot overlap a claim or re-roll.
static bool pending(bool appearance=false){return DailyState.pending && !(appearance && DailyState.backgroundRefresh);}
static bool actionable(bool appearance=false){return DailyState.ready && !pending(appearance) && !DailyState.rolling && (DailyState.p.flags&Ready);}
static bool rerollable(int slot,bool appearance=false) {
    const auto& r=DailyState.reroll;
    return actionable(appearance) && DailyState.p.protocol==reroll_version && !r.pending && r.used<r.limit && r.zeny>=r.cost && !DailyState.p.quests[slot].claimed;
}
static void price(char* out,u32 value) {
    char digits[16];int n=0;do{digits[n++]=static_cast<char>('0'+value%10);value/=10;}while(value);
    int at=0;for(int i=n-1;i>=0;--i){out[at++]=digits[i];if(i && i%3==0)out[at++]=',';}
    out[at++]='z';out[at]=0;
}
static void release() {
    void* w=DailyState.window;if(!w)return;
    if(DailyState.dragging){DailyState.dragging=0;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880BB0)(w,0,0);}
    if(at<void*>((void*)0x131F4E8,0x19C)==w)reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);
    DailyState.pressed=DailyState.right=0;
}
static bool send(u16 action,u32 slot=0,u32 attendancePage=0xFFFFFFFF,u32 rewardPage=0xFFFFFFFF,bool background=false) {
    if(DailyState.pending)return false;
    void* transport=reinterpret_cast<void* (__cdecl *)()>(DailyApi.ctor)();if(!transport)return false;
    if(++DailyState.sequence==0)++DailyState.sequence;
    const u16 protocol=DailyState.p.protocol==reroll_version?reroll_version:DailyState.p.protocol==six_reward_version?six_reward_version:DailyState.p.protocol==catalog_version?catalog_version:DailyState.p.protocol==bundle_version?bundle_version:action==Open?six_reward_version:version;
    if(action==Open || action==Refresh)slot=bundle_capability;
    Request r={request_id,sizeof(Request),magic,protocol,action,DailyState.sequence,(action==Open || action==Refresh)?(DailyState.ready || action==Open?reroll_capability:catalog_capability):DailyState.p.date,slot,
        attendancePage==0xFFFFFFFF?DailyState.p.attendance_page:attendancePage,rewardPage==0xFFFFFFFF?DailyState.p.reward_page:rewardPage};
    if(action==Reroll){r.slot=reroll_slot(slot,DailyState.reroll.used,DailyState.p.attendance_page,DailyState.p.reward_page);r.attendance_page=DailyState.reroll.cost;r.reward_page=0;}
    else if(action==QuestClaim && protocol==reroll_version)r.slot=slot|(DailyState.reroll.used<<3);
    DailyState.pending=1;DailyState.sent=tick();DailyState.backgroundRefresh=background && DailyState.ready && action==Refresh;
    reinterpret_cast<void (__thiscall *)(void*,int,const void*)>(DailyApi.send)(transport,sizeof(r),&r);
    if(!DailyState.backgroundRefresh)dirty();return true;
}
static void hide() {
    release();DailyState.visible=DailyState.ready=DailyState.rolling=0;DailyState.pending=DailyState.backgroundRefresh=0;++DailyState.sequence;
    if(DailyState.window)at<int>(DailyState.window,0x28)=0;
    if(DailyState.timer && DailyState.killTimer)DailyState.killTimer(0,DailyState.timer);DailyState.timer=0;
}
EXPORT void __stdcall DailyTick(void*,u32,u32 id,u32) {
    if(id!=DailyState.timer || !DailyState.visible || !DailyState.window)return;
    if(!at<int>(DailyState.window,0x28)){hide();return;}
    bool repaint=false;
    if(DailyState.dragging && at<void*>((void*)0x131F4E8,0x19C)!=DailyState.window){release();repaint=true;}
    const u32 now=tick();
    if(DailyState.rolling){
        if(!DailyState.motionOff){spinFrame(now);repaint=true;}
        if(DailyState.ready && !DailyState.pending &&
            now-DailyState.rollStart>=(DailyAnimation.revealed?next_reveal_ms:first_reveal_ms)){
            ++DailyAnimation.revealed;DailyState.rollStart=now;repaint=true;
            if(DailyAnimation.revealed>=DailyState.p.roll_count)DailyState.rolling=0;
        }
    }
    // Do not flash loading feedback for each short automatic read. A genuinely
    // slow request still becomes visible, without sending a second request.
    if(DailyState.pending && DailyState.backgroundRefresh && now-DailyState.sent>=1000){DailyState.backgroundRefresh=0;repaint=true;}
    if(DailyState.pending && now-DailyState.sent>=10000){DailyState.pending=0;DailyState.rolling=0;send(Refresh);}
    // Poll a paid reroll promptly, above the server's 150 ms request guard.
    // Keep one request in flight and retain the normal idle refresh cadence.
    else if(!DailyState.pending && !DailyState.rolling &&
        now-DailyState.received>=(DailyState.p.protocol==reroll_version && DailyState.reroll.pending?200u:3000u))send(Refresh,0,0xFFFFFFFF,0xFFFFFFFF,true);
    if(DailyState.ready && resetMinute(now)!=DailyState.drawnResetMinute)repaint=true;
    if(repaint)dirty();
}
static void startTimer() {
    if(DailyState.timer)return;
    if(!DailyState.setTimer){
        void* module=(*reinterpret_cast<void* (__stdcall **)(const char*)>(DailyApi.moduleIat))("user32.dll");if(!module)return;
        auto resolve=*reinterpret_cast<void* (__stdcall **)(void*,const char*)>(DailyApi.procIat);
        DailyState.setTimer=reinterpret_cast<u32 (__stdcall *)(void*,u32,u32,void*)>(resolve(module,"SetTimer"));
        DailyState.killTimer=reinterpret_cast<int (__stdcall *)(void*,u32)>(resolve(module,"KillTimer"));
    }
    if(DailyState.setTimer && DailyState.killTimer)DailyState.timer=DailyState.setTimer(0,0,spin_ms,reinterpret_cast<void*>(DailyTick));
}
EXPORT void __stdcall DailyToggle() {
    if(DailyState.visible){hide();return;}
    void* w=DailyState.window;
    if(!w){
        w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4);if(!w)return;
        reinterpret_cast<void (__thiscall *)(void*,int)>(0x86B950)(w,0);
        at<u32>(w,0)=DailyApi.vtable;
        reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,920,720);
        at<int>(w,0x2C)=0x3E8;at<int>(w,0x1C)=20;at<int>(w,0x20)=20;DailyState.window=w;
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA2D240)((void*)0x131F4E8,w);
    }
    clear(&DailyState.p,sizeof(DailyState.p));clear(DailyState.attendanceExtra,sizeof(DailyState.attendanceExtra));
    clear(&DailyAnimation,sizeof(DailyAnimation));
    clear(&DailyState.sixthRoll,sizeof(DailyState.sixthRoll));
    clear(&DailyState.reroll,sizeof(DailyState.reroll));
    DailyState.selectedDay=-1;DailyState.ready=DailyState.pending=DailyState.rolling=DailyState.backgroundRefresh=0;
    DailyState.tab=0;DailyState.visible=1;DailyState.received=tick();at<int>(w,0x28)=1;
    release();startTimer();dirty();reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA39130)((void*)0x131F4E8,w);
    send(Open);
}
EXPORT int __stdcall DailyReceive(const Snapshot* p) {
    if(!p || p->id!=snapshot_id || p->signature!=magic ||
        !((p->protocol==version && p->length==sizeof(Snapshot)) || (p->protocol==bundle_version && p->length==sizeof(BundleSnapshot)) ||
          (p->protocol==catalog_version && p->length==sizeof(CatalogSnapshot)) || (p->protocol==six_reward_version && p->length==sizeof(SixRewardSnapshot)) ||
          (p->protocol==reroll_version && p->length==sizeof(RerollSnapshot))) ||
        p->sequence!=DailyState.sequence || !DailyState.visible || !DailyState.pending || p->attendance_page>3 || p->roll_count>(p->protocol>=six_reward_version?6u:5u) ||
        p->attendance_day>28 || p->reward_total>max_roll_pool || p->reward_pages!=(p->reward_total+5)/6 ||
        (p->reward_pages?p->reward_page>=p->reward_pages:p->reward_page!=0) || (p->flags&~7))return 0;
    for(int i=0;i<7;++i)if(p->attendance[i].status>2)return 0;
    for(int i=0;i<5;++i)if(p->quests[i].claimed>1 || p->quests[i].required>1000000 || p->quests[i].progress>p->quests[i].required)return 0;
    if(p->protocol>=catalog_version){
        const auto* full=reinterpret_cast<const CatalogSnapshot*>(p);
        for(u32 i=0;i<p->reward_total;++i)if(!full->roll_ids[i])return 0;
        for(u32 i=0;i<6 && p->reward_page*6+i<p->reward_total;++i)
            if(p->possible[i].id!=full->roll_ids[p->reward_page*6+i])return 0;
    }
    if(p->protocol>=six_reward_version && p->roll_count==6){
        const auto& r=reinterpret_cast<const SixRewardSnapshot*>(p)->sixth_roll;
        if(!r.id || !r.amount)return 0;
    }
    if(p->protocol==reroll_version){
        const auto& r=reinterpret_cast<const RerollSnapshot*>(p)->reroll;
        if(r.used>max_rerolls || r.limit>max_rerolls || r.cost>2147483647u || r.zeny>2147483647u || r.pending>1 || (r.used>=r.limit && r.cost))return 0;
    }
    const bool samePage=DailyState.ready && DailyState.p.attendance_page==p->attendance_page && DailyState.p.date==p->date;
    copy(&DailyState.p,p,sizeof(Snapshot));DailyState.p.status[95]=0;
    clear(&DailyState.sixthRoll,sizeof(DailyState.sixthRoll));
    if(p->protocol>=six_reward_version)copy(&DailyState.sixthRoll,&reinterpret_cast<const SixRewardSnapshot*>(p)->sixth_roll,sizeof(Item));
    clear(&DailyState.reroll,sizeof(DailyState.reroll));
    if(p->protocol==reroll_version)copy(&DailyState.reroll,&reinterpret_cast<const RerollSnapshot*>(p)->reroll,sizeof(RerollInfo));
    DailyState.sixthRoll.name[47]=0;
    clear(DailyState.attendanceExtra,sizeof(DailyState.attendanceExtra));
    if(p->protocol>=bundle_version)copy(DailyState.attendanceExtra,reinterpret_cast<const BundleSnapshot*>(p)->attendance_extra,sizeof(DailyState.attendanceExtra));
    DailyAnimation.count=0;
    if(p->protocol>=catalog_version){
        const auto* full=reinterpret_cast<const CatalogSnapshot*>(p);
        for(u32 i=0;i<p->reward_total;++i)addRollIcon(full->roll_ids[i]);
    }else{
        // Old servers only supply their visible page; no invented prize icons.
        for(const auto& r:p->possible)addRollIcon(r.id);
    }
    for(auto& day:DailyState.attendanceExtra)for(auto& r:day)r.name[47]=0;
    if(!samePage)DailyState.selectedDay=-1;
    if(DailyState.selectedDay<0)for(int i=0;i<7;++i)if(p->attendance[i].status==1){DailyState.selectedDay=i;break;}
    for(auto& d:DailyState.p.attendance)d.reward.name[47]=0;
    for(auto& q:DailyState.p.quests){q.title[63]=0;for(auto& r:q.rewards)r.name[47]=0;}
    for(auto& r:DailyState.p.roll)r.name[47]=0;for(auto& r:DailyState.p.possible)r.name[47]=0;
    DailyState.pending=DailyState.backgroundRefresh=0;DailyState.ready=1;DailyState.received=tick();DailyState.pressed=DailyState.right=0;
    if(DailyState.rolling){
        if(!p->roll_count || (p->flags&Failed) || DailyState.motionOff)DailyState.rolling=0;
        else {DailyState.rollStart=DailyState.received;DailyAnimation.revealed=0;} // Keep the cosmetic clock continuous.
    }
    dirty();return 1;
}
static int hitAt(int x,int y,bool appearance=false) {
    if(!DailyState.visible)return 0;
    if(contains(x,y,896,3,20,20))return 1;
    for(int i=0;i<3;++i)if(contains(x,y,12+i*150,32,142,26))return 2+i;
    if(contains(x,y,806,32,102,26) && !pending(appearance) && !DailyState.rolling)return 5;
    if(DailyState.tab==2 && DailyState.ready){
        if(contains(x,y,24,358,104,26))return 43;
        if(DailyState.rolling && !DailyState.pending && contains(x,y,138,358,104,26))return 44;
    }
    if(!actionable(appearance))return 0;
    if(DailyState.tab==0){
        if(contains(x,y,782,80,24,22) && DailyState.p.attendance_page)return 10;
        if(contains(x,y,880,80,24,22) && DailyState.p.attendance_page<3)return 11;
        for(int i=0;i<7;++i)if(DailyState.p.attendance[i].status && contains(x,y,18+i*126,116,124,200))return 50+i;
        const int selected=DailyState.selectedDay;
        if(selected>=0 && selected<7 && DailyState.p.attendance[selected].status==1 && contains(x,y,730,354,162,28))return 20+selected;
    } else if(DailyState.tab==1){
        for(int i=0;i<5;++i){const auto& q=DailyState.p.quests[i];const int top=96+i*116;const bool rerolls=DailyState.p.protocol==reroll_version;
            if(!DailyState.reroll.pending && !q.claimed && q.required && q.progress>=q.required && contains(x,y,766,top+(rerolls?23:39),126,28))return 30+i;
            if(rerollable(i,appearance) && contains(x,y,766,top+56,126,28))return 60+i;
        }
    } else {
        if(!(DailyState.p.flags&RollClaimed) && DailyState.p.reward_total && contains(x,y,674,354,218,34))return 40;
        if(contains(x,y,784,414,24,22) && DailyState.p.reward_page)return 41;
        if(contains(x,y,882,414,24,22) && DailyState.p.reward_page+1<DailyState.p.reward_pages)return 42;
    }
    return 0;
}
EXPORT int __stdcall DailyHit(int x,int y) {return hitAt(x,y);}
static u32 itemHit(int x,int y){if(!DailyState.visible || !DailyState.ready || DailyState.rolling)return 0;for(int i=0;i<itemCount;++i)if(contains(x,y,items[i].x,items[i].y,items[i].w,items[i].h))return items[i].id;return 0;}
static void pager(u32 page,u32 pages,int x,int y,int left,int right) {
    button(left,"<",x,y,24,22,actionable(true) && page>0);char line[128];line[0]=0;append(line,"Page ");number(line,page+1);append(line," / ");number(line,pages?pages:1);
    text(line,x+28,y+5,70);button(right,">",x+98,y,24,22,actionable(true) && page+1<pages);
}
static void heading(const char* caption,int y) {
    panel(12,y,896,26,0xFFE6F2FC);text(caption,24,y+8,620,0x7D6045);
}
static const char* objectiveName(const Quest& q) {
    if(q.kind==AnyMonster)return "ANY";
    if(q.kind==Pvp)return "PvP Player";
    // DRUI v1/v2 supply the target name in their fixed Hunt/Collect/Use title.
    // Strip only the matching protocol prefix; leave unfamiliar titles intact.
    const char* prefix=q.kind==Monster?"Hunt ":q.kind==Collection?"Collect ":q.kind==UseItem?"Use ":"";
    int i=0;while(prefix[i] && q.title[i]==prefix[i])++i;
    return !prefix[i] && q.title[i]?q.title+i:q.title;
}
static void showTooltip(const char* name,u32 amount,bool required) {
    if(!name || !name[0])return;
    const int width=266,height=42;
    int x=DailyState.mouseX+12,y=DailyState.mouseY+18;
    if(x+width>916)x=916-width;if(x<4)x=4;
    if(y+height>678)y=DailyState.mouseY-height-4;if(y<26)y=26;
    panel(x,y,width,height,0xFFFFFFDE,0xFF8C847B);
    text(name,x+6,y+7,width-12,0x292929);
    char count[128];count[0]=0;append(count,required?"Required: ":"Quantity: ");number(count,amount);
    text(count,x+6,y+23,width-12,0x292929);
}
static void tooltip() {
    if(DailyState.rolling || !DailyState.ready || !(DailyState.p.flags&Ready))return;
    if(DailyState.tab==1){
        for(int i=0;i<5;++i){const auto& q=DailyState.p.quests[i];
            if(q.kind>=AnyMonster && q.kind<=Pvp && contains(DailyState.mouseX,DailyState.mouseY,24,104+i*116,98,98)){
                showTooltip(objectiveName(q),q.required,true);return;
            }
        }
    }
    for(int i=0;i<itemCount;++i){const auto& b=items[i];
        if(!b.name || !b.name[0] || !contains(DailyState.mouseX,DailyState.mouseY,b.x,b.y,b.w,b.h))continue;
        showTooltip(b.name,b.amount,false);return;
    }
}
static void objective(const Quest& q,int y) {
    panel(24,y+8,98,98,0xFFE8EFF9);
    if(q.kind==AnyMonster || q.kind==Monster){
        if(!DailyApi.monster(DailyState.window,q.kind==AnyMonster?1002:q.target,26,y+10,94,94,1200))
            center("Monster",26,y+50,94);
    }else if((q.kind==Collection || q.kind==UseItem) && q.target){
        DailyApi.item(DailyState.window,q.target,57,y+38);
        if(itemCount<64)items[itemCount++]={57,y+38,32,32,q.target,objectiveName(q),q.required};
    }else if(q.kind==Pvp){
        // Small private crossed-swords badge; no asset installation is required.
        for(int i=0;i<28;++i){rect(48+i,y+30+i,4,4,0xFF65788D);rect(77-i,y+30+i,4,4,0xFF65788D);}
        for(int i=0;i<24;++i){rect(50+i,y+31+i,2,2,0xFFE5EDF7);rect(77-i,y+31+i,2,2,0xFFE5EDF7);}
        rect(45,y+57,16,3,0xFFBD963D);rect(69,y+57,16,3,0xFFBD963D);
        center("PvP",28,y+78,90,0x7D6045);
    }
}
static void mysteryReward(int x,int y) {
    // Private 32px pouch, used before a roll and while waiting with Motion off.
    static const int widths[]={12,10,8,10,14,18,22,26,28,28,28,26,22,16};
    for(int row=0;row<14;++row){const int width=widths[row],left=x+(32-width)/2;
        rect(left,y+row*2,width,2,0xFFB6B6B6);
        if(row>0 && row<13)rect(left+2,y+row*2,width-4,2,0xFFE5E3DF);
    }
    rect(x+11,y+5,10,2,0xFFA5A5A5);center("?",x+2,y+11,28,0x999999);
}
static void rewardStar(int x,int y) {
    // Match Gacha's small gold star without changing its shared renderer/assets.
    static const int spans[][3]={{0,4,1},{1,3,3},{2,3,3},{3,0,9},{4,1,7},{5,2,5},{6,2,5},{7,1,3},{7,5,3},{8,1,2},{8,6,2}};
    for(const auto& span:spans)rect(x+span[1],y+span[0],span[2],1,0xFFE6B647);
}
static void rollCard(const Item& r,int x,int y,int width,int index,bool spin,bool result) {
    panel(x,y,width,74,r.id || spin?0xFFF8FCFF:0xFFEEEEEE);
    rect(x+2,y+2,width-4,13,0xFFE9ECF6);
    char line[128];line[0]=0;number(line,static_cast<u32>(index+1));append(line,"   Reward");text(line,x+6,y+3,width-12,0x7D6045);
    if(spin){
        // Centered cycling art, as in Gacha. Never read a real prize/name here.
        const int iconX=x+(width-32)/2,iconY=y+(74-32)/2;
        if(DailyAnimation.icons[index] && !DailyState.motionOff)
            DailyApi.item(DailyState.window,DailyAnimation.icons[index],iconX,iconY);
        else mysteryReward(iconX,iconY);
    }else if(r.id){
        panel(x+5,y+19,34,34,0xFFE7EDF8);DailyApi.item(DailyState.window,r.id,x+6,y+20);
        if(itemCount<64)items[itemCount++]={x+5,y+19,34,34,r.id,r.name,r.amount};
        text(r.name,x+48,y+21,width-56);line[0]=0;append(line,"x");number(line,r.amount);text(line,x+48,y+38,width-56);
        if(result){rewardStar(x+48,y+58);text("Received",x+62,y+58,width-70,0x438844);}
    }else if(result)center("No reward",x+4,y+35,width-8,0x909090);
    else {mysteryReward(x+6,y+21);text("Ready",x+48,y+28,width-56,0x909090);}
}
EXPORT void __fastcall DailyDraw(void* w,void*) {
    if(w!=DailyState.window || !DailyState.visible || at<int>(w,0x14)<920 || at<int>(w,0x18)<720)return;
    reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);itemCount=0;
    panel(0,0,920,720,0xFFF4FBFD);rect(1,1,918,23,0xFFD9ECFD);text("Attendance & Daily Rewards",8,6,400);
    button(1,"X",896,3,20,20);
    const char* tabs[]={"Attendance","Daily Quest","Daily Roll"};
    for(int i=0;i<3;++i){button(2+i,tabs[i],12+i*150,32,142,26);if(DailyState.tab==i)rect(13+i*150,56,140,3,0xFFDAAA48);}
    button(5,"Refresh",806,32,102,26,actionable(true));
    DailyState.drawnResetMinute=resetMinute(tick());
    char clock[128];clock[0]=0;append(clock,"Daily reset in ");number(clock,DailyState.drawnResetMinute/60);append(clock,"h ");number(clock,DailyState.drawnResetMinute%60);append(clock,"m");text(clock,584,40,208);
    if(!DailyState.ready){text("Loading rewards from the server...",30,110,700);text("Use the X or Attendance menu icon to close.",30,135,700);return;}
    if(!(DailyState.p.flags&Ready)){text(DailyState.p.status,24,110,865);button(5,"Refresh",806,32,102,26,true);return;}
    if(DailyState.tab==0){
        heading("Attendance Rewards",76);pager(DailyState.p.attendance_page,4,782,80,10,11);
        for(int i=0;i<7;++i){const auto& d=DailyState.p.attendance[i];const int x=18+i*126;
            const bool claimed=d.status==2,available=d.status==1;
            const u32 edge=d.status?0xFF60C789:0xFFD8D8D8;
            panel(x,116,124,20,d.status?0xFFEAF8EE:0xFFF0F0F0,edge);
            char title[128];title[0]=0;append(title,"Day ");number(title,d.day);center(title,x,121,124,d.status?0x7D6045:0x909090);
            panel(x,138,124,178,claimed?0xFFE5EFFD:available?0xFFF8FCFF:0xFFF0F0F0,edge);
            for(int j=0;j<6;++j){const Item& r=j?DailyState.attendanceExtra[i][j-1]:d.reward;
                reward(r,x+26+j%2*38,146+j/2*36,!available);}
            if(claimed)claimedStamp(w,x+14,138);
            center(claimed?"Claimed":available?"Available":"Locked",x,293,124,available?0x438844:0x7D6045);
            if(DailyState.selectedDay==i)rect(x+3,313,118,2,0xFF60C789);
        }
        panel(12,334,896,86);char day[128];day[0]=0;append(day,"Day ");
        number(day,DailyState.selectedDay>=0?DailyState.p.attendance[DailyState.selectedDay].day:DailyState.p.attendance_day<28?DailyState.p.attendance_day+1:28);
        append(day," / 28");text(day,28,349,400,0x7D6045);
        text("Claim one attendance reward each day.",28,377,680);
        const int selected=DailyState.selectedDay;
        const bool available=selected>=0 && selected<7 && DailyState.p.attendance[selected].status==1;
        button(selected>=0?20+selected:20,"Claim Reward",730,354,162,28,actionable(true) && available);
        text("Select an available day, then click Claim Reward.",28,450,850);
        text("The next reward unlocks at midnight server time. Missed days do not use a reward.",28,476,850);
        text("All items in the selected day's reward are delivered through RODEX.",28,502,850);
    } else if(DailyState.tab==1){
        heading("Daily Quests",70);
        if(DailyState.p.protocol==reroll_version){char line[128];line[0]=0;append(line,"Re-rolls remaining: ");number(line,DailyState.reroll.used<DailyState.reroll.limit?DailyState.reroll.limit-DailyState.reroll.used:0);append(line," / ");number(line,DailyState.reroll.limit);append(line," - Shared across all quests");text(line,570,78,328,0x7D6045);}
        else text("5 random quests each day",700,78,198,0x7D6045);
        for(int i=0;i<5;++i){const auto& q=DailyState.p.quests[i];const int y=96+i*116;
            panel(12,y,896,114,q.claimed?0xFFF0F4F7:0xFFF8FCFF);objective(q,y);
            text(q.title,136,y+16,474,0x7D6045);
            char progress[128];progress[0]=0;number(progress,q.progress);append(progress," / ");number(progress,q.required);
            append(progress,q.kind==Collection?" collected":q.kind==UseItem?" used":" defeated");text(progress,136,y+43,466);
            panel(136,y+67,468,8,0xFFF8FCFF);
            if(q.required)rect(138,y+69,static_cast<int>(464u*q.progress/q.required),4,q.claimed?0xFFABB9C9:0xFF95C8F5);
            text(q.kind==Collection?"Items required in inventory":q.kind==UseItem?"Use the required item":q.kind==Pvp?"Defeat players on a PvP map":"Complete the hunt to claim your reward",136,y+88,466,0x8B8075);
            for(int j=0;j<6;++j)reward(q.rewards[j],646+j%2*38,y+4+j/2*36,q.claimed!=0);
            if(q.claimed)claimedStamp(w,634,y-10);
            const bool rerolls=DailyState.p.protocol==reroll_version;
            button(30+i,q.claimed?"Claimed":q.required && q.progress>=q.required?"Claim Reward":"In Progress",766,y+(rerolls?23:39),126,28,actionable(true) && !DailyState.reroll.pending && !q.claimed && q.required && q.progress>=q.required);
            if(rerolls){
                const auto& r=DailyState.reroll;const bool exhausted=r.used>=r.limit;
                button(60+i,!r.limit?"Disabled":exhausted?"Limit reached":"Re-Roll",766,y+56,126,28,rerollable(i,true));
                if(!exhausted && !q.claimed){char cost[128];price(cost,r.cost);center(cost,766,y+91,126,r.zeny<r.cost?0x5555CC:0x7D6045);}
            }
        }
    } else {
        panel(12,72,896,76);text("Daily Roll",26,86,420,0x7D6045);
        text(DailyState.p.protocol>=six_reward_version?"One free roll each day. Receive 1 to 6 rewards.":"One free roll each day. Receive 1 to 5 rewards.",26,112,630);
        panel(674,82,218,34);
        text(DailyState.rolling?"Today's roll: Rolling...":DailyState.p.flags&RollClaimed?"Today's roll: Claimed":"Today's roll: Ready",682,94,202,0x438844);
        heading("Rolling Rewards",156);
        for(int i=0;i<(DailyState.p.protocol>=six_reward_version?6:5);++i){const bool spin=DailyState.rolling && (DailyState.pending ||
                (static_cast<u32>(i)<DailyState.p.roll_count && static_cast<u32>(i)>=DailyAnimation.revealed));
            rollCard(i==5?DailyState.sixthRoll:DailyState.p.roll[i],24+i%4*222,190+i/4*80,210,i,spin,(DailyState.p.flags&RollClaimed)!=0);
        }
        button(43,DailyState.motionOff?"Motion: Off":"Motion: On",24,358,104,26);
        button(44,"Skip Reveal",138,358,104,26,DailyState.rolling && !DailyState.pending);
        button(40,DailyState.rolling?"Rolling...":DailyState.p.flags&RollClaimed?"Claimed - return tomorrow":"Daily Roll",674,354,218,34,actionable(true) && !(DailyState.p.flags&RollClaimed) && DailyState.p.reward_total>0);
        heading("Possible Rewards",410);pager(DailyState.p.reward_page,DailyState.p.reward_pages,784,414,41,42);
        for(int i=0;i<6;++i){const auto& r=DailyState.p.possible[i];if(r.id)rollCard(r,24+i%3*296,446+i/3*80,284,static_cast<int>(DailyState.p.reward_page*6)+i,false,false);}
        char range[128];range[0]=0;append(range,"Rewards ");number(range,DailyState.p.reward_total?DailyState.p.reward_page*6+1:0);append(range," - ");
        const u32 end=DailyState.p.reward_page*6+6;number(range,end<DailyState.p.reward_total?end:DailyState.p.reward_total);append(range," of ");number(range,DailyState.p.reward_total);
        text(range,26,620,680);
    }
    rect(12,681,896,1,0xFFD4DFE9);
    text(pending(true)?"Waiting for the server...":DailyState.p.status,16,689,889,0x6D6255);
    text("Hover items for names. Right-click an item for details. Rewards arrive by RODEX.",16,706,889,0x8B8075);
    opaqueFooter();
    tooltip();
}
EXPORT void __fastcall DailyDown(void* w,void*,int x,int y) {
    if(w!=DailyState.window || !DailyState.visible)return;release();DailyState.pressed=DailyHit(x,y);
    if(DailyState.pressed)reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);
    else if(y>=0 && y<24){DailyState.dragging=1;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880AD0)(w,x,y);}dirty();
}
EXPORT void __fastcall DailyUp(void*,void*,int x,int y) {
    int hit=DailyHit(x,y),pressed=DailyState.pressed;release();if(!hit || hit!=pressed){dirty();return;}
    if(hit==1){hide();return;}
    if(hit>=2 && hit<=4){DailyState.tab=hit-2;itemCount=0;}
    else if(hit==5)send(Refresh);
    else if(hit==10 || hit==11)send(Refresh,0,DailyState.p.attendance_page+(hit==10?-1:1));
    else if(hit>=20 && hit<27)send(AttendanceClaim,DailyState.p.attendance[hit-20].day-1);
    else if(hit>=30 && hit<35)send(QuestClaim,static_cast<u32>(hit-30));
    else if(hit>=60 && hit<65)send(Reroll,static_cast<u32>(hit-60));
    else if(hit==40){if(send(Roll)){DailyState.rolling=1;DailyState.rollStart=tick();startRoll(DailyState.rollStart);}}
    else if(hit==43){DailyState.motionOff=!DailyState.motionOff;if(DailyState.motionOff && !DailyState.pending)DailyState.rolling=0;}
    else if(hit==44)DailyState.rolling=0;
    else if(hit>=50 && hit<57)DailyState.selectedDay=hit-50;
    else if(hit==41 || hit==42)send(Refresh,0,0xFFFFFFFF,DailyState.p.reward_page+(hit==41?-1:1));
    dirty();
}
EXPORT void __fastcall DailyMove(void*,void*,int x,int y) {
    const int hover=hitAt(x,y,true),right=DailyState.rightItem!=itemHit(x,y)?0:DailyState.right;
    const bool changed=x!=DailyState.mouseX || y!=DailyState.mouseY || hover!=DailyState.hover || right!=DailyState.right;
    DailyState.mouseX=x;DailyState.mouseY=y;DailyState.hover=hover;DailyState.right=right;
    if(changed)dirty();
}
EXPORT void __fastcall DailyDrag(void* w,void*,int x,int y) { if(DailyState.dragging)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880E00)(w,x,y);else DailyMove(w,0,x,y); }
EXPORT void __fastcall DailyCursor(void* w,void*,int x,int y) {
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA23470)(w,x,y);DailyMove(w,0,x,y);
    void* cursor=*reinterpret_cast<void**>(0x121333C);if(cursor)reinterpret_cast<void (__thiscall *)(void*,int)>(0xA764A0)(cursor,(DailyState.hover || itemHit(x,y))?2:0);
}
EXPORT void __fastcall DailyRightDown(void*,void*,int x,int y) {
    DailyState.right=0;if(at<void*>((void*)0x131F4E8,0x19C))return;
    DailyState.rightItem=itemHit(x,y);DailyState.rightSequence=DailyState.sequence;DailyState.right=DailyState.rightItem!=0;
}
EXPORT void __fastcall DailyRightUp(void*,void*,int x,int y) {
    const bool inspect=DailyState.right && DailyState.rightSequence==DailyState.sequence && DailyState.rightItem==itemHit(x,y);DailyState.right=0;
    if(inspect)DailyApi.describe(DailyState.rightItem);
}
EXPORT void __fastcall DailyWheel(void*,void*,int) {}
EXPORT void* __fastcall DailyDestroy(void* w,void*,int flags) { hide();DailyState.window=0;itemCount=0;return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(w,flags); }
