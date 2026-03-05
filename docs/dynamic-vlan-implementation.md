# Dynamic VLAN by AD Group — Step-by-Step Implementation

> **Date:** 2026-03-04  
> **Goal:** แยก VLAN อัตโนมัติตาม AD Group ทั้ง LAN (802.1X) และ WiFi (AAA Override)

---

## สรุป VLAN Table (Final)

| VLAN | Name | Subnet | GW | FW nameif | ใครได้ |
|------|------|--------|----|-----------|--------|
| 1 | TRANSIT | 10.1.1.0/30 | L3=.1, FW=.2 | `inside` | L3↔FW link |
| 10 | SERVER | 10.1.10.0/24 | **L3=.1** | — | RPi, AD, RADIUS |
| 20 | PRIVILEGED | 10.1.20.0/24 | **FW=.1**, L3=.2 | `employee` | IT group |
| 30 | CORPORATE | 10.1.30.0/24 | **FW=.1**, L3=.2 | `corporate` ★NEW | HR/Finance/Staff |
| 40 | GUEST | 10.1.40.0/24 | **FW=.1** | `guest` | No-auth |
| 50 | MGMT | 10.1.50.0/24 | **L3=.1** | — | Switch, WLC, AP |
| 60 | WIRELESS-MGMT | 10.1.60.0/24 | **L3=.1** | — | AP Bldg2, EWC |
| 100 | DMZ | 10.1.100.0/24 | **FW=.1** | `dmz` | Honeypot |

---

## P0 — Step 1: Firepower FTD — สร้าง Po1.30 `corporate`

> **Risk:** Zero — ยังไม่มี VLAN 30 traffic วิ่งผ่าน FW  
> **Device:** FIREPOWER-G1 (FPR-2110)  
> **Method:** FMC GUI (recommended) หรือ FlexConfig

### Option A: ผ่าน FMC GUI (แนะนำ)

```
FMC > Devices > Device Management > FIREPOWER-G1 > Interfaces

1. คลิก "Add Interfaces" > "Sub Interface"
   - Interface: Port-channel1
   - Sub Interface ID: 30
   - VLAN ID: 30
   - Name: corporate
   - Security Zone: สร้างใหม่ "corporate-zone"
   - IPv4 > Static > 10.1.30.1/24

2. Deploy
```

### Option B: FlexConfig / diagnostic CLI

```
! ===== เข้า diagnostic CLI =====
! FMC > Devices > FIREPOWER-G1 > CLI
! หรือ SSH เข้า FTD > system support diagnostic-cli

! ----- 1.1 สร้าง subinterface -----
configure terminal

interface Port-channel1.30
 vlan 30
 nameif corporate
 security-level 0
 ip address 10.1.30.1 255.255.255.0
 no shutdown
exit

! ----- 1.2 สร้าง network object -----
object network Corporate-Network
 subnet 10.1.30.0 255.255.255.0
exit

! ----- 1.3 NAT (corporate → outside) -----
object network Corporate-Network
 nat (corporate,outside) dynamic interface
exit

! ----- 1.4 MTU -----
mtu corporate 1500

! ----- 1.5 Monitor interface -----
monitor-interface corporate

! ----- 1.6 DNS Allow สำหรับ corporate -----
! (เพิ่มก่อน DefaultActionRule)
access-list NGFW_ONBOX_ACL line 1 remark rule-id 268435480: L5 RULE: Allow-DNS-For-Corporate
access-list NGFW_ONBOX_ACL line 2 advanced permit object-group |acSvcg-268435471 ifc corporate object Corporate-Network any rule-id 268435480

! ----- 1.7 Allow Corporate → Internet -----
! (เพิ่มก่อน DefaultActionRule)
access-list NGFW_ONBOX_ACL line 3 remark rule-id 268435481: L5 RULE: Allow-Internet-Corporate
access-list NGFW_ONBOX_ACL line 4 advanced permit ip ifc corporate any ifc outside any rule-id 268435481 event-log both

! ----- 1.8 Allow Internal Ping (corporate ↔ inside ↔ dmz) -----
access-list NGFW_ONBOX_ACL line 5 advanced permit icmp ifc corporate any ifc inside any rule-id 268435473
access-list NGFW_ONBOX_ACL line 6 advanced permit icmp ifc inside any ifc corporate any rule-id 268435473
access-list NGFW_ONBOX_ACL line 7 advanced permit icmp ifc corporate any ifc dmz any rule-id 268435473

end
write memory
```

### Verify Step 1

```
show interface Port-channel1.30
! ควรเห็น: nameif corporate, ip 10.1.30.1, line protocol up

show nameif
! ควรเห็น corporate ใน list

show nat
! ควรเห็น Corporate-Network → dynamic interface

show access-list NGFW_ONBOX_ACL | include corporate
! ควรเห็น rules ที่เพิ่ม
```

---

## P0 — Step 2: Firepower FTD — Rename nameif `employee` → `privileged`

> **Risk:** Low-Medium — ต้อง update ทุก ACL/NAT/route ที่อ้าง `employee`  
> **⚠️ WARNING:** ถ้าใช้ FMC จัดการ → **ทำผ่าน FMC GUI เท่านั้น** (rename interface name)  
> FMC จะ auto-update ACL refs ทั้งหมดเมื่อ Deploy  
> ถ้าใช้ CLI แก้จะ conflict กับ FMC

### Option A: ผ่าน FMC GUI (แนะนำ — กด deploy ครั้งเดียว)

```
FMC > Devices > Device Management > FIREPOWER-G1 > Interfaces
  > คลิก Port-channel1.20
  > เปลี่ยน Name: employee → privileged
  > เปลี่ยน Security Zone: employee-zone → privileged-zone (สร้างใหม่ หรือ rename)
  > Save
  
FMC > Objects > Object Management
  > เปลี่ยนชื่อ "Employee-Network" → "Privileged-Network" (optional — cosmetic)

FMC > Policies > Access Control > NGFW_Access_Policy
  > ทุก rule ที่อ้าง employee-zone → เปลี่ยนเป็น privileged-zone
  > Rules ที่ต้องแก้:
    - Allow-DNS-For-Employee → Allow-DNS-For-Privileged (zone: privileged-zone)
    - Allow_Outside_to_DMZ → เปลี่ยน src zone employee → privileged
    - ALLOW-INTERNET → เปลี่ยน src zone employee → privileged
    - Allow-Internal-Ping → เปลี่ยน zone employee → privileged
    - block HR group → ถ้าอ้าง zone ให้เปลี่ยน

FMC > Policies > NAT
  > Employee-Network NAT → เปลี่ยน interface employee → privileged

Deploy
```

### Option B: ผ่าน CLI (ถ้าไม่ใช้ FMC)

```
! ⚠️ ทำ MAINTENANCE WINDOW — ต้อง clear ACL ที่อ้าง employee ก่อน rename

configure terminal

! ----- 2.1 ลบ ACL ที่อ้าง employee (ต้องลบก่อน rename) -----
! บันทึก ACL เดิมไว้ก่อน:
show access-list NGFW_ONBOX_ACL | include employee
! copy output ไว้ !!!

! ลบทีละ line (entry ที่อ้าง ifc employee):
no access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435471 ifc employee object Employee-Network any rule-id 268435471
no access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435460 ifc employee any ifc dmz object-group |acDestNwg-268435460 rule-id 268435460 event-log both
no access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435459 ifc employee any ifc outside any rule-id 268435459 event-log both
no access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc dmz any ifc employee any rule-id 268435473
no access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc employee any ifc dmz any rule-id 268435473
no access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc employee any ifc employee any rule-id 268435473
no access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc employee any ifc inside any rule-id 268435473
no access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc inside any ifc employee any rule-id 268435473

! ----- 2.2 ลบ NAT ที่อ้าง employee -----
object network Employee-Network
 no nat (employee,outside) dynamic interface
exit

! ----- 2.3 ลบ mtu, monitor, ip-client -----
no mtu employee 1500
no monitor-interface employee
no ip-client employee
no ip-client employee ipv6

! ----- 2.4 Rename interface -----
interface Port-channel1.20
 nameif privileged
exit

! ----- 2.5 เพิ่ม ACL กลับ (เปลี่ยน employee → privileged) -----
! สร้าง object ใหม่ (เปลี่ยนชื่อ)
object network Privileged-Network
 subnet 10.1.20.0 255.255.255.0
exit

! DNS
access-list NGFW_ONBOX_ACL remark rule-id 268435471: L5 RULE: Allow-DNS-For-Privileged
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435471 ifc privileged object Privileged-Network any rule-id 268435471

! Outside to DMZ (from privileged)
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435460 ifc privileged any ifc dmz object-group |acDestNwg-268435460 rule-id 268435460 event-log both

! Internet
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435459 ifc privileged any ifc outside any rule-id 268435459 event-log both

! Ping (privileged ↔ dmz ↔ inside)
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc dmz any ifc privileged any rule-id 268435473
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc privileged any ifc dmz any rule-id 268435473
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc privileged any ifc privileged any rule-id 268435473
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc privileged any ifc inside any rule-id 268435473
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc inside any ifc privileged any rule-id 268435473

! Ping (privileged ↔ corporate)
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc privileged any ifc corporate any rule-id 268435473
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435473 ifc corporate any ifc privileged any rule-id 268435473

! ----- 2.6 NAT กลับ -----
object network Privileged-Network
 nat (privileged,outside) dynamic interface
exit

! ----- 2.7 MTU, monitor, ip-client -----
mtu privileged 1500
monitor-interface privileged
ip-client privileged
ip-client privileged ipv6

end
write memory
```

### Verify Step 2

```
show nameif
! ควรเห็น: privileged (VLAN 20), corporate (VLAN 30), guest, dmz, inside, outside

show interface Port-channel1.20
! ควรเห็น: nameif privileged

show access-list NGFW_ONBOX_ACL | include privileged
! ควรเห็น rules ทั้งหมดที่ย้ายมา

show nat | include privileged
! dynamic (privileged,outside) ...

! ทดสอบ: client ใน VLAN 20 ยัง ping 8.8.8.8 ได้
! ทดสอบ: client ใน VLAN 20 ยังเข้า internet ได้
```

---

## P1 — Step 3: L3 Core Switch — เพิ่ม VLAN 30 ลง Po3 trunk

> **Risk:** Zero — เพิ่ม VLAN ที่ allowed บน trunk ไปยัง FW  
> **Device:** L3_SW_G1 (C9200L)

```
L3_SW_G1# configure terminal

! ----- 3.1 ตั้งชื่อ VLAN (cosmetic) -----
vlan 20
 name PRIVILEGED
exit
vlan 30
 name CORPORATE
exit
vlan 40
 name GUEST
exit
vlan 60
 name WIRELESS-MGMT
exit

! ----- 3.2 เพิ่ม VLAN 30 ลง Port-channel3 (trunk ไป FW) -----
interface Port-channel3
 switchport trunk allowed vlan 1,10,20,30,40,100
!                                    ^^ เพิ่ม 30
exit

end
write memory
```

### Verify Step 3

```
show vlan brief
! ควรเห็น VLAN 20=PRIVILEGED, 30=CORPORATE, 40=GUEST, 60=WIRELESS-MGMT

show interfaces trunk | include Po3
! Vlans allowed: 1,10,20,30,40,100

! จาก FW verify:
show interface Port-channel1.30
! line protocol up (ถ้า L3 trunk ส่ง VLAN 30 มาแล้ว)
```

---

## P1 — Step 4: L3 Core Switch — SVI 30 + DHCP

> **Risk:** Low — WiFi staff (VLAN 30) จะย้าย GW จาก L3(.1) → FW(.1)  
> **⚠️ ทำตอนดึก** — user ที่ต่อ WiFi VLAN 30 จะ disconnect ชั่วคราว

```
L3_SW_G1# configure terminal

! ----- 4.1 เปลี่ยน SVI 30 IP (.1 → .2) -----
! เดิม: ip address 10.1.30.1 → gateway อยู่ที่ L3
! ใหม่: ip address 10.1.30.2 → gateway ย้ายไป FW (10.1.30.1)
interface Vlan30
 no ip address
 ip address 10.1.30.2 255.255.255.0
exit

! ----- 4.2 แก้ DHCP pool STAFF -----
! gateway ยังชี้ 10.1.30.1 (แต่ตอนนี้ .1 = FW แล้ว ✓)
! เพิ่ม AD DNS
ip dhcp pool STAFF
 default-router 10.1.30.1
 dns-server 10.1.10.20 172.30.0.4
exit

! ----- 4.3 เพิ่ม ip helper-address บน SVI 30 (ถ้ายังไม่มี) -----
! DHCP relay — L3 ส่ง DHCP request จาก VLAN 30 ไปหา DHCP server
! (ถ้า DHCP pool อยู่บน L3 เอง → ไม่ต้อง helper เพราะ L3 serve เอง)
! *** กรณีนี้ L3 มี DHCP pool STAFF อยู่แล้ว → ไม่ต้องเพิ่ม helper ***

! ----- 4.4 ACL VLAN30-IN (เหมือน VLAN20-IN) -----
ip access-list extended VLAN30-IN
 10 remark === Allow to Firewall ===
 10 permit ip any host 10.1.1.2
 20 remark === Allow to FW GW ===
 20 permit ip any host 10.1.30.1
 30 remark === Allow DNS to AD ===
 30 permit udp any host 10.1.10.20 eq 53
 40 remark === Block Internal ===
 40 deny ip any 10.1.0.0 0.0.255.255
 50 remark === Allow Internet ===
 50 permit ip any any
exit

interface Vlan30
 ip access-group VLAN30-IN in
exit

end
write memory
```

### Verify Step 4

```
show ip interface brief | include Vlan30
! Vlan30  10.1.30.2  YES manual  up  up

show ip dhcp pool STAFF
! Network 10.1.30.0/24, Default Router 10.1.30.1

! ทดสอบ: manual set port VLAN 30 บน L2 switch
! (L2 ยังไม่มี 802.1X — set static VLAN เพื่อทดสอบ)
!
! บน L2 switch:
!   interface Gi1/0/1
!    switchport access vlan 30
!
! Client ควร:
!  - ได้ DHCP IP 10.1.30.x
!  - Default GW = 10.1.30.1 (FW)
!  - ping 8.8.8.8 ได้ (ผ่าน FW → outside)
!  - ping 10.1.10.20 ได้ (DNS/AD)
!
! เสร็จแล้วเปลี่ยน port กลับ:
!   interface Gi1/0/1
!    switchport access vlan 20
```

---

## P2 — Step 5: FreeRADIUS — เพิ่ม L2 switch เป็น NAS client

> **Risk:** Zero — เพิ่ม client entry, L2 ยังไม่ส่ง RADIUS request  
> **Device:** rasberrypi-888 (10.1.10.10)

```bash
# SSH เข้า 10.1.10.10
ssh admin@10.1.10.10     # หรือ via Tailscale: ssh admin@100.92.40.11

# ----- 5.1 Backup config -----
sudo cp /etc/freeradius/3.0/clients.conf /etc/freeradius/3.0/clients.conf.bak.$(date +%Y%m%d)

# ----- 5.2 เพิ่ม L2 Switch เป็น NAS client -----
sudo tee -a /etc/freeradius/3.0/clients.conf << 'EOF'

# ===== L2 PoE Switch (802.1X wired) =====
client L2_PoE_Switch {
    ipaddr = 10.1.50.2
    secret = Rad1us_L2SW!
    nastype = cisco
    shortname = POE_SW_G1
}

# ===== L3 Core Switch (802.1X wired — ถ้าเปิดใช้) =====
client L3_Core_Switch {
    ipaddr = 10.1.50.1
    secret = Rad1us_L3SW!
    nastype = cisco
    shortname = L3_SW_G1
}
EOF

# ----- 5.3 Test config syntax -----
sudo freeradius -XC 2>&1 | tail -5
# ควรเห็น: Configuration appears to be OK

# ----- 5.4 Restart FreeRADIUS -----
# ถ้ารัน debug mode:
#   กด Ctrl+C ก่อน แล้ว:
sudo freeradius -X &
# หรือ systemd:
sudo systemctl restart freeradius
```

---

## P2 — Step 6: FreeRADIUS — Dynamic VLAN logic ตาม AD Group

> **Risk:** Zero — ยังไม่มี device ส่ง 802.1X request ที่ trigger logic นี้  
> **Device:** rasberrypi-888 (10.1.10.10)

### 6.1 ตรวจสอบ LDAP module

```bash
# ดูว่า ldap module enabled หรือยัง
ls -la /etc/freeradius/3.0/mods-enabled/ | grep ldap

# ถ้าไม่มี:
sudo ln -s /etc/freeradius/3.0/mods-available/ldap /etc/freeradius/3.0/mods-enabled/ldap
```

### 6.2 แก้ LDAP module (ให้ query group membership)

```bash
sudo cp /etc/freeradius/3.0/mods-available/ldap /etc/freeradius/3.0/mods-available/ldap.bak.$(date +%Y%m%d)
sudo nano /etc/freeradius/3.0/mods-available/ldap
```

ตรวจสอบว่ามี config นี้อยู่ (key sections):

```
ldap {
    server   = '10.1.10.20'
    port     = 389
    identity = 'CN=radius_svc,CN=Users,DC=group1,DC=corp'
    password = '<RADIUS_SVC_PASSWORD>'

    base_dn  = 'DC=group1,DC=corp'

    user {
        base_dn   = "CN=Users,${..base_dn}"
        filter    = "(sAMAccountName=%{%{Stripped-User-Name}:-%{User-Name}})"
        scope     = 'sub'
    }

    group {
        base_dn         = "CN=Users,${..base_dn}"
        filter          = "(objectClass=group)"
        scope           = 'sub'
        membership_filter = "(|(member=%{control:Ldap-UserDn})(memberOf=%{control:Ldap-UserDn}))"
        membership_attribute = 'memberOf'
        cacheable_name  = yes
        cacheable_dn    = yes
    }

    options {
        chase_referrals = yes
        rebind          = yes
    }

    pool {
        start   = ${thread[pool].start_servers}
        min     = ${thread[pool].min_spare_servers}
        max     = ${thread[pool].max_servers}
        spare   = ${thread[pool].max_spare_servers}
        uses    = 0
        lifetime = 0
        idle_timeout = 60
    }
}
```

### 6.3 แก้ inner-tunnel (post-auth VLAN assignment)

```bash
sudo cp /etc/freeradius/3.0/sites-available/inner-tunnel /etc/freeradius/3.0/sites-available/inner-tunnel.bak.$(date +%Y%m%d)
sudo nano /etc/freeradius/3.0/sites-available/inner-tunnel
```

ใน section `authorize { }` — ตรวจว่า `ldap` อยู่ก่อน `mschap`:

```
authorize {
    filter_username
    suffix
    eap {
        ok = return
    }
    files
    -sql
    ldap                    # ← ต้องมี: lookup user + group จาก AD
    mschap
    expiration
    logintime
    pap
}
```

แก้ section `post-auth { }` — **เพิ่ม VLAN assignment logic**:

```
post-auth {

    # ===== Dynamic VLAN Assignment by AD Group =====
    #
    # IT group       → VLAN 20 (PRIVILEGED)  — full access
    # HR group       → VLAN 30 (CORPORATE)   — restricted
    # Finance group  → VLAN 30 (CORPORATE)   — restricted
    # Staff group    → VLAN 30 (CORPORATE)   — restricted
    # (default)      → VLAN 30 (CORPORATE)   — auth passed but no specific group
    #

    if (LDAP-Group == "IT") {
        update reply {
            Tunnel-Type := VLAN
            Tunnel-Medium-Type := IEEE-802
            Tunnel-Private-Group-Id := "20"
        }
        update reply {
            Reply-Message := "Welcome IT - VLAN 20 (Privileged)"
        }
    }
    elsif (LDAP-Group == "HR") {
        update reply {
            Tunnel-Type := VLAN
            Tunnel-Medium-Type := IEEE-802
            Tunnel-Private-Group-Id := "30"
        }
        update reply {
            Reply-Message := "Welcome HR - VLAN 30 (Corporate)"
        }
    }
    elsif (LDAP-Group == "Finance") {
        update reply {
            Tunnel-Type := VLAN
            Tunnel-Medium-Type := IEEE-802
            Tunnel-Private-Group-Id := "30"
        }
        update reply {
            Reply-Message := "Welcome Finance - VLAN 30 (Corporate)"
        }
    }
    elsif (LDAP-Group == "Staff") {
        update reply {
            Tunnel-Type := VLAN
            Tunnel-Medium-Type := IEEE-802
            Tunnel-Private-Group-Id := "30"
        }
        update reply {
            Reply-Message := "Welcome Staff - VLAN 30 (Corporate)"
        }
    }
    else {
        # Authenticated but no matching group → default CORPORATE
        update reply {
            Tunnel-Type := VLAN
            Tunnel-Medium-Type := IEEE-802
            Tunnel-Private-Group-Id := "30"
        }
        update reply {
            Reply-Message := "Welcome - VLAN 30 (Corporate Default)"
        }
    }

    Post-Auth-Type REJECT {
        -sql
        attr_filter.access_reject
        eap
        remove_reply_message_if_eap
    }
}
```

### 6.4 Test RADIUS config

```bash
# Syntax check
sudo freeradius -XC 2>&1 | tail -10
# ควรเห็น: Configuration appears to be OK

# Restart (debug mode)
# กด Ctrl+C ก่อน (stop previous instance)
sudo freeradius -X &

# ===== Test LDAP group lookup =====
# ใช้ ldapsearch ทดสอบก่อนว่า radius_svc ดึง group ได้:
ldapsearch -x -H ldap://10.1.10.20 \
    -D "CN=radius_svc,CN=Users,DC=group1,DC=corp" \
    -w '<PASSWORD>' \
    -b "CN=Users,DC=group1,DC=corp" \
    "(sAMAccountName=winnie.p)" memberOf

# ควรเห็น:
# memberOf: CN=IT,CN=Users,DC=group1,DC=corp

# ===== Test RADIUS auth + VLAN return =====
# inner-tunnel test (MSCHAPv2):
radtest -t mschap winnie.p 'P@ssw0rd123' 127.0.0.1:18120 0 testing123

# ควรเห็นใน debug output (-X):
#   Tunnel-Type = VLAN
#   Tunnel-Medium-Type = IEEE-802
#   Tunnel-Private-Group-Id = "20"     # ถ้า winnie.p อยู่กลุ่ม IT

# ทดสอบ user ที่อยู่ HR:
radtest -t mschap anong.r 'P@ssw0rd123' 127.0.0.1:18120 0 testing123
# ควรเห็น Tunnel-Private-Group-Id = "30"
```

---

## P3 — Step 7: L2 PoE Switch — เปิด AAA + 802.1X + RADIUS

> **Risk:** Medium — user ที่ port 802.1X จะต้อง auth  
> **Device:** POE_SW_G1 (C3750X-48P)  
> **⚠️ ห้ามเผลอ enable dot1x system-auth-control ก่อน configure RADIUS !!!**

```
POE_SW_G1# configure terminal

! ----- 7.1 Enable AAA -----
aaa new-model

! ----- 7.2 RADIUS server definition -----
radius-server host 10.1.10.10 auth-port 1812 acct-port 1813 key Rad1us_L2SW!

! ----- 7.3 AAA methods -----
aaa authentication dot1x default group radius
aaa authorization network default group radius
aaa accounting dot1x default start-stop group radius

! ----- 7.4 Enable RADIUS VSA -----
radius-server vsa send authentication
radius-server vsa send accounting

! ----- 7.5 Enable 802.1X globally -----
dot1x system-auth-control

! ----- 7.6 VLAN ที่จำเป็น (ตรวจว่ามี) -----
! L2 switch ต้องมี VLAN 20, 30, 40 ใน VLAN database
! ดู: show vlan brief
! ถ้าไม่มี VLAN 30:
vlan 30
 name CORPORATE
exit

end
write memory
```

### Verify Step 7

```
show aaa servers
! ควรเห็น RADIUS server 10.1.10.10

show dot1x all
! Sysauthcontrol: Enabled

show vlan brief
! ควรเห็น VLAN 20, 30, 40

! ⚠️ ตอนนี้ port ยังเป็น access mode ปกติ — ยังไม่มี port ที่เปิด 802.1X
! ต่อ Step 8 ทดสอบ 1 port
```

---

## P3 — Step 8: L2 PoE Switch — ทดสอบ 802.1X บน 1 port

> **Risk:** Low — แก้แค่ 1 port  
> **เลือก port ที่ทดสอบได้:** เช่น Gi1/0/1

```
POE_SW_G1# configure terminal

interface GigabitEthernet1/0/1
 description 802.1X-TEST-PORT

 ! เปลี่ยนจาก static access → 802.1X dynamic
 switchport mode access
 switchport access vlan 20
 ! ↑ default VLAN ถ้า RADIUS ไม่ return VLAN (fallback)

 ! ----- 802.1X config -----
 authentication port-control auto
 authentication host-mode multi-auth
 ! multi-auth = หลายเครื่องต่อ port ได้ (ถ้าผ่าน hub/dock)

 dot1x pae authenticator
 dot1x timeout tx-period 10
 ! tx-period = กี่วินาทีส่ง EAP-Request ซ้ำ (10 วิ)

 ! ----- Failure handling -----
 ! Auth fail → Guest VLAN (VLAN 40)
 authentication event fail action authorize vlan 40

 ! No response (ไม่มี 802.1X supplicant) → Guest VLAN
 authentication event no-response action authorize vlan 40

 ! RADIUS server down → Critical VLAN (VLAN 20, ให้ทำงานต่อได้)
 authentication event server dead action authorize vlan 20
 authentication event server alive action reinitialize

 spanning-tree portfast edge
exit

end
write memory
```

### Verify Step 8

```
! ----- Test 1: IT user -----
! เสียบ PC ที่ Gi1/0/1 → ตั้ง 802.1X supplicant (Windows: Settings > Network > Ethernet > Authentication)
! Login: winnie.p / P@ssw0rd123

show authentication sessions interface Gi1/0/1
! ควรเห็น:
!   User-Name: winnie.p
!   Status: Authorized
!   Assigned VLAN: 20      ← IT group = VLAN 20 (PRIVILEGED) ✓

! ดู IP ที่ได้:
! Client: ipconfig → 10.1.20.x ✓

! ----- Test 2: HR user -----
! Login: anong.r / P@ssw0rd123

show authentication sessions interface Gi1/0/1
!   User-Name: anong.r
!   Assigned VLAN: 30      ← HR group = VLAN 30 (CORPORATE) ✓

! Client: ipconfig → 10.1.30.x ✓

! ----- Test 3: No 802.1X (ไม่ login) -----
! เสียบ PC ที่ไม่มี supplicant

show authentication sessions interface Gi1/0/1
!   Status: Unauthorized
!   Assigned VLAN: 40      ← Guest VLAN ✓

! Client: ipconfig → 10.1.40.x ✓

! ----- Test 4: RADIUS down -----
! ปิด FreeRADIUS:  sudo systemctl stop freeradius
! เสียบ PC ใหม่

show authentication sessions interface Gi1/0/1
!   Status: Authorized (Critical Auth)
!   Assigned VLAN: 20      ← Critical VLAN ✓

! เปิด RADIUS กลับ:  sudo systemctl start freeradius
! Port จะ reinitialize อัตโนมัติ
```

---

## P3 — Step 9: L2 PoE Switch — Roll out ทุก port

> **Risk:** Medium — ทุก employee port ต้อง auth แล้ว  
> **⚠️ แจ้ง user ก่อน:** "ต้องตั้ง 802.1X บน PC"

```
POE_SW_G1# configure terminal

! ----- 9.1 Apply 802.1X บน Gi1/0/1 - Gi1/0/12 (employee ports) -----
interface range GigabitEthernet1/0/1 - 12
 description EMPLOYEE-802.1X
 switchport mode access
 switchport access vlan 20

 authentication port-control auto
 authentication host-mode multi-auth

 dot1x pae authenticator
 dot1x timeout tx-period 10

 authentication event fail action authorize vlan 40
 authentication event no-response action authorize vlan 40
 authentication event server dead action authorize vlan 20
 authentication event server alive action reinitialize

 spanning-tree portfast edge
exit

end
write memory
```

### Verify Step 9

```
show authentication sessions
! ควรเห็น session ของ client ทุกตัวที่ต่ออยู่
! แต่ละ session แสดง User-Name + Assigned VLAN

show dot1x all summary
! ดู status ของทุก port

show vlan brief
! VLAN 20: ports ที่ IT user ได้
! VLAN 30: ports ที่ HR/Finance/Staff user ได้
! VLAN 40: ports ที่ auth fail / no supplicant
```

---

## P4 — Step 10: WLC — เปิด AAA Override (Dynamic VLAN WiFi)

> **Risk:** Low — WLC มี AAA Override เปิดอยู่แล้ว (`wlan aaa-override enable 1`) ✅  
> **Device:** WLC 10.1.50.10  

### ปัจจุบัน WLC มีอะไร:

```
WLAN 1: "Group1 WiFi (802.1x)" — interface: guest-staff-1 (VLAN 30)
  - aaa-override: ENABLED ✅
  - radius auth server 1: 10.1.10.10  ✅
  - security: WPA2 + 802.1X ✅

WLAN 2: "Group01 WiFi" — web auth (guest)
```

### สิ่งที่ต้องทำเพิ่ม:

#### 10.1 สร้าง interface VLAN 20 บน WLC (ถ้ายังไม่มี)

WLC ต้องมี interface ของ VLAN 20 เพื่อรองรับ dynamic VLAN assignment:

```
! WLC CLI (SSH หรือ console)

! ตรวจว่ามี interface VLAN 20 (lanuser) หรือยัง:
show interface summary
! เห็น: lanuser (VLAN 20, 10.1.20.2) ← มีอยู่แล้ว ✅

! ถ้าไม่มี:
config interface create privileged-wifi 20
config interface address dynamic-interface privileged-wifi 10.1.20.3 255.255.255.0 10.1.20.1
config interface vlan privileged-wifi 20
config interface dhcp dynamic-interface privileged-wifi primary 10.1.20.1
config interface port privileged-wifi 13
```

#### 10.2 VLAN 30 interface ก็มีอยู่แล้ว:

```
show interface summary
! guest-staff-1 (VLAN 30, 10.1.30.10, GW 10.1.30.1) ← มีอยู่แล้ว ✅
```

#### 10.3 Verify AAA Override ทำงาน

```
! AAA Override อยู่แล้ว — ไม่ต้องแก้อะไร
show wlan 1
! ...
! Allow AAA Override: Enabled ✅

! ทดสอบ:
! IT user เชื่อม "Group1 WiFi (802.1x)"
! → RADIUS return Tunnel-Private-Group-Id = 20
! → WLC override: ย้ายจาก default interface (VLAN 30) → VLAN 20
!
! HR user เชื่อม "Group1 WiFi (802.1x)"
! → RADIUS return Tunnel-Private-Group-Id = 30
! → WLC: อยู่ VLAN 30 เหมือนเดิม (default = VLAN 30)
```

### Verify Step 10

```
! ดู client ที่ต่ออยู่:
show client summary

! ดู detail ของ client ตัวนึง:
show client detail <MAC-ADDRESS>
! ดู VLAN: ควรเป็น 20 (IT) หรือ 30 (HR)

! Debug (ถ้า troubleshoot):
debug aaa all enable
debug dot1x all enable
! ดู RADIUS response + VLAN assignment
```

---

## P5 — Step 11: Firepower FTD — Fine-tune Access Policy

> **Risk:** Low — เพิ่ม/แก้ ACL rules  
> **ทำผ่าน FMC GUI เป็นหลัก**

### 11.1 Access Policy Matrix

```
FROM → TO          │ Action                           │ FMC Rule Name
════════════════════╪══════════════════════════════════╪═══════════════════════
privileged → outside│ ALLOW ALL                        │ Allow-Internet-Privileged
privileged → inside │ ALLOW ALL (server, MGMT access)  │ Allow-Privileged-to-Inside
privileged → corporate│ ALLOW ALL                      │ Allow-Privileged-to-Corporate
privileged → dmz    │ ALLOW ALL                        │ Allow-Privileged-to-DMZ
────────────────────┼──────────────────────────────────┼───────────────────────
corporate → outside │ ALLOW (+ URL filter optional)    │ Allow-Internet-Corporate
corporate → inside  │ ALLOW only DNS(53)+LDAP(389)     │ Allow-Corporate-to-AD
                    │   to 10.1.10.20                  │
corporate → privileged│ DENY                           │ (implicit: default deny)
corporate → dmz     │ ALLOW HTTP/HTTPS only            │ Allow-Corporate-to-DMZ-Web
────────────────────┼──────────────────────────────────┼───────────────────────
guest → outside     │ ALLOW (HTTP/HTTPS/DNS only)      │ Allow-Internet-Guest
guest → inside      │ DENY                             │ (implicit: default deny)
guest → privileged  │ DENY                             │ (implicit: default deny)
guest → corporate   │ DENY                             │ (implicit: default deny)
guest → dmz         │ DENY                             │ (implicit: default deny)
────────────────────┼──────────────────────────────────┼───────────────────────
dmz → outside       │ ALLOW ALL                        │ Allow-DMZ-to-Internet
dmz → inside        │ ALLOW to Server-LAN              │ Allow-DMZ-to-Server
────────────────────┼──────────────────────────────────┼───────────────────────
any → any           │ DENY (default)                   │ DefaultActionRule
```

### 11.2 FMC CLI equivalent (ถ้าไม่ใช้ FMC)

```
configure terminal

! ===== Object Group สำหรับ Corporate → AD =====
object-group service Corporate-to-AD-Svc
 service-object udp destination eq 53
 service-object tcp destination eq 53
 service-object tcp destination eq 389
 service-object udp destination eq 389
exit

object network AD-Server
 host 10.1.10.20
exit

object-group service Web-Only
 service-object tcp destination eq 80
 service-object tcp destination eq 443
exit

! ===== ลบ ACL เดิมที่ซ้ำ (จัดระเบียบ) =====
! ลบ rules เดิมที่ต้องเปลี่ยน (ถ้ายังมี employee refs)
! ... (ข้ามถ้าทำ Step 2 เรียบร้อยแล้ว)

! ===== NEW RULES (เพิ่มก่อน DefaultActionRule) =====

! --- Privileged (VLAN 20) → full access ---
access-list NGFW_ONBOX_ACL remark === PRIVILEGED ZONE RULES ===
access-list NGFW_ONBOX_ACL advanced permit ip ifc privileged any ifc outside any event-log both
access-list NGFW_ONBOX_ACL advanced permit ip ifc privileged any ifc inside any event-log flow-end
access-list NGFW_ONBOX_ACL advanced permit ip ifc privileged any ifc corporate any
access-list NGFW_ONBOX_ACL advanced permit ip ifc privileged any ifc dmz any

! --- Corporate (VLAN 30) → restricted ---
access-list NGFW_ONBOX_ACL remark === CORPORATE ZONE RULES ===
! Corporate → Internet
access-list NGFW_ONBOX_ACL advanced permit ip ifc corporate any ifc outside any event-log both
! Corporate → AD server only (DNS + LDAP)
access-list NGFW_ONBOX_ACL advanced permit object-group Corporate-to-AD-Svc ifc corporate any ifc inside object AD-Server
! Corporate → DMZ (web only)
access-list NGFW_ONBOX_ACL advanced permit object-group Web-Only ifc corporate any ifc dmz any
! Corporate → privileged: DENY (default deny handles this)
! Corporate → inside (other): DENY (default deny handles this)

! --- Guest (VLAN 40) → internet only ---
access-list NGFW_ONBOX_ACL remark === GUEST ZONE RULES ===
access-list NGFW_ONBOX_ACL advanced permit object-group Web-Only ifc guest any ifc outside any event-log both
access-list NGFW_ONBOX_ACL advanced permit object-group |acSvcg-268435471 ifc guest any ifc outside any
! Guest → internal: DENY (default deny handles this)

! --- Ping rules ---
access-list NGFW_ONBOX_ACL remark === INTERNAL PING ===
access-list NGFW_ONBOX_ACL advanced permit icmp ifc privileged any any
access-list NGFW_ONBOX_ACL advanced permit icmp ifc corporate any ifc outside any
access-list NGFW_ONBOX_ACL advanced permit icmp ifc inside any any

! --- Default Deny (ต้องอยู่ล่างสุดเสมอ) ---
! access-list NGFW_ONBOX_ACL advanced deny ip any any rule-id 1 event-log both
! ↑ มีอยู่แล้ว — ไม่ต้องเพิ่ม

end
write memory
```

### Verify Step 11

```
! ===== Test จาก VLAN 20 (Privileged/IT) =====
! ping 8.8.8.8          → ✅ pass (internet)
! ping 10.1.10.20       → ✅ pass (AD server)
! ping 10.1.30.x        → ✅ pass (corporate)
! ping 10.1.100.10      → ✅ pass (DMZ honeypot)
! curl http://10.1.50.1  → ✅ pass (switch mgmt)

! ===== Test จาก VLAN 30 (Corporate/HR) =====
! ping 8.8.8.8          → ✅ pass (internet)
! nslookup google.com 10.1.10.20 → ✅ pass (AD DNS)
! ping 10.1.10.20       → ❌ block (ICMP to server blocked, but DNS/LDAP works)
! ping 10.1.20.x        → ❌ block (can't reach privileged)
! curl http://10.1.100.10 → ✅ pass (DMZ web)
! ssh 10.1.50.1         → ❌ block (can't reach MGMT)

! ===== Test จาก VLAN 40 (Guest) =====
! curl http://google.com → ✅ pass (internet web)
! ping 8.8.8.8          → ❌ block (ICMP blocked, only web)
! ping 10.1.20.1        → ❌ block (can't reach internal)
! ping 10.1.30.1        → ❌ block (can't reach internal)

! ===== FW monitoring =====
show conn count
show conn all | include corporate
show conn all | include privileged
show access-list NGFW_ONBOX_ACL | include hitcnt
```

---

## Summary: Complete Test Matrix

| # | Test Case | From | To | Expected | Verify |
|---|-----------|------|----|----------|--------|
| 1 | IT user wired → VLAN 20 | L2 Gi1/0/x | — | DHCP 10.1.20.x | `show auth sessions` |
| 2 | HR user wired → VLAN 30 | L2 Gi1/0/x | — | DHCP 10.1.30.x | `show auth sessions` |
| 3 | No auth wired → VLAN 40 | L2 Gi1/0/x | — | DHCP 10.1.40.x | `show auth sessions` |
| 4 | IT user WiFi → VLAN 20 | WLC | — | AAA Override to VL20 | `show client detail` |
| 5 | HR user WiFi → VLAN 30 | WLC | — | Default VL30 | `show client detail` |
| 6 | Privileged → Internet | VL20 | 8.8.8.8 | ✅ PASS | `ping` |
| 7 | Privileged → Server | VL20 | 10.1.10.20 | ✅ PASS | `ping` |
| 8 | Corporate → Internet | VL30 | 8.8.8.8 | ✅ PASS | `ping` |
| 9 | Corporate → Server | VL30 | 10.1.10.20 | ❌ BLOCKED (except DNS) | `nslookup` ok, `ping` fail |
| 10 | Corporate → Privileged | VL30 | 10.1.20.x | ❌ BLOCKED | `ping` fail |
| 11 | Guest → Internet | VL40 | google.com | ✅ HTTP only | `curl` ok |
| 12 | Guest → Internal | VL40 | 10.1.x.x | ❌ BLOCKED | `ping` fail |
| 13 | RADIUS down → fallback | L2 | — | VLAN 20 (critical) | `show auth sessions` |
| 14 | DaloRADIUS accounting | — | — | เห็น VLAN per user | DaloRADIUS web |

---

## Rollback Plan

### ถ้ามีปัญหา ย้อนกลับทีละ layer:

```
! === L2 Switch: ปิด 802.1X ===
POE_SW_G1(config)# no dot1x system-auth-control
POE_SW_G1(config)# interface range Gi1/0/1 - 12
POE_SW_G1(config-if)#  no authentication port-control auto
POE_SW_G1(config-if)#  no dot1x pae authenticator
POE_SW_G1(config-if)#  switchport access vlan 20
! ← ทุก port กลับเป็น static VLAN 20

! === L3 Switch: ย้อน SVI 30 ===
L3_SW_G1(config)# interface Vlan30
L3_SW_G1(config-if)# no ip address
L3_SW_G1(config-if)# ip address 10.1.30.1 255.255.255.0
! ← gateway กลับมาที่ L3

! === FW: ลบ subinterface 30 ===
! (FMC: delete Po1.30 + Deploy)
! CLI:
! configure terminal
! no interface Port-channel1.30
```
