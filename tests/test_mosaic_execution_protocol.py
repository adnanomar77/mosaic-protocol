import pytest

from ccd_nexus import KeyPair
from mosaic import (
    DeterministicExecutor,
    ExecutionError,
    ExecutionInstruction,
    ExecutionTransaction,
    Member,
    MosaicProtocol,
)


def make_protocol():
    members = {}
    for index in range(4):
        key = KeyPair.generate()
        members[f"w{index}"] = Member(f"w{index}", key, weight=1)
    return MosaicProtocol(members)


def test_execution_is_bound_to_closure_and_successor_state_root():
    protocol = make_protocol()
    client = KeyPair.generate()
    executor = DeterministicExecutor({"counter": 0})
    predecessor = protocol.create_resource("asset", owner=client.identity, state_root=executor.state_root)
    tx = ExecutionTransaction.create(
        client,
        nonce=0,
        gas_limit=100,
        instructions=(ExecutionInstruction("ADD_INT", "counter", 1),),
    )
    preview = DeterministicExecutor({"counter": 0})
    expected = preview.execute(tx)
    capsule = protocol.create_capsule(
        client=client,
        predecessor=predecessor,
        successor_root=expected.post_state_root,
        rule_witness=tx.tx_id,
    )
    closure = protocol.close(capsule)
    next_seal, receipt, binding = protocol.apply_execution(capsule, closure, tx, executor)
    assert receipt.success
    assert next_seal.state_root == expected.post_state_root
    assert executor.state == {"counter": 1}
    assert binding.verify(receipt, capsule.capsule_id, predecessor.seal_id)


def test_execution_rolls_back_when_rule_witness_does_not_match():
    protocol = make_protocol()
    client = KeyPair.generate()
    executor = DeterministicExecutor({"counter": 0})
    predecessor = protocol.create_resource("asset", owner=client.identity, state_root=executor.state_root)
    tx = ExecutionTransaction.create(
        client,
        nonce=0,
        gas_limit=100,
        instructions=(ExecutionInstruction("ADD_INT", "counter", 1),),
    )
    preview = DeterministicExecutor({"counter": 0})
    expected = preview.execute(tx)
    capsule = protocol.create_capsule(
        client=client,
        predecessor=predecessor,
        successor_root=expected.post_state_root,
        rule_witness="wrong-transaction",
    )
    closure = protocol.close(capsule)
    with pytest.raises(ExecutionError, match="rule witness"):
        protocol.apply_execution(capsule, closure, tx, executor)
    assert executor.state == {"counter": 0}
    assert protocol.current_seals["asset"] == predecessor
