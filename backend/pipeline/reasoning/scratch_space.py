"""Isolated scratch space for reasoning transactions.

Provides begin/commit/rollback semantics so intermediate reasoning
results can be explored without polluting the shared knowledge base.
Only committed results are promoted to the global state.

Adopted from atomspace ExecutionOutputLink (transactional execution
with result promotion) and Soar's operator application semantics.
"""

from __future__ import annotations

import copy
import logging
import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TransactionState(str, Enum):
    ACTIVE = "active"
    COMMITTED = "committed"
    ROLLED_BACK = "rolled_back"


class ScratchEntry(BaseModel):
    """An entry in the scratch space."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    key: str
    value: Any
    metadata: dict[str, Any] = Field(default_factory=dict)


class Transaction(BaseModel):
    """A reasoning transaction with begin/commit/rollback semantics."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    state: TransactionState = TransactionState.ACTIVE
    entries: dict[str, ScratchEntry] = Field(default_factory=dict)
    parent_snapshot: dict[str, ScratchEntry] = Field(default_factory=dict)


class ScratchSpace:
    """Isolated scratch space for speculative reasoning.

    Usage:
        space = ScratchSpace()
        tx = space.begin()
        space.write(tx, "hypothesis", "RAG improves recall by 20%")
        space.write(tx, "evidence", [...])
        # Only visible within this transaction
        result = space.read(tx, "hypothesis")
        space.commit(tx)  # Now visible globally
    """

    def __init__(self):
        self._global: dict[str, ScratchEntry] = {}
        self._transactions: dict[str, Transaction] = {}

    def begin(self) -> Transaction:
        tx = Transaction(parent_snapshot=copy.deepcopy(self._global))
        self._transactions[tx.id] = tx
        logger.debug("Transaction %s started", tx.id)
        return tx

    def write(self, tx: Transaction, key: str, value: Any, metadata: dict | None = None) -> str:
        if tx.state != TransactionState.ACTIVE:
            raise ValueError(f"Transaction {tx.id} is {tx.state.value}, not active")
        entry = ScratchEntry(key=key, value=value, metadata=metadata or {})
        tx.entries[key] = entry
        return entry.id

    def read(self, tx: Transaction, key: str) -> Any | None:
        if tx.state != TransactionState.ACTIVE:
            raise ValueError(f"Transaction {tx.id} is {tx.state.value}, not active")
        if key in tx.entries:
            return tx.entries[key].value
        if key in tx.parent_snapshot:
            return tx.parent_snapshot[key].value
        return None

    def read_all(self, tx: Transaction) -> dict[str, Any]:
        if tx.state != TransactionState.ACTIVE:
            raise ValueError(f"Transaction {tx.id} is {tx.state.value}, not active")
        result = {k: v.value for k, v in tx.parent_snapshot.items()}
        result.update({k: v.value for k, v in tx.entries.items()})
        return result

    def commit(self, tx: Transaction) -> list[str]:
        if tx.state != TransactionState.ACTIVE:
            raise ValueError(f"Transaction {tx.id} is {tx.state.value}, not active")
        promoted_keys = []
        for key, entry in tx.entries.items():
            self._global[key] = entry
            promoted_keys.append(key)
        tx.state = TransactionState.COMMITTED
        logger.debug("Transaction %s committed: %d entries promoted", tx.id, len(promoted_keys))
        return promoted_keys

    def rollback(self, tx: Transaction) -> None:
        if tx.state != TransactionState.ACTIVE:
            raise ValueError(f"Transaction {tx.id} is {tx.state.value}, not active")
        tx.state = TransactionState.ROLLED_BACK
        logger.debug("Transaction %s rolled back", tx.id)

    def read_global(self, key: str) -> Any | None:
        entry = self._global.get(key)
        return entry.value if entry else None

    def read_all_global(self) -> dict[str, Any]:
        return {k: v.value for k, v in self._global.items()}

    def delete_global(self, key: str) -> bool:
        if key in self._global:
            del self._global[key]
            return True
        return False

    @property
    def global_count(self) -> int:
        return len(self._global)

    @property
    def active_transactions(self) -> int:
        return len([t for t in self._transactions.values() if t.state == TransactionState.ACTIVE])

    def get_transaction(self, tx_id: str) -> Transaction | None:
        return self._transactions.get(tx_id)
