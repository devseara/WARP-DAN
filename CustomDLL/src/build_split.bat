@echo off
setlocal
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

echo [1/12] Cleaning dedicated outputs...
del /q split_*.obj boh_text.dll boh_text.exp boh_text.lib ^
    boh_npc_names.dll boh_npc_names.exp boh_npc_names.lib ^
    boh_rune.dll boh_rune.exp boh_rune.lib ^
    boh_fps.dll boh_fps.exp boh_fps.lib ^
    boh_inventory_tabs.dll boh_inventory_tabs.exp boh_inventory_tabs.lib ^
    boh_weapon_sprite.dll boh_weapon_sprite.exp boh_weapon_sprite.lib ^
    boh_pincode_ui.dll boh_pincode_ui.exp boh_pincode_ui.lib >nul 2>&1

echo [2/12] Extended-name state...
cl.exe /nologo /c /O2 /Gy /MT /EHa /I"./" ^
    extended_name\extended_name.cpp /Fo:split_extended_name.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [3/12] Shared static text wrappers + item/player-name colors...
cl.exe /nologo /c /O2 /Gy /MT /EHa /I"./" ^
    item_color\colored_itemname.cpp /Fo:split_item_color.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [4/12] Text visual entry point...
cl.exe /nologo /c /O2 /Gy /MT /EHsc /I"./" ^
    text_visual\text_visual_proxy.cpp /Fo:split_text_proxy.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [5/12] Link boh_text.dll...
link.exe /nologo /DLL /OPT:REF /OUT:boh_text.dll ^
    split_text_proxy.obj split_item_color.obj split_extended_name.obj ^
    kernel32.lib user32.lib gdi32.lib
if errorlevel 1 (echo FAILED & exit /b 1)

echo [6/12] Build boh_npc_names.dll...
cl.exe /nologo /LD /O2 /MT /EHa /I"./" ^
    /DNpcNameOverlayDllMain=DllMain ^
    npc_name_overlay\npc_name_overlay.cpp ^
    /Fe:boh_npc_names.dll /Fo:split_npc_name_overlay.obj ^
    /link kernel32.lib user32.lib
if errorlevel 1 (echo FAILED & exit /b 1)

echo [7/12] Build boh_rune.dll...
cl.exe /nologo /c /O2 /GS- /GR- /I"./" ^
    rune_visual\boh_rune_visual.cpp /Fo:split_rune_visual.obj
if errorlevel 1 (echo FAILED & exit /b 1)
link.exe /nologo /DLL /ENTRY:DllMain /NODEFAULTLIB /OUT:boh_rune.dll ^
    split_rune_visual.obj kernel32.lib user32.lib
if errorlevel 1 (echo FAILED & exit /b 1)

echo [8/12] Compile FPS/ping...
cl.exe /nologo /c /O2 /MT /EHsc /I"./" ^
    fps_ping\fps_ping_overlay.cpp /Fo:split_fps_overlay.obj
if errorlevel 1 (echo FAILED & exit /b 1)
cl.exe /nologo /c /O2 /MT /I"./" ^
    fps_ping\ping.cpp /Fo:split_ping.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [9/12] Link boh_fps.dll...
link.exe /nologo /DLL /OUT:boh_fps.dll ^
    split_fps_overlay.obj split_ping.obj ^
    kernel32.lib user32.lib gdi32.lib d3d9.lib iphlpapi.lib ws2_32.lib
if errorlevel 1 (echo FAILED & exit /b 1)

echo [10/12] Build boh_inventory_tabs.dll...
cl.exe /nologo /LD /O2 /MT /EHa /I"./" ^
    inventory_tabs\inventory_tabs.cpp ^
    /Fe:boh_inventory_tabs.dll /Fo:split_inventory_tabs.obj ^
    /link kernel32.lib user32.lib
if errorlevel 1 (echo FAILED & exit /b 1)

echo [11/12] Build boh_weapon_sprite.dll...
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

echo [12/12] Build boh_pincode_ui.dll...
cl.exe /nologo /LD /O2 /MT /EHsc /I"./" ^
    pincode_ui\pincode_ui.cpp ^
    /Fe:boh_pincode_ui.dll /Fo:split_pincode_ui.obj ^
    /link kernel32.lib user32.lib gdi32.lib
if errorlevel 1 (echo FAILED & exit /b 1)

echo.
echo ============================================================
echo  Dedicated DLL build successful
echo    boh_text.dll           item colors + extended names + player name colors
echo    boh_npc_names.dll      always-show NPC names
echo    boh_rune.dll           rune visuals
echo    boh_fps.dll            FPS + ping
echo    boh_inventory_tabs.dll inventory tabs
echo    boh_weapon_sprite.dll  dual-wield custom renderer host
echo    boh_pincode_ui.dll     in-game PIN keypad
echo.
echo  These files may be renamed. Enter the matching filename in
echo  the corresponding WARP patch prompt.
echo ============================================================
endlocal
