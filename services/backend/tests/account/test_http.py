from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from stylecapture_backend.features.account.application import AccountApplication, AccountError
from stylecapture_backend.features.account.domain import AppleIdentityClaims, hash_nonce
from stylecapture_backend.features.account.infrastructure.repository import (
    InMemoryAccountRepository,
)
from stylecapture_backend.features.account.ports import AppleIdentityVerifier
from stylecapture_backend.features.capture.application import (
    CaptureApplication,
    JobRetryApplication,
)
from stylecapture_backend.features.capture.ports import JobRepository, ObjectStore, UploadAcceptor
from stylecapture_backend.features.wardrobe.application import WardrobeApplication
from stylecapture_backend.main import BackendServices, create_app


class FakeAppleVerifier(AppleIdentityVerifier):
    async def verify(
        self,
        identity_token: str,
        authorization_code: str,
    ) -> AppleIdentityClaims:
        return AppleIdentityClaims(
            issuer="https://appleid.apple.com",
            audience="com.stylecapture.journey",
            subject=f"apple-sub-http-{authorization_code}",
            expires_at=datetime(2026, 7, 28, 1, 15, tzinfo=UTC),
            issued_at=datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
            nonce=hash_nonce("nonce-1"),
        )


class FailingDeletionAccounts:
    def __init__(self) -> None:
        self.subject_id = uuid4()

    async def resolve_access_token(self, token: str) -> UUID:
        assert token == "access-token"
        return self.subject_id

    async def request_account_deletion(self, subject_id: UUID) -> None:
        assert subject_id == self.subject_id
        raise AccountError(
            "apple_provider_revocation_failed",
            "Apple provider token revocation failed",
        )

    async def request_account_deletion_with_access_token(self, command: object) -> None:
        del command
        raise AccountError(
            "apple_provider_revocation_failed",
            "Apple provider token revocation failed",
        )


def build_client() -> tuple[AsyncClient, InMemoryAccountRepository]:
    unused = object()
    repository = InMemoryAccountRepository()
    accounts = AccountApplication(
        repository=repository,
        apple_identity=FakeAppleVerifier(),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        token_secret="http-account-session-secret-with-enough-entropy",
        now=lambda: datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
    )
    app = create_app(
        BackendServices(
            capture=cast(CaptureApplication, unused),
            jobs=cast(JobRepository, unused),
            objects=cast(ObjectStore, unused),
            retries=cast(JobRetryApplication, unused),
            wardrobe=cast(WardrobeApplication, unused),
            accounts=accounts,
            uploads=cast(UploadAcceptor, unused),
        )
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test"), repository


def build_failing_deletion_client() -> AsyncClient:
    unused = object()
    app = create_app(
        BackendServices(
            capture=cast(CaptureApplication, unused),
            jobs=cast(JobRepository, unused),
            objects=cast(ObjectStore, unused),
            retries=cast(JobRetryApplication, unused),
            wardrobe=cast(WardrobeApplication, unused),
            accounts=cast(AccountApplication, FailingDeletionAccounts()),
            uploads=cast(UploadAcceptor, unused),
        )
    )
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_auth_apple_refresh_and_deletion_status_use_stable_error_envelope() -> None:
    client, repository = build_client()
    async with client:
        anonymous = await client.post("/v1/session")
        anonymous_subject = UUID(anonymous.json()["user_id"])
        await repository.remember_owned_record(anonymous_subject, "capture-1")

        auth = await client.post(
            "/v1/auth/apple",
            json={
                "identity_token": "valid",
                "authorization_code": "code-1",
                "nonce": "nonce-1",
                "device_name": "iPhone",
            },
        )
        assert auth.status_code == 200
        body = auth.json()
        assert body["account_subject"] != str(anonymous_subject)
        assert body["token_type"] == "Bearer"
        assert await repository.owned_records_for(UUID(body["account_subject"])) == ["capture-1"]

        refresh = await client.post(
            "/v1/auth/refresh",
            json={"refresh_token": body["refresh_token"]},
        )
        assert refresh.status_code == 200
        assert refresh.json()["refresh_token"] != body["refresh_token"]

        delete = await client.post(
            "/v1/account/delete",
            headers={
                "Authorization": f"Bearer {refresh.json()['access_token']}",
                "Idempotency-Key": "delete-account-test-1",
            },
        )
        assert delete.status_code == 202
        replay = await client.post(
            "/v1/account/delete",
            headers={
                "Authorization": f"Bearer {refresh.json()['access_token']}",
                "Idempotency-Key": "delete-account-test-1",
            },
        )
        assert replay.status_code == 202
        assert replay.json() == delete.json()


@pytest.mark.asyncio
async def test_auth_rejects_replayed_authorization_code_with_no_token_leak() -> None:
    client, _ = build_client()
    async with client:
        await client.post("/v1/session")
        first = await client.post(
            "/v1/auth/apple",
            json={
                "identity_token": "valid",
                "authorization_code": "code-1",
                "nonce": "nonce-1",
                "device_name": "iPhone",
            },
        )
        assert first.status_code == 200

        second = await client.post(
            "/v1/auth/apple",
            json={
                "identity_token": "valid",
                "authorization_code": "code-1",
                "nonce": "nonce-1",
                "device_name": "iPhone",
            },
        )

    assert second.status_code == 409
    payload = second.json()
    assert payload["error"]["code"] == "authorization_code_replayed"
    assert "code-1" not in str(payload)


@pytest.mark.asyncio
async def test_account_delete_maps_apple_provider_revocation_failed_to_503() -> None:
    client = build_failing_deletion_client()
    async with client:
        response = await client.post(
            "/v1/account/delete",
            headers={
                "Authorization": "Bearer access-token",
                "Idempotency-Key": "delete-account-test-1",
            },
        )

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "apple_provider_revocation_failed"


@pytest.mark.asyncio
async def test_account_delete_rejects_same_idempotency_key_for_different_account() -> None:
    client, _ = build_client()
    async with client:
        await client.post("/v1/session")
        first_auth = await client.post(
            "/v1/auth/apple",
            json={
                "identity_token": "valid",
                "authorization_code": "code-account-1",
                "nonce": "nonce-1",
                "device_name": "iPhone",
            },
        )
        assert first_auth.status_code == 200

        client.cookies.clear()
        await client.post("/v1/session")
        second_auth = await client.post(
            "/v1/auth/apple",
            json={
                "identity_token": "valid",
                "authorization_code": "code-account-2",
                "nonce": "nonce-1",
                "device_name": "iPhone",
            },
        )
        assert second_auth.status_code == 200

        first_delete = await client.post(
            "/v1/account/delete",
            headers={
                "Authorization": f"Bearer {first_auth.json()['access_token']}",
                "Idempotency-Key": "delete-cross-account-key",
            },
        )
        assert first_delete.status_code == 202

        conflict = await client.post(
            "/v1/account/delete",
            headers={
                "Authorization": f"Bearer {second_auth.json()['access_token']}",
                "Idempotency-Key": "delete-cross-account-key",
            },
        )

    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "account_delete_conflict"
