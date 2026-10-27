param(
    [string]$Version = "0.7.10",
    [string]$NsisCompiler = "makensis.exe",
    [string]$TrustBundle = ""
)

$ErrorActionPreference = "Stop"
$agentRoot = Split-Path -Parent $PSScriptRoot
$script = Join-Path $agentRoot "installer\BAPPS-Sync-Setup.nsi"
$releasePath = Join-Path $agentRoot "release"

foreach ($artifact in @("BAPPS-Sync-Agent", "BAPPS-Sync-Service")) {
    if (-not (Test-Path -LiteralPath (Join-Path $agentRoot "dist\$artifact\$artifact.exe"))) {
        throw "No se encontro $artifact. Ejecute build_portable.ps1 primero."
    }
}

New-Item -ItemType Directory -Path $releasePath -Force | Out-Null
$compilerArguments = @("/DAPP_VERSION=$Version")
if ($TrustBundle) {
    $resolvedTrustBundle = (Resolve-Path -LiteralPath $TrustBundle).Path
    $compilerArguments += "/DTRUST_BUNDLE=$resolvedTrustBundle"
}
$compilerArguments += $script
& $NsisCompiler @compilerArguments
if ($LASTEXITCODE -ne 0) {
    throw "NSIS no pudo generar el instalador."
}

$installer = Join-Path $releasePath "BAPPS-Sync-Setup-$Version.exe"
if (-not (Test-Path -LiteralPath $installer)) {
    throw "NSIS terminó sin generar $installer."
}
Write-Host "Instalador generado: $installer"
