from odoo import fields, models


class CustomHrChangeManagerWizard(models.TransientModel):
    _name = "custom_hr.change.manager.wizard"
    _description = "Đổi quản lý"

    employee_id = fields.Many2one("hr.employee", string="Nhân viên", required=True)
    manager_id = fields.Many2one(
        "hr.employee",
        string="Quản lý mới",
        required=True,
        domain="[('id', '!=', employee_id)]",
    )

    def action_confirm(self):
        self.ensure_one()
        employee = self.employee_id

        # Ghi lịch sử trước khi thay đổi, rồi skip auto-log trong write()
        employee._create_work_history_entry(
            change_reason="other",
            note=f"Đổi quản lý: {self.manager_id.name}",
        )
        employee.with_context(skip_work_history=True).write(
            {"parent_id": self.manager_id.id}
        )
        return {"type": "ir.actions.act_window_close"}
