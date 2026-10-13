// Native inventory presentation for the profiled 2025-07-16 client.
// Views retain slot identities, never rewrite the session/list or send packets.
typedef unsigned int u32;typedef unsigned char u8;typedef unsigned short u16;
#define EXPORT extern "C" __declspec(dllexport)
extern "C" void* __cdecl memset(void*,int,unsigned int);
extern "C" {int _fltused=0;}
#pragma function(memset)
extern "C" void* __cdecl memset(void* p,int v,unsigned int n){auto* d=static_cast<volatile u8*>(p);while(n--)*d++=static_cast<u8>(v);return p;}
struct Api {
    u32 version,editVtable;
    void (__stdcall *text)(void*,const char*,int,int,int,u32);
    void* (__thiscall *selector)(void*,void*,int,int);
    u32 keysIat;
    const char* paths[37];
    void (__thiscall *cursorFallback)(void*);
};
static_assert(sizeof(Api)==172,"InventoryUI API v1.4");
EXPORT Api InventoryApi={1};
struct Row{u32 index,id,fingerprint;};
struct State {void* window;void* editor;u32 ready,category,scroll,count;int mouseX,mouseY,pressed,action,dragging;char query[64];Row rows[4096];u32 expanded;};
EXPORT State InventoryState={};
static void* textures[37];
static int dragX,dragY,dragW,dragH;
static bool presented,menuOpen;
// Favorites keeps its native category 6; the search menu omits that sidebar-only view.
static const u32 menuCategories[]={0,1,2,3,4,5,7,8,9};
static const char* menuLabels[]={"All Items","Usable","Equipment","Miscelleneous","Card","Ammunition","Costume","Shadow Gear","Pet"};
static u32 dragSlot,dragFingerprint;
static u32 rememberedCategory,rememberedPage;
static bool remembered;
static void selectCategory(void* w,u32 category);
struct PetClass {u32 id;u8 pet;};static PetClass petClasses[1024];
template<typename T>T& at(void* p,int n){return *reinterpret_cast<T*>(static_cast<u8*>(p)+n);}
static int min(int a,int b){return a<b?a:b;}static int max(int a,int b){return a>b?a:b;}
// Read the existing native clamp immediates at runtime, after every selected
// WARP patch. BiggerInventoryWindow's configured limits remain authoritative.
static int maxWidth(){return min(2048,max(280,*reinterpret_cast<int*>(0x955980)));}
static int maxHeight(){return min(2048,max(296,*reinterpret_cast<int*>(0x95598B)));}
static int length(const char* s,int limit=127){int n=0;while(s && s[n] && n<limit)++n;return n;}
static const char* str(void* p,int n){return at<u32>(p,n+20)<16?static_cast<char*>(p)+n:at<const char*>(p,n);}
static void append(char* out,const char* s){int n=length(out);for(int i=0;s && s[i] && n<127;++i)out[n++]=s[i];out[n]=0;}
static void number(char* out,u32 n){char b[12];int i=0;do{b[i++]=static_cast<char>('0'+n%10);n/=10;}while(n);int pos=length(out);while(i && pos<127)out[pos++]=b[--i];out[pos]=0;}
static bool inside(int x,int y,int a,int b,int w,int h){return x>=a && y>=b && x<a+w && y<b+h;}
static void dirty(){if(InventoryState.window)at<int>(InventoryState.window,0x58)=1;}
static u32 id(void* item){const char* s=str(item,0x2C);u32 n=0,len=at<u32>(item,0x3C);if(!s || !len || len>10)return 0;for(u32 i=0;i<len;++i){u32 v=static_cast<u8>(s[i])-'0';if(v>9 || n>(0xFFFFFFFFu-v)/10)return 0;n=n*10+v;}return n;}
static u32 fingerprint(void* p){if(at<u32>(p,0x98)>5)return 0;u32 h=2166136261u;for(int i=0;i<0xF8;++i)h=(h^at<u8>(p,i))*16777619u;return h;}
EXPORT void* __stdcall InventorySlot(u32 index){void* session=(void*)0x15FA3C0;u32 n=at<u32>(session,0x16F4);void* head=at<void*>(session,0x16F0);if(!head || n>4096)return 0;void* p=at<void*>(head,0);for(u32 i=0;i<n && p && p!=head;++i,p=at<void*>(p,0))if(at<u32>(p,12)==index)return static_cast<u8*>(p)+8;return 0;}
static const char* name(void* item){u32 itemId=id(item);void* mgr=*reinterpret_cast<void**>(0x159C088);if(!mgr)return "";void* node=reinterpret_cast<void* (__thiscall *)(void*,const u32*)>(0xA7E780)(static_cast<u8*>(mgr)+8,&itemId);if(!node)return "";int offset=at<u8>(item,0x5C)?0x40:4;u32 len=at<u32>(node,offset+16);return len && len<=512?str(node,offset):"";}
static u8 fold(u8 c){return c>='A' && c<='Z'?static_cast<u8>(c+32):c;}
EXPORT bool __stdcall InventoryMatches(const char* value,const char* query){if(!query || !*query)return true;if(!value)return false;for(int start=0;value[start] && start<512;++start){int j=0;while(j<63 && query[j] && start+j<512 && value[start+j] && fold(value[start+j])==fold(query[j]))++j;if(!query[j])return true;}return false;}
static bool equipment(u32 type){return type==4 || type==5 || type==8 || type==9 || (type>=11 && type<=15);}
static bool costume(void* item){if(at<u32>(item,8)&0x3C00)return true;u32 itemId=id(item);void* mgr=*reinterpret_cast<void**>(0x159C088);if(!mgr)return false;void* node=reinterpret_cast<void* (__thiscall *)(void*,const u32*)>(0xA7E780)(static_cast<u8*>(mgr)+8,&itemId);return node && at<u32>(node,0x84)!=0;}
static bool pet(u32 itemId){PetClass& cached=petClasses[itemId&1023];if(cached.id!=itemId){cached.id=itemId;cached.pet=reinterpret_cast<int (__thiscall *)(void*,u32)>(0xD8EBE0)((void*)0x15FA3C0,itemId)!=0 || reinterpret_cast<u8 (__thiscall *)(void*,u32)>(0xD98320)((void*)0x15FA3C0,itemId)!=0;}return cached.pet!=0;}
static bool category(void* item){u32 t=at<u32>(item,0),c=InventoryState.category;switch(c){case 0:return true;case 1:return t<=2 || t==18;case 2:return equipment(t) && !costume(item) && !(at<u32>(item,8)&0x3F0000) && !pet(id(item));case 3:return (t==3 || t==7) && !pet(id(item));case 4:return t==6;case 5:return t==10 || t==16 || t==17 || t==19;case 6:return at<u8>(item,0x74)!=0;case 7:return costume(item);case 8:return (at<u32>(item,8)&0x3F0000)!=0;case 9:return pet(id(item));default:return false;}}
static int columns(){return max(1,(at<int>(InventoryState.window,0x14)-72)/32);}static int rows(){return max(1,(at<int>(InventoryState.window,0x18)-112)/32);}
static void clamp(){u32 total=(InventoryState.count+columns()-1)/columns(),visible=rows(),limit=total>visible?total-visible:0;if(InventoryState.scroll>limit)InventoryState.scroll=limit;}
static void sync(){auto& s=InventoryState;if(!s.editor)return;const char* raw=reinterpret_cast<const char* (__thiscall *)(void*)>(0x8210A0)(s.editor);int n=length(raw,63);bool same=n==length(s.query,63);for(int i=0;same && i<n;++i)same=raw[i]==s.query[i];if(!same){for(int i=0;i<n;++i)s.query[i]=raw[i];s.query[n]=0;s.scroll=0;s.count=0;presented=false;dirty();}}
EXPORT void __stdcall InventoryRebuild(){auto& s=InventoryState;presented=false;s.count=0;void* session=(void*)0x15FA3C0;u32 count=at<u32>(session,0x16F4);void* head=at<void*>(session,0x16F0);bool nativeFavorites=s.category==6 && s.window && at<void*>(s.window,0xE8);if(nativeFavorites){head=at<void*>(s.window,0xE8);count=at<u32>(s.window,0xEC);}if(!head || count>4096)return;void* p=at<void*>(head,0);for(u32 i=0;i<count && p && p!=head;++i,p=at<void*>(p,0)){void* item=nativeFavorites?InventorySlot(at<u32>(p,12)):static_cast<u8*>(p)+8;if(!item)continue;u32 itemId=id(item),f=fingerprint(item);if(!at<u32>(item,4) || !at<u32>(item,0x10) || !itemId || !f || !category(item))continue;
    // Preserve the stock hidden-item predicate before making an item actionable.
    if(at<u8>(item,0x5D) && reinterpret_cast<int (__thiscall *)(void*,u32)>(0xD8EBE0)(session,itemId))continue;
    if(!InventoryMatches(name(item),s.query))continue;s.rows[s.count++]={at<u32>(item,4),itemId,f};}if(s.window)clamp();}
EXPORT int __stdcall InventoryHit(int x,int y){auto& s=InventoryState;if(menuOpen || !presented || !s.ready || !s.window || at<int>(s.window,0x18)==17)return -1;int c=columns(),r=rows();if(!inside(x,y,56,58,c*32,r*32))return -1;u32 i=s.scroll*c+(y-58)/32*c+(x-56)/32;return i<s.count?static_cast<int>(i):-1;}
static void* itemAt(int x,int y){int n=InventoryHit(x,y);if(n<0)return 0;const Row& r=InventoryState.rows[n];void* p=InventorySlot(r.index);return p && at<u32>(p,0x10) && id(p)==r.id && fingerprint(p)==r.fingerprint?p:0;}
EXPORT void* __fastcall InventorySelect(void* w,void*,void* out,int x,int y){auto& s=InventoryState;if(w!=s.window || !s.ready)return InventoryApi.selector(w,out,x,y);sync();void* p=itemAt(x,y);// Sale/drop restrictions remain owned by the original game-mode handlers.
    if(p)reinterpret_cast<void* (__thiscall *)(void*,void*)>(0x5B72D0)(out,p);else reinterpret_cast<void* (__thiscall *)(void*,int)>(0x6A1A90)(out,0);return out;}
static bool assets(){static const int widths[]={280,32,32,32,32,32,32,32,32,9,17,9,9,32,32,32,32,32,32,32,32,32,245,13,9,12,12,12,12,12,12,25,25,25,13,280,26};static const int heights[]={240,30,30,30,30,30,30,30,30,5,16,9,9,32,30,30,30,30,30,30,30,30,29,13,12,12,12,12,12,12,11,17,17,17,13,208,22};void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return false;for(int i=0;i<37;++i){const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(InventoryApi.paths[i]);if(!path)return false;void* t=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);if(!t || at<int>(t,0x114)!=widths[i] || at<int>(t,0x118)!=heights[i] || !at<void*>(t,0x11C))return false;textures[i]=t;}return true;}
static void child(void* w,int off,int x,int y,bool visible){if(void* p=at<void*>(w,off)){at<int>(p,0x1C)=x;at<int>(p,0x20)=y;at<int>(p,0x28)=visible?1:0;}}
static void layout(void* w){auto& s=InventoryState;int width=at<int>(w,0x14),height=at<int>(w,0x18);if(width<280 || (height!=17 && height<296)){width=max(280,width);height=height==17?17:max(296,height);reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,width,height);}
    // Native settings restore treats unequal current/expanded heights as minimized.
    // Keep the expanded height in step with our custom resize, but retain it at 17px.
    if(height!=17)at<int>(w,0x110)=height;
    const int children[]={0xBC,0xC0,0xF4,0xF8,0xFC,0x114,0x118,0x11C,0x120,0x124,0x128,0x12C};for(int o:children)if(void* p=at<void*>(w,o))at<int>(p,0x28)=0;
    // Native OnCreate also owns an anonymous title label. Hide its children
    // through the real child list so stock controls cannot overlay this view.
    if(void* head=at<void*>(w,0x50)){void* node=at<void*>(head,0);for(int i=0;i<128 && node && node!=head;++i,node=at<void*>(node,0)){void* child=at<void*>(node,8);if(child && child!=s.editor)at<int>(child,0x28)=0;}}
    // Reuse the stock controls, tooltips and command handlers. Only move them.
    bool visible=height!=17,favorites=visible && s.category==6;
    child(w,0x114,83,height-16,visible);child(w,0x11C,113,height-17,visible);
    child(w,0x120,4,height-18,visible);child(w,0x124,132,height-20,favorites);child(w,0x12C,163,height-20,favorites);
    child(w,0x128,30,height-50,favorites);
    if(void* lock=at<void*>(w,0x114))at<int>(lock,0x30)=*reinterpret_cast<u8*>(0x15FFFA0)!=0;
    // Some GRFs omit bt_sort_off*. Seed the original button with the available
    // stock artwork; its native state, tooltip and sort command remain intact.
    if(void* align=at<void*>(w,0x12C)){if(at<int>(align,0x14)<25 || at<int>(align,0x18)<17){for(int i=0;i<3;++i)reinterpret_cast<int (__thiscall *)(void*,const char*,int,int)>(0x82DAC0)(align,InventoryApi.paths[31+i],i,0);reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(align,25,17);}}
    // Keep native list arithmetic nonzero for refreshes; view scrolling is private.
    at<int>(w,0xE0)=max(1,(width-40)/32);at<int>(w,0xDC)=max(1,(height-38)/32);
    if(s.editor){void* e=s.editor;if(at<int>(e,0x14)!=width-95)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(e,width-95,12);at<int>(e,0x1C)=55;at<int>(e,0x20)=31;at<int>(e,0x28)=height==17?0:1;}
}
EXPORT void __fastcall InventoryCreate(void* w,void*,int x,int y){reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x93F100)(w,x,y);auto& s=InventoryState;s.window=w;s.ready=0;menuOpen=false;presented=false;s.editor=0;s.category=s.scroll=s.count=s.expanded=0;s.query[0]=0;s.pressed=s.action=s.dragging=0;s.mouseX=s.mouseY=-1;for(auto& entry:petClasses)entry.id=0;if(!assets())return;
    void* e=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0x11C);if(!e)return;reinterpret_cast<void* (__thiscall *)(void*)>(0x817DA0)(e);at<u32>(e,0)=InventoryApi.editVtable;reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA1B780)(w,e);s.editor=e;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA1CB70)(e,max(280,at<int>(w,0x14))-95,12);at<int>(e,0x88)=63;at<int>(e,0x8C)=1;at<int>(e,0x90)=255;at<int>(e,0x94)=255;at<int>(e,0x98)=255;at<u32>(e,0xA8)=0x797979;s.ready=1;s.expanded=remembered?rememberedPage:0;dragSlot=dragFingerprint=0;selectCategory(w,remembered?rememberedCategory:0);}
EXPORT void __fastcall InventoryProcess(void* w,void*){reinterpret_cast<void (__thiscall *)(void*)>(0x94E520)(w);if(w==InventoryState.window && InventoryState.ready){layout(w);sync();dirty();}}
static void cursorRelease();
EXPORT void* __fastcall InventoryDestroy(void* w,void*,int flags){if(w==InventoryState.window){cursorRelease();menuOpen=false;rememberedCategory=InventoryState.category;rememberedPage=InventoryState.expanded;remembered=true;dragSlot=dragFingerprint=0;if(InventoryState.editor && at<void*>((void*)0x131F4E8,0x1A0)==InventoryState.editor)reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B760)((void*)0x131F4E8,0);void* capture=at<void*>((void*)0x131F4E8,0x19C);if(capture==w || (InventoryState.editor && capture==InventoryState.editor))reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);InventoryState.window=InventoryState.editor=0;InventoryState.ready=InventoryState.count=0;}return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x936700)(w,flags);}
static u32* pixels(){return at<u32*>(at<void*>(InventoryState.window,0x24),0x18);}
static void fill(int x,int y,int w,int h,u32 color){auto* p=pixels();int width=at<int>(InventoryState.window,0x14),height=at<int>(InventoryState.window,0x18);for(int yy=max(y,0);yy<min(y+h,height);++yy)for(int xx=max(x,0);xx<min(x+w,width);++xx)p[yy*width+xx]=color;}
static void slice(int tex,int sx,int sy,int sw,int sh,int dx,int dy,int dw=0,int dh=0){if(!dw)dw=sw;if(!dh)dh=sh;int width=at<int>(InventoryState.window,0x14),height=at<int>(InventoryState.window,0x18),tw=at<int>(textures[tex],0x114);u32* source=at<u32*>(textures[tex],0x11C),*dest=pixels();for(int y=0;y<dh;++y)for(int x=0;x<dw;++x){if(dx+x<0 || dy+y<0 || dx+x>=width || dy+y>=height)continue;u32 c=source[(sy+y*sh/dh)*tw+sx+x*sw/dw],a=c>>24;u32& d=dest[(dy+y)*width+dx+x];if(a==255)d=c;else if(a){u32 rb=(((c&0xFF00FF)*a+(d&0xFF00FF)*(255-a))>>8)&0xFF00FF,g=(((c&0xFF00)*a+(d&0xFF00)*(255-a))>>8)&0xFF00;d=0xFF000000|rb|g;}}}
static void text(const char* t,int x,int y,int width,u32 color=0x777777){InventoryApi.text(InventoryState.window,t,x,y,width,color);}
static void sprite(int texture,int x,int y){reinterpret_cast<void (__thiscall *)(void*,int,int,void*,int)>(0xA1D260)(InventoryState.window,x,y,textures[texture],1);}
static void grouped(char* out,u32 n){char value[128]={};number(value,n);int len=length(value),pos=length(out);for(int i=0;i<len && pos<125;++i){if(i && (len-i)%3==0)out[pos++]=',';out[pos++]=value[i];}out[pos]=0;}
static void rightText(const char* value,int right,int y,u32 color=0x232323){int size=reinterpret_cast<int (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA21C90)(InventoryState.window,value,0,0,11,0,0);text(value,right-size,y,size+2,color);}
static int weightPercent(){int value=*reinterpret_cast<int*>(0x15FBAA0),limit=*reinterpret_cast<int*>(0x15FBA9C);return limit>0?static_cast<int>((static_cast<double>(value)*100.0)/limit):0;}
static void panel(int width,int height){int x=width-139,y=height-52;fill(x,y,133,31,0xFFE8E7F0);text("Zeny",x+6,y+3,35,0x232323);char zeny[128]={},weight[128]={};grouped(zeny,*reinterpret_cast<u32*>(0x15FBA90));grouped(weight,*reinterpret_cast<u32*>(0x15FBAA0));append(weight," / ");grouped(weight,*reinterpret_cast<u32*>(0x15FBA9C));rightText(zeny,width-10,y+3);rightText(weight,width-10,y+17,weightPercent()>=*reinterpret_cast<int*>(0x1602324)?0x0000FF:0x232323);sprite(30,x+6,y+17);}
EXPORT void __fastcall InventoryDraw(void* w,void*){auto& s=InventoryState;if(w!=s.window || !s.ready){reinterpret_cast<void (__thiscall *)(void*)>(0x946DA0)(w);return;}layout(w);sync();InventoryRebuild();int width=at<int>(w,0x14),height=at<int>(w,0x18);if(!at<void*>(w,0x24) || !pixels())return;fill(0,0,width,height,0xFFF5FDFF);slice(0,0,0,17,17,0,0);slice(0,17,0,1,17,17,0,width-34,17);slice(0,263,0,17,17,width-17,0);text("Inventory",18,1,width-56,0x766449);text("-",width-30,1,12);slice(inside(s.mouseX,s.mouseY,width-17,0,17,17)?12:11,0,0,9,9,width-13,4);if(height==17)return;
    slice(0,0,17,34,10,0,17,34,height-38);slice(0,34,17,100,10,34,17,width-35,height-38);slice(0,0,220,280,20,0,height-21,width,21);
    const int icons[]={s.category==0?2:1,3,4,5,s.category==4?7:6};const u32 extra[]={0,5,7,8,9};for(int i=0;i<5;++i){u32 cat=s.expanded?extra[i]:i;int icon=s.expanded && i?14+(i-1)*2+(s.category==cat):icons[i];if(s.category==cat)fill(0,17+i*32,33,32,0xFFFFFFFF);slice(icon,0,0,32,30,0,18+i*32);}
    if(s.expanded)fill(0,177,33,13,0xFFFFFFFF);slice(9,0,0,9,5,12,181);if(s.category==6)fill(0,190,33,32,0xFFFFFFFF);slice(8,0,0,32,30,0,191);
    slice(22,35,11,3,18,52,28);slice(22,132,11,1,18,55,28,width-91,18);slice(22,190,11,18,18,width-36,28);
    int c=columns(),r=rows();for(int row=0;row<r;++row)for(int col=0;col<c;++col){
        int x=56+col*32,y=58+row*32;u32 i=s.scroll*c+row*c+col;
        void* item=i<s.count?InventorySlot(s.rows[i].index):0;
        if(item && fingerprint(item)!=s.rows[i].fingerprint)item=0;
        bool hover=!menuOpen && item && inside(s.mouseX,s.mouseY,x,y,32,32);
        if(hover){
            // selected_bg supplies an open right edge. Mirror its left edge and
            // rounded corners to complete the frame using the same source pixels.
            slice(13,0,0,28,32,x,y);
            for(int edge=0;edge<4;++edge)slice(13,edge,0,1,32,x+31-edge,y);
        }
        // Preserve the frame sides while retaining the shadow beneath selection.
        slice(0,hover?58:57,32,hover?30:32,20,x+(hover?1:0),y+8);
        if(item){
            if(at<u8>(item,0x75))reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x872B30)(w,x,y);
            // Native item art is 24x24; its center matches the shadow at (16,17).
            reinterpret_cast<void (__thiscall *)(void*,int,int,void*,int,int)>(0x8711A0)(w,x+4,y+5,item,0,0);
            int grade=at<short>(item,0x88);if(grade>0 && grade<=5)sprite(24+grade,x+4,y+17);
            if(equipment(at<u32>(item,0)) && at<u8>(item,0x5D))slice(23,0,0,13,13,x+19,y);
            if(at<u32>(item,0x68))slice(24,0,0,9,12,x+23,y+(equipment(at<u32>(item,0)) && at<u8>(item,0x5D)?13:0));
        }
    }
    panel(width,height);
    char cap[128]={};u32 count=*reinterpret_cast<u32*>(0x15FA3C0+0x16F4);count+=reinterpret_cast<u32 (__thiscall *)(void*)>(0xD9AA70)((void*)0x15FA3C0);count+=reinterpret_cast<u32 (__thiscall *)(void*)>(0xD9A960)((void*)0x15FA3C0);number(cap,count);const char* limit=*reinterpret_cast<const char**>(0x947553);if(limit && limit[0]=='/' && limit[1]>='0' && limit[1]<='9')append(cap,limit);else{append(cap,"/");number(cap,*reinterpret_cast<u32*>(0x1602354)+100);}text(cap,27,height-16,54,count>=*reinterpret_cast<u32*>(0x1602354)+100?0x0000FF:0x555555);
    fill(width-11,58,6,r*32,0xFFE0E6F2);u32 total=(s.count+c-1)/c;if(total>static_cast<u32>(r)){int track=r*32,thumb=max(12,track*r/static_cast<int>(total)),top=58+static_cast<int>(s.scroll)*(track-thumb)/(static_cast<int>(total)-r);fill(width-11,top,6,thumb,0xFF9BACD2);}sprite(34,width-15,height-15);
    if(menuOpen){fill(52,46,width-70,218,0xFFA9BFE6);fill(53,47,width-72,216,0xFFFFFFFF);for(int i=0;i<9;++i){if(s.category==menuCategories[i] || inside(s.mouseX,s.mouseY,53,47+i*24,width-72,24))fill(53,47+i*24,width-72,24,0xFFD7E8F9);text(menuLabels[i],59,52+i*24,width-84);}}
    presented=true;
}
#include "../InventoryCartCursor.h"
static int control(int x,int y){auto& s=InventoryState;int w=at<int>(s.window,0x14),h=at<int>(s.window,0x18);if(inside(x,y,w-17,0,17,17))return 20;if(inside(x,y,w-34,0,17,17))return 21;if(h==17)return 0;if(inside(x,y,w-36,28,18,18))return 30;if(menuOpen)return inside(x,y,53,47,w-72,216)?40+(y-47)/24:31;if(inside(x,y,w-15,h-15,15,15))return 25;if(inside(x,y,0,17,33,160))return 1+(y-17)/32;if(inside(x,y,0,177,33,13))return 6;if(inside(x,y,0,190,33,32))return 7;if(inside(x,y,3,h-20,18,19))return 26;if(inside(x,y,77,h-20,26,18))return 27;if(inside(x,y,109,h-20,20,18))return 28;if(s.category==6 && inside(x,y,132,h-20,26,18))return 22;if(s.category==6 && inside(x,y,163,h-20,25,18))return 29;if(inside(x,y,52,28,w-70,18))return 23;if(inside(x,y,w-13,58,13,rows()*32))return 24;return 0;}
EXPORT void __fastcall InventoryCursorDraw(void* mode,void*){auto& s=InventoryState;bool resizing=s.pressed==25;int x=0,y=0;if(s.ready && cursorPosition(s.window,resizing,x,y)){int c=control(x,y);if((resizing || ((c>=1 && c<=7) || c==20 || c==21 || c==25 || c==30 || (c>=40 && c<=48))) && cursorPaint(textures[36]))return;}InventoryApi.cursorFallback(mode);}

static int event(void* w,void* sender,u32 msg,u32 a,u32 b,u32 c,u32 d){return reinterpret_cast<int (__thiscall *)(void*,void*,u32,u32,u32,u32,u32)>(0x955530)(w,sender,msg,a,b,c,d);}
static void selectCategory(void* w,u32 selected){auto& s=InventoryState;menuOpen=false;s.category=selected;s.scroll=0;int native=selected==6?3:(selected==2 || selected>=7)?1:(selected>=3 && selected<=5)?2:0;if(void* tab=at<void*>(w,0x118))at<int>(tab,0x7C)=native;event(w,0,0x16,native,0,0,0);rememberedCategory=s.category;rememberedPage=s.expanded;layout(w);InventoryRebuild();dirty();}
static void blur(){auto& s=InventoryState;if(s.editor && at<void*>((void*)0x131F4E8,0x1A0)==s.editor)reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B760)((void*)0x131F4E8,0);}
struct NativeContext {void* window;void* tab;int category,selected;NativeContext(void* w):window(w),tab(at<void*>(w,0x118)),category(at<int>(w,0x10C)),selected(tab?at<int>(tab,0x7C):0){}~NativeContext(){at<int>(window,0x10C)=category;if(tab)at<int>(tab,0x7C)=selected;}};
static void context(void* w,int x,int y){sync();void* p=itemAt(x,y);if(!p)return;int native=at<u8>(p,0x74)?3:equipment(at<u32>(p,0))?1:(at<u32>(p,0)<=2 || at<u32>(p,0)==18)?0:2;at<int>(w,0x10C)=native;if(void* tab=at<void*>(w,0x118))at<int>(tab,0x7C)=native;}
EXPORT void __fastcall InventoryDown(void* w,void*,int x,int y){auto& s=InventoryState;if(!s.ready || w!=s.window){reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x94AFB0)(w,x,y);return;}sync();s.pressed=control(x,y);if(s.pressed==23){reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B760)((void*)0x131F4E8,s.editor);return;}blur();if(s.pressed){if(s.pressed==24 || s.pressed==25){reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);dragX=x;dragY=y;dragW=at<int>(w,0x14);dragH=at<int>(w,0x18);}if(s.pressed==24){presented=false;u32 total=(s.count+columns()-1)/columns();int limit=max(0,static_cast<int>(total)-rows());s.scroll=static_cast<u32>(max(0,min(limit,(y-58)*limit/max(1,rows()*32-1))));dirty();}return;}NativeContext saved(w);context(w,x,y);void* item=itemAt(x,y);dragSlot=item?at<u32>(item,4):0;dragFingerprint=item?fingerprint(item):0;s.action=1;s.pressed=-1;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x94AFB0)(w,x,y);s.action=0;}
EXPORT void __fastcall InventoryUp(void* w,void*,int x,int y){auto& s=InventoryState;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880BB0)(w,x,y);if(!s.ready || w!=s.window)return;int p=s.pressed;s.pressed=0;if(p<=0 || p!=control(x,y))return;if(p==30 || p==31){menuOpen=p==30?!menuOpen:false;presented=false;dirty();return;}if(p>=40 && p<49){u32 selected=menuCategories[p-40];s.expanded=selected==5 || selected>=7;selectCategory(w,selected);return;}if(p<=7){const u32 extra[]={0,5,7,8,9};if(p==6){s.expanded=!s.expanded;selectCategory(w,0);}else selectCategory(w,p==7?6:s.expanded?extra[p-1]:p-1);}else if(p==20)reinterpret_cast<void (__thiscall *)(void*,int)>(0xA2E770)((void*)0x131F4E8,8);else if(p==21){menuOpen=false;blur();event(w,0,6,0xCA,0,0,0);layout(w);dirty();}else{u32 command=p==22?0x1FB:p==26?0x221:p==27?0xD5:p==28?0x1C8:p==29?0x16C:0;if(command){event(w,0,6,command,0,0,0);layout(w);InventoryRebuild();dirty();}}}
EXPORT void __fastcall InventoryDouble(void* w,void*,int x,int y){NativeContext saved(w);auto& s=InventoryState;if(w==s.window && s.ready && y>=17 && control(x,y))return;if(w==s.window && s.ready)context(w,x,y);s.action=2;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x949FC0)(w,x,y);s.action=0;}
EXPORT void __fastcall InventoryRight(void* w,void*,int x,int y){NativeContext saved(w);auto& s=InventoryState;if(w==s.window && s.ready){if(control(x,y))return;context(w,x,y);}s.action=3;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x94F380)(w,x,y);s.action=0;}
static void tooltip(void* w,const char* label,int x,int y){void* manager=*reinterpret_cast<void**>(0x121333C);if(!manager)return;reinterpret_cast<void (__thiscall *)(void*,int*,int*)>(0xA1EF70)(w,&x,&y);reinterpret_cast<void (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA753D0)(manager,label,x,y,-1,0,1);}
EXPORT void __fastcall InventoryTooltipAnchor(void* w,void*,int* x,int* y){auto& s=InventoryState;if(w==s.window && s.ready && itemAt(s.mouseX,s.mouseY)){*x=56+(s.mouseX-56)/32*32;*y=58+(s.mouseY-58)/32*32-16;}reinterpret_cast<void (__thiscall *)(void*,int*,int*)>(0xA1EF70)(w,x,y);}
EXPORT void __fastcall InventoryMove(void* w,void*,int x,int y){auto& s=InventoryState;s.mouseX=x;s.mouseY=y;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x94D450)(w,x,y);if(w!=s.window || !s.ready || at<int>(w,0x18)==17)return;int width=at<int>(w,0x14),height=at<int>(w,0x18);if(inside(x,y,width-139,height-36,133,17)){char label[128]="Weight ";number(label,static_cast<u32>(max(0,weightPercent())));append(label,"%");tooltip(w,label,width-139,height-53);}else{const char* label=0;int p=control(x,y);static const char* names[]={"Search all items","All usables","Main equipment","ETC items","Cards","Ammunition","Costumes","Shadow equipment","Pet accessories and pet eggs"};if(p>=1 && p<=5)label=names[s.expanded && p>1?p+3:p-1];else if(p==6)label=s.expanded?"Previous categories":"More categories";else if(p==7)label="Favorited items";if(label)tooltip(w,label,33,y-16);}}
// Only adapt the drop target; the original handler owns the favorite packet.
EXPORT void __fastcall InventoryDrop(void* w,void*,int x,int y,void* data){auto& s=InventoryState;auto native=reinterpret_cast<void (__thiscall *)(void*,int,int,void*)>(0x938650);if(w!=s.window || !s.ready || !data || at<u32>(data,0)!=1){native(w,x,y,data);return;}void* tab=at<void*>(w,0x118);void* oldTarget=at<void*>(data,0x84);void* item=InventorySlot(at<u32>(data,4));bool valid=!menuOpen && tab && item && at<u32>(data,4)==dragSlot && fingerprint(item)==dragFingerprint && at<int>(w,0x18)!=17;bool add=inside(x,y,0,190,33,32) || (s.category==6 && inside(x,y,56,58,columns()*32,rows()*32));bool remove=inside(x,y,0,17,33,160);int nativeY=1;
    if(valid && ((add && !at<u8>(item,0x74)) || (remove && at<u8>(item,0x74)))){if(add){int* sizes=at<int*>(tab,0xCC);if(!sizes)valid=false;else for(int i=0;i<3;++i)nativeY+=sizes[i];}at<void*>(data,0x84)=valid?tab:w;}else{valid=false;at<void*>(data,0x84)=w;}
    native(w,1,nativeY,data);at<void*>(data,0x84)=oldTarget;dragSlot=dragFingerprint=0;if(valid && add)selectCategory(w,6);else dirty();}
EXPORT void __fastcall InventoryDrag(void* w,void*,int x,int y){auto& s=InventoryState;if(w!=s.window || !s.ready || s.pressed<=0){reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880E00)(w,x,y);return;}if(s.pressed==24){presented=false;int limit=max(0,static_cast<int>((s.count+columns()-1)/columns())-rows());s.scroll=static_cast<u32>(max(0,min(limit,(y-58)*limit/max(1,rows()*32-1))));dirty();}else if(s.pressed==25){presented=false;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,min(maxWidth(),max(280,dragW+x-dragX)),min(maxHeight(),max(296,dragH+y-dragY)));layout(w);clamp();dirty();}}
EXPORT void __fastcall InventoryWheel(void* w,void*,int delta){auto& s=InventoryState;if(w!=s.window || !s.ready){reinterpret_cast<void (__thiscall *)(void*,int)>(0x9500C0)(w,delta);return;}presented=false;int next=static_cast<int>(s.scroll)+(delta>0?-3:3);s.scroll=static_cast<u32>(max(0,next));clamp();dirty();}
EXPORT int __fastcall InventoryEvent(void* w,void*,void* sender,u32 msg,u32 a,u32 b,u32 c,u32 d){auto& s=InventoryState;if(w==s.window && s.ready && msg==14 && a==7){presented=false;reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,min(maxWidth(),max(280,static_cast<int>(b))),min(maxHeight(),max(296,static_cast<int>(c))));layout(w);clamp();dirty();return 0;}
    // Repair saved expanded windows from versions that left the restore height
    // stale. An explicitly minimized (17px) window must keep its restore height.
    if(w==s.window && s.ready && msg==0x22 && a && at<int>((void*)a,12)>17)at<int>((void*)a,16)=at<int>((void*)a,12);
    if(w==s.window && s.ready && msg==6 && (a==0xCA || a==0xC9))blur();int result=event(w,sender,msg,a,b,c,d);if(w==s.window && s.ready){if(msg==0x22){const u32 map[]={1,2,3,6};u32 old=at<u32>(w,0x10C);selectCategory(w,remembered?rememberedCategory:old<4?map[old]:0);}layout(w);dirty();}return result;}
EXPORT void __fastcall InventoryEditDraw(void* edit,void*){reinterpret_cast<void (__thiscall *)(void*)>(0x824FC0)(edit);if(edit==InventoryState.editor){sync();if(!InventoryState.query[0] && at<void*>((void*)0x131F4E8,0x1A0)!=edit)InventoryApi.text(edit,"Search",1,0,at<int>(edit,0x14)-8,0xAAAAAA);dirty();}}
EXPORT int __fastcall InventoryEditEvent(void* e,void*,void* sender,u32 msg,u32 a,u32 b,u32 c,u32 d){if(e==InventoryState.editor && msg==0){menuOpen=false;presented=false;blur();dirty();return 1;}return reinterpret_cast<int (__thiscall *)(void*,void*,u32,u32,u32,u32,u32)>(0x82C4E0)(e,sender,msg,a,b,c,d);}
