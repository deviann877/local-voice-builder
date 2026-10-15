"""Bounded local voice update; no cloud accounts or saved connection details."""
import base64
import hashlib
import http.server
import ipaddress
import logging
import secrets
import socket
import threading
import time


def varint(value):
    if type(value) is not int or not 0 <= value < 2 ** 32:
        raise ValueError('Invalid protocol integer.')
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    return bytes(result + bytes([value]))


def read_varint(data, position):
    value = 0
    for shift in range(0, 70, 7):
        if position >= len(data):
            raise ValueError('Truncated status.')
        byte = data[position]
        position += 1
        value |= (byte & 127) << shift
        if byte < 128:
            return value, position
    raise ValueError('Invalid status integer.')


def bytes_field(number, value):
    return varint(number * 8 + 2) + varint(len(value)) + value


def descriptor(package_id, version, url, archive):
    digest = hashlib.md5(archive).hexdigest().encode('ascii')
    inner = (varint(8) + varint(package_id) + bytes_field(2, url.encode('ascii')) +
             bytes_field(3, digest) + varint(32) + varint(version) +
             varint(40) + varint(len(archive)))
    outer = bytes_field(1, inner) + bytes_field(2, b'')
    return base64.b64encode(varint(len(outer)) + outer).decode('ascii')


def voice_status(value):
    if not isinstance(value, str) or len(value) > 4096:
        raise ValueError('Voice status unavailable.')
    raw = base64.b64decode(value, validate=True)
    length, pos = read_varint(raw, 0)
    if length != len(raw) - pos:
        raise ValueError('Unsupported voice framing.')
    fields = {}
    while pos < len(raw):
        tag, pos = read_varint(raw, pos)
        number = tag >> 3
        if tag & 7 or number not in range(1, 6) or number in fields:
            raise ValueError('Unsupported voice status.')
        fields[number], pos = read_varint(raw, pos)
    return {'current_id': fields.get(2, 0), 'version': fields.get(3, 0),
            'target_id': fields.get(4, 0), 'state': fields.get(5, 0)}


def lan_address(value):
    address = ipaddress.IPv4Address(value)
    if not (address.is_private and not address.is_loopback and
            not address.is_link_local and not address.is_unspecified and
            not address.is_multicast and not address.is_reserved):
        raise ValueError('Use an ordinary private LAN address.')
    # is_private includes non-LAN ranges on some Python versions.
    if not (address.packed[0] == 10 or address.packed[:2] == bytes([192, 168]) or
            address.packed[0] == 172 and 16 <= address.packed[1] <= 31):
        raise ValueError('Use an ordinary private LAN address.')
    return str(address)


def connection(device_id, address, local_key):
    address = lan_address(address)
    if not isinstance(device_id, str) or not device_id.isascii() or not device_id.isalnum() or not 8 <= len(device_id) <= 64:
        raise ValueError('Check the device ID.')
    if not isinstance(local_key, str) or len(local_key.encode('utf-8')) != 16:
        raise ValueError('The local key must be exactly 16 bytes.')
    logging.disable(logging.CRITICAL)
    import tinytuya
    from tinytuya.core import command_types as commands

    class BoundedDevice(tinytuya.Device):
        def __init__(self):
            self.mode = 'read'
            self.queries = 0
            self.writes = 0
            self.allowed = None
            super().__init__(device_id, address=address, local_key=local_key, version=3.3,
                connection_timeout=2, connection_retry_limit=1, connection_retry_delay=0, persist=True)
            self.dev_type_auto = False
            self.disabledetect = True
            self.set_retry(False)

        def generate_payload(self, command, data=None, *args, **kwargs):
            if args or kwargs:
                raise ValueError('Unexpected transport arguments.')
            if self.mode == 'read' and command == commands.DP_QUERY:
                return super().generate_payload(command, data={'162': None})
            if self.mode == 'write' and command == commands.CONTROL and data == {'162': self.allowed}:
                return super().generate_payload(command, data=data)
            raise ValueError('Operation outside voice update scope.')

        def _encode_message(self, message):
            if self.mode == 'read' and message.cmd == commands.DP_QUERY and not self.queries:
                self.queries += 1
            elif self.mode == 'write' and message.cmd == commands.CONTROL and not self.writes:
                self.writes += 1
            else:
                raise ValueError('Repeated or unexpected command blocked.')
            return super()._encode_message(message)

    return BoundedDevice()


def response_status(response):
    if not isinstance(response, dict) or not isinstance(response.get('dps'), dict):
        raise ValueError('No usable local response; check connection details and network.')
    state = voice_status(response['dps'].get('162'))
    if state['current_id'] not in (501, 502) or state['state'] not in (0, 2, 3):
        raise ValueError('Unsupported or busy voice state. No update sent.')
    return state


def check_connection(device_id, address, local_key):
    device = connection(device_id, address, local_key)
    try:
        return response_status(device.status())
    finally:
        device.close()


class PackageServer:
    """Only one in-memory file, available to one target address for a bounded time."""
    def __init__(self, listen_address, target_address, blob):
        self.path = '/' + secrets.token_hex(16) + '.zip'
        self.transferred = threading.Event()
        self.deadline = time.monotonic() + 180
        owner = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass

            def do_GET(self):
                if self.client_address[0] != target_address or self.path != owner.path or time.monotonic() > owner.deadline:
                    self.send_error(404)
                    return
                self.connection.settimeout(10)
                try:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/zip')
                    self.send_header('Content-Length', str(len(blob)))
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.wfile.write(blob)
                    self.wfile.flush()
                    owner.transferred.set()
                except OSError:
                    pass

        class Server(http.server.ThreadingHTTPServer):
            daemon_threads = True

            def handle_error(self, request, client_address):
                pass

        self.server = Server((lan_address(listen_address), 0), Handler)
        self.url = 'http://' + listen_address + ':' + str(self.server.server_port) + self.path

    def __enter__(self):
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.deadline = 0
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


def install(device_id, address, local_key, blob, package_id, version, notify):
    address = lan_address(address)
    device = connection(device_id, address, local_key)
    try:
        state = response_status(device.status())
        if state['current_id'] == package_id and state['version'] != version:
            raise ValueError('Template version differs from the installed voice. Update the stock template first.')
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as route:
            route.connect((address, 6668))
            listen = lan_address(route.getsockname()[0])
        with PackageServer(listen, address, blob) as server:
            device.allowed = descriptor(package_id, version, server.url, blob)
            device.mode = 'write'
            notify('Sending one voice-update request. Keep the app open and vacuum powered.')
            # Never repeat a write when the response is missing or ambiguous.
            device.set_value('162', device.allowed, nowait=True)
            settled = None
            while time.monotonic() < server.deadline:
                response = device.receive()
                try:
                    voice = voice_status(response.get('dps', {}).get('162'))
                except (ValueError, TypeError, AttributeError):
                    continue
                if voice['state'] == 3 and voice['target_id'] == package_id:
                    raise ValueError('Vacuum reported update failure. Do not retry automatically; use the recovery guide.')
                if voice['state'] == 2 and voice['current_id'] == package_id and voice['version'] == version:
                    settled = voice
                    if server.transferred.is_set():
                        return 'Transfer completed and vacuum reported success. Listen for the changed voice and verify normal operation.'
                time.sleep(0.1)
            if settled:
                return 'Voice selection reported success, but no complete download was observed. Custom installation is unconfirmed.'
            return 'Observation timed out. Outcome is unknown. Do not send another update until the vacuum state is resolved.'
    finally:
        device.close()
