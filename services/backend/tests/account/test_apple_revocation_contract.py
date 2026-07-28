from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

import httpx
import pytest
from stylecapture_backend.features.account.application import (
    AccountApplication,
    AuthenticateWithAppleCommand,
)
from stylecapture_backend.features.account.domain import (
    AppleIdentityClaims,
    DeletionRequest,
    hash_nonce,
)
from stylecapture_backend.features.account.infrastructure import (
    apple_identity as apple_identity_module,
)
from stylecapture_backend.features.account.infrastructure.repository import (
    InMemoryAccountRepository,
)
from stylecapture_backend.features.account.ports import AppleIdentityVerifier


class StaticAppleVerifier(AppleIdentityVerifier):
    async def verify(
        self,
        identity_token: str,
        authorization_code: str,
    ) -> AppleIdentityClaims:
        return AppleIdentityClaims(
            issuer="https://appleid.apple.com",
            audience="com.stylecapture.journey",
            subject="apple-sub-revocable",
            expires_at=datetime(2026, 7, 28, 1, 15, tzinfo=UTC),
            issued_at=datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
            nonce=hash_nonce("nonce-1"),
        )


class RevocationAwareRepository(InMemoryAccountRepository):
    def __init__(self, apple_refresh_token: str) -> None:
        super().__init__()
        self.apple_refresh_token = apple_refresh_token
        self.events: list[tuple[str, UUID | str]] = []

    async def revoke_apple_provider_token(self, subject_id: UUID) -> None:
        canonical = await self.resolve_subject(subject_id)
        self.events.append(("apple", self.apple_refresh_token))
        self.events.append(("apple_subject", canonical))

    async def revoke_subject_sessions(self, subject_id: UUID) -> None:
        canonical = await self.resolve_subject(subject_id)
        self.events.append(("stylecapture_sessions", canonical))
        await super().revoke_subject_sessions(subject_id)

    async def tombstone_subject(self, subject_id: UUID, *, reason: str) -> DeletionRequest:
        canonical = await self.resolve_subject(subject_id)
        self.events.append(("tombstone", canonical))
        return await super().tombstone_subject(subject_id, reason=reason)


@pytest.mark.asyncio
async def test_apple_code_exchange_returns_revocable_provider_grant_tokens() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "apple-access-token-for-revocation",
                "expires_in": 3600,
                "id_token": "exchanged-identity-token",
                "refresh_token": "apple-refresh-token-for-revocation",
                "token_type": "Bearer",
            },
        )

    exchange = apple_identity_module.HttpAppleAuthorizationCodeExchange(
        client_id="com.stylecapture.journey",
        client_secret=lambda: "signed-client-secret",
        transport=httpx.MockTransport(handle),
    )

    grant = await exchange.exchange("single-use-code")

    assert getattr(grant, "identity_token", None) == "exchanged-identity-token"
    assert getattr(grant, "access_token", None) == "apple-access-token-for-revocation"
    assert getattr(grant, "refresh_token", None) == "apple-refresh-token-for-revocation"


@pytest.mark.asyncio
async def test_account_deletion_revokes_apple_provider_token_before_local_sessions() -> None:
    repository = RevocationAwareRepository("apple-refresh-token-for-revocation")
    app = AccountApplication(
        repository=repository,
        apple_identity=StaticAppleVerifier(),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="account-session-secret-with-enough-entropy",
        now=lambda: datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
    )
    session = await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=uuid4(),
            identity_token="valid",
            authorization_code="single-use-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )

    await app.request_account_deletion(session.account_subject)

    apple_revocation = ("apple", "apple-refresh-token-for-revocation")
    local_session_revocation = ("stylecapture_sessions", session.account_subject)
    assert apple_revocation in repository.events
    assert repository.events.index(apple_revocation) < repository.events.index(
        local_session_revocation
    )
