# AppGrid

A lightweight Qt 6 software store built around one job: **find → decide → install**. Browse desktop apps as a screenshot grid, pick one, and install it from the sources you already use.

![AppGrid screenshot grid](docs/ui-grid.png)

![App detail page](docs/ui-detail.png)

## Why it exists

- Full desktop stores (GNOME Software, Discover, Ubuntu App Center) are heavy, slow to scan, or snap-first.
- Power-user tools (`apt`, Synaptic, Flathub browsers) are fast but not visual — hard to *see* an app before you install it.
- AppGrid sits in between: a **fast visual grid** over APT (and optional Flatpak), without trying to be a full DE software center.

This is a new take on the old App Grid idea (screenshot tiles from your existing sources). It is not a clone of the old Launchpad PPA project.

## Who it’s for

- People on **Ubuntu 24.04 LTS**, **Debian 12**, and relatives (**Linux Mint 22**, elementary OS 8, Pop!_OS 24.04, Zorin when 24.04-based, and similar)
- Users who want **native `.deb` / APT first**, with Flatpak available only if they turn it on
- Anyone who prefers browsing apps by screenshot instead of package names

**Not for:** Arch, CachyOS, Fedora, or other non-Debian-family distros.

## Highlights

- Screenshot-first grid with star ratings (ODRS when available)
- Search, categories, and Installed / Updates filters
- Install, remove, per-app update, and **Update all**
- APT via PackageKit (normal admin password prompt); Flatpak from Flathub when enabled
- **One card per app** when Flatpak is on — newer source wins; source labels stay out of the UI
- Small online `.deb`, plus an offline Setup `.deb` that vendors Qt for double-click install on 24.04 / Mint 22 amd64

## Install the .deb

**Offline installer (Ubuntu 24.04 / Mint 22 amd64):** `dist/AppGridSetup-1.0.0-amd64.deb` (same bits as `appgrid_1.0.0-1_amd64.deb`). Qt/PyQt6 live under `/opt/appgrid`, so they do **not** clash with apt’s Qt. Needs a normal desktop (Python 3, Mesa/OpenGL, GLib). Not for ARM.

Double-click the file in Files. App Center, GNOME Software, Discover, or GDebi should open with an **Install** button, then the usual administrator password prompt. That package does not pull Flatpak or extra Qt from the network.

If double-click says there is no app for Debian packages, right-click → **Open With** → App Center / Software Install / GDebi. Ubuntu 24.04 App Center needs a current `snap-store` (`snap refresh`) for local `.deb` files.

```bash
sudo dpkg -i ./dist/AppGridSetup-1.0.0-amd64.deb
```

**Online (any 24.04-family arch):** small package; apt fetches PyQt6/PySide6.

```bash
sudo apt install ./dist/appgrid_1.0.0-1_all.deb
```

## Run

```bash
python3 -m appgrid
```

Filler catalog (useful off Ubuntu, or for screenshots):

```bash
python3 -m appgrid --demo
```

Screenshot:

```bash
python3 -m appgrid --screenshot docs/ui-grid.png
```

## Ubuntu 24.04 dependencies

24.04 is the baseline. It ships **PyQt6**, not PySide6. Do not `pip install PySide6` (that wheel is the entire Qt SDK) and do not add KDE Neon for bindings.

```bash
sudo apt install python3-pyqt6 python3-pyqt6.qtqml python3-pyqt6.qtquick \
  qml6-module-qtquick qml6-module-qtquick-controls qml6-module-qtquick-layouts \
  qml6-module-qtquick-window \
  python3-gi gir1.2-appstream-1.0 libqt6svg6 \
  packagekit packagekit-tools pkexec
```

On 24.10+ / Debian 13+, the `.deb` prefers split `python3-pyside6.qt*` instead. AppGrid tries PySide6 first at runtime, then PyQt6.

Optional: `flatpak` (Settings → Enable Flatpak). The `.deb` only Recommends it so OSTree/portals are not forced.

## Architecture

| Plugin | Catalog | Install / remove / update |
| --- | --- | --- |
| `apt` | AppStream package bundles + python-apt / dpkg | PackageKit (`pkcon`), then `appgrid-apt-helper` via PolicyKit |
| `flatpak` | AppStream Flatpak bundles + libflatpak | `flatpak install/uninstall/update` from **Flathub** (`flathub` remote; added if missing) |

On Ubuntu/Debian-family systems the app list loads in the background so the window stays responsive. Flatpak apps are tracked in both the user and system installs. Other distributions are rejected with an on-screen message.

## License

BSD-2-Clause. See `LICENSE`.
