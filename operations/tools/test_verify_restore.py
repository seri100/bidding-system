import hashlib
import hmac
import io
import json
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest

from verify_restore import restore


class RestoreSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.key = self.root / 'backup.key'
        self.key.write_text('test-only-key-never-used-in-production\n')

    def tearDown(self):
        self.temp.cleanup()

    def archive(self, traversal=False, bad_hash=False):
        payload = b'print("fixture")\n'
        manifest = {'manifest': [{'path': 'home/pi/example.py', 'sha256': ('0' * 64 if bad_hash else hashlib.sha256(payload).hexdigest())}]}
        plain = self.root / 'plain.tar.gz'
        with tarfile.open(str(plain), 'w:gz') as tar:
            for name, data in [('snapshot/home/pi/example.py', payload), ('snapshot/metadata/inventory.json', json.dumps(manifest).encode())]:
                info = tarfile.TarInfo(name)
                info.size = len(data)
                tar.addfile(info, io.BytesIO(data))
            if traversal:
                info = tarfile.TarInfo('../escape')
                info.size = 1
                tar.addfile(info, io.BytesIO(b'x'))
        encrypted = self.root / 'archive.enc'
        subprocess.check_call(['openssl', 'enc', '-aes-256-cbc', '-salt', '-pbkdf2', '-iter', '200000', '-in', str(plain), '-out', str(encrypted), '-pass', 'file:' + str(self.key)])
        Path(str(encrypted) + '.hmac').write_text(hmac.new(self.key.read_bytes().strip(), encrypted.read_bytes(), hashlib.sha256).hexdigest())
        return encrypted

    def test_valid_archive_only_extracts_to_staging(self):
        self.assertEqual(restore(self.archive(), self.key, self.root / 'stage'), 1)

    def test_modified_ciphertext_is_rejected_before_extracting(self):
        archive = self.archive()
        archive.write_bytes(archive.read_bytes() + b'tamper')
        with self.assertRaisesRegex(ValueError, 'Authentication failed'):
            restore(archive, self.key, self.root / 'stage')
        self.assertFalse((self.root / 'stage').exists())

    def test_wrong_key_is_rejected(self):
        archive = self.archive()
        wrong = self.root / 'wrong.key'
        wrong.write_text('wrong')
        with self.assertRaisesRegex(ValueError, 'Authentication failed'):
            restore(archive, wrong, self.root / 'stage')

    def test_path_traversal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Unsafe archive path'):
            restore(self.archive(traversal=True), self.key, self.root / 'stage')
        self.assertFalse((self.root / 'escape').exists())

    def test_manifest_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'File verification failed'):
            restore(self.archive(bad_hash=True), self.key, self.root / 'stage')

    def test_existing_files_are_not_overwritten(self):
        stage = self.root / 'stage'
        stage.mkdir()
        (stage / 'keep').write_text('keep')
        with self.assertRaisesRegex(ValueError, 'Destination must be empty'):
            restore(self.archive(), self.key, stage)
        self.assertEqual((stage / 'keep').read_text(), 'keep')


if __name__ == '__main__':
    unittest.main()
