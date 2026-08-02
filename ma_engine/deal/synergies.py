"""Synergy estimation.

Cost synergies are estimated as a % of the *target's* operating costs, where the
% scales with the strategic overlap score from screening (higher overlap ->
more extractable cost). This ties synergies back to the strategic-fit score.

    target_operating_costs = target_revenue - target_ebit
    cost_synergy_pct       = lerp(low, high, overlap_score)
    cost_synergies_pretax  = cost_synergy_pct * target_operating_costs

Revenue synergies are optional, smaller and flagged lower-confidence.

Reported after-tax:
    synergies_after_tax = synergies_pretax * (1 - tax_rate)

A phase-in schedule (e.g. 50% Y1, 100% Y2) scales the run-rate over time.
"""
from __future__ import annotations

from ..config import Config, DEFAULT_CONFIG
from ..models import Company, SynergyEstimate


def estimate_synergies(acquirer: Company, target: Company,
                       overlap_score: float = 0.5,
                       cfg: Config = DEFAULT_CONFIG) -> SynergyEstimate:
    """Estimate annual run-rate synergies.

    ``overlap_score`` in [0, 1] scales the cost-synergy % between the configured
    low/high bounds. Tax rate is the acquirer's (synergies accrue to the combined
    entity, taxed at the acquirer's rate).
    """
    overlap_score = max(0.0, min(1.0, overlap_score))
    pct = cfg.cost_synergy_pct_low + overlap_score * (cfg.cost_synergy_pct_high - cfg.cost_synergy_pct_low)

    target_operating_costs = max(target.revenue - target.ebit, 0.0)
    cost_pretax = pct * target_operating_costs
    revenue_pretax = cfg.revenue_synergy_pct * target.revenue

    total_pretax = cost_pretax + revenue_pretax
    after_tax = total_pretax * (1 - acquirer.tax_rate)

    return SynergyEstimate(
        cost_synergies_pretax=cost_pretax,
        revenue_synergies_pretax=revenue_pretax,
        total_pretax=total_pretax,
        after_tax_run_rate=after_tax,
        phase_in=list(cfg.synergy_phase_in),
        cost_synergy_pct_used=pct,
    )


def phased_after_tax(estimate: SynergyEstimate, year: int) -> float:
    """After-tax synergies realized in a given (1-indexed) year per the phase-in."""
    if year < 1:
        return 0.0
    idx = min(year, len(estimate.phase_in)) - 1
    return estimate.after_tax_run_rate * estimate.phase_in[idx]
