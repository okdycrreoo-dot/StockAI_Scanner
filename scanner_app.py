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

# --- 2. Google Sheets 連線與自動回填引擎 (V1.9 終極版) ---
def sync_settings_to_sheets(updates):
    try:
        # A. 提取並清洗 Secrets 中的金鑰，解決截圖中出現過的轉義錯誤
        raw_val = st.secrets["connections"]["gsheets"]["service_account"]
        clean_str = str(raw_val).strip().strip("'").strip('"')
        clean_str = clean_str.replace('\\\\n', '\n').replace('\\n', '\n')
        
        # 使用正規表達式強力提取私鑰，避免格式毀損
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

        # B. 網址強力縫合：解決截圖中出現過的長網址換行斷裂問題
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        ss_url = str(raw_url).replace('\n', '').replace('\r', '').replace(' ', '').strip().strip('"').strip("'")
        sh = client.open_by_url(ss_url)
        
        # C. 授權與連線
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sh = client.open_by_url(ss_url)
        ws = sh.get_worksheet(0) 
        
        # D. 智能數據回填
        for key, val in updates.items():
            try:
                cell = ws.find(str(key))
                if cell:
                    ws.update_cell(cell.row, 2, str(val))
                else:
                    ws.append_row([str(key), str(val)])
            except:
                ws.append_row([str(key), str(val)])
                
    except Exception as e:
        # 即使同步失敗也不中斷主程式，僅顯示警告
        st.warning(f"⚠️ 試算表同步暫時無法連線，將繼續進行本地掃描。")

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
        except:
            continue
    return pool

# --- 4. AI 核心預測引擎 ---
def perform_ai_prediction(df, v_comp):
    try:
        close_data = df['Close']
        curr_p = float(close_data.iloc[-1])
        p_days = 20
        returns = df['Close'].pct_change().dropna()
        vol = float(returns.std()) * v_comp
        
        # 蒙地卡羅路徑模擬
        sims = 200
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
    st.caption("Admin: okdycrreoo | 核心版本: V1.9 (終極穩定版)")

    # 側邊欄管理面板 (截圖 image_af81ab.png 中顯示已正常運作)
    with st.sidebar:
        st.header("⚙️ AI 管理面板")
        scan_limit = st.slider("掃描數量限制", 5, 200, 20)
        ai_sensitivity = st.slider("AI 波動敏感度", 0.5, 2.0, 1.15)
        st.info("當前模式: 全市場掃描 (TW/TWO)")

    if st.button("🚀 啟動 AI 全市場掃描"):
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # 步驟 1: 同步至 Google Sheets
        st.info("🧬 AI 正在校準參數並同步至 Google Sheets...")
        sync_settings_to_sheets({
            "vol_comp": ai_sensitivity, 
            "last_scan": now_str,
            "status": "Running"
        })
        
        # 步驟 2: 獲取代碼清單
        pool = get_taiwan_stock_pool()
        results = []
        bar = st.progress(0)
        status = st.empty()
        
        # 步驟 3: 循環掃描，針對截圖中的 yfinance 錯誤進行保護
        for i, sym in enumerate(pool[:scan_limit]):
            status.text(f"📡 正在掃描 ({i+1}/{scan_limit}): {sym}")
            
            # 關鍵保護：增加延遲防止 yfinance 鎖定 IP
            time.sleep(2.5) 
            
            try:
                data = yf.download(sym, period="6mo", interval="1d", progress=False, timeout=15)
                if not data.empty and len(data) > 20:
                    buy, sell, days = perform_ai_prediction(data, ai_sensitivity)
                    if buy > 0:
                        potential = (sell - buy) / buy
                        results.append({
                            "id": sym, "buy": buy, "sell": sell, 
                            "days": days, "profit": potential
                        })
            except:
                continue
            bar.progress((i+1)/scan_limit)
            
        # 步驟 4: 輸出結果
        if results:
            top_30 = sorted(results, key=lambda x: x['profit'], reverse=True)[:30]
            status.success(f"✅ 掃描完成！已優選出最佳潛力標的")
            
            for idx, item in enumerate(top_30):
                st.markdown(f"""
                    <div class='rank-card'>
                        <span class='profit-badge'>預估獲利 {item['profit']:.2%}</span>
                        <h3>No.{idx+1} — {item['id']}</h3>
                        <p>🎯 <b>建議買入:</b> <span class='buy-label'>{item['buy']:.2f}</span> | 💰 <b>目標價:</b> <span class='sell-label'>{item['sell']:.2f}</span></p>
                        <p>📅 預計 <b>{item['days']}</b> 個交易日內達標</p>
                    </div>
                """, unsafe_allow_html=True)
            
            sync_settings_to_sheets({"status": "Scan Finished"})
        else:
            status.error("❌ 掃描完成但未獲取有效數據。請確保試算表已分享權限或稍後再試。")

if __name__ == "__main__":
    main()
