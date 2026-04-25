import secrets
from odoo import api, fields, models


class ZktecoDevice(models.Model):
    _name = 'zkteco.device'
    _description = 'Máy chấm công ZKTeco'
    _order = 'name'

    name = fields.Char(string='Tên máy', required=True)
    serial_number = fields.Char(string='Serial Number', readonly=True, copy=False,
        help='Serial number do máy tự gửi lên khi kết nối')
    location = fields.Char(string='Vị trí', help='Ví dụ: Cổng chính, Tầng 2...')
    active = fields.Boolean(default=True)
    state = fields.Selection([
        ('waiting', 'Chờ kết nối'),
        ('connected', 'Đã kết nối'),
        ('error', 'Lỗi'),
    ], string='Trạng thái', default='waiting', readonly=True)
    last_activity = fields.Datetime(string='Hoạt động cuối', readonly=True)
    token = fields.Char(string='Token xác thực', copy=False,
        help='Token dùng để xác thực máy ZKTeco. Để trống = không yêu cầu xác thực.')

    log_ids = fields.One2many('zkteco.attendance.log', 'device_id', string='Lịch sử chấm công')
    log_count = fields.Integer(compute='_compute_log_count', string='Số bản ghi')

    attendance_count = fields.Integer(compute='_compute_attendance_count', string='Lượt chấm công')

    @api.depends('log_ids')
    def _compute_log_count(self):
        for device in self:
            device.log_count = len(device.log_ids)

    def _compute_attendance_count(self):
        for device in self:
            device.attendance_count = self.env['hr.attendance'].search_count([
                ('zkteco_device_id', '=', device.id)
            ])

    def action_generate_token(self):
        self.token = secrets.token_hex(16)

    def action_view_logs(self):
        return {
            'name': 'Log chấm công',
            'type': 'ir.actions.act_window',
            'res_model': 'zkteco.attendance.log',
            'view_mode': 'list,form',
            'domain': [('device_id', '=', self.id)],
            'context': {'default_device_id': self.id},
        }

    def action_view_attendances(self):
        return {
            'name': 'Chấm công',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.attendance',
            'view_mode': 'list,form',
            'domain': [('zkteco_device_id', '=', self.id)],
        }
