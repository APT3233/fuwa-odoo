from odoo import api, fields, models


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
        """Backward-compat alias — redirects to the confirmation wizard."""
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
