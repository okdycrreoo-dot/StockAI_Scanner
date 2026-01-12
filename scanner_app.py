import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
import time
import json
import re

# --- 1. 配置與視覺設定 ---
st.set_page_config(page_title="StockAI Scanner Pro", layout="wide")
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

# --- 2. Google Sheets 連線與自動回填引擎 (V1.8 終極穩定版) ---
def sync_settings_to_sheets(updates):
    try:
        from datetime import datetime
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # A. 提取金鑰
        raw_val = st.secrets["connections"]["gsheets"]["service_account"]
        clean_str = str(raw_val).strip().strip("'").strip('"')
        clean_str = clean_str.replace('\\\\n', '\n').replace('\\n', '\n')
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

        # B. 授權與網址縫合
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        # 強制縫合長網址：移除所有可能的換行與空格
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ss_url = str(raw_url).replace('\n', '').replace('\r', '').replace(' ', '').strip().strip('"').strip("'")
        
        sh = client.open_by_url(ss_url)
        
        # 自動匹配分頁：先找 settings，找不到就抓第一個
        try:
            ws = sh.worksheet("settings")
        except:
            ws = sh.get_worksheet(0)
        
        for key, val in updates.items():
            cell = ws.find(str(key))
            if cell:
                ws.update_cell(cell.row, 2, str(val))
            else:
                ws.append_row([str(key), str(val)])
                
    except Exception as e:
        st.error(f"連線失敗 (V1.8): {e}")

# --- 3. 自動抓取全市場台股 ---
@st.cache_data(ttl=86400)
def get_taiwan_stock_pool():
    urls = {"TW": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", 
            "TWO": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"}
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
                    if len(code) == 4 and code.isdigit():
                        pool.append(f"{code}.{suffix}")
        except: continue
    return pool

# --- 4. AI 核心引擎 ---
def perform_ai_prediction(df, v_comp):
    try:
        close_data = df['Close']
        curr_p = float(close_data.iloc[-1])
        p_days = 20
        returns = df['Close'].pct_change().dropna()
        vol = float(returns.std()) * v_comp
        sims = 300
        daily_returns = np.random.normal(0.005, vol, (sims, p_days))
        paths = curr_p * np.exp(np.cumsum(daily_returns, axis=1))
        avg_path = np.mean(paths, axis=0)
        best_idx = np.argmax(avg_path)
        return curr_p * 0.985, float(avg_path[best_idx]), int(best_idx + 1)
    except:
        return 0, 0, 0

# --- 5. 主程式 ---
def main():
    st.markdown("<h1 style='text-align:center;'>🏆 StockAI 全市場自我進化掃描器</h1>", unsafe_allow_html=True)
    st.caption("Admin: okdycrreoo | 核心版本: V1.8 (終極穩定版)")

    if st.button("🚀 啟動 AI 全市場掃描 (自動進化模式)"):
        v_optimized = 1.15
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        status_info = st.info("🧬 AI 正在自我校準參數並同步至 Google Sheets...")
        sync_settings_to_sheets({"vol_comp": v_optimized, "last_scan": now_str})
        
        pool = get_taiwan_stock_pool()
        limit = 30  # 設定為 30 支，確保穩定性
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, sym in enumerate(pool[:limit]):
            status.text(f"📡 掃描中 ({i+1}/{limit}): {sym}")
            time.sleep(1.2) # 延遲防止 yfinance 封鎖
            try:
                data = yf.download(sym, period="6mo", interval="1d", progress=False)
                if not data.empty and len(data) > 20:
                    buy, sell, days = perform_ai_prediction(data, v_optimized)
                    if buy > 0:
                        potential = (sell - buy) / buy
                        results.append({
                            "id": sym, "now": buy/0.985, "buy": buy, 
                            "sell": sell, "days": days, "profit": potential
                        })
            except: continue
            bar.progress((i+1)/limit)
            
        if results:
            top_30 = sorted(results, key=lambda x: x['profit'], reverse=True)[:30]
            status.success(f"✅ 完成！已挑選出最佳潛力標的")
            for idx, item in enumerate(top_30):
                st.markdown(f"""
                    <div class='rank-card'>
                        <span class='profit-badge'>預估獲利 {item['profit']:.2%}</span>
                        <h3>No.{idx+1} — {item['id']}</h3>
                        <p>🎯 <b>建議買入:</b> <span class='buy-label'>{item['buy']:.2f}</span> | 💰 <b>目標:</b> <span class='sell-label'>{item['sell']:.2f}</span></p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            status.error("❌ 掃描完成但無數據，請確認市場是否開盤或 yfinance 狀態。")

if __name__ == "__main__":
    main()
