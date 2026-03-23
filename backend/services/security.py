from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any, Dict

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


MAGIC = b"LMENC1"
VERIFIER = b"localmind-security-check"


class SecurityError(Exception):
    pass


class SecurityManager:
    def __init__(self, metadata_path: Path):
        self.metadata_path = metadata_path
        self._key: bytes | None = None

    @property
    def configured(self) -> bool:
        return self.metadata_path.exists()

    @property
    def unlocked(self) -> bool:
        return self._key is not None

    def status(self) -> Dict[str, bool]:
        return {"configured": self.configured, "unlocked": self.unlocked}

    def _load_metadata(self) -> Dict[str, Any]:
        if not self.configured:
            raise SecurityError("Security is not configured")
        try:
            return json.loads(self.metadata_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise SecurityError("Security metadata is unreadable") from exc

    def _derive_key(self, passphrase: str, salt: bytes, length: int) -> bytes:
        if len(passphrase) < 8:
            raise SecurityError("Passphrase must be at least 8 characters")
        kdf = Scrypt(salt=salt, length=length, n=2**14, r=8, p=1)
        return kdf.derive(passphrase.encode("utf-8"))

    def _encrypt_with_key(self, key: bytes, plaintext: bytes) -> bytes:
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
        return MAGIC + nonce + ciphertext

    def _decrypt_with_key(self, key: bytes, payload: bytes) -> bytes:
        if not self.is_encrypted_blob(payload):
            raise SecurityError("Payload is not encrypted")
        nonce = payload[len(MAGIC) : len(MAGIC) + 12]
        ciphertext = payload[len(MAGIC) + 12 :]
        try:
            return AESGCM(key).decrypt(nonce, ciphertext, None)
        except Exception as exc:
            raise SecurityError("Invalid passphrase or corrupted data") from exc

    def is_encrypted_blob(self, payload: bytes) -> bool:
        return payload.startswith(MAGIC)

    def setup(self, passphrase: str) -> None:
        if self.configured:
            raise SecurityError("Security is already configured")
        salt = os.urandom(16)
        key = self._derive_key(passphrase, salt, length=32)
        verifier = self._encrypt_with_key(key, VERIFIER)
        metadata = {
            "version": 1,
            "kdf": {"name": "scrypt", "length": 32, "n": 2**14, "r": 8, "p": 1},
            "salt": base64.b64encode(salt).decode("ascii"),
            "verifier": base64.b64encode(verifier).decode("ascii"),
        }
        self.metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=True), encoding="utf-8")
        self._key = key

    def unlock(self, passphrase: str) -> None:
        metadata = self._load_metadata()
        try:
            salt = base64.b64decode(metadata["salt"])
            verifier = base64.b64decode(metadata["verifier"])
            length = int(metadata["kdf"]["length"])
        except Exception as exc:
            raise SecurityError("Security metadata is invalid") from exc
        key = self._derive_key(passphrase, salt, length=length)
        plaintext = self._decrypt_with_key(key, verifier)
        if plaintext != VERIFIER:
            raise SecurityError("Invalid passphrase or corrupted data")
        self._key = key

    def lock(self) -> None:
        self._key = None

    def encrypt_bytes(self, plaintext: bytes) -> bytes:
        if not self.configured or self._key is None:
            raise SecurityError("Unlock the backend before writing encrypted data")
        return self._encrypt_with_key(self._key, plaintext)

    def decrypt_bytes(self, payload: bytes) -> bytes:
        if not self.configured or self._key is None:
            raise SecurityError("Unlock the backend before reading encrypted data")
        return self._decrypt_with_key(self._key, payload)
