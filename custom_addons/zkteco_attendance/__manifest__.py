{
    'name': 'ZKTeco Attendance Integration',
    'version': '19.0.1.0.0',
    'category': 'Human Resources/Attendances',
    'summary': 'Tích hợp máy chấm công ZKTeco qua giao thức ADMS',
    'description': """
Tích hợp máy chấm công ZKTeco (SenseFace, F-series, K-series...) với Odoo
thông qua giao thức ADMS (push mode). Máy chấm công tự đẩy dữ liệu lên server.
    """,
    'author': 'Custom',
    'depends': ['hr_attendance'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_employee_views.xml',
        'views/zkteco_device_views.xml',
        'views/zkteco_log_views.xml',
        'views/res_config_settings_views.xml',
        'views/menu.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
