"""Ciclo del motore: campionamento, apprendimento, pubblicazione, prove."""
import logging
import threading
import time
from datetime import datetime, time as dtime

from . import config
from .combo import classify, descrizione, label_09, tipo_of, vent_idx
from .learner import aggregate, fascia, learning_pct
from .rules import Ctx, abort_reason, codes_for_season, is_night, propose, start_blockers
from .segmenter import segment
from .texts import best_line, detail_rows, summary_lines

log = logging.getLogger(__name__)
REQUIRED = ["p_cp", "p_tosh", "t_zg", "t_zn", "t_ext"]
SAMPLE_FIELDS = ["tosh_rps", "p_cp", "p_tosh", "t_zg", "t_zn", "t10", "t2", "t_ext", "soc", "pv",
                 "load", "imp", "discharge", "charge"]
SOGLIA_ESTATE_DEFAULT = 24.5
MANUALE = "input_select.ecm_manuale"
DURATA = "input_number.ecm_manuale_durata_minuti"


def build_sample(snap: dict, ts: int, open_test: dict | None) -> dict:
    c = classify(snap)
    s = {k: snap.get(k) for k in SAMPLE_FIELDS}
    s.update(ts=ts, stagione=snap.get("stagione"), test_id=None,
             cp_compressore=snap.get("cp_compressore"),
             code=c.code, tipo=c.tipo, valido=1, motivo=c.motivo)
    if c.code is None:
        s["valido"] = 0
    missing = [k for k in REQUIRED if snap.get(k) is None]
    if s["valido"] and missing:
        s["valido"], s["motivo"] = 0, f"dato mancante {missing[0]}"
    if open_test:
        s["test_id"] = open_test["id"]
        tc = open_test["code"]
        if s["valido"]:
            if c.code // 10 == tc // 10 and vent_idx(c.code % 10) == vent_idx(tc % 10):
                s["code"], s["tipo"] = tc, tipo_of(tc, snap.get("stagione"))
            else:
                s["valido"], s["motivo"] = 0, "prova non ancora applicata"
    return s


def _t(v, default):
    try:
        h, m = str(v).split(":")[:2]
        return dtime(int(h), int(m))
    except (ValueError, TypeError):
        return default


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts).isoformat(timespec="minutes")


class Engine:
    def __init__(self, api, store, pub, clock=time.time):
        self.api, self.store, self.pub, self.clock = api, store, pub, clock
        self.lock = threading.RLock()
        self.snap: dict | None = None
        self.stats: dict = {}
        self.proposal = None
        self.missing_since: dict[str, float] = {}
        self.ha_error: str | None = None

    # ---------- contesto
    def _ctx(self) -> Ctx | None:
        s = self.snap
        if not s or any(s.get(k) is None for k in ("t_zg", "t_zn", "lim_inf", "lim_sup", "soc")):
            return None
        comm, ist = s.get("commutazione"), s.get("isteresi_comm")
        soglia = comm + ist if comm is not None and ist is not None else SOGLIA_ESTATE_DEFAULT
        return Ctx(now=datetime.fromtimestamp(self.clock()), stagione=s.get("stagione"),
                   manuale=s.get("manuale"), free_cooling=s.get("free_cooling"),
                   acs_attivo=s.get("acs_inv") == "on" or s.get("acs_soc") == "on",
                   soc=s["soc"], pv=s.get("pv") or 0.0, load=s.get("load") or 0.0,
                   t_zg=s["t_zg"], t_zn=s["t_zn"], lim_inf=s["lim_inf"], lim_sup=s["lim_sup"],
                   mattina=_t(s.get("mattina"), dtime(8, 30)), serale=_t(s.get("serale"), dtime(22, 0)),
                   t_ext=s["t_ext"] if s.get("t_ext") is not None else 10.0,
                   soglia_estate=soglia)

    def _day_start(self) -> float:
        d = datetime.fromtimestamp(self.clock())
        return d.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()

    def _update_proposal(self) -> None:
        c = self._ctx()
        self.proposal = propose(self.stats, c) if c else None

    # ---------- campionamento
    def tick_sample(self) -> None:
        with self.lock:
            now = int(self.clock())
            try:
                self.snap = self.api.snapshot(config.ENTITIES, config.NUMERIC_KEYS)
                self.ha_error = None
            except Exception as ex:  # rete o HA giù
                self.ha_error = f"HA non raggiungibile: {ex}"
                log.warning(self.ha_error)
                self._publish_status()
                return
            self.store.add_sample(build_sample(self.snap, now, self.store.open_test()))
            for k in REQUIRED:
                if self.snap.get(k) is None:
                    self.missing_since.setdefault(k, now)
                else:
                    self.missing_since.pop(k, None)
            self._update_proposal()
            self._supervise()
            self._auto_start()
            self._publish_status()

    # ---------- prove
    def start_test(self, origine: str) -> str | None:
        c = self._ctx()
        p = self.proposal
        if c is None or p is None:
            return "dati non disponibili"
        last = self.store.last_test_end()
        blockers = start_blockers(c, p.tipo, origine == "auto",
                                  len(self.store.tests_since(self._day_start(), origine="auto")),
                                  datetime.fromtimestamp(last) if last else None)
        if self.store.open_test():
            blockers.append("prova già in corso")
        if blockers:
            return blockers[0]
        try:
            self.api.call_service("input_number", "set_value", {"entity_id": DURATA, "value": p.durata})
        except Exception as ex:  # helper assente: 09 usa la sua durata, la prova parte lo stesso
            log.warning("impostazione durata fallita: %s", ex)
        self.api.call_service("input_select", "select_option",
                              {"entity_id": MANUALE, "option": label_09(p.code)})
        self.store.start_test(p.code, p.durata, origine, int(self.clock()))
        log.info("prova %s avviata: E%s per %s min", origine, p.code, p.durata)
        return None

    def _supervise(self) -> None:
        t = self.store.open_test()
        c = self._ctx()
        if not t or c is None:
            return
        now = int(self.clock())
        label = label_09(t["code"])
        elapsed = now - t["inizio"]
        if elapsed < 90 and c.manuale != label:
            return  # 09 non ha ancora applicato la selezione
        if c.manuale == "AUTO" and elapsed >= t["durata_min"] * 60 - 60:
            self.store.end_test(t["id"], now, "completata")
            log.info("prova %s completata", t["id"])
            return
        reason = abort_reason(c, tipo_of(t["code"], c.stagione), label)
        if reason is None:
            return
        if reason != "interrotta dall'utente":
            self.api.call_service("input_select", "select_option", {"entity_id": MANUALE, "option": "AUTO"})
        self.store.end_test(t["id"], now, reason)
        log.info("prova %s chiusa: %s", t["id"], reason)

    def _auto_start(self) -> None:
        if self.store.get_setting("auto", "0") != "1" or self.store.open_test():
            return
        err = self.start_test("auto")
        if err:
            log.debug("avvio automatico non possibile: %s", err)

    def recover(self) -> None:
        """All'avvio: chiude una prova rimasta aperta."""
        with self.lock:
            t = self.store.open_test()
            if not t:
                return
            try:
                snap = self.api.snapshot(config.ENTITIES, config.NUMERIC_KEYS)
                if snap.get("manuale") == label_09(t["code"]):
                    self.api.call_service("input_select", "select_option",
                                          {"entity_id": MANUALE, "option": "AUTO"})
            except Exception as ex:
                log.warning("recover: %s", ex)
            self.store.end_test(t["id"], int(self.clock()), "interrotta dal riavvio del motore")

    def on_command(self, topic: str, payload: str) -> None:
        with self.lock:
            if topic == "ecm_engine/avvia_prova/cmd":
                err = self.start_test("manuale")
                if err:
                    log.info("avvio manuale rifiutato: %s", err)
            elif topic == "ecm_engine/prove_automatiche/set":
                on = payload.strip().upper() == "ON"
                self.store.set_setting("auto", "1" if on else "0")
                self.pub.set_state("prove_automatiche", "ON" if on else "OFF")
            self._publish_status()

    # ---------- apprendimento e pubblicazione
    def tick_learn(self) -> None:
        with self.lock:
            now = int(self.clock())
            since = now - config.RETENTION_DAYS * 86400
            self.store.purge(since)
            self.stats = aggregate(segment(self.store.iter_samples_since(since)))
            self._update_proposal()
            self._publish_learn()
            self._publish_status()

    def _publish_learn(self) -> None:
        c = self._ctx()
        if c is None:
            return
        f = fascia(c.t_ext)
        night = is_night(c)
        heat = [x for x in codes_for_season("INVERNO", night) if tipo_of(x, "INVERNO") == "HEAT"]
        cool = [x for x in codes_for_season("ESTATE", night) if tipo_of(x, "ESTATE") in ("COOL", "DRY")]
        pct_h = learning_pct(self.stats, heat, f, "INVERNO")
        pct_c = learning_pct(self.stats, cool, f, "ESTATE")
        pct = pct_h if c.stagione == "INVERNO" else pct_c
        lines = summary_lines(self.stats, c.stagione, f, pct)
        self.pub.set_state("in_breve", lines[0], {"righe": lines, "fascia_esterna": f})
        self.pub.set_state("migliore_caldo", best_line(self.stats, "HEAT", f, c.stagione))
        self.pub.set_state("migliore_freddo", best_line(self.stats, "COOL", f, c.stagione))
        self.pub.set_state("apprendimento_caldo", pct_h)
        self.pub.set_state("apprendimento_freddo", pct_c)
        rows = detail_rows(self.stats, f, c.stagione)
        self.pub.set_state("dettaglio", len(rows), {"fascia_esterna": f, "tabella": rows})

    def _publish_status(self) -> None:
        now = int(self.clock())
        avvisi = [f"{k} non disponibile da {round((now - t0) / 60)} minuti"
                  for k, t0 in self.missing_since.items() if now - t0 >= 1800]
        if self.ha_error:
            avvisi.append(self.ha_error)
        self.pub.set_state("avvisi", len(avvisi), {"elenco": avvisi})
        t = self.store.open_test()
        if t:
            stagione = (self.snap or {}).get("stagione") or "INVERNO"
            self.pub.set_state("prova_in_corso", descrizione(t["code"], stagione),
                               {"codice": f"E{t['code']}", "origine": t["origine"],
                                "inizio": _iso(t["inizio"]),
                                "fine_prevista": _iso(t["inizio"] + t["durata_min"] * 60),
                                "minuti_trascorsi": round((now - t["inizio"]) / 60)})
            stato = "prova in corso"
        else:
            self.pub.set_state("prova_in_corso", "nessuna", {})
            stato = "errore HA" if self.ha_error else "online"
        self.pub.set_state("stato", stato)
        self.pub.set_state("prove_automatiche", "ON" if self.store.get_setting("auto", "0") == "1" else "OFF")
        c, p = self._ctx(), self.proposal
        if p and c:
            last = self.store.last_test_end()
            blk = start_blockers(c, p.tipo, False, 0, datetime.fromtimestamp(last) if last else None)
            if t:
                blk = ["prova in corso"] + blk
            self.pub.set_state("prova_proposta", f"{descrizione(p.code, c.stagione)} per {p.durata} minuti",
                               {"codice": f"E{p.code}", "durata": p.durata, "motivo": p.motivo,
                                "avviabile": not blk, "motivo_blocco": blk[0] if blk else ""})
        else:
            why = "dati non disponibili" if c is None else "nessuna combinazione provabile con queste temperature"
            self.pub.set_state("prova_proposta", "nessuna", {"avviabile": False, "motivo_blocco": why})
