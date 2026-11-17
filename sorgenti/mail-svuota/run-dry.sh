#!/bin/sh
set -eu

secret="$HOME/.config/mail-svuota/app-password"
state="$HOME/.local/share/mail-svuota"
test -s "$secret" || exit 0
umask 077
mkdir -p "$state"
chmod 700 "$state"
exec /usr/bin/flock -n "$state/scan.lock" /usr/bin/python3 +  "$HOME/mail-svuota/mail_svuota.py" >> "$state/cron.log" 2>&1
