import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from datetime import datetime
from dateutil.relativedelta import relativedelta
import re 

# --- 設定頁面資訊 ---
st.set_page_config(page_title="Jeffy's FIRE 戰情室 🔥", page_icon="🛡️", layout="wide")

# --- 讀取 Secrets 中的 URL ---
try:
    SPREADSHEET_URL = st.secrets["data"]["sheet_url"]
except KeyError:
    st.error("⚠️ **Secrets 錯誤:** 請確認您的 `secrets.toml` 中有設定 `[data]` 和 `sheet_url`。")
    st.stop() 

# --- 讀取數據函數 ---
@st.cache_data(ttl=10) 
def load_data(url):
    try:
        df_total = pd.read_csv(url, header=1) 
        df_total.columns = df_total.columns.str.strip() 
        
        target_cols = [
            '真實總資產(TWD)', '總資產(TWD)', '總資產+汽車折舊', '汽車預估價格(GPT模型)',
            '股票價值(USD)', '股票成本(USD)', 
            'ETF價值(EUR)', 'ETF(EUR)', 
            '台幣現金(TWD)', '外幣現金(EUR)', '不動產(TWD)', 
            '加密貨幣(USD)', '其他(TWD)', 
            'USDTWD', 'EURTWD', '總資產增額(TWD)'
        ]
        
        for col in target_cols:
            if col in df_total.columns:
                cleaned_series = df_total[col].astype(str).str.replace(',', '', regex=False)
                df_total[col] = cleaned_series.apply(
                    lambda x: re.sub(r'[^\d\.\-]', '', x)
                )
                df_total[col] = pd.to_numeric(df_total[col], errors='coerce').fillna(0)
            else:
                df_total[col] = 0

        df_total['日期'] = pd.to_datetime(df_total['日期'], errors='coerce')
        
        # 建立有效資產欄位 (優先級：真實總資產 > 總資產+折舊 > 總資產)
        df_total['Effective_Asset'] = np.where(
            df_total['真實總資產(TWD)'] > 0, 
            df_total['真實總資產(TWD)'], 
            df_total['總資產+汽車折舊']
        )
        
        # 過濾無效行
        df_total = df_total[df_total['Effective_Asset'] > 0].copy()
        df_total = df_total.sort_values('日期').reset_index(drop=True)
        
        return df_total
    except Exception as e:
        st.error(f"⚠️ 數據讀取錯誤: {e}") 
        return pd.DataFrame() 

df_total = load_data(SPREADSHEET_URL)

# --- 介面呈現 ---
st.title("🛡️ Jeffy's FIRE Command Center")
st.markdown("### *Data-Driven Financial Independence*")

if not df_total.empty and len(df_total) > 0:
    
    # --- 基礎數據準備 ---
    latest = df_total.iloc[-1]
    prev = df_total.iloc[-2] if len(df_total) > 1 else latest
    
    # 匯率
    raw_usd_rate = latest.get('USDTWD', 0)
    raw_eur_rate = latest.get('EURTWD', 0)
    usd_rate = raw_usd_rate if raw_usd_rate > 10 else 32.5
    eur_rate = raw_eur_rate if raw_eur_rate > 10 else 35.0
    
    # --- 資產價值分解 (Market Value) ---
    stock_usd_val = latest.get('股票價值(USD)', 0) if latest.get('股票價值(USD)', 0) > 0 else latest.get('股票成本(USD)', 0)
    etf_eur_val = latest.get('ETF價值(EUR)', 0) if latest.get('ETF價值(EUR)', 0) > 0 else latest.get('ETF(EUR)', 0)
    
    val_stock = stock_usd_val * usd_rate
    val_etf = etf_eur_val * eur_rate
    val_crypto = latest.get('加密貨幣(USD)', 0) * usd_rate
    val_foreign_cash = latest.get('外幣現金(EUR)', 0) * eur_rate
    val_twd_cash = latest.get('台幣現金(TWD)', 0)
    val_real_estate = latest.get('不動產(TWD)', 0)
    val_other = latest.get('其他(TWD)', 0)
    val_car = latest.get('汽車預估價格(GPT模型)', 0)

    # --- 資產成本分解 (Cost Basis) ---
    cost_stock = latest.get('股票成本(USD)', 0) * usd_rate
    cost_etf = latest.get('ETF(EUR)', 0) * eur_rate
    cost_crypto = val_crypto * 0.8 # 模擬成本
    
    total_market_value = latest['Effective_Asset']
    total_cost_basis = cost_stock + cost_etf + cost_crypto + val_twd_cash + val_foreign_cash + val_real_estate + val_other + val_car
    
    # --- 側邊欄設定 ---
    with st.sidebar:
        st.header("⚙️ 戰情室參數")
        fire_goal = st.number_input("🎯 FIRE 目標 (TWD)", value=50000000, step=1000000)
        
        st.divider()
        st.subheader("⏳ FIRE 自由度設定")
        monthly_expense_twd = st.number_input("退休後每月開銷 (TWD)", value=100000, step=5000)
        
        st.divider()
        st.subheader("🔮 預測參數")
        car_depreciation_rate = st.slider("汽車年折舊率 (%)", 5.0, 30.0, 15.0, 1.0)
        forecast_years = st.slider("模擬年數", 1, 10, 5)
        annual_growth = st.slider("預期年化報酬 (CAGR %)", 0.0, 20.0, 7.0, 0.5)
        
        df_gains = df_total[df_total['總資產增額(TWD)'] > 0]
        historical_avg_gain = df_gains['總資產增額(TWD)'].mean() if not df_gains.empty else 50000
        monthly_contribution = st.number_input("每月投入 (TWD)", value=int(historical_avg_gain), step=5000)
        
        if st.button("🔄 刷新戰情室"):
            st.cache_data.clear()
            st.rerun()

    # --- Row 1: KPI 區塊 ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        month_diff = latest['Effective_Asset'] - prev['Effective_Asset']
        growth_pct = (month_diff / prev['Effective_Asset']) * 100 if prev['Effective_Asset'] != 0 else 0
        st.metric("💰 真實總淨值", f"${total_market_value:,.0f}", f"{month_diff:,.0f} ({growth_pct:.2f}%)")
    with col2:
        fire_progress = (total_market_value / fire_goal) * 100
        st.metric("🎯 FIRE 進度", f"{fire_progress:.2f}%", f"差 ${fire_goal - total_market_value:,.0f}", delta_color="inverse")
    with col3:
        runway_years = total_market_value / (monthly_expense_twd * 12)
        st.metric("⏳ 財務跑道 (Runway)", f"{runway_years:.1f} 年", f"月花費 ${monthly_expense_twd:,.0f}")
    with col4:
        safe_withdrawal = (total_market_value * 0.04) / 12
        coverage = (safe_withdrawal / monthly_expense_twd) * 100
        st.metric("🛡️ 4%法則覆蓋率", f"{coverage:.1f}%", f"被動月收 ${safe_withdrawal:,.0f}")

    st.divider()

    # --- Row 2: 核心圖表 ---
    col_main, col_treemap = st.columns([1.8, 1.2])

    with col_main:
        st.subheader("📈 資產累積趨勢 (Net Worth)")
        fig_trend = px.line(df_total, x='日期', y='Effective_Asset', markers=True, title='歷史淨值走勢', template="plotly_dark")
        
        # [最終修正] 拆解 update_traces 以解決 Plotly 版本兼容性問題
        fig_trend.update_traces(connectgaps=True)
        fig_trend.update_traces(line_color='#00CC96', line_width=3)
        
        fig_trend.add_hline(y=fire_goal, line_dash="dot", line_color="red", annotation_text="FIRE Goal")
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_treemap:
        st.subheader("🗺️ 資產板塊 (Asset Treemap)")
        treemap_data = [
            {'Asset': '美股 (Stocks)', 'Parent': '投資組合', 'Value': val_stock, 'Color': '#FF4B4B'},
            {'Asset': '歐股/ETF (ETFs)', 'Parent': '投資組合', 'Value': val_etf, 'Color': '#FFA500'},
            {'Asset': '加密貨幣 (Crypto)', 'Parent': '投資組合', 'Value': val_crypto, 'Color': '#9370DB'},
            {'Asset': '不動產 (Real Estate)', 'Parent': '防禦資產', 'Value': val_real_estate, 'Color': '#00CC96'},
            {'Asset': '台幣現金 (TWD Cash)', 'Parent': '防禦資產', 'Value': val_twd_cash, 'Color': '#00CC96'},
            {'Asset': '外幣現金 (FX Cash)', 'Parent': '防禦資產', 'Value': val_foreign_cash, 'Color': '#00CC96'},
            {'Asset': '汽車 (Car)', 'Parent': '消費資產', 'Value': val_car, 'Color': '#808080'},
            {'Asset': '其他', 'Parent': '其他', 'Value': val_other, 'Color': '#808080'},
            {'Asset': '投資組合', 'Parent': '總資產', 'Value': 0, 'Color': 'lightgrey'},
            {'Asset': '防禦資產', 'Parent': '總資產', 'Value': 0, 'Color': 'lightgrey'},
            {'Asset': '消費資產', 'Parent': '總資產', 'Value': 0, 'Color': 'lightgrey'},
            {'Asset': '其他', 'Parent': '總資產', 'Value': 0, 'Color': 'lightgrey'},
            {'Asset': '總資產', 'Parent': '', 'Value': 0, 'Color': 'white'}
        ]
        df_tree = pd.DataFrame(treemap_data)
        df_tree = df_tree[(df_tree['Value'] > 0) | (df_tree['Parent'] == '') | (df_tree['Parent'] == '總資產')]
        
        fig_tree = px.treemap(df_tree, names='Asset', parents='Parent', values='Value',
                              color='Parent', color_discrete_map={'(?)':'#262730', '投資組合':'#FF4B4B', '防禦資產':'#00CC96', '消費資產':'#808080'})
        fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0))
        st.plotly_chart(fig_tree, use_container_width=True)

    # --- Row 3: 進階分析 (Waterfall & Radar) ---
    col_water, col_radar = st.columns(2)

    with col_water:
        st.subheader("💧 成本 vs. 市值 (P&L Waterfall)")
        fig_water = go.Figure(go.Waterfall(
            name = "20", orientation = "v",
            measure = ["relative", "relative", "relative", "relative", "relative", "total"],
            x = ["投入成本", "股票損益", "ETF損益", "加密損益(估)", "其他損益", "目前淨值"],
            textposition = "outside",
            text = [f"{total_cost_basis/10000:.0f}萬", f"{val_stock-cost_stock:,.0f}", f"{val_etf-cost_etf:,.0f}", f"{val_crypto-cost_crypto:,.0f}", "", f"{total_market_value/10000:.0f}萬"],
            y = [total_cost_basis, val_stock-cost_stock, val_etf-cost_etf, val_crypto-cost_crypto, 0, total_market_value],
            connector = {"line":{"color":"rgb(63, 63, 63)"}},
        ))
        fig_water.update_layout(template="plotly_dark", showlegend=False)
        st.plotly_chart(fig_water, use_container_width=True)

    with col_radar:
        st.subheader("🌍 貨幣曝險分析 (Currency Risk)")
        usd_exposure = val_stock + val_crypto
        eur_exposure = val_etf + val_foreign_cash
        twd_exposure = val_twd_cash + val_real_estate + val_other + val_car
        
        df_curr = pd.DataFrame({
            'Currency': ['USD (美元)', 'EUR (歐元)', 'TWD (台幣)'],
            'Value': [usd_exposure, eur_exposure, twd_exposure]
        })
        fig_radar = px.pie(df_curr, values='Value', names='Currency', hole=0.6,
                           color='Currency', color_discrete_map={'USD (美元)':'#00CC96', 'EUR (歐元)':'#636EFA', 'TWD (台幣)':'#EF553B'})
        fig_radar.update_layout(showlegend=True)
        st.plotly_chart(fig_radar, use_container_width=True)

    # --- Row 4: 預測模型 ---
    st.divider()
    st.subheader(f"🔮 未來 {forecast_years} 年資產模擬 (含汽車折舊)")
    
    current_date = latest['日期']
    forecast_months = forecast_years * 12
    future_data = []
    
    # 預測邏輯：投資資產複利 + 汽車折舊
    curr_investable = total_market_value - val_car
    curr_car = val_car
    monthly_rate = annual_growth / 100 / 12
    depreciation_monthly = car_depreciation_rate / 100 / 12

    for i in range(1, forecast_months + 1):
        future_date = current_date + relativedelta(months=i)
        curr_investable = (curr_investable * (1 + monthly_rate)) + monthly_contribution
        curr_car = curr_car * (1 - depreciation_monthly)
        if curr_car < 0: curr_car = 0
        total_forecast = curr_investable + curr_car
        future_data.append({'日期': future_date, 'Effective_Asset': total_forecast})

    df_forecast = pd.DataFrame(future_data)
    df_history = df_total[['日期', 'Effective_Asset']].copy()
    df_history['Type'] = '歷史紀錄'
    df_forecast['Type'] = '未來預測'
    df_combined = pd.concat([df_history, df_forecast])
    
    fig_forecast = px.line(df_combined, x='日期', y='Effective_Asset', color='Type',
                           title=f'模擬情境: 年化 {annual_growth}% vs 汽車折舊 {car_depreciation_rate}%', 
                           template="plotly_dark",
                           color_discrete_map={'歷史紀錄': '#00CC96', '未來預測': '#FFA500'})
    fig_forecast.update_traces(selector=dict(name='未來預測'), line=dict(dash='dot'))
    st.plotly_chart(fig_forecast, use_container_width=True)
    
    final_val = df_forecast.iloc[-1]['Effective_Asset']
    years_to_fire = (fire_goal - total_market_value) / ( (monthly_contribution * 12) + (total_market_value * annual_growth/100) ) 
    years_to_fire = max(0, years_to_fire)
    
    st.success(f"""
    🎯 **戰情室推演：** 在年化報酬 **{annual_growth}%** 且每月存 **${monthly_contribution:,.0f}** 的情況下，
    {forecast_years} 年後總淨值約 **${final_val:,.0f}**。
    粗略估計，距離你的 FIRE 目標可能還需要 **{years_to_fire:.1f} 年**。
    """)

    # Debug
    with st.expander("🔍 數據除錯 (Debug)"):
        st.write("最新有效日期:", latest['日期'])
        st.dataframe(df_total.tail(5))

else:
    st.warning("⚠️ 讀取失敗，請確認 secrets.toml 設定。")