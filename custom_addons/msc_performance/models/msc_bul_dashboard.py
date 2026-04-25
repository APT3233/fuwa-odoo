from odoo import _, api, fields, models


RATING_LABELS = {
    "a_plus": "Hoàn thành xuất sắc (A+)",
    "a":      "Hoàn thành vượt mức (A)",
    "b":      "Hoàn thành ở mức đạt yêu cầu (B)",
    "c":      "Chưa hoàn thành công việc (C)",
    "d":      "Không hoàn thành công việc (D)",
}
RATING_ORDER = ["a_plus", "a", "b", "c", "d"]


class MscBulDashboard(models.TransientModel):
    """Bảng đánh giá xếp loại bộ phận — transient, computed on open."""
    _name = "msc.bul.dashboard"
    _description = "Bảng đánh giá xếp loại bộ phận"

    period_id = fields.Many2one(
        "msc.period",
        string="Chu kỳ",
        required=True,
    )
    line_ids = fields.One2many(
        "msc.bul.dashboard.line",
        "dashboard_id",
        string="Xếp loại theo bộ phận",
        readonly=True,
    )
    pending_ids = fields.One2many(
        "msc.bul.dashboard.pending",
        "dashboard_id",
        string="Danh sách MSC chờ phê duyệt",
        readonly=True,
    )

    def action_compute(self):
        """Recompute dashboard lines for selected period."""
        self.ensure_one()
        self.line_ids.unlink()
        self.pending_ids.unlink()

        # Records in state pm_approved for this period
        records = self.env["msc.record"].search([
            ("period_id", "=", self.period_id.id),
            ("state", "in", ("pm_approved", "bul_approved", "baselined")),
        ])

        # Group by department
        dept_map = {}  # {dept_id: {"name": ..., ratings: {a_plus:0, a:0, ...}}}
        for rec in records:
            dept = rec.department_id
            dept_key = dept.id if dept else 0
            dept_name = dept.name if dept else _("(Chưa phân bộ phận)")
            if dept_key not in dept_map:
                dept_map[dept_key] = {
                    "name": dept_name,
                    "ratings": {r: 0 for r in RATING_ORDER},
                }
            rating = rec.performance_rating or "d"
            if rating in dept_map[dept_key]["ratings"]:
                dept_map[dept_key]["ratings"][rating] += 1

        # Create summary lines
        Line = self.env["msc.bul.dashboard.line"]
        for dept_key, data in dept_map.items():
            total = sum(data["ratings"].values())
            for rating in RATING_ORDER:
                count = data["ratings"][rating]
                Line.create({
                    "dashboard_id": self.id,
                    "department_name": data["name"],
                    "performance_result": rating,
                    "count": count,
                    "percentage": round(count / total * 100, 2) if total else 0.0,
                })

        # Pending: pm_approved records (waiting BUL approve)
        pending_records = self.env["msc.record"].search([
            ("period_id", "=", self.period_id.id),
            ("state", "=", "pm_approved"),
        ])
        Pending = self.env["msc.bul.dashboard.pending"]
        for rec in pending_records:
            Pending.create({
                "dashboard_id": self.id,
                "record_id": rec.id,
                "employee_id": rec.employee_id.id,
                "department_id": rec.department_id.id if rec.department_id else False,
                "report_to_id": rec.report_to_id.id if rec.report_to_id else False,
                "performance_rating": rec.performance_rating or "d",
                "total_score": rec.total_score,
                "state": rec.state,
            })

        return {
            "type": "ir.actions.act_window",
            "res_model": "msc.bul.dashboard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }


class MscBulDashboardLine(models.TransientModel):
    """Dòng xếp loại theo bộ phận."""
    _name = "msc.bul.dashboard.line"
    _description = "Dòng bảng đánh giá xếp loại"
    _order = "department_name, performance_result"

    dashboard_id = fields.Many2one("msc.bul.dashboard", ondelete="cascade")
    department_name = fields.Char(string="Bộ phận", readonly=True)
    performance_result = fields.Selection(
        [
            ("a_plus", "Hoàn thành xuất sắc (A+)"),
            ("a",      "Hoàn thành vượt mức (A)"),
            ("b",      "Hoàn thành ở mức đạt yêu cầu (B)"),
            ("c",      "Chưa hoàn thành công việc (C)"),
            ("d",      "Không hoàn thành công việc (D)"),
        ],
        string="Performance Result",
        readonly=True,
    )
    count = fields.Integer(string="Tổng số", readonly=True)
    percentage = fields.Float(string="Tỷ lệ (%)", digits=(5, 2), readonly=True)


class MscBulDashboardPending(models.TransientModel):
    """MSC đang chờ Giám đốc chi nhánh phê duyệt."""
    _name = "msc.bul.dashboard.pending"
    _description = "Danh sách MSC chờ phê duyệt"
    _order = "department_id, employee_id"

    dashboard_id = fields.Many2one("msc.bul.dashboard", ondelete="cascade")
    record_id = fields.Many2one("msc.record", string="Bản ghi MSC", readonly=True)
    employee_id = fields.Many2one("hr.employee", string="Nhân viên", readonly=True)
    department_id = fields.Many2one("hr.department", string="Bộ phận", readonly=True)
    report_to_id = fields.Many2one("hr.employee", string="Quản lý", readonly=True)
    performance_rating = fields.Selection(
        [
            ("a_plus", "A+"),
            ("a",      "A"),
            ("b",      "B"),
            ("c",      "C"),
            ("d",      "D"),
        ],
        string="Xếp loại",
        readonly=True,
    )
    total_score = fields.Integer(string="Tổng điểm", readonly=True)
    state = fields.Char(string="Trạng thái", readonly=True)
