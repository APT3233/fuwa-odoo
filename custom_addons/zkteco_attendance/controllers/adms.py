"""
ADMS (Attendance Data Management System) Controller for ZKTeco devices.

ZKTeco ADMS protocol flow:
  1. Device sends GET /iclock/cdata?SN=<serial>&options=...
     → Server replies with device config (attendance interval, etc.)
  2. Device periodically sends POST /iclock/cdata?SN=<serial>&table=ATTLOG&...
     with body containing attendance records
  3. Device sends GET /iclock/getrequest?SN=<serial>
     → Server can push commands back to device (optional)
"""
import logging
from datetime import datetime, timedelta

import pytz

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

# ZKTeco ADMS standard responses
OK = 'OK'
KEEP_ALIVE = 'OK'


class ZktecoADMSController(http.Controller):

    # -------------------------------------------------------------------------
    # Initial handshake – device announces itself
    # -------------------------------------------------------------------------
    @http.route('/iclock/cdata', type='http', auth='none', methods=['GET'], csrf=False)
    def iclock_cdata_get(self, **params):
        """Device GET: initial connection / heartbeat."""
        sn = params.get('SN', '')
        _logger.info('ZKTeco ADMS GET /iclock/cdata SN=%s params=%s', sn, params)

        if not sn:
            return request.make_response('ERROR', headers=[('Content-Type', 'text/plain')])

        device = self._get_or_create_device(sn)
        device.sudo().write({
            'state': 'connected',
            'last_activity': datetime.utcnow(),
        })

        # Reply with server config pushed to device
        # ATTLOGStamp / OPERLOGStamp: last sync timestamps (0 = send all)
        response_lines = [
            'GET OPTION FROM: %s' % sn,
            'ATTLOGStamp=0',
            'OPERLOGStamp=9999',
            'ATTPHOTOStamp=None',
            'ErrorDelay=30',
            'Delay=10',
            'TransTimes=00:00;14:05',
            'TransInterval=1',
            'TransFlag=TransData AttLog OpLog AttPhoto EnrollUser ChgUser EnrollFP ChgFP FACE',
            'TimeZone=7',
            'Realtime=1',
            'Encrypt=None',
        ]
        body = '\n'.join(response_lines)
        return request.make_response(body, headers=[('Content-Type', 'text/plain')])

    # -------------------------------------------------------------------------
    # Data upload – device POSTs attendance records
    # -------------------------------------------------------------------------
    @http.route('/iclock/cdata', type='http', auth='none', methods=['POST'], csrf=False)
    def iclock_cdata_post(self, **params):
        """Device POST: upload attendance logs (ATTLOG) or other tables."""
        sn = params.get('SN', '')
        table = params.get('table', '')
        _logger.info('ZKTeco ADMS POST /iclock/cdata SN=%s table=%s', sn, table)

        if not sn:
            return request.make_response('ERROR', headers=[('Content-Type', 'text/plain')])

        device = self._get_or_create_device(sn)
        device.sudo().write({
            'state': 'connected',
            'last_activity': datetime.utcnow(),
        })

        raw_body = request.httprequest.get_data(as_text=True)
        _logger.debug('ZKTeco body: %s', raw_body)

        if table == 'ATTLOG':
            self._process_attlog(device, raw_body)
        elif table == 'OPERLOG':
            _logger.debug('ZKTeco OPERLOG (ignored): %s', raw_body[:200])
        else:
            _logger.debug('ZKTeco unknown table=%s body=%s', table, raw_body[:200])

        return request.make_response(OK, headers=[('Content-Type', 'text/plain')])

    # -------------------------------------------------------------------------
    # Command polling – device asks for pending commands
    # -------------------------------------------------------------------------
    @http.route('/iclock/getrequest', type='http', auth='none', methods=['GET'], csrf=False)
    def iclock_getrequest(self, **params):
        """Device polls for pending server commands. Return C:id:CMD format."""
        sn = params.get('SN', '')
        device = request.env['zkteco.device'].sudo().search([('serial_number', '=', sn)], limit=1)
        if device:
            device.write({
                'state': 'connected',
                'last_activity': datetime.utcnow(),
            })
        return request.make_response('OK', headers=[('Content-Type', 'text/plain')])

    # -------------------------------------------------------------------------
    # Device push acknowledgement
    # -------------------------------------------------------------------------
    @http.route('/iclock/devicecmd', type='http', auth='none', methods=['POST'], csrf=False)
    def iclock_devicecmd(self, **params):
        """Device acknowledges command execution."""
        return request.make_response('OK', headers=[('Content-Type', 'text/plain')])

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------
    def _get_or_create_device(self, serial_number):
        env = request.env['zkteco.device'].sudo()
        device = env.search([('serial_number', '=', serial_number)], limit=1)
        if not device:
            device = env.create({
                'name': 'ZKTeco %s' % serial_number,
                'serial_number': serial_number,
                'state': 'connected',
            })
            _logger.info('ZKTeco: auto-created device SN=%s id=%s', serial_number, device.id)
        return device

    def _process_attlog(self, device, body):
        """
        Parse ATTLOG body and create zkteco.attendance.log records.

        ATTLOG format (one record per line):
          PIN\tDate Time\tStatus\tVerify\tWorkCode\tReserved
          e.g.: 1\t2024-01-15 08:30:00\t0\t1\t0\t0
        """
        env = request.env
        log_model = env['zkteco.attendance.log'].sudo()
        lines = [l.strip() for l in body.strip().splitlines() if l.strip()]
        created = 0

        for line in lines:
            parts = line.split('\t')
            if len(parts) < 2:
                continue
            try:
                pin = parts[0].strip()
                time_str = parts[1].strip()
                punch_type = parts[2].strip() if len(parts) > 2 else '0'

                # Parse datetime – ZKTeco sends local time (Vietnam UTC+7)
                punch_time_local = datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S')
                # Convert Vietnam local → UTC for storage
                vn_tz = pytz.timezone('Asia/Ho_Chi_Minh')
                punch_time_utc = vn_tz.localize(punch_time_local).astimezone(pytz.utc).replace(tzinfo=None)

                # Skip duplicate
                existing = log_model.search([
                    ('device_id', '=', device.id),
                    ('pin', '=', pin),
                    ('punch_time', '=', punch_time_utc),
                ], limit=1)
                if existing:
                    continue

                log = log_model.create({
                    'device_id': device.id,
                    'pin': pin,
                    'punch_time': punch_time_utc,
                    'punch_type': punch_type if punch_type in ('0', '1', '4', '5') else '0',
                    'raw_data': line,
                    'state': 'new',
                })
                created += 1
            except Exception as e:
                _logger.warning('ZKTeco: failed to parse line %r: %s', line, e)

        _logger.info('ZKTeco: device=%s created %d new log(s) from %d line(s)',
                     device.serial_number, created, len(lines))

        if created:
            # Auto-process newly created logs
            new_logs = log_model.search([
                ('device_id', '=', device.id),
                ('state', '=', 'new'),
            ])
            new_logs._process_attendance()
