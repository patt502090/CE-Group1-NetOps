# 🎛️ NetOps Group 1 — Network Infrastructure (L2, L3, WLC)

---

## 1. Layer 3 Core Switch — L3_SW_G1 (C9200L-48T-4G, IOS-XE 17.9.4)

### 1.1 VLAN & IP Design

| VLAN | ชื่อ | Subnet | L3 Switch IP | FTD IP (Gateway) | หมายเหตุ |
|------|------|--------|-------------|-----------------|----------|
| 1 | Transit Link | 10.1.1.0/30 | 10.1.1.1 | 10.1.1.2 | P2P link ระหว่าง L3↔FTD |
| 10 | Server | 10.1.10.0/24 | 10.1.10.1 | — | RPi RADIUS, RPi AD, Servers |
| 20 | IT (Privileged) | 10.1.20.0/24 | 10.1.20.2 | 10.1.20.1 | Dual-gateway (FTD เป็น DHCP GW) |
| 30 | Corporate | 10.1.30.0/24 | 10.1.30.2 | 10.1.30.1 | Dual-gateway |
| 40 | Guest | 10.1.40.0/24 | 10.1.40.2 | 10.1.40.1 | Dual-gateway |
| 50 | Management | 10.1.50.0/24 | 10.1.50.1 | — | WLC, SNMP Devices |
| 60 | Building 2 MGMT | 10.1.60.0/24 | 10.1.60.1 | — | AP MGMT, Option 43 for WLC |
| 100 | DMZ | 10.1.100.0/24 | — (no IP) | 10.1.100.1 | Honeypot, Public Services |

> **Dual-gateway:** V20/V30/V40 มี IP ทั้งบน L3 Switch (.2) และ FTD (.1) โดย DHCP แจก FTD (.1) เป็น default-gateway → ทำให้ทราฟฟิกขาออกต้องผ่าน FTD เสมอ

### 1.2 ACL Policy (Inbound ทุก SVI)

ACL ใช้กรองทราฟฟิก **ก่อน** ส่งต่อให้ FTD เพื่อลดโหลด Firewall:

**ACL-V10-SERVER-IN** (Vlan10)
- Permit: V10 → V20/V30/V40/V50/V60 (response traffic) + any any
- PBR จะบังคับ traffic ที่ match `RETURN-TO-FTD` ให้วิ่งไป FTD (10.1.1.2)

**ACL-V20-IT-IN** (Vlan20)
| ลำดับ | Action | สรุป |
|-------|--------|------|
| 10 | permit | → FTD Gateway (10.1.1.2) |
| 20 | permit | → V10 Server (ALL protocols) |
| 30-40 | permit | → V50, V60 MGMT (จัดการอุปกรณ์) |
| 50-60 | **deny** | → V30 Corp, V40 Guest (ห้ามข้ามวง) |
| 70 | permit any | → Internet/DMZ (ให้ FTD จัดการต่อ) |

**ACL-V30-CORP-IN** (Vlan30)
| ลำดับ | Action | สรุป |
|-------|--------|------|
| 10 | permit | → FTD Gateway |
| 20-160 | permit | → V10 เฉพาะ AD Ports: DNS(53), Kerberos(88), MSRPC(135), NetBIOS(137-139), LDAP(389), SMB(445), Kpasswd(464), LDAPS(636), ICMP |
| 165-166 | permit | DHCP (bootps/bootpc) |
| 170 | **deny** | → 10.0.0.0/8 ทั้งหมด (บล็อก Internal ที่เหลือ) |
| 180 | permit any | → Internet (FTD filter ต่อ) |

**ACL-V40-GUEST-IN** (Vlan40)
| ลำดับ | Action | สรุป |
|-------|--------|------|
| 10 | permit | → FTD Gateway |
| 20 | **deny** | → 10.0.0.0/8 ทั้งหมด (ห้ามเข้า Internal) |
| 30-50 | permit | DNS(53), HTTP(80), HTTPS(443) เท่านั้น |
| 60 | **deny any** | บล็อกทุกอย่างที่เหลือ |

### 1.3 Policy-Based Routing — ASYM-FIX

**ปัญหา:** L3 Switch ทำ Inter-VLAN Routing ได้เอง → ทราฟฟิก response จาก Server/MGMT ถึง Client โดยไม่ผ่าน FTD → FTD drop เพราะไม่เห็น session ขาไป (Asymmetric Routing)

**แก้ไข:** ใช้ PBR บังคับทราฟฟิกที่ match ACL `RETURN-TO-FTD` ให้ next-hop ไป FTD (10.1.1.2):

```
route-map ASYM-FIX permit 10
 match ip address RETURN-TO-FTD
 set ip next-hop 10.1.1.2
```

**ใช้กับ SVI:**
- `Vlan10` — Server → Client traffic ต้องผ่าน FTD
- `Vlan50` — MGMT → Client traffic ต้องผ่าน FTD
- `Vlan60` — Building 2 → Client traffic ต้องผ่าน FTD

**ACL RETURN-TO-FTD** match traffic:
- V10 → V20, V30, V40, V100
- V50 → V20, V30, V40
- V60 → V20, V30, V40

### 1.4 DHCP Server

L3 Switch เป็น DHCP Server สำหรับทุก VLAN โดยแจก **FTD (.1) เป็น default-gateway** ให้ V20/V30/V40:

| Pool | Network | Gateway | DNS |
|------|---------|---------|-----|
| EMPLOYEE (V20) | 10.1.20.0/24 | 10.1.20.1 (FTD) | 10.1.10.20, 172.30.0.4 |
| STAFF (V30) | 10.1.30.0/24 | 10.1.30.1 (FTD) | 172.30.0.4 |
| GUEST (V40) | 10.1.40.0/24 | 10.1.40.1 (FTD) | 172.30.0.4 |
| MANAGEMENT (V50) | 10.1.50.0/24 | 10.1.50.1 (L3) | 172.30.0.4 |
| SERVER (V10) | 10.1.10.0/24 | 10.1.10.1 (L3) | 10.1.10.20, 8.8.8.8 |
| VLAN60_MGMT | 10.1.60.0/24 | 10.1.60.1 (L3) | — (Option 43 for WLC) |

### 1.5 NetFlow (Traffic Monitoring)

ส่ง NetFlow v9 ไปยัง:
- **Grafana/ElastiFlow:** 10.1.10.20:2055, 10.1.50.35:2055
- **เปิดบน SVI:** V10, V20, V40, V60 (input+output), V100 (input+output)

### 1.6 Port Assignments & EtherChannel

| Port-Channel | พอร์ต | ปลายทาง | Mode | VLANs Allowed |
|-------------|-------|---------|------|---------------|
| **Po1** | Gi37-40 | WLC (CT2504) | Static (mode on) | All ยกเว้น V60 |
| **Po2** | Gi45-47 | L2 Switch (PoE) | LACP (active) | V10,20,30,40,50,60,100 |
| **Po3** | Gi25-27 | L2 Switch → FTD trunk | Static (mode on) | V1,10,20,30,40,100 |

| พอร์ตเดี่ยว | VLAN | หมายเหตุ |
|-------------|------|----------|
| Gi1-12 | V50 | Management devices |
| Gi13-24 | V10 | Server LAN |
| Gi36 | V100 | DMZ |

---

## 2. Layer 2 Access Switch — POE_SW_G1 (WS-C3750X-48P, IOS 15.2(4)E6)

### 2.1 802.1X Configuration (Gi1/0/1 – Gi1/0/12)

```
interface GigabitEthernet1/0/1
 switchport access vlan 20                          ← default VLAN (ก่อน Auth)
 switchport mode access
 authentication event fail action authorize vlan 40          ← Auth ไม่ผ่าน → Guest
 authentication event server dead action authorize vlan 20   ← RADIUS ล่ม → Fallback IT
 authentication event no-response action authorize vlan 40   ← ไม่ตอบ → Guest
 authentication event server alive action reinitialize       ← RADIUS กลับมา → Auth ใหม่
 authentication host-mode multi-auth                         ← อุปกรณ์หลายตัว Auth แยกกัน
 authentication port-control auto
 dot1x pae authenticator
 dot1x timeout tx-period 10
 spanning-tree portfast edge
```

**สรุป Flow:**
1. เสียบสาย → Switch ส่ง EAP-Request
2. User ตอบ credentials → Switch ส่งไป RADIUS (10.1.10.10)
3. RADIUS ตอบ Accept + VLAN → Switch override port เป็น VLAN ที่ได้
4. ถ้า Fail → ลง VLAN 40 (Guest), ถ้า RADIUS ตาย → ลง VLAN 20 (Emergency)

### 2.2 RADIUS Server Config

```
radius-server host 10.1.10.10 auth-port 1812 acct-port 1813 key Rad1us_L2SW!
```

- AAA: `aaa authentication dot1x default group radius`
- Authorization: `aaa authorization network default group radius`
- Accounting: `aaa accounting dot1x default start-stop group radius`

### 2.3 DHCP Snooping

ป้องกัน Rogue DHCP Server:
- เปิดบน: `vlan 10,20,30,40,50,60,100`
- **Trust port:** Po1 (trunk ไป L3) → ยอมรับ DHCP Offer จากฝั่ง L3/FTD
- Access port (802.1X): untrusted → ถ้ามีคนเอา DHCP Server มาต่อจะโดนบล็อก

### 2.4 Port Assignments

| พอร์ต | หน้าที่ | Mode |
|-------|---------|------|
| Gi1/0/1–12 | 802.1X User Ports | Access (VLAN 20 default) |
| Gi1/0/13–24 | AP Indoor (Building 1) | Trunk |
| Gi1/0/25–36 | AP Outdoor / Building 2 | Trunk (native V999) |
| Po1 (Gi42-44) | Uplink → L3 Switch | Trunk (LACP) |

---

## 3. Wireless LAN Controller — WLC_G1 (AIR-CT2504-K9, Firmware 8.5.182.0)

### 3.1 SSIDs (WLANs)

| WLAN ID | SSID Name | Security | Interface | AAA Override | RADIUS | Session Timeout |
|---------|-----------|----------|-----------|-------------|--------|-----------------|
| **1** | Group01-Corporate Enterprise | **WPA2 + 802.1X** | corporate (V30) | **Enabled** | Server 1 (Auth+Acct) | 1800s |
| **2** | Group01-Corporate Guest | **WPA2 + PSK** | guest (V40) | Disabled | — | 1800s |

**WLAN 1 (Corporate) — Dynamic VLAN Flow:**
1. User เชื่อม SSID → WLC ส่ง RADIUS Auth ไปหา FreeRADIUS (10.1.10.10:1812)
2. RADIUS ตอบ Accept + `Tunnel-Private-Group-Id` (20 หรือ 30)
3. WLC ใช้ **aaa-override** → override interface จาก corporate (V30) เป็น VLAN ที่ RADIUS ส่งมา
4. IT user → ได้ VLAN 20, HR/Finance/Staff → ได้ VLAN 30

**WLAN 2 (Guest):**
- PSK authentication → ลง VLAN 40 ตรงๆ
- Custom web pages: `loginfailure-page error.html`, `logout-page logout.html`

### 3.2 Dynamic Interfaces

| Interface | IP Address | Subnet Mask | Gateway (FTD) | VLAN | DHCP Server |
|-----------|-----------|-------------|---------------|------|-------------|
| **management** | 10.1.50.10 | 255.255.255.0 | 10.1.50.1 | 50 | 10.1.50.1 (L3) |
| **corporate** | 10.1.30.10 | 255.255.255.0 | 10.1.30.1 | 30 | 10.1.30.2 (L3) |
| **guest** | 10.1.40.10 | 255.255.255.0 | 10.1.40.1 | 40 | 10.1.40.2 (L3) |
| **privileged** | 10.1.20.10 | 255.255.255.0 | 10.1.20.1 | 20 | 10.1.20.2 (L3) |
| **virtual** | 192.0.2.1 | — | — | — | Web Auth redirect |

### 3.3 RADIUS Config (WLC)

| Parameter | ค่า |
|-----------|-----|
| Auth Server 1 | 10.1.10.10 : 1812 |
| Acct Server 1 | 10.1.10.10 : 1813 |
| Retransmit Timeout | 5 sec |
| CallStationId Type | AP MAC + SSID |
| Fallback Test | Passive mode, interval 300s |

### 3.4 AP Groups

| Group Name | คำอธิบาย | WLAN 1 Interface | WLAN 2 Interface |
|-----------|----------|-----------------|-----------------|
| **Group-HighDensity** | Conference & Convention Halls | corporate | guest |
| **Group-Office_Standard** | Office & Food Court | corporate | guest |
| **Group-Outdoor** | Center Zone | corporate | guest |
| **default-group** | Default | corporate | guest |

> ทุก AP Group map WLAN 1 → corporate, WLAN 2 → guest เหมือนกัน (aaa-override จะ override VLAN ตาม RADIUS อีกที)

### 3.5 RF Profiles

| Profile | Band | Min Tx Power | RX-SOP | Use Case |
|---------|------|-------------|--------|----------|
| High-Client-Density | 802.11a/bg | 7 dBm | Medium | ห้องประชุม (คนเยอะ ลด power + ปิด low rates) |
| Low-Client-Density | 802.11a/bg | default | Low | พื้นที่โล่ง (coverage กว้าง) |
| Typical-Client-Density | 802.11a/bg | default | default | สำนักงานทั่วไป |

**High-Density tuning:** ปิด data rates ต่ำ (1/2/5.5/6/9/11 Mbps) → mandatory 12/24 Mbps → บังคับ client ใช้ rate สูง ลด airtime

### 3.6 Uplink & Other Settings

- **LAG:** Enabled (Port-channel ไป L3 Switch Po1)
- **Load Balancing:** Aggressive, window 5
- **Multicast:** mode multicast 239.1.1.1
- **SNMP v3:** user `AdminG1` (SHA+AES128) → trap receivers 172.31.0.102, 172.30.254.7
- **Syslog:** → 10.1.10.30
- **Mobility Domain:** Group1
