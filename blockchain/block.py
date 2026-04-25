"""
TallyChain — Block Structure
Each financial transaction becomes an immutable block in the chain.
"""
import hashlib
import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Optional
from datetime import datetime, timezone


def sha256(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def compute_merkle_root(transactions: list[dict]) -> str:
    """Compute Merkle root of a list of transactions."""
    if not transactions:
        return sha256("EMPTY")
    leaves = [sha256(json.dumps(tx, sort_keys=True, default=str)) for tx in transactions]
    while len(leaves) > 1:
        if len(leaves) % 2 != 0:
            leaves.append(leaves[-1])          # duplicate last leaf for odd count
        leaves = [sha256(leaves[i] + leaves[i + 1]) for i in range(0, len(leaves), 2)]
    return leaves[0]


@dataclass
class Block:
    index: int
    timestamp: str
    transactions: list[dict]          # list of transaction dicts
    previous_hash: str
    merkle_root: str = field(default="")
    nonce: int = field(default=0)
    hash: str = field(default="")
    block_type: str = "TRANSACTION"   # GENESIS | TRANSACTION | ADJUSTMENT
    created_by: str = "system"
    company_id: str = "default"

    def __post_init__(self):
        if not self.merkle_root:
            self.merkle_root = compute_merkle_root(self.transactions)
        if not self.hash:
            self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        """Deterministic SHA-256 hash of this block's content."""
        block_data = {
            "index": self.index,
            "timestamp": self.timestamp,
            "merkle_root": self.merkle_root,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
            "block_type": self.block_type,
            "created_by": self.created_by,
            "company_id": self.company_id,
        }
        return sha256(json.dumps(block_data, sort_keys=True))

    def is_valid(self) -> bool:
        """Verify this block's integrity."""
        expected_merkle = compute_merkle_root(self.transactions)
        expected_hash = self.compute_hash()
        return self.merkle_root == expected_merkle and self.hash == expected_hash

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Block":
        b = cls(
            index=data["index"],
            timestamp=data["timestamp"],
            transactions=data["transactions"],
            previous_hash=data["previous_hash"],
            merkle_root=data.get("merkle_root", ""),
            nonce=data.get("nonce", 0),
            hash=data.get("hash", ""),
            block_type=data.get("block_type", "TRANSACTION"),
            created_by=data.get("created_by", "system"),
            company_id=data.get("company_id", "default"),
        )
        return b

    @classmethod
    def genesis(cls, company_id: str = "default") -> "Block":
        """Create the immutable genesis block."""
        ts = datetime.now(timezone.utc).isoformat()
        genesis_tx = {
            "type": "GENESIS",
            "message": "TallyChain — Immutable Financial Ledger Initialized",
            "timestamp": ts,
            "company_id": company_id,
        }
        b = cls(
            index=0,
            timestamp=ts,
            transactions=[genesis_tx],
            previous_hash="0" * 64,
            block_type="GENESIS",
            created_by="system",
            company_id=company_id,
        )
        return b
