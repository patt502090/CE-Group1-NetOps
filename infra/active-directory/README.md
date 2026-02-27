# 🏢 Samba4 Active Directory Domain Controller

- **IP:** `10.1.10.20`
- **Host:** Raspberry Pi 4 (Debian/Docker)
- **Domain:** `GROUP1.CORP`
- **NetBIOS:** `GROUP1`
- **Forest/Domain Level:** 2008_R2 (Samba4 default)

## Overview

Samba4 AD DC ทำหน้าที่เป็น:

1. **Domain Controller** — จัดการ user/group/computer accounts
2. **DNS Server** — Integrated DNS สำหรับ domain GROUP1.CORP
3. **NTLM Backend** — ให้ FreeRADIUS ใช้ `ntlm_auth` สำหรับ 802.1X authentication
4. **(Optional) LDAP** — สำหรับ Cisco FTD Realm Identity Policy

## Domain Structure

```
GROUP1.CORP (Forest Root)
├── OU=Staff
│   ├── CN=admin1
│   └── CN=staff1
├── OU=Students
│   └── CN=student1
├── OU=Computers
│   ├── CN=WLC
│   └── CN=RADIUS
└── OU=Service Accounts
    └── CN=svc-radius        # FreeRADIUS bind account
```

## Key Accounts

| Account      | Type    | Purpose                            |
| ------------ | ------- | ---------------------------------- |
| Administrator| Admin   | Domain admin (เปลี่ยน password!)    |
| svc-radius   | Service | FreeRADIUS ใช้สำหรับ ntlm_auth     |
| svc-ftd      | Service | Firepower Realm LDAP bind          |

## Deployment

```bash
docker compose up -d

# ตรวจสอบ domain status
docker exec samba4-ad samba-tool domain level show

# สร้าง user
docker exec samba4-ad samba-tool user create testuser P@ssw0rd123 \
    --given-name="Test" --surname="User"

# ลิสต์ users
docker exec samba4-ad samba-tool user list
```

## Integration with FreeRADIUS

FreeRADIUS ใช้ `ntlm_auth` เพื่อ verify MSCHAPv2 credentials ผ่าน Samba4:

```bash
# ทดสอบ ntlm_auth
ntlm_auth --request-nt-key \
    --domain=GROUP1 \
    --username=testuser \
    --password=P@ssw0rd123
```

## Files

```
active-directory/
├── README.md
├── docker-compose.yml
└── config/
    └── smb.conf               # Samba4 AD DC configuration
```
