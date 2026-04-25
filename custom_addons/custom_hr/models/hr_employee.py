import re
from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    employment_status = fields.Selection(
        [
            ("active", "Đang làm việc"),
            ("probation", "Thử việc"),
            ("terminated", "Nghỉ việc"),
        ],
        string="Trạng thái nhân sự",
        default="active",
        tracking=True,
        index=True,
    )
    employment_type = fields.Selection(
        [
            ("full_time", "Toàn thời gian"),
            ("part_time", "Bán thời gian"),
            ("contract", "Hợp đồng"),
            ("intern", "Thực tập"),
        ],
        string="Loại hình làm việc",
        default="full_time",
        tracking=True,
    )
    join_date = fields.Date(string="Ngày vào", tracking=True, index=True)

    @api.onchange("join_date")
    def _onchange_join_date(self):
        """Sync join_date vào service_start_date của hr_employee_service (OCA)."""
        if self.join_date and not self.service_start_date:
            self.service_start_date = self.join_date

    # ── Validation constraints ───────────────────────────────────────────────

    @api.constrains("parent_id")
    def _check_manager_circular(self):
        """Ngăn vòng lặp quản lý: A→B→A hoặc chuỗi dài hơn."""
        for record in self:
            if not record.parent_id:
                continue
            visited = {record.id}
            manager = record.parent_id
            while manager:
                if manager.id in visited:
                    raise ValidationError(
                        _("Không thể đặt quản lý: tạo ra vòng lặp phân cấp. "
                          "Nhân viên '%s' đã có trong chuỗi quản lý.")
                        % manager.name
                    )
                visited.add(manager.id)
                manager = manager.parent_id

    @api.constrains("work_email")
    def _check_work_email(self):
        email_re = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
        for record in self:
            if record.work_email and not email_re.match(record.work_email):
                raise ValidationError(
                    _("Email công việc '%s' không đúng định dạng.") % record.work_email
                )

    @api.constrains("work_phone", "mobile_phone")
    def _check_phone_format(self):
        """Số điện thoại: chỉ cho phép số, dấu +, -, (), space. Tối thiểu 7 ký tự số."""
        phone_re = re.compile(r'^[\d\s\+\-\(\)\.]{7,20}$')
        for record in self:
            for fname, label in [("work_phone", "Điện thoại bàn"),
                                  ("mobile_phone", "Di động")]:
                val = record[fname]
                if val:
                    digits_only = re.sub(r'\D', '', val)
                    if not phone_re.match(val) or len(digits_only) < 7:
                        raise ValidationError(
                            _("%s '%s' không đúng định dạng. "
                              "Chỉ chứa số, dấu +, -, (, ), khoảng trắng. Tối thiểu 7 chữ số.")
                            % (label, val)
                        )

    @api.constrains("ssnid")
    def _check_ssnid_format(self):
        """CMND (9 số) hoặc CCCD (12 số)."""
        for record in self:
            if record.ssnid:
                digits = re.sub(r'\D', '', record.ssnid)
                if len(digits) not in (9, 12):
                    raise ValidationError(
                        _("CMND/CCCD '%s' phải có 9 hoặc 12 chữ số.") % record.ssnid
                    )

    @api.constrains("join_date", "birthday")
    def _check_join_date_after_birthday(self):
        for record in self:
            if record.join_date and record.birthday:
                if record.join_date < record.birthday:
                    raise ValidationError(
                        _("Ngày vào làm (%s) không thể trước ngày sinh (%s).")
                        % (record.join_date, record.birthday)
                    )

    # ── Wizard actions ────────────────────────────────────────────────────────

    def action_open_transfer_department(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Chuyển phòng ban",
            "res_model": "custom_hr.transfer.department.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_employee_id": self.id},
        }

    def action_open_change_manager(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Đổi quản lý",
            "res_model": "custom_hr.change.manager.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_employee_id": self.id},
        }

    def action_open_update_info(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Cập nhật thông tin",
            "res_model": "hr.employee",
            "view_mode": "form",
            "res_id": self.id,
            "target": "current",
        }

    def action_terminate_employee(self):
        self.ensure_one()
        return self.action_open_terminate_employee()

    def action_open_terminate_employee(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": "Nghỉ việc",
            "res_model": "custom_hr.terminate.employee.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_employee_id": self.id},
        }

    def write(self, vals):
        res = super().write(vals)
        if 'image_1920' in vals and not self.env.context.get('_sync_employee_image'):
            for employee in self:
                if employee.user_id:
                    employee.user_id.sudo().with_context(_sync_employee_image=True).write(
                        {'image_1920': vals['image_1920']}
                    )
        return res
