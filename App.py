import streamlit as st
import pandas as pd
import plotly.express as px
import requests

# Page Layout Configuration
st.set_page_config(page_title="Upstox Live Portfolio Analyzer", layout="wide")
st.title("📊 Real-Time Upstox Holdings Dashboard")

# --- SIDEBAR: AUTHENTICATION & CREDENTIALS ---
st.sidebar.header("🔑 Upstox API Credentials")

# 1. Access Token Input
access_token = st.sidebar.text_input("Enter Access Token", type="password")

# 2. Upstox OAuth Login Token Generator Assistant
with st.sidebar.expander("Generate Access Token"):
    api_key = st.sidebar.text_input("API Key")
    api_secret = st.sidebar.text_input("API Secret", type="password")
    redirect_uri = st.sidebar.text_input("Redirect URI", value="https://127.0.0.1")
    
    if api_key:
        login_url = f"https://api.upstox.com/v2/login/authorization/dialog?response_type=code&client_id={api_key}&redirect_uri={redirect_uri}"
        st.markdown(f"[👉 Click here to authorize on Upstox]({login_url})")
        st.caption("Log in, copy the `code=` value from the URL, and paste it below.")
        
    auth_code = st.sidebar.text_input("Paste Auth Code")
    if st.sidebar.button("Fetch Access Token"):
        if api_key and api_secret and auth_code:
            token_url = "https://api.upstox.com/v2/login/authorization/token"
            payload = {
                "code": auth_code,
                "client_id": api_key,
                "client_secret": api_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
            headers = {"Accept": "application/json", "Content-Type": "application/x-www-form-urlencoded"}
            res = requests.post(token_url, data=payload, headers=headers)
            if res.status_code == 200:
                token_data = res.json()
                st.sidebar.success("Access Token generated!")
                st.sidebar.code(token_data.get("access_token"))
            else:
                st.sidebar.error(f"Error fetching token: {res.text}")

# --- MAIN DASHBOARD LOGIC ---
def get_upstox_holdings(token):
    """Fetches real-time equity holdings from Upstox Portfolio API"""
    url = "https://api.upstox.com/v2/portfolio/long-term-holdings"
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    return response

if not access_token:
    st.warning("⚠️ Please provide an **Access Token** in the sidebar to load your live portfolio.")
else:
    with st.spinner("Fetching live portfolio from Upstox..."):
        res = get_upstox_holdings(access_token)
        
    if res.status_code == 200:
        holdings_data = res.json().get("data", [])
        
        if not holdings_data:
            st.info("No long-term holdings found in your Upstox account.")
        else:
            # Parse response into Pandas DataFrame
            df = pd.DataFrame(holdings_data)
            
            # Extract relevant fields
            df["Company"] = df["company_name"]
            df["Quantity"] = df["quantity"]
            df["Avg Price (₹)"] = df["average_price"]
            df["Current Price (₹)"] = df["last_price"]
            df["Current Value (₹)"] = df["Quantity"] * df["Current Price (₹)"]
            df["P&L (₹)"] = df["pnl"]
            
            # Add basic Sector mapping (Default fallback; can expand with dynamic maps later)
            df["Sector"] = df["trading_symbol"].apply(lambda s: "Equity Stock")

            # --- METRICS DISPLAY ---
            total_invested = (df["Quantity"] * df["Avg Price (₹)"]).sum()
            total_current = df["Current Value (₹)"].sum()
            total_pnl = df["P&L (₹)"].sum()
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Total Investment", f"₹{total_invested:,.2f}")
            col2.metric("Current Portfolio Value", f"₹{total_current:,.2f}")
            col3.metric("Overall P&L", f"₹{total_pnl:,.2f}", delta=f"{total_pnl:,.2f}")
            
            st.markdown("---")
            
            # --- CHARTS ---
            chart_col1, chart_col2 = st.columns(2)
            
            with chart_col1:
                st.subheader("Direct Stock Breakdown")
                fig_stock = px.pie(df, values="Current Value (₹)", names="Company", hole=0.4)
                st.plotly_chart(fig_stock, use_container_width=True)

            with chart_col2:
                st.subheader("Top Positions by Value")
                fig_bar = px.bar(df.sort_values(by="Current Value (₹)", ascending=False), 
                                 x="trading_symbol", y="Current Value (₹)", color="P&L (₹)")
                st.plotly_chart(fig_bar, use_container_width=True)

            # --- DETAILED DATA TABLE ---
            st.subheader("Holding Details")
            st.dataframe(
                df[["Company", "trading_symbol", "Quantity", "Avg Price (₹)", "Current Price (₹)", "Current Value (₹)", "P&L (₹)"]],
                use_container_width=True
            )
            
    else:
        st.error(f"Failed to fetch holdings from Upstox API. Status: {res.status_code}")
        st.json(res.json())
