from itertools import combinations


def quorum(n: int, f: int) -> int:
    return 2 * f + 1


def test_quorum_intersection_contains_honest_validator():
    for f in range(1, 4):
        n = 3 * f + 1
        q = quorum(n, f)
        validators = set(range(n))
        quorums = [set(item) for item in combinations(validators, q)]
        for byzantine in combinations(validators, f):
            byzantine = set(byzantine)
            for left in quorums:
                for right in quorums:
                    assert (left & right) - byzantine


def test_no_two_conflicting_certificates_without_honest_double_sign():
    for f in range(1, 4):
        n = 3 * f + 1
        q = quorum(n, f)
        validators = set(range(n))
        quorums = [set(item) for item in combinations(validators, q)]
        for byzantine in combinations(validators, f):
            byzantine = set(byzantine)
            for left in quorums:
                for right in quorums:
                    # Two conflicting certificates require an honest validator
                    # in the intersection to sign both statements.
                    assert (left & right) - byzantine
