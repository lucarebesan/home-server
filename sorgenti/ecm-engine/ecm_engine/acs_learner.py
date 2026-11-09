"""Resa netta osservata del bollitore basso, indipendente dalle fasce esterne."""
import math
from statistics import median

from .segmenter import slope_per_hour


def learn_acs(samples):
    groups = {}
    window = []
    previous = None
    stable_since = None
    rejected = 0
    for row in samples:
        code = row.get('code')
        valid = (row.get('acs_source_ok') == 1 and row.get('valido') == 1
                 and row.get('stagione') == 'INVERNO' and isinstance(code, int)
                 and code % 10 in (4, 5, 6, 8) and not row.get('motivo')
                 and row.get('cp_compressore') == 1)
        for key in ('t11', 't12', 'p_cp', 'p_tosh'):
            value = row.get(key)
            valid = valid and isinstance(value, (int, float)) and math.isfinite(value)
        if valid:
            valid = (0 < row['t12'] < 60 and 0 < row['t11'] < 60
                     and row['p_cp'] >= 0 and row['p_tosh'] >= 0)
        continuous = (valid and previous is not None and previous.get('code') == code
                      and 30 <= row['ts'] - previous['ts'] <= 90)
        # Un calo rapido segnala possibile prelievo o miscelazione; scarta anche
        # la finestra in corso e attende un nuovo assestamento di otto minuti.
        disturbance = continuous and any(
            row[k] - previous[k] < -0.3 or abs(row[k] - previous[k]) > 2
            for k in ('t11', 't12'))
        if not continuous or disturbance:
            rejected += bool(window)
            window = []
            stable_since = row['ts'] if valid else None
        previous = row if valid else None
        if not valid or row['ts'] - stable_since < 480:
            continue
        window.append(row)
        if row['ts'] - window[0]['ts'] < 600:
            continue
        minutes = (row['ts'] - window[0]['ts']) / 60
        rate = slope_per_hour([r['ts'] for r in window], [r['t12'] for r in window])
        # Non eliminare pendenze nulle/negative: sarebbe una selezione ottimistica.
        band = int(window[0]['t12'] // 5) * 5
        key = (code, band)
        groups.setdefault(key, []).append(dict(
            rate=rate, minutes=minutes,
            cp=sum(r['p_cp'] for r in window) / len(window),
            split=sum(r['p_tosh'] for r in window) / len(window),
            top=sum(r['t11'] for r in window) / len(window),
            test=any(r.get('test_id') is not None or r.get('acs_heat_test') == 1 for r in window)))
        window = []
    table = []
    for (code, band), episodes in sorted(groups.items()):
        u, d = code % 10, code // 10
        speed = {4: 2, 5: 3, 6: 4, 8: 1}[u]
        split = 'SPLIT OFF' if d == 0 else f"SPLIT {('DRY', 'COOL', 'HEAT')[(d-1)//3]} V{(d-1)%3+1}"
        table.append(dict(
            codice=f'E{code}', combinazione=f'CP HEAT V{speed} + {split}',
            fascia_bollitore_basso=f'{band}–{band+5} °C',
            resa_bollitore_basso_c_h=round(median(e['rate'] for e in episodes), 2),
            finestre=len(episodes), minuti=round(sum(e['minutes'] for e in episodes)),
            finestre_prova=sum(e['test'] for e in episodes),
            finestre_normali=sum(not e['test'] for e in episodes),
            potenza_cp_w=round(median(e['cp'] for e in episodes), 1),
            potenza_split_w=round(median(e['split'] for e in episodes), 1),
            bollitore_alto_medio=round(median(e['top'] for e in episodes), 1),
            dispersione_c_h=round(max(e['rate'] for e in episodes)-min(e['rate'] for e in episodes), 2),
            supporto='iniziale' if len(episodes) < 5 else 'ripetuto'))
    return {'tabella': table, 'finestre_interrotte': rejected,
            'nota': 'Resa netta osservata, non COP né effetto causale dello SPLIT. Prelievi piccoli non sempre rilevabili.',
            'assestamento_min': 8, 'finestra_min': 10}
