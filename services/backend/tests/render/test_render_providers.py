from __future__ import annotations

import base64
import json
from collections.abc import Callable
from io import BytesIO
from pathlib import Path
from typing import Any

import httpx
import pytest
from PIL import Image
from stylecapture_backend.features.capture.domain import ImagePayload
from stylecapture_backend.features.render.infrastructure import providers
from stylecapture_backend.features.render.infrastructure.providers import (
    DoubaoVirtualTryOnSkillGenerator,
    FashnTryOnGenerator,
    LiteLLMImageGenerator,
    RenderProviderError,
    RenderProviderUnavailable,
)


class FakeSkillProcess:
    def __init__(
        self,
        output_dir: Path,
        *,
        returncode: int = 0,
        quality_status: str | None = None,
        user_message: str | None = None,
        hard_pass: bool | None = None,
        release_eligible: bool | None = None,
        delivery_eligible: bool | None = None,
        audit_release_eligible: bool | None = None,
        audit_summary: dict[str, object] | None = None,
        result_body: bytes | None = None,
    ) -> None:
        self.returncode = returncode
        self._output_dir = output_dir
        self._quality_status = quality_status
        self._user_message = user_message
        self._hard_pass = hard_pass
        self._release_eligible = release_eligible
        self._delivery_eligible = delivery_eligible
        self._audit_release_eligible = audit_release_eligible
        self._audit_summary = audit_summary
        self._result_body = png_body() if result_body is None else result_body

    async def communicate(self) -> tuple[bytes, bytes]:
        self._output_dir.mkdir(parents=True)
        (self._output_dir / "result.jpg").write_bytes(self._result_body)
        (self._output_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "hard_pass": (
                        self.returncode == 0 if self._hard_pass is None else self._hard_pass
                    ),
                    "release_eligible": self._release_eligible,
                    "delivery_eligible": self._delivery_eligible,
                    "audit_release_eligible": self._audit_release_eligible,
                    "quality_status": self._quality_status
                    or ("pass" if self.returncode == 0 else "hard_fail"),
                    "selected_attempt": 2,
                    "user_message": self._user_message,
                    "selected_audit_summary": self._audit_summary,
                }
            ),
            encoding="utf-8",
        )
        return b"completed", b""


@pytest.mark.asyncio
async def test_doubao_skill_generator_runs_audited_skill_and_returns_only_passed_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_path = tmp_path / "virtual_try_on.py"
    skill_path.write_text("# test entry", encoding="utf-8")
    calls: list[tuple[tuple[object, ...], dict[str, object]]] = []

    async def create_process(*args: object, **kwargs: object) -> FakeSkillProcess:
        calls.append((args, kwargs))
        output_dir = Path(str(args[args.index("--output-dir") + 1]))
        return FakeSkillProcess(output_dir)

    monkeypatch.setattr(providers.asyncio, "create_subprocess_exec", create_process)
    generator = DoubaoVirtualTryOnSkillGenerator(
        skill_path=skill_path,
        api_key="ark-secret",
        understanding_model="understanding-model",
        image_model="image-model",
        timeout_seconds=10,
    )

    generated = await generator.try_on(
        model_image=image_payload(color=(1, 2, 3)),
        outfit_board=image_payload(color=(4, 5, 6)),
    )

    assert generated.content_type == "image/png"
    assert generated.provider_trace.provider == "doubao_virtual_try_on_skill"
    assert generated.provider_trace.parameters["hard_pass"] is True
    assert generated.provider_trace.parameters["selected_attempt"] == 2
    args, kwargs = calls[0]
    assert str(skill_path) in args
    assert "--max-attempts" in args
    assert kwargs["env"]["ARK_API_KEY"] == "ark-secret"  # type: ignore[index]
    assert "ark-secret" not in str(args)


@pytest.mark.asyncio
async def test_doubao_skill_generator_returns_review_required_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_path = tmp_path / "virtual_try_on.py"
    skill_path.write_text("# test entry", encoding="utf-8")

    async def create_process(*args: object, **kwargs: object) -> FakeSkillProcess:
        output_dir = Path(str(args[args.index("--output-dir") + 1]))
        return FakeSkillProcess(
            output_dir,
            quality_status="review_required",
            hard_pass=False,
            delivery_eligible=True,
            audit_release_eligible=True,
        )

    monkeypatch.setattr(providers.asyncio, "create_subprocess_exec", create_process)
    generator = DoubaoVirtualTryOnSkillGenerator(
        skill_path=skill_path,
        api_key="ark-secret",
        understanding_model="understanding-model",
        image_model="image-model",
        timeout_seconds=10,
    )

    generated = await generator.try_on(
        model_image=image_payload(color=(1, 2, 3)),
        outfit_board=image_payload(color=(4, 5, 6)),
    )

    assert generated.provider_trace.parameters["hard_pass"] is False
    assert generated.provider_trace.parameters["audit_release_eligible"] is True
    assert generated.provider_trace.parameters["delivery_eligible"] is True
    assert generated.provider_trace.parameters["quality_status"] == "review_required"


@pytest.mark.asyncio
async def test_doubao_skill_generator_returns_best_generated_result_needing_attention(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_path = tmp_path / "virtual_try_on.py"
    skill_path.write_text("# test entry", encoding="utf-8")

    async def create_process(*args: object, **kwargs: object) -> FakeSkillProcess:
        output_dir = Path(str(args[args.index("--output-dir") + 1]))
        return FakeSkillProcess(
            output_dir,
            quality_status="needs_attention",
            hard_pass=False,
            delivery_eligible=True,
            audit_release_eligible=False,
            audit_summary={"identity_score": 10},
        )

    monkeypatch.setattr(providers.asyncio, "create_subprocess_exec", create_process)
    generator = DoubaoVirtualTryOnSkillGenerator(
        skill_path=skill_path,
        api_key="ark-secret",
        understanding_model="understanding-model",
        image_model="image-model",
        timeout_seconds=10,
    )

    generated = await generator.try_on(
        model_image=image_payload(color=(1, 2, 3)),
        outfit_board=image_payload(color=(4, 5, 6)),
    )

    assert generated.provider_trace.parameters["hard_pass"] is False
    assert generated.provider_trace.parameters["audit_release_eligible"] is False
    assert generated.provider_trace.parameters["delivery_eligible"] is True
    assert generated.provider_trace.parameters["quality_status"] == "needs_attention"
    assert generated.provider_trace.parameters["audit_summary"] == {"identity_score": 10}


@pytest.mark.asyncio
async def test_doubao_skill_generator_rejects_invalid_generated_image(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_path = tmp_path / "virtual_try_on.py"
    skill_path.write_text("# test entry", encoding="utf-8")

    async def create_process(*args: object, **kwargs: object) -> FakeSkillProcess:
        output_dir = Path(str(args[args.index("--output-dir") + 1]))
        return FakeSkillProcess(
            output_dir,
            delivery_eligible=True,
            result_body=b"not-an-image",
        )

    monkeypatch.setattr(providers.asyncio, "create_subprocess_exec", create_process)
    generator = DoubaoVirtualTryOnSkillGenerator(
        skill_path=skill_path,
        api_key="ark-secret",
        understanding_model="understanding-model",
        image_model="image-model",
        timeout_seconds=10,
    )

    with pytest.raises(RenderProviderError) as captured:
        await generator.try_on(
            model_image=image_payload(color=(1, 2, 3)),
            outfit_board=image_payload(color=(4, 5, 6)),
        )

    assert captured.value.code == "render_provider_schema_invalid"
    assert "invalid result image" in str(captured.value)


@pytest.mark.asyncio
async def test_doubao_skill_generator_surfaces_source_photo_rejection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    skill_path = tmp_path / "virtual_try_on.py"
    skill_path.write_text("# test entry", encoding="utf-8")
    rejection = "照片只到大腿，无法可靠保持真实头身比例，请重新上传露出膝盖和小腿的照片。"  # noqa: RUF001

    async def create_process(*args: object, **kwargs: object) -> FakeSkillProcess:
        output_dir = Path(str(args[args.index("--output-dir") + 1]))
        return FakeSkillProcess(
            output_dir,
            returncode=2,
            quality_status="input_rejected",
            user_message=rejection,
        )

    monkeypatch.setattr(providers.asyncio, "create_subprocess_exec", create_process)
    generator = DoubaoVirtualTryOnSkillGenerator(
        skill_path=skill_path,
        api_key="ark-secret",
        understanding_model="understanding-model",
        image_model="image-model",
        timeout_seconds=10,
    )

    with pytest.raises(RenderProviderError) as captured:
        await generator.try_on(
            model_image=image_payload(color=(1, 2, 3)),
            outfit_board=image_payload(color=(4, 5, 6)),
        )

    assert captured.value.code == "try_on_source_photo_ineligible"
    assert str(captured.value) == rejection
    assert captured.value.retryable is False


def image_payload(
    *,
    color: tuple[int, int, int] = (139, 92, 246),
    content_type: str = "image/png",
) -> ImagePayload:
    buffer = BytesIO()
    Image.new("RGB", (16, 16), color=color).save(buffer, format="PNG")
    body = buffer.getvalue()
    return ImagePayload(
        object_key="derived/test/input.png",
        content_type=content_type,
        body=body,
        sha256="a" * 64,
    )


def png_body(color: tuple[int, int, int] = (20, 30, 40)) -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (8, 8), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def b64_image(body: bytes) -> str:
    return base64.b64encode(body).decode("ascii")


def transport_for(
    handler: Callable[[httpx.Request], httpx.Response],
) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.mark.asyncio
async def test_litellm_image_generator_uses_alias_and_returns_base64_image() -> None:
    output = png_body()
    requests: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(
            {
                "url": str(request.url),
                "authorization": request.headers.get("authorization"),
                "payload": request.read(),
            }
        )
        return httpx.Response(
            200,
            json={"data": [{"b64_json": b64_image(output)}]},
        )

    generator = LiteLLMImageGenerator(
        capability_alias="image_generation",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="gateway-secret",
        transport=transport_for(handler),
    )

    generated = await generator.generate(
        prompt="生成像素小人封面",
        images=[image_payload()],
        size="1024x1024",
        seed=482731,
        guidance_scale=7.0,
    )

    assert generated.body == output
    assert generated.content_type == "image/png"
    assert generated.sha256
    assert generated.provider_trace.provider == "litellm"
    assert generated.provider_trace.model == "image_generation"
    assert len(requests) == 1
    assert requests[0]["url"] == "http://litellm:4000/v1/images/generations"
    assert requests[0]["authorization"] == "Bearer gateway-secret"
    payload = requests[0]["payload"]
    assert b"image_generation" in payload
    assert b"gateway-secret" not in payload
    assert b"data:image/png;base64," in payload
    assert b'"image":' in payload
    assert b'"sequential_image_generation":"disabled"' in payload
    assert b'"watermark":false' in payload
    assert b'"seed":482731' in payload
    assert b'"guidance_scale":7.0' in payload
    assert generated.provider_trace.parameters["seed"] == 482731
    assert generated.provider_trace.parameters["guidance_scale"] == 7.0


@pytest.mark.asyncio
async def test_litellm_image_generator_rejects_invalid_stability_controls() -> None:
    generator = LiteLLMImageGenerator(
        capability_alias="image_generation",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="gateway-secret",
        transport=transport_for(lambda _request: httpx.Response(500)),
    )

    with pytest.raises(ValueError, match="seed"):
        await generator.generate(prompt="像素卡", images=[], seed=-1)
    with pytest.raises(ValueError, match="guidance"):
        await generator.generate(prompt="像素卡", images=[], guidance_scale=10.5)


@pytest.mark.asyncio
async def test_litellm_image_generator_downloads_url_output_with_limits() -> None:
    output = png_body()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/images/generations"):
            return httpx.Response(200, json={"data": [{"url": "https://cdn.test/render.png"}]})
        return httpx.Response(200, headers={"content-type": "image/png"}, content=output)

    generator = LiteLLMImageGenerator(
        capability_alias="image_generation",
        gateway_base_url="http://litellm:4000/v1",
        gateway_api_key="gateway-secret",
        download_max_bytes=2,
        transport=transport_for(handler),
    )

    with pytest.raises(RenderProviderError) as error:
        await generator.generate(prompt="生成真人搭配图", images=[image_payload()])

    assert error.value.code == "render_provider_output_too_large"
    assert error.value.retryable is False


@pytest.mark.asyncio
async def test_fashn_try_on_reports_missing_key_as_unavailable() -> None:
    generator = FashnTryOnGenerator(api_key=" ")

    with pytest.raises(RenderProviderUnavailable):
        await generator.try_on(model_image=image_payload(), garment_image=image_payload())


@pytest.mark.asyncio
async def test_fashn_try_on_posts_run_and_polls_base64_output(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = png_body((220, 120, 20))
    calls: list[tuple[str, dict[str, Any] | None, str | None]] = []

    async def no_sleep(seconds: float) -> None:
        calls.append(("sleep", {"seconds": seconds}, None))

    monkeypatch.setattr(providers, "_sleep", no_sleep)

    def handler(request: httpx.Request) -> httpx.Response:
        payload = request.read()
        if request.url.path == "/v1/run":
            calls.append(("run", json.loads(payload), request.headers.get("authorization")))
            return httpx.Response(200, json={"id": "pred_123"})
        if request.url.path == "/v1/status/pred_123":
            calls.append(("status", None, request.headers.get("authorization")))
            if len([call for call in calls if call[0] == "status"]) == 1:
                return httpx.Response(200, json={"status": "processing"})
            return httpx.Response(
                200,
                json={"status": "completed", "output": [b64_image(output)]},
            )
        return httpx.Response(404)

    generator = FashnTryOnGenerator(
        api_base_url="https://api.fashn.ai/v1",
        api_key="fashn-secret",
        poll_interval_seconds=0.01,
        poll_timeout_seconds=1,
        transport=transport_for(handler),
    )

    generated = await generator.try_on(
        model_image=image_payload(color=(1, 2, 3)),
        garment_image=image_payload(color=(4, 5, 6)),
        mode="balanced",
    )

    assert generated.body == output
    assert generated.content_type == "image/png"
    assert generated.provider_trace.provider == "fashn"
    assert generated.provider_trace.model == "tryon-v1.6"
    run_payload = calls[0][1]
    assert isinstance(run_payload, dict)
    assert run_payload["model_name"] == "tryon-v1.6"
    inputs = run_payload["inputs"]
    assert isinstance(inputs, dict)
    assert inputs["return_base64"] is True
    assert inputs["category"] == "auto"
    assert inputs["output_format"] == "png"
    assert str(inputs["model_image"]).startswith("data:image/png;base64,")
    assert "fashn-secret" not in str(run_payload)
    assert all(
        authorization == "Bearer fashn-secret"
        for name, _payload, authorization in calls
        if name in {"run", "status"}
    )
