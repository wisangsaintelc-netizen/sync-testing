param(
    [string]$Version = "0.7.10"
)

$ErrorActionPreference = "Stop"
$agentRoot = Split-Path -Parent $PSScriptRoot
$distPath = Join-Path $agentRoot "dist"
$releaseRoot = Join-Path $agentRoot "release"
$packageName = "BAPPS-Sync-Agent-$Version-windows-x64"
$packagePath = Join-Path $releaseRoot $packageName

foreach ($artifact in @("BAPPS-Sync-Agent", "BAPPS-Sync-Service")) {
    if (-not (Test-Path -LiteralPath (Join-Path $distPath "$artifact\$artifact.exe"))) {
        throw "No se encontro $artifact en $distPath. Ejecute build_portable.ps1 primero."
    }
}

if (Test-Path -LiteralPath $packagePath) {
    Remove-Item -LiteralPath $packagePath -Recurse -Force
}
New-Item -ItemType Directory -Path $packagePath -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $packagePath "dist") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $packagePath "scripts") -Force | Out-Null

Copy-Item -Path (Join-Path $distPath "BAPPS-Sync-Agent") -Destination (Join-Path $packagePath "dist") -Recurse -Force
Copy-Item -Path (Join-Path $distPath "BAPPS-Sync-Service") -Destination (Join-Path $packagePath "dist") -Recurse -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "install_service.ps1") -Destination (Join-Path $packagePath "scripts") -Force
Copy-Item -LiteralPath (Join-Path $PSScriptRoot "uninstall_service.ps1") -Destination (Join-Path $packagePath "scripts") -Force
Copy-Item -LiteralPath (Join-Path $agentRoot "README_INSTALACION.md") -Destination $packagePath -Force

$archivePath = Join-Path $releaseRoot "$packageName.zip"
if (Test-Path -LiteralPath $archivePath) {
    Remove-Item -LiteralPath $archivePath -Force
}
Compress-Archive -Path $packagePath -DestinationPath $archivePath -CompressionLevel Optimal
Write-Host "Paquete generado: $archivePath"
