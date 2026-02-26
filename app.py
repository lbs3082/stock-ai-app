import streamlit as st
import os
import time
import sqlite3
import re
import random
import yfinance as yf
import pandas as pd
import google.generativeai as genai
import plotly.graph_objects as go
import FinanceDataReader as fdr
from datetime import datetime, timedelta
from duckduckgo_search import DDGS
import yt_dlp

# ==========================================
# 1. 초기 설정 및 API 키
# ==========================================
st.set_page_config(page_title="AI 주식 마스터 Pro & 차트 게임", page_icon="📈", layout="wide")

# API 키 가져오기 (Streamlit Secrets -> Environment Variable -> Manual Check)
API_KEY = ""
try:
    if "GEMINI_API_KEY" in st.secrets:
        API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    # secrets file이 아예 없는 경우 예외 처리
    pass

if not API_KEY:
    API_KEY = os.getenv("GEMINI_API_KEY", "")

if API_KEY:
    genai.configure(api_key=API_KEY)
else:
    st.sidebar.error("⚠️ GEMINI_API_KEY가 설정되지 않았습니다. 사이드바나 환경 변수에 키를 설정해주세요.")

# 스타일 정의
st.markdown("""
<style>
    .stMetric { background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EEE; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .news-box { background: #F9F9F9; padding: 15px; border-radius: 10px; border: 1px solid #E0E0E0; margin-bottom: 10px; font-size: 0.9rem; }
    .game-news-container { background: #FFF4E5; padding: 15px; border-radius: 10px; border-left: 5px solid #FF9800; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 세션 상태 초기화
# ==========================================
if 'page' not in st.session_state:
    st.session_state.page = '🎮 차트 게임'

game_defaults = {
    'game_state': 'ready',
    'game_cash': 10000000,
    'game_shares': 0,
    'game_current_step': 0,
    'game_df': None,
    'game_ticker': None,
    'game_name': None,
    'game_news_cache': {}
}
for k, v in game_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

analyst_defaults = {
    'analyzed': False,
    'current_ticker': None,
    'current_name': None,
    'market_type': None,
    'news_result_text': None,
    'news_links': None,
    'last_query': None,
    'rec_beginner': None,
    'rec_expert': None,
}
for k, v in analyst_defaults.items():
    if k not in st.session_state: st.session_state[k] = v

# ==========================================
# 3. 공통 유틸리티 함수
# ==========================================

def detect_market(query: str):
    query = query.strip()
    if re.fullmatch(r'[A-Z]{1,5}', query): return 'US_TICKER', query.upper()
    if re.fullmatch(r'[a-zA-Z\s\.\-&]+', query): return 'US_NAME', query
    return 'KR', query

def initialize_database():
    db_file = "stocks.db"
    if not os.path.exists(db_file):
        try:
            df_krx = fdr.StockListing('KRX')
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            cursor.execute("CREATE TABLE IF NOT EXISTS stock_info (code TEXT, name TEXT, market TEXT)")
            for _, row in df_krx.iterrows():
                cursor.execute("INSERT INTO stock_info VALUES (?, ?, ?)", (row['Code'], row['Name'], row['Market']))
            conn.commit(); conn.close()
        except: pass

def get_ticker_from_db(stock_name: str):
    initialize_database()
    try:
        conn = sqlite3.connect("stocks.db")
        cursor = conn.cursor()
        cursor.execute("SELECT code, name, market FROM stock_info WHERE name LIKE ?", (f"%{stock_name}%",))
        results = cursor.fetchall(); conn.close()
        if not results: return None, None
        best_match = min(results, key=lambda x: len(x[1]))
        ticker = best_match[0] + (".KS" if best_match[2] == 'KOSPI' else ".KQ")
        return ticker, best_match[1]
    except: return None, None

def analyze_with_gemini(content_type: str, content_data, market_type: str = 'KR'):
    if not API_KEY:
        return "❌ API 키가 설정되지 않아 분석을 수행할 수 없습니다."
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")
        if content_type == "text":
            prompt = f"주식 분석 리포트를 작성해줘. [데이터]\n{content_data}\n양식: 요약, 의견, 리스크/호재."
            return model.generate_content(prompt).text
        elif content_type == "game_news":
            ticker, name, date_str = content_data
            prompt = f"""당신은 전문 경제 분석가입니다. {date_str} 당시의 시장 상황을 분석해주세요.
            지침: 종목명 '{name}'이나 티커 '{ticker}'를 절대 직접 언급하지 말고 '이 기업' 등으로 지칭하세요. 
            당시의 실제 주요 뉴스 3가지를 제목과 요약으로 한국어로 작성해줘."""
            return model.generate_content(prompt).text
        return "분석 유형 오류"
    except Exception as e: return f"❌ AI 분석 에러: {e}"

# ==========================================
# 4. 차트 게임 유틸리티
# ==========================================
@st.cache_data
def get_game_stock_list():
    try: return fdr.StockListing('KRX')[lambda x: x['Market'] == 'KOSPI']
    except: return pd.DataFrame()

def start_game():
    st.session_state.game_state = 'playing'
    st.session_state.game_cash = 10000000
    st.session_state.game_shares = 0
    st.session_state.game_current_step = 60
    st.session_state.game_news_cache = {}
    
    krx_list = get_game_stock_list()
    if krx_list.empty: return
    
    # 사용자 요청: 기간을 2019년부터 2025년으로 설정 (데이터 확보를 위해 시작일은 2019~2023 범위로 권장)
    start_year = random.randint(2019, 2023) 
    start_month = random.randint(1, 12)
    start_day = random.randint(1, 28)
    
    start_date = datetime(start_year, start_month, start_day)
    end_date = start_date + timedelta(days=500)
    
    for _ in range(15):
        stock = krx_list.sample(1).iloc[0]
        ticker = stock['Code'] + ".KS"
        try:
            df = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'), progress=False)
            if len(df) > 100:
                if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                st.session_state.game_df = df
                st.session_state.game_ticker = ticker
                st.session_state.game_name = stock['Name']
                return
        except: continue

# ==========================================
# 5. 사이드바
# ==========================================
with st.sidebar:
    st.title("🤖 AI 주식 마스터")
    st.session_state.page = st.radio("📂 메뉴", ["🎮 차트 게임", "📊 종목 분석", "💱 환율", "⭐ 추천 종목"])
    
    # API 키 입력 필드 (보안을 위해 환경변수가 없을 경우에만 권장)
    if not API_KEY:
        user_api_key = st.text_input("🔑 Gemini API Key 입력", type="password")
        if user_api_key:
            genai.configure(api_key=user_api_key)
            API_KEY = user_api_key
            st.rerun()

    st.divider()
    if st.session_state.page == "📊 종목 분석":
        query = st.text_input("종목명 또는 티커", placeholder="예: 삼성전자 / AAPL")
        if st.button("🔎 분석 시작", use_container_width=True):
            if query:
                m_guess, clean_q = detect_market(query)
                if m_guess == 'KR': t, n = get_ticker_from_db(clean_q); mt = 'KR'
                else: 
                    try:
                        s = yf.Ticker(clean_q); info = s.info
                        t = clean_q; n = info.get('shortName', clean_q); mt = 'US'
                    except: t = None
                if t: st.session_state.update({'analyzed': True, 'current_ticker': t, 'current_name': n, 'market_type': mt})
                else: st.error("종목을 찾지 못했습니다.")

# ==========================================
# 6. 메인 페이지
# ==========================================

if st.session_state.page == "🎮 차트 게임":
    st.title("🎮 블라인드 차트 게임 (2019-2025)")
    
    if st.session_state.game_state == 'ready':
        st.markdown("### 📈 2019년 이후의 차트와 뉴스로 투자하세요!")
        if st.button("🚀 게임 시작", type="primary"):
            with st.spinner("데이터 로딩 중..."): start_game()
            st.rerun()
            
    elif st.session_state.game_state in ['playing', 'ended']:
        df = st.session_state.game_df
        step = st.session_state.game_current_step
        visible_df = df.iloc[:step]
        current_date = visible_df.index[-1]
        price = float(visible_df.iloc[-1]['Close'])
        assets = st.session_state.game_cash + (st.session_state.game_shares * price)
        
        c_dash = st.columns(4)
        c_dash[0].metric("총 자산", f"{int(assets):,}원")
        c_dash[1].metric("수익률", f"{((assets-10000000)/10000000)*100:.2f}%")
        c_dash[2].metric("현재가", f"{int(price):,}원")
        c_dash[3].metric("현재 날짜", current_date.strftime('%Y-%m-%d') if st.session_state.game_state == 'ended' else "???-??-??")
        
        col_main, col_news = st.columns([2, 1])
        with col_main:
            p_df = visible_df.copy()
            if st.session_state.game_state == 'playing': p_df.index = range(len(p_df))
            fig = go.Figure(data=[go.Candlestick(x=p_df.index, open=p_df['Open'], high=p_df['High'], low=p_df['Low'], close=p_df['Close'], increasing_line_color='red', decreasing_line_color='blue')])
            fig.update_layout(height=450, xaxis_rangeslider_visible=False, template="plotly_white", margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, use_container_width=True)
            
            if st.session_state.game_state == 'playing':
                ctrl = st.columns(4)
                if ctrl[0].button("🔴 매수", use_container_width=True):
                    buy = int(st.session_state.game_cash // price)
                    if buy > 0: st.session_state.game_shares += buy; st.session_state.game_cash -= buy * price; st.rerun()
                if ctrl[1].button("🔵 매도", use_container_width=True):
                    st.session_state.game_cash += st.session_state.game_shares * price; st.session_state.game_shares = 0; st.rerun()
                if ctrl[2].button("▶️ 진행", use_container_width=True):
                    if step + 5 < len(df): st.session_state.game_current_step += 5; st.rerun()
                    else: st.session_state.game_state = 'ended'; st.rerun()
                if ctrl[3].button("🛑 종료", use_container_width=True):
                    st.session_state.game_state = 'ended'; st.rerun()
            else:
                st.success(f"결과: {st.session_state.game_name} ({st.session_state.game_ticker})")
                if st.button("🔄 다시 하기"): st.session_state.game_state = 'ready'; st.rerun()

        with col_news:
            st.subheader("📰 당시 주요 뉴스 (AI)")
            news_key = f"{current_date.year}-{current_date.month}"
            if news_key not in st.session_state.game_news_cache:
                with st.spinner("뉴스 분석 중..."):
                    st.session_state.game_news_cache[news_key] = analyze_with_gemini("game_news", (st.session_state.game_ticker, st.session_state.game_name, current_date.strftime('%Y년 %m월')))
            st.markdown(f'<div class="game-news-container"><b>📍 {current_date.year}년 {current_date.month}월 시장 요약</b><br><br>{st.session_state.game_news_cache[news_key]}</div>', unsafe_allow_html=True)

# (종목 분석, 환율, 추천 페이지는 동일하게 유지)
elif st.session_state.page == "📊 종목 분석":
    st.title("📊 AI 주식 애널리스트 Pro")
    if st.session_state.analyzed:
        ticker, name = st.session_state.current_ticker, st.session_state.current_name
        st.subheader(f"{name} ({ticker})")
        col_c, col_a = st.columns([1, 1])
        with col_c:
            dv = yf.Ticker(ticker).history(period="6mo")
            st.plotly_chart(go.Figure(data=[go.Candlestick(x=dv.index, open=dv['Open'], high=dv['High'], low=dv['Low'], close=dv['Close'])]).update_layout(height=400, xaxis_rangeslider_visible=False), use_container_width=True)
        with col_a:
            if st.button("📰 AI 분석"):
                res = DDGS().text(f"{name} 주가 전망", max_results=5)
                st.session_state.news_result_text = analyze_with_gemini("text", "".join([f"{r['title']}\n" for r in res]))
            if st.session_state.news_result_text: st.markdown(st.session_state.news_result_text)
    else: st.info("사이드바에서 검색하세요.")

elif st.session_state.page == "💱 환율":
    st.title("💱 환율")
    c1, c2 = st.columns(2)
    def fx(s, l):
        d = yf.Ticker(s).history(period="3mo")
        st.metric(l, f"{d['Close'].iloc[-1]:,.2f} 원")
        st.plotly_chart(go.Figure(go.Scatter(x=d.index, y=d['Close'], fill='tozeroy')).update_layout(height=250), use_container_width=True)
    with c1: fx("USDKRW=X", "USD/KRW")
    with c2: fx("JPYKRW=X", "JPY/KRW (100엔)")

elif st.session_state.page == "⭐ 추천 종목":
    st.title("⭐ 추천 종목")
    if st.button("✨ 생성"): st.session_state.rec_beginner = analyze_with_gemini("recommend", "beginner")
    if st.session_state.rec_beginner: st.markdown(st.session_state.rec_beginner)
