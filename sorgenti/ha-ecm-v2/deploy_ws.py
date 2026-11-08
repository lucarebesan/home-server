"""Deploy di ECM v2 via WebSocket, senza riavviare HA. Gira DENTRO il container homeassistant.

Uso (dal Mac, il token si espande solo sul server):
  scp lovelace.ecm_v2 deploy_ws.py home@192.168.1.100:/tmp/
  ssh home@192.168.1.100 'docker cp /tmp/lovelace.ecm_v2 homeassistant:/tmp/ && docker cp /tmp/deploy_ws.py homeassistant:/tmp/ && \
    docker exec -e TOKEN="$(cat ~/.config/ecm/ha_token)" homeassistant python3 /tmp/deploy_ws.py backup > ~/backup-ecm-v2-$(date +%Y%m%d-%H%M%S).json && \
    docker exec -e TOKEN="$(cat ~/.config/ecm/ha_token)" homeassistant python3 /tmp/deploy_ws.py save /tmp/lovelace.ecm_v2'

Modi: list (dashboard), backup (config attuale su stdout), save <file> (file di build.py o config nuda).
"""
import asyncio, json, os, sys
import aiohttp

URL_PATH = "ecm-v2"


async def call(ws, n, msg):
    await ws.send_json({"id": n, **msg})
    while True:
        r = await ws.receive_json()
        if r.get("id") == n:
            return r


async def main():
    mode = sys.argv[1]
    async with aiohttp.ClientSession() as s:
        async with s.ws_connect("http://127.0.0.1:8123/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": os.environ["TOKEN"]})
            assert (await ws.receive_json())["type"] == "auth_ok", "auth fallita"
            dl = await call(ws, 1, {"type": "lovelace/dashboards/list"})
            if not any(d.get("url_path") == URL_PATH for d in dl["result"]):
                sys.exit(f"dashboard {URL_PATH} non trovata")
            if mode == "list":
                for d in dl["result"]:
                    print(d.get("url_path"), d.get("title"), d.get("mode"), file=sys.stderr)
            elif mode == "backup":
                r = await call(ws, 2, {"type": "lovelace/config", "url_path": URL_PATH})
                assert r["success"], r
                print(json.dumps(r["result"], ensure_ascii=False, indent=2))
            elif mode == "save":
                data = json.load(open(sys.argv[2]))
                cfg = data["data"]["config"] if "data" in data else data
                r = await call(ws, 2, {"type": "lovelace/config/save", "url_path": URL_PATH, "config": cfg})
                print(json.dumps(r, ensure_ascii=False))
                r2 = await call(ws, 3, {"type": "lovelace/config", "url_path": URL_PATH})
                print("views ora:", [v.get("path") for v in r2["result"]["views"]])


asyncio.run(main())
