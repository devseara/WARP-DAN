@echo off
setlocal EnableDelayedExpansion
echo ============================================================
echo  BOH Combined DLL : Per-Customer Build
echo ============================================================
echo.
echo  Features are compiled into the DLL via customer_features.h
echo  Edit that file, then run this script. No runtime config needed.
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

echo [clean] Removing old combined outputs...
del /q *.obj boh.dll boh.exp boh.lib >nul 2>&1

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

set "LINK_OBJECTS=main_proxy.obj"

echo [core] main_proxy - DllMain + DDRAW forwarding...
cl.exe /nologo /c /O2 /MT /EHsc /I"./" ^
    main_proxy\main_proxy.cpp
if errorlevel 1 (echo FAILED & exit /b 1)

if "%BOH_TEXT_VISUAL%"=="1" (
    if "%BOH_ITEM_COLORS%"=="1" (
        set "TEXT_BRIDGE_SRC=item_color\colored_itemname.cpp"
        set "TEXT_BRIDGE_OBJ=colored_itemname.obj"
        set "TEXT_BRIDGE_LABEL=item_color - full static text bridge + item colors"
    ) else (
        set "TEXT_BRIDGE_SRC=text_visual\player_name_text_bridge.cpp"
        set "TEXT_BRIDGE_OBJ=player_name_text_bridge.obj"
        set "TEXT_BRIDGE_LABEL=text_visual - standalone EXTN/player-name bridge"
    )

    echo [text] extended_name - EXTN transport + substitution state...
    cl.exe /nologo /c /O2 /Gy /MT /EHa /I"./" ^
        extended_name\extended_name.cpp /Fo:extended_name.obj
    if errorlevel 1 (echo FAILED & exit /b 1)

    echo [text] player_name_color - standalone player color policy...
    cl.exe /nologo /c /O2 /Gy /MT /EHa /I"./" ^
        player_name_color\player_name_color.cpp /Fo:player_name_color.obj
    if errorlevel 1 (echo FAILED & exit /b 1)

    echo [text] !TEXT_BRIDGE_LABEL!...
    cl.exe /nologo /c /O2 /Gy /MT /EHa /I"./" ^
        !TEXT_BRIDGE_SRC! /Fo:!TEXT_BRIDGE_OBJ!
    if errorlevel 1 (echo FAILED & exit /b 1)

    set "LINK_OBJECTS=!LINK_OBJECTS! extended_name.obj player_name_color.obj !TEXT_BRIDGE_OBJ!"
) else (
    echo [skip] text visual modules disabled
)

if "%BOH_RUNE_VISUAL%"=="1" (
    echo [feature] rune_visual - Rune system rendering...
    cl.exe /nologo /c /O2 /MT /EHsc /I"./" ^
        /DDllMain=RuneVisualDllMain ^
        rune_visual\boh_rune_visual.cpp /Fo:rune_visual.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    set "LINK_OBJECTS=!LINK_OBJECTS! rune_visual.obj"
) else (
    echo [skip] rune_visual disabled
)

if "%BOH_FPS_PING%"=="1" (
    echo [feature] fps_ping - FPS/Ping overlay...
    cl.exe /nologo /c /O2 /MT /EHsc /I"./" ^
        /DDllMain=FpsOverlayDllMain ^
        fps_ping\fps_ping_overlay.cpp /Fo:fps_ping.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    cl.exe /nologo /c /O2 /MT /I"./" ^
        fps_ping\ping.cpp /Fo:ping.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    set "LINK_OBJECTS=!LINK_OBJECTS! fps_ping.obj ping.obj"
) else (
    echo [skip] FPS/Ping overlay disabled
)

if "%BOH_NPC_NAME_OVERLAY%"=="1" (
    echo [feature] npc_name_overlay - NPC name overlay...
    cl.exe /nologo /c /O2 /MT /EHa /I"./" ^
        /DDllMain=NpcNameOverlayDllMain ^
        npc_name_overlay\npc_name_overlay.cpp /Fo:npc_name_overlay.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    set "LINK_OBJECTS=!LINK_OBJECTS! npc_name_overlay.obj"
) else (
    echo [skip] NPC name overlay disabled
)

if "%BOH_INVENTORY_TABS%"=="1" (
    echo [feature] inventory_tabs - Image-based inventory tabs...
    cl.exe /nologo /c /O2 /MT /EHa /I"./" ^
        /DDllMain=InvTabsDllMain ^
        inventory_tabs\inventory_tabs.cpp /Fo:inventory_tabs.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    set "LINK_OBJECTS=!LINK_OBJECTS! inventory_tabs.obj"
) else (
    echo [skip] inventory tabs disabled
)

if "%BOH_PINCODE_UI%"=="1" (
    echo [feature] pincode_ui - In-game PIN keypad...
    cl.exe /nologo /c /O2 /MT /EHsc /I"./" ^
        pincode_ui\pincode_ui.cpp /Fo:pincode_ui.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    set "LINK_OBJECTS=!LINK_OBJECTS! pincode_ui.obj"
) else (
    echo [skip] pincode UI disabled
)

if "%BOH_WEAPON_SPRITE%"=="1" (
    echo [feature] weapon_sprite - Dual-wield custom renderer host...
    cl.exe /nologo /c /O2 /MT /EHa /I"./" ^
        /DDllMain=WeaponSpriteDllMain ^
        weapon_sprite\weapon_sprite.cpp /Fo:weapon_sprite.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    cl.exe /nologo /c /O2 /MT /EHa /I"./" ^
        weapon_sprite\weapon_overlay.cpp /Fo:weapon_overlay.obj
    if errorlevel 1 (echo FAILED & exit /b 1)
    set "LINK_OBJECTS=!LINK_OBJECTS! weapon_sprite.obj weapon_overlay.obj"
) else (
    echo [skip] weapon sprite disabled
)

echo [LINK] boh.dll...
link.exe /nologo /DLL /OPT:REF /OUT:boh.dll ^
    !LINK_OBJECTS! ^
    kernel32.lib user32.lib gdi32.lib d3d9.lib iphlpapi.lib ws2_32.lib
if errorlevel 1 (echo FAILED & exit /b 1)

echo.
echo ============================================================
echo  Build successful: boh.dll
echo  Deploy: copy/rename boh.dll to the game folder, e.g. bohcustoms.dll.
echo ============================================================
endlocal
