# MOSAIC adversarial state-machine matrix

This matrix records the minimum adversarial scenarios required for the ECTC claim. A `tested` entry means an executable test is present in the repository. `bounded-model` means the scenario is checked by the finite model-check harness. Network, crash, availability, and beacon cases remain local observations; they are not WAN proofs.

| # | Scenario | Evidence / test location | Status and scope |
|---:|---|---|---|
| 1 | Two conflicting Capsules | `tests/test_mosaic.py::test_conflicting_successor_cannot_close_after_first_closure`; `tests/test_ectc_and_safety.py::test_ectc_conflict_retains_conflict_evidence` | tested; local evidence preservation |
| 2 | Duplicate Capsule | `tests/test_mosaic_adversarial_matrix.py::test_duplicate_capsule_is_idempotent_at_identifier_boundary` | tested |
| 3 | Replay old WitnessReceipt | `tests/test_mosaic_adversarial_matrix.py::test_replayed_receipt_from_old_epoch_is_rejected` | tested |
| 4 | Validator signs competing Capsule | `tests/test_mosaic.py::test_conflicting_successor_cannot_close_after_first_closure` | tested; first-claim lock |
| 5 | Invalid predecessor | `tests/test_mosaic_adversarial_matrix.py::test_invalid_predecessor_is_rejected` | tested |
| 6 | Invalid nonce | `tests/test_mosaic_execution.py::test_execution_rejects_invalid_nonce_and_gas_without_partial_state` | tested in execution kernel |
| 7 | Invalid successor root | `tests/test_mosaic_adversarial_matrix.py::test_empty_successor_root_is_rejected`; `tests/test_mosaic_execution.py::test_execution_is_bound_to_closure_and_successor_state_root` | tested |
| 8 | Insufficient quorum | `tests/test_mosaic_adversarial_matrix.py::test_insufficient_quorum_cannot_close`; `tests/test_invariants.py::test_certificate_requires_quorum` | tested |
| 9 | Conflicting quorum | `tests/test_invariants.py::test_no_two_conflicting_certificates_without_honest_double_sign`; `benchmarks/model_check_mosaic.py::check_quorum_intersection` | tested and bounded-model |
| 10 | Restart before predecessor restoration | `testnet/artifacts/mosaic_testnet_long_final.json`; `tests/test_mosaic_production.py::test_protocol_state_survives_real_close_and_restart` | local rehearsal and persistence test |
| 11 | Restart after closure | `tests/test_mosaic_production.py::test_protocol_state_survives_real_close_and_restart` | tested locally |
| 12 | Partial frame | `tests/test_mosaic_network_limits.py::test_partial_frame_is_closed_by_timeout` | tested locally |
| 13 | Oversized frame | `tests/test_mosaic_network_limits.py::test_oversized_frame_is_rejected_without_killing_server` | tested locally; classified as malformed/protocol rejection |
| 14 | Message replay after restart | `tests/test_mosaic_security.py::test_replay_guard_rejects_duplicates_and_expires`; `tests/test_mosaic_adversarial_matrix.py::test_replayed_receipt_from_old_epoch_is_rejected` | tested at guard and receipt layers |
| 15 | Delayed receipt | `tests/test_mosaic_adversarial_matrix.py::test_delayed_receipt_from_old_attempt_cannot_close_new_attempt` | tested |
| 16 | Conflicting receipts | `tests/test_mosaic_adversarial_matrix.py::test_conflicting_receipts_cannot_form_one_closure` | tested |
| 17 | Byzantine non-reveal | `tests/test_mosaic_beacon.py::test_beacon_fallback_keeps_liveness_when_reveal_weight_is_low` | tested in local beacon model |
| 18 | Availability shard loss | `tests/test_mosaic_availability_store.py::test_availability_store_recovers_and_repairs_missing_shards`; `tests/test_mosaic_availability_erasure.py::test_erasure_codec_recovers_payload_after_two_shard_losses` | tested locally |
| 19 | Repair after node restart | `tests/test_mosaic_availability_store.py::test_availability_store_recovers_and_repairs_missing_shards` | tested in store/recovery path |
| 20 | Simultaneous independent resources | `tests/test_mosaic_adversarial_matrix.py::test_independent_resources_close_without_shared_predecessor`; `tests/test_mosaic.py::test_bundle_is_all_or_nothing_at_apply_boundary` | tested; not yet a scale/performance claim |

## Interpretation

The matrix demonstrates that the implementation has explicit checks for the principal negative paths and recovery paths. It does not demonstrate permissionless security, a general VM, independent operators, or WAN liveness. The revised paper reports the matrix as validation evidence and keeps theorem, model-checking, implementation, and observation claims separate.
