@echo off
call "C:\Program Files\Microsoft Visual Studio\18\Community\VC\Auxiliary\Build\vcvars64.bat" > nul
if errorlevel 1 exit /b %errorlevel%
cl /nologo /EHsc /std:c++17 /I"..\BanquetOfHeroes\src" /I"..\BanquetOfHeroes\3rdparty\rapidyaml\src" /I"..\BanquetOfHeroes\3rdparty\rapidyaml\ext\c4core\src" /I"..\BanquetOfHeroes\3rdparty\pcre\include" /I"..\BanquetOfHeroes\3rdparty\mysql\include" /I"..\BanquetOfHeroes\3rdparty\libconfig" /Fo"Outputs\name_scope_fix_20260910\packet_table.obj" /Fe"Outputs\name_scope_fix_20260910\packet_table.exe" "tools\verify_name_scope.cpp" > "Outputs\name_scope_fix_20260910\compile.log" 2>&1
exit /b %errorlevel%
