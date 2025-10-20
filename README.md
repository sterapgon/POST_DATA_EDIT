# TCL Form Status Poster

โปรเจ็กต์นี้รวบรวมสคริปต์สำหรับสื่อสารกับบริการของกรมสรรพากร โดยมุ่งเน้นการโพสต์และตรวจสอบสถานะเอกสารภาษีผ่าน REST API ภายใน ประกอบด้วยเครื่องมือหลัก 3 ตัว คือ `post_uids.py`, `chk_tcl_sta.py`, และ `chk_nid.sta.py`

## โครงสร้างไฟล์สำคัญ
- `post_uids.py` – สคริปต์โพสต์สถานะเอกสาร VAT POS ตาม UID ที่ระบุ
- `chk_tcl_sta.py` – สคริปต์ดึงข้อมูล VAT POS Status ตาม UID แล้วบันทึกผลลัพธ์เป็นไฟล์ log แยกตามเวลา
- `chk_nid.sta.py` – สคริปต์เรียกข้อมูลผู้เสียภาษี (NID) และบันทึกผลลัพธ์เป็น log รูปแบบเดียวกับ VAT POS
- `uids.txt` / `uids_chk_tcl.txt` / `nid.txt` – ไฟล์รายชื่อรหัสที่ต้องการประมวลผล (ละเว้นบรรทัดว่างและบรรทัดที่ขึ้นต้นด้วย `#`)
- โฟลเดอร์ `log/` – เก็บไฟล์ผลลัพธ์ที่สคริปต์แต่ละตัวสร้างขึ้น

## ข้อกำหนดเบื้องต้น
1. ติดตั้ง Python 3 และสามารถรันสคริปต์จากบรรทัดคำสั่งได้
2. เตรียมไฟล์รายชื่อ UID หรือ NID ที่ต้องการใช้งาน
3. มีสิทธิ์เข้าถึงเครือข่ายภายในและบริการปลายทางของกรมสรรพากร

## การใช้งาน `post_uids.py`
ใช้สำหรับโพสต์สถานะฟอร์ม VAT POS ไปยังบริการ `setFormStatusRESTful/vatpos`

### ตัวอย่างคำสั่ง
```powershell
python post_uids.py --environment prod --insecure --uids-file uids.txt
python post_uids.py --environment uat --insecure --uids-file uids.txt
```
หรือระบุ UID เป็นอาร์กิวเมนต์โดยตรง
```powershell
python post_uids.py 1234567890 9876543210
```

### ออปชันสำคัญ
- `uids` (ตำแหน่ง) – UID ที่ต้องการส่ง สามารถระบุหลายตัวได้
- `--uids-file` – กำหนดไฟล์ที่เก็บ UID (ดีฟอลต์ `uids.txt`)
- `--environment {prod,uat}` – เลือกปลายทางที่ต้องการ (ดีฟอลต์ `prod`)
- `--timeout` – ตั้งค่า timeout ต่อคำขอหน่วยเป็นวินาที (ดีฟอลต์ 10)
- `--cafile` – ระบุไฟล์ CA สำหรับตรวจสอบ TLS
- `--insecure` – ข้ามการตรวจสอบใบรับรอง TLS (ใช้เมื่อยังไม่มี CA ภายใน)
- `--dry-run` – แสดง payload ที่จะส่งโดยไม่โพสต์จริง และไม่สร้าง log

### หมายเหตุการทำงาน
- สคริปต์ดีเลย์ 3 วินาทีระหว่างการเรียกแต่ละ UID (ยกเว้น `--dry-run`)
- สร้างไฟล์ log (.log) ในโฟลเดอร์ `log/` โดยมี timestamp ในชื่อไฟล์
- เนื้อหา log บันทึกในรูป JSON ระบุ `timestamp`, `environment`, `uid`, `status`, และ `response`
- หากต้องตรวจสอบ TLS จริง ควรกำหนด `--cafile` และหลีกเลี่ยง `--insecure`

## การตรวจสอบสถานะ VAT POS (`chk_tcl_sta.py`)
สคริปต์นี้จะอ่าน UID จากไฟล์ (ดีฟอลต์ `uids_chk_tcl.txt`) แล้วเรียกบริการ `getTaxFormInformation2/vatpos` ตาม environment ที่เลือก ก่อนจะบันทึกผลลัพธ์ลงไฟล์ log ใหม่ที่มี timestamp ต่อท้าย เช่น `log/get_data_tcl_2025-10-08-10.37.29.000830.csv`

### ตัวอย่างคำสั่ง
```powershell
python chk_tcl_sta.py --environment prod --uids-file uids_chk_tcl.txt
python chk_tcl_sta.py --environment uat --uids-file uids_chk_tcl.txt
```

### ออปชันสำคัญ
- `--environment {prod,uat}` – เลือก base URL (ดีฟอลต์ `prod`)
- `--uids-file` – ไฟล์รายชื่อ UID (ดีฟอลต์ `uids_chk_tcl.txt`)
- `--log-dir` – โฟลเดอร์ปลายทางสำหรับไฟล์ log (ดีฟอลต์ `log`)
- `--log-format {text,csv}` – เลือกรูปแบบ log (ดีฟอลต์ `csv`; ใช้ `text` เมื่อต้องการรูปแบบบล็อก)
- `--timeout` – timeout ต่อคำขอ (ดีฟอลต์ 30 วินาที)
- `--delay` – เวลาหน่วงระหว่าง UID แต่ละตัว (ดีฟอลต์ 3 วินาที)
- `--verify-ssl` – ตรวจสอบ TLS ด้วย system CA (ดีฟอลต์ไม่ตรวจสอบ)

### ลักษณะ log
- โหมด `csv` (ค่าดีฟอลต์) จะสร้างไฟล์ `.csv` พร้อมคอลัมน์ที่ใช้งานได้ทันที เช่น `timestamp`, `environment`, `uid`, `status`, `formStatusCode`, `DLN`, `taxAmount`, `effectiveDate` และปิดท้ายด้วย `raw_response` เพื่ออ้างอิง JSON เต็ม
- โหมด `text` จะสร้างไฟล์ `.txt` ที่จัดรูป JSON อ่านง่ายเป็นบล็อก
- ไฟล์ log ใหม่ถูกสร้างทุกครั้งที่รัน ตาม timestamp ปัจจุบัน เพื่อไม่ให้ข้อมูลทับกัน

## การตรวจสอบข้อมูลผู้เสียภาษี (`chk_nid.sta.py`)
ใช้โพสต์ payload รูปแบบ `taxpayerList` ไปยังบริการ `getTaxpayerInfoList` โดยอ่าน NID จากไฟล์ (ดีฟอลต์ `nid.txt`) และสร้างไฟล์ log ใหม่ในโฟลเดอร์ `log/`

### ตัวอย่างคำสั่ง
```powershell
python chk_nid.sta.py --environment prod --nids-file nid.txt
python chk_nid.sta.py --environment uat --nids-file nid.txt
```

### ออปชันสำคัญ
- `--environment {prod,uat}` – เลือกปลายทาง (ดีฟอลต์ `prod`)
- `--nids-file` – ไฟล์รายชื่อ NID (ดีฟอลต์ `nid.txt`)
- `--log-dir` – โฟลเดอร์ที่ใช้บันทึก log (ดีฟอลต์ `log`)
- `--log-format {text,csv}` – เลือกรูปแบบ log (ดีฟอลต์ `csv`; ใช้ `text` เมื่อต้องการดู JSON แบบเต็ม)
- `--timeout` – timeout ต่อคำขอ (ดีฟอลต์ 30 วินาที)
- `--delay` – เวลาหน่วงระหว่างแต่ละ NID (ดีฟอลต์ 0 วินาที)
- `--verify-ssl` – ตรวจสอบ TLS ด้วย system CA (ดีฟอลต์ไม่ตรวจสอบ)

### ลักษณะ log
- โหมด `csv` (ค่าดีฟอลต์) จะแยกคอลัมน์สำคัญ เช่น `entryIdentifier`, ชื่อนามสกุล, ที่อยู่, รวมถึงข้อมูลเอกสารสำคัญ และเก็บ `raw_response` เพื่ออ้างอิง
- โหมด `text` จะแสดง `[timestamp] NID: ...` พร้อม URL, Status และ Response แบบจัดรูป
- การรันแต่ละครั้งจะได้ไฟล์ใหม่ที่มี timestamp ต่อท้าย เช่น `log/get_nid_data_2025-10-08-10.44.13.473358.csv`

## คำแนะนำเพิ่มเติม
- หากต้องการความปลอดภัย ควรเตรียมไฟล์ CA และเปิดใช้ `--verify-ssl`
- สามารถตั้งเวลารันซ้ำด้วย Task Scheduler (Windows) หรือ cron (Linux/Mac)
- ก่อนรันในระบบจริง ควรทดลองกับ environment `uat` พร้อมตรวจสอบ log ที่สร้างขึ้น
- ไฟล์ log เดิมที่ไม่ต้องการสามารถย้ายหรือจัดเก็บเพื่อป้องกันการสะสมของข้อมูลขนาดใหญ่ ทั้งในรูปแบบ `.txt` และ `.csv`

## tqr010.py
สคริปต์นี้ใช้เรียก API VATQR010JobAPIService ด้วย payload ที่กำหนด typePreProcess เป็น N และดึงเลข NID จากไฟล์ nid.txt พร้อมบันทึกผลลง tqr010.log และแสดงบนหน้าจอ.

### คำสั่งใช้งาน
```powershell
python tqr010.py
```
