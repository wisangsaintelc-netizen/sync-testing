# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['C:\\Sync\\Valery\\bapps-sync\\agent\\src\\bapps_sync_agent\\service_main.py'],
    pathex=['C:\\Sync\\Valery\\bapps-sync\\agent\\src'],
    binaries=[],
    datas=[],
    hiddenimports=['win32timezone', 'pymysql', 'firebirdsql', 'passlib.handlers.des_crypt', 'pyodbc', 'cryptography.hazmat.primitives.asymmetric.ed25519'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BAPPS-Sync-Service',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='BAPPS-Sync-Service',
)
