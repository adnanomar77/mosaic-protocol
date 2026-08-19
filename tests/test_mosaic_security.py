import pytest

from mosaic.security import CapabilityVault, ReplayGuard, SecurityError, TokenBucket, derive_node_key


def test_capability_vault_encrypts_and_consumes():
    vault = CapabilityVault(b"0" * 32)
    vault.put("cap-1", b"secret", associated_data=b"asset")
    assert vault.get("cap-1", associated_data=b"asset") == b"secret"
    assert vault.consume("cap-1", associated_data=b"asset") == b"secret"
    with pytest.raises(SecurityError):
        vault.get("cap-1", associated_data=b"asset")


def test_capability_associated_data_and_key_are_authenticated():
    vault = CapabilityVault(b"0" * 32)
    vault.put("cap-1", b"secret", associated_data=b"asset")
    with pytest.raises(SecurityError):
        vault.get("cap-1", associated_data=b"other")
    with pytest.raises(SecurityError):
        CapabilityVault(b"short")


def test_replay_guard_rejects_duplicates_and_expires():
    guard = ReplayGuard(max_entries=2, ttl_seconds=10)
    assert guard.accept("m1", now=0)
    assert not guard.accept("m1", now=1)
    assert guard.accept("m2", now=1)
    assert guard.accept("m3", now=1)
    assert guard.accept("m1", now=20)


def test_token_bucket_limits_burst():
    bucket = TokenBucket(capacity=2, refill_per_second=1)
    assert bucket.allow(now=0)
    assert bucket.allow(now=0)
    assert not bucket.allow(now=0)
    assert bucket.allow(now=1)


def test_node_key_derivation_is_domain_separated():
    first = derive_node_key(b"0" * 32, "w0", 0)
    second = derive_node_key(b"0" * 32, "w0", 1)
    third = derive_node_key(b"0" * 32, "w1", 0)
    assert len(first) == 32
    assert len({first, second, third}) == 3
