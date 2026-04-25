"""
TallyChain -- Proprietary Encrypted Database Engine
All data stored in AES-256-GCM encrypted format.
File format: JSON with base64-encoded encrypted blobs.
"""
import os
import json
import base64
import hashlib
import threading
from pathlib import Path
from typing import Any, Optional
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from config import settings

MAGIC_HEADER = "TALLYCHAIN_ENCRYPTED_DB_V1"


def _derive_key(password: str, salt: str) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt.encode("utf-8"),
        iterations=390_000,
    )
    return kdf.derive(password.encode("utf-8"))


class TallyDB:
    """Encrypted key-value + collection store."""

    def __init__(self, path: Optional[str] = None):
        self.path = path or settings.DB_PATH
        self._key = _derive_key(settings.DB_MASTER_PASSWORD, settings.DB_SALT)
        self._aesgcm = AESGCM(self._key)
        self._lock = threading.RLock()
        self._store: dict = {}
        self._load()

    def _encrypt(self, value: Any) -> str:
        plaintext = json.dumps(value, default=str).encode("utf-8")
        integrity = hashlib.sha256(plaintext).digest()
        payload = plaintext + b"||SHA256||" + integrity
        nonce = os.urandom(12)
        ct = self._aesgcm.encrypt(nonce, payload, None)
        blob = nonce + ct
        return base64.b64encode(blob).decode("ascii")

    def _decrypt(self, encoded: str) -> Any:
        blob = base64.b64decode(encoded.encode("ascii"))
        nonce = blob[:12]
        ct = blob[12:]
        payload = self._aesgcm.decrypt(nonce, ct, None)
        if b"||SHA256||" not in payload:
            raise ValueError("Integrity marker missing")
        plaintext, stored_hash = payload.rsplit(b"||SHA256||", 1)
        if hashlib.sha256(plaintext).digest() != stored_hash:
            raise ValueError("Integrity hash mismatch - tampered record")
        return json.loads(plaintext.decode("utf-8"))

    def _load(self):
        if not os.path.exists(self.path):
            self._store = {}
            return
        with open(self.path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if raw.get("__magic__") != MAGIC_HEADER:
            raise ValueError("Invalid TallyDB file")
        self._store = raw.get("records", {})

    def _save(self):
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"__magic__": MAGIC_HEADER, "records": self._store}, f)
        os.replace(tmp, self.path)

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store[key] = self._encrypt(value)
            self._save()

    def get(self, key: str, default: Any = None) -> Any:
        with self._lock:
            if key not in self._store:
                return default
            return self._decrypt(self._store[key])

    def delete(self, key: str) -> bool:
        with self._lock:
            if key not in self._store:
                return False
            del self._store[key]
            self._save()
            return True

    def exists(self, key: str) -> bool:
        with self._lock:
            return key in self._store

    def keys(self, prefix: str = "") -> list:
        with self._lock:
            return [k for k in self._store if k.startswith(prefix)]

    def col_insert(self, collection: str, record: dict) -> str:
        record_id = record.get("id")
        if not record_id:
            raise ValueError("Record must have an 'id' field")
        self.set(f"{collection}:{record_id}", record)
        idx_key = f"__idx__{collection}"
        idx = self.get(idx_key, [])
        if record_id not in idx:
            idx.append(record_id)
            self.set(idx_key, idx)
        return record_id

    def col_update(self, collection: str, record_id: str, updates: dict) -> Optional[dict]:
        existing = self.get(f"{collection}:{record_id}")
        if existing is None:
            return None
        existing.update(updates)
        self.set(f"{collection}:{record_id}", existing)
        return existing

    def col_get(self, collection: str, record_id: str) -> Optional[dict]:
        return self.get(f"{collection}:{record_id}")

    def col_delete(self, collection: str, record_id: str) -> bool:
        if not self.delete(f"{collection}:{record_id}"):
            return False
        idx = self.get(f"__idx__{collection}", [])
        if record_id in idx:
            idx.remove(record_id)
            self.set(f"__idx__{collection}", idx)
        return True

    def col_all(self, collection: str) -> list:
        idx = self.get(f"__idx__{collection}", [])
        return [r for r in (self.col_get(collection, rid) for rid in idx) if r is not None]

    def col_count(self, collection: str) -> int:
        return len(self.get(f"__idx__{collection}", []))

    def col_find(self, collection: str, **filters) -> list:
        return [r for r in self.col_all(collection)
                if all(r.get(k) == v for k, v in filters.items())]

    def db_stats(self) -> dict:
        with self._lock:
            collections = {}
            for key in self._store:
                if key.startswith("__idx__"):
                    cname = key[7:]
                    collections[cname] = self.col_count(cname)
            return {
                "total_keys": len(self._store),
                "collections": collections,
                "db_file": self.path,
                "encrypted": True,
            }


_db_instance: Optional[TallyDB] = None
_db_lock = threading.Lock()


def get_db() -> TallyDB:
    global _db_instance
    if _db_instance is None:
        with _db_lock:
            if _db_instance is None:
                _db_instance = TallyDB()
    return _db_instance
