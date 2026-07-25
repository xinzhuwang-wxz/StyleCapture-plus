from __future__ import annotations

import base64
import fcntl
import hmac
import json
import secrets
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import UUID

from PIL import Image, UnidentifiedImageError
from pillow_heif import register_heif_opener  # type: ignore[import-untyped]

from stylecapture_backend.features.capture.application import CaptureError
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.capture.ports import (
    PreparedUpload,
    StoredObject,
    UploadRequest,
)

register_heif_opener()

ALLOWED_MIME_EXTENSIONS = {
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
FORMAT_MIME_TYPES = {
    "HEIF": frozenset({"image/heic", "image/heif"}),
    "JPEG": frozenset({"image/jpeg"}),
    "PNG": frozenset({"image/png"}),
    "WEBP": frozenset({"image/webp"}),
}
HEIF_BRANDS = frozenset({b"heic", b"heix", b"hevc", b"hevx", b"heim", b"heis", b"mif1", b"msf1"})


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _base64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _matches_image_signature(body: bytes, content_type: str) -> bool:
    if content_type == "image/jpeg":
        return body.startswith(b"\xff\xd8\xff")
    if content_type == "image/png":
        return body.startswith(b"\x89PNG\r\n\x1a\n")
    if content_type == "image/webp":
        return len(body) >= 12 and body.startswith(b"RIFF") and body[8:12] == b"WEBP"
    if content_type in {"image/heic", "image/heif"}:
        return len(body) >= 12 and body[4:8] == b"ftyp" and body[8:12] in HEIF_BRANDS
    return False


class LocalObjectStore:
    def __init__(
        self,
        *,
        root: Path,
        signing_secret: str,
        public_upload_prefix: str = "/v1/uploads",
        max_upload_bytes: int = 20 * 1024 * 1024,
        max_image_pixels: int = 36_000_000,
        daily_upload_bytes_per_owner: int = 200 * 1024 * 1024,
        max_unattached_uploads_per_owner: int = 10,
        max_total_user_upload_bytes: int = 2 * 1024 * 1024 * 1024,
        unattached_upload_ttl: timedelta = timedelta(hours=24),
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if len(signing_secret) < 24:
            raise ValueError("upload signing secret must be at least 24 characters")
        self._root = root.resolve()
        self._secret = signing_secret.encode("utf-8")
        self._public_upload_prefix = public_upload_prefix.rstrip("/")
        self._max_upload_bytes = max_upload_bytes
        self._max_image_pixels = max_image_pixels
        self._daily_upload_bytes_per_owner = daily_upload_bytes_per_owner
        self._max_unattached_uploads_per_owner = max_unattached_uploads_per_owner
        self._max_total_user_upload_bytes = max_total_user_upload_bytes
        self._unattached_upload_ttl = unattached_upload_ttl
        self._now = now or (lambda: datetime.now(UTC))

    def prepare_upload(
        self,
        request: UploadRequest,
        *,
        ttl: timedelta = timedelta(minutes=10),
    ) -> PreparedUpload:
        if request.content_type not in ALLOWED_MIME_EXTENSIONS:
            raise CaptureError(
                "unsupported_image_type",
                "Supported image types are JPEG, PNG, WebP, HEIC, and HEIF",
            )
        if request.byte_size <= 0 or request.byte_size > self._max_upload_bytes:
            raise CaptureError(
                "upload_size_invalid",
                f"Image size must be between 1 and {self._max_upload_bytes} bytes",
                details={"max_bytes": self._max_upload_bytes},
            )
        self._validate_sha256(request.sha256)
        if ttl <= timedelta(0) or ttl > timedelta(hours=1):
            raise CaptureError(
                "upload_ttl_invalid",
                "Upload token lifetime must be between 1 second and 1 hour",
            )
        now = self._aware_now()
        expires_at = now + ttl
        object_key = (
            f"originals/{now:%Y/%m/%d}/{secrets.token_hex(16)}"
            f"{ALLOWED_MIME_EXTENSIONS[request.content_type]}"
        )
        payload = {
            "byte_size": request.byte_size,
            "content_type": request.content_type,
            "expires_at": int(expires_at.timestamp()),
            "object_key": object_key,
            "owner_id": str(request.owner_id),
            "sha256": request.sha256,
        }
        encoded_payload = _base64url_encode(
            json.dumps(payload, ensure_ascii=True, separators=(",", ":"), sort_keys=True).encode(
                "utf-8"
            )
        )
        signature = _base64url_encode(
            hmac.digest(self._secret, encoded_payload.encode("ascii"), "sha256")
        )
        token = f"{encoded_payload}.{signature}"
        return PreparedUpload(
            upload_url=self._public_upload_prefix,
            object_key=object_key,
            token=token,
            expires_at=expires_at,
        )

    def accept_upload(
        self,
        token: str,
        *,
        body: bytes,
        content_type: str,
    ) -> StoredObject:
        payload = self._decode_token(token)
        expected_type = str(payload["content_type"])
        if content_type != expected_type:
            raise CaptureError(
                "upload_content_type_mismatch",
                "Upload Content-Type does not match the prepared upload",
            )
        expected_size = int(payload["byte_size"])
        if len(body) != expected_size:
            raise CaptureError(
                "upload_size_mismatch",
                "Uploaded byte length does not match the prepared upload",
            )
        actual_hash = sha256(body).hexdigest()
        if not hmac.compare_digest(actual_hash, str(payload["sha256"])):
            raise CaptureError(
                "upload_hash_mismatch",
                "Uploaded bytes do not match the prepared SHA-256",
            )
        width, height = self._validate_image(body, expected_type)
        token_claim_path = self._claim_upload_token(token)
        stored = StoredObject(
            owner_id=UUID(str(payload["owner_id"])),
            object_key=str(payload["object_key"]),
            content_type=expected_type,
            byte_size=len(body),
            sha256=actual_hash,
            width=width,
            height=height,
        )
        try:
            assert stored.owner_id is not None
            with self._upload_quota_lock():
                self._collect_expired_unattached_locked()
                self._enforce_upload_quota(stored.owner_id, stored.byte_size)
                self._persist(
                    stored,
                    body,
                    metadata={
                        "attached_at": None,
                        "created_at": self._aware_now().isoformat(),
                        "origin": "user_upload",
                    },
                )
        except Exception:
            token_claim_path.unlink(missing_ok=True)
            raise
        return stored

    def mark_attached(self, object_key: str, owner_id: UUID) -> None:
        metadata_path = self._metadata_path(object_key)
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise KeyError(object_key) from error
        if payload.get("owner_id") != str(owner_id):
            raise CaptureError("upload_not_found", "The private upload is unavailable")
        if payload.get("origin") != "user_upload" or payload.get("attached_at") is not None:
            return
        payload["attached_at"] = self._aware_now().isoformat()
        self._write_metadata(metadata_path, payload)

    def discard_unattached_upload(self, object_key: str, owner_id: UUID) -> None:
        metadata_path = self._metadata_path(object_key)
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise CaptureError("upload_not_found", "The private upload is unavailable") from error
        if payload.get("owner_id") != str(owner_id) or payload.get("origin") != "user_upload":
            raise CaptureError("upload_not_found", "The private upload is unavailable")
        if payload.get("attached_at") is not None:
            raise CaptureError(
                "upload_already_attached",
                "上传已进入处理。不能再从临时上传入口删除",
            )
        self.delete(object_key)

    def describe(self, object_key: str) -> StoredObject:
        metadata_path = self._metadata_path(object_key)
        try:
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise KeyError(object_key) from error
        return StoredObject(
            owner_id=(
                UUID(str(payload["owner_id"])) if payload.get("owner_id") is not None else None
            ),
            object_key=object_key,
            content_type=str(payload["content_type"]),
            byte_size=int(payload["byte_size"]),
            sha256=str(payload["sha256"]),
            width=int(payload["width"]),
            height=int(payload["height"]),
        )

    def read(self, object_key: str) -> bytes:
        return self._object_path(object_key).read_bytes()

    def read_image(self, object_key: str) -> ImagePayload:
        stored = self.describe(object_key)
        return ImagePayload(
            object_key=stored.object_key,
            content_type=stored.content_type,
            body=self.read(object_key),
            sha256=stored.sha256,
        )

    def write_derived_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload:
        if image.content_type not in {"image/png", "image/webp", "image/jpeg"}:
            raise CaptureError(
                "derived_image_type_invalid",
                "Derived display assets must be PNG, WebP, or JPEG",
            )
        actual_hash = sha256(image.body).hexdigest()
        if not hmac.compare_digest(actual_hash, image.sha256):
            raise CaptureError(
                "derived_image_hash_mismatch",
                "Derived display asset hash does not match its bytes",
            )
        width, height = self._validate_image(image.body, image.content_type)
        extension = ALLOWED_MIME_EXTENSIONS[image.content_type]
        object_key = f"{self._validate_derived_prefix(prefix)}/{actual_hash}{extension}"
        stored = StoredObject(
            owner_id=owner_id,
            object_key=object_key,
            content_type=image.content_type,
            byte_size=len(image.body),
            sha256=actual_hash,
            width=width,
            height=height,
        )
        self._persist(stored, image.body)
        return ImagePayload(
            object_key=object_key,
            content_type=image.content_type,
            body=image.body,
            sha256=actual_hash,
        )

    def write_private_source_image(
        self,
        image: ImagePayload,
        *,
        owner_id: UUID,
        prefix: str,
    ) -> ImagePayload:
        if image.content_type not in ALLOWED_MIME_EXTENSIONS:
            raise CaptureError(
                "source_image_type_invalid",
                "Source assets must be JPEG, PNG, WebP, HEIC, or HEIF",
            )
        actual_hash = sha256(image.body).hexdigest()
        if not hmac.compare_digest(actual_hash, image.sha256):
            raise CaptureError(
                "source_image_hash_mismatch",
                "Source asset hash does not match its bytes",
            )
        width, height = self._validate_image(image.body, image.content_type)
        extension = ALLOWED_MIME_EXTENSIONS[image.content_type]
        object_key = f"{self._validate_originals_prefix(prefix)}/{actual_hash}{extension}"
        stored = StoredObject(
            owner_id=owner_id,
            object_key=object_key,
            content_type=image.content_type,
            byte_size=len(image.body),
            sha256=actual_hash,
            width=width,
            height=height,
        )
        self._persist(stored, image.body)
        return ImagePayload(
            object_key=object_key,
            content_type=image.content_type,
            body=image.body,
            sha256=actual_hash,
        )

    def delete(self, object_key: str) -> None:
        object_path = self._object_path(object_key)
        metadata_path = self._metadata_path(object_key)
        object_path.unlink(missing_ok=True)
        metadata_path.unlink(missing_ok=True)

    def _decode_token(self, token: str) -> dict[str, Any]:
        try:
            encoded_payload, supplied_signature = token.split(".", maxsplit=1)
            expected_signature = _base64url_encode(
                hmac.digest(self._secret, encoded_payload.encode("ascii"), "sha256")
            )
            if not hmac.compare_digest(supplied_signature, expected_signature):
                raise ValueError("signature mismatch")
            payload = json.loads(_base64url_decode(encoded_payload))
            required = {
                "byte_size",
                "content_type",
                "expires_at",
                "object_key",
                "owner_id",
                "sha256",
            }
            if set(payload) != required:
                raise ValueError("unexpected token fields")
            expires_at = datetime.fromtimestamp(int(payload["expires_at"]), tz=UTC)
            UUID(str(payload["owner_id"]))
        except (TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as error:
            raise CaptureError("upload_token_invalid", "Upload token is invalid") from error
        if self._aware_now() > expires_at:
            raise CaptureError("upload_token_expired", "Upload token has expired")
        self._validate_object_key(str(payload["object_key"]))
        self._validate_sha256(str(payload["sha256"]))
        return payload

    def _claim_upload_token(self, token: str) -> Path:
        claim_path = self._root / ".upload-tokens" / f"{sha256(token.encode('utf-8')).hexdigest()}.json"
        claim_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with claim_path.open("x", encoding="utf-8") as handle:
                json.dump(
                    {
                        "claimed_at": int(self._aware_now().timestamp()),
                    },
                    handle,
                    separators=(",", ":"),
                    sort_keys=True,
                )
        except FileExistsError as error:
            raise CaptureError(
                "upload_token_consumed",
                "Upload token has already been used",
            ) from error
        return claim_path

    def _validate_image(self, body: bytes, content_type: str) -> tuple[int, int]:
        if not _matches_image_signature(body, content_type):
            raise CaptureError(
                "image_format_mismatch",
                "Image signature does not match Content-Type",
            )
        try:
            with Image.open(BytesIO(body)) as image:
                image_format = image.format
                width, height = image.size
                image.verify()
        except (Image.DecompressionBombError, UnidentifiedImageError, OSError, ValueError) as error:
            raise CaptureError(
                "image_decode_failed", "Uploaded bytes are not a valid image"
            ) from error
        if (
            image_format not in FORMAT_MIME_TYPES
            or content_type not in FORMAT_MIME_TYPES[image_format]
        ):
            raise CaptureError(
                "image_format_mismatch",
                "Decoded image format does not match Content-Type",
            )
        if width <= 0 or height <= 0 or width * height > self._max_image_pixels:
            raise CaptureError(
                "image_dimensions_invalid",
                "Image dimensions are empty or exceed the pixel limit",
                details={"max_pixels": self._max_image_pixels},
            )
        return width, height

    def _persist(
        self,
        stored: StoredObject,
        body: bytes,
        *,
        metadata: dict[str, object] | None = None,
    ) -> None:
        object_path = self._object_path(stored.object_key)
        metadata_path = self._metadata_path(stored.object_key)
        object_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        if object_path.exists():
            if sha256(object_path.read_bytes()).hexdigest() != stored.sha256:
                raise CaptureError(
                    "upload_object_conflict",
                    "The upload key already contains different bytes",
                )
            return
        nonce = secrets.token_hex(8)
        temporary_path = object_path.with_suffix(f"{object_path.suffix}.uploading-{nonce}")
        temporary_metadata_path = metadata_path.with_suffix(f".json.uploading-{nonce}")
        try:
            temporary_path.write_bytes(body)
            temporary_path.replace(object_path)
            payload: dict[str, object] = {
                "byte_size": stored.byte_size,
                "content_type": stored.content_type,
                "height": stored.height,
                "object_key": stored.object_key,
                "owner_id": str(stored.owner_id),
                "sha256": stored.sha256,
                "width": stored.width,
            }
            payload.update(metadata or {})
            temporary_metadata_path.write_text(
                json.dumps(payload, separators=(",", ":"), sort_keys=True),
                encoding="utf-8",
            )
            temporary_metadata_path.replace(metadata_path)
        finally:
            temporary_path.unlink(missing_ok=True)
            temporary_metadata_path.unlink(missing_ok=True)

    @contextmanager
    def _upload_quota_lock(self) -> Iterator[None]:
        lock_path = self._root / ".upload-quota.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _user_upload_metadata(self) -> list[tuple[Path, dict[str, Any]]]:
        metadata_root = self._root / ".metadata"
        if not metadata_root.exists():
            return []
        records: list[tuple[Path, dict[str, Any]]] = []
        for path in metadata_root.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if payload.get("origin") == "user_upload":
                records.append((path, payload))
        return records

    def _collect_expired_unattached_locked(self) -> None:
        cutoff = self._aware_now() - self._unattached_upload_ttl
        for metadata_path, payload in self._user_upload_metadata():
            if payload.get("attached_at") is not None:
                continue
            try:
                created_at = datetime.fromisoformat(str(payload["created_at"])).astimezone(UTC)
                object_key = str(payload["object_key"])
            except (KeyError, TypeError, ValueError):
                continue
            if created_at <= cutoff:
                self._object_path(object_key).unlink(missing_ok=True)
                metadata_path.unlink(missing_ok=True)

    def _enforce_upload_quota(self, owner_id: UUID, incoming_bytes: int) -> None:
        now = self._aware_now()
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        owner_bytes_today = 0
        owner_unattached = 0
        total_bytes = 0
        for _, payload in self._user_upload_metadata():
            byte_size = int(payload.get("byte_size", 0))
            total_bytes += byte_size
            if payload.get("owner_id") != str(owner_id):
                continue
            if payload.get("attached_at") is None:
                owner_unattached += 1
            try:
                created_at = datetime.fromisoformat(str(payload["created_at"])).astimezone(UTC)
            except (KeyError, TypeError, ValueError):
                continue
            if created_at >= day_start:
                owner_bytes_today += byte_size
        if owner_unattached >= self._max_unattached_uploads_per_owner:
            raise CaptureError(
                "upload_unattached_quota_exceeded",
                "请先完成或删除已有上传后再继续",
            )
        if owner_bytes_today + incoming_bytes > self._daily_upload_bytes_per_owner:
            raise CaptureError("upload_daily_quota_exceeded", "今日上传额度已用完。请明天再试")
        if total_bytes + incoming_bytes > self._max_total_user_upload_bytes:
            raise CaptureError("upload_capacity_exceeded", "上传空间暂时已满。请稍后再试")

    def _write_metadata(self, path: Path, payload: dict[str, Any]) -> None:
        temporary = path.with_suffix(f".json.updating-{secrets.token_hex(8)}")
        try:
            temporary.write_text(
                json.dumps(payload, separators=(",", ":"), sort_keys=True),
                encoding="utf-8",
            )
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)

    def _object_path(self, object_key: str) -> Path:
        self._validate_object_key(object_key)
        candidate = (self._root / object_key).resolve()
        if not candidate.is_relative_to(self._root):
            raise CaptureError("object_key_invalid", "Object key escapes the upload root")
        return candidate

    def _metadata_path(self, object_key: str) -> Path:
        digest = sha256(object_key.encode("utf-8")).hexdigest()
        return self._root / ".metadata" / f"{digest}.json"

    @staticmethod
    def _validate_object_key(object_key: str) -> None:
        path = PurePosixPath(object_key)
        if (
            path.is_absolute()
            or ".." in path.parts
            or not (object_key.startswith("originals/") or object_key.startswith("derived/"))
            or "\\" in object_key
        ):
            raise CaptureError("object_key_invalid", "Object key is invalid")

    @staticmethod
    def _validate_derived_prefix(prefix: str) -> str:
        normalized = prefix.strip().strip("/")
        path = PurePosixPath(normalized)
        if (
            not normalized.startswith("derived/")
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in normalized
        ):
            raise CaptureError("object_key_invalid", "Derived object prefix is invalid")
        return normalized

    @staticmethod
    def _validate_originals_prefix(prefix: str) -> str:
        normalized = prefix.strip().strip("/")
        path = PurePosixPath(normalized)
        if (
            not normalized.startswith("originals/")
            or path.is_absolute()
            or ".." in path.parts
            or "\\" in normalized
        ):
            raise CaptureError("object_key_invalid", "Source object prefix is invalid")
        return normalized

    @staticmethod
    def _validate_sha256(value: str) -> None:
        if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
            raise CaptureError("sha256_invalid", "SHA-256 must be lowercase hexadecimal")

    def _aware_now(self) -> datetime:
        value = self._now()
        if value.tzinfo is None:
            raise RuntimeError("object store clock must return a timezone-aware datetime")
        return value.astimezone(UTC)
