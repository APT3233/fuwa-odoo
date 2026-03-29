/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";

function cloneOrgChart() {
    const source = document.querySelector("#o_employee_org_chart");
    const target = document.querySelector("#custom_hr_org_chart_overview");
    if (!source || !target) {
        return false;
    }

    const sync = () => {
        target.innerHTML = source.innerHTML;
    };

    sync();

    const observer = new MutationObserver(sync);
    observer.observe(source, { childList: true, subtree: true, attributes: true });
    return true;
}

patch(FormRenderer.prototype, {
    mounted() {
        this._super(...arguments);
        let attempts = 0;
        const tryInit = () => {
            attempts += 1;
            if (cloneOrgChart() || attempts >= 10) {
                return;
            }
            setTimeout(tryInit, 300);
        };
        tryInit();
    },
});
