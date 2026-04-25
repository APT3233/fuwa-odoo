# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Employee Contracts',
    'version': '19.0.1.0.0',
    'category': 'Human Resources',
    'summary': 'Manage employee contracts',
    'depends': ['hr', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/hr_contract_views.xml',
        'views/hr_employee_views.xml',
    ],
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
