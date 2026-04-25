# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models
from odoo.fields import Domain


class Employee(models.Model):
    _inherit = 'hr.employee'

    contract_id = fields.Many2one('hr.contract', string='Current Contract',
        groups='hr.group_hr_user', help='Current contract of the employee')
    contract_ids = fields.One2many('hr.contract', 'employee_id', string='Employee Contracts',
        groups='hr.group_hr_user')
    contracts_count = fields.Integer(compute='_compute_contracts_count', string='Contracts Count',
        groups='hr.group_hr_user')

    def _compute_contracts_count(self):
        contract_data = self.env['hr.contract'].read_group(
            [('employee_id', 'in', self.ids)],
            ['employee_id'],
            ['employee_id'],
        )
        count_map = {d['employee_id'][0]: d['employee_id_count'] for d in contract_data}
        for employee in self:
            employee.contracts_count = count_map.get(employee.id, 0)

    def _get_contracts(self, date_from, date_to, states=None):
        """Return contracts between date_from and date_to."""
        if states is None:
            states = ['open']
        domain = Domain([
            ('employee_id', 'in', self.ids),
            ('state', 'in', states),
            ('date_start', '<=', date_to),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', date_from),
        ])
        return self.env['hr.contract'].search(domain)

    def action_open_contracts(self):
        self.ensure_one()
        return {
            'name': 'Contracts',
            'type': 'ir.actions.act_window',
            'res_model': 'hr.contract',
            'view_mode': 'list,form',
            'domain': [('employee_id', '=', self.id)],
            'context': {'default_employee_id': self.id},
        }


