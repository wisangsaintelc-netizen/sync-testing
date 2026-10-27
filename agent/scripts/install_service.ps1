param(
    [string]$DistPath = (Split-Path -Parent $PSScriptRoot) + "\dist",
    [string]$InstallPath = "C:\Program Files\BAPPS Sync Agent"
)

$ErrorActionPreference = "Stop"
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Abra PowerShell como Administrador para instalar el servicio."
}
$guiSource = Join-Path $DistPath "BAPPS-Sync-Agent"
$serviceSource = Join-Path $DistPath "BAPPS-Sync-Service"
if (-not (Test-Path -LiteralPath (Join-Path $guiSource "BAPPS-Sync-Agent.exe"))) {
    throw "No se encontro BAPPS-Sync-Agent.exe en $guiSource. Compile primero el portable."
}
if (-not (Test-Path -LiteralPath (Join-Path $serviceSource "BAPPS-Sync-Service.exe"))) {
    throw "No se encontro BAPPS-Sync-Service.exe en $serviceSource. Compile primero el portable."
}

New-Item -ItemType Directory -Path $InstallPath -Force | Out-Null
$statePath = "C:\ProgramData\Bapps\SyncAgent"
New-Item -ItemType Directory -Path $statePath -Force | Out-Null
$stateOwner = (Get-Acl -LiteralPath $statePath).Owner
$installerUser = [Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls $statePath /inheritance:r /grant:r "$stateOwner`:(OI)(CI)F" "$installerUser`:(OI)(CI)F" "*S-1-5-18:(OI)(CI)F" "*S-1-5-32-544:(OI)(CI)F" /T /C | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "No se pudieron proteger los permisos de $statePath."
}
Copy-Item -Path (Join-Path $guiSource "*") -Destination $InstallPath -Recurse -Force
$serviceInstallPath = Join-Path $InstallPath "service"
New-Item -ItemType Directory -Path $serviceInstallPath -Force | Out-Null
Copy-Item -Path (Join-Path $serviceSource "*") -Destination $serviceInstallPath -Recurse -Force
$service = Join-Path $serviceInstallPath "BAPPS-Sync-Service.exe"
& $service --startup auto install
if ($LASTEXITCODE -ne 0) {
    throw "No se pudo registrar el servicio BAPPSyncAgent."
}
& $service start
if ($LASTEXITCODE -ne 0) {
    throw "El servicio se registro, pero no se pudo iniciar."
}
Write-Host "Servicio BAPPS Sync Agent instalado e iniciado. La GUI queda en $InstallPath y ambos usan C:\ProgramData\Bapps\SyncAgent con permisos restringidos."
