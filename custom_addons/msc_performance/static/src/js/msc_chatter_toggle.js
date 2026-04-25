/** @odoo-module **/
import { patch } from "@web/core/utils/patch";
import { FormRenderer } from "@web/views/form/form_renderer";
import { useEffect, useRef } from "@odoo/owl";

patch(FormRenderer.prototype, {
    setup() {
        super.setup(...arguments);
        useEffect(
            () => {
                // Only inject on msc.record forms
                const modelName = this.props.record?.resModel;
                if (modelName !== "msc.record") return;

                const formEl = document.querySelector(".o_form_view");
                if (!formEl || formEl.querySelector(".msc_chatter_toggle")) return;

                // Restore collapsed state from localStorage
                const collapsed = localStorage.getItem("msc_chatter_collapsed") === "1";
                if (collapsed) formEl.classList.add("msc_chatter_collapsed");

                const btn = document.createElement("button");
                btn.className = "msc_chatter_toggle";
                btn.title = "Thu/phóng khung thông báo";
                btn.innerHTML = `<i class="msc_toggle_icon">${collapsed ? "»" : "«"}</i><span>${collapsed ? "Thông báo" : "Thu gọn"}</span>`;

                btn.addEventListener("click", () => {
                    const isCollapsed = formEl.classList.toggle("msc_chatter_collapsed");
                    localStorage.setItem("msc_chatter_collapsed", isCollapsed ? "1" : "0");
                    btn.innerHTML = `<i class="msc_toggle_icon">${isCollapsed ? "»" : "«"}</i><span>${isCollapsed ? "Thông báo" : "Thu gọn"}</span>`;
                });

                document.body.appendChild(btn);

                return () => {
                    btn.remove();
                };
            },
            () => [this.props.record?.resModel, this.props.record?.resId]
        );
    },
});
