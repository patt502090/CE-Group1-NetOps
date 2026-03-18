# 🚑 NetOps Group 1 — Troubleshooting & Essential Commands

---

## Part A: ปัญหาที่เจอ & วิธีแก้ (Lessons Learned)

### Case 1: Wi-Fi Corporate SSID — Auth ไม่ผ่าน (Timeout)

| | |
|---|---|
| **อาการ** | เกาะ SSID "Group01-Corporate Enterprise" → กรอก Username/Password → ค้าง → Timeout |
| **สาเหตุ** | ACL-V30-CORP-IN บน L3 Switch บล็อกทราฟฟิก RADIUS (UDP 1812/1813) จาก WLC → FreeRADIUS |
| **ทำไมเกิด** | WLC ส่ง RADIUS packet จาก corporate interface (10.1.30.10, V30) → L3 ACL deny ก่อนถึง RADIUS server (10.1.10.10) |
| **วิธีแก้** | เพิ่ม pin-hole ใน ACL-V30-CORP-IN: |

```
ip access-list extended ACL-V30-CORP-IN
 11 permit udp 10.1.30.0 0.0.0.255 10.1.10.0 0.0.0.255 eq 1812
 12 permit udp 10.1.30.0 0.0.0.255 10.1.10.0 0.0.0.255 eq 1813
```

| **ตรวจสอบ** | `show access-lists ACL-V30-CORP-IN` → ดูว่า line 11/12 มี match count เพิ่มขึ้น |

---

### Case 2: Ping / Web ติดๆ ดับๆ — Asymmetric Routing

| | |
|---|---|
| **อาการ** | Client (V20/V30) ping Server (V10) ได้บ้างไม่ได้บ้าง, เว็บโหลดช้าหรือ timeout |
| **สาเหตุ** | L3 Switch ฉลาดเกินไป — route ทราฟฟิก V10→V20 ตรงๆ โดยไม่ผ่าน FTD → FTD ไม่เห็นขาไป → drop ขากลับ (TCP state mismatch) |
| **วิธีแก้** | สร้าง PBR (route-map ASYM-FIX) บังคับทราฟฟิกจาก V10/V50/V60 ไปหา Client ต้องผ่าน FTD (next-hop 10.1.1.2) |
| **ตรวจสอบ** | `show route-map ASYM-FIX` + `show ip policy` บน SVI ที่ apply |

---

## Part B: Debug Flowchart — User Login ไม่ผ่าน

ใช้ flow นี้เวลาทีม debug ว่าทำไม User login ไม่เข้า:

```
[1] User เสียบสาย / เชื่อม Wi-Fi → ไม่ได้ IP หรือ Timeout
          │
          ├─── เช็คที่ RADIUS ก่อน (RPi 10.1.10.10)
          │    └─ radtest <user> <pass> 127.0.0.1 0 testing123
          │         ├── Access-Accept → RADIUS+AD ปกติ → ปัญหาอยู่ที่ Switch/WLC/ACL
          │         └── Access-Reject → ดู freeradius -X output:
          │              ├── "mschap: FAILED" → password ผิด หรือ ntlm_auth ไม่ทำงาน
          │              │    └─ ntlm_auth --username=<user> --password=<pass>
          │              │         ├── OK → mschap module config ผิด
          │              │         └── FAIL → password ผิด / AD service ล่ม
          │              │              └─ systemctl status samba-ad-dc
          │              ├── "ldap: bind failed" → เชื่อม AD ไม่ได้
          │              │    └─ ping 10.1.10.20 + samba-tool domain info 127.0.0.1
          │              └── "No LDAP-Group" → user ไม่อยู่ในกลุ่ม
          │                   └─ samba-tool group listmembers <group>
          │
          ├─── RADIUS OK แต่ Switch/WLC ไม่ assign VLAN
          │    ├── L2 Switch: show authentication sessions interface Gi1/0/X
          │    │    └── ดูว่า Status = Authz Success? VLAN = ?
          │    └── WLC: show client detail <MAC>
          │         └── ดูว่า VLAN Override = ? Policy Type = ?
          │
          └─── ได้ VLAN แล้วแต่ไม่มีเน็ต
               ├── show ip dhcp binding (L3) → ได้ IP ไหม?
               ├── ping 10.1.X.1 (FTD gateway) → ถึงไหม?
               └── show access-lists (L3) → โดน ACL deny ไหม?
```

---

## Part C: Essential Commands แยกตามอุปกรณ์

### 1. Samba AD (Raspberry Pi — 10.1.10.20)

| คำสั่ง | ใช้ทำอะไร |
|--------|----------|
| `samba-tool group listmembers IT` | ดูสมาชิกกลุ่ม IT |
| `samba-tool group listmembers HR` | ดูสมาชิกกลุ่ม HR |
| `samba-tool group listmembers Finance` | ดูสมาชิกกลุ่ม Finance |
| `samba-tool group listmembers Staff` | ดูสมาชิกกลุ่ม Staff |
| `samba-tool user create <username> <password>` | สร้าง user ใหม่ |
| `samba-tool group addmembers <group> <username>` | เพิ่ม user เข้ากลุ่ม |
| `samba-tool group removemembers <group> <username>` | ลบ user ออกจากกลุ่ม |
| `samba-tool user list` | แสดง user ทั้งหมด |
| `samba-tool domain info 127.0.0.1` | ตรวจสถานะ DC |
| `systemctl status samba-ad-dc` | เช็ค service สถานะ |

### 2. FreeRADIUS (Raspberry Pi — 10.1.10.10)

| คำสั่ง | ใช้ทำอะไร |
|--------|----------|
| `freeradius -X` | รัน debug mode (เห็นทุก step ของ Auth) |
| `service freeradius stop` | หยุด service ก่อนรัน -X |
| `radtest <user> <pass> 127.0.0.1 0 testing123` | ทดสอบ Auth จากเครื่อง RADIUS เอง |
| `radtest winnie.p PASSWORD 127.0.0.1 0 testing123` | ตัวอย่าง: ถ้าได้ `Access-Accept` = RADIUS+AD ทำงานปกติ |
| `wbinfo -u` | ดู user ทั้งหมดผ่าน winbind (ต้องเห็น domain users) |
| `wbinfo -g` | ดู group ทั้งหมดผ่าน winbind |
| `ntlm_auth --username=<user> --password=<pass>` | ทดสอบ ntlm_auth ตรงๆ (ข้าม RADIUS) |
| `cat /var/log/freeradius/radius.log` | ดู log file |

> **Debug tip:** รัน `freeradius -X` → ลอง login จากอุปกรณ์ → ดู output ว่า fail ตรงไหน:
> - `mschap: FAILED` → password ผิดหรือ ntlm_auth ไม่ทำงาน
> - `ldap: bind failed` → เชื่อม AD ไม่ได้
> - `post-auth: LDAP-Group ==` → ดูว่า match กลุ่มไหน

### 3. L2 Switch — POE_SW_G1 (802.1X)

| คำสั่ง | ใช้ทำอะไร |
|--------|----------|
| `show authentication sessions` | ดูสถานะ 802.1X ทุกพอร์ต (ใครได้ VLAN อะไร) |
| `show authentication sessions interface Gi1/0/1` | ดูเฉพาะพอร์ต |
| `show dot1x all summary` | สรุป 802.1X ทุกพอร์ต |
| `show ip dhcp snooping binding` | ดู DHCP binding table |
| `show ip dhcp snooping` | ดูสถานะ DHCP snooping |
| `show access-lists` | ดู hit count ของ ACL |
| `show vlan brief` | ดู VLAN ที่มี |
| `show interfaces trunk` | ดู trunk port ทั้งหมด |
| `show etherchannel summary` | ดูสถานะ Po1 |
| `clear authentication sessions interface Gi1/0/X` | บังคับ re-auth พอร์ตนั้น |

### 4. L3 Switch — L3_SW_G1

| คำสั่ง | ใช้ทำอะไร |
|--------|----------|
| `show ip interface brief` | ดู IP ทุก SVI |
| `show access-lists` | ดู ACL + hit count (ดูว่าทราฟฟิกโดน deny ที่กฎไหน) |
| `show access-lists ACL-V30-CORP-IN` | ดูเฉพาะ ACL ของ V30 |
| `show route-map ASYM-FIX` | ดูว่า PBR match กี่ packets |
| `show ip policy` | ดูว่า SVI ไหนใช้ PBR อยู่ |
| `show ip dhcp binding` | ดู DHCP lease ที่แจกไป |
| `show ip dhcp pool` | ดูสถานะ pool |
| `show etherchannel summary` | ดู Po1/Po2/Po3 สถานะ |
| `show flow monitor NETFLOW-MONITOR cache` | ดู NetFlow cache |
| `show logging` | ดู syslog |

### 5. WLC — WLC_G1 (CT2504)

| คำสั่ง | ใช้ทำอะไร |
|--------|----------|
| `show wlan summary` | ดู SSID ทั้งหมด + สถานะ |
| `show wlan 1` | ดูรายละเอียด WLAN 1 (Corporate) |
| `show wlan 2` | ดูรายละเอียด WLAN 2 (Guest) |
| `show client summary` | ดู client ที่เชื่อมต่ออยู่ |
| `show client detail <MAC>` | ดูรายละเอียด client (VLAN, Auth status) |
| `show interface summary` | ดู dynamic interfaces ทั้งหมด |
| `show radius summary` | ดู RADIUS server + สถานะ |
| `show radius auth statistics` | ดูสถิติ Auth success/fail |
| `show ap summary` | ดู AP ทั้งหมด |
| `show ap join stats summary all` | ดูว่า AP join สำเร็จไหม |
| `show lag summary` | ดูสถานะ LAG |
| `debug aaa all enable` | เปิด debug AAA (ดูปัญหา Auth) |
| `debug dot1x all enable` | เปิด debug 802.1X |

### 6. FTD — FIREPOWER-G1

| คำสั่ง (CLI / diagnostic mode) | ใช้ทำอะไร |
|-------------------------------|----------|
| `show access-list NGFW_ONBOX_ACL` | ดูกฎทั้งหมด + hit count |
| `show nat` | ดู NAT rules |
| `show xlate` | ดู NAT translation table ปัจจุบัน |
| `show conn` | ดู active connections |
| `show conn address 10.1.20.x` | ดู connection เฉพาะ IP |
| `show route` | ดู routing table |
| `show interface ip brief` | ดู interface + IP |
| `show logging` | ดู syslog (denied traffic จะอยู่ที่นี่) |
| `packet-tracer input it tcp 10.1.20.100 12345 10.1.10.10 80` | จำลองทราฟฟิก → ดูว่าผ่านกฎไหน/โดน drop ตรงไหน |

> **packet-tracer** เป็นเครื่องมือสำคัญที่สุดบน FTD — จำลอง packet ว่าจะผ่านหรือโดน drop โดยไม่ต้องมี traffic จริง

---

## Part D: Quick Reference — IP & Credentials

| อุปกรณ์ | IP | Access | หมายเหตุ |
|---------|-----|--------|----------|
| L3 Switch | 10.1.50.1 | SSH (admin) | |
| L2 Switch | 10.1.50.2 | SSH (admin) | |
| WLC | 10.1.50.10 | HTTPS / SSH (admin) | |
| FTD | 10.1.1.2 (inside) | FDM HTTPS / CLI | |
| FreeRADIUS | 10.1.10.10 | SSH (pi user) | Debug: `freeradius -X` |
| Samba AD | 10.1.10.20 | SSH (pi user) | Domain: GROUP1.CORP |
| Syslog Server | 10.1.10.30 | — | รับ log จากทุกอุปกรณ์ |
| SNMP Manager | 172.31.0.102 | — | Cisco Prime / NMS |
| Grafana | 10.1.10.20:2055 | — | NetFlow dashboard |
| ElastiFlow | 10.1.50.35:2055 | — | NetFlow analytics |
