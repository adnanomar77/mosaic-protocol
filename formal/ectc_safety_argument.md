# ECTC safety argument

## Definitions

Let a protocol context be a resource identifier and epoch. Let `N` be the validator set and let `f` be the maximum Byzantine validator count. In **Model A**, validators are unweighted and the assumptions are

\[
N \geq 3f+1, \qquad |Q| \geq 2f+1.
\]

A `ClosureProof` for a Capsule is valid only if every signer in its quorum has issued a valid `WitnessReceipt` for that Capsule and the quorum satisfies the threshold. An honest validator does not sign two incompatible Capsules for the same resource and epoch context. The first-claim lock is the local mechanism that records this non-equivocation condition.

In **Model B**, validators have positive weights `w(v)`, total weight is `W`, a quorum satisfies `w(Q) > 2W/3`, and Byzantine weight is at most `W/3`. Model B is an extension; the paper's core theorem is stated first for Model A.

## Lemma 1: unweighted quorum intersection

For any two quorums `Q1` and `Q2` with `|Q1|, |Q2| >= 2f+1` in a validator set of size `N >= 3f+1`,

\[
|Q_1 \cap Q_2| \geq |Q_1|+|Q_2|-N \geq 4f+2-(3f+1)=f+1.
\]

At most `f` validators are Byzantine. Therefore `Q1 ∩ Q2` contains at least one honest validator.

## Theorem 1: Closure Exclusivity

Under the Model A assumptions, two incompatible Capsules cannot both obtain valid `ClosureProof`s for the same resource and protocol context.

### Proof

Assume for contradiction that incompatible Capsules `C1` and `C2` both obtain valid ClosureProofs with signer quorums `Q1` and `Q2`. By Lemma 1, `Q1 ∩ Q2` contains an honest validator `h`. Since both closure proofs are valid, `h` issued an ACCEPT receipt for both `C1` and `C2`. The Capsules are incompatible in the same first-claim context, so this violates the honest non-equivocation assumption implemented by the first-claim lock. Hence both ClosureProofs cannot be valid simultaneously. ∎

The theorem proves **closure exclusivity conditional on the stated quorum and signer assumptions**. It does not by itself prove network liveness, key security, Sybil resistance, economic security, or permissionless membership.

## Weighted extension

For two weighted quorums `Q1` and `Q2`,

\[
w(Q_1 \cap Q_2) \geq w(Q_1)+w(Q_2)-W > W/3.
\]

If Byzantine weight is at most `W/3`, the intersection contains positive honest weight. The same contradiction with weighted honest non-equivocation gives the weighted extension. The executable support in `mosaic/safety.py` and `benchmarks/model_check_mosaic.py` checks finite instances of these premises; it is not a substitute for the argument above.

## Scope of formal validation

The TLA+ specification `formal/mosaic_safety.tla` names the paper invariants I1--I8 and records the finite-state transition assumptions. The repository's Python model checker enumerates small unweighted committees, checks the weighted intersection extension on concrete weights, and exercises Closed, Conflict, and Abandoned outcomes through the reference implementation. These checks support the stated model but should be reported as bounded/model-checked evidence, not as an unbounded formal proof.
