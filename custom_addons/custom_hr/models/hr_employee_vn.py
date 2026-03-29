# Các trường mở rộng theo quy định pháp luật lao động Việt Nam
from odoo import api, fields, models


class HrEmployeeVN(models.Model):
    _inherit = "hr.employee"

    # ── CMND / CCCD ─────────────────────────────────────────────────────────
    id_issue_date = fields.Date(
        string="Ngày cấp CMND/CCCD",
        groups="hr.group_hr_user",
        tracking=True,
    )
    id_issue_place = fields.Char(
        string="Nơi cấp CMND/CCCD",
        groups="hr.group_hr_user",
        tracking=True,
    )

    # ── Dân tộc / Tôn giáo ──────────────────────────────────────────────────
    ethnicity = fields.Selection(
        [
            ("kinh", "Kinh"),
            ("tay", "Tày"),
            ("thai", "Thái"),
            ("muong", "Mường"),
            ("khmer", "Khmer"),
            ("hoa", "Hoa"),
            ("nung", "Nùng"),
            ("hmong", "Hmông"),
            ("dao", "Dao"),
            ("gia_rai", "Gia Rai"),
            ("other", "Khác"),
        ],
        string="Dân tộc",
        groups="hr.group_hr_user",
        tracking=True,
    )
    religion = fields.Selection(
        [
            ("none", "Không"),
            ("buddhism", "Phật giáo"),
            ("catholicism", "Công giáo"),
            ("protestantism", "Tin lành"),
            ("caodaism", "Cao Đài"),
            ("hoahao", "Hòa Hảo"),
            ("islam", "Hồi giáo"),
            ("other", "Khác"),
        ],
        string="Tôn giáo",
        default="none",
        groups="hr.group_hr_user",
        tracking=True,
    )

    # ── Địa chỉ thường trú ───────────────────────────────────────────────────
    permanent_address = fields.Char(
        string="Địa chỉ thường trú",
        groups="hr.group_hr_user",
        tracking=True,
    )
    permanent_ward = fields.Char(
        string="Phường/Xã",
        groups="hr.group_hr_user",
    )
    permanent_district = fields.Char(
        string="Quận/Huyện",
        groups="hr.group_hr_user",
    )
    permanent_province = fields.Char(
        string="Tỉnh/Thành phố",
        groups="hr.group_hr_user",
    )

    # ── Địa chỉ tạm trú ─────────────────────────────────────────────────────
    temporary_address = fields.Char(
        string="Địa chỉ tạm trú",
        groups="hr.group_hr_user",
    )
    temporary_ward = fields.Char(
        string="Phường/Xã (tạm trú)",
        groups="hr.group_hr_user",
    )
    temporary_district = fields.Char(
        string="Quận/Huyện (tạm trú)",
        groups="hr.group_hr_user",
    )
    temporary_province = fields.Char(
        string="Tỉnh/Thành phố (tạm trú)",
        groups="hr.group_hr_user",
    )
    same_as_permanent = fields.Boolean(
        string="Tạm trú giống thường trú",
        default=False,
        groups="hr.group_hr_user",
    )

    @api.onchange("same_as_permanent")
    def _onchange_same_as_permanent(self):
        if self.same_as_permanent:
            self.temporary_address = self.permanent_address
            self.temporary_ward = self.permanent_ward
            self.temporary_district = self.permanent_district
            self.temporary_province = self.permanent_province

    # ── BHXH ─────────────────────────────────────────────────────────────────
    social_insurance_number = fields.Char(
        string="Số sổ BHXH",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    social_insurance_start_date = fields.Date(
        string="Ngày tham gia BHXH",
        groups="hr.group_hr_user",
        tracking=True,
    )
    social_insurance_place = fields.Char(
        string="Nơi tham gia BHXH",
        groups="hr.group_hr_user",
    )

    # ── BHYT ─────────────────────────────────────────────────────────────────
    health_insurance_number = fields.Char(
        string="Mã số BHYT",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
    )
    health_insurance_hospital = fields.Char(
        string="Nơi đăng ký KCB ban đầu",
        groups="hr.group_hr_user",
    )
    health_insurance_expiry = fields.Date(
        string="Ngày hết hạn thẻ BHYT",
        groups="hr.group_hr_user",
    )

    # ── Thuế TNCN ────────────────────────────────────────────────────────────
    tax_code = fields.Char(
        string="Mã số thuế cá nhân",
        groups="hr.group_hr_user",
        tracking=True,
        copy=False,
        index=True,
    )
    tax_registration_place = fields.Char(
        string="Nơi đăng ký nộp thuế",
        groups="hr.group_hr_user",
    )
    dependent_count = fields.Integer(
        string="Số người phụ thuộc",
        default=0,
        groups="hr.group_hr_user",
        tracking=True,
    )
    dependent_ids = fields.One2many(
        "custom_hr.tax.dependent",
        "employee_id",
        string="Danh sách người phụ thuộc",
        groups="hr.group_hr_user",
    )

    @api.onchange("dependent_ids")
    def _onchange_dependent_ids(self):
        self.dependent_count = len(self.dependent_ids)

    # ── SQL constraints ───────────────────────────────────────────────────────
    _social_insurance_number_uniq = models.Constraint(
        "unique(social_insurance_number)",
        "Số sổ BHXH phải là duy nhất trong hệ thống.",
    )
    _tax_code_uniq = models.Constraint(
        "unique(tax_code)",
        "Mã số thuế cá nhân phải là duy nhất trong hệ thống.",
    )


class CustomHrTaxDependent(models.Model):
    _name = "custom_hr.tax.dependent"
    _description = "Người phụ thuộc giảm trừ thuế TNCN"
    _order = "employee_id, name"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Nhân viên",
        required=True,
        ondelete="cascade",
        index=True,
    )
    name = fields.Char(string="Họ và tên", required=True)
    relationship = fields.Selection(
        [
            ("child", "Con"),
            ("parent", "Bố/Mẹ"),
            ("spouse", "Vợ/Chồng"),
            ("sibling", "Anh/Chị/Em"),
            ("other", "Khác"),
        ],
        string="Quan hệ",
        required=True,
        default="child",
    )
    birth_date = fields.Date(string="Ngày sinh")
    id_number = fields.Char(string="CMND/CCCD/Giấy khai sinh")
    tax_dependent_code = fields.Char(
        string="Mã số người phụ thuộc (MST)",
        copy=False,
    )
    start_date = fields.Date(string="Từ tháng", required=True)
    end_date = fields.Date(string="Đến tháng")
    note = fields.Char(string="Ghi chú")
