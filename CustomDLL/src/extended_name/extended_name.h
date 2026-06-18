#pragma once

#include <windows.h>
#include <cstddef>
#include <cstdint>
#include <string>

static const uint16_t EXT_NAME_PACKET_ID = 0x0BB7;
static const uint16_t EXT_NAME_PACKET_LEN = 233;
static const uint32_t EXT_NAME_PACKET_MAGIC = 0x4558544E; // 'EXTN'

LPVOID ExtendedNameProbeSharedBlock();
void ExtendedNameInit(bool enableSharedPolling, bool debugLogEnabled);
void ExtendedNameCleanup();

bool ExtendedNameLooksLikePacket(const char* data, size_t length);
void ExtendedNameParsePacket(BYTE* data, uint32_t length);

// Returns true when text was replaced. Mob entries are intentionally limited
// to exact nameplate matches so item names such as "Poring Card" cannot inherit
// a mob's @showmobinfo suffix. Portal NPCs use type 3 so their hover names can
// still be cleaned without forwarding them to the always-on NPC overlay.
bool ExtendedNameSubstitute(
    const std::wstring& text,
    std::wstring& substitutedText,
    bool& isNameplate);
