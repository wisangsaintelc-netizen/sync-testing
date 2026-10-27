Unicode true
RequestExecutionLevel admin

!include "MUI2.nsh"
!include "x64.nsh"

!ifndef APP_VERSION
  !define APP_VERSION "0.7.10"
!endif

!define APP_NAME "BAPPS Sync Agent"
!define SERVICE_NAME "BAPPSyncAgent"
!define COMPANY_NAME "BAPPS"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"

Name "${APP_NAME} ${APP_VERSION}"
OutFile "..\release\BAPPS-Sync-Setup-${APP_VERSION}.exe"
InstallDir "$PROGRAMFILES\${APP_NAME}"
InstallDirRegKey HKLM "Software\${COMPANY_NAME}\${APP_NAME}" "InstallPath"
ShowInstDetails show
ShowUninstDetails show

!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_LANGUAGE "Spanish"

Function .onInit
  ${If} ${RunningX64}
    StrCpy $INSTDIR "$PROGRAMFILES64\${APP_NAME}"
  ${EndIf}
FunctionEnd

Section "${APP_NAME}" SEC_MAIN
  Call StopExistingService

  SetOutPath "$INSTDIR"
  File /r "..\dist\BAPPS-Sync-Agent\*.*"

  SetOutPath "$INSTDIR\service"
  File /r "..\dist\BAPPS-Sync-Service\*.*"

  !ifdef TRUST_BUNDLE
    SetOutPath "$INSTDIR"
    File "/oname=config-signing-trust.json" "${TRUST_BUNDLE}"
  !endif

  WriteRegStr HKLM "Software\${COMPANY_NAME}\${APP_NAME}" "InstallPath" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "Publisher" "${COMPANY_NAME}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\BAPPS-Sync-Agent.exe"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair" 1
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\BAPPS Sync Agent.lnk" "$INSTDIR\BAPPS-Sync-Agent.exe"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Desinstalar.lnk" "$INSTDIR\Uninstall.exe"

  Call RepairStatePermissions
  Call InstallSigningTrust
  Call PrepareAndStartService
SectionEnd

Function StopExistingService
  IfFileExists "$INSTDIR\service\BAPPS-Sync-Service.exe" 0 done
  DetailPrint "Deteniendo el servicio existente..."
  nsExec::ExecToStack '"$INSTDIR\service\BAPPS-Sync-Service.exe" --wait 30 stop'
  Pop $0
  ${If} $0 != "0"
    DetailPrint "El servicio existente ya estaba detenido o no respondio al stop; se continuara con la actualizacion."
  ${EndIf}
  ; El host congelado no siempre aparece en el filtro SERVICES de taskkill.
  ; Se termina solo su ejecutable exacto para liberar las DLL de PyInstaller.
  nsExec::ExecToStack '"$SYSDIR\taskkill.exe" /F /T /IM "BAPPS-Sync-Service.exe"'
  Pop $0
  Sleep 2000
done:
FunctionEnd

Function RepairStatePermissions
  DetailPrint "Verificando permisos seguros del estado del agente..."
  nsExec::ExecToStack '"$INSTDIR\BAPPS-Sync-Agent.exe" --repair-state-permissions'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_ICONSTOP|MB_OK "No se pudieron reparar los permisos seguros del estado del agente. No se instalara el servicio."
    Abort
  ${EndIf}
FunctionEnd

Function InstallSigningTrust
  IfFileExists "$INSTDIR\config-signing-trust.json" 0 done
  DetailPrint "Instalando la clave publica de confianza del Centro..."
  nsExec::ExecToStack '"$INSTDIR\BAPPS-Sync-Agent.exe" --install-signing-trust "$INSTDIR\config-signing-trust.json"'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_ICONSTOP|MB_OK "No se pudo instalar la confianza de firma. El servicio no se actualizara."
    Abort
  ${EndIf}
  Delete "$INSTDIR\config-signing-trust.json"
done:
FunctionEnd

Function PrepareAndStartService
  DetailPrint "Comprobando la identidad para el servicio..."
  nsExec::ExecToStack '"$INSTDIR\BAPPS-Sync-Agent.exe" --prepare-service'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_ICONEXCLAMATION|MB_OK "El agente se instalo, pero aun no esta enrolado o no se pudieron preparar sus credenciales. Abra BAPPS Sync Agent, complete la configuracion y ejecute de nuevo este instalador para activar el servicio."
    Return
  ${EndIf}

  DetailPrint "Registrando el servicio BAPPS Sync Agent..."
  nsExec::ExecToStack '"$INSTDIR\service\BAPPS-Sync-Service.exe" --startup auto install'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_ICONSTOP|MB_OK "No se pudo registrar el servicio. La aplicacion quedo instalada; revise el registro de eventos de Windows antes de reintentar."
    Return
  ${EndIf}

  DetailPrint "Iniciando el servicio..."
  nsExec::ExecToStack '"$INSTDIR\service\BAPPS-Sync-Service.exe" --wait 30 start'
  Pop $0
  ${If} $0 != "0"
    MessageBox MB_ICONSTOP|MB_OK "El servicio fue registrado pero no inicio correctamente. La aplicacion quedo instalada; revise el registro de eventos de Windows antes de reintentar."
    Return
  ${EndIf}
  DetailPrint "Servicio instalado e iniciado correctamente."
FunctionEnd

Section "Uninstall"
  IfFileExists "$INSTDIR\service\BAPPS-Sync-Service.exe" 0 +4
    nsExec::ExecToStack '"$INSTDIR\service\BAPPS-Sync-Service.exe" stop'
    Pop $0
    nsExec::ExecToStack '"$INSTDIR\service\BAPPS-Sync-Service.exe" remove'
    Pop $0

  Delete "$SMPROGRAMS\${APP_NAME}\BAPPS Sync Agent.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Desinstalar.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  DeleteRegKey HKLM "Software\${COMPANY_NAME}\${APP_NAME}"
  DeleteRegKey HKLM "${UNINSTALL_KEY}"
  RMDir /r "$INSTDIR"
SectionEnd
