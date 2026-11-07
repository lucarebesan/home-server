#!/bin/bash

ACT_ID="$1"
PLUGIN="$2"
VALUE="$3"
SCALE="${4:-1}"

BASE="http://192.168.1.171"
USR="user"
PSW="user"

COOKIE_FILE="/config/tmp/gwc_cookie.txt"

# Controllo parametri
if [ -z "$ACT_ID" ] || [ -z "$PLUGIN" ] || [ -z "$VALUE" ]; then
  echo "Uso: nilan_write.sh IdXX pluginId valore [scala]"
  echo "Esempio diretto: nilan_write.sh Id12 1999494 1 1"
  echo "Esempio x10:     nilan_write.sh Id15 1999494 20.5 10"
  exit 1
fi

# Converte il valore se serve scala x10
# Esempio: 20.5 con scala 10 diventa 205
SEND_VALUE=$(awk "BEGIN { printf \"%g\", $VALUE * $SCALE }")

ACT="W${ACT_ID}"

LOGIN_URL="${BASE}/cgi-bin/userCgi?u=${USR}&p=${PSW}&query=[{\"act\":\"getStatus\"}]"
DATA_URL="${BASE}/cgi-bin/pluginManager.cgi?query=[{\"act\":\"sendCmd\",\"pluginId\":${PLUGIN},\"command\":{\"act\":\"${ACT}\",\"arg\":${SEND_VALUE}}}]"

do_login() {
  LOGIN=$(curl -s -g "$LOGIN_URL" --compressed)
  echo "$LOGIN" | grep -ioP 'n[0-9a-zA-Z_=;.,:-]+' > "$COOKIE_FILE"
}

send_data() {
  COOKIE=$(cat "$COOKIE_FILE" 2>/dev/null)
  curl -s -g -b "$COOKIE" "$DATA_URL" --compressed
}

# Login se non esiste cookie
if [ ! -f "$COOKIE_FILE" ]; then
  do_login
fi

RESPONSE=$(send_data)

ERR=$(echo "$RESPONSE" | jq -r '.ERR // empty' 2>/dev/null)
STRERR=$(echo "$RESPONSE" | jq -r '.STRERR // empty' 2>/dev/null)

# Se cookie scaduto, rifai login e riprova
if [ "$ERR" = "-1" ] || [ "$STRERR" = "-1" ] || echo "$STRERR" | grep -qi "Permission Denied"; then
  do_login
  RESPONSE=$(send_data)
fi

echo "$RESPONSE"