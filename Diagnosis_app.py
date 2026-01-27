import streamlit as st
import yfinance as yf
import google.generativeai as genai

# --- 1. AI 配置區 ---
# 請在此輸入您的 Gemini API Key (建議使用環境變數或 Streamlit secrets)
GEMINI_API_KEY = "您的_GEMINI_API_KEY" 
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash') # 或使用 gemini-1.5-pro 獲得更深度的分析

# --- 2. 核心功能函數 ---
def get_stock_data(symbol):
    """判斷市場並抓取數據"""
    for suffix in [".TW", ".TWO"]:
        ticker_str = f"{symbol}{suffix}"
        data = yf.Ticker(ticker_str)
        info = data.info
        if info and 'regularMarketPrice' in info:
            return data, info, ticker_str
    return None, None, None

# --- 3. Streamlit UI 介面 ---
st.set_page_config(page_title="StockAI Scanner", layout="wide")
st.title("🤖 Gemini 股票深度診斷系統")

stock_code = st.text_input("請輸入股票前4碼代號", max_chars=4, placeholder="例如: 2330")

if stock_code:
    ticker_obj, info, full_symbol = get_stock_data(stock_code)
    
    if info:
        # 顯示基本數值
        st.subheader(f"📊 {info.get('longName')} ({full_symbol}) 基本面")
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
                macd_dif = st.number_input("MACD DIF (12-26)", value=0.0)
                rsi_5 = st.number_input("RSI 5日平均", value=0.0)
                di_plus = st.number_input("DMI +DI14", value=0.0)
                di_minus = st.number_input("DMI -DI14", value=0.0)
                k_val = st.number_input("KDJ-K", value=0.0)
                d_val = st.number_input("KDJ-D", value=0.0)
                j_val = st.number_input("KDJ-J", value=0.0)
            with t2:
                bias_5 = st.number_input("BIAS 5日平均", value=0.0)
                psy_12 = st.number_input("PSY 12日平均", value=0.0)
                obv = st.number_input("OBV 值", value=0.0)
                bbi = st.number_input("BBI 值", value=0.0)
                cci_3 = st.number_input("CCI 3日平均", value=0.0)
                mtm_10 = st.number_input("MTM 10日平均", value=0.0)
                roc_12 = st.number_input("ROC 12日平均", value=0.0)
            with t3:
                wc_val = st.number_input("WC 值", value=0.0)
                ad_val = st.number_input("AD 值", value=0.0)
                ar_13 = st.number_input("AR 13日平均", value=0.0)
                br_13 = st.number_input("BR 13日平均", value=0.0)
                vr_13 = st.number_input("VR 13日平均", value=0.0)
                eom_14 = st.number_input("14EOM", value=0.0)
                nvi = st.number_input("NVI", value=0.0)
                pvi = st.number_input("PVI", value=0.0)
                vao = st.number_input("VAO", value=0.0)
            
            submit = st.form_submit_button("🚀 發送給 Gemini 進行深度診斷")

        if submit:
            # --- 4. 構造 AI Prompt ---
            prompt = f"""
            你是一位專業的股市分析師。請根據以下數據，為股票 {info.get('longName')} ({full_symbol}) 提供詳細診斷報告。
            
            【基本面數據】
            - 現價: {price}, 本益比: {pe}, 每股淨值: {nav}, 股價淨值比: {pb}
            
            【技術指標數據】
            - 量價能量: 5日均量:{vol_5}, OBV:{obv}, VR(13):{vr_13}, VAO:{vao}
            - 動能/震盪: MACD DIF:{macd_dif}, RSI(5):{rsi_5}, KDJ:{k_val}/{d_val}/{j_val}, CCI(3):{cci_3}, ROC(12):{roc_12}, MTM(10):{mtm_10}
            - 趨勢/反轉: BBI:{bbi}, BIAS(5):{bias_5}, PSY(12):{psy_12}, DMI(+DI:{di_plus}, -DI:{di_minus}), EOM(14):{eom_14}
            - 籌碼與其他: NVI:{nvi}, PVI:{pvi}, WC:{wc_val}, AD:{ad_val}, AR(13):{ar_13}, BR(13):{br_13}
            
            【任務要求】
            1. 逐一說明這些技術指標數值在當前代表的意義（多頭、空頭或盤整）。
            2. 特別分析 NVI/PVI 與量價指標組合出的籌碼意涵。
            3. 結合基本面（是否低於淨值）給出綜合評價。
            4. 最後給出明確的「操作建議」（買進、觀察、減碼或觀望）。
            請使用繁體中文，格式清晰易讀。
            """

            with st.spinner("Gemini 正在精算指標並撰寫報告..."):
                try:
                    response = model.generate_content(prompt)
                    st.markdown("---")
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"AI 分析出錯: {e}")
    else:
        st.error("無法辨識股票代號，請確保輸入為4位數字。")
