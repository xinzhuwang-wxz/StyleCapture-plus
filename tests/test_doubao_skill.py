"""Offline contract tests for the shareable Doubao virtual try-on skill."""

from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from email.message import Message
from importlib import util
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = REPO_ROOT / "skills" / "doubao-virtual-try-on"
SCRIPT_DIR = SKILL_DIR / "scripts"


def load_script_module(name: str):
    spec = util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    assert spec is not None
    module = util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPT_DIR))
    try:
        assert spec.loader is not None
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPT_DIR))
    return module


class FakeImageResponse:
    def __init__(self, body: bytes, content_type: str = "image/jpeg") -> None:
        self._body = body
        self._offset = 0
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self) -> FakeImageResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            size = len(self._body) - self._offset
        chunk = self._body[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


class DoubaoSkillContractTest(unittest.TestCase):
    def test_cli_entry_points_are_available(self) -> None:
        for script in ("virtual_try_on.py", "batch_virtual_try_on.py"):
            path = SKILL_DIR / "scripts" / script
            help_run = subprocess.run(
                [sys.executable, "-B", str(path), "--help"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(help_run.returncode, 0, help_run.stderr)
            self.assertIn("--output-dir", help_run.stdout)

            version_run = subprocess.run(
                [sys.executable, "-B", str(path), "--version"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(version_run.returncode, 0, version_run.stderr)
            self.assertIn("1.4.1", version_run.stdout)

    def test_single_try_on_contract_strictly_locks_exact_face_geometry(self) -> None:
        core = load_script_module("virtual_try_on")
        source = Path(core.__file__).read_text(encoding="utf-8")

        self.assertIn("Keep the exact same visible face", source)
        self.assertIn("face shape, jawline", source)
        self.assertIn("identity_preservation.score >= 95", source)
        self.assertIn("overall_score >= 92", source)
        self.assertIn("Omit IMAGE 2 footwear", source)
        self.assertIn("source garment's tightness", source)

    def test_source_photo_gate_ignores_face_clarity_but_requires_body_coverage(self) -> None:
        core = load_script_module("virtual_try_on")
        eligible = {
            "source_photo_eligibility": {
                "eligible": True,
                "body_coverage": {
                    "neck_and_shoulders": True,
                    "torso": True,
                    "hips": True,
                    "knees": True,
                    "calves": True,
                    "feet": False,
                },
            }
        }
        self.assertIsNone(core.source_photo_rejection(eligible))

        eligible["source_photo_eligibility"]["body_coverage"]["knees"] = False
        self.assertIsNotNone(core.source_photo_rejection(eligible))

    def test_application_plan_skips_shoes_when_source_feet_are_not_visible(self) -> None:
        core = load_script_module("virtual_try_on")
        analysis = {
            "source_photo_eligibility": {
                "eligible": True,
                "body_coverage": {
                    "neck_and_shoulders": True,
                    "torso": True,
                    "hips": True,
                    "knees": True,
                    "calves": True,
                    "feet": False,
                },
            },
            "outfit_items": [
                {"name": "运动鞋", "category": "shoes"},
                {
                    "name": "宽松球衣",
                    "category": "garment",
                    "silhouette_and_ease": "relaxed oversized fit",
                },
            ],
        }
        plan = core.resolved_application_plan(analysis)
        self.assertTrue(plan["outfit_has_shoes"])
        self.assertFalse(plan["apply_shoes"])
        self.assertEqual(plan["skipped_categories"], ["shoes"])
        self.assertIn("relaxed oversized fit", plan["silhouette_constraints"])

    def test_generation_prompt_is_short_prioritized_and_color_body_aware(self) -> None:
        core = load_script_module("virtual_try_on")
        analysis = {
            "person_identity": "same visible face and glasses",
            "body_geometry_visibility": {
                "shoulders": "visible",
                "chest": "concealed",
                "waist": "concealed",
                "hips": "partly_visible",
            },
            "body_geometry_policy": (
                "Keep source shoulder and hip landmarks; use conservative neutral torso volume."
            ),
            "source_photo_eligibility": {"body_coverage": {"feet": True}},
            "outfit_items": [
                {
                    "name": "针织上衣",
                    "category": "garment",
                    "color": "浅灰",
                    "color_signature": "warm light heather gray, not white or cool gray",
                    "silhouette_and_ease": "close fit without changing the wearer's body",
                }
            ],
        }
        plan = core.resolved_application_plan(analysis)
        prompt = core.build_generation_prompt(analysis, plan)

        self.assertIn("P1 PERSON AND FRAME", prompt)
        self.assertIn("P2 BODY VOLUME", prompt)
        self.assertIn("P3 TARGET OUTFIT", prompt)
        self.assertIn("warm light heather gray, not white or cool gray", prompt)
        self.assertIn("use conservative neutral torso volume", prompt)
        self.assertIn("Do not neutralize, whiten, cool, warm", prompt)
        self.assertNotIn("stereotypical female", prompt)
        self.assertLess(len(prompt), 3500)

    def test_soft_visible_face_still_requires_exact_identity(self) -> None:
        core = load_script_module("virtual_try_on")
        audit = {
            "identity_preservation": {
                "score": 96,
                "source_face_visibility": "soft",
                "exact_same_person": False,
                "visible_identity_cues_preserved": True,
                "facial_features_changed": False,
                "beautification_detected": False,
                "source_occlusion_preserved": True,
            },
            "body_framing": {
                "score": 95,
                "head_through_calves_visible": True,
                "natural_head_to_body_ratio": True,
                "no_vertical_compression": True,
                "source_pose_and_camera_preserved": True,
            },
            "outfit_fidelity": {
                "score": 90,
                "silhouette_and_ease_preserved": True,
                "source_garment_fit_leaked": False,
            },
            "application_policy": {
                "shoe_policy_followed": True,
                "no_body_reframing_for_footwear": True,
            },
            "photorealism": {"score": 90, "artifacts": []},
            "overall_score": 95,
            "pass": True,
        }
        self.assertFalse(core.audit_passes(audit))
        audit["identity_preservation"]["exact_same_person"] = True
        self.assertTrue(core.audit_passes(audit))

    def test_ineligible_source_stops_before_paid_generation(self) -> None:
        core = load_script_module("virtual_try_on")
        with tempfile.TemporaryDirectory() as temporary:
            person = Path(temporary) / "person.png"
            outfit = Path(temporary) / "outfit.png"
            person.write_bytes(b"png")
            outfit.write_bytes(b"png")
            output = Path(temporary) / "out"
            args = unittest.mock.Mock(
                person_image=person,
                outfit_board=outfit,
                output_dir=output,
                style_reference=None,
                api_base="https://ark.example.com/api/v3",
                understanding_model="understanding",
                image_model="image",
                max_attempts=1,
                size="2K",
                watermark=False,
            )
            generation = mock.Mock()
            with (
                mock.patch.object(core, "parse_args", return_value=args),
                mock.patch.dict(core.os.environ, {"ARK_API_KEY": "test-key"}),
                mock.patch.object(core, "require_image", side_effect=lambda path, label: path),
                mock.patch.object(core, "image_data_url", return_value="data:image/png;base64,x"),
                mock.patch.object(
                    core,
                    "analyze_inputs",
                    return_value={
                        "source_photo_eligibility": {
                            "eligible": False,
                            "body_coverage": {
                                "neck_and_shoulders": True,
                                "torso": True,
                                "hips": True,
                                "knees": False,
                                "calves": False,
                                "feet": False,
                            },
                            "user_message": "照片只到大腿，请重新上传露出膝盖和小腿的照片。",  # noqa: RUF001
                        }
                    },
                ),
                mock.patch.object(core, "generate_image", generation),
            ):
                self.assertEqual(core.main(), 2)

            generation.assert_not_called()
            manifest = (output / "manifest.json").read_text(encoding="utf-8")
            self.assertIn('"quality_status": "input_rejected"', manifest)
            self.assertIn("照片只到大腿", manifest)

    def test_download_rejects_non_https_private_and_local_urls(self) -> None:
        core = load_script_module("virtual_try_on")
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            core.download_result({"data": [{"url": "http://example.com/result.jpg"}]}, Path("x"))

        with (
            mock.patch.object(
                core.socket,
                "getaddrinfo",
                return_value=[(None, None, None, "", ("10.0.0.5", 443))],
            ),
            self.assertRaisesRegex(ValueError, "non-public"),
        ):
            core.download_result(
                {"data": [{"url": "https://cdn.example.com/result.jpg"}]},
                Path("x"),
            )

        with self.assertRaisesRegex(ValueError, "not allowed"):
            core.download_result({"data": [{"url": "https://localhost/result.jpg"}]}, Path("x"))

    def test_download_requires_image_content_type_and_caps_streamed_bytes(self) -> None:
        core = load_script_module("virtual_try_on")
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "result.jpg"
            with (
                mock.patch.object(
                    core.socket,
                    "getaddrinfo",
                    return_value=[(None, None, None, "", ("93.184.216.34", 443))],
                ),
                mock.patch.object(
                    core.urllib.request,
                    "urlopen",
                    return_value=FakeImageResponse(b"not-image", "text/plain"),
                ),
                self.assertRaisesRegex(RuntimeError, "non-image Content-Type"),
            ):
                core.download_result(
                    {"data": [{"url": "https://cdn.example.com/result.jpg"}]},
                    target,
                )

            oversized = b"x" * (core.MAX_IMAGE_DOWNLOAD_BYTES + 1)
            with (
                mock.patch.object(
                    core.socket,
                    "getaddrinfo",
                    return_value=[(None, None, None, "", ("93.184.216.34", 443))],
                ),
                mock.patch.object(
                    core.urllib.request,
                    "urlopen",
                    return_value=FakeImageResponse(oversized, "image/jpeg"),
                ),
                self.assertRaisesRegex(RuntimeError, "exceeds 20 MB"),
            ):
                core.download_result(
                    {"data": [{"url": "https://cdn.example.com/result.jpg"}]},
                    target,
                )

    def test_b64_json_download_is_size_capped_and_never_logged(self) -> None:
        core = load_script_module("virtual_try_on")
        payload = "x" * ((core.MAX_IMAGE_DOWNLOAD_BYTES + 1) * 4 // 3 + 8)
        with (
            tempfile.TemporaryDirectory() as temporary,
            self.assertRaisesRegex(RuntimeError, "exceeds 20 MB"),
        ):
            core.download_result({"data": [{"b64_json": payload}]}, Path(temporary) / "result.jpg")

        logged = core.response_for_log(
            {
                "data": [
                    {
                        "url": "https://signed.example.com/result.jpg?X-Amz-Signature=secret",
                        "b64_json": "secret-image",
                    }
                ],
                "Authorization": "Bearer secret",
                "api_key": "secret",
            }
        )
        serialized = repr(logged)
        self.assertNotIn("secret", serialized)
        self.assertNotIn("X-Amz-Signature", serialized)
        self.assertNotIn("b64_json': 'secret-image", serialized)

    def test_single_try_on_returns_hard_fail_exit_when_best_audit_fails(self) -> None:
        core = load_script_module("virtual_try_on")
        with tempfile.TemporaryDirectory() as temporary:
            person = Path(temporary) / "person.png"
            outfit = Path(temporary) / "outfit.png"
            person.write_bytes(b"png")
            outfit.write_bytes(b"png")
            output = Path(temporary) / "out"
            args = unittest.mock.Mock(
                person_image=person,
                outfit_board=outfit,
                output_dir=output,
                style_reference=None,
                api_base="https://ark.example.com/api/v3",
                understanding_model="understanding",
                image_model="image",
                max_attempts=1,
                size="2K",
                watermark=False,
            )
            failing_audit = {
                "identity_preservation": {
                    "score": 10,
                    "source_face_visibility": "clear",
                    "exact_same_person": False,
                    "visible_identity_cues_preserved": False,
                    "facial_features_changed": True,
                    "beautification_detected": True,
                    "source_occlusion_preserved": False,
                    "notes": "wrong",
                },
                "body_framing": {
                    "score": 10,
                    "head_through_calves_visible": False,
                    "natural_head_to_body_ratio": False,
                    "no_vertical_compression": False,
                    "source_pose_and_camera_preserved": False,
                },
                "outfit_fidelity": {
                    "score": 10,
                    "silhouette_and_ease_preserved": False,
                    "source_garment_fit_leaked": True,
                    "matched": [],
                    "missing_or_wrong": [],
                },
                "application_policy": {
                    "shoe_policy_followed": False,
                    "no_body_reframing_for_footwear": False,
                },
                "photorealism": {"score": 10, "artifacts": []},
                "overall_score": 10,
                "pass": False,
                "recommended_retry_changes": [],
            }
            with (
                mock.patch.object(core, "parse_args", return_value=args),
                mock.patch.dict(core.os.environ, {"ARK_API_KEY": "test-key"}),
                mock.patch.object(core, "require_image", side_effect=lambda path, label: path),
                mock.patch.object(core, "image_data_url", return_value="data:image/png;base64,x"),
                mock.patch.object(
                    core,
                    "analyze_inputs",
                    return_value={
                        "source_photo_eligibility": {
                            "eligible": True,
                            "body_coverage": {
                                "neck_and_shoulders": True,
                                "torso": True,
                                "hips": True,
                                "knees": True,
                                "calves": True,
                                "feet": False,
                            },
                        },
                        "outfit_items": [],
                    },
                ),
                mock.patch.object(
                    core,
                    "generate_image",
                    return_value={"data": [{"url": "https://cdn.example.com/x.jpg"}]},
                ),
                mock.patch.object(
                    core,
                    "download_result",
                    side_effect=lambda response, target: target.write_bytes(b"jpg"),
                ),
                mock.patch.object(core, "audit_result", return_value=failing_audit),
            ):
                self.assertEqual(core.main(), 3)

            manifest = (output / "manifest.json").read_text(encoding="utf-8")
            self.assertIn('"hard_pass": false', manifest)
            self.assertIn('"quality_status": "hard_fail"', manifest)

    def test_packager_emits_expected_archive_without_cache_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "skill.zip"
            run = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "scripts" / "package_doubao_skill.py"),
                    "--output",
                    str(output),
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertTrue(output.is_file())
            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertIn("doubao-virtual-try-on/SKILL.md", names)
            self.assertIn("doubao-virtual-try-on/scripts/virtual_try_on.py", names)
            self.assertFalse(any("__pycache__" in name for name in names))
            self.assertFalse(any(name.endswith(".pyc") for name in names))


if __name__ == "__main__":
    unittest.main()
