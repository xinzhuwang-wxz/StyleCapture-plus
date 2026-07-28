#!/usr/bin/env python3
"""Normalize XcodeGen's nested SystemCapabilities attribute into PBX syntax."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PBXPROJ = ROOT / "apps/ios/StyleCaptureJourney/StyleCaptureJourney.xcodeproj/project.pbxproj"

CAPABILITY_KEY = "com.apple.SignInWithApple"


def normalize_system_capabilities(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    if "SystemCapabilities = {" in text and f"{CAPABILITY_KEY} = {{" in text:
        return

    pattern = re.compile(
        rf'^(?P<indent>\s*)SystemCapabilities = ".*{re.escape(CAPABILITY_KEY)}.*";$',
        re.MULTILINE,
    )
    match = pattern.search(text)
    if match is None:
        raise RuntimeError(
            "XcodeGen output did not contain the expected stringified Sign in with Apple "
            "SystemCapabilities attribute"
        )

    indent = match.group("indent")
    replacement = "\n".join(
        (
            f"{indent}SystemCapabilities = {{",
            f"{indent}\t{CAPABILITY_KEY} = {{",
            f"{indent}\t\tenabled = 1;",
            f"{indent}\t}};",
            f"{indent}}};",
        )
    )
    normalized, replacements = pattern.subn(replacement, text, count=1)
    if replacements != 1:
        raise RuntimeError(f"expected one SystemCapabilities replacement, got {replacements}")
    path.write_text(normalized, encoding="utf-8")


def main() -> int:
    try:
        normalize_system_capabilities(PBXPROJ)
    except (OSError, RuntimeError) as error:
        print(f"failed to normalize iOS SystemCapabilities: {error}", file=sys.stderr)
        return 1
    print("iOS Sign in with Apple SystemCapabilities: normalized")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
