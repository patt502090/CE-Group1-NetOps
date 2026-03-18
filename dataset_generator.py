import csv
import random
from datetime import datetime, timedelta

# ข้อมูลจำลองสำหรับโปรเจกต์ NetOps Group 1
groups = [
    ("IT", "VLAN 20", ["10.1.20."+str(i) for i in range(10, 50)]),
    ("HR", "VLAN 30", ["10.1.30."+str(i) for i in range(10, 50)]),
    ("Finance", "VLAN 30", ["10.1.30."+str(i) for i in range(51, 100)]),
    ("Staff", "VLAN 30", ["10.1.30."+str(i) for i in range(101, 200)]),
    ("Guest", "VLAN 40", ["10.1.40."+str(i) for i in range(10, 200)])
]

apps = ["HTTPS", "HTTP", "DNS", "SMB", "SSH", "FTP", "Active Directory", "Radius"]
actions = ["Permit", "Permit", "Permit", "Permit", "Permit", "Deny", "Deny"]
connection_type = ["Wired", "Wi-Fi"]

start_time = datetime.now() - timedelta(days=30) # ย้อนหลัง 1 เดือน

print("Generating dataset...")
with open('network_traffic_log.csv', 'w', newline='', encoding='utf-8') as file:
    writer = csv.writer(file)
    writer.writerow(["Timestamp", "Date", "User_Group", "VLAN", "Source_IP", "Application", "Traffic_MB", "Action", "Connection_Type"])
    
    for _ in range(5000): # สร้าง 5000 บรรทัดให้ดูกราฟสวยๆ
        group_name, vlan, ips = random.choice(groups)
        src_ip = random.choice(ips)
        app = random.choice(apps)
        
        # จัด Logic ให้เนียนๆ กับโปรเจกต์ที่เราทำ
        if vlan == "VLAN 40":
            conn = "Wi-Fi" # Guest มีแต่ Wi-Fi
            if app not in ["HTTP", "HTTPS", "DNS"]:
                action = "Deny" # Guest โดน Block ถ้าเข้าแปลกๆ
            else:
                action = random.choice(actions)
        else:
            conn = random.choice(connection_type)
            action = random.choice(actions)
            
        traffic = round(random.uniform(0.1, 50.0), 2)
        if app in ["HTTPS", "FTP", "SMB"]:
             traffic = round(random.uniform(10.0, 1024.0), 2) # โหลดหนัก
             
        # สุ่มเวลา
        random_seconds = random.randint(0, 30*24*60*60)
        log_time = start_time + timedelta(seconds=random_seconds)
        
        writer.writerow([
            log_time.strftime("%Y-%m-%d %H:%M:%S"), 
            log_time.strftime("%Y-%m-%d"), 
            group_name, 
            vlan, 
            src_ip, 
            app, 
            traffic, 
            action, 
            conn
        ])

print("Generated 'network_traffic_log.csv' successfully with 5000 records!")
