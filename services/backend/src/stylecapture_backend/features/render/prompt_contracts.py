from __future__ import annotations

PIXEL_COVER_CAPABILITY_ID = "look.pixel_cover"
PIXEL_COVER_OUTPUT_SIZE = "1728x2304"
PIXEL_COVER_PROMPT_VERSION = "look-pixel-cover-zh-v4"
PIXEL_COVER_SCHEMA_VERSION = "generated-image-v1"

TRY_ON_CAPABILITY_ID = "look.virtual_try_on"
TRY_ON_PROMPT_VERSION = "look-virtual-try-on-zh-v3"
TRY_ON_SCHEMA_VERSION = "generated-image-v1"

PIXEL_COVER_PROMPT = (
    "输出固定为竖版3:4像素人物卡 (1728x2304), 禁止使用1:1方形画布; 完整保留从头顶到鞋底的人物比例与四周留白, 不得压扁、裁掉脚部或让人物贴边。"
    "第一张参考图如果是完整穿搭,以它的整体轮廓、配色和搭配关系为主;"
    "最后一张参考图是这套穿搭真实单品的拼贴,用于补足材质和细节。"
    "把参考图里的上衣、下装、外套、鞋履和配饰组合到同一个且仅一个"
    "StyleCapture 可爱像素小人身上。画面中必须只有1个人物,全身正面"
    "站立并居中,完整展示从头到脚。输出竖版3:4构图,人物不得拉伸、压扁或裁切。保持真实单品的颜色、轮廓、材质、"
    "层次和搭配关系。使用清晰可见的粗像素方块与阶梯边缘,像素块约为"
    "成图的6-10px,每个服装平面只用3-4个色阶,避免细碎微像素、写实"
    "纹理、3D光照或油画笔触。背景从参考图提取克制的两色基调,只加入"
    "1-3个与场景有关的低对比像素小图标、少量星点和脚下椭圆阴影;不要"
    "复刻完整房间或默认使用粉色、蝴蝶结、爱心、花朵。禁止多人、分镜、"
    "九宫格、备选造型、换装前后对比、文字、品牌、水印或额外服饰。"
)

TRY_ON_PROMPT = (
    "以第一张全身人物照片为主体,保持人物身份、脸部、发型、体型、"
    "姿势和背景不变。把后续参考图中的整套真实服装准确换到人物身上,"
    "保持每件衣服的颜色、材质、版型、层次和搭配关系,不添加额外服饰、"
    "文字、品牌或水印。输出竖版3:4、自然、完整的写实全身试穿照,人物不得拉伸、压扁或裁切。"
)
