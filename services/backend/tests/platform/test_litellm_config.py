from pathlib import Path

import yaml  # type: ignore[import-untyped]

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def test_litellm_config_exposes_capability_alias_without_embedded_credentials() -> None:
    config_path = REPOSITORY_ROOT / "config" / "litellm.yaml"
    raw = config_path.read_text(encoding="utf-8")
    config = yaml.safe_load(raw)

    entries = config["model_list"]
    models = {entry["model_name"]: entry["litellm_params"] for entry in entries}
    assert len(models) == len(entries)
    assert {
        "reasoning",
        "vision_understanding",
        "visual_grounding",
        "outfit_analysis",
        "outfit_analysis_fallback",
        "image_generation",
    }.issubset(models)
    reasoning = models["reasoning"]
    vision = models["vision_understanding"]
    grounding = models["visual_grounding"]
    outfit_analysis = models["outfit_analysis"]
    image_generation = models["image_generation"]
    assert reasoning["model"] == "os.environ/STYLECAPTURE_TEXT_MODEL"
    assert vision["model"] == "os.environ/STYLECAPTURE_TEXT_MODEL"
    assert grounding["model"] == "os.environ/STYLECAPTURE_TEXT_MODEL"
    assert outfit_analysis["model"] == "os.environ/STYLECAPTURE_TEXT_MODEL"
    assert models["outfit_analysis_fallback"]["model"] == (
        "os.environ/STYLECAPTURE_TEXT_MODEL"
    )
    assert image_generation["model"] == "os.environ/STYLECAPTURE_IMAGE_MODEL"
    assert models["candidate_doubao_seed_2_0_lite_260428"]["model"] == (
        "openai/doubao-seed-2-0-lite-260428"
    )
    assert models["candidate_doubao_seed_2_0_mini_260428"]["model"] == (
        "openai/doubao-seed-2-0-mini-260428"
    )
    for candidate_alias in (
        "candidate_doubao_seed_2_0_lite_260428",
        "candidate_doubao_seed_2_0_mini_260428",
    ):
        assert models[candidate_alias]["api_base"] == "os.environ/ARK_BASE_URL"
        assert models[candidate_alias]["api_key"] == "os.environ/ARK_API_KEY"
    assert reasoning["api_key"] == "os.environ/STYLECAPTURE_AI_API_KEY"
    assert vision["api_key"] == "os.environ/STYLECAPTURE_AI_API_KEY"
    assert grounding["api_key"] == "os.environ/STYLECAPTURE_AI_API_KEY"
    assert outfit_analysis["api_key"] == "os.environ/STYLECAPTURE_AI_API_KEY"
    assert models["outfit_analysis_fallback"]["api_key"] == (
        "os.environ/STYLECAPTURE_AI_API_KEY"
    )
    assert image_generation["api_key"] == "os.environ/STYLECAPTURE_AI_API_KEY"
    assert vision["api_base"] == "os.environ/STYLECAPTURE_AI_API_BASE"
    assert "sk-" not in raw
    assert config["general_settings"]["master_key"] == "os.environ/LITELLM_MASTER_KEY"
