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

# --- [修復 1] 移除會導致黑底黑字的 CSS ---
# 這裡不再強制設定背景色，讓 Streamlit 自動適應你的瀏覽器主題 (深色/淺色)

# --- 讀取 Secrets ---
try:
    SPREADSHEET_URL = st.secrets["data"]["sheet_url"]
except KeyError:
    st.error("⚠️ Secrets Error: 請檢查 secrets.toml")
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
                # 強力清洗：先除逗號，再除雜訊
                cleaned = df_total[col].astype(str).str.replace(',', '', regex=False)
                df_total[col] = cleaned.apply(lambda x: re.sub(r'[^\d\.\-]', '', x))
                df_total[col] = pd.to_numeric(df_total[col], errors='coerce').fillna(0)
            else:
                df_total[col] = 0

        df_total['日期'] = pd.to_datetime(df_total['日期'], errors='coerce')
        
        # 建立有效資產
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

if not df_total.empty and len(df_total) > 0:
    
    # --- 基礎數據準備 ---
    latest = df_total.iloc[-1]
    prev = df_total.iloc[-2] if len(df_total) > 1 else latest
    
    # 匯率
    usd_rate = latest.get('USDTWD', 32.5) if latest.get('USDTWD', 0) > 10 else 31.5
    eur_rate = latest.get('EURTWD', 35.0) if latest.get('EURTWD', 0) > 10 else 36.0
    
    # --- 資產價值 (Market Value) ---
    stock_val = latest.get('股票價值(USD)', 0) * usd_rate
    if stock_val == 0: stock_val = latest.get('股票成本(USD)', 0) * usd_rate
    
    etf_val = latest.get('ETF價值(EUR)', 0) * eur_rate
    if etf_val == 0: etf_val = latest.get('ETF(EUR)', 0) * eur_rate

    crypto_val = latest.get('加密貨幣(USD)', 0) * usd_rate
    fx_cash_val = latest.get('外幣現金(EUR)', 0) * eur_rate
    twd_cash_val = latest.get('台幣現金(TWD)', 0)
    real_estate_val = latest.get('不動產(TWD)', 0)
    other_val = latest.get('其他(TWD)', 0)
    car_val = latest.get('汽車預估價格(GPT模型)', 0)

    # 資產成本 (用於損益圖)
    stock_cost = latest.get('股票成本(USD)', 0) * usd_rate
    etf_cost = latest.get('ETF(EUR)', 0) * eur_rate
    
    total_market_val = latest['Effective_Asset']
    
    # --- 側邊欄：還原 V01 設定 ---
    with st.sidebar:
        st.header("⚙️ 戰情室參數")
        fire_goal = st.number_input("🎯 FIRE 目標 (TWD)", value=100000000, step=10000000)
        st.divider()
        monthly_expense = st.number_input("退休後月開銷 (TWD)", value=300000, step=5000)
        
        st.divider()
        st.subheader("🔮 分析師估值模型")
        forecast_years = st.slider("模擬未來年數", 1, 25, 5)

        # 1. 情境選擇
        scenario = st.selectbox(
            "選擇市場情境",
            ("自訂 (Custom)", 
             "Cathie Wood (Ark Invest) - 科技牛市", 
             "Wall Street Consensus - 華爾街共識", 
             "Ray Dalio (All Weather) - 穩健防禦", 
             "Michael Burry (The Big Short) - 衰退修正")
        )

        # 2. 預設參數
        if "Cathie Wood" in scenario:
            def_stock, def_etf, def_crypto, def_safe = 25.0, 12.0, 50.0, 2.0
        elif "Wall Street" in scenario:
            def_stock, def_etf, def_crypto, def_safe = 10.0, 8.0, 15.0, 1.5
        elif "Ray Dalio" in scenario:
            def_stock, def_etf, def_crypto, def_safe = 6.0, 5.0, 5.0, 2.0
        elif "Michael Burry" in scenario:
            def_stock, def_etf, def_crypto, def_safe = -10.0, -5.0, -20.0, 1.0
        else:
            def_stock, def_etf, def_crypto, def_safe = 15.0, 7.0, 20.0, 1.0

        # 3. 細項設定
        st.markdown("**各類資產預期年化報酬率 (CAGR)**")
        col_s1, col_s2 = st.columns(2)
        rate_stock = col_s1.number_input("個股 (NVDA/TSLA)", value=def_stock, step=0.5, format="%.1f")
        rate_etf = col_s2.number_input("ETF (大盤)", value=def_etf, step=0.5, format="%.1f")
        
        col_s3, col_s4 = st.columns(2)
        rate_crypto = col_s3.number_input("加密貨幣", value=def_crypto, step=1.0, format="%.1f")
        rate_safe = col_s4.number_input("房產/現金", value=def_safe, step=0.1, format="%.1f")
        
        st.markdown("**折舊與投入**")
        car_depreciation_rate = st.slider("汽車年折舊率 (%)", 5.0, 30.0, 15.0, 1.0)
        
        df_gains = df_total[df_total['總資產增額(TWD)'] > 0]
        hist_avg_gain = df_gains['總資產增額(TWD)'].mean() if not df_gains.empty else 50000
        monthly_contribution = st.number_input("每月投入 (TWD)", value=int(hist_avg_gain), step=5000)
        
        if st.button("🔄 刷新"):
            st.cache_data.clear()
            st.rerun()

    # 計算權重
    total_investable = total_market_val - car_val
    if total_investable <= 0: total_investable = 1
    w_stock = stock_val / total_investable
    w_etf = etf_val / total_investable
    w_crypto = crypto_val / total_investable
    w_safe = (twd_cash_val + fx_cash_val + real_estate_val + other_val) / total_investable
    weighted_cagr = (w_stock * rate_stock) + (w_etf * rate_etf) + (w_crypto * rate_crypto) + (w_safe * rate_safe)

    # --- Row 1: KPI ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        diff = latest['Effective_Asset'] - prev['Effective_Asset']
        pct = (diff / prev['Effective_Asset']) * 100 if prev['Effective_Asset'] != 0 else 0
        st.metric("💰 真實總淨值", f"${total_market_val:,.0f}", f"{diff:,.0f} ({pct:.2f}%)")
    with col2:
        st.metric("📊 投資組合隱含CAGR", f"{weighted_cagr:.2f}%", f"情境: {scenario.split('-')[0]}")
    with col3:
        runway = total_market_val / (monthly_expense * 12)
        st.metric("⏳ 財務跑道", f"{runway:.1f} 年", f"月開銷 ${monthly_expense:,.0f}")
    with col4:
        passive = (total_market_val * 0.06) / 12
        st.metric("🛡️ 6%法則月收", f"${passive:,.0f}", f"目標: ${monthly_expense:,.0f}")

    st.divider()

    # --- Row 2: 核心圖表 ---
    col_main, col_tree = st.columns([1.8, 1.2])

    with col_main:
        st.subheader("📈 歷史淨值走勢 (History)")
        fig_trend = px.line(df_total, x='日期', y='Effective_Asset', markers=True, template="plotly_dark")
        fig_trend.update_traces(line=dict(width=3, color='#00CC96'))
        fig_trend.update_layout(
            xaxis=dict(rangeslider=dict(visible=True), type="date"),
            margin=dict(l=20, r=20, t=20, b=20),
            height=400
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_tree:
        st.subheader("🗺️ 資產板塊 (Asset Map)")
        # [修復 2] 改用 px.treemap 自動計算父層級數值，解決顯示為 0 的問題
        treemap_df = pd.DataFrame([
            {'Category': '投資組合', 'Asset': '美股 (Stocks)', 'Value': stock_val},
            {'Category': '投資組合', 'Asset': '歐股/ETF (ETFs)', 'Value': etf_val},
            {'Category': '投資組合', 'Asset': '加密貨幣 (Crypto)', 'Value': crypto_val},
            {'Category': '防禦資產', 'Asset': '不動產 (Real Estate)', 'Value': real_estate_val},
            {'Category': '防禦資產', 'Asset': '台幣現金 (TWD Cash)', 'Value': twd_cash_val},
            {'Category': '防禦資產', 'Asset': '外幣現金 (FX Cash)', 'Value': fx_cash_val},
            {'Category': '消費資產', 'Asset': '汽車 (Car)', 'Value': car_val},
            {'Category': '消費資產', 'Asset': '其他', 'Value': other_val}
        ])
        # 過濾掉 0 的項目
        treemap_df = treemap_df[treemap_df['Value'] > 0]
        
        if not treemap_df.empty:
            fig_tree = px.treemap(treemap_df, path=['Category', 'Asset'], values='Value',
                                  color='Category', color_discrete_map={'投資組合':'#FF4B4B', '防禦資產':'#00CC96', '消費資產':'#808080'})
            fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=400)
            st.plotly_chart(fig_tree, use_container_width=True)
        else:
            st.warning("暫無資產數據可顯示")

    # --- Row 3: 損益與貨幣 ---
    col_pnl, col_curr = st.columns(2)

    with col_pnl:
        st.subheader("📊 未實現損益 (P&L)")
        pnl_data = {
            '美股': stock_val - stock_cost,
            'ETF': etf_val - etf_cost,
            '加密貨幣': crypto_val * 0.0, #TBD 
        }
        df_pnl = pd.DataFrame(list(pnl_data.items()), columns=['Asset', 'PnL'])
        df_pnl['Color'] = np.where(df_pnl['PnL'] >= 0, '#00CC96', '#FF4B4B')
        
        fig_pnl = px.bar(df_pnl, x='PnL', y='Asset', orientation='h', text='PnL',
                         title="各類資產損益貢獻 (估)", template="plotly_dark")
        fig_pnl.update_traces(marker_color=df_pnl['Color'], texttemplate='%{text:,.0f}', textposition='auto')
        st.plotly_chart(fig_pnl, use_container_width=True)

    with col_curr:
        st.subheader("🌍 貨幣曝險")
        usd_exp = stock_val + crypto_val
        eur_exp = etf_val + fx_cash_val
        twd_exp = twd_cash_val + real_estate_val + other_val + car_val
        
        fig_pie = px.pie(
            values=[usd_exp, eur_exp, twd_exp], 
            names=['USD (美元)', 'EUR (歐元)', 'TWD (台幣)'],
            color_discrete_sequence=['#00CC96', '#636EFA', '#EF553B'],
            hole=0.5
        )
        fig_pie.update_layout(showlegend=True, height=350)
        st.plotly_chart(fig_pie, use_container_width=True)

    # --- Row 4: 預測模型 ---
    st.divider()
    st.subheader(f"🔮 未來 {forecast_years} 年資產模擬 (分項複利)")
    
    st.info(f"""
    **模型參數：**
    - 美股成長: **{rate_stock}%** | ETF成長: **{rate_etf}%** | 加密成長: **{rate_crypto}%**
    - 房產/現金成長: **{rate_safe}%** | 汽車折舊: **{car_depreciation_rate}%**
    - 每月投入: **${monthly_contribution:,.0f}**
    """)

    curr_date = latest['日期']
    months = forecast_years * 12
    
    curr_stock = stock_val
    curr_etf = etf_val
    curr_crypto = crypto_val
    curr_safe = twd_cash_val + fx_cash_val + real_estate_val + other_val
    curr_car = car_val * eur_rate
    
    invest_sum = stock_val + etf_val + crypto_val + curr_safe
    if invest_sum == 0: invest_sum = 1
    
    alloc_stock = monthly_contribution * (stock_val / invest_sum)
    alloc_etf = monthly_contribution * (etf_val / invest_sum)
    alloc_crypto = monthly_contribution * (crypto_val / invest_sum)
    alloc_safe = monthly_contribution * (curr_safe / invest_sum)

    future_vals = []
    for i in range(1, months + 1):
        d = curr_date + relativedelta(months=i)
        curr_stock = (curr_stock * (1 + rate_stock/100/12)) + alloc_stock
        curr_etf = (curr_etf * (1 + rate_etf/100/12)) + alloc_etf
        curr_crypto = (curr_crypto * (1 + rate_crypto/100/12)) + alloc_crypto
        curr_safe = (curr_safe * (1 + rate_safe/100/12)) + alloc_safe
        curr_car = curr_car * (1 - car_depreciation_rate/100/12)
        if curr_car < 0: curr_car = 0
        total = curr_stock + curr_etf + curr_crypto + curr_safe + curr_car
        future_vals.append({'日期': d, 'Effective_Asset': total})
        
    df_fut = pd.DataFrame(future_vals)
    df_hist = df_total[['日期', 'Effective_Asset']].copy()
    df_hist['Type'] = 'History'
    df_fut['Type'] = 'Forecast'
    df_final = pd.concat([df_hist, df_fut])
    
    fig_cast = px.line(df_final, x='日期', y='Effective_Asset', color='Type', 
                       template="plotly_dark", color_discrete_map={'History': '#00CC96', 'Forecast': '#FFA500'})
    
    fig_cast.add_hline(y=fire_goal, line_dash="dot", line_color="red", annotation_text=f"FIRE Goal")
    st.plotly_chart(fig_cast, use_container_width=True)
    
    final_v = df_fut.iloc[-1]['Effective_Asset']
    st.success(f"🎯 **預測結果：** {forecast_years} 年後資產約 **${final_v:,.0f}**")

else:
    st.warning("⚠️ 讀取失敗")