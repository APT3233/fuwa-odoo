import { ProjectTaskKanbanModel } from "@project/views/project_task_kanban/project_task_kanban_model";
import { patch } from "@web/core/utils/patch";

patch(ProjectTaskKanbanModel.Record.prototype, {
    update(changes, options = {}) {
        const hasStateChange = "state" in changes || "stage_id" in changes;
        const result = super.update(...arguments);
        if (hasStateChange && options.save) {
            result.then?.(() => this.model.load());
        }
        return result;
    },
});
