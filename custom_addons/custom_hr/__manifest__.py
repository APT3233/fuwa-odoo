{
    "name": "Custom HR",
    "version": "19.0.1.0.0",
    "summary": "Customizations for HR Employee Management",
    "author": "Custom",
    "category": "Human Resources",
    "license": "LGPL-3",
    "depends": [
        "hr",
        "hr_homeworking",
        "resource",
        "hr_employee_service",
        "hr_attendance",
        "hr_employee_document",
        "hr_employee_relative",
        "hr_employee_medical_examination",
        "hr_org_chart",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/hr_employee_rules.xml",
        "security/hr_groups_extend.xml",
        "views/hr_employee_form_inherit.xml",
        "views/hr_homeworking_employee_form_inherit.xml",
        "views/hr_employee_form_header.xml",     # priority 90: header + quick actions
        "views/hr_employee_form_work_tab.xml",   # priority 92+95: overview/work tabs + ordering
        "views/hr_employee_public_form.xml",     # priority 92+98: public form for non-HR users
        "views/hr_menu_restrict.xml",            # restrict menus for non-HR users
        "views/hr_employee_vn_fields.xml",
        "views/hr_employee_insurance_tab.xml",
        "views/hr_employee_tax_tab.xml",
        "views/hr_employee_bank_tab.xml",
        "views/hr_employee_work_history_tab.xml",
        "views/hr_employee_vn_labels.xml",
        "views/hr_employee_vn_labels_deep.xml",
        "views/hr_skills_vn_labels.xml",
        "views/transfer_department_wizard.xml",
        "views/change_manager_wizard.xml",
        "views/terminate_employee_wizard.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "custom_hr/static/src/scss/custom_hr.scss",
            "custom_hr/static/src/xml/hr_skills_templates_vn.xml",
            "custom_hr/static/src/xml/form_status_indicator_vn.xml",
            "custom_hr/static/src/js/org_chart_clone.js",
            "custom_hr/static/src/js/org_chart_avatar_patch.js",
        ],
    },
    "installable": True,
    "application": False,
}
