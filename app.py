import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
import numpy as np # 處理數據中的 NaN 或空值

# --- 設定頁面資訊 (活潑語氣) ---
st.set_page_config(page_title="Jeffy's FIRE 戰情室 🔥", page_icon="📈", layout="wide")

# --- CSS 美化 ---
st.markdown("""
<style>
    .big-font {
        font-size: 20px !important;
        font-weight: bold;
        color: #00CC96;
    }
</style>
""", unsafe_allow_html=True)

# --- 讀取 Secrets 中的 URL ---
try:
    # 從 secrets.toml 獲取完整的 CSV 匯出 URL
    SPREADSHEET_URL = st.secrets["data"]["sheet_url"]
except KeyError:
    st.error("⚠️ **Secrets 錯誤:** 請確認您的 `secrets.toml` 中有設定 `[data]` 和 `sheet_url`。")
    st.stop() 

# --- 讀取數據函數 (快取 10 秒) ---
@st.cache_data(ttl=10) 
def load_data(url):
    try:
        # 關鍵：直接使用 Pandas 讀取 Google Sheets 導出的 CSV 連結
        # header=1: 標題在第二行
        df_total = pd.read_csv(url, header=1) 
        
        # 數據清洗與前處理
        df_total = df_total.dropna(subset=['日期', '總資產(TWD)']).copy()
        
        # 轉換日期格式 (確保能排序)
        df_total['日期'] = pd.to_datetime(df_total['日期'], errors='coerce')
        df_total = df_total.sort_values('日期').reset_index(drop=True)
        
        # 確保關鍵數值欄位是數字，並處理逗號和 NaN
        numeric_cols = ['總資產(TWD)', '台幣現金(TWD)', '外幣現金(EUR)', 
                        '股票成本(USD)', 'ETF(EUR)', '不動產(TWD)', '加密貨幣(USD)', 'USDTWD', 'EURTWD']
        for col in numeric_cols:
            df_total[col] = df_total[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True).replace('', np.nan)
            df_total[col] = pd.to_numeric(df_total[col], errors='coerce').fillna(0)


        return df_total
        
    except Exception as e:
        # 保持 Debug 錯誤訊息
        st.error(f"⚠️ 直接讀取 CSV 發生錯誤: {e}") 
        return pd.DataFrame() 

# --- 執行讀取 ---
df_total = load_data(SPREADSHEET_URL)

# --- 介面呈現 ---
st.title("🔥 Jeffy 的 FIRE 戰情室")
st.markdown("### *用工程師的效率，看資產曲線穩穩爬升！💪*")

if not df_total.empty and len(df_total) > 0:
    
    # --- 側邊欄：個人化設定與提醒 ---
    with st.sidebar:
        st.header("⚙️ 戰情室設定")
        st.caption(f"數據最後同步: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (每 10 秒更新)")
        
        # FIRE 目標設定 (可調整)
        fire_goal = st.number_input("🎯 FIRE 目標金額 (TWD)", value=50000000, step=1000000)
        
        st.divider()
        st.info("嗨 Jeffy! 德國生活辛苦了，數據有在動就好，別忘了還有家人和貓貓在支持你！")
        if st.button("🔄 強制刷新數據"):
            st.cache_data.clear()
            st.rerun()

    # --- 核心數據計算 ---
    latest = df_total.iloc[-1]
    prev = df_total.iloc[-2] if len(df_total) > 1 else latest
    
    # 數值
    current_assets = latest['總資產(TWD)']
    prev_assets = prev['總資產(TWD)']
    month_diff = current_assets - prev_assets
    growth_rate = (month_diff / prev_assets) * 100 if prev_assets != 0 else 0
    
    progress = (current_assets / fire_goal) * 100
    
    # 匯率 (從 sheet 抓最新值，若無則預設)
    usd_rate = latest.get('USDTWD', 32.5)
    eur_rate = latest.get('EURTWD', 35.0)

    # --- 第一排：關鍵指標 (KPI) ---
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(label="💰 目前總資產 (TWD)", 
                  value=f"${current_assets:,.0f}", 
                  delta=f"{month_diff:,.0f} ({growth_rate:.2f}%)")
    
    with col2:
        st.metric(label="🎯 FIRE 進度", 
                  value=f"{progress:.2f}%",
                  delta=f"距離目標還差 ${(fire_goal - current_assets):,.0f}", delta_color="inverse")
        
    with col3:
        # 預估每月被動收入 (4% rule)
        passive_income_monthly = (current_assets * (0.04)) / 12
        st.metric(label="🛌 預估每月被動收入 (4% rule)", 
                  value=f"${passive_income_monthly:,.0f}")
        
    with col4:
        net_worth_eur = current_assets / eur_rate
        st.metric(label="🇪🇺 總資產 (EUR)", 
                  value=f"€{net_worth_eur:,.0f}", 
                  delta=f"1 EUR ≈ {eur_rate:.2f} TWD")

    st.divider()

    # --- 第二排：圖表區 ---
    col_chart1, col_chart2 = st.columns([2, 1])

    with col_chart1:
        st.subheader("📈 資產累積趨勢")
        # 繪製總資產隨時間變化的圖表
        fig_trend = px.line(df_total, x='日期', y='總資產(TWD)', 
                            markers=True, title='Net Worth Growth Over Time',
                            template="plotly_dark")
        fig_trend.update_traces(line_color='#00CC96', line_width=3)
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_chart2:
        st.subheader("🍰 最新資產配置")
        
        # 計算各類資產的最新 TWD 價值 (使用 sheet 提供的匯率轉換)
        assets_dict = {
            '台幣現金': latest['台幣現金(TWD)'],
            '不動產': latest['不動產(TWD)'],
            '外幣現金 (TWD)': latest['外幣現金(EUR)'] * eur_rate,
            '股票 (TWD)': latest['股票成本(USD)'] * usd_rate,
            'ETF (TWD)': latest['ETF(EUR)'] * eur_rate,
            '加密貨幣 (TWD)': latest['加密貨幣(USD)'] * usd_rate,
        }
        
        # 排除 0 資產的類別
        df_pie = pd.DataFrame([(k, v) for k, v in assets_dict.items() if v > 0], columns=['Type', 'Value'])
        
        fig_pie = px.pie(df_pie, values='Value', names='Type', hole=0.4,
                         color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 第三排：詳細數據 ---
    st.markdown("### 📝 詳細資產紀錄 (原始數據)")
    with st.expander("點擊展開查看原始數據表格"):
        st.dataframe(df_total.tail(20), use_container_width=True)

else:
    st.warning("⚠️ 數據讀取失敗。請確認您的 Google Sheet 權限、分頁名稱 (Summary) 和 `secrets.toml` 設定無誤。")