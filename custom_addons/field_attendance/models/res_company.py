"""Thêm tọa độ GPS cho văn phòng công ty."""
from odoo import fields, models


class ResCompany(models.Model):
    _inherit = 'res.company'

    office_latitude = fields.Float(
        string='Vĩ độ văn phòng', digits=(10, 7),
        help='Tọa độ GPS của văn phòng chính (dùng để validate check-in ngoài)',
    )
    office_longitude = fields.Float(
        string='Kinh độ văn phòng', digits=(10, 7),
    )
    attendance_radius = fields.Integer(
        string='Bán kính check-in (m)', default=200,
        help='Bán kính mặc định cho phép check-in quanh văn phòng',
    )
