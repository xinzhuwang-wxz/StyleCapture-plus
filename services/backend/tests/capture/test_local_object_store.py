from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from threading import Barrier
from unittest.mock import patch
from uuid import UUID

import pytest
from PIL import Image
from stylecapture_backend.features.capture.application import CaptureError
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.capture.infrastructure.object_store import LocalObjectStore
from stylecapture_backend.features.capture.ports import UploadRequest


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 24), color=(244, 114, 182)).save(buffer, format="PNG")
    return buffer.getvalue()


OWNER_ID = UUID("11111111-1111-4111-8111-111111111111")


def request_for(body: bytes, *, content_type: str = "image/png") -> UploadRequest:
    return UploadRequest(
        owner_id=OWNER_ID,
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
    assert prepared.upload_url == "/v1/uploads"
    assert prepared.token not in prepared.upload_url
    stored = store.accept_upload(
        prepared.token,
        body=body,
        content_type="image/png",
    )

    assert stored.object_key == prepared.object_key
    assert stored.owner_id == OWNER_ID
    assert stored.sha256 == sha256(body).hexdigest()
    assert stored.width == 32
    assert stored.height == 24
    assert store.read(stored.object_key) == body


def test_derived_display_asset_is_content_addressed_and_readable(tmp_path: Path) -> None:
    store = LocalObjectStore(
        root=tmp_path,
        signing_secret="test-signing-secret-with-enough-entropy",
    )
    body = png_bytes()

    stored = store.write_derived_image(
        ImagePayload(
            object_key="originals/feed/frame.png#selection=hat",
            content_type="image/png",
            body=body,
            sha256=sha256(body).hexdigest(),
        ),
        owner_id=OWNER_ID,
        prefix="derived/items",
    )

    assert stored.object_key == f"derived/items/{sha256(body).hexdigest()}.png"
    assert store.describe(stored.object_key).owner_id == OWNER_ID
    assert store.read_image(stored.object_key) == stored


def test_concurrent_upload_replay_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = LocalObjectStore(
        root=tmp_path,
        signing_secret="test-signing-secret-with-enough-entropy",
    )
    body = png_bytes()
    prepared = store.prepare_upload(request_for(body))
    barrier = Barrier(2)
    original_write_bytes = Path.write_bytes

    def synchronized_write(path: Path, data: bytes) -> int:
        result = original_write_bytes(path, data)
        if ".uploading" in path.name:
            barrier.wait(timeout=2)
        return result

    monkeypatch.setattr(Path, "write_bytes", synchronized_write)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: store.accept_upload(
                    prepared.token,
                    body=body,
                    content_type="image/png",
                ),
                range(2),
            )
        )

    assert results == [results[0], results[0]]
    assert store.read(results[0].object_key) == body


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
            owner_id=request.owner_id,
            file_name=request.file_name,
            content_type=request.content_type,
            byte_size=request.byte_size,
            sha256="a" * 64,
        )
    elif mutation == "wrong_size":
        request = UploadRequest(
            owner_id=request.owner_id,
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


def test_mismatched_magic_bytes_are_rejected_before_image_parser(tmp_path: Path) -> None:
    body = b"8BPS" + b"\x00" * 128
    store = LocalObjectStore(
        root=tmp_path,
        signing_secret="test-signing-secret-with-enough-entropy",
    )
    prepared = store.prepare_upload(request_for(body))

    with (
        patch(
            "stylecapture_backend.features.capture.infrastructure.object_store.Image.open",
            side_effect=AssertionError("image parser must not receive mismatched bytes"),
        ),
        pytest.raises(CaptureError) as error,
    ):
        store.accept_upload(prepared.token, body=body, content_type="image/png")

    assert error.value.code == "image_format_mismatch"
