# -*- coding: utf-8 -*-
from odoo import api, fields, models


class Project(models.Model):
    _inherit = 'project.project'

    # Default privacy to 'employees' so all internal users can navigate to projects.
    # _search below further restricts Nhân viên to only see projects with assigned tasks.
    privacy_visibility = fields.Selection(default='employees')

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """
        Nhân viên (group_project_user only, not group_project_manager_custom):
            Only see projects where they have at least one assigned task.
        Quản lý / Quản trị viên: no extra filter.
        """
        if (
            not self.env.user.has_group('project.group_project_manager')
            and not self.env.user.has_group('custom_project.group_project_manager_custom')
            and not self.env.user.has_group('base.group_portal')
            and not self.env.context.get('_no_project_filter')
        ):
            # Find project IDs where current user has assigned tasks
            assigned_tasks = self.env['project.task'].sudo().search([
                ('user_ids', 'in', [self.env.uid]),
                ('project_id', '!=', False),
            ])
            assigned_project_ids = assigned_tasks.mapped('project_id').ids
            if assigned_project_ids:
                domain = [('id', 'in', assigned_project_ids)] + list(domain)
            else:
                domain = [('id', 'in', [])] + list(domain)  # Empty result

        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    _DEFAULT_STAGE_NAMES = ['Idea', 'To do', 'In Progress', 'Review', 'Done']

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        Stage = self.env['project.task.type']
        for project in projects:
            if not project.type_ids:
                for seq, name in enumerate(self._DEFAULT_STAGE_NAMES):
                    existing = Stage.sudo().search([('name', '=', name)], limit=1)
                    if existing:
                        project.sudo().write({'type_ids': [(4, existing.id)]})
                    else:
                        Stage.sudo().create({'name': name, 'sequence': seq * 10, 'project_ids': [(4, project.id)]})
        return projects
