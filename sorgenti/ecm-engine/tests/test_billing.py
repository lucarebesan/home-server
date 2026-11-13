import json
from datetime import date
from pathlib import Path

import pytest

from ecm_engine.billing import CURRENT, RENEWAL_PROPOSAL, D, estimate, month_equivalents, reconcile_invoice


def test_five_invoices_reconcile():
    rows = json.loads((Path(__file__).parents[1] / "billing_invoices.json").read_text())
    assert [str(reconcile_invoice(row)) for row in rows] == [
        "449.37", "177.65", "110.82", "113.87", "119.05"
    ]


def test_renewal_only_increases_variable_supply():
    old = estimate(CURRENT, date(2026, 10, 1), date(2026, 11, 30), D(574), D(1279))
    new = estimate(RENEWAL_PROPOSAL, date(2026, 12, 1), date(2027, 1, 31), D(574), D(1279))
    assert D(99) < new["total"] - old["total"] < D(103)
    assert old["fixed"] == new["fixed"]
    assert old["power"] == new["power"]


def test_accrual_and_expiry():
    assert month_equivalents(date(2026, 10, 1), date(2026, 11, 13)) == D(1) + D(13) / D(30)
    with pytest.raises(ValueError, match="validità"):
        estimate(CURRENT, date(2026, 11, 1), date(2026, 12, 1), D(10), D(10))
