from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from stylecapture_backend.platform.session import InvalidSessionError, SessionSigner


def test_signed_session_round_trips_without_exposing_a_trusted_user_header() -> None:
    now = datetime(2026, 7, 25, 8, 0, tzinfo=UTC)
    signer = SessionSigner(
        "test-session-secret-with-enough-entropy",
        now=lambda: now,
    )
    user_id = uuid4()

    issued_user, token = signer.issue(user_id)

    assert issued_user == user_id
    assert signer.verify(token) == user_id
    assert str(user_id) not in token


def test_tampered_or_expired_session_is_rejected() -> None:
    now = datetime(2026, 7, 25, 8, 0, tzinfo=UTC)
    signer = SessionSigner(
        "test-session-secret-with-enough-entropy",
        now=lambda: now,
        lifetime=timedelta(minutes=5),
    )
    _, token = signer.issue()

    with pytest.raises(InvalidSessionError):
        signer.verify(f"{token[:-1]}x")

    now += timedelta(minutes=5)
    with pytest.raises(InvalidSessionError):
        signer.verify(token)
