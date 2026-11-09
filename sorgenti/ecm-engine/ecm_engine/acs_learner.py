"""Resa netta osservata del bollitore basso, indipendente dalle fasce esterne."""
import json
import math
from statistics import median

from .segmenter import slope_per_hour

# Una prova ACSe concordata dura 20 campioni: al massimo i primi 5 sono di avvio,
# i successivi 15 costituiscono una finestra completa. Un tratto più corto resta
# comunque visibile come stima provvisoria, invece di sparire dalla dashboard.
SETTLING_SAMPLES = 5
FULL_SAMPLES = 15
PARTIAL_MIN_SAMPLES = 5

# Il recorder di HA non salva attributi oltre 16384 byte (compresi nome e icona):
# oltre questa soglia si tengono le righe con più osservazioni e si contano le omesse.
ATTR_MAX_BYTES = 15000


def _speed(code):
    if not isinstance(code, int):
        return None
    return {4: 2, 5: 3, 6: 4, 8: 1}.get(code % 10)


def _split(code):
    d = code // 10
    if d == 0:
        return 'SPLIT OFF'
    return f"SPLIT {('DRY', 'COOL', 'HEAT')[(d-1)//3]} V{(d-1)%3+1}"


class AcsLearner:
    """Riceve i campioni uno alla volta, così condivide la lettura del database
    con la segmentazione del clima."""

    def __init__(self):
        self.groups = {}
        self.window = []
        self.previous = None
        self.settling = 0
        self.rejected = 0
        self.finished = False

    def _emit(self, rows, provisional):
        speed = rows[0]['_acs_speed']
        band = int(rows[0]['t12'] // 5) * 5
        self.groups.setdefault((speed, band), []).append(dict(
            rate=slope_per_hour([r['ts'] for r in rows], [r['t12'] for r in rows]),
            minutes=len(rows),
            cp=sum(r['p_cp'] for r in rows) / len(rows),
            split=sum(r['p_tosh'] for r in rows) / len(rows),
            top=sum(r['t11'] for r in rows) / len(rows),
            test=any(r.get('test_id') is not None or r.get('acs_heat_test') == 1
                     for r in rows),
            provisional=provisional,
            split_context=tuple(sorted({_split(r['code']) for r in rows}))))

    def _finish_partial(self):
        if len(self.window) >= PARTIAL_MIN_SAMPLES:
            self._emit(self.window, provisional=True)
        elif self.window:
            self.rejected += 1
        self.window = []

    def feed(self, row):
        if self.finished:
            raise RuntimeError('AcsLearner già finalizzato')
        code = row.get('code')
        speed = _speed(code)
        valid = (row.get('acs_source_ok') == 1 and row.get('valido') == 1
                 and row.get('stagione') == 'INVERNO' and speed is not None
                 and not row.get('motivo') and row.get('cp_compressore') == 1)
        for key in ('t11', 't12', 'p_cp', 'p_tosh'):
            value = row.get(key)
            valid = valid and isinstance(value, (int, float)) and math.isfinite(value)
        if valid:
            valid = (0 < row['t12'] < 60 and 0 < row['t11'] < 60
                     and row['p_cp'] >= 0 and row['p_tosh'] >= 0)

        previous = self.previous
        continuous = (valid and previous is not None
                      and previous['_acs_speed'] == speed
                      and 30 <= row['ts'] - previous['ts'] <= 90)
        disturbance = continuous and any(
            row[k] - previous[k] < -0.3 or abs(row[k] - previous[k]) > 2
            for k in ('t11', 't12'))

        if not continuous or disturbance:
            if disturbance:
                self.rejected += bool(self.window)
                self.window = []
            else:
                self._finish_partial()
            self.settling = 0

        if not valid:
            self.previous = None
            return

        current = dict(row, _acs_speed=speed)
        self.previous = current
        if self.settling < SETTLING_SAMPLES:
            self.settling += 1
            return

        self.window.append(current)
        if len(self.window) == FULL_SAMPLES:
            self._emit(self.window, provisional=False)
            self.window = []

    def result(self):
        if not self.finished:
            self._finish_partial()
            self.finished = True
        return _result(self.groups, self.rejected)


def learn_acs(samples):
    learner = AcsLearner()
    for row in samples:
        learner.feed(row)
    return learner.result()


def _result(groups, rejected):
    table = []
    for (speed, band), episodes in sorted(groups.items()):
        complete = [e for e in episodes if not e['provisional']]
        basis = complete or episodes
        contexts = sorted({c for e in episodes for c in e['split_context']})
        table.append(dict(
            codice=f'ACSe V{speed}', combinazione=f'CP HEAT V{speed}',
            fascia_bollitore_basso=f'{band}–{band+5} °C',
            resa_bollitore_basso_c_h=round(median(e['rate'] for e in basis), 2),
            finestre=len(complete), osservazioni=len(episodes),
            tratti_provvisori=len(episodes) - len(complete),
            provvisoria=not complete,
            minuti=round(sum(e['minutes'] for e in episodes)),
            finestre_prova=sum(e['test'] for e in complete),
            finestre_normali=sum(not e['test'] for e in complete),
            tratti_prova=sum(e['test'] for e in episodes),
            potenza_cp_w=round(median(e['cp'] for e in basis), 1),
            potenza_split_w=round(median(e['split'] for e in basis), 1),
            split_contesto=' / '.join(contexts),
            bollitore_alto_medio=round(median(e['top'] for e in basis), 1),
            dispersione_c_h=round(max(e['rate'] for e in basis)-min(e['rate'] for e in basis), 2),
            supporto=('provvisorio' if not complete else
                      'iniziale' if len(complete) < 5 else 'ripetuto')))
    out = {
        'tabella': table, 'righe_omesse': 0, 'finestre_interrotte': rejected,
        'nota': ('Resa netta osservata della CP, indipendente dallo SPLIT; non COP. '
                 'Le stime provvisorie usano tratti più corti di 15 campioni.'),
        'assestamento_campioni': SETTLING_SAMPLES,
        'finestra_campioni': FULL_SAMPLES,
        'minimo_provvisorio_campioni': PARTIAL_MIN_SAMPLES,
    }
    return _fit(out)


def _size(obj):
    return len(json.dumps(obj, ensure_ascii=False).encode())


def _fit(out):
    """Tabella entro ATTR_MAX_BYTES: priorità alle righe con più osservazioni e minuti,
    poi di nuovo in ordine di velocità e fascia."""
    if _size(out) <= ATTR_MAX_BYTES:
        return out
    table = out['tabella']
    budget = ATTR_MAX_BYTES - _size(dict(out, tabella=[], righe_omesse=len(table)))
    order = sorted(range(len(table)),
                   key=lambda i: (-table[i]['osservazioni'], -table[i]['minuti'], i))
    keep, used = set(), 0
    for i in order:
        cost = _size(table[i]) + 2
        if used + cost > budget:
            break
        keep.add(i)
        used += cost
    kept = [r for i, r in enumerate(table) if i in keep]
    return dict(out, tabella=kept, righe_omesse=len(table) - len(kept))
