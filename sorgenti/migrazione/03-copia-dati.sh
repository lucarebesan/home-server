#!/usr/bin/env bash
# Copia i dati dell'home server dall'HP al mini PC.
#
# Consigliato: eseguito SULL'HP, dati diretti HP -> mini PC (~39 MB/s misurati,
# contro ~3 MB/s passando dal Mac in WiFi). Usa la chiave temporanea
# ~/.ssh/id_migrazione dell'HP, autorizzata su home@minipc. Dal Mac:
#   scp sorgenti/migrazione/03-copia-dati.sh home@192.168.1.100:~/
#   ssh home@192.168.1.100 'NEW=home@192.168.1.76 bash ~/03-copia-dati.sh prova  </dev/null'
#   ssh home@192.168.1.100 'NEW=home@192.168.1.76 bash ~/03-copia-dati.sh finale </dev/null'
# (non usare 'bash -s < file': le ssh interne consumerebbero lo script dallo stdin)
# In alternativa, eseguito sul Mac (lento): bash sorgenti/migrazione/03-copia-dati.sh prova|finale
#
# prova  = a caldo, HP acceso (DB non consistenti: serve solo a provare);
# finale = con i container dell'HP fermi (lo script lo verifica).
#
# Niente sudo: 'home' è nel gruppo docker su entrambe le macchine, i file root
# si leggono/scrivono tramite un container alpine.
# Ogni cartella viene SPECCHIATA (svuotata e ricopiata): file residui di una copia
# precedente (es. -wal di SQLite) non devono sopravvivere.
set -euo pipefail

MODE="${1:-}"
[[ "$MODE" == prova || "$MODE" == finale ]] || { echo "uso: $0 prova|finale" >&2; exit 2; }

HP="${HP:-home@192.168.1.100}"
NEW="${NEW:-home@192.168.1.76}"   # IP ethernet del mini PC prima del cutover
SSH_OPTS=(-o BatchMode=yes -o ConnectTimeout=10)

if [[ "$(hostname)" == hp-homeassistant ]]; then
  hp() { bash -c "$*"; }
  SSH_OPTS+=(-i "$HOME/.ssh/id_migrazione")
else
  hp() { ssh "${SSH_OPTS[@]}" "$HP" "$@"; }
fi
new() { ssh "${SSH_OPTS[@]}" "$NEW" "$@"; }

# I container da cui dipendono i dati devono essere fermi nella copia finale.
SERVIZI="homeassistant mosquitto nginx letsencrypt duckdns hassconfigurator opt-portainer-1 crosschex-webapi ecm-engine dtbridge dtdiag"
if [[ "$MODE" == finale ]]; then
  running=$(hp "docker ps --format '{{.Names}}'" | grep -xF -f <(tr ' ' '\n' <<<"$SERVIZI") || true)
  if [[ -n "$running" ]]; then
    echo "ERRORE: sull'HP sono ancora attivi: $running" >&2; exit 1
  fi
fi

# mirror <sorgente HP> <destinazione mini PC>
# Percorso assoluto oppure 'vol:<nome volume>'.
mount_arg() { if [[ "$1" == vol:* ]]; then echo "${1#vol:}"; else echo "$1"; fi; }
mirror() {
  local src="$1" dst="$2"
  echo "-> $src  =>  $dst"
  hp "docker run --rm -v $(mount_arg "$src"):/src:ro alpine tar -C /src --numeric-owner --exclude=__pycache__ -cf - ." \
    | new "docker run --rm -i -v $(mount_arg "$dst"):/dst alpine sh -c 'find /dst -mindepth 1 -delete && tar -C /dst --numeric-owner -xpf -'"
}

# file singoli: copia/sovrascrive senza svuotare la cartella di destinazione
files() {
  local srcdir="$1" dstdir="$2"; shift 2
  echo "-> $srcdir/{$*}  =>  $dstdir"
  hp "docker run --rm -v $srcdir:/src:ro alpine sh -c 'cd /src && tar --numeric-owner -cf - $*'" \
    | new "docker run --rm -i -v $dstdir:/dst alpine tar -C /dst --numeric-owner -xpf -"
}

volume() {  # crea il volume con le etichette di compose, così compose lo riconosce come suo
  local name="$1" project="$2" key="$3"
  new "docker volume inspect $name >/dev/null 2>&1 || docker volume create \
       --label com.docker.compose.project=$project --label com.docker.compose.volume=$key $name >/dev/null"
}

echo "== /opt"
for d in homeassistant certs mosquitto nginx hassconf grott adguardhome frigate home-assistant-matter-hub home-assistant-matter-hub-2; do
  mirror "/opt/$d" "/opt/$d"
done
files /opt /opt docker-compose.yaml

echo "== volumi Docker"
volume opt_data opt data
volume dtbridge_dtbridge_data dtbridge dtbridge_data
volume dtdiag_dtdiag_data dtdiag dtdiag_data
mirror vol:opt_data vol:opt_data
mirror vol:dtbridge_dtbridge_data vol:dtbridge_dtbridge_data
mirror vol:dtdiag_dtdiag_data vol:dtdiag_dtdiag_data

echo "== /home/home (solo il necessario; i vecchi backup restano sull'HP)"
HOME_DIRS="ecm-engine dingtian webapi dtmon hassconf matterbridge .config/ecm"
HOME_FILES="docker-compose.yaml ha_backup_daily.sh audit_automations.py audit_candidates.py backup_db_snapshot.py cleanup_github.py read_night_temp.py remove_restart_button.py"
new "mkdir -p /home/home/.config/ecm"
for d in $HOME_DIRS; do
  mirror "/home/home/$d" "/home/home/$d"
done
files /home/home /home/home $HOME_FILES

echo "== proprietà: uid/gid 1000 dell'HP -> utente 'home' del mini PC"
uid=$(new 'id -u home'); gid=$(new 'id -g home')
targets=""; for p in $HOME_DIRS $HOME_FILES; do targets+=" /h/$p"; done
new "docker run --rm -v /home/home:/h alpine sh -c 'find $targets -xdev -user 1000 -exec chown -h $uid {} + ; find $targets -xdev -group 1000 -exec chgrp -h $gid {} +'"
new "chmod 600 /home/home/.config/ecm/ha_token && ls -l /home/home/.config/ecm/ha_token"

echo "== riepilogo dimensioni"
new "docker run --rm -v /opt:/opt:ro -v /home/home:/h:ro alpine du -sh /opt/homeassistant /opt/certs /opt/mosquitto /h/ecm-engine /h/dingtian /h/webapi"
echo "OK ($MODE)"
