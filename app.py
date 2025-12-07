import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 設定頁面資訊 ---
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
    SPREADSHEET_URL = st.secrets["data"]["sheet_url"]
except KeyError:
    st.error("⚠️ **Secrets 錯誤:** 請確認您的 `secrets.toml` 中有設定 `[data]` 和 `sheet_url`。")
    st.stop() 

# --- 讀取數據函數 (快取 10 秒) ---
@st.cache_data(ttl=10) 
def load_data(url):
    try:
        df_total = pd.read_csv(url, header=1) 
        
        # *** 關鍵修復：超激進欄位清洗 ***
        df_total.columns = df_total.columns.str.strip() 
        
        # 數據清洗與前處理
        df_total = df_total.dropna(subset=['日期', '總資產(TWD)']).copy()
        
        # 轉換日期格式 (確保能排序)
        df_total['日期'] = pd.to_datetime(df_total['日期'], errors='coerce')
        df_total = df_total.sort_values('日期').reset_index(drop=True)
        
        # 確保關鍵數值欄位是數字，並處理逗號和 NaN
        numeric_cols = ['總資產(TWD)', '台幣現金(TWD)', '外幣現金(EUR)', 
                        '股票成本(USD)', 'ETF(EUR)', '不動產(TWD)', '加密貨幣(USD)', 'USDTWD', 'EURTWD', '總資產增額(TWD)']
        for col in numeric_cols:
            if col in df_total.columns:
                df_total[col] = df_total[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True).replace('', np.nan)
                df_total[col] = pd.to_numeric(df_total[col], errors='coerce').fillna(0)
            else:
                # 如果欄位真的丟失，用 0 填充，但會在後續的 debug 報錯
                df_total[col] = 0

        return df_total
        
    except Exception as e:
        st.error(f"⚠️ 直接讀取 CSV 發生嚴重錯誤: {e}") 
        return pd.DataFrame() 

# --- 執行讀取 ---
df_total = load_data(SPREADSHEET_URL)
# 臨時 Debug 程式碼，請手動複製後貼上
st.markdown(f"**Pandas 讀到的所有欄位名稱:** {df_total.columns.tolist()}")

# --- 介面呈現 ---
st.title("🔥 Jeffy 的 FIRE 戰情室")

if not df_total.empty and len(df_total) > 0:
    
    # --- 核心數據計算 ---
    latest = df_total.iloc[-1]
    prev = df_total.iloc[-2] if len(df_total) > 1 else latest
    
    current_assets = latest['總資產(TWD)']
    month_diff = latest['總資產(TWD)'] - prev['總資產(TWD)']
    growth_rate = (month_diff / prev['總資產(TWD)']) * 100 if prev['總資產(TWD)'] != 0 else 0
    
    usd_rate = latest['USDTWD'] if 'USDTWD' in latest else 32.5
    eur_rate = latest['EURTWD'] if 'EURTWD' in latest else 35.0

    # --- 側邊欄：個人化設定與預測參數 ---
    with st.sidebar:
        st.header("⚙️ 戰情室設定")
        st.caption(f"數據最後同步: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        fire_goal = st.number_input("🎯 FIRE 目標金額 (TWD)", value=50000000, step=1000000)
        
        st.divider()
        st.subheader("🔮 預測模型參數")
        # 新增年化成長率輸入 (滿足 Q3)
        annual_growth = st.slider("年化成長率 (CAGR - %)", 4.0, 15.0, 7.0, 0.5) 
        
        # 計算平均每月儲蓄 (滿足 Q3)
        # 只計算有實際增額的歷史紀錄
        df_gains = df_total[df_total['總資產增額(TWD)'] > 0]
        avg_monthly_gain = df_gains['總資產增額(TWD)'].mean() if not df_gains.empty else 0
        st.write(f"平均月度貢獻: **${avg_monthly_gain:,.0f} TWD** (基於歷史增額)")
        st.info("嗨 Jeffy! NVC 流程是挑戰，但你的資產曲線會給你信心。我們來看看五年後橙橙上大學的資產預測！")
        if st.button("🔄 強制刷新數據"):
            st.cache_data.clear()
            st.rerun()

    # --- 第一排：KPI ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric(label="💰 目前總資產 (TWD)", value=f"${current_assets:,.0f}", delta=f"{month_diff:,.0f} ({growth_rate:.2f}%)")
    with col2:
        progress = (current_assets / fire_goal) * 100
        st.metric(label="🎯 FIRE 進度", value=f"{progress:.2f}%", delta=f"還差 ${(fire_goal - current_assets):,.0f}", delta_color="inverse")
    with col3:
        passive_income_monthly = (current_assets * (0.04)) / 12
        st.metric(label="🛌 預估每月被動收入 (4% rule)", value=f"${passive_income_monthly:,.0f}")
    with col4:
        net_worth_eur = current_assets / eur_rate
        st.metric(label="🇪🇺 總資產 (EUR)", value=f"€{net_worth_eur:,.0f}", delta=f"1 EUR ≈ {eur_rate:.2f} TWD")

    st.divider()

    # --- 第二排：資產趨勢與配置 (Q2 FIX) ---
    col_chart1, col_chart2 = st.columns([2, 1])

    with col_chart1:
        st.subheader("📈 資產累積趨勢")
        fig_trend = px.line(df_total, x='日期', y='總資產(TWD)', markers=True, title='Net Worth Growth Over Time', template="plotly_dark")
        fig_trend.update_traces(line_color='#00CC96', line_width=3)
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_chart2:
        st.subheader("🍰 最新資產配置 (Q2 Fix)")
        
        # *** 圓餅圖修復：使用清理後的欄位名稱，避免 Key Error ***
        assets_dict = {
            '台幣現金': latest['台幣現金(TWD)'],
            '不動產': latest['不動產(TWD)'],
            '外幣現金 (TWD)': latest['外幣現金(EUR)'] * eur_rate,
            '股票 (TWD)': latest['股票成本(USD)'] * usd_rate,
            'ETF (TWD)': latest['ETF(EUR)'] * eur_rate,
            '加密貨幣 (TWD)': latest['加密貨幣(USD)'] * usd_rate,
        }
        
        df_pie = pd.DataFrame([(k, v) for k, v in assets_dict.items() if v > 0], columns=['Type', 'Value'])
        
        fig_pie = px.pie(df_pie, values='Value', names='Type', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 第三排：新預測模型 (Q3 FIX) ---
    st.divider()
    st.subheader("🔮 未來五年資產預測 (CAGR 複合年均增長率)")
    
    # 1. 執行 CAGR 預測
    current_date = latest['日期']
    forecast_months = 60
    
    future_data = []
    current_value = current_assets
    monthly_rate = annual_growth / 100 / 12
    
    for i in range(1, forecast_months + 1):
        future_date = current_date + relativedelta(months=i)
        # 公式: A_t = (A_{t-1} * (1 + 月增長率)) + 平均每月貢獻
        current_value = (current_value * (1 + monthly_rate)) + avg_monthly_gain
        future_data.append({'日期': future_date, '總資產(TWD)': current_value})

    df_forecast = pd.DataFrame(future_data)
    
    # 2. 整合歷史與預測數據
    df_history = df_total[['日期', '總資產(TWD)']].copy()
    df_history['類型'] = '歷史資產'
    df_forecast['類型'] = '未來預測'
    
    df_combined = pd.concat([df_history, df_forecast])
    
    # 3. 繪製圖表
    fig_forecast = px.line(df_combined, x='日期', y='總資產(TWD)', color='類型',
                           title=f'資產預測 (CAGR {annual_growth}%)', template="plotly_dark",
                           color_discrete_map={'歷史資產': '#00CC96', '未來預測': '#FFA500'})
    fig_forecast.update_traces(line=dict(dash='dot'), selector=dict(name='未來預測'))
    
    st.plotly_chart(fig_forecast, use_container_width=True)
    
    final_forecast = df_forecast.iloc[-1]['總資產(TWD)']
    st.info(f"💡 **模型預測：** 假設年化增長率為 **{annual_growth}%** 且每月持續貢獻 **${avg_monthly_gain:,.0f} TWD**，五年後 (約 {df_forecast.iloc[-1]['日期'].strftime('%Y/%m')}) 總資產預計可達 **${final_forecast:,.0f} TWD**。")

    # --- 第四排：Debug 專區 (讓 Jeffy 檢查欄位名) ---
    st.divider()
    st.markdown("### 📝 **除錯專區：欄位名稱檢查**")
    st.caption("如果圓餅圖仍缺失資產，請將下方的欄位名稱貼給我。")
    with st.expander("點擊展開查看原始數據表格與欄位名稱"):
        st.dataframe(df_total.tail(20), use_container_width=True)
        st.markdown(f"**實際讀取到的所有欄位名稱:** {df_total.columns.tolist()}")

else:
    st.warning("⚠️ 數據讀取失敗。請檢查 Google Sheet 權限、分頁 GID 連結和 `secrets.toml` 設定無誤。")