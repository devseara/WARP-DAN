@echo off
setlocal
rem Stage-only Riftlock build. Uses the same hardened flags as build_split.bat
rem but writes riftlock.dll and the standalone verifier to riftlock_stage\.

set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
for /f "usebackq tokens=*" %%i in (`"%VSWHERE%" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do set "VSINSTALLPATH=%%i"
call "%VSINSTALLPATH%\VC\Auxiliary\Build\vcvars32.bat" >nul 2>&1 || (echo vcvars32 failed & exit /b 1)

cd /d "%~dp0"
if not exist riftlock_stage mkdir riftlock_stage

cl.exe /nologo /LD /O2 /GL /Gw /Gy /GS /guard:cf /W4 /WX /MT /EHsc /I"./" ^
	riftlock\riftlock.cpp ^
	/Fe:riftlock_stage\riftlock.dll /Fo:riftlock_stage\split_riftlock.obj ^
	/link /LTCG /OPT:REF /OPT:ICF /DYNAMICBASE /NXCOMPAT /GUARD:CF kernel32.lib advapi32.lib
if errorlevel 1 (echo FAILED riftlock.dll & exit /b 1)

cl.exe /nologo /O2 /W4 /WX /MT /EHsc /I"./" ^
	riftlock\riftlock_assets_verify.cpp ^
	/Fe:riftlock_stage\riftlock_v7_hooks_verify.exe /Fo:riftlock_stage\riftlock_assets_verify.obj ^
	/link kernel32.lib advapi32.lib
if errorlevel 1 (echo FAILED verifier & exit /b 1)

echo Riftlock stage build OK
endlocal
