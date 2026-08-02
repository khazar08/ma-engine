"""Streamlit front end for the M&A engine — run it without touching the terminal.

Launch:  streamlit run app.py     (or double-click run_app.command on macOS)

Pick an acquirer, set the premium and consideration mix with sliders, click
"Run analysis", and browse the ranked shortlist and one-page teasers in the
browser. Wraps the same pipeline the CLI uses — no separate logic.
"""
from __future__ import annotations

import os

import pandas as pd
import streamlit as st

from ma_engine.config import DEFAULT_CONFIG
from ma_engine.data import fundamentals
from ma_engine.embeddings import get_embedder
from ma_engine.pipeline import run_engine, summary_frame
from ma_engine.validation import backtest_screener

st.set_page_config(page_title="M&A Origination Engine", page_icon="📈", layout="wide")


@st.cache_data(show_spinner=False)
def load_universe():
    return fundamentals.build_from_seed()


@st.cache_resource(show_spinner=False)
def load_embedder():
    return get_embedder()


universe = load_universe()
tickers = sorted(c.ticker for c in universe)
names = {c.ticker: c.name for c in universe}

# ----------------------------- Sidebar controls -----------------------------
st.sidebar.title("Deal parameters")
acquirer = st.sidebar.selectbox(
    "Acquirer", tickers, index=tickers.index("CRM") if "CRM" in tickers else 0,
    format_func=lambda t: f"{t} — {names.get(t, '')}")
top_n = st.sidebar.slider("Shortlist size", 1, 10, 5)
premium = st.sidebar.slider("Offer premium", 0.0, 1.0, 0.30, 0.05,
                            help="How far above the current share price you bid.")

st.sidebar.markdown("**Consideration mix**")
cash_pct = st.sidebar.slider("Cash %", 0.0, 1.0, 0.50, 0.05)
new_debt_pct = st.sidebar.slider("New debt %", 0.0, 1.0 - cash_pct, 0.0, 0.05)
stock_pct = round(1.0 - cash_pct - new_debt_pct, 4)
st.sidebar.caption(f"Stock %: **{stock_pct:.0%}**  (cash + debt + stock = 100%)")

run = st.sidebar.button("Run analysis", type="primary", use_container_width=True)

# ------------------------------- Main panel ---------------------------------
st.title("📈 Automated M&A Origination & Deal Analysis")
st.caption("Pick an acquirer → ranked target shortlist → full first-pass deal analysis "
           "and a one-page teaser per target. Enterprise-software universe (seed data).")

if not run:
    st.info("Set the parameters in the sidebar and click **Run analysis**.")
    with st.expander("How the screener validates — hit-rate@K"):
        result = backtest_screener(universe, cfg=DEFAULT_CONFIG)
        st.write(result.summary_line())
        st.dataframe(pd.DataFrame(
            [{"acquirer": a, "actual target": t, "engine rank": (r if r else "unranked")}
             for a, t, r in result.ranks]), use_container_width=True, hide_index=True)
    st.stop()

cfg = DEFAULT_CONFIG.with_updates(default_premium=premium, cash_pct=cash_pct,
                                  stock_pct=stock_pct, new_debt_pct=new_debt_pct,
                                  top_n=top_n, out_dir="out")

with st.spinner(f"Screening {acquirer} and analyzing top {top_n} targets…"):
    shortlist, analyses = run_engine(
        acquirer, universe, cfg=cfg, top_n=top_n, premium=premium,
        cash_pct=cash_pct, stock_pct=stock_pct, new_debt_pct=new_debt_pct,
        make_teasers=True, embedder=load_embedder())
    summary = summary_frame(shortlist, analyses)

st.subheader(f"Shortlist for {acquirer} — {names.get(acquirer, '')}")
st.caption(f"{premium:.0%} premium · {cash_pct:.0%} cash / {stock_pct:.0%} stock / "
           f"{new_debt_pct:.0%} new debt")

# headline metrics for the #1 target
top = analyses[0]
c1, c2, c3 = st.columns(3)
c1.metric("Top target", f"{top.target}", names.get(top.target, ""))
c2.metric("Year-1 EPS impact", f"{top.accretion.accretion_dilution_pct:+.1%}",
          "accretive" if top.accretion.is_accretive else "dilutive",
          delta_color="normal" if top.accretion.is_accretive else "inverse")
c3.metric("Offer / share", f"${top.structure.offer_price_per_share:,.2f}")

show = summary.rename(columns={
    "ticker": "Target", "name": "Name", "total_score": "Score",
    "offer_per_share": "Offer $/sh", "premium": "Premium",
    "equity_purchase_$m": "Equity $m", "yr1_accretion": "Yr-1 EPS Δ",
    "breakeven_premium": "Breakeven prem."})
st.dataframe(
    show.style.format({"Score": "{:.3f}", "Offer $/sh": "${:,.2f}", "Premium": "{:.0%}",
                       "Equity $m": "${:,.0f}m", "Yr-1 EPS Δ": "{:+.1%}",
                       "Breakeven prem.": lambda v: f"{v:.0%}" if pd.notna(v) else "—"}),
    use_container_width=True, hide_index=True)
st.download_button("⬇ Download shortlist CSV", summary.to_csv(index=False),
                   file_name=f"shortlist_{acquirer}.csv", mime="text/csv")

st.divider()
st.subheader("One-page teasers")
for a in analyses:
    with st.expander(f"{acquirer} → {a.target} ({names.get(a.target,'')}) · "
                     f"Year-1 EPS {a.accretion.accretion_dilution_pct:+.1%}",
                     expanded=(a is analyses[0])):
        png = os.path.join(cfg.out_dir, f"teaser_{acquirer}_{a.target}.png")
        pdf = os.path.join(cfg.out_dir, f"teaser_{acquirer}_{a.target}.pdf")
        if os.path.exists(png):
            st.image(png, use_container_width=True)
        if os.path.exists(pdf):
            with open(pdf, "rb") as f:
                st.download_button("⬇ Download this teaser (PDF)", f.read(),
                                   file_name=os.path.basename(pdf), mime="application/pdf",
                                   key=f"dl_{a.target}")
