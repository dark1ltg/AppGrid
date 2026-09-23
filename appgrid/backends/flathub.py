from __future__ import annotations

import shutil
import time
from pathlib import Path

from appgrid.services.jobs import CancelledError, run_capture

FLATHUB_REMOTE = "flathub"
FLATHUB_REPO = "https://dl.flathub.org/repo/flathub.flatpakrepo"
_DISPLAY_ALIASES = {"", "flathub", "flatpak", "flathub.org", "flathub remote"}
_SCOPES = ("user", "system")
_appstream_fetched = False
_APPSTREAM_TTL = 12 * 60 * 60
_APPSTREAM_STAMP = Path.home() / ".cache" / "appgrid" / "flatpak-appstream.stamp"


def list_remote_names(scope: str | None = None) -> list[str]:
    names: list[str] = []
    scopes = (scope,) if scope in _SCOPES else _SCOPES
    binary = shutil.which("flatpak")
    if not binary:
        return []
    for item in scopes:
        result = run_capture(
            [binary, "remotes", f"--{item}", "--columns=name"],
        )
        for line in result.stdout.splitlines():
            name = line.strip()
            if name and name != "Name" and name not in names:
                names.append(name)
    return names


def _lookup(names: list[str], wanted: str) -> str | None:
    mapping = {name.lower(): name for name in names}
    return mapping.get(wanted.lower())


def scope_has_remote(scope: str, remote: str) -> bool:
    return _lookup(list_remote_names(scope), remote) is not None


def _add_user_flathub() -> None:
    binary = shutil.which("flatpak")
    if not binary:
        return
    run_capture(
        [binary, "remote-add", "--user", "--if-not-exists", FLATHUB_REMOTE, FLATHUB_REPO],
    )


def ensure_flathub_remote() -> str:
    """Return the Flathub remote name, adding a per-user remote if needed.

    Never tries a system-wide remote-add (that needs administrator permission and
    often fails with no visible error).
    """
    for scope in _SCOPES:
        found = _lookup(list_remote_names(scope), FLATHUB_REMOTE)
        if found:
            return found
    _add_user_flathub()
    found = _lookup(list_remote_names("user"), FLATHUB_REMOTE)
    return found or FLATHUB_REMOTE


def refresh_appstream(force: bool = False) -> None:
    """Download Flathub's app list. Skipped if it was refreshed within 12 hours."""
    global _appstream_fetched
    if not force and _appstream_fetched:
        return
    if not force and _APPSTREAM_STAMP.is_file():
        age = time.time() - _APPSTREAM_STAMP.stat().st_mtime
        if age < _APPSTREAM_TTL:
            _appstream_fetched = True
            return
    binary = shutil.which("flatpak")
    if not binary:
        return
    from appgrid.services import progress

    progress.report("Updating the Flatpak app list…")
    commands = (
        [binary, "update", "--appstream", "--user"],
        [binary, "update", "--appstream"],
    )
    for argv in commands:
        try:
            result = run_capture(argv)
        except CancelledError:
            raise
        except Exception:
            continue
        if result.returncode == 0:
            _appstream_fetched = True
            try:
                _APPSTREAM_STAMP.parent.mkdir(parents=True, exist_ok=True)
                _APPSTREAM_STAMP.touch()
            except Exception:
                pass
            return


def install_remote_and_scope(origin: str | None) -> tuple[str, str]:
    """Pick a remote that exists, preferring the user install over system.

    Adds Flathub for this user if neither scope has a usable remote.
    """
    wanted = (origin or "").strip()
    if wanted.lower() in _DISPLAY_ALIASES:
        wanted = FLATHUB_REMOTE
    for scope in _SCOPES:
        found = _lookup(list_remote_names(scope), wanted)
        if found:
            return found, f"--{scope}"
    if wanted.lower() != FLATHUB_REMOTE:
        for scope in _SCOPES:
            found = _lookup(list_remote_names(scope), FLATHUB_REMOTE)
            if found:
                return found, f"--{scope}"
    _add_user_flathub()
    found = _lookup(list_remote_names("user"), FLATHUB_REMOTE)
    if found:
        return found, "--user"
    raise RuntimeError(
        "Could not add the Flathub remote for your user. "
        "Open a terminal and run: flatpak remote-add --user --if-not-exists "
        f"{FLATHUB_REMOTE} {FLATHUB_REPO}"
    )


def display_origin(origin: str | None) -> str:
    if (origin or "").strip().lower() in _DISPLAY_ALIASES:
        return "Flathub"
    return (origin or "").strip() or "Flathub"


def remote_for_origin(origin: str | None) -> str:
    """Resolve an AppStream origin to a flatpak remote, defaulting to Flathub."""
    try:
        remote, _scope = install_remote_and_scope(origin)
        return remote
    except RuntimeError:
        return FLATHUB_REMOTE
