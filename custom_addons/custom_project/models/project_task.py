# -*- coding: utf-8 -*-
from odoo import api, fields, models
from odoo.exceptions import UserError, AccessError


class ProjectTask(models.Model):
    _inherit = 'project.task'

    assignee_personal_stage_ids = fields.One2many(
        'project.task.stage.personal', 'task_id',
        string='Assignee Personal Stages',
    )
    # Split into two separate compute methods to avoid Odoo 19 "inconsistent store" warning
    all_assignees_done = fields.Boolean(
        compute='_compute_all_assignees_done',
        store=True,
        string='All Assignees Done',
    )
    assignee_stage_summary = fields.Char(
        compute='_compute_assignee_stage_summary',
        string='Progress',
    )

    @api.depends('user_ids', 'assignee_personal_stage_ids.stage_id')
    def _compute_all_assignees_done(self):
        PersonalStage = self.env['project.task.stage.personal']
        for task in self:
            if not task.user_ids:
                task.all_assignees_done = False
                continue
            personal_stages = PersonalStage.search([
                ('task_id', '=', task.id),
                ('user_id', 'in', task.user_ids.ids),
            ])
            stage_by_user = {ps.user_id.id: ps.stage_id for ps in personal_stages}
            done_count = sum(
                1 for u in task.user_ids
                if stage_by_user.get(u.id) and stage_by_user[u.id].fold
            )
            task.all_assignees_done = (done_count == len(task.user_ids) and bool(task.user_ids))

    @api.depends('user_ids', 'assignee_personal_stage_ids.stage_id')
    def _compute_assignee_stage_summary(self):
        PersonalStage = self.env['project.task.stage.personal']
        for task in self:
            if not task.user_ids:
                task.assignee_stage_summary = ''
                continue
            personal_stages = PersonalStage.search([
                ('task_id', '=', task.id),
                ('user_id', 'in', task.user_ids.ids),
            ])
            stage_by_user = {ps.user_id.id: ps.stage_id for ps in personal_stages}
            done_count = 0
            parts = []
            for user in task.user_ids:
                stage = stage_by_user.get(user.id)
                if stage and stage.fold:
                    done_count += 1
                    parts.append('%s: ✓ %s' % (user.name, stage.name))
                elif stage:
                    parts.append('%s: %s' % (user.name, stage.name))
                else:
                    parts.append('%s: —' % user.name)
            total = len(task.user_ids)
            task.assignee_stage_summary = '%d/%d done  |  %s' % (
                done_count, total, '  ·  '.join(parts)
            )

    # ── Department helpers ────────────────────────────────────────────────────

    def _user_department(self):
        """Return hr.department for the current user's employee (sudo to bypass HR access)."""
        employee = self.env['hr.employee'].sudo().search(
            [('user_id', '=', self.env.uid)], limit=1
        )
        return employee.sudo().department_id if employee else self.env['hr.department'].browse()

    def _dept_tag(self, dept, create_if_missing=False):
        """Return project.tags whose name matches dept.name, optionally creating it."""
        if not dept:
            return self.env['project.tags']
        tag = self.env['project.tags'].sudo().search([('name', '=', dept.name)], limit=1)
        if not tag and create_if_missing:
            tag = self.env['project.tags'].sudo().create({'name': dept.name})
        return tag

    # ── Department-scoped search ──────────────────────────────────────────────

    @api.model
    def _search(self, domain, offset=0, limit=None, order=None, **kwargs):
        """
        Quản trị viên: no filter — sees everything.
        Quản lý:       only tasks tagged with their department.
        Nhân viên:     see ALL tasks in project kanban (same as Quản lý);
                       sub-tasks tab shows only own sub-tasks.
        """
        if (
            not self.env.user.has_group('project.group_project_manager')
            and not self.env.context.get('_no_dept_filter')
        ):
            if self.env.user.has_group('custom_project.group_project_manager_custom'):
                # ── Quản lý: department tag filter ───────────────────────────
                dept = self._user_department()
                if dept:
                    tag = self._dept_tag(dept)
                    if tag:
                        domain = [('tag_ids', 'in', tag.ids)] + list(domain)
            else:
                # ── Nhân viên ────────────────────────────────────────────────
                # Sub-tasks tab: domain contains parent_id=<task_id> (non-False)
                # → show ONLY sub-tasks assigned to current user
                # All other contexts (project kanban, my tasks): no extra filter
                loading_subtasks = any(
                    isinstance(leaf, (list, tuple)) and len(leaf) == 3
                    and leaf[0] == 'parent_id' and leaf[1] in ('=', 'in')
                    and leaf[2] not in (False, 0, None)
                    for leaf in domain
                )
                if loading_subtasks:
                    domain = [('user_ids', 'in', [self.env.uid])] + list(domain)

        return super()._search(domain, offset=offset, limit=limit, order=order, **kwargs)

    # ── Auto-tag on create ────────────────────────────────────────────────────

    @api.model_create_multi
    def create(self, vals_list):
        """
        Nhân viên: only allowed to create personal tasks (project_id=False).
        Quản lý (non-admin): auto-tag every new task with their department.
        """
        if (
            not self.env.user.has_group('custom_project.group_project_manager_custom')
            and not self.env.context.get('_bypass_restrictions')
        ):
            for vals in vals_list:
                if vals.get('project_id'):
                    raise UserError(
                        "Nhân viên không được phép tạo nhiệm vụ trong dự án. "
                        "Chỉ được tạo nhiệm vụ cá nhân."
                    )

        if not self.env.user.has_group('project.group_project_manager'):
            dept = self._user_department()
            if dept:
                tag = self._dept_tag(dept, create_if_missing=True)
                if tag:
                    for vals in vals_list:
                        if vals.get('project_id'):
                            existing = vals.get('tag_ids') or []
                            vals['tag_ids'] = list(existing) + [(4, tag.id)]
        return super().create(vals_list)

    # ── Restricted write for Nhân viên ───────────────────────────────────────

    # Fields Nhân viên may write on project tasks.
    # Personal to-do tasks (project_id=False) are unrestricted.
    _EMPLOYEE_WRITE_WHITELIST = frozenset({
        'personal_stage_type_id', # each assignee changes their own personal stage
        'sequence',               # reorder within same column (no stage change)
        'state',                  # request changes / mark in progress (own tasks only)
        'date_last_stage_update', # auto-written by Odoo when state changes
    })

    def write(self, vals):
        """
        Nhân viên (not group_project_manager_custom) restrictions on PROJECT tasks:
          • May only write personal_stage_type_id (their own progress indicator).
          • Must be assigned to the task to change personal stage.
        Personal to-do tasks (no project_id) are unrestricted.
        Quản lý / Quản trị viên are unrestricted.

        Auto-review trigger:
          When ALL assignees of a task have a personal stage with fold=True (Done),
          the task is automatically moved to the nearest Review stage.
        """
        if (
            not self.env.user.has_group('custom_project.group_project_manager_custom')
            and not self.env.context.get('_bypass_restrictions')
        ):
            project_tasks = self.filtered('project_id')
            if project_tasks:
                blocked = set(vals.keys()) - self._EMPLOYEE_WRITE_WHITELIST
                if blocked:
                    import logging
                    logging.getLogger(__name__).warning(
                        "CUSTOM_PROJECT blocked=%s vals=%s", blocked, list(vals.keys())
                    )
                    raise UserError(
                        "Nhân viên không được phép chỉnh sửa thông tin nhiệm vụ. "
                        "Chỉ được phép thay đổi tiến độ cá nhân."
                    )
                if 'personal_stage_type_id' in vals or 'state' in vals:
                    for task in project_tasks:
                        if self.env.user not in task.user_ids:
                            raise AccessError(
                                "Bạn chỉ được phép thay đổi tiến độ của nhiệm vụ "
                                "mà bạn được giao."
                            )
                        if 'state' in vals and not task.parent_id:
                            raise UserError(
                                "Nhân viên không được phép thay đổi trạng thái của nhiệm vụ chính. "
                                "Chỉ được thay đổi trạng thái nhiệm vụ phụ."
                            )
                if 'state' in vals and vals['state'] not in {'01_in_progress', '02_changes_requested'}:
                    raise UserError(
                        "Nhân viên chỉ được phép chuyển sang trạng thái "
                        "'Đang thực hiện' hoặc 'Đã yêu cầu thay đổi'."
                    )

        res = super().write(vals)

        # Cascade state to sub-tasks only for Done/Cancelled (not 03_approved)
        if not self.env.context.get('_cascade_state') and 'state' in vals and vals['state'] in ('1_done', '1_canceled'):
            for task in self:
                subtasks = self.env['project.task'].with_user(1).search([
                    ('parent_id', '=', task.id),
                ])
                if subtasks:
                    cascade_vals = {'state': vals['state']}
                    if vals['state'] == '1_done' and task.project_id:
                        project_stages = self.env['project.task.type'].sudo().search([
                            ('project_ids', 'in', task.project_id.ids),
                        ], order='sequence asc')
                        done_stage = next((s for s in project_stages if 'done' in s.name.lower()), None)
                        if done_stage:
                            cascade_vals['stage_id'] = done_stage.id
                    subtasks.with_context(_cascade_state=True, _bypass_restrictions=True).sudo().write(cascade_vals)

        # "Đã phê duyệt" (03_approved) logic — only for TOP-LEVEL tasks (no parent_id):
        #   - Move to Done stage, but keep state as 03_approved (not 1_done yet)
        #   Sub-tasks: 03_approved has no automatic side-effect.
        if not self.env.context.get('_auto_approved') and 'state' in vals and vals['state'] == '03_approved':
            for task in self:
                if not task.project_id or task.parent_id:
                    continue
                ctx = dict(_auto_approved=True, _auto_review=True, _bypass_restrictions=True)
                project_stages = self.env['project.task.type'].sudo().search([
                    ('project_ids', 'in', task.project_id.ids),
                ], order='sequence asc')
                done_stage = next((s for s in project_stages if 'done' in s.name.lower()), None)
                if done_stage and done_stage != task.stage_id:
                    task.with_context(**ctx).sudo().write({'stage_id': done_stage.id})

        # Auto-move PARENT task based on sub-task states.
        # Only sub-tasks trigger this; top-level tasks are managed by Quản lý only.
        if not self.env.context.get('_auto_review') and 'state' in vals:
            for task in self:
                if not task.project_id:
                    continue
                parent = task.sudo().parent_id
                if not parent or not parent.project_id:
                    continue
                assigned_siblings = self.env['project.task'].with_user(1).search([
                    ('parent_id', '=', parent.id),
                    ('user_ids', '!=', False),
                ])
                if not assigned_siblings:
                    continue
                all_requested = all(s.state == '02_changes_requested' for s in assigned_siblings)
                if all_requested:
                    project_stages = self.env['project.task.type'].sudo().search([
                        ('project_ids', 'in', parent.project_id.ids),
                    ], order='sequence asc')
                    review_stage = next(
                        (s for s in project_stages if 'review' in s.name.lower()), None
                    )
                    if review_stage and review_stage != parent.stage_id:
                        parent.with_context(_auto_review=True, _bypass_restrictions=True).sudo().write(
                            {'stage_id': review_stage.id}
                        )

        return res
