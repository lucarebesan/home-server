#!/bin/bash

ACT="${1:-T1}"
PLUGIN="${2:-1999283}"

BASE='http://192.168.1.171'
CMD='{"act":"'"$ACT"'","arg":1}'

LOGIN_URL="${BASE}"'/cgi-bin/userCgi?p=user&u=user&query=[{"act":"getStatus"}]'
DATA_URL_BASE="${BASE}"'/cgi-bin/pluginManager.cgi?query=[{"act":"sendCmd","pluginId":'"$PLUGIN"',"command":'
COOKIE_FILE='/config/tmp/gwc_cookie.txt'
FULL_URL="${DATA_URL_BASE}${CMD}}]"

do_login() {
 LOGIN=$(curl -s -g "$LOGIN_URL" --compressed)
 K=$(echo "$LOGIN" | jq -r ".DATI[0].DATI.k")
 mkdir -p /config/tmp/
 echo "gwc=$K" > "$COOKIE_FILE"
}

fetch_data() {
 COOKIE=$(cat "$COOKIE_FILE")
 curl -s -g -b "$COOKIE" "$FULL_URL"
}

[ ! -f "$COOKIE_FILE" ] && do_login

RESPONSE=$(fetch_data)

ERR=$(echo "$RESPONSE" | jq -r '.ERR // .err // empty')
STRERR=$(echo "$RESPONSE" | jq -r '.STRERR // .strErr // empty')
if [ -z "$RESPONSE" ] || { [ "$ERR" = "1" ] && [ "$STRERR" = "Permission Denied" ]; }; then
 do_login
 RESPONSE=$(fetch_data)
fi

# Gateway irraggiungibile o risposta non numerica: jq non stampa nulla e il
# sensore riceverebbe una stringa vuota, che supera il controllo availability.
VALUE=$(echo "$RESPONSE" | jq -r ".data.commandResult[0].data | tonumber * 10 | round / 10" 2>/dev/null)
if [ -n "$VALUE" ] && [ "$VALUE" != "null" ]; then
 echo "$VALUE"
else
 echo "NILAN_UNAVAILABLE"
fi
