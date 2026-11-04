from __future__ import annotations

import os
import signal
import subprocess
import threading

from appgrid.services import progress

_lock = threading.Lock()
_requested = threading.Event()
_procs: list[subprocess.Popen] = []
_mp: list[object] = []


class CancelledError(RuntimeError):
    """User stopped the job, closed the password window, or chose not to continue."""


def reset() -> None:
    _requested.clear()
    with _lock:
        _mp.clear()


def requested() -> bool:
    return _requested.is_set()


def check() -> None:
    if _requested.is_set():
        raise CancelledError("Cancelled.")


def register(proc: subprocess.Popen) -> None:
    with _lock:
        _procs.append(proc)


def unregister(proc: subprocess.Popen) -> None:
    with _lock:
        if proc in _procs:
            _procs.remove(proc)


def register_mp(proc: object) -> None:
    with _lock:
        _mp.append(proc)


def unregister_mp(proc: object) -> None:
    with _lock:
        if proc in _mp:
            _mp.remove(proc)


def kill_proc(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            return
    threading.Thread(target=_reap, args=(proc,), daemon=True).start()


def _reap(proc: subprocess.Popen) -> None:
    try:
        proc.wait(timeout=3)
        return
    except Exception:
        pass
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    try:
        proc.wait(timeout=1)
    except Exception:
        pass


def request() -> None:
    _requested.set()
    with _lock:
        procs = list(_procs)
        extras = list(_mp)
    for proc in procs:
        kill_proc(proc)
    for proc in extras:
        terminate = getattr(proc, "terminate", None)
        if terminate is None:
            continue
        try:
            terminate()
        except Exception:
            pass
        kill = getattr(proc, "kill", None)
        if kill is not None:
            try:
                kill()
            except Exception:
                pass


def _new_process_group() -> None:
    """Put the child in its own process group so Cancel can killpg().

    Do **not** use setsid()/start_new_session: that leaves the logind/polkit
    session, so PackageKit/pkexec fail with “Failed to obtain authorization”
    and never show a password dialog (seen on Kubuntu 26.04).
    """
    os.setpgrp()


def _popen(argv: list[str], env: dict[str, str] | None, *, capture_err: bool) -> subprocess.Popen:
    stderr = subprocess.PIPE if capture_err else subprocess.STDOUT
    return subprocess.Popen(
        argv,
        stdout=subprocess.PIPE,
        stderr=stderr,
        text=True,
        env=env,
        stdin=subprocess.DEVNULL,
        start_new_session=False,
        preexec_fn=_new_process_group,
    )


def run_streaming(argv: list[str], env: dict[str, str] | None = None) -> tuple[int, str]:
    """Run a command, stream stdout to the status bar, and honor Cancel."""
    check()
    proc = _popen(argv, env, capture_err=False)
    register(proc)
    chunks: list[str] = []
    try:
        if proc.stdout is not None:
            for line in proc.stdout:
                check()
                chunks.append(line)
                stripped = line.strip()
                if stripped:
                    progress.report(stripped)
        code = proc.wait()
    except CancelledError:
        kill_proc(proc)
        raise
    finally:
        unregister(proc)
    check()
    return code, "".join(chunks).strip()


def run_capture(argv: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    check()
    proc = _popen(argv, env, capture_err=True)
    register(proc)
    try:
        stdout, stderr = proc.communicate()
    except Exception:
        kill_proc(proc)
        raise
    finally:
        unregister(proc)
    check()
    return subprocess.CompletedProcess(argv, proc.returncode or 0, stdout or "", stderr or "")
