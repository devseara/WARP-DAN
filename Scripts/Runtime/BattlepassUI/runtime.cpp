// Private Gacha-style Battle Pass presentation, 2025-07-16 x86.
// Gameplay remains server-owned. No DLL, imports, global text or actor hooks.
typedef unsigned int u32;
typedef unsigned short u16;
typedef unsigned char u8;
#define EXPORT extern "C" __declspec(dllexport)
template<class T> T& at(void* p,int o){return *reinterpret_cast<T*>(static_cast<u8*>(p)+o);}
#pragma pack(push,1)
struct Objective {u32 kind,target,view,required,progress,exp,flags,token;char name[64];};
struct Item {u32 id,amount;char name[64];};
struct Level {u32 level,flags,count;Item items[5];};
struct UiText {char labels[27][64],trackInfo[6][64],rules[8][64];};
struct Board {u32 daily,weekly,seasonTime,page,pages,level,maxLevel,levelExp,perLevel,missionView;char season[48];Objective quests[6];Level tracks[2][5];Item sixth[2][5];UiText ui;};
struct Request {u16 id,size;u32 magic;u16 version,action;u32 value;};
#pragma pack(pop)
static_assert(sizeof(Board)==7728 && sizeof(UiText)==2624 && sizeof(Objective)==96 && sizeof(Level)==372,"BPUI v7 with unchanged v5/v6 prefixes");
struct Api {
	u8* state;Board* board;u32 font,ctor,send;
	void (__stdcall *text)(void*,const char*,int,int,int,u32);
	void (__stdcall *plain)(void*,const char*,int,int,int,u32);
	void (__stdcall *center)(void*,const char*,int,int,int,u32);
	void (__stdcall *item)(void*,u32,int,int);
	void (__stdcall *describe)(u32);
	int (__thiscall *monster)(void*,u32,int,int,int,int,int);
	const char* (__stdcall *itemName)(u32);
	const char* buttons[4];
	void (__cdecl *stop)();
	void (__thiscall *frameDown)(void*,int,int);
	void (__thiscall *frameUp)(void*,int,int);
	const char* mapPrefix;
};
EXPORT Api BpApi={};
static_assert(sizeof(Api)==80,"Battle Pass private API v2");
extern "C" int __stdcall BpPortrait(void*,int,int,int,int);
extern "C" void* BpPortraitCanvas;
enum {Window=0,Tab=4,Pressed=8,Ready=24,Dragging=28,Packet=32,Type=2904,Difficulty=2908,Pending=2912,
	RequestValue=2916,RewardMode=2920,RewardPending=2924,Hover=2928,Modal=2932,Quote=2936,Fee=2940,
	CursorX=2988,CursorY=2992,CursorPainted=2996,QuoteNonce=3008,Hidden=3020};
static int selectedTrack=0,selectedColumn=-1,rightSlot=0,pressedSlot=0;
static u32 pressedToken=0,rightId=0,replySerial=0,rightSerial=0,lastAction=0;
static int pendingAction=0;
static u32 pendingAt=0,lastReply=0;
static const int width=920,height=560;
static const int missionTierTop=252,missionTierStep=44,missionTierHeight=36;
static int& s(int o){return at<int>(BpApi.state,o);}
static u32 pv(int o){return at<u32>(BpApi.state,Packet+o);}
static u16 version(){return at<u16>(BpApi.state,Packet+8);}
static bool hasBoard(){return version()>=5 && version()<=7;}
enum Label {WindowTitle,BannerTitle,StatusLabel,LevelLabel,PassExpLabel,TrackInfoTitle,TiersTitle,TierLabel,CountLabel,ExpLabel,DifficultyLabel,RulesTitle,NormalLabel,PremiumLabel,RewardsLabel,StandardStatus,PremiumStatus,CurrentLevelLabel,TotalExpLabel,RewardStatusLabel,SeasonInfoTitle,EndsInLabel,EasyTier,NormalTier,HardTier,HardcoreTier,RewardsTitle};
static const char* label(int id){
	static const char* defaults[]={"Battle Pass","BATTLE PASS","Status","Level","Pass EXP","Track Information","Difficulty Tiers","Tier","Count","EXP","Difficulty","Rules","Normal","Premium","Rewards","Standard","Premium","Current level","Total EXP","Status","Season Information","Ends in","Easy","Normal","Hard","Hardcore","Battle Pass Rewards"};
	return version()==7?BpApi.board->ui.labels[id]:defaults[id];
}
static bool premiumUnlocked(){return (at<u16>(BpApi.state,Packet+10)&8)!=0;}
static const Item* rewardItem(int track,int col,int slot){return slot<5?&BpApi.board->tracks[track][col].items[slot]:version()>=6?&BpApi.board->sixth[track][col]:0;}
static bool rewardReached(const Level& r){return r.level && r.level<=BpApi.board->level;}
static bool rewardSelectable(int track,const Level& r){return rewardReached(r) && (!track || (premiumUnlocked() && !(r.flags&8)));}
static const Level* selectedReward(){
	if(!hasBoard() || selectedTrack<0 || selectedTrack>1 || selectedColumn<0 || selectedColumn>4)return 0;
	const auto& r=BpApi.board->tracks[selectedTrack][selectedColumn];return rewardSelectable(selectedTrack,r)?&r:0;
}
static bool rewardClaimable(const Level& r){return rewardReached(r) && (r.flags&4) && !(r.flags&(2|8|16)) && r.count>0 && r.count<=6 && (r.count<=5 || version()>=6);}
static u16 flags(){return at<u16>(BpApi.state,Packet+10);}
static const char* field(int o){return reinterpret_cast<const char*>(BpApi.state+Packet+o);}
static u32 tick(){return (*reinterpret_cast<u32 (__stdcall **)()>(0xFC17B0))();}
static bool inside(int x,int y,int bx,int by,int bw,int bh){return x>=bx && y>=by && x<bx+bw && y<by+bh;}
static void dirty(void* w){if(w)at<int>(w,0x58)=1;}
static void rect(void* w,int x,int y,int bw,int bh,u32 color){
	void* surface=at<void*>(w,0x24);if(!surface || !at<void*>(surface,0x18))return;
	const int stride=at<int>(surface,4),sh=at<int>(surface,8);
	if(x<0 || y<0 || bw<0 || bh<0 || x+bw>stride || y+bh>sh)return;
	u32* dst=at<u32*>(surface,0x18);
	for(int row=y;row<y+bh;++row)for(int col=x;col<x+bw;++col)dst[row*stride+col]=color;
	at<u8>(surface,0x1C)=1;
}
static void panel(void* w,int x,int y,int bw,int bh,u32 color=0xFFF4FBFD,u32 edge=0xFFD4DFE9){
	rect(w,x+2,y,bw-4,bh,edge);rect(w,x,y+2,bw,bh-4,edge);
	rect(w,x+1,y+3,bw-2,bh-6,color);rect(w,x+3,y+1,bw-6,bh-2,color);
}
static void grayReward(void* w,int x,int y){
	void* surface=at<void*>(w,0x24);if(!surface || !at<void*>(surface,0x18))return;
	const int stride=at<int>(surface,4);if(x<0 || y<0 || x+96>stride || y+133>at<int>(surface,8))return;
	u32* pixels=at<u32*>(surface,0x18);
	// Desaturate the complete future-level card, including native item icons.
	// A light gray wash keeps text readable. Tooltips are painted afterward.
	for(int row=y;row<y+133;++row)for(int col=x;col<x+96;++col){
		u32& pixel=pixels[row*stride+col];const u32 luminance=(((pixel>>16)&255)*77+((pixel>>8)&255)*150+(pixel&255)*29)>>8;
		const u32 gray=(luminance*3+224)/4;pixel=0xFF000000|gray*0x010101;
	}
	at<u8>(surface,0x1C)=1;
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
static void line(char* out,const char* value){int i=0;while(i<126 && value[i]){out[i]=value[i];++i;}out[i]=0;}
static void append(char* out,const char* value){int i=0;while(i<126 && out[i])++i;while(i<126 && *value)out[i++]=*value++;out[i]=0;}
static void number(char* out,u32 n){char rev[16];int i=0;do{rev[i++]=static_cast<char>('0'+n%10);n/=10;}while(n);int j=0;while(i)out[j++]=rev[--i];out[j]=0;}
static void addNumber(char* out,u32 n){char temp[128];number(temp,n);append(out,temp);}
static void txt(void* w,const char* value,int x,int y,int bw,u32 color=0x5A5A5A){BpApi.text(w,value,x,y,bw,color);}
static void clockText(char* out,u32 remaining){
	u32 elapsed=(tick()-lastReply)/1000;if(elapsed<remaining)remaining-=elapsed;else remaining=0;
	const u32 days=remaining/86400,hours=remaining/3600%24,minutes=remaining/60%60,seconds=remaining%60;
	line(out,"");if(days){addNumber(out,days);append(out,"d ");}addNumber(out,hours);append(out,":");
	if(minutes<10)append(out,"0");addNumber(out,minutes);append(out,":");if(seconds<10)append(out,"0");addNumber(out,seconds);
}
static void* loadTexture(const char* resource){
	if(!resource)return 0;
	void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return 0;
	const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(resource);if(!path)return 0;
	return reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);
}
static void* texture(int state){
	void* tex=loadTexture(BpApi.buttons[state]);
	return tex && at<int>(tex,0x114)==51 && at<int>(tex,0x118)==20 && at<void*>(tex,0x11C)?tex:0;
}
static void mapThumbnail(void* w,const char* map,int x,int y){
	// Same native map BMP resources as the original habitat list. The wire
	// field is a 24-byte map token, never a client-supplied resource path.
	int length=0;while(length<24 && map[length]){
		const char c=map[length];if(!((c>='a' && c<='z') || (c>='A' && c<='Z') || (c>='0' && c<='9') || c=='_' || c=='@'))return;
		++length;
	}
	if(!length || length==24 || !BpApi.mapPrefix)return;
	char path[128];int n=0;while(n<96 && BpApi.mapPrefix[n]){path[n]=BpApi.mapPrefix[n];++n;}
	if(n==96)return;
	path[n]=0;append(path,map);append(path,".bmp");
	void* tex=loadTexture(path);if(!tex)return;
	const int sw=at<int>(tex,0x114),sh=at<int>(tex,0x118);const u32* src=at<u32*>(tex,0x11C);
	if(!src || sw<1 || sh<1 || sw>1024 || sh>1024)return;
	void* surface=at<void*>(w,0x24);if(!surface || !at<void*>(surface,0x18))return;
	const int stride=at<int>(surface,4);if(x<0 || y<0 || x+24>stride || y+24>at<int>(surface,8))return;
	u32* dst=at<u32*>(surface,0x18);
	for(int row=0;row<24;++row)for(int col=0;col<24;++col){
		const u32 rgb=src[(row*sh/24)*sw+col*sw/24]&0xFFFFFF;
		// Stock BMPs can have zero alpha. Only the magenta color key is clear.
		if(rgb!=0xFF00FF)dst[(y+row)*stride+x+col]=0xFF000000|rgb;
	}
	at<u8>(surface,0x1C)=1;
}
struct Control {int id,x,y,w,h;const char* text;bool enabled;};
static void button(void* w,const Control& c,bool selected=false){
	int state=!c.enabled?3:s(Pressed)==c.id?2:s(Hover)==c.id?1:0;
	void* tex=texture(state);if(!tex && state)tex=texture(0);
	panel(w,c.x,c.y,c.w,c.h,0xFFDDEFFC);
	void* surface=at<void*>(w,0x24);
	if(tex && surface && at<void*>(surface,0x18) && c.x>=0 && c.y>=0 && c.w>4 && c.h>4 && c.x+c.w<=at<int>(surface,4) && c.y+c.h<=at<int>(surface,8)){
		u32* dst=at<u32*>(surface,0x18);const u32* src=at<u32*>(tex,0x11C);const int stride=at<int>(surface,4);
		for(int y=0;y<c.h;++y)for(int x=0;x<c.w;++x){
			const int sx=x<2?x:x>=c.w-2?51-(c.w-x):2+(x-2)*47/(c.w-4);
			const int sy=y<2?y:y>=c.h-2?20-(c.h-y):2+(y-2)*16/(c.h-4);
			const u32 p=src[sy*51+sx],alpha=p>>24;if(!alpha || (p&0xFFFFFF)==0xFF00FF)continue;
			u32& d=dst[(c.y+y)*stride+c.x+x];u32 result=0xFF000000;
			for(int shift=0;shift<24;shift+=8)result|=((((p>>shift)&255)*alpha+((d>>shift)&255)*(255-alpha)+127)/255)<<shift;
			d=result;
		}
	}
	if(selected){rect(w,c.x,c.y,c.w,1,0xFFD0A03C);rect(w,c.x,c.y+c.h-1,c.w,1,0xFFD0A03C);rect(w,c.x,c.y,1,c.h,0xFFD0A03C);rect(w,c.x+c.w-1,c.y,1,c.h,0xFFD0A03C);}
	if(c.id>=32 && c.id<=35)txt(w,c.text,c.x+12,c.y+(c.h-static_cast<int>(BpApi.font))/2,170,c.enabled?0x7D6045:0xA0A0A0);
	else BpApi.center(w,c.text,c.x+3,c.y+(c.h-static_cast<int>(BpApi.font))/2,c.w-6,c.enabled?0x7D6045:0xA0A0A0);
}
static bool busy(){return pendingAction && tick()-pendingAt<1200;}
static int controls(Control* out){
	int n=0;const bool enabled=s(Ready) && (flags()&16) && !busy();
	if(s(Modal)){
		out[n++]={80,345,326,90,22,"Cancel",s(Modal)!=3};out[n++]={81,485,326,90,22,"Confirm",s(Modal)==2 && s(Quote)!=0};return n;
	}
	static const char* tabs[]={"Quests","Mission","Rewards","My Stats"};
	for(int i=0;i<4;++i)out[n++]={i+1,10,38+i*32,92,24,tabs[i],true};
	out[n++]={5,896,2,20,18,"X",true};
	if(s(Tab)==0){
		if(hasBoard())for(int i=0;i<6;++i){const auto& q=BpApi.board->quests[i];out[n++]={10+i,639,167+(i%3)*42+(i/3)*168,82,22,(q.flags&2)?"Claimed":(q.flags&4)?"Claim":"In Progress",enabled && (q.flags&4)!=0};}
		out[n++]={6,581,482,140,22,"Difficulty Missions",true};
	}else if(s(Tab)==1){
		if(!(flags()&1)){
			out[n++]={30,138,177,184,24,"Hunt Monsters",enabled};out[n++]={31,334,177,184,24,"Collect Items",enabled};
			for(int i=0;i<4;++i)out[n++]={32+i,138,missionTierTop+i*missionTierStep,576,missionTierHeight,label(EasyTier+i),enabled && (flags()&(1<<(6+s(Type)*4+i)))!=0};
			const int d=s(Difficulty),t=s(Type);
			out[n++]={36,584,482,136,22,"Start Challenge",enabled && d>=1 && d<=4 && t>=0 && t<2 && (flags()&(1<<(5+t*4+d)))!=0};
		}else{
			out[n++]={37,478,482,102,22,"Abandon",enabled && (flags()&7)==1};
			out[n++]={38,590,482,130,22,(flags()&4)?"Get New Mission":"Claim Reward",enabled && (flags()&6)!=0};
		}
	}else if(s(Tab)==2 && hasBoard()){
		const auto& b=*BpApi.board;
		// Keep both button paint and hitboxes inside the 22px header, with 2px padding.
		out[n++]={40,664,138,26,18,"<",b.page>0 && !busy()};out[n++]={41,694,138,26,18,">",b.page+1<b.pages && !busy()};
		const Level* r=selectedReward();
		out[n++]={42,606,493,114,22,"Claim Reward",enabled && r && rewardClaimable(*r)};
	}else if(s(Tab)==3)out[n++]={43,606,482,114,22,"View Rewards",true};
	return n;
}
static int hit(int x,int y){Control c[16];const int n=controls(c);for(int i=0;i<n;++i)if(inside(x,y,c[i].x,c[i].y,c[i].w,c[i].h))return c[i].enabled?c[i].id:0;return 0;}
static bool input(void* w){
	if(!w || !at<int>(w,0x28) || s(Hidden) || at<int>((void*)0x131F4E8,0x404))return false;
	void* capture=at<void*>((void*)0x131F4E8,0x19C);return !capture || capture==w;
}
static void release(void* w){
	if(s(Dragging)){s(Dragging)=0;BpApi.frameUp(w,0,0);}
	if(at<void*>((void*)0x131F4E8,0x19C)==w)reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);
	s(Pressed)=0;pressedSlot=0;
}
static bool send(int action,u32 value=0){
	if(!s(Ready))return false;
	u16 protocol=version();if(pv(1188)&512)protocol=5;if(pv(1188)&1024)protocol=6;if(pv(1188)&2048)protocol=7;
	if(protocol<4 || (action>=19 && protocol<5))return false;
	if(action && action!=20 && tick()-lastAction<1000)return false;
	Request r={0x0BF9,16,0x49555042,protocol,static_cast<u16>(action),value};
	void* transport=reinterpret_cast<void* (__cdecl *)()>(BpApi.ctor)();if(!transport)return false;
	reinterpret_cast<void (__thiscall *)(void*,int,const void*)>(BpApi.send)(transport,16,&r);
	if(action){pendingAction=action;pendingAt=tick();if(action!=20)lastAction=pendingAt;}
	return true;
}
static void hide(void* w){release(w);s(Hidden)=1;s(Modal)=0;s(Hover)=0;rightSlot=0;at<int>(w,0x28)=0;BpApi.stop();}
static u32 percent(u32 value,u32 limit){if(!limit)return 0;if(value>=limit)return 100;while(value>42949672){value>>=1;limit>>=1;}return value*100/limit;}
static void bar(void* w,int x,int y,int bw,u32 percent){panel(w,x,y,bw,8,0xFFF5F8FD);if(percent>100)percent=100;rect(w,x+2,y+2,static_cast<int>((bw-4)*percent/100),4,0xFF89AEE8);}
static void heading(void* w,const char* label,int y,int textWidth=588){panel(w,122,y,612,22,0xFFE6F2FC);txt(w,label,132,y+5,textWidth,0x7D6045);}
static const char* name(u32 id,const char* fallback){const char* text=id && BpApi.itemName?BpApi.itemName(id):0;return text && *text?text:fallback;}
struct ItemHit {u32 id;const char* title;u32 amount,token;};
static ItemHit itemHit(int x,int y){
	ItemHit result={};if(s(Modal) || s(Dragging) || !s(Ready))return result;
	if(s(Tab)==0 && hasBoard()){
		for(int i=0;i<6;++i){const auto& q=BpApi.board->quests[i];int yy=161+i%3*42+i/3*168;
			if((q.flags&1) && q.kind<2 && inside(x,y,132,yy,328,38))return {q.kind==1?q.target:0,q.kind==1?name(q.target,q.name):q.name,q.required,q.token};}
	}else if(s(Tab)==1 && (flags()&1)){
		if(pv(1196)==0 && hasBoard() && BpApi.board->missionView && inside(x,y,140,176,96,102))return {0,field(108),0,pv(2528)};
		// Retain item inspection on its icon, not the entire mission panel.
		if(pv(1196)==1 && inside(x,y,172,209,32,32)){const u32 id=pv(2528);return {id,name(id,field(108)),0,id};}
	}else if(s(Tab)==2 && hasBoard()){
		for(int track=0;track<2;++track)for(int col=0;col<5;++col){const auto& r=BpApi.board->tracks[track][col];
			for(int i=0;i<6 && i<static_cast<int>(r.count);++i){int xx=222+col*100+(i%2)*38,yy=188+track*151+(i/2)*36;const Item* item=rewardItem(track,col,i);
				if(item && item->id && inside(x,y,xx,yy,34,34))return {item->id,name(item->id,item->name),item->amount,r.level};}}
	}return result;
}
static void tooltip(void* w){
	if(!input(w) || s(Dragging) || s(Pressed) || s(Modal))return;
	if(s(Tab)==1 && pv(1196)!=0)return; // Mission hover labels belong only to the monster preview.
	if(reinterpret_cast<void* (__thiscall *)(void*,int,int)>(0xA336D0)((void*)0x131F4E8,*reinterpret_cast<int*>(0x11E40D4),*reinterpret_cast<int*>(0x11E40D8))!=w)return;
	const auto item=itemHit(s(CursorX),s(CursorY));if(!item.title || !*item.title)return;
	char title[128];line(title,item.title);
	int x=s(CursorX)+16,y=s(CursorY)+18,bw=260,bh=item.amount?42:25;if(x+bw>width-6)x=width-6-bw;if(y+bh>height-6)y=s(CursorY)-bh-5;
	panel(w,x,y,bw,bh,0xFFFFFFDC,0xFF8A8778);txt(w,title,x+7,y+6,bw-14,0x282828);
	if(item.amount){char amount[128];line(amount,s(Tab)==0?"Required: ":"Quantity: ");addNumber(amount,item.amount);txt(w,amount,x+7,y+23,bw-14,0x484848);}
}
EXPORT void __stdcall BpDraw(void* w){
	if(!w || !BpApi.state || !BpApi.board)return;auto& b=*BpApi.board;
	s(CursorPainted)=0;rect(w,0,0,width,height,0xFFFFFFFF);panel(w,0,0,width,21,0xFFDDEFFC);
	txt(w,label(WindowTitle),8,4,870,0x7D6045);rect(w,0,22,112,height-22,0xFFF6F6FF);
	panel(w,122,28,504,96);txt(w,label(BannerTitle),138,42,470,0x7D6045);
	txt(w,hasBoard()?b.season:"Daily & Weekly Challenges",138,64,470);
	char text[128],time[128];if(hasBoard()){clockText(time,b.seasonTime);line(text,label(EndsInLabel));append(text,": ");append(text,time);txt(w,text,138,85,470,0x3333BB);}
	panel(w,636,28,272,96);panel(w,643,34,67,84,0xFFE8EFF9);BpPortrait(w,645,36,63,80);
	BpApi.plain(w,field(20),718,39,178,0x7D6045);
	line(text,label(StatusLabel));append(text,": ");append(text,field(348));txt(w,text,718,59,178);
	line(text,label(LevelLabel));append(text,": ");append(text,field(316));txt(w,text,718,79,178);
	line(text,label(PassExpLabel));append(text,": ");append(text,field(284));txt(w,text,718,99,178);
	panel(w,122,136,612,382);panel(w,746,136,162,382);
	txt(w,label(s(Tab)==2?TrackInfoTitle:TiersTitle),756,147,140,0x7D6045);
	if(s(Tab)==2){static const char* defaults[]={"Normal rewards are free.","Premium rewards require","an unlocked premium pass.","Select a level and track,","then click Claim Reward.","Items arrive via RODEX."};static const int rows[]={176,197,213,244,260,291};for(int i=0;i<6;++i)txt(w,version()==7?b.ui.trackInfo[i]:defaults[i],756,rows[i],140);}
	else{
		static const u32 colors[]={0xFFDEF0D0,0xFFFFEFBC,0xFFFFE0C7,0xFFF5D5D0};
		txt(w,label(TierLabel),756,174,52);txt(w,label(CountLabel),815,174,43);txt(w,label(ExpLabel),862,174,38);
		for(int i=0;i<4;++i){const int type=s(Type)==1?1:0;panel(w,754,192+i*24,59,21,colors[i]);txt(w,label(EasyTier+i),758,197+i*24,54);txt(w,field(788+(type*4+i)*48),818,197+i*24,41);txt(w,field(812+(type*4+i)*48),862,197+i*24,38);}
	}
	txt(w,label(RulesTitle),756,330,140,0x7D6045);static const char* rules[]={"One difficulty mission","per account at a time.","","Items used on turn-in.","","Abandon fee:","","Pass resets monthly."};for(int i=0;i<8;++i)txt(w,version()==7?b.ui.rules[i]:i==6?field(372):rules[i],756,353+i*18,140);
	if(s(Tab)==0){
		if(!hasBoard()){heading(w,"Daily & Weekly Quests",136);txt(w,"Waiting for the updated Battle Pass server...",136,181,580);}
		else for(int period=0;period<2;++period){int top=136+period*168;heading(w,period?"Weekly Quests":"Daily Quests",top);
			clockText(time,period?b.weekly:b.daily);line(text,"Resets in: ");append(text,time);txt(w,text,526,top+5,198);
			for(int kind=0;kind<3;++kind){const int index=period*3+kind,y=161+period*168+kind*42;const auto& q=b.quests[index];
				panel(w,132,y,591,38,0xFFF7FAFD);
				if(kind==1 && q.target){panel(w,136,y+2,34,34,0xFFE7EDF8);BpApi.item(w,q.target,137,y+3);}
				line(text,kind==0?"Hunt ":kind==1?"Collect ":"Complete ");addNumber(text,q.required);append(text,kind==2?" quests":" ");if(kind<2)append(text,kind==1?name(q.target,q.name):q.name);
				txt(w,(q.flags&1)?text:"Not configured",kind==1?177:141,y+5,kind==1?265:300);
				number(text,q.progress);append(text," / ");addNumber(text,q.required);txt(w,text,kind==1?177:141,y+21,278,(q.flags&4)?0x438844:0x707070);
				line(text,"+");addNumber(text,q.exp);append(text," ");append(text,label(ExpLabel));txt(w,text,552,y+12,80,0x7D6045);
			}
		}
	}else if(s(Tab)==1){
		if(!(flags()&1)){
			heading(w,"Choose a Difficulty Mission",136);txt(w,version()>=4 && (pv(1188)&4096)?field(2776):"Choose a type and an available tier. Targets use your configured pools.",138,207,576);
			panel(w,138,225,576,20,0xFFE6F2FC);
			txt(w,label(DifficultyLabel),150,230,170,0x7D6045);txt(w,label(CountLabel),335,230,65,0x7D6045);txt(w,label(ExpLabel),416,230,65,0x7D6045);txt(w,label(StatusLabel),509,230,194,0x7D6045);
		}else{
			heading(w,"Current Mission",136);panel(w,136,172,104,110,0xFFE8EFF9);
			if(pv(1196)==1)BpApi.item(w,pv(2528),172,209);else if(hasBoard() && b.missionView)BpApi.monster(w,b.missionView,140,176,96,102,1200);
			txt(w,field(44),252,176,460,0x7D6045);txt(w,field(236),252,199,460);txt(w,field(204),252,223,460,(flags()&4)?0x3333BB:0x438844);
			txt(w,field(172),252,250,460);bar(w,252,272,462,pv(12));heading(w,"Where to Hunt",294);txt(w,field(2776),136,320,578);
			for(int i=0;i<5 && i<static_cast<int>(pv(2532));++i){int yy=340+i*26;panel(w,136,yy,580,25);panel(w,140,yy,24,24,0xFFE8EFF9);mapThumbnail(w,field(2536+i*48),140,yy);txt(w,field(2536+i*48),174,yy+6,337);txt(w,field(2560+i*48),520,yy+6,181);}
		}
	}else if(s(Tab)==2){
		heading(w,label(RewardsTitle),136,524); // Reserve title space before the pager.
		if(hasBoard()){
			const u32 normalEdge=0xFF60C789,premiumEdge=0xFFD0A03C;
			for(int col=0;col<5;++col){const auto& r=b.tracks[0][col];const bool reached=rewardReached(r);if(selectedReward() && selectedColumn==col)panel(w,210+col*100,163,96,19,selectedTrack?0xFFFFF5DB:0xFFEAF8EE,selectedTrack?premiumEdge:normalEdge);else if(!reached)panel(w,210+col*100,163,96,19,0xFFF0F0F0,0xFFD8D8D8);line(text,r.level?label(LevelLabel):"");if(r.level){append(text," ");addNumber(text,r.level);}BpApi.center(w,text,210+col*100,168,96,reached?0x7D6045:0x909090);}
			for(int track=0;track<2;++track){int yy=184+track*151;const bool locked=track && !premiumUnlocked();panel(w,132,yy,72,133,locked?0xFFF0F0F0:track?0xFFFFF5DB:0xFFF4FBFD,locked?0xFFD8D8D8:0xFFD4DFE9);txt(w,label(track?PremiumLabel:NormalLabel),138,yy+45,62,locked?0x909090:0x5A5A5A);txt(w,label(RewardsLabel),138,yy+62,62,locked?0x909090:0x5A5A5A);
				for(int col=0;col<5;++col){const auto& r=b.tracks[track][col];int xx=210+col*100;
					panel(w,xx,yy,96,133,(r.flags&2)?0xFFE5EFFD:track?0xFFFFFCF3:0xFFF8FCFF,selectedReward()==&r?(track?premiumEdge:normalEdge):0xFFD4DFE9);
					for(int i=0;i<6 && i<static_cast<int>(r.count);++i){const Item* item=rewardItem(track,col,i);if(!item || !item->id)continue;int ix=xx+12+i%2*38,iy=yy+4+i/2*36;panel(w,ix,iy,34,34,0xFFE7EDF8);BpApi.item(w,item->id,ix+1,iy+1);number(text,item->amount);BpApi.center(w,text,ix,iy+25,34,0x5A5A5A);}
					const bool claimable=rewardSelectable(track,r) && rewardClaimable(r);
					const char* status=(r.flags&16) || r.count>6?"Config error":!(r.flags&1)?"No reward":r.flags&2?"Claimed":r.count==6 && version()<6?"Update server":claimable?"Available":"Locked";
					BpApi.center(w,status,xx,yy+119,96,claimable?0x438844:0x7D6045);
					if(r.flags&2)claimedStamp(w,xx,yy);
					if(!rewardSelectable(track,r))grayReward(w,xx,yy);
				}
			}
			line(text,label(LevelLabel));append(text," ");addNumber(text,b.level);txt(w,text,138,480,90,0x7D6045);bar(w,228,481,254,percent(b.levelExp,b.perLevel));
			number(text,b.levelExp);append(text," / ");addNumber(text,b.perLevel);append(text," ");append(text,label(ExpLabel));txt(w,text,228,498,265);
		}else txt(w,"Update the server for both reward tracks.",136,182,575);
	}else{
		heading(w,"My Stats",136);BpApi.plain(w,field(20),138,170,576,0x7D6045);
		txt(w,label(CurrentLevelLabel),138,207,180);txt(w,field(316),345,207,350);txt(w,label(TotalExpLabel),138,235,180);txt(w,field(284),345,235,350);txt(w,label(RewardStatusLabel),138,263,180);txt(w,field(348),345,263,350);
		bar(w,138,299,576,pv(1172));BpApi.center(w,field(516),138,320,576,0x7D6045);heading(w,label(SeasonInfoTitle),360);
		txt(w,hasBoard()?b.season:"Monthly Battle Pass",138,395,576);
		if(hasBoard()){clockText(time,b.seasonTime);line(text,label(EndsInLabel));append(text,": ");append(text,time);txt(w,text,138,423,576,0x3333BB);}
	}
	Control list[16];const int count=controls(list);for(int i=0;i<count;++i){bool selected=(list[i].id<=4 && list[i].id-1==s(Tab)) || (list[i].id==30+s(Type) && s(Tab)==1) || (list[i].id==31+s(Difficulty) && s(Difficulty)>0 && list[i].id>=32 && list[i].id<=35);button(w,list[i],selected);}
	// Tier values overlay the same clickable row, not separate hidden controls.
	if(s(Tab)==1 && !(flags()&1))for(int i=0;i<4;++i){int yy=missionTierTop+i*missionTierStep+(missionTierHeight-static_cast<int>(BpApi.font))/2;txt(w,field(788+(s(Type)*4+i)*48),335,yy,65);txt(w,field(812+(s(Type)*4+i)*48),416,yy,65);txt(w,field(2272+(s(Type)*4+i)*32),509,yy,194);}
	rect(w,122,526,786,1,0xFFD4DFE9);txt(w,"Rewards are delivered by RODEX. Hover items or targets for their names.",132,536,768,0x888888);
	if(s(Modal)){
		panel(w,270,200,380,168,0xFFF4FBFD);txt(w,"Abandon Mission",286,214,348,0x7D6045);txt(w,"Abandon this mission and pay the fee?",286,245,348);txt(w,"This difficulty will go on cooldown.",286,267,348);
		txt(w,s(Modal)==1?"Fetching current fee...":reinterpret_cast<const char*>(BpApi.state+Fee),286,297,348);
		for(int i=0;i<count;++i)button(w,list[i]);
	}else tooltip(w);
}
EXPORT void __stdcall BpNotify(){
	++replySerial;lastReply=tick();pendingAction=0;rightSlot=0;
	if(!hasBoard())return;auto& b=*BpApi.board;b.season[47]=0;
	for(auto& q:b.quests)q.name[63]=0;
	for(auto& track:b.tracks)for(auto& level:track)for(auto& item:level.items)item.name[63]=0;
	if(version()>=6)for(auto& track:b.sixth)for(auto& item:track)item.name[63]=0;
	if(version()==7){for(auto& text:b.ui.labels)text[63]=0;for(auto& text:b.ui.trackInfo)text[63]=0;for(auto& text:b.ui.rules)text[63]=0;}
	if(selectedTrack<0 || selectedTrack>1)selectedTrack=0;
	if(selectedTrack && !premiumUnlocked())selectedTrack=0;
	if(!selectedReward()){selectedColumn=-1;for(int col=0;col<5;++col)if(rewardSelectable(selectedTrack,b.tracks[selectedTrack][col])){selectedColumn=col;break;}}
}
EXPORT void __stdcall BpMove(void* w,int x,int y){
	if(!input(w))return;s(CursorX)=x;s(CursorY)=y;const int target=hit(x,y);if(target!=s(Hover) || itemHit(x,y).title){s(Hover)=target;dirty(w);}else dirty(w);
}
EXPORT void __stdcall BpCursor(void* w,int x,int y){
	reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA23470)(w,x,y);BpMove(w,x,y);
	void* cursor=*reinterpret_cast<void**>(0x121333C);if(cursor)reinterpret_cast<void (__thiscall *)(void*,int)>(0xA764A0)(cursor,(s(Hover)||itemHit(x,y).title)?2:0);
}
EXPORT void __stdcall BpMouse(void* w,int x,int y,int mode){
	if(!input(w)){if(mode==1)release(w);return;}BpMove(w,x,y);
	if(mode>=2){const auto item=itemHit(x,y);
		if(mode==2){rightSlot=item.id?1:0;rightId=item.id;rightSerial=replySerial;}
		else{const bool valid=rightSlot && rightSerial==replySerial && item.id==rightId && !s(Pressed);rightSlot=0;if(valid)BpApi.describe(item.id);}return;}
	int control=hit(x,y);
	if(!s(Modal) && s(Tab)==2 && hasBoard() && !control)for(int track=0;track<2;++track)for(int col=0;col<5;++col)if(rewardSelectable(track,BpApi.board->tracks[track][col]) && inside(x,y,210+col*100,184+track*151,96,133))control=50+track*5+col;
	if(mode==0){
		release(w);s(Pressed)=control;pressedSlot=control;pressedToken=replySerial;
		if(control){reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);return;}
		if(!s(Modal) && inside(x,y,0,0,width,21)){s(Dragging)=1;BpApi.frameDown(w,x,y);}return;
	}
	const int old=pressedSlot;const u32 serial=pressedToken;release(w);if(!control || old!=control)return;
	if(control<=4){s(Tab)=control-1;s(Hover)=0;return;}
	if(control==5){hide(w);return;}
	if(control==6){s(Tab)=1;return;}
	if(control==43){s(Tab)=2;return;}
	if(control>=50 && control<60){if(serial==replySerial){selectedTrack=(control-50)/5;selectedColumn=(control-50)%5;}return;}
	if(control==80){s(Modal)=0;return;}
	// Never reinterpret a held press after a reset/reply changed the target.
	if(serial!=replySerial || busy())return;
	if(control>=10 && control<16){send(19,BpApi.board->quests[control-10].token);return;}
	if(control==30 || control==31){s(Type)=control-30;s(Difficulty)=0;return;}
	if(control>=32 && control<=35){s(Difficulty)=control-31;return;}
	if(control==36){if(send(3+s(Type)*4+s(Difficulty)))s(Pending)=1;return;}
	if(control==37){s(Modal)=1;s(Quote)=0;s(QuoteNonce)=(s(QuoteNonce)+1)&65535;if(!s(QuoteNonce))s(QuoteNonce)=1;send(16,static_cast<u32>(s(QuoteNonce)));return;}
	if(control==38){if(flags()&4){if(send(18))s(Pending)=2;}else if(send(1))hide(w);return;}
	if(control==40 || control==41){send(20,BpApi.board->page+(control==40?-1:1));return;}
	if(control==42){const Level* r=selectedReward();if(r && rewardClaimable(*r))send(selectedTrack?15:14,r->level);return;}
	if(control==81 && s(Modal)==2 && s(Quote)){if(send(17,static_cast<u32>(s(Quote))))s(Modal)=3;}
}
EXPORT void __stdcall BpCleanup(){
	if(BpPortraitCanvas){reinterpret_cast<void* (__thiscall *)(void*,int)>(0x86E240)(BpPortraitCanvas,1);BpPortraitCanvas=0;}
	pressedSlot=rightSlot=pendingAction=0;
}
