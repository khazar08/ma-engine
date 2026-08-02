# Automated M&A Origination & Deal Analysis Engine

Given a **public acquirer**, this engine produces:

1. A **ranked shortlist of acquisition targets** (strategic + financial fit).
2. For each target, a **full first-pass deal analysis** — standalone valuation
   (trading comps, precedent transactions, DCF), synergy estimate, financing
   structure, and pro forma **accretion/dilution**.
3. A **one-page deal teaser PDF** per target.

It automates the "idea generation → preliminary analysis" pipeline that junior
M&A bankers spend most of their time on. Scope is disciplined to **one sector**
(enterprise software) end-to-end before broadening.

---

## Quickstart

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Web app (no terminal needed after launch) — dropdowns + sliders in the browser
streamlit run app.py            # or double-click run_app.command on macOS

# Run the whole pipeline for an acquirer (CLI)
python -m ma_engine.main --acquirer CRM --top 5 --premium 0.30 --cash 0.5 --stock 0.5

# Backtest the screener (hit-rate@K) + precedent-multiple calibration
python -m ma_engine.validation

# Tests (every finance module is covered)
python -m pytest ma_engine/tests -q
```

Outputs land in `out/`: one `teaser_<ACQ>_<TGT>.pdf` (+ `.png`) per target and a
`shortlist_<ACQ>.csv` summary index.

```
python -m ma_engine.main --acquirer CRM
CLI: --acquirer TICKER  --top N  --premium 0.30  --cash 0.5 --stock 0.5 --new-debt 0.0
     --source {parquet,seed,edgar}  --no-teasers  --out DIR
```

---

## Deploy (Streamlit Community Cloud)

The web app is deploy-ready as-is (offline seed data, headless matplotlib, light
deps). To publish a shareable link:

1. Push this repo to GitHub (public or private).
2. Go to **share.streamlit.io** → sign in with GitHub → **Create app**.
3. Pick this repo, branch `main`, main file **`app.py`**.
4. (Advanced settings) set Python version to **3.11** or **3.12**.
5. **Deploy** — you get a public URL like `https://<name>.streamlit.app`.

The deployed demo runs entirely on the seed universe + TF-IDF embeddings, so it
needs no API keys and no network access at runtime.

> Note: this is a Streamlit (long-running server) app — it runs on Streamlit
> Cloud / Render / Railway / Hugging Face Spaces, **not** on serverless hosts like
> Vercel or Netlify.

## Data: runs offline by default

The universe is ~22 enterprise-software names (ticker + CIK in
[`ma_engine/data/universe.py`](ma_engine/data/universe.py)). Two build paths:

- **Seed (default, deterministic, offline):** curated approximate recent-FY
  fundamentals in [`seed_fundamentals.py`](ma_engine/data/seed_fundamentals.py).
  The whole pipeline and test suite run with **no network access**.
- **Live EDGAR:** `--source edgar` pulls XBRL company-facts from
  `data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`, maps standard US-GAAP tags,
  and layers `yfinance` market data behind the `MarketDataProvider` interface.
  A SEC-required `User-Agent` is set from config; responses are cached to disk.

> The seed figures are **approximate** and exist so the engine is demo-able and
> testable without hammering APIs. Refresh with `--source edgar` for real filings.

---

## How each number is computed

### Valuation ([`valuation/`](ma_engine/valuation/))
- **Trading comps** — peers auto-selected by business-description embedding
  similarity (same sector, size band), then **median** peer EV/Revenue, EV/EBITDA,
  P/E applied to the target. *Standalone* value.
- **Precedent transactions** — median EV/Revenue & EV/EBITDA from a curated deal
  table ([`data/precedents.csv`](data/precedents.csv)). These embed a **control
  premium** (flagged), so they sit above trading comps.
- **DCF** — unlevered FCF, exactly:
  `UFCF_t = EBIT_t·(1−tax) + D&A_t − CapEx_t − ΔNWC_t`, 5-yr projection with
  growth fading to terminal, CAPM cost of equity, WACC-weighted, and **both**
  terminal-value methods (Gordon growth *and* exit multiple) reported. Guards
  against `g ≥ WACC`.
- **Football field** assembles the low/high ranges per method for charting.

### Screening ([`screening/`](ma_engine/screening/))
- **Strategic fit** = `w1·adjacency + w2·segment_fit + w3·digestibility`
  - *adjacency*: embedding cosine similarity (surfaces non-obvious adjacencies).
  - *segment_fit*: blend of Jaccard overlap and complementarity (config knob).
  - *digestibility*: smooth Gaussian bump peaking when target EV is 5–40% of
    acquirer market cap.
- **Financial fit** = margin-accretion potential + fundability, where fundability
  scores pro forma net leverage under a 100%-debt-financed purchase against a
  configurable ceiling (4.0×) — ties screening to whether the acquirer can pay.
- **Rank** = `alpha·strategic + (1−alpha)·financial`, with every sub-score exposed
  so the teaser can explain *why* a target ranked where it did.

### The core — accretion/dilution ([`deal/accretion_dilution.py`](ma_engine/deal/accretion_dilution.py))
Pro forma EPS bridge, implemented exactly:

```
pro_forma_NI    = acquirer_NI + target_NI + after_tax_synergies
                  − after_tax_new_interest − after_tax_foregone_interest
pro_forma_shares= acquirer_shares + new_shares_issued
accretion_%     = pro_forma_EPS / standalone_EPS − 1     # + accretive, − dilutive
```

Plus **breakeven premium** (solved numerically, structure held fixed) and
**after-tax synergies required for EPS-neutral** (closed form). Sources = uses is
asserted. `sensitivity.py` builds the premium × synergy-realization grid.

Sign conventions are pinned by hand-computed textbook tests
([`tests/test_accretion.py`](ma_engine/tests/test_accretion.py)):
all-stock deals are dilutive when the acquirer's P/E is below the P/E paid, cash
deals accretive when the after-tax cost of cash is below the target's earnings
yield, etc.

---

## Validation (Phase 7)

`python -m ma_engine.validation` reports **hit-rate@K** — for each held-out
(acquirer, target) pair, whether the actual target lands in the engine's top-K
shortlist — plus precedent-multiple calibration.

**On the seed universe the screen surfaces the intended target in its top-5 ~47%,
top-10 ~87%, and top-20 100% of held-out pairs.**

> **Honest caveat.** The shipped holdout
> ([`data/holdout_deals.csv`](data/holdout_deals.csv)) is a set of
> strategically-motivated pairs among *current* universe members, screened on
> *current* fundamentals — this is **not** a leak-free point-in-time backtest,
> because historical targets are delisted after close and absent from a current
> universe. The harness is generic: supply a point-in-time universe + a real
> announced-deal holdout (a stretch goal) and the same hit-rate@K numbers become
> fully out-of-sample.

---

## Layout

```
ma_engine/
├── config.py                 # every assumption, typed (pydantic)
├── models/                   # Company, Valuation, DealStructure, AccretionResult, ...
├── embeddings.py             # Embedder interface (TF-IDF default, sentence-transformers optional)
├── data/                     # EDGAR ingest, market data, universe, seed fundamentals
├── screening/                # strategic_fit, financial_fit, rank
├── valuation/                # comps, precedents, dcf, football_field
├── deal/                     # synergies, structure, accretion_dilution, sensitivity
├── report/                   # charts (football field + diverging heatmap), teaser PDF
├── pipeline.py               # acquirer -> shortlist -> analyses -> teasers
├── main.py                   # CLI
├── validation.py             # hit-rate@K backtest + multiple calibration
└── tests/                    # pytest — one module per finance area (33 tests)
```

## Design notes & limitations

- **Deterministic offline default.** TF-IDF embeddings and seed fundamentals keep
  every run and test reproducible without network access; swap in
  `sentence-transformers` (`get_embedder(prefer_semantic=True)`) and `--source
  edgar` for production-grade adjacency and live filings.
- **Software EV/EBITDA is noisy** (many targets run near-zero or negative EBITDA),
  so EV/Revenue carries the precedent and comps ranges for those names — visible
  in the football field and called out in the calibration output.
- Teasers are composed with matplotlib (self-contained PDF, no native toolchain).
- Preliminary, first-pass analysis — **not investment advice.**

## Stretch goals (post-v1)

LBO feasibility screen · point-in-time fundamentals for a leak-free backtest ·
Streamlit front end · fitted premium-vs-size / premium-vs-sector regressions.
