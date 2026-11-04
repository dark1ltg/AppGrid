from __future__ import annotations

import os
import re
import signal
import subprocess
import sys

# Package-name allowlist shared with PolicyKit helper callers (#6).
# Refuse shell metacharacters, paths, and anything outside Debian package syntax.
_SAFE = re.compile(r"^[A-Za-z0-9.+:~_-]+$")
_ACTIONS = {"install", "remove", "upgrade", "refresh", "refresh-upgrade"}
_apt_proc: subprocess.Popen | None = None


def apt_bin() -> str | None:
    for candidate in ("/usr/bin/apt-get", "/usr/bin/apt"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def same_release_upgrade_args(binary: str) -> list[str]:
    """Upgrade packages on the current Ubuntu/Debian release.

    Never a 24.04→26.04 style release upgrade (that is do-release-upgrade).
    apt-get upgrade --with-new-pkgs updates apps and libraries and may install
    new dependency packages, but it will not remove packages or change the OS version.
    """
    if binary.endswith("apt-get"):
        return ["upgrade", "-y", "--with-new-pkgs"]
    return ["upgrade", "-y"]


def is_safe_package_name(name: str) -> bool:
    """True when *name* matches the helper/PolicyKit package-name allowlist."""
    return bool(name) and bool(_SAFE.match(name))


def check_packages(names: list[str]) -> None:
    """Refuse any package name outside the allowlist (raises SystemExit)."""
    for name in names:
        if not is_safe_package_name(name):
            raise SystemExit(f"refusing unsafe package name: {name!r}")


def _check_packages(names: list[str]) -> None:
    check_packages(names)


def _stop_apt(_signum=None, _frame=None) -> None:
    proc = _apt_proc
    if proc is not None and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=3)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass
    raise SystemExit(1)


def run_apt(args: list[str]) -> None:
    global _apt_proc
    binary = apt_bin()
    if not binary:
        raise SystemExit("apt is not available")
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    env["APT_LISTCHANGES_FRONTEND"] = "none"
    env["NEEDRESTART_MODE"] = "l"
    # Same session as this helper so Cancel → SIGTERM to pkexec also stops apt.
    _apt_proc = subprocess.Popen([binary, *args], env=env, start_new_session=False)
    try:
        code = _apt_proc.wait()
    finally:
        _apt_proc = None
    if code != 0:
        raise subprocess.CalledProcessError(code, [binary, *args])


def dispatch(action: str, packages: list[str]) -> None:
    if action not in _ACTIONS:
        raise SystemExit(f"unknown action: {action}")
    _check_packages(packages)
    if os.geteuid() != 0:
        raise SystemExit("this helper must run as root (via pkexec)")
    signal.signal(signal.SIGTERM, _stop_apt)
    signal.signal(signal.SIGINT, _stop_apt)
    if action == "install":
        if not packages:
            raise SystemExit("install needs a package name")
        run_apt(["install", "-y", *packages])
    elif action == "remove":
        if not packages:
            raise SystemExit("remove needs a package name")
        run_apt(["remove", "-y", *packages])
    elif action == "upgrade":
        if not packages:
            raise SystemExit("upgrade needs a package name")
        run_apt(["install", "-y", "--only-upgrade", *packages])
    elif action == "refresh":
        run_apt(["update"])
    elif action == "refresh-upgrade":
        run_apt(["update"])
        binary = apt_bin() or ""
        run_apt(same_release_upgrade_args(binary))


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(
            "usage: appgrid-apt-helper install|remove|upgrade|refresh|refresh-upgrade [packages...]",
            file=sys.stderr,
        )
        return 2
    try:
        dispatch(args[0], args[1:])
    except subprocess.CalledProcessError as exc:
        return exc.returncode or 1
    except SystemExit as exc:
        if isinstance(exc.code, str):
            print(exc.code, file=sys.stderr)
            return 1
        return int(exc.code or 0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
