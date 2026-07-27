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
            self.assertIn("1.2.0", version_run.stdout)

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
                "identity_preservation": {"score": 10, "notes": "wrong"},
                "outfit_fidelity": {"score": 10, "matched": [], "missing_or_wrong": []},
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
                    return_value={"generation_prompt": "prompt"},
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
