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

# --- 1. 頁面配置與視覺美化 ---
st.set_page_config(page_title="StockAI Scanner Pro V2.0", layout="wide")
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

# --- 2. Google Sheets 批次同步引擎 (V2.0 優化版) ---
def sync_to_sheets_bulk(updates_dict):
    """
    接收一個字典，一次性執行所有寫入動作，減少 API 請求次數
    """
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        
        # A. 金鑰清洗與轉義處理
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

        # B. 網址強力縫合
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ss_url = str(raw_url).replace('\n', '').replace('\r', '').replace(' ', '').strip().strip('"').strip("'")
        
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(ss_url)
        ws = sh.get_worksheet(0)
        
        # C. 批次寫入：避免多次迴圈呼叫 API
        # 這裡會先找出現有的所有資料，並在本地比對，減少通訊次數
        all_data = ws.get_all_values()
        existing_keys = {row[0]: i+1 for i, row in enumerate(all_data) if row}

        for key, val in updates_dict.items():
            if key in existing_keys:
                ws.update_cell(existing_keys[key], 2, str(val))
            else:
                ws.append_row([str(key), str(val)])
                
    except Exception as e:
        st.error(f"⚠️ 雲端同步失敗: {str(e)[:50]}")

# --- 3. 自動抓取全市場台股清單 ---
@st.cache_data(ttl=86400)
def get_taiwan_stock_pool():
    urls = {
        "TW": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2", 
        "TWO": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"
    }
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

# --- 4. AI 核心預測引擎 ---
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
        best_idx = np.argmax(avg_path)
        return curr_p * 0.985, float(avg_path[best_idx]), int(best_idx + 1)
    except: return 0, 0, 0

# --- 5. 主程式 ---
def main():
    st.markdown("<h1 style='text-align:center;'>🏆 StockAI V2.0 批次強化掃描器</h1>", unsafe_allow_html=True)
    st.caption("Admin: okdycrreoo | 核心版本: V2.0 (批次寫入優化版)")

    with st.sidebar:
        st.header("⚙️ AI 管理面板")
        scan_limit = st.slider("掃描數量限制", 5, 200, 20)
        ai_sensitivity = st.slider("AI 波動敏感度", 0.5, 2.0, 1.15)
        st.info(f"當前連線頻率設定: {st.secrets.get('google_api_delay', 5)} 分鐘")

    if st.button("🚀 啟動全市場批次掃描"):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 初始化數據集 (只在本地記憶體運作)
        pool = get_taiwan_stock_pool()
        results = []
        bar = st.progress(0)
        status_msg = st.empty()
        
        # 開始掃描
        for i, sym in enumerate(pool[:scan_limit]):
            status_msg.text(f"📡 深度掃描中 ({i+1}/{scan_limit}): {sym}")
            time.sleep(2.5) # 保護 yfinance 頻率
            
            try:
                data = yf.download(sym, period="6mo", interval="1d", progress=False, timeout=15)
                if not data.empty and len(data) > 20:
                    buy, sell, days = perform_ai_prediction(data, ai_sensitivity)
                    if buy > 0:
                        results.append({
                            "id": sym, "buy": buy, "sell": sell, 
                            "days": days, "profit": (sell - buy) / buy
                        })
            except: continue
            bar.progress((i+1)/scan_limit)
            
        # 掃描完成後的批次處理
        if results:
            top_30 = sorted(results, key=lambda x: x['profit'], reverse=True)[:30]
            status_msg.success(f"✅ 掃描完成！正在執行一次性雲端同步...")
            
            # 打包所有數據，只呼叫一次 API
            bulk_data = {
                "last_scan_time": now_str,
                "scan_count": scan_limit,
                "ai_sensitivity": ai_sensitivity,
                "top_1_id": top_30[0]['id'] if len(top_30) > 0 else "None",
                "top_1_profit": f"{top_30[0]['profit']:.2%}" if len(top_30) > 0 else "0%",
                "status": "Success"
            }
            sync_to_sheets_bulk(bulk_data)
            
            # 前端顯示
            for idx, item in enumerate(top_30):
                st.markdown(f"""
                    <div class='rank-card'>
                        <span class='profit-badge'>預估獲利 {item['profit']:.2%}</span>
                        <h3>No.{idx+1} — {item['id']}</h3>
                        <p>🎯 <b>買入點:</b> {item['buy']:.2f} | 💰 <b>目標價:</b> {item['sell']:.2f}</p>
                        <p>📅 預計達標天數: {item['days']} 天</p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.error("❌ 掃描結束但無有效數據，請檢查網路環境。")

if __name__ == "__main__":
    main()
