# Fuwa Odoo 19 — Hệ thống quản lý nhân sự Việt Nam

Dự án Odoo 19 tùy chỉnh với module quản lý nhân sự (HR) theo chuẩn pháp luật lao động Việt Nam, tích hợp các module OCA và cải tiến giao diện web.

---

## Mục lục

- [Yêu cầu hệ thống](#yêu-cầu-hệ-thống)
- [Cài đặt](#cài-đặt)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [Module custom\_hr](#module-custom_hr)
- [Module OCA tích hợp](#module-oca-tích-hợp)
- [Hướng dẫn sử dụng](#hướng-dẫn-sử-dụng)
- [Cấu hình production](#cấu-hình-production)

---

## Yêu cầu hệ thống

| Thành phần | Phiên bản |
|-----------|-----------|
| Odoo | 19.0 |
| PostgreSQL | 15+ |
| Python | 3.10+ |
| Docker & Docker Compose | 24+ |

> **Lưu ý:** Repo này chỉ chứa `custom_addons/`, `oca_addons/` và file cấu hình.
> Cần clone thêm Odoo 19 core vào cùng thư mục hoặc mount vào Docker container.

---

## Cài đặt

### 1. Clone repository

```bash
git clone https://github.com/APT3233/fuwa-odoo.git
cd fuwa-odoo
```

### 2. Khởi động với Docker

```bash
docker compose up -d
```

Odoo sẽ chạy tại: `http://localhost:8069`

### 3. Cài module lần đầu

```bash
docker compose exec odoo python odoo-bin \
  -d odoo19 \
  -i custom_hr,web_responsive,web_refresher,web_dialog_size \
  --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/odoo/addons,/opt/odoo/custom_addons,/opt/odoo/oca_addons \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo
```

### 4. Upgrade sau khi cập nhật code

```bash
docker compose exec odoo python odoo-bin \
  -d odoo19 -u custom_hr --stop-after-init \
  --addons-path=/opt/odoo/addons,/opt/odoo/odoo/addons,/opt/odoo/custom_addons,/opt/odoo/oca_addons \
  --db_host=db --db_port=5432 --db_user=odoo --db_password=odoo
```

---

## Cấu trúc dự án

```
fuwa-odoo/
├── custom_addons/
│   └── custom_hr/              # Module HR tùy chỉnh cho thị trường VN
│       ├── models/             # Models mở rộng hr.employee
│       ├── views/              # Views XML (form, tab, wizard)
│       ├── wizards/            # Wizard: chuyển phòng ban, đổi quản lý, nghỉ việc
│       ├── security/           # Phân quyền và record rules
│       └── static/             # SCSS, JS, XML templates
├── oca_addons/                 # Các module OCA tích hợp (Odoo 19.0)
│   ├── hr_department_code/
│   ├── hr_employee_age/
│   ├── hr_employee_calendar_planning/
│   ├── hr_employee_document/
│   ├── hr_employee_id/
│   ├── hr_employee_medical_examination/
│   ├── hr_employee_relative/
│   ├── hr_employee_service/
│   ├── web_dialog_size/
│   ├── web_refresher/
│   └── web_responsive/
├── docker-compose.yml          # Docker Compose (dev + production config)
├── postgres.conf               # PostgreSQL performance tuning
└── Dockerfile
```

---

## Module custom\_hr

Module trung tâm, mở rộng Odoo HR với đầy đủ tính năng theo luật lao động Việt Nam.

### Tính năng chính

#### Thông tin nhân viên mở rộng

| Nhóm | Trường bổ sung |
|------|---------------|
| CMND/CCCD | Ngày cấp, nơi cấp |
| Nhân thân | Dân tộc (54 dân tộc), tôn giáo |
| Địa chỉ thường trú | Số nhà/đường, phường/xã, quận/huyện, tỉnh/thành phố |
| Địa chỉ tạm trú | Như trên + tùy chọn "giống địa chỉ thường trú" |
| Trạng thái nhân sự | Đang làm việc / Thử việc / Nghỉ việc |
| Loại hình làm việc | Toàn thời gian / Bán thời gian / Hợp đồng / Thực tập |

#### Tab Bảo hiểm

- **BHXH**: Số sổ BHXH, ngày tham gia, nơi tham gia
- **BHYT**: Mã số thẻ, ngày hết hạn, nơi đăng ký KCB ban đầu

#### Tab Thuế TNCN

- Mã số thuế cá nhân (MST), nơi đăng ký nộp thuế
- Danh sách người phụ thuộc: họ tên, quan hệ, ngày sinh, CMND, mã NPT, kỳ đăng ký

#### Tab Tài khoản ngân hàng

- Nhiều tài khoản ngân hàng trên mỗi nhân viên
- Đánh dấu tài khoản chính (dùng để chuyển lương)
- Tên ngân hàng, chi nhánh, số tài khoản, chủ tài khoản

#### Tab Lịch sử công tác

- Tự động ghi lại mỗi lần chuyển phòng ban hoặc đổi quản lý
- Lưu: phòng ban, chức danh, chức vụ, quản lý, số quyết định, lý do thay đổi

#### Wizard hành động nhanh

| Wizard | Quyền | Chức năng |
|--------|-------|-----------|
| Chuyển phòng ban | HR User | Ghi lịch sử → chuyển phòng ban; lưu số quyết định, ngày hiệu lực |
| Đổi quản lý | HR User | Cập nhật người quản lý trực tiếp |
| Nghỉ việc | HR Manager | Lưu lý do, ngày nghỉ; ẩn nhân viên khỏi danh sách |

#### Lịch làm việc

- Ràng buộc chỉ cho phép lịch từ Thứ 2 đến Thứ 6
- Tích hợp với OCA `hr_employee_service` để tính thâm niên tự động

### Phân quyền

| Vai trò | Quyền |
|---------|-------|
| HR User | Xem/sửa thông tin nhân viên; wizard chuyển phòng ban, đổi quản lý; xem lịch sử công tác |
| HR Manager | Toàn bộ quyền HR User + wizard nghỉ việc + xóa lịch sử công tác |

---

## Module OCA tích hợp

Tất cả các module OCA đã được điều chỉnh tương thích **Odoo 19.0**.

### HR

| Module | Chức năng |
|--------|-----------|
| `hr_department_code` | Thêm trường mã phòng ban |
| `hr_employee_age` | Tự động hiển thị tuổi nhân viên từ ngày sinh |
| `hr_employee_calendar_planning` | Lập lịch làm việc linh hoạt theo từng nhân viên |
| `hr_employee_document` | Quản lý hồ sơ, tài liệu đính kèm nhân viên |
| `hr_employee_id` | Mã số nhân viên nội bộ |
| `hr_employee_medical_examination` | Theo dõi lịch sử khám sức khỏe định kỳ |
| `hr_employee_relative` | Quản lý thông tin người thân (tab Người thân) |
| `hr_employee_service` | Tính thâm niên (năm/tháng) từ ngày bắt đầu làm việc |

### Web

| Module | Chức năng |
|--------|-----------|
| `web_responsive` | Giao diện responsive — hỗ trợ màn hình nhỏ và mobile |
| `web_refresher` | Nút Refresh trên thanh điều hướng để tải lại dữ liệu |
| `web_dialog_size` | Nút phóng to/thu nhỏ trên các cửa sổ dialog |

---

## Hướng dẫn sử dụng

### Thêm nhân viên mới

1. **Nhân sự → Nhân viên → Tạo mới**
2. Điền thông tin cơ bản: họ tên, chức vụ, phòng ban, quản lý, ngày vào
3. **Tab Công việc**: email, điện thoại, địa điểm làm việc, lịch làm việc
4. **Tab Cá nhân**:
   - Nhập số CMND/CCCD, ngày cấp, nơi cấp
   - Chọn dân tộc, tôn giáo
   - Nhập địa chỉ thường trú (tỉnh/huyện/xã/số nhà)
   - Tích "Giống địa chỉ thường trú" nếu tạm trú cùng địa chỉ
5. **Tab Bảo hiểm**: nhập số sổ BHXH, mã thẻ BHYT, ngày hết hạn
6. **Tab Thuế TNCN**: nhập MST; thêm người phụ thuộc nếu có
7. **Tab Tài khoản NH**: thêm tài khoản ngân hàng, đánh dấu tài khoản chính
8. **Lưu**

### Chuyển phòng ban

1. Mở form nhân viên → click **Chuyển phòng ban**
2. Chọn phòng ban mới, ngày hiệu lực, nhập số quyết định
3. Click **Xác nhận**

Hệ thống tự động tạo bản ghi lịch sử công tác trước khi thực hiện thay đổi.

### Đổi quản lý

1. Mở form nhân viên → click **Đổi quản lý**
2. Chọn quản lý mới → **Xác nhận**

### Cho nhân viên nghỉ việc

> Yêu cầu quyền **HR Manager**

1. Mở form nhân viên → click **Nghỉ việc**
2. Chọn lý do nghỉ, nhập ngày nghỉ việc
3. Click **Xác nhận nghỉ việc**

Nhân viên sẽ bị ẩn khỏi danh sách hoạt động. Để xem lại: bộ lọc **Đã nghỉ việc** hoặc bỏ bộ lọc **Đang hoạt động**.

### Xem lịch sử công tác

Vào **Tab Lịch sử công tác** trên form nhân viên — xem toàn bộ quá trình thay đổi phòng ban, chức danh, quản lý theo thời gian kèm số quyết định.

---

## Cấu hình production

Khi triển khai lên **Linux server**, bỏ comment block PRODUCTION trong `docker-compose.yml`:

```yaml
command: ["python", "odoo-bin", "-d", "odoo19",
  "--workers=4",              # 2*CPU + 1
  "--max-cron-threads=1",
  "--limit-memory-hard=2684354560",
  "--limit-memory-soft=2147483648",
  "--limit-time-cpu=600",
  "--limit-time-real=1200",
  "--db-filter=^odoo19$",
  "--proxy-mode"]
```

Khuyến nghị đặt **Nginx** làm reverse proxy:
- Xử lý SSL/HTTPS
- Gzip compression cho JS/CSS (~70% nhỏ hơn)
- Cache static files
- Proxy longpolling về port 8072

### Tuning PostgreSQL

File `postgres.conf` đã được cấu hình cho server 8GB RAM:

| Tham số | Giá trị | Mặc định |
|---------|---------|---------|
| `shared_buffers` | 512MB | 128MB |
| `work_mem` | 16MB | 4MB |
| `maintenance_work_mem` | 128MB | 64MB |
| `max_connections` | 50 | 100 |

---

## License

LGPL-3.0 — xem file [LICENSE](LICENSE)
