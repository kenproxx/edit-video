param([switch]$SkipTests)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
. "$PSScriptRoot/download.ps1"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
if (![Environment]::Is64BitOperatingSystem) { throw 'Requires Windows x64.' }
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
$ProgressPreference = 'SilentlyContinue'
$cache = Join-Path $root '.build'
New-Item -ItemType Directory -Force $cache | Out-Null
$manifest = Get-Content "$root/packaging/downloads.json" -Raw | ConvertFrom-Json
Get-VerifiedDownload $manifest.python.url "$cache/python.zip" $manifest.python.sha256
Get-VerifiedDownload $manifest.ffmpeg.url "$cache/ffmpeg.zip" $manifest.ffmpeg.sha256
# Always extract verified archives, so an interrupted extraction is recoverable.
Expand-Archive -LiteralPath "$cache/python.zip" -DestinationPath "$cache/python" -Force
Expand-Archive -LiteralPath "$cache/ffmpeg.zip" -DestinationPath "$cache/ffmpeg" -Force
$basePython = "$cache/python/tools/python.exe"
function Run-Python([string[]]$Arguments) {
    & $script:python @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Python step failed ($LASTEXITCODE): $Arguments" }
}
$python = $basePython
Run-Python @('-m', 'venv', "$cache/venv")
$python = "$cache/venv/Scripts/python.exe"
Run-Python @('-m','pip','install','--require-hashes','--only-binary=:all:','-r',"$root/requirements-build.lock")
Run-Python @('-m','pip','install','--no-build-isolation','--no-deps',$root)
$ffmpeg = Get-ChildItem "$cache/ffmpeg" -Recurse -Filter ffmpeg.exe | Select-Object -First 1
$env:EDIT_VIDEO_FFMPEG_DIR = $ffmpeg.DirectoryName
$env:QT_QPA_PLATFORM = 'offscreen'
if (!$SkipTests) { Run-Python @('-m','pytest','-q','--junitxml=.build/test-results.xml') }
Run-Python @('scripts/collect_notices.py')
Run-Python @('-m','PyInstaller','--noconfirm','--clean','EditVideo.spec')
Remove-Item Env:QT_QPA_PLATFORM
Run-Python @('scripts/verify_bundle.py','dist/EditVideo')
$zip = "$root/dist/EditVideo-windows-x64.zip"
if (Test-Path $zip) { Remove-Item $zip -Force }
Compress-Archive -Path "$root/dist/EditVideo" -DestinationPath $zip
# Verify the delivered archive, not only the build directory.
Expand-Archive -LiteralPath $zip -DestinationPath "$cache/unpacked" -Force
Run-Python @('scripts/verify_bundle.py',"$cache/unpacked/EditVideo")
Write-Host "Ready: $zip"
