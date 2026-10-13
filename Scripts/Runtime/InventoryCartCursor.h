// Private per-module cursor surface. Nothing is installed in the window tree,
// so the hand is not clipped by the panel bounds and cannot intercept input.
static void* cursorSurface;
static bool cursorPosition(void* w,bool resizing,int& x,int& y){
    if(!w || !at<int>(w,0x28))return false;
    void* manager=(void*)0x131F4E8;
    void* capture=at<void*>(manager,0x19C);
    if(capture && (capture!=w || !resizing))return false;
    int screenX=*reinterpret_cast<int*>(0x11E40D4),screenY=*reinterpret_cast<int*>(0x11E40D8);
    if(!(resizing && capture==w)){
        void* hit=reinterpret_cast<void* (__thiscall *)(void*,int,int)>(0xA336D0)(manager,screenX,screenY);
        for(int i=0;hit && hit!=w && i<32;++i)hit=at<void*>(hit,0x10);
        if(hit!=w)return false;
    }
    int originX=0,originY=0;
    reinterpret_cast<void (__thiscall *)(void*,int*,int*)>(0xA1EF70)(w,&originX,&originY);
    x=screenX-originX;y=screenY-originY;return true;
}
static bool cursorPaint(void* texture){
    if(!texture || !*reinterpret_cast<void**>(0x12515F8))return false;
    if(!cursorSurface){
        cursorSurface=reinterpret_cast<void* (__cdecl *)(int,int,int)>(0x560E50)(26,22,0);
        if(!cursorSurface)return false;
        u32* dest=at<u32*>(cursorSurface,0x18);
        if(!dest){cursorRelease();return false;}
        u32* source=at<u32*>(texture,0x11C);
        for(int i=0;i<26*22;++i){u32 rgb=source[i]&0xFFFFFF;dest[i]=rgb==0xFF00FF?0:0xFF000000|rgb;}
        at<u8>(cursorSurface,0x28)=1;at<u8>(cursorSurface,0x1C)=1;
    }
    // Native surface upload/render: screen x/y, width/height, ARGB modulation.
    reinterpret_cast<void (__thiscall *)(void*,int,int,int,int,u32)>(0x53EA90)(cursorSurface,*reinterpret_cast<int*>(0x11E40D4),*reinterpret_cast<int*>(0x11E40D8),26,22,0xFFFFFFFF);
    return true;
}
static void cursorRelease(){
    if(cursorSurface){void* surface=cursorSurface;cursorSurface=0;reinterpret_cast<void* (__thiscall *)(void*,int)>(at<u32*>(surface,0)[0])(surface,1);}
}
