import streamlit as st
import pandas as pd
import plotly.express as px
import requests

st.set_page_config(page_title="Consolidated Portfolio & Sector Exposure", layout="wide")
st.title("📊 Consolidated Stock & Mutual Fund Exposure Dashboard")

# --- SIDEBAR AUTHENTICATION ---
st.sidebar.header("🔑 Upstox API Credentials")
access_token = st.sidebar.text_input("Enter Access Token", type="password")

# --- MUTUAL FUND CONSTITUENT MAPPING (DB / Lookups) ---
# Maps MF ISIN/Names to underlying stock portfolio allocations & sectors
MF_PORTFOLIO_LOOKUP = {
    "HDFC Top 100 Fund": [
        {"Stock": "HDFC Bank", "Weight (%)": 9.5, "Sector": "BFSI / Banking"},
        {"Stock": "ICICI Bank", "Weight (%)": 7.8, "Sector": "BFSI / Banking"},
        {"Stock": "Reliance Industries", "Weight (%)": 8.2, "Sector": "Renewables & Energy"},
        {"Stock": "Infosys", "Weight (%)": 5.4, "Sector": "IT / Technology"},
        {"Stock": "Larsen & Toubro", "Weight (%)": 4.1, "Sector": "Capital Goods / Infra"}
    ],
    "Parag Parikh Flexi Cap Fund": [
        {"Stock": "HDFC Bank", "Weight (%)": 7.1, "Sector": "BFSI / Banking"},
        {"Stock": "Bajaj Holdings", "Weight (%)": 6.3, "Sector": "BFSI / Banking"},
        {"Stock": "ITC Ltd", "Weight (%)": 5.2, "Sector": "FMCG"},
        {"Stock": "Alphabet Inc", "Weight (%)": 4.8, "Sector": "IT / Technology"},
        {"Stock": "Coal India", "Weight (%)": 3.2, "Sector": "Metals & Mining"}
    ],
    "Nippon India Small Cap Fund": [
        {"Stock": "Tube Investments", "Weight (%)": 3.1, "Sector": "Auto & Auto Ancillary"},
        {"Stock": "HDFC Bank", "Weight (%)": 1.2, "Sector": "BFSI / Banking"},
        {"Stock": "Sun Pharma", "Weight (%)": 2.8, "Sector": "Pharma & Healthcare"}
    ]
}

# Stock to Sector Fallback Lookup table for Direct Equity
STOCK_SECTOR_MAP = {
    "RELIANCE": "Renewables & Energy",
    "INFY": "IT / Technology",
    "TCS": "IT / Technology",
    "HDFCBANK": "BFSI / Banking",
    "ICICIBANK": "BFSI / Banking",
    "TATAMOTORS": "Auto & Auto Ancillary",
    "HINDUNILVR": "FMCG",
    "SUNPHARMA": "Pharma & Healthcare",
    "TATASTEEL": "Metals & Mining",
    "HDFC Bank": "BFSI / Banking",
    "Infosys": "IT / Technology",
    "Reliance Industries": "Renewables & Energy"
}

# --- UPSTOX API FETCHERS ---
def fetch_direct_stocks(token):
    url = "https://api.upstox.com/v2/portfolio/long-term-holdings"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers)

def fetch_mf_holdings(token):
    url = "https://api.upstox.com/v2/mf/holdings"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {token}"}
    return requests.get(url, headers=headers)

# --- APP EXECUTION ---
if not access_token:
    st.info("👈 Please enter your **Upstox Access Token** in the sidebar to run exposure analysis.")
else:
    with st.spinner("Fetching Stocks & Mutual Fund Holdings from Upstox..."):
        stock_res = fetch_direct_stocks(access_token)
        mf_res = fetch_mf_holdings(access_token)
        
    all_rows = []
    
    # 1. PROCESS DIRECT STOCKS
    if stock_res.status_code == 200:
        stocks_data = stock_res.json().get("data", [])
        for item in stocks_data:
            symbol = item.get("trading_symbol", "UNKNOWN")
            company = item.get("company_name", symbol)
            val = float(item.get("quantity", 0)) * float(item.get("last_price", 0))
            sector = STOCK_SECTOR_MAP.get(symbol, STOCK_SECTOR_MAP.get(company, "Other / Uncategorized"))
            
            all_rows.append({
                "Company / Asset": company,
                "Holding Source": "Direct Stock",
                "Sector": sector,
                "Exposure Value (₹)": val
            })
            
    # 2. PROCESS MUTUAL FUNDS & BREAK DOWN CONSTITUENTS
    if mf_res.status_code == 200:
        mf_data = mf_res.json().get("data", [])
        for mf in mf_data:
            scheme_name = mf.get("scheme_name", "Mutual Fund")
            mf_total_val = float(mf.get("last_value", 0)) or (float(mf.get("quantity", 0)) * float(mf.get("last_price", 0)))
            
            # Check if scheme is in lookup database
            constituents = MF_PORTFOLIO_LOOKUP.get(scheme_name, None)
            
            if constituents:
                mapped_weight = 0
                for comp in constituents:
                    stock_name = comp["Stock"]
                    weight = comp["Weight (%)"]
                    sector = comp["Sector"]
                    calculated_val = mf_total_val * (weight / 100.0)
                    mapped_weight += weight
                    
                    all_rows.append({
                        "Company / Asset": stock_name,
                        "Holding Source": f"MF: {scheme_name}",
                        "Sector": sector,
                        "Exposure Value (₹)": calculated_val
                    })
                
                # Account for remaining unmapped MF cash/stocks
                if mapped_weight < 100:
                    remaining_val = mf_total_val * ((100 - mapped_weight) / 100.0)
                    all_rows.append({
                        "Company / Asset": f"{scheme_name} (Other Stocks/Cash)",
                        "Holding Source": f"MF: {scheme_name}",
                        "Sector": "Other / Diversified MF",
                        "Exposure Value (₹)": remaining_val
                    })
            else:
                # Fallback if MF is not in lookup table
                all_rows.append({
                    "Company / Asset": scheme_name,
                    "Holding Source": "Mutual Fund (Unmapped)",
                    "Sector": "Other / Diversified MF",
                    "Exposure Value (₹)": mf_total_val
                })

    # --- RENDER ANALYSIS ---
    if not all_rows:
        st.warning("No portfolio data returned or token invalid.")
    else:
        df_exposure = pd.DataFrame(all_rows)
        
        # Calculate Grand Totals
        total_portfolio_val = df_exposure["Exposure Value (₹)"].sum()
        
        # Display Core KPIs
        st.metric("Total Consolidated Portfolio Value", f"₹{total_portfolio_val:,.2f}")
        st.markdown("---")
        
        # Visual Grid Layout
        col1, col2 = st.columns(2)
        
        # Chart 1: Sector Breakdown (BFSI, FMCG, Tech, Renewables, etc.)
        with col1:
            st.subheader("🏢 Consolidated Sector Allocation")
            sector_summary = df_exposure.groupby("Sector")["Exposure Value (₹)"].sum().reset_index()
            sector_summary["Allocation (%)"] = (sector_summary["Exposure Value (₹)"] / total_portfolio_val) * 100
            
            fig_sector = px.pie(
                sector_summary, 
                values="Exposure Value (₹)", 
                names="Sector", 
                hole=0.4,
                hover_data=["Allocation (%)"]
            )
            st.plotly_chart(fig_sector, use_container_width=True)

        # Chart 2: Individual Company Overlap (Direct + MF Exposure Combined)
        with col2:
            st.subheader("🔍 Combined Company Concentration")
            company_summary = df_exposure.groupby("Company / Asset")["Exposure Value (₹)"].sum().reset_index()
            company_summary = company_summary.sort_values(by="Exposure Value (₹)", ascending=False).head(10)
            
            fig_company = px.bar(
                company_summary, 
                x="Company / Asset", 
                y="Exposure Value (₹)", 
                color="Company / Asset"
            )
            st.plotly_chart(fig_company, use_container_width=True)
            
        st.markdown("---")
        
        # Concentration Warnings
        st.subheader("⚠️ Concentration Risk & Overlap Warnings")
        top_company = company_summary.iloc[0]
        top_company_pct = (top_company["Exposure Value (₹)"] / total_portfolio_val) * 100
        
        if top_company_pct > 15:
            st.error(f"**High Exposure Warning:** Your combined holding in **{top_company['Company / Asset']}** accounts for **{top_company_pct:.1f}%** of your overall wealth (Direct Stock + MF constituents).")
        else:
            st.success("Your portfolio shows healthy single-stock diversification.")
            
        # Detailed Data Pivot Table
        st.subheader("Detailed Allocation Breakdown")
        st.dataframe(df_exposure, use_container_width=True)
