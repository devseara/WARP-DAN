@echo off
setlocal EnableDelayedExpansion
echo ============================================================
echo  BOH Dedicated Feature DLL Build
echo ============================================================
echo.
echo  Text wrappers are intentionally shared by item colors,
echo  extended names, and player name colors in boh_text.dll.
echo  Other features are isolated.
echo.

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if exist "%VSWHERE%" (
    for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
        set "VSINSTALLPATH=%%i"
    )
)

if defined VSINSTALLPATH (
    call "%VSINSTALLPATH%\VC\Auxiliary\Build\vcvars32.bat" >nul 2>&1
) else (
    if exist "%VS140COMNTOOLS%" call "%VS140COMNTOOLS%\vsvars32.bat" >nul 2>&1
    if exist "%VS120COMNTOOLS%" call "%VS120COMNTOOLS%\vsvars32.bat" >nul 2>&1
)

echo [clean] Removing old dedicated outputs...
del /q split_*.obj boh_text.dll boh_text.exp boh_text.lib ^
    boh_npc_names.dll boh_npc_names.exp boh_npc_names.lib ^
    boh_rune.dll boh_rune.exp boh_rune.lib ^
    boh_fps.dll boh_fps.exp boh_fps.lib ^
    boh_inventory_tabs.dll boh_inventory_tabs.exp boh_inventory_tabs.lib ^
    boh_weapon_sprite.dll boh_weapon_sprite.exp boh_weapon_sprite.lib ^
    boh_pincode_ui.dll boh_pincode_ui.exp boh_pincode_ui.lib >nul 2>&1

set "BOH_ITEM_COLORS=0"
set "BOH_EXTENDED_NAMES=0"
set "BOH_PLAYER_NAME_COLORS=0"
set "BOH_RUNE_VISUAL=0"
set "BOH_FPS_OVERLAY=0"
set "BOH_PING_OVERLAY=0"
set "BOH_NPC_NAME_OVERLAY=0"
set "BOH_INVENTORY_TABS=0"
set "BOH_PINCODE_UI=0"
set "BOH_WEAPON_SPRITE=0"

for /f "tokens=1,2,3" %%a in ('findstr /R /C:"^#define BOH_" customer_features.h') do (
    if "%%b"=="BOH_ITEM_COLORS" set "BOH_ITEM_COLORS=%%c"
    if "%%b"=="BOH_EXTENDED_NAMES" set "BOH_EXTENDED_NAMES=%%c"
    if "%%b"=="BOH_PLAYER_NAME_COLORS" set "BOH_PLAYER_NAME_COLORS=%%c"
    if "%%b"=="BOH_RUNE_VISUAL" set "BOH_RUNE_VISUAL=%%c"
    if "%%b"=="BOH_FPS_OVERLAY" set "BOH_FPS_OVERLAY=%%c"
    if "%%b"=="BOH_PING_OVERLAY" set "BOH_PING_OVERLAY=%%c"
    if "%%b"=="BOH_NPC_NAME_OVERLAY" set "BOH_NPC_NAME_OVERLAY=%%c"
    if "%%b"=="BOH_INVENTORY_TABS" set "BOH_INVENTORY_TABS=%%c"
    if "%%b"=="BOH_PINCODE_UI" set "BOH_PINCODE_UI=%%c"
    if "%%b"=="BOH_WEAPON_SPRITE" set "BOH_WEAPON_SPRITE=%%c"
)

set "BOH_TEXT_VISUAL=0"
if "%BOH_ITEM_COLORS%"=="1" set "BOH_TEXT_VISUAL=1"
if "%BOH_EXTENDED_NAMES%"=="1" set "BOH_TEXT_VISUAL=1"
if "%BOH_PLAYER_NAME_COLORS%"=="1" set "BOH_TEXT_VISUAL=1"

set "BOH_FPS_PING=0"
if "%BOH_FPS_OVERLAY%"=="1" set "BOH_FPS_PING=1"
if "%BOH_PING_OVERLAY%"=="1" set "BOH_FPS_PING=1"

if "%BOH_TEXT_VISUAL%"=="1" (
    if "%BOH_ITEM_COLORS%"=="1" (
        set "TEXT_BRIDGE_SRC=item_color\colored_itemname.cpp"
        set "TEXT_BRIDGE_OBJ=split_item_color.obj"
        set "TEXT_BRIDGE_LABEL=Shared static text wrappers + item/player-name colors"
    ) else (
        set "TEXT_BRIDGE_SRC=text_visual\player_name_text_bridge.cpp"
        set "TEXT_BRIDGE_OBJ=split_player_name_text_bridge.obj"
        set "TEXT_BRIDGE_LABEL=Standalone EXTN/player-name text bridge"
    )

    echo [text] Extended-name state...
    cl.exe /nologo /c /O2 /Gy /MT /EHa /I"./" ^
        extended_name\extended_name.cpp /Fo:split_extended_name.obj
    if errorlevel 1 (echo FAILED & exit /b 1)

    echo [text] Player-name color policy...
    cl.exe /nologo /c /O2 /Gy /MT /EHa /I"./" ^
        player_name_color\player_name_color.cpp /Fo:split_player_name_color.obj
    if errorlevel 1 (echo FAILED & exit /b 1)

    echo [text] !TEXT_BRIDGE_LABEL!...
    cl.exe /nologo /c /O2 /Gy /MT /EHa /I"./" ^
        !TEXT_BRIDGE_SRC! /Fo:!TEXT_BRIDGE_OBJ!
    if errorlevel 1 (echo FAILED & exit /b 1)

    echo [text] Text visual entry point...
    cl.exe /nologo /c /O2 /Gy /MT /EHsc /I"./" ^
        text_visual\text_visual_proxy.cpp /Fo:split_text_proxy.obj
    if errorlevel 1 (echo FAILED & exit /b 1)

    echo [text] Link boh_text.dll...
    link.exe /nologo /DLL /OPT:REF /OUT:boh_text.dll ^
        split_text_proxy.obj !TEXT_BRIDGE_OBJ! split_extended_name.obj split_player_name_color.obj ^
        kernel32.lib user32.lib gdi32.lib gdiplus.lib
    if errorlevel 1 (echo FAILED & exit /b 1)
) else (
    echo [skip] text visual DLL disabled
)

if "%BOH_NPC_NAME_OVERLAY%"=="1" (
    echo [feature] Build boh_npc_names.dll...
    cl.exe /nologo /LD /O2 /MT /EHa /I"./" ^
        /DNpcNameOverlayDllMain=DllMain ^
        npc_name_overlay\npc_name_overlay.cpp ^
        /Fe:boh_npc_names.dll /Fo:split_npc_name_overlay.obj ^
        /link kernel32.lib user32.lib
    if errorlevel 1 (echo FAILED & exit /b 1)
) else (
    echo [skip] NPC name overlay disabled
)

if "%BOH_RUNE_VISUAL%"=="1" (
    echo [feature] Build boh_rune.dll...
    cl.exe /nologo /c /O2 /GS- /GR- /I"./" ^
        rune_visual\boh_rune_visual.cpp /Fo:split_rune_visual.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    link.exe /nologo /DLL /ENTRY:DllMain /NODEFAULTLIB /OUT:boh_rune.dll ^
        split_rune_visual.obj kernel32.lib user32.lib
    if errorlevel 1 (echo FAILED & exit /b 1)
) else (
    echo [skip] rune visual disabled
)

if "%BOH_FPS_PING%"=="1" (
    echo [feature] Build boh_fps.dll...
    cl.exe /nologo /c /O2 /MT /EHsc /I"./" ^
        fps_ping\fps_ping_overlay.cpp /Fo:split_fps_overlay.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    cl.exe /nologo /c /O2 /MT /I"./" ^
        fps_ping\ping.cpp /Fo:split_ping.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    link.exe /nologo /DLL /OUT:boh_fps.dll ^
        split_fps_overlay.obj split_ping.obj ^
        kernel32.lib user32.lib gdi32.lib d3d9.lib iphlpapi.lib ws2_32.lib
    if errorlevel 1 (echo FAILED & exit /b 1)
) else (
    echo [skip] FPS/Ping overlay disabled
)

if "%BOH_INVENTORY_TABS%"=="1" (
    echo [feature] Build boh_inventory_tabs.dll...
    cl.exe /nologo /LD /O2 /MT /EHa /I"./" ^
        inventory_tabs\inventory_tabs.cpp ^
        /Fe:boh_inventory_tabs.dll /Fo:split_inventory_tabs.obj ^
        /link kernel32.lib user32.lib
    if errorlevel 1 (echo FAILED & exit /b 1)
) else (
    echo [skip] inventory tabs disabled
)

if "%BOH_WEAPON_SPRITE%"=="1" (
    echo [feature] Build boh_weapon_sprite.dll...
    cl.exe /nologo /c /O2 /MT /EHa /I"./" ^
        weapon_sprite\weapon_sprite.cpp /Fo:split_weapon_sprite.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    cl.exe /nologo /c /O2 /MT /EHa /I"./" ^
        weapon_sprite\weapon_overlay.cpp /Fo:split_weapon_overlay.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    link.exe /nologo /DLL /OUT:boh_weapon_sprite.dll ^
        split_weapon_sprite.obj split_weapon_overlay.obj ^
        kernel32.lib user32.lib gdi32.lib
    if errorlevel 1 (echo FAILED & exit /b 1)
) else (
    echo [skip] weapon sprite disabled
)

if "%BOH_PINCODE_UI%"=="1" (
    echo [feature] Build boh_pincode_ui.dll...
    cl.exe /nologo /LD /O2 /MT /EHsc /I"./" ^
        pincode_ui\pincode_ui.cpp ^
        /Fe:boh_pincode_ui.dll /Fo:split_pincode_ui.obj ^
        /link kernel32.lib user32.lib gdi32.lib
    if errorlevel 1 (echo FAILED & exit /b 1)
) else (
    echo [skip] pincode UI disabled
)

echo.
echo ============================================================
echo  Dedicated DLL build successful for enabled customer_features.h entries.
echo.
echo  These files may be renamed. Enter the matching filename in
echo  the corresponding WARP patch prompt.
echo ============================================================
endlocal
