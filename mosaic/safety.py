"""Executable support for MOSAIC's quorum-safety argument.

The functions in this module are finite checks for the assumptions used by the
paper's Closure Exclusivity theorem. They are not a replacement for a proof.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Set


def unweighted_fault_bound(n: int) -> int:
    """Return the largest Byzantine count allowed by ``N >= 3f + 1``."""
    if n < 1:
        raise ValueError("committee size must be positive")
    return (n - 1) // 3


def unweighted_quorum_size(n: int) -> int:
    """Return ``2f + 1`` for Model A."""
    f = unweighted_fault_bound(n)
    if n < 3 * f + 1:
        raise ValueError("committee does not satisfy N >= 3f + 1")
    return 2 * f + 1


def unweighted_honest_intersection(
    n: int,
    quorum_a: Iterable[int],
    quorum_b: Iterable[int],
    byzantine: Iterable[int],
) -> bool:
    """Check the honest-intersection premise for two unweighted quorums."""
    universe = set(range(n))
    a, b, byz = set(quorum_a), set(quorum_b), set(byzantine)
    q = unweighted_quorum_size(n)
    if not a <= universe or not b <= universe or not byz <= universe:
        return False
    if len(byz) > unweighted_fault_bound(n) or len(a) < q or len(b) < q:
        return False
    return bool((a & b) - byz)


def weighted_quorum_threshold(weights: Mapping[str, int]) -> int:
    """Return the strict ``> 2/3`` integer threshold for Model B."""
    total = sum(weights.values())
    if total <= 0 or any(weight <= 0 for weight in weights.values()):
        raise ValueError("weights must be positive and have positive total")
    return (2 * total) // 3 + 1


def weighted_honest_intersection(
    weights: Mapping[str, int],
    quorum_a: Iterable[str],
    quorum_b: Iterable[str],
    byzantine: Iterable[str],
) -> bool:
    """Check weighted quorum intersection under Byzantine weight <= one third."""
    universe = set(weights)
    a, b, byz = set(quorum_a), set(quorum_b), set(byzantine)
    if not a <= universe or not b <= universe or not byz <= universe:
        return False
    total = sum(weights.values())
    byz_weight = sum(weights[node] for node in byz)
    weight_a = sum(weights[node] for node in a)
    weight_b = sum(weights[node] for node in b)
    if 3 * byz_weight > total:
        return False
    if 3 * weight_a <= 2 * total or 3 * weight_b <= 2 * total:
        return False
    honest_intersection_weight = sum(weights[node] for node in (a & b) - byz)
    return honest_intersection_weight > 0


def closure_exclusivity_premise(
    *,
    quorum_a: Set[str],
    quorum_b: Set[str],
    honest_validators: Set[str],
) -> bool:
    """Return whether two closure proofs share an honest signer.

    If both proofs are valid for incompatible Capsules and a shared honest
    signer is forbidden from signing both lock contexts, the shared signer
    contradicts the proof validity. The theorem in the paper supplies the
    remaining protocol assumptions and does not claim this function alone is a
    complete consensus proof.
    """
    return bool((set(quorum_a) & set(quorum_b)) & set(honest_validators))
