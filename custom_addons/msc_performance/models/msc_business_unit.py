from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MscBusinessUnit(models.Model):
    _name = "msc.business.unit"
    _description = "Đơn vị kinh doanh MSC"
    _order = "year desc, name"

    name = fields.Char(string="Tên đơn vị", required=True)
    year = fields.Integer(string="Năm", required=True)
    active = fields.Boolean(default=True)
    description = fields.Text(string="Mô tả")

    bul_id = fields.Many2one(
        "hr.employee",
        string="BUL (Branch Manager)",
        required=True,
        domain=[("active", "=", True)],
    )
    vice_bul_ids = fields.Many2many(
        "hr.employee",
        "msc_bu_vice_bul_rel",
        "bu_id",
        "employee_id",
        string="Phó BUL",
    )
    pm_ids = fields.Many2many(
        "hr.employee",
        "msc_bu_pm_rel",
        "bu_id",
        "employee_id",
        string="PM (Manager)",
    )
    watcher_ids = fields.Many2many(
        "hr.employee",
        "msc_bu_watcher_rel",
        "bu_id",
        "employee_id",
        string="Người theo dõi",
    )

    @api.constrains("bul_id", "pm_ids", "vice_bul_ids")
    def _check_no_overlap(self):
        for rec in self:
            bul = rec.bul_id
            if bul and bul in rec.pm_ids:
                raise ValidationError(_("BUL không thể đồng thời là PM trong cùng đơn vị."))
            vice_buls = rec.vice_bul_ids
            overlap = vice_buls & rec.pm_ids
            if overlap:
                names = ", ".join(overlap.mapped("name"))
                raise ValidationError(
                    _("Nhân viên '%s' không thể vừa là Phó BUL vừa là PM.") % names
                )
