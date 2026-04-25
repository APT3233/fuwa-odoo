{
    "name": "Custom Project",
    "version": "19.0.1.0.0",
    "summary": "Custom project access control and task automation",
    "author": "Custom",
    "category": "Project",
    "license": "LGPL-3",
    "depends": ["project", "hr", "hr_timesheet"],
    "data": [
        "security/ir.model.access.csv",
        "security/project_groups.xml",
        "views/project_task_manager_board.xml",
        "views/project_menu.xml",
        "views/project_menu_restrict.xml",
        "views/project_task_list_columns.xml",
        "views/project_task_archive.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "custom_project/static/src/js/task_control_panel_patch.js",
            "custom_project/static/src/js/task_form_patch.js",
            "custom_project/static/src/js/task_kanban_patch.js",
        ],
    },
    "installable": True,
    "application": False,
}
