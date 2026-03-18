# 🔐 NetOps Group 1 — Identity Management (RADIUS + Samba AD)

## 1. ภาพรวมระบบ Authentication

```
┌──────────────┐   802.1X    ┌──────────────┐   RADIUS    ┌──────────────┐   ntlm_auth   ┌──────────────┐
│  User Device │ ──────────► │ L2 Switch /  │ ──────────► │ FreeRADIUS   │ ────────────► │  Samba AD    │
│  (Supplicant)│  EAP-PEAP   │ WLC (NAS)    │  UDP 1812   │  10.1.10.10  │   winbindd    │  10.1.10.20  │
└──────────────┘             └──────────────┘             └──────────────┘               └──────────────┘
                                                                │
                                                     ┌─────────┴──────────┐
                                                     │ ตรวจ LDAP-Group    │
                                                     │ แล้วส่ง VLAN กลับ │
                                                     │ (Tunnel-Private-   │
                                                     │  Group-Id)         │
                                                     └────────────────────┘
```

**Authentication Flow:**
1. User กรอก username/password (domain account) → Device ส่ง EAP-PEAP
2. NAS (L2 Switch หรือ WLC) ส่ง RADIUS Access-Request ไปหา FreeRADIUS (10.1.10.10:1812)
3. FreeRADIUS ใช้ **EAP-PEAP** เป็น outer method → **MSCHAPv2** เป็น inner method
4. MSCHAPv2 module เรียก `ntlm_auth` ผ่าน Samba winbindd → ตรวจ password กับ Samba AD (GROUP1.CORP)
5. ถ้า Auth สำเร็จ → inner-tunnel `post-auth` ตรวจ **LDAP-Group** → ส่ง `Tunnel-Private-Group-Id` กลับ
6. NAS รับค่า VLAN → Override access port ให้ User ตกลง VLAN ที่ถูกต้อง

---

## 2. รายชื่อ Users / Groups (Samba AD)

**Domain:** `GROUP1.CORP` | **DC:** 10.1.10.20 (Raspberry Pi)

ตรวจสอบด้วย: `samba-tool group listmembers <GroupName>`

| กลุ่ม | VLAN ที่ได้ | สมาชิก |
|-------|-----------|--------|
| **IT** | 20 (Privileged) | `Administrator`, `user_test1`, `saranyapong.a`, `suwijak.c`, `phodcharaphon.s`, `winnie.p`, `farik.b`, `poramet.k`, `touch.a` |
| **HR** | 30 (Corporate) | `Administrator`, `kanchana.p`, `winnie.p`, `andrew.c`, `michael.t`, `siriporn.w`, `david.l` |
| **Finance** | 30 (Corporate) | `Administrator`, `anong.r`, `krit.k`, `winnie.p`, `somchai.x`, `robert.j`, `nathan.k`, `pattarapong.m`, `poramet.k` |
| **Staff** | 30 (Corporate) | `Administrator` |

> **หมายเหตุ:** User ที่อยู่หลายกลุ่ม (เช่น `winnie.p`) → FreeRADIUS จะ match กลุ่มแรกที่เจอตาม if/elsif ใน inner-tunnel → ถ้าอยู่ทั้ง IT และ HR จะได้ **VLAN 20** (เพราะ `if (LDAP-Group == "IT")` อยู่บนสุด)

---

## 3. FreeRADIUS Configuration

### 3.1 Dynamic VLAN Assignment (inner-tunnel post-auth)

**ไฟล์:** `/etc/freeradius/3.0/sites-enabled/inner-tunnel` — section `post-auth {}`

```text
post-auth {
    if (LDAP-Group == "IT") {
        update reply {
            Tunnel-Type := VLAN
            Tunnel-Medium-Type := IEEE-802
            Tunnel-Private-Group-Id := "20"
        }
        update reply { Reply-Message := "Welcome IT - VLAN 20 (Privileged)" }
    }
    elsif (LDAP-Group == "HR") {
        update reply {
            Tunnel-Type := VLAN
            Tunnel-Medium-Type := IEEE-802
            Tunnel-Private-Group-Id := "30"
        }
    }
    elsif (LDAP-Group == "Finance") {
        update reply {
            Tunnel-Type := VLAN
            Tunnel-Medium-Type := IEEE-802
            Tunnel-Private-Group-Id := "30"
        }
    }
    elsif (LDAP-Group == "Staff") {
        update reply {
            Tunnel-Type := VLAN
            Tunnel-Medium-Type := IEEE-802
            Tunnel-Private-Group-Id := "30"
        }
    }
    else {
        # Default: ถ้า Auth ผ่านแต่ไม่ตรงกลุ่มไหนเลย → VLAN 30
        update reply {
            Tunnel-Type := VLAN
            Tunnel-Medium-Type := IEEE-802
            Tunnel-Private-Group-Id := "30"
        }
    }
}
```

### 3.2 Filter-Id Mapping (authorize file)

**ไฟล์:** `/etc/freeradius/3.0/mods-config/files/authorize`

```text
DEFAULT Ldap-Group == "IT"
    Filter-Id = "IT_Group",
    Reply-Message = "Authenticated as IT"

DEFAULT Ldap-Group == "Staff"
    Filter-Id = "Staff_Group"

DEFAULT Ldap-Group == "Finance"
    Filter-Id = "Finance_Group"
```

### 3.3 NAS Clients (ใครส่ง RADIUS มาได้บ้าง)

**ไฟล์:** `/etc/freeradius/3.0/clients.conf`

| NAS | IP | Secret | หมายเหตุ |
|-----|----|--------|----------|
| WLC / WLC2500 | 10.1.50.10 | `Rad1us_WLC!` | Wireless Controller |
| Cisco_FTD | 10.1.1.2 | `Rad1us_FTD!` | Firewall |
| MGMT_Device | 10.1.50.0/24 | `Rad1us_MgMt!` | อุปกรณ์ Management |
| Local_Subnet | 10.1.10.0/24 | `Rad1us_L2SW!` | Subnet ที่ RADIUS อยู่ |

### 3.4 EAP Configuration สรุป

| Parameter | ค่า |
|-----------|-----|
| Default EAP Type | **PEAP** |
| Inner Method | **MSCHAPv2** (ผ่าน ntlm_auth → Samba AD) |
| TLS version | **1.2** |
| Certificate | Let's Encrypt (`/etc/letsencrypt/live/rasberrypi-888.duckdns.org/`) |

---

## 4. Samba AD Configuration (smb.conf)

**ไฟล์:** `/etc/samba/smb.conf` บน DC (10.1.10.20)

| Parameter | ค่า | ทำไมต้องตั้ง |
|-----------|-----|-------------|
| `realm` | `GROUP1.CORP` | ชื่อ domain |
| `workgroup` | `GROUP1` | NetBIOS domain name |
| `server role` | `active directory domain controller` | เป็น AD DC |
| `dns forwarder` | `8.8.8.8` | Forward DNS queries ที่ไม่ใช่ domain ไปหา Google |
| `ntlm auth` | `yes` | **จำเป็น** — ให้ FreeRADIUS ใช้ ntlm_auth สำหรับ MSCHAPv2 |
| `ldap server require strong auth` | `no` | ให้ FreeRADIUS ทำ simple bind ได้ (ไม่บังคับ LDAPS) |
| `idmap_ldb:use rfc2307` | `yes` | ใช้ RFC2307 attributes สำหรับ uid/gid mapping |

---

## 5. GPO, File Sharing & Windows Client Configuration

### 5.1 File Shares (ACL-enforced)

Samba AD DC ให้บริการ File Share ผ่าน SMB โดย แต่ละ Share มี ACL ตาม AD Group:

| Share Name | Path บน DC | สิทธิ์ | Drive Letter (GPO) |
|------------|-----------|--------|-------------------|
| `Staff_Common` | `\\10.1.10.20\Staff_Common` | All Domain Users | **Z:** |
| `IT_Dept` | `\\10.1.10.20\IT_Dept` | GROUP1\IT only | **Y:** |
| `HR_Dept` | `\\10.1.10.20\HR_Dept` | GROUP1\HR only | **X:** |
| `Finance_Dept` | `\\10.1.10.20\Finance_Dept` | GROUP1\Finance only | **W:** |

Built-in shares จาก smb.conf:

| Share | Path | หน้าที่ |
|-------|------|--------|
| `[sysvol]` | `/var/lib/samba/sysvol` | AD replication (GPO, scripts) |
| `[netlogon]` | `/var/lib/samba/sysvol/group1.corp/scripts` | Logon scripts สำหรับ GPO |

### 5.2 GPO — Map Network Drives (Logon Script)

**วิธี:** ใช้ Logon Script (`map_drives.bat`) วางใน **netlogon share** → GPO เรียกตอน User login

**ไฟล์:** `\\GROUP1.CORP\netlogon\map_drives.bat`

```bat
@echo off
:: Map drives based on group membership
net use Z: \\10.1.10.20\Staff_Common /persistent:yes
:: IT group only
net use Y: \\10.1.10.20\IT_Dept /persistent:yes 2>nul
:: HR group only
net use X: \\10.1.10.20\HR_Dept /persistent:yes 2>nul
:: Finance group only
net use W: \\10.1.10.20\Finance_Dept /persistent:yes 2>nul
```

> **GPO Path:** `Computer/User Configuration → Windows Settings → Scripts → Logon → map_drives.bat`
> ถ้า Samba AD ยังไม่มี RSAT/GPMC → ใช้ Logon Script ผ่าน netlogon share แทน GPO snap-in

### 5.3 Windows 802.1X SSO (Single Sign-On)

**Script:** `security/802.1x-sso/setup-8021x-sso.ps1` — ตั้งค่า Windows ให้ใช้ AD credentials ทำ 802.1X อัตโนมัติ

**UX Flow:**
1. User เปิดเครื่อง → Login ด้วย AD account (`GROUP1\winnie.p`)
2. Windows ส่ง 802.1X EAP-PEAP/MSCHAPv2 อัตโนมัติ (ใช้ credentials เดียวกัน)
3. Switch/WLC assign dynamic VLAN → ได้ IP จาก DHCP → ไม่มี popup ให้กรอกซ้ำ

**สิ่งที่ Script ทำ:**

| ขั้นตอน | รายละเอียด |
|---------|-----------|
| 1. Enable `dot3svc` | เปิด Wired AutoConfig service (จำเป็นสำหรับ wired 802.1X) |
| 2. Wired Profile | สร้าง LAN XML profile: EAP Type 25 (PEAP), Inner Type 26 (MSCHAPv2), `UseWinLogonCredentials=true`, SSO preLogon |
| 3. WiFi Profile | สร้าง WLAN XML profile: WPA2-Enterprise, same PEAP/MSCHAPv2 + SSO |
| 4. Registry fallback | ถ้า netsh ไม่ได้ → ใช้ registry keys ที่ `HKLM:\...\WiredNetworkSettings` |

**การใช้งาน (Run as Admin):**
```powershell
.\setup-8021x-sso.ps1                     # ตั้งทั้ง LAN + WiFi
.\setup-8021x-sso.ps1 -Mode LAN           # เฉพาะ Wired
.\setup-8021x-sso.ps1 -Mode WiFi -SSIDName "Group01-Corporate Enterprise"
```

> **Key Setting:** `<UseWinLogonCredentials>true</UseWinLogonCredentials>` คือ ตัวที่ทำให้ Windows ส่ง AD password ไปทำ 802.1X อัตโนมัติ ไม่ต้องกรอกซ้ำ

---

## 6. Operational Caveats

- **AAA Override** ต้องเปิดที่ NAS เสมอ → ไม่งั้น VLAN assignment จาก RADIUS จะไม่มีผล
  - WLC: `aaa-override enable` ✅ (WLAN 1)
  - L2 Switch: `aaa authorization network default group radius` ✅
- FreeRADIUS ตอนนี้รันใน **debug mode** (`freeradius -X`) → production ควรย้ายเป็น `systemctl enable freeradius`
