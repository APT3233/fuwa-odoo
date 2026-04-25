"""
ZKTeco Push+ Protocol Controller.

SenseFace 4N and newer ZKTeco devices with "Push chấm công" / "Giao thức: Push+"
send attendance data via HTTP POST to /push/* endpoints (JSON format).

Push+ flow:
  1. Device POST /push/att   → sends attendance batch (JSON)
  2. Device POST /push/device → sends device info
  3. Server responds { "ret": "ok" } for all

Request format (attendance):
  Headers:
    Content-Type: application/json
    SN: <device_serial>
  Body (JSON array or object with "records"):
    { "sn": "PYAB252900147",
      "table": "att",
      "records": [
        { "pin": "1", "time": "2024-01-15 08:30:00", "status": 0, "verify": 1 },
        ...
      ]
    }

Alternative single-record format:
  { "sn": "...", "pin": "1", "time": "2024-01-15 08:30:00", "status": 0 }
"""
import json
import logging
from datetime import datetime

import pytz

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

OK_RESPONSE = json.dumps({'ret': 'ok', 'result': True})


class ZktecoPushController(http.Controller):

    # -------------------------------------------------------------------------
    # Attendance push endpoint
    # -------------------------------------------------------------------------
    @http.route(['/push/att', '/push/attendance'], type='http', auth='none',
                methods=['POST'], csrf=False)
    def push_att(self, **params):
        """Device POSTs attendance records in JSON format."""
        sn = self._get_sn(params)
        _logger.info('ZKTeco Push+ POST /push/att SN=%s', sn)

        try:
            raw = request.httprequest.get_data(as_text=True)
            _logger.debug('ZKTeco Push body: %s', raw[:500])
            data = json.loads(raw) if raw else {}
        except Exception as e:
            _logger.warning('ZKTeco Push: JSON parse error: %s', e)
            return self._ok()

        if not sn:
            sn = data.get('sn') or data.get('SN') or ''

        device = self._get_or_create_device(sn)
        device.sudo().write({
            'state': 'connected',
            'last_activity': datetime.utcnow(),
        })

        # Handle both array-of-records and nested {"records": [...]} formats
        records = data.get('records') or data.get('Attendance') or []
        if not records and isinstance(data, list):
            records = data
        if not records:
            # Single-record format: the payload IS the record
            if data.get('pin') or data.get('PIN'):
                records = [data]

        if records:
            self._process_push_records(device, records)
        else:
            _logger.debug('ZKTeco Push: no attendance records in payload')

        return self._ok()

    # -------------------------------------------------------------------------
    # Device info / heartbeat endpoint
    # -------------------------------------------------------------------------
    @http.route(['/push/device', '/push/conf', '/push/options'],
                type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def push_device(self, **params):
        """Device sends its info or requests server config."""
        sn = self._get_sn(params)
        _logger.info('ZKTeco Push+ device/conf SN=%s', sn)

        try:
            raw = request.httprequest.get_data(as_text=True)
            data = json.loads(raw) if raw else {}
            if not sn:
                sn = data.get('sn') or data.get('SN') or ''
        except Exception:
            pass

        if sn:
            device = self._get_or_create_device(sn)
            device.sudo().write({
                'state': 'connected',
                'last_activity': datetime.utcnow(),
            })

        return self._ok()

    # -------------------------------------------------------------------------
    # Catch-all for other Push endpoints the device might call
    # -------------------------------------------------------------------------
    @http.route(['/push/log', '/push/attphoto', '/push/enrolluser',
                 '/push/operlog', '/push/senduser'],
                type='http', auth='none', methods=['GET', 'POST'], csrf=False)
    def push_misc(self, **params):
        """Handle other Push+ endpoints gracefully."""
        sn = self._get_sn(params)
        _logger.debug('ZKTeco Push+ misc endpoint=%s SN=%s',
                      request.httprequest.path, sn)
        return self._ok()

    # -------------------------------------------------------------------------
    # Helpers
    # -------------------------------------------------------------------------
    def _get_sn(self, params):
        sn = params.get('SN') or params.get('sn') or ''
        if not sn:
            sn = request.httprequest.headers.get('SN', '')
        return sn.strip()

    def _ok(self):
        return request.make_response(
            OK_RESPONSE,
            headers=[('Content-Type', 'application/json')]
        )

    def _get_or_create_device(self, serial_number):
        if not serial_number:
            serial_number = 'UNKNOWN'
        env = request.env['zkteco.device'].sudo()
        device = env.search([('serial_number', '=', serial_number)], limit=1)
        if not device:
            device = env.create({
                'name': 'ZKTeco %s' % serial_number,
                'serial_number': serial_number,
                'state': 'connected',
            })
            _logger.info('ZKTeco Push: auto-created device SN=%s id=%s',
                         serial_number, device.id)
        return device

    def _process_push_records(self, device, records):
        """
        Parse Push+ attendance records and create zkteco.attendance.log entries.

        Push+ JSON record fields:
          pin / PIN       — employee badge ID
          time / Time     — "YYYY-MM-DD HH:MM:SS"
          status / Status — 0=check-in, 1=check-out (same as ADMS punch_type)
          verify          — verification method (ignored)
        """
        log_model = request.env['zkteco.attendance.log'].sudo()
        vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
        created = 0

        for rec in records:
            try:
                pin = str(rec.get('pin') or rec.get('PIN') or '').strip()
                time_str = str(rec.get('time') or rec.get('Time') or
                               rec.get('punch_time') or '').strip()
                status = str(rec.get('status') or rec.get('Status') or
                             rec.get('type') or '0').strip()

                if not pin or not time_str:
                    continue

                # Parse datetime — device sends local Vietnam time
                punch_time_local = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                punch_time_utc = (vn_tz.localize(punch_time_local)
                                  .astimezone(pytz.utc)
                                  .replace(tzinfo=None))

                # Map status to punch_type
                punch_type = status if status in ('0', '1', '4', '5') else '0'

                # Skip duplicate
                existing = log_model.search([
                    ('device_id', '=', device.id),
                    ('pin', '=', pin),
                    ('punch_time', '=', punch_time_utc),
                ], limit=1)
                if existing:
                    continue

                log_model.create({
                    'device_id': device.id,
                    'pin': pin,
                    'punch_time': punch_time_utc,
                    'punch_type': punch_type,
                    'raw_data': json.dumps(rec),
                    'state': 'new',
                })
                created += 1

            except Exception as e:
                _logger.warning('ZKTeco Push: failed to parse record %r: %s', rec, e)

        _logger.info('ZKTeco Push: device=%s created %d new log(s) from %d record(s)',
                     device.serial_number, created, len(records))

        if created:
            new_logs = log_model.search([
                ('device_id', '=', device.id),
                ('state', '=', 'new'),
            ])
            new_logs._process_attendance()
