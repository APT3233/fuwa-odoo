"""Mở rộng hr.attendance để thêm dữ liệu field check-in."""
import logging
from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

_logger = logging.getLogger(__name__)


class HrAttendance(models.Model):
    _inherit = 'hr.attendance'

    check_mode = fields.Selection([
        ('office', 'Văn phòng (ZKTeco)'),
        ('field', 'Công tác ngoài'),
        ('manual', 'Thủ công'),
    ], string='Hình thức', default='manual', index=True, readonly=True)

    # -------------------------------------------------------------------------
    # Check-in
    # -------------------------------------------------------------------------
    check_in_latitude = fields.Float('Vĩ độ check-in', digits=(10, 7), readonly=True)
    check_in_longitude = fields.Float('Kinh độ check-in', digits=(10, 7), readonly=True)
    check_in_selfie = fields.Image(
        'Ảnh selfie check-in', max_width=800, max_height=800, readonly=True,
    )
    check_in_location_id = fields.Many2one(
        'attendance.location', string='Địa điểm check-in', readonly=True,
    )
    check_in_distance = fields.Float(
        'Khoảng cách check-in (m)', digits=(10, 1), readonly=True,
        help='Khoảng cách từ vị trí GPS đến địa điểm gần nhất',
    )
    check_in_valid = fields.Boolean(
        'Check-in hợp lệ', readonly=True,
        help='Check-in trong bán kính cho phép của địa điểm',
    )
    check_in_note = fields.Char('Ghi chú check-in')

    # -------------------------------------------------------------------------
    # Check-out
    # -------------------------------------------------------------------------
    check_out_latitude = fields.Float('Vĩ độ check-out', digits=(10, 7), readonly=True)
    check_out_longitude = fields.Float('Kinh độ check-out', digits=(10, 7), readonly=True)
    check_out_selfie = fields.Image(
        'Ảnh selfie check-out', max_width=800, max_height=800, readonly=True,
    )
    check_out_location_id = fields.Many2one(
        'attendance.location', string='Địa điểm check-out', readonly=True,
    )
    check_out_distance = fields.Float(
        'Khoảng cách check-out (m)', digits=(10, 1), readonly=True,
    )
    check_out_valid = fields.Boolean('Check-out hợp lệ', readonly=True)
    check_out_note = fields.Char('Ghi chú check-out')

    # -------------------------------------------------------------------------
    # New location flag
    # -------------------------------------------------------------------------
    is_new_location = fields.Boolean(
        'Địa điểm mới', default=False, readonly=True, index=True,
        help='Nhân viên tự đăng ký địa điểm công tác mới khi check-in',
    )

    # -------------------------------------------------------------------------
    # Review
    # -------------------------------------------------------------------------
    review_state = fields.Selection([
        ('working', 'Đang làm việc'),
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã duyệt'),
        ('rejected', 'Từ chối'),
        ('no_checkout', 'Không checkout'),
    ], string='Trạng thái duyệt', default='pending', index=True, tracking=True)
    review_notes = fields.Text('Ghi chú duyệt')
    reviewed_by = fields.Many2one('res.users', string='Người duyệt', readonly=True)
    reviewed_on = fields.Datetime('Ngày duyệt', readonly=True)

    # -------------------------------------------------------------------------
    # Computed: Google Maps embed HTML (iframe) — dùng widget="html" trong form
    # -------------------------------------------------------------------------
    check_in_map_html = fields.Html(
        'Bản đồ check-in', compute='_compute_map_html', sanitize=False,
    )
    check_out_map_html = fields.Html(
        'Bản đồ check-out', compute='_compute_map_html', sanitize=False,
    )

    @api.depends('check_in_latitude', 'check_in_longitude',
                 'check_out_latitude', 'check_out_longitude')
    def _compute_map_html(self):
        ICP = self.env['ir.config_parameter'].sudo()
        api_key = ICP.get_param('field_attendance.google_maps_api_key', '')
        for rec in self:
            rec.check_in_map_html = self._build_map_iframe(
                rec.check_in_latitude, rec.check_in_longitude, api_key,
            )
            rec.check_out_map_html = self._build_map_iframe(
                rec.check_out_latitude, rec.check_out_longitude, api_key,
            )

    @staticmethod
    def _build_map_iframe(lat, lng, api_key=''):
        if not lat or not lng:
            return False
        if api_key:
            src = (
                'https://www.google.com/maps/embed/v1/place'
                '?key=%s&q=%s,%s&zoom=17'
            ) % (api_key, lat, lng)
        else:
            src = 'https://maps.google.com/maps?q=%s,%s&z=17&output=embed' % (lat, lng)
        return (
            '<iframe src="%s" width="100%%" height="180" frameborder="0" '
            'style="border:0;border-radius:8px;display:block;min-height:180px;max-height:180px" '
            'allowfullscreen></iframe>'
        ) % src

    # -------------------------------------------------------------------------
    # Override worked_hours: không tính công cho ca "Không checkout"
    # -------------------------------------------------------------------------
    def _compute_worked_hours(self):
        super()._compute_worked_hours()
        for att in self:
            if att.review_state == 'no_checkout':
                att.worked_hours = 0.0

    # -------------------------------------------------------------------------
    # Auto-detect check_mode on create
    # -------------------------------------------------------------------------
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('check_mode'):
                # ZKTeco module creates with zkteco_device_id
                if 'zkteco_device_id' in self._fields and vals.get('zkteco_device_id'):
                    vals['check_mode'] = 'office'
                elif vals.get('check_in_latitude') or vals.get('check_in_longitude'):
                    vals['check_mode'] = 'field'

            # office/manual: check-in → Đang làm việc; field: Chờ duyệt
            if vals.get('check_mode', 'manual') != 'field':
                vals.setdefault('review_state', 'working')

        return super().create(vals_list)

    def write(self, vals):
        res = super().write(vals)
        # Khi checkout xong: office/manual → Đã duyệt
        if 'check_out' in vals and vals['check_out']:
            to_approve = self.filtered(
                lambda a: a.check_mode != 'field' and a.review_state in ('working', 'pending')
            )
            if to_approve:
                to_approve.write({'review_state': 'approved'})
        return res

    # -------------------------------------------------------------------------
    # Review actions (HR)
    # -------------------------------------------------------------------------
    def action_approve(self):
        self._check_review_access()
        self.write({
            'review_state': 'approved',
            'reviewed_by': self.env.user.id,
            'reviewed_on': fields.Datetime.now(),
        })

    def action_reject(self):
        self._check_review_access()
        self.write({
            'review_state': 'rejected',
            'reviewed_by': self.env.user.id,
            'reviewed_on': fields.Datetime.now(),
        })

    def action_reset_review(self):
        self._check_review_access()
        self.write({
            'review_state': 'pending',
            'reviewed_by': False,
            'reviewed_on': False,
        })

    def _check_review_access(self):
        if not self.env.user.has_group('hr_attendance.group_hr_attendance_manager'):
            raise ValidationError(_('Chỉ HR Manager mới được duyệt chấm công.'))

    # -------------------------------------------------------------------------
    # Cron: tự động đóng ca chưa checkout sang ngày mới
    # -------------------------------------------------------------------------
    @api.model
    def _cron_auto_checkout_midnight(self):
        """
        Chạy lúc 00:05 (UTC+7 = 17:05 UTC hôm trước).
        Tìm tất cả attendance còn mở (check_out IS NULL) mà check_in
        thuộc ngày hôm qua (theo giờ VN) → tự checkout lúc 23:59:59
        hôm đó và set review_state = 'no_checkout'.
        """
        import pytz
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        now_vn = fields.Datetime.now().astimezone(vn_tz)
        # "Hôm qua" theo giờ VN
        yesterday_vn = (now_vn - timedelta(days=1)).date()
        # Đầu và cuối ngày hôm qua theo UTC
        start_utc = vn_tz.localize(
            fields.Datetime.from_string(str(yesterday_vn) + ' 00:00:00')
        ).astimezone(pytz.utc).replace(tzinfo=None)
        end_utc = vn_tz.localize(
            fields.Datetime.from_string(str(yesterday_vn) + ' 23:59:59')
        ).astimezone(pytz.utc).replace(tzinfo=None)

        stale = self.search([
            ('check_out', '=', False),
            ('check_in', '>=', start_utc),
            ('check_in', '<=', end_utc),
        ])
        if not stale:
            return

        _logger.info('field_attendance cron: auto-checkout %d record(s) from %s',
                     len(stale), yesterday_vn)
        for att in stale:
            # Checkout lúc 23:59:59 ngày check-in (UTC)
            checkout_time = vn_tz.localize(
                fields.Datetime.from_string(str(yesterday_vn) + ' 23:59:59')
            ).astimezone(pytz.utc).replace(tzinfo=None)
            # Dùng sudo để bypass các constraint nếu có
            att.sudo().write({
                'check_out': checkout_time,
                'review_state': 'no_checkout',
            })
