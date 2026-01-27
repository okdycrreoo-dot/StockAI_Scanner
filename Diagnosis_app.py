import streamlit as st
import yfinance as yf
import google.generativeai as genai

# --- 1. 核心配置 ---
# 從 Streamlit Secrets 讀取 API Key (已確認您的 Secrets 設定正確)
try:
    if "GEMINI_API_KEY" in st.secrets:
        GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=GEMINI_API_KEY)
        # 修正模型名稱呼叫格式，解決 404 報錯
        model = genai.GenerativeModel('gemini-1.5-flash')
    else:
        st.error("❌ 請在 Streamlit Secrets 設定 GEMINI_API_KEY")
except Exception as e:
    st.error(f"❌ API 配置異常: {e}")

# 初始化 Watchlist (上限 20 檔)
if 'watchlist' not in st.session_state:
    st.session_state.watchlist = []

# --- 2. 功能函數 ---
def get_stock_data(symbol):
    """判定市場並抓取 Yahoo Finance 數據"""
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
    """執行 20 檔上限邏輯"""
    if symbol in st.session_state.watchlist:
        st.info(f"💡 {symbol} 已在清單中。")
    elif len(st.session_state.watchlist) >= 20:
        st.warning(f"⚠️ 您的 Watchlist 已達 20 檔上限！請移除舊標的再添加。")
    else:
        st.session_state.watchlist.append(symbol)
        st.success(f"✅ {symbol} 已加入！目前清單共 {len(st.session_state.watchlist)}/20 檔。")

# --- 3. 介面設計 ---
st.set_page_config(page_title="StockAI Scanner", layout="wide")
st.title("🤖 Gemini 股票深度診斷與清單管理")

# 側邊欄：管理清單
st.sidebar.header(f"您的 Watchlist ({len(st.session_state.watchlist)}/20)")
if st.sidebar.button("🗑️ 清空清單"):
    st.session_state.watchlist = []
    st.rerun()
for item in st.session_state.watchlist:
    st.sidebar.write(f"📌 {item}")

# 股票輸入
stock_code = st.text_input("請輸入股票代號前 4 碼 (例如: 2330)", max_chars=4)

if stock_code:
    ticker_obj, info, full_symbol = get_stock_data(stock_code)
    
    if info:
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

        # 技術指標輸入：改用 text_input 徹底移除按鈕並支援負值
        st.subheader("🧪 技術指標手動填寫 (支援負數，如 MTM)")
        with st.form("tech_form"):
            t1, t2, t3 = st.columns(3)
            with t1:
                vol_5 = st.text_input("5日平均 VOL", "0")
                macd_dif = st.text_input("MACD DIF", "0")
                rsi_5 = st.text_input("RSI 5日平均", "0")
                di_plus = st.text_input("DMI +DI", "0")
                di_minus = st.text_input("DMI -DI", "0")
                k_val, d_val, j_val = st.text_input("K值", "0"), st.text_input("D值", "0"), st.text_input("J值", "0")
            with t2:
                bias_5 = st.text_input("BIAS 5日平均", "0")
                psy_12 = st.text_input("PSY 12日平均", "0")
                obv, bbi = st.text_input("OBV值", "0"), st.text_input("BBI值", "0")
                cci_3 = st.text_input("CCI 3日平均", "0")
                mtm_10 = st.text_input("MTM 10日平均", "0")
                roc_12 = st.text_input("ROC 12日平均", "0")
                wc_val = st.text_input("WC值", "0")
            with t3:
                ad_val, ar_13, br_13 = st.text_input("AD值", "0"), st.text_input("AR13", "0"), st.text_input("BR13", "0")
                vr_13, eom_14 = st.text_input("VR13", "0"), st.text_input("EOM14", "0")
                nvi, pvi, vao = st.text_input("NVI值", "0"), st.text_input("PVI值", "0"), st.text_input("VAO值", "0")
            
            submit = st.form_submit_button("💡 發送給 Gemini 進行深度診斷")

        if submit:
            prompt = f"""
            你是一位專業分析師。請針對 {info.get('longName')} 進行診斷。
            數據如下：
            【基本面】現價:{price}, PE:{pe}, 淨值:{nav}, PB:{pb}
            【技術面】
            - 能量: VOL5:{vol_5}, OBV:{obv}, VR13:{vr_13}, VAO:{vao}, AR13:{ar_13}, BR13:{br_13}
            - 震盪: MACD_DIF:{macd_dif}, RSI5:{rsi_5}, KDJ:{k_val}/{d_val}/{j_val}, CCI3:{cci_3}, ROC12:{roc_12}, MTM10:{mtm_10}
            - 趨勢: BBI:{bbi}, BIAS5:{bias_5}, PSY12:{psy_12}, DMI:{di_plus}/{di_minus}, EOM14:{eom_14}
            - 籌碼: NVI:{nvi}, PVI:{pvi}, WC:{wc_val}, AD:{ad_val}
            
            任務要求：
            1. 說明各指標數據的含義。
            2. 重點分析 NVI/PVI/VAO 的籌碼流動趨勢。
            3. 最後給出明確的診斷建議（買進/觀察/減碼）。
            """
            
            with st.spinner("Gemini 正在產生診斷報告..."):
                try:
                    response = model.generate_content(prompt)
                    st.markdown("---")
                    st.markdown(response.text)
                    
                    if st.button(f"➕ 將 {full_symbol} 加入 Watchlist"):
                        add_to_watchlist(full_symbol)
                except Exception as e:
                    st.error(f"分析失敗: {e}。請檢查 API Key 是否有對應模型的權限。")
    else:
        st.error("找不到該股票代碼，請輸入 4 位數字。")
