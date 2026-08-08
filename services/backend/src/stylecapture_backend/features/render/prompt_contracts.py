from __future__ import annotations

# ruff: noqa: RUF001 -- Chinese prompt punctuation is intentional.
from stylecapture_backend.features.render.pixel_card_style import build_pixel_card_prompt

PIXEL_COVER_CAPABILITY_ID = "look.pixel_cover"
PIXEL_COVER_OUTPUT_SIZE = "1728x2304"
PIXEL_COVER_PROMPT_VERSION = "look-pixel-cover-zh-v5"
PIXEL_COVER_SCHEMA_VERSION = "generated-image-v1"

TRY_ON_CAPABILITY_ID = "look.virtual_try_on"
TRY_ON_PROMPT_VERSION = "look-virtual-try-on-zh-v3"
TRY_ON_SCHEMA_VERSION = "generated-image-v1"

PIXEL_COVER_PROMPT = build_pixel_card_prompt(
    "前一至两张图是同一套 Look 的内容图，用于人物或服装轮廓、配色、材质和搭配关系；"
    "最后两张图只提供画风、人物与脸部比例、粗像素颗粒、卡片留白和地毯结构。"
    "不继承示例卡片的背景配色或装饰主题。"
)

TRY_ON_PROMPT = (
    "以第一张全身人物照片为主体,保持人物身份、脸部、发型、体型、"
    "姿势和背景不变。把后续参考图中的整套真实服装准确换到人物身上,"
    "保持每件衣服的颜色、材质、版型、层次和搭配关系,不添加额外服饰、"
    "文字、品牌或水印。输出竖版3:4、自然、完整的写实全身试穿照,人物不得拉伸、压扁或裁切。"
)
