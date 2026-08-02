"""Strategic-fit scoring: adjacency, segment fit, size digestibility.

Each candidate is scored 0-1 on three components, combined with config weights:

    strategic_score = w1*adjacency + w2*segment_fit + w3*digestibility

- adjacency:      cosine similarity of business-description embeddings. Surfaces
                  non-obvious adjacencies a keyword screen would miss.
- segment_fit:    a blend of pure overlap (shared segments) and complementarity
                  (segments the target adds that the acquirer lacks). The blend is
                  a config knob.
- digestibility:  a smooth bump peaking when target EV sits in a "digestible" band
                  as a fraction of acquirer market cap.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional

import numpy as np

from ..config import Config, DEFAULT_CONFIG
from ..embeddings import Embedder, cosine_similarity, get_embedder
from ..models import Company


@dataclass
class StrategicScore:
    ticker: str
    adjacency: float
    segment_fit: float
    digestibility: float
    strategic_score: float
    overlap: float          # raw overlap component (used by synergies)
    complementarity: float


def segment_fit_score(acquirer: Company, target: Company, cfg: Config = DEFAULT_CONFIG) -> tuple[float, float, float]:
    """Return (segment_fit, overlap, complementarity), each in [0, 1].

    overlap        = |A ∩ T| / |A ∪ T|      (Jaccard)
    complementarity= |T \\ A| / |T|          (share of target segments new to acquirer)
    segment_fit    = (1-c_w)*overlap + c_w*complementarity
    """
    a, t = acquirer.segment_names, target.segment_names
    if not a and not t:
        return 0.0, 0.0, 0.0
    union = a | t
    inter = a & t
    overlap = len(inter) / len(union) if union else 0.0
    complementarity = (len(t - a) / len(t)) if t else 0.0
    c_w = cfg.screening_weights.complementarity_weight
    fit = (1 - c_w) * overlap + c_w * complementarity
    return fit, overlap, complementarity


def digestibility_score(acquirer: Company, target: Company, cfg: Config = DEFAULT_CONFIG) -> float:
    """Smooth bump function of (target EV / acquirer market cap).

    Peaks (score 1.0) inside the digestible band [low, high]; decays smoothly
    with a Gaussian shoulder outside the band so nothing is a hard cutoff.
    """
    w = cfg.screening_weights
    acq_size = acquirer.market_cap
    if acq_size <= 0:
        return 0.0
    ratio = target.enterprise_value / acq_size
    lo, hi = w.digestible_low, w.digestible_high
    if lo <= ratio <= hi:
        return 1.0
    # Gaussian shoulders; sigma scaled to band width so the decay is gentle.
    sigma = max((hi - lo), 0.05)
    if ratio < lo:
        d = (lo - ratio) / sigma
    else:
        d = (ratio - hi) / sigma
    return float(math.exp(-0.5 * d * d))


def score_candidates(acquirer: Company, candidates: list[Company],
                     cfg: Config = DEFAULT_CONFIG,
                     embedder: Optional[Embedder] = None) -> list[StrategicScore]:
    embedder = embedder or get_embedder()
    # Embed acquirer + all candidates together so the vector space is shared.
    texts = [acquirer.business_description] + [c.business_description for c in candidates]
    vecs = embedder.embed(texts)
    acq_vec = vecs[0]

    w = cfg.screening_weights
    scores = []
    for i, c in enumerate(candidates):
        adjacency = max(0.0, cosine_similarity(acq_vec, vecs[i + 1]))
        seg_fit, overlap, comp = segment_fit_score(acquirer, c, cfg)
        digest = digestibility_score(acquirer, c, cfg)
        strategic = w.adjacency * adjacency + w.segment_fit * seg_fit + w.digestibility * digest
        scores.append(StrategicScore(
            ticker=c.ticker, adjacency=adjacency, segment_fit=seg_fit,
            digestibility=digest, strategic_score=strategic,
            overlap=overlap, complementarity=comp,
        ))
    return scores
