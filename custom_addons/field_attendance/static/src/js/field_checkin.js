/** @odoo-module **/
/*
 * Mobile OWL component cho chấm công công tác ngoài.
 *
 * Flow:
 *   1. Load state từ /field_attendance/state (employee, open attendance)
 *   2. Request camera + geolocation permissions
 *   3. Hiển thị live camera preview + nút "Chụp"
 *   4. User chụp → capture vào <canvas> → base64
 *   5. Submit qua /field_attendance/checkin hoặc /checkout
 *   6. Hiển thị kết quả + Google Maps embed
 */
import { Component, onMounted, onWillUnmount, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { rpc } from "@web/core/network/rpc";
import { _t } from "@web/core/l10n/translation";
import { useService } from "@web/core/utils/hooks";

export class FieldCheckInAction extends Component {
    static template = "field_attendance.FieldCheckIn";
    static props = ["*"];

    setup() {
        this.videoRef = useRef("video");
        this.canvasRef = useRef("canvas");

        this.state = useState({
            loading: true,
            error: "",
            stage: "init", // init | camera | preview | submitting | done | register_location
            employee: null,
            openAttendance: null,
            googleMapsApiKey: "",
            requireSelfieCheckout: false,

            // GPS
            latitude: null,
            longitude: null,
            accuracy: null,
            gpsError: "",

            // Selfie
            selfieDataUrl: "",

            // Note
            note: "",

            // Result
            result: null, // {success, message, is_valid, distance, location_name, ...}

            // Register location form
            regName: "",
            regType: "customer",
            regAddress: "",
            regPartnerId: null,
            regPartnerName: "",
            regPartnerResults: [],
            regSubmitting: false,
            regError: "",
            regDone: false,
        });

        this._stream = null;
        this.actionService = useService("action");

        onMounted(async () => {
            await this._loadState();
            await this._initGeolocation();
            await this._initCamera();
        });

        onWillUnmount(() => {
            this._stopCamera();
        });
    }

    // -------------------------------------------------------------------
    // State loading
    // -------------------------------------------------------------------
    async _loadState() {
        try {
            const res = await rpc("/field_attendance/state", {});
            if (res.error) {
                this.state.error = res.error;
                this.state.loading = false;
                return;
            }
            this.state.employee = res.employee;
            this.state.openAttendance = res.open_attendance || null;
            this.state.googleMapsApiKey = res.google_maps_api_key || "";
            this.state.requireSelfieCheckout = res.require_selfie_checkout;
            this.state.loading = false;
        } catch (err) {
            this.state.error = _t("Không thể tải dữ liệu: ") + (err.message || err);
            this.state.loading = false;
        }
    }

    // -------------------------------------------------------------------
    // Geolocation
    // -------------------------------------------------------------------
    async _initGeolocation() {
        if (!navigator.geolocation) {
            this.state.gpsError = _t("Trình duyệt không hỗ trợ GPS");
            return;
        }
        return new Promise((resolve) => {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    this.state.latitude = pos.coords.latitude;
                    this.state.longitude = pos.coords.longitude;
                    this.state.accuracy = Math.round(pos.coords.accuracy);
                    resolve();
                },
                (err) => {
                    this.state.gpsError = _t("Lỗi GPS: ") + err.message;
                    resolve();
                },
                { enableHighAccuracy: true, timeout: 15000, maximumAge: 0 }
            );
        });
    }

    async refreshGps() {
        this.state.gpsError = "";
        await this._initGeolocation();
    }

    // -------------------------------------------------------------------
    // Camera
    // -------------------------------------------------------------------
    async _initCamera() {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            this.state.error = _t("Trình duyệt không hỗ trợ camera");
            return;
        }
        try {
            this._stream = await navigator.mediaDevices.getUserMedia({
                video: { facingMode: "user", width: { ideal: 720 }, height: { ideal: 720 } },
                audio: false,
            });
            // wait for the video element to be mounted
            setTimeout(() => {
                if (this.videoRef.el && this._stream) {
                    this.videoRef.el.srcObject = this._stream;
                    this.videoRef.el.play().catch(() => {});
                }
            }, 100);
            this.state.stage = "camera";
        } catch (err) {
            this.state.error = _t("Không truy cập được camera: ") + (err.message || err);
        }
    }

    _stopCamera() {
        if (this._stream) {
            this._stream.getTracks().forEach((t) => t.stop());
            this._stream = null;
        }
    }

    captureSelfie() {
        const video = this.videoRef.el;
        const canvas = this.canvasRef.el;
        if (!video || !canvas) {
            return;
        }
        const w = video.videoWidth || 640;
        const h = video.videoHeight || 480;
        canvas.width = w;
        canvas.height = h;
        const ctx = canvas.getContext("2d");
        // mirror the selfie horizontally so it matches the preview
        ctx.save();
        ctx.scale(-1, 1);
        ctx.drawImage(video, -w, 0, w, h);
        ctx.restore();
        this.state.selfieDataUrl = canvas.toDataURL("image/jpeg", 0.85);
        this.state.stage = "preview";
    }

    retake() {
        this.state.selfieDataUrl = "";
        this.state.stage = "camera";
        // Re-assign stream to the video element after OWL re-renders it
        setTimeout(() => {
            if (this.videoRef.el && this._stream) {
                this.videoRef.el.srcObject = this._stream;
                this.videoRef.el.play().catch(() => {});
            }
        }, 100);
    }

    // -------------------------------------------------------------------
    // Submit
    // -------------------------------------------------------------------
    async submitCheckIn() {
        if (!this.state.latitude || !this.state.longitude) {
            this.state.error = _t("Chưa có tọa độ GPS. Bấm 'Lấy lại GPS'");
            return;
        }
        if (!this.state.selfieDataUrl) {
            this.state.error = _t("Chưa có ảnh selfie");
            return;
        }
        this.state.error = "";
        this.state.stage = "submitting";
        try {
            const res = await rpc("/field_attendance/checkin", {
                latitude: this.state.latitude,
                longitude: this.state.longitude,
                selfie: this.state.selfieDataUrl,
                note: this.state.note,
            });
            this._handleResult(res);
        } catch (err) {
            this.state.error = _t("Lỗi gửi dữ liệu: ") + (err.message || err);
            this.state.stage = "preview";
        }
    }

    async submitCheckOut() {
        if (!this.state.latitude || !this.state.longitude) {
            this.state.error = _t("Chưa có tọa độ GPS");
            return;
        }
        if (this.state.requireSelfieCheckout && !this.state.selfieDataUrl) {
            this.state.error = _t("Bắt buộc chụp ảnh selfie khi check-out");
            return;
        }
        this.state.error = "";
        this.state.stage = "submitting";
        try {
            const res = await rpc("/field_attendance/checkout", {
                latitude: this.state.latitude,
                longitude: this.state.longitude,
                selfie: this.state.selfieDataUrl || null,
                note: this.state.note,
            });
            this._handleResult(res);
        } catch (err) {
            this.state.error = _t("Lỗi gửi dữ liệu: ") + (err.message || err);
            this.state.stage = "preview";
        }
    }

    _handleResult(res) {
        this.state.result = res;
        if (res.success) {
            this._stopCamera();
            this.state.stage = "done";
        } else {
            this.state.error = res.error || _t("Thất bại");
            this.state.stage = "preview";
        }
    }

    goHome() {
        this._stopCamera();
        this.actionService.doAction('hr_attendance.hr_attendance_action');
    }

    cancel() {
        this._stopCamera();
        this.actionService.doAction('hr_attendance.hr_attendance_action');
    }

    // -------------------------------------------------------------------
    // Register new location
    // -------------------------------------------------------------------
    startRegisterLocation() {
        this.state.regName = "";
        this.state.regType = "customer";
        this.state.regAddress = "";
        this.state.regPartnerId = null;
        this.state.regPartnerName = "";
        this.state.regPartnerResults = [];
        this.state.regSubmitting = false;
        this.state.regError = "";
        this.state.regDone = false;
        this.state.stage = "register_location";
    }

    cancelRegisterLocation() {
        this.state.stage = "done";
    }

    async onPartnerInput(ev) {
        const val = ev.target.value;
        this.state.regPartnerName = val;
        this.state.regPartnerId = null;
        if (val.length < 2) {
            this.state.regPartnerResults = [];
            return;
        }
        try {
            const results = await rpc("/field_attendance/search_partners", { name: val });
            this.state.regPartnerResults = results;
        } catch {
            this.state.regPartnerResults = [];
        }
    }

    selectPartner(partner) {
        this.state.regPartnerId = partner.id;
        this.state.regPartnerName = partner.name;
        this.state.regPartnerResults = [];
    }

    async submitRegisterLocation() {
        this.state.regError = "";
        if (!this.state.regName.trim()) {
            this.state.regError = _t("Vui lòng nhập tên địa điểm");
            return;
        }
        if (!this.state.result || !this.state.result.attendance_id) {
            this.state.regError = _t("Không tìm thấy bản ghi chấm công");
            return;
        }

        this.state.regSubmitting = true;
        try {
            const res = await rpc("/field_attendance/register_location", {
                attendance_id: this.state.result.attendance_id,
                name: this.state.regName.trim(),
                location_type: this.state.regType,
                address: this.state.regAddress.trim(),
                partner_id: this.state.regPartnerId,
            });
            if (res.success) {
                this.state.regDone = true;
                // Update result so done stage reflects new location
                this.state.result = {
                    ...this.state.result,
                    is_valid: true,
                    location_name: res.location_name,
                    message: _t("Check-in thành công tại ") + res.location_name,
                };
            } else {
                this.state.regError = res.error || _t("Đăng ký thất bại");
            }
        } catch (err) {
            this.state.regError = _t("Lỗi: ") + (err.message || err);
        } finally {
            this.state.regSubmitting = false;
        }
    }

    // -------------------------------------------------------------------
    // Getters
    // -------------------------------------------------------------------
    get mapEmbedUrl() {
        if (!this.state.latitude || !this.state.longitude) {
            return "";
        }
        const key = this.state.googleMapsApiKey;
        if (key) {
            return `https://www.google.com/maps/embed/v1/place?key=${key}&q=${this.state.latitude},${this.state.longitude}&zoom=17`;
        }
        return `https://maps.google.com/maps?q=${this.state.latitude},${this.state.longitude}&z=17&output=embed`;
    }

    get isCheckedIn() {
        return !!this.state.openAttendance;
    }
}

registry.category("actions").add("field_attendance.checkin", FieldCheckInAction);
