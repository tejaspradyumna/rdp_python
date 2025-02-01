[Setup]
AppName=Office Monitor
AppVersion=1.0
DefaultDirName={pf}\OfficeMonitor
PrivilegesRequired=admin
OutputDir=Output
OutputBaseFilename=OfficeMonitorSetup
; Add this to the previous Inno script
; This installs a Windows service that runs with SYSTEM privileges

[Files]
; Assuming your main executable is named OfficeMonitor.exe
Source: "OfficeMonitor.exe"; DestDir: "{app}"; Flags: ignoreversion

[Run]
; Add firewall rules during installation
Filename: "netsh.exe"; \
    Parameters: "advfirewall firewall add rule name=""OfficeMonitor"" dir=out action=allow program=""{app}\OfficeMonitor.exe"" enable=yes"; \
    Flags: runhidden; \
    StatusMsg: "Configuring firewall rules..."
Filename: "netsh.exe"; \
    Parameters: "advfirewall firewall add rule name=""OfficeMonitor"" dir=in action=allow program=""{app}\OfficeMonitor.exe"" enable=yes"; \
    Flags: runhidden; \
    StatusMsg: "Configuring firewall rules..."
; Install the service during setup
Filename: "sc.exe"; \
    Parameters: "create ""OfficeMonitorService"" binPath= ""{app}\OfficeMonitorService.exe"" start= auto"; \
    Flags: runhidden
; Start the service
Filename: "sc.exe"; \
    Parameters: "start ""OfficeMonitorService"""; \
    Flags: runhidden

[Registry]
; Add registry entry for auto-start
Root: HKLM; \
    Subkey: "SOFTWARE\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; \
    ValueName: "OfficeMonitor"; \
    ValueData: """{app}\OfficeMonitor.exe"""; \
    Flags: uninsdeletevalue

[UninstallRun]
; Remove firewall rules during uninstallation
Filename: "netsh.exe"; \
    Parameters: "advfirewall firewall delete rule name=""OfficeMonitor"""; \
    Flags: runhidden
