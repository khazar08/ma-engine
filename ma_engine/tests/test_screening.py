"""Phase 2 tests: deterministic scoring, digestibility bump peak, ranking."""
import pytest

from ma_engine.config import DEFAULT_CONFIG
from ma_engine.data import fundamentals
from ma_engine.models import Company, Segment
from ma_engine.screening import financial_fit, rank, strategic_fit


def _co(ticker, ev_via_price, mc_shares=100.0, ebitda_margin=0.3, segments=None, desc=""):
    # build a company whose market cap == price*shares and EV includes given price
    return Company(ticker=ticker, business_description=desc,
                   segments=[Segment(name=s) for s in (segments or [])],
                   revenue=1000.0, ebitda=1000.0 * ebitda_margin, ebit=1000.0 * ebitda_margin,
                   net_income=100.0, share_price=ev_via_price, shares_diluted=mc_shares,
                   total_debt=0.0, cash_and_equivalents=0.0)


def test_digestibility_peaks_in_band():
    cfg = DEFAULT_CONFIG  # band 5%-40% of acquirer market cap
    acquirer = _co("ACQ", ev_via_price=100.0, mc_shares=1000.0)  # market cap 100,000
    # target EV = 20% of acquirer -> inside band -> score 1.0
    inside = _co("IN", ev_via_price=200.0, mc_shares=100.0)      # EV 20,000 = 20%
    # target EV = 200% -> way above band
    huge = _co("BIG", ev_via_price=2000.0, mc_shares=100.0)      # EV 200,000 = 200%
    # target EV = 0.5% -> below band
    tiny = _co("SM", ev_via_price=5.0, mc_shares=100.0)          # EV 500 = 0.5%

    s_in = strategic_fit.digestibility_score(acquirer, inside, cfg)
    s_big = strategic_fit.digestibility_score(acquirer, huge, cfg)
    s_tiny = strategic_fit.digestibility_score(acquirer, tiny, cfg)
    assert s_in == pytest.approx(1.0)
    assert s_big < s_in
    assert s_tiny < s_in
    assert 0.0 <= s_big <= 1.0 and 0.0 <= s_tiny <= 1.0


def test_segment_fit_overlap_vs_complementarity():
    cfg = DEFAULT_CONFIG
    acq = _co("A", 100.0, segments=["crm", "marketing"])
    # pure overlap
    overlap_target = _co("O", 50.0, segments=["crm", "marketing"])
    # pure complement
    comp_target = _co("C", 50.0, segments=["security", "identity"])
    f_over, ov, _ = strategic_fit.segment_fit_score(acq, overlap_target, cfg)
    f_comp, _, comp = strategic_fit.segment_fit_score(acq, comp_target, cfg)
    assert ov == pytest.approx(1.0)          # identical segment sets
    assert comp == pytest.approx(1.0)        # all target segments new
    # both should be positive; the config weighting blends them
    assert f_over > 0 and f_comp > 0


def test_margin_accretion_direction():
    acq = _co("A", 100.0, ebitda_margin=0.20)
    higher = _co("H", 50.0, ebitda_margin=0.40)
    lower = _co("L", 50.0, ebitda_margin=0.05)
    assert financial_fit.margin_accretion_score(acq, higher) > 0.5
    assert financial_fit.margin_accretion_score(acq, lower) < 0.5


def test_fundability_penalizes_high_leverage():
    cfg = DEFAULT_CONFIG
    # small acquirer, huge target -> high pro forma leverage -> low fundability
    small_acq = _co("A", ev_via_price=10.0, mc_shares=100.0, ebitda_margin=0.2)  # mc 1000
    big_tgt = _co("B", ev_via_price=100.0, mc_shares=100.0, ebitda_margin=0.2)   # mc 10000
    score, lev = financial_fit.fundability_score(small_acq, big_tgt, cfg)
    assert lev > cfg.leverage_ceiling
    assert score < 0.5


def test_ranking_deterministic_and_sorted():
    companies = fundamentals.build_from_seed()
    acq = fundamentals.get_company(companies, "CRM")
    df1 = rank.rank_targets(acq, companies, DEFAULT_CONFIG)
    df2 = rank.rank_targets(acq, companies, DEFAULT_CONFIG)
    # deterministic
    assert list(df1["ticker"]) == list(df2["ticker"])
    # sorted descending by total_score
    scores = list(df1["total_score"])
    assert scores == sorted(scores, reverse=True)
    # acquirer excluded
    assert "CRM" not in list(df1["ticker"])
    # rationale generation works on the top row
    bullets = rank.rationale_bullets(df1.iloc[0])
    assert isinstance(bullets, list) and len(bullets) >= 1
