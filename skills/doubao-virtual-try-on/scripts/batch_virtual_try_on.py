#!/usr/bin/env python3
# ruff: noqa: RUF001
"""Generate multiple outfits while preserving one accepted source-photo framing anchor."""

from __future__ import annotations

import argparse
import getpass
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import virtual_try_on as core


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate a consistent multi-look try-on set through Volcengine Ark. "
            "All looks preserve the accepted source photo's identity, body, and framing."
        )
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {core.VERSION}")
    parser.add_argument("person_image", type=Path)
    parser.add_argument("outfit_boards", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--look-attempts", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--workers", type=int, choices=(1, 2), default=2)
    parser.add_argument("--size", default="2K")
    parser.add_argument("--watermark", action="store_true")
    parser.add_argument("--api-base", default=core.DEFAULT_BASE_URL)
    parser.add_argument("--understanding-model", default=core.DEFAULT_UNDERSTANDING_MODEL)
    parser.add_argument("--image-model", default=core.DEFAULT_IMAGE_MODEL)
    return parser.parse_args()


def save_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_from_references(
    *,
    api_key: str,
    args: argparse.Namespace,
    prompt: str,
    image_urls: list[str],
) -> dict[str, Any]:
    return core.post_json(
        api_key,
        args.api_base,
        "/images/generations",
        {
            "model": args.image_model,
            "prompt": prompt,
            "image": image_urls,
            "size": args.size,
            "sequential_image_generation": "disabled",
            "stream": False,
            "response_format": "url",
            "watermark": args.watermark,
        },
        timeout=600,
    )


def analyze_identity(
    *,
    api_key: str,
    args: argparse.Namespace,
    person_url: str,
) -> dict[str, Any]:
    return core.chat(
        api_key=api_key,
        api_base=args.api_base,
        model=args.understanding_model,
        prompt="""Analyze the one source-person image for strict identity preservation.
Return only valid JSON:
{
  "source_photo_eligibility": {
    "eligible": true,
    "body_coverage": {
      "neck_and_shoulders": true,
      "torso": true,
      "hips": true,
      "knees": true,
      "calves": true,
      "feet": false
    },
    "rejection_code": null,
    "user_message": ""
  },
  "face_identity": {
    "face_shape": "...",
    "eyes_and_brows": "...",
    "nose": "...",
    "mouth_and_smile": "...",
    "hairline_and_hair": "...",
    "skin_and_distinctive_details": "..."
  },
  "body_geometry_visibility": {
    "shoulders": "visible|partly_visible|concealed",
    "chest": "visible|partly_visible|concealed",
    "waist": "visible|partly_visible|concealed",
    "hips": "visible|partly_visible|concealed"
  },
  "body_geometry_policy": "one short evidence-based instruction",
  "source_pose_and_camera": "...",
  "source_clothes_and_accessories_to_remove": [],
  "identity_lock_instruction": "detailed Chinese instruction"
}

First judge body coverage using only visible evidence. Mark eligible only when the person is
continuously visible from neck and shoulders through both knees and most of both calves. Do not
infer cropped anatomy. Face sharpness or existing face occlusion is not a rejection reason.
Judge shoulder, chest, waist and hip contour visibility separately. The outside edge of loose
source clothing is not a visible body contour. For concealed widths, prescribe conservative
neutral continuity from visible skeletal landmarks; never infer an idealized female shape or
enlarge, slim or reshape chest, waist or hips.
Describe observable geometry instead of attractiveness or style. The identity-lock instruction
must prohibit beautification, face reshaping, eye enlargement, jaw narrowing, nose alteration,
skin whitening, age changes, hairstyle changes, and expression changes. Preserve the exact visible
facial features and existing occlusion. Preserve the exact person, not merely a similar person.""",
        labeled_images=[("IMAGE 1 — sole source-person identity reference", person_url)],
    )


def anchor_prompt(identity: dict[str, Any], corrections: list[Any]) -> str:
    correction_text = (
        "\n上一次身份锚点存在以下问题，必须逐项修正：\n- " + "\n- ".join(map(str, corrections))
        if corrections
        else ""
    )
    return f"""使用图1创建同一个人的标准全身身份锚点照片。图1是唯一身份来源。

身份硬锁：
{identity.get("identity_lock_instruction", "")}
脸部几何描述：
{json.dumps(identity.get("face_identity", {}), ensure_ascii=False)}

绝对要求：
1. 人脸必须与图1是同一个真人，不是相似脸。保留图1的脸型、眼距、眼型、眉形、鼻翼宽度、
   嘴唇形状、微笑时牙齿露出方式、发际线、耳位和真实皮肤质感。
2. 禁止美颜、瘦脸、大眼、磨皮、改变五官比例、改变年龄或更换发型。
3. 生成正面自然站立的完整全身照，头顶到鞋底全部可见；双脚平行，双臂自然下垂，不遮挡躯干。
4. 建立固定且自然的成年女性人体模板：头身比约 1:7.2，肩宽、腰胯、躯干长度、腿长和脚长协调。
5. 固定构图：竖幅，人物垂直居中，头顶留白 6%，鞋底距底边 5%，人物总高度约占画面 89%；
   50mm 标准镜头，视平线在胸口附近，无广角畸变、无仰拍、无俯拍。
6. 穿无标识的合体纯灰短袖 T 恤、深灰直筒长裤、纯白简洁运动鞋；移除图1原有衣服、包、
   首饰和发夹，避免这些物品污染后续换装。
7. 保留图1海边日落环境和自然光方向，生成单张真实相机照片，不要拼贴、文字或人物说明图。
{correction_text}"""


def audit_anchor(
    *,
    api_key: str,
    args: argparse.Namespace,
    person_url: str,
    anchor_url: str,
) -> dict[str, Any]:
    return core.chat(
        api_key=api_key,
        api_base=args.api_base,
        model=args.understanding_model,
        prompt="""Strictly audit a canonical full-body identity anchor.
Return only valid JSON:
{
  "face_identity": {"score": 0, "differences": []},
  "expression_and_hair": {"score": 0, "differences": []},
  "canonical_body_and_camera": {"score": 0, "notes": []},
  "clean_neutral_styling": {"score": 0, "unwanted_carryover": []},
  "overall_score": 0,
  "pass": false,
  "recommended_retry_changes": []
}

IMAGE 1 is ground truth for the person's exact face. IMAGE 2 is the anchor candidate.
Do not award identity points for merely matching gender, ethnicity, hair color or general vibe.
Compare face shape, eye spacing and shape, eyebrows, nose, mouth, teeth/smile, jaw, hairline and
ear placement. Require a complete head-to-shoe body, natural approximately 1:7.2 head-to-body
ratio, straight eye-level 50mm-style camera, centered pose, and no retained source accessories.
Pass only if face_identity >= 88, expression_and_hair >= 88,
canonical_body_and_camera >= 90, clean_neutral_styling >= 90, and overall >= 89.""",
        labeled_images=[
            ("IMAGE 1 — source face identity ground truth", person_url),
            ("IMAGE 2 — generated canonical anchor candidate", anchor_url),
        ],
    )


def anchor_passes(audit: dict[str, Any]) -> bool:
    try:
        return (
            audit.get("pass") is True
            and float(audit["face_identity"]["score"]) >= 88
            and float(audit["expression_and_hair"]["score"]) >= 88
            and float(audit["canonical_body_and_camera"]["score"]) >= 90
            and float(audit["clean_neutral_styling"]["score"]) >= 90
            and float(audit["overall_score"]) >= 89
        )
    except (KeyError, TypeError, ValueError):
        return False


def create_anchor(
    *,
    api_key: str,
    args: argparse.Namespace,
    output_dir: Path,
    person_url: str,
    identity: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    anchor_dir = output_dir / "identity-anchor"
    anchor_dir.mkdir(parents=True, exist_ok=True)
    attempts: list[dict[str, Any]] = []
    corrections: list[Any] = []
    for number in range(1, args.anchor_attempts + 1):
        print(f"Generating identity anchor {number}/{args.anchor_attempts}...", flush=True)
        response = generate_from_references(
            api_key=api_key,
            args=args,
            prompt=anchor_prompt(identity, corrections),
            image_urls=[person_url],
        )
        candidate = anchor_dir / f"attempt-{number}.jpg"
        core.download_result(response, candidate)
        save_json(
            anchor_dir / f"generation-attempt-{number}.json",
            core.response_for_log(response),
        )
        audit = audit_anchor(
            api_key=api_key,
            args=args,
            person_url=person_url,
            anchor_url=core.image_data_url(candidate),
        )
        save_json(anchor_dir / f"audit-attempt-{number}.json", audit)
        score = float(audit.get("overall_score", 0))
        attempts.append(
            {
                "attempt": number,
                "image": candidate.name,
                "audit": f"audit-attempt-{number}.json",
                "overall_score": score,
                "pass": anchor_passes(audit),
            }
        )
        if anchor_passes(audit):
            break
        corrections = list(audit.get("recommended_retry_changes") or [])

    best = max(attempts, key=lambda item: item["overall_score"])
    selected = anchor_dir / "result.jpg"
    shutil.copyfile(anchor_dir / best["image"], selected)
    manifest = {
        "attempts": attempts,
        "selected_attempt": best["attempt"],
        "pass": best["pass"],
        "result": selected.name,
    }
    save_json(anchor_dir / "manifest.json", manifest)
    return selected, manifest


def create_source_anchor(*, output_dir: Path, person_path: Path) -> tuple[Path, dict[str, Any]]:
    """Reuse the accepted source framing without inventing a replacement body."""
    anchor_dir = output_dir / "identity-anchor"
    anchor_dir.mkdir(parents=True, exist_ok=True)
    selected = anchor_dir / f"result{person_path.suffix.lower()}"
    shutil.copyfile(person_path, selected)
    manifest = {
        "attempts": [],
        "selected_attempt": None,
        "pass": True,
        "strategy": "source_framing_lock",
        "result": selected.name,
    }
    save_json(anchor_dir / "manifest.json", manifest)
    return selected, manifest


def analyze_outfit(
    *,
    api_key: str,
    args: argparse.Namespace,
    outfit_url: str,
) -> dict[str, Any]:
    return core.chat(
        api_key=api_key,
        api_base=args.api_base,
        model=args.understanding_model,
        prompt="""Analyze this outfit board for virtual try-on. Return only valid JSON:
{
  "items": [
    {
      "name": "...",
      "category": "garment/shoes/bag/jewelry/hair accessory/other",
      "color": "...",
      "color_signature": "hue, undertone, lightness and surface variation",
      "material": "...",
      "silhouette_and_ease": "...",
      "construction_and_details": "...",
      "correct_wearing_location": "..."
    }
  ],
  "layering_order": [],
  "items_that_form_a_pair": [],
  "outfit_instruction": "detailed Chinese clothing-only instruction"
}

Describe the visible silhouette and wearing ease of every garment (for example fitted, regular,
relaxed, oversized, boxy, flared, structured or draped). Treat a pair of shoes or socks as one
wearable pair, not duplicated objects. Distinguish hair
accessories, earrings, necklaces, bracelets and scrunchies by construction and intended wearing
location. Describe color from visible pixels: include warm/neutral/cool undertone, relative
lightness, and heather/marl/mottled variation where present. Describe visible logos or text
conservatively; never invent extra accessories.""",
        labeled_images=[("IMAGE 1 — sole outfit-board reference", outfit_url)],
    )


def look_prompt(outfit: dict[str, Any], corrections: list[Any]) -> str:
    correction_text = (
        "\n上一次结果存在以下问题，必须逐项修正：\n- " + "\n- ".join(map(str, corrections))
        if corrections
        else ""
    )
    return f"""完成真人换装。参考图角色严格固定：
- 图1：原始真人的唯一面部身份依据。
- 图2：同一真人的标准全身锚点，是身体骨架、头身比、头部大小、姿势、镜头距离、构图和背景的唯一依据。
- 图3：唯一服装与配饰来源。

穿搭清单：
{json.dumps(outfit.get("items", []), ensure_ascii=False)}
叠穿顺序：
{json.dumps(outfit.get("layering_order", []), ensure_ascii=False)}
补充说明：
{outfit.get("outfit_instruction", "")}

身份硬锁：
1. 图1与图2是同一个真人。最终人脸必须精确保持图1的脸型、眼距、眼型、眉形、鼻子、嘴唇、
   牙齿与微笑、下颌、发际线和真实皮肤质感。禁止美颜、瘦脸、大眼、磨皮或生成相似脸。
2. 最终身体必须复用图2的同一骨架：头部像素大小、头身比、肩宽、腰胯、躯干长度、腿长、脚长、
   站姿、双手位置全部不变。禁止重新设计身材。
3. 最终构图必须复用图2：相同画布比例、人物高度、头顶与底边留白、50mm 视角、相机高度、
   拍摄距离、海边背景、光向和地平线。只能换衣，不能缩放人物或改变镜头。
4. 移除图1与图2原有的全部衣服、鞋、包、首饰和发饰。仅穿戴图3清单中的物品，并放在正确位置。
5. 每件单品只出现一次；一双鞋或袜子自然穿在双脚。准确保留颜色、面料、版型、长度、五金、
   图案和层次，不添加额外物品。
6. 单张竖幅真实全身照片，头顶到鞋底完整可见。手脚解剖自然，无重复物体、无拼贴、无说明文字。
{correction_text}"""


def look_prompt_v14(
    outfit: dict[str, Any], application_plan: dict[str, Any], corrections: list[Any]
) -> str:
    correction_text = "\n- ".join(map(str, corrections)) if corrections else "none"
    color_constraints = json.dumps(
        application_plan.get("color_constraints", []), ensure_ascii=False
    )
    silhouettes = json.dumps(
        application_plan.get("silhouette_constraints", []), ensure_ascii=False
    )
    body_visibility = json.dumps(
        application_plan.get("body_geometry_visibility", {}), ensure_ascii=False
    )
    body_policy = str(application_plan.get("body_geometry_policy", "")).strip() or (
        "Preserve visible skeletal landmarks and use conservative neutral volume for concealed "
        "widths; do not enlarge, slim, or reshape the chest, waist, or hips."
    )
    if application_plan.get("apply_shoes") is False:
        shoe_policy = (
            "Omit IMAGE 3 footwear; do not extend, compress or reframe the body to include it."
        )
    else:
        shoe_policy = "Apply footwear only to source feet already visible inside the frame."
    return f"""Create one photorealistic virtual try-on. Follow priorities in order.

P1 PERSON AND FRAME — IMAGE 1 is the only identity source; IMAGE 2 is the exact source framing.
Keep the same visible facial geometry/occlusion, pose, skeleton, limb and torso lengths,
head/body scale, camera, crop and canvas. Do not beautify or reconstruct the person.

P2 BODY VOLUME — clothing changes; the person's body does not.
Observed contour visibility: {body_visibility}
{body_policy}
Never use loose source-clothing edges as body contours or impose a stereotypical body shape.

P3 TARGET OUTFIT — IMAGE 3 pixels are the only clothing truth.
Items: {json.dumps(outfit.get("items", []), ensure_ascii=False)}
Layering: {json.dumps(outfit.get("layering_order", []), ensure_ascii=False)}
Exact color signatures: {color_constraints}
Exact silhouettes/ease: {silhouettes}
Preserve hue, undertone, relative lightness, marl/heather variation, material, cut, volume and
construction. Do not neutralize, whiten, cool, warm, tighten or loosen a target garment.
{shoe_policy}

P4 OUTPUT — replace source clothes with each non-skipped item once. Return one natural camera
photo with the source environment, no collage, labels, floating items or added objects.

Retry corrections: {correction_text}
"""


def audit_look(
    *,
    api_key: str,
    args: argparse.Namespace,
    person_url: str,
    anchor_url: str,
    outfit_url: str,
    result_url: str,
    application_plan: dict[str, Any],
) -> dict[str, Any]:
    return core.chat(
        api_key=api_key,
        api_base=args.api_base,
        model=args.understanding_model,
        prompt="""Strictly audit one identity-locked virtual try-on. Return only valid JSON:
{
  "face_identity": {"score": 0, "differences": []},
  "body_and_head_scale_lock": {"score": 0, "differences": []},
  "camera_and_composition_lock": {"score": 0, "differences": []},
  "outfit_fidelity": {
    "score": 0,
    "silhouette_and_ease_preserved": false,
    "source_garment_fit_leaked": true,
    "matched": [],
    "missing_or_wrong": []
  },
  "application_policy": {
    "shoe_policy_followed": false,
    "no_body_reframing_for_footwear": false,
    "notes": []
  },
  "photorealism": {"score": 0, "artifacts": []},
  "overall_score": 0,
  "pass": false,
  "recommended_retry_changes": []
}

IMAGE 1 is exact face ground truth. IMAGE 2 is exact body, head scale, pose and camera ground
truth. IMAGE 3 is exact outfit ground truth. IMAGE 4 is the generated result.
Do not confuse similar appearance with identity. Compare exact visible facial geometry and do not
lower the identity score merely because the source face is soft or low-resolution. Preserve any
source glasses, sticker, crop or other occlusion instead of repainting or revealing hidden facial
features. Compare IMAGE 4 against IMAGE 2 for head pixel size relative to frame, head-to-body ratio, shoulder width,
torso/leg lengths, stance, crop, horizon and camera distance. Check every outfit-board item and
remove all source accessories. Do not penalize shoes omitted by the resolved plan. Fail if footwear
was forced into a crop without feet, the body was reframed for footwear, or a loose target garment
became fitted to the source garment outline. Pass only if face_identity >= 95,
body_and_head_scale_lock >= 92, camera_and_composition_lock >= 92, outfit_fidelity >= 80,
silhouette_and_ease_preserved=true, source_garment_fit_leaked=false, both application-policy
booleans are true, photorealism >= 85 and overall >= 92.

Resolved application policy:
""" + json.dumps(application_plan, ensure_ascii=False),
        labeled_images=[
            ("IMAGE 1 — exact source face identity", person_url),
            ("IMAGE 2 — exact accepted source framing", anchor_url),
            ("IMAGE 3 — exact outfit board", outfit_url),
            ("IMAGE 4 — generated try-on candidate", result_url),
        ],
    )


def look_passes(audit: dict[str, Any]) -> bool:
    try:
        return (
            audit.get("pass") is True
            and float(audit["face_identity"]["score"]) >= 95
            and float(audit["body_and_head_scale_lock"]["score"]) >= 92
            and float(audit["camera_and_composition_lock"]["score"]) >= 92
            and float(audit["outfit_fidelity"]["score"]) >= 80
            and audit["outfit_fidelity"].get("silhouette_and_ease_preserved") is True
            and audit["outfit_fidelity"].get("source_garment_fit_leaked") is False
            and audit["application_policy"].get("shoe_policy_followed") is True
            and audit["application_policy"].get("no_body_reframing_for_footwear") is True
            and float(audit["photorealism"]["score"]) >= 85
            and float(audit["overall_score"]) >= 92
        )
    except (KeyError, TypeError, ValueError):
        return False


def create_look(
    *,
    index: int,
    outfit_path: Path,
    api_key: str,
    args: argparse.Namespace,
    output_dir: Path,
    person_url: str,
    anchor_url: str,
    identity: dict[str, Any],
) -> dict[str, Any]:
    look_dir = output_dir / f"look-{index:02d}"
    look_dir.mkdir(parents=True, exist_ok=True)
    outfit_url = core.image_data_url(outfit_path)
    outfit = analyze_outfit(api_key=api_key, args=args, outfit_url=outfit_url)
    save_json(look_dir / "outfit-analysis.json", outfit)
    application_plan = core.resolved_application_plan(
        {
            "source_photo_eligibility": identity.get("source_photo_eligibility"),
            "body_geometry_visibility": identity.get("body_geometry_visibility"),
            "body_geometry_policy": identity.get("body_geometry_policy"),
            "outfit_items": outfit.get("items"),
        }
    )
    save_json(look_dir / "application-plan.json", application_plan)
    attempts: list[dict[str, Any]] = []
    corrections: list[Any] = []
    for number in range(1, args.look_attempts + 1):
        print(
            f"Generating look {index} attempt {number}/{args.look_attempts}...",
            flush=True,
        )
        response = generate_from_references(
            api_key=api_key,
            args=args,
            prompt=look_prompt_v14(outfit, application_plan, corrections),
            image_urls=[person_url, anchor_url, outfit_url],
        )
        candidate = look_dir / f"attempt-{number}.jpg"
        core.download_result(response, candidate)
        save_json(
            look_dir / f"generation-attempt-{number}.json",
            core.response_for_log(response),
        )
        audit = audit_look(
            api_key=api_key,
            args=args,
            person_url=person_url,
            anchor_url=anchor_url,
            outfit_url=outfit_url,
            result_url=core.image_data_url(candidate),
            application_plan=application_plan,
        )
        save_json(look_dir / f"audit-attempt-{number}.json", audit)
        score = float(audit.get("overall_score", 0))
        attempts.append(
            {
                "attempt": number,
                "image": candidate.name,
                "audit": f"audit-attempt-{number}.json",
                "overall_score": score,
                "pass": look_passes(audit),
            }
        )
        if look_passes(audit):
            break
        corrections = list(audit.get("recommended_retry_changes") or [])
    best = max(attempts, key=lambda item: item["overall_score"])
    selected = look_dir / "result.jpg"
    shutil.copyfile(look_dir / best["image"], selected)
    manifest = {
        "index": index,
        "outfit_board": str(outfit_path),
        "application_plan": application_plan,
        "attempts": attempts,
        "selected_attempt": best["attempt"],
        "pass": best["pass"],
        "result": selected.name,
    }
    save_json(look_dir / "manifest.json", manifest)
    return {"index": index, "path": selected, "manifest": manifest}


def cross_audit(
    *,
    api_key: str,
    args: argparse.Namespace,
    person_url: str,
    anchor_url: str,
    looks: list[dict[str, Any]],
) -> dict[str, Any]:
    labeled = [
        ("IMAGE 1 — exact source face identity", person_url),
        ("IMAGE 2 — accepted source body/camera framing", anchor_url),
    ]
    for look in sorted(looks, key=lambda item: item["index"]):
        labeled.append(
            (
                f"LOOK {look['index']} — generated outfit result",
                core.image_data_url(look["path"]),
            )
        )
    return core.chat(
        api_key=api_key,
        api_base=args.api_base,
        model=args.understanding_model,
        prompt="""Cross-audit a set of outfit images intended to show the exact same person and
the exact same body/camera setup. Return only valid JSON:
{
  "face_consistency": {"score": 0, "outlier_looks": [], "differences": []},
  "head_scale_consistency": {
    "score": 0,
    "estimated_max_spread_percent": 0,
    "outlier_looks": [],
    "differences": []
  },
  "body_proportion_consistency": {"score": 0, "outlier_looks": [], "differences": []},
  "camera_composition_consistency": {"score": 0, "outlier_looks": [], "differences": []},
  "overall_score": 0,
  "pass": false,
  "recommended_retry_changes": []
}

IMAGE 1 is exact face ground truth and IMAGE 2 is exact head size, body, pose and camera ground
truth. Every later LOOK must match both. Compare all looks side by side. Penalize different face
shape, eyes, jaw, head pixel height, shoulder width, torso/leg proportions, subject scale, crop,
horizon and camera distance. Pass only if face_consistency >= 90, head_scale_consistency >= 94,
estimated head-size spread <= 3%, body_proportion_consistency >= 94,
camera_composition_consistency >= 94 and overall >= 92.""",
        labeled_images=labeled,
    )


def cross_passes(audit: dict[str, Any]) -> bool:
    try:
        has_outliers = any(
            audit[section].get("outlier_looks")
            for section in (
                "face_consistency",
                "head_scale_consistency",
                "body_proportion_consistency",
                "camera_composition_consistency",
            )
        )
        return (
            audit.get("pass") is True
            and not has_outliers
            and float(audit["face_consistency"]["score"]) >= 90
            and float(audit["head_scale_consistency"]["score"]) >= 94
            and float(audit["head_scale_consistency"]["estimated_max_spread_percent"]) <= 3
            and float(audit["body_proportion_consistency"]["score"]) >= 94
            and float(audit["camera_composition_consistency"]["score"]) >= 94
            and float(audit["overall_score"]) >= 92
        )
    except (KeyError, TypeError, ValueError):
        return False


def main() -> int:
    args = parse_args()
    if len(args.outfit_boards) < 2:
        raise ValueError("Batch mode requires at least two outfit boards")
    person_path = core.require_image(args.person_image, "Person image")
    outfit_paths = [
        core.require_image(path, f"Outfit board {index}")
        for index, path in enumerate(args.outfit_boards, 1)
    ]
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = os.getenv("ARK_API_KEY")
    if not api_key and sys.stdin.isatty():
        api_key = getpass.getpass("ARK_API_KEY: ")
    if not api_key:
        raise RuntimeError(
            "ARK_API_KEY is required. Set it in the environment or run interactively."
        )

    person_url = core.image_data_url(person_path)
    print("Analyzing strict identity geometry...", flush=True)
    identity = analyze_identity(api_key=api_key, args=args, person_url=person_url)
    save_json(output_dir / "identity-analysis.json", identity)
    rejection = core.source_photo_rejection(identity)
    if rejection is not None:
        code, message = rejection
        manifest = {
            "models": {
                "understanding": args.understanding_model,
                "generation": args.image_model,
            },
            "person_image": str(person_path),
            "outfit_boards": [str(path) for path in outfit_paths],
            "hard_pass": False,
            "quality_status": "input_rejected",
            "failure_code": code,
            "user_message": message,
            "anchor": None,
            "looks": [],
        }
        save_json(output_dir / "manifest.json", manifest)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
        return 2

    anchor_path, anchor_manifest = create_source_anchor(
        output_dir=output_dir,
        person_path=person_path,
    )
    anchor_url = core.image_data_url(anchor_path)

    looks: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = [
            executor.submit(
                create_look,
                index=index,
                outfit_path=outfit_path,
                api_key=api_key,
                args=args,
                output_dir=output_dir,
                person_url=person_url,
                anchor_url=anchor_url,
                identity=identity,
            )
            for index, outfit_path in enumerate(outfit_paths, 1)
        ]
        for future in as_completed(futures):
            looks.append(future.result())

    print("Cross-auditing face, head scale, body and camera consistency...", flush=True)
    batch_audit = cross_audit(
        api_key=api_key,
        args=args,
        person_url=person_url,
        anchor_url=anchor_url,
        looks=looks,
    )
    batch_audit["hard_pass"] = cross_passes(batch_audit)
    save_json(output_dir / "cross-look-audit.json", batch_audit)
    look_manifests: list[dict[str, Any]] = [
        dict(look["manifest"]) for look in sorted(looks, key=lambda item: item["index"])
    ]
    manifest: dict[str, Any] = {
        "models": {
            "understanding": args.understanding_model,
            "generation": args.image_model,
        },
        "person_image": str(person_path),
        "outfit_boards": [str(path) for path in outfit_paths],
        "anchor": anchor_manifest,
        "looks": look_manifests,
        "cross_look_pass": cross_passes(batch_audit),
        "cross_look_audit": "cross-look-audit.json",
    }
    manifest["hard_pass"] = (
        bool(anchor_manifest["pass"])
        and all(bool(look["pass"]) for look in look_manifests)
        and bool(manifest["cross_look_pass"])
    )
    manifest["quality_status"] = "pass" if manifest["hard_pass"] else "hard_fail"
    save_json(output_dir / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0 if manifest["hard_pass"] else 3


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
