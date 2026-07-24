import subprocess
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[4]
CHECKER = REPOSITORY_ROOT / "scripts" / "check_boundaries.py"


def run_checker(target: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CHECKER), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )


def test_domain_rejects_framework_and_provider_imports(tmp_path: Path) -> None:
    domain_file = tmp_path / "features" / "capture" / "domain.py"
    domain_file.parent.mkdir(parents=True)
    domain_file.write_text("from fastapi import FastAPI\n", encoding="utf-8")

    result = run_checker(tmp_path)

    assert result.returncode == 1
    assert "features/capture/domain.py imports forbidden module fastapi" in result.stdout


def test_current_backend_respects_architecture_boundaries() -> None:
    result = run_checker(REPOSITORY_ROOT / "services" / "backend" / "src")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "architecture boundaries: ok" in result.stdout
