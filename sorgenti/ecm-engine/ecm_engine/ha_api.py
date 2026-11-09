"""Accesso REST a Home Assistant (una richiesta template per tutti gli stati)."""
import json
import math
import urllib.request


def build_template(entities: dict, reported: dict | None = None) -> str:
    """Un dizionario JSON con lo stato di ogni entità e, per quelle in reported, il timestamp
    dell'ultima lettura ricevuta (None se l'entità non esiste)."""
    parts = [f"'{k}': states('{v}')" for k, v in entities.items()]
    parts += [f"'{k}': (expand('{v}') | map(attribute='last_reported') | map('as_timestamp') | first"
              f" | default(none))" for k, v in (reported or {}).items()]
    return "{{ {" + ", ".join(parts) + "} | tojson }}"


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def parse_snapshot(raw: dict, numeric: list[str]) -> dict:
    return {k: (_num(v) if k in numeric else v) for k, v in raw.items()}


class HAApi:
    def __init__(self, base: str, token_file: str, timeout: float = 15):
        self.base = base.rstrip("/")
        with open(token_file) as f:
            self.token = f.read().strip()
        self.timeout = timeout

    def _req(self, path: str, body: dict | None) -> str:
        req = urllib.request.Request(
            self.base + path, method="POST" if body is not None else "GET",
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            return r.read().decode()

    def snapshot(self, entities: dict, numeric: list[str], reported: dict | None = None) -> dict:
        txt = self._req("/api/template", {"template": build_template(entities, reported)})
        return parse_snapshot(json.loads(txt), numeric)

    def call_service(self, domain: str, service: str, data: dict) -> None:
        self._req(f"/api/services/{domain}/{service}", data)
