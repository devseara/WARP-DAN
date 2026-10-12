/* Bestiary-only native preview, 2025-07-16 Ragexe x86.
 * Freestanding code embedded by WARP; no DLL, CRT, hooks or resource mutation.
 * Native layouts profiled at 70F2C0, 70F390, A1DC80, 53CB50 and 53D8F0.
 * Native UI compositor uses top-left layer coordinates, scale and mirroring.
 * It does not apply ACT rotation; preserve that stock rendering contract.
 */
using u32 = unsigned int;
using u8 = unsigned char;
template<class T> struct Vector { T* begin; T* end; T* capacity; };
struct Layer {
	int x, y, image, mirror;
	u32 color;
	float scale_x, scale_y;
	int rotation, type;
};
struct Frame {
	u8 unused[32];
	Vector<Layer> layers;
	int layer_count;
	u8 tail[20];
};
struct SpriteImage { short width, height; };
struct Spr { u8 unused[0x510]; Vector<SpriteImage*> images[2]; };
struct Act { u8 unused[0x110]; Vector<Vector<Frame>> actions; };
static_assert(sizeof(void*) == 4 && sizeof(Layer) == 36 && sizeof(Frame) == 68, "2025 native ACT ABI");
static_assert(sizeof(Vector<Frame>) == 12, "2025 native action ABI");
extern "C" int _fltused = 0;

template<class T> static int count(const Vector<T>& v, u32 maximum) {
	u32 first = reinterpret_cast<u32>(v.begin), last = reinterpret_cast<u32>(v.end);
	if (!first || last < first || (last-first)%sizeof(T)) return -1;
	u32 size = (last-first)/sizeof(T);
	return size <= maximum ? static_cast<int>(size) : -1;
}

// Exact stdcall entry used by the resource adapter, ret 32. Pointers are
// borrowed for this draw only: resources may be unloaded between maps.
extern "C" int __stdcall BestiaryPreview(void* window, const Spr* spr, const Act* act,
	int x, int y, int width, int height, int cycle_ms) {
	if (!window || !spr || !act || x < 0 || y < 0 || width < 4 || height < 4 ||
		width > 4096 || height > 4096 || cycle_ms < 0 || cycle_ms > 60000) return 0;
	void* surface = *reinterpret_cast<void**>(static_cast<u8*>(window)+0x24);
	if (!surface || count(act->actions, 1024) <= 0) return 0;
	const auto& frames = act->actions.begin[0];
	int frame_count = count(frames, 1024);
	if (frame_count <= 0) return 0;
	int image_count[2] = {count(spr->images[0], 65536), count(spr->images[1], 65536)};
	// An empty native vector is allowed to have three null pointers.
	for (int i=0;i<2;++i) if (!spr->images[i].begin && !spr->images[i].end) image_count[i]=0;
	float min_x=0, min_y=0, max_x=0, max_y=0;
	bool any=false;
	u32 work=0;
	for (int f=0;f<frame_count;++f) {
		const auto& frame = frames.begin[f];
		int layers = count(frame.layers, 4096);
		if (!frame.layers.begin && !frame.layers.end) layers=0;
		if (layers < 0 || layers != frame.layer_count || (work+=layers) > 16384) return 0;
		for (int l=0;l<layers;++l) {
			const auto& layer=frame.layers.begin[l];
			if (layer.image == -1) continue;
			if (layer.type < 0 || layer.type > 1 || layer.image < 0 || layer.image >= image_count[layer.type]) return 0;
			const SpriteImage* image=spr->images[layer.type].begin[layer.image];
			if (!image || image->width <= 0 || image->height <= 0) return 0;
			float sx=layer.scale_x,sy=layer.scale_y;
			// Reject NaN/Inf, degenerate geometry and arithmetic overflow before
			// the native compositor (which trusts all these resource fields).
			if (!(sx >= -64 && sx <= 64 && sy >= -64 && sy <= 64) ||
				layer.x < -1000000 || layer.x > 1000000 || layer.y < -1000000 || layer.y > 1000000) return 0;
			if (sx <= 0 || sy <= 0 || !(layer.color >> 24)) continue; // Native compositor skips these layers.
			float left=layer.x*sx,top=layer.y*sy;
			float right=left+image->width*sx,bottom=top+image->height*sy;
			if (!any) {min_x=left;min_y=top;max_x=right;max_y=bottom;any=true;}
			else {if(left<min_x)min_x=left;if(top<min_y)min_y=top;if(right>max_x)max_x=right;if(bottom>max_y)max_y=bottom;}
		}
	}
	if (!any) return 0;
	float w=max_x-min_x,h=max_y-min_y;
	if (!(w>0 && h>0)) return 0;
	int padding=(width>64 && height>64)?4:1;
	float scale=1.0f, sx=(width-2*padding)/w, sy=(height-2*padding)/h;
	if(sx<scale)scale=sx;if(sy<scale)scale=sy;
	int offset_x=static_cast<int>((width-w*scale)*0.5f-min_x*scale);
	int offset_y=static_cast<int>((height-h*scale)*0.5f-min_y*scale);
	int frame=0;
	if(cycle_ms) {
		auto now=(*reinterpret_cast<u32(__stdcall**)()>(0x00FC17B0))();
		frame=(now%static_cast<u32>(cycle_ms))*frame_count/cycle_ms;
	}
	using Draw=void(__thiscall*)(void*,int,int,int,int,const Spr*,const Frame*,int,int,float,void*);
	void** vtable=*reinterpret_cast<void***>(surface);
	// Same slot and arguments used by stock UIFrameWnd::DrawSprite A1DC80.
	reinterpret_cast<Draw>(vtable[13])(surface,x,y,width,height,spr,&frames.begin[frame],offset_x,offset_y,scale,nullptr);
	return 1;
}
