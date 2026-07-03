#include "dll_integrity/dll_integrity.h"

#include <stdint.h>

namespace
{
static const DWORD kSha256InitialState[8] =
{
    0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a,
    0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19
};

static const DWORD kSha256RoundConstants[64] =
{
    0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5,
    0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
    0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3,
    0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
    0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc,
    0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
    0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7,
    0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
    0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13,
    0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
    0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3,
    0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
    0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5,
    0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
    0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208,
    0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2
};

struct Sha256Context
{
    BYTE data[64];
    DWORD dataLength;
    ULONGLONG bitLength;
    DWORD state[8];
};

static DWORD RotateRight(DWORD value, DWORD bits)
{
    return (value >> bits) | (value << (32 - bits));
}

static DWORD Choose(DWORD x, DWORD y, DWORD z)
{
    return (x & y) ^ (~x & z);
}

static DWORD Majority(DWORD x, DWORD y, DWORD z)
{
    return (x & y) ^ (x & z) ^ (y & z);
}

static DWORD BigSigma0(DWORD x)
{
    return RotateRight(x, 2) ^ RotateRight(x, 13) ^ RotateRight(x, 22);
}

static DWORD BigSigma1(DWORD x)
{
    return RotateRight(x, 6) ^ RotateRight(x, 11) ^ RotateRight(x, 25);
}

static DWORD SmallSigma0(DWORD x)
{
    return RotateRight(x, 7) ^ RotateRight(x, 18) ^ (x >> 3);
}

static DWORD SmallSigma1(DWORD x)
{
    return RotateRight(x, 17) ^ RotateRight(x, 19) ^ (x >> 10);
}

static void Sha256Transform(Sha256Context* context, const BYTE data[64])
{
    DWORD words[64];
    for (DWORD i = 0; i < 16; ++i)
    {
        words[i] = (static_cast<DWORD>(data[i * 4]) << 24) |
                   (static_cast<DWORD>(data[i * 4 + 1]) << 16) |
                   (static_cast<DWORD>(data[i * 4 + 2]) << 8) |
                   (static_cast<DWORD>(data[i * 4 + 3]));
    }

    for (DWORD i = 16; i < 64; ++i)
    {
        words[i] = SmallSigma1(words[i - 2]) + words[i - 7] +
                   SmallSigma0(words[i - 15]) + words[i - 16];
    }

    DWORD a = context->state[0];
    DWORD b = context->state[1];
    DWORD c = context->state[2];
    DWORD d = context->state[3];
    DWORD e = context->state[4];
    DWORD f = context->state[5];
    DWORD g = context->state[6];
    DWORD h = context->state[7];

    for (DWORD i = 0; i < 64; ++i)
    {
        const DWORD t1 = h + BigSigma1(e) + Choose(e, f, g) +
                         kSha256RoundConstants[i] + words[i];
        const DWORD t2 = BigSigma0(a) + Majority(a, b, c);
        h = g;
        g = f;
        f = e;
        e = d + t1;
        d = c;
        c = b;
        b = a;
        a = t1 + t2;
    }

    context->state[0] += a;
    context->state[1] += b;
    context->state[2] += c;
    context->state[3] += d;
    context->state[4] += e;
    context->state[5] += f;
    context->state[6] += g;
    context->state[7] += h;
}

static void Sha256Init(Sha256Context* context)
{
    context->dataLength = 0;
    context->bitLength = 0;
    for (DWORD i = 0; i < 8; ++i)
        context->state[i] = kSha256InitialState[i];
}

static void Sha256Update(Sha256Context* context, const BYTE* data, DWORD length)
{
    for (DWORD i = 0; i < length; ++i)
    {
        context->data[context->dataLength++] = data[i];
        if (context->dataLength == 64)
        {
            Sha256Transform(context, context->data);
            context->bitLength += 512;
            context->dataLength = 0;
        }
    }
}

static void Sha256Final(Sha256Context* context, BYTE digest[32])
{
    DWORD i = context->dataLength;

    context->data[i++] = 0x80;
    if (i > 56)
    {
        while (i < 64)
            context->data[i++] = 0;
        Sha256Transform(context, context->data);
        i = 0;
    }

    while (i < 56)
        context->data[i++] = 0;

    context->bitLength += static_cast<ULONGLONG>(context->dataLength) * 8;
    context->data[63] = static_cast<BYTE>(context->bitLength);
    context->data[62] = static_cast<BYTE>(context->bitLength >> 8);
    context->data[61] = static_cast<BYTE>(context->bitLength >> 16);
    context->data[60] = static_cast<BYTE>(context->bitLength >> 24);
    context->data[59] = static_cast<BYTE>(context->bitLength >> 32);
    context->data[58] = static_cast<BYTE>(context->bitLength >> 40);
    context->data[57] = static_cast<BYTE>(context->bitLength >> 48);
    context->data[56] = static_cast<BYTE>(context->bitLength >> 56);
    Sha256Transform(context, context->data);

    for (DWORD j = 0; j < 4; ++j)
    {
        digest[j]      = static_cast<BYTE>((context->state[0] >> (24 - j * 8)) & 0xff);
        digest[j + 4]  = static_cast<BYTE>((context->state[1] >> (24 - j * 8)) & 0xff);
        digest[j + 8]  = static_cast<BYTE>((context->state[2] >> (24 - j * 8)) & 0xff);
        digest[j + 12] = static_cast<BYTE>((context->state[3] >> (24 - j * 8)) & 0xff);
        digest[j + 16] = static_cast<BYTE>((context->state[4] >> (24 - j * 8)) & 0xff);
        digest[j + 20] = static_cast<BYTE>((context->state[5] >> (24 - j * 8)) & 0xff);
        digest[j + 24] = static_cast<BYTE>((context->state[6] >> (24 - j * 8)) & 0xff);
        digest[j + 28] = static_cast<BYTE>((context->state[7] >> (24 - j * 8)) & 0xff);
    }
}

#pragma pack(push, 1)
struct BohDllIntegritySeal
{
    char magic[32];
    BYTE digest[32];
};
#pragma pack(pop)

static const BYTE kUnsealedDigest[32] =
{
    0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5,
    0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5,
    0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5,
    0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5
};

#pragma section(".bohseal", read)
extern "C" __declspec(allocate(".bohseal")) const BohDllIntegritySeal g_bohDllIntegritySeal =
{
    "BOH_DLL_INTEGRITY_V1",
    {
        0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5,
        0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5,
        0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5,
        0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5, 0xa5
    }
};

static bool ReadExact(HANDLE file, void* buffer, DWORD bytesToRead)
{
    BYTE* out = static_cast<BYTE*>(buffer);
    DWORD total = 0;
    while (total < bytesToRead)
    {
        DWORD read = 0;
        if (!ReadFile(file, out + total, bytesToRead - total, &read, nullptr))
            return false;
        if (read == 0)
            return false;
        total += read;
    }
    return true;
}

static bool Seek(HANDLE file, LONG offset)
{
    return SetFilePointer(file, offset, nullptr, FILE_BEGIN) != INVALID_SET_FILE_POINTER ||
           GetLastError() == NO_ERROR;
}

static DWORD SectionSpan(const IMAGE_SECTION_HEADER& section)
{
    return section.Misc.VirtualSize > section.SizeOfRawData ?
           section.Misc.VirtualSize : section.SizeOfRawData;
}

static bool RvaToRawOffset(const wchar_t* path, DWORD rva, DWORD* rawOffset)
{
    HANDLE file = CreateFileW(path, GENERIC_READ,
                              FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                              nullptr, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE)
        return false;

    IMAGE_DOS_HEADER dos = {};
    if (!ReadExact(file, &dos, sizeof(dos)) || dos.e_magic != IMAGE_DOS_SIGNATURE)
    {
        CloseHandle(file);
        return false;
    }

    if (!Seek(file, dos.e_lfanew))
    {
        CloseHandle(file);
        return false;
    }

    DWORD signature = 0;
    IMAGE_FILE_HEADER fileHeader = {};
    if (!ReadExact(file, &signature, sizeof(signature)) ||
        signature != IMAGE_NT_SIGNATURE ||
        !ReadExact(file, &fileHeader, sizeof(fileHeader)))
    {
        CloseHandle(file);
        return false;
    }

    const LONG sectionOffset = dos.e_lfanew + sizeof(DWORD) +
                               sizeof(IMAGE_FILE_HEADER) +
                               fileHeader.SizeOfOptionalHeader;
    if (!Seek(file, sectionOffset))
    {
        CloseHandle(file);
        return false;
    }

    for (WORD i = 0; i < fileHeader.NumberOfSections; ++i)
    {
        IMAGE_SECTION_HEADER section = {};
        if (!ReadExact(file, &section, sizeof(section)))
        {
            CloseHandle(file);
            return false;
        }

        const DWORD span = SectionSpan(section);
        if (rva >= section.VirtualAddress && rva < section.VirtualAddress + span)
        {
            const DWORD delta = rva - section.VirtualAddress;
            if (delta >= section.SizeOfRawData)
            {
                CloseHandle(file);
                return false;
            }

            *rawOffset = section.PointerToRawData + delta;
            CloseHandle(file);
            return true;
        }
    }

    CloseHandle(file);
    return false;
}

static bool HashFileWithZeroedSeal(const wchar_t* path, DWORD sealOffset, BYTE digest[32])
{
    HANDLE file = CreateFileW(path, GENERIC_READ,
                              FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE,
                              nullptr, OPEN_EXISTING,
                              FILE_ATTRIBUTE_NORMAL | FILE_FLAG_SEQUENTIAL_SCAN,
                              nullptr);
    if (file == INVALID_HANDLE_VALUE)
        return false;

    Sha256Context context;
    Sha256Init(&context);

    BYTE buffer[8192];
    ULONGLONG fileOffset = 0;
    bool ok = true;

    for (;;)
    {
        DWORD read = 0;
        if (!ReadFile(file, buffer, sizeof(buffer), &read, nullptr))
        {
            ok = false;
            break;
        }
        if (read == 0)
            break;

        const ULONGLONG chunkStart = fileOffset;
        const ULONGLONG chunkEnd = fileOffset + read;
        const ULONGLONG sealStart = sealOffset;
        const ULONGLONG sealEnd = sealStart + sizeof(g_bohDllIntegritySeal.digest);

        if (chunkStart < sealEnd && chunkEnd > sealStart)
        {
            ULONGLONG zeroStart = sealStart > chunkStart ? sealStart : chunkStart;
            ULONGLONG zeroEnd = sealEnd < chunkEnd ? sealEnd : chunkEnd;
            for (ULONGLONG i = zeroStart; i < zeroEnd; ++i)
                buffer[i - chunkStart] = 0;
        }

        Sha256Update(&context, buffer, read);
        fileOffset = chunkEnd;
    }

    CloseHandle(file);
    if (!ok)
        return false;

    Sha256Final(&context, digest);
    return true;
}

static bool BytesEqual(const BYTE* a, const BYTE* b, DWORD length)
{
    BYTE diff = 0;
    for (DWORD i = 0; i < length; ++i)
        diff |= a[i] ^ b[i];
    return diff == 0;
}

static bool IsUnsealedDigest(const BYTE digest[32])
{
    return BytesEqual(digest, kUnsealedDigest, sizeof(kUnsealedDigest));
}

static void CopyExpectedDigest(BYTE digest[32])
{
    for (DWORD i = 0; i < sizeof(g_bohDllIntegritySeal.digest); ++i)
        digest[i] = g_bohDllIntegritySeal.digest[i];
}

static void LogIntegrityFailure(const wchar_t* reason)
{
    OutputDebugStringW(L"[BOH] DLL integrity verification failed: ");
    OutputDebugStringW(reason);
    OutputDebugStringW(L"\r\n");
}
}

bool BohVerifyDllIntegrity(HMODULE module)
{
    if (module == nullptr)
    {
        LogIntegrityFailure(L"missing module handle");
        return false;
    }

    wchar_t path[MAX_PATH] = {};
    const DWORD pathLength = GetModuleFileNameW(module, path, MAX_PATH);
    if (pathLength == 0 || pathLength >= MAX_PATH)
    {
        LogIntegrityFailure(L"could not resolve DLL path");
        return false;
    }

    BYTE expected[32] = {};
    BYTE actual[32] = {};
    CopyExpectedDigest(expected);

    if (IsUnsealedDigest(expected))
    {
        LogIntegrityFailure(L"DLL was not sealed after link");
        return false;
    }

    const DWORD digestRva = static_cast<DWORD>(
        reinterpret_cast<const BYTE*>(&g_bohDllIntegritySeal.digest[0]) -
        reinterpret_cast<const BYTE*>(module));

    DWORD digestRawOffset = 0;
    if (!RvaToRawOffset(path, digestRva, &digestRawOffset))
    {
        LogIntegrityFailure(L"could not map seal RVA to file offset");
        return false;
    }

    if (!HashFileWithZeroedSeal(path, digestRawOffset, actual))
    {
        LogIntegrityFailure(L"could not hash DLL file");
        return false;
    }

    if (!BytesEqual(expected, actual, sizeof(actual)))
    {
        LogIntegrityFailure(L"digest mismatch");
        return false;
    }

    return true;
}
