from __future__ import annotations

import os
from pathlib import Path


class StatePermissionsError(RuntimeError):
    """The Windows ACL of the shared agent state could not be repaired."""


def repair_state_permissions(root: Path) -> None:
    """Give only SYSTEM and local Administrators full access to the shared state.

    This is deliberately implemented through the Windows security API instead
    of shelling out to ``icacls``. It can replace an inherited explicit deny
    entry left by an older technical installation, including on existing files.
    The caller must be elevated.
    """
    if os.name != "nt":
        raise StatePermissionsError("La reparacion de permisos requiere Windows.")

    try:
        import ntsecuritycon
        import win32api
        import win32con
        import win32security
    except ImportError as exc:  # pragma: no cover - only possible in a broken portable build
        raise StatePermissionsError("No se pudo cargar la seguridad de Windows requerida.") from exc

    root.mkdir(parents=True, exist_ok=True)
    _enable_windows_privileges(win32api, win32con, win32security)

    try:
        administrators = win32security.CreateWellKnownSid(win32security.WinBuiltinAdministratorsSid, None)
        local_system = win32security.CreateWellKnownSid(win32security.WinLocalSystemSid, None)
        _set_acl(root, True, administrators, local_system, ntsecuritycon, win32security)

        for parent, directories, files in os.walk(root):
            parent_path = Path(parent)
            for directory in directories:
                _set_acl(parent_path / directory, True, administrators, local_system, ntsecuritycon, win32security)
            for file_name in files:
                _set_acl(parent_path / file_name, False, administrators, local_system, ntsecuritycon, win32security)
    except Exception as exc:
        raise StatePermissionsError(f"No se pudieron reparar los permisos de {root}: {exc}") from exc


def _enable_windows_privileges(win32api: object, win32con: object, win32security: object) -> None:
    token = win32security.OpenProcessToken(
        win32api.GetCurrentProcess(),
        win32con.TOKEN_ADJUST_PRIVILEGES | win32con.TOKEN_QUERY,
    )
    privileges = []
    for name in ("SeTakeOwnershipPrivilege", "SeRestorePrivilege"):
        luid = win32security.LookupPrivilegeValue(None, name)
        privileges.append((luid, win32con.SE_PRIVILEGE_ENABLED))
    win32security.AdjustTokenPrivileges(token, False, privileges)


def _set_acl(
    path: Path,
    is_directory: bool,
    administrators: object,
    local_system: object,
    ntsecuritycon: object,
    win32security: object,
) -> None:
    inheritance = 0
    if is_directory:
        inheritance = win32security.OBJECT_INHERIT_ACE | win32security.CONTAINER_INHERIT_ACE

    dacl = win32security.ACL()
    dacl.AddAccessAllowedAceEx(win32security.ACL_REVISION, inheritance, ntsecuritycon.FILE_ALL_ACCESS, local_system)
    dacl.AddAccessAllowedAceEx(win32security.ACL_REVISION, inheritance, ntsecuritycon.FILE_ALL_ACCESS, administrators)
    security_information = (
        win32security.OWNER_SECURITY_INFORMATION
        | win32security.DACL_SECURITY_INFORMATION
        | win32security.PROTECTED_DACL_SECURITY_INFORMATION
    )
    win32security.SetNamedSecurityInfo(
        str(path),
        win32security.SE_FILE_OBJECT,
        security_information,
        administrators,
        None,
        dacl,
        None,
    )
