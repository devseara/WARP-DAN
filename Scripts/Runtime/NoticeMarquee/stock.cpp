/* DevSeara - stock 2025-07-16 UIBroadcastBalloon item icons.
 * Legacy NoticeMarquee directory/patch ID retained for saved WARP profiles.
 * No new window, queue, timer, marquee, packet hook or shared text hook.
 */
typedef unsigned int u32;
typedef unsigned char u8;
struct Size { int x,y; };
typedef Size* (__thiscall *MeasureFn)(void*,Size*,const char*,int,int,int,int,int);
typedef int (__thiscall *HeightFn)(void*,const char*,int,int,int,int,int);
typedef void (__thiscall *DrawFn)(void*,int,int,const char*,int,u32,u32,int,int,int);
typedef const char* (__stdcall *ResourceFn)(u32,u32);
typedef void* (__cdecl *ManagerFn)();
typedef const char* (__cdecl *PathFn)(const char*);
typedef void* (__thiscall *TextureFn)(void*,const char*);
struct Api { u32 version; const char* prefix; ResourceFn resource; };
extern "C" __declspec(dllexport) Api NoticeApi = {2,0,0};
static u32 field(void* p,int offset) { return *(u32*)((u8*)p+offset); }
static const int IconSize=18, IconAdvance=20;
static bool tag(const char* s,int n,int& used,u32& id,u32& identified) {
	used=0;id=0;identified=1;
	if(n<5 || s[0]!='^' || s[1]!='i' || s[2]!='[') return false;
	int at=3,digits=0;
	while(at<n && s[at]>='0' && s[at]<='9' && digits<7) { id=id*10+s[at++]-'0';++digits; }
	if(!digits || !id || at>=n) return false;
	if(s[at]==',') {
		if(at+2>=n || (s[at+1]!='0' && s[at+1]!='1')) return false;
		identified=s[at+1]-'0';at+=2;
	}
	if(at>=n || s[at]!=']') return false;
	used=at+1;return true;
}
static int length(const char* s,int count) {
	if(!s || count<0 || count>1023) return -1;
	int n=0;while(n<(count?count:1024) && s[n]) ++n;
	return n<1024?n:-1;
}
static bool tagged(const char* s,int n) {
	int used;u32 id,identified;
	for(int i=0;i<n;++i) if(tag(s+i,n-i,used,id,identified)) return true;
	return false;
}
static Size measure(void* w,const char* s,int n,int font,int height,int bold,int italic) {
	Size total={0,0};int at=0,used;u32 id,identified;
	while(at<n) {
		if(tag(s+at,n-at,used,id,identified)) {
			total.x+=IconAdvance;if(total.y<IconSize) total.y=IconSize;at+=used;continue;
		}
		int start=at++;
		while(at<n && !tag(s+at,n-at,used,id,identified)) ++at;
		Size part;
		((MeasureFn)0xA21A50)(w,&part,s+start,at-start,font,height,bold,italic);
		total.x+=part.x;if(part.y>total.y) total.y=part.y;
	}
	return total;
}
static void icon(void* w,int x,int y,u32 id,u32 identified) {
	if(!NoticeApi.resource || !NoticeApi.prefix) return;
	const char* name=NoticeApi.resource(id,identified);if(!name || !*name) return;
	char path[512];int at=0;
	while(NoticeApi.prefix[at] && at<240) { path[at]=NoticeApi.prefix[at];++at; }
	if(at==240) return;
	int k=0;while(name[k] && k<180) path[at++]=name[k++];if(k==180) return;
	path[at++]='.';path[at++]='b';path[at++]='m';path[at++]='p';path[at]=0;
	void* mgr=((ManagerFn)0xA90350)();const char* converted=((PathFn)0xA9F030)(path);
	void* tex=mgr&&converted?((TextureFn)0xA8D4A0)(mgr,converted):0;
	void* surf=(void*)field(w,0x24);if(!tex || !surf) return;
	int tw=(int)field(tex,0x114),th=(int)field(tex,0x118);
	u32* src=(u32*)field(tex,0x11C);u32* dst=(u32*)field(surf,0x18);
	int ww=(int)field(surf,4),hh=(int)field(surf,8);
	if(!src || !dst || tw<1 || th<1 || tw>64 || th>64 || ww<1 || hh<1) return;
	for(int dy=0;dy<IconSize;++dy) for(int dx=0;dx<IconSize;++dx) {
		int xx=x+dx,yy=y+dy;if(xx<0 || yy<0 || xx>=ww || yy>=hh) continue;
		u32 c=src[(dy*th/IconSize)*tw+dx*tw/IconSize]&0xFFFFFF;
		if(c!=0xFF00FF) dst[yy*ww+xx]=0xFF000000|c;
	}
}
extern "C" __declspec(dllexport) Size* __fastcall NoticeMeasure(void* w,void*,Size* out,const char* s,int count,int font,int height,int bold,int italic) {
	int n=length(s,count);
	if(n<0 || !tagged(s,n)) return ((MeasureFn)0xA21A50)(w,out,s,count,font,height,bold,italic);
	*out=measure(w,s,n,font,height,bold,italic);return out;
}
extern "C" __declspec(dllexport) int __fastcall NoticeHeight(void* w,void*,const char* s,int count,int font,int height,int bold,int italic) {
	int n=length(s,count);
	if(n<0 || !tagged(s,n)) return ((HeightFn)0xA21880)(w,s,count,font,height,bold,italic);
	return measure(w,s,n,font,height,bold,italic).y;
}
extern "C" __declspec(dllexport) void __fastcall NoticeDraw(void* w,void*,int x,int y,const char* s,int count,u32 color,u32 shadow,int font,int height,int bold) {
	int n=length(s,count);
	if(n<0 || !tagged(s,n)) { ((DrawFn)0xA27C20)(w,x,y,s,count,color,shadow,font,height,bold);return; }
	Size total=measure(w,s,n,font,height,bold,0);
	int at=0,used;u32 id,identified;
	while(at<n) {
		if(tag(s+at,n-at,used,id,identified)) {
			icon(w,x,y+(total.y-IconSize)/2,id,identified);x+=IconAdvance;at+=used;continue;
		}
		int start=at++;
		while(at<n && !tag(s+at,n-at,used,id,identified)) ++at;
		Size part;((MeasureFn)0xA21A50)(w,&part,s+start,at-start,font,height,bold,0);
		((DrawFn)0xA27C20)(w,x,y+(total.y-part.y)/2,s+start,at-start,color,shadow,font,height,bold);
		x+=part.x;
	}
}
typedef void (__cdecl *SplitFn)(const char*,void*,int);
typedef void (__cdecl *AppendFn)(void*,const char*,const char*);
typedef const char* (__thiscall *NextFn)(void*,const char*,int);
extern "C" __declspec(dllexport) void __cdecl NoticeSplit(const char* s,void* vector,int budget) {
	int n=length(s,0);
	if(n<0 || !tagged(s,n) || budget<4 || budget>1024) { ((SplitFn)0x979F10)(s,vector,budget);return; }
	// Only this broadcast producer is changed. Native vector ownership and
	// locale character stepping are retained. Tags are indivisible and count
	// as three narrow characters, approximately the 20px icon slot.
	int start=0,at=0,units=0,space=-1,used;u32 id,identified;
	while(at<n) {
		if(s[at]=='\n') { ((AppendFn)0x97A0B0)(vector,s+start,s+at);start=++at;units=0;space=-1;continue; }
		int advance=1,cost=1;
		if(tag(s+at,n-at,used,id,identified)) { advance=used;cost=3; }
		else if((u8)s[at]>=128) {
			void* locale=*(void**)0x159B80C;
			if(locale) {
				const char* next=((NextFn)(*(u32**)locale)[5])(locale,s+at,n-at);
				if(next>s+at && next<=s+n) advance=cost=(int)(next-(s+at));
			}
		}
		if(units+cost>budget && at>start) {
			int end=space>start?space:at;
			((AppendFn)0x97A0B0)(vector,s+start,s+end);
			start=end;while(start<n && s[start]==' ') ++start;
			at=start;units=0;space=-1;continue;
		}
		if(s[at]==' ') space=at;
		at+=advance;units+=cost;
	}
	if(start<n) ((AppendFn)0x97A0B0)(vector,s+start,s+n);
}
