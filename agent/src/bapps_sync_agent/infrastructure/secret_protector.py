import base64
import ctypes
import os
from ctypes import wintypes


class SecretProtectionError(RuntimeError):
    pass


class _DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


class WindowsSecretProtector:
    """Protects local secrets with machine-scoped Windows DPAPI for the GUI and service."""

    _CRYPTPROTECT_UI_FORBIDDEN = 0x1
    _CRYPTPROTECT_LOCAL_MACHINE = 0x4

    def protect(self, value: str) -> str:
        if os.name != "nt":
            raise SecretProtectionError("Windows DPAPI is required to protect source credentials.")
        protected = self._crypt(value.encode("utf-8"), protect=True)
        return base64.b64encode(protected).decode("ascii")

    def unprotect(self, value: str) -> str:
        if os.name != "nt":
            raise SecretProtectionError("Windows DPAPI is required to read source credentials.")
        try:
            encrypted = base64.b64decode(value.encode("ascii"), validate=True)
        except ValueError as exc:
            raise SecretProtectionError("The stored source credential is invalid.") from exc
        return self._crypt(encrypted, protect=False).decode("utf-8")

    def _crypt(self, data: bytes, protect: bool) -> bytes:
        crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        input_blob, input_buffer = self._blob(data)
        output_blob = _DataBlob()

        if protect:
            result = crypt32.CryptProtectData(
                ctypes.byref(input_blob), None, None, None, None,
                self._CRYPTPROTECT_UI_FORBIDDEN | self._CRYPTPROTECT_LOCAL_MACHINE, ctypes.byref(output_blob),
            )
        else:
            result = crypt32.CryptUnprotectData(
                ctypes.byref(input_blob), None, None, None, None, self._CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(output_blob)
            )
        if not result:
            raise SecretProtectionError(ctypes.FormatError(ctypes.get_last_error()))
        try:
            return ctypes.string_at(output_blob.pbData, output_blob.cbData)
        finally:
            kernel32.LocalFree(output_blob.pbData)
            del input_buffer

    @staticmethod
    def _blob(data: bytes) -> tuple[_DataBlob, ctypes.Array[ctypes.c_char]]:
        buffer = ctypes.create_string_buffer(data)
        return _DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer
