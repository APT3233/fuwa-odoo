import { browser } from "@web/core/browser/browser";
import { ProjectTaskControlPanel } from "@project/views/project_task_control_panel/project_task_control_panel";
import { patch } from "@web/core/utils/patch";

patch(ProjectTaskControlPanel.prototype, {
    setup() {
        super.setup();
        // Default showSubtasks to true if not explicitly set by user
        const stored = browser.localStorage.getItem(this.showSubtasksKey);
        if (stored === null) {
            this.state.showSubtasks = true;
            browser.localStorage.setItem(this.showSubtasksKey, "true");
        }
    },
});
