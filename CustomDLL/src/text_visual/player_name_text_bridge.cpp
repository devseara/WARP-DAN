#define WIN32_LEAN_AND_MEAN
#include <windows.h>

#include <string>

#include "boh_features.h"
#include "extended_name/extended_name.h"
#include "player_name_color/player_name_color.h"
#include "text_visual/fluent_emoji_renderer.h"
#include "text_visual/text_visual_bridge.h"
#include "text_visual/utf8_char_bridge.h"

static LPVOID g_origTextOutW = nullptr;
static LPVOID g_origExtTextOutW = nullptr;
static LPVOID g_origGetTextExtentPoint32W = nullptr;
static volatile LONG g_textBridgeShuttingDown = 0;
static DWORD g_tlsPassthroughDepth = TLS_OUT_OF_INDEXES;

static bool IsTextBridgeShuttingDown()
{
    return InterlockedCompareExchange(&g_textBridgeShuttingDown, 0, 0) != 0;
}

static bool ResolveRealTextApis()
{
    HMODULE gdi32 = GetModuleHandleA("gdi32.dll");
    if (!gdi32)
        return false;

    if (!g_origTextOutW)
        g_origTextOutW = GetProcAddress(gdi32, "TextOutW");
    if (!g_origExtTextOutW)
        g_origExtTextOutW = GetProcAddress(gdi32, "ExtTextOutW");
    if (!g_origGetTextExtentPoint32W)
        g_origGetTextExtentPoint32W =
            GetProcAddress(gdi32, "GetTextExtentPoint32W");

    return g_origTextOutW &&
           g_origExtTextOutW &&
           g_origGetTextExtentPoint32W;
}

static bool IsShadowLayerColor(COLORREF color)
{
    return GetRValue(color) <= 0x20 &&
           GetGValue(color) <= 0x20 &&
           GetBValue(color) <= 0x20;
}

static std::wstring CaptureText(LPCWSTR text, int count)
{
    if (!text)
        return L"";
    if (count < 0)
        return text;
    if (count == 0)
        return L"";
    return std::wstring(text, count);
}

static bool TrySubstituteText(
    const std::wstring& text,
    std::wstring& substitutedText,
    bool& isNameplate)
{
#if BOH_EXTENDED_NAMES
    return ExtendedNameSubstitute(text, substitutedText, isNameplate);
#else
    (void)text;
    substitutedText.clear();
    isNameplate = false;
    return false;
#endif
}

static BOOL WINAPI BridgeTextOutW(
    HDC hdc,
    int x,
    int y,
    LPCWSTR lpString,
    int cchString)
{
    typedef BOOL (WINAPI *TextOutW_t)(HDC, int, int, LPCWSTR, int);
    typedef BOOL (WINAPI *ExtTextOutW_t)(
        HDC, int, int, UINT, const RECT*, LPCWSTR, UINT, const INT*);
    typedef BOOL (WINAPI *GetTextExtentPoint32W_t)(
        HDC, LPCWSTR, int, LPSIZE);

    if (IsTextBridgeShuttingDown() ||
        (DWORD_PTR)TlsGetValue(g_tlsPassthroughDepth) > 0)
    {
        return ((TextOutW_t)g_origTextOutW)(
            hdc, x, y, lpString, cchString);
    }

    std::wstring text = CaptureText(lpString, cchString);

    COLORREF playerNameColor = CLR_INVALID;
    bool hasPlayerNameColor = PlayerNameColorLookup(text, playerNameColor);
    COLORREF oldColor = CLR_INVALID;
    bool didColor = false;
    if (hasPlayerNameColor && !IsShadowLayerColor(GetTextColor(hdc)))
    {
        oldColor = SetTextColor(hdc, playerNameColor);
        didColor = true;
    }

    LPCWSTR outString = lpString;
    int outCount = cchString;
    std::wstring substitutedText;
    bool isNameplate = false;
    if (TrySubstituteText(text, substitutedText, isNameplate))
    {
        outString = substitutedText.c_str();
        outCount = static_cast<int>(substitutedText.length());
    }

    BOOL result = FALSE;
    TlsSetValue(
        g_tlsPassthroughDepth,
        (LPVOID)((DWORD_PTR)TlsGetValue(g_tlsPassthroughDepth) + 1));

    const std::wstring& renderText =
        substitutedText.empty() ? text : substitutedText;
    if (BohFluentEmoji::MayContainToken(renderText) &&
        BohFluentEmoji::Draw(
            hdc,
            x,
            y,
            renderText,
            (TextOutW_t)g_origTextOutW,
            (GetTextExtentPoint32W_t)g_origGetTextExtentPoint32W,
            false,
            &result))
    {
        TlsSetValue(
            g_tlsPassthroughDepth,
            (LPVOID)((DWORD_PTR)TlsGetValue(g_tlsPassthroughDepth) - 1));
        if (didColor && oldColor != CLR_INVALID)
            SetTextColor(hdc, oldColor);
        return result;
    }

    if (outString != lpString && outCount > 0)
    {
        int savedDC = SaveDC(hdc);
        if (savedDC)
            SelectClipRgn(hdc, nullptr);

        SIZE size = {};
        ((GetTextExtentPoint32W_t)g_origGetTextExtentPoint32W)(
            hdc, outString, outCount, &size);
        RECT rect = { x, y, x + size.cx + 50, y + size.cy };
        result = ((ExtTextOutW_t)g_origExtTextOutW)(
            hdc, x, y, 0, &rect, outString, (UINT)outCount, nullptr);

        if (savedDC)
            RestoreDC(hdc, savedDC);
    }
    else
    {
        result = ((TextOutW_t)g_origTextOutW)(
            hdc, x, y, outString, outCount);
    }

    TlsSetValue(
        g_tlsPassthroughDepth,
        (LPVOID)((DWORD_PTR)TlsGetValue(g_tlsPassthroughDepth) - 1));

    if (didColor && oldColor != CLR_INVALID)
        SetTextColor(hdc, oldColor);

    (void)isNameplate;
    return result;
}

static BOOL WINAPI BridgeGetTextExtentPoint32W(
    HDC hdc,
    LPCWSTR lpString,
    int cchString,
    LPSIZE lpSize)
{
    typedef BOOL (WINAPI *GetTextExtentPoint32W_t)(
        HDC, LPCWSTR, int, LPSIZE);

    if (IsTextBridgeShuttingDown())
    {
        return ((GetTextExtentPoint32W_t)g_origGetTextExtentPoint32W)(
            hdc, lpString, cchString, lpSize);
    }

    BOOL result = ((GetTextExtentPoint32W_t)g_origGetTextExtentPoint32W)(
        hdc, lpString, cchString, lpSize);
    if (!result || !lpSize || cchString <= 0)
        return result;
    if (!ExtendedNameHasSubstitutionState() &&
        !BohFluentEmoji::MayContainToken(lpString, cchString))
        return result;

    std::wstring text(lpString, cchString);
    std::wstring substitutedText;
    bool isNameplate = false;
    if (TrySubstituteText(text, substitutedText, isNameplate))
    {
        SIZE extSize = {};
        if (((GetTextExtentPoint32W_t)g_origGetTextExtentPoint32W)(
                hdc,
                substitutedText.c_str(),
                static_cast<int>(substitutedText.length()),
                &extSize))
        {
            lpSize->cx = extSize.cx;
            lpSize->cy = extSize.cy;
        }
    }

    const std::wstring& measureText =
        substitutedText.empty() ? text : substitutedText;
    SIZE emojiSize = {};
    if (BohFluentEmoji::MayContainToken(measureText) &&
        BohFluentEmoji::Measure(
            hdc,
            measureText,
            (GetTextExtentPoint32W_t)g_origGetTextExtentPoint32W,
            &emojiSize))
    {
        lpSize->cx = emojiSize.cx;
        lpSize->cy = emojiSize.cy;
    }

    (void)isNameplate;
    return result;
}

#if defined(_M_IX86)
#pragma comment(linker, "/EXPORT:BohTextOutW=_BohTextOutW@20")
#pragma comment(linker, "/EXPORT:BohGetTextExtentPoint32W=_BohGetTextExtentPoint32W@16")
#endif

extern "C" __declspec(dllexport) BOOL WINAPI BohTextOutW(
    HDC hdc,
    int x,
    int y,
    LPCWSTR lpString,
    int cchString)
{
    if (!ResolveRealTextApis())
        return FALSE;
    return BridgeTextOutW(hdc, x, y, lpString, cchString);
}

extern "C" __declspec(dllexport) BOOL WINAPI BohGetTextExtentPoint32W(
    HDC hdc,
    LPCWSTR lpString,
    int cchString,
    LPSIZE lpSize)
{
    if (!ResolveRealTextApis())
        return FALSE;
    return BridgeGetTextExtentPoint32W(hdc, lpString, cchString, lpSize);
}

void TextVisualInit(HMODULE module)
{
    BohFluentEmoji::SetModule(module);
    if (g_tlsPassthroughDepth == TLS_OUT_OF_INDEXES)
        g_tlsPassthroughDepth = TlsAlloc();
    InterlockedExchange(&g_textBridgeShuttingDown, 0);
    ResolveRealTextApis();

    ExtendedNameInit(true, false);
}

void TextVisualCleanup(bool isProcessTermination)
{
    (void)isProcessTermination;
    InterlockedExchange(&g_textBridgeShuttingDown, 1);
    ExtendedNameCleanup();
    BohFluentEmoji::Cleanup();

    if (g_tlsPassthroughDepth != TLS_OUT_OF_INDEXES)
    {
        TlsFree(g_tlsPassthroughDepth);
        g_tlsPassthroughDepth = TLS_OUT_OF_INDEXES;
    }
}
