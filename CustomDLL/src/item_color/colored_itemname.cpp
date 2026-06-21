// Extended-name/item-color visual hook.
// Can be built as ddraw.dll proxy or as a named startup DLL.

#include <windows.h>
#include <string>
#include <unordered_map>
#include <fstream>
#include <mutex>
#include <cstdint>
#include <vector>
#include <cwctype>
#include <set>
#include <stdio.h>

#include "boh_features.h"
#include "extended_name/extended_name.h"

#ifdef BOH_COMBINED_RUNE
BOOL APIENTRY RuneVisualDllMain(HMODULE module, DWORD reason, LPVOID reserved);
#endif
#ifdef BOH_COMBINED_FPS
BOOL APIENTRY FpsOverlayDllMain(HMODULE module, DWORD reason, LPVOID reserved);
#endif

// ============================================================================
//  Debug logging
// ============================================================================

static bool g_debugLogEnabled = false;

// ============================================================================
//  Performance tracking — logs TextOutW calls/sec to debug FPS issues
// ============================================================================
static DWORD  g_perfLastTick   = 0;
static UINT   g_perfItemProcd  = 0;
static UINT   g_perfFastSkips  = 0;
static UINT   g_perfThrottle   = 0;

// Forward declare LogMsg (defined below in hat-trace / general section)
static void LogMsg(const char* fmt, ...);

static void PerfTick()
{
	if (!g_debugLogEnabled)
		return;

	// Throttle: only check clock every 256 calls
	if ((++g_perfThrottle & 0xFF) != 0)
		return;
	DWORD now = GetTickCount();
	if (!g_perfLastTick) g_perfLastTick = now;
	if (now - g_perfLastTick >= 5000)
	{
		UINT procd = g_perfItemProcd;
		UINT skips = g_perfFastSkips;
		g_perfItemProcd = 0;
		g_perfFastSkips = 0;
		g_perfLastTick = now;
		UINT total = procd + skips;
		char buf[128];
		snprintf(buf, sizeof(buf), "[PERF] TextOutW: %u total/sec (item:%u skip:%u)\n",
			total/5, procd/5, skips/5);
		OutputDebugStringA(buf);
	}
}
static void LogMsg(const char* fmt, ...)
{
    if (!g_debugLogEnabled)
        return;

    char buf[512];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    HANDLE hFile = CreateFileW(L"boh_extname_visual.log", FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (hFile != INVALID_HANDLE_VALUE)
    {
        DWORD written;
        WriteFile(hFile, buf, (DWORD)strlen(buf), &written, nullptr);
        WriteFile(hFile, "\r\n", 2, &written, nullptr);
        CloseHandle(hFile);
    }
}

// ============================================================================
//  Proxy DLL exports
// ============================================================================

static HMODULE g_hRealDDraw = nullptr;
static FARPROC g_pDirectDrawCreateEx = nullptr;
static FARPROC g_pDirectDrawEnumerateExA = nullptr;
static HANDLE g_hookOwnerMutex = nullptr;
static bool g_ownsHookInstall = false;

// ============================================================================
//  Item color hook
// ============================================================================

static std::unordered_map<std::wstring, COLORREF> g_colorMap;
static std::unordered_map<uint8_t, COLORREF> g_gradeColorMap; // _GRADE_<n> → BGR
static std::set<std::wstring> g_gradeLabels;   // dynamic set of "[Label]" strings from _GRADE_* sentinels
static std::mutex g_mutex;

// Track the last item name rendered in item-description region for grade association
static std::wstring g_lastDescItemName;
static ULONGLONG g_lastDescItemTick = 0;

static LONG g_recvLogBudget = 60;
static LONG g_substitutionLogBudget = 160;
static LONG g_itemRenderLogBudget = 600;

static const uint16_t ITEM_COLOR_PACKET_ID = 0x0BDD;
static const uint16_t ITEM_COLOR_PACKET_ID_LEGACY = 0x0BB6;

static LPVOID g_origTextOutW = nullptr;
static LPVOID g_textOutWAddr = nullptr;
static SIZE_T g_stolenBytes = 0;
static volatile LONG g_textHooksShuttingDown = 0;

// ExtTextOutW hook globals
static LPVOID g_origExtTextOutW = nullptr;
static LPVOID g_extTextOutWAddr = nullptr;
static SIZE_T g_stolenBytesExt = 0;

// DrawTextW hook globals
static LPVOID g_origDrawTextW = nullptr;
static LPVOID g_drawTextWAddr = nullptr;
static SIZE_T g_stolenBytesDraw = 0;

// DrawTextExW hook globals
static LPVOID g_origDrawTextExW = nullptr;
static LPVOID g_drawTextExWAddr = nullptr;
static SIZE_T g_stolenBytesDrawEx = 0;

// GetTextExtentPoint32W hook globals
static LPVOID g_origGetTextExtentPoint32W = nullptr;
static LPVOID g_getTextExtentPoint32WAddr = nullptr;
static SIZE_T g_stolenBytesGTEP = 0;

// Shared F12 debounce across all hooks
static bool g_wasF12Down = false;

// Sequence tracking: when a text is colored, subsequent black calls for the
// same text are also colored (they would otherwise overwrite the colored text).
// This fixes equipment list where shadow is drawn AFTER main text.
static std::wstring g_lastSequenceText;
static bool g_sequenceWasColored = false;
static HDC g_lastSequenceHdc = nullptr;
static int g_lastSequenceX = 0;
static int g_lastSequenceY = 0;
static ULONGLONG g_lastSequenceTick = 0;
static const ULONGLONG g_sequenceWindowMs = 200;
static __declspec(thread) int g_textOutPassthroughDepth = 0;

// Grade-label continuation: when "[Rare]" or "[Epic]" etc. is colored,
// subsequent text rendered nearby (same item name continuation, or
// wrapped next line) inherits the same color.
static COLORREF g_gradeContColor = CLR_INVALID;
static HDC g_gradeContHdc = nullptr;
static int g_gradeContX = 0;
static int g_gradeContY = 0;
static ULONGLONG g_gradeContTick = 0;
static const ULONGLONG g_gradeContWindowMs = 300;



struct TextRegion
{
    HDC hdc = nullptr;
    int left = 0;
    int top = 0;
    int right = 0;
    int bottom = 0;
    ULONGLONG tick = 0;
};

static TextRegion g_itemDescriptionRegion;
static const ULONGLONG g_itemDescriptionRegionMs = 2000;

// Hot-reload state
static std::wstring g_colorsPath;

// Auto-reload: check file modification time every N frames
static ULONGLONG g_lastFileTime = 0;
static int g_frameCounter = 0;
static const int g_checkInterval = 60; // check every ~60 frames (~1 sec at 60fps)

// ============================================================================
//  Server-side packet receiver (shared memory + recv hook)
// ============================================================================

static LPVOID g_icolBlock = nullptr;   // WARP-allocated ICOL shared memory (item colors)
static bool g_checkedShared = false;
static CRITICAL_SECTION g_sharedBlockCS;
static HANDLE g_sharedPollThread = nullptr;
static HANDLE g_sharedPollStopEvent = nullptr;

// NPC name position capture — ring buffer read by npc_name_overlay.cpp
// Captures TextOutW calls that look like entity name tags.
struct NpcNamePosition
{
    char text[64];
    int x, y;
    DWORD tick;
};
static NpcNamePosition g_npcNamePositions[64];
static volatile LONG g_npcNamePosWrite = 0;
extern "C" NpcNamePosition* GetNpcNamePositionRing() { return g_npcNamePositions; }
extern "C" LONG GetNpcNamePosWrite() { return InterlockedCompareExchange(&g_npcNamePosWrite, 0, 0); }
extern "C" void ResetNpcNamePosRead(LONG v) { g_npcNamePosWrite = v; }

// recv hook fallback
static LPVOID g_origRecv = nullptr;
static LPVOID g_recvAddr = nullptr;
static SIZE_T g_stolenBytesRecv = 0;
static bool g_sharedBlockCSInitialized = false;

struct RecvStreamState
{
    std::vector<char> pendingInput;
    std::vector<char> pendingOutput;
};

static std::unordered_map<SOCKET, RecvStreamState> g_recvStates;
static std::mutex g_recvStateMutex;

enum class PacketSourceMode
{
    Auto,
    RecvAndShared,
    RecvOnly,
    SharedOnly,
    None
};

static PacketSourceMode g_packetSourceMode = PacketSourceMode::Auto;
static bool g_enableRecvHook = false;
static bool g_enableSharedPolling = true;

static LPVOID FindSharedBlock(uint32_t magic);
static LPVOID ClientAddress(DWORD va);

static bool IsTextHooksShuttingDown()
{
    return InterlockedCompareExchange(&g_textHooksShuttingDown, 0, 0) != 0;
}

static void RestorePatchedBytes(LPVOID target, LPVOID originalBytes, SIZE_T length)
{
    if (!target || !originalBytes || length < 5)
        return;

    DWORD oldProtect = 0;
    if (!VirtualProtect(target, length, PAGE_EXECUTE_READWRITE, &oldProtect))
        return;

    memcpy(target, originalBytes, length);
    FlushInstructionCache(GetCurrentProcess(), target, length);
    VirtualProtect(target, length, oldProtect, &oldProtect);
}

static bool IsShadowLayerColor(COLORREF color)
{
    BYTE red = GetRValue(color);
    BYTE green = GetGValue(color);
    BYTE blue = GetBValue(color);
    return red <= 0x20 && green <= 0x20 && blue <= 0x20;
}

static void TrackColorSequence(const std::wstring& text, bool didColor, HDC hdc, int x, int y)
{
    if (text != g_lastSequenceText || hdc != g_lastSequenceHdc)
    {
        g_lastSequenceText = text;
        g_lastSequenceHdc = hdc;
        g_sequenceWasColored = false;
    }
    if (didColor)
    {
        g_sequenceWasColored = true;
        g_lastSequenceX = x;
        g_lastSequenceY = y;
        g_lastSequenceTick = GetTickCount64();
    }
}

static bool ShouldColorLateShadow(const std::wstring& text, HDC hdc, int x, int y)
{
    if (!g_sequenceWasColored)
        return false;
    if (text != g_lastSequenceText)
        return false;
    if (hdc != g_lastSequenceHdc)
        return false;

    ULONGLONG now = GetTickCount64();
    if (now < g_lastSequenceTick || (now - g_lastSequenceTick) > g_sequenceWindowMs)
        return false;

    int dx = x - g_lastSequenceX;
    if (dx < 0)
        dx = -dx;
    int dy = y - g_lastSequenceY;
    if (dy < 0)
        dy = -dy;
    return dx <= 2 && dy <= 2;
}

// Check whether this text should inherit a grade-label color from a prior
// adjacent TextOutW call.  Handles two cases:
//   a) Same-line continuation: "[Epic]" then " Apple of ..." at x+~50
//   b) Wrapped line in Alt+Q: next line at same x with y+~16
static COLORREF GetGradeContinuationColor(HDC hdc, int x, int y)
{
    if (g_gradeContColor == CLR_INVALID || hdc != g_gradeContHdc)
        return CLR_INVALID;

    ULONGLONG now = GetTickCount64();
    if (now < g_gradeContTick || (now - g_gradeContTick) > g_gradeContWindowMs)
        return CLR_INVALID;

    // Wrapped line: same x-offset (+-2px for main/shadow offset),
    // y advanced by ~10-22 px (one line height)
    int adjustDx = (x > g_gradeContX) ? (x - g_gradeContX) : (g_gradeContX - x);
    if (adjustDx <= 2 && y > g_gradeContY && (y - g_gradeContY) <= 22)
        return g_gradeContColor;

    // Same-line continuation: y close, x is to the right within ~120 px
    int dy = (y > g_gradeContY) ? (y - g_gradeContY) : (g_gradeContY - y);
    if (dy <= 2 && x > g_gradeContX && (x - g_gradeContX) <= 120)
        return g_gradeContColor;

    return CLR_INVALID;
}

static void TrackGradeContinuation(COLORREF color, HDC hdc, int x, int y)
{
    g_gradeContColor = color;
    g_gradeContHdc   = hdc;
    g_gradeContX     = x;
    g_gradeContY     = y;
    g_gradeContTick  = GetTickCount64();
}

static bool IsGradeLabel(const std::wstring& text)
{
    for (const auto& label : g_gradeLabels) {
        if (text.find(label) != std::wstring::npos)
            return true;
    }
    return false;
}

static bool ShouldApplyItemColorToExtTextOut(UINT options, const RECT* lprc, bool inDescriptionRegion)
{
    // Item description/title labels render through clipped ExtTextOut.
    // Reject ONLY inside the description region to avoid colored text
    // stacking with the client's own shadow/title pass.
    // Allow clipped ExtTextOut elsewhere (Alt+Q equip window, inventory)
    // so grade-label coloring works for wrapped item names.
    if (inDescriptionRegion)
        return false;
    if (lprc != nullptr && (options & ETO_CLIPPED) != 0)
        return true; // Alt+Q / equip window with word-wrap
    return true; // hover balloons, unclipped text
}

static bool LooksLikeItemDescriptionMarker(const std::wstring& text)
{
    return text.find(L"Item Description") != std::wstring::npos ||
        text.find(L"Item Collection") != std::wstring::npos ||
        text.find(L"Item Stat") != std::wstring::npos ||
        text.find(L"Item ID:") != std::wstring::npos ||
        text.find(L"Compound on:") != std::wstring::npos ||
        text.find(L"Weight:") != std::wstring::npos;
}

static std::string WidePreview(const std::wstring& value, size_t maxChars);

static void RememberItemDescriptionRegion(const std::wstring& text, HDC hdc, int x, int y, const RECT* rect)
{
    if (!hdc || !LooksLikeItemDescriptionMarker(text))
        return;

    int anchorX = rect ? rect->left : x;
    int anchorY = rect ? rect->top : y;

    g_itemDescriptionRegion.hdc = hdc;
    g_itemDescriptionRegion.left = anchorX - 90;
    g_itemDescriptionRegion.top = anchorY - 240;
    g_itemDescriptionRegion.right = anchorX + 360;
    g_itemDescriptionRegion.bottom = anchorY + 260;
    g_itemDescriptionRegion.tick = GetTickCount64();

    if (g_debugLogEnabled)
    {
        LONG budget = InterlockedDecrement(&g_itemRenderLogBudget);
        if (budget >= 0)
        {
            std::string textUtf8 = WidePreview(text, 120);
            LogMsg("[IDESC] marker hdc=%p anchor=%d,%d rect=%d,%d,%d,%d region=%d,%d,%d,%d text=\"%s\"",
                hdc,
                anchorX,
                anchorY,
                rect ? rect->left : 0,
                rect ? rect->top : 0,
                rect ? rect->right : 0,
                rect ? rect->bottom : 0,
                g_itemDescriptionRegion.left,
                g_itemDescriptionRegion.top,
                g_itemDescriptionRegion.right,
                g_itemDescriptionRegion.bottom,
                textUtf8.c_str());
        }
    }
}

static bool IsInsideItemDescriptionRegion(HDC hdc, int x, int y, const RECT* rect)
{
    if (!hdc || hdc != g_itemDescriptionRegion.hdc)
        return false;

    ULONGLONG now = GetTickCount64();
    if (now < g_itemDescriptionRegion.tick || (now - g_itemDescriptionRegion.tick) > g_itemDescriptionRegionMs)
        return false;

    int testX = rect ? rect->left : x;
    int testY = rect ? rect->top : y;
    return testX >= g_itemDescriptionRegion.left &&
        testX <= g_itemDescriptionRegion.right &&
        testY >= g_itemDescriptionRegion.top &&
        testY <= g_itemDescriptionRegion.bottom;
}

static bool TryFindItemColor(const std::wstring& text, COLORREF& color, std::wstring& match)
{
    color = CLR_INVALID;
    match.clear();

    std::lock_guard<std::mutex> lock(g_mutex);

    // 1) Name-based match from item_color_db.yml or server-side item_color_set
    for (const auto& entry : g_colorMap)
    {
        // Substring match: "Red Potion [3]" contains "Red Potion".
        if (text.find(entry.first) != std::wstring::npos)
        {
            color = entry.second;
            match = entry.first;
            return true;
        }
    }

    return false;
}

static bool LooksLikeItemDescriptionTitle(const std::wstring& text, const std::wstring& match, int x, int y, const RECT* rect)
{
    if (text.empty() || match.empty() || text != match)
        return false;
    if (rect != nullptr)
        return false;

    // The item detail window title is drawn in a small local HDC just to the
    // right of the item sprite. Render traces show title passes around 90,10,
    // while hover labels use 6,4 and list rows render lower in their controls.
    return x >= 80 && x <= 180 && y >= 0 && y <= 24;
}

static void LogItemColorRender(
    const char* hook,
    const char* action,
    const std::wstring& text,
    const std::wstring& match,
    COLORREF customColor,
    HDC hdc,
    int x,
    int y,
    const RECT* rect,
    UINT options,
    COLORREF currentColor,
    bool isShadowLayer,
    bool inDescriptionRegion,
    bool isDescriptionMarker)
{
    if (!g_debugLogEnabled)
        return;

    LONG budget = InterlockedDecrement(&g_itemRenderLogBudget);
    if (budget < 0)
        return;

    int left = rect ? rect->left : 0;
    int top = rect ? rect->top : 0;
    int right = rect ? rect->right : 0;
    int bottom = rect ? rect->bottom : 0;
    std::string textUtf8 = WidePreview(text, 120);
    std::string matchUtf8 = WidePreview(match, 80);

    LogMsg("[ICOLOR:%s] action=%s hdc=%p xy=%d,%d rect=%d,%d,%d,%d opt=%08X cur=#%02X%02X%02X shadow=%u desc=%u marker=%u match=\"%s\" color=#%02X%02X%02X text=\"%s\"",
        hook,
        action,
        hdc,
        x,
        y,
        left,
        top,
        right,
        bottom,
        options,
        GetRValue(currentColor),
        GetGValue(currentColor),
        GetBValue(currentColor),
        isShadowLayer ? 1 : 0,
        inDescriptionRegion ? 1 : 0,
        isDescriptionMarker ? 1 : 0,
        matchUtf8.c_str(),
        GetRValue(customColor),
        GetGValue(customColor),
        GetBValue(customColor),
        textUtf8.c_str());
}

static std::string WidePreview(const std::wstring& value, size_t maxChars = 80)
{
    if (value.empty())
        return "";

    std::wstring trimmed = value.substr(0, maxChars);
    int bytes = WideCharToMultiByte(CP_UTF8, 0, trimmed.c_str(), (int)trimmed.length(), nullptr, 0, nullptr, nullptr);
    if (bytes <= 0)
        return "<wide-convert-failed>";

    std::string out(bytes, '\0');
    WideCharToMultiByte(CP_UTF8, 0, trimmed.c_str(), (int)trimmed.length(), &out[0], bytes, nullptr, nullptr);

    for (char& ch : out)
    {
        if (ch == '\r' || ch == '\n' || ch == '\t')
            ch = ' ';
    }
    return out;
}

static void LogSubstitution(const char* hook, const std::wstring& from, const std::wstring& to, bool isNameplate)
{
    if (!g_debugLogEnabled)
        return;

    LONG budget = InterlockedDecrement(&g_substitutionLogBudget);
    if (budget < 0)
        return;

    std::string fromUtf8 = WidePreview(from);
    std::string toUtf8 = WidePreview(to);
    LogMsg("[SUB:%s] nameplate=%u from=\"%s\" to=\"%s\"",
        hook,
        isNameplate ? 1 : 0,
        fromUtf8.c_str(),
        toUtf8.c_str());
}

static std::wstring ToLowerCopy(std::wstring s)
{
    for (wchar_t& ch : s)
        ch = (wchar_t)towlower(ch);
    return s;
}

static std::wstring GetExeDirectory()
{
    wchar_t exePath[MAX_PATH] = {};
    DWORD written = GetModuleFileNameW(nullptr, exePath, MAX_PATH);
    if (written == 0 || written >= MAX_PATH)
        return L"";

    std::wstring path(exePath, written);
    size_t pos = path.find_last_of(L"\\/");
    if (pos == std::wstring::npos)
        return L"";

    return path.substr(0, pos + 1);
}

static bool FileExists(const std::wstring& path)
{
    DWORD attrs = GetFileAttributesW(path.c_str());
    return attrs != INVALID_FILE_ATTRIBUTES && !(attrs & FILE_ATTRIBUTE_DIRECTORY);
}

static bool ParseBoolSetting(const std::wstring& rawValue)
{
    std::wstring value = ToLowerCopy(rawValue);
    return value == L"1" || value == L"yes" || value == L"true" || value == L"on" || value == L"debug";
}

static void ConfigureDebugLogging()
{
    wchar_t envValue[64] = {};
    DWORD envLen = GetEnvironmentVariableW(L"BOH_EXTNAME_VISUAL_LOG", envValue, _countof(envValue));
    if (envLen > 0 && envLen < _countof(envValue))
    {
        g_debugLogEnabled = ParseBoolSetting(envValue);
        return;
    }

    std::wstring iniPath = GetExeDirectory() + L"ddraw_proxy.ini";
    wchar_t iniValue[64] = {};
    DWORD iniLen = GetPrivateProfileStringW(L"CustomItemColors", L"DebugLog", L"", iniValue, _countof(iniValue), iniPath.c_str());
    g_debugLogEnabled = iniLen > 0 && iniLen < _countof(iniValue) && ParseBoolSetting(iniValue);
}

static bool IsLikelyGepardClient()
{
    if (GetModuleHandleA("gepard.dll") != nullptr)
        return true;

    std::wstring baseDir = GetExeDirectory();
    if (baseDir.empty())
        return false;

    return FileExists(baseDir + L"gepard.dll");
}

static PacketSourceMode ParsePacketSourceMode(const std::wstring& rawValue)
{
    std::wstring value = ToLowerCopy(rawValue);
    if (value == L"both" || value == L"recv_shared" || value == L"hybrid" ||
        value == L"recv" || value == L"recv_only" || value == L"runtime")
        return PacketSourceMode::SharedOnly;
    if (value == L"shared" || value == L"shared_only" || value == L"stub")
        return PacketSourceMode::SharedOnly;
    if (value == L"none" || value == L"off" || value == L"disabled")
        return PacketSourceMode::None;
    return PacketSourceMode::Auto;
}

static const char* PacketSourceModeToAnsi(PacketSourceMode mode)
{
    switch (mode)
    {
    case PacketSourceMode::RecvAndShared: return "both";
    case PacketSourceMode::RecvOnly: return "recv";
    case PacketSourceMode::SharedOnly: return "shared";
    case PacketSourceMode::None: return "none";
    case PacketSourceMode::Auto:
    default:
        return "auto";
    }
}

static PacketSourceMode ResolvePacketSourceMode(bool isLikelyGepard, bool hasWarpSharedBlocks)
{
    // Optional override through environment variable:
    // BOH_PACKET_SOURCE=auto|recv|shared|none
    wchar_t envValue[64] = {};
    DWORD envLen = GetEnvironmentVariableW(L"BOH_PACKET_SOURCE", envValue, _countof(envValue));
    if (envLen > 0 && envLen < _countof(envValue))
    {
        PacketSourceMode mode = ParsePacketSourceMode(envValue);
        if (mode != PacketSourceMode::Auto)
            return mode;
    }

    // Optional override through INI file next to the client executable:
    // [CustomItemColors]
    // PacketSource=auto|recv|shared|none
    std::wstring iniPath = GetExeDirectory() + L"ddraw_proxy.ini";
    wchar_t iniValue[64] = {};
    DWORD iniLen = GetPrivateProfileStringW(L"CustomItemColors", L"PacketSource", L"", iniValue, _countof(iniValue), iniPath.c_str());
    if (iniLen > 0 && iniLen < _countof(iniValue))
    {
        PacketSourceMode mode = ParsePacketSourceMode(iniValue);
        if (mode != PacketSourceMode::Auto)
            return mode;
    }

    // Default for Banquet: shared-block polling only. Runtime recv interception
    // is intentionally disabled; packet transport should be provided by an
    // approved WARP-side static integration point instead.
    if (hasWarpSharedBlocks)
        return PacketSourceMode::SharedOnly;
    (void)isLikelyGepard;
    return PacketSourceMode::None;
}

static void ApplyPacketSourceMode(PacketSourceMode mode)
{
    g_packetSourceMode = mode;
    switch (mode)
    {
    case PacketSourceMode::RecvAndShared:
        g_enableRecvHook = false;
        g_enableSharedPolling = true;
        break;
    case PacketSourceMode::RecvOnly:
        g_enableRecvHook = false;
        g_enableSharedPolling = true;
        break;
    case PacketSourceMode::SharedOnly:
        g_enableRecvHook = false;
        g_enableSharedPolling = true;
        break;
    case PacketSourceMode::None:
        g_enableRecvHook = false;
        g_enableSharedPolling = false;
        break;
    case PacketSourceMode::Auto:
    default:
        // Auto is resolved before this call, but keep a no-runtime-recv fallback.
        g_enableRecvHook = false;
        g_enableSharedPolling = true;
        break;
    }
}

static COLORREF ParseColor(const std::string& s)
{
    // Use strtoul instead of std::stoul to avoid C++ exceptions in hook context
    const char* str = s.c_str();
    char* endptr = nullptr;
    unsigned int base = 10;

    // Explicit 0x/0X prefix → hex; else auto-detect by A-F letters
    if (s.length() >= 2 && s[0] == '0' && (s[1] == 'x' || s[1] == 'X')) {
        base = 16;
        str += 2;
    } else if (s.find_first_of("aAbBcCdDeEfF") != std::string::npos) {
        base = 16;
    }

    unsigned long rgb = strtoul(str, &endptr, base);
    if (endptr == str) // parse failed
        return CLR_INVALID;

    unsigned int r = (rgb >> 16) & 0xFF;
    unsigned int g = (rgb >> 8) & 0xFF;
    unsigned int b = rgb & 0xFF;
    return (b << 16) | (g << 8) | r;
}

static std::wstring Utf8ToWide(const std::string& utf8)
{
    if (utf8.empty()) return std::wstring();
    int size = MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, nullptr, 0);
    if (size <= 1) return std::wstring();
    std::wstring wide(size - 1, 0);
    MultiByteToWideChar(CP_UTF8, 0, utf8.c_str(), -1, &wide[0], size);
    wide.resize(size - 1);
    return wide;
}

static bool LoadColorMapImpl(std::unordered_map<std::wstring, COLORREF>& outMap)
{
    wchar_t exePath[MAX_PATH];
    GetModuleFileNameW(nullptr, exePath, MAX_PATH);
    std::wstring path(exePath);
    size_t pos = path.find_last_of(L"\\/");
    if (pos != std::wstring::npos) path = path.substr(0, pos + 1);
    path += L"item_colors.txt";
    g_colorsPath = path;

    // Use Win32 file API instead of std::ifstream to avoid C++ exceptions in hook context
    HANDLE hFile = CreateFileW(path.c_str(), GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE, nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (hFile == INVALID_HANDLE_VALUE)
        return false;

    DWORD fileSize = GetFileSize(hFile, nullptr);
    if (fileSize == 0 || fileSize > 1024 * 1024) // sanity: max 1MB
    {
        CloseHandle(hFile);
        return false;
    }

    std::vector<char> buffer(fileSize + 1, 0);
    DWORD read = 0;
    if (!ReadFile(hFile, buffer.data(), fileSize, &read, nullptr) || read == 0)
    {
        CloseHandle(hFile);
        return false;
    }
    CloseHandle(hFile);
    buffer[read] = 0;

    // Skip UTF-8 BOM
    char* data = buffer.data();
    if (read >= 3 &&
        (unsigned char)data[0] == 0xEF &&
        (unsigned char)data[1] == 0xBB &&
        (unsigned char)data[2] == 0xBF)
    {
        data += 3;
    }

    size_t count = 0;
    char* lineStart = data;
    while (*lineStart)
    {
        // Find end of line
        char* lineEnd = lineStart;
        while (*lineEnd && *lineEnd != '\n' && *lineEnd != '\r')
            lineEnd++;

        // Create a temp null-terminated line
        char saved = *lineEnd;
        *lineEnd = 0;

        // Trim leading whitespace
        char* nameStart = lineStart;
        while (*nameStart == ' ' || *nameStart == '\t')
            nameStart++;

        // Parse: Name=Color
        if (*nameStart && *nameStart != '#')
        {
            char* eq = nameStart;
            while (*eq && *eq != '=')
                eq++;

            if (*eq == '=')
            {
                *eq = 0;
                char* name = nameStart;
                char* color = eq + 1;

                // Trim trailing whitespace from name
                char* nameEnd = name + strlen(name) - 1;
                while (nameEnd >= name && (*nameEnd == ' ' || *nameEnd == '\t' || *nameEnd == '\r' || *nameEnd == '\n'))
                    *nameEnd-- = 0;

                // Trim leading whitespace from color
                while (*color == ' ' || *color == '\t')
                    color++;

                // Trim trailing whitespace from color
                char* colorEnd = color + strlen(color) - 1;
                while (colorEnd >= color && (*colorEnd == ' ' || *colorEnd == '\t' || *colorEnd == '\r' || *colorEnd == '\n'))
                    *colorEnd-- = 0;

                if (*name && *color)
                {
                    // Detect _GRADE_<name> sentinel entries
                    if (strncmp(name, "_GRADE_", 7) == 0)
                    {
                        const char* rest = name + 7;
                        // New format: _GRADE_<N>_<Label>
                        char* endptr = nullptr;
                        unsigned long gradeVal = strtoul(rest, &endptr, 10);
                        if (gradeVal >= 1 && gradeVal <= 255 && endptr && *endptr == '_')
                        {
                            const char* label = endptr + 1;
                            uint8_t gv = static_cast<uint8_t>(gradeVal);
                            g_gradeColorMap[gv] = ParseColor(color);
                            std::string labelStr(label);
                            if (!labelStr.empty())
                            {
                                std::wstring wlabel = L"[" + Utf8ToWide(labelStr) + L"]";
                                g_gradeLabels.insert(wlabel);
                                outMap[wlabel] = ParseColor(color); // also match "[Legendary]" text
                            }
                            count++;
                            LogMsg("[GRADE:file] found _GRADE_%lu_%s -> grade=%u color=%s",
                                gradeVal, label, gv, color);
                        }
                    }
                    else
                    {
                        std::wstring wname = Utf8ToWide(name);
                        if (!wname.empty())
                        {
                            outMap[wname] = ParseColor(color);
                            count++;
                        }
                    }
                }
            }
        }

        *lineEnd = saved; // restore
        // Skip line ending
        if (*lineEnd == '\r') lineEnd++;
        if (*lineEnd == '\n') lineEnd++;
        lineStart = lineEnd;
    }

    (void)count; // unused in non-debug build
    return true;
}

static void LoadColorMap()
{
    std::unordered_map<std::wstring, COLORREF> newMap;
    size_t oldGradeSize = g_gradeColorMap.size();
    if (LoadColorMapImpl(newMap))
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        g_colorMap = std::move(newMap);
        LogMsg("[GRADE:file-reload] colorMap=%u gradeColorMap: %u -> %u",
            (unsigned)g_colorMap.size(), (unsigned)oldGradeSize, (unsigned)g_gradeColorMap.size());
    }
}

// ============================================================================
//  Shared memory scanner (WARP-allocated block)
// ============================================================================

static LPVOID FindSharedBlock(uint32_t magic)
{
    HMODULE hExe = GetModuleHandle(nullptr);
    if (!hExe) return nullptr;

    // Scan first 64MB of the EXE image for the magic DWORD
    BYTE* start = (BYTE*)hExe;
    const size_t SCAN_SIZE = 64 * 1024 * 1024;

    __try
    {
        for (size_t i = 0; i < SCAN_SIZE - 12; i += 4)
        {
            if (*(uint32_t*)(start + i) == magic)
            {
                uint32_t ready = *(uint32_t*)(start + i + 4);
                uint32_t length = *(uint32_t*)(start + i + 8);
                if ((ready == 0 || ready == 1) && length <= 4092)
                    return start + i;
            }
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        // Scan hit a non-readable page; return what we found so far
    }
    return nullptr;
}

static void ParsePacketData(BYTE* data, uint32_t length)
{
    // ZC_ITEM_COLOR_LIST packet:
    // uint16 packetType (0x0BDD dispatcher transport; legacy 0x0BB6)
    // uint16 packetLength
    // uint32 count
    // repeat count:
    //   uint16 nameLen (includes null terminator)
    //   char   name[nameLen]
    //   uint32 color (0x00RRGGBB)

    if (length < 8)
    {
        LogMsg("[GRADE:parse] reject len=%u < 8", length);
        return;
    }

    uint16_t packetType = *(uint16_t*)data;
    if (packetType != ITEM_COLOR_PACKET_ID && packetType != ITEM_COLOR_PACKET_ID_LEGACY)
    {
        LogMsg("[GRADE:parse] reject packetType=0x%04X (expected 0x%04X or 0x%04X)",
            packetType, ITEM_COLOR_PACKET_ID, ITEM_COLOR_PACKET_ID_LEGACY);
        return;
    }

    uint16_t packetLen = *(uint16_t*)(data + 2);
    uint32_t count = *(uint32_t*)(data + 4);

    LogMsg("[GRADE:parse] packet=0x%04X totalLen=%u count=%u", packetType, length, count);

    if (packetLen != length) // length is total raw packet bytes
    {
        LogMsg("[GRADE:parse] reject packetLen=%u != length=%u", packetLen, length);
        return;
    }

    std::unordered_map<std::wstring, COLORREF> newMap;
    std::unordered_map<uint8_t, COLORREF> newGradeMap;
    size_t offset = 8;

    for (uint32_t i = 0; i < count && offset + 6 <= length; i++)
    {
        uint16_t nameLen = *(uint16_t*)(data + offset);
        offset += 2;

        if (nameLen == 0 || offset + nameLen + 4 > length)
            break;

        char* name = (char*)(data + offset);
        // Ensure null-terminated
        if (name[nameLen - 1] != 0)
            name[nameLen - 1] = 0;

        offset += nameLen;

        uint32_t rgb = *(uint32_t*)(data + offset);
        offset += 4;

        // Convert RGB 0x00RRGGBB -> BGR 0x00BBGGRR for GDI
        unsigned int r = (rgb >> 16) & 0xFF;
        unsigned int g = (rgb >> 8) & 0xFF;
        unsigned int b = rgb & 0xFF;
        COLORREF bgr = (b << 16) | (g << 8) | r;

        // Detect _GRADE_<N>_<Label> sentinel entries for per-grade tinting.
        // Format: _GRADE_<N>_<Label> (e.g. _GRADE_4_Legendary).
        if (nameLen >= 8 && name[0] == '_' && name[1] == 'G' && name[2] == 'R' &&
            name[3] == 'A' && name[4] == 'D' && name[5] == 'E' && name[6] == '_')
        {
            const char* rest = name + 7;
            // New format: _GRADE_<N>_<Label>
            char* endptr = nullptr;
            unsigned long gradeVal = strtoul(rest, &endptr, 10);
            if (gradeVal >= 1 && gradeVal <= 255 && endptr && *endptr == '_')
            {
                const char* label = endptr + 1;
                uint8_t gv = static_cast<uint8_t>(gradeVal);
                newGradeMap[gv] = bgr;
                std::string labelStr(label);
                if (!labelStr.empty())
                {
                    std::wstring wlabel = L"[" + Utf8ToWide(labelStr) + L"]";
                    g_gradeLabels.insert(wlabel);
                    newMap[wlabel] = bgr; // also match "[Legendary]" text in g_colorMap
                }
                LogMsg("[GRADE:parse] found _GRADE_%lu_%s -> grade=%u bgr=0x%06X rgb=0x%06X",
                    gradeVal, label, gv, bgr, rgb);
            }
        }
        else
        {
            std::wstring wname = Utf8ToWide(name);
            if (!wname.empty())
                newMap[wname] = bgr;
        }
    }

    LogMsg("[GRADE:parse] done: nameEntries=%u gradeEntries=%u",
        (unsigned)newMap.size(), (unsigned)newGradeMap.size());

    if (!newMap.empty() || !newGradeMap.empty())
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        if (!newMap.empty())
        {
            size_t oldSize = g_colorMap.size();
            g_colorMap = std::move(newMap);
            LogMsg("[GRADE:store] colorMap: %u -> %u entries", (unsigned)oldSize, (unsigned)g_colorMap.size());
            if (g_colorMap.size() > 5000)
            {
                LogMsg("[WARN] g_colorMap capped at 5000, clearing");
                g_colorMap.clear();
            }
        }
        if (!newGradeMap.empty())
        {
            size_t oldSize = g_gradeColorMap.size();
            g_gradeColorMap = std::move(newGradeMap);
            LogMsg("[GRADE:store] gradeColorMap: %u -> %u entries", (unsigned)oldSize, (unsigned)g_gradeColorMap.size());
        }
    }
}

static void CheckSharedBlock()
{
    if (IsTextHooksShuttingDown())
        return;
    if (!g_enableSharedPolling || !g_sharedBlockCSInitialized)
        return;

    EnterCriticalSection(&g_sharedBlockCS);

    if (!g_icolBlock && !g_checkedShared)
    {
        g_icolBlock = FindSharedBlock(0x49434F4C); // 'ICOL'
        g_checkedShared = true;

        LogMsg("[GRADE:shared] SCAN: ICOL=%p sharedPolling=%u",
            g_icolBlock, g_enableSharedPolling ? 1 : 0);
        if (!g_icolBlock)
            LogMsg("[GRADE:shared] WARNING: ICOL shared block NOT found! Grade colors cannot be received.");
    }

    // Check ICOL block for item color updates
    if (g_icolBlock)
    {
        BYTE* base = (BYTE*)g_icolBlock;
        volatile uint32_t* pReady = (volatile uint32_t*)(base + 4);

        if (*pReady == 1)
        {
            uint32_t length = *(uint32_t*)(base + 8);
            LogMsg("[GRADE:shared] ICOL ready flag=1 length=%u", length);
            if (length > 0 && length <= 4092)
            {
                // Dump first 32 bytes of packet data for diagnostics
                char hex[128] = {};
                uint32_t dumpLen = length < 32 ? length : 32;
                for (uint32_t di = 0; di < dumpLen && di * 3 + 4 < sizeof(hex); di++)
                    snprintf(hex + di * 3, sizeof(hex) - di * 3, "%02X ", (unsigned char)*(base + 12 + di));
                LogMsg("[GRADE:shared] ICOL first %u bytes: %s", dumpLen, hex);
                ParsePacketData(base + 12, length); // data at +12 (magic+ready+length)
            }
            else
            {
                LogMsg("[GRADE:shared] ICOL invalid length=%u", length);
            }
            *pReady = 0;
        }
    }

    LeaveCriticalSection(&g_sharedBlockCS);
}

static DWORD WINAPI SharedPollThreadProc(LPVOID)
{
    for (;;)
    {
        CheckSharedBlock();
        if (!g_sharedPollStopEvent ||
            WaitForSingleObject(g_sharedPollStopEvent, 2) != WAIT_TIMEOUT)
            break;
    }
    return 0;
}

// ============================================================================
//  recv() hook fallback for server-side packets
// ============================================================================

// Extended-name packet parsing and state live in extended_name/.
static bool LooksLikeItemColorPacket(const char* data, size_t length)
{
    if (length < 8 || length > 4092)
        return false;
    uint16_t packetType = *(uint16_t*)data;
    if (packetType != ITEM_COLOR_PACKET_ID && packetType != ITEM_COLOR_PACKET_ID_LEGACY)
        return false;
    if (*(uint16_t*)(data + 2) != length)
        return false;

    uint32_t count = *(uint32_t*)(data + 4);
    if (count > 512)
        return false;

    size_t offset = 8;
    for (uint32_t i = 0; i < count; ++i)
    {
        if (offset + 2 > length)
            return false;

        uint16_t nameLen = *(uint16_t*)(data + offset);
        offset += 2;
        if (nameLen == 0 || nameLen > 128 || offset + nameLen + 4 > length)
            return false;
        if (data[offset + nameLen - 1] != '\0')
            return false;

        offset += nameLen + 4;
    }

    return offset == length;
}

static void ProcessCustomStream(RecvStreamState& state)
{
    std::vector<char>& input = state.pendingInput;
    size_t in = 0;

    while (in < input.size())
    {
        size_t available = input.size() - in;

        if (available < 2)
        {
            if (input[in] == (char)0xB6 || input[in] == (char)0xB7)
                break;
            state.pendingOutput.push_back(input[in++]);
            continue;
        }

        uint16_t type = *(uint16_t*)(&input[in]);

        if (type == ITEM_COLOR_PACKET_ID || type == ITEM_COLOR_PACKET_ID_LEGACY)
        {
            if (available < 4)
                break;

            uint16_t pktLen = *(uint16_t*)(&input[in + 2]);
            if (pktLen >= 8 && pktLen <= 4092)
            {
                if (available < pktLen)
                    break;

                if (LooksLikeItemColorPacket(&input[in], pktLen))
                {
                    LONG budget = InterlockedDecrement(&g_recvLogBudget);
                    if (budget >= 0)
                        LogMsg("[RECV] strip item-color type=%04X offset=%u len=%u buffered=%u", type, (unsigned)in, pktLen, (unsigned)input.size());
                    ParsePacketData((BYTE*)(&input[in]), pktLen);
                    in += pktLen;
                    continue;
                }
            }
        }
        else if (type == EXT_NAME_PACKET_ID)
        {
            if (available < 8)
                break;

            uint16_t pktLen = *(uint16_t*)(&input[in + 2]);
            uint32_t magic = *(uint32_t*)(&input[in + 4]);
            if (pktLen == EXT_NAME_PACKET_LEN && magic == EXT_NAME_PACKET_MAGIC)
            {
                if (available < pktLen)
                    break;

                if (ExtendedNameLooksLikePacket(&input[in], pktLen))
                {
                    LONG budget = InterlockedDecrement(&g_recvLogBudget);
                    if (budget >= 0)
                        LogMsg("[RECV] strip 0BB7 offset=%u len=%u buffered=%u", (unsigned)in, pktLen, (unsigned)input.size());
                    ExtendedNameParsePacket((BYTE*)(&input[in]), pktLen);
                    in += pktLen;
                    continue;
                }
            }
        }

        state.pendingOutput.push_back(input[in++]);
    }

    if (in > 0)
        input.erase(input.begin(), input.begin() + in);
}

static int DrainRecvOutput(RecvStreamState& state, char* buf, int len)
{
    if (state.pendingOutput.empty())
        return 0;

    size_t count = std::min<size_t>((size_t)len, state.pendingOutput.size());
    memcpy(buf, state.pendingOutput.data(), count);
    state.pendingOutput.erase(state.pendingOutput.begin(), state.pendingOutput.begin() + count);
    return (int)count;
}

static void SetRecvWouldBlock()
{
    HMODULE ws2_32 = GetModuleHandleA("ws2_32.dll");
    if (!ws2_32)
        return;

    typedef void (WINAPI *WSASetLastError_t)(int);
    WSASetLastError_t pWSASetLastError = (WSASetLastError_t)GetProcAddress(ws2_32, "WSASetLastError");
    if (pWSASetLastError)
        pWSASetLastError(WSAEWOULDBLOCK);
}

// Forward decl (defined later in file)
static bool BuildTrampolineFor(LPVOID target, LPVOID& outTrampoline, SIZE_T& outStolenBytes);

typedef int (WINAPI *recv_t)(SOCKET s, char* buf, int len, int flags);

static int WINAPI HookRecv(SOCKET s, char* buf, int len, int flags)
{
    if (IsTextHooksShuttingDown())
        return ((recv_t)g_origRecv)(s, buf, len, flags);

    if (!buf || len <= 0)
        return ((recv_t)g_origRecv)(s, buf, len, flags);

    {
        std::lock_guard<std::mutex> lock(g_recvStateMutex);
        int drained = DrainRecvOutput(g_recvStates[s], buf, len);
        if (drained > 0)
            return drained;
    }

    std::vector<char> temp((size_t)len);
    int result = ((recv_t)g_origRecv)(s, temp.data(), len, flags);
    if (result <= 0)
        return result;

    std::lock_guard<std::mutex> lock(g_recvStateMutex);
    RecvStreamState& state = g_recvStates[s];
    state.pendingInput.insert(state.pendingInput.end(), temp.begin(), temp.begin() + result);
    ProcessCustomStream(state);

    int drained = DrainRecvOutput(state, buf, len);
    if (drained > 0)
        return drained;

    SetRecvWouldBlock();
    return SOCKET_ERROR;
}

static bool InstallRecvHook()
{
    HMODULE ws2_32 = GetModuleHandleA("ws2_32.dll");
    if (!ws2_32) return false;

    g_recvAddr = GetProcAddress(ws2_32, "recv");
    if (!g_recvAddr) return false;

    if (!BuildTrampolineFor(g_recvAddr, g_origRecv, g_stolenBytesRecv))
        return false;

    DWORD jmpOffset = (DWORD)HookRecv - ((DWORD)g_recvAddr + 5);

    DWORD oldProtect;
    if (!VirtualProtect(g_recvAddr, g_stolenBytesRecv, PAGE_EXECUTE_READWRITE, &oldProtect))
        return false;

    BYTE jmp[5] = { 0xE9 };
    *(DWORD*)&jmp[1] = jmpOffset;
    memcpy(g_recvAddr, jmp, 5);

    if (g_stolenBytesRecv > 5)
    {
        BYTE* nopFill = (BYTE*)g_recvAddr + 5;
        memset(nopFill, 0x90, g_stolenBytesRecv - 5);
    }

    VirtualProtect(g_recvAddr, g_stolenBytesRecv, oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), g_recvAddr, g_stolenBytesRecv);
    return true;
}

// Forward decl
static BOOL WINAPI HookTextOutW(HDC hdc, int x, int y, LPCWSTR lpString, int cchString);

static SIZE_T GetStolenByteCount(BYTE* code)
{
    SIZE_T total = 0;
    while (total < 5)
    {
        BYTE b0 = code[total];
        BYTE b1 = code[total + 1];

        if (b0 == 0xFF && b1 == 0x25)
            return total + 6;
        if (b0 == 0xE9)
            return total + 5;
        if (b0 == 0xEB)
            return total + 2;
        if (b0 == 0x8B && b1 == 0xFF)
            total += 2;
        else if (b0 == 0x55)
            total += 1;
        else if (b0 == 0x8B && b1 == 0xEC)
            total += 2;
        else if ((b0 & 0xF0) == 0x50)
            total += 1;
        else if (b0 == 0x90)
            total += 1;
        else if (b0 >= 0xB8 && b0 <= 0xBF)
            total += 5;
        else
            total += 1;
    }
    return total;
}

static bool BuildTrampolineFor(LPVOID target, LPVOID& outTrampoline, SIZE_T& outStolenBytes)
{
    BYTE* src = (BYTE*)target;
    outStolenBytes = GetStolenByteCount(src);
    if (outStolenBytes < 5) outStolenBytes = 5;

    SIZE_T trampSize = outStolenBytes + 5;
    outTrampoline = VirtualAlloc(nullptr, trampSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!outTrampoline) return false;

    memcpy(outTrampoline, target, outStolenBytes);

    BYTE* tramp = (BYTE*)outTrampoline;
    tramp[outStolenBytes] = 0xE9;
    *(DWORD*)&tramp[outStolenBytes + 1] = ((DWORD)target + (DWORD)outStolenBytes) - ((DWORD)outTrampoline + (DWORD)outStolenBytes + 5);

    return true;
}

static bool BuildTrampoline(LPVOID target)
{
    BYTE* src = (BYTE*)target;
    g_stolenBytes = GetStolenByteCount(src);
    if (g_stolenBytes < 5) g_stolenBytes = 5;

    SIZE_T trampSize = g_stolenBytes + 5;
    g_origTextOutW = VirtualAlloc(nullptr, trampSize, MEM_COMMIT | MEM_RESERVE, PAGE_EXECUTE_READWRITE);
    if (!g_origTextOutW) return false;

    memcpy(g_origTextOutW, target, g_stolenBytes);

    BYTE* tramp = (BYTE*)g_origTextOutW;
    tramp[g_stolenBytes] = 0xE9;
    *(DWORD*)&tramp[g_stolenBytes + 1] = ((DWORD)target + (DWORD)g_stolenBytes) - ((DWORD)g_origTextOutW + (DWORD)g_stolenBytes + 5);

    return true;
}

// ============================================================================
//  Client address helper
// ============================================================================

static LPVOID ClientAddress(DWORD va)
{
    HMODULE exe = GetModuleHandleW(nullptr);
    if (!exe || va < 0x00400000)
        return nullptr;

    return reinterpret_cast<LPVOID>(reinterpret_cast<DWORD>(exe) + (va - 0x00400000));
}

static BOOL WINAPI HookTextOutW(HDC hdc, int x, int y, LPCWSTR lpString, int cchString)
{
    typedef BOOL (WINAPI *TextOutW_t)(HDC, int, int, LPCWSTR, int);
    if (IsTextHooksShuttingDown())
        return ((TextOutW_t)g_origTextOutW)(hdc, x, y, lpString, cchString);

    COLORREF customColor = CLR_INVALID;
    COLORREF matchedColor = CLR_INVALID;
    std::wstring colorMatch;
    std::wstring text;
    bool hasItemColorMatch = false;
    bool inDescriptionRegion = false;
    bool isDescriptionMarker = false;

    if (lpString)
    {
        if (cchString < 0)
            text = lpString;
        else if (cchString > 0)
            text.assign(lpString, cchString);

        if (!text.empty())
        {
            // FAST-PATH: item-related text always starts with '[' (grade labels)
            // or contains '^' (color codes). Skill names, UI labels, and other
            // non-item text skip ALL item-color processing — major FPS saver.
            bool looksItemRelated = false;
            for (size_t fi = 0; fi < text.size() && fi < 8; fi++)
            {
                if (text[fi] == L'[' || text[fi] == L'^')
                {
                    looksItemRelated = true;
                    break;
                }
            }
            if (!looksItemRelated)
            {
                g_perfFastSkips++;
                PerfTick();
                goto skip_item_processing;
            }
            g_perfItemProcd++;
            PerfTick();

            RememberItemDescriptionRegion(text, hdc, x, y, nullptr);
            inDescriptionRegion = IsInsideItemDescriptionRegion(hdc, x, y, nullptr);
            isDescriptionMarker = LooksLikeItemDescriptionMarker(text);

            // Periodic grade color diagnostic — fires once per ~600 frames (~10 sec)
            static int g_gradeDiagCounter = 0;
            if (g_debugLogEnabled && ++g_gradeDiagCounter >= 600)
            {
                g_gradeDiagCounter = 0;
                size_t gc = 0;
                {
                    std::lock_guard<std::mutex> lock(g_mutex);
                    gc = g_gradeColorMap.size();
                }
                LogMsg("[GRADE:diag] periodic: gradeColorMap=%u entries, colorMap=%u entries",
                    (unsigned)gc, (unsigned)g_colorMap.size());
                for (const auto& e : g_gradeColorMap)
                    LogMsg("[GRADE:diag]   grade[%u] = 0x%06X", e.first, e.second);

                // Raw ICOL block dump — shows whether dispatcher is writing
                if (g_icolBlock)
                {
                    BYTE* raw = (BYTE*)g_icolBlock;
                    uint32_t magic  = *(uint32_t*)(raw + 0);
                    uint32_t ready  = *(uint32_t*)(raw + 4);
                    uint32_t length = *(uint32_t*)(raw + 8);
                    LogMsg("[GRADE:diag] ICOL raw: magic=0x%08X ready=%u length=%u",
                        magic, ready, length);
                    if (length > 0 && length <= 64)
                    {
                        char hex[192] = {};
                        for (uint32_t di = 0; di < length && di < 64; di++)
                            snprintf(hex + di*3, sizeof(hex) - di*3, "%02X ", raw[12+di]);
                        LogMsg("[GRADE:diag] ICOL data[%u]: %s", length, hex);
                    }
                }
                else
                {
                    LogMsg("[GRADE:diag] ICOL block is NULL — dispatcher may not have allocated it");
                }
            }

            // Auto-reload: check file modification time every N frames.
            // More reliable than hotkey detection inside a hooked API.
            bool doReload = false;
            if (++g_frameCounter >= g_checkInterval)
            {
                g_frameCounter = 0;

                // Check WARP shared memory block for server-side color updates
                CheckSharedBlock();

                if (!g_colorsPath.empty())
                {
                    WIN32_FILE_ATTRIBUTE_DATA fad;
                    if (GetFileAttributesExW(g_colorsPath.c_str(), GetFileExInfoStandard, &fad))
                    {
                        ULONGLONG fileTime = ((ULONGLONG)fad.ftLastWriteTime.dwHighDateTime << 32) | fad.ftLastWriteTime.dwLowDateTime;
                        if (fileTime != g_lastFileTime)
                        {
                            g_lastFileTime = fileTime;
                            doReload = true;
                        }
                    }
                }
            }

            // Also reload on F12 press (manual override)
            if (!doReload)
            {
                bool isF12Down = (GetAsyncKeyState(VK_F12) & 0x8000) != 0;
                if (isF12Down && !g_wasF12Down)
                    doReload = true;
                g_wasF12Down = isF12Down;
            }

            if (doReload)
            {
                std::unordered_map<std::wstring, COLORREF> newMap;
                if (LoadColorMapImpl(newMap))
                {
                    std::lock_guard<std::mutex> lock(g_mutex);
                    g_colorMap = std::move(newMap);
                }
            }

            hasItemColorMatch = TryFindItemColor(text, matchedColor, colorMatch);
            if (hasItemColorMatch && !inDescriptionRegion)
                customColor = matchedColor;

            // Grade-label continuation: when "[Epic]" is colored, the rest
            // of the item name (" Apple of ...") and any wrapped lines in
            // Alt+Q should inherit the same color.
            if (hasItemColorMatch && !inDescriptionRegion && IsGradeLabel(text))
                TrackGradeContinuation(matchedColor, hdc, x, y);
        }
    }

skip_item_processing:

    // Apply grade-continuation color when no explicit match was found
    if (customColor == CLR_INVALID && !hasItemColorMatch)
    {
        COLORREF contColor = GetGradeContinuationColor(hdc, x, y);
        if (contColor != CLR_INVALID)
            customColor = contColor;
    }

    // Only apply custom color if this is NOT the shadow/outline layer.
    // The game draws text twice: once in black (shadow) and once in white (main).
    // Coloring the shadow makes text look bold/overlapping.
    COLORREF currentColor = GetTextColor(hdc);
    bool isShadowLayer = IsShadowLayerColor(currentColor);

    COLORREF oldColor = CLR_INVALID;
    bool didColor = false;
    if (customColor != CLR_INVALID && !isShadowLayer)
    {
        oldColor = SetTextColor(hdc, customColor);
        didColor = true;
    }

    if (hasItemColorMatch)
    {
        const char* action = "match-no-color";
        if (didColor)
            action = "color";
        else if (inDescriptionRegion)
            action = "skip-desc-region";
        else if (isShadowLayer)
            action = "skip-shadow";
        LogItemColorRender("TextOutW", action, text, colorMatch, matchedColor, hdc, x, y, nullptr, 0, currentColor, isShadowLayer, inDescriptionRegion, isDescriptionMarker);
    }

    if (customColor != CLR_INVALID && isShadowLayer)
        return TRUE;

    // Track sequence: if this text was colored, mark it for ETO shadow detection.
    // Equipment list draws main FIRST then shadow SECOND (shadow overwrites main).
    // Description panel draws shadow FIRST then main SECOND (main overwrites shadow).
    // We only need to color ETO shadows that come AFTER a colored main.
    TrackColorSequence(text, didColor, hdc, x, y);

    // Extended-name matching is centralized in extended_name/. Mob payloads
    // only match exact nameplates, preventing item collisions like
    // "Poring Card" -> "Poring | HP:...".
    LPCWSTR outString = lpString;
    int outCount = cchString;
    std::wstring substitutedText;
    bool isNameplate = false;
    if (ExtendedNameSubstitute(text, substitutedText, isNameplate))
    {
        outString = substitutedText.c_str();
        outCount = (int)substitutedText.length();
    }

    // Substituted text: use ExtTextOutW with large rect to bypass clipping
    if (outString != lpString)
    {
        LogSubstitution("TextOutW", text, substitutedText, isNameplate);

        int savedDC = SaveDC(hdc);
        SelectClipRgn(hdc, nullptr);

        SIZE sz = {};
        GetTextExtentPoint32W(hdc, outString, outCount, &sz);
        RECT bigRect = { x, y, x + sz.cx + 50, y + sz.cy };
        ++g_textOutPassthroughDepth;
        BOOL result = ExtTextOutW(hdc, x, y, 0, &bigRect, outString, outCount, nullptr);
        --g_textOutPassthroughDepth;

        RestoreDC(hdc, savedDC);

        if (oldColor != CLR_INVALID)
            SetTextColor(hdc, oldColor);
        return result;
    }

    // Capture non-item text with position for NPC name overlay
    if (g_textOutPassthroughDepth == 0 && outCount > 0 && outCount < 50 &&
        outString && wcsstr(outString, L"^") == nullptr && outString[0] != L'[')
    {
        LONG idx = InterlockedIncrement(&g_npcNamePosWrite) - 1;
        NpcNamePosition& cap = g_npcNamePositions[idx % 64];
        int bytes = WideCharToMultiByte(CP_UTF8, 0, outString, outCount, cap.text, 63, nullptr, nullptr);
        if (bytes > 0 && bytes < 64) cap.text[bytes] = '\0'; else cap.text[0] = '\0';
        cap.x = x;
        cap.y = y;
        cap.tick = GetTickCount();
    }

    ++g_textOutPassthroughDepth;
    BOOL result = ((TextOutW_t)g_origTextOutW)(hdc, x, y, outString, outCount);
    --g_textOutPassthroughDepth;

    if (oldColor != CLR_INVALID)
        SetTextColor(hdc, oldColor);

    return result;
}

static BOOL WINAPI HookExtTextOutW(HDC hdc, int x, int y, UINT options, const RECT* lprc, LPCWSTR lpString, UINT cchString, const INT* lpDx)
{
    typedef BOOL (WINAPI *ExtTextOutW_t)(HDC, int, int, UINT, const RECT*, LPCWSTR, UINT, const INT*);
    if (IsTextHooksShuttingDown())
        return ((ExtTextOutW_t)g_origExtTextOutW)(hdc, x, y, options, lprc, lpString, cchString, lpDx);

    if (g_textOutPassthroughDepth > 0)
        return ((ExtTextOutW_t)g_origExtTextOutW)(hdc, x, y, options, lprc, lpString, cchString, lpDx);

    COLORREF customColor = CLR_INVALID;
    COLORREF matchedColor = CLR_INVALID;
    std::wstring colorMatch;
    std::wstring text;
    bool hasItemColorMatch = false;
    bool inDescriptionRegion = false;
    bool isDescriptionMarker = false;
    bool itemColorEligible = false;

    if (lpString && cchString > 0)
    {
        // Same fast-path as TextOutW: skip if not item-related
        bool looksItemRelated = false;
        for (UINT fi = 0; fi < cchString && fi < 8; fi++)
        {
            if (lpString[fi] == L'[' || lpString[fi] == L'^')
            {
                looksItemRelated = true;
                break;
            }
        }
        if (!looksItemRelated)
        {
            g_perfFastSkips++;
            goto skip_eto_processing;
        }
        g_perfItemProcd++;

        text.assign(lpString, cchString);

        if (!text.empty())
        {
            RememberItemDescriptionRegion(text, hdc, x, y, lprc);
            inDescriptionRegion = IsInsideItemDescriptionRegion(hdc, x, y, lprc);
            isDescriptionMarker = LooksLikeItemDescriptionMarker(text);
        }

        itemColorEligible = !text.empty() && ShouldApplyItemColorToExtTextOut(options, lprc, inDescriptionRegion);
        if (itemColorEligible)
        {
            // Reload on F12 (auto-reload is handled by TextOutW hook)
            bool doReload = false;
            bool isF12Down = (GetAsyncKeyState(VK_F12) & 0x8000) != 0;
            if (isF12Down && !g_wasF12Down)
                doReload = true;
            g_wasF12Down = isF12Down;

            // Also check WARP shared memory block for server-side color updates
            CheckSharedBlock();

            if (doReload)
            {
                std::unordered_map<std::wstring, COLORREF> newMap;
                if (LoadColorMapImpl(newMap))
                {
                    std::lock_guard<std::mutex> lock(g_mutex);
                    g_colorMap = std::move(newMap);
                }
            }

            hasItemColorMatch = TryFindItemColor(text, matchedColor, colorMatch);
            if (hasItemColorMatch && !inDescriptionRegion)
                customColor = matchedColor;

            // Grade continuation tracking (same as TextOutW)
            if (hasItemColorMatch && !inDescriptionRegion && IsGradeLabel(text))
                TrackGradeContinuation(matchedColor, hdc, x, y);
        }
        else if (!text.empty())
        {
            hasItemColorMatch = TryFindItemColor(text, matchedColor, colorMatch);
        }
    }

skip_eto_processing:

    // Grade continuation fallback
    if (customColor == CLR_INVALID && !hasItemColorMatch)
    {
        COLORREF contColor = GetGradeContinuationColor(hdc, x, y);
        if (contColor != CLR_INVALID)
            customColor = contColor;
    }

    COLORREF currentColor = GetTextColor(hdc);
    bool isShadowLayer = IsShadowLayerColor(currentColor);

    bool shouldColor = (customColor != CLR_INVALID && !isShadowLayer);

    COLORREF oldColor = CLR_INVALID;
    if (shouldColor)
        oldColor = SetTextColor(hdc, customColor);

    if (hasItemColorMatch)
    {
        const char* action = "match-no-color";
        if (shouldColor)
            action = "color";
        else if (inDescriptionRegion)
            action = "skip-desc-region";
        else if (!itemColorEligible)
            action = "skip-ext-ineligible";
        else if (isShadowLayer)
            action = "skip-shadow";
        LogItemColorRender("ExtTextOutW", action, text, colorMatch, matchedColor, hdc, x, y, lprc, options, currentColor, isShadowLayer, inDescriptionRegion, isDescriptionMarker);
    }

    if (customColor != CLR_INVALID && isShadowLayer)
        return TRUE;

    // Track sequence for ETO too
    TrackColorSequence(text, shouldColor, hdc, x, y);

    // Extended name substitution.
    LPCWSTR outString = lpString;
    UINT outCount = cchString;
    std::wstring substitutedText;
    bool isNameplate = false;
    if (ExtendedNameSubstitute(text, substitutedText, isNameplate))
    {
        outString = substitutedText.c_str();
        outCount = (UINT)substitutedText.length();
    }

    // Expand bounding box to fit substituted (longer) text
    RECT adjustedRect;
    const RECT* pRect = lprc;
    if (lprc != nullptr && outString != lpString)
    {
        SIZE sz = {};
        if (GetTextExtentPoint32W(hdc, outString, outCount, &sz))
        {
            int currentWidth = lprc->right - lprc->left;
            if (sz.cx > currentWidth)
            {
                adjustedRect = *lprc;
                int extra = sz.cx - currentWidth;
                adjustedRect.right += extra;
                pRect = &adjustedRect;
            }
        }
    }

    // Clear clip region and pass NULL pRect for substituted text to prevent clipping
    int savedDC = 0;
    const RECT* pRenderRect = pRect;
    if (outString != lpString)
    {
        LogSubstitution("ExtTextOutW", text, substitutedText, isNameplate);

        savedDC = SaveDC(hdc);
        SelectClipRgn(hdc, nullptr);
        pRenderRect = nullptr; // remove ExtTextOutW's own clipping rect
    }

    BOOL result = ((ExtTextOutW_t)g_origExtTextOutW)(hdc, x, y, options, pRenderRect, outString, outCount, lpDx);

    if (savedDC != 0)
        RestoreDC(hdc, savedDC);

    if (oldColor != CLR_INVALID)
        SetTextColor(hdc, oldColor);

    return result;
}

static int WINAPI HookDrawTextW(HDC hdc, LPCWSTR lpchText, int cchText, LPRECT lprc, UINT format)
{
    typedef int (WINAPI *DrawTextW_t)(HDC, LPCWSTR, int, LPRECT, UINT);
    if (IsTextHooksShuttingDown())
        return ((DrawTextW_t)g_origDrawTextW)(hdc, lpchText, cchText, lprc, format);

    COLORREF customColor = CLR_INVALID;
    COLORREF matchedColor = CLR_INVALID;
    std::wstring colorMatch;
    std::wstring text;
    bool hasItemColorMatch = false;
    bool inDescriptionRegion = false;
    bool isDescriptionMarker = false;

    if (lpchText)
    {
        if (cchText < 0)
            text = lpchText;
        else if (cchText > 0)
            text.assign(lpchText, cchText);

        if (!text.empty())
        {
            RememberItemDescriptionRegion(text, hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0, lprc);
            inDescriptionRegion = IsInsideItemDescriptionRegion(hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0, lprc);
            isDescriptionMarker = LooksLikeItemDescriptionMarker(text);

            // Reload on F12 (auto-reload is handled by TextOutW hook)
            bool doReload = false;
            bool isF12Down = (GetAsyncKeyState(VK_F12) & 0x8000) != 0;
            if (isF12Down && !g_wasF12Down)
                doReload = true;
            g_wasF12Down = isF12Down;

            if (doReload)
            {
                std::unordered_map<std::wstring, COLORREF> newMap;
                if (LoadColorMapImpl(newMap))
                {
                    std::lock_guard<std::mutex> lock(g_mutex);
                    g_colorMap = std::move(newMap);
                }
            }

            // DrawText is used by item description titles and Alt+Q equip window.
            // Keep custom item colors out of the description-region path so the
            // client can draw its own title/shadow without overlap artifacts.
            // But allow grade-label continuation colors for wrapped item names
            // in the Alt+Q equipment window (outside description region).
            hasItemColorMatch = TryFindItemColor(text, matchedColor, colorMatch);
            if (hasItemColorMatch && !inDescriptionRegion && !isDescriptionMarker)
            {
                // If it's a grade label, track continuation for wrapped lines
                if (IsGradeLabel(text))
                    TrackGradeContinuation(matchedColor, hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0);
                // Outside description region: allow coloring for Alt+Q equip window
                if (!inDescriptionRegion)
                    customColor = matchedColor;
            }
        }
    }

    // Grade continuation fallback for DrawTextW wrapped lines
    if (customColor == CLR_INVALID && !hasItemColorMatch)
    {
        COLORREF contColor = GetGradeContinuationColor(hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0);
        if (contColor != CLR_INVALID)
            customColor = contColor;
    }

    COLORREF currentColor = GetTextColor(hdc);
    bool isShadowLayer = IsShadowLayerColor(currentColor);

    bool shouldColor = (customColor != CLR_INVALID && !isShadowLayer);

    COLORREF oldColor = CLR_INVALID;
    if (shouldColor)
        oldColor = SetTextColor(hdc, customColor);

    TrackColorSequence(text, shouldColor, hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0);

    if (hasItemColorMatch)
        LogItemColorRender("DrawTextW", "ignored-drawtext", text, colorMatch, matchedColor, hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0, lprc, format, currentColor, isShadowLayer, inDescriptionRegion, isDescriptionMarker);

    // Extended name substitution.
    LPCWSTR outString = lpchText;
    int outCount = cchText;
    std::wstring substitutedText;
    bool isNameplate = false;
    if (ExtendedNameSubstitute(text, substitutedText, isNameplate))
    {
        outString = substitutedText.c_str();
        outCount = (int)substitutedText.length();
    }

    // For substituted text: expand RECT, remove truncation flags, clear clip
    RECT adjustedRect = {};
    LPRECT pRect = lprc;
    int savedDC = 0;
    if (outString != lpchText)
    {
        LogSubstitution("DrawTextW", text, substitutedText, isNameplate);

        savedDC = SaveDC(hdc);
        SelectClipRgn(hdc, nullptr);

        if (lprc)
        {
            SIZE sz = {};
            GetTextExtentPoint32W(hdc, outString, outCount, &sz);
            int currentWidth = lprc->right - lprc->left;
            if (sz.cx > currentWidth)
            {
                adjustedRect = *lprc;
                adjustedRect.right += (sz.cx - currentWidth) + 50;
                pRect = &adjustedRect;
            }
        }

        // Remove ellipsis flags so substituted text isn't truncated
        format &= ~(DT_END_ELLIPSIS | DT_WORD_ELLIPSIS | DT_PATH_ELLIPSIS);
    }

    int result = ((DrawTextW_t)g_origDrawTextW)(hdc, outString, outCount, pRect, format);

    if (savedDC != 0)
        RestoreDC(hdc, savedDC);

    if (oldColor != CLR_INVALID)
        SetTextColor(hdc, oldColor);

    return result;
}

static int WINAPI HookDrawTextExW(HDC hdc, LPCWSTR lpchText, int cchText, LPRECT lprc, UINT format, LPDRAWTEXTPARAMS lpDTParams)
{
    typedef int (WINAPI *DrawTextExW_t)(HDC, LPCWSTR, int, LPRECT, UINT, LPDRAWTEXTPARAMS);
    if (IsTextHooksShuttingDown())
        return ((DrawTextExW_t)g_origDrawTextExW)(hdc, lpchText, cchText, lprc, format, lpDTParams);

    COLORREF customColor = CLR_INVALID;
    COLORREF matchedColor = CLR_INVALID;
    std::wstring colorMatch;
    std::wstring text;
    bool hasItemColorMatch = false;
    bool inDescriptionRegion = false;
    bool isDescriptionMarker = false;

    if (lpchText)
    {
        if (cchText < 0)
            text = lpchText;
        else if (cchText > 0)
            text.assign(lpchText, cchText);

        if (!text.empty())
        {
            RememberItemDescriptionRegion(text, hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0, lprc);
            inDescriptionRegion = IsInsideItemDescriptionRegion(hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0, lprc);
            isDescriptionMarker = LooksLikeItemDescriptionMarker(text);

            bool doReload = false;
            bool isF12Down = (GetAsyncKeyState(VK_F12) & 0x8000) != 0;
            if (isF12Down && !g_wasF12Down)
                doReload = true;
            g_wasF12Down = isF12Down;

            if (doReload)
            {
                std::unordered_map<std::wstring, COLORREF> newMap;
                if (LoadColorMapImpl(newMap))
                {
                    std::lock_guard<std::mutex> lock(g_mutex);
                    g_colorMap = std::move(newMap);
                }
            }

            // DrawTextEx is used by item description titles and Alt+Q equip window.
            // Keep custom item colors out of the description-region path so the
            // client can draw its own title/shadow without overlap artifacts.
            // But allow grade-label colors for wrapped item names in Alt+Q.
            hasItemColorMatch = TryFindItemColor(text, matchedColor, colorMatch);
            if (hasItemColorMatch && !inDescriptionRegion && !isDescriptionMarker)
            {
                if (IsGradeLabel(text))
                    TrackGradeContinuation(matchedColor, hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0);
                if (!inDescriptionRegion)
                    customColor = matchedColor;
            }
        }
    }

    // Grade continuation fallback for DrawTextExW wrapped lines
    if (customColor == CLR_INVALID && !hasItemColorMatch)
    {
        COLORREF contColor = GetGradeContinuationColor(hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0);
        if (contColor != CLR_INVALID)
            customColor = contColor;
    }

    COLORREF currentColor = GetTextColor(hdc);
    bool isShadowLayer = IsShadowLayerColor(currentColor);

    bool shouldColor = (customColor != CLR_INVALID && !isShadowLayer);

    COLORREF oldColor = CLR_INVALID;
    if (shouldColor)
        oldColor = SetTextColor(hdc, customColor);

    TrackColorSequence(text, shouldColor, hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0);

    if (hasItemColorMatch)
        LogItemColorRender("DrawTextExW", "ignored-drawtextex", text, colorMatch, matchedColor, hdc, lprc ? lprc->left : 0, lprc ? lprc->top : 0, lprc, format, currentColor, isShadowLayer, inDescriptionRegion, isDescriptionMarker);

    // Extended name substitution.
    LPCWSTR outString = lpchText;
    int outCount = cchText;
    std::wstring substitutedText;
    bool isNameplate = false;
    if (ExtendedNameSubstitute(text, substitutedText, isNameplate))
    {
        outString = substitutedText.c_str();
        outCount = (int)substitutedText.length();
    }

    // For substituted text: expand RECT, remove truncation flags, clear clip
    RECT adjustedRect = {};
    LPRECT pRect = lprc;
    int savedDC = 0;
    if (outString != lpchText)
    {
        LogSubstitution("DrawTextExW", text, substitutedText, isNameplate);

        savedDC = SaveDC(hdc);
        SelectClipRgn(hdc, nullptr);

        if (lprc)
        {
            SIZE sz = {};
            GetTextExtentPoint32W(hdc, outString, outCount, &sz);
            int currentWidth = lprc->right - lprc->left;
            if (sz.cx > currentWidth)
            {
                adjustedRect = *lprc;
                adjustedRect.right += (sz.cx - currentWidth) + 50;
                pRect = &adjustedRect;
            }
        }

        // Remove ellipsis flags so substituted text isn't truncated
        format &= ~(DT_END_ELLIPSIS | DT_WORD_ELLIPSIS | DT_PATH_ELLIPSIS);
    }

    int result = ((DrawTextExW_t)g_origDrawTextExW)(hdc, outString, outCount, pRect, format, lpDTParams);

    if (savedDC != 0)
        RestoreDC(hdc, savedDC);

    if (oldColor != CLR_INVALID)
        SetTextColor(hdc, oldColor);

    return result;
}

static BOOL WINAPI HookGetTextExtentPoint32W(HDC hdc, LPCWSTR lpString, int cchString, LPSIZE lpSize)
{
    typedef BOOL (WINAPI *GetTextExtentPoint32W_t)(HDC, LPCWSTR, int, LPSIZE);
    if (IsTextHooksShuttingDown())
        return ((GetTextExtentPoint32W_t)g_origGetTextExtentPoint32W)(hdc, lpString, cchString, lpSize);

    BOOL result = ((GetTextExtentPoint32W_t)g_origGetTextExtentPoint32W)(hdc, lpString, cchString, lpSize);

    if (!result || !lpSize || cchString <= 0)
        return result;

    std::wstring text(lpString, cchString);

    std::wstring substitutedText;
    bool isNameplate = false;
    if (ExtendedNameSubstitute(text, substitutedText, isNameplate))
    {
        SIZE extSz = {};
        if (((GetTextExtentPoint32W_t)g_origGetTextExtentPoint32W)(
                hdc,
                substitutedText.c_str(),
                (int)substitutedText.length(),
                &extSz))
        {
            lpSize->cx = extSz.cx;
            lpSize->cy = extSz.cy;
        }
    }

    return result;
}

static bool InstallHook()
{
    HMODULE gdi32 = GetModuleHandleA("gdi32.dll");
    if (!gdi32) return false;

    g_textOutWAddr = GetProcAddress(gdi32, "TextOutW");
    if (!g_textOutWAddr) return false;

    if (!BuildTrampoline(g_textOutWAddr))
        return false;

    DWORD jmpOffset = (DWORD)HookTextOutW - ((DWORD)g_textOutWAddr + 5);

    DWORD oldProtect;
    if (!VirtualProtect(g_textOutWAddr, g_stolenBytes, PAGE_EXECUTE_READWRITE, &oldProtect))
        return false;

    BYTE jmp[5] = { 0xE9 };
    *(DWORD*)&jmp[1] = jmpOffset;
    memcpy(g_textOutWAddr, jmp, 5);

    if (g_stolenBytes > 5)
    {
        BYTE* nopFill = (BYTE*)g_textOutWAddr + 5;
        memset(nopFill, 0x90, g_stolenBytes - 5);
    }

    VirtualProtect(g_textOutWAddr, g_stolenBytes, oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), g_textOutWAddr, g_stolenBytes);

    return true;
}

static bool InstallExtTextOutWHook()
{
    HMODULE gdi32 = GetModuleHandleA("gdi32.dll");
    if (!gdi32) return false;

    g_extTextOutWAddr = GetProcAddress(gdi32, "ExtTextOutW");
    if (!g_extTextOutWAddr) return false;

    if (!BuildTrampolineFor(g_extTextOutWAddr, g_origExtTextOutW, g_stolenBytesExt))
        return false;

    DWORD jmpOffset = (DWORD)HookExtTextOutW - ((DWORD)g_extTextOutWAddr + 5);

    DWORD oldProtect;
    if (!VirtualProtect(g_extTextOutWAddr, g_stolenBytesExt, PAGE_EXECUTE_READWRITE, &oldProtect))
        return false;

    BYTE jmp[5] = { 0xE9 };
    *(DWORD*)&jmp[1] = jmpOffset;
    memcpy(g_extTextOutWAddr, jmp, 5);

    if (g_stolenBytesExt > 5)
    {
        BYTE* nopFill = (BYTE*)g_extTextOutWAddr + 5;
        memset(nopFill, 0x90, g_stolenBytesExt - 5);
    }

    VirtualProtect(g_extTextOutWAddr, g_stolenBytesExt, oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), g_extTextOutWAddr, g_stolenBytesExt);

    return true;
}

static bool InstallDrawTextWHook()
{
    HMODULE user32 = GetModuleHandleA("user32.dll");
    if (!user32) return false;

    g_drawTextWAddr = GetProcAddress(user32, "DrawTextW");
    if (!g_drawTextWAddr) return false;

    if (!BuildTrampolineFor(g_drawTextWAddr, g_origDrawTextW, g_stolenBytesDraw))
        return false;

    DWORD jmpOffset = (DWORD)HookDrawTextW - ((DWORD)g_drawTextWAddr + 5);

    DWORD oldProtect;
    if (!VirtualProtect(g_drawTextWAddr, g_stolenBytesDraw, PAGE_EXECUTE_READWRITE, &oldProtect))
        return false;

    BYTE jmp[5] = { 0xE9 };
    *(DWORD*)&jmp[1] = jmpOffset;
    memcpy(g_drawTextWAddr, jmp, 5);

    if (g_stolenBytesDraw > 5)
    {
        BYTE* nopFill = (BYTE*)g_drawTextWAddr + 5;
        memset(nopFill, 0x90, g_stolenBytesDraw - 5);
    }

    VirtualProtect(g_drawTextWAddr, g_stolenBytesDraw, oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), g_drawTextWAddr, g_stolenBytesDraw);

    return true;
}

static bool InstallDrawTextExWHook()
{
    HMODULE user32 = GetModuleHandleA("user32.dll");
    if (!user32) return false;

    g_drawTextExWAddr = GetProcAddress(user32, "DrawTextExW");
    if (!g_drawTextExWAddr) return false;

    if (!BuildTrampolineFor(g_drawTextExWAddr, g_origDrawTextExW, g_stolenBytesDrawEx))
        return false;

    DWORD jmpOffset = (DWORD)HookDrawTextExW - ((DWORD)g_drawTextExWAddr + 5);

    DWORD oldProtect;
    if (!VirtualProtect(g_drawTextExWAddr, g_stolenBytesDrawEx, PAGE_EXECUTE_READWRITE, &oldProtect))
        return false;

    BYTE jmp[5] = { 0xE9 };
    *(DWORD*)&jmp[1] = jmpOffset;
    memcpy(g_drawTextExWAddr, jmp, 5);

    if (g_stolenBytesDrawEx > 5)
    {
        BYTE* nopFill = (BYTE*)g_drawTextExWAddr + 5;
        memset(nopFill, 0x90, g_stolenBytesDrawEx - 5);
    }

    VirtualProtect(g_drawTextExWAddr, g_stolenBytesDrawEx, oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), g_drawTextExWAddr, g_stolenBytesDrawEx);

    return true;
}

static bool InstallGetTextExtentPoint32WHook()
{
    HMODULE gdi32 = GetModuleHandleA("gdi32.dll");
    if (!gdi32) return false;

    g_getTextExtentPoint32WAddr = GetProcAddress(gdi32, "GetTextExtentPoint32W");
    if (!g_getTextExtentPoint32WAddr) return false;

    if (!BuildTrampolineFor(g_getTextExtentPoint32WAddr, g_origGetTextExtentPoint32W, g_stolenBytesGTEP))
        return false;

    DWORD jmpOffset = (DWORD)HookGetTextExtentPoint32W - ((DWORD)g_getTextExtentPoint32WAddr + 5);

    DWORD oldProtect;
    if (!VirtualProtect(g_getTextExtentPoint32WAddr, g_stolenBytesGTEP, PAGE_EXECUTE_READWRITE, &oldProtect))
        return false;

    BYTE jmp[5] = { 0xE9 };
    *(DWORD*)&jmp[1] = jmpOffset;
    memcpy(g_getTextExtentPoint32WAddr, jmp, 5);

    if (g_stolenBytesGTEP > 5)
    {
        BYTE* nopFill = (BYTE*)g_getTextExtentPoint32WAddr + 5;
        memset(nopFill, 0x90, g_stolenBytesGTEP - 5);
    }

    VirtualProtect(g_getTextExtentPoint32WAddr, g_stolenBytesGTEP, oldProtect, &oldProtect);
    FlushInstructionCache(GetCurrentProcess(), g_getTextExtentPoint32WAddr, g_stolenBytesGTEP);

    return true;
}
// ============================================================================
//  ItemColorExtNameInit — called from main_proxy.cpp DllMain
// ============================================================================

void ItemColorExtNameInit(HMODULE hModule)
{
    InterlockedExchange(&g_textHooksShuttingDown, 0);
    ConfigureDebugLogging();

    g_hookOwnerMutex = CreateMutexW(nullptr, TRUE, L"Local\\BOH_ExtNameVisual_HookOwner");
    g_ownsHookInstall = (g_hookOwnerMutex == nullptr || GetLastError() != ERROR_ALREADY_EXISTS);
    if (!g_ownsHookInstall)
    {
        LogMsg("[INIT] another extname visual DLL already owns hooks; forwarding only");
        return;
    }

    bool likelyGepard = IsLikelyGepardClient();
    LPVOID icolProbe = FindSharedBlock(0x49434F4C);
    LPVOID extnProbe = ExtendedNameProbeSharedBlock();
    bool hasWarpSharedBlocks = icolProbe != nullptr || extnProbe != nullptr;
    PacketSourceMode resolvedMode = ResolvePacketSourceMode(likelyGepard, hasWarpSharedBlocks);
    ApplyPacketSourceMode(resolvedMode);
    if (g_enableSharedPolling)
    {
        g_icolBlock = icolProbe;
        g_checkedShared = true;
    }
    LogMsg("[INIT] packet_source=%s likely_gepard=%s warp_shared=%s recv_hook=%s shared_poll=%s ICOL=%p EXTN=%p",
        PacketSourceModeToAnsi(g_packetSourceMode),
        likelyGepard ? "yes" : "no",
        hasWarpSharedBlocks ? "yes" : "no",
        g_enableRecvHook ? "on" : "off",
        g_enableSharedPolling ? "on" : "off",
        g_icolBlock, extnProbe);

    if (g_enableSharedPolling && g_icolBlock)
    {
        InitializeCriticalSection(&g_sharedBlockCS);
        g_sharedBlockCSInitialized = true;
        g_sharedPollStopEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
        if (g_sharedPollStopEvent)
            g_sharedPollThread = CreateThread(nullptr, 0, SharedPollThreadProc, nullptr, 0, nullptr);
        if (!g_sharedPollThread)
            LogMsg("[WARN] ICOL shared-block drain thread was not started");
    }

    ExtendedNameInit(
        g_enableSharedPolling && extnProbe != nullptr,
        g_debugLogEnabled);

    LoadColorMap();
    {
        std::lock_guard<std::mutex> lock(g_mutex);
        LogMsg("[GRADE:init] startup: colorMap=%u entries, gradeColorMap=%u entries",
            (unsigned)g_colorMap.size(), (unsigned)g_gradeColorMap.size());
        for (const auto& e : g_gradeColorMap)
            LogMsg("[GRADE:init] gradeMap[%u] = 0x%06X", e.first, e.second);
    }
    if (!g_colorsPath.empty())
    {
        WIN32_FILE_ATTRIBUTE_DATA fad;
        if (GetFileAttributesExW(g_colorsPath.c_str(), GetFileExInfoStandard, &fad))
            g_lastFileTime = ((ULONGLONG)fad.ftLastWriteTime.dwHighDateTime << 32) | fad.ftLastWriteTime.dwLowDateTime;
    }

#if BOH_ITEM_COLORS || BOH_EXTENDED_NAMES
    InstallHook();
    InstallExtTextOutWHook();
    InstallDrawTextWHook();
    InstallDrawTextExWHook();
    InstallGetTextExtentPoint32WHook();
#endif

    if (g_enableRecvHook)
    {
        if (!InstallRecvHook())
            LogMsg("[WARN] InstallRecvHook failed");
    }
}

void ItemColorExtNameCleanup()
{
    InterlockedExchange(&g_textHooksShuttingDown, 1);
    RestorePatchedBytes(g_recvAddr, g_origRecv, g_stolenBytesRecv);
    RestorePatchedBytes(g_getTextExtentPoint32WAddr, g_origGetTextExtentPoint32W, g_stolenBytesGTEP);
    RestorePatchedBytes(g_drawTextExWAddr, g_origDrawTextExW, g_stolenBytesDrawEx);
    RestorePatchedBytes(g_drawTextWAddr, g_origDrawTextW, g_stolenBytesDraw);
    RestorePatchedBytes(g_extTextOutWAddr, g_origExtTextOutW, g_stolenBytesExt);
    RestorePatchedBytes(g_textOutWAddr, g_origTextOutW, g_stolenBytes);

    ExtendedNameCleanup();

    if (g_sharedPollStopEvent)
        SetEvent(g_sharedPollStopEvent);
    if (g_sharedPollThread)
    {
        WaitForSingleObject(g_sharedPollThread, 3000);
        CloseHandle(g_sharedPollThread);
        g_sharedPollThread = nullptr;
    }
    if (g_sharedPollStopEvent)
    {
        CloseHandle(g_sharedPollStopEvent);
        g_sharedPollStopEvent = nullptr;
    }

    if (g_ownsHookInstall && g_hookOwnerMutex)
        ReleaseMutex(g_hookOwnerMutex);
    if (g_hookOwnerMutex)
    {
        CloseHandle(g_hookOwnerMutex);
        g_hookOwnerMutex = nullptr;
    }
    g_ownsHookInstall = false;
    if (g_sharedBlockCSInitialized)
    {
        DeleteCriticalSection(&g_sharedBlockCS);
        g_sharedBlockCSInitialized = false;
    }
}
