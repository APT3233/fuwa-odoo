from odoo import _, api, models
from odoo.exceptions import ValidationError


class ResourceCalendarAttendance(models.Model):
    _inherit = "resource.calendar.attendance"

    @api.constrains("dayofweek")
    def _check_weekday_only(self):
        for rec in self:
            if rec.dayofweek in ("5", "6"):
                raise ValidationError(
                    _("Lịch làm việc chỉ được phép từ Thứ 2 đến Thứ 6. "
                      "Vui lòng không thêm ca làm việc vào Thứ 7 hoặc Chủ nhật.")
                )
