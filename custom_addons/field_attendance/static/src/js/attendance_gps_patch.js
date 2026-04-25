/** @odoo-module **/
/**
 * Patch systray attendance button:
 * 1. Luôn lấy GPS trước khi check-in/out
 * 2. Hiện thông báo thành công sau mỗi lần check-in/out
 */
import { ActivityMenu } from "@hr_attendance/components/attendance_menu/attendance_menu";
import { rpc } from "@web/core/network/rpc";
import { patch } from "@web/core/utils/patch";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

patch(ActivityMenu.prototype, {
    setup() {
        super.setup();
        this.notification = useService("notification");
    },

    _showAttendanceNotification(wasCheckedIn) {
        const now = new Date().toLocaleTimeString("vi-VN", { hour: "2-digit", minute: "2-digit" });
        if (wasCheckedIn) {
            this.notification.add(
                _t("Check-out thành công lúc %(time)s", { time: now }),
                { type: "success", sticky: false }
            );
        } else {
            this.notification.add(
                _t("Check-in thành công lúc %(time)s", { time: now }),
                { type: "success", sticky: false }
            );
        }
    },

    async signInOut() {
        this.dropdown.close();
        const wasCheckedIn = this.state.checkedIn;

        const doCheckInOut = async (latitude, longitude) => {
            const params = latitude && longitude ? { latitude, longitude } : {};
            this.employee = await rpc("/hr_attendance/systray_check_in_out", params);
            this._searchReadEmployeeFill();
            this._showAttendanceNotification(wasCheckedIn);
        };

        if (navigator.geolocation) {
            return new Promise((resolve) => {
                // maximumAge: 60s — dùng cache GPS nếu có, tránh chờ lâu
                // timeout: 15s — tăng lên để máy tính/điện thoại chậm vẫn kịp
                navigator.geolocation.getCurrentPosition(
                    async ({ coords: { latitude, longitude } }) => {
                        await doCheckInOut(latitude, longitude);
                        resolve();
                    },
                    async () => {
                        // GPS timeout/denied — thử lại với độ chính xác thấp hơn
                        navigator.geolocation.getCurrentPosition(
                            async ({ coords: { latitude, longitude } }) => {
                                await doCheckInOut(latitude, longitude);
                                resolve();
                            },
                            async () => {
                                await doCheckInOut(null, null);
                                resolve();
                            },
                            { enableHighAccuracy: false, timeout: 8000, maximumAge: 300000 }
                        );
                    },
                    { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 }
                );
            });
        } else {
            await doCheckInOut(null, null);
        }
    },
});
