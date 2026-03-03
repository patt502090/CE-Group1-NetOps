# 🏢 Samba4 Active Directory Domain Controller

|                     |                                        |
| ------------------- | -------------------------------------- |
| **IP**              | `10.1.10.20/24`                        |
| **Hostname**        | `raspberrypi`                          |
| **FQDN**           | `raspberrypi.group1.corp`              |
| **Host**            | Raspberry Pi 4 (aarch64)               |
| **OS**              | Debian 13 (trixie)                     |
| **Kernel**          | 6.12.47+rpt-rpi-v8                     |
| **Domain**          | `GROUP1.CORP`                          |
| **NetBIOS**         | `RASPBERRYPI`                          |
| **Server Role**     | Active Directory Domain Controller     |
| **Forest Level**    | Windows 2008 R2                        |
| **Domain Level**    | Windows 2008 R2                        |
| **Service**         | `samba-ad-dc.service` (systemd)        |
| **Tailscale**       | `100.84.145.105`                       |

## Overview

Samba4 AD DC ทำหน้าที่เป็น:

1. **Domain Controller** — จัดการ user/group/computer accounts
2. **Integrated DNS Server** — DNS สำหรับ domain GROUP1.CORP (forwarder: 8.8.8.8)
3. **NTLM Backend** — ให้ FreeRADIUS (.10) ใช้ `ntlm_auth` สำหรับ 802.1X authentication
4. **LDAP Server** — สำหรับ FreeRADIUS ldap module และ Cisco FTD Identity Policy
5. **Kerberos KDC** — Kerberos authentication สำหรับ domain members

> **Note:** Deploy แบบ native (systemd) บน Raspberry Pi โดยตรง — ไม่ใช้ Docker

## Listening Ports

| Port  | Protocol | Service          |
| ----- | -------- | ---------------- |
| 53    | TCP/UDP  | DNS              |
| 88    | TCP/UDP  | Kerberos         |
| 135   | TCP      | RPC Endpoint     |
| 389   | TCP/UDP  | LDAP             |
| 445   | TCP      | SMB              |
| 636   | TCP      | LDAPS            |
| 3268  | TCP      | Global Catalog   |

## Domain Users (21 accounts)

| Account          | Type    | Purpose                            |
| ---------------- | ------- | ---------------------------------- |
| `Administrator`  | Admin   | Domain admin                       |
| `radius_svc`     | Service | FreeRADIUS — ntlm_auth / LDAP bind |
| `krbtgt`         | System  | Kerberos TGT (auto-created)        |
| `Guest`          | System  | Disabled guest account             |
| `user_test1`     | Test    | ทดสอบ authentication               |
| `poramet.k`      | User    | —                                  |
| `farik.b`        | User    | —                                  |
| `winnie.p`       | User    | —                                  |
| `saranyapong.a`  | User    | —                                  |
| `michael.t`      | User    | —                                  |
| `david.l`        | User    | —                                  |
| `anong.r`        | User    | —                                  |
| `pattarapong.m`  | User    | —                                  |
| `andrew.c`       | User    | —                                  |
| `phodcharaphon.s`| User    | —                                  |
| `siriporn.w`     | User    | —                                  |
| `suwijak.c`      | User    | —                                  |
| `robert.j`       | User    | —                                  |
| `nathan.k`       | User    | —                                  |
| `kanchana.p`     | User    | —                                  |
| `somchai.x`      | User    | —                                  |

## Custom Groups

| Group    | Purpose                    |
| -------- | -------------------------- |
| `Staff`  | พนักงาน / Staff VLAN 30    |
| `IT`     | ทีม IT                     |
| `HR`     | ทีม HR                     |
| `Finance`| ทีม Finance                |

> **Note:** ยังไม่มี custom OUs — users ทั้งหมดอยู่ใน default container `CN=Users,DC=group1,DC=corp`  
> มีเฉพาะ `OU=Domain Controllers` ที่เป็น default ของ Samba4

## Service Management

```bash
# ดูสถานะ
sudo systemctl status samba-ad-dc

# Restart
sudo systemctl restart samba-ad-dc

# ดู logs
sudo journalctl -u samba-ad-dc -f
```

## Domain Administration

```bash
# ดู domain level
sudo samba-tool domain level show

# ลิสต์ users / groups
sudo samba-tool user list
sudo samba-tool group list
sudo samba-tool ou list

# สร้าง user
sudo samba-tool user create USERNAME 'P@ssw0rd123' \
    --given-name="First" --surname="Last"

# เพิ่ม user เข้า group
sudo samba-tool group addmembers Staff USERNAME

# สร้าง OU (ถ้าต้องการ)
sudo samba-tool ou create 'OU=Staff,DC=group1,DC=corp'

# Reset password
sudo samba-tool user setpassword USERNAME --newpassword='NewP@ss123'

# DNS management
sudo samba-tool dns zonelist localhost -U Administrator
```

## Integration with FreeRADIUS (.10)

FreeRADIUS ใช้ 2 ช่องทางในการเชื่อมต่อ AD:

### 1. ntlm_auth (MSCHAPv2 Authentication)

```bash
# ทดสอบ ntlm_auth (รันบน .10)
ntlm_auth --request-nt-key \
    --domain=GROUP1 \
    --username=testuser \
    --password=P@ssw0rd123
```

FreeRADIUS mschap module เรียก ntlm_auth ผ่าน winbind pipe:
```
ntlm_auth = "/usr/bin/ntlm_auth --request-nt-key --domain=GROUP1 \
    --username=%{%{Stripped-User-Name}:-%{%{User-Name}:-None}} \
    --challenge=%{%{mschap:Challenge}:-00} \
    --nt-response=%{%{mschap:NT-Response}:-00}"
```

### 2. LDAP (User Lookup / Authorization)

FreeRADIUS inner-tunnel ใช้ ldap module ค้นหา user ก่อน authenticate:
- **LDAP Server:** `10.1.10.20` port 389
- **Bind Account:** `radius_svc`
- **Base DN:** `DC=group1,DC=corp`

## Key Configuration

### smb.conf Highlights

| Setting | Value | Note |
| ------- | ----- | ---- |
| `ntlm auth` | `yes` | อนุญาต NTLMv1+v2 (สำหรับ FreeRADIUS) |
| `ldap server require strong auth` | `no` | อนุญาต simple LDAP bind (ไม่ต้อง LDAPS) |
| `dns forwarder` | `8.8.8.8` | Forward non-local DNS queries |
| `idmap_ldb:use rfc2307` | `yes` | UID/GID mapping via RFC2307 |
| `log level` | `3` | Verbose logging (syslog) |

### Kerberos (/etc/krb5.conf)

```ini
[libdefaults]
    default_realm = GROUP1.CORP
    dns_lookup_realm = false
    dns_lookup_kdc = true

[realms]
GROUP1.CORP = {
    default_domain = group1.corp
}

[domain_realm]
    raspberrypi = GROUP1.CORP
```

### NSSwitch (/etc/nsswitch.conf)

```
passwd:  files winbind systemd
group:   files winbind systemd
```

## Process Tree

เมื่อ `samba-ad-dc.service` ทำงาน จะ spawn child processes ทั้งหมด:

```
samba: root process
├── task[s3fs]      — SMB file server
├── task[rpc]       — RPC services (4 workers)
├── task[nbt]       — NetBIOS
├── task[wrepl]     — WINS replication
├── task[ldap]      — LDAP server (4 workers)
├── task[cldap]     — Connectionless LDAP
├── task[kdc]       — Kerberos KDC (4 workers)
├── task[drepl]     — Directory replication
├── task[winbindd]  — Winbind daemon (built-in)
├── task[ntp_signd] — NTP signing
├── task[kcc]       — Knowledge Consistency Checker
├── task[dnsupdate] — Dynamic DNS updates
├── task[dns]       — DNS server
├── smbd            — SMB daemon
└── winbindd        — Winbind daemon + domain child [GROUP1]
```

> **Note:** `winbind.service` (standalone) ไม่จำเป็นต้องเปิด — winbindd รันเป็น child ของ samba-ad-dc อยู่แล้ว

## Integration with Cisco FTD (Identity Policy)

FTD ใช้ Samba4 AD เป็น Identity Source สำหรับ Captive Portal บน VLAN 20:

| Setting | Value |
| ------- | ----- |
| **Identity Source Name** | `Samba_AD` |
| **Protocol** | LDAP (port 389) |
| **Rule** | `Employee-LAN-Captive-Port` |
| **Auth Type** | HTTP Basic (Active Auth) |
| **Source** | `employee_zone` / `Employee-LAN` (VLAN 20) |
| **Certificate** | `Captive-Portal-Cert:885` |
| **Fallback** | Failed Authentication (ไม่เป็น Guest) |
| **Default Action** | Passive Auth |

**Flow:** User บน VLAN 20 เปิด browser → FTD redirect ไป captive portal → HTTP Basic prompt → FTD query Samba_AD ผ่าน LDAP → match user → map IP↔identity 24 ชม.

## � Monitoring — Wazuh Agent

ติดตั้ง Wazuh Agent บน .20 เพื่อส่ง Samba AD authentication logs ไป Wazuh Dashboard:

```bash
# Install Wazuh Agent
sudo apt install wazuh-agent

# Configure
sudo nano /var/ossec/etc/ossec.conf
# Set <address>WAZUH_MANAGER_IP</address>

sudo systemctl enable --now wazuh-agent
```

Wazuh มี built-in decoders สำหรับ Samba — จะ parse authentication events ได้โดยอัตโนมัติ  
เพิ่ม syslog monitoring ใน ossec.conf:

```xml
<localfile>
  <log_format>syslog</log_format>
  <location>/var/log/syslog</location>
</localfile>
```

**สิ่งที่ Wazuh จะเห็นจาก Samba AD:**
- ✅ AD authentication events (success/fail)
- ✅ LDAP bind events (จาก FreeRADIUS, FTD)
- ✅ Kerberos ticket events
- ✅ Password changes
- ✅ Account lockouts
- ✅ Brute force alerts (Wazuh active response)

## �🔧 Recommended: LDAP Account Manager (LAM)

Web UI สำหรับจัดการ users / groups ใน Samba4 AD แทนการใช้ CLI ทุกครั้ง

```bash
# ติดตั้งบน .20 (raspberrypi)
sudo apt install ldap-account-manager

# เปิด browser
# http://10.1.10.20/lam
```

**LAM Configuration:**

| Setting | Value |
| ------- | ----- |
| LDAP Server | `ldap://localhost` |
| Base DN | `DC=group1,DC=corp` |
| Admin DN | `CN=Administrator,CN=Users,DC=group1,DC=corp` |
| Account types | posixAccount, sambaAccount, etc. |

**ทำอะไรได้:**
- ✅ สร้าง / ลบ / แก้ไข user ผ่าน web
- ✅ Reset password
- ✅ จัดการ group membership (Staff, IT, HR, Finance)
- ✅ ดู account status (enabled/disabled/locked)
- ✅ Bulk import users (CSV)

## Files

```
active-directory/
├── README.md
├── docker-compose.yml         # ⚠️ Reference only — ไม่ได้ใช้งาน (native install)
└── config/
    └── smb.conf               # Real /etc/samba/smb.conf
```
