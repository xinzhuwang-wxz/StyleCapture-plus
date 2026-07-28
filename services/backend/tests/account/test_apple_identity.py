from __future__ import annotations

from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs

import httpx
import jwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from stylecapture_backend.features.account.application import AccountError
from stylecapture_backend.features.account.infrastructure import (
    apple_identity as apple_identity_module,
)
from stylecapture_backend.features.account.infrastructure.apple_identity import (
    AppleAuthorizationGrant,
    AppleJWK,
    AppleJWKSProvider,
    PyJWTAppleIdentityVerifier,
)


def _private_key() -> rsa.RSAPrivateKey:
    return rsa.generate_private_key(public_exponent=65537, key_size=2048)


def _token(private_key: rsa.RSAPrivateKey, *, kid: str = "kid-1", **claims: object) -> str:
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid, "alg": "RS256"})


def _jwk_payload(key: rsa.RSAPublicKey, *, kid: str) -> dict[str, object]:
    payload = jwt.algorithms.RSAAlgorithm.to_jwk(key, as_dict=True)
    assert isinstance(payload, dict)
    return {**payload, "kid": kid, "alg": "RS256", "use": "sig"}


class RejectingAuthorizationCodeExchange:
    async def exchange(self, authorization_code: str) -> AppleAuthorizationGrant:
        del authorization_code
        raise AccountError(
            "apple_authorization_failed",
            "Apple authorization code validation failed",
        )


class StaticAuthorizationCodeExchange:
    def __init__(self, identity_token: str) -> None:
        self.identity_token = identity_token

    async def exchange(self, authorization_code: str) -> AppleAuthorizationGrant:
        del authorization_code
        return AppleAuthorizationGrant(
            identity_token=self.identity_token,
            access_token="apple-access-token-from-static-exchange",
            refresh_token="apple-refresh-token-from-static-exchange",
        )


class StaticJWKProvider:
    def __init__(self, keys: list[AppleJWK]) -> None:
        self._keys = keys

    async def keys(self, *, force_refresh: bool = False) -> list[AppleJWK]:
        return self._keys


class RotatingJWKProvider:
    def __init__(self, *, stale: list[AppleJWK], fresh: list[AppleJWK]) -> None:
        self._current = stale
        self._fresh = fresh
        self.calls: list[bool] = []

    async def keys(self, *, force_refresh: bool = False) -> list[AppleJWK]:
        self.calls.append(force_refresh)
        if force_refresh:
            self._current = self._fresh
        return self._current


@pytest.mark.asyncio
async def test_http_code_exchange_posts_single_use_code_to_fixed_apple_endpoint() -> None:
    seen_requests: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        seen_requests.append(request)
        return httpx.Response(
            200,
            json={
                "access_token": "apple-access-token",
                "expires_in": 3600,
                "id_token": "exchanged-identity-token",
                "refresh_token": "apple-refresh-token",
                "token_type": "Bearer",
            },
        )

    exchange_type = apple_identity_module.HttpAppleAuthorizationCodeExchange
    exchange = exchange_type(
        client_id="com.stylecapture.journey",
        client_secret=lambda: "signed-client-secret",
        transport=httpx.MockTransport(handle),
    )

    grant = await exchange.exchange("single-use-code")

    assert grant.identity_token == "exchanged-identity-token"
    assert grant.access_token == "apple-access-token"
    assert grant.refresh_token == "apple-refresh-token"
    assert len(seen_requests) == 1
    request = seen_requests[0]
    assert str(request.url) == "https://appleid.apple.com/auth/token"
    assert request.headers["content-type"].startswith("application/x-www-form-urlencoded")
    assert parse_qs(request.content.decode("utf-8")) == {
        "client_id": ["com.stylecapture.journey"],
        "client_secret": ["signed-client-secret"],
        "code": ["single-use-code"],
        "grant_type": ["authorization_code"],
    }


@pytest.mark.asyncio
async def test_http_code_exchange_rejects_oversized_apple_response() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 65)

    exchange = apple_identity_module.HttpAppleAuthorizationCodeExchange(
        client_id="com.stylecapture.journey",
        client_secret=lambda: "signed-client-secret",
        transport=httpx.MockTransport(handle),
        max_response_bytes=64,
    )

    with pytest.raises(AccountError) as captured:
        await exchange.exchange("single-use-code")

    assert captured.value.code == "apple_authorization_invalid_response"


@pytest.mark.asyncio
async def test_http_code_exchange_maps_malformed_content_length_without_leaking_secrets() -> None:
    def handle(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            headers={"Content-Length": "not-a-number"},
            content=b'{"client_secret":"server-secret"}',
        )

    exchange = apple_identity_module.HttpAppleAuthorizationCodeExchange(
        client_id="com.stylecapture.journey",
        client_secret=lambda: "signed-client-secret",
        transport=httpx.MockTransport(handle),
    )

    with pytest.raises(AccountError) as captured:
        await exchange.exchange("single-use-code")

    assert captured.value.code == "apple_authorization_invalid_response"
    assert "signed-client-secret" not in str(captured.value)
    assert "server-secret" not in str(captured.value)


@pytest.mark.asyncio
async def test_async_jwks_provider_honors_apple_cache_control_without_refetching() -> None:
    key = _private_key()
    requests = 0

    def handle(request: httpx.Request) -> httpx.Response:
        nonlocal requests
        requests += 1
        return httpx.Response(
            200,
            headers={"Cache-Control": "public, max-age=120"},
            json={"keys": [_jwk_payload(key.public_key(), kid="kid-1")]},
        )

    provider = AppleJWKSProvider(
        transport=httpx.MockTransport(handle),
        monotonic_now=lambda: 1_000.0,
    )

    first = await provider.keys()
    second = await provider.keys()

    assert [item.kid for item in first] == ["kid-1"]
    assert second is first
    assert requests == 1


def test_client_secret_signer_uses_apple_es256_header_and_required_claims() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    private_key_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    now = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
    signer_type = apple_identity_module.AppleClientSecretSigner
    signer = signer_type(
        team_id="TEAMID1234",
        key_id="KEYID12345",
        client_id="com.stylecapture.journey",
        private_key_pem=private_key_pem,
        now=lambda: now,
        lifetime=timedelta(minutes=5),
    )

    token = signer()

    assert jwt.get_unverified_header(token) == {
        "alg": "ES256",
        "kid": "KEYID12345",
        "typ": "JWT",
    }
    claims = jwt.decode(
        token,
        key=private_key.public_key(),
        algorithms=["ES256"],
        audience="https://appleid.apple.com",
        options={"verify_exp": False},
    )
    assert claims == {
        "iss": "TEAMID1234",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
        "aud": "https://appleid.apple.com",
        "sub": "com.stylecapture.journey",
    }


@pytest.mark.asyncio
async def test_verifier_rejects_valid_identity_when_authorization_code_exchange_fails() -> None:
    key = _private_key()
    now = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
    verifier = PyJWTAppleIdentityVerifier(
        jwks=StaticJWKProvider([AppleJWK.from_public_key("kid-1", key.public_key())]),
        authorization_codes=RejectingAuthorizationCodeExchange(),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        now=lambda: now,
    )
    identity_token = _token(
        key,
        iss="https://appleid.apple.com",
        aud="com.stylecapture.journey",
        sub="apple-sub-1",
        exp=now + timedelta(minutes=5),
        iat=now,
        nonce="hashed-nonce",
    )

    with pytest.raises(AccountError) as captured:
        await verifier.verify(identity_token, "rejected-code")

    assert captured.value.code == "apple_authorization_failed"


@pytest.mark.asyncio
async def test_verifier_rejects_identity_when_exchanged_token_has_different_subject() -> None:
    key = _private_key()
    now = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
    client_identity_token = _token(
        key,
        iss="https://appleid.apple.com",
        aud="com.stylecapture.journey",
        sub="apple-sub-1",
        exp=now + timedelta(minutes=5),
        iat=now,
        nonce="hashed-nonce",
    )
    exchanged_identity_token = _token(
        key,
        iss="https://appleid.apple.com",
        aud="com.stylecapture.journey",
        sub="apple-sub-2",
        exp=now + timedelta(minutes=5),
        iat=now,
        nonce="hashed-nonce",
    )
    verifier = PyJWTAppleIdentityVerifier(
        jwks=StaticJWKProvider([AppleJWK.from_public_key("kid-1", key.public_key())]),
        authorization_codes=StaticAuthorizationCodeExchange(exchanged_identity_token),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        now=lambda: now,
    )

    with pytest.raises(AccountError) as captured:
        await verifier.verify(client_identity_token, "valid-code")

    assert captured.value.code == "apple_authorization_mismatch"


@pytest.mark.asyncio
async def test_verifier_rejects_exchange_for_a_different_allowed_client_id() -> None:
    key = _private_key()
    now = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
    client_identity_token = _token(
        key,
        iss="https://appleid.apple.com",
        aud="com.stylecapture.journey",
        sub="apple-sub-1",
        exp=now + timedelta(minutes=5),
        iat=now,
        nonce="hashed-nonce",
    )
    exchanged_identity_token = _token(
        key,
        iss="https://appleid.apple.com",
        aud="com.stylecapture.web",
        sub="apple-sub-1",
        exp=now + timedelta(minutes=5),
        iat=now,
        nonce="hashed-nonce",
    )
    verifier = PyJWTAppleIdentityVerifier(
        jwks=StaticJWKProvider([AppleJWK.from_public_key("kid-1", key.public_key())]),
        authorization_codes=StaticAuthorizationCodeExchange(exchanged_identity_token),
        allowed_audiences=frozenset({"com.stylecapture.journey", "com.stylecapture.web"}),
        now=lambda: now,
    )

    with pytest.raises(AccountError) as captured:
        await verifier.verify(client_identity_token, "valid-code")

    assert captured.value.code == "apple_authorization_mismatch"


@pytest.mark.asyncio
async def test_verifier_rejects_exchange_for_a_different_nonce() -> None:
    key = _private_key()
    now = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
    client_identity_token = _token(
        key,
        iss="https://appleid.apple.com",
        aud="com.stylecapture.journey",
        sub="apple-sub-1",
        exp=now + timedelta(minutes=5),
        iat=now,
        nonce="hashed-nonce-1",
    )
    exchanged_identity_token = _token(
        key,
        iss="https://appleid.apple.com",
        aud="com.stylecapture.journey",
        sub="apple-sub-1",
        exp=now + timedelta(minutes=5),
        iat=now,
        nonce="hashed-nonce-2",
    )
    verifier = PyJWTAppleIdentityVerifier(
        jwks=StaticJWKProvider([AppleJWK.from_public_key("kid-1", key.public_key())]),
        authorization_codes=StaticAuthorizationCodeExchange(exchanged_identity_token),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        now=lambda: now,
    )

    with pytest.raises(AccountError) as captured:
        await verifier.verify(client_identity_token, "valid-code")

    assert captured.value.code == "apple_authorization_mismatch"


@pytest.mark.asyncio
async def test_verifier_forces_one_jwks_refresh_when_apple_rotates_to_unknown_kid() -> None:
    stale_key = _private_key()
    fresh_key = _private_key()
    now = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
    identity_token = _token(
        fresh_key,
        kid="kid-fresh",
        iss="https://appleid.apple.com",
        aud="com.stylecapture.journey",
        sub="apple-sub-1",
        exp=now + timedelta(minutes=5),
        iat=now,
        nonce="hashed-nonce",
    )
    jwks = RotatingJWKProvider(
        stale=[AppleJWK.from_public_key("kid-stale", stale_key.public_key())],
        fresh=[AppleJWK.from_public_key("kid-fresh", fresh_key.public_key())],
    )
    verifier = PyJWTAppleIdentityVerifier(
        jwks=jwks,
        authorization_codes=StaticAuthorizationCodeExchange(identity_token),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        now=lambda: now,
    )

    claims = await verifier.verify(identity_token, "valid-code")

    assert claims.subject == "apple-sub-1"
    assert jwks.calls == [False, True, False]


@pytest.mark.asyncio
async def test_verifier_accepts_fixed_apple_issuer_audience_rs256_and_nonce() -> None:
    key = _private_key()
    now = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
    identity_token = _token(
        key,
        iss="https://appleid.apple.com",
        aud="com.stylecapture.journey",
        sub="apple-sub-1",
        exp=now + timedelta(minutes=5),
        iat=now,
        nonce="nonce-1",
    )
    verifier = PyJWTAppleIdentityVerifier(
        jwks=StaticJWKProvider([AppleJWK.from_public_key("kid-1", key.public_key())]),
        authorization_codes=StaticAuthorizationCodeExchange(identity_token),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        now=lambda: now,
    )

    claims = await verifier.verify(
        identity_token,
        "valid-code",
    )

    assert claims.subject == "apple-sub-1"
    assert claims.nonce == "nonce-1"


@pytest.mark.asyncio
async def test_verifier_rejects_token_controlled_key_urls_and_wrong_algorithm() -> None:
    key = _private_key()
    now = datetime(2026, 7, 28, 1, 0, tzinfo=UTC)
    exchanged_token = _token(
        key,
        iss="https://appleid.apple.com",
        aud="com.stylecapture.journey",
        sub="apple-sub-1",
        exp=now + timedelta(minutes=5),
        iat=now,
        nonce="nonce-1",
    )
    verifier = PyJWTAppleIdentityVerifier(
        jwks=StaticJWKProvider([AppleJWK.from_public_key("kid-1", key.public_key())]),
        authorization_codes=StaticAuthorizationCodeExchange(exchanged_token),
        allowed_audiences=frozenset({"com.stylecapture.journey"}),
        now=lambda: now,
    )
    token = jwt.encode(
        {
            "iss": "https://appleid.apple.com",
            "aud": "com.stylecapture.journey",
            "sub": "apple-sub-1",
            "exp": datetime(2026, 7, 28, 1, 5, tzinfo=UTC),
            "iat": datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
            "nonce": "nonce-1",
        },
        key,
        algorithm="RS256",
        headers={"kid": "kid-1", "alg": "RS256", "jku": "https://attacker.example/jwks"},
    )

    with pytest.raises(AccountError, match="header"):
        await verifier.verify(token, "valid-code")

    unsigned = jwt.encode(
        {
            "iss": "https://appleid.apple.com",
            "aud": "com.stylecapture.journey",
            "sub": "apple-sub-1",
            "exp": datetime(2026, 7, 28, 1, 5, tzinfo=UTC),
            "iat": datetime(2026, 7, 28, 1, 0, tzinfo=UTC),
        },
        key="",
        algorithm="none",
    )
    with pytest.raises(AccountError, match="algorithm"):
        await verifier.verify(unsigned, "valid-code")
