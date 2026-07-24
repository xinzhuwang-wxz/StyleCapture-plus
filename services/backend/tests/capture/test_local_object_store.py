from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from stylecapture_backend.features.capture.application import CaptureError
from stylecapture_backend.features.capture.infrastructure.object_store import LocalObjectStore
from stylecapture_backend.features.capture.ports import UploadRequest


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 24), color=(244, 114, 182)).save(buffer, format="PNG")
    return buffer.getvalue()


def request_for(body: bytes, *, content_type: str = "image/png") -> UploadRequest:
    return UploadRequest(
        file_name="衣服.png",
        content_type=content_type,
        byte_size=len(body),
        sha256=sha256(body).hexdigest(),
    )


def test_signed_upload_persists_validated_image_and_metadata(tmp_path: Path) -> None:
    now = datetime(2026, 7, 25, 3, 30, tzinfo=UTC)
    store = LocalObjectStore(
        root=tmp_path,
        signing_secret="test-signing-secret-with-enough-entropy",
        public_upload_prefix="/v1/uploads",
        now=lambda: now,
    )
    body = png_bytes()

    prepared = store.prepare_upload(request_for(body), ttl=timedelta(minutes=5))
    stored = store.accept_upload(
        prepared.token,
        body=body,
        content_type="image/png",
    )

    assert stored.object_key == prepared.object_key
    assert stored.sha256 == sha256(body).hexdigest()
    assert stored.width == 32
    assert stored.height == 24
    assert store.read(stored.object_key) == body


@pytest.mark.parametrize(
    ("mutation", "expected_code"),
    [
        ("wrong_hash", "upload_hash_mismatch"),
        ("wrong_size", "upload_size_mismatch"),
        ("wrong_type", "upload_content_type_mismatch"),
    ],
)
def test_signed_upload_rejects_bytes_that_do_not_match_the_contract(
    tmp_path: Path,
    mutation: str,
    expected_code: str,
) -> None:
    now = datetime(2026, 7, 25, 3, 30, tzinfo=UTC)
    store = LocalObjectStore(
        root=tmp_path,
        signing_secret="test-signing-secret-with-enough-entropy",
        now=lambda: now,
    )
    body = png_bytes()
    request = request_for(body)
    if mutation == "wrong_hash":
        request = UploadRequest(
            file_name=request.file_name,
            content_type=request.content_type,
            byte_size=request.byte_size,
            sha256="a" * 64,
        )
    elif mutation == "wrong_size":
        request = UploadRequest(
            file_name=request.file_name,
            content_type=request.content_type,
            byte_size=request.byte_size + 1,
            sha256=request.sha256,
        )
    prepared = store.prepare_upload(request)

    with pytest.raises(CaptureError) as error:
        store.accept_upload(
            prepared.token,
            body=body,
            content_type="image/jpeg" if mutation == "wrong_type" else "image/png",
        )

    assert error.value.code == expected_code


def test_signed_upload_rejects_expired_token_without_writing_source(tmp_path: Path) -> None:
    current = datetime(2026, 7, 25, 3, 30, tzinfo=UTC)
    store = LocalObjectStore(
        root=tmp_path,
        signing_secret="test-signing-secret-with-enough-entropy",
        now=lambda: current,
    )
    body = png_bytes()
    prepared = store.prepare_upload(request_for(body), ttl=timedelta(seconds=10))
    current += timedelta(seconds=11)

    with pytest.raises(CaptureError) as error:
        store.accept_upload(prepared.token, body=body, content_type="image/png")

    assert error.value.code == "upload_token_expired"
    assert list(tmp_path.rglob("*")) == []


def test_prepare_rejects_unsupported_mime_before_issuing_a_token(tmp_path: Path) -> None:
    body = b"not-an-image"
    store = LocalObjectStore(
        root=tmp_path,
        signing_secret="test-signing-secret-with-enough-entropy",
    )

    with pytest.raises(CaptureError) as error:
        store.prepare_upload(request_for(body, content_type="application/pdf"))

    assert error.value.code == "unsupported_image_type"
