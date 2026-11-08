"""Stato reale delle macchine -> codice combinazione E (numerazione HA)."""
from dataclasses import dataclass

CP_VENT = {"OFF": 0, "STEP 1": 1, "STEP 2": 2, "STEP 3": 3, "STEP 4": 4}
# u 0..6 e' la numerazione HA (09 la usa). u 7/8 = V1 (STEP 1) con compressore OFF/ON: solo
# osservazione e apprendimento, 09 non ha queste opzioni, quindi mai proposti come prova.
U_V1_OFF, U_V1_ON = 7, 8
V1_IDX = 4
TOSH_VENT = {"BASSA": 1, "MEDIA": 2, "ALTA": 3}
TOSH_MODO_BASE = {"DEUMIDIFICATORE": 0, "RAFFRESCAMENTO": 3, "RISCALDAMENTO": 6}
CP_STATI_ESCLUSI = {"ACS", "ANTILEGIONELLA", "SBRINAMENTO", "ALLARME", "SERVICE", "PROTEZIONE ANTIGELO"}
SPEED_NAME = {1: "bassa", 2: "media", 3: "alta"}
RESISTENZA_ACS = "resistenza ACS"


@dataclass(frozen=True)
class Combo:
    code: int | None
    tipo: str | None
    motivo: str | None


def _u(v):
    return (v or "").strip().upper()


def vent_idx(u: int) -> int:
    """0 = V0, 1/2/3 = V2/V3/V4, 4 = V1 indipendentemente dal compressore."""
    if u >= U_V1_OFF:
        return V1_IDX
    return 0 if u == 0 else (u - 1) % 3 + 1


def cp_unit(cp_vent: str, cp_compressore: str) -> int | None:
    v = CP_VENT.get(_u(cp_vent))
    comp = _u(cp_compressore)
    if v is None or comp not in ("ON", "OFF"):
        return None
    on = comp == "ON"
    if v == 0:
        return None if on else 0
    if v == 1:
        return U_V1_ON if on else U_V1_OFF
    return (v - 1) + (3 if on else 0)


def tosh_decade(on: str, modo: str, vent: str) -> int | None:
    if _u(on) not in ("ACCESO", "SPENTO"):
        return None
    if _u(on) == "SPENTO":
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
    if u >= 4 and u != U_V1_OFF:
        return "HEAT" if _u(stagione) == "INVERNO" else "COOL"
    return "NEUTRO"


def classify(s: dict) -> Combo:
    stato = _u(s.get("cp_stato"))
    if stato in CP_STATI_ESCLUSI:
        return Combo(None, None, f"cp_stato {stato}")
    if _u(s.get("free_cooling")) in ("ATTIVATO", "PREPARAZIONE"):
        return Combo(None, None, "free cooling")
    u = cp_unit(s.get("cp_vent"), s.get("cp_compressore"))
    if u is None:
        return Combo(None, None, "cp non classificato")
    d = tosh_decade(s.get("tosh_on"), s.get("tosh_modo"), s.get("tosh_vent"))
    if d is None:
        return Combo(None, None, "toshiba non classificato")
    code = 10 * d + u
    # resistenza ACS: la combinazione resta quella dell'aria; il suo consumo (contatore Nilan)
    # viene tolto dal segmenter (correct_acs). Il motivo resta sul campione come marcatore.
    acs = RESISTENZA_ACS if _u(s.get("cp_resistenza")) == "ON" else None
    return Combo(code, tipo_of(code, s.get("stagione")), acs)


def _vnum(u: int) -> int:
    return 1 if u >= U_V1_OFF else vent_idx(u) + 1


def _cp_on(u: int) -> bool:
    return u == U_V1_ON or 4 <= u <= 6


def _cp_label(u: int) -> str:
    if u == 0:
        return "CP OFF V0"
    return f"CP {'ON' if _cp_on(u) else 'OFF'} V{_vnum(u)}"


def _split_label(d: int) -> str:
    if d == 0:
        return "Split OFF"
    mode = ["DRY", "COOL", "HEAT"][(d - 1) // 3]
    return f"{mode} V{(d - 1) % 3 + 1}"


def label_09(code: int) -> str:
    d, u = divmod(code, 10)
    if u >= U_V1_OFF:
        raise ValueError(f"E{code}: V1 non ha un'opzione 09 (solo osservazione)")
    return f"E{code} - {_cp_label(u)} • {_split_label(d)}"


def descrizione(code: int, stagione: str) -> str:
    d, u = divmod(code, 10)
    if u == 0:
        cp = "Nilan ferma"
    elif _cp_on(u):
        cp = f"Nilan pompa di calore V{_vnum(u)}"
    else:
        cp = f"Nilan solo ventilazione V{_vnum(u)}"
    if d == 0:
        t = "Toshiba spento"
    else:
        mode = ["deumidifica", "freddo", "caldo"][(d - 1) // 3]
        t = f"Toshiba {mode} {SPEED_NAME[(d - 1) % 3 + 1]}"
    return f"{cp} + {t}"
