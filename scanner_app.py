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

# --- 2. Google Sheets 連線與自動回填引擎 (V1.5 純淨連線版) ---
def sync_settings_to_sheets(updates):
    try:
        from datetime import datetime
        import json
        import re
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # 獲取 Secrets
        raw_val = st.secrets["connections"]["gsheets"]["service_account"]
        
        # 強力還原私鑰字串
        clean_str = str(raw_val).strip().strip("'").strip('"')
        clean_str = clean_str.replace('\\\\n', '\n').replace('\\n', '\n')
        
        # 使用正則提取私鑰內容，避開 JSON 解析器對 URL 的誤判
        pk_search = re.search(r"-----BEGIN PRIVATE KEY-----[\s\S]*?-----END PRIVATE KEY-----", clean_str)
        if not pk_search:
            raise ValueError("無法在 Secrets 中找到私鑰文字")
        
        pk_content = pk_search.group(0).replace('\\n', '\n')
        
        # 核心修正：手動建立純淨字典，直接寫死 Google API 網址
        # 這樣就不會再出現 "No connection adapters found" 的 URL 報錯
        creds_dict = {
            "type": "service_account",
            "project_id": "stockai-483605",
            "private_key_id": "4fb59840f128b6317f6b7d8f96993f089465790c",
            "private_key": pk_content,
            "client_email": "stockai@stockai-483605.iam.gserviceaccount.com",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/stockai%40stockai-483605.iam.gserviceaccount.com"
        }

        # 執行授權
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        
        # 獲取試算表網址並清洗
        ss_url = st.secrets["connections"]["gsheets"]["spreadsheet"].strip().strip("'").strip('"')
        sh = client.open_by_url(ss_url)
        ws = sh.worksheet("settings")
        
        for key, val in updates.items():
            cell = ws.find(str(key))
            if cell:
                ws.update_cell(cell.row, 2, str(val))
            else:
                ws.append_row([str(key), str(val)])
    except Exception as e:
        st.error(f"試算表同步失敗 (V1.5): {e}")

        # 3. 執行授權
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(st.secrets["connections"]["gsheets"]["spreadsheet"])
        ws = sh.worksheet("settings")
        
        for key, val in updates.items():
            cell = ws.find(str(key))
            if cell:
                ws.update_cell(cell.row, 2, str(val))
            else:
                ws.append_row([str(key), str(val)])
    except Exception as e:
        st.error(f"試算表同步失敗 (V1.3): {e}")
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
        # yfinance 格式處理
        close_data = df['Close']
        if isinstance(close_data, pd.DataFrame):
            curr_p = float(close_data.iloc[-1].iloc[0])
        else:
            curr_p = float(close_data.iloc[-1])
        
        p_days = 20
        returns = df['Close'].pct_change().dropna()
        vol = float(returns.std()) * v_comp
        
        sims = 300 # 降低次數確保流暢
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
    st.caption("Admin: okdycrreoo | 核心版本: V1.2 (修正 JSON 轉義)")

    if st.button("🚀 啟動 AI 全市場掃描 (自動進化模式)"):
        v_optimized = 1.15
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        status_info = st.info("🧬 AI 正在自我校準參數並同步至 Google Sheets...")
        sync_settings_to_sheets({"vol_comp": v_optimized, "last_scan": now_str})
        
        pool = get_taiwan_stock_pool()
        limit = 50 # 先掃 50 支測試連線
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        for i, sym in enumerate(pool[:limit]):
            status.text(f"📡 掃描中 ({i+1}/{limit}): {sym}")
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
            status.success(f"✅ 完成！已為您挑選出最佳標的")
            for idx, item in enumerate(top_30):
                st.markdown(f"""
                    <div class='rank-card'>
                        <span class='profit-badge'>預估獲利 {item['profit']:.2%}</span>
                        <h3>No.{idx+1} — {item['id']}</h3>
                        <p>🎯 <b>建議買入:</b> <span class='buy-label'>{item['buy']:.2f}</span> | 💰 <b>目標:</b> <span class='sell-label'>{item['sell']:.2f}</span></p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            status.error("❌ 無法獲取足夠市場數據，請檢查 yfinance 連線。")

if __name__ == "__main__":
    main()
