from odoo import _, api, fields, models
from odoo.exceptions import UserError


class CustomHrTerminateEmployeeWizard(models.TransientModel):
    _name = "custom_hr.terminate.employee.wizard"
    _description = "Xác nhận nghỉ việc"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        readonly=True,
    )
    departure_reason_id = fields.Many2one(
        "hr.departure.reason",
        string="Lý do nghỉ việc",
        required=True,
    )
    departure_date = fields.Date(
        string="Ngày nghỉ việc",
        required=True,
        default=fields.Date.today,
    )
    departure_description = fields.Text(
        string="Ghi chú",
    )

    @api.constrains("departure_date", "employee_id")
    def _check_departure_date(self):
        for rec in self:
            if rec.employee_id.join_date and rec.departure_date < rec.employee_id.join_date:
                raise UserError(
                    _("Ngày nghỉ việc không thể trước ngày vào làm (%s).")
                    % rec.employee_id.join_date
                )

    def action_confirm(self):
        self.ensure_one()
        employee = self.employee_id

        # Ghi lịch sử nghỉ việc trước khi deactivate
        employee._create_work_history_entry(
            change_reason="resign",
            note=self.departure_description or f"Nghỉ việc ngày {self.departure_date}",
        )
        employee.with_context(skip_work_history=True).write({
            "employment_status": "terminated",
            "active": False,
            "departure_reason_id": self.departure_reason_id.id,
            "departure_date": self.departure_date,
            "departure_description": self.departure_description,
        })
        return {"type": "ir.actions.act_window_close"}
