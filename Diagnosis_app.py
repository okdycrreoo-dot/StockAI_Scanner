import streamlit as st
import yfinance as yf
import google.generativeai as genai

# --- 1. 配置與初始化 ---
# 讀取 Streamlit Secrets 中的 API Key
try:
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("❌ 請在 Streamlit Secrets 中設定 GEMINI_API_KEY")

# 初始化 Watchlist (存在 session 中，符合 20 檔限制規範)
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# --- 2. 核心函數 ---
def get_stock_data(symbol):
    """自動判定市場 (.TW 或 .TWO)"""
    for suffix in [".TW", ".TWO"]:
        ticker_str = f"{symbol}{suffix}"
        data = yf.Ticker(ticker_str)
        try:
            info = data.info
            if info and 'regularMarketPrice' in info:
                return data, info, ticker_str
        except:
            continue
    return None, None, None

def add_to_watchlist(symbol):
    """20 檔限制提醒邏輯 (依 2026-01-15 規範)"""
    if symbol in st.session_state.watchlist:
        st.info(f"💡 {symbol} 已在清單中。")
    elif len(st.session_state.watchlist) >= 20:
        st.warning(f"⚠️ 提醒：您的 Watchlist 已達 {len(st.session_state.watchlist)} 檔上限！請移除舊標的後再添加。")
    else:
        st.session_state.watchlist.append(symbol)
        st.success(f"✅ {symbol} 已加入！目前清單共 {len(st.session_state.watchlist)}/20 檔。")

# --- 3. UI 介面 ---
st.set_page_config(page_title="StockAI Scanner", layout="wide")
st.title("🤖 Gemini 股票深度診斷系統")

# 側邊欄：管理 20 檔 Watchlist
st.sidebar.header(f"您的 Watchlist ({len(st.session_state.watchlist)}/20)")
if st.sidebar.button("🗑️ 清空清單"):
    st.session_state.watchlist = []
    st.rerun()
for item in st.session_state.watchlist:
    st.sidebar.write(f"📌 {item}")

# 股票代號輸入
stock_code = st.text_input("請輸入股票前 4 碼 (例如: 2330)", max_chars=4)

if stock_code:
    ticker_obj, info, full_symbol = get_stock_data(stock_code)
    
    if info:
        # 基本面區塊
        st.subheader(f"📊 {info.get('longName', '未知')} ({full_symbol})")
        price = info.get('regularMarketPrice', 'N/A')
        pe = info.get('trailingPE', 'N/A')
        nav = info.get('bookValue', 'N/A')
        pb = info.get('priceToBook', 'N/A')
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("今日收盤", price)
        c2.metric("本益比 (PE)", pe)
        c3.metric("每股淨值 (NAV)", nav)
        c4.metric("股價淨值比 (PB)", pb)

        # 技術指標手動輸入區 (純文字輸入，支援負數，無按鈕)
        st.subheader("🧪 技術指標數據 (請手動填寫數值)")
        with st.form("tech_form"):
            t1, t2, t3 = st.columns(3)
            with t1:
                vol_5 = st.text_input("5日平均 VOL", "0.0")
                macd_dif = st.text_input("MACD DIF12-26", "0.0")
                rsi_5 = st.text_input("RSI 5日平均", "0.0")
                di_plus = st.text_input("DMI +DI14", "0.0")
                di_minus = st.text_input("DMI -DI14", "0.0")
                k_val = st.text_input("KDJ-K值", "0.0")
                d_val = st.text_input("KDJ-D值", "0.0")
                j_val = st.text_input("KDJ-J值", "0.0")
            with t2:
                bias_5 = st.text_input("BIAS 5日平均", "0.0")
                psy_12 = st.text_input("PSY 12日平均", "0.0")
                obv = st.text_input("OBV值", "0.0")
                bbi = st.text_input("BBI值", "0.0")
                cci_3 = st.text_input("CCI 3日平均", "0.0")
                mtm_10 = st.text_input("MTM 10日平均", "0.0")
                roc_12 = st.text_input("ROC 12日平均", "0.0")
                wc_val = st.text_input("WC值", "0.0")
            with t3:
                ad_val = st.text_input("AD值", "0.0")
                ar_13 = st.text_input("AR 13日平均", "0.0")
                br_13 = st.text_input("BR 13日平均", "0.0")
                vr_13 = st.text_input("VR 13日平均", "0.0")
                eom_14 = st.text_input("14EOM值", "0.0")
                nvi = st.text_input("NVI值", "0.0")
                pvi = st.text_input("PVI值", "0.0")
                vao = st.text_input("VAO值", "0.0")
            
            submit = st.form_submit_button("💡 開始 AI 深度診斷")

        if submit:
            # 構造 Prompt
            prompt = f"""
            你是一位專業分析師。請針對 {info.get('longName')} 進行診斷。
            數據如下：
            【基本面】現價:{price}, PE:{pe}, 淨值:{nav}, PB:{pb}
            【技術面】
            - 能量: VOL5:{vol_5}, OBV:{obv}, VR13:{vr_13}, VAO:{vao}, AR13:{ar_13}, BR13:{br_13}
            - 震盪: MACD_DIF:{macd_dif}, RSI5:{rsi_5}, KDJ:{k_val}/{d_val}/{j_val}, CCI3:{cci_3}, ROC12:{roc_12}, MTM10:{mtm_10}
            - 趨勢: BBI:{bbi}, BIAS5:{bias_5}, PSY12:{psy_12}, DMI:{di_plus}/{di_minus}, EOM14:{eom_14}
            - 籌碼: NVI:{nvi}, PVI:{pvi}, WC:{wc_val}, AD:{ad_val}
            
            任務：
            1. 說明各指標意義。
            2. 重點分析 NVI/PVI/VAO 的籌碼流向。
            3. 給出結論與買賣建議。
            """
            
            with st.spinner("Gemini 分析中..."):
                try:
                    response = model.generate_content(prompt)
                    st.markdown("---")
                    st.markdown(response.text)
                    
                    # 分析完後可選擇加入清單
                    if st.button(f"➕ 加入 Watchlist"):
                        add_to_watchlist(full_symbol)
                except Exception as e:
                    st.error(f"分析失敗: {e}")
    else:
        st.error("找不到代號，請檢查是否為 4 碼數字。")
