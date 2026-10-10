$ErrorActionPreference = 'Stop'
function Assert-Hash([string]$File, [string]$Expected) {
    $actual = (Get-FileHash -LiteralPath $File -Algorithm SHA256).Hash
    if ($actual -ne $Expected) { throw "SHA256 mismatch: $File. Delete this cached file and retry." }
}
function Get-VerifiedDownload([string]$Url, [string]$Destination, [string]$Hash) {
    if (!(Test-Path -LiteralPath $Destination)) {
        $partial = "$Destination.partial"
        try {
            Invoke-WebRequest -Uri $Url -OutFile $partial -UseBasicParsing -TimeoutSec 120
            Assert-Hash $partial $Hash
            Move-Item -LiteralPath $partial -Destination $Destination
        } finally {
            if (Test-Path -LiteralPath $partial) { Remove-Item -LiteralPath $partial -Force }
        }
    }
    Assert-Hash $Destination $Hash
}
