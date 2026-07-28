from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import asdict
from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, status
from pydantic import BaseModel, Field
from stylecapture_backend.features.account.application import (
    AccountApplication,
    AccountDeletionCommand,
    AuthenticateWithAppleCommand,
    RefreshSessionCommand,
)
from stylecapture_backend.platform.errors import STABLE_ERROR_RESPONSES


class AppleAuthBody(BaseModel):
    identity_token: str = Field(min_length=1)
    authorization_code: str = Field(min_length=1)
    nonce: str = Field(min_length=1, max_length=256)
    device_name: str | None = Field(default=None, max_length=120)


class RefreshBody(BaseModel):
    refresh_token: str = Field(min_length=1)


class AuthTokenResponse(BaseModel):
    account_subject: UUID
    access_token: str
    refresh_token: str
    access_expires_at: datetime
    token_type: str


class DeletionResponse(BaseModel):
    account_subject: UUID
    status: str
    requested_at: datetime
    updated_at: datetime


def _bearer_token(authorization: str | None) -> str | None:
    if authorization is None:
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token


def build_account_router(
    accounts: AccountApplication,
    *,
    current_user: Callable[..., Awaitable[UUID]],
) -> APIRouter:
    router = APIRouter(prefix="/v1")
    principal = Depends(current_user)

    @router.post(
        "/auth/apple",
        response_model=AuthTokenResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def authenticate_with_apple(
        body: AppleAuthBody,
        subject_id: UUID = principal,
    ) -> AuthTokenResponse:
        tokens = await accounts.authenticate_with_apple(
            AuthenticateWithAppleCommand(
                anonymous_subject=subject_id,
                identity_token=body.identity_token,
                authorization_code=body.authorization_code,
                nonce=body.nonce,
                device_name=body.device_name,
            )
        )
        return AuthTokenResponse(**asdict(tokens))

    @router.post(
        "/auth/refresh",
        response_model=AuthTokenResponse,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def refresh_session(body: RefreshBody) -> AuthTokenResponse:
        tokens = await accounts.refresh_session(
            RefreshSessionCommand(refresh_token=body.refresh_token)
        )
        return AuthTokenResponse(**asdict(tokens))

    @router.post(
        "/account/delete",
        response_model=DeletionResponse,
        status_code=status.HTTP_202_ACCEPTED,
        responses=STABLE_ERROR_RESPONSES,
    )
    async def delete_account(
        authorization: str | None = Header(default=None),
        idempotency_key: str = Header(
            min_length=8,
            max_length=128,
            alias="Idempotency-Key",
        ),
    ) -> DeletionResponse:
        token = _bearer_token(authorization)
        if token is None:
            from stylecapture_backend.features.account.application import AccountError

            raise AccountError("session_invalid", "Session is invalid")
        deletion = await accounts.request_account_deletion_with_access_token(
            AccountDeletionCommand(
                access_token=token,
                idempotency_key=idempotency_key,
            )
        )
        return DeletionResponse(
            account_subject=deletion.subject_id,
            status=deletion.status,
            requested_at=deletion.requested_at,
            updated_at=deletion.updated_at,
        )

    return router
