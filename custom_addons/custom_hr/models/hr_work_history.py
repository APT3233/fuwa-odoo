# Lịch sử quá trình công tác của nhân viên
from odoo import api, fields, models


class CustomHrWorkHistory(models.Model):
    _name = "custom_hr.work.history"
    _description = "Lịch sử quá trình công tác"
    _order = "employee_id, start_date desc"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        ondelete="cascade",
        index=True,
    )
    start_date = fields.Date(string="Từ ngày", required=True)
    end_date = fields.Date(string="Đến ngày")
    department_id = fields.Many2one("hr.department", string="Phòng ban")
    job_id = fields.Many2one("hr.job", string="Chức danh")
    job_title = fields.Char(string="Chức vụ")
    manager_id = fields.Many2one("hr.employee", string="Quản lý trực tiếp")
    decision_number = fields.Char(string="Số quyết định")
    change_reason = fields.Selection(
        [
            ("transfer", "Chuyển phòng ban"),
            ("promotion", "Thăng chức"),
            ("demotion", "Điều chuyển"),
            ("onboard", "Nhận việc"),
            ("resign", "Nghỉ việc"),
            ("other", "Khác"),
        ],
        string="Lý do thay đổi",
        default="transfer",
    )
    note = fields.Text(string="Ghi chú")
    created_by_wizard = fields.Boolean(default=False, readonly=True)


class HrEmployeeWorkHistoryLink(models.Model):
    """Link One2many vào hr.employee."""
    _inherit = "hr.employee"

    work_history_ids = fields.One2many(
        "custom_hr.work.history",
        "employee_id",
        string="Lịch sử công tác",
        groups="hr.group_hr_user",
    )

    def _create_work_history_entry(self, change_reason="transfer", note=""):
        """Tạo bản ghi lịch sử công tác từ trạng thái hiện tại của nhân viên."""
        self.ensure_one()
        self.env["custom_hr.work.history"].create({
            "employee_id": self.id,
            "start_date": fields.Date.today(),
            "department_id": self.department_id.id,
            "job_id": self.job_id.id,
            "job_title": self.job_title,
            "manager_id": self.parent_id.id,
            "change_reason": change_reason,
            "note": note,
            "created_by_wizard": True,
        })
