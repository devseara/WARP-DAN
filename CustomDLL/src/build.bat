@echo off
setlocal
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

echo [1/10] Cleaning...
del /q *.obj boh.dll boh.exp boh.lib >nul 2>&1

echo [2/10] main_proxy - DllMain + DDRAW forwarding...
cl.exe /nologo /c /O2 /MT /EHsc /I"./" ^
    main_proxy\main_proxy.cpp
if errorlevel 1 (echo FAILED & exit /b 1)

echo [3/10] extended_name - EXTN transport + substitution state...
cl.exe /nologo /c /O2 /Gy /MT /EHa /I"./" ^
    extended_name\extended_name.cpp /Fo:extended_name.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [4/10] item_color - static text wrappers + item colors...
cl.exe /nologo /c /O2 /Gy /MT /EHa /I"./" ^
    item_color\colored_itemname.cpp
if errorlevel 1 (echo FAILED & exit /b 1)

echo [5/10] rune_visual - Rune system rendering...
cl.exe /nologo /c /O2 /MT /EHsc /I"./" ^
    /DDllMain=RuneVisualDllMain ^
    rune_visual\boh_rune_visual.cpp /Fo:rune_visual.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [6/10] fps_ping - FPS/Ping overlay...
cl.exe /nologo /c /O2 /MT /EHsc /I"./" ^
    /DDllMain=FpsOverlayDllMain ^
    fps_ping\fps_ping_overlay.cpp /Fo:fps_ping.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [7/10] npc_name_overlay - NPC name overlay...
cl.exe /nologo /c /O2 /MT /EHa /I"./" ^
    /DDllMain=NpcNameOverlayDllMain ^
    npc_name_overlay\npc_name_overlay.cpp /Fo:npc_name_overlay.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [8/10] ping - Ping measurement...
cl.exe /nologo /c /O2 /MT /I"./" ^
    fps_ping\ping.cpp /Fo:ping.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [9/10] inventory_tabs - Image-based inventory tabs...
cl.exe /nologo /c /O2 /MT /EHa /I"./" ^
    /DDllMain=InvTabsDllMain ^
    inventory_tabs\inventory_tabs.cpp /Fo:inventory_tabs.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [10/10] pincode_ui - In-game PIN keypad...
cl.exe /nologo /c /O2 /MT /EHsc /I"./" ^
    pincode_ui\pincode_ui.cpp /Fo:pincode_ui.obj
if errorlevel 1 (echo FAILED & exit /b 1)

echo [LINK] boh.dll...
link.exe /nologo /DLL /OPT:REF /OUT:boh.dll ^
    main_proxy.obj colored_itemname.obj extended_name.obj rune_visual.obj ^
    fps_ping.obj ping.obj npc_name_overlay.obj inventory_tabs.obj pincode_ui.obj ^
    kernel32.lib user32.lib gdi32.lib d3d9.lib iphlpapi.lib ws2_32.lib
if errorlevel 1 (echo FAILED & exit /b 1)

echo.
echo ============================================================
echo  Build successful: boh.dll
echo  Deploy: copy/rename boh.dll to the game folder, e.g. bohcustoms.dll.
echo ============================================================
endlocal
