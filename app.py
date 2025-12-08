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

# --- CSS 優化 (讓圖表背景更融合) ---
st.markdown("""
<style>
    .stMetric {
        background-color: #1E1E1E;
        border: 1px solid #333;
        padding: 15px;
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 讀取 Secrets ---
try:
    SPREADSHEET_URL = st.secrets["data"]["sheet_url"]
except KeyError:
    st.error("⚠️ Secrets Error")
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
                cleaned = df_total[col].astype(str).str.replace(',', '', regex=False)
                df_total[col] = cleaned.apply(lambda x: re.sub(r'[^\d\.\-]', '', x))
                df_total[col] = pd.to_numeric(df_total[col], errors='coerce').fillna(0)
            else:
                df_total[col] = 0

        df_total['日期'] = pd.to_datetime(df_total['日期'], errors='coerce')
        
        # 建立有效資產 (優先取真實總資產)
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
    usd_rate = latest.get('USDTWD', 32.5) if latest.get('USDTWD', 0) > 10 else 32.5
    eur_rate = latest.get('EURTWD', 35.0) if latest.get('EURTWD', 0) > 10 else 35.0
    
    # --- 資產價值 (Market Value) ---
    stock_val = latest.get('股票價值(USD)', 0) * usd_rate
    if stock_val == 0: stock_val = latest.get('股票成本(USD)', 0) * usd_rate # Fallback
    
    etf_val = latest.get('ETF價值(EUR)', 0) * eur_rate
    if etf_val == 0: etf_val = latest.get('ETF(EUR)', 0) * eur_rate # Fallback

    crypto_val = latest.get('加密貨幣(USD)', 0) * usd_rate
    fx_cash_val = latest.get('外幣現金(EUR)', 0) * eur_rate
    twd_cash_val = latest.get('台幣現金(TWD)', 0)
    real_estate_val = latest.get('不動產(TWD)', 0)
    other_val = latest.get('其他(TWD)', 0)
    car_val = latest.get('汽車預估價格(GPT模型)', 0)

    # --- 資產成本 (Cost Basis) ---
    stock_cost = latest.get('股票成本(USD)', 0) * usd_rate
    etf_cost = latest.get('ETF(EUR)', 0) * eur_rate
    # 假設: 現金/房產/其他 成本=現值 (為了計算方便)
    
    total_market_val = latest['Effective_Asset']
    
    # --- 側邊欄 ---
    with st.sidebar:
        st.header("⚙️ 參數設定")
        fire_goal = st.number_input("🎯 FIRE 目標 (TWD)", value=50000000, step=1000000)
        st.divider()
        monthly_expense = st.number_input("退休後月開銷 (TWD)", value=100000, step=5000)
        st.divider()
        forecast_years = st.slider("模擬年數", 1, 15, 5)
        annual_growth = st.slider("預期年化報酬 (CAGR %)", 0.0, 20.0, 7.0, 0.5)
        
        df_gains = df_total[df_total['總資產增額(TWD)'] > 0]
        hist_avg_gain = df_gains['總資產增額(TWD)'].mean() if not df_gains.empty else 50000
        monthly_contribution = st.number_input("每月投入 (TWD)", value=int(hist_avg_gain), step=5000)
        
        if st.button("🔄 刷新"):
            st.cache_data.clear()
            st.rerun()

    # --- Row 1: KPI ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        diff = latest['Effective_Asset'] - prev['Effective_Asset']
        pct = (diff / prev['Effective_Asset']) * 100 if prev['Effective_Asset'] != 0 else 0
        st.metric("💰 真實總淨值", f"${total_market_val:,.0f}", f"{diff:,.0f} ({pct:.2f}%)")
    with col2:
        fire_pct = (total_market_val / fire_goal) * 100
        st.metric("🎯 FIRE 進度", f"{fire_pct:.2f}%", f"差 ${fire_goal - total_market_val:,.0f}", delta_color="inverse")
    with col3:
        runway = total_market_val / (monthly_expense * 12)
        st.metric("⏳ 財務跑道", f"{runway:.1f} 年", f"月開銷 ${monthly_expense:,.0f}")
    with col4:
        passive = (total_market_val * 0.04) / 12
        st.metric("🛡️ 4%法則月收", f"${passive:,.0f}", f"目標: ${monthly_expense:,.0f}")

    st.divider()

    # --- Row 2: 核心圖表 ---
    col_main, col_tree = st.columns([1.8, 1.2])

    with col_main:
        st.subheader("📈 歷史淨值走勢 (History)")
        # [視覺優化 1] 移除 FIRE 線，讓曲線自動適應 Y 軸
        fig_trend = px.line(df_total, x='日期', y='Effective_Asset', markers=True, template="plotly_dark")
        fig_trend.update_traces(connectgaps=True, line=dict(color='#00CC96', width=3))
        # 加入滑桿，方便縮放細節
        fig_trend.update_layout(
            xaxis=dict(rangeslider=dict(visible=True), type="date"),
            margin=dict(l=20, r=20, t=20, b=20),
            height=400
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with col_tree:
        st.subheader("🗺️ 資產板塊 (Asset Map)")
        # [視覺優化 2] 確保 Treemap 結構正確
        # 構建父子關係
        assets = [
            # ID, Label, Parent, Value, Color
            ('Total', '總資產', '', 0, 'lightgrey'),
            ('Invest', '投資組合', 'Total', 0, '#FF4B4B'),
            ('Defense', '防禦/現金', 'Total', 0, '#00CC96'),
            ('Consump', '消費/其他', 'Total', 0, '#808080'),
            
            ('US_Stock', '美股', 'Invest', stock_val, '#FF4B4B'),
            ('EU_ETF', '歐股 ETF', 'Invest', etf_val, '#FFA500'),
            ('Crypto', '加密貨幣', 'Invest', crypto_val, '#9370DB'),
            
            ('RealEstate', '不動產', 'Defense', real_estate_val, '#2E8B57'),
            ('TWD_Cash', '台幣現金', 'Defense', twd_cash_val, '#00CC96'),
            ('FX_Cash', '外幣現金', 'Defense', fx_cash_val, '#20B2AA'),
            
            ('Car', '汽車', 'Consump', car_val, '#708090'),
            ('Other', '其他', 'Consump', other_val, '#A9A9A9'),
        ]
        
        df_tree = pd.DataFrame(assets, columns=['ID', 'Label', 'Parent', 'Value', 'Color'])
        # 移除值為 0 的子項目 (保留 Parent)
        df_tree = df_tree[ (df_tree['Value'] > 0) | (df_tree['Parent'] == '') | (df_tree['Parent'] == 'Total') ]

        fig_tree = go.Figure(go.Treemap(
            ids = df_tree['ID'],
            labels = df_tree['Label'],
            parents = df_tree['Parent'],
            values = df_tree['Value'],
            marker = dict(colors=df_tree['Color']),
            branchvalues = "total",
            textinfo = "label+value+percent parent"
        ))
        fig_tree.update_layout(margin=dict(t=0, l=0, r=0, b=0), height=400)
        st.plotly_chart(fig_tree, use_container_width=True)

    # --- Row 3: 損益與貨幣 ---
    col_pnl, col_curr = st.columns(2)

    with col_pnl:
        st.subheader("📊 未實現損益 (P&L Breakdown)")
        # [視覺優化 3] 改用橫向長條圖展示損益，解決瀑布圖比例問題
        
        # 計算各項損益 (簡單估算)
        pnl_data = {
            '美股': stock_val - stock_cost,
            'ETF': etf_val - etf_cost,
            '加密貨幣': crypto_val * 0.2, # 假設 20% 獲利 (因無成本數據)
            # 不動產/現金 視為 0 損益或尚未實現
        }
        
        df_pnl = pd.DataFrame(list(pnl_data.items()), columns=['Asset', 'PnL'])
        df_pnl['Color'] = np.where(df_pnl['PnL'] >= 0, '#00CC96', '#FF4B4B') # 綠漲紅跌
        
        fig_pnl = px.bar(df_pnl, x='PnL', y='Asset', orientation='h', text='PnL',
                         title="各類資產損益貢獻 (估)", template="plotly_dark")
        fig_pnl.update_traces(marker_color=df_pnl['Color'], texttemplate='%{text:,.0f}', textposition='auto')
        st.plotly_chart(fig_pnl, use_container_width=True)

    with col_curr:
        st.subheader("🌍 貨幣曝險 (Currency Risk)")
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
    st.subheader(f"🔮 未來 {forecast_years} 年資產模擬")
    
    # 這裡的預測線可以保留 FIRE Goal 線，因為是看未來
    curr_date = latest['日期']
    months = forecast_years * 12
    
    # 預測邏輯 (簡化版：總淨值成長)
    # Investable gets growth, Car gets depreciation
    investable = total_market_val - car_val
    curr_car = car_val
    m_rate = annual_growth / 100 / 12
    m_car_dep = 0.15 / 12 # 預設 15% 折舊
    
    future_vals = []
    for i in range(1, months + 1):
        d = curr_date + relativedelta(months=i)
        investable = (investable * (1 + m_rate)) + monthly_contribution
        curr_car = curr_car * (1 - m_car_dep)
        total = investable + max(0, curr_car)
        future_vals.append({'日期': d, 'Effective_Asset': total})
        
    df_fut = pd.DataFrame(future_vals)
    df_hist = df_total[['日期', 'Effective_Asset']].copy()
    df_hist['Type'] = 'History'
    df_fut['Type'] = 'Forecast'
    df_final = pd.concat([df_hist, df_fut])
    
    fig_cast = px.line(df_final, x='日期', y='Effective_Asset', color='Type', 
                       template="plotly_dark", color_discrete_map={'History': '#00CC96', 'Forecast': '#FFA500'})
    
    # 在預測圖加上 FIRE 線
    fig_cast.add_hline(y=fire_goal, line_dash="dot", line_color="red", annotation_text=f"FIRE Goal: ${fire_goal/10000:.0f}萬")
    
    st.plotly_chart(fig_cast, use_container_width=True)
    
    final_v = df_fut.iloc[-1]['Effective_Asset']
    st.success(f"🎯 **預測結果：** {forecast_years} 年後資產約 **${final_v:,.0f}** (CAGR {annual_growth}%)")

else:
    st.warning("⚠️ 讀取失敗")