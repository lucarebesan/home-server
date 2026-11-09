#!/usr/bin/env bash
# Crea l'utente operativo 'home' sul mini PC, come sull'HP: percorsi /home/home,
# gruppo docker, stesse chiavi SSH di 'minipc'. Nessuna password (solo chiave),
# quindi niente sudo: l'amministrazione resta all'utente 'minipc'.
#   ssh -t minipc@192.168.1.25 'sudo bash ~/02-utente-home.sh'
# Idempotente.
set -euo pipefail

if ! getent passwd home >/dev/null; then
  useradd -m -s /bin/bash home
fi
usermod -aG docker,adm home

install -d -m 700 -o home -g home /home/home/.ssh
install -m 600 -o home -g home /home/minipc/.ssh/authorized_keys /home/home/.ssh/authorized_keys

id home
wc -l /home/home/.ssh/authorized_keys
echo "OK"
