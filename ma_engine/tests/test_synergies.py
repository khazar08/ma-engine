"""Phase 4 tests: synergy scaling with overlap, after-tax, phase-in."""
import pytest

from ma_engine.config import DEFAULT_CONFIG
from ma_engine.deal import synergies as syn
from ma_engine.models import Company


def _co(ticker, revenue, ebit, tax=0.21):
    return Company(ticker=ticker, revenue=revenue, ebit=ebit, ebitda=ebit,
                   net_income=ebit * 0.7, tax_rate=tax, share_price=10.0, shares_diluted=100.0)


def test_cost_synergy_scales_with_overlap():
    acq = _co("A", 1000.0, 200.0)
    tgt = _co("T", 500.0, 100.0)   # operating costs = 500 - 100 = 400
    low = syn.estimate_synergies(acq, tgt, overlap_score=0.0)
    high = syn.estimate_synergies(acq, tgt, overlap_score=1.0)
    assert low.cost_synergy_pct_used == pytest.approx(DEFAULT_CONFIG.cost_synergy_pct_low)
    assert high.cost_synergy_pct_used == pytest.approx(DEFAULT_CONFIG.cost_synergy_pct_high)
    assert high.cost_synergies_pretax > low.cost_synergies_pretax
    # 15% of 400 opex at full overlap
    assert high.cost_synergies_pretax == pytest.approx(0.15 * 400.0)


def test_after_tax_uses_acquirer_tax_rate():
    acq = _co("A", 1000.0, 200.0, tax=0.25)
    tgt = _co("T", 500.0, 100.0)
    est = syn.estimate_synergies(acq, tgt, overlap_score=0.5)
    assert est.after_tax_run_rate == pytest.approx(est.total_pretax * (1 - 0.25))


def test_phase_in_schedule():
    acq = _co("A", 1000.0, 200.0)
    tgt = _co("T", 500.0, 100.0)
    est = syn.estimate_synergies(acq, tgt, overlap_score=0.5)  # phase_in default [0.5, 1.0]
    y1 = syn.phased_after_tax(est, 1)
    y2 = syn.phased_after_tax(est, 2)
    y3 = syn.phased_after_tax(est, 3)
    assert y1 == pytest.approx(est.after_tax_run_rate * 0.5)
    assert y2 == pytest.approx(est.after_tax_run_rate * 1.0)
    assert y3 == pytest.approx(est.after_tax_run_rate * 1.0)  # holds at last schedule value
    assert syn.phased_after_tax(est, 0) == 0.0
