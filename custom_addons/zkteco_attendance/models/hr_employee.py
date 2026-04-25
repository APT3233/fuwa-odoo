from odoo import fields, models


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    zkteco_pin = fields.Char(
        string='PIN máy chấm công',
        copy=False,
        help='ID nhân viên được lưu trên máy ZKTeco (thường là số thứ tự hoặc mã nhân viên)',
    )


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    zkteco_device_id = fields.Many2one('zkteco.device', string='Máy chấm công',
        readonly=True, index=True)
    zkteco_log_checkin_id = fields.Many2one('zkteco.attendance.log',
        string='Log check-in', readonly=True)
    zkteco_log_checkout_id = fields.Many2one('zkteco.attendance.log',
        string='Log check-out', readonly=True)
