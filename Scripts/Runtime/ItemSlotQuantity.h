// Scoped to the 32px Inventory/Cart/Storage cells in the 2025-07-16 client.
// Keep native icon/quantity rendering when it fits. Native short counts start
// 14px right of the icon, so a three-digit count otherwise crosses the cell.
// A borrowed CItem copy suppresses only that draw's count; session items and
// the shared native renderer are never changed. Guild storage uses StorageUI.
#pragma once

static void drawSlotItem(void* window,int iconX,int iconY,void* item){
    typedef void (__thiscall *DrawItem)(void*,int,int,void*,int,int);
    typedef int (__thiscall *Measure)(void*,const char*,int,int,int,int,int);
    typedef void (__thiscall *DrawText)(void*,int,int,const char*,int,int,int,unsigned int,int,int);
    const auto native=reinterpret_cast<DrawItem>(0x8711A0);
    const int amount=*reinterpret_cast<const int*>(static_cast<const unsigned char*>(item)+0x10);
    if(amount<=0){native(window,iconX,iconY,item,0,0);return;}

    char value[12],reverse[12];int digits=0,n=amount;
    do{reverse[digits++]=static_cast<char>('0'+n%10);n/=10;}while(n);
    for(int i=0;i<digits;++i)value[i]=reverse[digits-i-1];value[digits]=0;
    const auto measure=reinterpret_cast<Measure>(0xA21C90);
    int font=11,width=measure(window,value,0,0,font,0,0);
    const int stockX=iconX+(amount<1000?14:0),right=iconX+28;
    if(stockX+width+1<=right){native(window,iconX,iconY,item,0,0);return;}
    // Leave one pixel for the native white outline on each side. Five digits
    // through 30000 fit at the normal font; allow wider configured fonts too.
    while(width>30 && font>8)width=measure(window,value,0,0,--font,0,0);

    unsigned int picture[0xF8/4];
    auto* copy=static_cast<volatile unsigned int*>(picture);
    const auto* source=static_cast<const unsigned int*>(item);
    for(int i=0;i<0xF8/4;++i)copy[i]=source[i];
    picture[4]=0;
    native(window,iconX,iconY,picture,0,0);

    const int x=right-width-1,y=iconY+15;
    const auto text=reinterpret_cast<DrawText>(0xA25A70);
    text(window,x+1,y,value,0,0,font,0xFFFFFF,0,0);
    text(window,x-1,y,value,0,0,font,0xFFFFFF,0,0);
    text(window,x,y+1,value,0,0,font,0xFFFFFF,0,0);
    text(window,x,y-1,value,0,0,font,0xFFFFFF,0,0);
    text(window,x,y,value,0,0,font,0,0,0);
}
