from __future__ import annotations

# This file intentionally keeps natural Chinese punctuation inside model prompts.
# ruff: noqa: RUF001
import argparse
import asyncio
import json
import os
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from typing import cast

from PIL import Image
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.render.infrastructure.providers import (
    LiteLLMImageGenerator,
)

LOOK_PROMPT = """
把参考图中的完整穿搭转换为一个且仅一个 StyleCapture 可爱像素小人。
全身正面站立并居中，完整展示从头到脚；忠实保留真实穿搭的主色、轮廓、材质、
层次和搭配关系。浅色纯净背景。禁止多人、分镜、九宫格、备选造型、文字、
品牌、水印或额外服饰。
""".strip()


def item_prompt(entry: dict[str, object]) -> str:
    name = str(entry["name"])
    category = str(entry["category"])
    subcategory = str(entry["subcategory"])
    colors = "、".join(str(color) for color in cast(list[object], entry["colors"]))
    return f"""
从参考图中只识别并提取目标商品“{name}”（类别 {category}/{subcategory}，主色 {colors}），
将这个目标商品转换为 StyleCapture 可爱像素风商品展示图。
必须是电商商品抠图式构图：只出现一个目标单品；若目标本来是一双鞋，则只出现一双配对鞋；
若目标明确是配饰组，才可保留该组配饰。不要画参考图中的模特、人体、内搭、裤子、包、
货架、商店、街景、其他衣服或其他鞋，不要生成完整穿搭。
忠实保留目标单品的主色、材质、版型、图案和关键细节，浅色纯净背景，居中完整展示。
禁止文字、品牌、水印、拼贴、分镜、多个候选或额外道具。
这只是一级衣橱的视觉封面，必须让用户点开后仍能认出对应的真实单品。
""".strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate Git-tracked curated pixel assets through LiteLLM."
    )
    parser.add_argument("--force", action="store_true", help="replace existing pixel assets")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument(
        "--kind",
        choices=("all", "items", "looks"),
        default="all",
        help="limit generation to item covers or look characters",
    )
    parser.add_argument(
        "--seed-key",
        action="append",
        default=[],
        help="generate only matching seed_key entries; may be supplied more than once",
    )
    return parser.parse_args()


def image_payload(path: Path) -> ImagePayload:
    body = path.read_bytes()
    content_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }[path.suffix.lower()]
    return ImagePayload(
        object_key=f"curated-seed/{path.name}",
        content_type=content_type,
        body=body,
        sha256=sha256(body).hexdigest(),
    )


def save_png(body: bytes, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(BytesIO(body)) as source:
        converted = source.convert("RGBA")
        converted.save(destination, format="PNG", optimize=True)


async def main() -> None:
    args = parse_args()
    if args.concurrency < 1 or args.concurrency > 3:
        raise SystemExit("--concurrency must be between 1 and 3")
    repo_root = Path(__file__).resolve().parents[1]
    assets_root = (
        repo_root / "services/backend/src/stylecapture_backend/demo_assets"
    )
    manifest = cast(
        dict[str, object],
        json.loads((assets_root / "seed-manifest.json").read_text(encoding="utf-8")),
    )
    api_key = os.environ.get(
        "STYLECAPTURE_LITELLM_API_KEY",
        os.environ.get(
            "LITELLM_MASTER_KEY",
            "local-litellm-gateway-key-change-before-production",
        ),
    )
    gateway = os.environ.get(
        "STYLECAPTURE_LITELLM_BASE_URL",
        "http://127.0.0.1:4000/v1",
    )
    generator = LiteLLMImageGenerator(
        capability_alias="image_generation",
        gateway_base_url=gateway,
        gateway_api_key=api_key,
        timeout_seconds=120,
    )
    semaphore = asyncio.Semaphore(args.concurrency)
    item_entries = [
        cast(dict[str, object], entry)
        for entry in cast(list[object], manifest["items"])
    ]
    item_generation_entries = [
        (entry, item_prompt(entry))
        for entry in item_entries
    ]
    look_generation_entries = [
        (cast(dict[str, object], entry), LOOK_PROMPT)
        for entry in cast(list[object], manifest["looks"])
    ]
    entries = {
        "all": item_generation_entries + look_generation_entries,
        "items": item_generation_entries,
        "looks": look_generation_entries,
    }[args.kind]
    if args.seed_key:
        selected_keys = set(args.seed_key)
        entries = [
            (entry, prompt)
            for entry, prompt in entries
            if str(entry["seed_key"]) in selected_keys
        ]
        missing = selected_keys.difference(
            str(entry["seed_key"]) for entry, _ in entries
        )
        if missing:
            raise SystemExit(f"unknown seed keys: {', '.join(sorted(missing))}")

    async def generate(entry: dict[str, object], prompt: str) -> str:
        source = assets_root / str(entry["product_image"])
        destination = assets_root / str(entry["pixel_asset"])
        if destination.exists() and not args.force:
            return f"skip {entry['seed_key']}"
        async with semaphore:
            generated = await generator.generate(
                prompt=prompt,
                images=(image_payload(source),),
                size="2K",
            )
        save_png(generated.body, destination)
        return f"generated {entry['seed_key']}"

    results = await asyncio.gather(
        *(generate(entry, prompt) for entry, prompt in entries)
    )
    for result in results:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
