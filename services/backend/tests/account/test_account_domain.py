from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from stylecapture_backend.features.account.domain import (
    DeviceSession,
    SessionState,
    constant_time_equal,
    hash_secret,
)


def test_hash_secret_is_deterministic_and_does_not_return_raw_value() -> None:
    digest = hash_secret("raw-token", "pepper")

    assert digest == hash_secret("raw-token", "pepper")
    assert digest != "raw-token"


def test_constant_time_equal_matches_only_equal_values() -> None:
    assert constant_time_equal("nonce", "nonce") is True
    assert constant_time_equal("nonce", "different") is False


def test_revoked_session_rejects_access() -> None:
    session = DeviceSession.create(
        account_subject="account-subject",
        refresh_token_hash="hash-1",
        now=datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
        refresh_expires_at=datetime(2026, 7, 28, 1, 0, tzinfo=UTC) + timedelta(days=30),
    ).revoke(datetime(2026, 7, 28, 1, 1, tzinfo=UTC))

    assert session.state is SessionState.REVOKED
    with pytest.raises(ValueError, match="revoked"):
        session.assert_access_active(now=datetime(2026, 7, 28, 1, 2, tzinfo=UTC))
