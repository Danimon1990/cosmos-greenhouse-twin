#!/bin/bash
# Install Docker Engine, then NVIDIA Container Toolkit 1.16.2+ on Ubuntu 24.04.
# CUDA 12.4+ is provided by NVIDIA container images (e.g. nvidia/cuda:12.4.0-base-ubuntu24.04).
# Run: sudo bash scripts/install-docker-nvidia-container.sh

set -e

echo "=== 1. Docker Engine ==="
# Remove old/conflicting Docker packages if present
for pkg in docker.io docker-doc docker-compose podman-docker containerd runc; do
  apt-get remove -y "$pkg" 2>/dev/null || true
done

# Docker official repo
apt-get update
apt-get install -y ca-certificates curl
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "${VERSION_CODENAME:-$UBUNTU_CODENAME}") stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
echo "Docker installed: $(docker --version)"

echo "=== 2. NVIDIA Container Toolkit ==="
# NVIDIA Container Toolkit repo (stable)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
apt-get update
apt-get install -y nvidia-container-toolkit
echo "NVIDIA Container Toolkit installed: $(dpkg -l nvidia-container-toolkit | awk '/^ii/ {print $3}')"

echo "=== 3. Configure Docker to use NVIDIA runtime ==="
nvidia-ctk runtime configure --runtime=docker

echo "=== 4. Restart Docker ==="
systemctl restart docker

echo "=== Done. Verify with: ==="
echo "  docker run --rm --gpus all nvidia/cuda:12.4.0-base-ubuntu24.04 nvidia-smi"
