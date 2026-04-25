{
    'name': 'Field Attendance (Hybrid Office + Field Check-in)',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Chấm công công tác ngoài với selfie + GPS + Google Maps',
    'description': """
Hybrid Attendance cho đội sale/kỹ thuật đi công tác ngoài.

Tính năng:
- Check-in tại văn phòng qua máy ZKTeco (module zkteco_attendance)
- Check-in công tác ngoài qua mobile web: selfie + GPS + Google Maps
- Validate trong bán kính cho phép từ công ty hoặc điểm khách hàng
- Dashboard HR xem ảnh + vị trí trên bản đồ, duyệt/từ chối
    """,
    'author': 'Custom',
    'depends': ['hr_attendance', 'hr'],
    'data': [
        'security/ir.model.access.csv',
        'security/security.xml',
        'data/default_location.xml',
        'data/cron.xml',
        'views/attendance_location_views.xml',
        'views/hr_attendance_views.xml',
        'views/res_config_settings_views.xml',
        'views/field_checkin_client_action.xml',
        'views/menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'field_attendance/static/src/js/field_checkin.js',
            'field_attendance/static/src/js/attendance_gps_patch.js',
            'field_attendance/static/src/xml/field_checkin.xml',
            'field_attendance/static/src/scss/field_checkin.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
