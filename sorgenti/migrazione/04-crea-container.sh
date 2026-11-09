#!/usr/bin/env bash
# Crea (o avvia) i container sul mini PC con gli stessi progetti compose dell'HP.
# Da lanciare sul mini PC come utente 'home' (gruppo docker), dopo 03-copia-dati.sh:
#   ssh home@192.168.1.25 'bash -s' < sorgenti/migrazione/04-crea-container.sh            # solo crea, NON avvia
#   ssh home@192.168.1.25 'bash -s -- avvia' < sorgenti/migrazione/04-crea-container.sh   # cutover: avvia
#
# --pull never: usa solo le immagini copiate dall'HP (HA resta 2026.9.3).
# Gli stack Portainer stanno in un volume leggibile solo da root: compose gira in un
# container docker:cli con lo stesso percorso, così le etichette working_dir coincidono
# con quelle dell'HP e Portainer riconosce gli stack.
# Container fermi di proposito sull'HP (grott, matter-hub, adguard, reolink-tv): non creati.
set -euo pipefail

ACTION=(up --no-start --pull never)
[[ "${1:-}" == avvia ]] && ACTION=(up -d --pull never --no-build)

STACKS=/var/lib/docker/volumes/opt_data/_data/compose
portainer_stack() {  # <n> <progetto> <servizi...>
  local n="$1" project="$2"; shift 2
  echo "== stack Portainer $n ($project): $*"
  docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    -v "$STACKS:$STACKS:ro" -w "$STACKS/$n" docker:cli \
    compose -p "$project" "${ACTION[@]}" "$@"
}
local_project() {  # <cartella>
  echo "== $1"
  (cd "$1" && docker compose "${ACTION[@]}")
}

# Ordine: broker MQTT e HA prima dei servizi che li usano.
portainer_stack 2 server mosquitto duckdns letsencrypt nginx
portainer_stack 3 homeassistant homeassistant hass-configurator
portainer_stack 12 anviz-local-api crosschex-webapi
(cd /opt && echo "== opt (portainer)" && docker compose -p opt "${ACTION[@]}")
local_project /home/home/ecm-engine
local_project /home/home/dingtian/dtbridge
local_project /home/home/dingtian/dtdiag

docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'
