from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MscPeriod(models.Model):
    _name = "msc.period"
    _description = "Chu kỳ MSC"
    _order = "year desc, month desc"

    name = fields.Char(string="Tên", compute="_compute_name", store=True, readonly=False)
    year = fields.Integer(string="Năm", required=True)
    month = fields.Selection(
        [
            ("1", "Tháng 1"), ("2", "Tháng 2"), ("3", "Tháng 3"),
            ("4", "Tháng 4"), ("5", "Tháng 5"), ("6", "Tháng 6"),
            ("7", "Tháng 7"), ("8", "Tháng 8"), ("9", "Tháng 9"),
            ("10", "Tháng 10"), ("11", "Tháng 11"), ("12", "Tháng 12"),
        ],
        string="Tháng",
        required=True,
    )
    state = fields.Selection(
        [
            ("draft", "Nháp"),
            ("open", "Đang mở"),
            ("closed", "Đã đóng"),
        ],
        string="Trạng thái",
        default="draft",
    )

    # Goal submission window
    date_submit_open = fields.Date(string="Mở nộp mục tiêu", required=True)
    date_submit_close = fields.Date(string="Đóng nộp mục tiêu", required=True)
    date_auto_confirm = fields.Date(
        string="Tự động xác nhận",
        help="Nếu PM không xác nhận trước ngày này, hệ thống tự xác nhận.",
    )

    # Result submission window
    date_result_open = fields.Date(string="Mở nộp kết quả", required=True)
    date_result_close = fields.Date(string="Đóng nộp kết quả", required=True)
    date_auto_approve = fields.Date(
        string="Tự động phê duyệt",
        help="Nếu BUL không phê duyệt trước ngày này, hệ thống tự phê duyệt.",
    )

    record_ids = fields.One2many("msc.record", "period_id", string="Bản ghi MSC")
    record_count = fields.Integer(string="Số bản ghi", compute="_compute_record_count")

    _unique_year_month = models.Constraint(
        "UNIQUE(year, month)",
        "Đã tồn tại chu kỳ MSC cho tháng/năm này.",
    )

    @api.depends("year", "month")
    def _compute_name(self):
        for rec in self:
            if rec.year and rec.month:
                rec.name = f"MSC T{int(rec.month):02d}/{rec.year}"
            else:
                rec.name = ""

    def _compute_record_count(self):
        for rec in self:
            rec.record_count = len(rec.record_ids)

    @api.constrains(
        "date_submit_open", "date_submit_close",
        "date_result_open", "date_result_close",
        "date_auto_confirm", "date_auto_approve",
    )
    def _check_dates(self):
        for rec in self:
            if rec.date_submit_open and rec.date_submit_close:
                if rec.date_submit_open > rec.date_submit_close:
                    raise ValidationError(_("Ngày mở nộp mục tiêu phải trước ngày đóng."))
            if rec.date_result_open and rec.date_result_close:
                if rec.date_result_open > rec.date_result_close:
                    raise ValidationError(_("Ngày mở nộp kết quả phải trước ngày đóng."))
            if rec.date_submit_close and rec.date_result_open:
                if rec.date_submit_close > rec.date_result_open:
                    raise ValidationError(_("Ngày mở nộp kết quả phải sau ngày đóng nộp mục tiêu."))
            if rec.date_auto_confirm and rec.date_submit_close:
                if rec.date_auto_confirm < rec.date_submit_close:
                    raise ValidationError(_(
                        "Ngày tự động xác nhận phải sau hoặc bằng ngày đóng nộp mục tiêu (%s)."
                    ) % rec.date_submit_close)
            if rec.date_auto_approve and rec.date_result_close:
                if rec.date_auto_approve < rec.date_result_close:
                    raise ValidationError(_(
                        "Ngày tự động phê duyệt phải sau hoặc bằng ngày đóng nộp kết quả (%s)."
                    ) % rec.date_result_close)

    def action_open(self):
        self.write({"state": "open"})

    def action_close(self):
        self.write({"state": "closed"})

    def action_view_records(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Bản ghi MSC — {self.name}",
            "res_model": "msc.record",
            "view_mode": "list,form",
            "domain": [("period_id", "=", self.id)],
            "context": {"default_period_id": self.id},
        }
