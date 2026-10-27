param(
    [string]$Python = "python",
    [switch]$SkipDependencies,
    [switch]$ServiceOnly,
    [string]$TclTkRuntime = ""
)

$agentRoot = Split-Path -Parent $PSScriptRoot
$entryPoint = Join-Path $agentRoot "src\bapps_sync_agent\ui_main.py"
$specRoot = Join-Path $agentRoot "build\specs"
New-Item -ItemType Directory -Path $specRoot -Force | Out-Null

if (-not $SkipDependencies) {
    & $Python -m pip install -e "$agentRoot[portable]"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

Push-Location $agentRoot
try {
    if (-not $ServiceOnly) {
        $guiArguments = @(
            "-m", "PyInstaller",
            "--noconfirm", "--clean", "--windowed",
            "--name", "BAPPS-Sync-Agent",
            "--specpath", $specRoot,
            "--paths", "$agentRoot\src",
            "--hidden-import", "pymysql",
            "--hidden-import", "firebirdsql",
            "--hidden-import", "passlib.handlers.des_crypt",
            "--hidden-import", "pyodbc",
            "--hidden-import", "cryptography.hazmat.primitives.asymmetric.ed25519"
        )
        $tkinterLibrary = (& $Python -c "import pathlib, tkinter; print(pathlib.Path(tkinter.__file__).parent)").Trim()
        if (-not $tkinterLibrary) {
            throw "No se pudo localizar la biblioteca Python tkinter."
        }
        if ($TclTkRuntime) {
            $runtime = (Resolve-Path -LiteralPath $TclTkRuntime).Path
            $tclData = Join-Path $runtime "_tcl_data"
            $tkData = Join-Path $runtime "_tk_data"
        } else {
            $pythonBase = (& $Python -c "import sys; print(sys.base_prefix)").Trim()
            if (-not $pythonBase) {
                throw "No se pudo localizar el runtime base de Python."
            }
            $runtime = Join-Path $pythonBase "DLLs"
            $tclData = Join-Path $pythonBase "tcl\tcl8.6"
            $tkData = Join-Path $pythonBase "tcl\tk8.6"
        }
        foreach ($required in @(
            (Join-Path $runtime "_tkinter.pyd"),
            (Join-Path $runtime "tcl86t.dll"),
            (Join-Path $runtime "tk86t.dll"),
            $tclData,
            $tkData
        )) {
            if (-not (Test-Path -LiteralPath $required)) {
                throw "Runtime Tcl/Tk incompleto: falta $required."
            }
        }
        $guiArguments += @(
            "--hidden-import", "tkinter",
            "--hidden-import", "tkinter.ttk",
            "--hidden-import", "tkinter.messagebox",
            "--runtime-hook", "$PSScriptRoot\pyinstaller_tk_runtime.py",
            "--add-binary", "$(Join-Path $runtime '_tkinter.pyd');.",
            "--add-binary", "$(Join-Path $runtime 'tcl86t.dll');.",
            "--add-binary", "$(Join-Path $runtime 'tk86t.dll');.",
            "--add-data", "$tkinterLibrary;tkinter",
            "--add-data", "$tclData;_tcl_data",
            "--add-data", "$tkData;_tk_data"
        )
        $guiArguments += $entryPoint
        & $Python @guiArguments
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    }
    & $Python -m PyInstaller --noconfirm --clean --console --name "BAPPS-Sync-Service" --specpath $specRoot --paths "$agentRoot\src" --hidden-import win32timezone --hidden-import pymysql --hidden-import firebirdsql --hidden-import passlib.handlers.des_crypt --hidden-import pyodbc --hidden-import cryptography.hazmat.primitives.asymmetric.ed25519 "$agentRoot\src\bapps_sync_agent\service_main.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $portableGui = Join-Path $agentRoot "dist\BAPPS-Sync-Agent\BAPPS-Sync-Agent.exe"
    & $portableGui --portable-self-test
    if ($LASTEXITCODE -ne 0) {
        throw "El ejecutable portable no supero la prueba de arranque e importaciones."
    }
    Write-Host "Prueba portable superada: $portableGui"
    exit 0
} finally {
    Pop-Location
}
