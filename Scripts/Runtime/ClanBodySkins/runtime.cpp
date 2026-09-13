/* Freestanding x86 payload, statically injected by ClanBodySkins.qjs.
 * No DLL is loaded by Ragexe. Native strings/files retain their own ownership.
 * Native ABI/profile: 2025-07-16 Ragexe, MSVC x86, 24-byte std::string.
 */
typedef unsigned int u32;
typedef unsigned char u8;
#ifndef CLAN_SKIN_TEST
extern "C" void* __cdecl memcpy(void*,const void*,u32);
#pragma function(memcpy)
extern "C" void* __cdecl memcpy(void* destination,const void* source,u32 count) {
	volatile u8* d=(volatile u8*)destination;const u8* s=(const u8*)source;
	for(u32 i=0;i<count;++i)d[i]=s[i];return destination;
}
#endif
extern "C" long _InterlockedCompareExchange(volatile long*,long,long);
extern "C" long _InterlockedExchange(volatile long*,long);
#pragma intrinsic(_InterlockedCompareExchange)
#pragma intrinsic(_InterlockedExchange)

struct NativeString { union { char local[16]; char* heap; } data; u32 length,capacity; };
struct NativeFile { u32 vtable; int handle; u32 archive,position,size; NativeString name; };
static_assert(sizeof(NativeString)==24,"x86 native string ABI");
static_assert(sizeof(NativeFile)==44,"native CFile ABI");
typedef NativeString* (__thiscall *BodyFn)(void*,NativeString*,int,int,int,int,int);
typedef int (__thiscall *TripleFn)(void*,int,int,int);
typedef NativeString* (__thiscall *AssignFn)(NativeString*,const char*,u32);
typedef void (__thiscall *DestroyFn)(NativeString*);
typedef bool (__thiscall *OpenFn)(NativeFile*,const char*,int,int,int);
typedef void (__thiscall *CloseFn)(NativeFile*);

struct Api {
	u32 version;
	BodyFn body,alternateBody;
	TripleFn mapBody,palette;
	AssignFn assign;
	DestroyFn destroy;
	OpenFn open;
	CloseFn close;
	u32 fileVtable;
};
static_assert(sizeof(Api)==40,"clan body-only API v2");
extern "C" __declspec(dllexport) Api ClanSkinApi={};

enum { PATH_CAPACITY=384,CACHE_COUNT=128,TOKEN_BASE=30000,MAX_SKIN=255 };
struct CacheEntry { u32 hash; int result; char key[PATH_CAPACITY]; };
static CacheEntry cache[CACHE_COUNT];
static volatile long cacheLock;
static u32 cacheNext;

static int skin(int body) { return body>TOKEN_BASE && body<=TOKEN_BASE+MAX_SKIN ? body-TOKEN_BASE:0; }
static u32 length(const char* s,u32 limit) { u32 n=0;while(n<limit&&s[n])++n;return n; }
static void copy(char* d,const char* s,u32 n) { for(u32 i=0;i<n;++i)d[i]=s[i]; }
static bool equal(const char* a,const char* b) { for(u32 i=0;i<PATH_CAPACITY;++i){if(a[i]!=b[i])return false;if(!a[i])return true;}return false; }
static u32 hash(const char* s) { u32 h=2166136261u;for(u32 i=0;s[i];++i)h=(h^(u8)s[i])*16777619u;return h?h:1; }
static const char* text(const NativeString* s) { return s->capacity<16?s->data.local:s->data.heap; }

static bool exists(const char* path) {
	// Native body names are relative to sprite/. CFile needs the full path.
	char filename[PATH_CAPACITY+8];copy(filename,"sprite\\",7);
	u32 n=length(path,PATH_CAPACITY);if(n>=PATH_CAPACITY)return false;
	copy(filename+7,path,n+1);
	NativeFile file;
	file.vtable=ClanSkinApi.fileVtable;file.handle=-1;file.archive=0;file.position=0;file.size=0;
	file.name.data.local[0]=0;file.name.length=0;file.name.capacity=15;
	const bool found=ClanSkinApi.open(&file,filename,0,1,0);
	ClanSkinApi.close(&file);
	// Close releases the OS/archive handle, not the embedded filename string.
	ClanSkinApi.destroy(&file.name);
	return found;
}

static bool pairExists(char* path,u32 n) {
	// Cache both outcomes by the complete stem, not job/skin IDs or a hash alone.
	// The native resource cache subsequently receives the distinct full path.
	char extension[4];copy(extension,path+n-3,4);path[n-4]=0;
	u32 h=hash(path);int cached=-1;
	if(_InterlockedCompareExchange(&cacheLock,1,0)==0){
		for(u32 i=0;i<CACHE_COUNT;++i)if(cache[i].hash==h&&equal(cache[i].key,path)){cached=cache[i].result;break;}
		_InterlockedExchange(&cacheLock,0);
	}
	path[n-4]='.';
	if(cached>=0)return cached!=0;
	copy(path+n-3,"spr",4);const bool spr=exists(path);
	copy(path+n-3,"act",4);const bool act=spr&&exists(path);
	copy(path+n-3,extension,4);
	const bool found=spr&&act;
	path[n-4]=0;
	if(_InterlockedCompareExchange(&cacheLock,1,0)==0){
		CacheEntry* entry=&cache[cacheNext++%CACHE_COUNT];
		copy(entry->key,path,n-3);entry->hash=h;entry->result=found?1:0;
		_InterlockedExchange(&cacheLock,0);
	}
	path[n-4]='.';
	return found;
}

static NativeString* route(NativeString* out,int selected,int extension) {
	if(!selected || extension<0 || extension>1 || ClanSkinApi.version!=2)return out;
	const char* source=text(out);u32 n=out->length;
	if(!source || n<5 || n>=PATH_CAPACITY-20 || length(source,n+1)!=n)return out;
	// Limit to genuine native SPR/ACT filenames. Never redirect other resources.
	if(source[n-4]!='.' || !((source[n-3]=='s'&&source[n-2]=='p'&&source[n-1]=='r')||(source[n-3]=='a'&&source[n-2]=='c'&&source[n-1]=='t')))return out;
	char candidate[PATH_CAPACITY];const char prefix[]="clan_skins\\";
	u32 at=sizeof(prefix)-1;copy(candidate,prefix,at);
	if(selected>=100)candidate[at++]=(char)('0'+selected/100);
	if(selected>=10)candidate[at++]=(char)('0'+(selected/10)%10);
	candidate[at++]=(char)('0'+selected%10);candidate[at++]='\\';
	copy(candidate+at,source,n+1);n+=at;
	if(pairExists(candidate,n))ClanSkinApi.assign(out,candidate,n);
	return out;
}

extern "C" __declspec(dllexport) NativeString* __fastcall ClanBodyHook(void* self,void*,NativeString* out,int extension,int job,int sex,int body,int mode) {
	const int selected=skin(body);
	ClanSkinApi.body(self,out,extension,job,sex,selected?job:body,mode);
	return route(out,selected,extension);
}
extern "C" __declspec(dllexport) NativeString* __fastcall ClanAlternateBodyHook(void* self,void*,NativeString* out,int extension,int raceJob,int job,int sex,int body) {
	const int selected=skin(body);
	ClanSkinApi.alternateBody(self,out,extension,raceJob,job,sex,selected?job:body);
	return route(out,selected,extension);
}
extern "C" __declspec(dllexport) int __fastcall ClanBodyMapHook(void* self,void*,int job,int body,int normalized) {
	return ClanSkinApi.mapBody(self,job,skin(body)?job:body,normalized);
}
extern "C" __declspec(dllexport) int __fastcall ClanPaletteHook(void* self,void*,int job,int color,int body) {
	return ClanSkinApi.palette(self,job,color,skin(body)?job:body);
}
