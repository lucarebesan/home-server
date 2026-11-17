#!/usr/bin/env bash
set -euo pipefail

if [[ ! -t 0 ]]; then
  echo "Serve un terminale interattivo (ssh -t)." >&2
  exit 1
fi

directory="$HOME/.config/mail-svuota"
install -d -m 700 "$directory"
read -r -s -p "Incolla la password per le app Gmail e premi Invio: " password
printf '\n'
password="${password// /}"
if [[ ${#password} -ne 16 ]]; then
  echo "La password per le app deve contenere 16 caratteri (gli spazi sono ignorati)." >&2
  exit 1
fi

umask 077
temporary="$(mktemp "$directory/.app-password.XXXXXX")"
trap 'rm -f "$temporary"' EXIT
printf '%s' "$password" > "$temporary"
unset password
chmod 600 "$temporary"
mv -f "$temporary" "$directory/app-password"
trap - EXIT
echo "Credenziale salvata sul mini PC."
