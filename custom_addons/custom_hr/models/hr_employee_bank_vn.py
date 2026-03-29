# Thông tin tài khoản ngân hàng nhân viên (hỗ trợ nhiều tài khoản)
from odoo import fields, models


class CustomHrEmployeeBankVN(models.Model):
    _name = "custom_hr.employee.bank"
    _description = "Tài khoản ngân hàng nhân viên"
    _order = "employee_id, is_primary desc, id"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        ondelete="cascade",
        index=True,
    )
    bank_name = fields.Char(string="Tên ngân hàng", required=True)
    bank_branch = fields.Char(string="Chi nhánh")
    account_number = fields.Char(string="Số tài khoản", required=True, copy=False)
    account_holder = fields.Char(string="Chủ tài khoản")
    is_primary = fields.Boolean(string="Tài khoản chính", default=False)
    note = fields.Char(string="Ghi chú")

    _account_number_employee_uniq = models.Constraint(
        "unique(employee_id, account_number)",
        "Số tài khoản này đã tồn tại cho nhân viên này.",
    )


class HrEmployeeBankLink(models.Model):
    """Link One2many vào hr.employee."""
    _inherit = "hr.employee"

    custom_bank_account_ids = fields.One2many(
        "custom_hr.employee.bank",
        "employee_id",
        string="Tài khoản ngân hàng",
        groups="hr.group_hr_user",
    )
