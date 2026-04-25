from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    google_maps_api_key = fields.Char(
        string='Google Maps API Key',
        config_parameter='field_attendance.google_maps_api_key',
        help='API key dùng để nhúng Google Maps vào form chấm công. '
             'Lấy tại https://console.cloud.google.com → APIs → Maps Embed API',
    )
    attendance_default_radius = fields.Integer(
        string='Bán kính check-in mặc định (m)',
        config_parameter='field_attendance.default_radius',
        default=200,
    )
    attendance_require_selfie_checkout = fields.Boolean(
        string='Yêu cầu selfie khi check-out',
        config_parameter='field_attendance.require_selfie_checkout',
        default=False,
        help='Nếu bật: nhân viên phải chụp selfie cả khi check-out. Mặc định: chỉ check-in',
    )
    office_latitude = fields.Float(
        related='company_id.office_latitude', readonly=False,
    )
    office_longitude = fields.Float(
        related='company_id.office_longitude', readonly=False,
    )
    attendance_radius = fields.Integer(
        related='company_id.attendance_radius', readonly=False,
    )
