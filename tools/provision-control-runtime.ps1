[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [ValidateNotNullOrEmpty()]
    [string]$PhpPath,

    [string]$ProjectPath,

    [switch]$GenerateSigningKey,

    [ValidatePattern('^[A-Za-z0-9._-]+$')]
    [string]$SigningKeyId = 'recipe-v1',

    [switch]$SkipLaravelCacheClear
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ([string]::IsNullOrWhiteSpace($ProjectPath)) {
    $ProjectPath = Join-Path $PSScriptRoot '..'
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Content)

    $temporaryPath = "$Path.bapps-tmp-$PID"
    [System.IO.File]::WriteAllText(
        $temporaryPath,
        $Content,
        [System.Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $temporaryPath -Destination $Path -Force
}

function Get-EnvValue {
    param([string]$Path, [string]$Name)

    if (-not (Test-Path -LiteralPath $Path)) {
        return $null
    }

    $match = [regex]::Match(
        [System.IO.File]::ReadAllText($Path),
        "(?m)^\s*$([regex]::Escape($Name))\s*=\s*(.*)$"
    )

    if (-not $match.Success) {
        return $null
    }

    return $match.Groups[1].Value.Trim().Trim('"').Trim("'")
}

function Set-EnvValue {
    param([string]$Path, [string]$Name, [string]$Value)

    $content = if (Test-Path -LiteralPath $Path) {
        [System.IO.File]::ReadAllText($Path)
    } else {
        ''
    }

    $line = "$Name=$Value"
    $pattern = "(?m)^\s*$([regex]::Escape($Name))\s*=.*$"

    if ([regex]::IsMatch($content, $pattern)) {
        $content = ([regex]$pattern).Replace(
            $content,
            [System.Text.RegularExpressions.MatchEvaluator]{ param($m) $line },
            1
        )
    } else {
        if ($content.Length -gt 0 -and -not $content.EndsWith("`n")) {
            $content += [Environment]::NewLine
        }
        $content += "$line$([Environment]::NewLine)"
    }

    Write-Utf8NoBom -Path $Path -Content $content
}

function Test-PhpModule {
    param([string[]]$Modules, [string]$Name)

    return $Modules -contains $Name.ToLowerInvariant()
}

$phpExe = (Resolve-Path -LiteralPath $PhpPath).Path
if ((Split-Path -Leaf $phpExe).ToLowerInvariant() -ne 'php.exe') {
    throw "-PhpPath debe apuntar a php.exe, no a una carpeta. Recibido: $phpExe"
}

$projectRoot = (Resolve-Path -LiteralPath $ProjectPath).Path
$envFile = Join-Path $projectRoot '.env'
$artisanFile = Join-Path $projectRoot 'artisan'
$phpDirectory = Split-Path -Parent $phpExe
$phpIni = Join-Path $phpDirectory 'php.ini'
$extensionDirectory = Join-Path $phpDirectory 'ext'

if (-not (Test-Path -LiteralPath $extensionDirectory)) {
    throw "No existe la carpeta de extensiones de PHP: $extensionDirectory"
}

$requiredExtensions = @('mbstring', 'sodium', 'pdo_mysql', 'pdo_sqlite', 'curl', 'fileinfo', 'openssl')
foreach ($extension in $requiredExtensions) {
    $dllPath = Join-Path $extensionDirectory "php_$extension.dll"
    if (-not (Test-Path -LiteralPath $dllPath)) {
        throw "Falta la extensión requerida '$extension' ($dllPath). Instale una distribución completa de PHP para Windows."
    }
}

$iniExisted = Test-Path -LiteralPath $phpIni
$previousIni = if ($iniExisted) { [System.IO.File]::ReadAllText($phpIni) } else { $null }
$backupPath = $null

try {
    if ($iniExisted) {
        $backupPath = "$phpIni.bapps-backup-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
        Copy-Item -LiteralPath $phpIni -Destination $backupPath -ErrorAction Stop
        $iniContent = $previousIni
    } else {
        $template = Join-Path $phpDirectory 'php.ini-production'
        if (-not (Test-Path -LiteralPath $template)) {
            throw "No existe php.ini ni la plantilla segura php.ini-production en $phpDirectory"
        }
        $iniContent = [System.IO.File]::ReadAllText($template)
    }

    # El bloque anterior es administrado por este script. Se quita antes de
    # detectar extensiones activas para poder reconstruirlo completo e idempotente.
    $iniContent = [regex]::Replace(
        $iniContent,
        '(?ms)\r?\n?; BEGIN BAPPS Sync Control Runtime.*?; END BAPPS Sync Control Runtime\r?\n?',
        "`r`n"
    )

    $activeExtensions = [System.Collections.Generic.HashSet[string]]::new([System.StringComparer]::OrdinalIgnoreCase)
    foreach ($match in [regex]::Matches($iniContent, '(?im)^\s*extension\s*=\s*"?([^\s";]+)"?\s*(?:;.*)?$')) {
        $name = $match.Groups[1].Value -replace '^php_', '' -replace '\.dll$', ''
        [void]$activeExtensions.Add($name)
    }

    $bappsBlock = @(
        '',
        '; BEGIN BAPPS Sync Control Runtime',
        '; Managed by tools/provision-control-runtime.ps1. Do not put secrets here.',
        "extension_dir = `"$extensionDirectory`""
    )
    foreach ($extension in $requiredExtensions) {
        if (-not $activeExtensions.Contains($extension)) {
            $bappsBlock += "extension=$extension"
        }
    }
    $bappsBlock += '; END BAPPS Sync Control Runtime'

    $iniContent = $iniContent.TrimEnd() + "`r`n" + ($bappsBlock -join "`r`n") + "`r`n"
    Write-Utf8NoBom -Path $phpIni -Content $iniContent

    $moduleOutput = & $phpExe -m 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "PHP no pudo cargar php.ini. Salida: $($moduleOutput -join [Environment]::NewLine)"
    }
    $loadedModules = @($moduleOutput | ForEach-Object { $_.ToString().Trim().ToLowerInvariant() })
    $missingModules = @($requiredExtensions | Where-Object { -not (Test-PhpModule -Modules $loadedModules -Name $_) })
    if ($missingModules.Count -gt 0) {
        throw "PHP inició, pero faltan extensiones: $($missingModules -join ', '). Revise el respaldo y las DLL de $extensionDirectory"
    }

    $signingKey = Get-EnvValue -Path $envFile -Name 'BAPPS_SYNC_RECIPE_SIGNING_PRIVATE_KEY'
    $keyStatus = 'ya existente; no se modificó'
    if ([string]::IsNullOrWhiteSpace($signingKey)) {
        if (-not $GenerateSigningKey) {
            $keyStatus = 'pendiente: ejecute otra vez con -GenerateSigningKey para crearla'
        } else {
            $generator = '$keypair = sodium_crypto_sign_keypair(); echo base64_encode(sodium_crypto_sign_secretkey($keypair));'
            $signingKey = (& $phpExe -r $generator).ToString().Trim()
            try {
                $keyBytes = [Convert]::FromBase64String($signingKey)
            } catch {
                throw 'PHP devolvió una clave de firma inválida.'
            }
            if ($keyBytes.Length -ne 64) {
                throw 'PHP devolvió una clave de firma con una longitud inválida.'
            }
            Set-EnvValue -Path $envFile -Name 'BAPPS_SYNC_RECIPE_SIGNING_PRIVATE_KEY' -Value $signingKey
            Set-EnvValue -Path $envFile -Name 'BAPPS_SYNC_RECIPE_SIGNING_KEY_ID' -Value $SigningKeyId
            $keyStatus = "generada y guardada con key id '$SigningKeyId'"
        }
    }

    if (-not $SkipLaravelCacheClear -and (Test-Path -LiteralPath $artisanFile)) {
        Push-Location $projectRoot
        try {
            $artisanOutput = & $phpExe artisan config:clear 2>&1
            if ($LASTEXITCODE -ne 0) {
                throw "Laravel no pudo limpiar la caché de configuración. Salida: $($artisanOutput -join [Environment]::NewLine)"
            }
        } finally {
            Pop-Location
        }
    }
} catch {
    if ($iniExisted) {
        Write-Utf8NoBom -Path $phpIni -Content $previousIni
    } elseif (Test-Path -LiteralPath $phpIni) {
        Remove-Item -LiteralPath $phpIni -Force
    }
    throw
}

Write-Host ''
Write-Host 'BAPPS Sync Control Runtime listo.' -ForegroundColor Green
Write-Host "PHP: $phpExe"
Write-Host "php.ini: $phpIni$(if ($backupPath) { " (respaldo: $backupPath)" })"
Write-Host "Extensiones verificadas: $($requiredExtensions -join ', ')"
Write-Host "Clave de recetas: $keyStatus"
Write-Host 'La clave secreta no se muestra ni se escribe en php.ini.'
