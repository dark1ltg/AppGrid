#!/usr/bin/env python3
"""Build an amd64 Ubuntu 24.04 offline .deb that vendors PyQt6/QML/Qt."""
from __future__ import annotations

import gzip
import io
import os
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARCH = "amd64"
SUITE = "noble"
MIRROR = "http://archive.ubuntu.com/ubuntu"
INDEXES = [
    f"{MIRROR}/dists/{SUITE}/main/binary-{ARCH}/Packages.gz",
    f"{MIRROR}/dists/{SUITE}/universe/binary-{ARCH}/Packages.gz",
    f"{MIRROR}/dists/{SUITE}-updates/main/binary-{ARCH}/Packages.gz",
    f"{MIRROR}/dists/{SUITE}-updates/universe/binary-{ARCH}/Packages.gz",
]
SEEDS = [
    "python3-pyqt6",
    "python3-pyqt6.qtqml",
    "python3-pyqt6.qtquick",
    "python3-pyqt6.sip",
    "qml6-module-qtquick",
    "qml6-module-qtquick-controls",
    "qml6-module-qtquick-layouts",
    "qml6-module-qtquick-window",
    "gir1.2-appstream-1.0",
    "libappstream5",
    "libqt6svg6",
    "packagekit",
    "packagekit-tools",
    "libpackagekit-glib2-18",
    "fonts-ubuntu",
    "qt6-wayland",
    "qt6-qpa-plugins",
    "qt6-svg-plugins",
]
# Only walk Depends that are Qt/PyQt/AppStream/PackageKit. Everything else
# (libc, glib, Mesa, systemd, GTK) must already be on Ubuntu 24.04.
BUNDLE_PREFIX = (
    "python3-pyqt6",
    "qml6-module-qt",
    "libqt6",
    "qt6-",
    "gir1.2-appstream",
    "libappstream",
    "packagekit",
    "libpackagekit",
    "fonts-ubuntu",
)
SKIP = {
    "adduser",
    "apt",
    "base-files",
    "base-passwd",
    "bash",
    "bsdutils",
    "ca-certificates",
    "coreutils",
    "dash",
    "debconf",
    "debianutils",
    "diffutils",
    "dpkg",
    "e2fsprogs",
    "findutils",
    "gcc-13-base",
    "gcc-14-base",
    "grep",
    "gzip",
    "hostname",
    "init-system-helpers",
    "libc-bin",
    "libc6",
    "libgcc-s1",
    "libstdc++6",
    "login",
    "lsb-base",
    "mawk",
    "ncurses-base",
    "ncurses-bin",
    "openssl",
    "passwd",
    "perl-base",
    "python3",
    "python3-minimal",
    "python3.12",
    "python3.12-minimal",
    "sed",
    "sensible-utils",
    "sysvinit-utils",
    "tar",
    "tzdata",
    "util-linux",
    "zlib1g",
}
SKIP_PREFIX = ("gcc-", "linux-libc-", "libpython3")

_DEP = re.compile(r"^([a-zA-Z0-9.+-]+)")


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "AppGrid-offline-builder/1.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        return response.read()


def parse_packages(blob: bytes) -> dict[str, dict[str, str]]:
    text = gzip.decompress(blob).decode("utf-8", errors="replace")
    packages: dict[str, dict[str, str]] = {}
    for block in text.split("\n\n"):
        fields: dict[str, str] = {}
        key = ""
        for line in block.splitlines():
            if not line:
                continue
            if line.startswith(" ") and key:
                fields[key] += "\n" + line[1:]
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                fields[key] = value.strip()
        name = fields.get("Package")
        if not name:
            continue
        old = packages.get(name)
        if old is None or _version_newer(fields.get("Version", ""), old.get("Version", "")):
            packages[name] = fields
    return packages


def _version_newer(left: str, right: str) -> bool:
    return left > right


def dep_names(field: str) -> list[str]:
    names: list[str] = []
    for item in (field or "").split(","):
        item = item.strip()
        if not item:
            continue
        first = item.split("|")[0].strip()
        match = _DEP.match(first)
        if match:
            names.append(match.group(1))
    return names


def should_skip(name: str, meta: dict[str, str] | None) -> bool:
    if name in SKIP:
        return True
    if name.startswith(SKIP_PREFIX):
        return True
    if meta and meta.get("Essential", "").lower() == "yes":
        return True
    if meta and meta.get("Priority") == "required":
        return True
    return False


def resolve(index: dict[str, dict[str, str]], provides: dict[str, str]) -> list[str]:
    wanted = list(SEEDS)
    seen: set[str] = set()
    ordered: list[str] = []
    while wanted:
        name = wanted.pop(0)
        if name in seen:
            continue
        seen.add(name)
        meta = index.get(name)
        if meta is None:
            provider = provides.get(name)
            if provider and provider not in seen:
                wanted.append(provider)
            continue
        if should_skip(name, meta):
            continue
        if not name.startswith(BUNDLE_PREFIX) and name not in SEEDS:
            continue
        ordered.append(name)
        for field in ("Depends", "Pre-Depends"):
            for dep in dep_names(meta.get(field, "")):
                if dep not in seen:
                    wanted.append(dep)
    return ordered


def build_provides(index: dict[str, dict[str, str]]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for name, meta in index.items():
        for item in dep_names(meta.get("Provides", "").replace(",", "\n").replace("\n", ",")):
            mapping.setdefault(item, name)
        # Provides uses commas too
        for raw in (meta.get("Provides") or "").split(","):
            raw = raw.strip()
            match = _DEP.match(raw)
            if match:
                mapping.setdefault(match.group(1), name)
    return mapping


def extract_deb(path: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix="deb-"))
    try:
        subprocess.run(["ar", "x", str(path)], cwd=staging, check=True, capture_output=True)
        data = None
        for name in ("data.tar.zst", "data.tar.xz", "data.tar.gz", "data.tar.bz2"):
            candidate = staging / name
            if candidate.is_file():
                data = candidate
                break
        if data is None:
            raise RuntimeError(f"no data.tar in {path.name}")
        if data.name.endswith(".zst"):
            raw = subprocess.check_output(["zstd", "-d", "-c", str(data)])
            tar = tarfile.open(fileobj=io.BytesIO(raw), mode="r:")
        else:
            tar = tarfile.open(str(data))
        with tar:
            try:
                tar.extractall(dest, filter="fully_trusted")
            except TypeError:
                tar.extractall(dest)
    finally:
        shutil.rmtree(staging, ignore_errors=True)


# Shell wrapper so LD_LIBRARY_PATH / PYTHONPATH are set *before* Python starts.
# Setting those in a running Python process does not put vendored PyQt6 on sys.path
# and does not reconfigure the dynamic linker — the BlankOn/clean-host failure mode.
WRAPPER = r"""#!/bin/sh
ROOT=/opt/appgrid
LIB="$ROOT/usr/lib/x86_64-linux-gnu"
PY="$ROOT/usr/lib/python3/dist-packages"
QML="$LIB/qt6/qml"
PLUGINS="$LIB/qt6/plugins"
GI="$LIB/girepository-1.0"
BIN="$ROOT/usr/bin"

export LD_LIBRARY_PATH="$LIB${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
export PYTHONPATH="$PY${PYTHONPATH:+:$PYTHONPATH}"
export QML2_IMPORT_PATH="$QML${QML2_IMPORT_PATH:+:$QML2_IMPORT_PATH}"
export QT_PLUGIN_PATH="$PLUGINS"
export QT_QPA_PLATFORM_PLUGIN_PATH="$PLUGINS/platforms"
if [ -d "$GI" ]; then
  export GI_TYPELIB_PATH="$GI${GI_TYPELIB_PATH:+:$GI_TYPELIB_PATH}"
fi
export PATH="$BIN:${PATH:-/usr/bin}"

exec /usr/bin/python3 -m appgrid "$@"
"""


def overlay_appgrid(dest: Path) -> None:
    pkg = dest / "usr/lib/python3/dist-packages/appgrid"
    pkg.parent.mkdir(parents=True, exist_ok=True)
    if pkg.exists():
        shutil.rmtree(pkg)
    shutil.copytree(
        ROOT / "appgrid",
        pkg,
        ignore=shutil.ignore_patterns("__pycache__", "*.pyc", "*.qmlc"),
    )
    bindir = dest / "usr/bin"
    bindir.mkdir(parents=True, exist_ok=True)
    (bindir / "appgrid").write_text(WRAPPER, encoding="utf-8")
    (bindir / "appgrid-apt-helper").write_text(
        "#!/usr/bin/python3\nfrom appgrid.helpers.apt_helper import main\nraise SystemExit(main())\n",
        encoding="utf-8",
    )
    os.chmod(bindir / "appgrid", 0o755)
    os.chmod(bindir / "appgrid-apt-helper", 0o755)
    apps = dest / "usr/share/applications"
    apps.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "data/appgrid.desktop", apps / "appgrid.desktop")
    metainfo = dest / "usr/share/metainfo"
    metainfo.mkdir(parents=True, exist_ok=True)
    shutil.copy2(
        ROOT / "data/metainfo/org.appgrid.AppGrid.metainfo.xml",
        metainfo / "org.appgrid.AppGrid.metainfo.xml",
    )
    icons = dest / "usr/share/icons/hicolor/scalable/apps"
    icons.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "appgrid/data/appgrid.svg", icons / "appgrid.svg")
    polkit = dest / "usr/share/polkit-1/actions"
    polkit.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "data/polkit/org.appgrid.policy", polkit / "org.appgrid.policy")
    docs = dest / "usr/share/doc/appgrid"
    docs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "debian/copyright", docs / "copyright")
    shutil.copy2(ROOT / "LICENSE", docs / "LICENSE")
    subprocess.run(
        ["gzip", "-9n", "-c", str(ROOT / "debian/changelog")],
        check=True,
        stdout=open(docs / "changelog.Debian.gz", "wb"),
    )


def main() -> int:
    print("Fetching Ubuntu 24.04 package indexes…")
    index: dict[str, dict[str, str]] = {}
    for url in INDEXES:
        print(" ", url)
        parsed = parse_packages(fetch(url))
        for name, meta in parsed.items():
            old = index.get(name)
            if old is None or _version_newer(meta.get("Version", ""), old.get("Version", "")):
                index[name] = meta
    provides = build_provides(index)
    names = resolve(index, provides)
    print(f"Bundling {len(names)} packages")
    cache = ROOT / "build" / "noble-debs"
    cache.mkdir(parents=True, exist_ok=True)
    for name in names:
        meta = index[name]
        filename = meta["Filename"]
        dest = cache / Path(filename).name
        if dest.is_file() and dest.stat().st_size > 0:
            continue
        url = f"{MIRROR}/{filename}"
        print("  get", dest.name)
        dest.write_bytes(fetch(url))

    staging = Path(tempfile.mkdtemp(prefix="appgrid-fat-"))
    data = staging / "data"
    control = staging / "control"
    data.mkdir()
    control.mkdir()
    for name in names:
        meta = index[name]
        deb = cache / Path(meta["Filename"]).name
        print("  unpack", deb.name)
        extract_deb(deb, data / "opt" / "appgrid")
    overlay_appgrid(data)
    shutil.rmtree(data / "opt" / "appgrid" / "DEBIAN", ignore_errors=True)

    size = int(subprocess.check_output(["du", "-sk", str(data)]).split()[0])
    control_text = f"""Package: appgrid
Version: 1.0.0-1
Section: utils
Priority: optional
Architecture: amd64
Maintainer: AppGrid contributors <appgrid@localhost>
Installed-Size: {size}
Homepage: https://github.com/appgrid/appgrid
Depends: python3 (>= 3.10), python3-gi, pkexec
Description: AppGrid software store
 Double-click this file to open App Center, GNOME Software, or GDebi, then
 click Install. Bundles Ubuntu 24.04 PyQt6, QML, and Qt under /opt/appgrid
 so a normal 24.04/Mint 22 desktop can install fully offline. Does not
 replace distro Qt packages. Enable Flatpak later in AppGrid Settings.
"""
    (control / "control").write_text(control_text, encoding="utf-8")
    postinst = control / "postinst"
    postinst.write_text(
        "#!/bin/sh\nset -e\n"
        "if [ \"$1\" = configure ]; then\n"
        "    if [ -x /usr/bin/gtk-update-icon-cache ]; then\n"
        "        gtk-update-icon-cache -f -t /usr/share/icons/hicolor >/dev/null 2>&1 || true\n"
        "    fi\n"
        "    if [ -x /usr/bin/update-desktop-database ]; then\n"
        "        update-desktop-database -q /usr/share/applications >/dev/null 2>&1 || true\n"
        "    fi\n"
        "fi\n",
        encoding="utf-8",
    )
    os.chmod(postinst, 0o755)
    md5 = subprocess.check_output(
        "find usr opt -type f -print0 | sort -z | xargs -0 md5sum",
        cwd=data,
        shell=True,
    )
    (control / "md5sums").write_bytes(md5)

    tar_opts = [
        "tar",
        "--sort=name",
        "--mtime=@1726185720",
        "--owner=0",
        "--group=0",
        "--numeric-owner",
        "-czf",
    ]
    subprocess.run(tar_opts + [str(staging / "data.tar.gz"), "-C", str(data), "."], check=True)
    subprocess.run(tar_opts + [str(staging / "control.tar.gz"), "-C", str(control), "."], check=True)
    (staging / "debian-binary").write_text("2.0\n", encoding="ascii")
    outdir = ROOT / "dist"
    outdir.mkdir(exist_ok=True)
    deb = outdir / "appgrid_1.0.0-1_amd64.deb"
    if deb.exists():
        deb.unlink()
    subprocess.run(
        ["ar", "-qc", str(deb), "debian-binary", "control.tar.gz", "data.tar.gz"],
        cwd=staging,
        check=True,
    )
    shutil.rmtree(staging, ignore_errors=True)
    setup = outdir / "AppGridSetup-1.0.0-amd64.deb"
    shutil.copy2(deb, setup)
    print("Wrote", deb, "size", deb.stat().st_size)
    print("Wrote", setup)
    print("Packages:", ", ".join(names))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
