import streamlit as st
import pandas as pd
import plotly.express as px
import requests
import io

st.set_page_config(page_title="Upstox Consolidated Portfolio Analyzer", layout="wide")
st.title("📊 Consolidated Equity & Mutual Fund Portfolio Analyzer")

# --- SIDEBAR: AUTH & CONTROLS ---
st.sidebar.header("🔑 1. Upstox API Settings")
access_token = st.sidebar.text_input("Enter Upstox Access Token", type="password")

# --- DEFAULT SECTOR MAPPING DATABASE ---
DEFAULT_SECTOR_MAP = {
    "HDFCBANK": "BFSI / Banking", "ICICIBANK": "BFSI / Banking", "KOTAKBANK": "BFSI / Banking",
    "AXISBANK": "BFSI / Banking", "SBIN": "BFSI / Banking", "BAJFINANCE": "BFSI / Banking",
    "INFY": "IT / Technology", "TCS": "IT / Technology", "WIPRO": "IT / Technology",
    "HCLTECH": "IT / Technology", "TECHM": "IT / Technology",
    "RELIANCE": "Renewables & Energy", "NTPC": "Renewables & Energy", "POWERGRID": "Renewables & Energy",
    "TATAPOWER": "Renewables & Energy", "ADANIGREEN": "Renewables & Energy",
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG", "TATACONSUM": "FMCG",
    "SUNPHARMA": "Pharma & Healthcare", "CIPLA": "Pharma & Healthcare", "DRREDDY": "Pharma & Healthcare",
    "TATAMOTORS": "Auto & Mobility", "M&M": "Auto & Mobility", "MARUTI": "Auto & Mobility",
    "TATASTEEL": "Metals & Mining", "HINDALCO": "Metals & Mining", "COALINDIA": "Metals & Mining"
}

# Feature 4: Interactive Sector Override Editor
st.sidebar.header("🏷️ 2. Manual Sector Manager")
st.sidebar.caption("Override or set sectors for uncategorized direct stocks.")
user_override_symbol = st.sidebar.text_input("Stock Symbol (e.g. INFY)").upper().strip()
user_override_sector = st.sidebar.text_input("Assign Sector (e.g. IT / Technology)").strip()

if "sector_db" not in st.session_state:
    st.session_state.sector_db = DEFAULT_SECTOR_MAP.copy()

if user_override_symbol and user_override_sector:
    st.session_state.sector_db[user_override_symbol] = user_override_sector
    st.sidebar.success(f"Updated {user_override_symbol} ➔ {user_override_sector}")

# Feature 6: AMC Excel / CSV Holdings Uploader
st.sidebar.header("📁 3. Upload AMC Portfolio Files")
st.sidebar.caption("Upload monthly MF portfolio Excel/CSV from AMC websites.")
uploaded_files = st.sidebar.file_uploader("Upload AMC Holdings Files", type=["xlsx", "xls", "csv"], accept_multiple_files=True)

# --- UPSTOX API FETCHERS ---
def fetch_direct_stocks(token):
    url = "https://api.upstox.com/v2/portfolio/long-term-holdings"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers)

def fetch_mf_holdings(token):
    url = "https://api.upstox.com/v2/mf/holdings"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers)

# --- MAIN EXECUTION ---
if not access_token:
    st.info("👈 Please enter your **Upstox Access Token** in the sidebar to load your live portfolio.")
else:
    with st.spinner("Fetching live portfolio from Upstox..."):
        stock_res = fetch_direct_stocks(access_token)
        mf_res = fetch_mf_holdings(access_token)

    stocks_list = []
    mf_list = []

    # 1. PROCESS DIRECT STOCKS
    if stock_res.status_code == 200:
        raw_stocks = stock_res.json().get("data", [])
        for s in raw_stocks:
            symbol = s.get("trading_symbol", "").upper()
            comp_name = s.get("company_name", symbol)
            qty = float(s.get("quantity", 0))
            avg_price = float(s.get("average_price", 0))
            last_price = float(s.get("last_price", 0))
            
            invested = qty * avg_price
            current = qty * last_price
            pnl = current - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
            
            sector = st.session_state.sector_db.get(symbol, "Other / Uncategorized")
            
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

    # 2. PROCESS MUTUAL FUNDS
    if mf_res.status_code == 200:
        raw_mfs = mf_res.json().get("data", [])
        for m in raw_mfs:
            scheme_name = m.get("scheme_name", "Unknown Mutual Fund")
            qty = float(m.get("quantity", 0))
            avg_nav = float(m.get("average_price", 0))
            last_nav = float(m.get("last_price", 0))
            
            invested = qty * avg_nav if avg_nav > 0 else float(m.get("cost_amount", 0))
            current = qty * last_nav if last_nav > 0 else float(m.get("last_value", 0))
            pnl = current - invested
            pnl_pct = (pnl / invested * 100) if invested > 0 else 0.0
            
            mf_list.append({
                "Symbol": m.get("isin", "MF"),
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

    # --- FEATURE 1: TOP BIFURCATED METRICS ---
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
        st.markdown("### 💼 Total Combined Portfolio")
        st.write(f"**Invested:** ₹{tot_inv:,.2f}")
        st.write(f"**Current Value:** ₹{tot_cur:,.2f}")
        st.metric(label="Return", value=f"₹{tot_cur - tot_inv:,.2f}", delta=f"{tot_ret:.2f}%")

    st.markdown("---")

    # --- FEATURE 5: INVESTED VS CURRENT VALUE PIE CHARTS ---
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
            
        # Sector Breakdown Chart
        st.markdown("**Direct Stock Sector Breakdown**")
        df_sector = df_stocks.groupby("Sector")["Current Value (₹)"].sum().reset_index()
        fig_sec = px.pie(df_sector, values="Current Value (₹)", names="Sector", color_discrete_sequence=px.colors.sequential.Teal)
        st.plotly_chart(fig_sec, use_container_width=True)
    else:
        st.info("No direct stocks found.")

    st.markdown("---")

    # --- FEATURE 2 & 3: DETAILED ALLOCATION TABLES ---
    st.subheader("📋 Detailed Asset Breakdown")
    
    st.markdown("#### 1. Direct Stocks Table")
    if not df_stocks.empty:
        st.dataframe(df_stocks[["Name", "Symbol", "Sector", "Units/Qty", "Avg Price (₹)", "Current Price (₹)", "Invested Amount (₹)", "Current Value (₹)", "P&L (₹)", "Return (%)"]], use_container_width=True)
        
    st.markdown("#### 2. Mutual Funds Table (Scheme Names)")
    if not df_mfs.empty:
        st.dataframe(df_mfs[["Name", "Symbol", "Units/Qty", "Avg Price (₹)", "Current Price (₹)", "Invested Amount (₹)", "Current Value (₹)", "P&L (₹)", "Return (%)"]], use_container_width=True)

    st.markdown("---")

    # --- FEATURE 6: AMC EXCEL UPLOAD PARSER & UNDERLYING EXPOSURE CALCULATOR ---
    st.subheader("🔍 True Company-Level Exposure (Direct + AMC File Parsing)")
    st.caption("Combines direct stocks with parsed AMC holdings files to reveal true aggregate stock exposure.")

    parsed_mf_stock_holdings = []

    if uploaded_files:
        for file in uploaded_files:
            try:
                if file.name.endswith(".csv"):
                    file_df = pd.read_csv(file)
                else:
                    file_df = pd.read_excel(file)
                
                # Standardize column headers
                file_df.columns = [str(c).strip().lower() for c in file_df.columns]
                
                # Dynamic column mapping logic
                stock_col = next((c for c in file_df.columns if "company" in c or "stock" in c or "instrument" in c or "issuer" in c), None)
                weight_col = next((c for c in file_df.columns if "weight" in c or "allocation" in c or "portfolio" in c or "%" in c), None)
                
                if stock_col and weight_col:
                    # Match uploaded AMC file against active MF holdings
                    for _, mf_row in df_mfs.iterrows():
                        mf_value = mf_row["Current Value (₹)"]
                        for _, row in file_df.iterrows():
                            stock_name = str(row[stock_col]).strip()
                            try:
                                weight_pct = float(str(row[weight_col]).replace("%", "").strip())
                                indirect_val = mf_value * (weight_pct / 100.0)
                                parsed_mf_stock_holdings.append({
                                    "Stock": stock_name,
                                    "Indirect MF Exposure (₹)": indirect_val
                                })
                            except ValueError:
                                continue
                    st.success(f"Successfully processed AMC File: {file.name}")
                else:
                    st.warning(f"Could not automatically detect 'Company' and 'Weight (%)' columns in {file.name}. Please ensure your Excel file has standard headers.")
            except Exception as e:
                st.error(f"Error parsing file {file.name}: {e}")

    # Combine Direct Stocks + Parsed MF Indirect Stocks
    combined_exposure = []

    # Add Direct Stocks
    if not df_stocks.empty:
        for _, s in df_stocks.iterrows():
            combined_exposure.append({
                "Stock": s["Name"],
                "Direct Exposure (₹)": s["Current Value (₹)"],
                "Indirect MF Exposure (₹)": 0.0
            })

    # Add Parsed MF Stocks
    if parsed_mf_stock_holdings:
        for p in parsed_mf_stock_holdings:
            combined_exposure.append({
                "Stock": p["Stock"],
                "Direct Exposure (₹)": 0.0,
                "Indirect MF Exposure (₹)": p["Indirect MF Exposure (₹)"]
            })

    if combined_exposure:
        df_exp = pd.DataFrame(combined_exposure)
        df_agg = df_exp.groupby("Stock")[["Direct Exposure (₹)", "Indirect MF Exposure (₹)"]].sum().reset_index()
        df_agg["Total True Exposure (₹)"] = df_agg["Direct Exposure (₹)"] + df_agg["Indirect MF Exposure (₹)"]
        df_agg = df_agg.sort_values(by="Total True Exposure (₹)", ascending=False)
        
        st.dataframe(df_agg, use_container_width=True)
        
        fig_true = px.bar(
            df_agg.head(15), 
            x="Stock", 
            y=["Direct Exposure (₹)", "Indirect MF Exposure (₹)"],
            title="Top 15 Aggregate Company Exposures (Direct + MF)",
            barmode="stack"
        )
        st.plotly_chart(fig_true, use_container_width=True)
    else:
        st.info("Upload AMC portfolio disclosure files in the sidebar to calculate true consolidated company exposure.")
