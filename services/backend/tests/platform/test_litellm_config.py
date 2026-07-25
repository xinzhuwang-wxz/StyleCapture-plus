from pathlib import Path

import yaml  # type: ignore[import-untyped]

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]


def test_litellm_config_exposes_capability_alias_without_embedded_credentials() -> None:
    config_path = REPOSITORY_ROOT / "config" / "litellm.yaml"
    raw = config_path.read_text(encoding="utf-8")
    config = yaml.safe_load(raw)

    assert [entry["model_name"] for entry in config["model_list"]] == [
        "reasoning",
        "vision_understanding",
        "image_generation",
    ]
    reasoning = config["model_list"][0]["litellm_params"]
    vision = config["model_list"][1]["litellm_params"]
    image_generation = config["model_list"][2]["litellm_params"]
    assert reasoning["model"] == "openai/doubao-seed-2-0-lite-260428"
    assert vision["model"] == "openai/doubao-seed-2-0-lite-260428"
    assert image_generation["model"] == "openai/doubao-seedream-5-0-260128"
    assert reasoning["api_key"] == "os.environ/ARK_API_KEY"
    assert vision["api_key"] == "os.environ/ARK_API_KEY"
    assert image_generation["api_key"] == "os.environ/ARK_API_KEY"
    assert vision["api_base"] == "os.environ/ARK_BASE_URL"
    assert "sk-" not in raw
    assert config["general_settings"]["master_key"] == "os.environ/LITELLM_MASTER_KEY"
