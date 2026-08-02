"""Curated seed fundamentals for the enterprise-software universe.

These are *approximate* recent-fiscal-year figures (millions USD; shares in
millions; price in USD) used so the full pipeline runs offline and
deterministically. They are NOT a substitute for a live EDGAR pull — run
``ingest_edgar`` to refresh with point-in-time SEC data. Fields:

  revenue, ebit, da, net_income, total_debt, cash, capex, interest_expense,
  tax_rate, share_price, shares_diluted, beta

EBITDA is derived as ebit + da downstream.
"""
from __future__ import annotations

# ticker -> dict of fields
SEED: dict[str, dict] = {
    "CRM":  dict(revenue=37900, ebit=7200, da=1800, net_income=6200, total_debt=8400, cash=14000, capex=660, interest_expense=280, tax_rate=0.20, share_price=265, shares_diluted=970, beta=1.30),
    "NOW":  dict(revenue=10980, ebit=1360, da=430, net_income=1430, total_debt=1490, cash=5470, capex=250, interest_expense=30, tax_rate=0.19, share_price=880, shares_diluted=206, beta=1.05),
    "WDAY": dict(revenue=8450, ebit=415, da=230, net_income=1390, total_debt=2980, cash=7000, capex=280, interest_expense=60, tax_rate=0.18, share_price=230, shares_diluted=267, beta=1.15),
    "ADBE": dict(revenue=21500, ebit=6740, da=1000, net_income=5560, total_debt=5600, cash=7900, capex=360, interest_expense=170, tax_rate=0.20, share_price=500, shares_diluted=445, beta=1.30),
    "INTU": dict(revenue=16290, ebit=3630, da=640, net_income=2960, total_debt=6100, cash=3600, capex=250, interest_expense=190, tax_rate=0.22, share_price=640, shares_diluted=280, beta=1.20),
    "SNOW": dict(revenue=3630, ebit=-1380, da=250, net_income=-1290, total_debt=0, cash=5000, capex=40, interest_expense=0, tax_rate=0.21, share_price=180, shares_diluted=333, beta=1.10),
    "DDOG": dict(revenue=2680, ebit=55, da=90, net_income=185, total_debt=750, cash=3000, capex=40, interest_expense=10, tax_rate=0.15, share_price=120, shares_diluted=345, beta=1.20),
    "TEAM": dict(revenue=4360, ebit=-120, da=180, net_income=-120, total_debt=1000, cash=2200, capex=40, interest_expense=20, tax_rate=0.21, share_price=200, shares_diluted=260, beta=1.25),
    "ZS":   dict(revenue=2170, ebit=-60, da=90, net_income=-58, total_debt=1140, cash=2400, capex=90, interest_expense=15, tax_rate=0.21, share_price=190, shares_diluted=150, beta=1.05),
    "CRWD": dict(revenue=3060, ebit=-1, da=180, net_income=90, total_debt=740, cash=3700, capex=130, interest_expense=10, tax_rate=0.15, share_price=380, shares_diluted=245, beta=1.10),
    "PANW": dict(revenue=8030, ebit=680, da=250, net_income=2580, total_debt=0, cash=2600, capex=130, interest_expense=30, tax_rate=0.20, share_price=330, shares_diluted=330, beta=1.15),
    "HUBS": dict(revenue=2560, ebit=-30, da=130, net_income=120, total_debt=460, cash=1700, capex=60, interest_expense=10, tax_rate=0.15, share_price=530, shares_diluted=51, beta=1.35),
    "DOCU": dict(revenue=2760, ebit=90, da=90, net_income=890, total_debt=0, cash=1000, capex=30, interest_expense=5, tax_rate=0.10, share_price=85, shares_diluted=205, beta=1.00),
    "MDB":  dict(revenue=2000, ebit=-170, da=40, net_income=-180, total_debt=1140, cash=2300, capex=15, interest_expense=10, tax_rate=0.21, share_price=250, shares_diluted=74, beta=1.10),
    "NET":  dict(revenue=1670, ebit=-160, da=120, net_income=-160, total_debt=1290, cash=1700, capex=130, interest_expense=15, tax_rate=0.21, share_price=90, shares_diluted=340, beta=1.20),
    "OKTA": dict(revenue=2450, ebit=-340, da=180, net_income=-360, total_debt=810, cash=2300, capex=15, interest_expense=10, tax_rate=0.21, share_price=90, shares_diluted=170, beta=1.05),
    "TWLO": dict(revenue=4460, ebit=-880, da=360, net_income=-880, total_debt=990, cash=2700, capex=40, interest_expense=20, tax_rate=0.21, share_price=65, shares_diluted=185, beta=1.25),
    "ZM":   dict(revenue=4610, ebit=660, da=90, net_income=640, total_debt=0, cash=7000, capex=90, interest_expense=0, tax_rate=0.22, share_price=70, shares_diluted=305, beta=1.00),
    "BILL": dict(revenue=1290, ebit=-190, da=90, net_income=30, total_debt=1730, cash=2500, capex=20, interest_expense=20, tax_rate=0.15, share_price=55, shares_diluted=104, beta=1.30),
    "PATH": dict(revenue=1310, ebit=-160, da=30, net_income=-90, total_debt=0, cash=1800, capex=10, interest_expense=0, tax_rate=0.21, share_price=13, shares_diluted=570, beta=1.10),
    "GTLB": dict(revenue=760, ebit=-140, da=20, net_income=-100, total_debt=0, cash=1000, capex=5, interest_expense=0, tax_rate=0.21, share_price=50, shares_diluted=160, beta=1.20),
    "FROG": dict(revenue=430, ebit=-40, da=20, net_income=-30, total_debt=0, cash=1300, capex=10, interest_expense=0, tax_rate=0.21, share_price=30, shares_diluted=110, beta=1.15),
}
