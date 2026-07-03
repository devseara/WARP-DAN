#include <windows.h>

#include "text_visual/text_visual_bridge.h"

BOOL APIENTRY DllMain(HMODULE module, DWORD reason, LPVOID lpReserved)
{
    switch (reason)
    {
    case DLL_PROCESS_ATTACH:
        DisableThreadLibraryCalls(module);
        TextVisualInit(module);
        break;
    case DLL_PROCESS_DETACH:
        TextVisualCleanup(lpReserved != nullptr);
        break;
    }
    return TRUE;
}

extern "C" __declspec(dllexport) void ExtNameVisualInit() {}
extern "C" __declspec(dllexport) void ColoredItemNameVisualInit() {}
extern "C" __declspec(dllexport) void PlayerNameColorVisualInit() {}
