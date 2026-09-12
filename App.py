import re
import io
import requests
import streamlit as st
import pandas as pd
import plotly.express as px

# ============================================================
# PAGE CONFIG
# ============================================================
st.set_page_config(page_title="Upstox Portfolio X-Ray", layout="wide")
st.title("📊 Upstox Portfolio X-Ray")
st.caption("Look-through analysis of direct stocks + mutual fund underlying holdings")

# ============================================================
# CONSTANTS / TAXONOMY
# ============================================================
# This is intentionally only a fallback. Provider-supplied sector / user overrides
# should take precedence. Keep this small and auditable rather than pretending to be
# a complete security master.
DEFAULT_SECTOR_MAP = {
    "HDFCBANK": "Financial Services",
    "ICICIBANK": "Financial Services",
    "KOTAKBANK": "Financial Services",
    "AXISBANK": "Financial Services",
    "SBIN": "Financial Services",
    "BANKBARODA": "Financial Services",
    "BAJFINANCE": "Financial Services",
    "BAJAJFINSV": "Financial Services",
    "INDUSINDBK": "Financial Services",
    "INFY": "Information Technology",
    "TCS": "Information Technology",
    "WIPRO": "Information Technology",
    "HCLTECH": "Information Technology",
    "TECHM": "Information Technology",
    "LTIM": "Information Technology",
    "COFORGE": "Information Technology",
    "PERSISTENT": "Information Technology",
    "RELIANCE": "Energy",
    "NTPC": "Power",
    "POWERGRID": "Power",
    "TATAPOWER": "Power",
    "ADANIGREEN": "Power",
    "BPCL": "Energy",
    "IOC": "Energy",
    "ONGC": "Energy",
    "HINDUNILVR": "Consumer Staples",
    "ITC": "Consumer Staples",
    "NESTLEIND": "Consumer Staples",
    "BRITANNIA": "Consumer Staples",
    "TATACONSUM": "Consumer Staples",
    "DABUR": "Consumer Staples",
    "GODREJCP": "Consumer Staples",
    "MARICO": "Consumer Staples",
    "SUNPHARMA": "Healthcare",
    "CIPLA": "Healthcare",
    "DRREDDY": "Healthcare",
    "DIVISLAB": "Healthcare",
    "APOLLOHOSP": "Healthcare",
    "MANKIND": "Healthcare",
    "TATAMOTORS": "Automobile & Auto Components",
    "M&M": "Automobile & Auto Components",
    "MARUTI": "Automobile & Auto Components",
    "BAJAJ-AUTO": "Automobile & Auto Components",
    "HEROMOTOCO": "Automobile & Auto Components",
    "EICHERMOT": "Automobile & Auto Components",
    "TATASTEEL": "Metals & Mining",
    "HINDALCO": "Metals & Mining",
    "COALINDIA": "Metals & Mining",
    "JSWSTEEL": "Metals & Mining",
    "VEDL": "Metals & Mining",
}

SECTOR_NORMALIZATION = {
    "bank": "Financial Services",
    "banks": "Financial Services",
    "banking": "Financial Services",
    "financial services": "Financial Services",
    "finance": "Financial Services",
    "nbfc": "Financial Services",
    "it": "Information Technology",
    "information technology": "Information Technology",
    "it & technology": "Information Technology",
    "technology": "Information Technology",
    "software": "Information Technology",
    "oil & gas": "Energy",
    "petroleum products": "Energy",
    "energy": "Energy",
    "power": "Power",
    "utilities": "Power",
    "renewable energy": "Power",
    "telecommunication": "Telecommunication",
    "telecom": "Telecommunication",
    "healthcare": "Healthcare",
    "pharma": "Healthcare",
    "pharmaceuticals": "Healthcare",
    "fmcg": "Consumer Staples",
    "consumer staples": "Consumer Staples",
    "consumer discretionary": "Consumer Discretionary",
    "automobile": "Automobile & Auto Components",
    "automobiles": "Automobile & Auto Components",
    "auto": "Automobile & Auto Components",
    "metals & mining": "Metals & Mining",
    "metals": "Metals & Mining",
    "construction": "Construction & Infrastructure",
    "infrastructure": "Construction & Infrastructure",
    "realty": "Real Estate",
    "real estate": "Real Estate",
    "hospitality": "Hospitality & Travel",
    "hotels": "Hospitality & Travel",
    "travel": "Hospitality & Travel",
    "chemicals": "Chemicals",
    "capital goods": "Capital Goods",
    "cement": "Construction Materials",
    "construction materials": "Construction Materials",
    "media": "Media & Entertainment",
}

# ============================================================
# HELPERS
# ============================================================
def safe_float(value, default=0.0):
    try:
        if value is None or (isinstance(value, float) and pd.isna(value)):
            return default
        s = str(value).replace(",", "").replace("₹", "").replace("%", "").strip()
        if s == "" or s.lower() in {"nan", "none", "na", "n/a"}:
            return default
        return float(s)
    except (TypeError, ValueError):
        return default


def normalize_name(name: str) -> str:
    """Fallback company-name key when ISIN is unavailable."""
    if not name:
        return ""
    s = str(name).upper().strip()
    s = re.sub(r"\bLIMITED\b|\bLTD\b|\bLTD\.\b|\bPRIVATE\b|\bPVT\b", "", s)
    s = re.sub(r"[^A-Z0-9]", "", s)
    return s


def normalize_sector(raw_sector: str) -> str:
    if not raw_sector:
        return "Unclassified"
    s = str(raw_sector).strip()
    if not s or s.lower() in {"nan", "none", "na", "n/a", "-"}:
        return "Unclassified"
    key = s.lower()
    if key in SECTOR_NORMALIZATION:
        return SECTOR_NORMALIZATION[key]

    # substring fallback for verbose AMC labels
    for needle, canonical in SECTOR_NORMALIZATION.items():
        if needle in key:
            return canonical
    return s


def make_security_key(isin: str, name: str) -> str:
    isin = (isin or "").strip().upper()
    if isin and isin not in {"NAN", "NONE", "NA"}:
        return f"ISIN:{isin}"
    return f"NAME:{normalize_name(name)}"


def first_matching_column(columns, candidates):
    lowered = {str(c).strip().lower(): c for c in columns}

    # exact aliases first
    for cand in candidates:
        if cand in lowered:
            return lowered[cand]

    # then substring matching
    for c in columns:
        lc = str(c).strip().lower()
        for cand in candidates:
            if cand in lc:
                return c
    return None


def read_uploaded_table(file):
    file.seek(0)
    name = file.name.lower()
    if name.endswith(".csv"):
        return pd.read_csv(file)
    return pd.read_excel(file)


# ============================================================
# API FETCHERS
# ============================================================
def fetch_direct_stocks(token):
    url = "https://api.upstox.com/v2/portfolio/long-term-holdings"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers, timeout=20)


def fetch_mf_holdings(token):
    url = "https://api.upstox.com/v2/mf/holdings"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers, timeout=20)


# ============================================================
# SESSION STATE
# ============================================================
if "sector_overrides" not in st.session_state:
    st.session_state.sector_overrides = {}


# ============================================================
# SIDEBAR
# ============================================================
st.sidebar.header("🔑 1. Upstox")
access_token = st.sidebar.text_input("Access token", type="password")

st.sidebar.header("🏷️ 2. Sector override")
st.sidebar.caption("Use an ISIN where possible; symbol also works for direct stocks.")
override_id = st.sidebar.text_input("ISIN or symbol", placeholder="INE040A01034 or HDFCBANK").strip().upper()
override_sector = st.sidebar.text_input("Sector", placeholder="Financial Services").strip()
if st.sidebar.button("Save sector override", use_container_width=True):
    if override_id and override_sector:
        st.session_state.sector_overrides[override_id] = normalize_sector(override_sector)
        st.sidebar.success("Override saved for this session.")
    else:
        st.sidebar.warning("Enter both identifier and sector.")

st.sidebar.header("📁 3. MF look-through data")
st.sidebar.caption(
    "Upload the latest AMC portfolio Excel/CSV for each mutual fund. "
    "You will map each file to exactly one Upstox MF holding."
)
uploaded_files = st.sidebar.file_uploader(
    "AMC portfolio files",
    type=["xlsx", "xls", "csv"],
    accept_multiple_files=True,
)

# ============================================================
# LOAD UPSTOX DATA
# ============================================================
if not access_token:
    st.info("👈 Enter your Upstox access token in the sidebar to load your portfolio.")
    st.stop()

with st.spinner("Fetching holdings from Upstox..."):
    try:
        stock_res = fetch_direct_stocks(access_token)
        mf_res = fetch_mf_holdings(access_token)
    except requests.RequestException as e:
        st.error(f"Could not reach Upstox: {e}")
        st.stop()

if stock_res.status_code != 200:
    st.error(f"Upstox stock holdings request failed ({stock_res.status_code}).")
    st.code(stock_res.text[:1200])

if mf_res.status_code != 200:
    st.error(f"Upstox MF holdings request failed ({mf_res.status_code}).")
    st.code(mf_res.text[:1200])

raw_stocks = stock_res.json().get("data", []) if stock_res.status_code == 200 else []
raw_mfs = mf_res.json().get("data", []) if mf_res.status_code == 200 else []

# ============================================================
# PARSE DIRECT STOCKS
# ============================================================
stocks_list = []
for s in raw_stocks:
    symbol = str(s.get("trading_symbol") or s.get("tradingsymbol") or "").upper().strip()
    isin = str(s.get("isin") or "").upper().strip()
    comp_name = s.get("company_name") or symbol
    qty = safe_float(s.get("quantity"))
    avg_price = safe_float(s.get("average_price"))
    last_price = safe_float(s.get("last_price"))

    invested = qty * avg_price
    current = qty * last_price
    pnl = current - invested
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    # Override priority: ISIN > symbol > fallback map > unclassified
    sector = (
        st.session_state.sector_overrides.get(isin)
        or st.session_state.sector_overrides.get(symbol)
        or DEFAULT_SECTOR_MAP.get(symbol)
        or "Unclassified"
    )

    stocks_list.append({
        "Security Key": make_security_key(isin, comp_name),
        "ISIN": isin,
        "Symbol": symbol,
        "Name": comp_name,
        "Type": "Direct Stock",
        "Sector": normalize_sector(sector),
        "Industry": "",
        "Units/Qty": qty,
        "Avg Price (₹)": avg_price,
        "Current Price (₹)": last_price,
        "Invested Amount (₹)": invested,
        "Current Value (₹)": current,
        "P&L (₹)": pnl,
        "Return (%)": pnl_pct,
    })

df_stocks = pd.DataFrame(stocks_list)

# ============================================================
# PARSE MUTUAL FUNDS
# ============================================================
mf_list = []
for m in raw_mfs:
    scheme_name = (
        m.get("fund")
        or m.get("scheme_name")
        or m.get("fund_name")
        or m.get("trading_symbol")
        or "Mutual Fund"
    )
    mf_isin = str(m.get("instrument_key") or m.get("isin") or "").upper().strip()
    qty = safe_float(m.get("quantity"))
    avg_nav = safe_float(m.get("average_price"))
    last_nav = safe_float(m.get("last_price"))

    invested = qty * avg_nav if avg_nav > 0 else safe_float(m.get("cost_amount"))
    current = qty * last_nav if last_nav > 0 else safe_float(m.get("last_value"))
    pnl = safe_float(m.get("pnl"), current - invested)
    pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0

    mf_list.append({
        "MF ISIN": mf_isin,
        "Name": scheme_name,
        "Units/Qty": qty,
        "Avg NAV (₹)": avg_nav,
        "Current NAV (₹)": last_nav,
        "Invested Amount (₹)": invested,
        "Current Value (₹)": current,
        "P&L (₹)": pnl,
        "Return (%)": pnl_pct,
    })

df_mfs = pd.DataFrame(mf_list)

# ============================================================
# PORTFOLIO OVERVIEW
# ============================================================
st.subheader("📌 Portfolio Overview")
st_inv = df_stocks["Invested Amount (₹)"].sum() if not df_stocks.empty else 0.0
st_cur = df_stocks["Current Value (₹)"].sum() if not df_stocks.empty else 0.0
mf_inv = df_mfs["Invested Amount (₹)"].sum() if not df_mfs.empty else 0.0
mf_cur = df_mfs["Current Value (₹)"].sum() if not df_mfs.empty else 0.0

tot_inv = st_inv + mf_inv
tot_cur = st_cur + mf_cur

c1, c2, c3 = st.columns(3)
with c1:
    st.metric("Direct stocks", f"₹{st_cur:,.0f}", f"₹{st_cur - st_inv:,.0f}")
with c2:
    st.metric("Mutual funds", f"₹{mf_cur:,.0f}", f"₹{mf_cur - mf_inv:,.0f}")
with c3:
    total_ret = ((tot_cur - tot_inv) / tot_inv * 100) if tot_inv > 0 else 0.0
    st.metric("Total portfolio", f"₹{tot_cur:,.0f}", f"{total_ret:.2f}%")

if tot_cur > 0:
    asset_df = pd.DataFrame({
        "Asset Class": ["Direct Stocks", "Mutual Funds"],
        "Current Value (₹)": [st_cur, mf_cur],
    })
    fig_asset = px.pie(asset_df, values="Current Value (₹)", names="Asset Class", hole=0.45)
    st.plotly_chart(fig_asset, use_container_width=True)

# ============================================================
# HOLDINGS TABLES
# ============================================================
with st.expander("📋 Raw holdings from Upstox", expanded=False):
    st.markdown("#### Direct stocks")
    if df_stocks.empty:
        st.info("No direct stocks found.")
    else:
        st.dataframe(
            df_stocks[[
                "Name", "Symbol", "ISIN", "Sector", "Units/Qty", "Avg Price (₹)",
                "Current Price (₹)", "Invested Amount (₹)", "Current Value (₹)",
                "P&L (₹)", "Return (%)"
            ]],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("#### Mutual funds")
    if df_mfs.empty:
        st.info("No mutual funds found.")
    else:
        st.dataframe(df_mfs, use_container_width=True, hide_index=True)

# ============================================================
# MF FILE MAPPING + PARSING
# ============================================================
st.markdown("---")
st.subheader("🔍 Mutual Fund Look-through")

mf_underlying_rows = []
file_diagnostics = []

if uploaded_files and df_mfs.empty:
    st.warning("AMC files were uploaded, but no mutual fund holdings were returned by Upstox.")

if uploaded_files and not df_mfs.empty:
    st.write("Map each uploaded AMC file to the matching mutual fund in your Upstox portfolio.")

    mf_options = {
        f"{row['Name']}  [{row['MF ISIN']}]": idx
        for idx, row in df_mfs.iterrows()
    }

    for file_no, file in enumerate(uploaded_files):
        with st.expander(f"📄 {file.name}", expanded=True):
            selected_label = st.selectbox(
                "This file belongs to:",
                options=["-- Select mutual fund --"] + list(mf_options.keys()),
                key=f"mf_file_map_{file_no}_{file.name}",
            )

            if selected_label == "-- Select mutual fund --":
                st.info("Select a fund to include this file in look-through analysis.")
                continue

            mf_row = df_mfs.loc[mf_options[selected_label]]
            mf_value = safe_float(mf_row["Current Value (₹)"])
            mf_isin = str(mf_row["MF ISIN"])
            mf_name = str(mf_row["Name"])

            try:
                file_df = read_uploaded_table(file)
            except Exception as e:
                st.error(f"Could not read file: {e}")
                continue

            # Preserve originals for display, create normalized header lookup only.
            file_df.columns = [str(c).strip() for c in file_df.columns]

            name_col = first_matching_column(
                file_df.columns,
                ["company", "company name", "stock", "instrument", "security", "name"],
            )
            isin_col = first_matching_column(file_df.columns, ["isin", "security isin"])
            weight_col = first_matching_column(
                file_df.columns,
                ["weight", "holding %", "holding(%)", "allocation", "% to nav", "% of nav", "percentage"],
            )
            sector_col = first_matching_column(
                file_df.columns,
                ["sector", "sector / rating", "sector/rating"],
            )
            industry_col = first_matching_column(
                file_df.columns,
                ["industry", "industry / rating", "industry/rating"],
            )

            detected = pd.DataFrame({
                "Field": ["Security name", "ISIN", "Weight %", "Sector", "Industry"],
                "Detected column": [name_col, isin_col, weight_col, sector_col, industry_col],
            })
            st.dataframe(detected, use_container_width=True, hide_index=True)

            if not name_col or not weight_col:
                st.error("Could not detect both a security-name column and a holding-weight column.")
                continue

            parsed_count = 0
            weight_sum = 0.0

            for _, row in file_df.iterrows():
                security_name = str(row.get(name_col, "")).strip()
                if not security_name or security_name.lower() in {"nan", "none", "total"}:
                    continue

                weight_pct = safe_float(row.get(weight_col), None)
                if weight_pct is None or weight_pct <= 0:
                    continue

                # Handle decimal weights such as 0.0545 when clearly represented as fractions.
                # We do NOT auto-convert all values <1 because a valid holding can be 0.50%.
                # The user can override below if the file uses fractions.
                security_isin = str(row.get(isin_col, "") if isin_col else "").strip().upper()
                raw_sector = str(row.get(sector_col, "") if sector_col else "").strip()
                raw_industry = str(row.get(industry_col, "") if industry_col else "").strip()

                sector = normalize_sector(raw_sector)

                # Sector override priority for MF constituents: ISIN > normalized name
                override = (
                    st.session_state.sector_overrides.get(security_isin)
                    or st.session_state.sector_overrides.get(normalize_name(security_name))
                )
                if override:
                    sector = normalize_sector(override)

                indirect_value = mf_value * (weight_pct / 100.0)
                mf_underlying_rows.append({
                    "MF ISIN": mf_isin,
                    "Mutual Fund": mf_name,
                    "Security Key": make_security_key(security_isin, security_name),
                    "ISIN": security_isin,
                    "Security": security_name,
                    "Sector": sector,
                    "Industry": raw_industry,
                    "Weight %": weight_pct,
                    "MF Current Value (₹)": mf_value,
                    "Indirect MF Exposure (₹)": indirect_value,
                    "Source File": file.name,
                })
                parsed_count += 1
                weight_sum += weight_pct

            file_diagnostics.append({
                "File": file.name,
                "Mapped MF": mf_name,
                "MF ISIN": mf_isin,
                "Rows parsed": parsed_count,
                "Weight total %": weight_sum,
            })

            if parsed_count:
                if weight_sum > 115:
                    st.warning(
                        f"Parsed weights sum to {weight_sum:.2f}%. The file may contain multiple sections "
                        "or duplicated holdings; exclude non-portfolio rows before relying on results."
                    )
                else:
                    st.success(f"Parsed {parsed_count} holdings; weights total {weight_sum:.2f}%.")

if file_diagnostics:
    st.markdown("#### File diagnostics")
    st.dataframe(pd.DataFrame(file_diagnostics), use_container_width=True, hide_index=True)

# ============================================================
# CONSOLIDATED SECURITY EXPOSURE
# ============================================================
st.markdown("---")
st.subheader("🎯 True Security Exposure — Direct + Mutual Funds")

exposure_rows = []

# Direct stock exposures
if not df_stocks.empty:
    for _, s in df_stocks.iterrows():
        exposure_rows.append({
            "Security Key": s["Security Key"],
            "ISIN": s["ISIN"],
            "Security": s["Name"],
            "Sector": s["Sector"],
            "Industry": s["Industry"],
            "Direct Exposure (₹)": safe_float(s["Current Value (₹)"]),
            "Indirect MF Exposure (₹)": 0.0,
        })

# MF underlying exposures
for r in mf_underlying_rows:
    exposure_rows.append({
        "Security Key": r["Security Key"],
        "ISIN": r["ISIN"],
        "Security": r["Security"],
        "Sector": r["Sector"],
        "Industry": r["Industry"],
        "Direct Exposure (₹)": 0.0,
        "Indirect MF Exposure (₹)": safe_float(r["Indirect MF Exposure (₹)"]),
    })

if exposure_rows:
    df_exp = pd.DataFrame(exposure_rows)

    # Prefer a classified / non-empty label when duplicate rows disagree.
    def best_label(series, default=""):
        vals = [str(v).strip() for v in series if str(v).strip() not in {"", "nan", "None", "Unclassified"}]
        return vals[0] if vals else default

    grouped = []
    for sec_key, g in df_exp.groupby("Security Key", dropna=False):
        isin_vals = [x for x in g["ISIN"].astype(str) if x and x not in {"nan", "None"}]
        grouped.append({
            "Security Key": sec_key,
            "ISIN": isin_vals[0] if isin_vals else "",
            "Security": best_label(g["Security"], "Unknown Security"),
            "Sector": normalize_sector(best_label(g["Sector"], "Unclassified")),
            "Industry": best_label(g["Industry"], ""),
            "Direct Exposure (₹)": g["Direct Exposure (₹)"].sum(),
            "Indirect MF Exposure (₹)": g["Indirect MF Exposure (₹)"].sum(),
        })

    df_agg = pd.DataFrame(grouped)
    df_agg["Total Exposure (₹)"] = df_agg["Direct Exposure (₹)"] + df_agg["Indirect MF Exposure (₹)"]
    df_agg["Portfolio %"] = (df_agg["Total Exposure (₹)"] / tot_cur * 100) if tot_cur > 0 else 0.0
    df_agg = df_agg.sort_values("Total Exposure (₹)", ascending=False)

    st.dataframe(
        df_agg[[
            "Security", "ISIN", "Sector", "Industry", "Direct Exposure (₹)",
            "Indirect MF Exposure (₹)", "Total Exposure (₹)", "Portfolio %"
        ]],
        use_container_width=True,
        hide_index=True,
    )

    top_n = st.slider("Top securities to chart", min_value=5, max_value=min(30, max(5, len(df_agg))), value=min(15, max(5, len(df_agg))))
    chart_df = df_agg.head(top_n)
    fig_true = px.bar(
        chart_df,
        x="Security",
        y=["Direct Exposure (₹)", "Indirect MF Exposure (₹)"],
        barmode="stack",
        title=f"Top {top_n} Security Exposures",
    )
    st.plotly_chart(fig_true, use_container_width=True)

    # ========================================================
    # SECTOR LOOK-THROUGH
    # ========================================================
    st.subheader("🏭 Sector Exposure — Look-through")
    df_sector = (
        df_agg.groupby("Sector", dropna=False)["Total Exposure (₹)"]
        .sum()
        .reset_index()
        .sort_values("Total Exposure (₹)", ascending=False)
    )
    df_sector["Portfolio %"] = (df_sector["Total Exposure (₹)"] / tot_cur * 100) if tot_cur > 0 else 0.0

    col1, col2 = st.columns([1.2, 1])
    with col1:
        st.dataframe(df_sector, use_container_width=True, hide_index=True)
    with col2:
        fig_sector = px.pie(df_sector, values="Total Exposure (₹)", names="Sector", hole=0.42)
        st.plotly_chart(fig_sector, use_container_width=True)

    # ========================================================
    # DATA QUALITY
    # ========================================================
    st.subheader("🧪 Data Quality")
    classified_value = df_agg.loc[df_agg["Sector"] != "Unclassified", "Total Exposure (₹)"].sum()
    analyzed_security_value = df_agg["Total Exposure (₹)"].sum()
    sector_coverage = (classified_value / analyzed_security_value * 100) if analyzed_security_value > 0 else 0.0

    mf_lookthrough_value = sum(safe_float(r["Indirect MF Exposure (₹)"]) for r in mf_underlying_rows)
    mf_coverage = (mf_lookthrough_value / mf_cur * 100) if mf_cur > 0 else 0.0

    q1, q2, q3 = st.columns(3)
    q1.metric("MF look-through coverage", f"{mf_coverage:.1f}%")
    q2.metric("Sector classification coverage", f"{sector_coverage:.1f}%")
    q3.metric("Unclassified securities", int((df_agg["Sector"] == "Unclassified").sum()))

    if mf_cur > 0 and mf_coverage < 90:
        st.warning(
            "MF look-through coverage is below 90%. This can be normal if AMC files omit cash/debt/derivatives, "
            "but it can also mean a fund file is missing or mapped incorrectly."
        )

    unclassified = df_agg[df_agg["Sector"] == "Unclassified"]
    if not unclassified.empty:
        st.markdown("#### Securities needing sector mapping")
        st.dataframe(
            unclassified[["Security", "ISIN", "Total Exposure (₹)"]],
            use_container_width=True,
            hide_index=True,
        )
        st.caption("Use the sidebar sector override with the ISIN whenever possible.")

    # Export normalized exposure table
    csv_bytes = df_agg.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Download normalized exposure CSV",
        data=csv_bytes,
        file_name="portfolio_true_exposure.csv",
        mime="text/csv",
    )
else:
    st.info(
        "Direct holdings are empty and/or no MF portfolio files have been mapped yet. "
        "Upload AMC portfolio files and map each one to its matching Upstox mutual fund."
    )

# ============================================================
# NOTES
# ============================================================
with st.expander("ℹ️ How this version calculates exposure", expanded=False):
    st.markdown(
        """
        **Direct stock exposure** = current stock quantity × current Upstox price.

        **MF stock exposure** = current MF value × latest disclosed holding weight.

        Securities are joined using **ISIN first**. If a source file does not contain ISIN,
        the app falls back to a normalized company name. ISIN-based matching is materially safer.

        Mutual fund disclosures are periodic, so look-through exposure is an estimate based on the
        latest uploaded portfolio disclosure rather than a real-time constituent portfolio.
        """
    )