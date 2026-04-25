from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError


class MscRecord(models.Model):
    _name = "msc.record"
    _description = "Bản ghi MSC"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    # ── Identity ──────────────────────────────────────────────────────────────

    name = fields.Char(string="Tên", compute="_compute_name", store=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        index=True,
        tracking=True,
        ondelete="restrict",
    )
    period_id = fields.Many2one(
        "msc.period",
        string="Chu kỳ",
        required=True,
        index=True,
        tracking=True,
        ondelete="restrict",
    )
    report_to_id = fields.Many2one(
        "hr.employee",
        string="Quản lý trực tiếp",
        related="employee_id.parent_id",
        store=True,
    )
    employee_parent_id = fields.Many2one(
        "hr.employee",
        related="employee_id.parent_id",
        string="Quản lý của nhân viên",
        store=False,
    )
    department_id = fields.Many2one(
        related="employee_id.department_id",
        string="Phòng ban",
        store=True,
    )
    job_id = fields.Many2one(
        related="employee_id.job_id",
        string="Chức danh",
        store=True,
    )

    # ── State & Rating ────────────────────────────────────────────────────────

    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("submitted", "Đã nộp mục tiêu"),
            ("manager_confirmed", "Cấp trên đã xác nhận"),
            ("confirmed", "Mục tiêu đã xác nhận"),
            ("result_submitted", "Đã nộp kết quả"),
            ("pm_approved", "Trưởng CN đã phê duyệt"),
            ("bul_approved", "Trưởng phòng đã phê duyệt"),
            ("pmo_approved", "PMO đã phê duyệt"),
            ("baselined", "Đã cơ sở hóa"),
        ],
        string="Trạng thái",
        default="draft",
        tracking=True,
        index=True,
    )
    is_sale_admin = fields.Boolean(
        string="Trưởng phòng / Sale Admin (báo cáo PMO)",
        default=False,
        help="Nếu True, bỏ qua bước Trưởng CN và Trưởng phòng — kết quả được PMO phê duyệt trực tiếp.",
        tracking=True,
    )
    is_branch_manager = fields.Boolean(
        string="Trưởng chi nhánh (Trưởng phòng xác nhận)",
        default=False,
        help="Nếu True, bỏ qua bước Trưởng CN — mục tiêu/kết quả được Trưởng phòng xác nhận/phê duyệt.",
        tracking=True,
    )
    # ── Loại nhân viên (UI duy nhất thay cho 2 toggle) ───────────────────────
    employee_level = fields.Selection(
        [
            ("employee", "Nhân viên"),
            ("branch_manager", "Trưởng chi nhánh (Trưởng phòng → PMO → HR)"),
            ("dept_head", "Trưởng phòng / Sale Admin (PMO → HR)"),
        ],
        string="Loại nhân viên",
        compute="_compute_employee_level",
        inverse="_set_employee_level",
    )

    @api.depends("is_sale_admin", "is_branch_manager")
    def _compute_employee_level(self):
        for rec in self:
            if rec.is_sale_admin:
                rec.employee_level = "dept_head"
            elif rec.is_branch_manager:
                rec.employee_level = "branch_manager"
            else:
                rec.employee_level = "employee"

    def _set_employee_level(self):
        for rec in self:
            level = rec.employee_level or "employee"
            rec.is_sale_admin = (level == "dept_head")
            rec.is_branch_manager = (level == "branch_manager")
    performance_rating = fields.Selection(
        [
            ("a_plus", "A+"),
            ("a", "A"),
            ("b", "B"),
            ("c", "C"),
            ("d", "D"),
        ],
        string="Xếp loại",
        compute="_compute_performance_rating",
        store=True,
        readonly=False,
        tracking=True,
    )

    # ── Goal lines ────────────────────────────────────────────────────────────

    goal_line_ids = fields.One2many(
        "msc.goal.line",
        "record_id",
        string="Tất cả mục tiêu",
    )
    must_goal_ids = fields.One2many(
        "msc.goal.line",
        "record_id",
        string="MUST",
        domain=[("goal_type", "=", "must")],
        context={"default_goal_type": "must"},
    )
    should_goal_ids = fields.One2many(
        "msc.goal.line",
        "record_id",
        string="SHOULD",
        domain=[("goal_type", "=", "should")],
        context={"default_goal_type": "should"},
    )
    could_goal_ids = fields.One2many(
        "msc.goal.line",
        "record_id",
        string="COULD",
        domain=[("goal_type", "=", "could")],
        context={"default_goal_type": "could"},
    )

    # ── Approval log ──────────────────────────────────────────────────────────

    approval_log_ids = fields.One2many(
        "msc.approval.log",
        "record_id",
        string="Nhật ký phê duyệt",
    )

    # ── Computed helpers ──────────────────────────────────────────────────────

    is_own_record = fields.Boolean(
        string="Là bản ghi của tôi",
        compute="_compute_is_own_record",
    )
    # Role flags: True khi user đang ở đúng cấp (không phải cấp cao hơn)
    # Dùng để kiểm soát nút hiện cho đúng cấp mà không cần marker group
    is_manager_role = fields.Boolean(
        string="Là Trưởng CN (không phải BUL/PMO/HR)",
        compute="_compute_user_role_flags",
    )
    is_bul_role = fields.Boolean(
        string="Là Trưởng phòng (không phải PMO/HR)",
        compute="_compute_user_role_flags",
    )
    is_pmo_role = fields.Boolean(
        string="Là PMO (không phải HR)",
        compute="_compute_user_role_flags",
    )
    must_count = fields.Integer(compute="_compute_goal_counts")
    should_count = fields.Integer(compute="_compute_goal_counts")
    could_count = fields.Integer(compute="_compute_goal_counts")
    must_full = fields.Boolean(compute="_compute_goal_counts")
    should_full = fields.Boolean(compute="_compute_goal_counts")
    could_full = fields.Boolean(compute="_compute_goal_counts")

    # ── Score ─────────────────────────────────────────────────────────────────

    total_score = fields.Integer(
        string="Tổng điểm",
        compute="_compute_total_score",
        store=True,
    )

    # ── Notes ─────────────────────────────────────────────────────────────────

    member_note = fields.Text(string="Ghi chú của thành viên")
    manager_note = fields.Text(string="Ghi chú của quản lý")

    # ── Constraints ───────────────────────────────────────────────────────────

    _unique_employee_period = models.Constraint(
        "UNIQUE(employee_id, period_id)",
        "Mỗi nhân viên chỉ có một bản ghi MSC cho mỗi chu kỳ.",
    )

    # ── Compute methods ───────────────────────────────────────────────────────

    @api.depends("employee_id", "period_id")
    def _compute_name(self):
        for rec in self:
            emp = rec.employee_id.name or ""
            period = rec.period_id.name or ""
            rec.name = f"{emp} — {period}" if emp and period else emp or period

    def _compute_is_own_record(self):
        for rec in self:
            rec.is_own_record = (
                rec.employee_id.user_id == self.env.user
            )

    def _compute_user_role_flags(self):
        """Xác định cấp bậc của user hiện tại để hiện đúng nút.
        - is_manager_role: trong group_msc_manager nhưng KHÔNG trong group_msc_bul
        - is_bul_role: trong group_msc_bul nhưng KHÔNG trong group_msc_pmo
        - is_pmo_role: trong group_msc_pmo nhưng KHÔNG trong group_msc_admin
        Không cần marker group — tự động theo role được gán.
        """
        user = self.env.user
        is_admin = user.has_group('msc_performance.group_msc_admin')
        is_pmo = user.has_group('msc_performance.group_msc_pmo')
        is_bul = user.has_group('msc_performance.group_msc_bul')
        is_manager = user.has_group('msc_performance.group_msc_manager')
        for rec in self:
            rec.is_manager_role = is_manager and not is_bul
            rec.is_bul_role = is_bul and not is_pmo
            rec.is_pmo_role = is_pmo and not is_admin

    def _compute_goal_counts(self):
        for rec in self:
            rec.must_count = len(rec.must_goal_ids)
            rec.should_count = len(rec.should_goal_ids)
            rec.could_count = len(rec.could_goal_ids)
            rec.must_full = rec.must_count >= 4
            rec.should_full = rec.should_count >= 2
            rec.could_full = rec.could_count >= 1

    @api.depends("goal_line_ids.score_total", "goal_line_ids.goal_type")
    def _compute_total_score(self):
        # Scoring formula (64-24-12):
        #   MUST:   4 goals × max 16 raw pts (4 criteria × max 4pts) → 64 pts total
        #   SHOULD: 2 goals × max 12 raw pts (4 criteria × max 3pts) → 24 pts total
        #   COULD:  1 goal  × max 12 raw pts (4 criteria × max 3pts) → 12 pts total
        MUST_MAX_PTS = 64
        MUST_MAX_RAW = 16   # 4 criteria × 4pts each
        SHOULD_MAX_PTS = 24
        SHOULD_MAX_RAW = 12  # 4 criteria × 3pts each
        COULD_MAX_PTS = 12
        COULD_MAX_RAW = 12   # 4 criteria × 3pts each

        for rec in self:
            must_lines = rec.goal_line_ids.filtered(lambda l: l.goal_type == "must")
            should_lines = rec.goal_line_ids.filtered(lambda l: l.goal_type == "should")
            could_lines = rec.goal_line_ids.filtered(lambda l: l.goal_type == "could")

            def pool_score(lines, pool, max_raw):
                if not lines:
                    return 0
                per_goal = pool / len(lines)
                total = 0
                for line in lines:
                    total += round((line.score_total / max_raw) * per_goal, 2)
                return total

            rec.total_score = round(
                pool_score(must_lines, MUST_MAX_PTS, MUST_MAX_RAW)
                + pool_score(should_lines, SHOULD_MAX_PTS, SHOULD_MAX_RAW)
                + pool_score(could_lines, COULD_MAX_PTS, COULD_MAX_RAW)
            )

    @api.depends("total_score")
    def _compute_performance_rating(self):
        # A+: 90-100 | A: 80-90 | B: 60-80 | C: 50-60 | D: <50
        for rec in self:
            score = rec.total_score
            if score >= 90:
                rec.performance_rating = "a_plus"
            elif score >= 80:
                rec.performance_rating = "a"
            elif score >= 60:
                rec.performance_rating = "b"
            elif score >= 50:
                rec.performance_rating = "c"
            else:
                rec.performance_rating = "d"

    # ── Defaults ─────────────────────────────────────────────────────────────

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        if "employee_id" in fields_list and "employee_id" not in res:
            employee = self.env["hr.employee"].sudo().search(
                [("user_id", "=", self.env.uid)], limit=1
            )
            if employee:
                res["employee_id"] = employee.id
                # Auto-set flags based on MSC role and department
                user = self.env.user
                is_pmo = user.has_group("msc_performance.group_msc_pmo")
                is_manager = user.has_group("msc_performance.group_msc_manager")
                if is_manager and not is_pmo:
                    # Trưởng CN / Trưởng phòng KD: luồng branch_manager
                    res["is_branch_manager"] = True
                else:
                    # Nhân viên các phòng ban gửi thẳng PMO (không qua Trưởng CN/Trưởng phòng)
                    _PMO_DIRECT_DEPTS = {"marketing", "nghiên cứu và phát triển"}
                    dept_name = (employee.department_id.name or "").strip().lower()
                    if dept_name in _PMO_DIRECT_DEPTS:
                        res["is_sale_admin"] = True
        return res

    # ── Business logic helpers ────────────────────────────────────────────────

    def _validate_must_goals(self):
        """4 MUST goals are required before submission."""
        for rec in self:
            must_goals = rec.goal_line_ids.filtered(lambda l: l.goal_type == "must")
            if len(must_goals) != 4:
                raise ValidationError(
                    _("Bản ghi '%s' cần đúng 4 mục tiêu MUST (hiện có %d).")
                    % (rec.name, len(must_goals))
                )

    def _validate_optional_goals(self):
        """SHOULD limited to 2, COULD limited to 1."""
        for rec in self:
            should = rec.goal_line_ids.filtered(lambda l: l.goal_type == "should")
            could = rec.goal_line_ids.filtered(lambda l: l.goal_type == "could")
            if len(should) > 2:
                raise ValidationError(
                    _("Bản ghi '%s' có tối đa 2 mục tiêu SHOULD (hiện có %d).")
                    % (rec.name, len(should))
                )
            if len(could) > 1:
                raise ValidationError(
                    _("Bản ghi '%s' có tối đa 1 mục tiêu COULD (hiện có %d).")
                    % (rec.name, len(could))
                )

    def _log(self, action, note=None):
        self.env["msc.approval.log"].create({
            "record_id": self.id,
            "action": action,
            "actor_id": self.env.user.id,
            "note": note,
        })

    # ── State transitions: Goal phase ─────────────────────────────────────────

    def _validate_period_submit(self):
        """Kiểm tra chu kỳ còn mở và trong thời gian nộp mục tiêu."""
        today = fields.Date.today()
        for rec in self:
            period = rec.period_id
            if period.state == "closed":
                raise UserError(
                    _("Chu kỳ '%s' đã đóng. Không thể nộp mục tiêu.") % period.name
                )
            if period.state == "draft":
                raise UserError(
                    _("Chu kỳ '%s' chưa được mở. Không thể nộp mục tiêu.") % period.name
                )
            if period.date_submit_open and today < period.date_submit_open:
                raise UserError(
                    _("Chưa đến thời gian nộp mục tiêu. Chu kỳ '%s' mở nộp từ %s.")
                    % (period.name, period.date_submit_open)
                )
            if period.date_submit_close and today > period.date_submit_close:
                raise UserError(
                    _("Đã hết hạn nộp mục tiêu. Chu kỳ '%s' đóng nộp ngày %s.")
                    % (period.name, period.date_submit_close)
                )

    def _validate_period_submit_result(self):
        """Kiểm tra chu kỳ còn mở và trong thời gian nộp kết quả."""
        today = fields.Date.today()
        for rec in self:
            period = rec.period_id
            if period.state == "closed":
                raise UserError(
                    _("Chu kỳ '%s' đã đóng. Không thể nộp kết quả.") % period.name
                )
            if period.state == "draft":
                raise UserError(
                    _("Chu kỳ '%s' chưa được mở. Không thể nộp kết quả.") % period.name
                )
            if period.date_result_open and today < period.date_result_open:
                raise UserError(
                    _("Chưa đến thời gian nộp kết quả. Chu kỳ '%s' mở nộp kết quả từ %s.")
                    % (period.name, period.date_result_open)
                )
            if period.date_result_close and today > period.date_result_close:
                raise UserError(
                    _("Đã hết hạn nộp kết quả. Chu kỳ '%s' đóng nộp kết quả ngày %s.")
                    % (period.name, period.date_result_close)
                )

    def action_submit(self):
        """Member submits goals → submitted."""
        self._validate_period_submit()
        self._validate_must_goals()
        self._validate_optional_goals()
        for rec in self:
            if rec.state != "draft":
                raise UserError(_("Chỉ có thể nộp mục tiêu từ trạng thái Nháp."))
            # Block nếu còn dòng bị từ chối (nhân viên phải xử lý trước)
            rejected_lines = rec.goal_line_ids.filtered(
                lambda l: l.manager_status == "rejected"
            )
            if rejected_lines:
                names = ", ".join(rejected_lines.mapped("name"))
                raise ValidationError(_(
                    "Các mục tiêu sau đang bị từ chối, vui lòng chỉnh sửa hoặc xóa trước khi nộp lại: %s"
                ) % names)
            rec.goal_line_ids.write({"member_status": "submitted"})
            rec.write({"state": "submitted"})
            rec._log("submit")
            rec.message_post(body=_("Nhân viên đã nộp mục tiêu."))

    def action_cancel_submit(self):
        """Member cancels submitted goals → back to draft (keep all data)."""
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Chỉ có thể hủy nộp ở trạng thái Đã nộp mục tiêu."))
            rec.goal_line_ids.write({"member_status": "na", "manager_status": "na"})
            rec.write({"state": "draft"})
            rec._log("cancel_submit")
            rec.message_post(body=_("Nhân viên đã hủy nộp mục tiêu và trả về Nháp."))
            # Notify employee
            employee_user = rec.employee_id.user_id
            if employee_user:
                rec.message_post(
                    body=_("Bạn đã hủy nộp mục tiêu MSC <b>%s</b>. Bản ghi đã được trả về trạng thái Nháp.") % rec.name,
                    subject=_("MSC đã hủy nộp: %s") % rec.name,
                    message_type="comment",
                    subtype_xmlid="mail.mt_comment",
                    partner_ids=employee_user.partner_id.ids,
                )

    def action_pm_confirm_all(self):
        """Trưởng CN confirms goals for regular employees → confirmed."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Chỉ có thể xác nhận mục tiêu ở trạng thái Đã nộp mục tiêu."))
            if rec.is_sale_admin:
                raise UserError(_("Nhân viên Sale Admin được xác nhận bởi PMO, không phải Trưởng CN."))
            # Block nếu có dòng đã được điền reject_reason (PM nên dùng nút Từ chối)
            lines_with_reason = rec.goal_line_ids.filtered(
                lambda l: l.reject_reason and l.reject_reason.strip()
            )
            if lines_with_reason:
                names = ", ".join(lines_with_reason.mapped("name"))
                raise ValidationError(_(
                    "Bạn đã điền lý do từ chối cho các mục tiêu: %s\n"
                    "Vui lòng bấm nút 'Từ chối' thay vì 'Xác nhận mục tiêu'."
                ) % names)
            rec.goal_line_ids.write({
                "manager_status": "confirmed",
                "confirmed_by": self.env.user.id,
                "confirmed_date": now,
                "reject_reason": False,
            })
            rec.write({"state": "manager_confirmed"})
            rec._log("pm_confirm")
            rec.message_post(body=_("Trưởng CN đã xác nhận mục tiêu. Chờ PMO xác nhận."))

    def action_pmo_confirm_all(self):
        """PMO confirms goals → confirmed.
        - Sale Admin / branch_manager: from 'submitted'
        - Regular employees / branch managers after PM/BUL confirm: from 'manager_confirmed'
        """
        now = fields.Datetime.now()
        for rec in self:
            valid_states = ["submitted", "manager_confirmed"]
            if rec.state not in valid_states:
                raise UserError(_("Chỉ có thể xác nhận mục tiêu ở trạng thái Đã nộp hoặc Cấp trên đã xác nhận."))
            # Sale Admin/branch_manager xác nhận trực tiếp từ submitted
            if rec.state == "submitted" and not rec.is_sale_admin and not rec.is_branch_manager:
                raise UserError(_("Nhân viên thường cần Trưởng CN xác nhận trước."))
            lines_with_reason = rec.goal_line_ids.filtered(
                lambda l: l.reject_reason and l.reject_reason.strip()
            )
            if lines_with_reason:
                names = ", ".join(lines_with_reason.mapped("name"))
                raise ValidationError(_(
                    "Bạn đã điền lý do từ chối cho các mục tiêu: %s\n"
                    "Vui lòng bấm nút 'Từ chối' thay vì 'Xác nhận mục tiêu'."
                ) % names)
            rec.goal_line_ids.write({
                "manager_status": "confirmed",
                "confirmed_by": self.env.user.id,
                "confirmed_date": now,
                "reject_reason": False,
            })
            rec.write({"state": "confirmed"})
            rec._log("pmo_confirm")
            rec.message_post(body=_("PMO đã xác nhận mục tiêu. Nhân viên có thể điền kết quả."))

    def button_pm_reject(self):
        """Open reject wizard for PM reject (goal phase)."""
        return self._open_reject_wizard("confirm")

    def action_bul_confirm_for_manager(self):
        """BUL confirms goals for branch manager employees → confirmed."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != "submitted":
                raise UserError(_("Chỉ có thể xác nhận mục tiêu ở trạng thái Đã nộp mục tiêu."))
            if not rec.is_branch_manager:
                raise UserError(_("Hành động này chỉ dành cho nhân viên Trưởng chi nhánh."))
            lines_with_reason = rec.goal_line_ids.filtered(
                lambda l: l.reject_reason and l.reject_reason.strip()
            )
            if lines_with_reason:
                names = ", ".join(lines_with_reason.mapped("name"))
                raise ValidationError(_(
                    "Bạn đã điền lý do từ chối cho các mục tiêu: %s\n"
                    "Vui lòng bấm nút 'Từ chối' thay vì 'Xác nhận mục tiêu'."
                ) % names)
            rec.goal_line_ids.write({
                "manager_status": "confirmed",
                "confirmed_by": self.env.user.id,
                "confirmed_date": now,
                "reject_reason": False,
            })
            rec.write({"state": "manager_confirmed"})
            rec._log("bul_confirm_goals")
            rec.message_post(body=_("Trưởng phòng đã xác nhận mục tiêu (Trưởng chi nhánh). Chờ PMO xác nhận."))

    def button_bul_reject_goals_for_manager(self):
        """BUL rejects goals for branch manager → submitted → draft."""
        return self._open_reject_wizard("confirm")

    def button_bul_reject_result_for_manager(self):
        """BUL rejects results for branch manager → result_submitted → confirmed."""
        return self._open_reject_wizard("result_reject")

    def button_pmo_reject_goals(self):
        """PMO rejects goals → draft.
        - submitted (Sale Admin/branch_manager): wizard type 'confirm'
        - manager_confirmed (all): wizard type 'pmo_reject_goals'
        """
        for rec in self:
            if rec.state == "manager_confirmed":
                return self._open_reject_wizard("pmo_reject_goals")
        return self._open_reject_wizard("confirm")

    def action_pmo_confirm_goals(self):
        """PMO xác nhận mục tiêu sau khi Trưởng CN/BUL đã xác nhận → confirmed."""
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != "manager_confirmed":
                raise UserError(_("Chỉ có thể PMO xác nhận mục tiêu ở trạng thái 'Cấp trên đã xác nhận'."))
            lines_with_reason = rec.goal_line_ids.filtered(
                lambda l: l.reject_reason and l.reject_reason.strip()
            )
            if lines_with_reason:
                names = ", ".join(lines_with_reason.mapped("name"))
                raise UserError(_(
                    "Bạn đã điền lý do từ chối cho các mục tiêu: %s\n"
                    "Vui lòng bấm nút 'Từ chối' thay vì 'Xác nhận mục tiêu'."
                ) % names)
            rec.write({"state": "confirmed"})
            rec._log("pmo_confirm_goals")
            rec.message_post(body=_("PMO đã xác nhận mục tiêu. Nhân viên có thể nộp kết quả."))

    def button_pmo_reject_manager_confirmed(self):
        """PMO từ chối mục tiêu sau khi cấp trên đã xác nhận → trả về draft."""
        return self._open_reject_wizard("pmo_reject_goals")

    def button_pmo_unapprove_goals(self):
        """PMO hủy xác nhận mục tiêu → trả về manager_confirmed."""
        return self._open_reject_wizard("pmo_unapprove_goals")

    # ── State transitions: Result phase ───────────────────────────────────────

    def action_submit_result(self):
        """Member submits results → result_submitted. Auto-map self scores → manager scores."""
        self._validate_period_submit_result()
        for rec in self:
            if rec.state != "confirmed":
                raise UserError(_("Chỉ có thể nộp kết quả từ trạng thái Mục tiêu đã xác nhận."))
            confirmed_lines = rec.goal_line_ids.filtered(
                lambda l: l.manager_status in ("confirmed", "un_approved")
            )
            # Block nếu còn bất kỳ dòng nào bị từ chối kết quả (in_completed) — nhân viên phải sửa điểm
            incomplete_rejected = rec.goal_line_ids.filtered(
                lambda l: l.member_status == "in_completed"
            )
            if incomplete_rejected:
                names = ", ".join(incomplete_rejected.mapped("name"))
                raise ValidationError(_(
                    "Các mục tiêu sau bị từ chối kết quả, vui lòng cập nhật lại điểm tự đánh trước khi nộp: %s"
                ) % names)
            incomplete = confirmed_lines.filtered(
                lambda l: (
                    l.self_work_result == 0 and l.self_work_quality == 0
                    and l.self_cost_efficiency == 0 and l.self_scope == 0
                )
            )
            if incomplete:
                names = ", ".join(incomplete.mapped("name"))
                raise ValidationError(_(
                    "Vui lòng điền đủ 4 tiêu chí tự đánh giá cho các mục tiêu: %s"
                ) % names)
            # Auto-map self scores → manager scores (baseline for manager review)
            # Clear reject_reason from previous cycle
            for line in confirmed_lines:
                line.write({
                    "score_work_result": line.self_work_result,
                    "score_work_quality": line.self_work_quality,
                    "score_cost_efficiency": line.self_cost_efficiency,
                    "score_scope": line.self_scope,
                    "score_work_result_modified": False,
                    "score_work_quality_modified": False,
                    "score_cost_efficiency_modified": False,
                    "score_scope_modified": False,
                    "bul_score_work_result_modified": False,
                    "bul_score_work_quality_modified": False,
                    "bul_score_cost_efficiency_modified": False,
                    "bul_score_scope_modified": False,
                    "pmo_score_work_result_modified": False,
                    "pmo_score_work_quality_modified": False,
                    "pmo_score_cost_efficiency_modified": False,
                    "pmo_score_scope_modified": False,
                    "reject_reason": False,
                    "member_status": "submitted",
                    "manager_status": "confirmed",  # reset un_approved → confirmed khi nộp lại
                })
            rec.write({"state": "result_submitted"})
            rec._log("submit_result")
            rec.message_post(body=_("Nhân viên đã nộp kết quả."))

    def action_pm_approve(self):
        """PM approves results → pm_approved.
        Nếu có điểm bị sửa (khác với tự đánh) → phải dùng nút Từ chối (không được approve).
        """
        now = fields.Datetime.now()
        for rec in self:
            if rec.state != "result_submitted":
                raise UserError(_("Chỉ có thể phê duyệt kết quả ở trạng thái Đã nộp kết quả."))
            confirmed_lines = rec.goal_line_ids.filtered(
                lambda l: l.manager_status in ("confirmed", "un_approved")
            )
            # Block nếu còn dòng in_completed (nhân viên chưa sửa lại)
            incomplete_lines = rec.goal_line_ids.filtered(
                lambda l: l.member_status == "in_completed"
            )
            if incomplete_lines:
                names = ", ".join(incomplete_lines.mapped("name"))
                raise ValidationError(_(
                    "Các mục tiêu sau bị từ chối kết quả và chưa được nhân viên cập nhật lại: %s\n"
                    "Vui lòng yêu cầu nhân viên sửa điểm tự đánh trước khi phê duyệt."
                ) % names)
            # Nếu có điểm bị sửa (khác tự đánh) hoặc đã điền lý do từ chối → chặn approve
            modified_lines = confirmed_lines.filtered(
                lambda l: (
                    l.score_work_result != l.self_work_result
                    or l.score_work_quality != l.self_work_quality
                    or l.score_cost_efficiency != l.self_cost_efficiency
                    or l.score_scope != l.self_scope
                    or (l.reject_reason and l.reject_reason.strip())
                )
            )
            if modified_lines:
                names = ", ".join(modified_lines.mapped("name"))
                raise ValidationError(_(
                    "Bạn đã sửa điểm hoặc điền lý do từ chối các mục tiêu: %s\n"
                    "Vui lòng bấm nút 'Từ chối' thay vì 'Phê duyệt'."
                ) % names)
            confirmed_lines.write({
                "manager_status": "approved",
                "approved_by": self.env.user.id,
                "approved_date": now,
                "reject_reason": False,
            })
            rec.write({"state": "pm_approved"})
            rec._log("pm_approve")
            rec.message_post(body=_("Quản lý đã phê duyệt kết quả."))

    def button_pm_reject_result(self):
        """Trưởng CN từ chối kết quả → trả về confirmed (nhân viên nộp lại)."""
        return self._open_reject_wizard("result_reject")

    def button_pm_unapprove(self):
        """Open reject wizard for PM unapprove."""
        return self._open_reject_wizard("approve")

    # ── State transitions: BUL phase ─────────────────────────────────────────

    def action_bul_approve(self):
        """BUL approves:
        - Regular flow: pm_approved → bul_approved
        - Branch manager flow: result_submitted → bul_approved (skip pm_approved)
        """
        now = fields.Datetime.now()
        for rec in self:
            if rec.is_branch_manager:
                # Branch manager: BUL approves directly from result_submitted
                if rec.state != "result_submitted":
                    raise UserError(_("Trưởng chi nhánh: chỉ có thể Trưởng phòng phê duyệt ở trạng thái Đã nộp kết quả."))
                confirmed_lines = rec.goal_line_ids.filtered(
                    lambda l: l.manager_status in ("confirmed", "un_approved")
                )
                # Block nếu còn dòng in_completed
                incomplete_lines = rec.goal_line_ids.filtered(
                    lambda l: l.member_status == "in_completed"
                )
                if incomplete_lines:
                    names = ", ".join(incomplete_lines.mapped("name"))
                    raise ValidationError(_(
                        "Các mục tiêu sau bị từ chối kết quả và chưa được nhân viên cập nhật lại: %s\n"
                        "Vui lòng yêu cầu nhân viên sửa điểm tự đánh trước khi phê duyệt."
                    ) % names)
                # Chặn nếu điểm bị sửa hoặc có lý do từ chối
                modified_lines = confirmed_lines.filtered(
                    lambda l: (
                        l.score_work_result != l.self_work_result
                        or l.score_work_quality != l.self_work_quality
                        or l.score_cost_efficiency != l.self_cost_efficiency
                        or l.score_scope != l.self_scope
                        or (l.reject_reason and l.reject_reason.strip())
                    )
                )
                if modified_lines:
                    names = ", ".join(modified_lines.mapped("name"))
                    raise ValidationError(_(
                        "Bạn đã sửa điểm hoặc điền lý do từ chối các mục tiêu: %s\n"
                        "Vui lòng bấm nút 'Từ chối' thay vì 'Phê duyệt'."
                    ) % names)
                confirmed_lines.write({
                    "manager_status": "approved",
                    "approved_by": self.env.user.id,
                    "approved_date": now,
                    "reject_reason": False,
                })
                rec.write({"state": "bul_approved"})
                rec._log("bul_approve")
                rec.message_post(body=_("Trưởng phòng đã phê duyệt kết quả (Trưởng chi nhánh)."))
            else:
                # Regular flow: pm_approved → bul_approved
                if rec.state != "pm_approved":
                    raise UserError(_("Chỉ có thể BUL phê duyệt ở trạng thái Quản lý đã phê duyệt."))
                approved_lines = rec.goal_line_ids.filtered(
                    lambda l: l.manager_status == "approved"
                )
                # Block nếu còn dòng in_completed
                incomplete_lines = rec.goal_line_ids.filtered(
                    lambda l: l.member_status == "in_completed"
                )
                if incomplete_lines:
                    names = ", ".join(incomplete_lines.mapped("name"))
                    raise ValidationError(_(
                        "Các mục tiêu sau bị từ chối kết quả và chưa được nhân viên cập nhật lại: %s\n"
                        "Vui lòng yêu cầu nhân viên sửa điểm tự đánh trước khi phê duyệt."
                    ) % names)
                modified_lines = approved_lines.filtered(
                    lambda l: (
                        l.bul_score_work_result_modified or l.bul_score_work_quality_modified
                        or l.bul_score_cost_efficiency_modified or l.bul_score_scope_modified
                        or (l.reject_reason and l.reject_reason.strip())
                    )
                )
                if modified_lines:
                    names = ", ".join(modified_lines.mapped("name"))
                    raise ValidationError(_(
                        "Bạn đã sửa điểm hoặc điền lý do từ chối các mục tiêu: %s\n"
                        "Vui lòng bấm nút 'Từ chối' thay vì 'Phê duyệt'."
                    ) % names)
                approved_lines.write({"reject_reason": False})
                rec.write({"state": "bul_approved"})
                rec._log("bul_approve")
                rec.message_post(body=_("Giám đốc chi nhánh đã phê duyệt."))

    def button_bul_reject(self):
        """Open reject wizard for BUL reject."""
        return self._open_reject_wizard("bul")

    def button_bul_unapprove(self):
        """Open reject wizard for BUL unapprove (bul_approved → pm_approved)."""
        return self._open_reject_wizard("bul_unapprove")

    # ── State transitions: PMO phase ──────────────────────────────────────────

    def action_pmo_approve(self):
        """PMO approves:
        - Regular flow: bul_approved → pmo_approved
        - Sale Admin flow: result_submitted → pmo_approved
        Lines with PMO-modified scores must have reject_reason.
        """
        for rec in self:
            if rec.is_sale_admin:
                if rec.state != "result_submitted":
                    raise UserError(_("Sale Admin: chỉ có thể PMO phê duyệt ở trạng thái Đã nộp kết quả."))
            else:
                if rec.state != "bul_approved":
                    raise UserError(_("Chỉ có thể PMO phê duyệt ở trạng thái Trưởng phòng đã phê duyệt."))
            lines = rec.goal_line_ids
            # Block nếu còn dòng in_completed (nhân viên chưa sửa lại)
            incomplete_lines = rec.goal_line_ids.filtered(
                lambda l: l.member_status == "in_completed"
            )
            if incomplete_lines:
                names = ", ".join(incomplete_lines.mapped("name"))
                raise ValidationError(_(
                    "Các mục tiêu sau bị từ chối kết quả và chưa được nhân viên cập nhật lại: %s\n"
                    "Vui lòng yêu cầu nhân viên sửa điểm tự đánh trước khi phê duyệt."
                ) % names)
            modified_lines = lines.filtered(
                lambda l: (
                    l.pmo_score_work_result_modified or l.pmo_score_work_quality_modified
                    or l.pmo_score_cost_efficiency_modified or l.pmo_score_scope_modified
                    or (l.reject_reason and l.reject_reason.strip())
                )
            )
            if modified_lines:
                names = ", ".join(modified_lines.mapped("name"))
                raise ValidationError(_(
                    "Bạn đã sửa điểm hoặc điền lý do từ chối các mục tiêu: %s\n"
                    "Vui lòng bấm nút 'Từ chối' thay vì 'Phê duyệt'."
                ) % names)
            lines.write({"reject_reason": False})
            rec.write({"state": "pmo_approved"})
            rec._log("pmo_approve")
            rec.message_post(body=_("PMO đã phê duyệt."))

    def button_pmo_reject(self):
        """Open reject wizard for PMO reject."""
        return self._open_reject_wizard("pmo")

    def button_pmo_unapprove(self):
        """Open reject wizard for PMO unapprove (pmo_approved → bul_approved or result_submitted)."""
        return self._open_reject_wizard("pmo_unapprove")

    # ── State transitions: HR / Baseline ─────────────────────────────────────

    def action_baseline(self):
        """HR baselines the record → baselined."""
        for rec in self:
            if rec.state != "pmo_approved":
                raise UserError(_("Chỉ có thể cơ sở hóa ở trạng thái PMO đã phê duyệt."))
            rec.write({"state": "baselined"})
            rec._log("baseline")
            rec.message_post(body=_("Bản ghi đã được cơ sở hóa."))

    def button_hr_reject(self):
        """Open reject wizard for HR reject."""
        return self._open_reject_wizard("hr")

    def button_hr_reset_to_draft(self):
        """Admin/HR: reset bất kỳ bản ghi về Nháp, xóa toàn bộ điểm, giữ mục tiêu."""
        return self._open_reject_wizard("hr_reset")

    # ── Reject wizard launcher ────────────────────────────────────────────────

    def _open_reject_wizard(self, reject_type):
        wizard = self.env["msc.reject.wizard"].create({
            "record_ids": [(6, 0, self.ids)],
            "reject_type": reject_type,
        })
        return {
            "type": "ir.actions.act_window",
            "name": _("Lý do từ chối"),
            "res_model": "msc.reject.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }

    # ── Cron: auto-confirm ────────────────────────────────────────────────────

    @api.model
    def cron_auto_confirm(self):
        """Auto-confirm submitted records past the period's auto-confirm date."""
        today = fields.Date.today()
        periods = self.env["msc.period"].search([
            ("date_auto_confirm", "<=", today),
            ("state", "=", "open"),
        ])
        if not periods:
            return
        records = self.search([
            ("period_id", "in", periods.ids),
            ("state", "=", "submitted"),
        ])
        now = fields.Datetime.now()
        for rec in records:
            rec.goal_line_ids.write({
                "manager_status": "confirmed",
                "confirmed_by": self.env.ref("base.user_root").id,
                "confirmed_date": now,
            })
            # Sale Admin/Branch Manager đi thẳng confirmed (PMO đã là người duyệt duy nhất)
            # Loại thường → manager_confirmed (chờ PMO xác nhận thêm)
            new_state = "confirmed" if (rec.is_sale_admin or rec.is_branch_manager) else "manager_confirmed"
            rec.write({"state": new_state})
            rec.env["msc.approval.log"].create({
                "record_id": rec.id,
                "action": "auto_confirm",
                "actor_id": self.env.ref("base.user_root").id,
                "note": _("Tự động xác nhận do hết hạn."),
            })
            rec.message_post(body=_("Mục tiêu đã được tự động xác nhận do hết hạn xác nhận."))

    # ── Cron: auto-approve ────────────────────────────────────────────────────

    @api.model
    def cron_auto_approve(self):
        """Auto-approve result_submitted records past the period's auto-approve date."""
        today = fields.Date.today()
        periods = self.env["msc.period"].search([
            ("date_auto_approve", "<=", today),
            ("state", "=", "open"),
        ])
        if not periods:
            return
        records = self.search([
            ("period_id", "in", periods.ids),
            ("state", "=", "result_submitted"),
        ])
        now = fields.Datetime.now()
        for rec in records:
            rec.goal_line_ids.filtered(
                lambda l: l.manager_status == "confirmed"
            ).write({
                "manager_status": "approved",
                "approved_by": self.env.ref("base.user_root").id,
                "approved_date": now,
            })
            rec.write({"state": "pm_approved"})
            rec.env["msc.approval.log"].create({
                "record_id": rec.id,
                "action": "auto_approve",
                "actor_id": self.env.ref("base.user_root").id,
                "note": _("Tự động phê duyệt do hết hạn."),
            })
            rec.message_post(body=_("Kết quả đã được tự động phê duyệt do hết hạn phê duyệt."))
