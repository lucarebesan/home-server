#!/bin/sh
set -eu

test "$(id -un)" = home
test -f "$HOME/mail-svuota/mail_svuota.py"
test -f "$HOME/mail-svuota/rules.json"
test -f "$HOME/mail-svuota/run-dry.sh"

tmp="$(mktemp)"
trap 'rm -f "$tmp"' EXIT
crontab -l > "$tmp" 2>/dev/null || :
if grep -Fq '# MAIL_SVUOTA_DRY' "$tmp"; then
  echo "Timer di simulazione già presente"
  exit 0
fi
printf '%s\n' '*/30 * * * * /bin/sh /home/home/mail-svuota/run-dry.sh # MAIL_SVUOTA_DRY' >> "$tmp"
crontab "$tmp"
echo "Timer di simulazione installato (ogni 30 minuti)"
