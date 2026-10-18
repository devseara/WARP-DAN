// Isolated 2025-07-16 storage skin. Native storage lifecycle, CItem ownership,
// amount dialogs, drag payloads and transactions remain in the client.
typedef unsigned int u32;
typedef unsigned char u8;
#define EXPORT extern "C" __declspec(dllexport)
extern "C" void* __cdecl memset(void*,int,unsigned int);
#pragma function(memset)
extern "C" void* __cdecl memset(void* p,int value,unsigned int n){auto* d=static_cast<volatile u8*>(p);while(n--)*d++=static_cast<u8>(value);return p;}
struct Api {
    u32 version,vtable,editVtable;
    void (__stdcall *text)(void*,const char*,int,int,int,u32);
    void (__thiscall *png)(void*,int,int,void*,int);
    const char* (__stdcall *name)(u32);
    const char* paths[31];
    void (__thiscall *cursorFallback)(void*);
};
static_assert(sizeof(Api)==152,"StorageUI API v1.1");
EXPORT Api StorageApi={1};
struct Visible {u32 slot,id,fingerprint;};
struct State {void* window;void* editor;int category,block,sort,scroll,count,hover,pressed,dragging,grab,ready;char query[128];Visible visible[126];int visibleCount;int rows,resizeY,resizeRows,menu,locked,closing,mouseX,mouseY;};
EXPORT State StorageState={};
static void* textures[31];
static void* view[10000];
struct PetClass {u32 id;int pet;};
static PetClass petClasses[1024];
template<typename T>T& at(void* p,int o){return *reinterpret_cast<T*>(static_cast<u8*>(p)+o);}
static int min(int a,int b){return a<b?a:b;}
static int max(int a,int b){return a>b?a:b;}
static bool inside(int x,int y,int bx,int by,int w,int h){return x>=bx && y>=by && x<bx+w && y<by+h;}
static int length(const char* s){int n=0;while(s && s[n] && n<127)++n;return n;}
static bool equal(const char* a,const char* b){int i=0;for(;i<127 && a[i] && a[i]==b[i];++i){}return a[i]==b[i];}
static void textCopy(char* d,const char* s){int i=0;for(;s && s[i] && i<127;++i)d[i]=s[i];d[i]=0;}
static void number(char* d,u32 v){char t[20];int n=0;do{t[n++]=static_cast<char>('0'+v%10);v/=10;}while(v);while(n)*d++=t[--n];*d=0;}
static u32 itemId(void* item){u32 n=0,len=at<u32>(item,0x3C);if(!len || len>10)return 0;const char* s=at<u32>(item,0x40)<16?static_cast<char*>(item)+0x2C:at<const char*>(item,0x2C);if(!s)return 0;for(u32 i=0;i<len;++i){u32 d=static_cast<u8>(s[i])-'0';if(d>9 || n>(0xFFFFFFFFu-d)/10)return 0;n=n*10+d;}return n;}
static const char* itemName(void* item,u32 id){void* manager=*reinterpret_cast<void**>(0x159C088);void* info=manager?reinterpret_cast<void* (__thiscall *)(void*,u32*)>(0xA7E780)(static_cast<u8*>(manager)+8,&id):0;if(!info)return StorageApi.name(id);int off=at<u8>(item,0x5C)?0x40:4;return at<u32>(info,off+20)<16?static_cast<char*>(info)+off:at<const char*>(info,off);}
static u32 fingerprint(void* item){u32 v=2166136261u;auto* p=static_cast<u8*>(item);for(int i=0;i<0xF8;++i)v=(v^p[i])*16777619u;return v;}
static int petClass(u32 id){PetClass& entry=petClasses[id&1023];if(entry.id!=id){entry.pet=reinterpret_cast<int (__thiscall *)(void*,u32)>(0xD8EBE0)((void*)0x15FA3C0,id) || reinterpret_cast<u8 (__thiscall *)(void*,u32)>(0xD98320)((void*)0x15FA3C0,id);entry.id=id;}return entry.pet;}
static void dirty(){if(StorageState.window)at<int>(StorageState.window,0x58)=1;}
static bool own(void* w){return w && w==StorageState.window && at<u32>(w,0)==StorageApi.vtable && StorageState.ready;}
static int cols(){return StorageState.block?7:1;}
static int rows(){return max(10,min(18,StorageState.rows));}
static int height(){return 125+32*rows();}
static int footer(){return height()-56;}
static int maxScroll(){return max(0,(StorageState.count+cols()-1)/cols()-rows());}
EXPORT int __stdcall StorageContains(const char* hay,const char* needle){
    if(!needle || !*needle)return 1;if(!hay)return 0;
    for(int i=0;hay[i] && i<1024;++i){int j=0;for(;needle[j] && j<127;++j){u8 a=static_cast<u8>(hay[i+j]),b=static_cast<u8>(needle[j]);if(!a)break;if(a>='A' && a<='Z')a+=32;if(b>='A' && b<='Z')b+=32;if(a!=b)break;}if(!needle[j])return 1;}return 0;
}
// These are the native CItem kinds, not rAthena's server item-type numbers.
// Fine equipment subcategories are resolved independently of display names.
EXPORT int __stdcall StorageCategory(void* item,u32 id,int category){
    if(category==0)return 1;int type=at<int>(item,0);
    void* manager=*reinterpret_cast<void**>(0x159C088);
    void* info=manager?reinterpret_cast<void* (__thiscall *)(void*,u32*)>(0xA7E780)(static_cast<u8*>(manager)+8,&id):0;
    int costume=(info?at<int>(info,0x84):0) || (at<u32>(item,8)&0x3C00);
    int shadow=(at<u32>(item,8)&0x3F0000)!=0;
    int pet=petClass(id);
    if(category==7)return costume!=0;
    if(category==8)return shadow;
    if(category==9)return pet;
    if(costume || shadow || pet)return 0;
    if(category==1)return type==0 || type==1 || type==2;
    // Base native kinds are 5 = weapon, 4 = armor (including headgear).
    if(category==2)return type==5 || (type>=11 && type<=14);
    if(category==3)return type==4 || type==8 || type==9 || type==15;
    if(category==4)return type==3 || type==7;
    if(category==5)return type==6;
    if(category==6)return type==10 || type==16 || type==17 || type==19;
    if(category==11)return type==18;
    return 0;
}
static void sync(){
    if(!StorageState.editor)return;
    const char* raw=reinterpret_cast<const char* (__thiscall *)(void*)>(0x8210A0)(StorageState.editor);
    if(!raw)raw="";if(!equal(raw,StorageState.query)){textCopy(StorageState.query,raw);StorageState.scroll=StorageState.visibleCount=0;dirty();}
}
EXPORT int __stdcall StorageBuildView(){
    StorageState.count=0;void* session=(void*)0x15FA3C0;void* head=at<void*>(session,0x1718);u32 count=at<u32>(session,0x171C);
    if(!head || count>10000)return 0;void* node=at<void*>(head,0);
    for(u32 i=0;i<count && node && node!=head;++i,node=at<void*>(node,0)){
        void* item=static_cast<u8*>(node)+8;u32 id=itemId(item);if(!id || !at<u32>(item,4) || !at<u32>(item,0x10))continue;
        if(!StorageCategory(item,id,StorageState.category))continue;
        if(StorageState.query[0] && !StorageContains(itemName(item,id),StorageState.query))continue;
        // Match the stock visibility predicate for unavailable/unidentified items.
        if(at<u8>(item,0x5D) && reinterpret_cast<int (__thiscall *)(void*,u32)>(0xD8EBE0)(session,id))continue;
        view[StorageState.count++]=item;
    }
    // Stable insertion sort preserves slot identity for equal refine levels.
    if(StorageState.sort)for(int i=1;i<StorageState.count;++i){void* item=view[i];u32 refine=at<u32>(item,0x60);int j=i;while(j>0 && (StorageState.sort==1?at<u32>(view[j-1],0x60)<refine:at<u32>(view[j-1],0x60)>refine)){view[j]=view[j-1];--j;}view[j]=item;}
    StorageState.scroll=min(max(0,StorageState.scroll),maxScroll());return StorageState.count;
}
EXPORT int __stdcall StorageItemHit(int x,int y){
    if(StorageState.menu || !inside(x,y,57,57,StorageState.block?224:230,32*rows()))return -1;
    return (y-57)/32*cols()+(StorageState.block?(x-57)/32:0);
}
EXPORT void* __fastcall StorageSelect(void* w,void*,void* out,int x,int y){
    if(!own(w))return reinterpret_cast<void* (__thiscall *)(void*,void*,int,int)>(0x939CF0)(w,out,x,y);
    sync();int n=StorageItemHit(x,y);void* found=0;
    if(at<u8>(w,0x190) && n>=0 && n<StorageState.visibleCount){
        const Visible& expected=StorageState.visible[n];void* session=(void*)0x15FA3C0;void* head=at<void*>(session,0x1718);u32 count=at<u32>(session,0x171C);
        if(head && count<=10000){void* node=at<void*>(head,0);for(u32 i=0;i<count && node && node!=head;++i,node=at<void*>(node,0)){void* item=static_cast<u8*>(node)+8;
            if(at<u32>(item,4)==expected.slot && itemId(item)==expected.id && fingerprint(item)==expected.fingerprint){found=item;break;}}}
    }
    if(found)reinterpret_cast<void (__thiscall *)(void*,void*)>(0x5B72D0)(out,found);
    else reinterpret_cast<void (__thiscall *)(void*,int)>(0x6A1A90)(out,0);
    return out;
}
static void layout(void* w){
    if(at<int>(w,0x14)!=312 || at<int>(w,0x18)!=height())reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(w,312,height());
    for(int off=0xBC;off<=0xD0;off+=4)if(void* c=at<void*>(w,off))at<int>(c,0x28)=0;
    if(void* c=at<void*>(w,0xF4))at<int>(c,0x28)=0;
    for(int off=0x100;off<=0x11C;off+=4)if(void* c=at<void*>(w,off))at<int>(c,0x28)=0;
    if(void* c=at<void*>(w,0x168))at<int>(c,0x28)=0;
    if(void* c=at<void*>(w,0x15C))at<int>(c,0x28)=0;
    void* e=at<void*>(w,0xF0);if(!e)return;StorageState.editor=e;at<u32>(e,0)=StorageApi.editVtable;
    // Include the unindexed stock title button: hidden children must never
    // receive category clicks or enqueue their old close/search commands.
    void* head=at<void*>(w,0x50);if(head){void* node=at<void*>(head,0);for(int i=0;i<64 && node && node!=head;++i,node=at<void*>(node,0)){void* child=at<void*>(node,8);if(child && child!=e)at<int>(child,0x28)=0;}}
    at<int>(e,0x88)=127;at<int>(e,0x8C)=1;at<int>(e,0x90)=255;at<int>(e,0x94)=255;at<int>(e,0x98)=255;at<u32>(e,0xA8)=0x797979;
    if(at<int>(e,0x14)!=151 || at<int>(e,0x18)!=12)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA245C0)(e,151,12);
    at<int>(e,0x1C)=86;at<int>(e,0x20)=30;at<int>(e,0x28)=1;
}
static bool assets(){
    static const int widths[]={312,33,33,33,33,33,33,33,33,33,33,33,33,262,43,43,81,81,81,44,44,44,9,9,17,312,26,13,11,14,32};
    static const int heights[]={442,396,396,396,396,396,396,396,396,396,396,396,396,37,12,12,9,9,9,18,18,18,9,9,16,442,22,13,14,11,32};
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return false;
    for(int i=0;i<31;++i){const char* path=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)(StorageApi.paths[i]);if(!path)return false;void* t=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,path);
        if(!t || at<int>(t,0x114)!=widths[i] || at<int>(t,0x118)!=heights[i] || !at<void*>(t,0x11C))return false;textures[i]=t;}
    return true;
}
static void blur(){if(StorageState.editor && at<void*>((void*)0x131F4E8,0x1A0)==StorageState.editor)reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B760)((void*)0x131F4E8,0);}
static void release(){if(at<void*>((void*)0x131F4E8,0x19C)==StorageState.window)reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);}
static void cursorRelease();
EXPORT void* __fastcall StorageConstruct(void* w,void*){
    reinterpret_cast<void* (__thiscall *)(void*)>(0x934AE0)(w);
    if(!assets())return w;
    cursorRelease();memset(&StorageState,0,sizeof(StorageState));memset(petClasses,0,sizeof(petClasses));StorageState.window=w;StorageState.rows=10;StorageState.mouseX=StorageState.mouseY=-1;StorageState.ready=1;at<u32>(w,0)=StorageApi.vtable;return w;
}
EXPORT void __fastcall StorageCreate(void* w,void*,int x,int y){reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x93DC60)(w,x,y);layout(w);StorageState.ready=2;dirty();}
static int nativeEvent(void* w,void* sender,u32 m,u32 a,u32 b,u32 c,u32 d){return reinterpret_cast<int (__thiscall *)(void*,void*,u32,u32,u32,u32,u32)>(0x9544F0)(w,sender,m,a,b,c,d);}
static void cancelTransfer(){
    void* mode=reinterpret_cast<void* (__thiscall *)(void*)>(0xA75340)((void*)0x1213338);
    if(mode)reinterpret_cast<void (__thiscall *)(void*,u32,u32,u32,u32,u32)>(at<u32*>(mode,0)[6])(mode,0x12,0,0,0,0);
}
EXPORT int __fastcall StorageEvent(void* w,void*,void* sender,u32 m,u32 a,u32 b,u32 c,u32 d){
    if(own(w)){
        if(m==0x26 && (StorageState.locked || StorageState.closing)){cancelTransfer();return 0;}
        if(m==6 && sender && sender!=w && at<void*>(sender,0x10)==w && !at<int>(sender,0x28))return 0;
        if(m==0xE){if(a==7){StorageState.rows=max(10,min(18,(static_cast<int>(c)-125)/32));layout(w);StorageState.scroll=min(StorageState.scroll,maxScroll());StorageState.visibleCount=0;}dirty();return 0;}
        if(m==0x16 || (m==6 && (a==0x16D || a==0x85))){sync();dirty();return 0;}
    }
    int result=nativeEvent(w,sender,m,a,b,c,d);
    if(own(w) && StorageState.ready==2){layout(w);StorageState.visibleCount=0;dirty();}return result;
}
EXPORT int __fastcall StorageEditEvent(void* e,void*,void* sender,u32 m,u32 a,u32 b,u32 c,u32 d){
    if(e==StorageState.editor && m==0){sync();StorageState.menu=0;blur();dirty();return 1;}
    return reinterpret_cast<int (__thiscall *)(void*,void*,u32,u32,u32,u32,u32)>(0x82C4E0)(e,sender,m,a,b,c,d);
}
EXPORT void __fastcall StorageEditDraw(void* e,void*){
    // UIBalloonEditCtrl draws the native text/caret without the stock edit box.
    reinterpret_cast<void (__thiscall *)(void*)>(0x824FC0)(e);
    if(e==StorageState.editor){sync();if(!StorageState.query[0] && at<void*>((void*)0x131F4E8,0x1A0)!=e)StorageApi.text(e,"Search",1,0,142,0xAAAAAA);dirty();}
}
EXPORT void __fastcall StorageProcess(void* w,void*){if(own(w) && StorageState.ready==2){sync();dirty();}}
static u32* pixels(){return at<u32*>(at<void*>(StorageState.window,0x24),0x18);}
static void fill(int x,int y,int width,int h,u32 color){u32* p=pixels();for(int yy=max(0,y);yy<min(height(),y+h);++yy)for(int xx=max(0,x);xx<min(312,x+width);++xx)p[yy*312+xx]=color;}
static void slice(int tex,int sx,int sy,int width,int h,int dx,int dy){
    int tw=at<int>(textures[tex],0x114);u32* source=at<u32*>(textures[tex],0x11C),*dest=pixels();
    for(int y=0;y<h;++y)for(int x=0;x<width;++x){if(dx+x<0 || dy+y<0 || dx+x>=312 || dy+y>=height())continue;
        u32 c=source[(sy+y)*tw+sx+x],a=c>>24;u32& d=dest[(dy+y)*312+dx+x];
        if(a==255)d=c;else if(a){u32 rb=(((c&0xFF00FF)*a+(d&0xFF00FF)*(255-a))>>8)&0xFF00FF,g=(((c&0xFF00)*a+(d&0xFF00)*(255-a))>>8)&0xFF00;d=0xFF000000|rb|g;}}
}
static void png(void* w,int i,int x,int y){StorageApi.png(w,x,y,textures[i],0);}
static void sprite(void* w,int i,int x,int y){reinterpret_cast<void (__thiscall *)(void*,int,int,void*,int)>(0xA1D260)(w,x,y,textures[i],1);}
static void text(void* w,const char* s,int x,int y,int width,u32 color=0x797979){StorageApi.text(w,s,x,y,width,color);}
#include "../ItemSlotQuantity.h"
static int thumbSize(){return max(20,(rows()*32-24)*rows()/max(rows(),(StorageState.count+cols()-1)/cols()));}
static int thumbTravel(){return rows()*32-24-thumbSize();}
static int thumbTop(){return 69+(maxScroll()?StorageState.scroll*thumbTravel()/maxScroll():0);}
static const char* categories[]={"All Items","Usable","Weapon","Armor","Miscelleneous","Card","Ammunition","Costume","Shadow Gear","Pet","Cash"};
EXPORT int __stdcall StorageHit(int x,int y){
    if(!StorageState.ready)return 0;
    if(inside(x,y,296,0,16,17))return 2;
    if(inside(x,y,239,28,18,18))return 9;
    if(StorageState.menu)return inside(x,y,84,46,173,242)?30+(y-46)/22:8;
    if(inside(x,y,297,height()-15,15,15))return 23;
    if(inside(x,y,251,height()-24,44,18))return 1;
    if(inside(x,y,110,height()-27,22,22))return 24;
    if(inside(x,y,0,17,33,336)){int row=min(10,max(0,(y-23)/30));return 10+row+(row==10?1:0);}
    if(inside(x,y,8,footer()+6,65,20))return 3;
    if(inside(x,y,204,footer()+7,90,20))return 4;
    if(inside(x,y,84,28,155,18))return 25;
    if(maxScroll()){
        if(inside(x,y,295,57,13,12))return 5;
        if(inside(x,y,295,57+rows()*32-12,13,12))return 6;
        if(inside(x,y,295,69,13,rows()*32-24))return 7;
    }return 0;
}
EXPORT void __fastcall StorageDraw(void* w,void*){
    layout(w);sync();StorageBuildView();reinterpret_cast<void (__thiscall *)(void*,int)>(0xA1CB30)(w,0);
    if(!at<void*>(w,0x24) || !pixels())return;
    int bg=StorageState.block?25:0;fill(0,0,312,height(),0xFFF7FBFE);slice(bg,0,0,312,57,0,0);
    // Copy rows, never scale the artwork or its circle shadows.
    for(int row=0;row<rows();++row)slice(bg,0,57,312,32,0,57+row*32);
    for(int y=57+rows()*32;y<footer();++y)slice(bg,0,409+(y-57-rows()*32)%4,312,1,0,y);
    slice(StorageState.category+1,0,0,33,306,0,17);slice(StorageState.category+1,0,336,33,30,0,323);
    for(int y=353;y<footer();++y)slice(bg,0,408,33,1,0,y);
    png(w,13,33,17);text(w,"Storage",16,2,245);png(w,StorageState.hover==2?23:22,299,4);
    slice(bg,0,413,312,1,0,footer());
    for(int y=footer()+1;y<height()-5;++y)slice(bg,0,414+(y-footer())%3,312,1,0,y);
    slice(bg,0,437,312,5,0,height()-5);
    StorageState.visibleCount=0;int start=StorageState.scroll*cols();
    if(at<u8>(w,0x190))for(int n=0;n<rows()*cols() && start+n<StorageState.count;++n){int x=57+n%cols()*32,y=57+n/cols()*32;void* item=view[start+n];
        if(!StorageState.menu && inside(StorageState.mouseX,StorageState.mouseY,x,y,StorageState.block?32:230,32)){
            slice(30,0,0,28,32,x,y);for(int edge=0;edge<4;++edge)slice(30,edge,0,1,32,x+31-edge,y);
            slice(bg,58,65,30,20,x+1,y+8);
        }
        // Center the native 24px icon and keep its count inside the 32px cell.
        drawSlotItem(w,x+4,y+4,item);
        if(!StorageState.block)reinterpret_cast<void (__thiscall *)(void*,int,int,int,void*,int,int,int)>(0x897860)(w,96,y+12,191,item,0,0,12);
        StorageState.visible[n]={at<u32>(item,4),itemId(item),fingerprint(item)};StorageState.visibleCount=n+1;
    }else text(w,"Waiting for storage...",81,193,208);
    if(maxScroll()){
        fill(297,57,9,rows()*32,0xFFE1E6F0);fill(298,thumbTop(),7,thumbSize(),0xFF9BACD2);
        text(w,"^",298,57,8);text(w,"v",298,57+rows()*32-12,8);
    }
    png(w,StorageState.block?15:14,8,footer()+10);png(w,16+StorageState.sort,208,footer()+12);
    sprite(w,28,8,height()-23);char counter[128];number(counter,at<u32>(w,0x188));int pos=length(counter);counter[pos++]=' ';counter[pos++]='/';counter[pos++]=' ';number(counter+pos,at<u32>(w,0x18C));text(w,counter,24,height()-20,85);
    if(StorageState.locked)png(w,24,112,height()-25);else sprite(w,29,113,height()-23);
    png(w,StorageState.pressed==1?21:StorageState.hover==1?20:19,251,height()-24);sprite(w,27,297,height()-15);
    if(StorageState.menu){
        fill(84,46,173,242,0xFFA9BFE6);fill(85,47,171,240,0xFFFFFFFF);
        for(int i=0;i<11;++i){int cat=i+(i==10?1:0);if(StorageState.category==cat || StorageState.hover==30+i)fill(85,47+i*22,171,21,0xFFD7E8F9);text(w,categories[i],91,51+i*22,159);}
    }
}
#include "../InventoryCartCursor.h"
EXPORT void __fastcall StorageCursorDraw(void* mode,void*){
    auto& s=StorageState;int x=0,y=0;bool resizing=s.pressed==23;
    if(s.ready==2 && !s.closing && cursorPosition(s.window,resizing,x,y)){
        int id=StorageHit(x,y);if((resizing || (id && id!=8 && id!=25)) && cursorPaint(textures[26]))return;
    }StorageApi.cursorFallback(mode);
}
static void scroll(int delta){StorageState.scroll=min(max(0,StorageState.scroll+delta),maxScroll());StorageState.visibleCount=0;dirty();}
static void action(void* w,int id){
    auto& s=StorageState;
    if(id==1 || id==2){if(s.closing)return;s.closing=1;s.menu=0;blur();release();nativeEvent(w,0,6,0xC9,0,0,0);return;}
    if(id>=10 && id<22){s.category=id-10;s.menu=0;s.scroll=s.visibleCount=0;}
    if(id>=30 && id<41){s.category=id-30+(id==40?1:0);s.menu=0;s.scroll=s.visibleCount=0;}
    if(id==3){s.block=!s.block;s.scroll=s.visibleCount=0;}
    if(id==4){s.sort=(s.sort+1)%3;s.visibleCount=0;}
    if(id==5)scroll(-1);if(id==6)scroll(1);if(id==8)s.menu=0;if(id==9)s.menu=!s.menu;
    if(id==24)s.locked=!s.locked;
    StorageBuildView();dirty();
}
static void track(int y){StorageState.scroll=min(max(0,(y-69-thumbSize()/2)*maxScroll()/max(1,thumbTravel())),maxScroll());StorageState.visibleCount=0;dirty();}
EXPORT void __fastcall StorageDown(void* w,void*,int x,int y){
    auto& s=StorageState;if(s.closing)return;sync();s.hover=s.pressed=StorageHit(x,y);dirty();
    if(s.pressed==25){s.menu=0;reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B760)((void*)0x131F4E8,s.editor);return;}
    blur();if(s.pressed){
        reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);
        if(s.pressed==7)track(y);if(s.pressed==23){s.resizeY=y;s.resizeRows=rows();}return;
    }
    if(y<17)s.dragging=1;
    if(s.locked && StorageItemHit(x,y)>=0)return;
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x94AE80)(w,x,y);
}
EXPORT void __fastcall StorageUp(void* w,void*,int x,int y){
    auto& s=StorageState;int pressed=s.pressed;s.pressed=s.grab=0;
    // Custom controls must never enter UIWindow's drag/save/release path.
    // It uses the native +38 drag mode, which was not initialized by these tabs.
    if(!pressed)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880BB0)(w,x,y);
    release();s.dragging=0;if(!s.closing && pressed && pressed==StorageHit(x,y))action(w,pressed);dirty();
}
static void tooltip(void* w,const char* label,int x,int y){
    void* manager=*reinterpret_cast<void**>(0x121333C);if(!manager)return;
    reinterpret_cast<void (__thiscall *)(void*,int*,int*)>(0xA1EF70)(w,&x,&y);
    reinterpret_cast<void (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA753D0)(manager,label,x,y,-1,0,1);
}
EXPORT void __fastcall StorageMove(void* w,void*,int x,int y){
    auto& s=StorageState;s.mouseX=x;s.mouseY=y;s.hover=StorageHit(x,y);dirty();
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x94D250)(w,x,y);
    if(!own(w) || s.ready!=2 || s.closing)return;
    const char* label=0;
    static const char* tabs[]={"Search","Usable","Weapon","Armor","ETC","Card","Ammunition","Costume","Shadow Gear","Pet"};
    if(s.hover>=10 && s.hover<20)label=tabs[s.hover-10];
    else if(s.hover==21)label="Cash";
    else if(s.hover==24)label=s.locked?"Unlock Storage Transfers":"Lock Storage Transfers";
    else if(s.hover==4)label="Sort Refine";
    else if(s.hover==3)label=s.block?"Change to List":"Change to Block";
    if(label)tooltip(w,label,x<33?33:x,y-16);
}
EXPORT void __fastcall StorageDrag(void* w,void*,int x,int y){
    auto& s=StorageState;if(s.pressed==7)track(y);
    else if(s.pressed==23){s.rows=max(10,min(18,s.resizeRows+(y-s.resizeY)/32));layout(w);s.scroll=min(s.scroll,maxScroll());s.visibleCount=0;dirty();}
    else if(!s.pressed && s.dragging)reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x880E00)(w,x,y);
}
EXPORT void __fastcall StorageRight(void* w,void*,int x,int y){
    if(StorageState.closing || StorageHit(x,y))return;
    if(StorageState.locked && ((*reinterpret_cast<short (__stdcall **)(int)>(0xFC1658))(0x10)&0x8000))return;
    sync();reinterpret_cast<void (__thiscall *)(void*,int,int)>(0x94F200)(w,x,y);
}
EXPORT void __fastcall StorageDrop(void* w,void*,int x,int y,void* item){
    if(own(w) && (StorageState.locked || StorageState.closing)){cancelTransfer();return;}
    reinterpret_cast<void (__thiscall *)(void*,int,int,void*)>(0x938490)(w,x,y,item);
}
EXPORT void __fastcall StorageTooltipAnchor(void* w,void*,int* x,int* y){
    if(own(w)){*x=57+(StorageState.block?max(0,StorageState.mouseX-57)/32*32:0);*y=57+max(0,StorageState.mouseY-57)/32*32-16;}
    reinterpret_cast<void (__thiscall *)(void*,int*,int*)>(0xA1EF70)(w,x,y);
}
EXPORT void __fastcall StorageWheel(void*,void*,int delta){if(!StorageState.menu)scroll(delta>0?-3:delta<0?3:0);}
EXPORT void* __fastcall StorageDestroy(void* w,void*,int flags){
    if(w==StorageState.window){cursorRelease();blur();release();memset(&StorageState,0,sizeof(StorageState));}
    return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x936640)(w,flags);
}
