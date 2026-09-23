from __future__ import annotations

import os
import re
import shutil
import subprocess

_SAFE = re.compile(r"^[A-Za-z0-9.+:~_-]+$")


def run_privileged(argv: list[str]) -> None:
    """Run a package-manager command, using pkexec when not root."""
    if not argv:
        raise RuntimeError("empty command")
    for part in argv[1:]:
        if part.startswith("-"):
            continue
        if not _SAFE.match(part):
            raise RuntimeError(f"refusing unsafe argument: {part!r}")
    if os.geteuid() == 0:
        subprocess.run(argv, check=True)
        return
    pkexec = shutil.which("pkexec")
    if not pkexec:
        raise RuntimeError("pkexec is required to install or remove packages")
    subprocess.run([pkexec, *argv], check=True)
