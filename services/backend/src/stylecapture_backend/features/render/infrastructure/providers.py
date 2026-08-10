from __future__ import annotations

import asyncio
import base64
import ipaddress
import json
import os
import socket
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.render.domain import RenderProviderTrace
from stylecapture_backend.features.render.ports import (
    GeneratedImage,
    RenderProviderError,
    RenderProviderUnavailable,
)

SUPPORTED_OUTPUT_TYPES = frozenset({"image/png", "image/jpeg", "image/webp"})


class DoubaoVirtualTryOnSkillGenerator:
    def __init__(
        self,
        *,
        skill_path: Path,
        api_key: str,
        understanding_model: str,
        image_model: str,
        timeout_seconds: float = 1800,
        max_attempts: int = 2,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("try-on Skill timeout must be positive")
        if max_attempts not in {1, 2, 3}:
            raise ValueError("try-on Skill attempts must be between 1 and 3")
        if not understanding_model.strip() or not image_model.strip():
            raise ValueError("try-on Skill model configuration must not be empty")
        self._skill_path = skill_path
        self._api_key = api_key.strip()
        self._understanding_model = understanding_model.strip()
        self._image_model = image_model.strip()
        self._timeout = timeout_seconds
        self._max_attempts = max_attempts

    async def try_on(
        self,
        *,
        model_image: ImagePayload,
        outfit_board: ImagePayload,
    ) -> GeneratedImage:
        if not self._api_key:
            raise RenderProviderUnavailable("Doubao try-on Skill API key is not configured")
        if not self._skill_path.is_file():
            raise RenderProviderUnavailable("Doubao try-on Skill entry point is unavailable")

        with tempfile.TemporaryDirectory(prefix="stylecapture-try-on-") as temporary:
            workspace = Path(temporary)
            person_path = workspace / _skill_input_name("person", model_image.content_type)
            outfit_path = workspace / _skill_input_name("outfit", outfit_board.content_type)
            output_dir = workspace / "output"
            person_path.write_bytes(model_image.body)
            outfit_path.write_bytes(outfit_board.body)
            environment = os.environ.copy()
            environment["ARK_API_KEY"] = self._api_key
            process: asyncio.subprocess.Process | None = None
            try:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    "-B",
                    str(self._skill_path),
                    str(person_path),
                    str(outfit_path),
                    "--output-dir",
                    str(output_dir),
                    "--max-attempts",
                    str(self._max_attempts),
                    "--size",
                    "2K",
                    "--understanding-model",
                    self._understanding_model,
                    "--image-model",
                    self._image_model,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=environment,
                )
                await asyncio.wait_for(
                    process.communicate(),
                    timeout=self._timeout,
                )
            except TimeoutError as error:
                if process is not None:
                    process.kill()
                    await process.wait()
                raise RenderProviderUnavailable("Doubao try-on Skill timed out") from error
            except OSError as error:
                raise RenderProviderUnavailable("Doubao try-on Skill could not start") from error

            if process is None:
                raise RenderProviderUnavailable("Doubao try-on Skill could not start")
            manifest = _read_skill_manifest(output_dir / "manifest.json")
            delivery_eligible = (
                manifest.get("delivery_eligible") is True
                or manifest.get("hard_pass") is True
                or manifest.get("release_eligible") is True
            )
            if process.returncode != 0 or not delivery_eligible:
                if manifest.get("quality_status") == "input_rejected":
                    raise RenderProviderError(
                        "try_on_source_photo_ineligible",
                        _skill_user_message(manifest),
                        retryable=False,
                    )
                raise RenderProviderError(
                    "try_on_identity_audit_failed",
                    "Doubao try-on Skill did not pass its quality audit",
                    retryable=False,
                )
            result_path = output_dir / "result.jpg"
            if not result_path.is_file():
                raise RenderProviderError(
                    "render_provider_schema_invalid",
                    "Doubao try-on Skill returned no result image",
                    retryable=False,
                )
            body = result_path.read_bytes()
            if not body:
                raise RenderProviderError(
                    "render_provider_schema_invalid",
                    "Doubao try-on Skill returned an empty result image",
                    retryable=False,
                )
            content_type = _image_content_type(body)
            if content_type is None:
                raise RenderProviderError(
                    "render_provider_schema_invalid",
                    "Doubao try-on Skill returned an invalid result image",
                    retryable=False,
                )
            return GeneratedImage(
                body=body,
                content_type=content_type,
                sha256=sha256(body).hexdigest(),
                provider_trace=RenderProviderTrace(
                    provider="doubao_virtual_try_on_skill",
                    model="audited_identity_locked_workflow",
                    parameters={
                        "skill_version": "1.4.3",
                        "selected_attempt": manifest.get("selected_attempt"),
                        "hard_pass": manifest.get("hard_pass") is True,
                        "audit_release_eligible": (
                            manifest.get("audit_release_eligible") is True
                        ),
                        "delivery_eligible": delivery_eligible,
                        "quality_status": manifest.get("quality_status"),
                        "audit_summary": manifest.get("selected_audit_summary"),
                        "max_attempts": self._max_attempts,
                    },
                ),
            )


def _skill_input_name(stem: str, content_type: str) -> str:
    suffix = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }.get(content_type)
    if suffix is None:
        raise ValueError("try-on Skill input image type is unsupported")
    return f"{stem}{suffix}"


def _image_content_type(body: bytes) -> str | None:
    if body.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if body.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if len(body) >= 12 and body.startswith(b"RIFF") and body[8:12] == b"WEBP":
        return "image/webp"
    return None


def _read_skill_manifest(path: Path) -> dict[str, object]:
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _skill_user_message(manifest: dict[str, object]) -> str:
    message = manifest.get("user_message")
    if isinstance(message, str) and message.strip():
        return message.strip()[:240]
    return "照片中的身体取景不完整，请重新上传一张至少连续露出颈肩、躯干、髋部、膝盖和小腿的照片。"  # noqa: RUF001


class LiteLLMImageGenerator:
    def __init__(
        self,
        *,
        capability_alias: str,
        gateway_base_url: str,
        gateway_api_key: str,
        timeout_seconds: float = 45,
        download_max_bytes: int = 20 * 1024 * 1024,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not capability_alias.strip():
            raise ValueError("image generation capability alias must not be empty")
        if not gateway_base_url.strip():
            raise ValueError("image generation gateway base URL must not be empty")
        if not gateway_api_key.strip():
            raise ValueError("image generation gateway API key must not be empty")
        if timeout_seconds <= 0:
            raise ValueError("image generation timeout must be positive")
        if download_max_bytes <= 0:
            raise ValueError("image generation download limit must be positive")
        self._alias = capability_alias.strip()
        self._base_url = gateway_base_url.rstrip("/")
        self._api_key = gateway_api_key
        self._timeout = timeout_seconds
        self._download_max_bytes = download_max_bytes
        self._transport = transport

    async def generate(
        self,
        *,
        prompt: str,
        images: Sequence[ImagePayload],
        size: str = "1024x1024",
        seed: int | None = None,
        guidance_scale: float | None = None,
    ) -> GeneratedImage:
        if not prompt.strip():
            raise ValueError("image generation prompt must not be empty")
        if seed is not None and not 0 <= seed <= 2_147_483_647:
            raise ValueError("image generation seed must be between 0 and 2147483647")
        if guidance_scale is not None and not 1 <= guidance_scale <= 10:
            raise ValueError("image generation guidance scale must be between 1 and 10")
        payload: dict[str, object] = {
            "model": self._alias,
            "prompt": prompt.strip(),
            "size": size,
            "response_format": "b64_json",
            "sequential_image_generation": "disabled",
            "watermark": False,
        }
        if images:
            payload["image"] = [_data_url(image) for image in images]
        if seed is not None:
            payload["seed"] = seed
        if guidance_scale is not None:
            payload["guidance_scale"] = guidance_scale
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            try:
                response = await client.post(
                    f"{self._base_url}/images/generations",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                response.raise_for_status()
                decoded = response.json()
                image = await _image_from_openai_response(
                    decoded,
                    client=client,
                    download_max_bytes=self._download_max_bytes,
                    resolve_download_host=self._transport is None,
                )
            except RenderProviderError:
                raise
            except Exception as error:
                raise RenderProviderUnavailable(
                    "Image generation is temporarily unavailable"
                ) from error
        return GeneratedImage(
            body=image.body,
            content_type=image.content_type,
            sha256=sha256(image.body).hexdigest(),
            provider_trace=RenderProviderTrace(
                provider="litellm",
                model=self._alias,
                parameters={
                    "capability_alias": self._alias,
                    "size": size,
                    **({"seed": seed} if seed is not None else {}),
                    **({"guidance_scale": guidance_scale} if guidance_scale is not None else {}),
                },
            ),
        )


class FashnTryOnGenerator:
    def __init__(
        self,
        *,
        api_base_url: str = "https://api.fashn.ai/v1",
        api_key: str,
        timeout_seconds: float = 45,
        poll_interval_seconds: float = 1,
        poll_timeout_seconds: float = 90,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        if not api_base_url.strip():
            raise ValueError("FASHN API base URL must not be empty")
        if timeout_seconds <= 0 or poll_interval_seconds <= 0 or poll_timeout_seconds <= 0:
            raise ValueError("FASHN timeouts and poll intervals must be positive")
        self._base_url = api_base_url.rstrip("/")
        self._api_key = api_key.strip()
        self._timeout = timeout_seconds
        self._poll_interval = poll_interval_seconds
        self._poll_timeout = poll_timeout_seconds
        self._transport = transport

    async def try_on(
        self,
        *,
        model_image: ImagePayload,
        garment_image: ImagePayload,
        category: str = "auto",
        mode: str = "balanced",
    ) -> GeneratedImage:
        if not self._api_key:
            raise RenderProviderUnavailable("FASHN API key is not configured")
        if category not in {"auto", "tops", "bottoms", "one-pieces"}:
            raise ValueError("FASHN garment category is unsupported")
        async with httpx.AsyncClient(
            timeout=self._timeout,
            transport=self._transport,
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            },
        ) as client:
            try:
                run = await client.post(
                    f"{self._base_url}/run",
                    json={
                        "model_name": "tryon-v1.6",
                        "inputs": {
                            "model_image": _data_url(model_image),
                            "garment_image": _data_url(garment_image),
                            "category": category,
                            "mode": mode,
                            "output_format": "png",
                            "return_base64": True,
                        },
                    },
                )
                run.raise_for_status()
                prediction_id = _prediction_id(run.json())
                status_payload = await self._poll_until_terminal(client, prediction_id)
                image = await _image_from_fashn_status(
                    status_payload,
                    client=client,
                    resolve_download_host=self._transport is None,
                )
            except RenderProviderError:
                raise
            except Exception as error:
                raise RenderProviderUnavailable(
                    "Hosted try-on is temporarily unavailable"
                ) from error
        return GeneratedImage(
            body=image.body,
            content_type=image.content_type,
            sha256=sha256(image.body).hexdigest(),
            provider_trace=RenderProviderTrace(
                provider="fashn",
                model="tryon-v1.6",
                parameters={
                    "category": category,
                    "mode": mode,
                    "output_format": "png",
                    "return_base64": True,
                },
            ),
        )

    async def _poll_until_terminal(
        self,
        client: httpx.AsyncClient,
        prediction_id: str,
    ) -> dict[str, object]:
        deadline = client.timeout.read or self._poll_timeout
        elapsed = 0.0
        while elapsed <= self._poll_timeout:
            response = await client.get(f"{self._base_url}/status/{prediction_id}")
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise RenderProviderError(
                    "render_provider_schema_invalid",
                    "FASHN status response is not an object",
                    retryable=False,
                )
            status = payload.get("status")
            if status == "completed":
                return dict(payload)
            if status == "failed":
                raise RenderProviderError(
                    "render_provider_failed",
                    "Hosted try-on failed",
                    retryable=False,
                )
            if elapsed + self._poll_interval > self._poll_timeout:
                break
            await _sleep(self._poll_interval)
            elapsed += self._poll_interval
        raise RenderProviderUnavailable(
            f"Hosted try-on did not complete within {min(deadline, self._poll_timeout):g}s"
        )


@dataclass(frozen=True, slots=True)
class _DecodedImage:
    body: bytes
    content_type: str


async def _image_from_openai_response(
    payload: object,
    *,
    client: httpx.AsyncClient,
    download_max_bytes: int,
    resolve_download_host: bool,
) -> _DecodedImage:
    if not isinstance(payload, dict):
        raise RenderProviderError(
            "render_provider_schema_invalid",
            "Image generation response is not an object",
            retryable=False,
        )
    data = payload.get("data")
    if not isinstance(data, list) or not data:
        raise RenderProviderError(
            "render_provider_schema_invalid",
            "Image generation response does not contain image data",
            retryable=False,
        )
    first = data[0]
    if not isinstance(first, dict):
        raise RenderProviderError(
            "render_provider_schema_invalid",
            "Image generation response item is invalid",
            retryable=False,
        )
    if isinstance(first.get("b64_json"), str):
        return _decode_base64_image(
            first["b64_json"],
            content_type="image/png",
            max_bytes=download_max_bytes,
        )
    if isinstance(first.get("url"), str):
        return await _download_image(
            first["url"],
            client=client,
            download_max_bytes=download_max_bytes,
            resolve_host=resolve_download_host,
        )
    raise RenderProviderError(
        "render_provider_schema_invalid",
        "Image generation response has no usable image",
        retryable=False,
    )


async def _image_from_fashn_status(
    payload: dict[str, object],
    *,
    client: httpx.AsyncClient,
    resolve_download_host: bool,
) -> _DecodedImage:
    output = payload.get("output")
    if isinstance(output, str):
        if output.startswith("http://") or output.startswith("https://"):
            return await _download_image(
                output,
                client=client,
                download_max_bytes=20 * 1024 * 1024,
                resolve_host=resolve_download_host,
            )
        return _decode_base64_image(
            output,
            content_type="image/png",
            max_bytes=20 * 1024 * 1024,
        )
    if isinstance(output, list) and output:
        first = output[0]
        if isinstance(first, str):
            if first.startswith("http://") or first.startswith("https://"):
                return await _download_image(
                    first,
                    client=client,
                    download_max_bytes=20 * 1024 * 1024,
                    resolve_host=resolve_download_host,
                )
            return _decode_base64_image(
                first,
                content_type="image/png",
                max_bytes=20 * 1024 * 1024,
            )
    raise RenderProviderError(
        "render_provider_schema_invalid",
        "FASHN status response has no usable output image",
        retryable=False,
    )


def _prediction_id(payload: object) -> str:
    if not isinstance(payload, dict):
        raise RenderProviderError(
            "render_provider_schema_invalid",
            "FASHN run response is not an object",
            retryable=False,
        )
    value = payload.get("id") or payload.get("prediction_id")
    if not isinstance(value, str) or not value.strip():
        raise RenderProviderError(
            "render_provider_schema_invalid",
            "FASHN run response has no prediction id",
            retryable=False,
        )
    return value.strip()


def _decode_base64_image(
    value: str,
    *,
    content_type: str,
    max_bytes: int,
) -> _DecodedImage:
    try:
        if value.startswith("data:"):
            header, raw = value.split(",", maxsplit=1)
            content_type = header.removeprefix("data:").split(";", maxsplit=1)[0]
            value = raw
        if len(value) > ((max_bytes + 2) // 3) * 4 + 4:
            raise RenderProviderError(
                "render_provider_output_too_large",
                "Provider image exceeds the configured download limit",
                retryable=False,
            )
        body = base64.b64decode(value, validate=True)
    except ValueError as error:
        raise RenderProviderError(
            "render_provider_schema_invalid",
            "Provider returned invalid base64 image data",
            retryable=False,
        ) from error
    _validate_image_content_type(content_type)
    if len(body) > max_bytes:
        raise RenderProviderError(
            "render_provider_output_too_large",
            "Provider image exceeds the configured download limit",
            retryable=False,
        )
    return _DecodedImage(body=body, content_type=content_type)


async def _download_image(
    url: str,
    *,
    client: httpx.AsyncClient,
    download_max_bytes: int,
    resolve_host: bool = True,
) -> _DecodedImage:
    await _validate_download_url(url, resolve_host=resolve_host)
    body = bytearray()
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").split(";", maxsplit=1)[0].strip()
        _validate_image_content_type(content_type)
        async for chunk in response.aiter_bytes():
            body.extend(chunk)
            if len(body) > download_max_bytes:
                raise RenderProviderError(
                    "render_provider_output_too_large",
                    "Provider image exceeds the configured download limit",
                    retryable=False,
                )
    return _DecodedImage(body=bytes(body), content_type=content_type)


async def _validate_download_url(url: str, *, resolve_host: bool) -> None:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.hostname.lower() == "localhost"
    ):
        raise RenderProviderError(
            "render_provider_url_invalid",
            "Provider image URL is not a public HTTPS resource",
            retryable=False,
        )
    try:
        literal = ipaddress.ip_address(parsed.hostname)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise RenderProviderError(
            "render_provider_url_invalid",
            "Provider image URL resolves to a non-public address",
            retryable=False,
        )
    if not resolve_host or literal is not None:
        return
    import asyncio

    try:
        addresses = await asyncio.to_thread(
            socket.getaddrinfo,
            parsed.hostname,
            parsed.port or 443,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as error:
        raise RenderProviderUnavailable("Provider image host could not be resolved") from error
    if not addresses or any(
        not ipaddress.ip_address(sockaddr[0]).is_global
        for _family, _type, _proto, _canonname, sockaddr in addresses
    ):
        raise RenderProviderError(
            "render_provider_url_invalid",
            "Provider image URL resolves to a non-public address",
            retryable=False,
        )


def _data_url(image: ImagePayload) -> str:
    _validate_image_content_type(image.content_type)
    return f"data:{image.content_type};base64,{base64.b64encode(image.body).decode('ascii')}"


def _validate_image_content_type(content_type: str) -> None:
    if content_type not in SUPPORTED_OUTPUT_TYPES:
        raise RenderProviderError(
            "render_provider_image_type_invalid",
            "Render providers must exchange PNG, JPEG, or WebP images",
            retryable=False,
        )


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
