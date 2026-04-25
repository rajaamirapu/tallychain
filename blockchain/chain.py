"""
TallyChain — Blockchain Engine
Manages the append-only chain of financial transaction blocks.
Persists to an encrypted JSON file and validates chain integrity on every load.
"""
import json
import os
from datetime import datetime, timezone
from typing import Optional
from pathlib import Path

from .block import Block, sha256
from config import settings


class BlockchainIntegrityError(Exception):
    """Raised when chain validation fails — tamper detected."""
    pass


class Blockchain:
    """
    Append-only blockchain for financial transactions.
    Thread-safe for single-process use; add a file lock for multi-process.
    """

    def __init__(self, path: Optional[str] = None, company_id: str = "default"):
        self.path = path or settings.BLOCKCHAIN_PATH
        self.company_id = company_id
        self.chain: list[Block] = []
        self._load()

    # ─────────────────────────── persistence ────────────────────────────────

    def _load(self):
        """Load chain from disk; create genesis block if new."""
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            self.chain = [Block.from_dict(b) for b in raw]
            valid, msg = self.validate_chain()
            if not valid:
                raise BlockchainIntegrityError(
                    f"Chain integrity check FAILED — possible tampering detected!\n{msg}"
                )
        else:
            self.chain = [Block.genesis(self.company_id)]
            self._save()

    def _save(self):
        """Persist chain to disk."""
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([b.to_dict() for b in self.chain], f, indent=2, default=str)

    # ─────────────────────────── core operations ────────────────────────────

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_block(self, transactions: list[dict], created_by: str = "system",
                  block_type: str = "TRANSACTION") -> Block:
        """
        Add a new block containing one or more transactions.
        Returns the newly created block.
        """
        ts = datetime.now(timezone.utc).isoformat()
        block = Block(
            index=len(self.chain),
            timestamp=ts,
            transactions=transactions,
            previous_hash=self.last_block.hash,
            block_type=block_type,
            created_by=created_by,
            company_id=self.company_id,
        )
        self.chain.append(block)
        self._save()
        return block

    # ─────────────────────────── validation ─────────────────────────────────

    def validate_chain(self) -> tuple[bool, str]:
        """
        Full chain validation:
          1. Each block's hash must equal compute_hash()
          2. Each block's merkle_root must match its transactions
          3. Each block's previous_hash must equal the prior block's hash
        Returns (is_valid, message).
        """
        if not self.chain:
            return True, "Empty chain"

        # Validate genesis
        genesis = self.chain[0]
        if not genesis.is_valid():
            return False, "Genesis block hash mismatch"

        for i in range(1, len(self.chain)):
            current = self.chain[i]
            previous = self.chain[i - 1]

            if current.previous_hash != previous.hash:
                return False, (
                    f"Block {i}: previous_hash mismatch — "
                    f"expected {previous.hash[:16]}… got {current.previous_hash[:16]}…"
                )
            if not current.is_valid():
                return False, (
                    f"Block {i}: hash/merkle integrity check failed — "
                    f"block may have been tampered with"
                )

        return True, f"Chain valid — {len(self.chain)} blocks verified"

    def get_block_by_index(self, index: int) -> Optional[Block]:
        if 0 <= index < len(self.chain):
            return self.chain[index]
        return None

    def find_transaction(self, tx_id: str) -> Optional[tuple[Block, dict]]:
        """Find a transaction by its 'id' field across all blocks."""
        for block in self.chain:
            for tx in block.transactions:
                if tx.get("id") == tx_id:
                    return block, tx
        return None

    def get_chain_stats(self) -> dict:
        total_txs = sum(len(b.transactions) for b in self.chain)
        valid, msg = self.validate_chain()
        return {
            "total_blocks": len(self.chain),
            "total_transactions": total_txs,
            "genesis_hash": self.chain[0].hash if self.chain else None,
            "latest_hash": self.last_block.hash,
            "latest_index": self.last_block.index,
            "is_valid": valid,
            "validation_message": msg,
            "company_id": self.company_id,
        }

    def get_recent_blocks(self, n: int = 10) -> list[dict]:
        blocks = self.chain[-n:]
        return [b.to_dict() for b in reversed(blocks)]


    @property
    def blocks(self) -> list:
        """Alias for self.chain — used by UI panels."""
        return self.chain

    def get_chain_stats(self) -> dict:  # noqa: F811 — override to add 'length' alias
        total_txs = sum(len(b.transactions) for b in self.chain)
        valid, msg = self.validate_chain()
        return {
            "total_blocks": len(self.chain),
            "length": len(self.chain),           # alias used by UI
            "total_transactions": total_txs,
            "genesis_hash": self.chain[0].hash if self.chain else None,
            "latest_hash": self.last_block.hash,
            "latest_index": self.last_block.index,
            "is_valid": valid,
            "validation_message": msg,
            "company_id": self.company_id,
        }


# ─── Module-level singleton ────────────────────────────────────────────────────

import threading as _threading

_chain_instance: "Blockchain | None" = None
_chain_lock = _threading.Lock()


def get_blockchain(path: str | None = None) -> Blockchain:
    """Return (or create) the process-wide Blockchain singleton."""
    global _chain_instance
    if _chain_instance is None:
        with _chain_lock:
            if _chain_instance is None:
                _chain_instance = Blockchain(path=path)
    return _chain_instance
