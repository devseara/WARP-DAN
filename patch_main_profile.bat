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


echo [done] %TARGET%
endlocal
exit /b 0
