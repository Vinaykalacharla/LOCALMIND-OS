from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from services.security import SecurityError, SecurityManager


class SecurityManagerTests(unittest.TestCase):
    def test_setup_unlock_and_roundtrip_encrypt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / "security.json"
            manager = SecurityManager(metadata_path)
            manager.setup("correct horse battery staple")

            ciphertext = manager.encrypt_bytes(b"secret notes")
            self.assertTrue(manager.is_encrypted_blob(ciphertext))

            manager.lock()
            manager.unlock("correct horse battery staple")
            self.assertEqual(manager.decrypt_bytes(ciphertext), b"secret notes")

    def test_unlock_rejects_wrong_passphrase(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            metadata_path = Path(temp_dir) / "security.json"
            manager = SecurityManager(metadata_path)
            manager.setup("correct horse battery staple")
            manager.lock()

            with self.assertRaises(SecurityError):
                manager.unlock("wrong passphrase")


if __name__ == "__main__":
    unittest.main()
