"""Override hr.employee để fix access + tích hợp GPS location khi check-in thủ công."""
import logging
from datetime import datetime, timezone

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    # In Odoo 19, attendance_manager_id has groups='..._officer' which blocks
    # regular employees (own.reader only) from reading their own attendance.
    # Must pass groups=False EXPLICITLY — omitting groups= keeps the base value.
    attendance_manager_id = fields.Many2one(
        'res.users',
        string='Attendance Manager',
        groups=False,
    )

    def _attendance_action_change(self, geo_information=None):
        """Override để populate location fields từ GPS khi check-in/out thủ công."""
        was_checked_in = self.attendance_state == 'checked_in'

        # Block checkout nếu check-in chưa đủ 1 phút
        if was_checked_in:
            open_att = self.env['hr.attendance'].search([
                ('employee_id', '=', self.id),
                ('check_out', '=', False),
            ], limit=1, order='check_in desc')
            if open_att:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                elapsed = (now - open_att.check_in).total_seconds()
                if elapsed < 60:
                    remaining = int(60 - elapsed)
                    raise UserError(_(
                        'Bạn vừa check-in rồi, vui lòng đợi %(s)d giây nữa để check-out.',
                        s=remaining,
                    ))

        attendance = super()._attendance_action_change(geo_information)

        if not geo_information:
            return attendance

        lat = geo_information.get('latitude')
        lng = geo_information.get('longitude')
        if not lat or not lng:
            return attendance

        try:
            lat = float(lat)
            lng = float(lng)
            Location = self.env['attendance.location'].sudo()
            nearest, distance = Location.find_nearest(lat, lng, company_id=self.company_id.id)
            is_valid = bool(nearest and distance is not None and distance <= nearest.radius)

            if not was_checked_in:
                # Vừa check IN
                attendance.write({
                    'check_in_latitude': lat,
                    'check_in_longitude': lng,
                    'check_in_location_id': nearest.id if (nearest and is_valid) else False,
                    'check_in_distance': round(distance, 1) if distance is not None else 0.0,
                    'check_in_valid': is_valid,
                    'check_mode': 'manual',
                })
            else:
                # Vừa check OUT
                attendance.write({
                    'check_out_latitude': lat,
                    'check_out_longitude': lng,
                    'check_out_location_id': nearest.id if (nearest and is_valid) else False,
                    'check_out_distance': round(distance, 1) if distance is not None else 0.0,
                    'check_out_valid': is_valid,
                })
        except Exception as e:
            _logger.warning('field_attendance: GPS location enrichment failed: %s', e)

        return attendance
