param(
    [string]$InstallPath = "C:\Program Files\BAPPS Sync Agent"
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Abra PowerShell como Administrador para desinstalar el servicio."
}
$service = Join-Path $InstallPath "service\BAPPS-Sync-Service.exe"
if (Test-Path -LiteralPath $service) {
    & $service stop
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo detener el servicio BAPPSyncAgent."
    }
    & $service remove
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudo eliminar el servicio BAPPSyncAgent."
    }
}
Write-Host "Servicio BAPPS Sync Agent desinstalado. La configuracion en C:\ProgramData\Bapps\SyncAgent se conserva."
