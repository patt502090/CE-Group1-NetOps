# 🚀 Enterprise-Grade Network Configuration Management Stack

ระบบบริหารจัดการคอนฟิกเครือข่ายอัตโนมัติ ออกแบบตามหลักความปลอดภัยระดับสูง (Security-Hardened Architecture)

### 🏗️ Technology Stack (The Core)
* **Fetcher Engine:** Oxidized (Ruby-based) [cite: 2026-02-23]
* **Environment:** Hardened Debian 12 on Raspberry Pi infrastructure [cite: 2026-02-23]
* **Version Control:** Git with localized differential tracking [cite: 2026-02-23]
* **Remote Sync:** Secure GitHub Private Repository via Personal Access Token
* **Service Control:** Managed via Systemd for 24/7 high availability [cite: 2026-02-23]

### ⚙️ Automation & Security Logic
* **Interval Polling:** ทุก 10,800 วินาที (3 ชั่วโมง) [cite: 2026-02-23]
* **Operational Window:** 08:00 - 23:59 (UTC+7) [cite: 2026-02-23]
* **Custom Driver Implementation:** `myftd.rb` - พัฒนาขึ้นพิเศษเพื่อจัดการ Regex สำหรับ SSH Prompt ของ Cisco Firepower 2110 [cite: 2026-02-23]
* **Security Design:** หน้า Dashboard (Port 8081) ถูกจำกัดการเข้าถึงเฉพาะภายในวงเครือข่ายที่กำหนด (Restricted Access) เพื่อป้องกันการรั่วไหลของข้อมูลโครงสร้างพื้นฐาน [cite: 2026-02-23]

### 📊 Network Node Inventory
| Hostname | Type | Driver | Sync Status |
| :--- | :--- | :--- | :--- |
| **L3_SW_G1** | Core Switch | `ios` | ✅ Online |
| **L2_SW_G1** | Access Switch | `ios` | ✅ Online |
| **WLC** | Wireless Ctrl | `aireos` | ✅ Online |
| **FIREPOWER-G1** | Firewall | `myftd` | ✅ Online |
