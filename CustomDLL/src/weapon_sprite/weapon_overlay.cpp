// weapon_overlay.cpp - layered-window renderer harness for weapon sprites.
//
// This is intentionally outside the game's native actor-part renderer. It gives
// us a safe render surface while the custom weapon renderer is built up:
// decode SPR frames first, then feed actor/equipment state into this layer.

#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

extern "C" DWORD poll_weapon_state();

namespace {

static HMODULE g_module = nullptr;
static HWND g_overlayWnd = nullptr;
static HWND g_ownerWnd = nullptr;
static HDC g_memDC = nullptr;
static HBITMAP g_hbm = nullptr;
static void* g_bits = nullptr;
static HGDIOBJ g_oldBmp = nullptr;
static bool g_classRegistered = false;
static volatile LONG g_shutdown = 1;
static HANDLE g_thread = nullptr;
static DWORD g_threadId = 0;

static const int kOverlayW = 256;
static const int kOverlayH = 160;
static const int kMaxFrames = 64;
static const char kClassName[] = "BohWeaponOverlayWnd";

struct SpriteFrame
{
    int w;
    int h;
    int originX;
    int originY;
    DWORD* pixels;
};

struct SpriteAsset
{
    SpriteFrame frames[kMaxFrames];
    int frameCount;
    wchar_t path[1024];
};

static SpriteAsset g_mainSprite = {};
static SpriteAsset g_offSprite = {};
static bool g_assetsTried = false;
static int g_spriteScale = 1;
static bool g_hideWhenInactive = true;
static bool g_allowFallbackAssets = false;
static DWORD g_loadedMainItem = 0xFFFFFFFFu;
static DWORD g_loadedOffItem = 0xFFFFFFFFu;
static DWORD g_lastDrawMainItem = 0xFFFFFFFFu;
static DWORD g_lastDrawOffItem = 0xFFFFFFFFu;
static DWORD g_lastDrawTick = 0;

struct OverlayState
{
    volatile LONG seq;
    DWORD tick;
    DWORD charObj;
    DWORD mode;
    DWORD mainItem;
    DWORD offItem;
    DWORD mainView;
    DWORD offView;
};

static OverlayState g_state = {};

static void logf(const char* fmt, ...)
{
    char body[640];
    va_list ap;
    va_start(ap, fmt);
    wvsprintfA(body, fmt, ap);
    va_end(ap);

    char line[720];
    wsprintfA(line, "[WR_OV] %s\n", body);
    OutputDebugStringA(line);
}

static bool shutting_down()
{
    return InterlockedCompareExchange(&g_shutdown, 0, 0) != 0;
}

static WORD read_le16(const BYTE* p)
{
    return static_cast<WORD>(p[0] | (p[1] << 8));
}

static DWORD read_le32(const BYTE* p)
{
    return static_cast<DWORD>(p[0] | (p[1] << 8) |
                              (p[2] << 16) | (p[3] << 24));
}

static int read_i32(const BYTE* p)
{
    LONG v = 0;
    CopyMemory(&v, p, sizeof(v));
    return static_cast<int>(v);
}

static float read_f32(const BYTE* p)
{
    float v = 0.0f;
    CopyMemory(&v, p, sizeof(v));
    return v;
}

static int env_num(const char* name, int fallback)
{
    char buf[32] = {};
    DWORD got = GetEnvironmentVariableA(name, buf, sizeof(buf));
    if (!got || got >= sizeof(buf))
        return fallback;
    int v = atoi(buf);
    return v;
}

static bool env_flag(const char* name, bool fallback)
{
    char buf[32] = {};
    DWORD got = GetEnvironmentVariableA(name, buf, sizeof(buf));
    if (!got || got >= sizeof(buf))
        return fallback;
    return atoi(buf) != 0;
}

static void wide_to_log(const wchar_t* src, char* dst, int dstCount)
{
    if (!dst || dstCount <= 0)
        return;
    dst[0] = 0;
    if (!src)
        return;
    int ok = WideCharToMultiByte(CP_UTF8, 0, src, -1, dst, dstCount,
                                 nullptr, nullptr);
    if (!ok)
        lstrcpynA(dst, "<path>", dstCount);
}

static void log_path(const char* prefix, const wchar_t* path)
{
    char tmp[520];
    wide_to_log(path, tmp, sizeof(tmp));
    logf("%s%s", prefix, tmp);
}

static void free_asset(SpriteAsset& asset)
{
    for (int i = 0; i < asset.frameCount; ++i)
    {
        if (asset.frames[i].pixels)
            HeapFree(GetProcessHeap(), 0, asset.frames[i].pixels);
        asset.frames[i].pixels = nullptr;
        asset.frames[i].w = 0;
        asset.frames[i].h = 0;
        asset.frames[i].originX = 0;
        asset.frames[i].originY = 0;
    }
    asset.frameCount = 0;
    asset.path[0] = 0;
}

static void free_assets()
{
    free_asset(g_mainSprite);
    free_asset(g_offSprite);
    g_assetsTried = false;
}

static bool copy_path(wchar_t* dst, int dstCount, const wchar_t* src)
{
    if (!dst || dstCount <= 0 || !src)
        return false;
    if (lstrlenW(src) >= dstCount)
        return false;
    lstrcpynW(dst, src, dstCount);
    return true;
}

static bool join_path(wchar_t* out, int outCount,
                      const wchar_t* left, const wchar_t* right)
{
    if (!out || !left || !right)
        return false;
    int leftLen = lstrlenW(left);
    int rightLen = lstrlenW(right);
    bool needSlash = leftLen > 0 &&
        left[leftLen - 1] != L'\\' && left[leftLen - 1] != L'/';
    if (leftLen + (needSlash ? 1 : 0) + rightLen + 1 > outCount)
        return false;
    lstrcpynW(out, left, outCount);
    if (needSlash)
        lstrcatW(out, L"\\");
    lstrcatW(out, right);
    return true;
}

static void get_exe_dir(wchar_t* out, int outCount)
{
    out[0] = 0;
    GetModuleFileNameW(nullptr, out, outCount);
    for (int i = lstrlenW(out) - 1; i >= 0; --i)
    {
        if (out[i] == L'\\' || out[i] == L'/')
        {
            out[i] = 0;
            return;
        }
    }
}

static bool is_absolute_path(const wchar_t* path)
{
    if (!path || !path[0])
        return false;
    if (path[0] == L'\\' && path[1] == L'\\')
        return true;
    return path[1] == L':';
}

static bool env_path(const char* name, wchar_t* out, int outCount)
{
    char raw[1024] = {};
    DWORD got = GetEnvironmentVariableA(name, raw, sizeof(raw));
    if (!got || got >= sizeof(raw))
        return false;

    wchar_t wide[1024] = {};
    if (!MultiByteToWideChar(CP_ACP, 0, raw, -1, wide, 1024))
        return false;

    if (is_absolute_path(wide))
        return copy_path(out, outCount, wide);

    wchar_t exeDir[1024];
    get_exe_dir(exeDir, 1024);
    return join_path(out, outCount, exeDir, wide);
}

static bool suffix_match_i(const wchar_t* name, const wchar_t* suffix)
{
    int nameLen = lstrlenW(name);
    int suffixLen = lstrlenW(suffix);
    if (suffixLen <= 0 || nameLen < suffixLen)
        return false;
    return _wcsicmp(name + nameLen - suffixLen, suffix) == 0;
}

static void find_best_sprite_rec(const wchar_t* dir, const wchar_t* suffix,
                                 int depth, wchar_t* best, DWORD* bestSize)
{
    if (depth > 14 || shutting_down())
        return;

    wchar_t pattern[1024];
    if (!join_path(pattern, 1024, dir, L"*"))
        return;

    WIN32_FIND_DATAW fd = {};
    HANDLE h = FindFirstFileW(pattern, &fd);
    if (h == INVALID_HANDLE_VALUE)
        return;

    do
    {
        if (lstrcmpW(fd.cFileName, L".") == 0 ||
            lstrcmpW(fd.cFileName, L"..") == 0)
            continue;

        wchar_t full[1024];
        if (!join_path(full, 1024, dir, fd.cFileName))
            continue;

        if (fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
        {
            find_best_sprite_rec(full, suffix, depth + 1, best, bestSize);
            continue;
        }

        if (!suffix_match_i(fd.cFileName, suffix))
            continue;

        if (fd.nFileSizeHigh == 0 && fd.nFileSizeLow < *bestSize)
        {
            *bestSize = fd.nFileSizeLow;
            copy_path(best, 1024, full);
        }
    } while (FindNextFileW(h, &fd));

    FindClose(h);
}

static bool find_best_sprite(const wchar_t* suffix, wchar_t* out, int outCount)
{
    wchar_t exeDir[1024];
    wchar_t spriteRoot[1024];
    get_exe_dir(exeDir, 1024);
    if (!join_path(spriteRoot, 1024, exeDir, L"data\\sprite"))
        return false;

    wchar_t best[1024] = {};
    DWORD bestSize = 0xFFFFFFFFu;
    find_best_sprite_rec(spriteRoot, suffix, 0, best, &bestSize);
    if (!best[0])
    {
        char suffixText[120];
        char rootText[520];
        wide_to_log(suffix, suffixText, sizeof(suffixText));
        wide_to_log(spriteRoot, rootText, sizeof(rootText));
        logf("asset search miss suffix=%s root=%s", suffixText, rootText);
        return false;
    }
    return copy_path(out, outCount, best);
}

static BYTE* read_file_heap(const wchar_t* path, DWORD* outSize)
{
    *outSize = 0;
    HANDLE h = CreateFileW(path, GENERIC_READ, FILE_SHARE_READ, nullptr,
                           OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE)
        return nullptr;

    DWORD hi = 0;
    DWORD size = GetFileSize(h, &hi);
    if (hi != 0 || size < 16 || size > 32 * 1024 * 1024)
    {
        CloseHandle(h);
        return nullptr;
    }

    BYTE* data = static_cast<BYTE*>(HeapAlloc(GetProcessHeap(), 0, size));
    if (!data)
    {
        CloseHandle(h);
        return nullptr;
    }

    DWORD got = 0;
    BOOL ok = ReadFile(h, data, size, &got, nullptr);
    CloseHandle(h);
    if (!ok || got != size)
    {
        HeapFree(GetProcessHeap(), 0, data);
        return nullptr;
    }

    *outSize = size;
    return data;
}

static bool decode_paletted_frame(const BYTE* enc, DWORD encSize,
                                  const BYTE* palette, int w, int h,
                                  SpriteFrame* out)
{
    if (!enc || !palette || !out || w <= 0 || h <= 0 || w > 512 || h > 512)
        return false;

    int total = w * h;
    DWORD* pixels = static_cast<DWORD*>(
        HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, total * sizeof(DWORD)));
    if (!pixels)
        return false;

    DWORD src = 0;
    int dst = 0;
    while (src < encSize && dst < total)
    {
        BYTE b = enc[src++];
        if (b == 0)
        {
            if (src >= encSize)
                break;
            int run = static_cast<int>(enc[src++]);
            if (run < 0)
                run = 0;
            dst += run;
            if (dst > total)
                dst = total;
            continue;
        }

        const BYTE* c = palette + (static_cast<int>(b) * 4);
        BYTE blue = c[0];
        BYTE green = c[1];
        BYTE red = c[2];
        pixels[dst++] = 0xFF000000u |
                        (static_cast<DWORD>(red) << 16) |
                        (static_cast<DWORD>(green) << 8) |
                        static_cast<DWORD>(blue);
    }

    out->w = w;
    out->h = h;
    out->originX = w / 2;
    out->originY = h / 2;
    out->pixels = pixels;
    return true;
}

static bool decode_spr_bytes(const wchar_t* path, const BYTE* data, DWORD size,
                             SpriteAsset& asset, const char* tag)
{
    free_asset(asset);

    bool ok = false;
    if (size >= 8 + 1024 && data[0] == 'S' && data[1] == 'P')
    {
        BYTE minor = data[2];
        BYTE major = data[3];
        bool v21Plus = (major > 2) || (major == 2 && minor >= 1);
        bool v22Plus = (major > 2) || (major == 2 && minor >= 2);
        WORD palCount = read_le16(data + 4);
        DWORD paletteOffset = size - 1024;
        const BYTE* palette = data + paletteOffset;
        DWORD off = 8;

        for (WORD i = 0; i < palCount && asset.frameCount < kMaxFrames; ++i)
        {
            DWORD headerSize = v22Plus ? 8 : (v21Plus ? 6 : 4);
            if (off + headerSize > paletteOffset)
                break;
            int w = read_le16(data + off);
            int h = read_le16(data + off + 2);
            DWORD encSize = v22Plus ? read_le32(data + off + 4) :
                            (v21Plus ? read_le16(data + off + 4) :
                             static_cast<DWORD>(w * h));
            off += headerSize;
            if (encSize == 0 || off + encSize > paletteOffset)
                break;

            SpriteFrame frame = {};
            if (decode_paletted_frame(data + off, encSize, palette, w, h, &frame))
                asset.frames[asset.frameCount++] = frame;
            off += encSize;
        }

        ok = asset.frameCount > 0;
    }

    if (!ok)
    {
        log_path("sprite decode failed path=", path);
        free_asset(asset);
        return false;
    }

    copy_path(asset.path, 1024, path);
    char pathText[520];
    wide_to_log(path, pathText, sizeof(pathText));
    logf("sprite loaded tag=%s frames=%d first=%dx%d path=%s",
         tag, asset.frameCount, asset.frames[0].w, asset.frames[0].h, pathText);
    return true;
}

static bool load_spr(const wchar_t* path, SpriteAsset& asset, const char* tag)
{
    DWORD size = 0;
    BYTE* data = read_file_heap(path, &size);
    if (!data)
    {
        log_path("sprite open failed path=", path);
        return false;
    }

    bool ok = decode_spr_bytes(path, data, size, asset, tag);
    HeapFree(GetProcessHeap(), 0, data);
    return ok;
}

struct ActLayerLite
{
    int offsetX;
    int offsetY;
    int spriteIndex;
    bool mirror;
};

static bool clone_empty_frame(SpriteFrame* out, int w, int h)
{
    if (!out || w <= 0 || h <= 0 || w > 512 || h > 512)
        return false;
    DWORD* pixels = static_cast<DWORD*>(
        HeapAlloc(GetProcessHeap(), HEAP_ZERO_MEMORY, w * h * sizeof(DWORD)));
    if (!pixels)
        return false;
    out->w = w;
    out->h = h;
    out->pixels = pixels;
    return true;
}

static bool compose_act_frame(const SpriteAsset& spr,
                              const ActLayerLite* layers, int layerCount,
                              SpriteFrame* out)
{
    if (!layers || layerCount <= 0 || !out)
        return false;

    bool any = false;
    int minX = 0, minY = 0, maxX = 0, maxY = 0;

    for (int i = 0; i < layerCount; ++i)
    {
        int idx = layers[i].spriteIndex;
        if (idx < 0 || idx >= spr.frameCount)
            continue;
        const SpriteFrame& src = spr.frames[idx];
        if (!src.pixels || src.w <= 0 || src.h <= 0)
            continue;

        int left = layers[i].offsetX - (src.w / 2);
        int top = layers[i].offsetY - (src.h / 2);
        int right = left + src.w;
        int bottom = top + src.h;

        if (!any)
        {
            minX = left;
            minY = top;
            maxX = right;
            maxY = bottom;
            any = true;
        }
        else
        {
            if (left < minX) minX = left;
            if (top < minY) minY = top;
            if (right > maxX) maxX = right;
            if (bottom > maxY) maxY = bottom;
        }
    }

    if (!any)
        return false;

    const int margin = 6;
    int w = (maxX - minX) + margin * 2;
    int h = (maxY - minY) + margin * 2;
    if (!clone_empty_frame(out, w, h))
        return false;
    out->originX = margin - minX;
    out->originY = margin - minY;

    DWORD* dst = out->pixels;
    for (int i = 0; i < layerCount; ++i)
    {
        int idx = layers[i].spriteIndex;
        if (idx < 0 || idx >= spr.frameCount)
            continue;
        const SpriteFrame& src = spr.frames[idx];
        if (!src.pixels)
            continue;

        int left = layers[i].offsetX - (src.w / 2) - minX + margin;
        int top = layers[i].offsetY - (src.h / 2) - minY + margin;

        for (int sy = 0; sy < src.h; ++sy)
        {
            int dy = top + sy;
            if (dy < 0 || dy >= out->h)
                continue;
            for (int sx = 0; sx < src.w; ++sx)
            {
                int srcX = layers[i].mirror ? (src.w - 1 - sx) : sx;
                DWORD px = src.pixels[sy * src.w + srcX];
                if ((px >> 24) == 0)
                    continue;
                int dx = left + sx;
                if (dx < 0 || dx >= out->w)
                    continue;
                dst[dy * out->w + dx] = px;
            }
        }
    }

    return true;
}

static bool replace_ext(wchar_t* out, int outCount,
                        const wchar_t* path, const wchar_t* ext)
{
    if (!copy_path(out, outCount, path))
        return false;
    wchar_t* slash = out;
    wchar_t* dot = nullptr;
    for (wchar_t* p = out; *p; ++p)
    {
        if (*p == L'\\' || *p == L'/')
        {
            slash = p + 1;
            dot = nullptr;
        }
        else if (*p == L'.')
        {
            dot = p;
        }
    }
    if (!dot || dot < slash)
        dot = out + lstrlenW(out);
    *dot = 0;
    if (lstrlenW(out) + lstrlenW(ext) + 1 > outCount)
        return false;
    lstrcatW(out, ext);
    return true;
}

static bool decode_act_asset_bytes(const wchar_t* actPath,
                                   const BYTE* actData, DWORD actSize,
                                   const BYTE* sprData, DWORD sprSize,
                                   SpriteAsset& asset, const char* tag)
{
    free_asset(asset);

    SpriteAsset spr = {};
    wchar_t sprPath[1024] = {};
    if (!replace_ext(sprPath, 1024, actPath, L".spr") ||
        !decode_spr_bytes(sprPath, sprData, sprSize, spr, tag))
        return false;

    bool ok = false;
    if (actSize >= 16 && actData[0] == 'A' && actData[1] == 'C')
    {
        BYTE minor = actData[2];
        BYTE major = actData[3];
        bool v20Plus = (major > 2) || (major == 2 && minor >= 0);
        bool v23Plus = (major > 2) || (major == 2 && minor >= 3);
        bool v24Plus = (major > 2) || (major == 2 && minor >= 4);
        bool v25Plus = (major > 2) || (major == 2 && minor >= 5);
        bool v26Plus = (major > 2) || (major == 2 && minor >= 6);
        WORD actionCount = read_le16(actData + 4);
        DWORD off = 16;
        int actStart = env_num("BOH_DUALWPN_ACT_START", 32);
        int actEnd = env_num("BOH_DUALWPN_ACT_END", 39);
        if (actStart < 0) actStart = 0;
        if (actEnd < actStart) actEnd = actStart;

        for (WORD ai = 0; ai < actionCount && off + 4 <= actSize; ++ai)
        {
            int frameCount = read_i32(actData + off);
            off += 4;
            if (frameCount < 0 || frameCount > 512)
                break;

            for (int fi = 0; fi < frameCount && off + 36 <= actSize; ++fi)
            {
                off += 32;
                int layerCount = read_i32(actData + off);
                off += 4;
                if (layerCount < 0 || layerCount > 128)
                    break;

                ActLayerLite layers[32] = {};
                int stored = 0;

                for (int li = 0; li < layerCount; ++li)
                {
                    if (off + 16 > actSize)
                    {
                        off = actSize;
                        break;
                    }

                    int offsetX = 0;
                    int offsetY = 0;
                    if (v26Plus)
                    {
                        offsetX = static_cast<int>(read_f32(actData + off));
                        offsetY = static_cast<int>(read_f32(actData + off + 4));
                    }
                    else
                    {
                        offsetX = read_i32(actData + off);
                        offsetY = read_i32(actData + off + 4);
                    }
                    off += 8;

                    int spriteIndex = read_i32(actData + off);
                    bool mirror = read_i32(actData + off + 4) != 0;
                    off += 8;

                    int spriteType = 0;
                    if (v20Plus)
                    {
                        if (off + 16 > actSize)
                        {
                            off = actSize;
                            break;
                        }
                        off += 4; // color
                        off += 4; // scale x
                        if (v24Plus)
                            off += 4; // scale y
                        off += 4; // rotation
                        spriteType = read_i32(actData + off);
                        off += 4;
                        if (v25Plus)
                            off += 8; // width/height
                    }

                    if (spriteType == 0 && stored < 32)
                    {
                        layers[stored].offsetX = offsetX;
                        layers[stored].offsetY = offsetY;
                        layers[stored].spriteIndex = spriteIndex;
                        layers[stored].mirror = mirror;
                        ++stored;
                    }
                }

                if (v20Plus && off + 4 <= actSize)
                    off += 4; // sound id
                if (v23Plus && off + 4 <= actSize)
                {
                    int anchors = read_i32(actData + off);
                    off += 4;
                    if (anchors >= 0 && anchors <= 128 &&
                        off + static_cast<DWORD>(anchors * 16) <= actSize)
                        off += anchors * 16;
                    else
                        off = actSize;
                }

                if (ai >= actStart && ai <= actEnd &&
                    asset.frameCount < kMaxFrames && stored > 0)
                {
                    SpriteFrame frame = {};
                    if (compose_act_frame(spr, layers, stored, &frame))
                        asset.frames[asset.frameCount++] = frame;
                }
            }
        }

        ok = asset.frameCount > 0;
    }

    free_asset(spr);

    if (!ok)
    {
        log_path("act decode failed path=", actPath);
        free_asset(asset);
        return false;
    }

    copy_path(asset.path, 1024, actPath);
    char pathText[520];
    wide_to_log(actPath, pathText, sizeof(pathText));
    logf("act loaded tag=%s frames=%d first=%dx%d path=%s",
         tag, asset.frameCount, asset.frames[0].w, asset.frames[0].h,
         pathText);
    return true;
}

static bool load_act_asset(const wchar_t* actPath, SpriteAsset& asset,
                           const char* tag)
{
    wchar_t sprPath[1024] = {};
    if (!replace_ext(sprPath, 1024, actPath, L".spr"))
        return false;

    DWORD sprSize = 0;
    BYTE* sprData = read_file_heap(sprPath, &sprSize);
    if (!sprData)
    {
        log_path("sprite open failed path=", sprPath);
        return false;
    }

    DWORD actSize = 0;
    BYTE* actData = read_file_heap(actPath, &actSize);
    if (!actData)
    {
        log_path("act open failed path=", actPath);
        HeapFree(GetProcessHeap(), 0, sprData);
        return false;
    }

    bool ok = decode_act_asset_bytes(actPath, actData, actSize, sprData,
                                     sprSize, asset, tag);
    HeapFree(GetProcessHeap(), 0, actData);
    HeapFree(GetProcessHeap(), 0, sprData);
    return ok;
}

static bool ascii_eq_i(char a, char b)
{
    if (a >= 'A' && a <= 'Z')
        a = static_cast<char>(a - 'A' + 'a');
    if (b >= 'A' && b <= 'Z')
        b = static_cast<char>(b - 'A' + 'a');
    return a == b;
}

static bool suffix_match_i_a(const char* name, const char* suffix)
{
    if (!name || !suffix)
        return false;
    int nameLen = lstrlenA(name);
    int suffixLen = lstrlenA(suffix);
    if (suffixLen <= 0 || nameLen < suffixLen)
        return false;
    const char* p = name + nameLen - suffixLen;
    for (int i = 0; i < suffixLen; ++i)
    {
        if (!ascii_eq_i(p[i], suffix[i]))
            return false;
    }
    return true;
}

static bool contains_i_a(const char* text, const char* needle)
{
    if (!text || !needle || !needle[0])
        return false;
    int textLen = lstrlenA(text);
    int needleLen = lstrlenA(needle);
    if (needleLen > textLen)
        return false;
    for (int i = 0; i <= textLen - needleLen; ++i)
    {
        bool ok = true;
        for (int j = 0; j < needleLen; ++j)
        {
            if (!ascii_eq_i(text[i + j], needle[j]))
            {
                ok = false;
                break;
            }
        }
        if (ok)
            return true;
    }
    return false;
}

static bool same_i_a(const char* a, const char* b)
{
    if (!a || !b)
        return false;
    int al = lstrlenA(a);
    int bl = lstrlenA(b);
    if (al != bl)
        return false;
    for (int i = 0; i < al; ++i)
    {
        if (!ascii_eq_i(a[i], b[i]))
            return false;
    }
    return true;
}

static bool copy_entry_path(char* out, int outCount,
                            const BYTE* data, int len)
{
    if (!out || outCount <= 0 || !data || len <= 0 || len >= outCount)
        return false;
    for (int i = 0; i < len; ++i)
        out[i] = static_cast<char>(data[i]);
    out[len] = 0;
    return true;
}

static void replace_ext_a(char* path, int pathCount, const char* ext)
{
    if (!path || !ext || pathCount <= 0)
        return;
    char* slash = path;
    char* dot = nullptr;
    for (char* p = path; *p; ++p)
    {
        if (*p == '\\' || *p == '/')
        {
            slash = p + 1;
            dot = nullptr;
        }
        else if (*p == '.')
        {
            dot = p;
        }
    }
    if (!dot || dot < slash)
        dot = path + lstrlenA(path);
    *dot = 0;
    if (lstrlenA(path) + lstrlenA(ext) + 1 < pathCount)
        lstrcatA(path, ext);
}

static bool grf_name_char(BYTE c)
{
    return (c >= 'a' && c <= 'z') ||
           (c >= 'A' && c <= 'Z') ||
           (c >= '0' && c <= '9') ||
           c == '_' || c == '-' || c == '.' ||
           c == '\\' || c == '/';
}

static int add_grf_path(wchar_t paths[][1024], int count, int maxCount,
                        const wchar_t* name)
{
    if (!name || !name[0] || count >= maxCount)
        return count;

    wchar_t full[1024] = {};
    if (is_absolute_path(name))
    {
        if (!copy_path(full, 1024, name))
            return count;
    }
    else
    {
        wchar_t exeDir[1024];
        get_exe_dir(exeDir, 1024);
        if (!join_path(full, 1024, exeDir, name))
            return count;
    }

    for (int i = 0; i < count; ++i)
    {
        if (_wcsicmp(paths[i], full) == 0)
            return count;
    }

    DWORD attr = GetFileAttributesW(full);
    if (attr == INVALID_FILE_ATTRIBUTES ||
        (attr & FILE_ATTRIBUTE_DIRECTORY))
        return count;

    copy_path(paths[count], 1024, full);
    return count + 1;
}

static int load_grf_list_from_data_ini(wchar_t paths[][1024], int maxCount)
{
    wchar_t exeDir[1024];
    wchar_t iniPath[1024];
    get_exe_dir(exeDir, 1024);
    if (!join_path(iniPath, 1024, exeDir, L"DATA.INI"))
        return 0;

    DWORD attr = GetFileAttributesW(iniPath);
    if (attr == INVALID_FILE_ATTRIBUTES ||
        (attr & FILE_ATTRIBUTE_DIRECTORY))
        return 0;

    int count = 0;
    for (int i = 0; i < 100 && count < maxCount; ++i)
    {
        wchar_t key[16];
        wchar_t value[260] = {};
        wsprintfW(key, L"%d", i);
        GetPrivateProfileStringW(L"Data", key, L"", value, 260, iniPath);
        if (value[0])
            count = add_grf_path(paths, count, maxCount, value);
    }
    if (count > 0)
        logf("grf list source=DATA.INI count=%d", count);
    return count;
}

static int load_grf_list_from_exe_strings(wchar_t paths[][1024], int maxCount)
{
    wchar_t exePath[1024] = {};
    GetModuleFileNameW(nullptr, exePath, 1024);

    DWORD size = 0;
    BYTE* data = read_file_heap(exePath, &size);
    if (!data)
        return 0;

    int count = 0;
    for (DWORD i = 0; i + 4 <= size && count < maxCount; ++i)
    {
        if (!ascii_eq_i(static_cast<char>(data[i]), '.') ||
            !ascii_eq_i(static_cast<char>(data[i + 1]), 'g') ||
            !ascii_eq_i(static_cast<char>(data[i + 2]), 'r') ||
            !ascii_eq_i(static_cast<char>(data[i + 3]), 'f'))
            continue;

        DWORD begin = i;
        while (begin > 0 && grf_name_char(data[begin - 1]))
            --begin;

        DWORD end = i + 4;
        while (end < size && grf_name_char(data[end]))
            ++end;

        DWORD len = end - begin;
        if (len == 0 || len >= 260)
            continue;

        char raw[260] = {};
        for (DWORD j = 0; j < len; ++j)
            raw[j] = static_cast<char>(data[begin + j]);
        raw[len] = 0;

        if (!suffix_match_i_a(raw, ".grf"))
            continue;

        wchar_t wide[260] = {};
        if (!MultiByteToWideChar(CP_ACP, 0, raw, -1, wide, 260))
            continue;

        int before = count;
        count = add_grf_path(paths, count, maxCount, wide);
        if (count != before)
            i = end;
    }

    HeapFree(GetProcessHeap(), 0, data);
    if (count > 0)
        logf("grf list source=embedded-exe count=%d", count);
    return count;
}

static int load_default_grf_list(wchar_t paths[][1024], int maxCount)
{
    static const wchar_t* defaults[] = {
        L"update.grf",
        L"maindata.grf",
        L"mapdata.grf",
        L"palettedata.grf",
        L"spritedata.grf",
        L"data.grf",
        L"greyworld.grf",
        L"rdata.grf",
        L"sdata.grf"
    };

    int count = 0;
    for (int i = 0; i < static_cast<int>(sizeof(defaults) / sizeof(defaults[0])); ++i)
        count = add_grf_path(paths, count, maxCount, defaults[i]);
    if (count > 0)
        logf("grf list source=default count=%d", count);
    return count;
}

static int load_grf_list(wchar_t paths[][1024], int maxCount)
{
    int count = load_grf_list_from_data_ini(paths, maxCount);
    if (count > 0)
        return count;

    count = load_grf_list_from_exe_strings(paths, maxCount);
    if (count > 0)
        return count;

    return load_default_grf_list(paths, maxCount);
}

typedef int (__cdecl *CpsUncompressFn)(BYTE* outData, int* outLen,
                                       const BYTE* compData, int compLen);

static HMODULE g_cpsModule = nullptr;
static CpsUncompressFn g_cpsUncompress = nullptr;
static bool g_cpsTried = false;

static FARPROC get_proc_any(HMODULE mod, const char* name)
{
    if (!mod || !name || !name[0])
        return nullptr;

    FARPROC p = GetProcAddress(mod, name);
    if (p)
        return p;

    char tmp[96] = {};
    wsprintfA(tmp, "_%s", name);
    p = GetProcAddress(mod, tmp);
    if (p)
        return p;

    wsprintfA(tmp, "%s@16", name);
    p = GetProcAddress(mod, tmp);
    if (p)
        return p;

    wsprintfA(tmp, "_%s@16", name);
    return GetProcAddress(mod, tmp);
}

static bool resolve_cps_uncompress()
{
    if (g_cpsUncompress)
        return true;
    if (g_cpsTried)
        return false;
    g_cpsTried = true;

    g_cpsModule = GetModuleHandleW(L"cps.dll");
    if (!g_cpsModule)
    {
        wchar_t exeDir[1024];
        wchar_t cpsPath[1024];
        get_exe_dir(exeDir, 1024);
        if (join_path(cpsPath, 1024, exeDir, L"cps.dll"))
            g_cpsModule = LoadLibraryW(cpsPath);
    }
    if (!g_cpsModule)
        g_cpsModule = LoadLibraryW(L"cps.dll");
    if (!g_cpsModule)
    {
        logf("grf cps missing");
        return false;
    }

    FARPROC p = get_proc_any(g_cpsModule, "uncompress");
    if (!p)
        p = GetProcAddress(g_cpsModule, MAKEINTRESOURCEA(2));
    if (!p)
    {
        logf("grf cps uncompress missing");
        return false;
    }

    g_cpsUncompress = reinterpret_cast<CpsUncompressFn>(p);
    logf("grf cps resolved");
    return true;
}

static BYTE* grf_decompress_block(const BYTE* comp, DWORD compSize,
                                  DWORD alignedSize, DWORD decompSize,
                                  DWORD* outSize)
{
    *outSize = 0;
    if (!comp || compSize == 0 || decompSize == 0 ||
        decompSize > 64 * 1024 * 1024 ||
        !resolve_cps_uncompress())
        return nullptr;

    BYTE* out = static_cast<BYTE*>(
        HeapAlloc(GetProcessHeap(), 0, decompSize));
    if (!out)
        return nullptr;

    int outLen = static_cast<int>(decompSize);
    int rc = g_cpsUncompress(out, &outLen, comp, static_cast<int>(compSize));
    if (rc != 0 && alignedSize != compSize)
    {
        outLen = static_cast<int>(decompSize);
        rc = g_cpsUncompress(out, &outLen, comp,
                             static_cast<int>(alignedSize));
    }

    if (rc != 0 || outLen <= 0 || static_cast<DWORD>(outLen) > decompSize)
    {
        HeapFree(GetProcessHeap(), 0, out);
        return nullptr;
    }

    *outSize = static_cast<DWORD>(outLen);
    return out;
}

static bool read_at(HANDLE h, ULONGLONG offset, void* out, DWORD size)
{
    LARGE_INTEGER pos;
    pos.QuadPart = static_cast<LONGLONG>(offset);
    if (!SetFilePointerEx(h, pos, nullptr, FILE_BEGIN))
        return false;

    DWORD got = 0;
    return ReadFile(h, out, size, &got, nullptr) && got == size;
}

static ULONGLONG read_le64(const BYTE* p)
{
    ULONGLONG lo = read_le32(p);
    ULONGLONG hi = read_le32(p + 4);
    return lo | (hi << 32);
}

struct GrfHeaderLite
{
    int major;
    int minor;
    int version;
    ULONGLONG tableOffset;
};

struct GrfEntryLite
{
    char path[520];
    DWORD sizeCompressed;
    DWORD sizeAligned;
    DWORD sizeDecompressed;
    BYTE flags;
    ULONGLONG fileOffset;
    int score;
};

static bool grf_read_header(HANDLE h, GrfHeaderLite* out)
{
    BYTE hdr[46] = {};
    if (!read_at(h, 0, hdr, sizeof(hdr)))
        return false;
    if (memcmp(hdr, "Master of Magic", 15) != 0)
        return false;

    DWORD version = read_le32(hdr + 42);
    out->major = static_cast<int>((version >> 8) & 0xFF);
    out->minor = static_cast<int>(version & 0xFF);
    out->version = out->major * 100 + out->minor;

    if (out->major == 3 && out->minor == 0 &&
        hdr[35] == 0 && hdr[36] == 0 && hdr[37] == 0)
        out->tableOffset = read_le64(hdr + 30) + 46;
    else
        out->tableOffset = read_le32(hdr + 30) + 46;

    return out->major == 2 || out->major == 3;
}

static bool grf_read_table(HANDLE h, const GrfHeaderLite& hdr,
                           BYTE** outTable, DWORD* outTableSize)
{
    *outTable = nullptr;
    *outTableSize = 0;

    ULONGLONG pos = hdr.tableOffset;
    BYTE sizes[12] = {};
    DWORD sizeBytes = (hdr.major == 3) ? 12 : 8;
    if (!read_at(h, pos, sizes, sizeBytes))
        return false;

    DWORD compSize = 0;
    DWORD tableSize = 0;
    if (hdr.major == 3)
    {
        compSize = read_le32(sizes + 4);
        tableSize = read_le32(sizes + 8);
        pos += 12;
    }
    else
    {
        compSize = read_le32(sizes);
        tableSize = read_le32(sizes + 4);
        pos += 8;
    }

    if (compSize == 0 || tableSize == 0 ||
        compSize > 64 * 1024 * 1024 ||
        tableSize > 96 * 1024 * 1024)
        return false;

    BYTE* comp = static_cast<BYTE*>(
        HeapAlloc(GetProcessHeap(), 0, compSize));
    if (!comp)
        return false;
    if (!read_at(h, pos, comp, compSize))
    {
        HeapFree(GetProcessHeap(), 0, comp);
        return false;
    }

    DWORD got = 0;
    BYTE* table = grf_decompress_block(comp, compSize, compSize,
                                       tableSize, &got);
    HeapFree(GetProcessHeap(), 0, comp);
    if (!table || got < tableSize)
    {
        if (table)
            HeapFree(GetProcessHeap(), 0, table);
        return false;
    }

    *outTable = table;
    *outTableSize = tableSize;
    return true;
}

static int path_token_score(const char* path)
{
    int score = 0;

    char pref[160] = {};
    DWORD got = GetEnvironmentVariableA("BOH_DUALWPN_GRF_PREF",
                                        pref, sizeof(pref));
    if (got > 0 && got < sizeof(pref))
    {
        char token[64] = {};
        int tokenLen = 0;
        int rank = 0;
        for (DWORD i = 0; ; ++i)
        {
            char c = pref[i];
            bool end = c == 0 || c == ';' || c == ',';
            if (!end && tokenLen < static_cast<int>(sizeof(token)) - 1)
                token[tokenLen++] = c;
            if (end)
            {
                token[tokenLen] = 0;
                if (token[0] && contains_i_a(path, token))
                    score += 8000 - (rank * 100);
                tokenLen = 0;
                ++rank;
            }
            if (c == 0)
                break;
        }
    }
    else
    {
        static const char kAssassin[] =
            "\xBE\xEE\xBC\xBC\xBD\xC5";
        if (contains_i_a(path, "shadow_cross"))
            score += 6000;
        if (contains_i_a(path, kAssassin))
            score += 5900;
        if (contains_i_a(path, "assassin"))
            score += 5800;
    }

    char gender[32] = {};
    got = GetEnvironmentVariableA("BOH_DUALWPN_GRF_GENDER",
                                  gender, sizeof(gender));
    bool female = got > 0 && got < sizeof(gender) &&
                  contains_i_a(gender, "female");
    static const char kMale[] = "_\xB3\xB2_";
    static const char kFemale[] = "_\xBF\xA9_";
    if (female)
    {
        if (contains_i_a(path, kFemale))
            score += 1000;
    }
    else
    {
        if (contains_i_a(path, kMale))
            score += 1000;
    }

    if (contains_i_a(path, "data\\sprite\\"))
        score += 10;
    return score;
}

static bool better_grf_entry(const GrfEntryLite& candidate,
                             bool haveBest,
                             const GrfEntryLite& best)
{
    if (!haveBest)
        return true;
    if (candidate.score != best.score)
        return candidate.score > best.score;
    if (candidate.sizeDecompressed != best.sizeDecompressed)
        return candidate.sizeDecompressed < best.sizeDecompressed;
    return lstrcmpiA(candidate.path, best.path) < 0;
}

static void table_find_entries(const BYTE* table, DWORD tableSize, int version,
                               const char* actSuffix,
                               GrfEntryLite* bestAct, bool* haveAct,
                               GrfEntryLite* bestSpr, bool* haveSpr)
{
    DWORD pos = 0;
    int entrySize = (version == 300) ? 21 : 17;
    char sprSuffix[64] = {};
    lstrcpynA(sprSuffix, actSuffix, sizeof(sprSuffix));
    replace_ext_a(sprSuffix, sizeof(sprSuffix), ".spr");

    while (pos < tableSize)
    {
        DWORD nameStart = pos;
        while (pos < tableSize && table[pos] != 0)
            ++pos;
        if (pos >= tableSize)
            break;

        DWORD nameLen = pos - nameStart;
        ++pos;
        if (pos + static_cast<DWORD>(entrySize) > tableSize)
            break;

        GrfEntryLite entry = {};
        if (!copy_entry_path(entry.path, sizeof(entry.path),
                             table + nameStart, static_cast<int>(nameLen)))
        {
            pos += entrySize;
            continue;
        }

        entry.sizeCompressed = read_le32(table + pos);
        entry.sizeAligned = read_le32(table + pos + 4);
        entry.sizeDecompressed = read_le32(table + pos + 8);
        entry.flags = table[pos + 12];
        if (version == 300)
            entry.fileOffset = read_le64(table + pos + 13) + 46;
        else
            entry.fileOffset = read_le32(table + pos + 13) + 46;
        pos += entrySize;

        if ((entry.flags & 0x01) == 0 || (entry.flags & 0x80) != 0)
            continue;
        if (entry.sizeCompressed == 0 || entry.sizeAligned == 0 ||
            entry.sizeDecompressed == 0 ||
            entry.sizeDecompressed > 32 * 1024 * 1024)
            continue;

        entry.score = path_token_score(entry.path);
        if (suffix_match_i_a(entry.path, actSuffix))
        {
            if (better_grf_entry(entry, *haveAct, *bestAct))
            {
                *bestAct = entry;
                *haveAct = true;
            }
        }
        else if (suffix_match_i_a(entry.path, sprSuffix))
        {
            if (better_grf_entry(entry, *haveSpr, *bestSpr))
            {
                *bestSpr = entry;
                *haveSpr = true;
            }
        }
    }
}

static bool table_find_exact_entry(const BYTE* table, DWORD tableSize,
                                   int version, const char* exactPath,
                                   GrfEntryLite* out)
{
    DWORD pos = 0;
    int entrySize = (version == 300) ? 21 : 17;
    while (pos < tableSize)
    {
        DWORD nameStart = pos;
        while (pos < tableSize && table[pos] != 0)
            ++pos;
        if (pos >= tableSize)
            break;

        DWORD nameLen = pos - nameStart;
        ++pos;
        if (pos + static_cast<DWORD>(entrySize) > tableSize)
            break;

        char path[520] = {};
        if (!copy_entry_path(path, sizeof(path), table + nameStart,
                             static_cast<int>(nameLen)))
        {
            pos += entrySize;
            continue;
        }

        if (same_i_a(path, exactPath))
        {
            ZeroMemory(out, sizeof(*out));
            lstrcpynA(out->path, path, sizeof(out->path));
            out->sizeCompressed = read_le32(table + pos);
            out->sizeAligned = read_le32(table + pos + 4);
            out->sizeDecompressed = read_le32(table + pos + 8);
            out->flags = table[pos + 12];
            if (version == 300)
                out->fileOffset = read_le64(table + pos + 13) + 46;
            else
                out->fileOffset = read_le32(table + pos + 13) + 46;
            out->score = path_token_score(out->path);
            return (out->flags & 0x01) != 0 && (out->flags & 0x80) == 0;
        }

        pos += entrySize;
    }
    return false;
}

static BYTE* read_grf_entry(HANDLE h, const GrfEntryLite& entry,
                            DWORD* outSize)
{
    *outSize = 0;
    if (entry.sizeAligned == 0 || entry.sizeAligned > 32 * 1024 * 1024 ||
        entry.sizeDecompressed == 0 ||
        entry.sizeDecompressed > 32 * 1024 * 1024)
        return nullptr;

    BYTE* comp = static_cast<BYTE*>(
        HeapAlloc(GetProcessHeap(), 0, entry.sizeAligned));
    if (!comp)
        return nullptr;

    if (!read_at(h, entry.fileOffset, comp, entry.sizeAligned))
    {
        HeapFree(GetProcessHeap(), 0, comp);
        return nullptr;
    }

    BYTE* out = nullptr;
    if ((entry.flags & 0x800) != 0)
    {
        out = static_cast<BYTE*>(
            HeapAlloc(GetProcessHeap(), 0, entry.sizeDecompressed));
        if (out)
        {
            CopyMemory(out, comp, entry.sizeDecompressed);
            *outSize = entry.sizeDecompressed;
        }
    }
    else
    {
        out = grf_decompress_block(comp, entry.sizeCompressed,
                                   entry.sizeAligned,
                                   entry.sizeDecompressed, outSize);
    }

    HeapFree(GetProcessHeap(), 0, comp);
    return out;
}

static void entry_to_wide_path(const wchar_t* grfPath, const char* entryPath,
                               wchar_t* out, int outCount)
{
    if (!out || outCount <= 0)
        return;
    out[0] = 0;

    wchar_t entryWide[620] = {};
    if (!MultiByteToWideChar(CP_ACP, 0, entryPath, -1,
                             entryWide, 620))
        lstrcpynW(entryWide, L"<entry>", 620);

    lstrcpynW(out, grfPath, outCount);
    if (lstrlenW(out) + 1 < outCount)
        lstrcatW(out, L"|");
    if (lstrlenW(out) + lstrlenW(entryWide) + 1 < outCount)
        lstrcatW(out, entryWide);
}

static bool load_grf_asset_from_file(const wchar_t* grfPath, DWORD item,
                                     SpriteAsset& asset, const char* tag)
{
    HANDLE h = CreateFileW(grfPath, GENERIC_READ,
                           FILE_SHARE_READ | FILE_SHARE_WRITE |
                               FILE_SHARE_DELETE,
                           nullptr, OPEN_EXISTING,
                           FILE_ATTRIBUTE_NORMAL, nullptr);
    if (h == INVALID_HANDLE_VALUE)
        return false;

    GrfHeaderLite hdr = {};
    BYTE* table = nullptr;
    DWORD tableSize = 0;
    bool ok = false;
    char actSuffix[64] = {};
    GrfEntryLite act = {};
    GrfEntryLite spr = {};
    GrfEntryLite exact = {};
    bool haveAct = false;
    bool haveSpr = false;
    char exactSpr[520] = {};
    DWORD actSize = 0;
    DWORD sprSize = 0;
    BYTE* actData = nullptr;
    BYTE* sprData = nullptr;
    wchar_t displayPath[1024] = {};
    char grfText[520] = {};
    char actText[520] = {};
    char sprText[520] = {};

    if (!grf_read_header(h, &hdr) ||
        !grf_read_table(h, hdr, &table, &tableSize))
        goto done;

    wsprintfA(actSuffix, "_%u.act", item);

    table_find_entries(table, tableSize, hdr.version, actSuffix,
                       &act, &haveAct, &spr, &haveSpr);
    if (!haveAct)
        goto done;

    lstrcpynA(exactSpr, act.path, sizeof(exactSpr));
    replace_ext_a(exactSpr, sizeof(exactSpr), ".spr");
    if (table_find_exact_entry(table, tableSize, hdr.version, exactSpr, &exact))
    {
        spr = exact;
        haveSpr = true;
    }
    if (!haveSpr)
        goto done;

    actData = read_grf_entry(h, act, &actSize);
    sprData = read_grf_entry(h, spr, &sprSize);
    if (!actData || !sprData)
        goto done;

    entry_to_wide_path(grfPath, act.path, displayPath, 1024);
    ok = decode_act_asset_bytes(displayPath, actData, actSize, sprData,
                                sprSize, asset, tag);

    wide_to_log(grfPath, grfText, sizeof(grfText));
    lstrcpynA(actText, act.path, sizeof(actText));
    lstrcpynA(sprText, spr.path, sizeof(sprText));
    logf("grf asset tag=%s item=%u loaded=%u grf=%s act=%s spr=%s",
         tag, item, ok ? 1 : 0, grfText, actText, sprText);

done:
    if (actData)
        HeapFree(GetProcessHeap(), 0, actData);
    if (sprData)
        HeapFree(GetProcessHeap(), 0, sprData);
    if (table)
        HeapFree(GetProcessHeap(), 0, table);
    CloseHandle(h);
    return ok;
}

static bool load_grf_asset_for_item(DWORD item, SpriteAsset& asset,
                                    const char* tag)
{
    wchar_t grfs[32][1024] = {};
    int count = load_grf_list(grfs, 32);
    for (int i = 0; i < count; ++i)
    {
        if (load_grf_asset_from_file(grfs[i], item, asset, tag))
            return true;
    }

    logf("grf sprite missing tag=%s item=%u searched=%d",
         tag, item, count);
    return false;
}

static bool load_asset_for_item(const char* actEnvName, const char* sprEnvName,
                                DWORD item,
                                SpriteAsset& asset, const char* tag)
{
    wchar_t path[1024] = {};
    if (env_path(actEnvName, path, 1024) && load_act_asset(path, asset, tag))
        return true;

    if (env_path(sprEnvName, path, 1024) && load_spr(path, asset, tag))
        return true;

    if (item != 0 && load_grf_asset_for_item(item, asset, tag))
        return true;

    if (item != 0)
    {
        wchar_t suffix[64] = {};
        wsprintfW(suffix, L"_%u.act", item);
        if (find_best_sprite(suffix, path, 1024) &&
            load_act_asset(path, asset, tag))
            return true;

        wsprintfW(suffix, L"_%u.spr", item);
        if (find_best_sprite(suffix, path, 1024) &&
            load_spr(path, asset, tag))
            return true;

        wsprintfW(suffix, L"%u.spr", item);
        if (find_best_sprite(suffix, path, 1024) &&
            load_spr(path, asset, tag))
            return true;
    }

    if (g_allowFallbackAssets && find_best_sprite(
            (lstrcmpA(tag, "off") == 0) ? L"DRAKEDAGGER_BLUE.spr" :
                                           L"DRAKESWORD_BLUE.spr",
            path, 1024) &&
        load_spr(path, asset, tag))
        return true;

    logf("sprite missing tag=%s item=%u", tag, item);
    return false;
}

static void load_assets_for_state(DWORD mainItem, DWORD offItem)
{
    g_spriteScale = env_num("BOH_DUALWPN_SPR_SCALE", 1);
    if (g_spriteScale < 1)
        g_spriteScale = 1;
    if (g_spriteScale > 4)
        g_spriteScale = 4;
    g_hideWhenInactive = env_flag("BOH_DUALWPN_HIDE_INACTIVE", true);
    g_allowFallbackAssets = env_flag("BOH_DUALWPN_ALLOW_FALLBACK_SPR", false);

    if (mainItem != g_loadedMainItem)
    {
        free_asset(g_mainSprite);
        g_loadedMainItem = mainItem;
        bool mainOk = mainItem != 0 &&
            load_asset_for_item("BOH_DUALWPN_MAIN_ACT",
                                "BOH_DUALWPN_MAIN_SPR",
                                mainItem, g_mainSprite, "main");
        logf("sprite asset main item=%u loaded=%u scale=%d",
             mainItem, mainOk ? 1 : 0, g_spriteScale);
    }

    if (offItem != g_loadedOffItem)
    {
        free_asset(g_offSprite);
        g_loadedOffItem = offItem;
        bool offOk = offItem != 0 &&
            load_asset_for_item("BOH_DUALWPN_OFF_ACT",
                                "BOH_DUALWPN_OFF_SPR",
                                offItem, g_offSprite, "off");
        logf("sprite asset off item=%u loaded=%u scale=%d",
             offItem, offOk ? 1 : 0, g_spriteScale);
    }
}

static int state_ttl_ms()
{
    int ttlMs = env_num("BOH_DUALWPN_STATE_TTL_MS", 120000);
    if (ttlMs < 1000)
        ttlMs = 1000;
    if (ttlMs > 600000)
        ttlMs = 600000;
    return ttlMs;
}

static void destroy_gdi()
{
    if (g_memDC && g_oldBmp)
    {
        SelectObject(g_memDC, g_oldBmp);
        g_oldBmp = nullptr;
    }
    if (g_hbm)
    {
        DeleteObject(g_hbm);
        g_hbm = nullptr;
    }
    if (g_memDC)
    {
        DeleteDC(g_memDC);
        g_memDC = nullptr;
    }
    g_bits = nullptr;
}

static void destroy_window()
{
    if (g_overlayWnd && IsWindow(g_overlayWnd))
    {
        ShowWindow(g_overlayWnd, SW_HIDE);
        DestroyWindow(g_overlayWnd);
    }
    g_overlayWnd = nullptr;
    g_ownerWnd = nullptr;

    if (g_classRegistered)
    {
        UnregisterClassA(kClassName, g_module);
        g_classRegistered = false;
    }
}

static bool ensure_window(HWND gameWnd)
{
    if (g_overlayWnd && IsWindow(g_overlayWnd) && g_ownerWnd == gameWnd)
        return true;

    if (g_overlayWnd)
        destroy_window();

    if (!g_classRegistered)
    {
        WNDCLASSA wc = {};
        wc.lpfnWndProc = DefWindowProcA;
        wc.hInstance = g_module;
        wc.lpszClassName = kClassName;
        if (!RegisterClassA(&wc) && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
        {
            logf("RegisterClass failed err=%lu", GetLastError());
            return false;
        }
        g_classRegistered = true;
    }

    g_overlayWnd = CreateWindowExA(
        WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW,
        kClassName, "",
        WS_POPUP,
        0, 0, kOverlayW, kOverlayH,
        gameWnd, nullptr, g_module, nullptr);

    if (!g_overlayWnd)
    {
        logf("CreateWindowEx failed err=%lu", GetLastError());
        return false;
    }

    g_ownerWnd = gameWnd;
    logf("overlay window created hwnd=%p owner=%p", g_overlayWnd, g_ownerWnd);
    return true;
}

static bool ensure_dib(HDC screenDC)
{
    if (g_bits)
        return true;

    g_memDC = CreateCompatibleDC(screenDC);
    if (!g_memDC)
        return false;

    BITMAPINFO bmi = {};
    bmi.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bmi.bmiHeader.biWidth = kOverlayW;
    bmi.bmiHeader.biHeight = -kOverlayH;
    bmi.bmiHeader.biPlanes = 1;
    bmi.bmiHeader.biBitCount = 32;
    bmi.bmiHeader.biCompression = BI_RGB;

    g_hbm = CreateDIBSection(g_memDC, &bmi, DIB_RGB_COLORS,
                             &g_bits, nullptr, 0);
    if (!g_hbm || !g_bits)
    {
        destroy_gdi();
        return false;
    }

    g_oldBmp = SelectObject(g_memDC, g_hbm);
    return true;
}

struct FindWindowCtx
{
    DWORD pid;
    HWND hwnd;
    char title[256];
};

static BOOL CALLBACK enum_game_window(HWND hwnd, LPARAM param)
{
    FindWindowCtx* ctx = reinterpret_cast<FindWindowCtx*>(param);
    if (hwnd == g_overlayWnd || !IsWindowVisible(hwnd))
        return TRUE;

    DWORD pid = 0;
    GetWindowThreadProcessId(hwnd, &pid);
    if (pid != ctx->pid)
        return TRUE;

    char className[64] = {};
    GetClassNameA(hwnd, className, sizeof(className));
    if (lstrcmpA(className, kClassName) == 0)
        return TRUE;

    char title[256] = {};
    GetWindowTextA(hwnd, title, sizeof(title));
    if (!title[0])
        return TRUE;

    ctx->hwnd = hwnd;
    lstrcpynA(ctx->title, title, sizeof(ctx->title));
    return title[0] ? FALSE : TRUE;
}

static HWND find_game_window()
{
    DWORD pid = GetCurrentProcessId();
    HWND hwnd = FindWindowA(nullptr, "Banquet of Heroes: Ragnarok Online");
    if (hwnd)
    {
        DWORD windowPid = 0;
        GetWindowThreadProcessId(hwnd, &windowPid);
        if (windowPid == pid)
            return hwnd;
    }

    FindWindowCtx ctx = { pid, nullptr, "" };
    EnumWindows(enum_game_window, reinterpret_cast<LPARAM>(&ctx));
    if (ctx.hwnd)
        logf("found game window fallback hwnd=%p title=\"%s\"",
             ctx.hwnd, ctx.title);
    return ctx.hwnd;
}

static bool foreground_is_game(HWND gameWnd)
{
    if (!g_hideWhenInactive)
        return true;

    HWND fg = GetForegroundWindow();
    if (!fg)
        return false;
    if (fg == gameWnd)
        return true;

    HWND root = GetAncestor(fg, GA_ROOT);
    HWND owner = GetAncestor(fg, GA_ROOTOWNER);
    return root == gameWnd || owner == gameWnd;
}

static bool get_active_state(OverlayState* out)
{
    if (!out)
        return false;

    LONG seqA = InterlockedCompareExchange(&g_state.seq, 0, 0);
    out->tick = g_state.tick;
    out->charObj = g_state.charObj;
    out->mode = g_state.mode;
    out->mainItem = g_state.mainItem;
    out->offItem = g_state.offItem;
    out->mainView = g_state.mainView;
    out->offView = g_state.offView;
    LONG seqB = InterlockedCompareExchange(&g_state.seq, 0, 0);
    if (seqA != seqB)
        return false;

    DWORD age = GetTickCount() - out->tick;
    if (age > static_cast<DWORD>(state_ttl_ms()))
        return false;
    if (out->mode != 2 && out->mode != 9)
        return false;
    if (out->mainItem == 0 && out->offItem == 0)
        return false;

    // Keep this renderer scoped to dual/offhand cases. Main-only rendering is
    // not the bug being solved, and it would make false positives much louder.
    return out->mode == 9 || out->offItem != 0;
}

static const char* get_state_status(OverlayState* out, DWORD* ageOut)
{
    if (ageOut)
        *ageOut = 0;
    if (!out)
        return "bad-output";

    LONG seqA = InterlockedCompareExchange(&g_state.seq, 0, 0);
    out->tick = g_state.tick;
    out->charObj = g_state.charObj;
    out->mode = g_state.mode;
    out->mainItem = g_state.mainItem;
    out->offItem = g_state.offItem;
    out->mainView = g_state.mainView;
    out->offView = g_state.offView;
    LONG seqB = InterlockedCompareExchange(&g_state.seq, 0, 0);
    if (seqA != seqB)
        return "seq-race";

    if (out->tick == 0)
        return "never-updated";

    DWORD age = GetTickCount() - out->tick;
    if (ageOut)
        *ageOut = age;
    if (age > static_cast<DWORD>(state_ttl_ms()))
        return "stale";
    if (out->mode != 2 && out->mode != 9)
        return "bad-mode";
    if (out->mainItem == 0 && out->offItem == 0)
        return "empty-items";
    if (!(out->mode == 9 || out->offItem != 0))
        return "not-dual";
    return "ok";
}

static bool should_show_overlay(HWND gameWnd)
{
    OverlayState state = {};
    return get_active_state(&state) &&
           gameWnd && IsWindow(gameWnd) && IsWindowVisible(gameWnd) &&
           !IsIconic(gameWnd) && foreground_is_game(gameWnd);
}

static void hide_overlay()
{
    if (g_overlayWnd && IsWindow(g_overlayWnd) && IsWindowVisible(g_overlayWnd))
        ShowWindow(g_overlayWnd, SW_HIDE);
}

static void draw_marker()
{
    memset(g_bits, 0, kOverlayW * kOverlayH * 4);
    DWORD* pix = reinterpret_cast<DWORD*>(g_bits);

    int left = (kOverlayW / 2) - 24;
    int top = (kOverlayH / 2) - 24;
    for (int y = 0; y < 48; ++y)
    {
        for (int x = 0; x < 48; ++x)
        {
            bool border = x < 3 || x >= 45 || y < 3 || y >= 45;
            bool slash = (x == y) || (x == (47 - y));
            if (border || slash)
                pix[(top + y) * kOverlayW + (left + x)] =
                    border ? 0xD000E0FF : 0xD0FF4040;
        }
    }
}

static void draw_sprite_frame(const SpriteFrame& frame, int dstX, int dstY,
                              int scale)
{
    if (!frame.pixels || frame.w <= 0 || frame.h <= 0)
        return;

    DWORD* dst = reinterpret_cast<DWORD*>(g_bits);
    for (int sy = 0; sy < frame.h; ++sy)
    {
        for (int sx = 0; sx < frame.w; ++sx)
        {
            DWORD src = frame.pixels[sy * frame.w + sx];
            if ((src >> 24) == 0)
                continue;

            int baseX = dstX + sx * scale;
            int baseY = dstY + sy * scale;
            for (int yy = 0; yy < scale; ++yy)
            {
                int py = baseY + yy;
                if (py < 0 || py >= kOverlayH)
                    continue;
                for (int xx = 0; xx < scale; ++xx)
                {
                    int px = baseX + xx;
                    if (px < 0 || px >= kOverlayW)
                        continue;
                    dst[py * kOverlayW + px] = src;
                }
            }
        }
    }
}

static bool draw_asset(SpriteAsset& asset, int centerX, int centerY,
                       DWORD ticks)
{
    if (asset.frameCount <= 0)
        return false;

    int frameMs = env_num("BOH_DUALWPN_FRAME_MS", 180);
    if (frameMs < 60)
        frameMs = 60;
    if (frameMs > 1000)
        frameMs = 1000;

    int idx = static_cast<int>((ticks / static_cast<DWORD>(frameMs)) %
                               static_cast<DWORD>(asset.frameCount));
    SpriteFrame& frame = asset.frames[idx];
    draw_sprite_frame(frame, centerX - (frame.originX * g_spriteScale),
                      centerY - (frame.originY * g_spriteScale),
                      g_spriteScale);
    return true;
}

static int clamp_anchor(int value, int minValue, int maxValue)
{
    if (value < minValue)
        return minValue;
    if (value > maxValue)
        return maxValue;
    return value;
}

static bool draw_scene()
{
    memset(g_bits, 0, kOverlayW * kOverlayH * 4);

    OverlayState state = {};
    if (!get_active_state(&state))
        return false;

    load_assets_for_state(state.mainItem, state.offItem);

    DWORD ticks = GetTickCount();
    int baseX = (kOverlayW / 2) + env_num("BOH_DUALWPN_ANCHOR_X", 0);
    int baseY = (kOverlayH / 2) + env_num("BOH_DUALWPN_ANCHOR_Y", 30);
    int gap = env_num("BOH_DUALWPN_HAND_GAP", 24);
    if (gap < 0)
        gap = -gap;
    if (gap > 120)
        gap = 120;
    baseX = clamp_anchor(baseX, -128, kOverlayW + 128);
    baseY = clamp_anchor(baseY, -128, kOverlayH + 160);
    int mainX = baseX + env_num("BOH_DUALWPN_MAIN_X", -gap);
    int mainY = baseY + env_num("BOH_DUALWPN_MAIN_Y", 0);
    int offX = baseX + env_num("BOH_DUALWPN_OFF_X", gap);
    int offY = baseY + env_num("BOH_DUALWPN_OFF_Y", 0);

    bool drew = false;
    if (state.mainItem != 0)
        drew = draw_asset(g_mainSprite, mainX, mainY, ticks) || drew;
    if (state.offItem != 0)
        drew = draw_asset(g_offSprite, offX, offY, ticks) || drew;

    if (drew &&
        (state.mainItem != g_lastDrawMainItem ||
         state.offItem != g_lastDrawOffItem ||
         ticks - g_lastDrawTick > 5000))
    {
        g_lastDrawMainItem = state.mainItem;
        g_lastDrawOffItem = state.offItem;
        g_lastDrawTick = ticks;
        int mainOriginX = g_mainSprite.frameCount > 0 ? g_mainSprite.frames[0].originX : 0;
        int mainOriginY = g_mainSprite.frameCount > 0 ? g_mainSprite.frames[0].originY : 0;
        int offOriginX = g_offSprite.frameCount > 0 ? g_offSprite.frames[0].originX : 0;
        int offOriginY = g_offSprite.frameCount > 0 ? g_offSprite.frames[0].originY : 0;
        logf("draw active mode=%u main=%u off=%u mainFrames=%d offFrames=%d anchor=%d,%d gap=%d mainAnchor=%d,%d offAnchor=%d,%d mainOrigin=%d,%d offOrigin=%d,%d",
             state.mode, state.mainItem, state.offItem,
             g_mainSprite.frameCount, g_offSprite.frameCount,
             baseX, baseY, gap, mainX, mainY, offX, offY,
             mainOriginX, mainOriginY, offOriginX, offOriginY);
    }

    return drew;
}

static void update_overlay(HWND gameWnd)
{
    if (!should_show_overlay(gameWnd))
    {
        hide_overlay();
        return;
    }

    if (!ensure_window(gameWnd))
        return;

    RECT client = {};
    POINT origin = { 0, 0 };
    if (!GetClientRect(gameWnd, &client) || !ClientToScreen(gameWnd, &origin))
        return;

    int clientW = client.right - client.left;
    int clientH = client.bottom - client.top;
    POINT dst = {
        origin.x + (clientW / 2) - (kOverlayW / 2),
        origin.y + (clientH / 2) - (kOverlayH / 2)
    };

    HDC screenDC = GetDC(nullptr);
    if (!screenDC)
        return;

    if (ensure_dib(screenDC))
    {
        if (draw_scene())
        {
            POINT src = { 0, 0 };
            SIZE size = { kOverlayW, kOverlayH };
            BLENDFUNCTION blend = { AC_SRC_OVER, 0, 255, AC_SRC_ALPHA };

            UpdateLayeredWindow(g_overlayWnd, screenDC, &dst, &size,
                                g_memDC, &src, 0, &blend, ULW_ALPHA);
            SetWindowPos(g_overlayWnd, HWND_TOP, dst.x, dst.y,
                         kOverlayW, kOverlayH,
                         SWP_NOACTIVATE | SWP_SHOWWINDOW);
        }
        else
        {
            hide_overlay();
        }
    }

    ReleaseDC(nullptr, screenDC);
}

static DWORD WINAPI overlay_thread(LPVOID)
{
    g_threadId = GetCurrentThreadId();
    logf("overlay thread start");

    HWND gameWnd = nullptr;
    for (int i = 0; i < 300 && !shutting_down(); ++i)
    {
        gameWnd = find_game_window();
        if (gameWnd)
            break;
        Sleep(100);
    }

    if (!gameWnd)
    {
        logf("game window not found");
        g_threadId = 0;
        return 0;
    }

    logf("game window hwnd=%p", gameWnd);

    int frames = 0;
    while (!shutting_down())
    {
        if (!gameWnd || !IsWindow(gameWnd))
        {
            hide_overlay();
            gameWnd = find_game_window();
            if (!gameWnd)
            {
                Sleep(250);
                continue;
            }
            logf("game window reacquired hwnd=%p", gameWnd);
        }

        // Poll weapon state directly from game memory (no hooks needed)
        {
            static int pollCounter = 0;
            if (++pollCounter >= 10) { // every ~330ms
                pollCounter = 0;
                poll_weapon_state();
            }
        }

        update_overlay(gameWnd);
        if ((++frames % 300) == 0)
        {
            OverlayState dbg = {};
            DWORD age = 0;
            const char* status = get_state_status(&dbg, &age);
            logf("overlay heartbeat frames=%d state=%s age=%lu mode=%u main=%u off=%u mainFrames=%d offFrames=%d",
                 frames, status, age, dbg.mode, dbg.mainItem, dbg.offItem,
                 g_mainSprite.frameCount, g_offSprite.frameCount);
        }
        Sleep(33);
    }

    destroy_window();
    destroy_gdi();
    free_assets();
    logf("overlay thread stop");
    g_threadId = 0;
    return 0;
}

} // namespace

extern "C" bool WeaponOverlayStart(HMODULE module)
{
    g_module = module;
    if (g_thread)
        return true;

    InterlockedExchange(&g_shutdown, 0);
    g_thread = CreateThread(nullptr, 0, overlay_thread, nullptr, 0, &g_threadId);
    if (!g_thread)
    {
        InterlockedExchange(&g_shutdown, 1);
        logf("CreateThread failed err=%lu", GetLastError());
        return false;
    }

    logf("WeaponOverlayStart");
    return true;
}

extern "C" void WeaponOverlayStop()
{
    InterlockedExchange(&g_shutdown, 1);

    HANDLE thread = g_thread;
    if (!thread)
        return;

    if (GetCurrentThreadId() != g_threadId)
    {
        DWORD waitResult = WaitForSingleObject(thread, 2000);
        if (waitResult == WAIT_TIMEOUT)
            logf("overlay thread did not stop within timeout");
    }

    CloseHandle(thread);
    g_thread = nullptr;
}

extern "C" void WeaponOverlayUpdateState(DWORD charObj, DWORD mode,
                                          DWORD mainItem, DWORD offItem,
                                          DWORD mainView, DWORD offView)
{
    if (shutting_down())
        return;

    DWORD now = GetTickCount();
    InterlockedIncrement(&g_state.seq);
    g_state.tick = now;
    g_state.charObj = charObj;
    g_state.mode = mode;
    g_state.mainItem = mainItem;
    g_state.offItem = offItem;
    g_state.mainView = mainView;
    g_state.offView = offView;
    InterlockedIncrement(&g_state.seq);

    static DWORD lastLogTick = 0;
    static DWORD lastChar = 0xFFFFFFFFu;
    static DWORD lastMode = 0xFFFFFFFFu;
    static DWORD lastMain = 0xFFFFFFFFu;
    static DWORD lastOff = 0xFFFFFFFFu;
    if (charObj != lastChar || mode != lastMode || mainItem != lastMain ||
        offItem != lastOff || now - lastLogTick > 5000)
    {
        lastLogTick = now;
        lastChar = charObj;
        lastMode = mode;
        lastMain = mainItem;
        lastOff = offItem;
        logf("state update char=%08X mode=%u main=%u off=%u mainView=%u offView=%u",
             charObj, mode, mainItem, offItem, mainView, offView);
    }
}

extern "C" void WeaponOverlayClearState()
{
    InterlockedIncrement(&g_state.seq);
    g_state.tick = 0;
    g_state.charObj = 0;
    g_state.mode = 0;
    g_state.mainItem = 0;
    g_state.offItem = 0;
    g_state.mainView = 0;
    g_state.offView = 0;
    InterlockedIncrement(&g_state.seq);
}
