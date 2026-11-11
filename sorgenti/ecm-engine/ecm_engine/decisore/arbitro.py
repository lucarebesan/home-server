"""Valutatore e arbitro in un'unica pipeline pura: decidi(contesto, appresi, stato) -> piano."""
from dataclasses import replace

from . import ambiente, energia
from .parametri import (LEASE_S, PERMANENZA_S, TREND_NON_POSITIVI, VEL_MAX, VEL_RIPIEGO, W_RIPIEGO)
from .tipi import Appresi, Candidato, Contesto, Piano, Stato

VELOCITA = (0, 1, 2, 3)


def _stato_precedente(c: Contesto, stato: Stato) -> tuple[Stato, str]:
    if c.latch_ha is not None:
        return replace(stato, rec_zg=c.latch_ha["rec_zg"], rec_zn=c.latch_ha["rec_zn"],
                       accumulo=c.latch_ha["accumulo"]), "ha"
    return stato, "proprio"


def _w(appresi: Appresi, vel: int) -> float:
    return 0.0 if vel == 0 else appresi.w.get(vel, W_RIPIEGO[vel])


def _trend_insufficiente(c: Contesto, zone) -> bool:
    for z in zone:
        tr = c.trend_zg if z == "zg" else c.trend_zn
        valori = [tr.get(m) for m in (20, 30, 60)]
        # La 10 richiede tutte e tre le finestre numeriche prima di salire.
        if all(v is not None for v in valori) and sum(v <= 0 for v in valori) >= TREND_NON_POSITIVI:
            return True
    return False


def _preferita(c: Contesto, appresi: Appresi, cap: int, richiesta, permanenza_finita: bool) -> int:
    noti = {v: appresi.costo[v] for v in range(1, cap + 1) if appresi.costo.get(v) is not None}
    if appresi.preferita:
        # La 10 usa prima il codice di migliore_caldo, anche se marcato da confermare.
        base = min(appresi.preferita, cap)
    else:
        base = min(noti, key=lambda v: (noti[v], v)) if noti else min(VEL_RIPIEGO[c.notte], cap)
    if (richiesta and richiesta.servizio == "recupero" and permanenza_finita
            and c.vel_reale and _trend_insufficiente(c, richiesta.zone)):
        base = max(base, min(c.vel_reale + 1, cap))
    return base


def decidi(c: Contesto, appresi: Appresi, stato: Stato) -> Piano:
    prev, fonte = _stato_precedente(c, stato)
    seq = stato.seq + 1
    lease = dict(seq=seq, emesso=c.ts, valido_fino=c.ts + LEASE_S)
    if c.t_min is None or c.t_zg is None or c.t_zn is None or c.vel_reale is None:
        return Piano(**lease, vel=c.vel_reale, richiesta=None, servite=(), rinviate=(),
                     motivo="dati critici non validi: nessun cambio", scartati={}, energia={},
                     fonte_stato=fonte, stato=replace(prev, seq=seq))

    # 1. domanda (l'accumulo è possibile solo se almeno un candidato acceso supera l'energia)
    cap = VEL_MAX[c.notte]
    possibile = any(energia.giudica(c, v, _w(appresi, v), prev.accumulo)[0] for v in range(1, cap + 1))
    st, richiesta, info = ambiente.domanda(c, prev, accumulo_possibile=possibile)

    # 2-3. candidati e vincoli rigidi
    in_permanenza = (0 < c.vel_reale <= cap and c.vel_reale_dal is not None
                     and c.ts - c.vel_reale_dal < PERMANENZA_S and not info["massimo"])
    scartati, giudizi = {}, {}
    for v in VELOCITA:
        cand = Candidato(v)
        if cand.risorse & c.risorse_occupate:
            scartati[v] = "risorsa occupata"
        elif v > cap:
            scartati[v] = "di notte non oltre V2"
        elif v and info["massimo"]:
            scartati[v] = "una zona ha raggiunto il massimo"
        elif in_permanenza and v != c.vel_reale:
            scartati[v] = "permanenza minima di 15 minuti"
        else:
            # 4. energia applicata a ogni candidato acceso
            ok, perche = energia.giudica(c, v, _w(appresi, v), prev.accumulo)
            giudizi[v] = perche
            if v and richiesta and richiesta.servizio == "accumulo" and not ok:
                scartati[v] = f"energia: {perche}"

    ammessi = [v for v in VELOCITA if v not in scartati]
    if not ammessi:   # nessuna alternativa ammessa: si resta dove si è
        ammessi = [c.vel_reale]

    # 5. punteggio a livelli: domanda non servita, accensione senza domanda, distanza dalla
    # velocità preferita, consumo. Con più domini il primo termine diventa il vettore delle
    # domande non servite ordinate per livello.
    pref = _preferita(c, appresi, cap, richiesta, not in_permanenza)

    def chiave(v):
        return (int(bool(richiesta) and v == 0), int(not richiesta and v > 0),
                abs(v - pref) if v else 0, _w(appresi, v))

    vel = min(ammessi, key=chiave)
    servite = (richiesta.servizio,) if richiesta and vel > 0 else ()
    rinviate = (richiesta.servizio,) if richiesta and vel == 0 else ()
    st = replace(st, accumulo=bool(richiesta and richiesta.servizio == "accumulo" and vel > 0), seq=seq)
    if richiesta and vel:
        motivo = f"{richiesta.motivo}; Toshiba HEAT V{vel}"
    elif richiesta:
        motivo = f"{richiesta.motivo} rinviato: {scartati.get(pref) or 'nessun candidato ammesso'}"
    elif vel:
        motivo = f"Toshiba HEAT V{vel} mantenuto: {scartati.get(0, 'permanenza minima')}"
    else:
        motivo = "zone sopra le soglie: Toshiba spento"
    return Piano(**lease, vel=vel, richiesta=richiesta, servite=servite, rinviate=rinviate,
                 motivo=motivo, scartati=scartati, energia=giudizi, fonte_stato=fonte, stato=st,
                 soglie=info["soglie"])
