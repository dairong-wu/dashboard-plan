import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta

# --- 設定頁面資訊 ---
st.set_page_config(page_title="Jeffy's FIRE 戰情室 🔥", page_icon="📈", layout="wide")

# --- 讀取 Secrets 中的 URL ---
try:
    # 這裡會讀取你設定在 Streamlit Cloud Secrets 中的 GID 連結
    SPREADSHEET_URL = st.secrets["data"]["sheet_url"]
except KeyError:
    st.error("⚠️ **Secrets 錯誤:** 請確認您的 `secrets.toml` 中有設定 `[data]` 和 `sheet_url`。")
    st.stop() 

# --- 讀取數據函數 (快取 10 秒) ---
@st.cache_data(ttl=10) 
def load_data(url):
    try:
        # 讀取 GID 格式的 CSV 匯出連結
        df_total = pd.read_csv(url, header=1) 
        
        # 1. 欄位清洗與去空格
        df_total.columns = df_total.columns.str.strip() 
        
        # 2. 數據清洗與前處理
        df_total = df_total.dropna(subset=['日期', '總資產(TWD)']).copy()
        
        # 3. 排除未來空行 (總資產為零或空白的紀錄)
        df_total = df_total[df_total['總資產(TWD)'] != 0].copy()
        
        # 4. 轉換日期
        df_total['日期'] = pd.to_datetime(df_total['日期'], errors='coerce')
        df_total = df_total.sort_values('日期').reset_index(drop=True)
        
        # 5. ***最終修復：極限數值轉換 (解決 0 值問題)***
        numeric_cols = ['總資產(TWD)', '台幣現金(TWD)', '外幣現金(EUR)', 
                        '股票成本(USD)', 'ETF(EUR)', '不動產(TWD)', '加密貨幣(USD)', '其他(TWD)', 'USDTWD', 'EURTWD', '總資產增額(TWD)']
        for col in numeric_cols:
            if col in df_total.columns:
                # 關鍵修復：強制去除所有非數字、非小數點、非負號的符號
                df_total[col] = df_total[col].astype(str).str.replace(r'[^\d\.\-]', '', regex=True).replace('', np.nan)
                # 然後強制轉數字，失敗就變成 NaN (最後用 0 填充)
                df_total[col] = pd.to_numeric(df_total[col], errors='coerce').fillna(0)
            else:
                df_total[col] = 0

        return df_total
        
    except Exception as e:
        st.error(f"⚠️ 直接讀取 CSV 發生嚴重錯誤: {e}") 
        return pd.DataFrame() 

# --- 執行讀取 ---
df_total = load_data(SPREADSHEET_URL)

# --- 介面呈現 ---
st.title("🔥 Jeffy 的 FIRE 戰情室")
st.markdown("### *用工程師的效率，看資產曲線穩穩爬升！💪*")

if not df_total.empty and len(df_total) > 0:
    
    # --- 核心數據計算 ---
    latest = df_total.iloc[-1]
    prev = df_total.iloc[-2] if len(df_total) > 1 else latest
    
    current_assets = latest['總資產(TWD)']
    month_diff = latest['總資產(TWD)'] - prev['總資產(TWD)']
    growth_rate = (month_diff / prev['總資產(TWD)']) * 100 if prev['總資產(TWD)'] != 0 else 0
    
    usd_rate = latest['USDTWD'] if 'USDTWD' in latest else 32.5
    eur_rate = latest['EURTWD'] if 'EURTWD' in latest else 35.0
    
    # 計算平均每月儲蓄
    df_gains = df_total[df_total['總資產增額(TWD)'] > 0]
    avg_monthly_gain = df_gains['總資產增額(TWD)'].mean() if not df_gains.empty else 0
    
    # --- 側邊欄：個人化設定與預測參數 ---
    with st.sidebar:
        st.header("⚙️ 戰情室設定")
        st.caption(f"數據最後同步: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        fire_goal = st.number_input("🎯 FIRE 目標金額 (TWD)", value=50000000, step=1000000)
        
        st.divider()
        st.subheader("🔮 預測模型參數")
        annual_growth = st.slider("年化成長率 (CAGR - %)", 4.0, 15.0, 7.0, 0.5) 
        st.write(f"平均月度貢獻: **${avg_monthly_gain:,.0f} TWD**")
        st.info("嗨 Jeffy! NVC 流程是挑戰，但你的資產曲線會給你信心。")
        if st.button("🔄 強制刷新數據"):
            st.cache_data.clear()
            st.rerun()

    # --- 關鍵修復：資產值檢查 (Pie Chart Debug) ---
    st.info(f"💰 **資產值檢查 (最新記錄 {latest['日期'].strftime('%Y/%m')}):** 股票(USD): **${latest['股票成本(USD)']:.2f}**, ETF(EUR): **€{latest['ETF(EUR)']:.2f}**, 加密貨幣(USD): **${latest['加密貨幣(USD)']:.2f}**。理論上讀到的原始值。")
    st.divider()

    # --- 第一排：關鍵指標 (KPI) ---
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

    # --- 第二排：資產趨勢與配置 ---
    col_chart1, col_chart2 = st.columns([2, 1])

    with col_chart1:
        st.subheader("📈 資產累積趨勢")
        fig_trend = px.line(df_total, x='日期', y='總資產(TWD)', markers=True, title='Net Worth Growth Over Time', template="plotly_dark")
        fig_trend.update_traces(line_color='#00CC96', line_width=3)
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_chart2:
        st.subheader("🍰 最新資產配置")
        
        # 圓餅圖數據準備 (使用清理後的欄位名稱)
        assets_dict = {
            '台幣現金': latest['台幣現金(TWD)'],
            '不動產': latest['不動產(TWD)'],
            '外幣現金 (TWD)': latest['外幣現金(EUR)'] * eur_rate,
            '股票 (TWD)': latest['股票成本(USD)'] * usd_rate,
            'ETF (TWD)': latest['ETF(EUR)'] * eur_rate,
            '加密貨幣 (TWD)': latest['加密貨幣(USD)'] * usd_rate,
            '其他資產 (TWD)': latest['其他(TWD)'],
        }
        
        df_pie = pd.DataFrame([(k, v) for k, v in assets_dict.items() if v > 0], columns=['Type', 'Value'])
        
        fig_pie = px.pie(df_pie, values='Value', names='Type', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- 第三排：預測模型 (CAGR) ---
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

    # --- 第四排：詳細數據 (用於 Debug) ---
    st.divider()
    st.markdown("### 📝 **原始數據與欄位名稱檢查**")
    st.caption("以下為程式碼讀取並清理後的原始數據。")
    with st.expander("點擊展開查看原始數據表格"):
        st.dataframe(df_total.tail(20), use_container_width=True)

else:
    st.warning("⚠️ 數據讀取失敗。請檢查 Google Sheet 權限、分頁 GID 連結和 `secrets.toml` 設定無誤。")