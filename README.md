# 🚀 Group 1: Enterprise Network & Security Infrastructure

[![Network Backup](https://img.shields.io/badge/Oxidized-Auto_Sync-success?style=for-the-badge&logo=cisco)](#)
[![Security](https://img.shields.io/badge/SOC-Active-red?style=for-the-badge)](#)
[![Identity](https://img.shields.io/badge/Samba4_AD-Online-blue?style=for-the-badge)](#)

ระบบบริหารจัดการโครงสร้างพื้นฐานเครือข่าย ความปลอดภัย และเซิร์ฟเวอร์แบบบูรณาการ (Infrastructure as Code) ออกแบบโดยยึดหลัก Security-Hardened Architecture สำหรับโปรเจกต์ Computer Engineering

---

## 🏗️ Architecture & Core Components

โปรเจกต์นี้ประกอบด้วย 3 เสาหลัก ได้แก่:

1. **Network Core:** Routing & Switching (L3 C9200L, L2 C3750X, WLC AireOS)
2. **Security Edge:** Next-Gen Firewall (FPR-2110 FTD) ควบคุม Zone Control + NAT
3. **Compute & Identity (NOC/SOC):** Raspberry Pi 4 (AD DC/RADIUS) และ Mac Mini (Honeypot/Monitoring)

### 📊 VLAN & IP Allocation

| VLAN    | Role                   | Subnet          | Gateway (L3/FW)   | Access Control   |
| ------- | ---------------------- | --------------- | ----------------- | ---------------- |
| **10**  | SERVER (App+DB+Infra)  | `10.1.10.0/24`  | `10.1.10.1` (L3)  | 🔒 Restricted    |
| **20**  | USER (Wired Users/Lab) | `10.1.20.0/24`  | `10.1.20.1` (L3)  | ✔️ Outbound Only |
| **30**  | STAFF-WIFI (802.1X)    | `10.1.30.0/24`  | `10.1.30.1` (L3)  | ✔️ Internal      |
| **40**  | GUEST-WIFI (Internet)  | `10.1.40.0/24`  | `10.1.40.1` (FW)  | ❌ Internet Only |
| **50**  | MGMT (SSH/SNMP)        | `10.1.50.0/24`  | `10.1.50.1` (L3)  | 🔒 High Security |
| **100** | DMZ (Public Services)  | `10.1.100.0/24` | `10.1.100.1` (FW) | 🛡️ Monitored     |

---

## 🛡️ Security Operations (SOC) & Services

- **Authentication:** Samba4 Active Directory Domain Controller (GROUP1.CORP)
- **WiFi Security:** 802.1X EAP-PEAP/MSCHAPv2 via FreeRADIUS
- **Intrusion Detection:** Cyberpunk Flask Honeypot deployed in DMZ (`10.1.100.10`)
- **Monitoring:** Grafana (SNMP) & Wazuh (Log Analysis)

---

## ⚙️ Automation Workflow (Oxidized)

ระบบสำรองข้อมูลคอนฟิกเครือข่ายทำงานอัตโนมัติ:

- **Interval:** ทุก 3 ชั่วโมง
- **Flow:** `Fetch via SSH` ➡️ `Detect Diff` ➡️ `Local Git Commit` ➡️ `Auto-Push via Hook`

---

## 🎯 Current Sprint & Task Tracker

- [x] L3/L2 Core Setup & VLAN Routing
- [x] Firewall Policy & NAT Configuration
- [x] Oxidized Auto-Backup Pipeline
- [x] Deploy DMZ Honeypot
- [ ] 🚧 **Blocker:** Fix 802.1X EAP-PEAP Handshake Timeout (Client not responding to Success TLV)
- [ ] 🚧 **Pending:** Integrate Samba AD with Cisco FTD Realm Identity Policy
- [ ] Configure SNMP traps to Grafana/Prime
