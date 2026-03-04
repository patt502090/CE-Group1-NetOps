# Wazuh Podman — คู่มือใช้งาน (Step-by-step)

## ภาพรวม
คู่มือนี้อธิบายวิธีเริ่มต้นใช้งาน Wazuh ด้วย **Podman** และ **podman-compose** ในโฟลเดอร์ `wazuh-docker` (single-node และ multi-node) พร้อมคำสั่งสำคัญและแนวทางแก้ปัญหาเบื้องต้น

## ข้อกำหนดล่วงหน้า
- ติดตั้ง **Podman** (`podman`) และ **podman-compose** (`pip install podman-compose`)
- พื้นที่ว่างสำหรับ volumes และสิทธิ์เขียนไฟล์
- ตั้งค่า `vm.max_map_count` สำหรับ Wazuh Indexer:
  ```bash
  sudo sysctl -w vm.max_map_count=262144
  # เพิ่มลงใน /etc/sysctl.conf เพื่อให้คงอยู่หลัง reboot
  echo "vm.max_map_count=262144" | sudo tee -a /etc/sysctl.conf
  ```
- (แนะนำ) อ่าน README หลัก: [wazuh-docker/README.md](README.md)

## โครงสร้างสำคัญ
- Compose แบบเดี่ยว (single-node): [single-node/docker-compose.yml](single-node/docker-compose.yml)
- Compose แบบหลายโหนด (multi-node): [multi-node/docker-compose.yml](multi-node/docker-compose.yml)
- สคริปต์สร้าง image: [build-docker-images/build-images.sh](build-docker-images/build-images.sh)
- Configs ของแต่ละส่วนอยู่ในโฟลเดอร์ย่อย `wazuh-manager`, `wazuh-indexer`, `wazuh-dashboard` ภายใน `build-docker-images` และ `single-node`/`multi-node`/`config`

## ติดตั้ง Podman และ podman-compose

### macOS
```bash
brew install podman
podman machine init
podman machine start
pip3 install podman-compose
```

### Linux (Ubuntu/Debian)
```bash
sudo apt-get update && sudo apt-get install -y podman
pip3 install podman-compose
```

### Linux (RHEL/CentOS/Fedora)
```bash
sudo dnf install -y podman
pip3 install podman-compose
```

## Quick Start — Single-node
1. เปิดเทอร์มินัลแล้วไปที่โฟลเดอร์ single-node:

```bash
cd wazuh-docker/single-node
```

2. สร้าง SSL certificates:

```bash
podman-compose -f generate-indexer-certs.yml run --rm generator
```

3. ปรับค่า config ถ้าจำเป็น (ไฟล์ใน `config/` เช่น `certs.yml` หรือไฟล์ environment ที่ repo root `.env`).

4. รัน:

```bash
podman-compose up -d
```

5. ตรวจสอบสถานะและ logs:

```bash
podman-compose ps
podman-compose logs -f
```

6. เข้าถึง Wazuh / OpenSearch Dashboards โดยปกติพอร์ตทั่วไปคือ `5601` (dashboard) และ `9200` (indexer) — หากต้องการพอร์ตที่แน่นอนให้ตรวจสอบไฟล์ compose

## Quick Start — Multi-node (สรุป)
1. อ่านคำแนะนำเพิ่มเติม: [multi-node/README.md](multi-node/README.md)
2. สร้าง/จัดการใบรับรอง (ถ้ามี):

```bash
cd wazuh-docker/multi-node
podman-compose -f generate-indexer-certs.yml run --rm generator
```

3. จากนั้นรัน compose:

```bash
podman-compose up -d
```

4. ตรวจสอบสถานะด้วย `podman-compose ps` และ logs เช่นกัน

หมายเหตุ: Multi-node มีความซับซ้อนมากขึ้น (certs, network, volumes) — อ่านไฟล์ `multi-node/README.md` และ `config/` ก่อนใช้งานจริง

## สร้าง image ภายในเครื่อง (ถ้าต้องการ)
1. ไปที่โฟลเดอร์ `build-docker-images`:

```bash
cd wazuh-docker/build-docker-images
./build-images.sh
```

สคริปต์นี้จะช่วย build image ของ `wazuh-dashboard`, `wazuh-indexer`, `wazuh-manager` ตามที่กำหนด (ใช้ `podman-compose` ภายใน)

## คำสั่งที่ใช้บ่อย
- Start: `podman-compose up -d`
- Stop & remove containers: `podman-compose down` (เพิ่ม `-v` เพื่อลบ volumes)
- Rebuild: `podman-compose up -d --build`
- ดู logs ของ service ใด ๆ: `podman-compose logs -f <service>`
- ดู status: `podman-compose ps`
- ดู containers ทั้งหมด: `podman ps -a`
- ดู volumes: `podman volume ls`
- ลบ volume: `podman volume rm <volume_name>`

## การแก้ปัญหาเบื้องต้น
- ถ้า service ขึ้นไม่ครบ: ดู `podman-compose logs -f` ของ service นั้น
- ปัญหา permission ของ volume: ตรวจสอบสิทธิ์โฟลเดอร์ host ที่แมปเข้า container (Podman rootless อาจต้องใช้ `:Z` suffix สำหรับ SELinux)
- ปัญหา rootless Podman: ตรวจสอบว่า `/etc/subuid` และ `/etc/subgid` กำหนดค่าถูกต้อง
- หากต้องการข้อมูลละเอียด: อ่านไฟล์ config ที่เกี่ยวข้องใน
  - [single-node/config](single-node/config)
  - [multi-node/config](multi-node/config)
  - [build-docker-images/README.md](build-docker-images/README.md)

## ข้อมูลเพิ่มเติมและแหล่งอ้างอิง
- README หลัก: [wazuh-docker/README.md](README.md)
- ตัวอย่าง config และ entrypoint ต่าง ๆ อยู่ในโฟลเดอร์ `build-docker-images/*/config`
- Podman documentation: https://docs.podman.io
- podman-compose: https://github.com/containers/podman-compose