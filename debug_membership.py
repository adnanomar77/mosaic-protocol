from ccd_nexus import KeyPair
from mosaic.membership import AdmissionRequest, MembershipManager

manager = MembershipManager(b"genesis", minimum_stake=1)
for index, stake in enumerate((5, 2, 1, 1)):
    key = KeyPair.generate()
    manager.admit(AdmissionRequest.create(key, f"v{index}", stake, f"deposit-{index}", 0))
proof = manager.select_committee(3)
print(proof)
print("snapshot seed", manager.snapshot.seed)
print("verify", manager.verify_selection(proof))
print("tickets", manager._tickets(manager.snapshot)[:3])
print("expected tuples", tuple((item[1], item[2]) for item in sorted(manager._tickets(manager.snapshot))[:3]))
print("proof tuples", proof.selected_tickets)
print("expected ids", tuple(dict.fromkeys(item[0] for item in proof.selected_tickets)))
print("proof ids", proof.selected_ids)
from ccd_nexus.crypto import digest
print("expected digest", digest({"protocol":"MOSAIC/COMMITTEE/v1","epoch":proof.epoch,"size":proof.committee_size,"selected":proof.selected_tickets,"seed":proof.seed.hex()}))
print("proof id", proof.proof_id)
