# 🖥️ Infrastructure Services

การตั้งค่าและ Deployment ของ Server Services ทั้งหมดใน VLAN 10 (SERVER) — `10.1.10.0/24`

ทุก service รันแบบ **Native (systemd)** บน Raspberry Pi 4 — ไม่ใช้ Docker

## 📋 Service Inventory

| Service             | IP Address   | Hostname          | Host           | OS                   | Managed By             | Status |
| ------------------- | ------------ | ----------------- | -------------- | -------------------- | ---------------------- | ------ |
| Samba4 AD DC        | `10.1.10.20` | `raspberrypi`     | Raspberry Pi 4 | Debian 13 (trixie)   | `samba-ad-dc.service`  | ✅      |
| FreeRADIUS (802.1X) | `10.1.10.10` | `rasberrypi-888`  | Raspberry Pi 4 | Debian 13 (trixie)   | `freeradius.service`   | ⚠️      |
| Grafana + SNMP      | `10.1.10.30` | —                 | Mac Mini       | —                    | —                      | 📋      |

> **⚠️ FreeRADIUS:** ปัจจุบันรันแบบ debug mode (`sudo freeradius -X`) ไม่ได้รันผ่าน systemd  
> **⚠️ .10 Subnet Mask:** `10.1.10.10/8` — ควรเป็น `/24` ให้ตรงกับ VLAN design

### Remote Access (Tailscale)

| Host              | Tailscale IP       |
| ----------------- | ------------------ |
| raspberrypi (.20) | `100.84.145.105`   |
| rasberrypi-888 (.10) | `100.92.40.11` |

## 🗂️ Directory Structure

```
infra/
├── README.md                  # (this file)
├── active-directory/          # Samba4 AD Domain Controller (GROUP1.CORP)
│   ├── README.md
│   ├── docker-compose.yml     # Reference only — ไม่ได้ใช้งาน (native install)
│   └── config/
│       └── smb.conf           # Real /etc/samba/smb.conf
├── radius/                    # FreeRADIUS 3.2.7 — 802.1X Authentication Server
│   ├── README.md
│   ├── docker-compose.yml     # Reference only — ไม่ได้ใช้งาน (native install)
│   └── config/
│       ├── clients.conf       # NAS client definitions
│       ├── radiusd.conf       # Main config (reference)
│       └── mods-available/
│           ├── eap            # EAP-PEAP/MSCHAPv2 configuration
│           └── mschap         # MSCHAPv2 + ntlm_auth configuration
└── monitoring/                # Grafana Dashboard + SNMP Polling (planned)
```

## 🚀 Service Management

```bash
# === Samba4 AD DC (on .20) ===
sudo systemctl status samba-ad-dc
sudo systemctl restart samba-ad-dc

# === FreeRADIUS (on .10) ===
# Production (systemd):
sudo systemctl enable --now freeradius
sudo systemctl status freeradius

# Debug mode (current):
sudo freeradius -X
```

## 🔗 Dependencies

```
                    ┌─────────────────────┐
                    │    Samba4 AD DC      │
                    │   10.1.10.20 (.20)   │
                    │   GROUP1.CORP        │
                    │  raspberrypi         │
                    │  [Wazuh Agent]       │
                    └──────┬─────┬────────┘
                           │     │
           ntlm_auth       │     │  LDAP (389)
           (winbind pipe)  │     │  Identity Source: Samba_AD
                           │     │
                           ▼     ▼
┌──────────┐  ┌──────────────┐  ┌────────────────────┐
│   WLC    │─▶│ FreeRADIUS   │  │   Cisco FTD        │
│10.1.50.10│  │ 10.1.10.10   │  │   10.1.1.2         │
│ 1812/UDP │  │ (.10)        │  │                    │
│          │  │ [Wazuh Agent]│  │ syslog ──┐         │
└──────────┘  └──────────────┘  └──────────┼─────────┘
      │                                    │
      │ EAP-PEAP/MSCHAPv2                  │ HTTP Basic (Captive Portal)
      │ (TLS 1.2 + NTLM)                  │ Active Auth → Samba_AD
      ▼                                    ▼
┌──────────────┐                ┌──────────────────┐
│  VLAN 30     │                │  VLAN 20         │
│  STAFF-WIFI  │                │  USER (Wired)    │
│  802.1X      │                │  Employee-LAN    │
│  ✅ Wazuh    │                │  ✅ FTD Identity │
│   monitored  │                │  ✅ Wazuh        │
└──────────────┘                └──────────────────┘
         │                              │
         └──────────┬───────────────────┘
                    ▼
          ┌──────────────────┐
          │  Wazuh Manager   │
          │  + Dashboard     │
          │  (centralized    │
          │   auth logs)     │
          └──────────────────┘
```

## 👁️ Identity Visibility Matrix

| VLAN | Network | Auth Method | Identity Source | FTD Identity | Centralized Log |
| ---- | ------- | ----------- | --------------- | ------------ | --------------- |
| **20** | USER (Wired) | FTD Captive Portal (HTTP Basic) | Samba_AD (LDAP) | ✅ FTD knows who | ✅ FTD Events + Wazuh |
| **30** | STAFF-WIFI | 802.1X EAP-PEAP/MSCHAPv2 | FreeRADIUS → AD | ❌ FTD ไม่เห็น | ✅ **Wazuh** (เก็บ FreeRADIUS + Samba log) |
| **40** | GUEST-WIFI | — | — | ❌ Anonymous | ❌ ไม่มี |

### ทำไม FTD เห็น VLAN 20 แต่ไม่เห็น VLAN 30?

FTD รู้จัก identity ได้ 2 วิธีเท่านั้น:
1. **Active Auth (Captive Portal)** — FTD ดัก HTTP แล้ว prompt login (ใช้กับ VLAN 20)
2. **Passive Auth (pxGrid/ISE)** — รับ identity mapping จาก Cisco ISE (ต้องมี ISE license)

FTD **ไม่รู้จัก FreeRADIUS** — มันไม่ได้รับ RADIUS accounting จาก third-party RADIUS เป็น identity source  
WiFi 802.1X auth เกิดขึ้นระหว่าง Client ↔ WLC ↔ FreeRADIUS **ก่อนที่ traffic จะถึง FTD** → FTD ไม่เคยเห็น RADIUS exchange

**ทางออกที่เป็นไปได้ (แต่ไม่แนะนำ):**
- Active Auth สำหรับ VLAN 30 ด้วย → แต่ user ต้อง login ซ้ำ 2 ครั้ง (802.1X + captive portal) = bad UX
- Cisco ISE-PIC (pxGrid) → ต้องมี ISE license = แพง
- FMC REST API push user→IP → ต้องเขียน script เอง = ซับซ้อน

**ทางออกที่ดีที่สุด: Wazuh** — รวม log ทุกอย่างไว้ที่เดียว โดยไม่ต้องยุ่งกับ FTD

## 🔐 FTD Identity Policy (Cisco Firepower)

| Setting | Value |
| ------- | ----- |
| **Rule Name** | `Employee-LAN-Captive-Port` |
| **AD Identity Source** | `Samba_AD` (LDAP → 10.1.10.20) |
| **Action** | Active Auth |
| **Auth Type** | HTTP Basic |
| **Server Certificate** | `Captive-Portal-Cert:885` |
| **Source Zone** | `employee_zone` |
| **Source Network** | `Employee-LAN` (VLAN 20) |
| **Destination** | Any Zone / Any Network / Any Port |
| **Fall Back as Guest** | Disabled |
| **Default Action** | Passive Auth (Any Identity Source) |

เมื่อ user บน VLAN 20 เปิด browser → FTD จะแสดง HTTP Basic login prompt → authenticate กับ Samba_AD ผ่าน LDAP → map IP กับ username เป็นเวลา 24 ชม.

## 📊 Monitoring & Management — Wazuh Centralized

### Architecture Overview

```
┌────────────────┐     ┌────────────────┐     ┌────────────────┐
│  Samba4 AD     │     │  FreeRADIUS     │     │  Cisco FTD      │
│  .20           │     │  .10            │     │  10.1.1.2       │
│                │     │                │     │                │
│ syslog:        │     │ log file:      │     │ syslog:        │
│ • AD auth      │     │ • 802.1X login │     │ • Identity     │
│ • LDAP bind    │     │ • accept/reject│     │ • Captive Port │
│ • Kerberos     │     │ • ntlm_auth    │     │ • AC rules     │
└────────┬───────┘     └────────┬───────┘     └────────┬───────┘
         │ wazuh-agent        │ wazuh-agent        │ syslog
         └──────────┬─────────┘                    │
                    │                              │
              ┌─────▼──────────────────────────▼─────┐
              │         Wazuh Manager / Dashboard          │
              │         (Mac Mini .30 หรือแยก)              │
              │                                            │
              │  • ดู login events ทั้งหมดจากที่เดียว       │
              │  • Alert เมื่อ brute force / failed auth       │
              │  • Compliance (PCI DSS, HIPAA)             │
              │  • File integrity monitoring                │
              └────────────────────────────────────────────┘
```

### ทำไมต้อง Wazuh? (ไม่ monitor ผ่าน FTD โดยตรงได้เหรอ?)

**FTD รู้จัก identity เฉพาะ traffic ที่วิ่งผ่าน FTD เอง:**
- VLAN 20 → FTD ดัก HTTP แล้ว prompt captive portal → ✅ เห็น identity
- VLAN 30 (WiFi) → 802.1X auth เกิดที่ WLC↔FreeRADIUS **ก่อน traffic จะถึง FTD** → ❌ FTD ไม่เคยเห็น

FTD ไม่สามารถรับ RADIUS accounting จาก third-party RADIUS (FreeRADIUS) เป็น passive identity source ได้ — ต้องใช้ **Cisco ISE + pxGrid** ซึ่งต้องมี license

**Wazuh แก้ปัญหานี้ได้** — เพราะเก็บ log จากทุกแหล่งมารวมกันใน dashboard เดียว:

| Log Source | สิ่งที่เห็น | Wazuh Method |
| ---------- | ---------- | ------------ |
| **FreeRADIUS** (.10) | ใคร login WiFi, accept/reject, MAC, NAS | Wazuh Agent → monitor `/var/log/freeradius/` หรือ `freeradius -X` stdout |
| **Samba4 AD** (.20) | ใคร auth AD, LDAP bind, Kerberos, password change | Wazuh Agent → monitor syslog (`log level = 3`) |
| **Cisco FTD** | Identity events, ACL hits, captive portal login | Syslog → Wazuh Manager (syslog receiver) |
| **WLC** | WiFi associations, 802.1X events | Syslog → Wazuh Manager |

### Setup Steps

#### Step 1: Install Wazuh Agents (.10 + .20)

```bash
# On both Raspberry Pis (.10 and .20)
curl -s https://packages.wazuh.com/key/GPG-KEY-WAZUH | gpg --dearmor -o /usr/share/keyrings/wazuh.gpg
echo "deb [signed-by=/usr/share/keyrings/wazuh.gpg] https://packages.wazuh.com/4.x/apt/ stable main" > /etc/apt/sources.list.d/wazuh.list
sudo apt update && sudo apt install wazuh-agent

# Configure agent to point to Wazuh Manager
sudo nano /var/ossec/etc/ossec.conf
# Set <address>WAZUH_MANAGER_IP</address>

sudo systemctl enable --now wazuh-agent
```

#### Step 2: Configure FreeRADIUS Log Monitoring (.10)

เพิ่มใน `/var/ossec/etc/ossec.conf` บน .10:

```xml
<localfile>
  <log_format>syslog</log_format>
  <location>/var/log/freeradius/radius.log</location>
</localfile>
```

> **Note:** ถ้ารัน `freeradius -X` (debug mode) ต้องเปลี่ยนเป็น systemd + log to file ก่อน  
> แก้ radiusd.conf: `destination = files` (แทน stdout)

#### Step 3: Configure Samba AD Log Monitoring (.20)

เพิ่มใน `/var/ossec/etc/ossec.conf` บน .20:

```xml
<localfile>
  <log_format>syslog</log_format>
  <location>/var/log/syslog</location>
</localfile>
```

Wazuh มี built-in decoders สำหรับ Samba อยู่แล้ว — จะ parse ได้อัตโนมัติ

#### Step 4: Configure FTD Syslog → Wazuh

บน FMC: Devices → Platform Settings → Syslog → เพิ่ม Wazuh Manager IP

เพิ่มใน Wazuh Manager ossec.conf:

```xml
<remote>
  <connection>syslog</connection>
  <port>514</port>
  <protocol>udp</protocol>
  <allowed-ips>10.1.1.2</allowed-ips>  <!-- FTD IP -->
</remote>
```

### Wazuh Dashboard — สิ่งที่จะเห็น

| ข้อมูล | แหล่งที่มา |
| ------- | -------- |
| ใคร login WiFi 802.1X (ชื่อ, เวลา, MAC) | FreeRADIUS log → Wazuh |
| ใคร login Captive Portal VLAN 20 | FTD syslog → Wazuh |
| AD authentication events | Samba syslog → Wazuh |
| Failed login attempts / brute force alerts | Wazuh built-in rules (rule ID 5710, 5712) |
| Password changes | Samba syslog → Wazuh |
| สรุป: ใครทำอะไร เมื่อไหร่ จากที่ไหน | Dashboard รวมหมด |

### Optional Extras

| Tool | ทำอะไร | ติดตั้งเมื่อ | Complexity |
| ---- | ------ | ---------- | ---------- |
| **LAM** | Web UI จัดการ AD users/groups (เพิ่ม/ลบ/reset pass) | ต้องการ manage users ผ่าน web | ⭐ Easy |
| **daloRADIUS** | Web UI ดู RADIUS accounting detail | ต้องการ session detail (MAC, duration, bytes) | ⭐⭐ Medium |
| **Grafana** | Dashboard visualization | มีอยู่แล้ว แล้วต้องการ custom dashboard | ⭐⭐⭐ Complex |

## ⚠️ Known Issues

| Issue | Detail | Fix |
| ----- | ------ | --- |
| .10 subnet mask is /8 | `inet 10.1.10.10/8` — จะเข้าถึง 10.x.x.x ทั้งหมด | แก้ใน `/etc/network/interfaces` หรือ NetworkManager เป็น `/24` |
| FreeRADIUS อยู่ใน debug mode | `sudo freeradius -X` ตั้งแต่ Feb 26 | เปลี่ยนเป็น `sudo systemctl enable --now freeradius` |
| winbind.service failed บน .20 | ไม่มีปัญหา — winbindd รันเป็น child ของ samba-ad-dc แล้ว | ปิด service นี้: `sudo systemctl disable winbind` |
| radtest ได้ Access-Reject | PAP test ใช้กับ PEAP/MSCHAPv2 backend ไม่ได้ | ใช้ `radtest -t mschap` หรือ test ผ่าน inner-tunnel port 18120 |
| ไม่มี custom OUs | Users อยู่ใน default container (CN=Users) | ใช้ `samba-tool ou create` ถ้าต้องการจัดกลุ่ม |
