# ECTC safety argument

## Definitions

Let a protocol context be a resource identifier and epoch. Let `N` be the validator set and let `f` be the maximum Byzantine validator count. In **Model A**, validators are unweighted and the assumptions are

\[
N \geq 3f+1, \qquad |Q| \geq 2f+1.
\]

For a Capsule `C` and candidate proof `P`, let `U(P)` be the receipts after deduplication by witness identifier and let `I(P)` be their witness-ID set. Define `VCP(C,P)` to hold iff (i) the proof capsule ID, predecessor ID, epoch, and attempt equal those of `C`; (ii) `I(P)` equals the proof's signer-ID set and contains no duplicate signer entry; (iii) every receipt in `U(P)` verifies under the current membership, is an `ACCEPT` receipt, and names `C`; (iv) the sum of the current member weights in `I(P)` meets the configured threshold; and (v) the proof ID recomputes from the canonical protocol label, capsule context, and the receipt IDs obtained after sorting `U(P)` by witness identifier. This is the ordering used by `ClosureProof.create` and `verify_closure`. In Model A, the weights are one and the threshold is `2f+1`. A closure is admissible for registration only if no recorded ConflictEvidence has the same predecessor identifier. An honest validator does not sign two incompatible Capsules for the same resource, predecessor, epoch, and attempt context. The first-claim lock is the local mechanism that records this non-equivocation condition.

In **Model B**, validators have positive weights `w(v)`, total weight is `W`, a quorum satisfies `w(Q) > 2W/3`, and Byzantine weight is at most `W/3`. Model B is an extension; the paper's core theorem is stated first for Model A.

## Lemma 1: unweighted quorum intersection

For any two quorums `Q1` and `Q2` with `|Q1|, |Q2| >= 2f+1` in a validator set of size `N >= 3f+1`,

\[
|Q_1 \cap Q_2| \geq |Q_1|+|Q_2|-N \geq 4f+2-(3f+1)=f+1.
\]

At most `f` validators are Byzantine. Therefore `Q1 ∩ Q2` contains at least one honest validator.

## Theorem 1: Closure Exclusivity

Under the Model A assumptions, there do not exist incompatible Capsules `C1`, `C2` and proofs `P1`, `P2` such that `VCP(C1,P1)` and `VCP(C2,P2)` both hold for the same resource, predecessor, epoch, and attempt context.

### Proof

Assume for contradiction that incompatible Capsules `C1` and `C2` satisfy `VCP` with signer sets `Q1` and `Q2`. The threshold clause gives `|Q1|, |Q2| >= 2f+1`. By Lemma 1, `Q1 ∩ Q2` contains an honest validator `h`. The receipt-validity clause of `VCP` says that `h` issued a valid `ACCEPT` receipt for both Capsules. Because the Capsules are incompatible in the same first-claim context, this contradicts honest non-equivocation. Hence both proofs cannot satisfy `VCP` simultaneously. Registration additionally rejects any predecessor context with recorded ConflictEvidence, so two incompatible Closed observations are excluded under the same premises. ∎

Evidence completeness is a state-observation predicate: at time `t`, a Capsule is complete when a verifier can audit the recorded Closed, Conflict, or Abandoned artifact set against the referenced Capsules, signatures, receipts, and identifiers. The current implementation does not expose a standalone verifier routine for ConflictEvidence or AbandonProof; the phrase “evidence-complete” therefore denotes an auditable artifact state, not an already-implemented independent verification API. Liveness is a separate temporal predicate, `Live(C,t0) == \E t >= t0 : Outcome_t(C) is terminal`. ECTC defines the former and does not imply the latter. The local long-run is an operational observation under one schedule, not a termination theorem.

## Weighted extension

For two weighted quorums `Q1` and `Q2`,

\[
w(Q_1 \cap Q_2) \geq w(Q_1)+w(Q_2)-W > W/3.
\]

If Byzantine weight is at most `W/3`, the intersection contains positive honest weight. The same contradiction with weighted honest non-equivocation gives the weighted extension. The executable support in `mosaic/safety.py` and `benchmarks/model_check_mosaic.py` checks finite instances of these premises; it is not a substitute for the argument above.

## Scope of formal validation

The TLA+ specification `formal/mosaic_safety.tla` names the paper invariants I1--I8 and records the finite-state transition assumptions. The repository's Python model checker enumerates small unweighted committees, checks the weighted intersection extension on concrete weights, and exercises Closed, Conflict, and Abandoned outcomes through the reference implementation. These checks support the stated model but should be reported as bounded/model-checked evidence, not as an unbounded formal proof.
