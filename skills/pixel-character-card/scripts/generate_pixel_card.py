#!/usr/bin/env python3
"""Generate one pixel character card through the StyleCapture Product API."""

from __future__ import annotations

import argparse
import hashlib
import http.cookiejar
import json
import mimetypes
import os
import sys
import time
import uuid
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import HTTPCookieProcessor, Request, build_opener


DEFAULT_API_BASE_URL = "https://119.45.216.38"
SUPPORTED_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/heic",
    "image/heif",
}
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class ProductApiFailure(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="通过 StyleCapture Product API 生成固定 3:4 像素小人卡片。"
    )
    parser.add_argument("image", type=Path, help="单人人物图片路径")
    parser.add_argument(
        "--api-base-url",
        default=os.getenv("STYLECAPTURE_API_URL", DEFAULT_API_BASE_URL),
        help="StyleCapture Product API 根地址",
    )
    parser.add_argument("--output", type=Path, help="输出 PNG 路径")
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--poll-seconds", type=float, default=2.0)
    return parser.parse_args()


class ProductApiClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        if not base_url.strip():
            raise ValueError("API base URL must not be empty")
        self.base_url = base_url.rstrip("/") + "/"
        self.timeout = timeout_seconds
        self.opener = build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.session_cookie = os.getenv("STYLECAPTURE_SESSION_COOKIE", "").strip()

    def request(
        self,
        method: str,
        path_or_url: str,
        *,
        body: bytes | None = None,
        headers: dict[str, str] | None = None,
        expect_json: bool = True,
    ) -> object:
        url = urljoin(self.base_url, path_or_url)
        safe_headers = dict(headers or {})
        if self.session_cookie:
            safe_headers["Cookie"] = self.session_cookie
        request = Request(url, data=body, headers=safe_headers, method=method)
        try:
            with self.opener.open(request, timeout=self.timeout) as response:
                payload = response.read()
        except HTTPError as error:
            raw = error.read()
            code, message = _error_details(raw, fallback=f"HTTP {error.code}")
            raise ProductApiFailure(code, message, retryable=error.code >= 500) from None
        except (URLError, TimeoutError) as error:
            raise ProductApiFailure(
                "product_api_unavailable", "StyleCapture Product API 暂时不可用", retryable=True
            ) from error
        if not expect_json:
            return payload
        try:
            return json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ProductApiFailure("product_api_schema_invalid", "Product API 返回格式无效") from error

    def json_request(
        self,
        method: str,
        path: str,
        payload: dict[str, object] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, object]:
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        merged = {"Accept": "application/json", **(headers or {})}
        if body is not None:
            merged["Content-Type"] = "application/json"
        result = self.request(method, path, body=body, headers=merged)
        if not isinstance(result, dict):
            raise ProductApiFailure("product_api_schema_invalid", "Product API 返回格式无效")
        return result


def main() -> int:
    args = parse_args()
    started = time.monotonic()
    try:
        if args.timeout_seconds <= 0 or args.poll_seconds <= 0:
            raise ValueError("timeout and poll interval must be positive")
        source = args.image.resolve(strict=True)
        body = source.read_bytes()
        if not body or len(body) > MAX_UPLOAD_BYTES:
            raise ValueError("input image must be between 1 byte and 20 MB")
        content_type = _content_type(source)
        output = (args.output or source.with_name(f"{source.stem}-pixel-card.png")).resolve()
        deadline = started + args.timeout_seconds
        client = ProductApiClient(args.api_base_url, min(args.timeout_seconds, 60.0))
        if not client.session_cookie:
            client.json_request("POST", "/v1/session")
        digest = hashlib.sha256(body).hexdigest()
        prepared = client.json_request(
            "POST",
            "/v1/uploads/prepare",
            {
                "file_name": source.name,
                "content_type": content_type,
                "byte_size": len(body),
                "sha256": digest,
            },
        )
        upload_url = _required_string(prepared, "upload_url")
        upload_token = _required_string(prepared, "upload_token")
        object_key = _required_string(prepared, "object_key")
        client.request(
            "PUT",
            upload_url,
            body=body,
            headers={"Content-Type": content_type, "X-Upload-Token": upload_token},
        )
        trial = client.json_request(
            "POST",
            "/v1/pixel-trials",
            {"subject_object_key": object_key},
            {"Idempotency-Key": f"pixel-card-skill:{uuid.uuid4()}"},
        )
        trial_id = _required_string(trial, "id")
        while True:
            status = str(trial.get("status", ""))
            if status == "succeeded":
                image_url = str(trial.get("output_image_url") or f"/v1/pixel-trials/{trial_id}/image")
                image = client.request("GET", image_url, expect_json=False)
                if not isinstance(image, bytes) or not image:
                    raise ProductApiFailure("pixel_trial_output_invalid", "生成结果为空")
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_bytes(image)
                print(
                    json.dumps(
                        {
                            "status": "succeeded",
                            "trial_id": trial_id,
                            "output": str(output),
                            "elapsed_seconds": round(time.monotonic() - started, 2),
                        },
                        ensure_ascii=False,
                    )
                )
                return 0
            if status == "failed":
                raise ProductApiFailure(
                    str(trial.get("failure_code") or "pixel_trial_failed"),
                    str(trial.get("failure_message") or "像素卡生成失败"),
                    retryable=bool(trial.get("retryable")),
                )
            if time.monotonic() + args.poll_seconds > deadline:
                raise ProductApiFailure("pixel_trial_timeout", "等待像素卡生成超时", retryable=True)
            time.sleep(args.poll_seconds)
            trial = client.json_request("GET", f"/v1/pixel-trials/{trial_id}")
    except (OSError, ValueError, ProductApiFailure) as error:
        code = error.code if isinstance(error, ProductApiFailure) else "input_invalid"
        retryable = error.retryable if isinstance(error, ProductApiFailure) else False
        print(
            json.dumps(
                {"status": "failed", "code": code, "message": str(error), "retryable": retryable},
                ensure_ascii=False,
            ),
            file=sys.stderr,
        )
        return 1


def _content_type(path: Path) -> str:
    suffixes = {".heic": "image/heic", ".heif": "image/heif"}
    content_type = suffixes.get(path.suffix.lower()) or mimetypes.guess_type(path.name)[0]
    if content_type not in SUPPORTED_TYPES:
        raise ValueError("input must be JPG, PNG, WebP, HEIC, or HEIF")
    return content_type


def _required_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ProductApiFailure("product_api_schema_invalid", f"Product API 缺少字段: {key}")
    return value.strip()


def _error_details(raw: bytes, *, fallback: str) -> tuple[str, str]:
    try:
        payload = json.loads(raw.decode("utf-8"))
        error = payload.get("error", {}) if isinstance(payload, dict) else {}
        if isinstance(error, dict):
            return str(error.get("code") or "product_api_error"), str(error.get("message") or fallback)
    except (UnicodeDecodeError, json.JSONDecodeError):
        pass
    return "product_api_error", fallback


if __name__ == "__main__":
    raise SystemExit(main())
