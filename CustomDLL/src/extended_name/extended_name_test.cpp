#include <windows.h>
#include <cassert>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>

#include "extended_name.h"

static void WriteField(
    std::vector<BYTE>& packet,
    size_t offset,
    size_t capacity,
    const char* value)
{
    assert(offset + capacity <= packet.size());
    strncpy_s(
        reinterpret_cast<char*>(packet.data() + offset),
        capacity,
        value,
        _TRUNCATE);
}

static std::vector<BYTE> MakePacket(
    uint32_t gid,
    uint8_t type,
    const char* shortName,
    const char* extendedName,
    const char* partyName = "",
    uint32_t nameColor = 0,
    const char* titleName = "",
    const char* titleNameShort = "")
{
    std::vector<BYTE> packet(EXT_NAME_PACKET_LEN, 0);
    *reinterpret_cast<uint16_t*>(packet.data()) = EXT_NAME_PACKET_ID;
    *reinterpret_cast<uint16_t*>(packet.data() + 2) = EXT_NAME_PACKET_LEN;
    *reinterpret_cast<uint32_t*>(packet.data() + 4) =
        EXT_NAME_PACKET_MAGIC;
    *reinterpret_cast<uint32_t*>(packet.data() + 8) = gid;
    const size_t payload = 8;
    const size_t shortOffset = payload + 4;
    const size_t nameOffset = shortOffset + EXT_NAME_SHORT_FIELD_LEN;
    const size_t partyOffset = nameOffset + EXT_NAME_TEXT_FIELD_LEN;
    const size_t guildOffset = partyOffset + EXT_NAME_TEXT_FIELD_LEN;
    const size_t positionOffset = guildOffset + EXT_NAME_TEXT_FIELD_LEN;
    const size_t titleOffset = positionOffset + EXT_NAME_TEXT_FIELD_LEN;
    const size_t partyShortOffset = titleOffset + EXT_NAME_TEXT_FIELD_LEN;
    const size_t guildShortOffset =
        partyShortOffset + EXT_NAME_SHORT_FIELD_LEN;
    const size_t positionShortOffset =
        guildShortOffset + EXT_NAME_SHORT_FIELD_LEN;
    const size_t titleShortOffset =
        positionShortOffset + EXT_NAME_SHORT_FIELD_LEN;
    WriteField(packet, shortOffset, EXT_NAME_SHORT_FIELD_LEN, shortName);
    WriteField(packet, nameOffset, EXT_NAME_TEXT_FIELD_LEN, extendedName);
    WriteField(packet, partyOffset, EXT_NAME_TEXT_FIELD_LEN, partyName);
    WriteField(packet, titleOffset, EXT_NAME_TEXT_FIELD_LEN, titleName);
    WriteField(
        packet,
        titleShortOffset,
        EXT_NAME_SHORT_FIELD_LEN,
        titleNameShort);
    packet[EXT_NAME_PACKET_TYPE_OFFSET] = type;
    *reinterpret_cast<uint32_t*>(
        packet.data() + EXT_NAME_PACKET_COLOR_OFFSET) = nameColor;
    return packet;
}

int main()
{
    std::vector<BYTE> mob =
        MakePacket(1001, 1, "Poring", "Poring", "HP: 50/50 | Water 1");
    ExtendedNameParsePacket(mob.data(), static_cast<uint32_t>(mob.size()));

    std::wstring output;
    bool isNameplate = false;
    assert(ExtendedNameSubstitute(L"Poring", output, isNameplate));
    assert(isNameplate);
    assert(output.find(L"HP: 50/50") != std::wstring::npos);

    output.clear();
    isNameplate = false;
    assert(!ExtendedNameSubstitute(L"Poring Card", output, isNameplate));
    assert(!ExtendedNameSubstitute(L"Poring: hello", output, isNameplate));

    std::vector<BYTE> player =
        MakePacket(1002, 0, "Alice", "Alice the Brave");
    ExtendedNameParsePacket(
        player.data(), static_cast<uint32_t>(player.size()));

    output.clear();
    isNameplate = false;
    assert(ExtendedNameSubstitute(L"Alice: hello", output, isNameplate));
    assert(!isNameplate);
    assert(output == L"Alice the Brave: hello");

    std::string longName(127, 'X');
    std::vector<BYTE> longPlayer =
        MakePacket(1005, 0, "LongName", longName.c_str(), "", 0, "Administrator");
    ExtendedNameParsePacket(
        longPlayer.data(), static_cast<uint32_t>(longPlayer.size()));
    output.clear();
    isNameplate = false;
    assert(ExtendedNameSubstitute(L"LongName", output, isNameplate));
    assert(output.find(std::wstring(127, L'X')) != std::wstring::npos);
    assert(output.find(L"Administrator") != std::wstring::npos);

    std::vector<BYTE> colorOnly =
        MakePacket(1004, 0, "Bob", "", "", 0x00FF00);
    ExtendedNameParsePacket(
        colorOnly.data(), static_cast<uint32_t>(colorOnly.size()));
    COLORREF nameColor = CLR_INVALID;
    assert(ExtendedNameLookupNameplateColor(L"Bob", nameColor));
    assert(nameColor == RGB(0, 255, 0));

    std::vector<BYTE> portal =
        MakePacket(1003, 3, "East Gate#warp", "East Gate");
    assert(ExtendedNameLooksLikePacket(
        reinterpret_cast<const char*>(portal.data()), portal.size()));
    ExtendedNameParsePacket(
        portal.data(), static_cast<uint32_t>(portal.size()));

    output.clear();
    isNameplate = false;
    assert(ExtendedNameSubstitute(L"East Gate#warp", output, isNameplate));
    assert(output == L"East Gate");

    std::vector<BYTE> npcTitle =
        MakePacket(
            1006,
            2,
            "Dietrich",
            "Dietrich the Smith",
            "",
            0,
            "<Responsible for smelting products>",
            "<Responsible for smelt");
    ExtendedNameParsePacket(
        npcTitle.data(), static_cast<uint32_t>(npcTitle.size()));

    output.clear();
    isNameplate = false;
    assert(ExtendedNameSubstitute(L"Dietrich", output, isNameplate));
    assert(isNameplate);
    assert(output == L"Dietrich the Smith");

    output.clear();
    isNameplate = false;
    assert(ExtendedNameSubstitute(
        L"<Responsible for smelt", output, isNameplate));
    assert(!isNameplate);
    assert(output == L"<Responsible for smelting products>");

    portal[EXT_NAME_PACKET_TYPE_OFFSET] = 4;
    assert(!ExtendedNameLooksLikePacket(
        reinterpret_cast<const char*>(portal.data()), portal.size()));

    std::cout << "extended_name regression tests passed\n";
    return 0;
}
