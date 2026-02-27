# 🖥️ Infrastructure Services

รวมการตั้งค่าและ Deployment ของ Server Services ทั้งหมดใน VLAN 10 (SERVER) — `10.1.10.0/24`

## 📋 Service Inventory

| Service              | IP Address     | Host           | Platform           | Status |
| -------------------- | -------------- | -------------- | ------------------ | ------ |
| FreeRADIUS (802.1X)  | `10.1.10.10`   | Raspberry Pi 4 | Docker / Debian    | 🚧     |
| Samba4 AD DC         | `10.1.10.20`   | Raspberry Pi 4 | Docker / Debian    | 🚧     |
| Grafana + SNMP       | `10.1.10.30`   | Mac Mini       | Docker             | 📋     |

## 🗂️ Directory Structure

```
infra/
├── radius/              # FreeRADIUS — 802.1X Authentication Server
├── active-directory/    # Samba4 AD Domain Controller (GROUP1.CORP)
└── monitoring/          # Grafana Dashboard + SNMP Polling
```

## 🚀 Quick Start

```bash
# Deploy RADIUS server
cd radius && docker compose up -d

# Deploy AD Domain Controller
cd active-directory && docker compose up -d

# Deploy Monitoring stack
cd monitoring && docker compose up -d
```

## 🔗 Dependencies

```
                    ┌──────────────┐
                    │  Samba4 AD   │
                    │ 10.1.10.20   │
                    │ (GROUP1.CORP)│
                    └──────┬───────┘
                           │ NTLM Auth (ntlm_auth)
                           ▼
┌──────────┐       ┌──────────────┐       ┌────────────┐
│  WLC     │──────▶│  FreeRADIUS  │◀──────│ L3 Switch  │
│ (NAS)    │ 1812  │ 10.1.10.10   │ 1812  │   (NAS)    │
└──────────┘       └──────────────┘       └────────────┘
                           │
                    EAP-PEAP/MSCHAPv2
                           │
                    ┌──────▼───────┐
                    │   Clients    │
                    │ (VLAN 30/40) │
                    └──────────────┘
```
