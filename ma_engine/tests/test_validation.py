"""Phase 7 tests: backtest harness mechanics + calibration coverage."""
import pandas as pd

from ma_engine.config import DEFAULT_CONFIG
from ma_engine.data import fundamentals
from ma_engine import validation


def test_backtest_computes_hit_rate():
    universe = fundamentals.build_from_seed()
    result = validation.backtest_screener(universe, cfg=DEFAULT_CONFIG, ks=(5, 10, 20))
    assert result.n_deals > 0
    for k in (5, 10, 20):
        assert 0.0 <= result.hit_rate[k] <= 1.0
    # monotonic: hit-rate can only grow with K
    assert result.hit_rate[5] <= result.hit_rate[10] <= result.hit_rate[20]
    # every pair yields a rank slot (int or None)
    for acq, tgt, rank in result.ranks:
        assert rank is None or rank >= 1


def test_backtest_perfect_when_target_is_top_ranked():
    # synthetic universe where the acquirer's obvious twin should rank #1
    universe = fundamentals.build_from_seed()
    holdout = pd.DataFrame({"acquirer_ticker": ["PANW"], "target_ticker": ["ZS"]})
    result = validation.backtest_screener(universe, holdout=holdout, cfg=DEFAULT_CONFIG, ks=(20,))
    # a security-platform pair should certainly be within top-20 of a 22-name universe
    assert result.hit_rate[20] == 1.0


def test_precedent_multiple_calibration_has_coverage():
    calib = validation.calibrate_precedent_multiples(DEFAULT_CONFIG)
    assert calib.engine_median_ev_ebitda is not None
    assert calib.engine_median_ev_revenue is not None
    assert len(calib.deal_ev_revenue) >= 10
