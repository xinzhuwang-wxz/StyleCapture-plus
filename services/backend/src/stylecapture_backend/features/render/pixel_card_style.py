from __future__ import annotations

# ruff: noqa: RUF001 -- Chinese prompt punctuation is intentional.
from functools import lru_cache
from hashlib import sha256
from importlib.resources import files

from stylecapture_backend.features.capture.domain import ImagePayload

PIXEL_CARD_STYLE_REFERENCE_VERSION = "pixel-card-style-v2-candidate"
PIXEL_CARD_SEED = 482731
# Seedream 5.0 rejects guidance_scale. Keep this explicit so both pixel-card
# entry points omit the provider-incompatible field while sharing one contract.
PIXEL_CARD_GUIDANCE_SCALE: None = None

_STYLE_REFERENCE_NAMES = (
    "anchor-formal-light-pixel.png",
    "anchor-casual-dark-pixel.png",
)

_PIXEL_CARD_RULES = (
    "生成竖版 3:4 单人全身像素角色卡。{image_roles}"
    "按人物动作外接框居中，完整保留头顶、手臂和鞋底，四周留白，脚下放椭圆像素地毯。"
    "忠实保留内容图的身份、表情、身材、发型、眼镜、服装版型与配色、鞋履和关键配饰。"
    "姿势属于人物内容：保留躯干朝向、头部倾斜、四肢方向和身体重心，不改成对称立正；"
    "伸展动作通过缩小人物完整容纳。半身图只自然补全不可见的下装与鞋履。"
    "外轮廓使用清晰偏粗的阶梯像素；脸部、头发和服装内部使用中细像素与有限色阶柔和抖色，"
    "用明暗层级概括发丝、衣褶和材质，避免硬黑描边、写实纹理和马赛克滤镜。"
    "面部适度美化且仍可辨认：眼睛较大圆润有高光，脸型短而柔和，五官集中；"
    "表情仍以内容图为准，避免小眼睛、长中庭和低幼娃娃。"
    "移除原背景。由穿搭主辅色、配饰和气质延伸出柔和有色浅底，避免大面积纯白或中性灰。"
    "加入细像素边框、1至3类小尺寸低对比主题图标和少量光点；图标从原场景语义抽象，"
    "颜色呼应穿搭，单个不超过人物头宽四分之一，不画完整场景。"
    "不要文字、品牌、水印、额外人物、重复肢体或裁切鞋履。"
)


def build_pixel_card_prompt(image_roles: str) -> str:
    return _PIXEL_CARD_RULES.format(image_roles=image_roles.strip())


@lru_cache(maxsize=1)
def load_pixel_card_style_references() -> tuple[ImagePayload, ...]:
    root = files("stylecapture_backend.features.render").joinpath("assets", "pixel-card-references")
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
