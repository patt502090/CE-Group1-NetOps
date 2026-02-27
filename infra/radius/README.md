# 🔐 FreeRADIUS — 802.1X Authentication Server

- **IP:** `10.1.10.10`
- **Host:** Raspberry Pi 4 (Debian/Docker)
- **Domain:** GROUP1.CORP (ใช้ Samba4 AD backend)
- **Port:** 1812/UDP (Authentication), 1813/UDP (Accounting)

## Overview

FreeRADIUS ทำหน้าที่เป็น Authentication Server สำหรับ:

- **VLAN 30 (STAFF-WIFI):** 802.1X EAP-PEAP/MSCHAPv2 — authenticate ผ่าน Samba4 AD
- **Wired 802.1X** (ถ้าเปิดใช้งาน): ผ่าน L2/L3 Switch

## Architecture

```
WiFi Client ──▶ WLC (NAS) ──▶ FreeRADIUS ──▶ Samba4 AD (ntlm_auth)
                                  │
                            EAP-PEAP/MSCHAPv2
                            (TLS Tunnel + NTLM)
```

## NAS Clients

| Device      | IP           | Shared Secret       | Purpose         |
| ----------- | ------------ | ------------------- | --------------- |
| WLC         | `10.1.50.4`  | `<CHANGE_ME>`       | WiFi 802.1X     |
| L3 Switch   | `10.1.50.1`  | `<CHANGE_ME>`       | Wired 802.1X    |
| Firepower   | `10.1.50.5`  | `<CHANGE_ME>`       | Identity Policy |

## Deployment

```bash
docker compose up -d
```

## Troubleshooting

```bash
# ทดสอบ authentication
docker exec freeradius radtest testuser testpass 127.0.0.1 0 testing123

# Debug mode
docker exec freeradius freeradius -X

# ดู log
docker logs -f freeradius
```

## Files

```
radius/
├── README.md
├── docker-compose.yml
└── config/
    ├── clients.conf            # NAS client definitions
    ├── radiusd.conf            # Main FreeRADIUS configuration
    └── mods-available/
        └── eap                 # EAP method config (PEAP/MSCHAPv2)
```
