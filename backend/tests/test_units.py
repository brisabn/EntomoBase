import pytest

from rate_limit import AttemptLimiter
from security import hash_password, is_hash, needs_rehash, verify_password


# ---------- passwords ----------
def test_a_hash_is_not_the_password_and_verifies():
    stored = hash_password("senhaforte1")
    assert stored != "senhaforte1" and is_hash(stored)
    assert verify_password("senhaforte1", stored) is True
    assert verify_password("other-password", stored) is False


def test_hashes_of_the_same_password_differ():
    assert hash_password("senhaforte1") != hash_password("senhaforte1")


@pytest.mark.parametrize("stored", [None, "", "123", "plain-text-password", "$argon2-broken"])
def test_anything_that_is_not_a_valid_hash_is_refused(stored):
    assert verify_password("123", stored) is False
    assert verify_password("plain-text-password", stored) is False


def test_the_dummy_password_never_logs_anyone_in():
    assert verify_password("password-nobody-uses", None) is False


def test_a_fresh_hash_needs_no_rehash():
    assert needs_rehash(hash_password("senhaforte1")) is False


def test_is_hash():
    assert is_hash("$argon2id$v=19$m=65536,t=3,p=4$abc$def") and not is_hash("123") and not is_hash(None)


# ---------- attempt limiter ----------
@pytest.fixture
def clock():
    now = [0.0]
    return now


def limiter(clock, max_attempts=3, window=100):
    return AttemptLimiter(max_attempts, window, clock=lambda: clock[0])


def test_limiter_blocks_at_the_maximum(clock):
    lim = limiter(clock)
    for _ in range(2):
        lim.record_failure("a")
    assert lim.seconds_remaining("a") == 0
    lim.record_failure("a")
    assert lim.seconds_remaining("a") == 100


def test_limiter_keys_are_independent(clock):
    lim = limiter(clock)
    for _ in range(3):
        lim.record_failure("a")
    assert lim.seconds_remaining("b") == 0


def test_limiter_releases_after_the_window(clock):
    lim = limiter(clock)
    for _ in range(3):
        lim.record_failure("a")
    clock[0] = 60
    assert lim.seconds_remaining("a") == 40
    clock[0] = 101
    assert lim.seconds_remaining("a") == 0


def test_limiter_reset(clock):
    lim = limiter(clock)
    for _ in range(3):
        lim.record_failure("a")
    lim.reset("a")
    assert lim.seconds_remaining("a") == 0
    lim.reset("never-seen")


def test_old_failures_stop_counting(clock):
    lim = limiter(clock)
    lim.record_failure("a")
    lim.record_failure("a")
    clock[0] = 150
    lim.record_failure("a")
    assert lim.seconds_remaining("a") == 0


def test_limiter_forgets_old_keys(clock):
    lim = limiter(clock)
    for i in range(10050):
        lim.record_failure(f"k{i}")
    clock[0] = 500
    lim.record_failure("new")
    assert len(lim._failures) == 1
