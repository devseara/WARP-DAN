#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <tlhelp32.h>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <unordered_map>
#include <vector>

#include "extended_name.h"

static const uint32_t EXT_NAME_RING_MAGIC = 0x474E4952; // 'RING'
static const uint32_t EXT_NAME_RING_CAPACITY = 128;
static const uint32_t EXT_NAME_RING_HEADER_SIZE = 16;
static const uint32_t EXT_NAME_RING_SLOT_SIZE = 256;
static const uint32_t EXT_NAME_RING_PAYLOAD_SIZE =
    EXT_NAME_RING_SLOT_SIZE - sizeof(uint32_t);
static const uintptr_t RO_IMAGE_BASE = 0x00400000;
static const uintptr_t PACKET_DISPATCH_TABLE = 0x00CAA2E0;
static const uint16_t PACKET_DISPATCH_FIRST_ID = 0x0073;

static std::unordered_map<std::wstring, std::wstring> g_extNameMap;
static std::unordered_map<std::wstring, std::wstring> g_extPartyMap;
static std::unordered_map<std::wstring, std::wstring> g_extGuildMap;
static std::unordered_map<std::wstring, std::wstring> g_extPositionMap;
static std::unordered_map<std::wstring, uint8_t> g_extTypeMap;
static std::mutex g_extNameMutex;

static LPVOID g_extnBlock = nullptr;
static bool g_probeComplete = false;
static HANDLE g_pollThread = nullptr;
static HANDLE g_stopEvent = nullptr;
static uint32_t g_readSequence = 0;
static bool g_debugLogEnabled = false;
static LONG g_sharedLogBudget = 40;
static LONG g_packetLogBudget = 160;
static LONG g_rejectLogBudget = 40;

using NpcOverlaySink = void (__cdecl*)(uint32_t, uint8_t, const char*);
static NpcOverlaySink g_npcOverlaySink = nullptr;
static std::unordered_map<uint32_t, std::string> g_pendingNpcNames;
static std::mutex g_sinkMutex;

static void LogMsg(const char* fmt, ...)
{
    if (!g_debugLogEnabled)
        return;

    char buf[512];
    va_list args;
    va_start(args, fmt);
    vsnprintf(buf, sizeof(buf), fmt, args);
    va_end(args);

    HANDLE file = CreateFileW(
        L"boh_extname_visual.log",
        FILE_APPEND_DATA,
        FILE_SHARE_READ | FILE_SHARE_WRITE,
        nullptr,
        OPEN_ALWAYS,
        FILE_ATTRIBUTE_NORMAL,
        nullptr);
    if (file == INVALID_HANDLE_VALUE)
        return;

    DWORD written = 0;
    WriteFile(file, buf, (DWORD)strlen(buf), &written, nullptr);
    WriteFile(file, "\r\n", 2, &written, nullptr);
    CloseHandle(file);
}

static bool IsValidSharedBlock(BYTE* candidate)
{
    if (!candidate)
        return false;

    uint32_t magic = *reinterpret_cast<uint32_t*>(candidate);
    if (magic != EXT_NAME_PACKET_MAGIC)
        return false;

    uint32_t readyOrSequence = *reinterpret_cast<uint32_t*>(candidate + 4);
    uint32_t lengthOrFormat = *reinterpret_cast<uint32_t*>(candidate + 8);
    uint32_t capacity = *reinterpret_cast<uint32_t*>(candidate + 12);
    if (lengthOrFormat == EXT_NAME_RING_MAGIC &&
        capacity == EXT_NAME_RING_CAPACITY)
        return true;

    return (readyOrSequence == 0 || readyOrSequence == 1) &&
        lengthOrFormat <= 4092;
}

static BYTE* NormalizeExeVa(BYTE* exe, uintptr_t value)
{
    const uintptr_t exeBase = reinterpret_cast<uintptr_t>(exe);
    const uintptr_t scanEnd = exeBase + 64 * 1024 * 1024;
    if (value >= exeBase && value < scanEnd)
        return reinterpret_cast<BYTE*>(value);
    if (value >= RO_IMAGE_BASE && value < RO_IMAGE_BASE + 64 * 1024 * 1024)
        return exe + (value - RO_IMAGE_BASE);
    return nullptr;
}

static LPVOID FindActiveDispatcherBlock()
{
    HMODULE exeModule = GetModuleHandleW(nullptr);
    if (!exeModule)
        return nullptr;

    BYTE* exe = reinterpret_cast<BYTE*>(exeModule);
    __try
    {
        const uintptr_t entryOffset =
            PACKET_DISPATCH_TABLE - RO_IMAGE_BASE +
            (EXT_NAME_PACKET_ID - PACKET_DISPATCH_FIRST_ID) * sizeof(uint32_t);
        DWORD handlerVa = *reinterpret_cast<DWORD*>(exe + entryOffset);
        BYTE* handler = NormalizeExeVa(exe, handlerVa);
        if (!handler)
            return nullptr;

        if (handler[0] != 0x9C || handler[1] != 0x60 ||
            handler[2] != 0xBE)
            return nullptr;
        if (*reinterpret_cast<uint16_t*>(handler + 10) != EXT_NAME_PACKET_ID)
            return nullptr;

        DWORD blockVa = *reinterpret_cast<DWORD*>(handler + 35);
        BYTE* block = NormalizeExeVa(exe, blockVa);
        return IsValidSharedBlock(block) ? block : nullptr;
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        return nullptr;
    }
}

static std::wstring Utf8ToWide(const char* value)
{
    if (!value || !value[0])
        return L"";

    int chars = MultiByteToWideChar(CP_UTF8, 0, value, -1, nullptr, 0);
    if (chars <= 1)
        return L"";

    std::wstring result((size_t)chars, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, value, -1, &result[0], chars);
    result.resize((size_t)chars - 1);
    return result;
}

static std::string WidePreview(const std::wstring& value, size_t maxChars = 80)
{
    if (value.empty())
        return "";

    std::wstring trimmed = value.substr(0, maxChars);
    int bytes = WideCharToMultiByte(
        CP_UTF8, 0, trimmed.c_str(), (int)trimmed.length(),
        nullptr, 0, nullptr, nullptr);
    if (bytes <= 0)
        return "<wide-convert-failed>";

    std::string result((size_t)bytes, '\0');
    WideCharToMultiByte(
        CP_UTF8, 0, trimmed.c_str(), (int)trimmed.length(),
        &result[0], bytes, nullptr, nullptr);
    return result;
}

static LPVOID FindSharedBlock()
{
    LPVOID active = FindActiveDispatcherBlock();
    if (active)
        return active;

    HMODULE exe = GetModuleHandleW(nullptr);
    if (!exe)
        return nullptr;

    BYTE* start = reinterpret_cast<BYTE*>(exe);
    const size_t scanSize = 64 * 1024 * 1024;
    __try
    {
        for (size_t offset = 0; offset < scanSize - 16; offset += 4)
        {
            BYTE* candidate = start + offset;
            if (*reinterpret_cast<uint32_t*>(candidate) != EXT_NAME_PACKET_MAGIC)
                continue;

            if (IsValidSharedBlock(candidate))
                return candidate;
        }
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
    }
    return nullptr;
}

LPVOID ExtendedNameProbeSharedBlock()
{
    if (!g_probeComplete)
    {
        g_extnBlock = FindSharedBlock();
        g_probeComplete = true;
    }
    return g_extnBlock;
}

static NpcOverlaySink FindNpcOverlaySink()
{
    HANDLE snapshot = CreateToolhelp32Snapshot(
        TH32CS_SNAPMODULE | TH32CS_SNAPMODULE32,
        GetCurrentProcessId());
    if (snapshot == INVALID_HANDLE_VALUE)
        return nullptr;

    MODULEENTRY32W entry = {};
    entry.dwSize = sizeof(entry);
    NpcOverlaySink sink = nullptr;
    if (Module32FirstW(snapshot, &entry))
    {
        do
        {
            FARPROC proc = GetProcAddress(entry.hModule, "NpcOverlay_OnExtName");
            if (proc)
            {
                sink = reinterpret_cast<NpcOverlaySink>(proc);
                break;
            }
        } while (Module32NextW(snapshot, &entry));
    }
    CloseHandle(snapshot);
    return sink;
}

static void ForwardNpcName(uint32_t gid, uint8_t type, const char* name)
{
    if (type != 2 || !name || !name[0])
        return;

    std::vector<std::pair<uint32_t, std::string>> replay;
    NpcOverlaySink sink = nullptr;
    {
        std::lock_guard<std::mutex> lock(g_sinkMutex);
        g_pendingNpcNames[gid] = name;
        if (!g_npcOverlaySink)
        {
            g_npcOverlaySink = FindNpcOverlaySink();
            if (g_npcOverlaySink)
            {
                replay.reserve(g_pendingNpcNames.size());
                for (const auto& entry : g_pendingNpcNames)
                    replay.push_back(entry);
                g_pendingNpcNames.clear();
            }
        }
        sink = g_npcOverlaySink;
    }

    if (!sink)
        return;
    if (!replay.empty())
    {
        for (const auto& entry : replay)
            sink(entry.first, 2, entry.second.c_str());
    }
    else
    {
        sink(gid, type, name);
    }
}

void ExtendedNameParsePacket(BYTE* data, uint32_t length)
{
    bool hasHeader = false;
    uint32_t offset = 2;
    if (length >= EXT_NAME_PACKET_LEN)
    {
        uint16_t packetLength = *reinterpret_cast<uint16_t*>(data + 2);
        uint32_t magic = *reinterpret_cast<uint32_t*>(data + 4);
        hasHeader =
            packetLength == EXT_NAME_PACKET_LEN &&
            magic == EXT_NAME_PACKET_MAGIC;
    }

    if (hasHeader)
        offset = 8;
    else if (length < 226)
    {
        LONG budget = InterlockedDecrement(&g_rejectLogBudget);
        if (budget >= 0)
            LogMsg("[EXT:reject] len=%u is below minimum", length);
        return;
    }

    uint16_t packetType = *reinterpret_cast<uint16_t*>(data);
    if (packetType != EXT_NAME_PACKET_ID)
    {
        LONG budget = InterlockedDecrement(&g_rejectLogBudget);
        if (budget >= 0)
            LogMsg("[EXT:reject] type=%04X len=%u", packetType, length);
        return;
    }

    uint32_t gid = *reinterpret_cast<uint32_t*>(data + offset);
    char* shortName = reinterpret_cast<char*>(data + offset + 4);
    char* extName = reinterpret_cast<char*>(data + offset + 4 + 24);
    char* partyName = reinterpret_cast<char*>(data + offset + 4 + 24 + 31);
    char* guildName = reinterpret_cast<char*>(data + offset + 4 + 24 + 31 + 31);
    char* positionName =
        reinterpret_cast<char*>(data + offset + 4 + 24 + 31 + 31 + 31);
    char* partyNameShort =
        reinterpret_cast<char*>(data + offset + 4 + 24 + 31 + 31 + 31 + 31);
    char* guildNameShort =
        reinterpret_cast<char*>(data + offset + 4 + 24 + 31 + 31 + 31 + 31 + 24);
    char* positionNameShort =
        reinterpret_cast<char*>(data + offset + 4 + 24 + 31 + 31 + 31 + 31 + 24 + 24);

    shortName[23] = '\0';
    extName[30] = '\0';
    partyName[30] = '\0';
    guildName[30] = '\0';
    positionName[30] = '\0';
    partyNameShort[23] = '\0';
    guildNameShort[23] = '\0';
    positionNameShort[23] = '\0';

    uint8_t type = 0;
    if (hasHeader)
        type = *reinterpret_cast<uint8_t*>(data + 232);
    else if (length >= 227)
        type = *reinterpret_cast<uint8_t*>(data + 226);

    ForwardNpcName(gid, type, extName[0] ? extName : shortName);

    try
    {
        std::wstring wShort = Utf8ToWide(shortName);
        std::wstring wExt = Utf8ToWide(extName);
        std::wstring wParty = Utf8ToWide(partyName);
        std::wstring wPartyShort = Utf8ToWide(partyNameShort);
        std::wstring wGuild = Utf8ToWide(guildName);
        std::wstring wGuildShort = Utf8ToWide(guildNameShort);
        std::wstring wPosition = Utf8ToWide(positionName);
        std::wstring wPositionShort = Utf8ToWide(positionNameShort);

        std::lock_guard<std::mutex> lock(g_extNameMutex);
        if (!wShort.empty() &&
            (!wExt.empty() || !wParty.empty() || !wGuild.empty() ||
             !wPosition.empty()))
        {
            std::wstring composite;
            if (type == 1)
            {
                if (!wExt.empty())
                {
                    composite =
                        wExt.find(wShort) == 0 ? wExt : wShort + L" " + wExt;
                }
                else
                {
                    composite = wShort;
                }
                if (!wParty.empty())
                    composite += L" | " + wParty;
                if (!wGuild.empty())
                    composite += L" | " + wGuild;
                if (!wPosition.empty())
                    composite += L" | " + wPosition;
            }
            else if (type == 2 || type == 3)
            {
                composite = !wExt.empty() ? wExt : wShort;
            }
            else if (!wExt.empty())
            {
                composite =
                    wExt.find(wShort) == 0 ? wExt : wShort + L" " + wExt;
            }
            else
            {
                composite = wShort;
                if (!wParty.empty())
                    composite += L" [" + wParty + L"]";
                if (!wGuild.empty())
                    composite += L" {" + wGuild + L"}";
                if (!wPosition.empty())
                    composite += L" (" + wPosition + L")";
            }
            g_extNameMap[wShort] = composite;
            g_extTypeMap[wShort] = type;
        }
        if (!wPartyShort.empty() && !wParty.empty())
            g_extPartyMap[wPartyShort] = wParty;
        if (!wGuildShort.empty() && !wGuild.empty())
            g_extGuildMap[wGuildShort] = wGuild;
        if (!wPositionShort.empty() && !wPosition.empty())
            g_extPositionMap[wPositionShort] = wPosition;

        if (g_extNameMap.size() > 5000)
        {
            g_extNameMap.clear();
            g_extTypeMap.clear();
        }
        if (g_extPartyMap.size() > 5000)
            g_extPartyMap.clear();
        if (g_extGuildMap.size() > 5000)
            g_extGuildMap.clear();
        if (g_extPositionMap.size() > 5000)
            g_extPositionMap.clear();

        LONG budget = InterlockedDecrement(&g_packetLogBudget);
        if (budget >= 0)
        {
            LogMsg(
                "[EXT] gid=%u type=%u len=%u short=\"%s\" ext=\"%s\" "
                "party=\"%s\" guild=\"%s\" pos=\"%s\" maps=%u/%u/%u/%u",
                gid,
                (unsigned)type,
                length,
                WidePreview(wShort).c_str(),
                WidePreview(wExt).c_str(),
                WidePreview(wParty).c_str(),
                WidePreview(wGuild).c_str(),
                WidePreview(wPosition).c_str(),
                (unsigned)g_extNameMap.size(),
                (unsigned)g_extPartyMap.size(),
                (unsigned)g_extGuildMap.size(),
                (unsigned)g_extPositionMap.size());
        }
    }
    catch (...)
    {
        LogMsg(
            "[EXT:exception] parse exception gid=%u len=%u type=%u",
            gid, length, (unsigned)type);
    }
}

static bool HasNullTerminator(const char* value, size_t length)
{
    return memchr(value, '\0', length) != nullptr;
}

bool ExtendedNameLooksLikePacket(const char* data, size_t length)
{
    if (!data || length < EXT_NAME_PACKET_LEN)
        return false;
    if (*reinterpret_cast<const uint16_t*>(data) != EXT_NAME_PACKET_ID)
        return false;
    if (*reinterpret_cast<const uint16_t*>(data + 2) != EXT_NAME_PACKET_LEN)
        return false;
    if (*reinterpret_cast<const uint32_t*>(data + 4) != EXT_NAME_PACKET_MAGIC)
        return false;
    // 0=PC, 1=MOB, 2=NPC, 3=portal NPC. Portal names still participate in
    // hover-name substitution but are not forwarded to the always-on overlay.
    if (static_cast<uint8_t>(data[232]) > 3)
        return false;
    const char* shortName = data + 12;
    return shortName[0] != '\0' && HasNullTerminator(shortName, 24);
}

static void DrainRing(BYTE* base)
{
    volatile uint32_t* writeSequence =
        reinterpret_cast<volatile uint32_t*>(base + 4);
    for (;;)
    {
        uint32_t published = *writeSequence;
        MemoryBarrier();
        uint32_t pending = published - g_readSequence;
        if (pending == 0)
            break;
        if (pending > EXT_NAME_RING_CAPACITY)
        {
            uint32_t lost = pending - EXT_NAME_RING_CAPACITY;
            g_readSequence = published - EXT_NAME_RING_CAPACITY;
            LogMsg(
                "[SHARED:overflow] EXTN ring lost=%u write=%u read=%u",
                lost, published, g_readSequence);
        }

        uint32_t slotIndex =
            g_readSequence & (EXT_NAME_RING_CAPACITY - 1);
        BYTE* slot =
            base + EXT_NAME_RING_HEADER_SIZE +
            slotIndex * EXT_NAME_RING_SLOT_SIZE;
        uint32_t length = *reinterpret_cast<volatile uint32_t*>(slot);
        MemoryBarrier();

        if (length > 0 && length <= EXT_NAME_RING_PAYLOAD_SIZE)
        {
            BYTE packet[EXT_NAME_RING_PAYLOAD_SIZE];
            CopyMemory(packet, slot + sizeof(uint32_t), length);
            ExtendedNameParsePacket(packet, length);
        }
        else
        {
            LONG budget = InterlockedDecrement(&g_rejectLogBudget);
            if (budget >= 0)
                LogMsg(
                    "[SHARED:reject] EXTN ring slot=%u invalid len=%u",
                    slotIndex, length);
        }
        ++g_readSequence;
    }
}

static void PollSharedBlock()
{
    BYTE* base = reinterpret_cast<BYTE*>(ExtendedNameProbeSharedBlock());
    if (!base)
        return;

    uint32_t format = *reinterpret_cast<uint32_t*>(base + 8);
    uint32_t capacity = *reinterpret_cast<uint32_t*>(base + 12);
    if (format == EXT_NAME_RING_MAGIC &&
        capacity == EXT_NAME_RING_CAPACITY)
    {
        DrainRing(base);
        return;
    }

    volatile uint32_t* ready =
        reinterpret_cast<volatile uint32_t*>(base + 4);
    if (*ready != 1)
        return;

    uint32_t length = *reinterpret_cast<uint32_t*>(base + 8);
    if (length > 0 && length <= 4092)
    {
        LONG budget = InterlockedDecrement(&g_sharedLogBudget);
        if (budget >= 0)
            LogMsg("[SHARED] EXTN ready len=%u", length);
        ExtendedNameParsePacket(base + 12, length);
    }
    else
    {
        LONG budget = InterlockedDecrement(&g_rejectLogBudget);
        if (budget >= 0)
            LogMsg("[SHARED:reject] EXTN invalid len=%u", length);
    }
    *ready = 0;
}

static DWORD WINAPI PollThreadProc(LPVOID)
{
    for (;;)
    {
        PollSharedBlock();
        if (!g_stopEvent ||
            WaitForSingleObject(g_stopEvent, 2) != WAIT_TIMEOUT)
            break;
    }
    return 0;
}

void ExtendedNameInit(bool enableSharedPolling, bool debugLogEnabled)
{
    g_debugLogEnabled = debugLogEnabled;
    if (!enableSharedPolling || g_pollThread)
        return;

    if (!ExtendedNameProbeSharedBlock())
    {
        LogMsg("[INIT] EXTN shared block is absent; drain thread not needed");
        return;
    }

    g_stopEvent = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    if (g_stopEvent)
        g_pollThread =
            CreateThread(nullptr, 0, PollThreadProc, nullptr, 0, nullptr);
    if (!g_pollThread)
        LogMsg("[WARN] EXTN shared-block drain thread was not started");
}

void ExtendedNameCleanup()
{
    if (g_stopEvent)
        SetEvent(g_stopEvent);
    if (g_pollThread)
    {
        WaitForSingleObject(g_pollThread, 3000);
        CloseHandle(g_pollThread);
        g_pollThread = nullptr;
    }
    if (g_stopEvent)
    {
        CloseHandle(g_stopEvent);
        g_stopEvent = nullptr;
    }

    // Drain C++ containers while CRT heap is intact — see
    // ItemColorExtNameCleanup for the full explanation.
    // NO LOCK: all other threads are dead during DETACH.
    g_extNameMap.clear();
    g_extPartyMap.clear();
    g_extGuildMap.clear();
    g_extPositionMap.clear();
    g_extTypeMap.clear();
    g_pendingNpcNames.clear();
}

static bool IsChatNameMatch(
    const std::wstring& text,
    const std::wstring& shortName,
    size_t& position)
{
    position = text.find(shortName);
    while (position != std::wstring::npos)
    {
        size_t after = position + shortName.length();
        while (after < text.length() &&
               (text[after] == L' ' || text[after] == L'\t'))
            ++after;
        if (after < text.length() && text[after] == L':')
            return true;
        position = text.find(shortName, position + 1);
    }
    return false;
}

bool ExtendedNameSubstitute(
    const std::wstring& text,
    std::wstring& substitutedText,
    bool& isNameplate)
{
    substitutedText.clear();
    isNameplate = false;
    if (text.empty())
        return false;

    std::lock_guard<std::mutex> lock(g_extNameMutex);
    for (const auto& entry : g_extNameMap)
    {
        auto typeIt = g_extTypeMap.find(entry.first);
        uint8_t type = typeIt == g_extTypeMap.end() ? 0 : typeIt->second;
        if (text == entry.second ||
            (type == 0 && text.find(entry.second) != std::wstring::npos))
            continue;

        if (text == entry.first)
        {
            substitutedText = entry.second;
            isNameplate = true;
            return true;
        }

        // Mobs never use player-chat rendering. Restricting them to an exact
        // nameplate match prevents "Poring Card" and similar item names from
        // being replaced by @showmobinfo text.
        if (type == 1)
            continue;

        size_t position = std::wstring::npos;
        if (IsChatNameMatch(text, entry.first, position))
        {
            substitutedText = text;
            substitutedText.replace(
                position, entry.first.length(), entry.second);
            return true;
        }
    }

    const auto replaceExact = [&](const auto& map) -> bool
    {
        auto it = map.find(text);
        if (it == map.end())
            return false;
        substitutedText = it->second;
        return true;
    };

    return replaceExact(g_extPartyMap) ||
           replaceExact(g_extGuildMap) ||
           replaceExact(g_extPositionMap);
}
