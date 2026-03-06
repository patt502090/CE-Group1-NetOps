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
                                             │
                              ┌──────────────▼───────────────┐
                              │      FIREPOWER-G1             │
                              │   Cisco FPR-2110 · NGFW       │
                              │   IPS · NAT · URL Filter      │
                              │   Zone: outside/inside/dmz    │
                              └──────────────┬───────────────┘
                                        LAG Po3 (2x1G)
                              ┌──────────────▼───────────────┐
                              │        L3_SW_G1               │
                              │  Cisco C9200L · Core Switch   │
                              │  SVIs · NetFlow Export        │
                              └───────┬──────────┬───────────┘
                           LAG Po2    │          │    LAG Po1
                    ┌──────────▼──┐   │   ┌──────▼──────────┐
                    │  POE_SW_G1  │   │   │     WLC_G1       │
                    │  C3750X-48P │   │   │  AIR-CT2504-K9   │
                    │  802.1X Auth│   │   │  SSID x 2        │
                    └─────────────┘   │   └─────────────────┘
                                      │
                         ┌────────────┼──────────────────────┐
                         │            │                      │
                  ┌──────▼──┐  ┌──────▼──┐  ┌───────────────▼──┐
                  │  RPi-01 │  │  RPi-02 │  │   Mac-Wazuh      │
                  │VLAN10   │  │VLAN10   │  │   VLAN10         │
                  │.10      │  │.20 (DC) │  │   .30            │
                  └─────────┘  └─────────┘  └──────────────────┘
                                                  ┌────────────────┐
                                                  │ Mac-Honeypot   │
                                                  │ VLAN100 · DMZ  │
                                                  │ .10 · Internet │
                                                  └────────────────┘
```

---

## Network Segmentation

| VLAN | Name | Subnet | Gateway | Description |
|:----:|------|--------|---------|-------------|
| **10** | SERVER | `10.1.10.0/24` | `10.1.10.1` | Internal servers — static IPs |
| **20** | EMPLOYEE | `10.1.20.0/24` | `10.1.20.1` | Wired employee access · 802.1X enforced |
| **30** | STAFF-WIFI | `10.1.30.0/24` | `10.1.30.1` | Corporate wireless · WPA2-Enterprise |
| **40** | GUEST-WIFI | `10.1.40.0/24` | `10.1.40.1` | Guest wireless · isolated |
| **50** | MGMT | `10.1.50.0/24` | `10.1.50.1` | Network device management |
| **60** | EWC-MGMT | `10.1.60.0/24` | `10.1.60.1` | Building 2 wireless management |
| **100** | DMZ | `10.1.100.0/24` | `10.1.100.1` | Public-facing · honeypot isolated |

---

## Hardware Inventory

### Network Infrastructure

| Device | Model | Version | Management IP | Role |
|--------|-------|---------|--------------|------|
| FIREPOWER-G1 | Cisco FPR-2110 | NGFW v7.4.2 | `10.1.50.20` | Next-gen Firewall · IPS · NAT |
| L3_SW_G1 | Cisco C9200L-48T-4G | IOS-XE 17.9.4 | `10.1.50.1` | Core L3 · NetFlow · DHCP |
| POE_SW_G1 | Cisco C3750X-48P | IOS 15.2(4)E6 | `10.1.50.2` | PoE Access · 802.1X Authenticator |
| WLC_G1 | Cisco AIR-CT2504-K9 | WLC 8.5.182 | `10.1.50.10` | Wireless Controller · Dual SSID |

### Servers

| Device | Model | IP | Role |
|--------|-------|----|------|
| RPi-01 | Raspberry Pi 4B | `10.1.10.10` | Grafana · Loki · DVWA · FreeRADIUS |
| RPi-02 | Raspberry Pi 4B | `10.1.10.20` | Samba AD DC · NetBox · Oxidized · InfluxDB · NetFlow |
| Mac-Wazuh | Apple Mac Mini | `10.1.10.30` | Wazuh Manager + Indexer + Dashboard |
| Mac-Honeypot | Apple Mac Mini | `10.1.100.10` | Honeypot v2.0 · Cloudflare Tunnel · DMZ |

---

## Security Stack

### Perimeter — Cisco FPR-2110 (FTD)
- Stateful next-generation firewall with IPS signatures
- Zone-based policy: `outside → inside`, `outside → dmz`, `inside → dmz`
- NAT/PAT for all internal VLANs
- URL filtering and application visibility
- Syslog forwarding to Wazuh

### Network Access Control — 802.1X
```
Supplicant (endpoint)
    └─► Authenticator (C3750X / WLC)
            └─► Authentication Server (FreeRADIUS · RPi-01)
                        └─► Identity Store (Samba AD · RPi-02)

Fail-open VLAN : VLAN40 (Guest)
Success VLAN   : VLAN20 (Employee) / VLAN30 (Staff-WiFi)
```

### SIEM — Wazuh
- Agent-based + agentless syslog collection
- Sources: Cisco FTD · C9200L · Honeypot · All servers
- MITRE ATT&CK framework mapping
- File Integrity Monitoring + Vulnerability Detection

### Honeypot — DMZ
- Flask-based Honeypot v2.0 on Mac Mini
- Exposed to internet via Cloudflare Tunnel
- All hits logged via Promtail → Loki → Grafana Attack Map
- Isolated in VLAN100, routed only through FTD policy

---

## Active Directory — GROUP1.CORP

**Domain Controller:** `raspberrypi.group1.corp` (RPi-02 · `10.1.10.20`)

```
Forest: group1.corp
  └── Domain: GROUP1.CORP
        ├── Users: 20 accounts
        ├── Groups: IT · HR · Finance · Staff · Domain Admins
        └── File Shares (ACL-enforced)
              ├── IT_Dept      → GROUP1\IT only
              ├── HR_Dept      → GROUP1\HR only
              ├── Finance_Dept → GROUP1\Finance only
              └── Staff_Common → All Domain Users
```

**GPO — Map Network Drives** (auto-maps on login)

```
Z: \\10.1.10.20\Staff_Common   → everyone
Y: \\10.1.10.20\IT_Dept        → IT group only
X: \\10.1.10.20\HR_Dept        → HR group only
W: \\10.1.10.20\Finance_Dept   → Finance group only
```

---

## Observability

### NetFlow Pipeline
```
C9200L ──UDP 2055──► pmacct (RPi-02) ──► InfluxDB ──► Grafana
```

### Log Pipeline
```
FTD Syslog ───────────────────┐
C9200L Syslog ────────────────┤
Honeypot (Promtail) ──────────┼──► Loki ──► Grafana
System logs (Promtail) ───────┘        ──► Wazuh
```

### Network Automation
- **Oxidized** — config backup every 6h, Git-versioned diffs
- **NetBox** — source of truth for all devices, IPs, VLANs, cables
- **Tailscale** — zero-config remote access overlay

---

## Service Map

| Service | Host | Endpoint |
|---------|------|----------|
| Grafana | RPi-01 | `http://10.1.10.10:3000` |
| NetBox | RPi-02 | `http://10.1.10.20:8000` |
| Oxidized | RPi-02 | `http://10.1.10.20:8081` |
| Wazuh Dashboard | Mac-Wazuh | `https://10.1.10.30` |
| DVWA | RPi-01 | `http://10.1.10.10:8080` |
| Loki | RPi-01 | `http://10.1.10.10:3100` |
| InfluxDB | RPi-02 | `http://10.1.10.20:8086` |
| NetFlow Collector | RPi-02 | `UDP :2055` |
| FreeRADIUS | RPi-01 | `UDP :1812` |
| Samba AD DC | RPi-02 | `:389 / :445 / :88` |
| Honeypot | Mac-Honeypot | Public via Cloudflare Tunnel |
| Topology Map | RPi-01 | `http://10.1.10.10/topology.html` |

---

## Repository Structure

```
.
├── README.md
├── topology/
│   └── group1-topology.html        # Interactive network diagram
├── netbox/
│   ├── populate-devices.sh
│   ├── populate-vlans.sh
│   └── populate-cables.sh
├── samba/
│   ├── smb.conf
│   └── map_drives.bat              # GPO logon script
├── configs/
│   ├── firewall/
│   ├── l3-switch/
│   ├── l2-switch/
│   └── wlc/
├── grafana/
│   └── dashboards/
└── wazuh/
    └── rules/
```

---

<div align="center">

**Built on physical hardware. Monitored in real-time. Zero compromises.**

```
Cisco FPR-2110  ·  C9200L  ·  C3750X  ·  AIR-CT2504
Raspberry Pi 4B  ·  Apple Mac Mini
Wazuh · Grafana · Loki · NetBox · Oxidized · Samba AD
```

*Group 01 — Enterprise Network & Security Infrastructure*

</div>
