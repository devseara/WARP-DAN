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
extern "C" __declspec(dllexport) Api NoticeApi = {3,0,0};
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
// MSVC's native narrow string. Borrowed inputs are never destroyed; the native
// formatter owns its output and that output is released with its own destructor.
struct NativeString { u32 data[4],size,capacity; };
static const char* chars(const NativeString& s) { return s.capacity<16?(const char*)s.data:(const char*)s.data[0]; }
static NativeString borrow(const char* s,int n) {
	NativeString value={{0,0,0,0},(u32)n,15};
	if(n<16) { for(int i=0;i<n;++i) ((volatile char*)value.data)[i]=s[i]; }
	else { value.data[0]=(u32)s;value.capacity=(u32)n; }
	return value;
}
static int base62(char c) {
	if(c>='0' && c<='9') return c-'0';
	if(c>='a' && c<='z') return c-'a'+10;
	if(c>='A' && c<='Z') return c-'A'+36;
	return -1;
}
static bool field62(const char* s,int n,int& at,char separator) {
	if(at>=n || s[at++]!=separator) return false;
	int start=at;u32 value=0;
	while(at<n && base62(s[at])>=0) {
		u32 digit=(u32)base62(s[at++]);if(value>(0xFFFFFFFFu-digit)/62) return false;
		value=value*62+digit;
	}
	return at-start>=2;
}
static bool itemLink(const char* s,int n,int& used,u32& id) {
	const char* open="<ITEML>";const char* close="</ITEML>";
	if(n<37) return false;
	for(int i=0;i<7;++i) if(s[i]!=open[i]) return false;
	int end=7;while(end<n && end<512 && s[end]!='<') ++end;
	if(end+8>n || end==512) return false;
	for(int i=0;i<8;++i) if(s[end+i]!=close[i]) return false;
	for(int i=7;i<12;++i) if(base62(s[i])<0) return false;
	if(s[12]!='0' && s[12]!='1') return false;
	int at=13;id=0;
	while(at<end && base62(s[at])>=0) {
		u32 digit=(u32)base62(s[at++]);if(id>(9999999u-digit)/62) return false;
		id=id*62+digit;
	}
	if(at==13 || !id) return false;
	if(at<end && s[at]=='%' && !field62(s,end,at,'%')) return false;
	if(at<end && s[at]=='&' && !field62(s,end,at,'&')) return false;
	if(!field62(s,end,at,'\'')) return false;
	for(int i=0;i<4;++i) if(!field62(s,end,at,')')) return false;
	int options=0;
	while(at<end && options++<5) if(!field62(s,end,at,'+') || !field62(s,end,at,',') || !field62(s,end,at,'-')) return false;
	if(at!=end) return false;
	used=end+8;return true;
}
typedef NativeString* (__thiscall *LinksFn)(void*,NativeString*,const NativeString*);
extern "C" __declspec(dllexport) NativeString* __fastcall NoticeLinks(void* manager,void*,NativeString* out,const NativeString* input) {
	// Only the two broadcast call sites enter here. General chat keeps its own
	// original ITEML children, click handlers and decoration hooks.
	LinksFn stock=(LinksFn)0x8E1730;
	if(!manager || !input || input->size>1023) return stock(manager,out,input);
	u32 panes=field(manager,0xF4);if(!panes || panes==field(manager,0xF8) || !*(u32*)panes) return stock(manager,out,input);
	void* pane=*(void**)panes;const char* source=chars(*input);if(!source) return stock(manager,out,input);
	char converted[1024],raw[512];int at=0,written=0,n=(int)input->size;bool changed=false;u32 precedingIcon=0;
	while(at<n) {
		int used=0;u32 id=0,identified=1;
		if(itemLink(source+at,n-at,used,id)) {
			int body=used-15;for(int i=0;i<body;++i) raw[i]=source[at+7+i];raw[body]=0;
			NativeString token=borrow(raw,body),name={{0,0,0,0},0,15};
			u8 valid=((u8 (__thiscall *)(void*,NativeString*,NativeString*))0x849A00)(pane,&token,&name);
			if(valid && name.size && name.size<=1023) {
				char digits[10];int count=0;u32 number=id;
				do { digits[count++]=(char)('0'+number%10);number/=10; } while(number);
				int prefix=precedingIcon==id?0:count+4;
				if(written+prefix+(int)name.size>1023) { ((void (__thiscall *)(void*))0x4F08F0)(&name);return stock(manager,out,input); }
				if(prefix) { converted[written++]='^';converted[written++]='i';converted[written++]='[';while(count) converted[written++]=digits[--count];converted[written++]=']'; }
				const char* text=chars(name);for(u32 i=0;i<name.size;++i) converted[written++]=text[i];
				((void (__thiscall *)(void*))0x4F08F0)(&name);at+=used;changed=true;precedingIcon=0;continue;
			}
			((void (__thiscall *)(void*))0x4F08F0)(&name);
		}
		if(tag(source+at,n-at,used,id,identified)) {
			if(written+used>1023) return stock(manager,out,input);
			for(int i=0;i<used;++i) converted[written++]=source[at++];precedingIcon=id;
		} else {
			if(written==1023) return stock(manager,out,input);
			converted[written++]=source[at++];precedingIcon=0;
		}
	}
	if(!changed) return stock(manager,out,input);
	converted[written]=0;NativeString prepared=borrow(converted,written);
	return stock(manager,out,&prepared);
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
