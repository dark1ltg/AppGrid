#!/bin/bash
# Rootless chroot tests for AppGrid .debs (Ubuntu 24.04 + Debian 12).
set -u
PROJECT=/home/dark1ltg/Projects/AppGrid
DIST="$PROJECT/dist"
LOG="$PROJECT/build/distro-deb-test.log"
: >"$LOG"

log() { printf '%s\n' "$*" | tee -a "$LOG"; }

run_in() {
  local root=$1
  shift
  unshare --user --map-auto --map-root-user --mount --pid --fork -- \
    bash -s -- "$root" "$@" <<'EOS'
set -e
root=$1
shift
mkdir -p "$root/proc" "$root/dev" "$root/sys" "$root/tmp" "$root/run"
mount -t proc proc "$root/proc" 2>/dev/null || true
if ! mount --bind /dev "$root/dev" 2>/dev/null; then
  mount -t tmpfs tmpfs "$root/dev"
  mknod -m 666 "$root/dev/null" c 1 3 || true
  mknod -m 666 "$root/dev/zero" c 1 5 || true
  mknod -m 666 "$root/dev/urandom" c 1 9 || true
fi
if [ -f /etc/resolv.conf ]; then
  cp /etc/resolv.conf "$root/etc/resolv.conf"
fi
echo '#!/bin/sh' >"$root/usr/sbin/policy-rc.d"
echo 'exit 101' >>"$root/usr/sbin/policy-rc.d"
chmod 755 "$root/usr/sbin/policy-rc.d"
export DEBIAN_FRONTEND=noninteractive
export PATH=/usr/sbin:/usr/bin:/sbin:/bin
chroot "$root" "$@"
EOS
}

copy_debs() {
  local root=$1
  mkdir -p "$root/tmp/appgrid-debs"
  cp -f "$DIST/AppGridSetup-1.0.0-amd64.deb" "$DIST/appgrid_1.0.0-1_all.deb" "$root/tmp/appgrid-debs/"
}

section() {
  log ""
  log "======== $* ========"
}

# Returns 0/1; captures output
try() {
  local title=$1
  shift
  log "-- $title"
  local out
  set +e
  out=$("$@" 2>&1)
  local rc=$?
  set -e
  printf '%s\n' "$out" | tee -a "$LOG" | tail -n 40
  log "exit:$rc ($title)"
  return $rc
}

prepare_apt() {
  local root=$1
  run_in "$root" bash -c 'apt-get update -qq && apt-get install -y -qq pkexec >/dev/null'
}

test_fat_after_pyqt() {
  local distro=$1
  local root=$2
  section "$distro: install distro PyQt6, then fat AppGridSetup.deb"
  if [ "$distro" = ubuntu-24.04 ]; then
    try "apt install python3-pyqt6 stack" run_in "$root" bash -c \
      'apt-get install -y python3-pyqt6 python3-pyqt6.qtqml python3-pyqt6.qtquick qml6-module-qtquick qml6-module-qtquick-controls'
  else
    try "apt install python3-pyqt6 stack" run_in "$root" bash -c \
      'apt-get install -y python3-pyqt6 python3-pyqt6.qtqml python3-pyqt6.qtquick qml6-module-qtquick qml6-module-qtquick-controls'
  fi
  try "dpkg -i AppGridSetup (expect no file conflicts)" run_in "$root" bash -c \
    'dpkg -i /tmp/appgrid-debs/AppGridSetup-1.0.0-amd64.deb'
  try "apt-get -f install" run_in "$root" bash -c 'apt-get install -y -f'
  try "dpkg -s appgrid" run_in "$root" dpkg -s appgrid
  try "no Qt libs in /usr/lib from appgrid" run_in "$root" bash -c \
    'dpkg -L appgrid | grep -E "^/usr/lib/.*/libQt" || echo "OK: no /usr/lib Qt from appgrid"'
  try "file overlap vs python3-pyqt6" run_in "$root" bash -c \
    'comm -12 <(dpkg -L appgrid | sort) <(dpkg -L python3-pyqt6 2>/dev/null | sort) | grep -v "^$" | head || echo "OK: no shared files with python3-pyqt6"'
  try "appgrid --help (loads Qt via wrapper)" run_in "$root" bash -c \
    'export QT_QPA_PLATFORM=offscreen; /usr/bin/appgrid --help'
  cat >"$root/tmp/test_opt_pyqt.py" <<'PY'
import os, sys
root = "/opt/appgrid"
lib = root + "/usr/lib/x86_64-linux-gnu"
py = root + "/usr/lib/python3/dist-packages"
os.environ["LD_LIBRARY_PATH"] = lib + (
    (":" + os.environ["LD_LIBRARY_PATH"]) if os.environ.get("LD_LIBRARY_PATH") else ""
)
sys.path.insert(0, py)
print("python", sys.version)
try:
    import PyQt6.QtCore as c
    print("PyQt6.QtCore", c.PYQT_VERSION_STR)
except Exception as e:
    print("IMPORT_FAIL", type(e).__name__, e)
    sys.exit(1)
print("wrapper", os.path.isfile("/usr/bin/appgrid"))
PY
  try "import bundled PyQt6 via LD_LIBRARY_PATH" run_in "$root" python3 /tmp/test_opt_pyqt.py
}

test_thin() {
  local distro=$1
  local root=$2
  section "$distro: remove fat appgrid, apt install thin _all.deb"
  try "remove appgrid" run_in "$root" bash -c 'dpkg --purge appgrid || true'
  try "apt install ./appgrid_1.0.0-1_all.deb" run_in "$root" bash -c \
    'apt-get install -y /tmp/appgrid-debs/appgrid_1.0.0-1_all.deb'
  try "dpkg -s appgrid (thin)" run_in "$root" dpkg -s appgrid
  try "thin appgrid --help" run_in "$root" bash -c \
    'export QT_QPA_PLATFORM=offscreen; /usr/bin/appgrid --help'
}

main() {
  log "AppGrid distro .deb tests $(date -Iseconds)"
  log "Host: $(uname -a)"

  for pair in "ubuntu-24.04:$PROJECT/build/chroots/noble" "debian-12:$PROJECT/build/chroots/bookworm"; do
    distro=${pair%%:*}
    root=${pair#*:}
    section "prepare $distro ($root)"
    copy_debs "$root"
    if ! try "apt-get update + pkexec" prepare_apt "$root"; then
      log "WARN: pkexec install failed on $distro; dpkg may report unmet Depends"
    fi
    test_fat_after_pyqt "$distro" "$root"
    test_thin "$distro" "$root"
  done
  log ""
  log "Log written to $LOG"
}

main
