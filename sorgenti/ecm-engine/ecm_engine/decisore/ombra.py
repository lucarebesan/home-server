"""Ombra dell'ambiente invernale: dal campione HA al contesto, decisione, confronto con la
realtà, persistenza e metriche. Non chiama servizi HA."""
import logging
from dataclasses import replace
from datetime import datetime, time as dtime, timedelta

from ..learner import fascia
from ..texts import best_stat
from . import energia
from .arbitro import decidi
from .parametri import DIVERGENZA_CICLI
from .tipi import Appresi, Contesto, Stato

log = logging.getLogger(__name__)
VEL = {"BASSA": 1, "MEDIA": 2, "ALTA": 3}
AFFIDABILITA_MIN = 0.4
ON_OFF = {"on": True, "off": False}


def vel_toshiba(snap: dict) -> int | None:
    on = str(snap.get("tosh_on") or "").upper()
    if on == "SPENTO":
        return 0
    if on != "ACCESO" or str(snap.get("tosh_modo") or "").upper() != "RISCALDAMENTO":
        return None
    return VEL.get(str(snap.get("tosh_vent") or "").upper())


def appresi_da(stats: dict, power_stats: dict, f: str) -> Appresi:
    costo, w = {}, {}
    for v in (1, 2, 3):
        s = stats.get((10 * (6 + v), "HEAT", f))
        if s is not None and s.costo is not None and s.affidabilita >= AFFIDABILITA_MIN:
            costo[v] = s.costo
        if s is not None:
            # La tabella letta dalla 10 espone W misurati del periodo prima della stima separata.
            w[v] = s.p_tot
        else:
            p = power_stats.get(("INVERNO", "tosh", 6 + v, f))
            if p is not None:
                w[v] = p.W
    migliore = best_stat(stats, "HEAT", f)
    preferita = (migliore.code // 10 - 6) if migliore and migliore.code in (70, 80, 90) else None
    return Appresi(costo=costo, w=w, preferita=preferita)


def _ora(v, default: dtime) -> dtime:
    try:
        h, m = str(v).split(":")[:2]
        return dtime(int(h), int(m))
    except (ValueError, TypeError):
        return default


def _num(v):
    return v if isinstance(v, (int, float)) else None


class Ombra:
    def __init__(self, store, pub, now: int):
        self.store, self.pub = store, pub
        self.stato = Stato.from_json(store.get_setting("decisore_stato", ""))
        self.divergenze = 0
        self.ultimo_contesto: Contesto | None = None
        self.ultimo_piano = None
        self._pubblicato = None

    def _contesto(self, snap: dict, now: int) -> Contesto:
        dt = datetime.fromtimestamp(now)
        mattina = _ora(snap.get("mattina"), dtime(8, 30))
        # La 10 usa il sensore che applica nilan_notturna - 1 h, non nilan_serale.
        notte = snap.get("fascia_climatica") == "NOTTE"
        prossima = datetime.combine(dt.date(), mattina)
        if prossima <= dt:
            prossima += timedelta(days=1)
        ore = (prossima - dt).total_seconds() / 3600 if notte else 0.0
        consumo_base = _num(snap.get("consumo_base"))
        carico = None
        if notte:
            if (_num(snap.get("copertura_profilo")) or 0) >= 100 and consumo_base is not None:
                profilo = {h: (_num(snap.get(f"profilo_h{h:02d}"))
                                if _num(snap.get(f"profilo_h{h:02d}")) is not None else consumo_base)
                           for h in range(24)}
                carico = energia.carico_fino_a(profilo, dt, prossima)
            if carico is None and consumo_base is not None:
                carico = consumo_base * ore   # come la 10 quando la copertura è sotto 100%
        zg, zn = _num(snap.get("t_zg_10m")), _num(snap.get("t_zn_10m"))
        trend_zg = {m: _num(snap.get(f"trend_zg_{m}")) for m in (20, 30, 60)}
        trend_zn = {m: _num(snap.get(f"trend_zn_{m}")) for m in (20, 30, 60)}
        vel = vel_toshiba(snap)
        if vel != self.stato.ultimo_vel:
            self.stato = replace(self.stato, ultimo_vel=vel, vel_dal=now)
        latch = {k: ON_OFF.get(str(snap.get(e))) for k, e in
                 (("rec_zg", "rec_zg"), ("rec_zn", "rec_zn"), ("accumulo", "accumulo_ha"))}
        return Contesto(
            ts=now, notte=notte, t_min=_num(snap.get("t_min_inv")), massimo=_num(snap.get("massimo_acc")),
            t_zg=zg, t_zn=zn, trend_zg=trend_zg, trend_zn=trend_zn,
            vel_reale=vel, vel_reale_dal=self.stato.vel_dal, soc=_num(snap.get("soc")),
            pv=_num(snap.get("pv")), load=_num(snap.get("load")), consumo_base=consumo_base,
            imp=_num(snap.get("imp")), discharge=_num(snap.get("discharge")), charge=_num(snap.get("charge")),
            consenso_fv=(snap.get("consenso_carica") == "on"
                         or snap.get("consenso_batteria_piena") == "on"),
            prelievo_rete_stabile=snap.get("prelievo_rete_stabile") == "on",
            ore_al_mattino=ore, carico_notte_wh=carico,
            latch_ha=latch if None not in latch.values() else None)

    @staticmethod
    def _non_confrontabile(snap: dict, open_test, c: Contesto, piano) -> str | None:
        if snap.get("stagione") != "INVERNO":
            return "stagione non INVERNO"
        if snap.get("manuale") != "AUTO":
            return "09 non in AUTO"
        if open_test:
            return "prova in corso"
        if snap.get("auto_10") != "on":
            return "10 non accesa"
        if c.vel_reale is None:
            return "Toshiba in un modo diverso da spento/HEAT"
        if piano.motivo.startswith("dati critici"):
            return "dati critici non validi"
        return None

    # ---------- un ciclo
    def passo(self, snap: dict, now: int, open_test, stats: dict, power_stats: dict) -> dict:
        c = self._contesto(snap, now)
        t_ext = next((v for v in (_num(snap.get("t_ext_aff")), _num(snap.get("t_ext"))) if v is not None), None)
        appresi = appresi_da(stats, power_stats, fascia(t_ext)) if t_ext is not None else Appresi({}, {})
        piano = decidi(c, appresi, self.stato)
        self.stato = piano.stato
        self.ultimo_contesto, self.ultimo_piano = c, piano

        perche = self._non_confrontabile(snap, open_test, c, piano)
        if perche:
            self.divergenze, confronto = 0, "non confrontabile"
        elif piano.vel == c.vel_reale:
            self.divergenze, confronto = 0, "concorde"
        else:
            self.divergenze += 1
            confronto = "divergente" if self.divergenze >= DIVERGENZA_CICLI else "transitorio"
        sotto = {z: int(t is not None and z in piano.soglie and t < piano.soglie[z][0])
                 for z, t in (("zg", c.t_zg), ("zn", c.t_zn))}
        row = dict(ts=now, confronto=confronto, motivo_confronto=perche, py_vel=piano.vel,
                   ha_vel=c.vel_reale, motivo=piano.motivo, fonte_stato=piano.fonte_stato,
                   sotto_zg=sotto["zg"], sotto_zn=sotto["zn"])
        self.store.add_ombra(row)
        self.store.set_setting("decisore_stato", self.stato.to_json())
        self._pubblica(row, piano)
        return row

    def _pubblica(self, row: dict, piano) -> None:
        # niente seq/emesso negli attributi: il recorder di HA scrive solo ai cambi
        stato = "divergente" if row["confronto"] == "divergente" else (
            "non confrontabile" if row["confronto"] == "non confrontabile" else "concorde")
        attrs = {"python": f"E{piano.code}" if piano.code is not None else None,
                 "reale": f"E{10 * (6 + row['ha_vel'])}" if row["ha_vel"] else ("E0" if row["ha_vel"] == 0 else None),
                 "motivo": piano.motivo, "motivo_confronto": row["motivo_confronto"],
                 "fonte_stato": piano.fonte_stato, "soglie": piano.soglie,
                 "scartati": {f"V{k}": v for k, v in piano.scartati.items()},
                 "energia": piano.energia.get(piano.vel) if piano.vel else None}
        if (stato, attrs) != self._pubblicato:
            self.pub.set_state("ombra_ambiente", stato, attrs)
            self._pubblicato = (stato, attrs)

    # ---------- metriche di risultato del giorno
    def metriche(self, now: int) -> dict:
        inizio = int(datetime.fromtimestamp(now).replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        rows = self.store.ombra_since(inizio)
        kwh_t, kwh_r = self.store.energia_since(inizio)
        reali = [r["ha_vel"] for r in rows if r["ha_vel"] is not None]
        m = {"minuti_confrontabili": sum(r["confronto"] != "non confrontabile" for r in rows),
             "minuti_divergenti": sum(r["confronto"] == "divergente" for r in rows),
             "minuti_sotto_soglia_zg": sum(r["sotto_zg"] or 0 for r in rows),
             "minuti_sotto_soglia_zn": sum(r["sotto_zn"] or 0 for r in rows),
             "kwh_toshiba": round(kwh_t, 2), "kwh_rete": round(kwh_r, 2),
             "cambi_velocita_reali": sum(1 for a, b in zip(reali, reali[1:]) if a != b)}
        self.pub.set_state("ombra_metriche", m["minuti_divergenti"], m)
        return m
