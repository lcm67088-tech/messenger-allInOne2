param(
    [string]$SrcDir,
    [string]$DestZip
)
if (Test-Path $DestZip) { Remove-Item $DestZip -Force }
Compress-Archive -Path $SrcDir -DestinationPath $DestZip -Force
Write-Host "[OK] ZIP saved: $DestZip"
