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
    # index=True: hỗ trợ sort theo (employee_id, start_date desc) hiệu quả
    start_date = fields.Date(string="Từ ngày", required=True, index=True)
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
    """Gắn One2many work_history_ids vào hr.employee và xử lý auto-logging."""

    _inherit = "hr.employee"

    work_history_ids = fields.One2many(
        "custom_hr.work.history",
        "employee_id",
        string="Lịch sử công tác",
        groups="hr.group_hr_user",
    )

    def _create_work_history_entry(self, change_reason="transfer", note=""):
        """Tạo bản ghi lịch sử công tác từ trạng thái HIỆN TẠI của nhân viên.

        Luôn gọi TRƯỚC khi thay đổi department_id / parent_id / job_id để
        bản ghi phản ánh đúng trạng thái cũ.
        """
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

    def write(self, vals):
        """Auto-tạo work history khi department/manager thay đổi trực tiếp.

        Bỏ qua nếu context có skip_work_history=True (wizard đã tự log).
        """
        if not self.env.context.get("skip_work_history"):
            _TRIGGERS = frozenset({"department_id", "parent_id", "job_id", "job_title"})
            if _TRIGGERS & set(vals.keys()):
                for record in self:
                    new_dept_id = vals.get("department_id")
                    new_mgr_id = vals.get("parent_id")
                    new_job_id = vals.get("job_id")

                    if new_dept_id and new_dept_id != record.department_id.id:
                        dept_name = self.env["hr.department"].browse(new_dept_id).name
                        record._create_work_history_entry(
                            change_reason="transfer",
                            note=f"Chuyển sang: {dept_name}",
                        )
                    elif new_mgr_id and new_mgr_id != record.parent_id.id:
                        mgr_name = self.env["hr.employee"].browse(new_mgr_id).name
                        record._create_work_history_entry(
                            change_reason="other",
                            note=f"Đổi quản lý: {mgr_name}",
                        )
                    elif new_job_id and new_job_id != record.job_id.id:
                        job_name = self.env["hr.job"].browse(new_job_id).name
                        record._create_work_history_entry(
                            change_reason="other",
                            note=f"Đổi chức danh: {job_name}",
                        )
        return super().write(vals)
