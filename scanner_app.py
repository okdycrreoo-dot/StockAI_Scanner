import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import time
import json
import re
import random

# --- 1. 頁面配置 ---
st.set_page_config(page_title="StockAI Scanner Pro V2.2", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    .rank-card { 
        background: #161B22; border: 1px solid #30363D; border-radius: 12px; 
        padding: 20px; margin-bottom: 15px; border-left: 10px solid #00F5FF;
    }
    .buy-label { color: #FF3131; font-weight: 900; font-size: 1.2rem; }
    .sell-label { color: #00FF41; font-weight: 900; font-size: 1.2rem; }
    .profit-badge { background: #00F5FF; color: #000; padding: 4px 12px; border-radius: 20px; font-weight: 900; float: right; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Google Sheets 批次同步引擎 ---
def sync_to_sheets_bulk(updates_dict):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        raw_val = st.secrets["connections"]["gsheets"]["service_account"]
        clean_str = str(raw_val).strip().strip("'").strip('"').replace('\\\\n', '\n').replace('\\n', '\n')
        pk_search = re.search(r"-----BEGIN PRIVATE KEY-----[\s\S]*?-----END PRIVATE KEY-----", clean_str)
        pk_content = pk_search.group(0).replace('\\n', '\n') if pk_search else ""
        
        creds_dict = {
            "type": "service_account",
            "project_id": "stockai-483605",
            "private_key_id": "4fb59840f128b6317f6b7d8f96993f089465790c",
            "private_key": pk_content,
            "client_email": "stockai@stockai-483605.iam.gserviceaccount.com",
            "token_uri": "https://oauth2.googleapis.com/token"
        }
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ss_url = str(raw_url).replace('\n', '').replace('\r', '').replace(' ', '').strip().strip('"').strip("'")
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(ss_url)
        ws = sh.get_worksheet(0)
        
        all_data = ws.get_all_values()
        existing_keys = {row[0]: i+1 for i, row in enumerate(all_data) if row}
        for key, val in updates_dict.items():
            if key in existing_keys:
                ws.update_cell(existing_keys[key], 2, str(val))
            else:
                ws.append_row([str(key), str(val)])
    except: pass

# --- 3. 自動抓取清單 ---
@st.cache_data(ttl=86400)
def get_taiwan_stock_pool():
    urls = {"TW": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", "TWO": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"}
    pool = []
    for suffix, url in urls.items():
        try:
            res = requests.get(url, timeout=10)
            dfs = pd.read_html(res.text)
            df = dfs[0]
            df.columns = df.iloc[0]
            for item in df.iloc[1:]['有價證券代號及名稱']:
                if isinstance(item, str) and '\u3000' in item:
                    code = item.split('\u3000')[0]
                    if len(code) == 4 and code.isdigit(): pool.append(f"{code}.{suffix}")
        except: continue
    return pool

# --- 4. AI 核心引擎 ---
def perform_ai_prediction(df, v_comp):
    try:
        close_data = df['Close']
        curr_p = float(close_data.iloc[-1])
        returns = df['Close'].pct_change().dropna()
        vol = float(returns.std()) * v_comp
        sims = 200
        daily_returns = np.random.normal(0.005, vol, (sims, 20))
        paths = curr_p * np.exp(np.cumsum(daily_returns, axis=1))
        avg_path = np.mean(paths, axis=0)
        return curr_p * 0.985, float(np.max(avg_path)), int(np.argmax(avg_path) + 1)
    except: return 0, 0, 0

# --- 5. 主程式 ---
def main():
    st.markdown("<h1 style='text-align:center;'>🏆 StockAI V2.2 全時段掃描器</h1>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("⚙️ AI 管理面板")
        scan_limit = st.slider("掃描數量", 5, 100, 10)
        ai_sensitivity = st.slider("AI 敏感度", 0.5, 2.0, 1.15)
        st.info("💡 非開盤時段亦可執行掃描分析。")

    if st.button("🚀 啟動全市場分析"):
        pool = get_taiwan_stock_pool()
        results = []
        bar = st.progress(0)
        status_msg = st.empty()
        
        for i, sym in enumerate(pool[:scan_limit]):
            status_msg.text(f"📡 正在獲取歷史數據 ({i+1}/{scan_limit}): {sym}")
            
            # --- 強力抓取邏輯 (V2.2) ---
            data = pd.DataFrame()
            retry_count = 0
            while data.empty and retry_count < 3: # 最多重試 3 次
                try:
                    # 改用 history 並強制抓取 1 年數據確保盤後數據完整
                    ticker = yf.Ticker(sym)
                    data = ticker.history(period="1y", interval="1d", timeout=25)
                    if data.empty:
                        time.sleep(random.uniform(3, 5)) # 失敗則延長等待
                        retry_count += 1
                except:
                    time.sleep(5)
                    retry_count += 1
            
            if not data.empty and len(data) > 20:
                buy, sell, days = perform_ai_prediction(data, ai_sensitivity)
                if buy > 0:
                    results.append({"id": sym, "buy": buy, "sell": sell, "days": days, "profit": (sell-buy)/buy})
            
            time.sleep(random.uniform(2, 4)) # 基礎防護延遲
            bar.progress((i+1)/scan_limit)
            
        if results:
            top_list = sorted(results, key=lambda x: x['profit'], reverse=True)[:30]
            status_msg.success("✅ 分析完成！已生成獲利名單")
            sync_to_sheets_bulk({"last_scan": datetime.now().strftime("%Y-%m-%d %H:%M"), "top_1": top_list[0]['id']})
            for item in top_list:
                st.markdown(f"<div class='rank-card'><span class='profit-badge'>{item['profit']:.2%}</span><h3>{item['id']}</h3><p>買入: {item['buy']:.2f} | 目標: {item['sell']:.2f} | 預計: {item['days']}天</p></div>", unsafe_allow_html=True)
        else:
            st.error("❌ 仍被 Yahoo 頻率限制鎖定。請嘗試將掃描數量設為 5，或等待 10 分鐘後再試。")

if __name__ == "__main__":
    main()
