param([string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$repoRoot = Split-Path $PSScriptRoot -Parent
if (-not $OutputDirectory) { $OutputDirectory = Join-Path $repoRoot 'Outputs/riftlock-receive-tests' }
$OutputDirectory = [IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
$vswhere = Join-Path ${env:ProgramFiles(x86)} 'Microsoft Visual Studio\Installer\vswhere.exe'
$vsPath = & $vswhere -latest -products '*' -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath
if (-not $vsPath) { throw 'MSVC C++ tools are required.' }
$vcvars = Join-Path $vsPath 'VC\Auxiliary\Build\vcvars32.bat'
$source = Join-Path $repoRoot 'tools/riftlock_receive_test.cpp'
$include = Join-Path $repoRoot 'CustomDLL/src'
$commandFile = Join-Path $OutputDirectory 'run.cmd'
$lines = @('@echo off', ('call "{0}" >nul' -f $vcvars), ('cd /d "{0}"' -f $OutputDirectory),
    ('cl /nologo /std:c++17 /EHsc /MT /W4 /WX /DWIN32 /I"{0}" "{1}" /Fe:regression.exe' -f $include,$source),
    'if errorlevel 1 exit /b 1', 'regression.exe')
[IO.File]::WriteAllLines($commandFile,$lines,[Text.Encoding]::ASCII)
& $commandFile | Tee-Object -FilePath (Join-Path $OutputDirectory 'results.txt')
if ($LASTEXITCODE -ne 0) { throw "Riftlock regression failed ($LASTEXITCODE)." }
