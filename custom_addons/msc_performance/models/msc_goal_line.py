from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


def _color(val, max_val):
    """Return 'green'/'yellow'/'red' based on score ratio."""
    if max_val == 0:
        return "red"
    ratio = val / max_val
    if ratio >= 0.75:
        return "green"
    elif ratio > 0:
        return "yellow"
    return "red"


class MscGoalLine(models.Model):
    _name = "msc.goal.line"
    _description = "Mục tiêu MSC"
    _order = "goal_type, sequence, id"

    record_id = fields.Many2one(
        "msc.record",
        string="Bản ghi MSC",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(default=10)
    goal_type = fields.Selection(
        [
            ("must", "MUST"),
            ("should", "SHOULD"),
            ("could", "COULD"),
        ],
        string="Loại mục tiêu",
        required=True,
        default="must",
    )
    name = fields.Text(string="Tên mục tiêu", required=True)
    description = fields.Text(string="Mô tả / KPI")
    result_note = fields.Text(string="Kết quả thực tế")

    member_status = fields.Selection(
        [
            ("na", "Chưa cập nhật"),
            ("submitted", "Đã nộp"),
            ("completed", "Hoàn thành"),
            ("in_completed", "Không hoàn thành"),
        ],
        string="Trạng thái (thành viên)",
        default="na",
    )
    manager_status = fields.Selection(
        [
            ("na", "Chưa xác nhận"),
            ("confirmed", "Đã xác nhận"),
            ("rejected", "Từ chối"),
            ("approved", "Đã phê duyệt"),
            ("un_approved", "Hủy phê duyệt"),
        ],
        string="Trạng thái (quản lý)",
        default="na",
    )
    reject_reason = fields.Text(string="Lý do từ chối / hủy")

    confirmed_by = fields.Many2one("res.users", string="Xác nhận bởi", readonly=True)
    confirmed_date = fields.Datetime(string="Ngày xác nhận", readonly=True)
    approved_by = fields.Many2one("res.users", string="Phê duyệt bởi", readonly=True)
    approved_date = fields.Datetime(string="Ngày phê duyệt", readonly=True)

    # ── Self-scoring by member (0–4) ──────────────────────────────────────────

    self_work_result = fields.Integer(string="Kết quả công việc (tự đánh)", default=0)
    self_work_quality = fields.Integer(string="Chất lượng công việc (tự đánh)", default=0)
    self_cost_efficiency = fields.Integer(string="Hiệu quả về chi phí (tự đánh)", default=0)
    self_scope = fields.Integer(string="Phạm vi đăng ký (tự đánh)", default=0)

    # ── Manager/BUL scoring (0–4) — mapped from self, editable by manager/BUL ─

    score_work_result = fields.Integer(string="Kết quả công việc (QL)", default=0)
    score_work_quality = fields.Integer(string="Chất lượng công việc (QL)", default=0)
    score_cost_efficiency = fields.Integer(string="Hiệu quả về chi phí (QL)", default=0)
    score_scope = fields.Integer(string="Phạm vi đăng ký (QL)", default=0)

    # ── Track which scores were modified ──────────────────────────────────────
    # PM modified flags (set True when PM changes score from self-score)
    score_work_result_modified = fields.Boolean(default=False)
    score_work_quality_modified = fields.Boolean(default=False)
    score_cost_efficiency_modified = fields.Boolean(default=False)
    score_scope_modified = fields.Boolean(default=False)

    # BUL modified flags (set True when BUL changes score from PM-approved score)
    bul_score_work_result_modified = fields.Boolean(default=False)
    bul_score_work_quality_modified = fields.Boolean(default=False)
    bul_score_cost_efficiency_modified = fields.Boolean(default=False)
    bul_score_scope_modified = fields.Boolean(default=False)

    # PMO modified flags (set True when PMO changes score at bul_approved stage)
    pmo_score_work_result_modified = fields.Boolean(default=False)
    pmo_score_work_quality_modified = fields.Boolean(default=False)
    pmo_score_cost_efficiency_modified = fields.Boolean(default=False)
    pmo_score_scope_modified = fields.Boolean(default=False)

    # ── Computed totals ───────────────────────────────────────────────────────

    score_max_per_criterion = fields.Integer(
        compute="_compute_score", store=True,
    )
    score_total = fields.Integer(
        string="Tổng điểm (QL)",
        compute="_compute_score", store=True,
    )
    score_color = fields.Char(
        compute="_compute_score", store=True,
    )
    self_score_total = fields.Integer(
        string="Tổng điểm tự đánh",
        compute="_compute_score", store=True,
    )
    self_score_color = fields.Char(
        compute="_compute_score", store=True,
    )

    @api.depends(
        "goal_type",
        "self_work_result", "self_work_quality",
        "self_cost_efficiency", "self_scope",
        "score_work_result", "score_work_quality",
        "score_cost_efficiency", "score_scope",
    )
    def _compute_score(self):
        for line in self:
            # MUST: max 4pts per criterion; SHOULD/COULD: max 3pts per criterion
            max_per = 4 if line.goal_type == "must" else 3
            line.score_max_per_criterion = max_per

            pm_total = (
                line.score_work_result + line.score_work_quality
                + line.score_cost_efficiency + line.score_scope
            )
            line.score_total = pm_total
            line.score_color = _color(pm_total, max_per * 4)

            self_total = (
                line.self_work_result + line.self_work_quality
                + line.self_cost_efficiency + line.self_scope
            )
            line.self_score_total = self_total
            line.self_score_color = _color(self_total, max_per * 4)

    @api.constrains(
        "goal_type",
        "self_work_result", "self_work_quality",
        "self_cost_efficiency", "self_scope",
        "score_work_result", "score_work_quality",
        "score_cost_efficiency", "score_scope",
    )
    def _check_scores(self):
        for line in self:
            max_val = 4 if line.goal_type == "must" else 3
            for fname in (
                "self_work_result", "self_work_quality",
                "self_cost_efficiency", "self_scope",
                "score_work_result", "score_work_quality",
                "score_cost_efficiency", "score_scope",
            ):
                val = getattr(line, fname)
                if val < 0 or val > max_val:
                    raise ValidationError(
                        _("Điểm mỗi tiêu chí phải từ 0 đến %d (loại mục tiêu: %s).") % (max_val, line.goal_type.upper())
                    )

    def write(self, vals):
        """Auto-set modified flags when score_* fields change.
        Also restricts self-score editing to in_completed lines after rejection.
        """
        # Pre-write: sau khi từ chối, chỉ được sửa điểm tự đánh ở dòng 'Không hoàn thành'
        self_score_fields_set = {"self_work_result", "self_work_quality", "self_cost_efficiency", "self_scope"}
        if self_score_fields_set & set(vals):
            for line in self:
                if line.record_id.state == "confirmed":
                    has_rejected = line.record_id.goal_line_ids.filtered(
                        lambda l: l.member_status == "in_completed"
                    )
                    if has_rejected and line.member_status != "in_completed":
                        status_label = dict(
                            line._fields["member_status"].selection
                        ).get(line.member_status, line.member_status)
                        raise ValidationError(_(
                            "Sau khi bị từ chối, chỉ được sửa điểm tự đánh cho mục tiêu 'Không hoàn thành'.\n"
                            "Mục tiêu '%s' đang ở trạng thái '%s'."
                        ) % (line.name, status_label))

        # PM modified flags: track when score changes vs self-score (state: result_submitted)
        pm_score_map = {
            "score_work_result": ("score_work_result_modified", "self_work_result"),
            "score_work_quality": ("score_work_quality_modified", "self_work_quality"),
            "score_cost_efficiency": ("score_cost_efficiency_modified", "self_cost_efficiency"),
            "score_scope": ("score_scope_modified", "self_scope"),
        }
        # BUL modified flags: track when score changes at pm_approved stage
        bul_score_map = {
            "score_work_result": "bul_score_work_result_modified",
            "score_work_quality": "bul_score_work_quality_modified",
            "score_cost_efficiency": "bul_score_cost_efficiency_modified",
            "score_scope": "bul_score_scope_modified",
        }
        # PMO modified flags: track when score changes at bul_approved stage
        pmo_score_map = {
            "score_work_result": "pmo_score_work_result_modified",
            "score_work_quality": "pmo_score_work_quality_modified",
            "score_cost_efficiency": "pmo_score_cost_efficiency_modified",
            "score_scope": "pmo_score_scope_modified",
        }
        result = super().write(vals)
        for line in self:
            state = line.record_id.state
            extra = {}
            # Khi nhân viên sửa tên/mô tả mục tiêu ở draft → reset rejected status
            if state == "draft" and ("name" in vals or "description" in vals):
                if line.manager_status == "rejected":
                    extra["manager_status"] = "na"
                    extra["reject_reason"] = False
            # Khi nhân viên sửa điểm tự đánh ở confirmed → reset in_completed → submitted
            self_score_fields = {"self_work_result", "self_work_quality", "self_cost_efficiency", "self_scope"}
            if state == "confirmed" and self_score_fields & set(vals):
                if line.member_status == "in_completed":
                    extra["member_status"] = "submitted"
                    extra["reject_reason"] = False
            for score_field, (pm_flag, self_field) in pm_score_map.items():
                if score_field in vals and state == "result_submitted":
                    new_val = vals[score_field]
                    extra[pm_flag] = (new_val != getattr(line, self_field))
                if score_field in vals and state == "pm_approved":
                    extra[bul_score_map[score_field]] = True
                if score_field in vals and state == "bul_approved":
                    extra[pmo_score_map[score_field]] = True
            if extra:
                super(MscGoalLine, line).write(extra)
        return result
