import streamlit as st
import pandas as pd
import plotly.express as px
import requests

st.set_page_config(page_title="Upstox Portfolio Analyzer", layout="wide")
st.title("📊 Consolidated Equity & Mutual Fund Portfolio Analyzer")

# --- SIDEBAR: AUTH & CONTROLS ---
st.sidebar.header("🔑 1. Upstox API Settings")
access_token = st.sidebar.text_input("Enter Upstox Access Token", type="password")

# --- EXTENDED INDIAN STOCK SECTOR DATABASE ---
DEFAULT_SECTOR_MAP = {
    # BFSI / Banking
    "HDFCBANK": "BFSI / Banking", "ICICIBANK": "BFSI / Banking", "KOTAKBANK": "BFSI / Banking",
    "AXISBANK": "BFSI / Banking", "SBIN": "BFSI / Banking", "BAJFINANCE": "BFSI / Banking",
    "BAJAJFINSV": "BFSI / Banking", "INDUSINDBK": "BFSI / Banking", "BANKBARODA": "BFSI / Banking",
    # IT / Technology
    "INFY": "IT / Technology", "TCS": "IT / Technology", "WIPRO": "IT / Technology",
    "HCLTECH": "IT / Technology", "TECHM": "IT / Technology", "LTIM": "IT / Technology",
    "COFORGE": "IT / Technology", "PERSISTENT": "IT / Technology",
    # Renewables & Energy / Power
    "RELIANCE": "Renewables & Energy", "NTPC": "Renewables & Energy", "POWERGRID": "Renewables & Energy",
    "TATAPOWER": "Renewables & Energy", "ADANIGREEN": "Renewables & Energy", "BPCL": "Renewables & Energy",
    "IOC": "Renewables & Energy", "ONGC": "Renewables & Energy",
    # FMCG
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "TATACONSUM": "FMCG", "DABUR": "FMCG", "GODREJCP": "FMCG", "MARICO": "FMCG",
    # Pharma & Healthcare
    "SUNPHARMA": "Pharma & Healthcare", "CIPLA": "Pharma & Healthcare", "DRREDDY": "Pharma & Healthcare",
    "DIVISLAB": "Pharma & Healthcare", "APOLLOHOSP": "Pharma & Healthcare", "MANKIND": "Pharma & Healthcare",
    # Auto & Mobility
    "TATAMOTORS": "Auto & Mobility", "M&M": "Auto & Mobility", "MARUTI": "Auto & Mobility",
    "BAJAJ-AUTO": "Auto & Mobility", "HEROMOTOCO": "Auto & Mobility", "EICHERMOT": "Auto & Mobility",
    # Metals & Mining
    "TATASTEEL": "Metals & Mining", "HINDALCO": "Metals & Mining", "COALINDIA": "Metals & Mining",
    "JSWSTEEL": "Metals & Mining", "VEDL": "Metals & Mining"
}

# Sector Override Manager
st.sidebar.header("🏷️ 2. Manual Sector Override")
st.sidebar.caption("Fix or update sector mapping for any stock.")
user_override_symbol = st.sidebar.text_input("Stock Symbol (e.g. INFY)").upper().strip()
user_override_sector = st.sidebar.text_input("Assign Sector (e.g. IT / Technology)").strip()

if "sector_db" not in st.session_state:
    st.session_state.sector_db = DEFAULT_SECTOR_MAP.copy()

if user_override_symbol and user_override_sector:
    st.session_state.sector_db[user_override_symbol] = user_override_sector
    st.sidebar.success(f"Mapped {user_override_symbol} ➔ {user_override_sector}")

# AMC Excel / CSV Holdings Uploader
st.sidebar.header("📁 3. Upload AMC Portfolio Files")
uploaded_files = st.sidebar.file_uploader("Upload AMC Holdings (Excel/CSV)", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

# --- API FETCHERS ---
def fetch_direct_stocks(token):
    url = "https://api.upstox.com/v2/portfolio/long-term-holdings"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers)

def fetch_mf_holdings(token):
    url = "https://api.upstox.com/v2/mf/holdings"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers)

# --- DASHBOARD LOGIC ---
if not access_token:
    st.info("👈 Enter your **Upstox Access Token** in the sidebar to load holdings.")
else:
    with st.spinner("Fetching live portfolio from Upstox..."):
        stock_res = fetch_direct_stocks(access_token)
        mf_res = fetch_mf_holdings(access_token)

    stocks_list = []
    mf_list = []

    # 1. PARSE DIRECT STOCKS
    if stock_res.status_code == 200:
        raw_stocks = stock_res.json().get("data", [])
        for s in raw_stocks:
            symbol = str(s.get("trading_symbol", "")).upper()
            comp_name = s.get("company_name", symbol)
            qty = float(s.get("quantity", 0))
            avg_price = float(s.get("average_price", 0))
            last_price = float(s.get("last_price", 0))
            
            invested = qty * avg_price
            current = qty * last_price
            pnl = current - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
            
            sector = st.session_state.sector_db.get(symbol, "Uncategorized")
            
            stocks_list.append({
                "Symbol": symbol,
                "Name": comp_name,
                "Type": "Direct Stock",
                "Sector": sector,
                "Units/Qty": qty,
                "Avg Price (₹)": avg_price,
                "Current Price (₹)": last_price,
                "Invested Amount (₹)": invested,
                "Current Value (₹)": current,
                "P&L (₹)": pnl,
                "Return (%)": pnl_pct
            })

    # 2. PARSE MUTUAL FUNDS (FIELD RESOLVER FOR SCHEME NAME)
    if mf_res.status_code == 200:
        raw_mfs = mf_res.json().get("data", [])
        for m in raw_mfs:
            # Resolves Upstox API variations: 'fund', 'scheme_name', or 'trading_symbol'
            scheme_name = m.get("fund") or m.get("scheme_name") or m.get("fund_name") or m.get("trading_symbol") or "Mutual Fund"
            qty = float(m.get("quantity", 0))
            avg_nav = float(m.get("average_price", 0))
            last_nav = float(m.get("last_price", 0))
            
            invested = qty * avg_nav if avg_nav > 0 else float(m.get("cost_amount", 0))
            current = qty * last_nav if last_nav > 0 else float(m.get("last_value", 0))
            pnl = float(m.get("pnl", current - invested))
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
            
            mf_list.append({
                "Symbol": m.get("isin") or m.get("instrument_key") or "MF",
                "Name": scheme_name,
                "Type": "Mutual Fund",
                "Sector": "Mutual Fund",
                "Units/Qty": qty,
                "Avg Price (₹)": avg_nav,
                "Current Price (₹)": last_nav,
                "Invested Amount (₹)": invested,
                "Current Value (₹)": current,
                "P&L (₹)": pnl,
                "Return (%)": pnl_pct
            })

    df_stocks = pd.DataFrame(stocks_list)
    df_mfs = pd.DataFrame(mf_list)

    # --- TOP BIFURCATED METRICS ---
    st.subheader("📌 Portfolio Overview & Bifurcation")
    
    st_inv = df_stocks["Invested Amount (₹)"].sum() if not df_stocks.empty else 0
    st_cur = df_stocks["Current Value (₹)"].sum() if not df_stocks.empty else 0
    st_ret = ((st_cur - st_inv) / st_inv * 100) if st_inv > 0 else 0
    
    mf_inv = df_mfs["Invested Amount (₹)"].sum() if not df_mfs.empty else 0
    mf_cur = df_mfs["Current Value (₹)"].sum() if not df_mfs.empty else 0
    mf_ret = ((mf_cur - mf_inv) / mf_inv * 100) if mf_inv > 0 else 0
    
    tot_inv = st_inv + mf_inv
    tot_cur = st_cur + mf_cur
    tot_ret = ((tot_cur - tot_inv) / tot_inv * 100) if tot_inv > 0 else 0

    c1, c2, c3 = st.columns(3)
    
    with c1:
        st.markdown("### 📈 Direct Stocks")
        st.write(f"**Invested:** ₹{st_inv:,.2f}")
        st.write(f"**Current Value:** ₹{st_cur:,.2f}")
        st.metric(label="Return", value=f"₹{st_cur - st_inv:,.2f}", delta=f"{st_ret:.2f}%")

    with c2:
        st.markdown("### 🧺 Mutual Funds")
        st.write(f"**Invested:** ₹{mf_inv:,.2f}")
        st.write(f"**Current Value:** ₹{mf_cur:,.2f}")
        st.metric(label="Return", value=f"₹{mf_cur - mf_inv:,.2f}", delta=f"{mf_ret:.2f}%")

    with c3:
        st.markdown("### 💼 Total Portfolio")
        st.write(f"**Invested:** ₹{tot_inv:,.2f}")
        st.write(f"**Current Value:** ₹{tot_cur:,.2f}")
        st.metric(label="Return", value=f"₹{tot_cur - tot_inv:,.2f}", delta=f"{tot_ret:.2f}%")

    st.markdown("---")

    # --- PIE CHARTS: INVESTED VS CURRENT VALUE ---
    st.subheader("📊 Direct Stock Portfolio Breakdown")
    if not df_stocks.empty:
        col_pie1, col_pie2 = st.columns(2)
        with col_pie1:
            st.markdown("**Stock Allocation by Invested Cost (₹)**")
            fig_inv = px.pie(df_stocks, values="Invested Amount (₹)", names="Name", hole=0.4)
            st.plotly_chart(fig_inv, use_container_width=True)
            
        with col_pie2:
            st.markdown("**Stock Allocation by Current Market Value (₹)**")
            fig_cur = px.pie(df_stocks, values="Current Value (₹)", names="Name", hole=0.4)
            st.plotly_chart(fig_cur, use_container_width=True)
            
        # Sector Breakdown
        st.markdown("**Direct Stock Sector Breakdown**")
        df_sector = df_stocks.groupby("Sector")["Current Value (₹)"].sum().reset_index()
        fig_sec = px.pie(df_sector, values="Current Value (₹)", names="Sector", color_discrete_sequence=px.colors.sequential.Teal)
        st.plotly_chart(fig_sec, use_container_width=True)
    else:
        st.info("No direct stocks found.")

    st.markdown("---")

    # --- TABLES ---
    st.subheader("📋 Detailed Holdings Tables")
    
    st.markdown("#### 1. Direct Stocks Table")
    if not df_stocks.empty:
        st.dataframe(df_stocks[["Name", "Symbol", "Sector", "Units/Qty", "Avg Price (₹)", "Current Price (₹)", "Invested Amount (₹)", "Current Value (₹)", "P&L (₹)", "Return (%)"]], use_container_width=True)
        
    st.markdown("#### 2. Mutual Funds Table")
    if not df_mfs.empty:
        st.dataframe(df_mfs[["Name", "Symbol", "Units/Qty", "Avg Price (₹)", "Current Price (₹)", "Invested Amount (₹)", "Current Value (₹)", "P&L (₹)", "Return (%)"]], use_container_width=True)

    st.markdown("---")

    # --- AMC EXCEL UPLOADER & CONSOLIDATED EXPOSURE ---
    st.subheader("🔍 Consolidated Company Exposure (Direct + AMC Parsed Files)")

    parsed_mf_stock_holdings = []

    if uploaded_files:
        for file in uploaded_files:
            try:
                file_df = pd.read_csv(file) if file.name.endswith(".csv") else pd.read_excel(file)
                file_df.columns = [str(c).strip().lower() for c in file_df.columns]
                
                stock_col = next((c for c in file_df.columns if "company" in c or "stock" in c or "instrument" in c), None)
                weight_col = next((c for c in file_df.columns if "weight" in c or "allocation" in c or "%" in c), None)
                
                if stock_col and weight_col:
                    for _, mf_row in df_mfs.iterrows():
                        mf_value = mf_row["Current Value (₹)"]
                        for _, row in file_df.iterrows():
                            stock_name = str(row[stock_col]).strip()
                            try:
                                weight_pct = float(str(row[weight_col]).replace("%", "").strip())
                                indirect_val = mf_value * (weight_pct / 100.0)
                                parsed_mf_stock_holdings.append({"Stock": stock_name, "Indirect MF Exposure (₹)": indirect_val})
                            except ValueError:
                                continue
                    st.success(f"Parsed AMC File: {file.name}")
                else:
                    st.warning(f"Could not auto-detect columns in {file.name}. Ensure headers contain 'Company' and 'Weight'.")
            except Exception as e:
                st.error(f"Error reading {file.name}: {e}")

    # Combine Direct + MF Parsed Exposure
    combined_exposure = []
    if not df_stocks.empty:
        for _, s in df_stocks.iterrows():
            combined_exposure.append({"Stock": s["Name"], "Direct Exposure (₹)": s["Current Value (₹)"], "Indirect MF Exposure (₹)": 0.0})

    if parsed_mf_stock_holdings:
        for p in parsed_mf_stock_holdings:
            combined_exposure.append({"Stock": p["Stock"], "Direct Exposure (₹)": 0.0, "Indirect MF Exposure (₹)": p["Indirect MF Exposure (₹)"]})

    if combined_exposure:
        df_exp = pd.DataFrame(combined_exposure)
        df_agg = df_exp.groupby("Stock")[["Direct Exposure (₹)", "Indirect MF Exposure (₹)"]].sum().reset_index()
        df_agg["Total True Exposure (₹)"] = df_agg["Direct Exposure (₹)"] + df_agg["Indirect MF Exposure (₹)"]
        df_agg = df_agg.sort_values(by="Total True Exposure (₹)", ascending=False)
        
        st.dataframe(df_agg, use_container_width=True)
        fig_true = px.bar(df_agg.head(15), x="Stock", y=["Direct Exposure (₹)", "Indirect MF Exposure (₹)"], title="Top 15 Aggregate Company Exposures", barmode="stack")
        st.plotly_chart(fig_true, use_container_width=True)
    else:
        st.info("Upload monthly AMC portfolio Excel files in the sidebar to calculate true consolidated company exposure.")
