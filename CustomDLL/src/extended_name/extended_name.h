#pragma once

#include <windows.h>
#include <cstddef>
#include <cstdint>
#include <string>

static const uint16_t EXT_NAME_PACKET_ID = 0x0BB7;
static const uint16_t EXT_NAME_SHORT_FIELD_LEN = 24;
static const uint16_t EXT_NAME_LEGACY_TEXT_FIELD_LEN = 31;
static const uint16_t EXT_NAME_TEXT_FIELD_LEN = 128; // INT8_MAX visible bytes + NUL
static const uint16_t EXT_NAME_PACKET_LEN_LEGACY_V1 = 233;
static const uint16_t EXT_NAME_PACKET_LEN_LEGACY = 237;
static const uint16_t EXT_NAME_PACKET_TYPE_OFFSET_LEGACY = 232;
static const uint16_t EXT_NAME_PACKET_COLOR_OFFSET_LEGACY = 233;
static const uint16_t EXT_NAME_PACKET_LEN_V1 = 773;
static const uint16_t EXT_NAME_PACKET_LEN = 777;
static const uint16_t EXT_NAME_PACKET_TYPE_OFFSET = 772;
static const uint16_t EXT_NAME_PACKET_COLOR_OFFSET = 773;
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

bool ExtendedNameLookupNameplateColor(
    const std::wstring& text,
    COLORREF& color);
