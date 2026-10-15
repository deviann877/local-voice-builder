import base64
import io
import json
import socket
import tarfile
import tempfile
import unittest
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from unittest.mock import patch

from packs import import_pack, validate_install
from transport import (PackageServer, descriptor, read_varint, response_status,
                       varint, voice_status, lan_address, install, connection)


def status(**values):
    data = b''.join(varint(number * 8) + varint(value) for number, value in values.items())
    return base64.b64encode(varint(len(data)) + data).decode()


def response(current=501, version=1, state=2, target=501):
    data = b''.join(varint(n * 8) + varint(v) for n, v in ((2, current), (3, version), (4, target), (5, state)))
    return {'dps': {'162': base64.b64encode(varint(len(data)) + data).decode()}}


class PackTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)

    def test_tar_audio_only_and_no_scripts_executed(self):
        path = self.folder / 'pack.tar.gz'
        with tarfile.open(path, 'w:gz') as archive:
            for name, data in [('audio/1.ogg', b'synthetic'), ('pack.py', b'raise RuntimeError()')]:
                entry = tarfile.TarInfo(name)
                entry.size = len(data)
                archive.addfile(entry, io.BytesIO(data))
        audio = import_pack(path, self.folder)
        self.assertEqual(set(audio), {'audio/1.ogg'})
        self.assertEqual(next(iter(audio.values())).read_bytes(), b'synthetic')
        self.assertFalse((self.folder / 'pack.py').exists())

    def test_tar_symlink_rejected(self):
        path = self.folder / 'pack.tar'
        with tarfile.open(path, 'w') as archive:
            entry = tarfile.TarInfo('linked')
            entry.type = tarfile.SYMTYPE
            entry.linkname = '../elsewhere'
            archive.addfile(entry)
        with self.assertRaises(ValueError):
            import_pack(path, self.folder)

    def test_zip_traversal_rejected(self):
        path = self.folder / 'pack.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            archive.writestr('../recording.ogg', b'synthetic')
        with self.assertRaises(ValueError):
            import_pack(path, self.folder)

    def test_candidate_requires_same_configuration_and_full_layout(self):
        names = json.loads((Path(__file__).parent / 'events.json').read_text())
        paths = [self.folder / 'stock.zip', self.folder / 'candidate.zip']
        def write(path, version):
            with zipfile.ZipFile(path, 'w') as archive:
                archive.writestr('en_us_male/config.yaml', ('id: 502\nversion: ' + str(version) + '\n').encode())
                for name in names:
                    archive.writestr('en_us_male/main/' + name, b'synthetic')
        for path in paths:
            write(path, 1)
        self.assertEqual(validate_install(*paths, names), (502, 1))
        write(paths[1], 2)
        with self.assertRaises(ValueError):
            validate_install(*paths, names)


class ProtocolTests(unittest.TestCase):
    def test_real_library_guard_blocks_second_write_and_other_commands(self):
        from tinytuya.core import command_types as commands
        with patch('transport.lan_address', return_value='localhost'):
            device = connection('syntheticdevice', 'localhost', 'syntheticfixture')
        self.addCleanup(device.close)
        with self.assertRaises(ValueError):
            device.generate_payload(commands.HEART_BEAT)
        device.mode = 'write'
        device.allowed = 'synthetic-descriptor'
        payload = device.generate_payload(commands.CONTROL, {'162': device.allowed})
        encoded = device._encode_message(payload)
        self.assertTrue(encoded)
        with self.assertRaises(ValueError):
            device._encode_message(payload)
        self.assertEqual(device.writes, 1)

    def test_descriptor_length_and_md5_not_a_signature(self):
        encoded = descriptor(502, 1, 'http://localhost/package.zip', b'synthetic')
        data = base64.b64decode(encoded)
        length, position = read_varint(data, 0)
        self.assertEqual(length, len(data) - position)
        self.assertIn(b'http://localhost/package.zip', data)
        self.assertTrue(data.endswith(b'\x12\x00'))

    def test_truncated_and_wrong_wire_status_rejected(self):
        for data in (b'\x08', b'\x02\x12\x00'):
            with self.assertRaises(ValueError):
                voice_status(base64.b64encode(data).decode())

    def test_busy_and_unrecognized_device_status_rejected(self):
        for data in (response(state=1), response(current=999), {'dps': {}}):
            with self.assertRaises(ValueError):
                response_status(data)

    def test_non_lan_targets_rejected(self):
        for address in ('localhost', 'example.org', str(socket.INADDR_ANY)):
            with self.assertRaises(ValueError):
                lan_address(address)

    def test_server_serves_only_approved_file_then_closes(self):
        peer = socket.gethostbyname('localhost')
        with patch('transport.lan_address', side_effect=lambda value: value):
            with PackageServer('localhost', peer, b'synthetic') as server:
                with urllib.request.urlopen(server.url, timeout=3) as result:
                    self.assertEqual(result.read(), b'synthetic')
                self.assertTrue(server.transferred.is_set())
                with self.assertRaises(urllib.error.HTTPError):
                    urllib.request.urlopen(server.url + '/outside', timeout=3)
            self.assertEqual(server.server.fileno(), -1)

    def test_write_is_not_retried_on_ambiguous_result(self):
        class Device:
            writes = 0
            closed = False
            def status(self):
                return response()
            def set_value(self, *args, **kwargs):
                self.writes += 1
                raise OSError('synthetic transport failure')
            def close(self):
                self.closed = True
        device = Device()
        class Route:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def connect(self, *args): pass
            def getsockname(self): return ('localhost', 0)
        with patch('transport.connection', return_value=device), patch('transport.lan_address', side_effect=lambda x: x), \
                patch('transport.socket.socket', return_value=Route()), patch('transport.PackageServer') as server:
            server.return_value.__enter__.return_value.url = 'http://localhost/package.zip'
            with self.assertRaises(OSError):
                install('synthetic', 'localhost', 'synthetic', b'synthetic', 502, 1, lambda _: None)
        self.assertEqual(device.writes, 1)
        self.assertTrue(device.closed)

    def simulated_success(self, downloaded):
        class Route:
            def __enter__(self): return self
            def __exit__(self, *args): pass
            def connect(self, *args): pass
            def getsockname(self): return ('localhost', 0)
        from unittest.mock import MagicMock
        device = MagicMock()
        device.status.return_value = response()
        device.receive.return_value = response(current=502, target=502)
        with patch('transport.connection', return_value=device), patch('transport.lan_address', side_effect=lambda x: x), \
                patch('transport.socket.socket', return_value=Route()), patch('transport.PackageServer') as server, \
                patch('transport.time.monotonic', side_effect=[0, 2]), patch('transport.time.sleep'):
            listener = server.return_value.__enter__.return_value
            listener.url = 'http://localhost/package.zip'
            listener.deadline = 1
            listener.transferred.is_set.return_value = downloaded
            result = install('synthetic', 'localhost', 'synthetic', b'synthetic', 502, 1, lambda _: None)
        device.set_value.assert_called_once()
        device.close.assert_called_once()
        return result

    def test_success_requires_full_transfer_and_matching_status(self):
        self.assertIn('Transfer completed', self.simulated_success(True))

    def test_cached_selection_does_not_confirm_installation(self):
        self.assertIn('unconfirmed', self.simulated_success(False))


if __name__ == '__main__':
    unittest.main()
