#!/usr/bin/env bash
# Run on the future Ubuntu server, not your development computer.
set -euo pipefail
if [[ $EUID -ne 0 ]]; then
    echo 'Run with sudo bash deploy/install-docker-ubuntu.sh' >&2
    exit 1
fi
source /etc/os-release
if [[ "$ID" != ubuntu ]]; then
    echo 'This installer supports Ubuntu only.' >&2
    exit 1
fi
if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
    echo 'Docker and Compose are already installed.'
    exit 0
fi
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: ${UBUNTU_CODENAME:-$VERSION_CODENAME}
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
systemctl enable --now docker
docker version
docker compose version
