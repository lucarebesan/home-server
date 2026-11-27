"""Aggiunge Chiusure2 alla Overview via WebSocket, senza reload o comandi fisici.

Eseguire nel container HA con aiohttp. Argomenti: vista-nuova.json originale.json.
Per aggiornare: aggiungere --replace precedente-chiusure2.json.
Il token arriva solo da stdin JSON {"token": ...}; non viene stampato o salvato.
"""
import asyncio
import copy
from datetime import datetime
import json
from pathlib import Path
import sys

import aiohttp


async def call(ws, seq, message):
    await ws.send_json({"id": seq, **message})
    while True:
        response = await ws.receive_json()
        if response.get("id") == seq:
            assert response.get("success"), response
            return response["result"]


def markdowns(value):
    if isinstance(value, dict):
        if value.get("type") == "markdown":
            yield value["content"]
        for child in value.values():
            yield from markdowns(child)
    elif isinstance(value, list):
        for child in value:
            yield from markdowns(child)


async def main():
    incoming = json.load(sys.stdin)
    token = incoming["token"]
    new = json.loads(Path(sys.argv[1]).read_text())
    expected = json.loads(Path(sys.argv[2]).read_text())
    previous = None
    if len(sys.argv) > 3:
        assert len(sys.argv) == 5 and sys.argv[3] == "--replace"
        previous = json.loads(Path(sys.argv[4]).read_text())
    assert new["path"] == "chiusure2" and expected["path"] == "chiusure"
    headers = {"Authorization": "Bearer " + token}
    timeout = aiohttp.ClientTimeout(total=45)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        count = 0
        for template in markdowns(new):
            async with session.post(
                "http://127.0.0.1:8123/api/template",
                headers=headers,
                json={"template": template},
            ) as response:
                assert response.status == 200, await response.text()
                rendered = await response.text()
                assert "TemplateError" not in rendered, rendered
                count += 1
        async with session.ws_connect("http://127.0.0.1:8123/api/websocket") as ws:
            await ws.receive_json()
            await ws.send_json({"type": "auth", "access_token": token})
            assert (await ws.receive_json())["type"] == "auth_ok"
            current = await call(ws, 1, {"type": "lovelace/config"})
            paths = [v.get("path") for v in current["views"]]
            index = paths.index("chiusure")
            assert current["views"][index] == expected, "Chiusure è cambiata: ricostruire dal live"
            desired = copy.deepcopy(current)
            if previous is None:
                assert "chiusure2" not in paths, "Chiusure2 esiste già: non sovrascritta"
                desired["views"].insert(index + 1, new)
                target_index = index + 1
            else:
                target_index = paths.index("chiusure2")
                assert current["views"][target_index] == previous, "Chiusure2 è cambiata in parallelo"
                desired["views"][target_index] = new
            stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            backup = Path("/config/tmp") / ("backup_lovelace_chiusure2_" + stamp + ".json")
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n")
            latest = await call(ws, 2, {"type": "lovelace/config"})
            assert latest == current, "Dashboard modificata in parallelo: salvataggio annullato"
            await call(ws, 3, {"type": "lovelace/config/save", "config": desired})
            actual = await call(ws, 4, {"type": "lovelace/config"})
            assert actual == desired, "Configurazione riletta diversa dal salvataggio"
            assert actual["views"][index] == expected
            remaining = actual["views"][:target_index] + actual["views"][target_index + 1:]
            old_remaining = current["views"] if previous is None else current["views"][:target_index] + current["views"][target_index + 1:]
            assert remaining == old_remaining
            source = Path("/config/dashboards/chiusure2.json")
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_text(json.dumps(new, ensure_ascii=False, indent=2) + "\n")
            print(json.dumps({
                "success": True,
                "path": "/lovelace/chiusure2",
                "after": "chiusure",
                "other_views_unchanged": True,
                "readback_identical": True,
                "markdown_templates_validated": count,
                "backup": str(backup),
                "source": str(source),
            }))


if __name__ == "__main__":
    asyncio.run(main())
