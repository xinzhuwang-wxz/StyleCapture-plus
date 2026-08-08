from __future__ import annotations

# ruff: noqa: RUF001 -- Chinese prompt punctuation is intentional.
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files

from stylecapture_backend.features.capture.domain import ImagePayload

PIXEL_CARD_STYLE_REFERENCE_VERSION = "pixel-card-style-v1"
PIXEL_CARD_SEED = 482731
PIXEL_CARD_GUIDANCE_SCALE = 7.0

_STYLE_REFERENCE_NAMES = (
    "anchor-formal-light-pixel.png",
    "anchor-casual-dark-pixel.png",
)

_PIXEL_CARD_RULES = (
    "生成竖版 3:4 单人全身像素角色卡。{image_roles}"
    "人物完整居中，保留头顶、鞋底和四周留白，脚下放轻量椭圆地毯。"
    "保留内容图中可见的发型、发饰、眼镜、表情、身材比例、服装版型、主辅色、鞋履和关键配饰；"
    "如果内容图只有半身，只补全不可见的下装与鞋履，并让补全部分与可见上装自然协调。"
    "使用较粗且一致的方格像素、清晰阶梯边缘和有限色阶；不要平滑线条、写实纹理、3D质感或低清放大滤镜。"
    "面部适度美化，眼睛略大、有神且符合人物气质，表情仍以内容图为准。"
    "移除内容图原背景。根据服装颜色、款式、正式度和气质选择卡片的两种主色与一种点缀色："
    "正式或中性穿搭更克制，休闲或甜美穿搭更轻盈，酷感穿搭可提高对比。"
    "背景加入1至3类轻量漂浮简笔像素图标和少量光点，图标颜色呼应穿搭；"
    "图标主题可从原场景语义提炼，但只保留符号，不画完整场景。"
    "不可纯色空白，不可复刻原场景，也不可变成细节繁重的房间或街景。"
    "不要文字、品牌、水印、额外人物、重复肢体或裁切鞋履。"
)


def build_pixel_card_prompt(image_roles: str) -> str:
    return _PIXEL_CARD_RULES.format(image_roles=image_roles.strip())


@lru_cache(maxsize=1)
def load_pixel_card_style_references() -> tuple[ImagePayload, ...]:
    root = files("stylecapture_backend.features.render").joinpath(
        "assets", "pixel-card-references"
    )
    references: list[ImagePayload] = []
    for name in _STYLE_REFERENCE_NAMES:
        body = root.joinpath(name).read_bytes()
        references.append(
            ImagePayload(
                object_key=f"bundled/pixel-card-style/{name}",
                content_type="image/png",
                body=body,
                sha256=sha256(body).hexdigest(),
            )
        )
    return tuple(references)


def pixel_card_style_reference_hashes() -> tuple[str, ...]:
    return tuple(reference.sha256 for reference in load_pixel_card_style_references())
