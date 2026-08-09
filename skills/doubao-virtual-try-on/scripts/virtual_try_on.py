#!/usr/bin/env python3
# ruff: noqa: RUF001
"""Create and audit a Doubao Seedream virtual try-on from two local images."""

from __future__ import annotations

import argparse
import base64
import binascii
import getpass
import ipaddress
import json
import mimetypes
import os
import shutil
import socket
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_UNDERSTANDING_MODEL = "doubao-seed-2-0-lite-260428"
DEFAULT_IMAGE_MODEL = "doubao-seedream-5-0-260128"
VERSION = "1.3.0"
TRANSIENT_HTTP_CODES = {408, 409, 429, 500, 502, 503, 504}
MAX_IMAGE_DOWNLOAD_BYTES = 20 * 1024 * 1024
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "ark_api_key",
    "authorization",
    "b64_json",
    "token",
    "signature",
    "signed_url",
    "url",
}
BLOCKED_HOSTNAMES = {"localhost", "localhost.localdomain"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a photorealistic try-on through Volcengine Ark."
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    parser.add_argument("person_image", type=Path)
    parser.add_argument("outfit_board", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--style-reference", type=Path)
    parser.add_argument("--max-attempts", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--size", default="2K")
    parser.add_argument("--watermark", action="store_true")
    parser.add_argument("--api-base", default=DEFAULT_BASE_URL)
    parser.add_argument("--understanding-model", default=DEFAULT_UNDERSTANDING_MODEL)
    parser.add_argument("--image-model", default=DEFAULT_IMAGE_MODEL)
    return parser.parse_args()


def require_image(path: Path, label: str) -> Path:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{label} not found: {path}")
    mime = mimetypes.guess_type(path.name)[0]
    if mime not in {"image/jpeg", "image/png", "image/webp"}:
        raise ValueError(f"{label} must be JPEG, PNG, or WebP: {path}")
    return path


def _is_blocked_ip(address: str) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def validate_https_public_url(url: str, label: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        raise ValueError(f"{label} must use HTTPS")
    if parsed.username or parsed.password:
        raise ValueError(f"{label} must not contain credentials")
    hostname = parsed.hostname
    if not hostname:
        raise ValueError(f"{label} must include a hostname")
    normalized_host = hostname.rstrip(".").lower()
    if normalized_host in BLOCKED_HOSTNAMES or normalized_host.endswith(".localhost"):
        raise ValueError(f"{label} host is not allowed")
    try:
        addresses = socket.getaddrinfo(normalized_host, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError(f"{label} host could not be resolved") from exc
    resolved: set[str] = {str(entry[4][0]) for entry in addresses}
    if not resolved or any(_is_blocked_ip(address) for address in resolved):
        raise ValueError(f"{label} resolves to a non-public address")
    return url


def redact_for_log(value: Any) -> Any:
    if isinstance(value, dict):
        redacted_mapping: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower().replace("-", "_")
            if normalized in SENSITIVE_KEYS or "authorization" in normalized:
                redacted_mapping[key] = "<redacted>"
            else:
                redacted_mapping[key] = redact_for_log(item)
        return redacted_mapping
    if isinstance(value, list):
        return [redact_for_log(item) for item in value]
    if isinstance(value, str):
        redacted_text = value
        if "Bearer " in redacted_text:
            redacted_text = redacted_text.split("Bearer ", 1)[0] + "Bearer <redacted>"
        if "b64_json" in redacted_text or "data:image/" in redacted_text:
            return "<redacted image payload>"
        return redacted_text
    return value


def image_data_url(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def sanitized_http_error(exc: urllib.error.HTTPError, endpoint: str) -> RuntimeError:
    body = exc.read().decode("utf-8", errors="replace")
    try:
        payload = json.loads(body)
        detail = json.dumps(redact_for_log(payload), ensure_ascii=False)
    except json.JSONDecodeError:
        detail = str(redact_for_log(body[:2000]))
    return RuntimeError(f"Ark HTTP {exc.code} from {endpoint}: {detail}")


def post_json(
    api_key: str,
    api_base: str,
    endpoint: str,
    payload: dict[str, Any],
    *,
    timeout: int,
    transport_attempts: int = 4,
) -> dict[str, Any]:
    request_body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    api_base = validate_https_public_url(api_base.rstrip("/"), "Ark API base URL")
    url = api_base.rstrip("/") + endpoint
    for attempt in range(transport_attempts):
        request = urllib.request.Request(
            url,
            data=request_body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": f"doubao-virtual-try-on/{VERSION}",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as exc:
            if exc.code not in TRANSIENT_HTTP_CODES or attempt + 1 == transport_attempts:
                raise sanitized_http_error(exc, endpoint) from exc
            exc.close()
        except (TimeoutError, urllib.error.URLError):
            if attempt + 1 == transport_attempts:
                raise
        time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"Ark request failed without response: {endpoint}")


def extract_json_object(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"Expected a JSON object from understanding model: {text}")
    try:
        value = json.loads(text[start : end + 1])
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON from understanding model: {text}") from exc
    if not isinstance(value, dict):
        raise ValueError("Understanding model JSON must be an object")
    return value


def chat(
    *,
    api_key: str,
    api_base: str,
    model: str,
    prompt: str,
    labeled_images: list[tuple[str, str]],
) -> dict[str, Any]:
    content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
    for label, url in labeled_images:
        content.append({"type": "text", "text": label})
        content.append({"type": "image_url", "image_url": {"url": url}})
    response = post_json(
        api_key,
        api_base,
        "/chat/completions",
        {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "temperature": 0.1,
            "max_tokens": 3500,
        },
        timeout=300,
    )
    try:
        text = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            "Unexpected Ark chat response: " + json.dumps(response, ensure_ascii=False)[:2000]
        ) from exc
    return extract_json_object(text)


def analyze_inputs(
    *,
    api_key: str,
    api_base: str,
    model: str,
    person_url: str,
    outfit_url: str,
    style_url: str | None,
) -> dict[str, Any]:
    images = [
        ("IMAGE 1 — the only identity/person reference", person_url),
        ("IMAGE 2 — the only replacement outfit item board", outfit_url),
    ]
    style_instruction = (
        "\nIMAGE 3 is a framing/realism example only. Never copy its person, face, "
        "body, clothing, accessories, or background-specific objects."
        if style_url
        else "\nNo style-reference image is provided. Infer a natural vertical full-body "
        "fashion-photo composition from IMAGE 1 while preserving a believable environment."
    )
    if style_url:
        images.append(("IMAGE 3 — optional composition/realism reference only", style_url))
    prompt = f"""Prepare a photorealistic virtual try-on generation from the labeled images.
Return only valid JSON with this schema:
{{
  "person_identity": "observable identity, face, hair, skin tone and body-proportion traits",
  "outfit_items": [
    {{"name": "...", "color": "...", "material": "...", "shape_and_details": "...",
      "wearing_instruction": "..."}}
  ],
  "composition": "recommended pose, crop, camera, background and lighting",
  "generation_prompt": "complete Chinese image-generation instruction"
}}

Requirements for generation_prompt:
- State that IMAGE 1 is the only source of identity, facial features, hairstyle, skin tone and
  body proportions. Keep the exact same person, not a merely similar person.
- Lock observable facial geometry: face shape and jawline, hairline, eyebrow shape and spacing,
  eye shape and spacing, eyelids, nose bridge and width, lip shape, mouth corners, ears, skin
  tone, age cues, glasses and distinctive details. Preserve expression, makeup and hairstyle.
- Prohibit beautification, face slimming, eye enlargement, nose reshaping, skin smoothing or
  whitening, age/gender changes, and any reinterpretation of the face. Except where a new collar
  meets hair or skin, preserve IMAGE 1's head and face region instead of repainting it.
- State that IMAGE 2 is the only source of replacement clothing and accessories. The person must
  naturally wear or carry every visible outfit-board item exactly once in the correct place.
- Replace all clothes and accessories from IMAGE 1. Do not retain an item from IMAGE 1 unless the
  same item is visible in IMAGE 2.
- Describe each item precisely, including color, material, cut, hardware, neckline, hem, heel,
  strap and bag structure when visible.
- Reconstruct a believable full body if IMAGE 1 is cropped. Keep anatomy, hands, fingers, legs,
  feet, garment construction and object scale realistic.
- Produce one single vertical photorealistic camera image. No collage, split screen, item layout,
  text, logo addition, extra garments, duplicated objects, floating items or illustration style.
- Preserve a plausible version of IMAGE 1's environment unless the style instruction says
  otherwise.
{style_instruction}
"""
    return chat(
        api_key=api_key,
        api_base=api_base,
        model=model,
        prompt=prompt,
        labeled_images=images,
    )


def generate_image(
    *,
    api_key: str,
    api_base: str,
    model: str,
    prompt: str,
    person_url: str,
    outfit_url: str,
    size: str,
    watermark: bool,
) -> dict[str, Any]:
    return post_json(
        api_key,
        api_base,
        "/images/generations",
        {
            "model": model,
            "prompt": prompt,
            "image": [person_url, outfit_url],
            "size": size,
            "sequential_image_generation": "disabled",
            "stream": False,
            "response_format": "url",
            "watermark": watermark,
        },
        timeout=600,
    )


def download_result(response: dict[str, Any], target: Path) -> None:
    try:
        item = response["data"][0]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            "Unexpected Ark image response: " + json.dumps(response, ensure_ascii=False)[:2000]
        ) from exc
    if item.get("b64_json"):
        try:
            data = base64.b64decode(item["b64_json"], validate=True)
        except (binascii.Error, TypeError) as exc:
            raise RuntimeError("Ark image response contains invalid b64_json") from exc
        if len(data) > MAX_IMAGE_DOWNLOAD_BYTES:
            raise RuntimeError("Ark b64_json image exceeds 20 MB limit")
        target.write_bytes(data)
        return
    url = item.get("url")
    if not url:
        raise RuntimeError("Ark image response has neither url nor b64_json")
    url = validate_https_public_url(str(url), "Ark image download URL")
    request = urllib.request.Request(
        url, headers={"User-Agent": f"doubao-virtual-try-on/{VERSION}"}
    )
    with urllib.request.urlopen(request, timeout=300) as result:
        content_type = result.headers.get_content_type()
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise RuntimeError(
                f"Ark image download returned non-image Content-Type: {content_type}"
            )
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = result.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_IMAGE_DOWNLOAD_BYTES:
                raise RuntimeError("Ark image download exceeds 20 MB limit")
            chunks.append(chunk)
        target.write_bytes(b"".join(chunks))


def response_for_log(response: dict[str, Any]) -> dict[str, Any]:
    """Copy an image response while removing temporary signed download URLs."""
    value = redact_for_log(json.loads(json.dumps(response)))
    for item in value.get("data", []):
        if isinstance(item, dict) and item.get("url"):
            item["url"] = "<temporary signed URL omitted; image saved locally>"
        if isinstance(item, dict) and item.get("b64_json"):
            item["b64_json"] = "<base64 image omitted; image saved locally>"
    return value


def audit_result(
    *,
    api_key: str,
    api_base: str,
    model: str,
    person_url: str,
    outfit_url: str,
    result_url: str,
) -> dict[str, Any]:
    prompt = """Audit the generated virtual try-on conservatively using visible evidence.
Return only valid JSON with exactly this structure:
{
  "identity_preservation": {"score": 0, "notes": "..."},
  "outfit_fidelity": {"score": 0, "matched": [], "missing_or_wrong": []},
  "photorealism": {"score": 0, "artifacts": []},
  "overall_score": 0,
  "pass": false,
  "recommended_retry_changes": []
}

Compare IMAGE 3's person only against IMAGE 1 and IMAGE 3's clothing/items only against IMAGE 2.
Do not award identity points for merely matching gender, ethnicity, hair color or general vibe.
Compare exact face shape, jawline, eye spacing and shape, eyebrows, nose, mouth, hairline, ears,
glasses, skin tone and age cues. Check every board item, colors, materials, cut, hardware, item
count, shoes, bag, anatomy, hands, feet and unintended carry-over from IMAGE 1's original
clothes/accessories. Pass only when overall_score >= 88, identity_preservation.score >= 88,
outfit_fidelity.score >= 80, and there is no severe anatomical or object-duplication artifact."""
    audit = chat(
        api_key=api_key,
        api_base=api_base,
        model=model,
        prompt=prompt,
        labeled_images=[
            ("IMAGE 1 — source person", person_url),
            ("IMAGE 2 — requested outfit board", outfit_url),
            ("IMAGE 3 — generated result", result_url),
        ],
    )
    for key in (
        "identity_preservation",
        "outfit_fidelity",
        "photorealism",
        "overall_score",
        "pass",
        "recommended_retry_changes",
    ):
        if key not in audit:
            raise ValueError(f"Audit JSON missing key: {key}")
    return audit


def overall_score(audit: dict[str, Any]) -> float:
    try:
        return float(audit["overall_score"])
    except (KeyError, TypeError, ValueError):
        return 0.0


def audit_passes(audit: dict[str, Any]) -> bool:
    try:
        identity = float(audit["identity_preservation"]["score"])
        outfit = float(audit["outfit_fidelity"]["score"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        audit.get("pass") is True and overall_score(audit) >= 88 and identity >= 88 and outfit >= 80
    )


def main() -> int:
    args = parse_args()
    person_path = require_image(args.person_image, "Person image")
    outfit_path = require_image(args.outfit_board, "Outfit board")
    style_path = (
        require_image(args.style_reference, "Style reference") if args.style_reference else None
    )
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("ARK_API_KEY")
    if not api_key and sys.stdin.isatty():
        api_key = getpass.getpass("ARK_API_KEY: ")
    if not api_key:
        raise RuntimeError(
            "ARK_API_KEY is required. Set it in the environment or run interactively."
        )

    person_url = image_data_url(person_path)
    outfit_url = image_data_url(outfit_path)
    style_url = image_data_url(style_path) if style_path else None

    print("Analyzing identity, outfit items, and composition...", flush=True)
    analysis = analyze_inputs(
        api_key=api_key,
        api_base=args.api_base,
        model=args.understanding_model,
        person_url=person_url,
        outfit_url=outfit_url,
        style_url=style_url,
    )
    analysis_path = output_dir / "analysis.json"
    analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    base_prompt = str(analysis.get("generation_prompt", "")).strip()
    if not base_prompt:
        raise ValueError("Analysis JSON contains no generation_prompt")

    attempts: list[dict[str, Any]] = []
    retry_changes: list[Any] = []
    for number in range(1, args.max_attempts + 1):
        prompt = base_prompt
        if retry_changes:
            prompt += (
                "\n\n上一次结果存在以下问题。必须逐项修正，同时继续严格遵守原始人物和穿搭约束：\n- "
                + "\n- ".join(map(str, retry_changes))
            )
        print(f"Generating attempt {number}/{args.max_attempts}...", flush=True)
        generation = generate_image(
            api_key=api_key,
            api_base=args.api_base,
            model=args.image_model,
            prompt=prompt,
            person_url=person_url,
            outfit_url=outfit_url,
            size=args.size,
            watermark=args.watermark,
        )
        image_path = output_dir / f"attempt-{number}.jpg"
        download_result(generation, image_path)
        response_path = output_dir / f"generation-attempt-{number}.json"
        response_path.write_text(
            json.dumps(response_for_log(generation), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        print(f"Auditing attempt {number}...", flush=True)
        result_url = image_data_url(image_path)
        audit = audit_result(
            api_key=api_key,
            api_base=args.api_base,
            model=args.understanding_model,
            person_url=person_url,
            outfit_url=outfit_url,
            result_url=result_url,
        )
        audit_path = output_dir / f"audit-attempt-{number}.json"
        audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
        attempts.append(
            {
                "attempt": number,
                "image": image_path.name,
                "audit": audit_path.name,
                "overall_score": overall_score(audit),
                "pass": audit_passes(audit),
            }
        )
        if audit_passes(audit):
            break
        retry_changes = list(audit.get("recommended_retry_changes") or [])
        if not retry_changes:
            retry_changes = [
                "提高人物面部身份一致性",
                "逐一核对并准确呈现穿搭拼贴图中的全部单品",
                "修复解剖、手脚、服装结构或物体重复问题",
            ]

    best = max(attempts, key=lambda item: item["overall_score"])
    result_path = output_dir / "result.jpg"
    shutil.copyfile(output_dir / best["image"], result_path)
    manifest = {
        "models": {
            "understanding": args.understanding_model,
            "generation": args.image_model,
        },
        "inputs": {
            "person_image": str(person_path),
            "outfit_board": str(outfit_path),
            "style_reference": str(style_path) if style_path else None,
        },
        "attempts": attempts,
        "selected_attempt": best["attempt"],
        "hard_pass": bool(best["pass"]),
        "quality_status": "pass" if best["pass"] else "hard_fail",
        "result": result_path.name,
    }
    manifest_path = output_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    print(f"RESULT={result_path}")
    return 0 if best["pass"] else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
