/* HD Job UI resource routing, 2025-07-16 x86. No world hooks or DLL.
 * Equipment: native thiscall consumes a 24-byte std::string by value.
 * Skill Tree: native thiscall consumes const char*. Both preserve ECX.
 * VFS existence uses the same CFile Open/Close/string lifecycle recovered
 * from clan-skins-v11-check.exe. Decisions cache paths, never resource ptrs.
 */
using u32=unsigned int;
using u8=unsigned char;
struct NativeString { union { char local[16]; char* heap; }; u32 size,capacity; };
struct File { u32 vtable; int handle; u32 a,b,c; NativeString name; };
struct Pair { const char* source; const char* preview; const char* stock; };
struct Config { u32 version,count; Pair* pairs; u32 previous_resource,previous_string; };
static_assert(sizeof(NativeString)==24 && sizeof(File)==44 && sizeof(Pair)==12,"2025 ABI");
extern "C" __declspec(dllexport) Config HDJobConfig={1,0,0,0x00A8D4A0,0x00A8D9F0};
static u8 decisions[2048]; // 0 unknown, 1 complete preview, 2 verified stock.
using ResourceLoader=void* (__thiscall *)(void*,const char*);
using StringLoader=void* (__thiscall *)(void*,NativeString);
using StringAssign=void* (__thiscall *)(NativeString*,const char*,u32);
using Destructor=void (__thiscall *)(void*);
using FileOpen=bool (__thiscall *)(File*,const char*,int,int,int);
static const u32 Resource=0x00A8D4A0,StringResource=0x00A8D9F0,Assign=0x004F1940;
static const u32 Open=0x00573750,Close=0x00573060,StringDestroy=0x004F08F0,FileVtable=0x00FD3074;

static u32 length(const char* s,u32 cap=384) { if(!s)return cap; u32 n=0;while(n<cap&&s[n])++n;return n; }
static bool equal(const char* a,const char* b) { for(u32 i=0;i<384;++i){if(a[i]!=b[i])return false;if(!a[i])return true;}return false; }
static bool prefix(const char* a,const char* b) { for(u32 i=0;b[i];++i)if(a[i]!=b[i])return false;return true; }
static bool append(char* out,u32& at,const char* text) {
 for(u32 i=0;text[i];++i){if(at>=383)return false;out[at++]=text[i];}out[at]=0;return true;
}
static bool normalize(const char* in,char* out) {
 if(length(in)>=384)return false;
 for(u32 i=0;;++i){u8 c=(u8)in[i];if(!c){out[i]=0;return true;}
  if(c>=0x81){out[i]=(char)c;++i;if(!in[i])return false;out[i]=in[i];continue;}
  if(c=='\\')c='/';if(c>='A'&&c<='Z')c+=32;out[i]=(char)c;
 }
}
static bool exists(const char* relative,const char* extension) {
 char path[384];u32 at=0;
 if(!append(path,at,"sprite\\")||!append(path,at,relative)||!append(path,at,extension))return false;
 for(u32 i=0;i<at;++i)if(path[i]=='/')path[i]='\\';
 File file;file.vtable=FileVtable;file.handle=-1;file.a=file.b=file.c=0;
 file.name.local[0]=0;file.name.size=0;file.name.capacity=15;
 bool result=((FileOpen)Open)(&file,path,0,1,0);
 ((Destructor)Close)(&file);((Destructor)StringDestroy)(&file.name);
 return result;
}
// Exposed for machine-code verification; outputs a separate complete pair.
extern "C" __declspec(dllexport) int __cdecl HDJobResolve(const char* input,char* output) {
 if(HDJobConfig.version!=1||HDJobConfig.count>2048||!HDJobConfig.pairs)return 0;
 char canonical[384];if(!normalize(input,canonical))return 0;
 char* key=canonical;const char* leading="";
 if(prefix(key,"data/sprite/")){key+=12;leading="data\\sprite\\";}
 else if(prefix(key,"sprite/")){key+=7;leading="sprite\\";}
 else if(prefix(key,"data/")){key+=5;leading="data\\";}
 u32 n=length(key);if(n<5||key[n-4]!='.')return 0;
 const char* ext=key+n-4;if(!equal(ext,".spr")&&!equal(ext,".act"))return 0;
 bool spr=ext[1]=='s';key[n-4]=0;
 for(u32 i=0;i<HDJobConfig.count;++i){
  const Pair& pair=HDJobConfig.pairs[i];if(!equal(key,pair.source))continue;
  u8 choice=decisions[i];
  if(!choice){choice=exists(pair.preview,".spr")&&exists(pair.preview,".act")?1:2;decisions[i]=choice;}
  u32 at=0;if(!append(output,at,leading)||!append(output,at,choice==1?pair.preview:pair.stock)||!append(output,at,spr?".spr":".act"))return 0;
  for(u32 j=0;j<at;++j)if(output[j]=='/')output[j]='\\';return choice;
 }
 return 0;
}
extern "C" __declspec(dllexport) void* __fastcall HDJobResourceHook(void* manager,void*,const char* path) {
 char resolved[384];u32 choice=HDJobResolve(path,resolved);bool matched=choice!=0;
 return ((ResourceLoader)(matched?Resource:HDJobConfig.previous_resource))(manager,matched?resolved:path);
}
extern "C" __declspec(dllexport) void* __fastcall HDJobStringHook(void* manager,void*,NativeString path) {
 char resolved[384];const char* name=path.capacity<16?path.local:path.heap;
 u32 choice=HDJobResolve(name,resolved);bool matched=choice!=0;
 if(matched)((StringAssign)Assign)(&path,resolved,length(resolved));
 // Transfer the by-value string exactly once; the native loader destroys it.
 return ((StringLoader)(matched?StringResource:HDJobConfig.previous_string))(manager,path);
}