from __future__ import annotations

import os
import shutil

from appgrid.helpers.apt_helper import is_safe_package_name
from appgrid.services import progress
from appgrid.services.jobs import CancelledError, run_streaming

_CANCEL_TEXT = ("dismissed", "not authorized", "cancelled", "canceled")
# Do not include bare "already" — matches "already locked" / "already running" (#1).
_NOOP_TEXT = (
    "nothing useful",
    "no updates",
    "no packages",
    "already up-to-date",
    "already up to date",
    "already the newest",
)
# Only explicit “no dialog / no session” — not blank output, not wrong password (#2).
_HELPER_FALLBACK_TEXT = (
    "failed to obtain authorization",
    "no session for cookie",
    "no agent is available",
    "authorization requires authentication but no agent",
)
_WRONG_PASSWORD_TEXT = (
    "authentication failed",
    "authentication failure",
    "pam_authenticate",
    "incorrect password",
    "not authenticated",
)
_PK_VERBS = frozenset(
    {
        "install",
        "remove",
        "update",
        "upgrade",
        "refresh",
        "get-details",
        "resolve",
        "search",
        "get-updates",
    }
)


def _check_name(name: str) -> str:
    package = (name or "").strip()
    if not is_safe_package_name(package):
        raise RuntimeError(f"refusing unsafe package name: {package!r}")
    return package


def _looks_cancelled(output: str) -> bool:
    text = output.lower()
    return any(token in text for token in _CANCEL_TEXT)


def _pk_verb_and_packages(argv: list[str]) -> tuple[str, list[str]]:
    """Strip flags from pkcon/pkgcli argv → (verb, packages).

    Skips bare numeric tokens (e.g. --cache-age 0) so they are not mistaken for
    the verb (#5).
    """
    positional = [a for a in argv[1:] if a and not a.startswith("-")]
    if not positional:
        return "", []
    # Prefer a known PackageKit verb if a numeric cache-age slipped through.
    for index, token in enumerate(positional):
        if token in _PK_VERBS or not token.isdigit():
            return token, positional[index + 1 :]
    return positional[0], positional[1:]


def _fail_message(output: str, code: int, fallback: str) -> str:
    text = (output or "").strip()
    if text:
        return text
    return f"{fallback} (exit {code})"


def _looks_wrong_password(output: str) -> bool:
    text = (output or "").lower()
    return any(token in text for token in _WRONG_PASSWORD_TEXT)


def _looks_helper_fallback(output: str) -> bool:
    """True only for explicit no-dialog/session auth failures (#2).

    Blank PackageKit output does **not** open pkexec — that caused a second
    password dialog after odd empty failures.
    """
    text = (output or "").lower()
    if _looks_wrong_password(text):
        return False
    if any(token in text for token in _HELPER_FALLBACK_TEXT):
        return True
    if "no password dialog" in text and any(
        token in text for token in _HELPER_FALLBACK_TEXT
    ):
        return True
    return False


def _auth_fail_message(output: str, code: int) -> str:
    """User-facing text when polkit/PackageKit could not show a password dialog."""
    base = (output or "").strip() or "Failed to obtain authorization"
    return (
        f"{base}. No password dialog appeared. On Kubuntu, confirm "
        "polkit-kde-agent-1 is running, then try Install again."
    )


def _run(argv: list[str], env: dict[str, str] | None = None) -> str:
    code, output = run_streaming(argv, env=env)
    name = os.path.basename(argv[0]) if argv else ""
    if name in {"pkcon", "pkgcli", "pkexec"}:
        if code == 0:
            return output
        if _looks_cancelled(output):
            raise CancelledError("Cancelled — administrator permission was not granted.")
        if _looks_wrong_password(output):
            raise RuntimeError(
                _fail_message(output, code, "Administrator password was not accepted")
            )
        lowered = (output or "").lower()
        # Explicit no-agent text → auth message (helper may recover). Blank → plain fail (#2).
        if any(token in lowered for token in _HELPER_FALLBACK_TEXT):
            raise RuntimeError(_auth_fail_message(output, code))
        if not (output or "").strip():
            raise RuntimeError(_fail_message(output, code, "PackageKit failed"))
        if name == "pkexec":
            raise RuntimeError(_fail_message(output, code, "pkexec failed"))
        verb, packages = _pk_verb_and_packages(argv)
        mutating = verb in {"install", "remove", "update", "upgrade"}
        # pkcon: 5 = nothing useful / cancel on some versions. Never treat that as
        # success for install/remove/update when packages were named (Kubuntu silent fail).
        if name == "pkcon" and code == 5:
            if any(
                token in lowered
                for token in ("not found", "couldn't find", "could not find", "no such package")
            ):
                raise RuntimeError(_fail_message(output, code, "Package not found"))
            # Busy/locked must not look like success (#1).
            if any(
                token in lowered
                for token in ("locked", "already running", "cannot obtain lock", "unable to acquire")
            ):
                raise RuntimeError(_fail_message(output, code, "PackageKit is busy"))
            if mutating and packages:
                raise RuntimeError(
                    _fail_message(output, code, f"PackageKit could not {verb} the package")
                )
            if output and any(token in lowered for token in _NOOP_TEXT):
                return output
            if verb in {"refresh", "update", "upgrade"} and not packages:
                # Exit 5 with no clear noop text on system update/refresh → fail closed (#1).
                if verb in {"update", "upgrade"} and not any(
                    token in lowered for token in _NOOP_TEXT
                ):
                    raise RuntimeError(_fail_message(output, code, "PackageKit failed"))
                return output
            if not packages:
                return output
            raise RuntimeError(_fail_message(output, code, "PackageKit failed"))
        raise RuntimeError(_fail_message(output, code, "PackageKit failed"))
    if code != 0:
        if _looks_cancelled(output):
            raise CancelledError("Cancelled — administrator permission was not granted.")
        if _looks_wrong_password(output):
            raise RuntimeError(
                _fail_message(output, code, "Administrator password was not accepted")
            )
        if _looks_helper_fallback(output):
            raise RuntimeError(_auth_fail_message(output, code))
        raise RuntimeError(_fail_message(output, code, f"command failed: {' '.join(argv)}"))
    return output


def _packagekit_cli() -> tuple[str, str] | None:
    """Return (path, kind): prefer pkgcli (PackageKit 1.4+/Ubuntu 26.04), else pkcon."""
    for kind, candidates in (
        ("pkgcli", ("pkgcli", "/usr/bin/pkgcli")),
        ("pkcon", ("pkcon", "/usr/bin/pkcon")),
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
    # Classic pkcon — use --cache-age=0 so "0" is not a positional verb (#5).
    if verb == "refresh":
        return [path, "--plain", "-y", "refresh"]
    if verb == "update-system":
        return [path, "--plain", "-y", "--cache-age=0", "update"]
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


def _packagekit_then_helper(
    pk_verb: str, helper_action: str, packages: list[str] | None = None
) -> bool:
    """Run PackageKit; on no-dialog auth failure, fall back to helper once.

    Returns True if PackageKit or helper handled the call. False if neither is available.
    """
    packages = packages or []
    if _packagekit_cli():
        try:
            _run_packagekit(pk_verb, packages)
            return True
        except CancelledError:
            raise
        except RuntimeError as exc:
            if _helper() and _looks_helper_fallback(str(exc)):
                progress.report("Asking for administrator permission…")
                _run_helper(helper_action, packages)
                return True
            raise
    if _helper():
        _run_helper(helper_action, packages)
        return True
    return False


def _one_auth_path(pk_verb: str, packages: list[str], helper_action: str, apt_args: list[str]) -> None:
    """Use PackageKit or the helper, never both on success (avoids two password windows).

    Helper fallback only when PackageKit could not show a dialog — not after a
    wrong password, and not on blank/empty PK output (#2).
    """
    if _packagekit_then_helper(pk_verb, helper_action, packages):
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
    if _packagekit_then_helper("refresh", "refresh", []):
        return
    from appgrid.helpers.apt_helper import apt_bin

    if not apt_bin():
        raise RuntimeError("AppGrid cannot refresh the package list")
    _via_apt(["update"])


def refresh_and_upgrade_system() -> None:
    """Refresh indexes, then upgrade packages on this Ubuntu/Debian release only.

    PackageKit first; privileged helper is fallback only (#6), including auth
    no-dialog recovery like per-app install (#3).
    Does not run do-release-upgrade or move 24.04 → 26.04.
    """
    progress.report("Updating installed packages and libraries…")
    if _packagekit_then_helper("update-system", "refresh-upgrade", []):
        return
    from appgrid.helpers.apt_helper import apt_bin, same_release_upgrade_args

    binary = apt_bin()
    if binary:
        _via_apt(["update"])
        _via_apt(same_release_upgrade_args(binary))
        return
    raise RuntimeError("AppGrid cannot update packages: the APT helper or PackageKit is missing")
