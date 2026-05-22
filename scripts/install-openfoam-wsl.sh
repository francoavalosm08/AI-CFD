#!/usr/bin/env bash
set -euo pipefail

run_root() {
    if [ "$(id -u)" -eq 0 ]; then
        "$@"
    else
        sudo "$@"
    fi
}

echo "[1/8] Checking Ubuntu version..."
. /etc/os-release
if [ "${ID:-}" != "ubuntu" ]; then
    echo "This installer expects Ubuntu in WSL. Found ID=${ID:-unknown}."
    exit 1
fi
if [ "${VERSION_CODENAME:-}" != "jammy" ]; then
    echo "This project currently targets Ubuntu 22.04 jammy for OpenFOAM 10. Found ${VERSION_CODENAME:-unknown}."
    exit 1
fi

echo "[2/8] Updating apt package metadata..."
run_root apt-get update

echo "[3/8] Installing apt repository prerequisites..."
run_root apt-get install -y wget software-properties-common ca-certificates gnupg

echo "[4/8] Enabling Ubuntu universe repository..."
run_root add-apt-repository -y universe

echo "[5/8] Adding OpenFOAM Foundation apt key and repository..."
run_root sh -c "wget -O - https://dl.openfoam.org/gpg.key > /etc/apt/trusted.gpg.d/openfoam.asc"
if ! grep -Rqs "dl.openfoam.org/ubuntu" /etc/apt/sources.list /etc/apt/sources.list.d 2>/dev/null; then
    run_root add-apt-repository -y http://dl.openfoam.org/ubuntu
fi

echo "[6/8] Installing OpenFOAM 10..."
run_root apt-get update
run_root apt-get install -y openfoam10

echo "[7/8] Adding OpenFOAM source line to ~/.bashrc..."
target_user="${TARGET_USER:-${SUDO_USER:-$USER}}"
target_home="$(getent passwd "$target_user" | cut -d: -f6)"
if [ -z "$target_home" ] || [ ! -d "$target_home" ]; then
    echo "Could not resolve home directory for target user '$target_user'."
    exit 1
fi
target_bashrc="$target_home/.bashrc"
if ! grep -qxF "source /opt/openfoam10/etc/bashrc" "$target_bashrc" 2>/dev/null; then
    printf "\nsource /opt/openfoam10/etc/bashrc\n" >> "$target_bashrc"
fi
if [ "$(id -u)" -eq 0 ]; then
    chown "$target_user:$target_user" "$target_bashrc"
fi

echo "[8/8] Verifying OpenFOAM commands..."
set +eu
source /opt/openfoam10/etc/bashrc >/dev/null 2>&1 || true
set -e
command -v gmshToFoam
command -v checkMesh
command -v simpleFoam
command -v foamToVTK
simpleFoam -help >/dev/null

echo "PASS: OpenFOAM 10 installed and sourceable from /opt/openfoam10/etc/bashrc"
