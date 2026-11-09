#!/usr/bin/env bash
# Setup base del mini PC (nuovo home server). Da eseguire una volta con sudo:
#   ssh -t minipc@192.168.1.25 'sudo bash ~/01-setup-minipc.sh'
# Idempotente: si può rilanciare.
set -euo pipefail

USER_NAME="${SUDO_USER:-minipc}"

echo "== Fuso orario (come l'HP: HA monta /etc/localtime)"
timedatectl set-timezone Europe/Rome

echo "== Repository Docker ufficiale (stesso pacchetto dell'HP: docker-ce)"
apt-get update
apt-get install -y ca-certificates curl rsync bluez
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
chmod a+r /etc/apt/keyrings/docker.asc
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

echo "== Servizi"
usermod -aG docker "$USER_NAME"
systemctl enable --now docker
systemctl enable --now bluetooth

echo "== Rete: ethernet preferita (metrica 100), WiFi fallback (metrica 600)"
# Il file WiFi dell'installer (00-installer-config.yaml) non viene toccato.
cat > /etc/netplan/60-ethernet.yaml <<'EOF'
network:
  version: 2
  ethernets:
    enp2s0:
      dhcp4: true
      optional: true
      dhcp4-overrides:
        route-metric: 100
EOF
chmod 600 /etc/netplan/60-ethernet.yaml
netplan generate
netplan apply

echo "== Verifica"
timedatectl | grep -E "zone"
docker --version
docker compose version
systemctl is-active docker bluetooth
ip -br a
echo "OK: esci e rientra in SSH perché il gruppo docker sia attivo."
