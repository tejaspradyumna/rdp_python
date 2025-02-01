[Setup]
AppName=Office Monitor
AppVersion=1.0
DefaultDirName={pf}\OfficeMonitor
PrivilegesRequired=admin
OutputDir=Output
OutputBaseFilename=OfficeMonitorSetup

[Files]
; Replace "your_script.exe" with your actual PyInstaller-generated .exe
Source: "dist\your_script.exe"; DestDir: "{app}"; Flags: ignoreversion

[Run]
; Add firewall rules
Filename: "netsh.exe"; \
    Parameters: "advfirewall firewall add rule name=""OfficeMonitor"" dir=out action=allow program=""{app}\your_script.exe"" enable=yes"; \
    Flags: runhidden; \
    StatusMsg: "Configuring firewall rules..."
Filename: "netsh.exe"; \
    Parameters: "advfirewall firewall add rule name=""OfficeMonitor"" dir=in action=allow program=""{app}\your_script.exe"" enable=yes"; \
    Flags: runhidden; \
    StatusMsg: "Configuring firewall rules..."

; Create a scheduled task to run the app as SYSTEM on user login
Filename: "schtasks.exe"; \
    Parameters: "/Create /F /TN ""OfficeMonitor"" /SC ONLOGON /RL HIGHEST /TR ""'{app}\your_script.exe'"" /RU ""SYSTEM"""; \
    Flags: runhidden; \
    StatusMsg: "Creating scheduled task..."

[UninstallRun]
; Remove firewall rules
Filename: "netsh.exe"; \
    Parameters: "advfirewall firewall delete rule name=""OfficeMonitor"""; \
    Flags: runhidden

; Delete the scheduled task
Filename: "schtasks.exe"; \
    Parameters: "/Delete /TN ""OfficeMonitor"" /F"; \
    Flags: runhidden
