# 🏛️ NetOps Group 1 — Architecture & Access Matrix

## 1. แนวคิดการออกแบบ: Defense in Depth

ระบบเครือข่ายใช้หลักการ **Defense in Depth** แบ่งการรักษาความปลอดภัยเป็น 4 ชั้น:

| ชั้น | อุปกรณ์ | หน้าที่ |
|------|---------|---------|
| **1. Identity** | Samba AD + FreeRADIUS (RPi) | ยืนยันตัวตน + กำหนด VLAN ตาม AD Group (RBAC) |
| **2. Access Edge** | L2 Switch (802.1X) + WLC | บังคับ Authentication ตั้งแต่ Layer 2, DHCP Snooping |
| **3. Distribution** | L3 Switch (C9200L) | Inter-VLAN Routing + Stateless ACL กรองที่ Hardware line-rate |
| **4. Security** | FTD (FPR-2110) | Stateful Inspection, NAT, L7 App Control, Deep Packet Inspection |

> **หลักการ:** L3 ACL ตัดทราฟฟิกที่ไม่จำเป็นก่อน → ลดโหลดที่ Firewall → FTD เน้นตรวจสอบเฉพาะทราฟฟิกที่ผ่านเข้ามา

---

## 2. Device Inventory

| อุปกรณ์ | Model | Hostname | IP (Management) | Software | บทบาท |
|---------|-------|----------|-----------------|----------|--------|
| **NGFW** | FPR-2110 | FIREPOWER-G1 | 10.1.1.2 (inside) / 10.0.1.2 (outside) | NGFW 7.4.2 | Stateful FW, NAT, L7 |
| **L3 Switch** | C9200L-48T-4G | L3_SW_G1 | 10.1.50.1 (Vlan50) | IOS-XE 17.9.4 | Core Routing, DHCP, ACL, PBR |
| **L2 Switch** | WS-C3750X-48P | POE_SW_G1 | 10.1.50.2 (Vlan50) | IOS 15.2(4)E6 | 802.1X Edge, PoE for APs |
| **WLC** | AIR-CT2504-K9 | WLC_G1 | 10.1.50.10 (Vlan50) | 8.5.182.0 | Wireless Controller |
| **RADIUS** | Raspberry Pi | rasberrypi-888 | 10.1.10.10 (Vlan10) | FreeRADIUS 3.2.7 + Debian 13 | Auth + Dynamic VLAN |
| **AD DC** | Raspberry Pi | raspberrypi | 10.1.10.20 (Vlan10) | Samba4 AD DC | Identity (GROUP1.CORP) |

---

## 3. AD Group → VLAN Mapping (Dynamic VLAN Assignment)

เมื่อ User ล็อกอินผ่าน 802.1X (สาย LAN หรือ Wi-Fi) → FreeRADIUS ตรวจ LDAP-Group จาก Samba AD → ส่ง `Tunnel-Private-Group-Id` กลับไปบอก Switch/WLC ว่าจะใส่ VLAN ไหน:

| AD Group | Auth Method | VLAN ที่ได้ | สิทธิ์หลัก |
|----------|------------|-------------|-----------|
| **IT** | 802.1X / Corporate SSID | **20 (Privileged)** | เข้าถึงทุก Server, จัดการ MGMT (V50/V60), ออก Internet ได้ทั้งหมด |
| **HR** | 802.1X / Corporate SSID | **30 (Corporate)** | เข้า AD/DNS/SMB Ports ใน V10 เท่านั้น + Internet (ผ่าน FTD) |
| **Finance** | 802.1X / Corporate SSID | **30 (Corporate)** | เหมือน HR |
| **Staff** | 802.1X / Corporate SSID | **30 (Corporate)** | เหมือน HR |
| *(ไม่มีกลุ่ม / Auth ไม่ผ่าน)* | Fallback / Guest SSID | **40 (Guest)** | Internet เท่านั้น (DNS + HTTP/S) |

---

## 4. End-to-End Traffic Flow (Wired 802.1X)

```
[1] User เสียบสาย LAN (L2 Switch Gi1/0/1-12)
          │
[2] Switch ส่ง EAP-Request Identity
          │
[3] User ตอบ domain credentials (EAP-PEAP)
          │
[4] Switch → RADIUS Access-Request → FreeRADIUS (10.1.10.10:1812)
          │
[5] FreeRADIUS: EAP-PEAP → inner MSCHAPv2 → ntlm_auth → Samba AD (10.1.10.20)
          │
[6] AD ตรวจ password → OK → FreeRADIUS ตรวจ LDAP-Group
          │
[7] inner-tunnel post-auth: IT→VLAN 20 / HR,Finance,Staff→VLAN 30
          │
[8] RADIUS Access-Accept + Tunnel-Private-Group-Id → Switch
          │
[9] Switch override port → User ได้ IP จาก DHCP (Gateway = FTD .1)
          │
[10] User ส่ง traffic → FTD (.1) → Stateful Inspection → NAT → Internet
                           ↕
                   L3 Switch ACL กรองก่อน (deny ข้าม VLAN ที่ไม่อนุญาต)
                   PBR (ASYM-FIX) บังคับ response traffic กลับผ่าน FTD
```

---

## 5. Access Control Matrix

ตารางรวมผลของ **L3 Switch ACL** + **FTD Access Policy** (ทั้งสองชั้นทำงานร่วมกัน):

| From ↓ \ To → | V10 Server | V20 IT | V30 Corp | V40 Guest | V50/60 MGMT | V100 DMZ | Internet |
|---------------|-----------|--------|----------|-----------|-------------|----------|----------|
| **V10 Server** | ✅ | ✅ (via PBR→FTD) | ✅ (via PBR→FTD) | ✅ (via PBR→FTD) | ✅ Direct | — | ✅ NAT |
| **V20 IT** | ✅ ALL | ✅ | ❌ L3 Block | ❌ L3 Block | ✅ Manage | ✅ | ✅ ALL |
| **V30 Corp** | ✅ AD Ports Only¹ | ❌ L3 Block | ✅ | ❌ L3 Block | ❌ L3 Block | ❌ L3 Block | ✅ FTD Filter |
| **V40 Guest** | ❌ L3 Block | ❌ L3 Block | ❌ L3 Block | ✅ | ❌ L3 Block | ❌ L3 Block | ✅ DNS+Web Only |
| **V50/60 MGMT** | ✅ | ✅ (via PBR→FTD) | ✅ (via PBR→FTD) | ✅ (via PBR→FTD) | ✅ | ✅ | ✅ |
| **V100 DMZ** | ✅ App Only | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ NAT |
| **Outside** | ❌ | ❌ | ❌ | ❌ | ❌ | ✅ HTTP/S | — |

> ¹ **AD Ports Only** = DNS (53), Kerberos (88), MSRPC (135), NetBIOS (137-139), LDAP (389), SMB (445), Kpasswd (464), LDAPS (636), ICMP
>
> **"L3 Block"** = ถูก deny ตั้งแต่ ACL ที่ L3 Switch → ทราฟฟิกไม่ถึง Firewall เลย (ลดโหลด FTD)
>
> **"via PBR→FTD"** = L3 ACL อนุญาต แต่ route-map ASYM-FIX บังคับส่งไปให้ FTD (10.1.1.2) ตรวจก่อน
