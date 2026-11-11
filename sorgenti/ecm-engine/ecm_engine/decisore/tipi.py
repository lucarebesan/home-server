"""Tipi del decisore: dati puri, nessun I/O."""
import json
from dataclasses import asdict, dataclass, field, fields
from enum import Enum


class Risorsa(str, Enum):
    TOSHIBA = "toshiba"
    CP_COMPRESSORE = "cp_compressore"
    CP_VENTILATORE = "cp_ventilatore"
    CP_RESISTENZA = "cp_resistenza"


@dataclass(frozen=True)
class Contesto:
    """Fotografia coerente di un ciclo. Le temperature di zona sono medie a 10 minuti."""
    ts: int
    notte: bool
    t_min: float | None
    massimo: float | None
    t_zg: float | None
    t_zn: float | None
    trend_zg: dict
    trend_zn: dict
    vel_reale: int | None          # Toshiba: 0 spento, 1..3 HEAT V1..V3, None non classificabile
    vel_reale_dal: int | None
    soc: float | None
    pv: float | None
    load: float | None
    consumo_base: float | None
    imp: float | None
    discharge: float | None
    charge: float | None
    consenso_fv: bool | None
    prelievo_rete_stabile: bool
    ore_al_mattino: float
    carico_notte_wh: float | None
    risorse_occupate: frozenset = frozenset()
    latch_ha: dict | None = None   # {"rec_zg", "rec_zn", "accumulo"} se leggibili in HA


@dataclass(frozen=True)
class Appresi:
    costo: dict                    # velocità Toshiba -> W per °C/h (solo misurati)
    w: dict                        # velocità Toshiba -> W misurati
    preferita: int | None = None   # codice di migliore_caldo se è E70/E80/E90


@dataclass(frozen=True)
class Richiesta:
    servizio: str                  # "recupero" | "accumulo"
    livello: int
    zone: tuple
    motivo: str


@dataclass(frozen=True)
class Candidato:
    vel: int

    @property
    def code(self) -> int:
        return 10 * (6 + self.vel) if self.vel else 0

    @property
    def risorse(self) -> frozenset:
        return frozenset({Risorsa.TOSHIBA}) if self.vel else frozenset()


VERSIONE_STATO = 1


@dataclass(frozen=True)
class Stato:
    rec_zg: bool = False
    rec_zn: bool = False
    accumulo: bool = False
    seq: int = 0
    ultimo_vel: int | None = None  # ultima velocità reale vista e da quando
    vel_dal: int | None = None

    def to_json(self) -> str:
        return json.dumps({"versione": VERSIONE_STATO, **asdict(self)})

    @classmethod
    def from_json(cls, txt: str) -> "Stato":
        try:
            d = json.loads(txt)
        except (TypeError, ValueError):
            return cls()
        if not isinstance(d, dict) or d.get("versione") != VERSIONE_STATO:
            return cls()
        return cls(**{f.name: d[f.name] for f in fields(cls) if f.name in d})


@dataclass(frozen=True)
class Piano:
    seq: int
    emesso: int
    valido_fino: int
    vel: int | None
    richiesta: Richiesta | None
    servite: tuple
    rinviate: tuple
    motivo: str
    scartati: dict
    energia: dict
    fonte_stato: str
    stato: Stato
    soglie: dict = field(default_factory=dict)

    @property
    def code(self) -> int | None:
        return None if self.vel is None else Candidato(self.vel).code
