param(
    [string]$Profile = "profiles/2025-07-16 GEPARD SAFE.yml"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$profilePath = Join-Path $root $Profile

if (!(Test-Path -LiteralPath $profilePath)) {
    throw "Profile not found: $Profile"
}

$failed = $false
$profileText = Get-Content -Raw -LiteralPath $profilePath

$bannedPatches = @(
    "RecvStrip0BB6",
    "AllowDualCustomWeaponSprites",
    "NoNagle",
    "EnableProxy",
    "LoadClientPlugins",
    "IgnoreDebugger",
    "SkipCheatCheck",
    "NoGGuard",
    "DisableProtect",
    "RestoreCpsDll",
    "CustomDLL"
)

foreach ($patch in $bannedPatches) {
    if ($profileText -match "(?m)^\s*-\s*$([regex]::Escape($patch))\s*$") {
        Write-Host "FAIL profile contains banned patch: $patch" -ForegroundColor Red
        $failed = $true
    }
}

$bannedDllNames = @(
    "boh.dll",
    "boh_weapon_sprite.dll"
)

foreach ($dll in $bannedDllNames) {
    if ($profileText -match [regex]::Escape($dll)) {
        Write-Host "FAIL profile references runtime-hook DLL: $dll" -ForegroundColor Red
        $failed = $true
    }
}

$safeSources = @(
    "Scripts/Patches/AlwaysShowNpcName.qjs",
    "Scripts/Patches/CustomExtName.qjs",
    "Scripts/Patches/CustomColoredItemName.qjs",
    "Scripts/Patches/ROGlobalZeroInventory.qjs",
    "Scripts/Patches/FpsOverlay.qjs",
    "Scripts/Patches/PingOverlay.qjs",
    "Scripts/Patches/InGamePincodeUI.qjs",
    "Scripts/Patches/AutoCombatUI.qjs",
    "Scripts/Patches/CustomRuneSystem.qjs"
)

$bannedSourcePattern = "WriteProcessMemory|CreateRemoteThread|SetWindowsHook"

foreach ($source in $safeSources) {
    $sourcePath = Join-Path $root $source
    if (!(Test-Path -LiteralPath $sourcePath)) {
        Write-Host "FAIL safe source missing: $source" -ForegroundColor Red
        $failed = $true
        continue
    }

    $matches = Select-String -LiteralPath $sourcePath -Pattern $bannedSourcePattern -AllMatches
    foreach ($match in $matches) {
        Write-Host "FAIL banned runtime-hook token in ${source}:$($match.LineNumber): $($match.Line.Trim())" -ForegroundColor Red
        $failed = $true
    }
}

$allowedDlls = @(
    "boh_rune.dll"
)

$bannedBinaryTokens = @(
    "VirtualAlloc",
    "FlushInstructionCache",
    "WriteProcessMemory",
    "CreateRemoteThread",
    "SetWindowsHook",
    "patch_jmp",
    "patch_call",
    "HookRecv",
    "InstallRecvHook",
    "ws2_32.recv",
    "recv"
)

foreach ($dll in $allowedDlls) {
    if ($profileText -notmatch [regex]::Escape($dll)) {
        continue
    }

    $dllPath = Join-Path $root "CustomDLL/src/$dll"
    if (!(Test-Path -LiteralPath $dllPath)) {
        Write-Host "FAIL allowed DLL referenced but missing: $dll" -ForegroundColor Red
        $failed = $true
        continue
    }

    $bytes = [System.IO.File]::ReadAllBytes($dllPath)
    $ascii = [System.Text.Encoding]::ASCII.GetString($bytes)
    foreach ($token in $bannedBinaryTokens) {
        if ($ascii.Contains($token)) {
            Write-Host "FAIL banned runtime token in ${dll}: $token" -ForegroundColor Red
            $failed = $true
        }
    }
}

if ($failed) {
    exit 1
}

Write-Host "PASS Gepard-safe profile/runtime audit: $Profile" -ForegroundColor Green
