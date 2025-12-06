import streamlit as st
import pandas as pd
import plotly.express as px
from streamlit_gsheets import GSheetsConnection
from datetime import datetime

# --- 設定頁面與隱私 ---
st.set_page_config(page_title="Jeffy's FIRE Dashboard", page_icon="🔥", layout="wide")

# --- 連接 Google Sheets ---
conn = st.connection("gsheets", type=GSheetsConnection)

# --- 讀取數據 (快取 10 秒) ---
@st.cache_data(ttl=10)
def load_data():
    try:
        # 讀取「總計」分頁，header=1 表示第二列是標題
        df_total = conn.read(worksheet="總計", header=1)
        df_total = df_total.dropna(subset=['日期'])
        df_total['日期'] = pd.to_datetime(df_total['日期'], errors='coerce')
        return df_total
    except Exception as e:
        st.error(f"⚠️ Google Sheets 連線詳細錯誤：{e}")
        return None

df_total = load_data()

# --- 介面呈現 ---
st.title("🔥 Jeffy's FIRE 戰情室")
st.caption(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

if df_total is not None:
    # 取得最新數據
    latest = df_total.iloc[-1]
    
    # 顯示 KPI
    col1, col2 = st.columns(2)
    with col1:
        st.metric("💰 總資產 (TWD)", f"${latest['總資產(TWD)']:,.0f}")
    with col2:
        # 假設你的目標是 5000 萬
        goal = 50000000 
        progress = (latest['總資產(TWD)'] / goal) * 100
        st.metric("🎯 FIRE 進度", f"{progress:.2f}%")

    # 顯示圖表
    st.subheader("資產趨勢")
    fig = px.line(df_total, x='日期', y='總資產(TWD)', markers=True)
    st.plotly_chart(fig, use_container_width=True)
    
    # 顯示數據表
    with st.expander("詳細數據"):
        st.dataframe(df_total)
else:
    st.error("無法讀取數據，請檢查 Google Sheets 連線設定。")