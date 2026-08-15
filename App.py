import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Portfolio Exposure Analyzer", layout="wide")
st.title("📊 Portfolio Overlap & Sector Exposure Dashboard")

st.info("Upstox Integration Setup Complete! Next step: Authenticate API Token.")

# Demo Portfolio Breakdown (Will be replaced by live API + MF mapping)
data = {
    "Stock": ["Reliance Industries", "Infosys", "HDFC Bank", "ICICI Bank", "TCS"],
    "Sector": ["Energy", "IT", "Banking", "Banking", "IT"],
    "Combined Exposure (₹)": [70000, 45000, 40000, 35000, 10000]
}
df = pd.DataFrame(data)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Top Stock Exposure (Direct + MF)")
    fig_stock = px.pie(df, values="Combined Exposure (₹)", names="Stock", hole=0.4)
    st.plotly_chart(fig_stock, use_container_width=True)

with col2:
    st.subheader("Combined Sector Allocation")
    sector_df = df.groupby("Sector")["Combined Exposure (₹)"].sum().reset_index()
    fig_sector = px.pie(sector_df, values="Combined Exposure (₹)", names="Sector", color_discrete_sequence=px.colors.sequential.RdBu)
    st.plotly_chart(fig_sector, use_container_width=True)
