from odoo import fields, models


class MscApprovalLog(models.Model):
    _name = "msc.approval.log"
    _description = "Nhật ký phê duyệt MSC"
    _order = "date desc, id desc"

    record_id = fields.Many2one(
        "msc.record",
        string="Bản ghi MSC",
        required=True,
        ondelete="cascade",
        index=True,
    )
    action = fields.Selection(
        [
            ("submit", "Nộp mục tiêu"),
            ("cancel_submit", "Hủy nộp mục tiêu"),
            ("pm_confirm", "Trưởng CN xác nhận"),
            ("pm_reject", "Trưởng CN từ chối"),
            ("bul_confirm_goals", "Trưởng phòng xác nhận mục tiêu"),
            ("pmo_confirm", "PMO xác nhận mục tiêu"),
            ("pmo_reject_goals", "PMO từ chối mục tiêu"),
            ("pmo_unapprove_goals", "PMO hủy xác nhận mục tiêu"),
            ("pmo_confirm_goals", "PMO xác nhận mục tiêu (sau cấp trên)"),
            ("submit_result", "Nộp kết quả"),
            ("pm_approve", "Trưởng CN phê duyệt"),
            ("pm_unapprove", "Trưởng CN hủy phê duyệt"),
            ("bul_approve", "Trưởng phòng phê duyệt"),
            ("bul_unapprove", "Trưởng phòng hủy phê duyệt"),
            ("bul_reject", "Trưởng phòng từ chối"),
            ("pmo_approve", "PMO phê duyệt"),
            ("pmo_unapprove", "PMO hủy phê duyệt"),
            ("pmo_reject", "PMO từ chối"),
            ("baseline", "HR xác nhận cuối"),
            ("hr_reject", "HR từ chối"),
            ("hr_reset", "Admin/HR hoàn trả về Nháp"),
            ("pmo_confirm_goals", "PMO xác nhận mục tiêu (sau cấp trên)"),
            ("pmo_reject_goals", "PMO từ chối mục tiêu (sau cấp trên)"),
            ("pmo_unapprove_goals", "PMO hủy xác nhận mục tiêu"),
            ("auto_confirm", "Tự động xác nhận"),
            ("auto_approve", "Tự động phê duyệt"),
        ],
        string="Hành động",
        required=True,
    )
    actor_id = fields.Many2one("res.users", string="Người thực hiện", required=True)
    date = fields.Datetime(string="Thời gian", default=fields.Datetime.now, readonly=True)
    note = fields.Text(string="Ghi chú / Lý do")
