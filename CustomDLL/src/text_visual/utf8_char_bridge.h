#pragma once

#include <windows.h>

#include <cstring>

namespace BohUtf8CharBridge
{
typedef LPSTR (WINAPI *CharNextExA_t)(WORD, LPCSTR, DWORD);
typedef LPSTR (WINAPI *CharPrevExA_t)(WORD, LPCSTR, LPCSTR, DWORD);

static LPVOID g_origCharNextExA = nullptr;
static LPVOID g_origCharPrevExA = nullptr;

static bool ResolveRealCharApis()
{
    HMODULE user32 = GetModuleHandleA("user32.dll");
    if (!user32)
        return false;

    if (!g_origCharNextExA)
        g_origCharNextExA = GetProcAddress(user32, "CharNextExA");
    if (!g_origCharPrevExA)
        g_origCharPrevExA = GetProcAddress(user32, "CharPrevExA");

    return g_origCharNextExA && g_origCharPrevExA;
}

static bool IsContinuation(unsigned char ch)
{
    return (ch & 0xC0) == 0x80;
}

static bool DecodeUtf8Scalar(const char* text, DWORD& codepoint, size_t& length)
{
    codepoint = 0;
    length = 0;
    if (!text || text[0] == '\0')
        return false;

    const unsigned char b0 = static_cast<unsigned char>(text[0]);
    if (b0 < 0x80)
    {
        codepoint = b0;
        length = 1;
        return true;
    }

    if (b0 >= 0xC2 && b0 <= 0xDF)
    {
        if (text[1] == '\0')
            return false;
        const unsigned char b1 = static_cast<unsigned char>(text[1]);
        if (!IsContinuation(b1))
            return false;
        codepoint = ((b0 & 0x1F) << 6) | (b1 & 0x3F);
        length = 2;
        return true;
    }

    if (b0 >= 0xE0 && b0 <= 0xEF)
    {
        if (text[1] == '\0' || text[2] == '\0')
            return false;
        const unsigned char b1 = static_cast<unsigned char>(text[1]);
        const unsigned char b2 = static_cast<unsigned char>(text[2]);
        if (!IsContinuation(b1) || !IsContinuation(b2))
            return false;
        if (b0 == 0xE0 && b1 < 0xA0)
            return false;
        if (b0 == 0xED && b1 >= 0xA0)
            return false;
        codepoint =
            ((b0 & 0x0F) << 12) |
            ((b1 & 0x3F) << 6) |
            (b2 & 0x3F);
        length = 3;
        return true;
    }

    if (b0 >= 0xF0 && b0 <= 0xF4)
    {
        if (text[1] == '\0' || text[2] == '\0' || text[3] == '\0')
            return false;
        const unsigned char b1 = static_cast<unsigned char>(text[1]);
        const unsigned char b2 = static_cast<unsigned char>(text[2]);
        const unsigned char b3 = static_cast<unsigned char>(text[3]);
        if (!IsContinuation(b1) || !IsContinuation(b2) || !IsContinuation(b3))
            return false;
        if (b0 == 0xF0 && b1 < 0x90)
            return false;
        if (b0 == 0xF4 && b1 >= 0x90)
            return false;
        codepoint =
            ((b0 & 0x07) << 18) |
            ((b1 & 0x3F) << 12) |
            ((b2 & 0x3F) << 6) |
            (b3 & 0x3F);
        length = 4;
        return true;
    }

    return false;
}

static bool IsCombiningOrEmojiSuffix(DWORD codepoint)
{
    return
        (codepoint >= 0x0300 && codepoint <= 0x036F) ||
        (codepoint >= 0x1AB0 && codepoint <= 0x1AFF) ||
        (codepoint >= 0x1DC0 && codepoint <= 0x1DFF) ||
        (codepoint >= 0x20D0 && codepoint <= 0x20FF) ||
        (codepoint >= 0xFE00 && codepoint <= 0xFE0F) ||
        (codepoint >= 0x1F3FB && codepoint <= 0x1F3FF) ||
        (codepoint >= 0xE0020 && codepoint <= 0xE007F);
}

static bool IsRegionalIndicator(DWORD codepoint)
{
    return codepoint >= 0x1F1E6 && codepoint <= 0x1F1FF;
}

static const char* NextUtf8Cluster(const char* current)
{
    if (!current || *current == '\0')
        return current;

    DWORD first = 0;
    size_t length = 0;
    if (!DecodeUtf8Scalar(current, first, length))
        return current + 1;

    const bool firstWasRegionalIndicator = IsRegionalIndicator(first);
    const char* p = current + length;
    bool allowRegionalPair = firstWasRegionalIndicator;

    while (p && *p != '\0')
    {
        DWORD codepoint = 0;
        size_t nextLength = 0;
        if (!DecodeUtf8Scalar(p, codepoint, nextLength))
            break;

        if (IsCombiningOrEmojiSuffix(codepoint))
        {
            p += nextLength;
            continue;
        }

        if (allowRegionalPair && IsRegionalIndicator(codepoint))
        {
            p += nextLength;
            allowRegionalPair = false;
            continue;
        }

        if (codepoint == 0x200D)
        {
            p += nextLength;
            if (*p == '\0')
                break;
            if (!DecodeUtf8Scalar(p, codepoint, nextLength))
                break;
            p += nextLength;
            continue;
        }

        break;
    }

    return p;
}

static const char* PrevUtf8Cluster(const char* start, const char* current)
{
    if (!start || !current || current <= start)
        return start;

    const char* cursor = start;
    while (cursor && *cursor != '\0' && cursor < current)
    {
        const char* next = NextUtf8Cluster(cursor);
        if (!next || next <= cursor)
            return cursor;
        if (next >= current)
            return cursor;
        cursor = next;
    }

    return cursor;
}
}

#if defined(_M_IX86)
#pragma comment(linker, "/EXPORT:BohCharNextExA=_BohCharNextExA@12")
#pragma comment(linker, "/EXPORT:BohCharPrevExA=_BohCharPrevExA@16")
#endif

extern "C" __declspec(dllexport) LPSTR WINAPI BohCharNextExA(
    WORD codePage,
    LPCSTR current,
    DWORD flags)
{
    if (codePage != CP_UTF8 || flags != 0)
    {
        if (BohUtf8CharBridge::ResolveRealCharApis())
        {
            return ((BohUtf8CharBridge::CharNextExA_t)
                BohUtf8CharBridge::g_origCharNextExA)(
                    codePage, current, flags);
        }
    }

    return const_cast<LPSTR>(BohUtf8CharBridge::NextUtf8Cluster(current));
}

extern "C" __declspec(dllexport) LPSTR WINAPI BohCharPrevExA(
    WORD codePage,
    LPCSTR start,
    LPCSTR current,
    DWORD flags)
{
    if (codePage != CP_UTF8 || flags != 0)
    {
        if (BohUtf8CharBridge::ResolveRealCharApis())
        {
            return ((BohUtf8CharBridge::CharPrevExA_t)
                BohUtf8CharBridge::g_origCharPrevExA)(
                    codePage, start, current, flags);
        }
    }

    return const_cast<LPSTR>(BohUtf8CharBridge::PrevUtf8Cluster(start, current));
}
