# version 6.1 - AI Investment Simulator (Enhanced News & Navigation)

import streamlit as st
import os
import yfinance as yf
import pandas as pd
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime, timedelta
import FinanceDataReader as fdr
from duckduckgo_search import DDGS

# ==========================================
# 1. 초기 설정 및 세션 상태 관리
# ==========================================
st.set_page_config(page_title="AI 시뮬레이션 투자 Pro", page_icon="📈", layout="wide")

# API 설정
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=API_KEY)

# 세션 상태 초기화
if 'sim_active' not in st.session_state:
    st.session_state.update({
        'sim_active': False,
        'balance': 1000000,
        'shares': 0,
        'avg_price': 0,
        'current_date': None,
        'ticker': "",
        'history': [],
        'log': []
    })

# 스타일
st.markdown("""
<style>
    .stMetric { background: #FFFFFF; padding: 20px; border-radius: 15px; border: 1px solid #E0E0E0; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
    .news-card { background: #F8F9FA; padding: 15px; border-left: 5px solid #00B496; border-radius: 5px; margin-bottom: 10px; }
    .info-box { background: #E3F2FD; padding: 15px; border-radius: 10px; border: 1px solid #BBDEFB; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 핵심 로직 함수
# ==========================================

@st.cache_data(ttl=3600)
def get_historical_data(ticker, start_year):
    """데이터 로드 및 유효성 검사"""
    try:
        start_date = f"{start_year}-01-01"
        end_date = "2025-12-31"
        df = yf.download(ticker, start=start_date, end=end_date)
        if df.empty: return None
        # 데이터가 MultiIndex인 경우 처리 (yfinance 최신 버전 대응)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        return df
    except Exception as e:
        st.error(f"데이터 로드 오류: {e}")
        return None

def fetch_real_news(ticker, date):
    """DuckDuckGo를 통해 당시의 실제 뉴스 검색 시도"""
    query = f"{ticker} {date.year}년 {date.month}월 뉴스"
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if results:
                news_text = "\n".join([f"- {r['title']}" for r in results])
                return news_text
            return "검색된 실제 뉴스 데이터가 부족합니다."
    except:
        return "뉴스 검색 서비스를 일시적으로 사용할 수 없습니다."

def get_ai_news_summary(ticker, current_date):
    """검색된 뉴스 + AI 지식을 결합한 당시 상황 요약"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    real_news = fetch_real_news(ticker, current_date)
    date_str = current_date.strftime("%Y년 %m월")
    
    prompt = f"""
    당신은 금융 분석가입니다. {date_str} 당시 {ticker} 종목의 상황을 분석해주세요.
    참고할 실제 뉴스 키워드: {real_news}
    
    위 정보와 당신의 지식을 바탕으로 당시 투자자들이 주목했던 이슈 3가지를 
    '[제목] 내용' 형식으로 한국어로 아주 짧고 명확하게 작성해주세요.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "AI 분석을 불러올 수 없습니다."

@st.cache_data
def get_stock_key_points(ticker):
    """종목 핵심 정보 3가지 요약"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"{ticker} 종목에 대해 투자자가 반드시 알아야 할 핵심 정보(비즈니스 모델, 시장 지위, 리스크 등) 3가지를 요약해줘."
    try:
        return model.generate_content(prompt).text
    except:
        return "정보를 가져올 수 없습니다."

# ==========================================
# 3. 메인 UI 및 컨트롤
# ==========================================

st.sidebar.title("🔍 시뮬레이션 제어")

# [수정 1] 언제든 종목을 변경할 수 있도록 입력창 상시 노출
with st.sidebar:
    new_ticker = st.text_input("종목 변경/검색", value=st.session_state.ticker if st.session_state.ticker else "005930.KS")
    new_year = st.selectbox("시작 연도", [2019, 2020, 2021, 2022, 2023, 2024], index=1)
    
    if st.button("🚀 새로운 시뮬레이션 시작"):
        df_check = get_historical_data(new_ticker, new_year)
        if df_check is not None:
            st.session_state.update({
                'sim_active': True,
                'ticker': new_ticker,
                'current_date': df_check.index[0],
                'balance': 1000000,
                'shares': 0,
                'avg_price': 0,
                'history': []
            })
            st.rerun()
        else:
            st.error("유효하지 않은 종목 코드이거나 데이터가 없습니다.")

    if st.session_state.sim_active:
        st.divider()
        if st.button("❌ 시뮬레이션 초기화"):
            st.session_state.sim_active = False
            st.rerun()

# 게임 본문
if st.session_state.sim_active:
    df = get_historical_data(st.session_state.ticker, 2019)
    current_idx = df.index.get_loc(st.session_state.current_date)
    current_price = float(df.iloc[current_idx]['Close'])
    
    st.title(f"💹 {st.session_state.ticker} 투자 시뮬레이션")
    
    # 상단 대시보드
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재 날짜", st.session_state.current_date.strftime("%Y-%m-%d"))
    m2.metric("예수금", f"{int(st.session_state.balance):,}원")
    m3.metric("보유 주식", f"{st.session_state.shares}주")
    
    total_asset = st.session_state.balance + (st.session_state.shares * current_price)
    profit_rate = ((total_asset - 1000000) / 1000000) * 100
    m4.metric("총 자산 (수익률)", f"{int(total_asset):,}원", f"{profit_rate:.2f}%")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        # 차트
        hist_view = df.iloc[max(0, current_idx-40):current_idx+1]
        fig = go.Figure(data=[go.Candlestick(x=hist_view.index,
                        open=hist_view['Open'], high=hist_view['High'],
                        low=hist_view['Low'], close=hist_view['Close'])])
        fig.update_layout(title=f"주가 흐름 (현재가: {current_price:,.0f}원)", xaxis_rangeslider_visible=False, height=500)
        st.plotly_chart(fig, use_container_width=True)

        # 액션 버튼
        st.subheader("📝 투자 명령")
        act1, act2, act3, act4 = st.columns(4)
        
        if act1.button("💰 매수 (All-In)"):
            if st.session_state.balance >= current_price:
                new_shares = int(st.session_state.balance // current_price)
                st.session_state.avg_price = ((st.session_state.avg_price * st.session_state.shares) + (new_shares * current_price)) / (st.session_state.shares + new_shares)
                st.session_state.shares += new_shares
                st.session_state.balance -= (new_shares * current_price)
                st.success(f"{new_shares}주 매수 완료!")
        
        if act2.button("💧 물타기 (50%)"):
            if st.session_state.balance >= current_price:
                buy_amount = st.session_state.balance * 0.5
                new_shares = int(buy_amount // current_price)
                st.session_state.avg_price = ((st.session_state.avg_price * st.session_state.shares) + (new_shares * current_price)) / (st.session_state.shares + new_shares)
                st.session_state.shares += new_shares
                st.session_state.balance -= (new_shares * current_price)
                st.info(f"평단가 조절: {st.session_state.avg_price:,.0f}원")

        if act3.button("🚪 전량 매도"):
            if st.session_state.shares > 0:
                st.session_state.balance += (st.session_state.shares * current_price)
                st.session_state.shares = 0
                st.session_state.avg_price = 0
                st.warning("전량 매도 완료!")

        if act4.button("⏩ 다음 달 이동"):
            if current_idx + 20 < len(df):
                st.session_state.current_date = df.index[current_idx + 20]
                st.rerun()
            else:
                st.error("시뮬레이션 종료 시점입니다.")

    with col_right:
        # [수정 2] 뉴스 및 기사 섹션 강화
        st.subheader("📰 당시 주요 기사 요약")
        with st.container(border=True):
            with st.spinner("당시 뉴스를 수집 중..."):
                news = get_ai_news_summary(st.session_state.ticker, st.session_state.current_date)
                st.markdown(news)

        # [수정 3] 종목 핵심 요약 3가지
        st.subheader("💡 종목 투자 포인트")
        with st.container():
            points = get_stock_key_points(st.session_state.ticker)
            st.info(points)
        
        if st.session_state.shares > 0:
            st.divider()
            st.write(f"**보유 평단:** {st.session_state.avg_price:,.0f}원")
            diff = ((current_price - st.session_state.avg_price) / st.session_state.avg_price) * 100
            color = "red" if diff > 0 else "blue"
            st.write(f"**수익률:** :{color}[{diff:.2f}%]")

else:
    st.info("왼쪽 사이드바에서 종목(티커)과 시작 연도를 선택하고 '새로운 시뮬레이션 시작'을 눌러주세요.")
    st.write("---")
    st.markdown("""
    ### 시뮬레이션 가이드
    1. **종목 입력**: 삼성전자(005930.KS), 애플(AAPL), 테슬라(TSLA) 등 티커를 입력하세요.
    2. **뉴스 분석**: 매달 이동할 때마다 당시의 **실제 뉴스**를 기반으로 한 AI 요약이 제공됩니다.
    3. **전략 실습**: 하락장에서 '물타기'를 하거나, 뉴스에 따라 '전량 매도'하는 등 자신만의 전략을 테스트해보세요.
    """)
