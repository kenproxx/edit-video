# Downloads are pinned and verified before execution or extraction.
[CmdletBinding()]
param(
    [string]$CacheDir,
    [string]$ManifestPath,
    [switch]$VerifyCache
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

function Assert-Hash([string]$Path, [string]$Expected) {
    if ($Expected -notmatch '^[0-9a-fA-F]{64}$') { throw 'Invalid SHA256 in build manifest' }
    if ((Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash -ne $Expected) {
        throw "SHA256 mismatch: $Path. Remove the corrupt cache file and retry."
    }
}
function Get-VerifiedArtifact($Artifact) {
    $target = Join-Path $CacheDir $Artifact.filename
    if (Test-Path -LiteralPath $target -PathType Leaf) {
        Assert-Hash $target $Artifact.sha256
        return $target
    }
    if (-not $Artifact.url.StartsWith('https://')) { throw 'Download must use HTTPS' }
    $partial = "$target.$([guid]::NewGuid().ToString('N')).partial"
    try {
        Invoke-WebRequest -Uri $Artifact.url -OutFile $partial -UseBasicParsing
        Assert-Hash $partial $Artifact.sha256
        Move-Item -LiteralPath $partial -Destination $target
    } finally {
        if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
    }
    return $target
}
function Invoke-Checked([string]$Program, [string[]]$Arguments) {
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) { throw "Command failed ($LASTEXITCODE): $Program" }
}
function Test-Python([string]$Program, [string]$Version) {
    if (-not (Test-Path -LiteralPath $Program -PathType Leaf)) { return $false }
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Program -I -c "import sys,struct,tkinter,venv,ensurepip; assert '.'.join(map(str,sys.version_info[:3])) == '$Version'; assert struct.calcsize('P') == 8" 2>$null
        return $LASTEXITCODE -eq 0
    } catch { return $false } finally { $ErrorActionPreference = $savedPreference }
}

try {
    # Resolve defaults after parameter binding: PSScriptRoot may be empty
    # while Windows PowerShell evaluates default parameter expressions.
    $scriptDir = $PSScriptRoot
    if ([string]::IsNullOrEmpty($scriptDir)) {
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    if ([string]::IsNullOrEmpty($CacheDir)) {
        $CacheDir = Join-Path $scriptDir '..\.build-cache'
    }
    if ([string]::IsNullOrEmpty($ManifestPath)) {
        $ManifestPath = Join-Path $scriptDir 'build-manifest.json'
    }
    $manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema_version -ne 1) { throw 'Unsupported build manifest schema' }
    if ($VerifyCache) {
        $verified = 0
        foreach ($artifact in @($manifest.ffmpeg,$manifest.python)) {
            $path = Join-Path $CacheDir $artifact.filename
            if (Test-Path -LiteralPath $path -PathType Leaf) { Assert-Hash $path $artifact.sha256; $verified++ }
        }
        if ($verified -eq 0) { throw 'No cached artifacts to verify' }
        Write-Host "Verified $verified cached artifacts"
        exit 0
    }
    if ([Environment]::OSVersion.Platform -ne 'Win32NT' -or -not [Environment]::Is64BitProcess -or $env:PROCESSOR_ARCHITECTURE -ne 'AMD64') {
        throw 'Build requires Windows x64 (PowerShell x64); Linux cross-build is unsupported.'
    }
    $root = [IO.Path]::GetFullPath((Join-Path $scriptDir '..'))
    $CacheDir = [IO.Path]::GetFullPath($CacheDir)
    New-Item -ItemType Directory -Path $CacheDir -Force | Out-Null
    $pythonHome = Join-Path $CacheDir "python-$($manifest.python.version)"
    $python = Join-Path $pythonHome 'python.exe'
    if (-not (Test-Python $python $manifest.python.version)) {
        $existing = Get-Command python.exe -ErrorAction SilentlyContinue
        if ($existing -and (Test-Python $existing.Source $manifest.python.version)) {
            $python = $existing.Source
        } else {
            $installer = Get-VerifiedArtifact $manifest.python
            $signature = Get-AuthenticodeSignature -LiteralPath $installer
            if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'O=Python Software Foundation(?:,|$)') {
                throw 'Python installer Authenticode signature is not valid for Python Software Foundation'
            }
            $arguments = @('/quiet','InstallAllUsers=0',"TargetDir=`"$pythonHome`"",'Include_pip=1','Include_tcltk=1','Include_launcher=0','InstallLauncherAllUsers=0','PrependPath=0','AssociateFiles=0','Shortcuts=0','Include_test=0','Include_doc=0')
            $process = Start-Process -FilePath $installer -ArgumentList $arguments -PassThru -Wait
            if ($process.ExitCode -notin @(0,3010)) { throw "Python installer failed: $($process.ExitCode)" }
            if (-not (Test-Python $python $manifest.python.version)) { throw 'Private Python installation failed validation (version/x64/Tk/venv)' }
        }
    }
    # Fresh build venv prevents mutated installed wheels from being reused.
    $venv = Join-Path $CacheDir 'venv'
    if (Test-Path -LiteralPath $venv) { Remove-Item -LiteralPath $venv -Recurse -Force }
    Invoke-Checked $python @('-I','-m','venv',$venv)
    $buildPython = Join-Path $venv 'Scripts\python.exe'
    Invoke-Checked $buildPython @('-I','-m','pip','install','--disable-pip-version-check','--require-hashes','--only-binary=:all:','-r',(Join-Path $root 'requirements-build.txt'))
    Invoke-Checked $buildPython @('-I','-m','pip','check')
    $archive = Get-VerifiedArtifact $manifest.ffmpeg
    $unpack = Join-Path $CacheDir 'ffmpeg-extracted'
    if (Test-Path -LiteralPath $unpack) { Remove-Item -LiteralPath $unpack -Recurse -Force }
    Expand-Archive -LiteralPath $archive -DestinationPath $unpack
    $ffmpegRoot = Join-Path $unpack $manifest.ffmpeg.archive_root
    $tools = Join-Path $root 'tools'
    New-Item -ItemType Directory -Path $tools -Force | Out-Null
    foreach ($tool in @('ffmpeg.exe','ffprobe.exe','ffplay.exe')) {
        Copy-Item -LiteralPath (Join-Path $ffmpegRoot "bin\$tool") -Destination (Join-Path $tools $tool) -Force
    }
    $licenses = Join-Path $root 'build\licenses'
    if (Test-Path -LiteralPath $licenses) { Remove-Item -LiteralPath $licenses -Recurse -Force }
    New-Item -ItemType Directory -Path (Join-Path $licenses 'ffmpeg') -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $ffmpegRoot 'LICENSE'),(Join-Path $ffmpegRoot 'README.txt') -Destination (Join-Path $licenses 'ffmpeg')
    $roboto = Join-Path $licenses 'Roboto'
    New-Item -ItemType Directory -Path $roboto -Force | Out-Null
    Copy-Item -LiteralPath (Join-Path $root 'licenses\Roboto-APACHE-2.0.txt') -Destination $roboto
    Push-Location $root
    try {
        Invoke-Checked $buildPython @('scripts\prepare-package.py','--licenses',$licenses)
        Invoke-Checked $buildPython @('-m','PyInstaller','--clean','--noconfirm','VideoEditor.spec')
        if (-not (Test-Path -LiteralPath (Join-Path $root 'dist\VideoEditor.exe') -PathType Leaf)) { throw 'PyInstaller did not produce VideoEditor.exe' }
        Copy-Item -LiteralPath (Join-Path $root 'THIRD_PARTY_NOTICES.md') -Destination (Join-Path $root 'dist') -Force
        if (Test-Path -LiteralPath (Join-Path $root 'dist\licenses')) { Remove-Item -LiteralPath (Join-Path $root 'dist\licenses') -Recurse -Force }
        Copy-Item -LiteralPath $licenses -Destination (Join-Path $root 'dist\licenses') -Recurse
        $exeHash = (Get-FileHash -LiteralPath (Join-Path $root 'dist\VideoEditor.exe') -Algorithm SHA256).Hash.ToLowerInvariant()
        [IO.File]::WriteAllText((Join-Path $root 'dist\VideoEditor.exe.sha256'),"$exeHash  VideoEditor.exe`n")
    } finally { Pop-Location }
    Write-Host 'Built dist\VideoEditor.exe. Validate on Windows before distributing.'
} catch {
    [Console]::Error.WriteLine($_.Exception.Message)
    exit 1
}
