"""
HTTP controller cho chấm công công tác ngoài (Field Check-in).

Flow:
  1. Nhân viên mở menu "Chấm công công tác" trên mobile
  2. OWL component xin quyền camera + geolocation
  3. User chụp selfie → base64
  4. POST /field_attendance/checkin với {latitude, longitude, selfie, note}
  5. Server validate khoảng cách, tạo/cập nhật hr.attendance
"""
import logging

from odoo import _, fields, http
from odoo.exceptions import UserError, ValidationError
from odoo.http import request

_logger = logging.getLogger(__name__)


class FieldAttendanceController(http.Controller):

    @http.route(
        '/field_attendance/state', type='json', auth='user', methods=['POST'],
        csrf=False,
    )
    def get_state(self):
        """
        Trả về trạng thái hiện tại cho mobile UI:
          - employee info
          - open attendance (nếu đang check-in)
          - google maps api key
          - require_selfie_checkout flag
        """
        employee = self._get_current_employee()
        if not employee:
            return {
                'error': _('Không tìm thấy hồ sơ nhân viên cho user hiện tại'),
            }

        ICP = request.env['ir.config_parameter'].sudo()
        api_key = ICP.get_param('field_attendance.google_maps_api_key', '')
        require_selfie_checkout = ICP.get_param(
            'field_attendance.require_selfie_checkout', 'False'
        ) == 'True'

        # Tìm attendance đang mở (chưa check-out)
        open_att = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
        ], limit=1, order='check_in desc')

        return {
            'employee': {
                'id': employee.id,
                'name': employee.name,
                'avatar': '/web/image/hr.employee.public/%s/avatar_128' % employee.id,
                'department': employee.department_id.name or '',
                'job': employee.job_title or '',
            },
            'open_attendance': {
                'id': open_att.id,
                'check_in': open_att.check_in and open_att.check_in.isoformat() or False,
                'check_in_location': open_att.check_in_location_id.name or '',
                'check_in_valid': open_att.check_in_valid,
            } if open_att else False,
            'google_maps_api_key': api_key,
            'require_selfie_checkout': require_selfie_checkout,
        }

    @http.route(
        '/field_attendance/checkin', type='json', auth='user', methods=['POST'],
        csrf=False,
    )
    def checkin(self, latitude, longitude, selfie, note=None):
        """
        Tạo hr.attendance mới cho field check-in.

        Params:
          latitude (float)
          longitude (float)
          selfie (str): base64 data URL (data:image/jpeg;base64,...)
          note (str, optional)
        """
        employee = self._get_current_employee()
        if not employee:
            return {'success': False, 'error': _('Không tìm thấy hồ sơ nhân viên')}

        if not latitude or not longitude:
            return {'success': False, 'error': _('Thiếu tọa độ GPS')}

        if not selfie:
            return {'success': False, 'error': _('Bắt buộc phải chụp ảnh selfie')}

        # Không cho phép check-in chồng
        existing = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
        ], limit=1)
        if existing:
            return {
                'success': False,
                'error': _('Bạn đang có phiên chấm công chưa kết thúc. Vui lòng check-out trước.'),
                'open_attendance_id': existing.id,
            }

        # Parse selfie base64 (strip data URL prefix)
        selfie_binary = self._decode_selfie(selfie)

        # Validate khoảng cách
        Location = request.env['attendance.location'].sudo()
        nearest, distance = Location.find_nearest(
            float(latitude), float(longitude), company_id=employee.company_id.id,
        )
        is_valid = False
        if nearest and distance is not None:
            is_valid = distance <= nearest.radius

        vals = {
            'employee_id': employee.id,
            'check_in': fields.Datetime.now(),
            'check_mode': 'field',
            'check_in_latitude': float(latitude),
            'check_in_longitude': float(longitude),
            'check_in_selfie': selfie_binary,
            'check_in_location_id': nearest.id if (nearest and is_valid) else False,
            'check_in_distance': distance or 0.0,
            'check_in_valid': is_valid,
            'check_in_note': note or '',
            'review_state': 'pending',
        }

        try:
            att = request.env['hr.attendance'].sudo().create(vals)
        except (ValidationError, UserError) as e:
            return {'success': False, 'error': str(e)}
        except Exception as e:
            _logger.exception('Field check-in create failed')
            return {'success': False, 'error': _('Lỗi hệ thống: %s') % e}

        return {
            'success': True,
            'attendance_id': att.id,
            'is_valid': is_valid,
            'distance': round(distance or 0, 1),
            'location_name': nearest.name if nearest else _('Không xác định'),
            'message': (
                _('Check-in thành công tại %s (cách %.0fm)') % (nearest.name, distance)
                if nearest and is_valid
                else _('Check-in đã ghi nhận nhưng ngoài bán kính cho phép. HR sẽ xem xét.')
            ),
        }

    @http.route(
        '/field_attendance/checkout', type='json', auth='user', methods=['POST'],
        csrf=False,
    )
    def checkout(self, latitude, longitude, selfie=None, note=None):
        """
        Đóng hr.attendance đang mở với dữ liệu check-out.

        Selfie có thể không bắt buộc (tùy config require_selfie_checkout).
        """
        employee = self._get_current_employee()
        if not employee:
            return {'success': False, 'error': _('Không tìm thấy hồ sơ nhân viên')}

        if not latitude or not longitude:
            return {'success': False, 'error': _('Thiếu tọa độ GPS')}

        ICP = request.env['ir.config_parameter'].sudo()
        require_selfie = ICP.get_param(
            'field_attendance.require_selfie_checkout', 'False'
        ) == 'True'
        if require_selfie and not selfie:
            return {'success': False, 'error': _('Bắt buộc chụp ảnh selfie khi check-out')}

        att = request.env['hr.attendance'].sudo().search([
            ('employee_id', '=', employee.id),
            ('check_out', '=', False),
        ], limit=1, order='check_in desc')
        if not att:
            return {'success': False, 'error': _('Không tìm thấy phiên chấm công đang mở')}

        Location = request.env['attendance.location'].sudo()
        nearest, distance = Location.find_nearest(
            float(latitude), float(longitude), company_id=employee.company_id.id,
        )
        is_valid = False
        if nearest and distance is not None:
            is_valid = distance <= nearest.radius

        vals = {
            'check_out': fields.Datetime.now(),
            'check_out_latitude': float(latitude),
            'check_out_longitude': float(longitude),
            'check_out_location_id': nearest.id if nearest else False,
            'check_out_distance': distance or 0.0,
            'check_out_valid': is_valid,
            'check_out_note': note or '',
        }
        if selfie:
            vals['check_out_selfie'] = self._decode_selfie(selfie)

        try:
            att.write(vals)
        except (ValidationError, UserError) as e:
            return {'success': False, 'error': str(e)}

        return {
            'success': True,
            'attendance_id': att.id,
            'is_valid': is_valid,
            'distance': round(distance or 0, 1),
            'location_name': nearest.name if nearest else _('Không xác định'),
            'worked_hours': att.worked_hours,
            'message': _('Check-out thành công. Thời gian làm việc: %.2f giờ') % att.worked_hours,
        }

    @http.route(
        '/field_attendance/register_location', type='json', auth='user', methods=['POST'],
        csrf=False,
    )
    def register_location(self, attendance_id, name, location_type,
                          address=None, partner_id=None):
        """
        Nhân viên tự đăng ký địa điểm công tác mới.
        Toạ độ GPS lấy từ bản ghi attendance đang mở.
        """
        employee = self._get_current_employee()
        if not employee:
            return {'success': False, 'error': _('Không tìm thấy hồ sơ nhân viên')}

        if not name or not name.strip():
            return {'success': False, 'error': _('Tên địa điểm không được để trống')}

        att = request.env['hr.attendance'].sudo().search([
            ('id', '=', int(attendance_id)),
            ('employee_id', '=', employee.id),
        ], limit=1)
        if not att:
            return {'success': False, 'error': _('Không tìm thấy bản ghi chấm công')}

        if not att.check_in_latitude or not att.check_in_longitude:
            return {'success': False, 'error': _('Bản ghi không có tọa độ GPS')}

        loc_vals = {
            'name': name.strip(),
            'location_type': location_type or 'other',
            'latitude': att.check_in_latitude,
            'longitude': att.check_in_longitude,
            'address': address or '',
            'company_id': employee.company_id.id,
            'radius': 200,
        }
        if partner_id:
            loc_vals['partner_id'] = int(partner_id)

        new_loc = request.env['attendance.location'].sudo().create(loc_vals)

        att.write({
            'check_in_location_id': new_loc.id,
            'check_in_distance': 0.0,
            'check_in_valid': True,
            'is_new_location': True,
        })

        return {
            'success': True,
            'location_id': new_loc.id,
            'location_name': new_loc.name,
        }

    @http.route(
        '/field_attendance/search_partners', type='json', auth='user', methods=['POST'],
        csrf=False,
    )
    def search_partners(self, name=''):
        """Tìm kiếm res.partner theo tên cho form đăng ký địa điểm."""
        if not name or len(name.strip()) < 2:
            return []
        partners = request.env['res.partner'].sudo().search([
            ('name', 'ilike', name.strip()),
            ('active', '=', True),
        ], limit=8, order='name asc')
        return [{'id': p.id, 'name': p.name} for p in partners]

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _get_current_employee(self):
        user = request.env.user
        employee = request.env['hr.employee'].sudo().search([
            ('user_id', '=', user.id),
            ('company_id', '=', user.company_id.id),
        ], limit=1)
        if not employee:
            employee = request.env['hr.employee'].sudo().search([
                ('user_id', '=', user.id),
            ], limit=1)
        return employee

    def _decode_selfie(self, selfie_data):
        """Convert data URL (data:image/jpeg;base64,...) → binary bytes for Image field."""
        if not selfie_data:
            return False
        if ',' in selfie_data:
            # strip "data:image/jpeg;base64," prefix
            selfie_data = selfie_data.split(',', 1)[1]
        try:
            # Odoo Image field expects base64-encoded bytes
            return selfie_data.encode('utf-8')
        except Exception as e:
            _logger.warning('Failed to decode selfie: %s', e)
            return False
