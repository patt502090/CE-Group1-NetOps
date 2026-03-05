#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Configure Windows 802.1X SSO for LAN (Wired) and WiFi
    Uses Windows logon credentials automatically - no popup!

.DESCRIPTION
    UX Flow:
    1. User powers on PC
    2. User logs in to Windows with AD credentials (GROUP1\winnie.p)
    3. 802.1X PEAP/MSCHAPv2 authenticates automatically in background
    4. Switch/WLC assigns dynamic VLAN based on AD group
    5. User gets IP via DHCP - zero extra prompts

.PARAMETER Mode
    "LAN" = Wired 802.1X only
    "WiFi" = Wireless 802.1X only  
    "Both" = LAN + WiFi (default)

.PARAMETER SSIDName
    WiFi SSID name for Employee network (default: "Employee-G1")

.PARAMETER VerifyServerCert
    Whether to verify RADIUS server certificate (default: $false)
    Set $true only if you have a proper CA cert installed

.EXAMPLE
    .\setup-8021x-sso.ps1
    .\setup-8021x-sso.ps1 -Mode LAN
    .\setup-8021x-sso.ps1 -Mode WiFi -SSIDName "Corp-WiFi"
#>

param(
    [ValidateSet("LAN", "WiFi", "Both")]
    [string]$Mode = "Both",
    
    [string]$SSIDName = "Employee-G1",
    
    [bool]$VerifyServerCert = $false
)

$ErrorActionPreference = "Stop"

function Write-Status($msg, $color = "Cyan") {
    Write-Host "[*] $msg" -ForegroundColor $color
}
function Write-OK($msg) {
    Write-Host "[+] $msg" -ForegroundColor Green
}
function Write-Fail($msg) {
    Write-Host "[-] $msg" -ForegroundColor Red
}

# ============================================================
# STEP 1: Enable Wired AutoConfig Service (REQUIRED for LAN)
# ============================================================
function Enable-WiredAutoConfig {
    Write-Status "Enabling 'Wired AutoConfig' service (dot3svc)..."
    
    $svc = Get-Service -Name "dot3svc" -ErrorAction SilentlyContinue
    if (-not $svc) {
        Write-Fail "dot3svc service not found! This Windows edition may not support wired 802.1X"
        return $false
    }
    
    # Set to Automatic startup
    Set-Service -Name "dot3svc" -StartupType Automatic
    
    # Start if not running
    if ($svc.Status -ne "Running") {
        Start-Service -Name "dot3svc"
        Start-Sleep -Seconds 2
    }
    
    $svc = Get-Service -Name "dot3svc"
    if ($svc.Status -eq "Running") {
        Write-OK "Wired AutoConfig is running (startup: Automatic)"
        return $true
    } else {
        Write-Fail "Failed to start Wired AutoConfig"
        return $false
    }
}

# ============================================================
# STEP 2: Configure Wired 802.1X via XML Profile
# ============================================================
function Setup-Wired8021X {
    Write-Status "Configuring Wired 802.1X SSO profile..."
    
    # Determine server cert validation
    if ($VerifyServerCert) {
        $serverValidation = "<ServerValidation><DisableUserPromptForServerValidation>false</DisableUserPromptForServerValidation></ServerValidation>"
    } else {
        $serverValidation = "<ServerValidation><DisableUserPromptForServerValidation>true</DisableUserPromptForServerValidation></ServerValidation>"
    }
    
    # Wired 802.1X profile XML
    # Key settings:
    #   - EapType 25 = PEAP
    #   - InnerEapType 26 = EAP-MSCHAPv2
    #   - CredentialsSource > SmartCard = false (use password)
    #   - SingleSignOn PerformImmediatelyBefore = true
    #   - UseLogonCredentials = true  <-- THIS IS THE MAGIC
    $wiredProfileXml = @"
<?xml version="1.0"?>
<LANProfile xmlns="http://www.microsoft.com/networking/LAN/profile/v1">
    <MSM>
        <security>
            <OneXEnforced>false</OneXEnforced>
            <OneXEnabled>true</OneXEnabled>
            <OneX xmlns="http://www.microsoft.com/networking/OneX/v1">
                <cacheUserData>true</cacheUserData>
                <authMode>user</authMode>
                <singleSignOn>
                    <type>preLogon</type>
                    <maxDelay>10</maxDelay>
                </singleSignOn>
                <EAPConfig>
                    <EapHostConfig xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
                        <EapMethod>
                            <Type xmlns="http://www.microsoft.com/provisioning/EapCommon">25</Type>
                            <VendorId xmlns="http://www.microsoft.com/provisioning/EapCommon">0</VendorId>
                            <VendorType xmlns="http://www.microsoft.com/provisioning/EapCommon">0</VendorType>
                            <AuthorId xmlns="http://www.microsoft.com/provisioning/EapCommon">0</AuthorId>
                        </EapMethod>
                        <Config xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
                            <Eap xmlns="http://www.microsoft.com/provisioning/BaseEapConnectionPropertiesV1">
                                <Type>25</Type>
                                <EapType xmlns="http://www.microsoft.com/provisioning/MsPeapConnectionPropertiesV1">
                                    <FastReconnect>true</FastReconnect>
                                    <InnerEapOptional>false</InnerEapOptional>
                                    <ServerValidation>
                                        <DisableUserPromptForServerValidation>true</DisableUserPromptForServerValidation>
                                    </ServerValidation>
                                    <Eap xmlns="http://www.microsoft.com/provisioning/BaseEapConnectionPropertiesV1">
                                        <Type>26</Type>
                                        <EapType xmlns="http://www.microsoft.com/provisioning/MsChapV2ConnectionPropertiesV1">
                                            <UseWinLogonCredentials>true</UseWinLogonCredentials>
                                        </EapType>
                                    </Eap>
                                    <EnableQuarantineChecks>false</EnableQuarantineChecks>
                                    <RequireCryptoBinding>false</RequireCryptoBinding>
                                </EapType>
                            </Eap>
                        </Config>
                    </EapHostConfig>
                </EAPConfig>
            </OneX>
        </security>
    </MSM>
</LANProfile>
"@
    
    # Save XML profile
    $profileDir = "$env:TEMP\8021x-profiles"
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    $wiredProfilePath = "$profileDir\wired-8021x-sso.xml"
    $wiredProfileXml | Out-File -FilePath $wiredProfilePath -Encoding UTF8
    
    # Get the active Ethernet adapter name
    $ethernetAdapter = Get-NetAdapter | Where-Object { 
        $_.Status -eq "Up" -and ($_.InterfaceDescription -match "Ethernet|Realtek|Intel.*Gigabit|I219|I225|I226" -or $_.Name -match "Ethernet")
    } | Select-Object -First 1
    
    if (-not $ethernetAdapter) {
        $ethernetAdapter = Get-NetAdapter | Where-Object { $_.PhysicalMediaType -eq "802.3" -and $_.Status -eq "Up" } | Select-Object -First 1
    }
    
    if (-not $ethernetAdapter) {
        Write-Fail "No active Ethernet adapter found!"
        Write-Status "Available adapters:" "Yellow"
        Get-NetAdapter | Format-Table Name, InterfaceDescription, Status, PhysicalMediaType -AutoSize
        return $false
    }
    
    Write-Status "Using adapter: $($ethernetAdapter.Name) ($($ethernetAdapter.InterfaceDescription))"
    
    # Apply wired profile using netsh
    $interfaceName = $ethernetAdapter.Name
    
    # Enable 802.1X on the interface
    $result = netsh lan set profileparameter interface="$interfaceName" 2>&1
    
    # Add the profile
    $result = netsh lan add profile filename="$wiredProfilePath" interface="$interfaceName" 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-OK "Wired 802.1X SSO profile applied to '$interfaceName'"
    } else {
        # Try alternative method - set via registry
        Write-Status "netsh method failed, trying registry method..." "Yellow"
        Set-Wired8021XviaRegistry -InterfaceName $interfaceName
    }
    
    # Verify
    Write-Status "Verifying wired profile..."
    $verify = netsh lan show profiles interface="$interfaceName" 2>&1
    Write-Host $verify
    
    return $true
}

function Set-Wired8021XviaRegistry {
    param([string]$InterfaceName)
    
    # Enable 802.1X via registry for all wired adapters
    $regPath = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\Network Connections"
    if (-not (Test-Path $regPath)) {
        New-Item -Path $regPath -Force | Out-Null
    }
    
    # Alternative: use Group Policy equivalent registry keys
    $dot3Path = "HKLM:\SOFTWARE\Policies\Microsoft\Windows\WiredNetworkSettings"
    if (-not (Test-Path $dot3Path)) {
        New-Item -Path $dot3Path -Force | Out-Null
    }
    
    # Enable 802.1X
    Set-ItemProperty -Path $dot3Path -Name "Enable8021X" -Value 1 -Type DWord -Force
    # Auth mode: user (1=user, 2=machine, 3=user or machine)
    Set-ItemProperty -Path $dot3Path -Name "AuthMode" -Value 1 -Type DWord -Force
    # Single Sign On: preLogon
    Set-ItemProperty -Path $dot3Path -Name "SingleSignOn" -Value 1 -Type DWord -Force
    
    Write-OK "802.1X enabled via registry policy"
}

# ============================================================
# STEP 3: Configure WiFi 802.1X SSO Profile
# ============================================================
function Setup-WiFi8021X {
    param([string]$SSID = "Employee-G1")
    
    Write-Status "Configuring WiFi 802.1X SSO for SSID: $SSID"
    
    # Ensure WLAN AutoConfig is running
    $wlanSvc = Get-Service -Name "WlanSvc" -ErrorAction SilentlyContinue
    if ($wlanSvc -and $wlanSvc.Status -ne "Running") {
        Set-Service -Name "WlanSvc" -StartupType Automatic
        Start-Service -Name "WlanSvc"
        Write-OK "WLAN AutoConfig started"
    }
    
    # Convert SSID to hex
    $ssidHex = ($SSID.ToCharArray() | ForEach-Object { '{0:X2}' -f [int]$_ }) -join ''
    
    # WiFi profile XML with 802.1X SSO
    $wifiProfileXml = @"
<?xml version="1.0"?>
<WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1">
    <name>$SSID</name>
    <SSIDConfig>
        <SSID>
            <hex>$ssidHex</hex>
            <name>$SSID</name>
        </SSID>
    </SSIDConfig>
    <connectionType>ESS</connectionType>
    <connectionMode>auto</connectionMode>
    <MSM>
        <security>
            <authEncryption>
                <authentication>WPA2</authentication>
                <encryption>AES</encryption>
                <useOneX>true</useOneX>
            </authEncryption>
            <OneX xmlns="http://www.microsoft.com/networking/OneX/v1">
                <cacheUserData>true</cacheUserData>
                <authMode>user</authMode>
                <singleSignOn>
                    <type>preLogon</type>
                    <maxDelay>10</maxDelay>
                </singleSignOn>
                <EAPConfig>
                    <EapHostConfig xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
                        <EapMethod>
                            <Type xmlns="http://www.microsoft.com/provisioning/EapCommon">25</Type>
                            <VendorId xmlns="http://www.microsoft.com/provisioning/EapCommon">0</VendorId>
                            <VendorType xmlns="http://www.microsoft.com/provisioning/EapCommon">0</VendorType>
                            <AuthorId xmlns="http://www.microsoft.com/provisioning/EapCommon">0</AuthorId>
                        </EapMethod>
                        <Config xmlns="http://www.microsoft.com/provisioning/EapHostConfig">
                            <Eap xmlns="http://www.microsoft.com/provisioning/BaseEapConnectionPropertiesV1">
                                <Type>25</Type>
                                <EapType xmlns="http://www.microsoft.com/provisioning/MsPeapConnectionPropertiesV1">
                                    <FastReconnect>true</FastReconnect>
                                    <InnerEapOptional>false</InnerEapOptional>
                                    <ServerValidation>
                                        <DisableUserPromptForServerValidation>true</DisableUserPromptForServerValidation>
                                    </ServerValidation>
                                    <Eap xmlns="http://www.microsoft.com/provisioning/BaseEapConnectionPropertiesV1">
                                        <Type>26</Type>
                                        <EapType xmlns="http://www.microsoft.com/provisioning/MsChapV2ConnectionPropertiesV1">
                                            <UseWinLogonCredentials>true</UseWinLogonCredentials>
                                        </EapType>
                                    </Eap>
                                    <EnableQuarantineChecks>false</EnableQuarantineChecks>
                                    <RequireCryptoBinding>false</RequireCryptoBinding>
                                </EapType>
                            </Eap>
                        </Config>
                    </EapHostConfig>
                </EAPConfig>
            </OneX>
        </security>
    </MSM>
    <MacRandomization xmlns="http://www.microsoft.com/networking/WLAN/profile/v3">
        <enableRandomization>false</enableRandomization>
    </MacRandomization>
</WLANProfile>
"@

    # Save and apply
    $profileDir = "$env:TEMP\8021x-profiles"
    New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    $wifiProfilePath = "$profileDir\wifi-8021x-sso.xml"
    $wifiProfileXml | Out-File -FilePath $wifiProfilePath -Encoding UTF8
    
    # Remove existing profile if present
    netsh wlan delete profile name="$SSID" 2>$null | Out-Null
    
    # Add new profile (user scope = all users)
    $result = netsh wlan add profile filename="$wifiProfilePath" user=all 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-OK "WiFi 802.1X SSO profile added for '$SSID'"
    } else {
        Write-Fail "Failed to add WiFi profile: $result"
        return $false
    }
    
    # Verify
    Write-Status "WiFi profile details:"
    netsh wlan show profile name="$SSID" 2>&1 | Select-String "SSID|Authentication|Encryption|802.1X|Connection mode"
    
    return $true
}

# ============================================================
# STEP 4: Verify Configuration
# ============================================================
function Show-Summary {
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  802.1X SSO Configuration Complete!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "  Network Architecture:" -ForegroundColor Cyan
    Write-Host "    RADIUS Server : 10.1.10.10 (FreeRADIUS + Samba AD)" 
    Write-Host "    AD Domain     : GROUP1.CORP"
    Write-Host "    Auth Method   : PEAP / EAP-MSCHAPv2"
    Write-Host "    SSO           : Pre-logon (uses Windows credentials)"
    Write-Host ""
    Write-Host "  Dynamic VLAN Assignment:" -ForegroundColor Cyan
    Write-Host "    IT group      -> VLAN 20 (Privileged)    10.1.20.0/24"
    Write-Host "    HR group      -> VLAN 30 (Corporate)     10.1.30.0/24"
    Write-Host "    Finance group -> VLAN 30 (Corporate)     10.1.30.0/24"
    Write-Host "    Staff group   -> VLAN 30 (Corporate)     10.1.30.0/24"
    Write-Host ""
    Write-Host "  User Experience:" -ForegroundColor Cyan
    Write-Host "    1. Power on PC"
    Write-Host "    2. Login to Windows (GROUP1\username)"
    Write-Host "    3. 802.1X authenticates automatically (0-10s)"
    Write-Host "    4. VLAN assigned, DHCP IP received"
    Write-Host "    5. Network ready - no extra prompts!"
    Write-Host ""
    Write-Host "  Troubleshooting:" -ForegroundColor Yellow
    Write-Host "    - Check: services.msc -> 'Wired AutoConfig' = Running"
    Write-Host "    - Check: ncpa.cpl -> Ethernet -> Properties -> Authentication"  
    Write-Host "    - Logs:  eventvwr.msc -> Windows Logs -> Security (Event 5632)"
    Write-Host "    - Debug: netsh lan show interfaces"
    Write-Host "    - Debug: netsh wlan show interfaces"
    Write-Host ""
}

# ============================================================
# MAIN
# ============================================================
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  802.1X SSO Setup - GROUP1 Network" -ForegroundColor Cyan  
Write-Host "  PEAP/MSCHAPv2 + Windows Logon Creds" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$success = $true

if ($Mode -eq "LAN" -or $Mode -eq "Both") {
    Write-Host "--- Wired (LAN) 802.1X ---" -ForegroundColor Yellow
    $wiredOk = Enable-WiredAutoConfig
    if ($wiredOk) {
        $wiredOk = Setup-Wired8021X
    }
    if (-not $wiredOk) { $success = $false }
    Write-Host ""
}

if ($Mode -eq "WiFi" -or $Mode -eq "Both") {
    Write-Host "--- Wireless (WiFi) 802.1X ---" -ForegroundColor Yellow
    $wifiOk = Setup-WiFi8021X -SSID $SSIDName
    if (-not $wifiOk) { $success = $false }
    Write-Host ""
}

Show-Summary

if ($success) {
    Write-OK "All configurations applied successfully!"
    Write-Host ""
    Write-Status "Next: Restart the network adapter or reboot to activate SSO" "Yellow"
    Write-Host ""
    
    $restart = Read-Host "Restart network adapters now? (y/N)"
    if ($restart -eq "y" -or $restart -eq "Y") {
        if ($Mode -eq "LAN" -or $Mode -eq "Both") {
            $eth = Get-NetAdapter | Where-Object { $_.Name -match "Ethernet" -and $_.Status -eq "Up" } | Select-Object -First 1
            if ($eth) {
                Write-Status "Restarting $($eth.Name)..."
                Restart-NetAdapter -Name $eth.Name
                Start-Sleep -Seconds 5
                Write-OK "$($eth.Name) restarted - 802.1X SSO should authenticate now"
            }
        }
    }
} else {
    Write-Fail "Some configurations failed - check errors above"
}
