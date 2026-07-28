from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from urllib.parse import parse_qs
from uuid import UUID, uuid4

import httpx
import pytest
from stylecapture_backend.features.account.application import (
    AccountApplication,
    AccountError,
    AuthenticateWithAppleCommand,
)
from stylecapture_backend.features.account.domain import (
    AccountDeletionAcceptance,
    AppleIdentityClaims,
    AppleProviderGrant,
    DeletionRequest,
    ProviderGrantRevocationError,
    hash_nonce,
)
from stylecapture_backend.features.account.infrastructure import (
    apple_identity as apple_identity_module,
)
from stylecapture_backend.features.account.infrastructure.repository import (
    InMemoryAccountRepository,
    InMemoryAppleProviderGrantRepository,
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
            provider_grant=AppleProviderGrant(
                provider_subject="apple-sub-revocable",
                access_token="apple-access-token-for-revocation",
                refresh_token="apple-refresh-token-for-revocation",
                issued_at=datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
            ),
        )


class RevocationAwareRepository(InMemoryAccountRepository):
    def __init__(self, events: list[tuple[str, UUID | str]]) -> None:
        super().__init__()
        self.events = events

    async def revoke_subject_sessions(self, subject_id: UUID) -> None:
        canonical = await self.resolve_subject(subject_id)
        self.events.append(("stylecapture_sessions", canonical))
        await super().revoke_subject_sessions(subject_id)

    async def tombstone_subject(self, subject_id: UUID, *, reason: str) -> DeletionRequest:
        canonical = await self.resolve_subject(subject_id)
        self.events.append(("tombstone", canonical))
        return await super().tombstone_subject(subject_id, reason=reason)

    async def accept_account_deletion(
        self,
        subject_id: UUID,
        *,
        reason: str,
        access_token_hash: str | None = None,
        idempotency_key_hash: str | None = None,
    ) -> AccountDeletionAcceptance:
        canonical = await self.resolve_subject(subject_id)
        result = await super().accept_account_deletion(
            subject_id,
            reason=reason,
            access_token_hash=access_token_hash,
            idempotency_key_hash=idempotency_key_hash,
        )
        self.events.append(("tombstone", canonical))
        self.events.append(("stylecapture_sessions", canonical))
        return result


class FailingGrantPersistRepository(InMemoryAccountRepository):
    def _store_apple_provider_grant(self, canonical: UUID, grant: AppleProviderGrant) -> None:
        del canonical, grant
        raise RuntimeError("grant write failed")


class RecordingAppleRevoker:
    def __init__(self, events: list[tuple[str, UUID | str]], *, fail: bool = False) -> None:
        self.events = events
        self.fail = fail

    async def revoke(self, *, token: str, token_type_hint: str) -> None:
        self.events.append(("apple", token))
        self.events.append(("apple_hint", token_type_hint))
        if self.fail:
            raise ProviderGrantRevocationError("Apple token revocation failed")


class UnreadableResponseStream(httpx.AsyncByteStream):
    def __aiter__(self) -> AsyncIterator[bytes]:
        raise AssertionError("Apple revoke response body must not be read")


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

    assert grant.identity_token == "exchanged-identity-token"
    assert grant.access_token == "apple-access-token-for-revocation"
    assert grant.refresh_token == "apple-refresh-token-for-revocation"


@pytest.mark.asyncio
async def test_apple_code_exchange_rejects_missing_refresh_token() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "access_token": "apple-access-token-for-revocation",
                "expires_in": 3600,
                "id_token": "exchanged-identity-token",
                "token_type": "Bearer",
            },
        )

    exchange = apple_identity_module.HttpAppleAuthorizationCodeExchange(
        client_id="com.stylecapture.journey",
        client_secret=lambda: "signed-client-secret",
        transport=httpx.MockTransport(handle),
    )

    with pytest.raises(AccountError) as captured:
        await exchange.exchange("single-use-code")

    assert captured.value.code == "apple_authorization_invalid_response"


@pytest.mark.asyncio
async def test_account_deletion_freezes_and_revokes_local_sessions_before_apple_io() -> None:
    events: list[tuple[str, UUID | str]] = []
    repository = RevocationAwareRepository(events)
    apple_provider_grants = InMemoryAppleProviderGrantRepository(repository)
    app = AccountApplication(
        repository=repository,
        apple_identity=StaticAppleVerifier(),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="account-session-secret-with-enough-entropy",
        apple_provider_grants=apple_provider_grants,
        apple_provider_revoker=RecordingAppleRevoker(events),
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
    assert apple_revocation not in events
    assert apple_provider_grants.revocation_status[session.account_subject] == "pending"

    await app.process_apple_provider_revocations(lease_owner="test-worker")

    assert apple_revocation in events
    assert events.index(("tombstone", session.account_subject)) < events.index(apple_revocation)
    assert events.index(local_session_revocation) < events.index(apple_revocation)
    assert apple_provider_grants.revocation_status[session.account_subject] == "revoked"
    assert apple_provider_grants.grants[session.account_subject].access_token is None
    assert apple_provider_grants.grants[session.account_subject].refresh_token is None


@pytest.mark.asyncio
async def test_active_account_grant_is_not_claimed_by_revocation_sweep() -> None:
    events: list[tuple[str, UUID | str]] = []
    repository = RevocationAwareRepository(events)
    apple_provider_grants = InMemoryAppleProviderGrantRepository(repository)
    app = AccountApplication(
        repository=repository,
        apple_identity=StaticAppleVerifier(),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="account-session-secret-with-enough-entropy",
        apple_provider_grants=apple_provider_grants,
        apple_provider_revoker=RecordingAppleRevoker(events),
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

    processed = await app.process_apple_provider_revocations(lease_owner="test-worker")

    assert processed == 0
    assert ("apple", "apple-refresh-token-for-revocation") not in events
    assert apple_provider_grants.revocation_status[session.account_subject] == "active"


@pytest.mark.asyncio
async def test_http_apple_revoker_posts_refresh_token_to_fixed_revoke_endpoint() -> None:
    seen_requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(200)

    revoker = apple_identity_module.HttpAppleProviderGrantRevoker(
        client_id="com.stylecapture.journey",
        client_secret=lambda: "signed-client-secret",
        transport=httpx.MockTransport(handle),
    )

    await revoker.revoke(
        token="apple-refresh-token-for-revocation",
        token_type_hint="refresh_token",
    )

    assert len(seen_requests) == 1
    request = seen_requests[0]
    assert str(request.url) == "https://appleid.apple.com/auth/revoke"
    assert request.headers["content-type"].startswith("application/x-www-form-urlencoded")
    assert parse_qs(request.content.decode("utf-8")) == {
        "client_id": ["com.stylecapture.journey"],
        "client_secret": ["signed-client-secret"],
        "token": ["apple-refresh-token-for-revocation"],
        "token_type_hint": ["refresh_token"],
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("status_code", [204, 302, 400, 503])
async def test_http_apple_revoker_rejects_every_non_200_status(status_code: int) -> None:
    seen_urls: list[str] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(
            status_code,
            headers={"location": "https://attacker.invalid/revoke"} if status_code == 302 else {},
        )

    revoker = apple_identity_module.HttpAppleProviderGrantRevoker(
        client_id="com.stylecapture.journey",
        client_secret=lambda: "signed-client-secret",
        transport=httpx.MockTransport(handle),
    )

    with pytest.raises(ProviderGrantRevocationError):
        await revoker.revoke(
            token="apple-refresh-token-for-revocation",
            token_type_hint="refresh_token",
        )

    assert seen_urls == ["https://appleid.apple.com/auth/revoke"]


@pytest.mark.asyncio
async def test_http_apple_revoker_accepts_200_without_buffering_response_body() -> None:
    revoker = apple_identity_module.HttpAppleProviderGrantRevoker(
        client_id="com.stylecapture.journey",
        client_secret=lambda: "signed-client-secret",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, stream=UnreadableResponseStream())
        ),
    )

    await revoker.revoke(
        token="apple-refresh-token-for-revocation",
        token_type_hint="refresh_token",
    )


@pytest.mark.asyncio
async def test_account_deletion_records_apple_revocation_failure_after_local_freeze() -> None:
    events: list[tuple[str, UUID | str]] = []
    repository = RevocationAwareRepository(events)
    apple_provider_grants = InMemoryAppleProviderGrantRepository(repository)
    app = AccountApplication(
        repository=repository,
        apple_identity=StaticAppleVerifier(),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="account-session-secret-with-enough-entropy",
        apple_provider_grants=apple_provider_grants,
        apple_provider_revoker=RecordingAppleRevoker(events, fail=True),
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

    deletion = await app.request_account_deletion(session.account_subject)

    assert deletion.status == "frozen"
    assert apple_provider_grants.revocation_status[session.account_subject] == "pending"

    await app.process_apple_provider_revocations(lease_owner="test-worker")

    assert apple_provider_grants.revocation_status[session.account_subject] == "failed"
    assert ("stylecapture_sessions", session.account_subject) in events


@pytest.mark.asyncio
async def test_failed_atomic_grant_persistence_does_not_consume_code_or_bind_identity() -> None:
    repository = FailingGrantPersistRepository()
    app = AccountApplication(
        repository=repository,
        apple_identity=StaticAppleVerifier(),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="account-session-secret-with-enough-entropy",
        now=lambda: datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
    )
    anonymous_subject = uuid4()

    with pytest.raises(RuntimeError, match="grant write failed"):
        await app.authenticate_with_apple(
            AuthenticateWithAppleCommand(
                anonymous_subject=anonymous_subject,
                identity_token="valid",
                authorization_code="single-use-code",
                nonce="nonce-1",
                device_name="iPhone",
            )
        )

    assert repository.authorization_code_hashes == set()
    assert repository.identities == {}
    assert await repository.resolve_subject(anonymous_subject) == anonymous_subject
