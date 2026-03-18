<div align="center">
<br/>

```
░██████╗░██████╗░░█████╗░██╗░░░██╗██████╗░  ░█████╗░░░███╗░░
██╔════╝░██╔══██╗██╔══██╗██║░░░██║██╔══██╗  ██╔══██╗░████║░░
██║░░██╗░██████╔╝██║░░██║██║░░░██║██████╔╝  ██║░░██║██╔██║░░
██║░░╚██╗██╔══██╗██║░░██║██║░░░██║██╔═══╝░  ██║░░██║╚═╝██║░░
╚██████╔╝██║░░██║╚█████╔╝╚██████╔╝██║░░░░░  ╚█████╔╝███████╗
░╚═════╝░╚═╝░░╚═╝░╚════╝░░╚═════╝░╚═╝░░░░░  ░╚════╝░╚══════╝
```

# Enterprise Network & Security Infrastructure
### A production-grade SOC platform built on physical Cisco hardware

<br/>

[![Cisco NGFW](https://img.shields.io/badge/Cisco_FPR--2110-NGFW_v7.4.2-1BA0D7?style=for-the-badge&logo=cisco&logoColor=white)](https://www.cisco.com)
[![Wazuh SIEM](https://img.shields.io/badge/Wazuh-SIEM_4.x-005571?style=for-the-badge&logo=elastic&logoColor=white)](https://wazuh.com)
[![NetBox](https://img.shields.io/badge/NetBox-4.5.4-00d4ff?style=for-the-badge)](https://netbox.dev)
[![Grafana](https://img.shields.io/badge/Grafana-Dashboards-F46800?style=for-the-badge&logo=grafana&logoColor=white)](https://grafana.com)
[![Samba AD](https://img.shields.io/badge/Samba_AD-GROUP1.CORP-ff6b35?style=for-the-badge)](https://www.samba.org)

<br/>

> *Built from scratch. No cloud. No shortcuts. Real hardware, real threats, real responses.*

<br/>

</div>

---

## What is this?

A fully operational **enterprise network and security operations platform** designed and deployed on physical infrastructure — Cisco enterprise-grade hardware paired with Raspberry Pi servers and Apple Mac Minis running a complete SOC stack.

This isn't a simulation. Every component is live, interconnected, and monitored. The platform includes network segmentation, wireless authentication, intrusion detection, centralized logging, network automation, Active Directory, file sharing with ACL enforcement, and a live honeypot exposed to the internet.

---

## Architecture

```
                              ┌──────────────────────────────┐
                              │          INTERNET             │
                              │       10.0.1.1/30 · ISP      │
                              └──────────────┬───────────────┘
                                             │ Eth1/13
                              ┌──────────────▼───────────────┐
                              │      FIREPOWER-G1             │
                              │   Cisco FPR-2110 · NGFW       │
                              │   IPS · NAT · Zone Policy     │
                              │   GW: V20 V30 V40 V100        │
                              └──────────────┬───────────────┘
                                        Po1 (Eth1/1-3)
                              ┌──────────────▼───────────────┐
                              │        L3_SW_G1               │
                              │  Cisco C9200L · Core Switch   │
                              │  GW: V1 V10 V50 V60           │
                              │  DHCP · PBR · ACL · NetFlow   │
                              └───────┬──────────┬───────────┘
                         Po3 (3p)     │          │    Po1 (4p)
                     ┌──────────▼──┐  │   ┌──────▼──────────┐
                     │  POE_SW_G1  │  │   │     WLC_G1       │
                     │  C3750X-48P │  │   │  AIR-CT2504-K9   │
                     │  802.1X NAC │  │   │  SSID x 2        │
                     └──────┬──────┘  │   └─────────────────┘
                            │ Po2     │
                     ┌──────▼──┐      │
                     │Building2│      │
                     │EWC HA   │      │
                     │Act/Stby │      │
                     └─────────┘      │
                         ┌────────────┼──────────────────────┐
                         │            │                      │
                  ┌──────▼──┐  ┌──────▼──┐  ┌───────────────▼──┐
                  │  RPi-01 │  │  RPi-02 │  │   Mac-Wazuh      │
                  │ VLAN 10 │  │ VLAN 10 │  │   VLAN 10        │
                  │ .10.10  │  │ .10.20  │  │   .10.30         │
                  └─────────┘  └─────────┘  └──────────────────┘
                                                  ┌────────────────┐
                                                  │ Mac-Honeypot   │
                                                  │ VLAN 100 · DMZ │
                                                  │ .100.10        │
                                                  └────────────────┘
```

---

## Network Segmentation & Gateway Assignment

> **หลักคิด:** VLAN ที่ต้องผ่าน FTD ก่อนออก Internet → Gateway = FTD  
> VLAN ที่ L3 Switch จัดการเอง (Server, MGMT, Building 2) → Gateway = L3 Switch

| VLAN | Name | Subnet | Gateway IP | Gateway Device | Description |
|:----:|------|--------|:----------:|:--------------:|-------------|
| **1** | Transit | `10.1.1.0/30` | — | L3 ↔ FTD | Inter-device transit link |
| **10** | Server | `10.1.10.0/24` | `10.1.10.1` | **L3 Switch** | RPi-01, RPi-02, Wazuh |
| **20** | IT / Privileged | `10.1.20.0/24` | `10.1.20.1` | **FTD** | Wired 802.1X, Domain-joined PC |
| **30** | Corporate | `10.1.30.0/24` | `10.1.30.1` | **FTD** | HR, Finance, Staff (Wi-Fi) |
| **40** | Guest | `10.1.40.0/24` | `10.1.40.1` | **FTD** | Guest Wi-Fi, 802.1X fallback |
| **50** | Management | `10.1.50.0/24` | `10.1.50.1` | **L3 Switch** | Network device management |
| **60** | Building 2 | `10.1.60.0/24` | `10.1.60.1` | **L3 Switch** | EWC HA, AP Building 2 |
| **100** | DMZ | `10.1.100.0/24` | `10.1.100.1` | **FTD** | Honeypot (isolated) |

> **L3 Switch SVI (secondary IP):** VLAN 20 = `10.1.20.2`, VLAN 30 = `10.1.30.2`, VLAN 40 = `10.1.40.2`  
> **Default Route:** L3 Switch → `0.0.0.0/0` next-hop `10.1.1.2` (FTD)  
> **PBR (ASYM-FIX):** Return traffic จาก V10/V50/V60 → Client ถูกบังคับผ่าน FTD (10.1.1.2) เสมอ

---

## Hardware Inventory

### Network Infrastructure

| Device | Model | Software | Management IP | Role |
|--------|-------|----------|:------------:|------|
| FIREPOWER-G1 | Cisco FPR-2110 | NGFW v7.4.2 | `10.1.50.20` | Next-gen Firewall · IPS · NAT · Zone Policy |
| L3_SW_G1 | Cisco C9200L-48T-4G | IOS-XE 17.9.4 | `10.1.50.1` | Core L3 Switch · DHCP · PBR · ACL · NetFlow |
| POE_SW_G1 | Cisco WS-C3750X-48PF-L | IOS 15.2(4)E6 | `10.1.50.2` | PoE Access Switch · 802.1X NAC · DHCP Snooping |
| WLC_G1 | Cisco AIR-CT2504-K9 | WLC 8.5.182 | `10.1.50.10` | Wireless LAN Controller · Building 1 |
| EWC-Active | Cisco C9120AXI-S | — | `10.1.60.10` | EWC HA Primary · Building 2 |
| EWC-Standby | Cisco C9120AXI-S | — | `10.1.60.51` | EWC HA Standby · Building 2 |

### Servers

| Device | Hardware | IP | Services |
|--------|----------|----|----------|
| RPi-01 | Raspberry Pi 4B | `10.1.10.10` | FreeRADIUS · Grafana · Loki · DaloRADIUS · DVWA |
| RPi-02 | Raspberry Pi 4B | `10.1.10.20` | Samba AD DC · NetBox · Oxidized · InfluxDB · pmacct |
| Mac-Wazuh | Apple Mac Mini | `10.1.10.30` | Wazuh Manager + Indexer + Dashboard · Syslog Relay |
| Mac-Honeypot | Apple Mac Mini | `10.1.100.10` | Honeypot v2.0 · Promtail · Cloudflare Tunnel |

---

## Security Stack

### Perimeter — Cisco FPR-2110 (FTD)
- Stateful next-generation firewall with IPS (5 Intrusion Policies)
- Zone-based policy: `outside`, `inside`, `it`, `corporate`, `guest`, `dmz`
- 11 Access Control Rules + Default Deny
- NAT/PAT for all internal VLANs
- Syslog → Wazuh, SNMPv3 → Cisco Prime

### Network Access Control — 802.1X + SSO
```
Supplicant (Windows Client — GPO SSO)
    └─► Authenticator (C3750X / WLC)
            └─► Authentication Server (FreeRADIUS · RPi-01)
                        └─► Identity Store (Samba AD · RPi-02)

Auth Success    : Dynamic VLAN (IT→V20, Staff→V30)
Auth Fail       : VLAN 40 (Guest)
Server Dead     : VLAN 20 (Fail-Open)
Server Alive    : Re-authenticate
```

### SIEM — Wazuh
- Agent-based + agentless syslog collection
- Sources: Cisco FTD · C9200L · C3750X · Honeypot · All servers
- MITRE ATT&CK framework mapping
- Custom decoders + rules for Cisco Syslog
- Active Response: Brute-force detection → auto-block + Discord alert
- File Integrity Monitoring + Vulnerability Detection

### Honeypot — DMZ (VLAN 100)
- Flask-based Honeypot v2.0 with fake login + SQL injection trap
- Exposed to internet via Cloudflare Tunnel
- All hits logged via Promtail → Loki → Grafana dashboard
- Isolated in VLAN 100, routed only through FTD policy

---

## Active Directory — GROUP1.CORP

**Domain Controller:** `raspberrypi.group1.corp` (RPi-02 · `10.1.10.20`)

```
Forest: group1.corp
  └── Domain: GROUP1.CORP
        ├── KDC (Kerberos Port 88) — Domain Join, GPO, File Share
        ├── LDAP (Port 389/636) — FreeRADIUS Group Lookup
        ├── DNS (Port 53) — SRV Records for DC
        ├── SMB (Port 445) — File Share + GPO Distribution
        ├── Users: 20 accounts
        ├── Groups: IT · HR · Finance · Staff · Domain Admins
        └── File Shares (NT ACL enforced)
              ├── IT_Dept      → GROUP1\IT only
              ├── HR_Dept      → GROUP1\HR only
              ├── Finance_Dept → GROUP1\Finance only
              └── Staff_Common → All Domain Users
```

**GPO Policies:**
| GPO | Function |
|-----|----------|
| Wired 802.1X SSO | Auto-authenticate LAN with AD credentials |
| Wireless 802.1X SSO | Auto-connect `Group01-Corporate Enterprise` |
| Drive Maps | Z: Staff, Y: IT, X: HR, W: Finance |
| Desktop Wallpaper | Enforce corporate wallpaper |

**Protocol Note:**
- **Kerberos** → Domain Join, GPO Apply, File Share (SMB3)
- **NTLM (ntlm_auth)** → 802.1X PEAP/MSCHAPv2 via FreeRADIUS + winbind

---

## EtherChannel / Port-channel

| Port-channel | Members | Protocol | Endpoints | VLANs |
|:------------:|---------|:--------:|-----------|-------|
| Po1 (L3 SW) | Gi1/0/37-40 (4p) | Static | L3 Switch ↔ WLC | All (1-59, 61-4094) |
| Po2 (L3 SW) | Gi1/0/45-47 (3p) | LACP | L3 Switch ↔ EWC Building 2 | 10,20,30,40,50,60,100 |
| Po3 (L3 SW) | Gi1/0/25-27 (3p) | Static | L3 Switch ↔ L2 PoE Switch | 1,10,20,30,40,100 |
| Po1 (L2 SW) | Gi1/0/42-44 (3p) | LACP | L2 PoE Switch ↔ L3 Switch | 10,20,30,40,50,60,100 |
| Po1 (FTD) | Eth1/1-3 (3p) | — | FTD ↔ L3 Switch | Sub-interfaces (V1,V20,V30,V40,V100) |

---

## ACL Summary

| ACL | Applied to | Policy |
|-----|:----------:|--------|
| ACL-V10-SERVER-IN | Vlan10 (in) | Allow Server → all Client VLANs + Internet |
| ACL-V20-IT-IN | Vlan20 (in) | IT → V10, V50, V60 ✅ / V30, V40 ❌ |
| ACL-V30-CORP-IN | Vlan30 (in) | Corp → V10 AD Ports only (DNS/Kerberos/LDAP/SMB) / Block rest |
| ACL-V40-GUEST-IN | Vlan40 (in) | Block all Internal / Allow HTTP/S + DNS only |
| RETURN-TO-FTD | PBR | Force return traffic through FTD (Asymmetric fix) |

---

## Observability

### NetFlow Pipeline
```
C9200L (V9) ──UDP 2055──► pmacct (RPi-02) ──► InfluxDB ──► Grafana
```
Applied on: Vlan10, Vlan20, Vlan40, Vlan60, Vlan100 (input + output)

### Log Pipeline
```
FTD Syslog ───────────────────┐
C9200L Syslog ────────────────┤
C3750X Syslog ────────────────┼──► Wazuh (10.1.10.30:514)
Honeypot (Promtail) ──────────┤
System logs (Promtail) ───────┼──► Loki (10.1.10.10:3100) ──► Grafana
All Servers (Wazuh Agent) ────┘
```

### Network Automation
- **Oxidized** — config backup every hour, Git-versioned diffs
- **NetBox** — source of truth for all devices, IPs, VLANs, cables, topology
- **Tailscale** — zero-config remote access overlay

---

## Service Map

| Service | Host | Endpoint | Access |
|---------|------|----------|--------|
| Firewall (FDM) | FIREPOWER-G1 | `https://10.1.50.20` | VLAN 50/10 |
| Cisco Prime | External | `https://172.31.0.102` | Intranet only |
| WLC GUI | WLC_G1 | `https://10.1.50.10` | VLAN 50 |
| EWC GUI | EWC-Active | `https://10.1.60.10` | VLAN 50/60 |
| Grafana | RPi-01 | `http://10.1.10.10:3000` | VLAN 10/20 |
| Loki | RPi-01 | `http://10.1.10.10:3100` | VLAN 10 |
| DaloRADIUS | RPi-01 | `http://10.1.10.10/daloradius` | VLAN 10/20 |
| FreeRADIUS | RPi-01 | `UDP :1812, :1813` | Network devices |
| DVWA | RPi-01 | `http://10.1.10.10:8080` | VLAN 10/20 |
| Samba AD DC | RPi-02 | `:88 / :389 / :445 / :636` | All internal |
| LDAP Account Manager | RPi-02 | `http://10.1.10.20/lam` | VLAN 10/20 |
| NetBox | RPi-02 | `http://10.1.10.20:8000` | VLAN 10/20 |
| Oxidized | RPi-02 | `http://10.1.10.20:8081` | VLAN 10 |
| InfluxDB | RPi-02 | `http://10.1.10.20:8086` | VLAN 10 |
| pmacct | RPi-02 | `UDP :2055` | L3 Switch |
| Wazuh Dashboard | Mac-Wazuh | `https://10.1.10.30` | VLAN 10/20 |
| Syslog Relay | Mac-Wazuh | `UDP :514` | Network devices |
| Honeypot | Mac-Honeypot | Public via Cloudflare Tunnel | Internet |
| Honeypot Dashboard | Mac-Honeypot | `http://10.1.100.10/secret` | VLAN 10/20 |

---

## Repository Structure

```
.
├── README.md
├── network-configs/
│   ├── FIREPOWER-G1          # FTD running-config
│   ├── L3_SW_G1              # C9200L running-config
│   ├── L2_SW_G1              # C3750X running-config
│   └── WLC                   # CT2504 running-config
├── infra/
│   ├── active-directory/     # Samba AD configs (smb.conf, GPO scripts)
│   └── radius/               # FreeRADIUS configs (mods, sites, inner-tunnel)
├── security/
│   ├── 802.1x-sso/           # GPO wired/wireless 802.1X SSO configs
│   └── honeypot/             # Flask Honeypot v2.0 + Docker Compose
├── wazuh/
│   ├── local_decoder.xml     # Custom decoders for Cisco Syslog
│   ├── local_rules.xml       # Custom rules (brute-force, Discord alert)
│   ├── syslog_relay.py       # UDP→Docker syslog forwarder
│   └── wazuh-docker/         # Docker Compose stack
├── docs/                     # Project documentation
├── Project_Documentation/    # Detailed per-device documentation
├── dataset_generator.py      # Traffic log simulator for Looker Studio
└── network_traffic_log.csv   # Generated sample dataset
```

---

## Quick Reference — SSH Access

| Server | IP | Username | Auth |
|--------|----|----------|------|
| RPi-01 | `10.1.10.10` | `admin` | SSH key / password |
| RPi-02 | `10.1.10.20` | `admin` | SSH key / password |
| Mac-Wazuh | `10.1.10.30` | `admin` | SSH key / password |
| L3 Switch | `10.1.50.1` | `admin` | SSH (VTY local) |
| L2 Switch | `10.1.50.2` | `admin` | SSH (VTY local) |

---

<div align="center">

**Built on physical hardware. Monitored in real-time. Zero compromises.**

```
Cisco FPR-2110  ·  C9200L  ·  C3750X  ·  AIR-CT2504  ·  C9120AXI
Raspberry Pi 4B  ·  Apple Mac Mini
Wazuh · Grafana · Loki · NetBox · Oxidized · Samba AD · FreeRADIUS
```

*Group 01 — CE, Prince of Songkla University*

</div>
