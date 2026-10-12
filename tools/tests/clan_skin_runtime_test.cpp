// Executes the actual x86 runtime with native-ABI test endpoints.
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <set>
#define CLAN_SKIN_TEST
#include "../../Scripts/Runtime/ClanBodySkins/runtime.cpp"

static int failures,opens,closes,fileDestroys,liveFiles,lastJob,lastBody,lastSex,lastMode;
static std::set<std::string> available;
static std::string forcedPath;
#define CHECK(c) do { if(!(c)){std::printf("FAIL line %d: %s\n",__LINE__,#c);++failures;} } while(0)
static void init(NativeString* s){s->data.local[0]=0;s->length=0;s->capacity=15;}
static NativeString* __fastcall assignFake(NativeString* s,void*,const char* value,u32 n){
	if(s->capacity>=16)std::free(s->data.heap);
	if(n<16){s->capacity=15;std::memcpy(s->data.local,value,n);s->data.local[n]=0;}
	else{s->capacity=n;s->data.heap=(char*)std::malloc(n+1);std::memcpy(s->data.heap,value,n);s->data.heap[n]=0;}
	s->length=n;return s;
}
static void __fastcall destroyFake(NativeString* s,void*){if(s->capacity>=16)std::free(s->data.heap);init(s);++fileDestroys;}
static NativeString* __fastcall bodyFake(void*,void*,NativeString* out,int ext,int job,int sex,int body,int mode){
	lastJob=job;lastBody=body;lastSex=sex;lastMode=mode;init(out);
	char path[96];std::snprintf(path,sizeof(path),"human\\body\\%d\\job%d.%s",sex,body,ext==0?"spr":ext==1?"act":"pal");
	const std::string s=forcedPath.empty()?path:forcedPath;
	return assignFake(out,0,s.c_str(),(u32)s.size());
}
static NativeString* __fastcall altFake(void* self,void*,NativeString* out,int ext,int race,int job,int sex,int body){
	CHECK(race==77);return bodyFake(self,0,out,ext,job,sex,body,0);
}
static bool __fastcall openFake(NativeFile* f,void*,const char* path,int a,int b,int c){
	CHECK(f->vtable==0x12345678 && f->handle==-1 && f->name.capacity==15);
	CHECK(a==0&&b==1&&c==0);++opens;++liveFiles;
	assignFake(&f->name,0,path,(u32)std::strlen(path));f->handle=123;
	return available.count(path)!=0;
}
static void __fastcall closeFake(NativeFile* f,void*){CHECK(f->handle==123);f->handle=-1;++closes;--liveFiles;}
static int __fastcall mapperFake(void*,void*,int job,int body,int mode){lastJob=job;lastBody=body;lastMode=mode;return body+mode;}
static int __fastcall paletteFake(void*,void*,int job,int color,int body){lastJob=job;lastBody=body;return color;}
static void reset(){
	available.clear();forcedPath.clear();opens=closes=fileDestroys=liveFiles=0;cacheNext=0;cacheLock=0;
	std::memset(cache,0,sizeof(cache));
}
static void pair(int selected,int job,int sex,bool withAct=true){
	char b[160];std::snprintf(b,sizeof(b),"sprite\\clan_skins\\%d\\human\\body\\%d\\job%d.spr",selected,sex,job);available.insert(b);
	if(withAct){std::snprintf(b,sizeof(b),"sprite\\clan_skins\\%d\\human\\body\\%d\\job%d.act",selected,sex,job);available.insert(b);}
}
static std::string invoke(int job,int sex,int body,int ext=0){
	NativeString out;NativeString* result=ClanBodyHook((void*)1,0,&out,ext,job,sex,body,0);
	CHECK(result==&out);std::string value=text(&out);destroyFake(&out,0);return value;
}
int main(){
	ClanSkinApi.version=2;ClanSkinApi.body=(BodyFn)bodyFake;ClanSkinApi.alternateBody=(BodyFn)altFake;
	ClanSkinApi.mapBody=(TripleFn)mapperFake;ClanSkinApi.palette=(TripleFn)paletteFake;
	ClanSkinApi.assign=(AssignFn)assignFake;ClanSkinApi.destroy=(DestroyFn)destroyFake;
	ClanSkinApi.open=(OpenFn)openFake;ClanSkinApi.close=(CloseFn)closeFake;ClanSkinApi.fileVtable=0x12345678;
	reset();CHECK(invoke(1,0,1)=="human\\body\\0\\job1.spr");CHECK(opens==0&&lastBody==1);
	pair(1,1,0);CHECK(invoke(1,0,30001)=="clan_skins\\1\\human\\body\\0\\job1.spr");CHECK(opens==2&&closes==2&&liveFiles==0&&lastJob==1&&lastBody==1);
	CHECK(invoke(1,0,30001,1)=="clan_skins\\1\\human\\body\\0\\job1.act");CHECK(opens==2);
	pair(1,1,1);CHECK(invoke(1,1,30001)=="clan_skins\\1\\human\\body\\1\\job1.spr");CHECK(opens==4);
	pair(2,1,0);CHECK(invoke(1,0,30002)=="clan_skins\\2\\human\\body\\0\\job1.spr");CHECK(opens==6);
	pair(1,2,0);CHECK(invoke(2,0,30001)=="clan_skins\\1\\human\\body\\0\\job2.spr");CHECK(opens==8);
	reset();pair(1,1,0,false);CHECK(invoke(1,0,30001)=="human\\body\\0\\job1.spr");CHECK(opens==2&&closes==2);
	CHECK(invoke(1,0,30001,1)=="human\\body\\0\\job1.act");CHECK(opens==2);
	reset();CHECK(invoke(1,0,30001)=="human\\body\\0\\job1.spr");CHECK(opens==1&&closes==1&&liveFiles==0);
	CHECK(invoke(1,0,30000)=="human\\body\\0\\job30000.spr");CHECK(invoke(1,0,30256)=="human\\body\\0\\job30256.spr");CHECK(opens==1);
	reset();pair(255,1,0);CHECK(invoke(1,0,30255)=="clan_skins\\255\\human\\body\\0\\job1.spr");CHECK(invoke(1,0,30001,2)=="human\\body\\0\\job1.pal");
	reset();pair(1,1,0);cacheLock=1;CHECK(invoke(1,0,30001)=="clan_skins\\1\\human\\body\\0\\job1.spr");CHECK(opens==2);cacheLock=0;
	reset();pair(1,1,0);cache[0].hash=hash("clan_skins\\1\\human\\body\\0\\job1");cache[0].result=0;std::memcpy(cache[0].key,"different-key",sizeof("different-key"));
	CHECK(invoke(1,0,30001)=="clan_skins\\1\\human\\body\\0\\job1.spr");CHECK(opens==2);
	reset();for(int i=1;i<=260;++i){pair(1,i,0);CHECK(invoke(i,0,30001).find("clan_skins\\1\\")==0);}CHECK(opens==520&&closes==520&&liveFiles==0);CHECK(invoke(1,0,30001).find("clan_skins\\1\\")==0);CHECK(opens==522);
	reset();forcedPath=std::string(370,'a')+".spr";CHECK(invoke(1,0,30001)==forcedPath);CHECK(opens==0);
	forcedPath="human\\body\\0\\job1.bmp";CHECK(invoke(1,0,30001)==forcedPath);CHECK(opens==0);
	reset();pair(1,1,0);NativeString out;ClanAlternateBodyHook((void*)1,0,&out,0,77,1,0,30001);CHECK(std::string(text(&out))=="clan_skins\\1\\human\\body\\0\\job1.spr");destroyFake(&out,0);
	CHECK(ClanBodyMapHook((void*)1,0,1,30001,1)==2&&lastBody==1&&lastJob==1);
	CHECK(ClanBodyMapHook((void*)1,0,1,4332,1)==4333&&lastBody==4332);
	CHECK(ClanPaletteHook((void*)1,0,1,7,30001)==7&&lastBody==1&&lastJob==1);
	CHECK(ClanPaletteHook((void*)1,0,1,7,4332)==7&&lastBody==4332);
	CHECK(opens==closes&&liveFiles==0);
#ifdef CLAN_POLICY_PRESENT
	for(unsigned i=0;i<=255;++i){
		CHECK(skin(clan_skin_policy::wire_body(4332,(unsigned short)i,false))==(int)i);
		CHECK(clan_skin_policy::wire_body(4332,(unsigned short)i,true)==4332);
	}
	CHECK(clan_skin_policy::wire_body(1,256,false)==1);
#endif

	reset();pair(1,1,0);ClanSkinApi.version=0;CHECK(invoke(1,0,30001)=="human\\body\\0\\job1.spr"&&lastJob==1&&lastBody==1&&opens==0);ClanSkinApi.version=2;
	std::printf("%s: x86 native-ABI runtime, pair fallback, cache isolation/collision/eviction/reentry, range and path bounds, normalizer, palette and CFile cleanup\n",failures?"FAIL":"PASS");
	return failures?1:0;
}
