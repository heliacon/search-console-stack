#!/usr/bin/env bash
#
# Installer for the Search Console Stack on macOS and Linux.
# This script does three tasks:
#   - It makes sure that Python 3.9 or later is on the system.
#   - It makes a local Python environment in the .venv folder.
#   - It installs the Python packages that the pull scripts need.
# You can run this script again. It examines the system first. It changes only
# the items that you agree to change.
#
# How to use this script:
#   ./setup.sh         The script asks before it installs or changes software.
#   ./setup.sh --yes   The script does not ask. It uses yes for each question.
#                      Use this mode for an agent or an unattended run.
#
set -euo pipefail

MINIMUM_PYTHON_MINOR=9                 # the script needs Python 3.9 or later
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$REPO_ROOT/.venv"
REQUIREMENTS="$REPO_ROOT/requirements.txt"

assume_yes=0
for argument in "$@"; do
  case "$argument" in
    -y|--yes) assume_yes=1 ;;
    -h|--help)
      printf 'Usage: ./setup.sh [--yes]\n'
      printf '  --yes, -y   Do not ask. Use yes for each question.\n'
      exit 0 ;;
    *) printf 'Unknown option: %s\n' "$argument" >&2; exit 2 ;;
  esac
done
[ "${SCS_ASSUME_YES:-0}" = "1" ] && assume_yes=1

say()  { printf '\n%s\n' "$*"; }
step() { printf '\n==> %s\n' "$*"; }
warn() { printf 'WARNING: %s\n' "$*" >&2; }
die()  { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# Ask a yes/no question. The function returns success for yes. With --yes, it
# returns yes. With an empty answer, it uses the default that the hint shows
# (Y/n is yes, y/N is no). It reads the terminal even when a shell pipes this
# script in.
confirm() {
  local question="$1" hint="${2:-Y/n}"
  if [ "$assume_yes" = "1" ]; then return 0; fi
  local default_yes=1
  case "$hint" in y/N|Y/N) default_yes=0 ;; esac
  printf '%s [%s] ' "$question" "$hint"
  local reply=""
  { read -r reply </dev/tty; } 2>/dev/null || reply=""
  case "$reply" in
    "")              [ "$default_yes" = "1" ] ;;
    y|Y|yes|YES|Yes) return 0 ;;
    *)               return 1 ;;
  esac
}

detect_platform() {
  case "$(uname -s)" in
    Darwin) echo mac ;;
    Linux)  echo linux ;;
    *) die "This operating system is not supported: $(uname -s). Use setup.ps1 on Windows." ;;
  esac
}

# The function returns success when python3 is on PATH and is new enough.
python_version_ok() {
  command -v python3 >/dev/null 2>&1 || return 1
  python3 - "$MINIMUM_PYTHON_MINOR" <<'PY'
import sys
required_minor = int(sys.argv[1])
sys.exit(0 if sys.version_info[:2] >= (3, required_minor) else 1)
PY
}

# The function prints the first supported Linux package manager on PATH.
linux_package_manager() {
  local candidate
  for candidate in apt-get dnf yum pacman zypper; do
    if command -v "$candidate" >/dev/null 2>&1; then echo "$candidate"; return 0; fi
  done
  return 1
}

install_python_linux() {
  local manager
  manager="$(linux_package_manager)" \
    || die "No supported package manager is on the system (apt, dnf, yum, pacman, zypper). Install Python 3.$MINIMUM_PYTHON_MINOR or later, then run this script again."
  step "Install Python with $manager. The system can ask for your password."
  case "$manager" in
    apt-get) sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip ;;
    dnf)     sudo dnf install -y python3 python3-pip ;;
    yum)     sudo yum install -y python3 python3-pip ;;
    pacman)  sudo pacman -Sy --noconfirm python python-pip ;;
    zypper)  sudo zypper install -y python3 python3-pip ;;
  esac
}

install_python_mac() {
  if command -v brew >/dev/null 2>&1; then
    step "Install Python with Homebrew."
    brew install python
  else
    step "Install the Apple command line tools. The tools give you Python 3."
    xcode-select --install || true
    die "Wait for the command line tools to install. Then run ./setup.sh again. You can also install Homebrew from https://brew.sh and then run this script again."
  fi
}

# Make sure that a correct Python 3 is on the system. Install it or upgrade it
# if you agree.
ensure_python() {
  local platform="$1"
  if python_version_ok; then
    say "Python is on the system: $(python3 --version)."
    if confirm "Install a newer Python?" "y/N"; then
      case "$platform" in
        mac)   command -v brew >/dev/null 2>&1 && brew upgrade python || warn "Homebrew is not on the system. The script does not upgrade Python." ;;
        linux) install_python_linux ;;
      esac
    fi
    return
  fi

  if command -v python3 >/dev/null 2>&1; then
    say "Python is on the system ($(python3 --version)), but it is older than the required 3.$MINIMUM_PYTHON_MINOR."
  else
    say "Python 3 is not on the system."
  fi
  confirm "Install Python 3 now?" "Y/n" || die "You must have Python 3.$MINIMUM_PYTHON_MINOR or later. The script did not change anything."
  case "$platform" in
    mac)   install_python_mac ;;
    linux) install_python_linux ;;
  esac
  python_version_ok || die "Python 3.$MINIMUM_PYTHON_MINOR or later is still not on the system. Install it manually, then run this script again."
}

ensure_virtualenv() {
  if [ -d "$VENV_DIR" ]; then
    say "The Python environment is already at $VENV_DIR."
  else
    step "Make the Python environment at $VENV_DIR."
    python3 -m venv "$VENV_DIR"
  fi
}

install_packages() {
  local pip_exe="$VENV_DIR/bin/pip"
  local python_exe="$VENV_DIR/bin/python"
  step "Upgrade pip in the Python environment."
  "$python_exe" -m pip install --upgrade pip >/dev/null
  # The package google-cloud-bigquery is present when a previous run installed
  # the packages.
  if "$pip_exe" show google-cloud-bigquery >/dev/null 2>&1; then
    if confirm "The Python packages are installed. Install the latest versions?" "y/N"; then
      step "Install the latest versions of the packages."
      "$pip_exe" install --upgrade -r "$REQUIREMENTS"
    else
      say "The script keeps the installed versions."
    fi
  else
    step "Install the Python packages."
    "$pip_exe" install -r "$REQUIREMENTS"
  fi
}

main() {
  local platform
  platform="$(detect_platform)"
  say "Search Console Stack installer ($platform)."
  [ -f "$REQUIREMENTS" ] || die "The file requirements.txt is not next to this script."
  ensure_python "$platform"
  ensure_virtualenv
  install_packages
  cat <<EOF

The installation is complete.

Do these steps:
  1. Put your Google credentials in the GSC-setup folder:
       service_account.json   (service account method), or
       client_secret.json     (OAuth method)
  2. Open the script basic_gsc_pull.py or basic_big_query_pull.py in the
     GSC-setup folder. Set SITE_URL, PROJECT, and the dates at the top.
  3. Run a pull. Then check the result:
       source "$VENV_DIR/bin/activate"
       cd GSC-setup
       python basic_gsc_pull.py      # the Search Console API backfill
       python basic_check.py         # the check of the database
EOF
}

main
