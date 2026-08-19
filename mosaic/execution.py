"""Deterministic execution kernel for MOSAIC resources.

This module intentionally exposes a bounded instruction set rather than an
unrestricted smart-contract VM. It provides a safe foundation for
composability and state-root receipts without executing untrusted Python code.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ccd_nexus import KeyPair
from ccd_nexus.crypto import canonical_bytes, digest


class ExecutionError(ValueError):
    pass


GAS_COSTS = {"SET": 10, "DELETE": 8, "ADD_INT": 12}
MAX_KEY_BYTES = 256
MAX_VALUE_BYTES = 16 * 1024


def compute_state_root(state: dict[str, Any]) -> str:
    return digest(
        {
            "protocol": "MOSAIC/STATE-ROOT/v1",
            "state": {key: state[key] for key in sorted(state)},
        }
    )


@dataclass(frozen=True)
class ExecutionInstruction:
    operation: str
    key: str
    value: Any = None

    def validate(self) -> None:
        if self.operation not in GAS_COSTS:
            raise ExecutionError("unsupported deterministic operation")
        if not self.key or len(self.key.encode("utf-8")) > MAX_KEY_BYTES:
            raise ExecutionError("execution key is invalid or too large")
        if len(canonical_bytes(self.value)) > MAX_VALUE_BYTES:
            raise ExecutionError("execution value is too large")
        if self.operation == "ADD_INT" and not isinstance(self.value, int):
            raise ExecutionError("ADD_INT requires an integer value")
        if self.operation in {"DELETE"} and self.value is not None:
            raise ExecutionError("DELETE cannot carry a value")


@dataclass(frozen=True)
class ExecutionTransaction:
    tx_id: str
    caller: str
    caller_public_key: bytes
    nonce: int
    gas_limit: int
    instructions: tuple[ExecutionInstruction, ...]
    signature: bytes

    @classmethod
    def create(
        cls,
        caller: KeyPair,
        nonce: int,
        gas_limit: int,
        instructions: Iterable[ExecutionInstruction],
    ) -> "ExecutionTransaction":
        instructions_tuple = tuple(instructions)
        unsigned = {
            "protocol": "MOSAIC/EXECUTION-TX/v1",
            "caller": caller.identity,
            "caller_public_key": caller.public_key.hex(),
            "nonce": nonce,
            "gas_limit": gas_limit,
            "instructions": [
                {"operation": item.operation, "key": item.key, "value": item.value}
                for item in instructions_tuple
            ],
        }
        tx_id = digest(unsigned)
        return cls(
            tx_id=tx_id,
            caller=caller.identity,
            caller_public_key=caller.public_key,
            nonce=nonce,
            gas_limit=gas_limit,
            instructions=instructions_tuple,
            signature=caller.sign(canonical_bytes(unsigned)),
        )

    def statement(self) -> dict:
        return {
            "protocol": "MOSAIC/EXECUTION-TX/v1",
            "caller": self.caller,
            "caller_public_key": self.caller_public_key.hex(),
            "nonce": self.nonce,
            "gas_limit": self.gas_limit,
            "instructions": [
                {"operation": item.operation, "key": item.key, "value": item.value}
                for item in self.instructions
            ],
        }

    def verify(self) -> bool:
        return (
            self.nonce >= 0
            and self.gas_limit > 0
            and bool(self.instructions)
            and self.tx_id == digest(self.statement() | {})
            and KeyPair.verify(
                self.caller_public_key,
                canonical_bytes(self.statement()),
                self.signature,
            )
        )


@dataclass(frozen=True)
class ExecutionReceipt:
    tx_id: str
    pre_state_root: str
    post_state_root: str
    gas_used: int
    event_root: str
    state_diff_digest: str
    success: bool
    error: str | None = None


@dataclass(frozen=True)
class ExecutionBinding:
    capsule_id: str
    predecessor_id: str
    pre_state_root: str
    receipt_digest: str
    binding_id: str

    @classmethod
    def create(
        cls,
        capsule_id: str,
        predecessor_id: str,
        receipt: ExecutionReceipt,
    ) -> "ExecutionBinding":
        if not receipt.success:
            raise ExecutionError("cannot bind a failed execution receipt")
        if receipt.pre_state_root == "":
            raise ExecutionError("execution receipt has no pre-state root")
        receipt_digest = digest(
            {
                "protocol": "MOSAIC/EXECUTION-RECEIPT/v1",
                "tx_id": receipt.tx_id,
                "pre_state_root": receipt.pre_state_root,
                "post_state_root": receipt.post_state_root,
                "gas_used": receipt.gas_used,
                "event_root": receipt.event_root,
                "state_diff_digest": receipt.state_diff_digest,
            }
        )
        binding_id = digest(
            {
                "protocol": "MOSAIC/EXECUTION-BINDING/v1",
                "capsule_id": capsule_id,
                "predecessor_id": predecessor_id,
                "pre_state_root": receipt.pre_state_root,
                "receipt_digest": receipt_digest,
            }
        )
        return cls(capsule_id, predecessor_id, receipt.pre_state_root, receipt_digest, binding_id)

    def verify(self, receipt: ExecutionReceipt, capsule_id: str, predecessor_id: str) -> bool:
        if capsule_id != self.capsule_id or predecessor_id != self.predecessor_id:
            return False
        rebuilt = ExecutionBinding.create(capsule_id, predecessor_id, receipt)
        return rebuilt == self


class DeterministicExecutor:
    """Bounded state executor with explicit operations and nonce tracking."""

    def __init__(self, initial_state: dict[str, Any] | None = None, max_instructions: int = 128):
        self.state: dict[str, Any] = dict(initial_state or {})
        self.max_instructions = max_instructions
        self.nonces: dict[str, int] = {}
        self.receipts: dict[str, ExecutionReceipt] = {}

    @property
    def state_root(self) -> str:
        return compute_state_root(self.state)

    def to_dict(self) -> dict:
        return {
            "protocol": "MOSAIC/EXECUTION-STATE/v1",
            "state": dict(self.state),
            "nonces": dict(self.nonces),
            "receipts": {
                key: {
                    "tx_id": value.tx_id,
                    "pre_state_root": value.pre_state_root,
                    "post_state_root": value.post_state_root,
                    "gas_used": value.gas_used,
                    "event_root": value.event_root,
                    "state_diff_digest": value.state_diff_digest,
                    "success": value.success,
                    "error": value.error,
                }
                for key, value in self.receipts.items()
            },
            "state_root": self.state_root,
        }

    def persist(self, store: object) -> None:
        store.put("execution_state", "executor", self.to_dict(), event=False)

    @classmethod
    def from_store(cls, store: object, max_instructions: int = 128) -> "DeterministicExecutor":
        payload = store.get("execution_state", "executor")
        if payload is None:
            raise ExecutionError("execution state is missing")
        executor = cls(payload["state"], max_instructions=max_instructions)
        executor.nonces = {key: int(value) for key, value in payload["nonces"].items()}
        executor.receipts = {
            key: ExecutionReceipt(
                tx_id=value["tx_id"],
                pre_state_root=value["pre_state_root"],
                post_state_root=value["post_state_root"],
                gas_used=int(value["gas_used"]),
                event_root=value["event_root"],
                state_diff_digest=value["state_diff_digest"],
                success=bool(value["success"]),
                error=value.get("error"),
            )
            for key, value in payload["receipts"].items()
        }
        if executor.state_root != payload["state_root"]:
            raise ExecutionError("execution state root mismatch")
        return executor

    def execute(self, transaction: ExecutionTransaction) -> ExecutionReceipt:
        if transaction.tx_id in self.receipts:
            return self.receipts[transaction.tx_id]
        pre_root = self.state_root
        try:
            if not transaction.verify():
                raise ExecutionError("invalid execution transaction signature or digest")
            if len(transaction.instructions) > self.max_instructions:
                raise ExecutionError("instruction count exceeds limit")
            expected_nonce = self.nonces.get(transaction.caller, 0)
            if transaction.nonce != expected_nonce:
                raise ExecutionError("invalid transaction nonce")
            staged = dict(self.state)
            events: list[dict[str, Any]] = []
            gas_used = 0
            for instruction in transaction.instructions:
                instruction.validate()
                gas_used += GAS_COSTS[instruction.operation]
                if gas_used > transaction.gas_limit:
                    raise ExecutionError("gas limit exceeded")
                before = staged.get(instruction.key)
                if instruction.operation == "SET":
                    staged[instruction.key] = instruction.value
                elif instruction.operation == "DELETE":
                    staged.pop(instruction.key, None)
                elif instruction.operation == "ADD_INT":
                    current = staged.get(instruction.key, 0)
                    if not isinstance(current, int):
                        raise ExecutionError("ADD_INT target is not an integer")
                    staged[instruction.key] = current + instruction.value
                events.append(
                    {
                        "operation": instruction.operation,
                        "key": instruction.key,
                        "before": before,
                        "after": staged.get(instruction.key),
                    }
                )
            post_root = compute_state_root(staged)
            receipt = ExecutionReceipt(
                tx_id=transaction.tx_id,
                pre_state_root=pre_root,
                post_state_root=post_root,
                gas_used=gas_used,
                event_root=digest(events),
                state_diff_digest=digest({"before": self.state, "after": staged}),
                success=True,
            )
            self.state = staged
            self.nonces[transaction.caller] = expected_nonce + 1
        except ExecutionError as exc:
            receipt = ExecutionReceipt(
                tx_id=transaction.tx_id,
                pre_state_root=pre_root,
                post_state_root=pre_root,
                gas_used=0,
                event_root=digest([]),
                state_diff_digest=digest({"before": self.state, "after": self.state}),
                success=False,
                error=str(exc),
            )
        self.receipts[transaction.tx_id] = receipt
        return receipt

    def execute_for_capsule(
        self,
        transaction: ExecutionTransaction,
        capsule: object,
        closure: object,
        protocol: object,
    ) -> tuple[ExecutionReceipt, ExecutionBinding]:
        if capsule.capsule_id != closure.capsule_id:
            raise ExecutionError("closure does not belong to capsule")
        if not protocol.verify_closure(capsule, closure):
            raise ExecutionError("execution requires a verified closure")
        predecessor = protocol.known_seals.get(capsule.predecessor_id)
        if predecessor is None or predecessor.state_root != self.state_root:
            raise ExecutionError("executor state does not match capsule predecessor")
        if capsule.rule_witness != transaction.tx_id:
            raise ExecutionError("capsule rule witness is not this transaction")
        if capsule.successor_root == predecessor.state_root:
            raise ExecutionError("capsule successor root does not advance state")
        snapshot_state = dict(self.state)
        snapshot_nonces = dict(self.nonces)
        snapshot_receipts = dict(self.receipts)
        receipt = self.execute(transaction)
        if not receipt.success or receipt.pre_state_root != predecessor.state_root or receipt.post_state_root != capsule.successor_root:
            self.state = snapshot_state
            self.nonces = snapshot_nonces
            self.receipts = snapshot_receipts
            raise ExecutionError("execution receipt does not match capsule state roots")
        return receipt, ExecutionBinding.create(capsule.capsule_id, capsule.predecessor_id, receipt)

    def execute_batch(self, transactions: Iterable[ExecutionTransaction]) -> tuple[ExecutionReceipt, ...]:
        transactions_tuple = tuple(transactions)
        if not transactions_tuple:
            raise ExecutionError("empty execution batch")
        snapshot_state = dict(self.state)
        snapshot_nonces = dict(self.nonces)
        snapshot_receipts = dict(self.receipts)
        receipts = tuple(self.execute(item) for item in transactions_tuple)
        if not all(item.success for item in receipts):
            self.state = snapshot_state
            self.nonces = snapshot_nonces
            self.receipts = snapshot_receipts
            raise ExecutionError("execution batch reverted atomically")
        return receipts
