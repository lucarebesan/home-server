"""Domanda dell'ambiente invernale: soglie per fascia e zona, latch di recupero, accumulo."""
from dataclasses import replace

from .parametri import (LIVELLO_ACCUMULO, LIVELLO_RECUPERO, MARGINE_AVVIO_ACCUMULO, MARGINE_RECUPERO,
                        MASSIMO_DEFAULT, OFFSET)
from .tipi import Contesto, Richiesta, Stato

ZONE = ("zg", "zn")
NOME = {"zg": "zona giorno", "zn": "zona notte"}


def soglie(t_min: float, notte: bool) -> dict:
    """{zona: (avvio sotto, recupero fino a)}"""
    out = {}
    for z in ZONE:
        avvio = round(t_min + OFFSET[(notte, z)], 2)
        out[z] = (avvio, round(avvio + MARGINE_RECUPERO, 2))
    return out


def domanda(c: Contesto, prev: Stato, accumulo_possibile: bool = False):
    """Restituisce (stato con latch aggiornati, richiesta o None, info)."""
    s = soglie(c.t_min, c.notte)
    t = {"zg": c.t_zg, "zn": c.t_zn}
    massimo = c.massimo if c.massimo is not None else MASSIMO_DEFAULT
    latch = {"zg": prev.rec_zg, "zn": prev.rec_zn}
    for z in ZONE:
        avvio, fine = s[z]
        if t[z] < avvio:
            latch[z] = True
        elif t[z] >= fine:
            latch[z] = False
    al_massimo = any(t[z] >= massimo for z in ZONE)
    info = {"soglie": s, "massimo": al_massimo, "valore_massimo": massimo,
            "sotto": {z: t[z] < s[z][0] for z in ZONE}}
    st = replace(prev, rec_zg=latch["zg"], rec_zn=latch["zn"])
    in_rec = tuple(z for z in ZONE if latch[z])
    if in_rec:
        motivo = ", ".join(f"{NOME[z]} {t[z]:.2f} °C sotto {s[z][1]} °C" for z in in_rec)
        return st, Richiesta("recupero", LIVELLO_RECUPERO, in_rec, f"recupero: {motivo}"), info
    sotto_avvio = all(t[z] < massimo - MARGINE_AVVIO_ACCUMULO for z in ZONE)
    if accumulo_possibile and not al_massimo and (prev.accumulo or sotto_avvio):
        return st, Richiesta("accumulo", LIVELLO_ACCUMULO, ZONE, f"accumulo fino a {massimo} °C"), info
    return st, None, info
