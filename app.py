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

# --- 讀取數據函數 ---
@st.cache_data(ttl=10) 
def load_data(url):
    try:
        df_total = pd.read_csv(url, header=1) 
        df_total.columns = df_total.columns.str.strip() 
        
        # 定義所有相關欄位
        target_cols = [
            '真實總資產(TWD)', '總資產(TWD)',
            '股票價值(USD)', '股票成本(USD)',
            'ETF價值(EUR)', 'ETF(EUR)',
            '台幣現金(TWD)', '外幣現金(EUR)', '不動產(TWD)', 
            '加密貨幣(USD)', '其他(TWD)', 
            'USDTWD', 'EURTWD', '總資產增額(TWD)'
        ]
        
        # 1. 數值清洗 (全面轉為數字，失敗填 0)
        for col in target_cols:
            if col in df_total.columns:
                df_total[col] = df_total[col].astype(str).apply(
                    lambda x: re.sub(r'[^\d\.\-]', '', x)
                )
                df_total[col] = pd.to_numeric(df_total[col], errors='coerce').fillna(0)
            else:
                df_total[col] = 0

        # 2. [關鍵邏輯] 建立「最終顯示資產」欄位
        # 邏輯：優先使用 '真實總資產(TWD)'，如果該月資料為 0 (歷史未填)，則回退使用 '總資產(TWD)'
        # 這樣可以確保曲線圖在歷史部分不斷掉，而最新部分顯示真實價值
        df_total['Display_Assets'] = np.where(
            df_total['真實總資產(TWD)'] > 0, 
            df_total['真實總資產(TWD)'], 
            df_total['總資產(TWD)']
        )

        # 3. 過濾無效列 (使用 Display_Assets 判斷)
        df_total = df_total.dropna(subset=['日期']).copy()
        df_total = df_total[df_total['Display_Assets'] != 0].copy()
        
        # 4. 日期排序
        df_total['日期'] = pd.to_datetime(df_total['日期'], errors='coerce')
        df_total = df_total.sort_values('日期').reset_index(drop=True)
        
        return df_total
    except Exception as e:
        st.error(f"⚠️ 數據讀取錯誤: {e}") 
        return pd.DataFrame() 

df_total = load_data(SPREADSHEET_URL)

# --- 介面呈現 ---
st.title("🔥 Jeffy 的 FIRE 戰情室 - Pro Valuation Edition")

if not df_total.empty and len(df_total) > 0:
    
    # --- 基礎數據 ---
    latest = df_total.iloc[-1]
    prev = df_total.iloc[-2] if len(df_total) > 1 else latest
    
    # 匯率防呆
    raw_usd_rate = latest.get('USDTWD', 0)
    raw_eur_rate = latest.get('EURTWD', 0)
    usd_rate = raw_usd_rate if raw_usd_rate > 10 else 31.5
    eur_rate = raw_eur_rate if raw_eur_rate > 10 else 36.2
    
    # --- 資產價值計算 (優先使用真實價值) ---
    stock_usd_col = '股票價值(USD)' if latest.get('股票價值(USD)', 0) > 0 else '股票成本(USD)'
    etf_eur_col = 'ETF價值(EUR)' if latest.get('ETF價值(EUR)', 0) > 0 else 'ETF(EUR)'
    
    val_stock = latest.get(stock_usd_col, 0) * usd_rate
    val_etf = latest.get(etf_eur_col, 0) * eur_rate
    val_crypto = latest.get('加密貨幣(USD)', 0) * usd_rate
    val_foreign_cash = latest.get('外幣現金(EUR)', 0) * eur_rate
    val_twd_cash = latest.get('台幣現金(TWD)', 0)
    val_real_estate = latest.get('不動產(TWD)', 0)
    val_other = latest.get('其他(TWD)', 0)
    
    # --- [關鍵修改] 總資產使用 Smart Merge 後的欄位 ---
    current_assets = latest['Display_Assets']
    prev_assets = prev['Display_Assets']
    
    # KPI 計算
    month_diff = current_assets - prev_assets
    growth_rate = (month_diff / prev_assets) * 100 if prev_assets != 0 else 0
    
    # 歷史平均月儲蓄
    df_gains = df_total[df_total['總資產增額(TWD)'] > 0]
    historical_avg_gain = df_gains['總資產增額(TWD)'].mean() if not df_gains.empty else 50000

    # --- 側邊欄：進階模型設定 ---
    with st.sidebar:
        st.header("⚙️ 參數設定")
        fire_goal = st.number_input("🎯 FIRE 目標 (TWD)", value=100000000, step=10000000)
        st.divider()
        
        st.subheader("🔮 分析師估值模型 (SOP)")
        forecast_years = st.slider("模擬未來年數", 1, 20, 5)

        scenario = st.selectbox(
            "選擇分析師/市場情境",
            ("自訂 (Custom)", 
             "Cathie Wood (Ark Invest) - 科技牛市", 
             "Wall Street Consensus - 華爾街共識", 
             "Ray Dalio (All Weather) - 穩健防禦", 
             "Michael Burry (The Big Short) - 衰退修正")
        )

        if scenario == "Cathie Wood (Ark Invest) - 科技牛市":
            def_stock_rate, def_etf_rate, def_safe_rate = 25.0, 12.0, 2.0
        elif scenario == "Wall Street Consensus - 華爾街共識":
            def_stock_rate, def_etf_rate, def_safe_rate = 12.0, 8.0, 1.5
        elif scenario == "Ray Dalio (All Weather) - 穩健防禦":
            def_stock_rate, def_etf_rate, def_safe_rate = 6.0, 5.0, 1.5
        elif scenario == "Michael Burry (The Big Short) - 衰退修正":
            def_stock_rate, def_etf_rate, def_safe_rate = -10.0, -5.0, 1.0
        else: 
            def_stock_rate, def_etf_rate, def_safe_rate = 15.0, 7.0, 1.0

        st.markdown("**各類資產預期年化報酬率 (CAGR)**")
        col_s1, col_s2 = st.columns(2)
        rate_stock = col_s1.number_input("個股 (NVDA/TSLA)", value=def_stock_rate, step=0.5, format="%.1f")
        rate_etf = col_s2.number_input("ETF (大盤)", value=def_etf_rate, step=0.5, format="%.1f")
        
        col_s3, col_s4 = st.columns(2)
        rate_crypto = col_s3.number_input("加密貨幣", value=rate_stock if scenario != "自訂 (Custom)" else 20.0, step=1.0, format="%.1f")
        rate_safe = col_s4.number_input("房產/現金", value=def_safe_rate, step=0.1, format="%.1f")

        monthly_contribution = st.number_input(
            "每月投入資金 (TWD)", 
            value=int(historical_avg_gain), 
            step=5000
        )
        
        if st.button("🔄 刷新數據"):
            st.cache_data.clear()
            st.rerun()

    # --- 邏輯運算：計算加權成長率 ---
    # 分母使用 Display_Assets 確保一致性
    total_val = current_assets if current_assets > 0 else 1
    
    w_stock = val_stock / total_val
    w_etf = val_etf / total_val
    w_crypto = val_crypto / total_val
    w_safe = (val_twd_cash + val_foreign_cash + val_real_estate + val_other) / total_val
    
    # 確保權重總和不超過 1 (因四捨五入或資料誤差)
    weight_sum = w_stock + w_etf + w_crypto + w_safe
    if weight_sum > 0:
        w_stock /= weight_sum
        w_etf /= weight_sum
        w_crypto /= weight_sum
        w_safe /= weight_sum
    
    weighted_cagr = (w_stock * rate_stock) + (w_etf * rate_etf) + (w_crypto * rate_crypto) + (w_safe * rate_safe)

    # --- KPI 區塊 ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        # 這裡明確顯示是 "真實總資產"
        st.metric("💰 真實總資產 (TWD)", f"${current_assets:,.0f}", f"{month_diff:,.0f} ({growth_rate:.2f}%)")
    with col2:
        st.metric("📊 投資組合隱含CAGR", f"{weighted_cagr:.2f}%", f"情境: {scenario.split('-')[0]}")
    with col3:
        passive_monthly = (current_assets * 0.04) / 12
        st.metric("🛌 4%法則月收", f"${passive_monthly:,.0f}")
    with col4:
        total_eur_est = current_assets / eur_rate
        st.metric("🇪🇺 總資產 (EUR)", f"€{total_eur_est:,.0f}", f"Rate: {eur_rate}")

    st.divider()

    # --- 圖表與表格區 ---
    col_chart1, col_chart2 = st.columns([2, 1])

    with col_chart1:
        st.subheader("📈 資產累積趨勢 (真實價值)")
        # [關鍵] 曲線圖改用 Display_Assets
        fig_trend = px.line(df_total, x='日期', y='Display_Assets', markers=True, title='Net Worth Growth (Real Value)', template="plotly_dark")
        fig_trend.update_traces(line_color='#00CC96', line_width=3)
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_chart2:
        st.subheader("🍰 資產權重分布")
        
        assets_dict_detail = {
            '不動產': val_real_estate,
            '美股 (市值)': val_stock, 
            '台幣現金': val_twd_cash,
            '歐股/ETF (市值)': val_etf, 
            '外幣現金': val_foreign_cash,
            '加密貨幣': val_crypto,
            '其他': val_other
        }
        
        df_display = pd.DataFrame([
            {'資產種類': k, '金額(TWD)': v, 'Raw_Value': v} 
            for k, v in assets_dict_detail.items() if v > 0
        ])
        
        if not df_display.empty:
            total_display_val = df_display['Raw_Value'].sum()
            df_display['占比(%)'] = (df_display['Raw_Value'] / total_display_val * 100)
            df_display = df_display.sort_values(by='Raw_Value', ascending=False)
            
            # 1. 圓餅圖
            fig_pie = px.pie(df_display, values='Raw_Value', names='資產種類', hole=0.4, 
                             color_discrete_sequence=px.colors.sequential.RdBu)
            st.plotly_chart(fig_pie, use_container_width=True)
            
            # 2. 表格
            df_table = df_display[['資產種類', '金額(TWD)', '占比(%)']].copy()
            df_table['金額(TWD)'] = df_table['金額(TWD)'].map('${:,.0f}'.format)
            df_table['占比(%)'] = df_table['占比(%)'].map('{:.2f}%'.format)
            
            st.dataframe(df_table, use_container_width=True, hide_index=True)
        else:
            st.warning("無有效資產數據")

    # --- 預測模型區 ---
    st.divider()
    st.subheader(f"🔮 {forecast_years} 年資產模擬 (加權成分成長模型)")
    st.info(f"""
    **模型邏輯：**
    - **{w_stock*100:.1f}%** 在個股 (預估成長 {rate_stock}%)
    - **{w_etf*100:.1f}%** 在 ETF (預估成長 {rate_etf}%)
    - **{w_safe*100:.1f}%** 在防禦資產 (預估成長 {rate_safe}%)
    👉 **綜合年化成長率 (Weighted CAGR): {weighted_cagr:.2f}%**
    """)

    current_date = latest['日期']
    forecast_months = forecast_years * 12
    future_data = []
    
    # 預測初始值 (使用真實價值)
    curr_stock = val_stock
    curr_etf = val_etf
    curr_crypto = val_crypto
    curr_safe = val_twd_cash + val_foreign_cash + val_real_estate + val_other
    
    # 投入分配
    monthly_in_stock = monthly_contribution * w_stock
    monthly_in_etf = monthly_contribution * w_etf
    monthly_in_crypto = monthly_contribution * w_crypto
    monthly_in_safe = monthly_contribution * w_safe

    for i in range(1, forecast_months + 1):
        future_date = current_date + relativedelta(months=i)
        
        # 分項複利
        curr_stock = (curr_stock * (1 + rate_stock/100/12)) + monthly_in_stock
        curr_etf = (curr_etf * (1 + rate_etf/100/12)) + monthly_in_etf
        curr_crypto = (curr_crypto * (1 + rate_crypto/100/12)) + monthly_in_crypto
        curr_safe = (curr_safe * (1 + rate_safe/100/12)) + monthly_in_safe
        
        total_forecast = curr_stock + curr_etf + curr_crypto + curr_safe
        future_data.append({'日期': future_date, 'Display_Assets': total_forecast})

    df_forecast = pd.DataFrame(future_data)
    
    df_history = df_total[['日期', 'Display_Assets']].copy()
    df_history['Type'] = '歷史紀錄'
    df_forecast['Type'] = '未來預測'
    df_combined = pd.concat([df_history, df_forecast])
    
    fig_forecast = px.line(df_combined, x='日期', y='Display_Assets', color='Type',
                           title=f'情境模擬: {scenario} (綜合 CAGR {weighted_cagr:.2f}%)', 
                           template="plotly_dark",
                           color_discrete_map={'歷史紀錄': '#00CC96', '未來預測': '#FFA500'})
    fig_forecast.update_traces(selector=dict(name='未來預測'), line=dict(dash='dot'))
    st.plotly_chart(fig_forecast, use_container_width=True)
    
    final_val = df_forecast.iloc[-1]['Display_Assets']
    st.success(f"🎯 **模擬結果：** {forecast_years} 年後總資產預估 **${final_val:,.0f} TWD**。")

    with st.expander("查看原始數據"):
        st.dataframe(df_total.tail(10))

else:
    st.warning("⚠️ 讀取失敗，請確認 secrets.toml 設定。")