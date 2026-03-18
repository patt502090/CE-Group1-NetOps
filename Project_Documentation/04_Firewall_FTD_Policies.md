# 🧱 NetOps Group 1 — Firewall (Cisco FTD / FPR-2110)

## 1. บทบาท

Cisco Firepower Threat Defense (NGFW 7.4.2) ทำหน้าที่:
- **Stateful Inspection** — ติดตาม session ทุก connection (TCP state, UDP pseudo-state)
- **NAT** — แปลง IP ภายในออกสู่ Internet (Dynamic PAT)
- **L7 Application Control** — กรองระดับ Application ผ่าน Snort engine
- **Zone-based Firewall** — แยกโซนตาม Sub-interface บน Port-channel1

---

## 2. Interfaces & Security Zones

| Sub-interface | Zone Name | IP Address | VLAN | Network |
|--------------|-----------|-----------|------|---------|
| Po1.1 | **inside** | 10.1.1.2/30 | 1 | Transit link ไป L3 Switch |
| Po1.20 | **it** | 10.1.20.1/24 | 20 | IT / Privileged |
| Po1.30 | **corporate** | 10.1.30.1/24 | 30 | HR, Finance, Staff |
| Po1.40 | **guest** | 10.1.40.1/24 | 40 | Guest |
| Po1.100 | **dmz** | 10.1.100.1/24 | 100 | DMZ (Honeypot, Public) |
| Eth1/13 | **outside** | 10.0.1.2/30 | — | อินเทอร์เน็ต (ไป Router 10.0.1.1) |

> **V50/V60 (MGMT)** ไม่มี Sub-interface บน FTD โดยตรง → ทราฟฟิก MGMT เข้า FTD ผ่าน **inside zone** (transit link V1) เมื่อถูก PBR บังคับมา

---

## 3. Access Control Policy — NGFW_Access_Policy

กฎทั้งหมดรันจากบนลงล่าง (top-down) — กฎที่ match ก่อนจะถูก apply:

| # | Rule Name | Source Zone → Dest Zone | Service | Action | สรุป |
|---|-----------|------------------------|---------|--------|------|
| 1 | Allow-DNS-For-Employee | inside, it → any | DNS (TCP/UDP 53) | ✅ Permit | ให้ IT (ผ่านทั้ง inside/it zone) query DNS ได้ |
| 2 | Allow-Prime-SNMP | outside → inside | ICMP, SSH, SNMP | ✅ Permit | ให้ SNMP Server (172.31.0.102) ดึงข้อมูลอุปกรณ์ |
| 3 | Allow_Outside_to_DMZ | outside, it → dmz | HTTP, HTTPS | ✅ Permit | เปิด Web เข้า DMZ (Honeypot/Portal) |
| 4 | block HR group | any → outside | IP (all) | ✅ Permit* | *L7 Rule — Snort ตรวจ identity/app ก่อนปล่อย |
| 5 | Allow-DMZ-to-Server-App | dmz → inside | IP (all) | ✅ Permit | DMZ เข้าหา Server LAN (V10) |
| 6 | Allow_InsideAndIT_to_DMZ | inside, it → dmz | IP (all) | ✅ Permit | Server/IT เข้า DMZ |
| 7 | Allow-All-for-MGMT | inside (MGMT-Network) → any | IP (all) | ✅ Permit | วง MGMT (10.1.50.0/24) ออกได้ทุกที่ |
| 8 | ALLOW-INTERNET | corporate, dmz, guest, inside, it → outside | IP (all) | ✅ Permit | ทุกวงออก Internet (ผ่าน NAT) |
| 9 | Allow-Internal-Ping | inside, it, dmz ↔ inside, it, dmz | ICMP | ✅ Permit | Ping ภายในระหว่าง 3 zone |
| 10 | Allow_IT_To_Inside | it → inside, it | IP (all) | ✅ Permit | IT เข้าถึง Server LAN ได้ทั้งหมด |
| 11 | Allow_Corp_To_AD | corporate → corporate, inside | AD Ports² | ✅ Permit | Corp เข้า AD Server เฉพาะ AD ports |
| **Last** | **DefaultActionRule** | **any → any** | **any** | **❌ Deny** | **บล็อกทุกอย่างที่ไม่ match ข้างบน** |

> ² **AD Ports** = ICMP, Kerberos(88), MSRPC(135), NetBIOS-SSN(139), LDAP(389), SMB(445), Kpasswd(464), LDAPS(636), NetBIOS-NS/DGM(137-138)

---

## 4. NAT (Dynamic PAT)

ทุก zone ที่ต้องออก Internet ใช้ Dynamic Interface NAT → แปลง source IP เป็น outside IP ของ FTD (10.0.1.2):

```
object network inside-lan    → nat (inside,outside)    dynamic interface
object network IT-Network     → nat (it,outside)        dynamic interface
object network Corporate-Network → nat (corporate,outside) dynamic interface
object network Guest-Network  → nat (guest,outside)     dynamic interface
object network DMZ-LAN        → nat (dmz,outside)       dynamic interface
```

มี Static NAT พิเศษ 1 ตัว:
```
nat (inside,outside) source static inside-lan inside-lan destination static SNMP_Server SNMP_Server
```
→ ให้ SNMP Server (172.31.0.102) เข้าถึง inside-lan โดยไม่ถูก NAT (identity NAT)

---

## 5. Routing

```
route outside 0.0.0.0 0.0.0.0 10.0.1.1 1     ← Default route ออก Internet
route inside 10.1.0.0 255.255.0.0 10.1.1.1 1  ← Internal traffic ส่งไป L3 Switch
```

---

## 6. Inspection & Monitoring

- **Global Policy:** inspect DNS, FTP, H323, SIP, ICMP, NetBIOS, SNMP, TFTP, และอื่นๆ
- **Threat Detection:** basic-threat + access-list statistics
- **Logging:** → 10.1.10.30 (Syslog server), level warnings
- **SNMP v3:** user `AdminG1` (SHA+AES128) → trap receiver 172.31.0.102
