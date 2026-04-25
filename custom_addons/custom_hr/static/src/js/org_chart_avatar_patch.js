/** @odoo-module **/

/**
 * Patch HrOrgChart để bust cache avatar background-image sau mỗi lần re-render.
 * Khi user upload avatar mới, form saves → OWL patched() → bust cache → browser load ảnh mới.
 */

import { patch } from "@web/core/utils/patch";
import { HrOrgChart } from "@hr_org_chart/fields/hr_org_chart";
import { onPatched } from "@odoo/owl";

patch(HrOrgChart.prototype, {
    setup() {
        super.setup();
        onPatched(() => this._bustOrgChartAvatarCache());
    },

    /**
     * Thêm ?t=timestamp vào background-image URL của các avatar trong org chart.
     * Mỗi lần patched() gọi với timestamp mới → browser bỏ cache cũ, load ảnh mới.
     */
    _bustOrgChartAvatarCache() {
        // Tìm container org chart gần nhất từ root element của component
        const root = this.__owl__?.bdom?.el;
        if (!root) return;

        const container = root.closest("#o_employee_org_chart") || root;
        const ts = Date.now();

        container.querySelectorAll(".o_media_object[style]").forEach((el) => {
            const style = el.getAttribute("style") || "";
            if (!style.includes("background-image")) return;

            // Xóa timestamp cũ (nếu có) rồi thêm mới
            const newStyle = style.replace(
                /(url\(['"])(\/web\/image\/[^?'"]+)(?:\?[^'"]*)?(['"]\))/g,
                (_, open, url, close) => `${open}${url}?t=${ts}${close}`
            );

            if (newStyle !== style) {
                el.setAttribute("style", newStyle);
            }
        });
    },
});
