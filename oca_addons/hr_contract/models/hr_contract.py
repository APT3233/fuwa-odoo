# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models


class HrContract(models.Model):
    _name = 'hr.contract'
    _description = 'Employee Contract'
    _inherit = ['mail.thread']
    _order = 'date_start desc'

    name = fields.Char(string='Contract Reference', required=True)
    active = fields.Boolean(default=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, index=True)
    company_id = fields.Many2one('res.company', string='Company', default=lambda self: self.env.company, required=True)
    department_id = fields.Many2one('hr.department', string='Department', related='employee_id.department_id', readonly=True)
    job_id = fields.Many2one('hr.job', string='Job Position')
    resource_calendar_id = fields.Many2one('resource.calendar', string='Working Schedule', required=True,
        default=lambda self: self.env.company.resource_calendar_id, index=True)
    wage = fields.Monetary(string='Wage', required=True, tracking=True, help='Employee monthly gross wage.')
    currency_id = fields.Many2one('res.currency', related='company_id.currency_id')
    date_start = fields.Date(string='Contract Start Date', required=True, default=fields.Date.today)
    date_end = fields.Date(string='Contract End Date')
    state = fields.Selection([
        ('draft', 'New'),
        ('open', 'Running'),
        ('close', 'Expired'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)
    notes = fields.Html(string='Notes')

    def action_confirm(self):
        self.write({'state': 'open'})

    def action_close(self):
        self.write({'state': 'close'})

    def action_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})
