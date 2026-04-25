from odoo import fields, models


class CustomHrTransferDepartmentWizard(models.TransientModel):
    _name = "custom_hr.transfer.department.wizard"
    _description = "Chuyển phòng ban"

    employee_id = fields.Many2one("hr.employee", string="Nhân viên", required=True)
    department_id = fields.Many2one("hr.department", string="Phòng ban mới", required=True)
    effective_date = fields.Date(
        string="Ngày hiệu lực",
        required=True,
        default=fields.Date.today,
    )
    decision_number = fields.Char(string="Số quyết định")
    note = fields.Text(string="Ghi chú")

    def action_confirm(self):
        self.ensure_one()
        employee = self.employee_id

        # Ghi lịch sử công tác trước khi thay đổi
        self.env["custom_hr.work.history"].create({
            "employee_id": employee.id,
            "start_date": employee.join_date or fields.Date.today(),
            "end_date": self.effective_date,
            "department_id": employee.department_id.id,
            "job_id": employee.job_id.id,
            "job_title": employee.job_title,
            "manager_id": employee.parent_id.id,
            "change_reason": "transfer",
            "decision_number": self.decision_number,
            "note": self.note or f"Chuyển sang: {self.department_id.name}",
            "created_by_wizard": True,
        })

        # skip_work_history=True: wizard đã tự tạo history bên trên, tránh double-log
        employee.with_context(skip_work_history=True).write(
            {"department_id": self.department_id.id}
        )
        return {"type": "ir.actions.act_window_close"}
