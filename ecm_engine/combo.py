"""Stato reale delle macchine -> codice combinazione E (numerazione HA)."""
from dataclasses import dataclass

CP_VENT = {"OFF": 0, "STEP 2": 2, "STEP 3": 3, "STEP 4": 4}
TOSH_VENT = {"BASSA": 1, "MEDIA": 2, "ALTA": 3}
TOSH_MODO_BASE = {"DEUMIDIFICATORE": 0, "RAFFRESCAMENTO": 3, "RISCALDAMENTO": 6}
CP_STATI_ESCLUSI = {"ACS", "ANTILEGIONELLA", "SBRINAMENTO", "ALLARME", "SERVICE", "PROTEZIONE ANTIGELO"}
SPEED_NAME = {1: "bassa", 2: "media", 3: "alta"}


@dataclass(frozen=True)
class Combo:
    code: int | None
    tipo: str | None
    motivo: str | None


def _u(v):
    return (v or "").strip().upper()


def vent_idx(u: int) -> int:
    """0 = V0, 1/2/3 = V2/V3/V4 indipendentemente dal compressore."""
    return 0 if u == 0 else (u - 1) % 3 + 1


def cp_unit(cp_vent: str, cp_compressore: str) -> int | None:
    v = CP_VENT.get(_u(cp_vent))
    if v is None:
        return None
    on = _u(cp_compressore) == "ON"
    if v == 0:
        return None if on else 0
    return (v - 1) + (3 if on else 0)


def tosh_decade(on: str, modo: str, vent: str) -> int | None:
    if _u(on) != "ACCESO":
        return 0
    base = TOSH_MODO_BASE.get(_u(modo))
    v = TOSH_VENT.get(_u(vent))
    if base is None or v is None:
        return None
    return base + v


def tipo_of(code: int, stagione: str) -> str:
    d, u = divmod(code, 10)
    if d >= 7:
        return "HEAT"
    if d >= 4:
        return "COOL"
    if d >= 1:
        return "DRY"
    if u >= 4:
        return "HEAT" if _u(stagione) == "INVERNO" else "COOL"
    return "NEUTRO"


def classify(s: dict) -> Combo:
    stato = _u(s.get("cp_stato"))
    if stato in CP_STATI_ESCLUSI:
        return Combo(None, None, f"cp_stato {stato}")
    if _u(s.get("cp_resistenza")) == "ON":
        return Combo(None, None, "resistenza ACS")
    if _u(s.get("free_cooling")) in ("ATTIVATO", "PREPARAZIONE"):
        return Combo(None, None, "free cooling")
    u = cp_unit(s.get("cp_vent"), s.get("cp_compressore"))
    if u is None:
        return Combo(None, None, "cp non classificato")
    d = tosh_decade(s.get("tosh_on"), s.get("tosh_modo"), s.get("tosh_vent"))
    if d is None:
        return Combo(None, None, "toshiba non classificato")
    code = 10 * d + u
    return Combo(code, tipo_of(code, s.get("stagione")), None)


def _cp_label(u: int) -> str:
    if u == 0:
        return "CP OFF V0"
    return f"CP {'ON' if u >= 4 else 'OFF'} V{vent_idx(u) + 1}"


def _split_label(d: int) -> str:
    if d == 0:
        return "Split OFF"
    mode = ["DRY", "COOL", "HEAT"][(d - 1) // 3]
    return f"{mode} V{(d - 1) % 3 + 1}"


def label_09(code: int) -> str:
    d, u = divmod(code, 10)
    return f"E{code} - {_cp_label(u)} • {_split_label(d)}"


def descrizione(code: int, stagione: str) -> str:
    d, u = divmod(code, 10)
    if u == 0:
        cp = "Nilan ferma"
    elif u >= 4:
        cp = f"Nilan pompa di calore V{vent_idx(u) + 1}"
    else:
        cp = f"Nilan solo ventilazione V{vent_idx(u) + 1}"
    if d == 0:
        t = "Toshiba spento"
    else:
        mode = ["deumidifica", "freddo", "caldo"][(d - 1) // 3]
        t = f"Toshiba {mode} {SPEED_NAME[(d - 1) % 3 + 1]}"
    return f"{cp} + {t}"
