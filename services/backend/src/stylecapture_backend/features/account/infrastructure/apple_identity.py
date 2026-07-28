from __future__ import annotations

import base64
import hmac
import json
from collections.abc import Callable, Sequence
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Any, Protocol

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ec import (
    SECP256R1,
    EllipticCurvePrivateKey,
)
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from stylecapture_backend.features.account.application import AccountError
from stylecapture_backend.features.account.domain import AppleIdentityClaims

APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
MAX_APPLE_CLIENT_SECRET_LIFETIME = timedelta(seconds=15_777_000)


def _b64url_int(value: int) -> str:
    raw = value.to_bytes((value.bit_length() + 7) // 8, byteorder="big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class AppleJWK:
    def __init__(self, *, kid: str, key: RSAPublicKey) -> None:
        self.kid = kid
        self.key = key

    @classmethod
    def from_public_key(cls, kid: str, key: RSAPublicKey) -> AppleJWK:
        return cls(kid=kid, key=key)

    @classmethod
    def from_dict(cls, payload: dict[str, object]) -> AppleJWK:
        kid = str(payload["kid"])
        key = jwt.PyJWK.from_dict(payload).key
        if not isinstance(key, RSAPublicKey):
            raise AccountError("apple_identity_invalid", "Apple identity key is not RSA")
        return cls(kid=kid, key=key)


class AppleAuthorizationCodeExchange(Protocol):
    async def exchange(self, authorization_code: str) -> str: ...


class AppleJWKSource(Protocol):
    async def keys(self, *, force_refresh: bool = False) -> Sequence[AppleJWK]: ...


class AppleClientSecretSigner:
    def __init__(
        self,
        *,
        team_id: str,
        key_id: str,
        client_id: str,
        private_key_pem: str,
        now: Callable[[], datetime] | None = None,
        lifetime: timedelta = timedelta(minutes=5),
    ) -> None:
        if lifetime <= timedelta(0) or lifetime > MAX_APPLE_CLIENT_SECRET_LIFETIME:
            raise ValueError("Apple client secret lifetime must be positive and at most six months")
        key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=None,
        )
        if not isinstance(key, EllipticCurvePrivateKey) or not isinstance(key.curve, SECP256R1):
            raise ValueError("Apple client secret key must be a P-256 private key")
        self._team_id = team_id
        self._key_id = key_id
        self._client_id = client_id
        self._private_key = key
        self._now = now or (lambda: datetime.now(UTC))
        self._lifetime = lifetime

    def __call__(self) -> str:
        now = self._now()
        if now.tzinfo is None:
            raise RuntimeError("Apple client secret clock must be timezone-aware")
        issued_at = now.astimezone(UTC)
        return jwt.encode(
            {
                "iss": self._team_id,
                "iat": int(issued_at.timestamp()),
                "exp": int((issued_at + self._lifetime).timestamp()),
                "aud": "https://appleid.apple.com",
                "sub": self._client_id,
            },
            key=self._private_key,
            algorithm="ES256",
            headers={"kid": self._key_id},
        )


class HttpAppleAuthorizationCodeExchange:
    def __init__(
        self,
        *,
        client_id: str,
        client_secret: Callable[[], str],
        transport: httpx.AsyncBaseTransport | None = None,
        timeout_seconds: float = 2.0,
        max_response_bytes: int = 64 * 1024,
    ) -> None:
        self._client_id = client_id
        self._client_secret = client_secret
        self._transport = transport
        self._timeout_seconds = timeout_seconds
        self._max_response_bytes = max_response_bytes

    async def exchange(self, authorization_code: str) -> str:
        try:
            async with (
                httpx.AsyncClient(
                    transport=self._transport,
                    timeout=self._timeout_seconds,
                    follow_redirects=False,
                ) as client,
                client.stream(
                    "POST",
                    APPLE_TOKEN_URL,
                    data={
                        "client_id": self._client_id,
                        "client_secret": self._client_secret(),
                        "code": authorization_code,
                        "grant_type": "authorization_code",
                    },
                ) as response,
            ):
                if response.status_code != 200:
                    raise AccountError(
                        "apple_authorization_failed",
                        "Apple authorization code validation failed",
                    )
                declared_length = response.headers.get("content-length")
                if declared_length is not None:
                    try:
                        response_bytes = int(declared_length)
                    except ValueError as error:
                        raise AccountError(
                            "apple_authorization_invalid_response",
                            "Apple authorization response is invalid",
                        ) from error
                    if response_bytes > self._max_response_bytes:
                        raise AccountError(
                            "apple_authorization_invalid_response",
                            "Apple authorization response is invalid",
                        )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._max_response_bytes:
                        raise AccountError(
                            "apple_authorization_invalid_response",
                            "Apple authorization response is invalid",
                        )
        except AccountError:
            raise
        except httpx.HTTPError as error:
            raise AccountError(
                "apple_authorization_unavailable",
                "Apple authorization service is unavailable",
            ) from error
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AccountError(
                "apple_authorization_invalid_response",
                "Apple authorization response is invalid",
            ) from error
        identity_token = payload.get("id_token") if isinstance(payload, dict) else None
        if not isinstance(identity_token, str) or not identity_token:
            raise AccountError(
                "apple_authorization_invalid_response",
                "Apple authorization response is invalid",
            )
        return identity_token


class AppleJWKSProvider:
    def __init__(
        self,
        *,
        timeout_seconds: float = 2.0,
        cache_seconds: int = 3600,
        max_response_bytes: int = 64 * 1024,
        transport: httpx.AsyncBaseTransport | None = None,
        monotonic_now: Callable[[], float] = monotonic,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._cache_seconds = cache_seconds
        self._max_response_bytes = max_response_bytes
        self._transport = transport
        self._monotonic_now = monotonic_now
        self._cached_until = 0.0
        self._cached: list[AppleJWK] = []

    async def keys(self, *, force_refresh: bool = False) -> Sequence[AppleJWK]:
        now = self._monotonic_now()
        if not force_refresh and self._cached and now < self._cached_until:
            return self._cached
        try:
            async with (
                httpx.AsyncClient(
                    transport=self._transport,
                    timeout=self._timeout_seconds,
                    follow_redirects=False,
                ) as client,
                client.stream("GET", APPLE_JWKS_URL) as response,
            ):
                response.raise_for_status()
                declared_length = response.headers.get("content-length")
                if declared_length is not None and int(declared_length) > self._max_response_bytes:
                    raise AccountError(
                        "apple_identity_invalid",
                        "Apple JWKS response exceeded the allowed size",
                    )
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._max_response_bytes:
                        raise AccountError(
                            "apple_identity_invalid",
                            "Apple JWKS response exceeded the allowed size",
                        )
                cache_control = response.headers.get("cache-control", "")
        except AccountError:
            raise
        except (httpx.HTTPError, ValueError) as error:
            raise AccountError(
                "apple_identity_unavailable",
                "Apple identity keys are unavailable",
            ) from error
        try:
            payload = json.loads(body)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AccountError(
                "apple_identity_invalid", "Apple JWKS response is invalid"
            ) from error
        keys = payload.get("keys")
        if not isinstance(keys, list):
            raise AccountError("apple_identity_invalid", "Apple JWKS response is invalid")
        self._cached = [
            AppleJWK.from_dict(key)
            for key in keys
            if isinstance(key, dict) and key.get("alg") == "RS256"
        ]
        cache_seconds = self._cache_seconds
        for directive in cache_control.split(","):
            name, separator, value = directive.strip().partition("=")
            if separator and name.lower() == "max-age" and value.isdigit():
                cache_seconds = int(value)
                break
        self._cached_until = now + cache_seconds
        return self._cached


class PyJWTAppleIdentityVerifier:
    def __init__(
        self,
        *,
        jwks: AppleJWKSource,
        authorization_codes: AppleAuthorizationCodeExchange | None = None,
        allowed_audiences: frozenset[str],
        now: Callable[[], datetime] | None = None,
        issuer: str = "https://appleid.apple.com",
        leeway_seconds: int = 60,
    ) -> None:
        self._jwks = jwks
        self._authorization_codes = authorization_codes
        self._allowed_audiences = allowed_audiences
        self._issuer = issuer
        self._leeway_seconds = leeway_seconds
        self._now = now or (lambda: datetime.now(UTC))

    async def verify(
        self,
        identity_token: str,
        authorization_code: str,
    ) -> AppleIdentityClaims:
        if self._authorization_codes is None:
            raise AccountError(
                "apple_authorization_unavailable",
                "Apple authorization code validation is not configured",
            )
        exchanged_identity_token = await self._authorization_codes.exchange(authorization_code)
        claims = await self._decode(identity_token)
        exchanged_claims = await self._decode(exchanged_identity_token)
        if (
            exchanged_claims.subject != claims.subject
            or exchanged_claims.audience != claims.audience
            or not hmac.compare_digest(
                exchanged_claims.nonce or "",
                claims.nonce or "",
            )
        ):
            raise AccountError(
                "apple_authorization_mismatch",
                "Apple authorization result did not match the identity token",
            )
        return claims

    async def _decode(self, identity_token: str) -> AppleIdentityClaims:
        try:
            header = jwt.get_unverified_header(identity_token)
        except jwt.PyJWTError as error:
            raise AccountError(
                "apple_identity_invalid", "Apple identity token is invalid"
            ) from error
        if "jku" in header or "x5u" in header:
            raise AccountError("apple_identity_invalid", "Apple identity header is not allowed")
        if header.get("alg") != "RS256":
            raise AccountError("apple_identity_invalid", "Apple identity algorithm is not allowed")
        kid = str(header.get("kid", ""))
        key = next((jwk.key for jwk in await self._jwks.keys() if jwk.kid == kid), None)
        if key is None:
            refreshed = await self._jwks.keys(force_refresh=True)
            key = next((jwk.key for jwk in refreshed if jwk.kid == kid), None)
        if key is None:
            raise AccountError("apple_identity_invalid", "Apple identity key is unknown")
        try:
            payload: dict[str, Any] = jwt.decode(
                identity_token,
                key=key,
                algorithms=["RS256"],
                audience=list(self._allowed_audiences),
                issuer=self._issuer,
                leeway=self._leeway_seconds,
                options={
                    "require": ["iss", "aud", "exp", "iat", "sub"],
                    "verify_exp": False,
                    "verify_iat": False,
                },
            )
        except jwt.InvalidAlgorithmError as error:
            raise AccountError(
                "apple_identity_invalid", "Apple identity algorithm is not allowed"
            ) from error
        except jwt.PyJWTError as error:
            raise AccountError(
                "apple_identity_invalid", "Apple identity token is invalid"
            ) from error
        now = self._now().astimezone(UTC)
        expires_at = datetime.fromtimestamp(int(payload["exp"]), tz=UTC)
        issued_at = datetime.fromtimestamp(int(payload["iat"]), tz=UTC)
        if expires_at <= now - timedelta(seconds=self._leeway_seconds):
            raise AccountError("apple_identity_invalid", "Apple identity token is expired")
        if issued_at > now + timedelta(seconds=self._leeway_seconds):
            raise AccountError(
                "apple_identity_invalid", "Apple identity token was issued in the future"
            )
        return AppleIdentityClaims(
            issuer=str(payload["iss"]),
            audience=str(payload["aud"]),
            subject=str(payload["sub"]),
            expires_at=expires_at,
            issued_at=issued_at,
            nonce=str(payload["nonce"]) if "nonce" in payload else None,
        )
