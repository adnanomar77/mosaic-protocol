import pytest

from ccd_nexus import KeyPair
from mosaic import (
    DeterministicExecutor,
    ExecutionBinding,
    ExecutionError,
    ExecutionInstruction,
    ExecutionTransaction,
)


def test_deterministic_execution_updates_state_and_receipt():
    client = KeyPair.generate()
    executor = DeterministicExecutor({"counter": 1})
    tx = ExecutionTransaction.create(
        client,
        nonce=0,
        gas_limit=100,
        instructions=(
            ExecutionInstruction("ADD_INT", "counter", 4),
            ExecutionInstruction("SET", "status", "ready"),
        ),
    )
    receipt = executor.execute(tx)
    assert receipt.success is True
    assert executor.state == {"counter": 5, "status": "ready"}
    assert receipt.pre_state_root != receipt.post_state_root
    assert receipt.gas_used == 22
    assert executor.execute(tx) == receipt


def test_execution_rejects_invalid_nonce_and_gas_without_partial_state():
    client = KeyPair.generate()
    executor = DeterministicExecutor({"counter": 1})
    tx = ExecutionTransaction.create(
        client,
        nonce=1,
        gas_limit=10,
        instructions=(ExecutionInstruction("ADD_INT", "counter", 4),),
    )
    receipt = executor.execute(tx)
    assert receipt.success is False
    assert executor.state == {"counter": 1}

    valid = ExecutionTransaction.create(
        client,
        nonce=0,
        gas_limit=10,
        instructions=(ExecutionInstruction("ADD_INT", "counter", 4),),
    )
    receipt = executor.execute(valid)
    assert receipt.success is False
    assert "gas" in receipt.error
    assert executor.state == {"counter": 1}


def test_execution_batch_reverts_atomically():
    client = KeyPair.generate()
    executor = DeterministicExecutor({"counter": 0})
    first = ExecutionTransaction.create(
        client, 0, 100, (ExecutionInstruction("ADD_INT", "counter", 1),)
    )
    second = ExecutionTransaction.create(
        client, 1, 1, (ExecutionInstruction("ADD_INT", "counter", 1),)
    )
    with pytest.raises(ExecutionError, match="reverted"):
        executor.execute_batch((first, second))
    assert executor.state == {"counter": 0}
    assert executor.nonces == {}


def test_execution_receipt_binding_is_specific_to_capsule_and_predecessor():
    client = KeyPair.generate()
    executor = DeterministicExecutor({"counter": 0})
    tx = ExecutionTransaction.create(
        client, 0, 100, (ExecutionInstruction("ADD_INT", "counter", 1),)
    )
    receipt = executor.execute(tx)
    binding = ExecutionBinding.create("capsule-1", "seal-0", receipt)
    assert binding.verify(receipt, "capsule-1", "seal-0")
    assert not binding.verify(receipt, "capsule-2", "seal-0")
    assert not binding.verify(receipt, "capsule-1", "seal-1")


def test_execution_does_not_execute_unknown_operations_or_unbounded_values():
    client = KeyPair.generate()
    executor = DeterministicExecutor()
    unknown = ExecutionTransaction.create(
        client, 0, 100, (ExecutionInstruction("EVAL", "x", "__import__('os')"),)
    )
    result = executor.execute(unknown)
    assert result.success is False
    assert executor.state == {}
