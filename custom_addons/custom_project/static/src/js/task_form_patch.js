import { ProjectTaskFormController } from "@project/views/project_task_form/project_task_form_controller";
import { patch } from "@web/core/utils/patch";

patch(ProjectTaskFormController.prototype, {
    async onRecordSaved(record, changes) {
        const result = await super.onRecordSaved(...arguments);
        // Reload the current view model so cascaded changes (parent stage moves,
        // sub-task state updates) appear immediately without F5.
        if (changes && ("state" in changes || "stage_id" in changes)) {
            await this.model.load();
        }
        return result;
    },
});
