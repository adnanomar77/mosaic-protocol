from ccd_nexus import KeyPair
from mosaic import DurableStore, DeterministicExecutor, ExecutionInstruction, ExecutionTransaction


def test_execution_state_persists_across_restart(tmp_path):
    key = KeyPair.generate()
    path = tmp_path / "execution.sqlite"
    with DurableStore(path) as store:
        executor = DeterministicExecutor({"counter": 0})
        tx = ExecutionTransaction.create(
            key,
            0,
            100,
            (ExecutionInstruction("ADD_INT", "counter", 3),),
        )
        receipt = executor.execute(tx)
        executor.persist(store)
        root = executor.state_root
    with DurableStore(path) as reopened_store:
        restored = DeterministicExecutor.from_store(reopened_store)
        assert restored.state_root == root
        assert restored.state == {"counter": 3}
        assert restored.nonces[key.identity] == 1
        assert restored.receipts[tx.tx_id] == receipt
