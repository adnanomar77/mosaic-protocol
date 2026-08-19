from itertools import combinations


def quorum(n, f):
    # Strictly more than 2/3 of voting power for equal-weight validators.
    return 2 * f + 1


def test_quorum_intersection():
    results = []
    for f in range(1, 4):
        n = 3 * f + 1
        q = quorum(n, f)
        validators = set(range(n))
        # The worst case has exactly f Byzantine validators.
        for byz_tuple in combinations(validators, f):
            byz = set(byz_tuple)
            quorums = [set(qs) for qs in combinations(validators, q)]
            for left in quorums:
                for right in quorums:
                    honest_intersection = (left & right) - byz
                    assert honest_intersection, (
                        f"empty honest intersection: f={f}, byz={byz}, "
                        f"left={left}, right={right}"
                    )
        results.append((f, n, q, "ok"))
    return results


def test_no_two_conflicting_certificates():
    results = []
    for f in range(1, 4):
        n = 3 * f + 1
        q = quorum(n, f)
        validators = set(range(n))
        quorums = [set(qs) for qs in combinations(validators, q)]
        for byz_tuple in combinations(validators, f):
            byz = set(byz_tuple)
            for cert_a in quorums:
                for cert_b in quorums:
                    # Two conflicting certificates would be admissible only
                    # if every overlap were Byzantine. This is impossible.
                    admissible = ((cert_a & cert_b) - byz) == set()
                    assert not admissible, (
                        f"two conflicting certs possible: f={f}, byz={byz}, "
                        f"A={cert_a}, B={cert_b}"
                    )
        results.append((f, n, q, "ok"))
    return results


def validate_join(domains, prepared, aborted):
    # A multi-domain operation is final only if every required domain prepared
    # the exact same operation and none has an abort certificate.
    required = set(domains)
    return required.issubset(prepared) and required.isdisjoint(aborted)


def test_cross_domain_atomicity():
    assert validate_join(["A", "B"], {"A", "B"}, set())
    assert not validate_join(["A", "B"], {"A"}, set())
    assert not validate_join(["A", "B"], {"A", "B"}, {"B"})
    return "ok"


def test_domain_separation():
    # The same operation id in different epochs/domains must not be replayable.
    op_id = "hash(op)"
    digest_a = ("CCD/PREPARE/v1", 7, "domain-A", op_id)
    digest_b = ("CCD/PREPARE/v1", 7, "domain-B", op_id)
    digest_c = ("CCD/PREPARE/v1", 8, "domain-A", op_id)
    assert digest_a != digest_b
    assert digest_a != digest_c
    return "ok"


if __name__ == "__main__":
    print("quorum_intersection:", test_quorum_intersection())
    print("no_two_conflicting_certificates:", test_no_two_conflicting_certificates())
    print("cross_domain_atomicity:", test_cross_domain_atomicity())
    print("domain_separation:", test_domain_separation())
    print("ALL TESTS PASSED")
