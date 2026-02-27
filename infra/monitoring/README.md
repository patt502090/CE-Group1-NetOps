# 📊 Monitoring Stack

- **IP:** `10.1.10.30` (หรือ Mac Mini IP)
- **Host:** Mac Mini
- **Services:** Grafana + SNMP Polling

## Overview

Monitoring stack สำหรับ:

- **Grafana:** Dashboard แสดง Network Metrics (SNMP), System Health
- **SNMP Exporter / Telegraf:** Poll SNMP data จากอุปกรณ์ Network
- **(Optional) Wazuh:** Log Analysis & SIEM

## SNMP Targets

| Device       | IP          | SNMP Version | Community / Auth |
| ------------ | ----------- | ------------ | ---------------- |
| L3 Switch    | `10.1.50.1` | v2c / v3     | `<CHANGE_ME>`    |
| L2 Switch    | `10.1.50.2` | v2c / v3     | `<CHANGE_ME>`    |
| WLC          | `10.1.50.4` | v2c / v3     | `<CHANGE_ME>`    |
| Firepower    | `10.1.50.5` | v2c / v3     | `<CHANGE_ME>`    |

## Deployment

```bash
docker compose up -d
```

## Access

| Service  | URL                           | Default Credentials |
| -------- | ----------------------------- | ------------------- |
| Grafana  | `http://10.1.10.30:3000`      | admin / admin       |
