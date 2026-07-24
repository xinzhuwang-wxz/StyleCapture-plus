from __future__ import annotations

import argparse
import asyncio
from collections.abc import Sequence

from stylecapture_backend.platform.config import BackendSettings
from stylecapture_backend.platform.database import run_migrations


def main(argv: Sequence[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="stylecapture-manage")
    parser.add_argument("command", choices=("migrate",))
    arguments = parser.parse_args(argv)
    settings = BackendSettings()  # type: ignore[call-arg]

    if arguments.command == "migrate":
        asyncio.run(run_migrations(settings.database_url.get_secret_value()))


if __name__ == "__main__":
    main()
