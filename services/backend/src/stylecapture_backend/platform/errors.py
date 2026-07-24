from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorBody(BaseModel):
    code: str
    message: str
    request_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    error: ErrorBody


STABLE_ERROR_RESPONSES: dict[int | str, dict[str, Any]] = {
    401: {"model": ErrorEnvelope, "description": "A valid product session is required"},
    400: {"model": ErrorEnvelope, "description": "The request cannot be processed"},
    404: {"model": ErrorEnvelope, "description": "The requested resource was not found"},
    409: {"model": ErrorEnvelope, "description": "The request conflicts with stored state"},
    410: {"model": ErrorEnvelope, "description": "The upload token has expired"},
    413: {"model": ErrorEnvelope, "description": "The upload exceeds the allowed size"},
    415: {"model": ErrorEnvelope, "description": "The media type is not supported"},
    422: {"model": ErrorEnvelope, "description": "The request violates the API contract"},
    503: {"model": ErrorEnvelope, "description": "Processing is temporarily unavailable"},
}
