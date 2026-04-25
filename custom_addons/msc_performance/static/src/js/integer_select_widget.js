/** @odoo-module **/

import { registry } from "@web/core/registry";
import { IntegerField, integerField } from "@web/views/fields/integer/integer_field";
import { xml } from "@odoo/owl";

class IntegerSelectField extends IntegerField {
    static template = xml`
        <t t-if="props.readonly">
            <span class="o_field_integer o_readonly"><t t-esc="formattedValue"/></span>
        </t>
        <t t-else="">
            <select class="o_input msc_integer_select" t-on-change="onSelectChange">
                <t t-foreach="selectOptions" t-as="opt" t-key="opt">
                    <option t-att-value="opt"
                            t-att-selected="opt === currentIntValue ? 'selected' : undefined">
                        <t t-esc="opt"/>
                    </option>
                </t>
            </select>
        </t>
    `;

    get currentIntValue() {
        return this.props.record.data[this.props.name] ?? 0;
    }

    get formattedValue() {
        return String(this.currentIntValue);
    }

    get selectOptions() {
        const rec = this.props.record;
        let max = 4;
        if (rec && rec.data && rec.data.score_max_per_criterion > 0) {
            max = rec.data.score_max_per_criterion;
        }
        const opts = [];
        for (let i = 0; i <= max; i++) {
            opts.push(i);
        }
        return opts;
    }

    onSelectChange(ev) {
        const val = parseInt(ev.target.value, 10);
        this.props.record.update({ [this.props.name]: val });
    }
}

registry.category("fields").add("integer_select", {
    ...integerField,
    component: IntegerSelectField,
});
