from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from stylecapture_backend.features.account.application import (
    AccountApplication,
    AccountError,
    AuthenticateWithAppleCommand,
    RefreshSessionCommand,
)
from stylecapture_backend.features.account.domain import AppleIdentityClaims, hash_nonce
from stylecapture_backend.features.account.infrastructure.repository import (
    InMemoryAccountRepository,
)
from stylecapture_backend.features.account.ports import AppleIdentityVerifier


class FakeAppleVerifier(AppleIdentityVerifier):
    def __init__(self, claims: AppleIdentityClaims) -> None:
        self.claims = claims

    async def verify(
        self,
        identity_token: str,
        authorization_code: str,
    ) -> AppleIdentityClaims:
        if identity_token == "bad-audience":
            raise AccountError("apple_identity_invalid", "Apple identity token is invalid")
        return self.claims


class RejectingAppleExchangeVerifier(AppleIdentityVerifier):
    async def verify(
        self,
        identity_token: str,
        authorization_code: str,
    ) -> AppleIdentityClaims:
        raise AccountError(
            "apple_authorization_failed",
            "Apple authorization code validation failed",
        )


class MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value

    def advance(self, delta: timedelta) -> None:
        self.value += delta


def build_app(
    *,
    clock: MutableClock | None = None,
    repository: InMemoryAccountRepository | None = None,
    apple_identity: AppleIdentityVerifier | None = None,
    apple_subject: str = "apple-sub-1",
    refresh_lifetime: timedelta | None = None,
) -> tuple[AccountApplication, InMemoryAccountRepository]:
    repository = repository or InMemoryAccountRepository()
    clock = clock or MutableClock(datetime(2026, 7, 28, 1, 0, tzinfo=UTC))
    options: dict[str, object] = {}
    if refresh_lifetime is not None:
        options["refresh_lifetime"] = refresh_lifetime
    app = AccountApplication(
        repository=repository,
        apple_identity=apple_identity
        or FakeAppleVerifier(
            AppleIdentityClaims(
                issuer="https://appleid.apple.com",
                audience="com.stylecapture.journey",
                subject=apple_subject,
                expires_at=datetime(2026, 7, 28, 1, 15, tzinfo=UTC),
                issued_at=datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
                nonce=hash_nonce("nonce-1"),
            )
        ),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="account-session-secret-with-enough-entropy",
        now=clock,
        **options,
    )
    return app, repository


@pytest.mark.asyncio
async def test_apple_bind_migrates_anonymous_subject_to_one_canonical_account_subject() -> None:
    app, repository = build_app()
    anonymous_subject = uuid4()
    await repository.remember_owned_record(anonymous_subject, "capture-1")

    result = await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=anonymous_subject,
            identity_token="valid",
            authorization_code="first-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )

    assert result.account_subject != anonymous_subject
    assert await repository.resolve_subject(anonymous_subject) == result.account_subject
    assert await repository.owned_records_for(result.account_subject) == ["capture-1"]
    assert await repository.owned_records_for(anonymous_subject) == []


@pytest.mark.asyncio
async def test_rejects_nonce_mismatch_without_creating_alias_or_session() -> None:
    app, repository = build_app()
    anonymous_subject = uuid4()

    with pytest.raises(AccountError, match="nonce"):
        await app.authenticate_with_apple(
            AuthenticateWithAppleCommand(
                anonymous_subject=anonymous_subject,
                identity_token="valid",
                authorization_code="first-code",
                nonce="different",
                device_name="iPhone",
            )
        )

    assert await repository.resolve_subject(anonymous_subject) == anonymous_subject
    assert repository.sessions == {}


@pytest.mark.asyncio
async def test_rejects_invalid_audience_before_binding() -> None:
    app, repository = build_app()
    anonymous_subject = uuid4()
    app._apple_identity = FakeAppleVerifier(
        AppleIdentityClaims(
            issuer="https://appleid.apple.com",
            audience="wrong.bundle",
            subject="apple-sub-1",
            expires_at=datetime(2026, 7, 28, 1, 15, tzinfo=UTC),
            issued_at=datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
            nonce="nonce-1",
        )
    )

    with pytest.raises(AccountError, match="audience"):
        await app.authenticate_with_apple(
            AuthenticateWithAppleCommand(
                anonymous_subject=anonymous_subject,
                identity_token="valid",
                authorization_code="first-code",
                nonce="nonce-1",
                device_name="iPhone",
            )
        )

    assert await repository.resolve_subject(anonymous_subject) == anonymous_subject


@pytest.mark.asyncio
async def test_failed_apple_authorization_code_exchange_leaves_ownership_unchanged() -> None:
    repository = InMemoryAccountRepository()
    anonymous_subject = uuid4()
    await repository.remember_owned_record(anonymous_subject, "capture-1")
    app, _ = build_app(
        repository=repository,
        apple_identity=RejectingAppleExchangeVerifier(),
    )

    with pytest.raises(AccountError) as captured:
        await app.authenticate_with_apple(
            AuthenticateWithAppleCommand(
                anonymous_subject=anonymous_subject,
                identity_token="valid",
                authorization_code="rejected-code",
                nonce="nonce-1",
                device_name="iPhone",
            )
        )

    assert captured.value.code == "apple_authorization_failed"
    assert await repository.resolve_subject(anonymous_subject) == anonymous_subject
    assert await repository.owned_records_for(anonymous_subject) == ["capture-1"]
    assert repository.accounts == {}
    assert repository.identities == {}
    assert repository.sessions == {}


@pytest.mark.asyncio
async def test_replayed_authorization_code_is_rejected() -> None:
    app, _ = build_app()
    first_subject = uuid4()
    second_subject = uuid4()

    await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=first_subject,
            identity_token="valid",
            authorization_code="first-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )

    with pytest.raises(AccountError, match="replayed"):
        await app.authenticate_with_apple(
            AuthenticateWithAppleCommand(
                anonymous_subject=second_subject,
                identity_token="valid",
                authorization_code="first-code",
                nonce="nonce-1",
                device_name="iPhone",
            )
        )


@pytest.mark.asyncio
async def test_deleted_anonymous_subject_is_not_misreported_as_authorization_code_replay() -> None:
    app, repository = build_app()
    anonymous_subject = uuid4()
    await repository.tombstone_subject(anonymous_subject, reason="account_deletion")

    with pytest.raises(AccountError) as captured:
        await app.authenticate_with_apple(
            AuthenticateWithAppleCommand(
                anonymous_subject=anonymous_subject,
                identity_token="valid",
                authorization_code="unused-code",
                nonce="nonce-1",
                device_name="iPhone",
            )
        )

    assert captured.value.code == "account_deleted"
    assert repository.authorization_code_hashes == set()
    assert repository.sessions == {}


@pytest.mark.asyncio
async def test_existing_account_cannot_be_rebound_to_a_different_apple_subject() -> None:
    anonymous_subject = uuid4()
    first_app, repository = build_app(apple_subject="apple-sub-1")
    first = await first_app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=anonymous_subject,
            identity_token="valid",
            authorization_code="first-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )
    second_app, _ = build_app(
        repository=repository,
        apple_subject="apple-sub-2",
    )

    with pytest.raises(AccountError) as captured:
        await second_app.authenticate_with_apple(
            AuthenticateWithAppleCommand(
                anonymous_subject=anonymous_subject,
                identity_token="valid",
                authorization_code="second-code",
                nonce="nonce-1",
                device_name="iPhone",
            )
        )

    assert captured.value.code == "account_binding_conflict"
    assert await repository.resolve_subject(anonymous_subject) == first.account_subject
    assert ("apple", "apple-sub-2") not in repository.identities
    assert len(repository.sessions) == 1


@pytest.mark.asyncio
async def test_refresh_rotates_and_reuse_revokes_session_family() -> None:
    app, _ = build_app()
    session = await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=uuid4(),
            identity_token="valid",
            authorization_code="first-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )

    rotated = await app.refresh_session(RefreshSessionCommand(refresh_token=session.refresh_token))
    assert rotated.refresh_token != session.refresh_token

    with pytest.raises(AccountError, match="reuse"):
        await app.refresh_session(RefreshSessionCommand(refresh_token=session.refresh_token))
    with pytest.raises(AccountError, match="revoked"):
        await app.resolve_access_token(rotated.access_token)


@pytest.mark.asyncio
async def test_deleted_account_tombstone_revokes_sessions_and_blocks_new_writes() -> None:
    app, repository = build_app()
    session = await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=uuid4(),
            identity_token="valid",
            authorization_code="first-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )

    deletion = await app.request_account_deletion(session.account_subject)

    assert deletion.status == "frozen"
    with pytest.raises(AccountError, match="revoked"):
        await app.resolve_access_token(session.access_token)
    with pytest.raises(ValueError, match="deleted"):
        await repository.assert_can_write(session.account_subject)


@pytest.mark.asyncio
async def test_expired_access_token_is_rejected_even_if_session_exists() -> None:
    clock = MutableClock(datetime(2026, 7, 28, 1, 0, tzinfo=UTC))
    app, _ = build_app(clock=clock)
    session = await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=uuid4(),
            identity_token="valid",
            authorization_code="first-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )
    clock.advance(timedelta(minutes=16))

    with pytest.raises(AccountError, match="expired"):
        await app.resolve_access_token(session.access_token)


@pytest.mark.asyncio
async def test_refresh_remains_valid_after_short_access_token_expires() -> None:
    clock = MutableClock(datetime(2026, 7, 28, 1, 0, tzinfo=UTC))
    app, _ = build_app(clock=clock)
    session = await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=uuid4(),
            identity_token="valid",
            authorization_code="first-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )
    clock.advance(timedelta(minutes=16))

    rotated = await app.refresh_session(
        RefreshSessionCommand(refresh_token=session.refresh_token)
    )

    assert rotated.refresh_token != session.refresh_token
    assert rotated.access_expires_at == datetime(2026, 7, 28, 1, 31, tzinfo=UTC)


@pytest.mark.asyncio
async def test_refresh_token_expires_on_its_own_absolute_deadline() -> None:
    clock = MutableClock(datetime(2026, 7, 28, 1, 0, tzinfo=UTC))
    app, _ = build_app(clock=clock, refresh_lifetime=timedelta(days=30))
    session = await app.authenticate_with_apple(
        AuthenticateWithAppleCommand(
            anonymous_subject=uuid4(),
            identity_token="valid",
            authorization_code="first-code",
            nonce="nonce-1",
            device_name="iPhone",
        )
    )
    clock.advance(timedelta(days=30))

    with pytest.raises(AccountError) as captured:
        await app.refresh_session(RefreshSessionCommand(refresh_token=session.refresh_token))

    assert captured.value.code == "refresh_token_expired"
