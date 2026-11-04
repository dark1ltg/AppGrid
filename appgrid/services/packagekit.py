from __future__ import annotations

import os
import shutil

from appgrid.helpers.apt_helper import is_safe_package_name
from appgrid.services import progress
from appgrid.services.jobs import CancelledError, run_streaming

_CANCEL_TEXT = ("dismissed", "not authorized", "cancelled", "canceled")
_NOOP_TEXT = ("nothing useful", "no updates", "already", "no packages")


def _check_name(name: str) -> str:
    package = (name or "").strip()
    if not is_safe_package_name(package):
        raise RuntimeError(f"refusing unsafe package name: {package!r}")
    return package


def _looks_cancelled(output: str) -> bool:
    text = output.lower()
    return any(token in text for token in _CANCEL_TEXT)


def _run(argv: list[str], env: dict[str, str] | None = None) -> str:
    code, output = run_streaming(argv, env=env)
    name = os.path.basename(argv[0]) if argv else ""
    if name in {"pkcon", "pkgcli"}:
        if code == 0:
            return output
        # pkcon: 5 = nothing useful / cancel on some versions.
        if name == "pkcon" and code == 5:
            if _looks_cancelled(output):
                raise CancelledError("Cancelled.")
            lowered = output.lower()
            if any(
                token in lowered
                for token in ("not found", "couldn't find", "could not find", "no such package")
            ):
                raise RuntimeError(output or "Package not found")
            if output and any(token in lowered for token in _NOOP_TEXT):
                return output
            if argv and argv[-1] in {"refresh", "update"}:
                return output
            # pkcon --plain -y <verb>  (no extra packages)
            if len(argv) <= 4:
                return output
            raise RuntimeError(output or "PackageKit failed")
        if _looks_cancelled(output):
            raise CancelledError("Cancelled.")
        raise RuntimeError(output or "PackageKit failed")
    if code != 0:
        if _looks_cancelled(output):
            raise CancelledError("Cancelled.")
        raise RuntimeError(output or f"command failed: {' '.join(argv)}")
    return output


def _packagekit_cli() -> tuple[str, str] | None:
    """Return (path, kind) for PackageKit CLI: pkcon (older) or pkgcli (1.4+/Sid)."""
    for kind, candidates in (
        ("pkcon", ("pkcon", "/usr/bin/pkcon")),
        ("pkgcli", ("pkgcli", "/usr/bin/pkgcli")),
    ):
        for candidate in candidates:
            if candidate.startswith("/"):
                path = candidate if os.path.isfile(candidate) and os.access(candidate, os.X_OK) else None
            else:
                path = shutil.which(candidate)
            if path:
                return path, kind
    return None


def _pkcon() -> str | None:
    """Back-compat: path to any PackageKit CLI, or None."""
    found = _packagekit_cli()
    return found[0] if found else None


def _helper() -> str | None:
    """Only the PolicyKit-annotated helper path (see data/polkit/org.appgrid.policy)."""
    candidate = "/usr/bin/appgrid-apt-helper"
    if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
        return candidate
    return None


def _pkexec() -> str | None:
    path = shutil.which("pkexec")
    if path:
        return path
    candidate = "/usr/bin/pkexec"
    return candidate if os.path.isfile(candidate) else None


def _apt_env() -> dict[str, str]:
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    env["APT_LISTCHANGES_FRONTEND"] = "none"
    env["NEEDRESTART_MODE"] = "l"
    return env


def _pk_argv(verb: str, packages: list[str] | None = None) -> list[str]:
    """Build pkcon or pkgcli argv for a PackageKit action."""
    found = _packagekit_cli()
    if not found:
        raise RuntimeError("PackageKit (pkcon/pkgcli) is missing")
    path, kind = found
    packages = packages or []
    if kind == "pkgcli":
        # PackageKit 1.4+ dropped pkcon; pkgcli uses --yes (not -y / --plain).
        if verb == "refresh":
            return [path, "refresh"]
        if verb == "update-system":
            return [path, "--yes", "update"]
        return [path, "--yes", verb, *packages]
    # Classic pkcon
    if verb == "refresh":
        return [path, "--plain", "-y", "refresh"]
    if verb == "update-system":
        return [path, "--plain", "-y", "--cache-age", "0", "update"]
    return [path, "--plain", "-y", verb, *packages]


def _run_packagekit(verb: str, packages: list[str] | None = None) -> None:
    _run(_pk_argv(verb, packages))


def _run_helper(action: str, packages: list[str]) -> None:
    helper = _helper()
    if not helper:
        raise RuntimeError("appgrid-apt-helper is missing")
    if os.geteuid() == 0:
        _run([helper, action, *packages], env=_apt_env())
        return
    pkexec = _pkexec()
    if not pkexec:
        raise RuntimeError("pkexec is missing")
    _run([pkexec, helper, action, *packages])


def _via_apt(args: list[str]) -> None:
    from appgrid.helpers.apt_helper import apt_bin

    binary = apt_bin()
    if not binary:
        raise RuntimeError("AppGrid cannot install software: PackageKit (pkcon/pkgcli) or APT is missing")
    if os.geteuid() == 0:
        _run([binary, *args], env=_apt_env())
        return
    raise RuntimeError(
        "AppGrid cannot ask for administrator permission. "
        "Install the AppGrid package so appgrid-apt-helper is in /usr/bin, "
        "or install PackageKit (pkcon/pkgcli)."
    )


def _one_auth_path(pk_verb: str, packages: list[str], helper_action: str, apt_args: list[str]) -> None:
    """Use PackageKit or the helper, never both (avoids two password windows)."""
    if _packagekit_cli():
        _run_packagekit(pk_verb, packages)
        return
    if _helper():
        _run_helper(helper_action, packages)
        return
    _via_apt(apt_args)


def install_packages(names: list[str]) -> None:
    packages = [_check_name(name) for name in names]
    progress.report(f"Installing {', '.join(packages)}…")
    _one_auth_path("install", packages, "install", ["install", "-y", *packages])


def remove_packages(names: list[str]) -> None:
    packages = [_check_name(name) for name in names]
    progress.report(f"Removing {', '.join(packages)}…")
    _one_auth_path("remove", packages, "remove", ["remove", "-y", *packages])


def upgrade_packages(names: list[str]) -> None:
    packages = [_check_name(name) for name in names]
    progress.report(f"Updating {', '.join(packages)}…")
    _one_auth_path(
        "update",
        packages,
        "upgrade",
        ["install", "--only-upgrade", "-y", *packages],
    )


def refresh_package_indexes() -> None:
    """Download the latest package lists. May ask for the administrator password."""
    progress.report("Checking for updates…")
    if _packagekit_cli():
        _run_packagekit("refresh")
        return
    if _helper():
        _run_helper("refresh", [])
        return
    from appgrid.helpers.apt_helper import apt_bin

    if not apt_bin():
        raise RuntimeError("AppGrid cannot refresh the package list")
    _via_apt(["update"])


def refresh_and_upgrade_system() -> None:
    """Refresh indexes, then upgrade packages on this Ubuntu/Debian release only.

    PackageKit first; privileged helper is fallback only (#6).
    Does not run do-release-upgrade or move 24.04 → 26.04.
    """
    progress.report("Updating installed packages and libraries…")
    if _packagekit_cli():
        _run_packagekit("update-system")
        return
    if _helper():
        _run_helper("refresh-upgrade", [])
        return
    from appgrid.helpers.apt_helper import apt_bin, same_release_upgrade_args

    binary = apt_bin()
    if binary:
        _via_apt(["update"])
        _via_apt(same_release_upgrade_args(binary))
        return
    raise RuntimeError("AppGrid cannot update packages: the APT helper or PackageKit is missing")
