@echo off
setlocal

cd /d "%~dp0"

set "PROFILE=profiles\2025-07-16 PROFILE MAIN.yml"
set "TARGET=2025-07-16_Ragexe_175220998_clientinfo\2025-07-16_Ragexe_175220998_clientinfo_patched.exe"

echo [warp] Applying %PROFILE%...
win32\WARP_console.exe -using "%PROFILE%"
if errorlevel 1 (
    echo [warp] FAILED
    exit /b 1
)

where py >nul 2>&1
if not errorlevel 1 (
    echo [bridge-iat] Repairing static bridge IAT operands...
    py -3 tools\fix_custom_bridge_iats.py "%TARGET%" --write
    if errorlevel 1 exit /b 1
    goto :done
)

where python >nul 2>&1
if errorlevel 1 (
    echo [bridge-iat] FAILED: Python was not found.
    exit /b 1
)

echo [bridge-iat] Repairing static bridge IAT operands...
python tools\fix_custom_bridge_iats.py "%TARGET%" --write
if errorlevel 1 exit /b 1

:done
echo [done] %TARGET%
endlocal
