# 🔐 FreeRADIUS 3.2.7 — 802.1X Authentication Server

|                     |                                             |
| ------------------- | ------------------------------------------- |
| **IP**              | `10.1.10.10/8` ⚠️ (ควรเป็น `/24`)           |
| **Hostname**        | `rasberrypi-888`                            |
| **Host**            | Raspberry Pi 4 (aarch64)                    |
| **OS**              | Debian 13 (trixie)                          |
| **Kernel**          | 6.12.47+rpt-rpi-v8                          |
| **FreeRADIUS**      | 3.2.7                                       |
| **Config Path**     | `/etc/freeradius/3.0/`                      |
| **Ports**           | 1812/UDP (Auth), 1813/UDP (Acct)            |
| **Service**         | `freeradius.service` (systemd)              |
| **Current Mode**    | ⚠️ Debug mode (`sudo freeradius -X`)         |
| **ntlm_auth**       | `/usr/bin/ntlm_auth` v4.22.6               |
| **Tailscale**       | `100.92.40.11`                              |

## Overview

FreeRADIUS ทำหน้าที่เป็น Authentication Server สำหรับ:

- **VLAN 30 (STAFF-WIFI):** 802.1X EAP-PEAP/MSCHAPv2 — authenticate ผ่าน Samba4 AD
- **Wired 802.1X:** ผ่าน L2/L3 Switch (ถ้าเปิดใช้งาน)
- **Cisco FTD Identity:** RADIUS auth สำหรับ Identity Policy

> **Note:** Deploy แบบ native (systemd) บน Raspberry Pi โดยตรง — ไม่ใช้ Docker  
> ปัจจุบันรันใน debug mode (`sudo freeradius -X`) ตั้งแต่ Feb 26, 2026

## Architecture

```
WiFi Client ──▶ WLC (10.1.50.10) ──▶ FreeRADIUS (10.1.10.10)
                                           │
                                    ┌──────┴──────┐
                                    │             │
                              EAP-PEAP      Inner Tunnel
                           (TLS 1.2 outer)  (MSCHAPv2)
                                    │             │
                                    │      ┌──────┴──────┐
                                    │      │             │
                                    │    LDAP         ntlm_auth
                                    │  (user lookup)  (password verify)
                                    │      │             │
                                    │      └──────┬──────┘
                                    │             │
                                    │      Samba4 AD DC
                                    │     (10.1.10.20)
                                    │      GROUP1.CORP
                                    └─────────────┘
```

## NAS Clients (RADIUS Clients)

| Client Name    | IP              | Shared Secret | Purpose                           |
| -------------- | --------------- | ------------- | --------------------------------- |
| `localhost`    | `127.0.0.1`     | `testing123`  | Local testing (radtest)           |
| `WLC`          | `10.1.50.10`    | `WLC2500`     | WiFi 802.1X (VLAN 30 STAFF-WIFI) |
| `Cisco_FTD`    | `10.1.1.2`      | `testing123`  | Firepower Identity Policy         |
| `MGMT_Device`  | `10.1.50.20`    | `testing123`  | Management device                 |
| `Local_Subnet` | `10.1.10.0/24`  | `testing123`  | ทุกอุปกรณ์ใน Server VLAN          |

## Enabled Modules

| Module           | Type    | Note                              |
| ---------------- | ------- | --------------------------------- |
| `eap`            | FILE    | ⚠️ Copied (not symlink) — customized |
| `mschap`         | symlink | ntlm_auth → Samba4 AD             |
| `ldap`           | symlink | User lookup จาก AD                |
| `pap`            | symlink | PAP fallback                      |
| `files`          | symlink | Local users file                  |
| `always`         | symlink | —                                 |
| `attr_filter`    | symlink | —                                 |
| `chap`           | symlink | —                                 |
| `detail`         | symlink | —                                 |
| `detail.log`     | symlink | —                                 |
| `digest`         | symlink | —                                 |
| `dynamic_clients`| symlink | —                                 |
| `echo`           | symlink | —                                 |
| `exec`           | symlink | —                                 |
| `expiration`     | symlink | —                                 |
| `expr`           | symlink | —                                 |
| `linelog`         | symlink | —                                 |
| `logintime`      | symlink | —                                 |
| `passwd`         | symlink | —                                 |
| `preprocess`     | symlink | —                                 |
| `radutmp`        | symlink | —                                 |
| `realm`          | symlink | —                                 |
| `replicate`      | symlink | —                                 |
| `soh`            | symlink | —                                 |
| `sradutmp`       | symlink | —                                 |
| `unix`           | symlink | —                                 |
| `unpack`         | symlink | —                                 |
| `utf8`           | symlink | —                                 |

## Enabled Sites

| Site             | Purpose                                     |
| ---------------- | ------------------------------------------- |
| `default`        | Main virtual server (port 1812/1813)        |
| `inner-tunnel`   | PEAP/TTLS inner authentication (port 18120) |

## TLS Certificates

Certificates อยู่ใน `/etc/freeradius/3.0/certs/`:

| File             | Usage                      | Note                          |
| ---------------- | -------------------------- | ----------------------------- |
| `privkey1.pem`   | Private key (EAP-PEAP TLS) | Password: `admin888`          |
| `fullchain1.pem` | Server cert + chain        | ใช้ใน `certificate_file`      |
| `cert1.pem`      | CA cert                    | ใช้ใน `ca_file`               |
| `ca.pem`         | Self-signed CA             | จาก `make` (ไม่ได้ใช้ตอนนี้)  |
| `server.pem`     | Self-signed server cert    | จาก `make` (ไม่ได้ใช้ตอนนี้)  |

> ปัจจุบันใช้ cert แบบ Let's Encrypt style (`privkey1.pem`, `fullchain1.pem`, `cert1.pem`)

## Inner-Tunnel Authentication Flow

```
inner-tunnel authorize:
  1. filter_username
  2. suffix
  3. eap { ok = return }
  4. files                    # local users file
  5. -sql                     # SQL (optional, soft fail)
  6. ldap                     # ← lookup user จาก Samba4 AD
  7. mschap                   # ← set Auth-Type := MS-CHAP
  8. expiration / logintime
  9. pap                      # fallback

inner-tunnel authenticate:
  - Auth-Type MS-CHAP → mschap (ntlm_auth → Samba4 AD)
  - eap
```

## Service Management

```bash
# === Production (systemd) ===
sudo systemctl enable --now freeradius
sudo systemctl status freeradius
sudo systemctl restart freeradius

# === Debug mode (verbose output) ===
sudo systemctl stop freeradius
sudo freeradius -X

# ดู logs (systemd mode)
sudo journalctl -u freeradius -f
```

## Testing

```bash
# ===== Test inner-tunnel directly (MSCHAPv2) =====
# This bypasses EAP/TLS — tests mschap + ntlm_auth directly
radtest -t mschap USERNAME PASSWORD 127.0.0.1:18120 0 testing123

# ===== Test full EAP-PEAP (from client or eapol_test) =====
# ต้องใช้ eapol_test หรือ wpa_supplicant

# ===== Plain PAP test (will FAIL with MSCHAPv2 backend) =====
# radtest testuser P@ssw0rd123 127.0.0.1 0 testing123
# ↑ Access-Reject เพราะ backend เป็น ntlm_auth ไม่ใช่ plaintext

# ===== Test ntlm_auth directly =====
ntlm_auth --request-nt-key --domain=GROUP1 \
    --username=testuser --password=P@ssw0rd123
```

## 👁️ Identity Visibility & Monitoring

| VLAN | Auth | FTD Identity | Centralized Log |
| ---- | ---- | ------------ | --------------- |
| **20** (USER wired) | FTD Captive Portal → Samba_AD | ✅ เห็นชื่อ user | ✅ FTD Events + **Wazuh** |
| **30** (STAFF-WIFI) | 802.1X → FreeRADIUS → AD | ❌ FTD ไม่เห็น | ✅ **Wazuh** (เก็บ FreeRADIUS log) |

### ทำไม FTD ดู WiFi 802.1X identity โดยตรงไม่ได้?

802.1X auth เกิดระหว่าง Client ↔ WLC ↔ FreeRADIUS **ก่อนที่ traffic จะถึง FTD** → FTD ไม่เคยเห็น RADIUS exchange  
FTD รับ passive identity ได้เฉพาะจาก **Cisco ISE (pxGrid)** ซึ่งต้องมี license — ไม่รับจาก FreeRADIUS โดยตรง

### วิธีที่ดีที่สุด: Wazuh (centralized log)

ติดตั้ง Wazuh Agent บน .10 → monitor FreeRADIUS log file → เห็นทุกอย่างบน Wazuh Dashboard

```bash
# 1. Install Wazuh Agent on .10
sudo apt install wazuh-agent

# 2. Configure agent to point to Wazuh Manager
sudo nano /var/ossec/etc/ossec.conf
# Set <address>WAZUH_MANAGER_IP</address>

# 3. Add FreeRADIUS log monitoring
# เพิ่มใน /var/ossec/etc/ossec.conf:
```

```xml
<localfile>
  <log_format>syslog</log_format>
  <location>/var/log/freeradius/radius.log</location>
</localfile>
```

```bash
# 4. Switch FreeRADIUS to log to file (not stdout)
# แก้ radiusd.conf: destination = files
# แล้วเปลี่ยนเป็น systemd:
sudo systemctl enable --now freeradius

# 5. Start agent
sudo systemctl enable --now wazuh-agent
```

**สิ่งที่ Wazuh จะเห็นจาก FreeRADIUS:**
- ✅ ใคร login WiFi 802.1X (username, MAC, Access-Accept/Reject)
- ✅ Failed authentication attempts
- ✅ ntlm_auth errors (AD connectivity issues)
- ✅ Alert เมื่อ brute force (Wazuh active response)
- ✅ รวมกับ Samba AD + FTD log ใน dashboard เดียว

**(Optional) daloRADIUS** — ถ้าต้องการ session detail เพิ่มเติม (MAC, duration, bytes) ต้อง enable FreeRADIUS SQL module + MariaDB

## ⚠️ Known Issues

| Issue | Detail | Fix |
| ----- | ------ | --- |
| Subnet mask is `/8` | `10.1.10.10/8` — เข้าถึง 10.x.x.x ทั้งหมด ไม่ตรง VLAN design | แก้ network config เป็น `/24` |
| Debug mode | รันผ่าน `sudo freeradius -X` ไม่ใช่ systemd | `systemctl enable --now freeradius` |
| radtest = Access-Reject | ปกติ — PAP ใช้กับ ntlm_auth backend ไม่ได้ | ใช้ `radtest -t mschap ... 127.0.0.1:18120` |
| EAP mod is a file copy | `mods-enabled/eap` เป็น file ไม่ใช่ symlink | ระวังเวลา update — ต้อง edit file โดยตรง |
| WiFi identity gap | FTD ไม่เห็น 802.1X user identity (ต้องใช้ ISE pxGrid) | ใช้ Wazuh เก็บ FreeRADIUS log แทน |

## Files

```
radius/
├── README.md
├── docker-compose.yml              # ⚠️ Reference only — ไม่ได้ใช้งาน (native install)
└── config/
    ├── clients.conf                # NAS client definitions
    ├── radiusd.conf                # Main config (reference — actual is default + minor changes)
    └── mods-available/
        ├── eap                     # EAP-PEAP/MSCHAPv2 configuration
        └── mschap                  # MSCHAPv2 + ntlm_auth → Samba4 AD
```
