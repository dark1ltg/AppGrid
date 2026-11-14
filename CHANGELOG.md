# Changelog

All notable changes to AppGrid are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project aims to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

Product pitch and install steps live in [README.md](README.md). Packages: [GitHub Release v1.0.0](https://github.com/dark1ltg/AppGrid/releases/tag/v1.0.0).

## [Unreleased]

### Changed

- **Browse by categories** sits under search and opens the category chip strip; the strip no longer auto-scrolls (static / flickable chips only); **Clear filter** is the last chip and resets to All while closing the strip

**Current ship:** `master` tip includes the Categories browse change above. **Deb payloads** on [Release v1.0.0](https://github.com/dark1ltg/AppGrid/releases/tag/v1.0.0) / `dist/` are rebuilt to match (same `1.0.0-1` package version).

## [1.0.0] - 2026-11-11

First public release for Debian-family desktops (Ubuntu 24.04 baseline and close relatives).

### Added

- Screenshot-first software store over **APT** (default) and optional **Flatpak** / Flathub, with search, categories, Installed / Updates, and **Update system**
- One merged card per app when both sources are on — newer build wins; source labels stay out of the normal UI
- Online `.deb` plus offline **AppGridSetup** `.deb` (vendors Qt/PyQt6 under `/opt/appgrid` for Ubuntu 24.04 / Mint 22 amd64)
- PackageKit install path (`pkcon` / `pkgcli`) with a narrow PolicyKit helper fallback
- Detail **facts** strip (version, license, size, website) and live progress percent when backends report it
- Dual-install confirm when installing a newer copy beside an older one; **Update installed** when Install-newer is the primary action

### Fixed

- **Password dialog / auth (Kubuntu and friends):** keep the polkit login session (`setpgrp`, not `setsid`); recover once via the helper on no-dialog / no-agent failures, blank auth-ish exits, and bare “not authorized”; wrong password and dismiss stay single-shot
- **Silent Install:** sticky success/fail footer with a generation token so catalog refresh does not wipe errors; clear copy when nothing installed after a failed install
- **Update system / PackageKit:** do not treat busy/locked or “no packages were found” as success; fail-closed refresh; share exit-5 / noop handling with `pkgcli`; partial Flatpak/APT failure uses a fail sticky
- **Which copy is “newer”:** installed APT version for merge (not the candidate); one-sided timestamps and runtime trains (`YY.02` / `YY.08`) no longer mis-rank CalVer app versions; empty versions never win
- **Updates list / CTAs:** Indexes re-check on Updates with a short cooldown; Flatpak installed-only apps can show updates; Install-newer does not hide Update for an older installed copy
- **Offline installer:** launcher finds vendored PyQt6; `libicu74` bundled for Qt6Core soname match

### Changed

- Prefer PackageKit first for system upgrade / index refresh, with helper only as fallback
- Hide APT vs Flatpak chrome from confirm dialogs and the detail CTA stack (prefs)
- README expanded to a full product description with screenshots, install steps, Release SHA256s, and highlights that match this release

[Unreleased]: https://github.com/dark1ltg/AppGrid/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/dark1ltg/AppGrid/releases/tag/v1.0.0
