import streamlit as st
import yfinance as yf
import google.generativeai as genai

# --- 1. 配置區 ---
# 請在此輸入您的 Gemini API Key
GEMINI_API_KEY = "您的_GEMINI_API_KEY" 
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

# 模擬 Watchlist 數據庫 (實際開發建議存於 st.session_state 或資料庫)
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# --- 2. 核心功能函數 ---
def get_stock_data(symbol):
    """自動判定市場並抓取數據"""
    for suffix in [".TW", ".TWO"]:
        ticker_str = f"{symbol}{suffix}"
        data = yf.Ticker(ticker_str)
        info = data.info
        if info and 'regularMarketPrice' in info:
            return data, info, ticker_str
    return None, None, None

def add_to_watchlist(symbol):
    """Watchlist 數量檢查邏輯 (上限 20 檔)"""
    if symbol in st.session_state.watchlist:
        st.info(f"💡 {symbol} 已經在您的清單中。")
    elif len(st.session_state.watchlist) >= 20:
        st.warning(f"⚠️ 提醒：您的 Watchlist 已達 {len(st.session_state.watchlist)} 檔（上限 20 檔）。請移除舊標的後再添加。")
    else:
        st.session_state.watchlist.append(symbol)
        st.success(f"✅ {symbol} 已加入 Watchlist！目前總計: {len(st.session_state.watchlist)}/20")

# --- 3. Streamlit UI 介面 ---
st.set_page_config(page_title="StockAI Scanner", layout="wide")
st.title("🤖 Gemini 股票深度診斷與清單管理")

# 側邊欄顯示目前清單狀況
st.sidebar.header(f"您的 Watchlist ({len(st.session_state.watchlist)}/20)")
st.sidebar.write(st.session_state.watchlist)
if st.sidebar.button("清空清單"):
    st.session_state.watchlist = []
    st.rerun()

stock_code = st.text_input("請輸入股票代號前4碼", max_chars=4, placeholder="例如: 2330")

if stock_code:
    ticker_obj, info, full_symbol = get_stock_data(stock_code)
    
    if info:
        # 基本面顯示
        st.subheader(f"📊 {info.get('longName')} ({full_symbol})")
        c1, c2, c3, c4 = st.columns(4)
        price = info.get('regularMarketPrice', 'N/A')
        pe = info.get('trailingPE', 'N/A')
        nav = info.get('bookValue', 'N/A')
        pb = info.get('priceToBook', 'N/A')
        
        c1.metric("今日收盤", price)
        c2.metric("本益比 (PE)", pe)
        c3.metric("每股淨值 (NAV)", nav)
        c4.metric("股價淨值比 (PB)", pb)

        # 技術指標輸入表單
        st.subheader("🧪 技術指標數據輸入")
        with st.form("tech_data"):
            t1, t2, t3 = st.columns(3)
            with t1:
                vol_5 = st.number_input("5日平均 VOL", value=0.0)
                macd_dif = st.number_input("MACD DIF", value=0.0)
                rsi_5 = st.number_input("RSI 5日平均", value=0.0)
                di_plus = st.number_input("DMI +DI", value=0.0)
                di_minus = st.number_input("DMI -DI", value=0.0)
                k_val, d_val, j_val = st.number_input("K",0.0), st.number_input("D",0.0), st.number_input("J",0.0)
            with t2:
                bias_5 = st.number_input("BIAS 5日平均", value=0.0)
                psy_12 = st.number_input("PSY 12日平均", value=0.0)
                obv, bbi = st.number_input("OBV",0.0), st.number_input("BBI",0.0)
                cci_3, mtm_10, roc_12 = st.number_input("CCI",0.0), st.number_input("MTM",0.0), st.number_input("ROC",0.0)
            with t3:
                wc_val, ad_val = st.number_input("WC",0.0), st.number_input("AD",0.0)
                ar_13, br_13, vr_13 = st.number_input("AR",0.0), st.number_input("BR",0.0), st.number_input("VR",0.0)
                eom_14, nvi, pvi, vao = st.number_input("EOM",0.0), st.number_input("NVI",0.0), st.number_input("PVI",0.0), st.number_input("VAO",0.0)
            
            submit = st.form_submit_button("🚀 發送給 Gemini 進行深度診斷")

        if submit:
            # 強化權重的 Prompt
            prompt = f"""
            你是一位專業的股市分析師。請根據以下數據，為股票 {info.get('longName')} 進行深度診斷。
            
            【基本面】現價:{price}, PE:{pe}, 淨值:{nav}, PB:{pb}
            【技術指標數據】
            - 籌碼與特殊指標(重點分析): NVI:{nvi}, PVI:{pvi}, VAO:{vao}, EOM:{eom_14}
            - 量價/能量: 5日均量:{vol_5}, OBV:{obv}, VR(13):{vr_13}, AR/BR:{ar_13}/{br_13}
            - 震盪與趨勢: MACD DIF:{macd_dif}, RSI(5):{rsi_5}, KDJ:{k_val}/{d_val}/{j_val}, BBI:{bbi}, BIAS(5):{bias_5}
            
            【分析要求】
            1. 必須詳述每個指標的意義。
            2. 特別解讀 NVI/PVI/VAO 反映的大戶與散戶心理與籌碼流向。
            3. 若 PB < 1，請分析其安全邊際。
            4. 最後給出明確的「買進/觀望/減碼」結論與建議。
            """

            with st.spinner("Gemini 正在精算報告..."):
                response = model.generate_content(prompt)
                st.markdown("---")
                st.markdown(response.text)
                
                # 診斷完後詢問是否加入清單
                if st.button(f"➕ 將 {full_symbol} 加入 Watchlist"):
                    add_to_watchlist(full_symbol)
    else:
        st.error("找不到該股票代碼，請確認輸入。")
