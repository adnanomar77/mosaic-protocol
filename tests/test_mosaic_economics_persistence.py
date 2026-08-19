from ccd_nexus import KeyPair
from mosaic import DurableStore, SettlementLedger, StakeBond


def test_settlement_ledger_persists_and_restores_state_root(tmp_path):
    key = KeyPair.generate()
    path = tmp_path / "settlement.sqlite"
    with DurableStore(path) as store:
        ledger = SettlementLedger()
        ledger.fund(key.identity, 100, source_id="fund-1")
        bond = StakeBond.create(key, "bond-1", 100, "MOSAIC", 0, 2)
        ledger.bond(bond)
        ledger.persist(store)
        root = ledger.state_root
    with DurableStore(path) as reopened_store:
        restored = SettlementLedger.from_store(reopened_store)
        assert restored.state_root == root
        assert restored.bonds["bond-1"].amount == 100
        assert restored.balance_of(key.identity) == 0
        assert restored.audit()
