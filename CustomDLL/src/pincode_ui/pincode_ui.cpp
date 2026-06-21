#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <windowsx.h>
#include <stdint.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>

#ifndef PINCODE_UI_DEBUG
#define PINCODE_UI_DEBUG 0
#endif

typedef void (__cdecl *PincodeSendCheckFn)(uint32_t aid, const char* pin);
typedef void (__cdecl *PincodeSendSetFn)(uint32_t aid, const char* pin);
typedef void (__cdecl *PincodeSendChangeFn)(uint32_t aid, const char* oldPin, const char* newPin);

enum PincodeState
{
    PINCODE_ASK = 1,
    PINCODE_NOTSET = 2,
    PINCODE_EXPIRED = 3,
    PINCODE_NEW = 4,
    PINCODE_ILLEGAL = 5,
    PINCODE_PASSED = 7,
    PINCODE_WRONG = 8
};

enum PincodeStep
{
    STEP_VERIFY = 0,
    STEP_NEW = 1,
    STEP_CONFIRM = 2
};

enum PincodeResult
{
    RESULT_NONE = 0,
    RESULT_CHECK = 1,
    RESULT_SET = 2,
    RESULT_CHANGE = 3
};

static const char* kPincodeClassName = "BOH_Pincode_UI";
static const int ID_DIGIT_BASE = 1000;
static const int ID_RESET = 1010;
static const int ID_CONFIRM = 1011;
static const int ID_CHANGE = 1012;
static const int ID_CANCEL = 1013;
static const int ID_CLOSE = 1014;

static const int kWindowWidth = 540;
static const int kTitleHeight = 18;
static const int kBgWidth = 540;
static const int kBgHeight = 320;
static const int kWindowHeight = kTitleHeight + kBgHeight;
static const UINT WM_PINCODE_SERVER_STATE = WM_APP + 0x5C1;
static const UINT WM_PINCODE_REOPEN_STATE = WM_APP + 0x5C2;

static volatile LONG g_pincodeUiOpen = 0;
static HWND g_pincodeHwnd = nullptr;
static HWND g_gameHwnd = nullptr;
static bool g_assetsLoaded = false;
static HBITMAP g_bgBitmap = nullptr;
static HBITMAP g_confirmBitmap = nullptr;
static HBITMAP g_changeBitmap = nullptr;
static HBITMAP g_cancelBitmap = nullptr;
static HBITMAP g_resetBitmap = nullptr;
static HBITMAP g_confirmBitmaps[3] = {};
static HBITMAP g_changeBitmaps[3] = {};
static HBITMAP g_cancelBitmaps[3] = {};
static HBITMAP g_resetBitmaps[3] = {};
static HBITMAP g_digitBitmaps[10][3] = {};

struct PincodeDialog
{
    uint32_t seed;
    uint32_t aid;
    uint32_t state;
    PincodeSendCheckFn sendCheck;
    PincodeSendSetFn sendSet;
    PincodeSendChangeFn sendChange;

    HWND hwnd;
    HFONT uiFont;
    HFONT smallFont;
    HFONT digitFont;
    HFONT resetFont;
    HFONT titleFont;

    HBITMAP bgBitmap;
    HBITMAP confirmBitmap;
    HBITMAP changeBitmap;
    HBITMAP cancelBitmap;
    HBITMAP resetBitmap;
    HBITMAP confirmBitmaps[3];
    HBITMAP changeBitmaps[3];
    HBITMAP cancelBitmaps[3];
    HBITMAP resetBitmaps[3];
    HBITMAP digitBitmaps[10][3];

    int digitSlots[10];
    int step;
    int currentLen;
    char current[5];
    char oldPin[5];
    char newPin[5];
    char statusText[96];
    int result;
    int pendingResult;
    int hotId;
    int downId;
    DWORD createdTick;
    char closeReason[64];
    bool waiting;
    bool done;
};

static void PincodeDebug(const char* fmt, ...)
{
#if PINCODE_UI_DEBUG
    char msg[512];
    va_list args;
    va_start(args, fmt);
    _vsnprintf_s(msg, sizeof(msg), _TRUNCATE, fmt, args);
    va_end(args);

    char line[560];
    _snprintf_s(line, sizeof(line), _TRUNCATE, "[PincodeUI] %s\r\n", msg);
    OutputDebugStringA(line);
#else
    (void)fmt;
#endif
}

static void SendResult(PincodeDialog* dlg);

static RECT RectFromXYWH(int x, int y, int w, int h)
{
    RECT rc = {x, y, x + w, y + h};
    return rc;
}

static bool PtInRectXY(const RECT* rc, int x, int y)
{
    return x >= rc->left && x < rc->right && y >= rc->top && y < rc->bottom;
}

static void JoinPath(char* out, size_t outSize, const char* a, const char* b)
{
    if (!out || outSize == 0)
        return;
    out[0] = '\0';
    if (!a || !b)
        return;

    size_t len = strlen(a);
    if (len > 0 && (a[len - 1] == '\\' || a[len - 1] == '/'))
        _snprintf_s(out, outSize, _TRUNCATE, "%s%s", a, b);
    else
        _snprintf_s(out, outSize, _TRUNCATE, "%s\\%s", a, b);
}

static void GetExeDir(char* out, size_t outSize)
{
    if (!out || outSize == 0)
        return;
    out[0] = '\0';

    GetModuleFileNameA(nullptr, out, static_cast<DWORD>(outSize));
    char* slash = strrchr(out, '\\');
    if (slash)
        *slash = '\0';
}

static bool FileExistsA(const char* path)
{
    DWORD attrs = GetFileAttributesA(path);
    return attrs != INVALID_FILE_ATTRIBUTES && (attrs & FILE_ATTRIBUTE_DIRECTORY) == 0;
}

struct NativeFileBytes
{
    unsigned char* data;
    size_t size;
};

#pragma pack(push, 1)
struct BmpFileHeader
{
    uint16_t type;
    uint32_t size;
    uint16_t reserved1;
    uint16_t reserved2;
    uint32_t offBits;
};
#pragma pack(pop)

static const uintptr_t kClientCFileVtable = 0x00FD3074;
static const uintptr_t kClientCFileOpen = 0x00573750;
static const uintptr_t kClientCFileRead = 0x00573980;
static const uintptr_t kClientCFileClose = 0x00573060;

typedef bool (__thiscall *ClientCFileOpenFn)(void* self, const char* path, int mode, int fromPak, int flags);
typedef void (__thiscall *ClientCFileReadFn)(void* self, void* buffer, int size);
typedef void (__thiscall *ClientCFileCloseFn)(void* self);

static void InitClientCFile(unsigned char file[0x2C])
{
    memset(file, 0, 0x2C);
    *reinterpret_cast<uint32_t*>(file + 0x00) = static_cast<uint32_t>(kClientCFileVtable);
    *reinterpret_cast<int32_t*>(file + 0x04) = -1;
    *reinterpret_cast<uint32_t*>(file + 0x24) = 0;
    *reinterpret_cast<uint32_t*>(file + 0x28) = 0x0F;
    file[0x14] = '\0';
}

static void FreeNativeFileBytes(NativeFileBytes* bytes)
{
    if (!bytes)
        return;
    if (bytes->data)
        HeapFree(GetProcessHeap(), 0, bytes->data);
    bytes->data = nullptr;
    bytes->size = 0;
}

static bool ReadClientFileNative(const char* relativePath, NativeFileBytes* out)
{
    if (!relativePath || !out)
        return false;

    out->data = nullptr;
    out->size = 0;

    unsigned char file[0x2C];
    InitClientCFile(file);

    bool opened = false;
    __try
    {
        ClientCFileOpenFn openFn = reinterpret_cast<ClientCFileOpenFn>(kClientCFileOpen);
        ClientCFileReadFn readFn = reinterpret_cast<ClientCFileReadFn>(kClientCFileRead);
        ClientCFileCloseFn closeFn = reinterpret_cast<ClientCFileCloseFn>(kClientCFileClose);

        opened = openFn(file, relativePath, 0, 1, 0);
        if (!opened)
        {
            closeFn(file);
            return false;
        }

        uint32_t fileSize = *reinterpret_cast<uint32_t*>(file + 0x10);
        if (fileSize == 0 || fileSize > 16 * 1024 * 1024)
        {
            closeFn(file);
            return false;
        }

        unsigned char* buffer = reinterpret_cast<unsigned char*>(
            HeapAlloc(GetProcessHeap(), 0, fileSize));
        if (!buffer)
        {
            closeFn(file);
            return false;
        }

        readFn(file, buffer, static_cast<int>(fileSize));
        closeFn(file);

        out->data = buffer;
        out->size = static_cast<size_t>(fileSize);
        return true;
    }
    __except (EXCEPTION_EXECUTE_HANDLER)
    {
        if (opened)
        {
            __try
            {
                reinterpret_cast<ClientCFileCloseFn>(kClientCFileClose)(file);
            }
            __except (EXCEPTION_EXECUTE_HANDLER)
            {
            }
        }
        FreeNativeFileBytes(out);
        return false;
    }
}

static bool TryNativeAssetPath(const char* dir, const char* fileName, NativeFileBytes* out)
{
    char relativePath[MAX_PATH];
    JoinPath(relativePath, sizeof(relativePath), dir, fileName);
    return ReadClientFileNative(relativePath, out);
}

static bool LoadClientAssetBytes(const char* fileName, NativeFileBytes* out)
{
    if (!fileName || !out)
        return false;

    static const char kBasicInterfaceDir[] =
        "texture\\"
        "\xC0\xAF\xC0\xFA\xC0\xCE\xC5\xCD\xC6\xE4\xC0\xCC\xBD\xBA"
        "\\basic_interface";
    static const char kUiTextureDir[] =
        "texture\\"
        "\xC0\xAF\xC0\xFA\xC0\xCE\xC5\xCD\xC6\xE4\xC0\xCC\xBD\xBA";
    static const char kDataBasicInterfaceDir[] =
        "data\\texture\\"
        "\xC0\xAF\xC0\xFA\xC0\xCE\xC5\xCD\xC6\xE4\xC0\xCC\xBD\xBA"
        "\\basic_interface";

    if (TryNativeAssetPath(kBasicInterfaceDir, fileName, out) ||
        TryNativeAssetPath(kUiTextureDir, fileName, out) ||
        TryNativeAssetPath(kDataBasicInterfaceDir, fileName, out) ||
        ReadClientFileNative(fileName, out))
    {
        return true;
    }

    return false;
}

static HBITMAP CreateBitmapFromBmpBytes(const unsigned char* bytes, size_t size)
{
    if (!bytes || size < sizeof(BmpFileHeader) + sizeof(BITMAPINFOHEADER))
        return nullptr;

    const BmpFileHeader* header = reinterpret_cast<const BmpFileHeader*>(bytes);
    if (header->type != 0x4D42 || header->offBits >= size)
        return nullptr;

    const BITMAPINFO* info = reinterpret_cast<const BITMAPINFO*>(bytes + sizeof(BmpFileHeader));
    if (info->bmiHeader.biSize < sizeof(BITMAPINFOHEADER) ||
        sizeof(BmpFileHeader) + info->bmiHeader.biSize > size)
    {
        return nullptr;
    }

    HDC dc = GetDC(nullptr);
    if (!dc)
        return nullptr;

    HBITMAP bitmap = CreateDIBitmap(
        dc,
        &info->bmiHeader,
        CBM_INIT,
        bytes + header->offBits,
        info,
        DIB_RGB_COLORS);
    ReleaseDC(nullptr, dc);
    return bitmap;
}

static bool TryAssetPath(const char* dir, const char* fileName, char* out, size_t outSize)
{
    char candidate[MAX_PATH];
    JoinPath(candidate, sizeof(candidate), dir, fileName);
    if (!FileExistsA(candidate))
        return false;

    _snprintf_s(out, outSize, _TRUNCATE, "%s", candidate);
    return true;
}

static bool FindAssetInTextureTree(const char* textureDir, const char* fileName, char* out, size_t outSize)
{
    if (!textureDir || !fileName)
        return false;

    char pattern[MAX_PATH];
    JoinPath(pattern, sizeof(pattern), textureDir, "*");

    WIN32_FIND_DATAA data;
    HANDLE find = FindFirstFileA(pattern, &data);
    if (find == INVALID_HANDLE_VALUE)
        return false;

    bool found = false;
    do
    {
        if (strcmp(data.cFileName, ".") == 0 || strcmp(data.cFileName, "..") == 0)
            continue;
        if ((data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) == 0)
            continue;

        char localeDir[MAX_PATH];
        JoinPath(localeDir, sizeof(localeDir), textureDir, data.cFileName);

        char basicDir[MAX_PATH];
        JoinPath(basicDir, sizeof(basicDir), localeDir, "basic_interface");
        if (TryAssetPath(basicDir, fileName, out, outSize) ||
            TryAssetPath(localeDir, fileName, out, outSize))
        {
            found = true;
            break;
        }
    } while (FindNextFileA(find, &data));

    FindClose(find);
    return found;
}

static bool FindAssetRecursive(const char* dir, const char* fileName, char* out, size_t outSize, int depth)
{
    if (!dir || !fileName || depth < 0)
        return false;

    char pattern[MAX_PATH];
    JoinPath(pattern, sizeof(pattern), dir, "*");

    WIN32_FIND_DATAA data;
    HANDLE find = FindFirstFileA(pattern, &data);
    if (find == INVALID_HANDLE_VALUE)
        return false;

    bool found = false;
    do
    {
        if (strcmp(data.cFileName, ".") == 0 || strcmp(data.cFileName, "..") == 0)
            continue;

        char full[MAX_PATH];
        JoinPath(full, sizeof(full), dir, data.cFileName);

        if (data.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)
        {
            if (FindAssetRecursive(full, fileName, out, outSize, depth - 1))
            {
                found = true;
                break;
            }
        }
        else if (_stricmp(data.cFileName, fileName) == 0)
        {
            _snprintf_s(out, outSize, _TRUNCATE, "%s", full);
            found = true;
            break;
        }
    } while (FindNextFileA(find, &data));

    FindClose(find);
    return found;
}

static bool FindClientAsset(const char* fileName, char* out, size_t outSize)
{
    char exeDir[MAX_PATH];
    GetExeDir(exeDir, sizeof(exeDir));

    char dataDir[MAX_PATH];
    JoinPath(dataDir, sizeof(dataDir), exeDir, "data");

    char textureDir[MAX_PATH];
    JoinPath(textureDir, sizeof(textureDir), dataDir, "texture");
    if (FindAssetInTextureTree(textureDir, fileName, out, outSize))
        return true;

    if (FindAssetRecursive(dataDir, fileName, out, outSize, 4))
        return true;

    char skinDir[MAX_PATH];
    JoinPath(skinDir, sizeof(skinDir), exeDir, "Skin");
    if (FindAssetRecursive(skinDir, fileName, out, outSize, 5))
        return true;

    return FindAssetRecursive(exeDir, fileName, out, outSize, 2);
}

static HBITMAP LoadClientBitmap(const char* fileName)
{
    NativeFileBytes bytes = {};
    if (LoadClientAssetBytes(fileName, &bytes))
    {
        HBITMAP nativeBitmap = CreateBitmapFromBmpBytes(bytes.data, bytes.size);
        FreeNativeFileBytes(&bytes);
        if (nativeBitmap)
            return nativeBitmap;

        PincodeDebug("native asset decode failed: %s", fileName);
    }

    char path[MAX_PATH];
    if (!FindClientAsset(fileName, path, sizeof(path)))
    {
        PincodeDebug("asset not found: %s", fileName);
        return nullptr;
    }

    HBITMAP bitmap = reinterpret_cast<HBITMAP>(LoadImageA(
        nullptr,
        path,
        IMAGE_BITMAP,
        0,
        0,
        LR_LOADFROMFILE | LR_CREATEDIBSECTION));

    if (!bitmap)
        PincodeDebug("asset load failed: %s err=%lu", fileName, GetLastError());
    return bitmap;
}

static int LoadBitmapTriplet(HBITMAP out[3], const char* normal, const char* over, const char* press)
{
    int loaded = 0;
    out[0] = normal ? LoadClientBitmap(normal) : nullptr;
    out[1] = over ? LoadClientBitmap(over) : nullptr;
    out[2] = press ? LoadClientBitmap(press) : nullptr;

    for (int i = 0; i < 3; ++i)
        if (out[i])
            ++loaded;

    if (!out[1])
        out[1] = out[0];
    if (!out[2])
        out[2] = out[1] ? out[1] : out[0];
    return loaded;
}

static void EnsureSharedBitmaps()
{
    if (g_assetsLoaded)
        return;

    g_bgBitmap = LoadClientBitmap("2ndpassword_bg.bmp");
    g_confirmBitmap = LoadClientBitmap("btn_big_ok.bmp");
    g_changeBitmap = LoadClientBitmap("btn_e_change_a.bmp");
    g_cancelBitmap = LoadClientBitmap("btn_cancel2_normal.bmp");
    g_resetBitmap = LoadClientBitmap("reset-a.bmp");
    int confirmAssets = LoadBitmapTriplet(g_confirmBitmaps, "btn_big_ok.bmp", nullptr, nullptr);
    int changeAssets = LoadBitmapTriplet(g_changeBitmaps, "btn_e_change_a.bmp", "btn_e_change_b.bmp", "btn_e_change_c.bmp");
    if (!g_changeBitmaps[0])
    {
        g_changeBitmaps[0] = g_changeBitmap;
        g_changeBitmaps[1] = g_changeBitmap;
        g_changeBitmaps[2] = g_changeBitmap;
    }
    int cancelAssets = LoadBitmapTriplet(g_cancelBitmaps, "btn_cancel2_normal.bmp", "btn_cancel2_over.bmp", "btn_cancel2_press.bmp");
    if (!g_cancelBitmaps[0])
    {
        g_cancelBitmaps[0] = g_cancelBitmap;
        g_cancelBitmaps[1] = g_cancelBitmap;
        g_cancelBitmaps[2] = g_cancelBitmap;
    }
    int resetAssets = LoadBitmapTriplet(g_resetBitmaps, "reset-a.bmp", "reset-b.bmp", "reset-c.bmp");
    int digitAssets = 0;
    for (int digit = 0; digit < 10; ++digit)
    {
        for (int state = 0; state < 3; ++state)
        {
            char fileName[16];
            _snprintf_s(fileName, sizeof(fileName), _TRUNCATE, "%d-%c.bmp", digit, 'a' + state);
            g_digitBitmaps[digit][state] = LoadClientBitmap(fileName);
            if (g_digitBitmaps[digit][state])
                ++digitAssets;
        }
    }
    g_assetsLoaded = true;

    PincodeDebug("asset cache ready bg=%d ok=%d change=%d/3 cancel=%d/3 reset=%d/3 digits=%d/30",
        g_bgBitmap ? 1 : 0,
        confirmAssets,
        changeAssets,
        cancelAssets,
        resetAssets,
        digitAssets);
}

static BOOL CALLBACK FindGameWindowProc(HWND hwnd, LPARAM lParam)
{
    DWORD targetPid = GetCurrentProcessId();
    DWORD pid = 0;
    GetWindowThreadProcessId(hwnd, &pid);
    if (pid != targetPid || !IsWindowVisible(hwnd) || GetWindow(hwnd, GW_OWNER) != nullptr)
        return TRUE;

    char title[128] = {};
    DWORD_PTR unused = 0;
    if (!SendMessageTimeoutA(hwnd, WM_GETTEXT, sizeof(title), reinterpret_cast<LPARAM>(title),
        SMTO_ABORTIFHUNG | SMTO_BLOCK, 50, &unused))
    {
        return TRUE;
    }

    if (title[0] == '\0')
        return TRUE;

    HWND* out = reinterpret_cast<HWND*>(lParam);
    if (strstr(title, "Ragnarok") != nullptr)
    {
        *out = hwnd;
        return FALSE;
    }

    if (*out == nullptr)
        *out = hwnd;
    return TRUE;
}

static HWND FindGameWindow()
{
    if (g_gameHwnd && IsWindow(g_gameHwnd))
    {
        PincodeDebug("using cached game parent hwnd=%p", g_gameHwnd);
        return g_gameHwnd;
    }

    HWND hwnd = nullptr;
    EnumWindows(FindGameWindowProc, reinterpret_cast<LPARAM>(&hwnd));
    if (hwnd && IsWindow(hwnd))
        g_gameHwnd = hwnd;
    return hwnd;
}

static void CenterWindow(HWND hwnd, HWND parent, int width, int height)
{
    RECT area = {};
    LONG style = GetWindowLongA(hwnd, GWL_STYLE);
    if ((style & WS_CHILD) && parent && GetClientRect(parent, &area))
    {
        int clientW = area.right - area.left;
        int clientH = area.bottom - area.top;
        int x = (clientW - width) / 2;
        int y = (clientH - height) / 2;
        if (x < 0)
            x = 0;
        if (y < 0)
            y = 0;
        SetWindowPos(hwnd, HWND_TOP, x, y, width, height, SWP_SHOWWINDOW);
        return;
    }

    if (parent && GetWindowRect(parent, &area))
    {
        int x = area.left + ((area.right - area.left) - width) / 2;
        int y = area.top + ((area.bottom - area.top) - height) / 2;
        SetWindowPos(hwnd, HWND_TOP, x, y, width, height, SWP_NOACTIVATE | SWP_SHOWWINDOW);
        return;
    }

    SystemParametersInfoA(SPI_GETWORKAREA, 0, &area, 0);
    int x = area.left + ((area.right - area.left) - width) / 2;
    int y = area.top + ((area.bottom - area.top) - height) / 2;
    SetWindowPos(hwnd, HWND_TOP, x, y, width, height, SWP_NOACTIVATE | SWP_SHOWWINDOW);
}

static void EncryptPin(uint32_t seed, const char plain[5], char encrypted[5])
{
    unsigned char tab[10] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};

    for (int i = 1; i < 10; ++i)
    {
        seed = 0x881234u + seed * 0x3498u;
        int pos = static_cast<int>(seed % (i + 1));
        if (i != pos)
        {
            unsigned char tmp = tab[i];
            tab[i] = tab[pos];
            tab[pos] = tmp;
        }
    }

    for (int i = 0; i < 4; ++i)
    {
        int wanted = plain[i] - '0';
        int encoded = 0;
        for (int n = 0; n < 10; ++n)
        {
            if (tab[n] == wanted)
            {
                encoded = n;
                break;
            }
        }
        encrypted[i] = static_cast<char>('0' + encoded);
    }
    encrypted[4] = '\0';
}

static void BuildDigitSlots(PincodeDialog* dlg)
{
    for (int i = 0; i < 10; ++i)
        dlg->digitSlots[i] = i;

    uint32_t value = dlg->seed ^ 0x5A17C0DEu;
    for (int i = 9; i > 0; --i)
    {
        value = value * 1103515245u + 12345u;
        int j = static_cast<int>((value >> 16) % (i + 1));
        int tmp = dlg->digitSlots[i];
        dlg->digitSlots[i] = dlg->digitSlots[j];
        dlg->digitSlots[j] = tmp;
    }
}

static void ResetEntry(PincodeDialog* dlg)
{
    dlg->currentLen = 0;
    memset(dlg->current, 0, sizeof(dlg->current));
}

static void RedrawPincodeWindow(HWND hwnd)
{
    if (hwnd && IsWindow(hwnd))
        RedrawWindow(hwnd, nullptr, nullptr, RDW_INVALIDATE | RDW_UPDATENOW | RDW_NOERASE);
}

static void SetStatus(PincodeDialog* dlg, const char* text)
{
    if (!dlg)
        return;
    _snprintf_s(dlg->statusText, sizeof(dlg->statusText), _TRUNCATE, "%s", text ? text : "");
    RedrawPincodeWindow(dlg->hwnd);
}

static void SetCloseReason(PincodeDialog* dlg, const char* reason)
{
    if (!dlg || dlg->closeReason[0] != '\0')
        return;
    _snprintf_s(dlg->closeReason, sizeof(dlg->closeReason), _TRUNCATE, "%s", reason ? reason : "unknown");
}

static bool IgnoreEarlyClose(PincodeDialog* dlg, const char* reason)
{
    if (!dlg)
        return false;

    DWORD age = GetTickCount() - dlg->createdTick;
    if (age >= 700)
        return false;

    PincodeDebug("ignored early close reason=%s age=%lu", reason ? reason : "unknown", age);
    return true;
}

static void FinishDialog(PincodeDialog* dlg, int result, const char* reason = nullptr)
{
    SetCloseReason(dlg, reason ? reason : "FinishDialog");
    dlg->result = result;
    dlg->done = true;
    if (dlg->hwnd && IsWindow(dlg->hwnd))
        DestroyWindow(dlg->hwnd);
}

static void BringPincodeWindowToFront(HWND hwnd)
{
    if (!hwnd || !IsWindow(hwnd))
        return;

    ShowWindow(hwnd, SW_SHOW);
    SetWindowPos(hwnd, HWND_TOP, 0, 0, 0, 0,
        SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW);
    BringWindowToTop(hwnd);
    SetActiveWindow(hwnd);
    SetFocus(hwnd);
}

static const char* MainPrompt(const PincodeDialog* dlg)
{
    if (dlg->state == PINCODE_ASK)
        return "Please enter a password to login.";
    if (dlg->state == PINCODE_EXPIRED)
        return "Please enter your current password, then set a new one.";
    return "Please enter a new 4-digit password.";
}

static const char* SubPrompt(const PincodeDialog* dlg)
{
    if (dlg->step == STEP_VERIFY)
        return "Use the mouse to enter the 4-digit password below.";
    if (dlg->step == STEP_NEW)
        return "Enter the new 4-digit password below.";
    return "Enter the new password again to confirm.";
}

static void AdvanceDialog(PincodeDialog* dlg)
{
    if (dlg->waiting)
        return;

    dlg->result = RESULT_NONE;

    if (dlg->currentLen != 4)
    {
        SetStatus(dlg, "Enter exactly 4 digits.");
        return;
    }

    if (dlg->state == PINCODE_ASK)
    {
        memcpy(dlg->oldPin, dlg->current, 5);
        dlg->result = RESULT_CHECK;
        return;
    }

    if (dlg->state == PINCODE_NEW || dlg->state == PINCODE_NOTSET)
    {
        if (dlg->step == STEP_NEW)
        {
            memcpy(dlg->newPin, dlg->current, 5);
            dlg->step = STEP_CONFIRM;
            ResetEntry(dlg);
            SetStatus(dlg, "");
            return;
        }

        if (memcmp(dlg->newPin, dlg->current, 4) != 0)
        {
            dlg->step = STEP_NEW;
            ResetEntry(dlg);
            memset(dlg->newPin, 0, sizeof(dlg->newPin));
            SetStatus(dlg, "PINs did not match.");
            return;
        }

        dlg->result = RESULT_SET;
        return;
    }

    if (dlg->state == PINCODE_EXPIRED)
    {
        if (dlg->step == STEP_VERIFY)
        {
            memcpy(dlg->oldPin, dlg->current, 5);
            dlg->step = STEP_NEW;
            ResetEntry(dlg);
            SetStatus(dlg, "");
            return;
        }

        if (dlg->step == STEP_NEW)
        {
            memcpy(dlg->newPin, dlg->current, 5);
            dlg->step = STEP_CONFIRM;
            ResetEntry(dlg);
            SetStatus(dlg, "");
            return;
        }

        if (memcmp(dlg->newPin, dlg->current, 4) != 0)
        {
            dlg->step = STEP_NEW;
            ResetEntry(dlg);
            memset(dlg->newPin, 0, sizeof(dlg->newPin));
            SetStatus(dlg, "PINs did not match.");
            return;
        }

        dlg->result = RESULT_CHANGE;
        return;
    }

    SetStatus(dlg, "Unsupported PIN state.");
}

static void AddDigit(PincodeDialog* dlg, int digit)
{
    if (dlg->waiting)
        return;

    if (dlg->currentLen >= 4)
        return;
    dlg->current[dlg->currentLen++] = static_cast<char>('0' + digit);
    dlg->current[dlg->currentLen] = '\0';
    SetStatus(dlg, "");
}

static void BackspaceDigit(PincodeDialog* dlg)
{
    if (dlg->waiting)
        return;

    if (dlg->currentLen <= 0)
        return;
    dlg->current[--dlg->currentLen] = '\0';
    SetStatus(dlg, "");
}

static void RestartEntryFlow(PincodeDialog* dlg)
{
    if (dlg->waiting)
        return;

    dlg->step = (dlg->state == PINCODE_ASK || dlg->state == PINCODE_EXPIRED) ? STEP_VERIFY : STEP_NEW;
    ResetEntry(dlg);
    memset(dlg->oldPin, 0, sizeof(dlg->oldPin));
    memset(dlg->newPin, 0, sizeof(dlg->newPin));
    SetStatus(dlg, "Entry reset.");
}

static RECT DigitRectBySlot(int slot)
{
    if (slot < 9)
    {
        int row = slot / 3;
        int col = slot % 3;
        return RectFromXYWH(230 + col * 60, kTitleHeight + 67 + row * 60, 59, 59);
    }
    return RectFromXYWH(230, kTitleHeight + 247, 59, 59);
}

static RECT ResetRect()
{
    return RectFromXYWH(290, kTitleHeight + 247, 119, 60);
}

static RECT ConfirmRect()
{
    return RectFromXYWH(426, kTitleHeight + 187, 100, 20);
}

static RECT ChangeRect()
{
    return RectFromXYWH(426, kTitleHeight + 212, 100, 20);
}

static RECT CancelRect()
{
    return RectFromXYWH(426, kTitleHeight + 272, 100, 20);
}

static RECT CloseRect()
{
    return RectFromXYWH(kWindowWidth - 18, 3, 13, 12);
}

static int HitTest(PincodeDialog* dlg, int x, int y)
{
    RECT rc = CloseRect();
    if (PtInRectXY(&rc, x, y))
        return ID_CLOSE;

    rc = ResetRect();
    if (PtInRectXY(&rc, x, y))
        return ID_RESET;

    rc = ConfirmRect();
    if (PtInRectXY(&rc, x, y))
        return ID_CONFIRM;

    rc = ChangeRect();
    if (PtInRectXY(&rc, x, y))
        return ID_CHANGE;

    rc = CancelRect();
    if (PtInRectXY(&rc, x, y))
        return ID_CANCEL;

    for (int i = 0; i < 10; ++i)
    {
        rc = DigitRectBySlot(i);
        if (PtInRectXY(&rc, x, y))
            return ID_DIGIT_BASE + dlg->digitSlots[i];
    }

    return 0;
}

static void DrawBitmapAt(HDC hdc, HBITMAP bitmap, int x, int y, int w, int h)
{
    if (!bitmap)
        return;

    BITMAP info = {};
    GetObject(bitmap, sizeof(info), &info);

    HDC mem = CreateCompatibleDC(hdc);
    HGDIOBJ old = SelectObject(mem, bitmap);
    StretchBlt(hdc, x, y, w, h, mem, 0, 0, info.bmWidth, info.bmHeight, SRCCOPY);
    SelectObject(mem, old);
    DeleteDC(mem);
}

static void DrawTextInRect(HDC hdc, const char* text, RECT rc, HFONT font, COLORREF color, UINT flags)
{
    HGDIOBJ oldFont = font ? SelectObject(hdc, font) : nullptr;
    SetTextColor(hdc, color);
    SetBkMode(hdc, TRANSPARENT);
    DrawTextA(hdc, text ? text : "", -1, &rc, flags);
    if (oldFont)
        SelectObject(hdc, oldFont);
}

static void DrawFallbackButton(HDC hdc, RECT rc, const char* text, bool active, HFONT font)
{
    COLORREF top = active ? RGB(223, 235, 255) : RGB(248, 253, 245);
    HBRUSH brush = CreateSolidBrush(top);
    FillRect(hdc, &rc, brush);
    DeleteObject(brush);

    HPEN edge = CreatePen(PS_SOLID, 1, active ? RGB(88, 106, 170) : RGB(132, 160, 132));
    HGDIOBJ oldPen = SelectObject(hdc, edge);
    HGDIOBJ oldBrush = SelectObject(hdc, GetStockObject(HOLLOW_BRUSH));
    RoundRect(hdc, rc.left, rc.top, rc.right, rc.bottom, 8, 8);
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldPen);
    DeleteObject(edge);

    DrawTextInRect(hdc, text, rc, font, RGB(35, 35, 35), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
}

static int ButtonVisualState(const PincodeDialog* dlg, int id)
{
    if (dlg->downId == id)
        return 2;
    if (dlg->hotId == id)
        return 1;
    return 0;
}

static void DrawImageButton(HDC hdc, HBITMAP bitmaps[3], RECT rc, const char* text, int visualState, HFONT font)
{
    HBITMAP bitmap = bitmaps[visualState];
    if (!bitmap && visualState != 0)
        bitmap = bitmaps[0];

    if (bitmap)
        DrawBitmapAt(hdc, bitmap, rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top);
    else
        DrawFallbackButton(hdc, rc, text, visualState != 0, font);
}

static void DrawDigitButton(HDC hdc, PincodeDialog* dlg, RECT rc, int id, int digit, HFONT font)
{
    int visualState = ButtonVisualState(dlg, id);
    HBITMAP bitmap = dlg->digitBitmaps[digit][visualState];
    if (!bitmap && visualState != 0)
        bitmap = dlg->digitBitmaps[digit][0];

    if (bitmap)
    {
        DrawBitmapAt(hdc, bitmap, rc.left, rc.top, rc.right - rc.left, rc.bottom - rc.top);
        return;
    }

    bool active = visualState != 0;
    HBRUSH brush = CreateSolidBrush(active ? RGB(235, 241, 255) : RGB(245, 250, 250));
    FillRect(hdc, &rc, brush);
    DeleteObject(brush);

    HPEN pen = CreatePen(PS_SOLID, 1, active ? RGB(97, 117, 178) : RGB(133, 146, 154));
    HGDIOBJ oldPen = SelectObject(hdc, pen);
    HGDIOBJ oldBrush = SelectObject(hdc, GetStockObject(HOLLOW_BRUSH));
    Rectangle(hdc, rc.left, rc.top, rc.right, rc.bottom);
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldPen);
    DeleteObject(pen);

    char label[8];
    _snprintf_s(label, sizeof(label), _TRUNCATE, "%d", digit);
    DrawTextInRect(hdc, label, rc, font, RGB(82, 82, 82), DT_CENTER | DT_VCENTER | DT_SINGLELINE);
}

static void DrawPasswordField(HDC hdc, PincodeDialog* dlg, int field, const char* label, RECT labelRc, RECT boxRc)
{
    bool active = false;
    const char* value = "";
    char stars[5] = {};

    if (field == 0)
    {
        active = (dlg->step == STEP_VERIFY);
        if (active)
        {
            for (int i = 0; i < dlg->currentLen && i < 4; ++i)
                stars[i] = '*';
            value = stars;
        }
        else if (dlg->oldPin[0] != '\0')
            value = "****";
    }
    else if (field == 1)
    {
        active = (dlg->step == STEP_NEW);
        if (active)
        {
            for (int i = 0; i < dlg->currentLen && i < 4; ++i)
                stars[i] = '*';
            value = stars;
        }
        else if (dlg->newPin[0] != '\0')
            value = "****";
    }
    else
    {
        active = (dlg->step == STEP_CONFIRM);
        if (active)
        {
            for (int i = 0; i < dlg->currentLen && i < 4; ++i)
                stars[i] = '*';
            value = stars;
        }
    }

    if (field == 0 && (dlg->state == PINCODE_NEW || dlg->state == PINCODE_NOTSET))
        active = false;
    if ((field == 1 || field == 2) && dlg->state == PINCODE_ASK)
        active = false;

    DrawTextInRect(hdc, label, labelRc, dlg->smallFont, active ? RGB(20, 20, 20) : RGB(255, 255, 255),
        DT_LEFT | DT_VCENTER | DT_SINGLELINE);

    HBRUSH brush = CreateSolidBrush(active ? RGB(255, 255, 255) : RGB(240, 244, 255));
    FillRect(hdc, &boxRc, brush);
    DeleteObject(brush);

    HPEN pen = CreatePen(PS_SOLID, 1, active ? RGB(118, 130, 192) : RGB(202, 210, 232));
    HGDIOBJ oldPen = SelectObject(hdc, pen);
    HGDIOBJ oldBrush = SelectObject(hdc, GetStockObject(HOLLOW_BRUSH));
    Rectangle(hdc, boxRc.left, boxRc.top, boxRc.right, boxRc.bottom);
    SelectObject(hdc, oldBrush);
    SelectObject(hdc, oldPen);
    DeleteObject(pen);

    RECT textRc = boxRc;
    textRc.left += 5;
    DrawTextInRect(hdc, value, textRc, dlg->smallFont, RGB(80, 80, 130), DT_LEFT | DT_VCENTER | DT_SINGLELINE);
}

static void DrawPincodeWindow(PincodeDialog* dlg, HDC hdc)
{
    RECT client = RectFromXYWH(0, 0, kWindowWidth, kWindowHeight);
    HBRUSH frame = CreateSolidBrush(RGB(236, 243, 255));
    FillRect(hdc, &client, frame);
    DeleteObject(frame);

    RECT title = RectFromXYWH(0, 0, kWindowWidth, kTitleHeight);
    HBRUSH titleBrush = CreateSolidBrush(RGB(210, 226, 255));
    FillRect(hdc, &title, titleBrush);
    DeleteObject(titleBrush);

    HPEN titlePen = CreatePen(PS_SOLID, 1, RGB(82, 116, 188));
    HGDIOBJ oldPen = SelectObject(hdc, titlePen);
    MoveToEx(hdc, 0, 0, nullptr);
    LineTo(hdc, kWindowWidth, 0);
    MoveToEx(hdc, 0, kTitleHeight - 1, nullptr);
    LineTo(hdc, kWindowWidth, kTitleHeight - 1);
    SelectObject(hdc, oldPen);
    DeleteObject(titlePen);

    RECT titleText = RectFromXYWH(18, 0, 200, kTitleHeight);
    DrawTextInRect(hdc, "Security Code", titleText, dlg->titleFont, RGB(20, 30, 55), DT_LEFT | DT_VCENTER | DT_SINGLELINE);

    RECT close = CloseRect();
    DrawTextInRect(hdc, "x", close, dlg->smallFont,
        dlg->hotId == ID_CLOSE ? RGB(120, 30, 30) : RGB(90, 100, 120),
        DT_CENTER | DT_VCENTER | DT_SINGLELINE);

    if (dlg->bgBitmap)
        DrawBitmapAt(hdc, dlg->bgBitmap, 0, kTitleHeight, kBgWidth, kBgHeight);
    else
    {
        RECT bg = RectFromXYWH(0, kTitleHeight, kBgWidth, kBgHeight);
        HBRUSH fallback = CreateSolidBrush(RGB(221, 241, 250));
        FillRect(hdc, &bg, fallback);
        DeleteObject(fallback);
    }

    RECT mainText = RectFromXYWH(212, kTitleHeight + 25, 310, 18);
    RECT subText = RectFromXYWH(212, kTitleHeight + 47, 310, 18);
    DrawTextInRect(hdc, MainPrompt(dlg), mainText, dlg->smallFont, RGB(20, 20, 20), DT_LEFT | DT_SINGLELINE);
    DrawTextInRect(hdc, SubPrompt(dlg), subText, dlg->smallFont, RGB(20, 20, 20), DT_LEFT | DT_SINGLELINE);

    for (int i = 0; i < 10; ++i)
    {
        RECT rc = DigitRectBySlot(i);
        int id = ID_DIGIT_BASE + dlg->digitSlots[i];
        DrawDigitButton(hdc, dlg, rc, id, dlg->digitSlots[i], dlg->digitFont);
    }

    RECT reset = ResetRect();
    DrawImageButton(hdc, dlg->resetBitmaps, reset, "Reset", ButtonVisualState(dlg, ID_RESET), dlg->resetFont);

    DrawPasswordField(hdc, dlg, 0, "Password",
        RectFromXYWH(422, kTitleHeight + 70, 110, 14),
        RectFromXYWH(426, kTitleHeight + 84, 100, 15));
    DrawPasswordField(hdc, dlg, 1, "New Password",
        RectFromXYWH(422, kTitleHeight + 113, 110, 14),
        RectFromXYWH(426, kTitleHeight + 127, 100, 15));
    DrawPasswordField(hdc, dlg, 2, "Confirm Password",
        RectFromXYWH(422, kTitleHeight + 156, 115, 14),
        RectFromXYWH(426, kTitleHeight + 170, 100, 15));

    DrawImageButton(hdc, dlg->confirmBitmaps, ConfirmRect(), "Confirm",
        ButtonVisualState(dlg, ID_CONFIRM), dlg->smallFont);
    DrawImageButton(hdc, dlg->changeBitmaps, ChangeRect(), "change",
        ButtonVisualState(dlg, ID_CHANGE), dlg->smallFont);
    DrawImageButton(hdc, dlg->cancelBitmaps, CancelRect(), "Cancel",
        ButtonVisualState(dlg, ID_CANCEL), dlg->smallFont);

    if (dlg->statusText[0] != '\0')
    {
        RECT status = RectFromXYWH(212, kTitleHeight + 300, 310, 16);
        DrawTextInRect(hdc, dlg->statusText, status, dlg->smallFont, RGB(148, 52, 52),
            DT_CENTER | DT_SINGLELINE);
    }

    HPEN border = CreatePen(PS_SOLID, 1, RGB(132, 143, 170));
    HGDIOBJ old = SelectObject(hdc, border);
    SelectObject(hdc, GetStockObject(HOLLOW_BRUSH));
    Rectangle(hdc, 0, 0, kWindowWidth, kWindowHeight);
    SelectObject(hdc, old);
    DeleteObject(border);
}

static void DoAction(PincodeDialog* dlg, int id)
{
    if (id >= ID_DIGIT_BASE && id <= ID_DIGIT_BASE + 9)
        AddDigit(dlg, id - ID_DIGIT_BASE);
    else if (id == ID_RESET)
    {
        if (dlg->waiting)
            return;
        ResetEntry(dlg);
        SetStatus(dlg, "");
    }
    else if (id == ID_CONFIRM)
    {
        AdvanceDialog(dlg);
        if (dlg->result != RESULT_NONE)
        {
            dlg->pendingResult = dlg->result;
            dlg->result = RESULT_NONE;
            SendResult(dlg);
            dlg->waiting = true;
            ResetEntry(dlg);
            SetStatus(dlg,
                dlg->pendingResult == RESULT_CHECK ? "Checking PIN..." :
                dlg->pendingResult == RESULT_SET ? "Saving PIN..." :
                "Changing PIN...");
        }
    }
    else if (id == ID_CHANGE)
        RestartEntryFlow(dlg);
    else if (id == ID_CANCEL || id == ID_CLOSE)
    {
        if (IgnoreEarlyClose(dlg, id == ID_CANCEL ? "button cancel" : "button close"))
            return;
        FinishDialog(dlg, RESULT_NONE, id == ID_CANCEL ? "button cancel" : "button close");
    }
}

static void HandleServerState(PincodeDialog* dlg, uint32_t state, uint32_t seed)
{
    if (!dlg)
        return;

    PincodeDebug("server state received state=%u aid=%u seed=%u", state, dlg->aid, seed);

    if (state == PINCODE_PASSED)
    {
        FinishDialog(dlg, RESULT_NONE, "server passed");
        return;
    }

    if (state == PINCODE_WRONG || state == PINCODE_ILLEGAL)
    {
        if (seed != 0)
        {
            dlg->seed = seed;
            BuildDigitSlots(dlg);
        }

        dlg->waiting = false;
        dlg->pendingResult = RESULT_NONE;
        dlg->result = RESULT_NONE;
        dlg->step = (dlg->state == PINCODE_ASK || dlg->state == PINCODE_EXPIRED) ? STEP_VERIFY : STEP_NEW;
        ResetEntry(dlg);
        memset(dlg->oldPin, 0, sizeof(dlg->oldPin));
        memset(dlg->newPin, 0, sizeof(dlg->newPin));
        SetStatus(dlg, state == PINCODE_WRONG ? "Incorrect PIN." : "PIN rejected. Please try again.");
        BringPincodeWindowToFront(dlg->hwnd);
        return;
    }
}

static void ReopenDialog(PincodeDialog* dlg, uint32_t state, uint32_t seed)
{
    if (!dlg)
        return;

    PincodeDebug("reopen active dialog state=%u->%u aid=%u seed=%u", dlg->state, state, dlg->aid, seed);
    dlg->state = state;
    dlg->seed = seed;
    dlg->waiting = false;
    dlg->pendingResult = RESULT_NONE;
    dlg->result = RESULT_NONE;
    dlg->step = (state == PINCODE_ASK || state == PINCODE_EXPIRED) ? STEP_VERIFY : STEP_NEW;
    ResetEntry(dlg);
    memset(dlg->oldPin, 0, sizeof(dlg->oldPin));
    memset(dlg->newPin, 0, sizeof(dlg->newPin));
    BuildDigitSlots(dlg);
    SetStatus(dlg, "");
    BringPincodeWindowToFront(dlg->hwnd);
}

static LRESULT CALLBACK PincodeWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
    PincodeDialog* dlg = reinterpret_cast<PincodeDialog*>(GetWindowLongPtrA(hwnd, GWLP_USERDATA));

    if (msg == WM_NCCREATE)
    {
        CREATESTRUCTA* cs = reinterpret_cast<CREATESTRUCTA*>(lParam);
        dlg = reinterpret_cast<PincodeDialog*>(cs->lpCreateParams);
        SetWindowLongPtrA(hwnd, GWLP_USERDATA, reinterpret_cast<LONG_PTR>(dlg));
        dlg->hwnd = hwnd;
        return TRUE;
    }

    switch (msg)
    {
    case WM_PINCODE_SERVER_STATE:
        HandleServerState(dlg, static_cast<uint32_t>(wParam), static_cast<uint32_t>(lParam));
        return 0;

    case WM_PINCODE_REOPEN_STATE:
        ReopenDialog(dlg, static_cast<uint32_t>(wParam), static_cast<uint32_t>(lParam));
        return 0;

    case WM_CREATE:
    {
        dlg->uiFont = CreateFontA(17, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            DEFAULT_PITCH | FF_SWISS, "Arial");
        dlg->smallFont = CreateFontA(13, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            DEFAULT_PITCH | FF_SWISS, "Arial");
        dlg->digitFont = CreateFontA(34, 0, 0, 0, FW_BOLD, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            DEFAULT_PITCH | FF_SWISS, "Arial");
        dlg->resetFont = CreateFontA(28, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            DEFAULT_PITCH | FF_SWISS, "Arial");
        dlg->titleFont = CreateFontA(12, 0, 0, 0, FW_NORMAL, FALSE, FALSE, FALSE,
            DEFAULT_CHARSET, OUT_DEFAULT_PRECIS, CLIP_DEFAULT_PRECIS, CLEARTYPE_QUALITY,
            DEFAULT_PITCH | FF_SWISS, "Arial");

        EnsureSharedBitmaps();
        dlg->bgBitmap = g_bgBitmap;
        dlg->confirmBitmap = g_confirmBitmap;
        dlg->changeBitmap = g_changeBitmap;
        dlg->cancelBitmap = g_cancelBitmap;
        dlg->resetBitmap = g_resetBitmap;
        memcpy(dlg->confirmBitmaps, g_confirmBitmaps, sizeof(dlg->confirmBitmaps));
        memcpy(dlg->changeBitmaps, g_changeBitmaps, sizeof(dlg->changeBitmaps));
        memcpy(dlg->cancelBitmaps, g_cancelBitmaps, sizeof(dlg->cancelBitmaps));
        memcpy(dlg->resetBitmaps, g_resetBitmaps, sizeof(dlg->resetBitmaps));
        memcpy(dlg->digitBitmaps, g_digitBitmaps, sizeof(dlg->digitBitmaps));

        return 0;
    }

    case WM_PAINT:
    {
        PAINTSTRUCT ps;
        HDC hdc = BeginPaint(hwnd, &ps);
        DrawPincodeWindow(dlg, hdc);
        EndPaint(hwnd, &ps);
        return 0;
    }

    case WM_MOUSEMOVE:
    {
        TRACKMOUSEEVENT tme = {sizeof(tme), TME_LEAVE, hwnd, 0};
        TrackMouseEvent(&tme);

        int id = HitTest(dlg, GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam));
        if (dlg->hotId != id)
        {
            dlg->hotId = id;
            RedrawPincodeWindow(hwnd);
        }
        return 0;
    }

    case WM_MOUSELEAVE:
        dlg->hotId = 0;
        RedrawPincodeWindow(hwnd);
        return 0;

    case WM_LBUTTONDOWN:
        SetCapture(hwnd);
        dlg->downId = HitTest(dlg, GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam));
        RedrawPincodeWindow(hwnd);
        return 0;

    case WM_LBUTTONUP:
    {
        int id = HitTest(dlg, GET_X_LPARAM(lParam), GET_Y_LPARAM(lParam));
        int down = dlg->downId;
        dlg->downId = 0;
        ReleaseCapture();
        RedrawPincodeWindow(hwnd);
        if (id != 0 && id == down)
            DoAction(dlg, id);
        return 0;
    }

    case WM_CHAR:
        if (wParam >= '0' && wParam <= '9')
            AddDigit(dlg, static_cast<int>(wParam - '0'));
        else if (wParam == VK_BACK)
            BackspaceDigit(dlg);
        else if (wParam == VK_RETURN)
            DoAction(dlg, ID_CONFIRM);
        else if (wParam == VK_ESCAPE)
        {
            if (IgnoreEarlyClose(dlg, "escape"))
                return 0;
            FinishDialog(dlg, RESULT_NONE, "escape");
        }
        return 0;

    case WM_CLOSE:
        if (IgnoreEarlyClose(dlg, "WM_CLOSE"))
            return 0;
        FinishDialog(dlg, RESULT_NONE, "WM_CLOSE");
        return 0;

    case WM_DESTROY:
        SetCloseReason(dlg, "WM_DESTROY");
        return 0;

    case WM_NCDESTROY:
        if (dlg)
        {
            SetCloseReason(dlg, "WM_NCDESTROY");
            dlg->hwnd = nullptr;
            dlg->done = true;
        }
        if (g_pincodeHwnd == hwnd)
            g_pincodeHwnd = nullptr;
        SetWindowLongPtrA(hwnd, GWLP_USERDATA, 0);
        return 0;
    }

    return DefWindowProcA(hwnd, msg, wParam, lParam);
}

static bool EnsurePincodeWindowClass()
{
    HINSTANCE instance = GetModuleHandleA(nullptr);
    WNDCLASSEXA existing = {};
    existing.cbSize = sizeof(existing);
    if (GetClassInfoExA(instance, kPincodeClassName, &existing))
        return true;

    WNDCLASSEXA wc = {};
    wc.cbSize = sizeof(wc);
    wc.lpfnWndProc = PincodeWndProc;
    wc.hInstance = instance;
    wc.hCursor = LoadCursor(nullptr, IDC_ARROW);
    wc.hbrBackground = reinterpret_cast<HBRUSH>(COLOR_BTNFACE + 1);
    wc.lpszClassName = kPincodeClassName;

    ATOM atom = RegisterClassExA(&wc);
    if (!atom && GetLastError() != ERROR_CLASS_ALREADY_EXISTS)
        return false;
    return true;
}

static bool CreatePincodeWindow(PincodeDialog* dlg)
{
    PincodeDebug("create window begin");
    if (!EnsurePincodeWindowClass())
    {
        PincodeDebug("abort: window class failed err=%lu", GetLastError());
        return false;
    }
    PincodeDebug("window class ready");

    HWND parent = FindGameWindow();
    if (parent)
        PincodeDebug("game parent hwnd=%p", parent);
    else
        PincodeDebug("warning: game parent not found; using popup fallback");

    DWORD style = parent ? (WS_CHILD | WS_CLIPSIBLINGS | WS_VISIBLE) : (WS_POPUP | WS_VISIBLE);
    DWORD exStyle = parent ? 0 : WS_EX_TOOLWINDOW;
    PincodeDebug("CreateWindowEx style=0x%08lx ex=0x%08lx parent=%p", style, exStyle, parent);

    dlg->hwnd = CreateWindowExA(
        exStyle,
        kPincodeClassName,
        "Security Code",
        style,
        0,
        0,
        kWindowWidth,
        kWindowHeight,
        parent,
        nullptr,
        GetModuleHandleA(nullptr),
        dlg);

    if (!dlg->hwnd)
        return false;

    g_pincodeHwnd = dlg->hwnd;
    CenterWindow(dlg->hwnd, parent, kWindowWidth, kWindowHeight);
    ShowWindow(dlg->hwnd, SW_SHOW);
    BringPincodeWindowToFront(dlg->hwnd);
    return true;
}

static void CleanupDialog(PincodeDialog* dlg)
{
    if (dlg->hwnd && IsWindow(dlg->hwnd))
        DestroyWindow(dlg->hwnd);

    if (dlg->uiFont)
        DeleteObject(dlg->uiFont);
    if (dlg->smallFont)
        DeleteObject(dlg->smallFont);
    if (dlg->digitFont)
        DeleteObject(dlg->digitFont);
    if (dlg->resetFont)
        DeleteObject(dlg->resetFont);
    if (dlg->titleFont)
        DeleteObject(dlg->titleFont);

    dlg->uiFont = nullptr;
    dlg->smallFont = nullptr;
    dlg->digitFont = nullptr;
    dlg->resetFont = nullptr;
    dlg->titleFont = nullptr;
    dlg->bgBitmap = nullptr;
    dlg->confirmBitmap = nullptr;
    dlg->changeBitmap = nullptr;
    dlg->cancelBitmap = nullptr;
    dlg->resetBitmap = nullptr;
    memset(dlg->confirmBitmaps, 0, sizeof(dlg->confirmBitmaps));
    memset(dlg->changeBitmaps, 0, sizeof(dlg->changeBitmaps));
    memset(dlg->cancelBitmaps, 0, sizeof(dlg->cancelBitmaps));
    memset(dlg->resetBitmaps, 0, sizeof(dlg->resetBitmaps));
    memset(dlg->digitBitmaps, 0, sizeof(dlg->digitBitmaps));
}

static void SendResult(PincodeDialog* dlg)
{
    char encA[5] = {};
    char encB[5] = {};
    int sendResult = dlg->pendingResult != RESULT_NONE ? dlg->pendingResult : dlg->result;

    if (sendResult == RESULT_CHECK)
    {
        if (!dlg->sendCheck)
        {
            PincodeDebug("abort: check sender missing");
            return;
        }
        EncryptPin(dlg->seed, dlg->oldPin, encA);
        PincodeDebug("sending check pkt=0x08B8 aid=%u", dlg->aid);
        dlg->sendCheck(dlg->aid, encA);
        PincodeDebug("check sender returned");
        return;
    }

    if (sendResult == RESULT_SET)
    {
        if (!dlg->sendSet)
        {
            PincodeDebug("abort: set sender missing");
            return;
        }
        EncryptPin(dlg->seed, dlg->newPin, encA);
        PincodeDebug("sending setnew pkt=0x08BA aid=%u", dlg->aid);
        dlg->sendSet(dlg->aid, encA);
        PincodeDebug("setnew sender returned");
        return;
    }

    if (sendResult == RESULT_CHANGE)
    {
        if (!dlg->sendChange)
        {
            PincodeDebug("abort: change sender missing");
            return;
        }
        EncryptPin(dlg->seed, dlg->oldPin, encA);
        EncryptPin(dlg->seed, dlg->newPin, encB);
        PincodeDebug("sending change pkt=0x08BE aid=%u", dlg->aid);
        dlg->sendChange(dlg->aid, encA, encB);
        PincodeDebug("change sender returned");
        return;
    }
}

static DWORD WINAPI PincodeThreadMain(LPVOID param)
{
    PincodeDialog* dlg = reinterpret_cast<PincodeDialog*>(param);
    if (!dlg)
    {
        InterlockedExchange(&g_pincodeUiOpen, 0);
        return 0;
    }

    PincodeDebug("ui thread start state=%u aid=%u seed=%u", dlg->state, dlg->aid, dlg->seed);
    dlg->createdTick = GetTickCount();
    BuildDigitSlots(dlg);

    if (!CreatePincodeWindow(dlg))
    {
        PincodeDebug("abort: CreateWindow failed err=%lu", GetLastError());
        CleanupDialog(dlg);
        delete dlg;
        InterlockedExchange(&g_pincodeUiOpen, 0);
        return 0;
    }

    MSG msg;
    BOOL messageResult = 0;
    while (!dlg->done && (messageResult = GetMessageA(&msg, nullptr, 0, 0)) > 0)
    {
        TranslateMessage(&msg);
        DispatchMessageA(&msg);
    }

    if (messageResult == 0)
        SetCloseReason(dlg, "WM_QUIT");
    else if (messageResult < 0)
    {
        char reason[64];
        _snprintf_s(reason, sizeof(reason), _TRUNCATE, "GetMessage failed err=%lu", GetLastError());
        SetCloseReason(dlg, reason);
    }

    int result = dlg->result;
    uint32_t state = dlg->state;
    uint32_t aid = dlg->aid;
    char closeReason[64];
    _snprintf_s(closeReason, sizeof(closeReason), _TRUNCATE, "%s",
        dlg->closeReason[0] ? dlg->closeReason : "unknown");
    CleanupDialog(dlg);

    PincodeDebug("dialog closed state=%u aid=%u result=%d reason=%s", state, aid, result, closeReason);

    delete dlg;
    InterlockedExchange(&g_pincodeUiOpen, 0);
    PincodeDebug("ui thread finish state=%u aid=%u result=%d", state, aid, result);
    return 0;
}

extern "C" __declspec(dllexport) void PincodeUIInit(void)
{
}

extern "C" __declspec(dllexport) void PincodeUIShow(
    uint32_t seed,
    uint32_t aid,
    uint32_t state,
    PincodeSendCheckFn sendCheck,
    PincodeSendSetFn sendSet,
    PincodeSendChangeFn sendChange)
{
    PincodeDebug("show request state=%u aid=%u seed=%u", state, aid, seed);

    if (state == PINCODE_PASSED || state == PINCODE_WRONG || state == PINCODE_ILLEGAL)
    {
        HWND hwnd = g_pincodeHwnd;
        if (hwnd && IsWindow(hwnd))
        {
            PostMessageA(hwnd, WM_PINCODE_SERVER_STATE, static_cast<WPARAM>(state), static_cast<LPARAM>(seed));
            if (state != PINCODE_PASSED)
                BringPincodeWindowToFront(hwnd);
            PincodeDebug("server state dispatched state=%u aid=%u seed=%u", state, aid, seed);
        }
        else
            PincodeDebug("ignore: server state=%u with no active UI", state);
        return;
    }

    if (state != PINCODE_ASK && state != PINCODE_NOTSET &&
        state != PINCODE_EXPIRED && state != PINCODE_NEW)
    {
        PincodeDebug("ignore: unsupported state=%u", state);
        return;
    }

    if (InterlockedCompareExchange(&g_pincodeUiOpen, 1, 0) != 0)
    {
        HWND hwnd = g_pincodeHwnd;
        if (hwnd && IsWindow(hwnd))
        {
            PostMessageA(hwnd, WM_PINCODE_REOPEN_STATE, static_cast<WPARAM>(state), static_cast<LPARAM>(seed));
            BringPincodeWindowToFront(hwnd);
            PincodeDebug("reopen dispatched to active UI state=%u aid=%u seed=%u", state, aid, seed);
            return;
        }

        PincodeDebug("recover: stale UI guard reset");
        InterlockedExchange(&g_pincodeUiOpen, 0);
        if (InterlockedCompareExchange(&g_pincodeUiOpen, 1, 0) != 0)
        {
            PincodeDebug("ignore: UI already open after stale guard recovery");
            return;
        }
    }

    PincodeDialog* dlg = new PincodeDialog();
    memset(dlg, 0, sizeof(*dlg));
    dlg->seed = seed;
    dlg->aid = aid;
    dlg->state = state;
    dlg->sendCheck = sendCheck;
    dlg->sendSet = sendSet;
    dlg->sendChange = sendChange;
    dlg->step = (state == PINCODE_ASK || state == PINCODE_EXPIRED) ? STEP_VERIFY : STEP_NEW;

    HANDLE thread = CreateThread(nullptr, 0, PincodeThreadMain, dlg, 0, nullptr);
    if (!thread)
    {
        PincodeDebug("abort: CreateThread failed err=%lu", GetLastError());
        delete dlg;
        InterlockedExchange(&g_pincodeUiOpen, 0);
        return;
    }

    CloseHandle(thread);
    PincodeDebug("show dispatched state=%u aid=%u seed=%u", state, aid, seed);
}
