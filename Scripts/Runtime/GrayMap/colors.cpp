/**************************************************************************\
*                                                                          *
*   Copyright (C) 2026 WARP contributors                                   *
*                                                                          *
*   This file is a part of WARP project (specific to RO clients)           *
*                                                                          *
*   WARP is free software: you can redistribute it and/or modify           *
*   it under the terms of the GNU General Public License as published by   *
*   the Free Software Foundation, either version 3 of the License, or      *
*   (at your option) any later version.                                    *
*                                                                          *
*   WARP is distributed in the hope that it will be useful,                *
*   but WITHOUT ANY WARRANTY; without even the implied warranty of         *
*   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the           *
*   GNU General Public License for more details.                           *
*                                                                          *
|**************************************************************************|
*                                                                          *
*   Author(s)     : WARP contributors                                      *
*   Created Date  : 2026-10-16                                             *
*   Last Modified : 2026-10-16                                             *
*                                                                          *
*   Description   : Offline source for the 2025-07-16 GrayMap static       *
*                   payload. Replaces the atlas palette in memory and      *
*                   adds nonmodal native Graphics controls and help.       *
*                   QJS embeds the import-free result at patch time;       *
*                   no DLL is shipped and map resources stay read-only.    *
*                                                                          *
\**************************************************************************/

typedef unsigned int u32;
typedef unsigned char u8;
#define EXPORT extern "C" __declspec(dllexport)
struct State { u32 enabled,grid,hide,ground,texture,child; };
EXPORT State* GrayMapState=0;
template<class T>T& at(void* p,int off){return *reinterpret_cast<T*>(static_cast<u8*>(p)+off);}
template<class T>T iat(u32 p){return *reinterpret_cast<T*>(p);}
struct Prefs {u32 magic,version,walk,blocked,preset,flags,custom[16];};
static Prefs prefs={0x50414D47,1,0xA0ABB5,0x2B323A,0,3,{}};
static u32 loaded,revision=1,bufferRevision,appliedRevision;
static void* appliedTexture;
static u32 appliedHandle,appliedSurface;
static u32 pixels[512*256];
static char path[260];
struct Preset {const char* name;u32 walk,blocked;};
static Preset presets[]={
    {"Tactical",0xA0ABB5,0x2B323A}, {"Classic gray",0xAAAAAA,0x353535},
    {"High contrast",0xCBD2D8,0x20252B}, {"Warm stone",0xB8AF9D,0x403B35},
    {"Custom",0,0}};
static u32 colorref(u32 rgb){return ((rgb&255)<<16)|(rgb&0xFF00)|((rgb>>16)&255);}
struct UiApi {u32 rowTable,popupTable,scrollTable,pageTable,pageDestroy,toggleTable,toggleDestroy;};
EXPORT UiApi GrayUIApi={};
enum Layout { RowCount=6, RowHeight=32, GrayStart=232, ViewHeight=272,
    ContentHeight=GrayStart+RowCount*RowHeight, ScrollMax=ContentHeight-ViewHeight,
    ArrowHeight=13, ThumbHeight=(ViewHeight-2*ArrowHeight)*ViewHeight/ContentHeight,
    ThumbTravel=ViewHeight-2*ArrowHeight-ThumbHeight, RowX=16, ControlX=134,
    FieldWidth=182, MenuX=RowX+ControlX, MenuHeight=94 };
struct Child {void* window;int x,y,height;u32 visible;};
struct UI {
    void* page;void* rows[3];void* bar;void* popup;
    int scroll,mode,hover,drag;void* pressed;int hit,button,popupY;
    u32 oldWalk,oldBlocked,oldPreset,oldCustom[16];
    Child children[16];int count,dragOffset;
    void* menu;void* editor;void* toggle[3];
    void* extraRows[3];void* tipManager;void* tipWindow;u32 tipTick;
};
EXPORT UI GrayUI={};
static void* rowWindow(int i){return i<3?GrayUI.rows[i]:GrayUI.extraRows[i-3];}
static void hideTip(){
    void* manager=*reinterpret_cast<void**>(0x121333C);
    if(manager && manager==GrayUI.tipManager && GrayUI.tipWindow &&
       at<void*>(manager,0x1C)==GrayUI.tipWindow && at<u32>(manager,0x20)==GrayUI.tipTick)
        reinterpret_cast<void (__thiscall *)(void*)>(0xA753A0)(manager);
    GrayUI.tipManager=0;GrayUI.tipWindow=0;GrayUI.tipTick=0;
}
static void dirty(){
    for(int i=0;i<3;++i)if(GrayUI.toggle[i]){
        u32 value=i==0?GrayMapState->enabled:i==1?GrayMapState->grid:GrayMapState->hide;
        at<u8>(GrayUI.toggle[i],0xF8)=u8(!!value);
    }
    for(int i=0;i<RowCount;++i)if(rowWindow(i))at<u32>(rowWindow(i),0x58)=1;
    if(GrayUI.popup)at<u32>(GrayUI.popup,0x58)=1;
    if(GrayUI.bar)at<u32>(GrayUI.bar,0x58)=1;
    // Moving/hiding transparent children must clear their old parent pixels.
    // CUIObjectWnd::UpdateSurface climbs to the settings root and recursively
    // invalidates the visible subtree (9AC860 -> A1EDD0 -> A23360). Setting
    // only leaf +58 redraws over the cached composite and leaves old positions.
    if(GrayUI.page)
        reinterpret_cast<void (__thiscall **)(void*)>(at<void*>(GrayUI.page,0))[38](GrayUI.page);
}
static void copy(void* d,const void* s,u32 n){volatile u8* out=static_cast<u8*>(d);const u8* in=static_cast<const u8*>(s);for(u32 i=0;i<n;++i)out[i]=in[i];}
static void clear(void* d,u32 n){volatile u8* out=static_cast<u8*>(d);for(u32 i=0;i<n;++i)out[i]=0;}
static void changed(){++revision;dirty();}
static void save(){
    if(!path[0])return;
    prefs.flags=(GrayMapState->grid?1u:0u)|(GrayMapState->hide?2u:0u);
    void* f=iat<void* (__stdcall *)(const char*,u32,u32,void*,u32,u32,void*)>(0xFC1224)(path,0x40000000,1,0,2,0x80,0);
    if(f==(void*)-1)return;
    u32 written=0;
    iat<int (__stdcall *)(void*,const void*,u32,u32*,void*)>(0xFC1234)(f,&prefs,sizeof(prefs),&written,0);
    iat<int (__stdcall *)(void*)>(0xFC1238)(f);
}
EXPORT void __stdcall GrayLoad(){
    if(loaded)return;loaded=1;
    u32 n=iat<u32 (__stdcall *)(void*,char*,u32)>(0xFC1394)(0,path,260);
    if(!n || n>=260){path[0]=0;return;}
    while(n && path[n-1]!='\\' && path[n-1]!='/')--n;
    const char* tail="savedata\\graymap.bin";
    if(n+20>=260){path[0]=0;return;}
    for(u32 i=0;tail[i];++i)path[n+i]=tail[i];
    // Explicit terminator; keep the path relative to this executable, not CWD.
    u32 t=0;while(tail[t])++t;path[n+t]=0;
    void* f=iat<void* (__stdcall *)(const char*,u32,u32,void*,u32,u32,void*)>(0xFC1224)(path,0x80000000,3,0,3,0x80,0);
    if(f==(void*)-1)return;
    Prefs p;clear(&p,sizeof(p));u32 got=0;
    int ok=iat<int (__stdcall *)(void*,void*,u32,u32*,void*)>(0xFC122C)(f,&p,sizeof(p),&got,0);
    // Reject trailing bytes as well as truncated/unknown records.
    u8 extra=0;u32 more=0;
    iat<int (__stdcall *)(void*,void*,u32,u32*,void*)>(0xFC122C)(f,&extra,1,&more,0);
    iat<int (__stdcall *)(void*)>(0xFC1238)(f);
    if(!ok || got!=sizeof(p) || more || p.magic!=prefs.magic || p.version!=1 || p.preset>4 || p.flags>3 || (p.walk|p.blocked)&0xFF000000)return;
    for(int i=0;i<16;++i)if(p.custom[i]&0xFF000000)return;
    if(p.preset<4 && (p.walk!=presets[p.preset].walk || p.blocked!=presets[p.preset].blocked))p.preset=4;
    copy(&prefs,&p,sizeof(p));GrayMapState->grid=p.flags&1;GrayMapState->hide=(p.flags>>1)&1;
}
static u32 shade(u32 c,u32 delta){
    u32 result=0;for(int s=0;s<24;s+=8){u32 v=((c>>s)&255)+delta;if(v>255)v=255;result|=v<<s;}return result;
}
EXPORT void __stdcall GrayGenerate(){
    // The native raw upload consumes bottom-up rows, matching CBitmap's loader.
    for(u32 physical=0;physical<256;++physical){u32 y=255-physical;
        for(u32 x=0;x<512;++x){
            u32 variant=(y/64)*8+x/64,tx=x%64,ty=y%64,bit=(ty/32)*2+tx/32;
            bool blocked=(variant&(1u<<bit))!=0;
            u32 c=blocked?shade(prefs.blocked,(tx+ty)%8<2?2:0):prefs.walk;
            if((variant&16) && !blocked && (tx%32==0 || ty%32==0))c=shade(prefs.walk,33);
            pixels[physical*512+x]=0xFF000000|c;
        }
    }
    bufferRevision=revision;
}
EXPORT void __stdcall GrayPrepare(){
    GrayLoad();void* tex=(void*)GrayMapState->texture;if(!tex)return;
    u32 vt=at<u32>(tex,0);
    const char* name="graymap\\cells.tga";bool own=at<u8>(tex,8)==1;
    for(int i=0;i<=17;++i){if(at<u8>(tex,0x24+i)!=u8(name[i]))own=false;if(!name[i])break;}
    if(!own || (vt!=0xFD7160 && vt!=0xFD5BF0) || at<u32>(tex,0xC)!=512 || at<u32>(tex,0x10)!=256){
        // Never upload into the manager's shared fallback texture, or submit
        // an atlas whose dimensions cannot preserve the cell classifications.
        GrayMapState->texture=0;return;
    }
    if(bufferRevision!=revision)GrayGenerate();
    bool dx9=vt==0xFD7160;
    u32 handle=at<u32>(tex,dx9?0x12C:0x128),surface=dx9?at<u32>(tex,0x130):0;
    if(appliedRevision==revision && appliedTexture==tex && appliedHandle==handle && appliedSurface==surface)return;
    // The profiled CTexture interface owns allocation, conversion and mipmaps.
    typedef void (__thiscall *Upload)(void*,int,int,int,int,void*,void*,int);
    reinterpret_cast<Upload*>(at<void*>(tex,0))[8](tex,0,0,512,256,pixels,0,0);
    appliedRevision=revision;appliedTexture=tex;
    appliedHandle=at<u32>(tex,dx9?0x12C:0x128);appliedSurface=dx9?at<u32>(tex,0x130):0;
}

// Native UI callbacks return immediately. Never enter an OS menu/dialog loop.
static void local(void* w,int& x,int& y){
    if(w==GrayUI.menu){x-=MenuX;y-=GrayUI.popupY;}
    else if(w==GrayUI.editor){x-=20;y-=8;}
}
static void text(void* w,int x,int y,const char* s,u32 color=0x4F4F4F,int bold=0){
    local(w,x,y);
    reinterpret_cast<void (__thiscall *)(void*,int,int,const char*,int,int,int,u32,int,int)>(0xA25A70)(w,x,y,s,0,0,12,color,bold,0);
}
static void fill(void* w,int x,int y,int width,int height,u32 color){
    local(w,x,y);
    void* b=at<void*>(w,0x24);if(!b)return;
    int bw=at<int>(b,4),bh=at<int>(b,8);u32* p=at<u32*>(b,0x18);
    if(!p || x<0 || y<0 || width<1 || height<1 || bw<1 || bh<1 || x>bw-width || y>bh-height)return;
    for(int row=y;row<y+height;++row)for(int col=x;col<x+width;++col)p[row*bw+col]=color|0xFF000000;
}
static void box(void* w,int x,int y,int width,int height,u32 c){fill(w,x,y,width,height,0xC6C6C6);fill(w,x+1,y+1,width-2,height-2,c);}
static void pos(void* w,int x,int y){reinterpret_cast<void (__thiscall **)(void*,int,int)>(at<void*>(w,0))[4](w,x,y);}
static void release(void* w){
    void* captured=reinterpret_cast<void* (__thiscall *)(void*)>(0xA32E00)((void*)0x131F4E8);
    if(captured==w)reinterpret_cast<void (__thiscall *)(void*)>(0xA482E0)((void*)0x131F4E8);
}
static void capture(void* w){reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA4B750)((void*)0x131F4E8,w);}
static bool inside(int x,int y,int bx,int by,int width,int height){return x>=bx && y>=by && x<bx+width && y<by+height;}
static int row(void* w){for(int i=0;i<RowCount;++i)if(w==rowWindow(i))return i;return -1;}
static int toggle(void* w){for(int i=0;i<3;++i)if(w==GrayUI.toggle[i])return i;return -1;}
static void closePopup(bool cancel){
    hideTip();
    if(cancel && GrayUI.mode>=2){prefs.walk=GrayUI.oldWalk;prefs.blocked=GrayUI.oldBlocked;prefs.preset=GrayUI.oldPreset;copy(prefs.custom,GrayUI.oldCustom,sizeof(prefs.custom));changed();}
    GrayUI.mode=0;if(GrayUI.pressed==GrayUI.popup)GrayUI.drag=0;
    if(GrayUI.popup){at<u32>(GrayUI.popup,0x28)=0;release(GrayUI.popup);}
    dirty();
}
static void scrollTo(int value){
    if(value<0)value=0;if(value>ScrollMax)value=ScrollMax;
    if(value==GrayUI.scroll)return;
    closePopup(true);GrayUI.scroll=value;
    for(int i=0;i<GrayUI.count;++i){
        Child& c=GrayUI.children[i];int y=c.y-value;
        // Whole controls remain inside the content viewport. Never draw or hit
        // test a clipped native control against the fixed settings footer.
        at<u32>(c.window,0x28)=c.visible && y>=0 && y+c.height<=ViewHeight;
        pos(c.window,c.x,y);at<u32>(c.window,0x58)=1;
    }
    dirty();
}
static void arrow(void* w,int x,int y){
    // The exact txtbox_btn_a.bmp used by Graphics API/Device/Resolution.
    void* mgr=reinterpret_cast<void* (__cdecl *)()>(0xA90350)();if(!mgr)return;
    const char* name=reinterpret_cast<const char* (__cdecl *)(const char*)>(0xA9F030)((const char*)0x1045CB4);
    if(!name)return;
    void* bmp=reinterpret_cast<void* (__thiscall *)(void*,const char*)>(0xA8D4A0)(mgr,name);if(!bmp)return;
    reinterpret_cast<void (__thiscall *)(void*,int,int,void*,int)>(0xA1D260)(w,x,y,bmp,0);
}
static void number(char* out,u32 value){
    if(value>=100){out[0]=char('0'+value/100);out[1]=char('0'+value/10%10);out[2]=char('0'+value%10);out[3]=0;}
    else if(value>=10){out[0]=char('0'+value/10);out[1]=char('0'+value%10);out[2]=0;}
    else {out[0]=char('0'+value);out[1]=0;}
}
static u32 selected(){return GrayUI.mode==3?prefs.blocked:prefs.walk;}
static void selected(u32 c){u32& target=GrayUI.mode==3?prefs.blocked:prefs.walk;if(target!=c){target=c;prefs.preset=4;changed();}}
static void channel(int which,int x){if(x<44)x=44;if(x>299)x=299;int shift=16-which*8;selected((selected()&~(255u<<shift))|(u32(x-44)<<shift));}
EXPORT void __fastcall GrayDraw(void* w,void*){
    GrayLoad();int r=row(w);fill(w,0,0,350,RowHeight,0xFFFFFF);
    const char* names[]={"Gray Map","Cell Grid","Hide Scenery","Preset","Walkable","Blocked"};
    if(r<0 || r>=RowCount)return;
    text(w,3,10,names[r],0,1);
    if(r==3){box(w,ControlX,7,FieldWidth,20,0xFFFFFF);text(w,ControlX+4,10,presets[prefs.preset].name);arrow(w,ControlX+FieldWidth-18,8);}
    else if(r>=4)box(w,ControlX,7,FieldWidth,20,r==4?prefs.walk:prefs.blocked);
}
EXPORT void __fastcall GrayCursor(void* w,void*,int x,int y){
    // Reuse the same native cursor/tooltip path as VipUI. Coordinates are
    // converted through the real window hierarchy and clamped by the client.
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA23470)(w,x,y);
    int r=toggle(w);bool isToggle=r>=0;if(!isToggle)r=row(w);
    if(!GrayUI.page || GrayUI.mode || GrayUI.pressed || GrayUI.drag || r<0 || r>=RowCount ||
       !at<u32>(w,0x28) || !at<u32>(GrayUI.page,0x28) ||
       !inside(x,y,0,0,isToggle?34:350,isToggle?15:RowHeight)){hideTip();return;}
    const char* tips[]={
        "Replaces terrain textures with simplified cell colors. Off restores the original map.",
        "Shows cell borders while Gray Map is on.",
        "Hides map trees and buildings while Gray Map is on. Characters and monsters remain visible.",
        "Choose a color palette. Editing a color switches the preset to Custom.",
        "Color used for walkable terrain cells. Click the swatch to edit.",
        "Color used for blocked terrain cells and walls. Click the swatch to edit."};
    void* manager=*reinterpret_cast<void**>(0x121333C);if(!manager)return;
    int tx=x+12,ty=y+20;
    reinterpret_cast<void (__thiscall *)(void*,int*,int*)>(0xA1EF70)(w,&tx,&ty);
    reinterpret_cast<void (__thiscall *)(void*,const char*,int,int,int,int,int)>(0xA753D0)(manager,tips[r],tx,ty,-1,0,0);
    GrayUI.tipManager=manager;GrayUI.tipWindow=at<void*>(manager,0x1C);GrayUI.tipTick=at<u32>(manager,0x20);
}
EXPORT void __fastcall GrayPopupDraw(void* w,void*){
    // Both windows have opaque, tightly bounded native surfaces. There is no
    // full-page transparent bitmap that can erase the settings underneath.
    if(GrayUI.mode==1){
        int y=GrayUI.popupY;box(w,MenuX,y,FieldWidth,MenuHeight,0xFFFFFF);
        for(int i=0;i<5;++i){if(i==GrayUI.hover || (GrayUI.hover<0 && (u32)i==prefs.preset))fill(w,MenuX+1,y+2+i*18,FieldWidth-2,18,0xCEDEFF);text(w,MenuX+5,y+4+i*18,presets[i].name);}
    }else if(GrayUI.mode>=2){
        box(w,20,8,350,238,0xF8F9FA);text(w,30,17,GrayUI.mode==2?"Walkable color":"Blocked color");box(w,274,14,82,24,selected());
        for(int i=0;i<3;++i){int y=48+i*28,shift=16-i*8;const char* labels[]={"R","G","B"};text(w,31,y+3,labels[i]);
            for(int x=0;x<256;++x)fill(w,20+44+x,8+y,1,14,(selected()&~(255u<<shift))|(u32(x)<<shift));
            int thumb=int((selected()>>shift)&255);box(w,20+44+thumb,8+y-3,2,20,0xFFFFFF);
            char value[4];number(value,(selected()>>shift)&255);text(w,20+307,8+y+2,value);
        }
        for(int i=0;i<16;++i)box(w,32+(i%8)*41,140+(i/8)*23,32,19,colorref(prefs.custom[i]));
        text(w,32,190,"Right-click a swatch to save this color");
        box(w,224,215,62,22,0xEAF0F8);text(w,237,221,"Apply");box(w,294,215,62,22,0xF5F5F5);text(w,303,221,"Cancel");
    }
}
EXPORT void __fastcall GrayScrollDraw(void* w,void*){
    at<int>(w,0x80)=ScrollMax;at<int>(w,0x84)=GrayUI.scroll;at<int>(w,0x98)=ContentHeight;at<int>(w,0x9C)=ViewHeight;
    // Native UIScrollBar paints scroll0up/mid/down and scroll0bar_* skin BMPs.
    // Its original GetThumbSize virtual computes a proportional thumb from the content height.
    reinterpret_cast<void (__thiscall *)(void*)>(0x856560)(w);
}
static int hit(void* w,int x,int y){
    int toggleIndex=toggle(w);
    if(toggleIndex>=0)return inside(x,y,0,0,34,15)?10+toggleIndex:-1;
    if(w==GrayUI.popup){
        if(w==GrayUI.menu){x+=MenuX;y+=GrayUI.popupY;}else {x+=20;y+=8;}
        if(GrayUI.mode==1){if(inside(x,y,MenuX+1,GrayUI.popupY+2,FieldWidth-2,90))return 100+(y-GrayUI.popupY-2)/18;return 199;}
        if(GrayUI.mode>=2){
            if(!inside(x,y,20,8,350,238))return 199;
            for(int i=0;i<3;++i)if(inside(x,y,64,56+i*28,256,14))return 200+i;
            for(int i=0;i<16;++i)if(inside(x,y,32+(i%8)*41,140+(i/8)*23,32,19))return 220+i;
            if(inside(x,y,224,215,62,22))return 250;if(inside(x,y,294,215,62,22))return 251;
        }
        return -1;
    }
    if(w==GrayUI.bar){if(!inside(x,y,0,0,13,272))return -1;if(y<13)return 300;if(y>=259)return 301;return 302;}
    int r=row(w);if(r<0 || !inside(x,y,0,0,350,RowHeight))return -1;
    if(r<3)return inside(x,y,ControlX,9,34,15)?10+r:-1;
    if(inside(x,y,ControlX,7,FieldWidth,20))return r;

    return -1;
}
static void show(int mode){
    closePopup(true);GrayUI.popup=mode==1?GrayUI.menu:GrayUI.editor;if(!GrayUI.popup)return;
    GrayUI.mode=mode;GrayUI.hover=-1;
    GrayUI.oldWalk=prefs.walk;GrayUI.oldBlocked=prefs.blocked;GrayUI.oldPreset=prefs.preset;copy(GrayUI.oldCustom,prefs.custom,sizeof(prefs.custom));
    GrayUI.popupY=GrayStart+3*RowHeight+7-GrayUI.scroll-MenuHeight;
    if(mode==1)pos(GrayUI.popup,MenuX,GrayUI.popupY);
    at<u32>(GrayUI.popup,0x28)=1;dirty();
}
static void action(int id){
    if(id>=0 && id<=2){if(id==0)GrayMapState->enabled^=1;else if(id==1)GrayMapState->grid^=1;else GrayMapState->hide^=1;changed();save();}
    else if(id==3){if(GrayUI.mode==1)closePopup(true);else show(1);}
    else if(id==4){if(GrayUI.mode==2)closePopup(true);else show(2);}
    else if(id==5){if(GrayUI.mode==3)closePopup(true);else show(3);}
    else if(id>=100 && id<=104){prefs.preset=id-100;if(id<104){prefs.walk=presets[id-100].walk;prefs.blocked=presets[id-100].blocked;}changed();save();closePopup(false);}
    else if(id==199 || id==251)closePopup(true);
    else if(id>=220 && id<236)selected(colorref(prefs.custom[id-220]));
    else if(id==250){save();closePopup(false);}
    else if(id>=10 && id<13){
        int group=id-10;u32& flag=group==0?GrayMapState->enabled:group==1?GrayMapState->grid:GrayMapState->hide;
        flag^=1;changed();save();
    }
}
static void down(void* w,int x,int y,int button){
    hideTip();GrayLoad();int id=hit(w,x,y);GrayUI.pressed=w;GrayUI.hit=id;GrayUI.button=button;GrayUI.drag=0;capture(w);
    if(button)return;
    if(id>=200 && id<=202){GrayUI.drag=id;channel(id-200,x);}
    else if(id==300)scrollTo(GrayUI.scroll-16);else if(id==301)scrollTo(GrayUI.scroll+16);
    else if(id==302){int top=ArrowHeight+GrayUI.scroll*ThumbTravel/ScrollMax;GrayUI.drag=302;GrayUI.dragOffset=(y>=top && y<top+ThumbHeight)?y-top:ThumbHeight/2;scrollTo((y-ArrowHeight-GrayUI.dragOffset)*ScrollMax/ThumbTravel);}
}
EXPORT void __fastcall GrayDown(void* w,void*,int x,int y){down(w,x,y,0);}
EXPORT void __fastcall GrayRightDown(void* w,void*,int x,int y){down(w,x,y,1);}
EXPORT void __fastcall GrayMove(void* w,void*,int x,int y){
    if(GrayUI.pressed==w && !GrayUI.button){
        if(GrayUI.drag>=200 && GrayUI.drag<=202)channel(GrayUI.drag-200,x);
        else if(GrayUI.drag==302)scrollTo((y-ArrowHeight-GrayUI.dragOffset)*ScrollMax/ThumbTravel);
    }
    if(w==GrayUI.popup && GrayUI.mode==1){int id=hit(w,x,y),hover=(id>=100 && id<=104)?id-100:-1;if(hover!=GrayUI.hover){GrayUI.hover=hover;dirty();}}
}
static void up(void* w,int x,int y,int button){
    // Release the exact native capture before opening/changing another control.
    // No nested message pump can swallow the client's physical mouse-up.
    release(w);bool owned=GrayUI.pressed==w && GrayUI.button==button;int old=GrayUI.hit;
    GrayUI.pressed=0;GrayUI.drag=0;GrayUI.hit=-1;if(!owned)return;
    int id=hit(w,x,y);if(id!=old)return;
    if(button){if(w==GrayUI.popup && GrayUI.mode>=2 && id>=220 && id<236){prefs.custom[id-220]=colorref(selected());dirty();}return;}
    if(id<300 && !(id>=200 && id<=202))action(id);
}
EXPORT void __fastcall GrayUp(void* w,void*,int x,int y){up(w,x,y,0);}
EXPORT void __fastcall GrayRightUp(void* w,void*,int x,int y){up(w,x,y,1);}
EXPORT void __fastcall GrayWheel(void*,void*,int delta){if(delta>0)scrollTo(GrayUI.scroll-16);else if(delta<0)scrollTo(GrayUI.scroll+16);}
static void* child(void* page,u32 table,int x,int y,int width,int height,u32 id){
    void* w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0x120);if(!w)return 0;
    w=reinterpret_cast<void* (__thiscall *)(void*)>(0x8172B0)(w);if(!w)return 0;
    at<u32>(w,0)=table;at<u32>(w,0x2C)=id;
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA1CB70)(w,width,height);pos(w,x,y);
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA1B780)(page,w);return w;
}
static void* nativeToggle(void* parent,int index){
    // Effects tab's CUICheckBox is constructed inline in the stock client:
    // CUIButtonImage base, native state vtable, bool +F8, empty callback +100.
    void* w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0x128);if(!w)return 0;
    w=reinterpret_cast<void* (__thiscall *)(void*)>(0x983C90)(w);if(!w)return 0;
    clear(static_cast<u8*>(w)+0xF8,0x30);
    at<u32>(w,0)=GrayUIApi.toggleTable;at<u32>(w,0x2C)=0x7FF6+index;
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA1CB70)(w,34,15);
    pos(w,ControlX,9);
    struct String {const char* ptr;u32 pad[3];u32 length,capacity;};
    static_assert(sizeof(String)==24,"2025 MSVC string reference");
    // Exact Effects images and state mapping: off, on, off, off.
    String off,on;clear(&off,sizeof(off));clear(&on,sizeof(on));
    off.ptr=(const char*)0x10459B4;off.length=44;off.capacity=44;
    on.ptr=(const char*)0x10459E4;on.length=43;on.capacity=43;
    reinterpret_cast<void (__thiscall *)(void*,const String*,const String*,const String*,const String*)>(0x9ACD80)(w,&off,&on,&off,&off);
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA1B780)(parent,w);return w;
}
static void* nativeScroll(void* page){
    void* w=reinterpret_cast<void* (__cdecl *)(u32)>(0xDBBC4F)(0xB4);if(!w)return 0;
    w=reinterpret_cast<void* (__thiscall *)(void*)>(0x836870)(w);if(!w)return 0;
    at<u32>(w,0)=GrayUIApi.scrollTable;at<u32>(w,0x2C)=0x7FF9;
    reinterpret_cast<void (__thiscall *)(void*,int,int)>(0xA1CB70)(w,13,272);pos(w,382,0);
    reinterpret_cast<void (__thiscall *)(void*,void*)>(0xA1B780)(page,w);return w;
}
EXPORT void __stdcall GrayAttach(void* page){
    if(!page || GrayUI.page==page)return;
    clear(&GrayUI,sizeof(GrayUI));GrayUI.page=page;GrayUI.hover=-1;GrayUI.hit=-1;
    // The engine owns this list and all native children. Snapshot before adding.
    void* head=at<void*>(page,0x50);void* node=head?at<void*>(head,0):0;
    for(int n=0;node && node!=head && n<16;++n,node=at<void*>(node,0)){
        void* w=at<void*>(node,8);if(!w)continue;
        Child& c=GrayUI.children[GrayUI.count++];c.window=w;c.x=at<int>(w,0x1C);c.y=at<int>(w,0x20);c.height=at<int>(w,0x18);c.visible=at<u32>(w,0x28);
    }
    at<u32>(page,0)=GrayUIApi.pageTable;
    for(int i=0;i<RowCount;++i){
        void* w=child(page,GrayUIApi.rowTable,RowX,GrayStart+i*RowHeight,350,RowHeight,0x7FED+i);
        if(i<3)GrayUI.rows[i]=w;else GrayUI.extraRows[i-3]=w;
        if(w && GrayUI.count<16){Child& c=GrayUI.children[GrayUI.count++];c.window=w;c.x=RowX;c.y=GrayStart+i*RowHeight;c.height=RowHeight;c.visible=1;at<u32>(w,0x28)=c.y+c.height<=ViewHeight;}
    }
    GrayMapState->child=(u32)GrayUI.rows[0];
    for(int i=0;i<3;++i)if(GrayUI.rows[i])GrayUI.toggle[i]=nativeToggle(GrayUI.rows[i],i);

    GrayUI.bar=nativeScroll(page);
    GrayUI.menu=child(page,GrayUIApi.popupTable,MenuX,GrayStart+3*RowHeight+7-MenuHeight,FieldWidth,MenuHeight,0x7FFB);
    GrayUI.editor=child(page,GrayUIApi.popupTable,20,8,350,238,0x7FFC);
    if(GrayUI.menu)at<u32>(GrayUI.menu,0x28)=0;
    if(GrayUI.editor)at<u32>(GrayUI.editor,0x28)=0;
    GrayUI.popup=GrayUI.menu;
    GrayLoad();dirty();
}
EXPORT void* __fastcall GrayDestroy(void* w,void*,int flags){
    release(w);if(GrayUI.pressed==w){GrayUI.pressed=0;GrayUI.drag=0;}
    for(int i=0;i<RowCount;++i)if(rowWindow(i)==w){if(i<3)GrayUI.rows[i]=0;else GrayUI.extraRows[i-3]=0;}
    if(GrayUI.bar==w)GrayUI.bar=0;if(GrayUI.popup==w){closePopup(true);GrayUI.popup=0;}
    if(GrayUI.menu==w)GrayUI.menu=0;if(GrayUI.editor==w)GrayUI.editor=0;
    if(GrayMapState->child==(u32)w)GrayMapState->child=0;
    return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x81A5A0)(w,flags);
}
EXPORT void* __fastcall GrayToggleDestroy(void* w,void*,int flags){
    release(w);int i=toggle(w);if(i>=0)GrayUI.toggle[i]=0;
    if(GrayUI.pressed==w){GrayUI.pressed=0;GrayUI.drag=0;}
    return reinterpret_cast<void* (__thiscall *)(void*,int)>(GrayUIApi.toggleDestroy)(w,flags);
}
EXPORT void* __fastcall GrayScrollDestroy(void* w,void*,int flags){
    release(w);if(GrayUI.pressed==w){GrayUI.pressed=0;GrayUI.drag=0;}
    if(GrayUI.bar==w)GrayUI.bar=0;
    return reinterpret_cast<void* (__thiscall *)(void*,int)>(0x83C2C0)(w,flags);
}
EXPORT void* __fastcall GrayPageDestroy(void* w,void*,int flags){
    // The parent settings destructor may already have deleted sibling pages.
    // Cancel pending edits without traversing that partially destroyed root.
    if(GrayUI.page==w){GrayUI.page=0;closePopup(true);if(GrayUI.pressed)release(GrayUI.pressed);clear(&GrayUI,sizeof(GrayUI));GrayMapState->child=0;}
    return reinterpret_cast<void* (__thiscall *)(void*,int)>(GrayUIApi.pageDestroy)(w,flags);
}
