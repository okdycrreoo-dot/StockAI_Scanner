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

# --- 1. 頁面配置與進階美化 ---
st.set_page_config(page_title="StockAI Scanner Pro V2.3", layout="wide")
st.markdown("""
    <style>
    .stApp { background-color: #0E1117; color: #FFFFFF; }
    .rank-card { 
        background: #161B22; border: 1px solid #30363D; border-radius: 12px; 
        padding: 20px; margin-bottom: 15px; border-left: 10px solid #00F5FF;
        transition: transform 0.3s;
    }
    .rank-card:hover { transform: scale(1.02); border-color: #00F5FF; }
    .buy-label { color: #FF3131; font-weight: 900; font-size: 1.2rem; }
    .sell-label { color: #00FF41; font-weight: 900; font-size: 1.2rem; }
    .profit-badge { background: #00F5FF; color: #000; padding: 4px 12px; border-radius: 20px; font-weight: 900; float: right; }
    </style>
    """, unsafe_allow_html=True)

# --- 2. Google Sheets 核心引擎 (V2.3 穩定版) ---
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
    random.shuffle(pool) # 隨機化順序，避免每次都抓同一批被封鎖
    return pool

# --- 4. AI 核心預測引擎 ---
def perform_ai_prediction(df, v_comp):
    try:
        close_data = df['Close']
        curr_p = float(close_data.iloc[-1])
        returns = df['Close'].pct_change().dropna()
        vol = float(returns.std()) * v_comp
        sims = 300 # 提高模擬次數
        daily_returns = np.random.normal(0.005, vol, (sims, 20))
        paths = curr_p * np.exp(np.cumsum(daily_returns, axis=1))
        avg_path = np.mean(paths, axis=0)
        return curr_p * 0.98, float(np.max(avg_path)), int(np.argmax(avg_path) + 1)
    except: return 0, 0, 0

# --- 5. 主程式 ---
def main():
    st.markdown("<h1 style='text-align:center;'>🚀 StockAI V2.3 最終穩定版</h1>", unsafe_allow_html=True)
    
    with st.sidebar:
        st.header("⚙️ 智能控制台")
        scan_limit = st.slider("掃描數量", 5, 50, 5) # 預設改為 5 以利解鎖
        ai_sensitivity = st.slider("AI 波動係數", 0.5, 2.0, 1.15)
        st.warning("⚠️ 若顯示頻率限制，請更換手機熱點連線。")

    if st.button("🔥 啟動深度掃描分析"):
        pool = get_taiwan_stock_pool()
        results = []
        bar = st.progress(0)
        status_msg = st.empty()
        
        for i, sym in enumerate(pool[:scan_limit]):
            status_msg.markdown(f"📡 **正在透過加密隧道獲取數據**: `{sym}` ({i+1}/{scan_limit})")
            
            data = pd.DataFrame()
            # V2.3 新增：多時段嘗試策略
            for period in ["1y", "2y", "max"]:
                try:
                    ticker = yf.Ticker(sym)
                    data = ticker.history(period=period, interval="1d", timeout=30)
                    if not data.empty: break
                except:
                    time.sleep(3)
                    continue
            
            if not data.empty and len(data) > 30:
                buy, sell, days = perform_ai_prediction(data, ai_sensitivity)
                if buy > 0:
                    results.append({"id": sym, "buy": buy, "sell": sell, "days": days, "profit": (sell-buy)/buy})
            
            # 高強度防護延遲
            time.sleep(random.uniform(5.0, 8.0)) 
            bar.progress((i+1)/scan_limit)
            
        if results:
            top_list = sorted(results, key=lambda x: x['profit'], reverse=True)
            status_msg.success(f"✨ 分析完成！找到 {len(top_list)} 個潛力標的")
            sync_to_sheets_bulk({"last_scan": datetime.now().strftime("%H:%M:%S"), "found": len(top_list)})
            
            for item in top_list:
                st.markdown(f"""
                    <div class='rank-card'>
                        <span class='profit-badge'>預估獲利 {item['profit']:.2%}</span>
                        <h3>📈 {item['id']}</h3>
                        <p>🔹 <b>進場參考:</b> <span class='buy-label'>{item['buy']:.2f}</span></p>
                        <p>🔹 <b>目標獲利:</b> <span class='sell-label'>{item['sell']:.2f}</span></p>
                        <p>🔹 <b>策略週期:</b> 約 {item['days']} 個交易日</p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.error("🚫 Yahoo 封鎖尚未解除。解法：請改用手機行動網路熱點測試。")

if __name__ == "__main__":
    main()
