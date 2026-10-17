// Copyright (c) rAthena Dev Teams - Licensed under GNU GPL
// For more information, see LICENCE in the main folder
// Native medallion overlays. Thunderstorms require the negotiated WENV v4 state.

// Presentation only: never accepted in the current server weather mask.
constexpr u32 thunderstorm_art_preview = 0x80000000u;
static void skyPixel(int x,int y,u32 color) {
    if(x*x+y*y<28*28)pixel(140+x,35+y,color);
}
static bool cloudShape(int x,int y) {
    return ((x+12)*(x+12)*9+(y-9)*(y-9)*16<1296) ||
        ((x+2)*(x+2)+(y-5)*(y-5)<121) ||
        ((x-11)*(x-11)+(y-9)*(y-9)<100) ||
        (x>=-18 && x<=18 && y>=9 && y<=17);
}
static void medallionWeather(u32 weather,bool night) {
    const bool storm=(weather&(Thunderstorm|thunderstorm_art_preview))!=0;
    if(weather&(Rain|Clouds|Snow) || storm){
        // The cloud occludes the lower sun rays/crescent; precipitation owns this band.
        for(int y=17;y<=27;++y)for(int x=-27;x<=27;++x)
            skyPixel(x,y,shade(night?0xFF233752:0xFFF0F7FD,night?0xFF596E8D:0xFFBDD8E5,(y+30)*255/60));
        for(int y=-7;y<=19;++y)for(int x=-25;x<=25;++x){
            if(!cloudShape(x,y))continue;
            const bool edge=!cloudShape(x-1,y)||!cloudShape(x+1,y)||!cloudShape(x,y-1)||!cloudShape(x,y+1);
            const u32 light=storm?0xFF9EB1C6:(night?0xFFD6E3F1:0xFFF7FAFF);
            const u32 dark=storm?0xFF52677F:(night?0xFF829DBA:0xFFACC0D3);
            skyPixel(x,y,edge?(night?0xFF405873:0xFF6B829B):shade(light,dark,(y+6)*255/25));
        }
        if(storm){
            // A compact gold bolt; this is artwork only, with no screen flashes.
            for(int y=16;y<=27;++y){
                const int left=y<22?2-(y-16):1-(y-22);
                for(int x=left;x<=left+4;++x)skyPixel(x,y,x==left?0xFFBC8B39:0xFFFFE59A);
            }
        }else if(weather&Rain){
            for(int i=0;i<3;++i)for(int y=20;y<=27;++y){
                const int x=-12+i*12-(y-20)/3;
                skyPixel(x,y,night?0xFF98D9F5:0xFF438DBB);
                skyPixel(x+1,y,night?0xFFD0F0FF:0xFF97D7EF);
            }
        }else if(weather&Snow){
            for(int i=0;i<3;++i){
                const int x=-12+i*12,y=23;
                for(int d=-2;d<=2;++d){skyPixel(x+d,y,0xFFE6F7FF);skyPixel(x,y+d,0xFFE6F7FF);}
            }
        }
    }else if(weather&Fog){
        for(int row=0;row<3;++row)for(int x=-22+row*2;x<=20-row*2;++x)
            for(int y=11+row*5;y<13+row*5;++y)skyPixel(x,y,night?0xFFB4C8DA:0xFF94AABB);
    }else if(weather&(Petals|Leaves)){
        for(int i=0;i<3;++i){
            const int cx=-14+i*13,cy=15+(i%2)*7;
            for(int y=-4;y<=4;++y)for(int x=-3;x<=3;++x)
                if(x*x*2+y*y<18)skyPixel(cx+x,cy+y,weather&Petals?0xFFE9B6CE:0xFFC7A565);
            for(int y=-3;y<=3;++y)skyPixel(cx,cy+y,0xFF977E57);
        }
    }else if(weather&Fireworks){
        for(int i=0;i<2;++i){
            const int cx=-13+i*27,cy=14+i*5;
            for(int d=-4;d<=4;++d){skyPixel(cx+d,cy,0xFFFFD88E);skyPixel(cx,cy+d,0xFFFFD88E);}
            for(int d=-3;d<=3;++d){skyPixel(cx+d,cy+d,0xFFB9D7F7);skyPixel(cx-d,cy+d,0xFFB9D7F7);}
        }
    }
}
