import logging
from datetime import timedelta

from odoo import api, fields, models

_logger = logging.getLogger(__name__)

# Max gap between check-in and check-out to be paired (hours)
MAX_WORK_HOURS = 24


class ZktecoAttendanceLog(models.Model):
    """Raw log từ máy ZKTeco trước khi xử lý thành hr.attendance"""
    _name = 'zkteco.attendance.log'
    _description = 'Log chấm công ZKTeco'
    _order = 'punch_time desc'
    _rec_name = 'punch_time'

    device_id = fields.Many2one('zkteco.device', string='Máy chấm công',
        required=True, ondelete='cascade', index=True)
    pin = fields.Char(string='PIN nhân viên', required=True, index=True,
        help='ID nhân viên trên máy ZKTeco')
    employee_id = fields.Many2one('hr.employee', string='Nhân viên',
        compute='_compute_employee', store=True)
    punch_time = fields.Datetime(string='Thời gian chấm', required=True)
    punch_type = fields.Selection([
        ('0', 'Check-in'),
        ('1', 'Check-out'),
        ('4', 'OT-in'),
        ('5', 'OT-out'),
    ], string='Loại', default='0')
    state = fields.Selection([
        ('new', 'Mới'),
        ('processed', 'Đã xử lý'),
        ('error', 'Lỗi'),
        ('ignored', 'Bỏ qua'),
    ], string='Trạng thái', default='new', index=True)
    error_msg = fields.Char(string='Lỗi')
    attendance_id = fields.Many2one('hr.attendance', string='Bản ghi chấm công',
        readonly=True)
    raw_data = fields.Text(string='Dữ liệu gốc', readonly=True)

    @api.depends('pin')
    def _compute_employee(self):
        for log in self:
            employee = self.env['hr.employee'].search([
                ('zkteco_pin', '=', log.pin)
            ], limit=1)
            log.employee_id = employee or False

    def action_reprocess(self):
        """Reprocess failed/ignored logs."""
        logs = self.filtered(lambda l: l.state in ('error', 'ignored', 'new'))
        logs.write({'state': 'new', 'error_msg': False})
        logs._process_attendance()

    def _process_attendance(self):
        """
        Convert raw ZKTeco logs into hr.attendance records.

        Strategy:
        - Group logs by employee
        - Sort by punch_time
        - Pair check-in / check-out chronologically
        - If punch_type is explicit (0=in, 1=out) use it; otherwise auto-detect
          by alternating: first punch of day = check-in, next = check-out, etc.
        """
        Attendance = self.env['hr.attendance']

        # Group by pin
        pin_logs = {}
        for log in self:
            pin_logs.setdefault(log.pin, []).append(log)

        for pin, logs in pin_logs.items():
            # Find employee
            employee = self.env['hr.employee'].search([
                ('zkteco_pin', '=', pin)
            ], limit=1)
            if not employee:
                for log in logs:
                    log.write({
                        'state': 'error',
                        'error_msg': 'Không tìm thấy nhân viên với PIN=%s' % pin,
                    })
                continue

            # Sort by punch_time
            sorted_logs = sorted(logs, key=lambda l: l.punch_time)

            for log in sorted_logs:
                if log.state != 'new':
                    continue
                try:
                    self._pair_log(log, employee, Attendance)
                except Exception as e:
                    _logger.error('ZKTeco: error processing log %s: %s', log.id, e)
                    log.write({'state': 'error', 'error_msg': str(e)[:200]})

    def _pair_log(self, log, employee, Attendance):
        """
        Process a single log record into hr.attendance.

        Auto-detect mode: ignore punch_type from device.
        - If employee has an open attendance (check-in without check-out) → this is check-out
        - If no open attendance → this is check-in
        - Duplicate threshold: ignore if same direction within 1 minute
        """
        punch_time = log.punch_time

        # Find open attendance (check-in without check-out) within MAX_WORK_HOURS
        open_att = Attendance.search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
            ('check_in', '<=', punch_time),
            ('check_in', '>=', punch_time - timedelta(hours=MAX_WORK_HOURS)),
        ], limit=1, order='check_in desc')

        if open_att:
            # Has open check-in → this punch is check-out
            gap = (punch_time - open_att.check_in).total_seconds()
            if gap < 60:
                # Too close to check-in — likely duplicate scan, ignore
                log.write({'state': 'ignored',
                           'error_msg': 'Trùng lặp (quét lại trong vòng 1 phút)',
                           'attendance_id': open_att.id})
                return
            open_att.write({
                'check_out': punch_time,
                'zkteco_log_checkout_id': log.id,
            })
            log.write({'state': 'processed', 'attendance_id': open_att.id,
                       'punch_type': '1'})
        else:
            # No open check-in → this punch is check-in
            # Check if duplicate check-in very recently
            recent = Attendance.search([
                ('employee_id', '=', employee.id),
                ('check_in', '>=', punch_time - timedelta(minutes=1)),
                ('check_in', '<=', punch_time),
            ], limit=1)
            if recent:
                log.write({'state': 'ignored',
                           'error_msg': 'Trùng lặp check-in (trong vòng 1 phút)',
                           'attendance_id': recent.id})
                return

            att = Attendance.create({
                'employee_id': employee.id,
                'check_in': punch_time,
                'zkteco_device_id': log.device_id.id,
                'zkteco_log_checkin_id': log.id,
            })
            log.write({'state': 'processed', 'attendance_id': att.id})
