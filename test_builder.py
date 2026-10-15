import tempfile
import unittest
import zipfile
from pathlib import Path
from builder import read_template, build


class ArchiveSafetyTests(unittest.TestCase):
    def archive(self, entries):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / 'template.zip'
        with zipfile.ZipFile(path, 'w') as archive:
            for name, data in entries:
                archive.writestr(name, data)
        return path

    def test_supported_template(self):
        path = self.archive([('voice/config.yaml', b'id: 1\nversion: 1\n'),
                             ('voice/main/A0001.mp3', b'synthetic fixture')])
        files, clips = read_template(path)
        self.assertEqual(clips, ['voice/main/A0001.mp3'])
        self.assertEqual(len(files), 2)

    def test_rejects_traversal_and_unexpected_content(self):
        for name in ('../outside', '/outside', 'voice/main/unknown.mp3', 'voice\\secret'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                read_template(self.archive([(name, b'fixture')]))

    def test_rejects_yaml_tags(self):
        with self.assertRaises(ValueError):
            read_template(self.archive([('voice/config.yaml', b'!!unsafe'),
                                       ('voice/main/A0001.mp3', b'fixture')]))

    def test_rejects_unknown_replacement(self):
        path = self.archive([('voice/config.yaml', b'id: 1\nversion: 1\n'),
                             ('voice/main/A0001.mp3', b'fixture')])
        with self.assertRaises(ValueError):
            build(path, {'unknown': 'unused'}, 'unused.zip')


if __name__ == '__main__':
    unittest.main()
