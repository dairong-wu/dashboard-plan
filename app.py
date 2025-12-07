import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re 

# --- 設定頁面資訊 ---
st.set_page_config(page_title="Jeffy's FIRE 戰情室 🔥", page_icon="📈", layout="wide")

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
        
        # 1. 欄位清洗
        df_total.columns = df_total.columns.str.strip() 
        
        # 2. 移除完全無效的列
        df_total = df_total.dropna(subset=['日期', '總資產(TWD)']).copy()
        
        # 3. 排除未來空行 (總資產為零)
        df_total = df_total[df_total['總資產(TWD)'] != 0].copy()
        
        # 4. 日期轉換
        df_total['日期'] = pd.to_datetime(df_total['日期'], errors='coerce')
        df_total = df_total.sort_values('日期').reset_index(drop=True)
        
        # 5. 數值清洗 (使用 re 模組，兼容性最高)
        # 包含匯率欄位 USDTWD, EURTWD
        numeric_cols = ['總資產(TWD)', '台幣現金(TWD)', '外幣現金(EUR)', 
                        '股票成本(USD)', 'ETF(EUR)', '不動產(TWD)', '加密貨幣(USD)', 
                        '其他(TWD)', 'USDTWD', 'EURTWD', '總資產增額(TWD)']
        
        for col in numeric_cols:
            if col in df_total.columns:
                df_total[col] = df_total[col].astype(str).apply(
                    lambda x: re.sub(r'[^\d\.\-]', '', x)
                )
                df_total[col] = pd.to_numeric(df_total[col], errors='coerce').fillna(0)
            else:
                df_total[col] = 0

        return df_total
        
    except Exception as e:
        st.error(f"⚠️ 數據讀取錯誤: {e}") 
        return pd.DataFrame() 

# --- 執行讀取 ---
df_total = load_data(SPREADSHEET_URL)

# --- 介面呈現 ---
st.title("🔥 Jeffy 的 FIRE 戰情室")

if not df_total.empty and len(df_total) > 0:
    
    # --- 取得最新一筆資料 ---
    latest = df_total.iloc[-1]
    prev = df_total.iloc[-2] if len(df_total) > 1 else latest
    
    # --- [關鍵修復] 匯率防呆機制 ---
    # 如果讀到的匯率是 0 (因為空值或轉換失敗)，強行使用預設值
    raw_usd_rate = latest.get('USDTWD', 0)
    raw_eur_rate = latest.get('EURTWD', 0)
    
    usd_rate = raw_usd_rate if raw_usd_rate > 10 else 31.3
    eur_rate = raw_eur_rate if raw_eur_rate > 10 else 36.5
    
    # 標示匯率來源 (用於 Debug)
    rate_source = "即時數據" if raw_usd_rate > 10 else "系統預設 (因原始數據異常)"

    # --- 核心數據計算 ---
    current_assets = latest['總資產(TWD)']
    month_diff = latest['總資產(TWD)'] - prev['總資產(TWD)']
    growth_rate = (month_diff / prev['總資產(TWD)']) * 100 if prev['總資產(TWD)'] != 0 else 0
    
    # 計算歷史平均月儲蓄 (作為預設值)
    df_gains = df_total[df_total['總資產增額(TWD)'] > 0]
    historical_avg_gain = df_gains['總資產增額(TWD)'].mean() if not df_gains.empty else 50000

    # --- 側邊欄：設定區 ---
    with st.sidebar:
        st.header("⚙️ 參數設定")
        st.caption(f"同步時間: {datetime.now().strftime('%H:%M:%S')}")
        
        fire_goal = st.number_input("🎯 FIRE 目標 (TWD)", value=50000000, step=1000000)
        
        st.divider()
        st.subheader("🔮 預測模型參數 (可調整)")
        
        # 1. 預測年限
        forecast_years = st.slider("模擬未來幾年?", 1, 30, 5)
        
        # 2. 年化報酬率
        annual_growth = st.slider("預期年化報酬率 (CAGR %)", 0.0, 20.0, 7.0, 0.5)
        
        # 3. 月度貢獻 (預設值為歷史平均，但可手動改)
        monthly_contribution = st.number_input(
            "每月投入資金 (TWD)", 
            value=int(historical_avg_gain), 
            step=5000,
            help="預設為您的歷史平均資產增額，您可以手動調整以模擬不同情境。"
        )
        
        st.info(f"ℹ️ **匯率狀態:** {rate_source}\nUSD: {usd_rate} | EUR: {eur_rate}")
        
        if st.button("🔄 刷新數據"):
            st.cache_data.clear()
            st.rerun()

    # --- 第一排：KPI ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("💰 總資產 (TWD)", f"${current_assets:,.0f}", f"{month_diff:,.0f} ({growth_rate:.2f}%)")
    with col2:
        progress = (current_assets / fire_goal) * 100
        st.metric("🎯 FIRE 進度", f"{progress:.2f}%", f"還差 ${(fire_goal - current_assets):,.0f}", delta_color="inverse")
    with col3:
        passive_monthly = (current_assets * 0.04) / 12
        st.metric("🛌 4%法則月收", f"${passive_monthly:,.0f}")
    with col4:
        # 顯示所有資產的「原始」外幣總值估算 (參考用)
        total_eur_est = current_assets / eur_rate
        st.metric("🇪🇺 總資產 (EUR)", f"€{total_eur_est:,.0f}", f"Rate: {eur_rate}")

    st.divider()

    # --- 第二排：趨勢與配置 ---
    col_chart1, col_chart2 = st.columns([2, 1])

    with col_chart1:
        st.subheader("📈 資產累積趨勢")
        fig_trend = px.line(df_total, x='日期', y='總資產(TWD)', markers=True, template="plotly_dark")
        fig_trend.update_traces(line_color='#00CC96', line_width=3)
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_chart2:
        st.subheader("🍰 最新資產配置")
        
        # 計算各項資產 TWD 價值 (使用防呆後的匯率)
        # 確保即使是 0 也不會報錯
        val_stock = latest.get('股票成本(USD)', 0) * usd_rate
        val_etf = latest.get('ETF(EUR)', 0) * eur_rate
        val_crypto = latest.get('加密貨幣(USD)', 0) * usd_rate
        val_foreign_cash = latest.get('外幣現金(EUR)', 0) * eur_rate
        val_twd_cash = latest.get('台幣現金(TWD)', 0)
        val_real_estate = latest.get('不動產(TWD)', 0)
        val_other = latest.get('其他(TWD)', 0)

        assets_dict = {
            '台幣現金': val_twd_cash,
            '不動產': val_real_estate,
            '外幣現金': val_foreign_cash,
            '美股': val_stock,
            '歐股/ETF': val_etf,
            '加密貨幣': val_crypto,
            '其他': val_other,
        }
        
        # 過濾掉 <= 0 的項目
        df_pie = pd.DataFrame([(k, v) for k, v in assets_dict.items() if v > 100], columns=['Type', 'Value'])
        
        if not df_pie.empty:
            fig_pie = px.pie(df_pie, values='Value', names='Type', hole=0.4, 
                             color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.error("⚠️ 資產總和為 0，請檢查匯率或原始數值。")
            st.write(f"Debug: Stock USD Raw: {latest.get('股票成本(USD)', 0)}, Rate: {usd_rate}")

    # --- 第三排：資產預測模型 (可調式) ---
    st.divider()
    st.subheader(f"🔮 未來 {forecast_years} 年資產模擬")
    
    current_date = latest['日期']
    forecast_months = forecast_years * 12
    
    future_data = []
    current_value = current_assets
    monthly_rate = annual_growth / 100 / 12
    
    for i in range(1, forecast_months + 1):
        future_date = current_date + relativedelta(months=i)
        # 複利公式 + 每月投入
        current_value = (current_value * (1 + monthly_rate)) + monthly_contribution
        future_data.append({'日期': future_date, '總資產(TWD)': current_value})

    df_forecast = pd.DataFrame(future_data)
    
    # 合併圖表
    df_history = df_total[['日期', '總資產(TWD)']].copy()
    df_history['Type'] = '歷史紀錄'
    df_forecast['Type'] = '未來預測'
    
    df_combined = pd.concat([df_history, df_forecast])
    
    fig_forecast = px.line(df_combined, x='日期', y='總資產(TWD)', color='Type',
                           title=f'模擬情境: 年化 {annual_growth}% + 月存 ${monthly_contribution:,.0f}', 
                           template="plotly_dark",
                           color_discrete_map={'歷史紀錄': '#00CC96', '未來預測': '#FFA500'})
    fig_forecast.update_traces(selector=dict(name='未來預測'), line=dict(dash='dot'))
    
    st.plotly_chart(fig_forecast, use_container_width=True)
    
    # 預測結論
    final_val = df_forecast.iloc[-1]['總資產(TWD)']
    st.success(f"""
    💡 **模擬結果：** 在 **{forecast_years} 年後** (約 {df_forecast.iloc[-1]['日期'].strftime('%Y/%m')})，
    你的總資產預計將達到 **${final_val:,.0f} TWD**。
    *(條件：CAGR {annual_growth}%，且每月持續投入 ${monthly_contribution:,.0f})*
    """)

    # --- Debug 區 (折疊) ---
    with st.expander("查看原始數據 (Debug)"):
        st.dataframe(df_total.tail(10))

else:
    st.warning("⚠️ 讀取失敗，請確認 secrets.toml 設定。")