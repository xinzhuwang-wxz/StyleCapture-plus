from __future__ import annotations

import base64
import hmac
import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

SESSION_COOKIE_NAME = "stylecapture_session"


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


class InvalidSessionError(ValueError):
    pass


class SessionSigner:
    def __init__(
        self,
        secret: str,
        *,
        now: Callable[[], datetime] | None = None,
        lifetime: timedelta = timedelta(days=30),
    ) -> None:
        if len(secret) < 24:
            raise ValueError("session signing secret must be at least 24 characters")
        if lifetime <= timedelta(0):
            raise ValueError("session lifetime must be positive")
        self._secret = secret.encode("utf-8")
        self._now = now or (lambda: datetime.now(UTC))
        self._lifetime = lifetime

    @property
    def max_age_seconds(self) -> int:
        return int(self._lifetime.total_seconds())

    def issue(self, user_id: UUID | None = None) -> tuple[UUID, str]:
        principal = user_id or uuid4()
        expires_at = self._aware_now() + self._lifetime
        payload = {
            "expires_at": int(expires_at.timestamp()),
            "user_id": str(principal),
            "version": 1,
        }
        encoded = _base64url_encode(
            json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
        )
        signature = _base64url_encode(hmac.digest(self._secret, encoded.encode("ascii"), "sha256"))
        return principal, f"{encoded}.{signature}"

    def verify(self, token: str) -> UUID:
        try:
            encoded, supplied_signature = token.split(".", maxsplit=1)
            expected_signature = _base64url_encode(
                hmac.digest(self._secret, encoded.encode("ascii"), "sha256")
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError("signature mismatch")
            payload = json.loads(_base64url_decode(encoded))
            if set(payload) != {"expires_at", "user_id", "version"}:
                raise ValueError("unexpected session fields")
            if payload["version"] != 1:
                raise ValueError("unsupported session version")
            expires_at = datetime.fromtimestamp(int(payload["expires_at"]), tz=UTC)
            principal = UUID(str(payload["user_id"]))
        except (
            TypeError,
            ValueError,
            UnicodeDecodeError,
            json.JSONDecodeError,
        ) as error:
            raise InvalidSessionError("Session is invalid") from error
        if self._aware_now() >= expires_at:
            raise InvalidSessionError("Session has expired")
        return principal

    def _aware_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise RuntimeError("session clock must return a timezone-aware datetime")
        return value.astimezone(UTC)
