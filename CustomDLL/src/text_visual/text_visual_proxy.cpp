#include <windows.h>

void ItemColorExtNameInit(HMODULE module);
void ItemColorExtNameCleanup();

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID)
{
    switch (reason)
    {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(module);
        ItemColorExtNameInit(module);
        break;
    case DLL_PROCESS_DETACH:
        ItemColorExtNameCleanup();
        break;
    }
    return TRUE;
}

extern "C" __declspec(dllexport) void ExtNameVisualInit() {}
extern "C" __declspec(dllexport) void ColoredItemNameVisualInit() {}
