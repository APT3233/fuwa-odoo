"""Địa điểm chấm công hợp lệ (công ty, chi nhánh, khách hàng, công trường)."""
import math

from odoo import api, fields, models


class AttendanceLocation(models.Model):
    _name = 'attendance.location'
    _description = 'Địa điểm chấm công hợp lệ'
    _order = 'location_type, name'

    name = fields.Char(string='Tên địa điểm', required=True, index=True)
    location_type = fields.Selection([
        ('office', 'Văn phòng'),
        ('branch', 'Chi nhánh'),
        ('customer', 'Khách hàng'),
        ('site', 'Công trường'),
        ('other', 'Khác'),
    ], string='Loại', default='office', required=True, index=True)

    partner_id = fields.Many2one(
        'res.partner', string='Khách hàng',
        help='Liên kết với khách hàng (nếu là địa điểm khách hàng)',
    )
    company_id = fields.Many2one(
        'res.company', string='Công ty', default=lambda self: self.env.company,
    )

    # Stored as float for Haversine calculation
    latitude = fields.Float(digits=(10, 7), store=True)
    longitude = fields.Float(digits=(10, 7), store=True)

    # Char input fields to bypass locale decimal-separator issue
    # (Vietnamese locale uses "." as thousands sep → "16.051" → 16051)
    latitude_input = fields.Char(
        string='Vĩ độ',
        compute='_compute_coord_str', inverse='_set_latitude',
        help='Vĩ độ (latitude). Dùng dấu chấm hoặc phẩy làm dấu thập phân. VD: 16.051682',
    )
    longitude_input = fields.Char(
        string='Kinh độ',
        compute='_compute_coord_str', inverse='_set_longitude',
        help='Kinh độ (longitude). Dùng dấu chấm hoặc phẩy làm dấu thập phân. VD: 108.209630',
    )
    radius = fields.Integer(
        string='Bán kính cho phép (m)', default=200,
        help='Nhân viên check-in trong bán kính này được coi là hợp lệ',
    )
    address = fields.Char(string='Địa chỉ')
    active = fields.Boolean(default=True)

    google_maps_url = fields.Char(
        string='Xem trên Google Maps', compute='_compute_maps_url',
    )

    @api.depends('latitude', 'longitude')
    def _compute_coord_str(self):
        for rec in self:
            rec.latitude_input = ('%.7f' % rec.latitude) if rec.latitude else ''
            rec.longitude_input = ('%.7f' % rec.longitude) if rec.longitude else ''

    def _parse_coord(self, value):
        """Parse coordinate string, accepting both '.' and ',' as decimal separator."""
        if not value:
            return 0.0
        # Normalise: replace comma with dot, remove spaces
        s = value.strip().replace(',', '.').replace(' ', '')
        # If multiple dots remain (e.g. "16.051.682" → thousands-sep style),
        # keep only the last dot as decimal
        parts = s.split('.')
        if len(parts) > 2:
            s = ''.join(parts[:-1]) + '.' + parts[-1]
        try:
            return float(s)
        except ValueError:
            return 0.0

    def _set_latitude(self):
        for rec in self:
            rec.latitude = self._parse_coord(rec.latitude_input)

    def _set_longitude(self):
        for rec in self:
            rec.longitude = self._parse_coord(rec.longitude_input)

    @api.depends('latitude', 'longitude')
    def _compute_maps_url(self):
        for rec in self:
            if rec.latitude and rec.longitude:
                rec.google_maps_url = (
                    'https://www.google.com/maps?q=%s,%s' % (rec.latitude, rec.longitude)
                )
            else:
                rec.google_maps_url = False

    # -------------------------------------------------------------------------
    # Geo helpers
    # -------------------------------------------------------------------------
    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """Khoảng cách giữa 2 điểm GPS tính bằng mét."""
        R = 6371000.0  # Earth radius in meters
        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlam = math.radians(lon2 - lon1)
        a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    # Khoảng cách tối đa để map vào địa điểm (mét). Xa hơn → trả về (None, distance)
    MAX_MATCH_DISTANCE = 2000  # 2 km

    @api.model
    def find_nearest(self, latitude, longitude, company_id=None):
        """
        Tìm địa điểm gần nhất với vị trí GPS cho trước.

        Returns: (location, distance_meters) hoặc (None, distance) nếu không có location nào
        trong bán kính MAX_MATCH_DISTANCE.
        """
        domain = [
            ('active', '=', True),
            ('latitude', '!=', 0),
            ('longitude', '!=', 0),
        ]
        if company_id:
            domain.append(('company_id', 'in', [company_id, False]))

        locations = self.search(domain)
        if not locations:
            return (self.browse(), None)

        best = None
        best_dist = None
        for loc in locations:
            dist = self._haversine(latitude, longitude, loc.latitude, loc.longitude)
            if best_dist is None or dist < best_dist:
                best = loc
                best_dist = dist

        # Không map nếu địa điểm gần nhất vẫn quá xa
        if best_dist is not None and best_dist > self.MAX_MATCH_DISTANCE:
            return (self.browse(), best_dist)

        return (best, best_dist)
