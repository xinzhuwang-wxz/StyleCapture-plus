from __future__ import annotations

PIXEL_COVER_CAPABILITY_ID = "look.pixel_cover"
PIXEL_COVER_PROMPT_VERSION = "look-pixel-cover-zh-v2"
PIXEL_COVER_SCHEMA_VERSION = "generated-image-v1"

TRY_ON_CAPABILITY_ID = "look.virtual_try_on"
TRY_ON_PROMPT_VERSION = "look-virtual-try-on-zh-v2"
TRY_ON_SCHEMA_VERSION = "generated-image-v1"

PIXEL_COVER_PROMPT = (
    "第一张参考图如果是完整穿搭,以它的整体轮廓、配色和搭配关系为主;"
    "最后一张参考图是这套穿搭真实单品的拼贴,用于补足材质和细节。"
    "把参考图里的上衣、下装、外套、鞋履和配饰组合到同一个且仅一个"
    "StyleCapture 可爱像素小人身上。画面中必须只有1个人物,全身正面"
    "站立并居中,完整展示从头到脚。保持真实单品的颜色、轮廓、材质、"
    "层次和搭配关系。浅色纯净单色背景。禁止多人、分镜、九宫格、"
    "备选造型、换装前后对比、文字、品牌、水印或额外服饰。"
)

TRY_ON_PROMPT = (
    "以第一张全身人物照片为主体,保持人物身份、脸部、发型、体型、"
    "姿势和背景不变。把后续参考图中的整套真实服装准确换到人物身上,"
    "保持每件衣服的颜色、材质、版型、层次和搭配关系,不添加额外服饰、"
    "文字、品牌或水印。输出自然、完整、写实的全身试穿照。"
)
