"""
Robotics Universe Stock Screener & Risk Analysis Tool
Run: streamlit run app.py
Deps: pip install streamlit yfinance pandas numpy
"""

import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import date, timedelta

# ---------------------------------------------------------------------------
# Universe Definition
# ---------------------------------------------------------------------------

UNIVERSE = [
    {"name": "Nvidia",             "ticker": "NVDA",      "isin": "US67066G1040", "hq": "USA",         "moat": "Monopoly in AI training compute and CUDA software."},
    {"name": "ASML Holding",       "ticker": "ASML.AS",   "isin": "NL0010273215", "hq": "EU",          "moat": "Absolute monopoly in EUV lithography."},
    {"name": "Fanuc",              "ticker": "6954.T",    "isin": "JP3802400006", "hq": "Japan",       "moat": "World leader in CNC systems and industrial robots."},
    {"name": "Intuitive Surgical", "ticker": "ISRG",      "isin": "US46120E6023", "hq": "USA",         "moat": "Dominant pioneer in robotic-assisted surgery."},
    {"name": "Keyence",            "ticker": "6861.T",    "isin": "JP3236200006", "hq": "Japan",       "moat": "Fabless manufacturer of machine vision and sensors."},
    {"name": "Siemens AG",         "ticker": "SIE.DE",    "isin": "DE0007236101", "hq": "EU",          "moat": "Deeply entrenched industrial automation software ecosystem."},
    {"name": "Teradyne",           "ticker": "TER",       "isin": "US8807701029", "hq": "USA",         "moat": "Market leader in the collaborative robot (cobot) segment."},
    {"name": "Estun Automation",   "ticker": "002747.SZ", "isin": "CNE100001XK1", "hq": "China",       "moat": "State-backed domestic champion in AC servo systems."},
    {"name": "Doosan Robotics",    "ticker": "454910.KS", "isin": "KR7454910006", "hq": "South Korea", "moat": "Top-tier cobot manufacturer integrated into Korean heavy industry."},
    {"name": "Symbotic",           "ticker": "SYM",       "isin": "US87151X1019", "hq": "USA",         "moat": "Proprietary AI-driven autonomous warehouse robotics."},
    {"name": "ATS Corporation",    "ticker": "ATS.TO",    "isin": "CA04684Y1051", "hq": "Canada",      "moat": "Automation solutions for highly regulated life sciences."},
    {"name": "Yaskawa Electric",   "ticker": "6506.T",    "isin": "JP3932000007", "hq": "Japan",       "moat": "Global leader in servo motors and AC drives."},
]

PORTFOLIO_SIZE_EUR = 1_000_000  # EUR per position for VaR calculation

# ---------------------------------------------------------------------------
# FX Rates (cached 1h) — pull live EUR cross-rates from yfinance
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_fx_rates() -> dict:
    """
    Returns a dict mapping ISO currency code -> EUR conversion rate.
    Rate means: 1 unit of that currency = rate EUR.
    EUR itself is 1.0 by definition.
    """
    pairs = {
        "USD": "EURUSD=X",   # USD per EUR -> invert
        "JPY": "EURJPY=X",   # JPY per EUR -> invert
        "CNY": "EURCNY=X",
        "KRW": "EURKRW=X",
        "CAD": "EURCAD=X",
        "HKD": "EURHKD=X",
    }
    rates = {"EUR": 1.0}
    for currency, pair in pairs.items():
        try:
            ticker = yf.Ticker(pair)
            hist = ticker.history(period="1d")
            if not hist.empty:
                eur_per_foreign = 1.0 / hist["Close"].iloc[-1]
                rates[currency] = eur_per_foreign
            else:
                rates[currency] = None
        except Exception:
            rates[currency] = None
    return rates


def currency_for_ticker(ticker: str) -> str:
    """Infer reporting currency from ticker suffix convention."""
    if ticker.endswith(".T"):
        return "JPY"
    if ticker.endswith(".AS") or ticker.endswith(".DE"):
        return "EUR"
    if ticker.endswith(".SZ") or ticker.endswith(".SS"):
        return "CNY"
    if ticker.endswith(".KS"):
        return "KRW"
    if ticker.endswith(".TO"):
        return "CAD"
    if ticker.endswith(".HK"):
        return "HKD"
    return "USD"


def to_eur(value, currency: str, fx: dict) -> float | None:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return None
    rate = fx.get(currency)
    if rate is None:
        return None
    return value * rate


def fmt_eur(value_eur: float | None) -> str:
    """Format a EUR value as 'X M EUR' or 'X B EUR'."""
    if value_eur is None:
        return "N/A"
    abs_val = abs(value_eur)
    sign = "-" if value_eur < 0 else ""
    if abs_val >= 1e9:
        return f"{sign}{abs_val / 1e9:.2f} B EUR"
    if abs_val >= 1e6:
        return f"{sign}{abs_val / 1e6:.1f} M EUR"
    return f"{sign}{abs_val:,.0f} EUR"


def fmt_var(value_eur: float | None) -> str:
    """Format VaR as 'X,XXX EUR' (positive loss figure)."""
    if value_eur is None:
        return "N/A"
    return f"{abs(value_eur):,.0f} EUR"


# ---------------------------------------------------------------------------
# Fundamental Data (cached 1h)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_fundamentals(ticker: str) -> dict:
    """Fetch key fundamental metrics for one ticker via yfinance."""
    try:
        t = yf.Ticker(ticker)
        info = t.info

        price        = info.get("currentPrice") or info.get("regularMarketPrice")
        high_52w     = info.get("fiftyTwoWeekHigh")
        low_52w      = info.get("fiftyTwoWeekLow")
        pe_ratio     = info.get("trailingPE")
        beta         = info.get("beta")
        revenue      = info.get("totalRevenue")
        earnings     = info.get("netIncomeToCommon")

        return {
            "price":    price,
            "high_52w": high_52w,
            "low_52w":  low_52w,
            "pe":       pe_ratio,
            "beta":     beta,
            "revenue":  revenue,
            "earnings": earnings,
        }
    except Exception:
        return {k: None for k in ["price", "high_52w", "low_52w", "pe", "beta", "revenue", "earnings"]}


# ---------------------------------------------------------------------------
# Historical Price Data & VaR (cached 1h)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600)
def fetch_prices(ticker: str) -> pd.Series | None:
    """Fetch 3 years of adjusted daily closing prices."""
    end   = date.today()
    start = end - timedelta(days=3 * 365 + 10)  # slight buffer for calendar gaps
    try:
        hist = yf.download(ticker, start=start, end=end, auto_adjust=True, progress=False)
        if hist.empty:
            return None
        close = hist["Close"]
        # yfinance may return a DataFrame with MultiIndex columns for single ticker
        if isinstance(close, pd.DataFrame):
            close = close.iloc[:, 0]
        return close.dropna()
    except Exception:
        return None


def compute_var(prices: pd.Series | None) -> dict:
    """
    Pure historical simulation VaR — no parametric assumptions, no scaling.

    10-day 95% VaR:
        Compute every overlapping 10-trading-day cumulative return from the
        3-year price series. Take the 5th percentile of that distribution.
        Loss = |5th pct| * 1M EUR.

    250-day 99% VaR:
        Same approach over 250-trading-day windows (approx. 1 calendar year).
        Take the 1st percentile. Loss = |1st pct| * 1M EUR.

    Both figures represent the maximum expected loss at the stated confidence
    level over the stated horizon, derived entirely from observed price history.
    """
    result = {"var_10d_95": None, "var_250d_99": None}
    if prices is None or len(prices) < 260:
        return result

    # Compute overlapping n-day simple returns: (P_t / P_{t-n}) - 1
    def rolling_returns(n: int) -> np.ndarray:
        p = prices.values
        return (p[n:] / p[:-n]) - 1

    rets_10d  = rolling_returns(10)
    rets_250d = rolling_returns(250)

    p5 = np.percentile(rets_10d,  5)
    p1 = np.percentile(rets_250d, 1)

    result["var_10d_95"]  = abs(p5) * PORTFOLIO_SIZE_EUR
    result["var_250d_99"] = abs(p1) * PORTFOLIO_SIZE_EUR

    return result


# ---------------------------------------------------------------------------
# Build Master DataFrame
# ---------------------------------------------------------------------------

def build_dataframe(fx: dict) -> pd.DataFrame:
    rows = []
    progress = st.progress(0, text="Loading universe data...")

    for i, stock in enumerate(UNIVERSE):
        ticker   = stock["ticker"]
        currency = currency_for_ticker(ticker)

        fund  = fetch_fundamentals(ticker)
        prices = fetch_prices(ticker)
        var   = compute_var(prices)

        # Convert monetary fields to EUR
        price_eur    = to_eur(fund["price"],    currency, fx)
        high_eur     = to_eur(fund["high_52w"], currency, fx)
        low_eur      = to_eur(fund["low_52w"],  currency, fx)
        revenue_eur  = to_eur(fund["revenue"],  currency, fx)
        earnings_eur = to_eur(fund["earnings"], currency, fx)

        # 52w position: how far current price sits in the 52w range (0-100%)
        if price_eur and high_eur and low_eur and (high_eur - low_eur) > 0:
            pct_of_range = (price_eur - low_eur) / (high_eur - low_eur) * 100
        else:
            pct_of_range = None

        rows.append({
            "Company":             stock["name"],
            "Ticker":              ticker,
            "ISIN":                stock["isin"],
            "HQ":                  stock["hq"],
            "Price (EUR)":         f"{price_eur:,.2f}" if price_eur else "N/A",
            "52W High (EUR)":      f"{high_eur:,.2f}"  if high_eur  else "N/A",
            "52W Low (EUR)":       f"{low_eur:,.2f}"   if low_eur   else "N/A",
            "52W Position %":      round(pct_of_range, 1) if pct_of_range is not None else None,
            "P/E Ratio":           round(fund["pe"], 1)   if fund["pe"]   else "N/A",
            "Beta":                round(fund["beta"], 2) if fund["beta"] else "N/A",
            "Revenue (EUR)":       fmt_eur(revenue_eur),
            "Net Income (EUR)":    fmt_eur(earnings_eur),
            "VaR 10d 95% (EUR)":   fmt_var(var["var_10d_95"]),
            "VaR 250d 99% (EUR)":  fmt_var(var["var_250d_99"]),
            "Moat":                stock["moat"],
        })

        progress.progress((i + 1) / len(UNIVERSE), text=f"Loaded {stock['name']}...")

    progress.empty()
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Streamlit App Layout
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Robotics Universe Screener",
    page_icon="🤖",
    layout="wide",
)

st.title("🤖 Robotics Universe — Stock Screener & Risk Dashboard")
st.caption(
    "Data sourced via yfinance (1h cache). "
    "VaR computed via pure historical simulation on 3Y overlapping multi-day return windows. "
    f"Portfolio assumption: {PORTFOLIO_SIZE_EUR:,} EUR per position."
)

# --- Sidebar ---
st.sidebar.header("Filters")
st.sidebar.markdown("---")

all_regions = sorted({s["hq"] for s in UNIVERSE})
selected_regions = st.sidebar.multiselect(
    "Geography (HQ)",
    options=all_regions,
    default=all_regions,
    help="Filter stocks by headquarters region.",
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    "**Risk Model — Pure Historical Simulation**\n\n"
    "VaR 10d 95%: 5th percentile of all observed overlapping 10-day returns (3Y window) × 1M EUR\n\n"
    "VaR 250d 99%: 1st percentile of all observed overlapping 250-day returns (3Y window) × 1M EUR\n\n"
    "No parametric scaling. No sqrt-of-time. Raw historical loss distributions only."
)

# --- Load data ---
with st.spinner("Fetching FX rates..."):
    fx_rates = fetch_fx_rates()

df = build_dataframe(fx_rates)

# --- Apply filters ---
filtered_df = df[df["HQ"].isin(selected_regions)].reset_index(drop=True)

# --- KPI Summary Row ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Stocks Displayed",    len(filtered_df))
col2.metric("Geographies",         filtered_df["HQ"].nunique())
col3.metric("Portfolio Size (EUR)", f"{PORTFOLIO_SIZE_EUR * len(filtered_df):,}")
col4.metric("Data Freshness",       "Live (1h cache)")

st.markdown("---")

# --- Main Dataframe ---
st.subheader("Universe Overview")

st.dataframe(
    filtered_df,
    use_container_width=True,
    hide_index=True,
    column_config={
        "Company":            st.column_config.TextColumn("Company",           width="medium"),
        "Ticker":             st.column_config.TextColumn("Ticker",            width="small"),
        "ISIN":               st.column_config.TextColumn("ISIN",              width="medium"),
        "HQ":                 st.column_config.TextColumn("HQ",                width="small"),
        "Price (EUR)":        st.column_config.TextColumn("Price (EUR)",        width="small"),
        "52W High (EUR)":     st.column_config.TextColumn("52W High (EUR)",     width="small"),
        "52W Low (EUR)":      st.column_config.TextColumn("52W Low (EUR)",      width="small"),
        "52W Position %":     st.column_config.ProgressColumn(
                                  "52W Range Position",
                                  help="Where current price sits in 52W High/Low range.",
                                  min_value=0, max_value=100, format="%.1f%%",
                                  width="medium",
                              ),
        "P/E Ratio":          st.column_config.TextColumn("P/E",               width="small"),
        "Beta":               st.column_config.TextColumn("Beta",              width="small"),
        "Revenue (EUR)":      st.column_config.TextColumn("Revenue",           width="small"),
        "Net Income (EUR)":   st.column_config.TextColumn("Net Income",        width="small"),
        "VaR 10d 95% (EUR)":  st.column_config.TextColumn("VaR 10d 95%",       width="small"),
        "VaR 250d 99% (EUR)": st.column_config.TextColumn("VaR 250d 99%",      width="small"),
        "Moat":               st.column_config.TextColumn("Competitive Moat",  width="large"),
    },
    height=500,
)

# --- VaR Detail Table ---
st.markdown("---")
st.subheader("Risk Module — Value at Risk Detail")
st.caption("Positive figures represent maximum expected loss (EUR) at given confidence level and horizon.")

var_cols = ["Company", "HQ", "Beta", "VaR 10d 95% (EUR)", "VaR 250d 99% (EUR)"]
st.dataframe(
    filtered_df[var_cols],
    use_container_width=True,
    hide_index=True,
    height=420,
)

st.markdown("---")
st.caption(
    "Disclaimer: This tool is for analytical purposes only and does not constitute investment advice. "
    "VaR is a statistical measure and does not capture tail risk beyond the stated confidence interval."
)
