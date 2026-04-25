from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


class MscRejectWizard(models.TransientModel):
    _name = "msc.reject.wizard"
    _description = "Wizard từ chối / hủy phê duyệt MSC"

    record_ids = fields.Many2many(
        "msc.record",
        "msc_reject_wizard_record_rel",
        "wizard_id",
        "record_id",
        string="Bản ghi MSC",
        required=True,
    )
    reason = fields.Text(string="Lý do")
    reject_type = fields.Selection(
        [
            ("confirm", "Trưởng CN từ chối xác nhận"),
            ("result_reject", "Trưởng CN từ chối kết quả"),
            ("approve", "Trưởng CN hủy phê duyệt"),
            ("bul", "Trưởng phòng từ chối"),
            ("bul_unapprove", "Trưởng phòng hủy phê duyệt"),
            ("pmo", "PMO từ chối"),
            ("pmo_unapprove", "PMO hủy phê duyệt"),
            ("hr", "HR từ chối"),
            ("hr_reset", "Admin/HR hoàn trả về Nháp"),
            ("pmo_reject_goals", "PMO từ chối mục tiêu (sau cấp trên xác nhận)"),
            ("pmo_unapprove_goals", "PMO hủy xác nhận mục tiêu"),
        ],
        string="Loại từ chối",
        required=True,
    )

    def action_confirm(self):
        self.ensure_one()
        method_map = {
            "confirm": self._do_pm_reject,
            "result_reject": self._do_pm_reject_result,
            "approve": self._do_pm_unapprove,
            "bul": self._do_bul_reject,
            "bul_unapprove": self._do_bul_unapprove,
            "pmo": self._do_pmo_reject,
            "pmo_unapprove": self._do_pmo_unapprove,
            "hr": self._do_hr_reject,
            "hr_reset": self._do_hr_reset_to_draft,
            "pmo_reject_goals": self._do_pmo_reject_manager_confirmed,
            "pmo_unapprove_goals": self._do_pmo_unapprove_goals,
        }
        handler = method_map.get(self.reject_type)
        if not handler:
            raise UserError(_("Loại từ chối không hợp lệ."))
        for rec in self.record_ids:
            handler(rec)
        return {"type": "ir.actions.act_window_close"}

    # ── In-app notification (bus) ─────────────────────────────────────────────

    def _notify_users(self, rec, title, message, *employees):
        """Gửi in-app notification (chuông) đến các nhân viên — không gửi email."""
        for emp in employees:
            if not emp or not emp.user_id:
                continue
            partner = emp.user_id.partner_id
            if not partner:
                continue
            self.env['bus.bus']._sendone(
                partner,
                "simple_notification",
                {
                    "title": title,
                    "message": message,
                    "sticky": True,
                    "type": "warning",
                }
            )

    # ── Reject handlers ───────────────────────────────────────────────────────

    def _notify_chain(self, rec, title, msg):
        """Notify employee + report_to_id (Trưởng CN) — luôn dùng cho mọi loại reject."""
        self._notify_users(rec, title, msg, rec.employee_id, rec.report_to_id)

    def _do_pm_reject(self, rec):
        if rec.state != "submitted":
            raise UserError(
                _("Không thể từ chối bản ghi '%s': trạng thái không hợp lệ.") % rec.name
            )
        # Per-line rejection: lines with reject_reason filled → rejected; others untouched
        lines_with_reason = rec.goal_line_ids.filtered(
            lambda l: l.reject_reason and l.reject_reason.strip()
        )
        if lines_with_reason:
            lines_with_reason.write({"manager_status": "rejected"})
            # Lines without reason keep manager_status as-is (na)
        else:
            # Fallback: reject all with wizard-level reason
            rec.goal_line_ids.write({
                "manager_status": "rejected",
                "reject_reason": self.reason or "",
            })
        rec.write({"state": "draft"})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "pm_reject",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        title = _("MSC bị Trưởng CN từ chối")
        if lines_with_reason:
            goal_details = "\n".join(
                "- %s: %s" % (l.name, l.reject_reason) for l in lines_with_reason
            )
            msg = _("Nhân viên: %s\nTừ chối bởi: %s\nCác mục tiêu bị từ chối:\n%s") % (
                rec.employee_id.name, self.env.user.name, goal_details)
        else:
            reason_text = self.reason or _("(không có lý do)")
            msg = _("Nhân viên: %s\nTừ chối bởi: %s\nLý do: %s") % (
                rec.employee_id.name, self.env.user.name, reason_text)
        # PM reject: chỉ notify employee
        self._notify_users(rec, title, msg, rec.employee_id)

    def _do_pm_reject_result(self, rec):
        """Trưởng CN từ chối kết quả → trả về confirmed.
        Chỉ dòng có reject_reason → in_completed. Dòng khác giữ nguyên member_status.
        Bắt buộc: dòng nào bị sửa điểm phải có reject_reason.
        """
        if rec.state != "result_submitted":
            raise UserError(
                _("Không thể từ chối kết quả bản ghi '%s': trạng thái không hợp lệ.") % rec.name
            )
        # Kiểm tra: dòng nào có điểm bị sửa mà không có lý do → block
        modified_without_reason = rec.goal_line_ids.filtered(
            lambda l: (
                l.score_work_result_modified or l.score_work_quality_modified
                or l.score_cost_efficiency_modified or l.score_scope_modified
            ) and not (l.reject_reason and l.reject_reason.strip())
        )
        if modified_without_reason:
            names = ", ".join(modified_without_reason.mapped("name"))
            raise UserError(_(
                "Bạn đã sửa điểm các mục tiêu sau nhưng chưa điền lý do từ chối: %s\n"
                "Vui lòng điền lý do vào cột 'Lý do từ chối / hủy' trước khi bấm Từ chối."
            ) % names)
        rejected_lines = rec.goal_line_ids.filtered(
            lambda l: l.reject_reason and l.reject_reason.strip()
        )
        if not rejected_lines:
            raise UserError(_(
                "Vui lòng điền lý do từ chối vào ít nhất một dòng mục tiêu trước khi bấm Từ chối."
            ))
        # Chỉ dòng có lý do → in_completed; dòng khác giữ nguyên
        rejected_lines.write({"member_status": "in_completed"})
        rec.write({"state": "confirmed"})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "pm_reject",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        title = _("MSC bị Trưởng CN từ chối kết quả")
        goal_details = "\n".join(
            "- %s: %s" % (l.name, l.reject_reason) for l in rejected_lines
        )
        msg = _("Nhân viên: %s\nTừ chối bởi: %s\nCác mục tiêu bị từ chối:\n%s") % (
            rec.employee_id.name, self.env.user.name, goal_details)
        self._notify_users(rec, title, msg, rec.employee_id)

    def _do_pm_unapprove(self, rec):
        if rec.state != "pm_approved":
            raise UserError(
                _("Không thể hủy phê duyệt bản ghi '%s': trạng thái không hợp lệ.") % rec.name
            )
        rec.goal_line_ids.filtered(
            lambda l: l.manager_status == "approved"
        ).write({
            "manager_status": "un_approved",
            "reject_reason": self.reason or "",
        })
        rec.write({"state": "result_submitted"})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "pm_unapprove",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        reason_text = self.reason or _("(không có lý do)")
        title = _("MSC bị Trưởng CN hủy phê duyệt")
        msg = _("Nhân viên: %s\nHủy phê duyệt bởi: %s\nLý do: %s") % (
            rec.employee_id.name, self.env.user.name, reason_text)
        self._notify_users(rec, title, msg, rec.employee_id)

    def _do_bul_reject(self, rec):
        """Trưởng phòng từ chối → trả về result_submitted.
        Dòng nào có reject_reason → in_completed; dòng khác giữ nguyên.
        Bắt buộc: dòng sửa điểm phải có lý do.
        """
        if rec.state != "pm_approved":
            raise UserError(
                _("Không thể từ chối bản ghi '%s': trạng thái không hợp lệ.") % rec.name
            )
        modified_without_reason = rec.goal_line_ids.filtered(
            lambda l: (
                l.bul_score_work_result_modified or l.bul_score_work_quality_modified
                or l.bul_score_cost_efficiency_modified or l.bul_score_scope_modified
            ) and not (l.reject_reason and l.reject_reason.strip())
        )
        if modified_without_reason:
            names = ", ".join(modified_without_reason.mapped("name"))
            raise UserError(_(
                "Bạn đã sửa điểm các mục tiêu sau nhưng chưa điền lý do từ chối: %s\n"
                "Vui lòng điền lý do vào cột 'Lý do từ chối / hủy' trước khi bấm Từ chối."
            ) % names)
        rejected_lines = rec.goal_line_ids.filtered(
            lambda l: l.reject_reason and l.reject_reason.strip()
        )
        if not rejected_lines:
            raise UserError(_(
                "Vui lòng điền lý do từ chối vào ít nhất một dòng mục tiêu trước khi bấm Từ chối."
            ))
        # Dòng bị từ chối: in_completed + un_approved; dòng không bị từ chối: giữ member_status, reset về confirmed
        rejected_lines.write({"member_status": "in_completed", "manager_status": "un_approved"})
        other_lines = rec.goal_line_ids - rejected_lines
        other_lines.filtered(lambda l: l.manager_status == "approved").write({"manager_status": "confirmed"})
        rec.write({"state": "result_submitted"})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "bul_reject",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        title = _("MSC bị Trưởng phòng từ chối")
        goal_details = "\n".join(
            "- %s: %s" % (l.name, l.reject_reason) for l in rejected_lines
        )
        msg = _("Nhân viên: %s\nTừ chối bởi: %s\nCác mục tiêu bị từ chối:\n%s") % (
            rec.employee_id.name, self.env.user.name, goal_details)
        self._notify_chain(rec, title, msg)

    def _do_bul_unapprove(self, rec):
        if rec.state != "bul_approved":
            raise UserError(
                _("Không thể hủy phê duyệt bản ghi '%s': trạng thái không hợp lệ.") % rec.name
            )
        rec.write({"state": "pm_approved"})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "bul_unapprove",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        reason_text = self.reason or _("(không có lý do)")
        title = _("MSC bị Trưởng phòng hủy phê duyệt")
        msg = _("Nhân viên: %s\nHủy phê duyệt bởi: %s\nLý do: %s") % (
            rec.employee_id.name, self.env.user.name, reason_text)
        # BUL unapprove: notify employee + Trưởng CN
        self._notify_chain(rec, title, msg)

    def _do_pmo_reject(self, rec):
        """PMO từ chối → trả về pm_approved (regular) hoặc confirmed (sale admin).
        Dòng nào có reject_reason → in_completed; dòng khác giữ nguyên.
        Bắt buộc: dòng sửa điểm phải có lý do.
        """
        valid_states = ("bul_approved",) if not rec.is_sale_admin else ("result_submitted",)
        if rec.state not in valid_states:
            raise UserError(
                _("Không thể PMO từ chối bản ghi '%s': trạng thái không hợp lệ.") % rec.name
            )
        modified_without_reason = rec.goal_line_ids.filtered(
            lambda l: (
                l.pmo_score_work_result_modified or l.pmo_score_work_quality_modified
                or l.pmo_score_cost_efficiency_modified or l.pmo_score_scope_modified
            ) and not (l.reject_reason and l.reject_reason.strip())
        )
        if modified_without_reason:
            names = ", ".join(modified_without_reason.mapped("name"))
            raise UserError(_(
                "Bạn đã sửa điểm các mục tiêu sau nhưng chưa điền lý do từ chối: %s\n"
                "Vui lòng điền lý do vào cột 'Lý do từ chối / hủy' trước khi bấm Từ chối."
            ) % names)
        rejected_lines = rec.goal_line_ids.filtered(
            lambda l: l.reject_reason and l.reject_reason.strip()
        )
        if not rejected_lines:
            raise UserError(_(
                "Vui lòng điền lý do từ chối vào ít nhất một dòng mục tiêu trước khi bấm Từ chối."
            ))
        # Dòng bị từ chối: in_completed + un_approved; dòng không bị từ chối: reset về confirmed/approved
        rejected_lines.write({"member_status": "in_completed", "manager_status": "un_approved"})
        other_lines = rec.goal_line_ids - rejected_lines
        other_lines.filtered(lambda l: l.manager_status == "approved").write({"manager_status": "confirmed"})
        back_state = "confirmed" if rec.is_sale_admin else "pm_approved"
        rec.write({"state": back_state})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "pmo_reject",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        title = _("MSC bị PMO từ chối")
        goal_details = "\n".join(
            "- %s: %s" % (l.name, l.reject_reason) for l in rejected_lines
        )
        msg = _("Nhân viên: %s\nTừ chối bởi: %s\nCác mục tiêu bị từ chối:\n%s") % (
            rec.employee_id.name, self.env.user.name, goal_details)
        self._notify_chain(rec, title, msg)

    def _do_pmo_unapprove(self, rec):
        """PMO hủy phê duyệt (pmo_approved → bul_approved/result_submitted)."""
        if rec.state != "pmo_approved":
            raise UserError(
                _("Không thể PMO hủy phê duyệt bản ghi '%s': trạng thái không hợp lệ.") % rec.name
            )
        back_state = "confirmed" if rec.is_sale_admin else "bul_approved"
        rec.write({"state": back_state})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "pmo_unapprove",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        reason_text = self.reason or _("(không có lý do)")
        title = _("MSC bị PMO hủy phê duyệt")
        msg = _("Nhân viên: %s\nHủy phê duyệt bởi: %s\nLý do: %s") % (
            rec.employee_id.name, self.env.user.name, reason_text)
        # PMO unapprove: notify employee + Trưởng CN
        self._notify_chain(rec, title, msg)

    def _do_hr_reject(self, rec):
        if rec.state != "pmo_approved":
            raise UserError(
                _("Không thể từ chối bản ghi '%s': trạng thái không hợp lệ.") % rec.name
            )
        rec.write({"state": "bul_approved" if not rec.is_sale_admin else "result_submitted"})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "hr_reject",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        reason_text = self.reason or _("(không có lý do)")
        title = _("MSC bị HR từ chối")
        msg = _("Nhân viên: %s\nTừ chối bởi: %s\nLý do: %s") % (
            rec.employee_id.name, self.env.user.name, reason_text)
        # HR reject: notify employee + Trưởng CN
        self._notify_chain(rec, title, msg)

    def _do_pmo_reject_manager_confirmed(self, rec):
        """PMO từ chối mục tiêu sau khi cấp trên xác nhận → trả về draft, reset goal lines."""
        if rec.state != "manager_confirmed":
            raise UserError(
                _("Không thể PMO từ chối bản ghi '%s': trạng thái không hợp lệ.") % rec.name
            )
        lines_with_reason = rec.goal_line_ids.filtered(
            lambda l: l.reject_reason and l.reject_reason.strip()
        )
        if lines_with_reason:
            lines_with_reason.write({"manager_status": "rejected"})
        else:
            rec.goal_line_ids.write({
                "manager_status": "rejected",
                "reject_reason": self.reason or "",
            })
        rec.goal_line_ids.write({"confirmed_by": False, "confirmed_date": False})
        rec.write({"state": "draft"})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "pmo_reject_goals",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        reason_text = self.reason or _("(không có lý do)")
        title = _("MSC bị PMO từ chối mục tiêu")
        msg = _("Nhân viên: %s\nTừ chối bởi: %s\nLý do: %s") % (
            rec.employee_id.name, self.env.user.name, reason_text)
        self._notify_chain(rec, title, msg)

    def _do_pmo_unapprove_goals(self, rec):
        """PMO hủy xác nhận mục tiêu (confirmed → manager_confirmed)."""
        if rec.state != "confirmed":
            raise UserError(
                _("Không thể hủy xác nhận mục tiêu bản ghi '%s': trạng thái không hợp lệ.") % rec.name
            )
        rec.write({"state": "manager_confirmed"})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "pmo_unapprove_goals",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        reason_text = self.reason or _("(không có lý do)")
        title = _("MSC bị PMO hủy xác nhận mục tiêu")
        msg = _("Nhân viên: %s\nHủy xác nhận bởi: %s\nLý do: %s") % (
            rec.employee_id.name, self.env.user.name, reason_text)
        self._notify_chain(rec, title, msg)

    def _do_hr_reset_to_draft(self, rec):
        """Admin/HR hoàn trả về Nháp: giữ mục tiêu, xóa toàn bộ điểm và trạng thái dòng."""
        rec.goal_line_ids.write({
            "member_status": "na",
            "manager_status": "na",
            "reject_reason": False,
            "confirmed_by": False,
            "confirmed_date": False,
            "approved_by": False,
            "approved_date": False,
            # Xóa điểm tự đánh
            "self_work_result": 0,
            "self_work_quality": 0,
            "self_cost_efficiency": 0,
            "self_scope": 0,
            # Xóa điểm quản lý
            "score_work_result": 0,
            "score_work_quality": 0,
            "score_cost_efficiency": 0,
            "score_scope": 0,
            "score_work_result_modified": False,
            "score_work_quality_modified": False,
            "score_cost_efficiency_modified": False,
            "score_scope_modified": False,
            # Xóa điểm BUL
            "bul_score_work_result_modified": False,
            "bul_score_work_quality_modified": False,
            "bul_score_cost_efficiency_modified": False,
            "bul_score_scope_modified": False,
            # Xóa điểm PMO
            "pmo_score_work_result_modified": False,
            "pmo_score_work_quality_modified": False,
            "pmo_score_cost_efficiency_modified": False,
            "pmo_score_scope_modified": False,
        })
        rec.write({"state": "draft"})
        rec.env["msc.approval.log"].create({
            "record_id": rec.id, "action": "hr_reset",
            "actor_id": self.env.user.id, "note": self.reason,
        })
        reason_text = self.reason or _("(không có lý do)")
        title = _("MSC đã được Admin/HR hoàn trả về Nháp")
        msg = _("Nhân viên: %s\nHoàn trả bởi: %s\nLý do: %s") % (
            rec.employee_id.name, self.env.user.name, reason_text)
        self._notify_chain(rec, title, msg)
