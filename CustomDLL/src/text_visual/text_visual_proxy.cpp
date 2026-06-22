#include <windows.h>

void ItemColorExtNameInit(HMODULE module);
void ItemColorExtNameCleanup(bool isProcessTermination);

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID lpReserved)
{
    switch (reason)
    {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(module);
        ItemColorExtNameInit(module);
        break;
    case DLL_PROCESS_DETACH:
        ItemColorExtNameCleanup(lpReserved != nullptr);
        break;
    }
    return TRUE;
}

extern "C" __declspec(dllexport) void ExtNameVisualInit() {}
extern "C" __declspec(dllexport) void ColoredItemNameVisualInit() {}
