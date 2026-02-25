# version 6.0 - AI Investment Simulator (Backtesting Edition)

import streamlit as st
import os
import yfinance as yf
import pandas as pd
import google.generativeai as genai
import plotly.graph_objects as go
from datetime import datetime, timedelta
import FinanceDataReader as fdr

# ==========================================
# 1. 초기 설정 및 세션 상태 관리
# ==========================================
st.set_page_config(page_title="AI 시뮬레이션 투자", page_icon="💰", layout="wide")

# API 설정
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=API_KEY)

# 세션 상태 초기화 (게임 데이터 저장)
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
    .reportview-container { background: #F0F2F6; }
    .stMetric { background: white; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .news-box { background: #E1E8EB; padding: 15px; border-radius: 8px; border-left: 5px solid #00B496; margin-bottom: 10px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 핵심 로직 함수
# ==========================================

def get_historical_data(ticker, start_year):
    """2019년부터 2025년까지의 데이터 로드"""
    start_date = f"{start_year}-01-01"
    end_date = "2025-12-31"
    try:
        df = yf.download(ticker, start=start_date, end=end_date)
        return df
    except:
        return pd.DataFrame()

def get_ai_context(ticker, current_date):
    """당시의 시장 상황 및 뉴스 요약 (Gemini 활용)"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    date_str = current_date.strftime("%Y년 %m월")
    
    prompt = f"""
    당신은 경제 역사학자이자 분석가입니다. {date_str} 당시 {ticker} 종목과 관련된 
    실제 주요 경제 뉴스, 시장 분위기, 그리고 기업의 주요 이슈를 3가지 핵심 요약해서 알려주세요.
    또한, 당시의 전반적인 코스피/나스닥 분위기도 짧게 언급해줘.
    형식:
    1. [뉴스/이슈 제목] 내용
    2. [뉴스/이슈 제목] 내용
    3. [뉴스/이슈 제목] 내용
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except:
        return "당시 뉴스를 불러오는 데 실패했습니다."

def get_stock_info_summary(ticker):
    """종목의 핵심 정보 3가지 요약"""
    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"{ticker} 주식에 대해 투자자가 반드시 알아야 할 비즈니스 모델 및 핵심 강점 3가지를 아주 간단하게 요약해줘."
    try:
        return model.generate_content(prompt).text
    except:
        return "정보를 가져올 수 없습니다."

# ==========================================
# 3. 메인 UI 및 게임 컨트롤
# ==========================================

st.title("🚀 AI 과거 데이터 모의투자 시뮬레이터")

# 사이드바: 설정 섹션
with st.sidebar:
    st.header("⚙️ 시뮬레이션 설정")
    if not st.session_state.sim_active:
        ticker_input = st.text_input("종목 티커 (예: 005930.KS, AAPL)", value="005930.KS")
        start_year = st.selectbox("시작 연도 선택", [2019, 2020, 2021, 2022, 2023, 2024])
        
        if st.button("시뮬레이션 시작"):
            df = get_historical_data(ticker_input, start_year)
            if not df.empty:
                st.session_state.sim_active = True
                st.session_state.ticker = ticker_input
                st.session_state.current_date = df.index[0]
                st.session_state.balance = 1000000
                st.session_state.shares = 0
                st.session_state.avg_price = 0
                st.rerun()
            else:
                st.error("데이터를 불러올 수 없습니다.")
    else:
        if st.button("시뮬레이션 종료/리셋"):
            st.session_state.sim_active = False
            st.rerun()

# 메인 화면: 게임 진행
if st.session_state.sim_active:
    df = get_historical_data(st.session_state.ticker, 2019) # 전체 데이터 로드
    if df.empty:
        st.error("데이터를 불러오는데 실패했습니다.")
        st.session_state.sim_active = False
        st.rerun()
        
    # 현재 날짜 기준 데이터 추출
    current_data = df.loc[:st.session_state.current_date].tail(30) # 최근 30일치 차트용
    current_price = df.loc[st.session_state.current_date]['Close']
    if isinstance(current_price, pd.Series): current_price = float(current_price.iloc[0])
    else: current_price = float(current_price)

    # 상단 정보 바
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("현재 시뮬레이션 날짜", st.session_state.current_date.strftime("%Y-%m-%d"))
    m2.metric("보유 자금", f"{int(st.session_state.balance):,}원")
    m3.metric("보유 주식", f"{st.session_state.shares}주")
    
    total_value = st.session_state.balance + (st.session_state.shares * current_price)
    profit = ((total_value - 1000000) / 1000000) * 100
    m4.metric("총 자산 (수익률)", f"{int(total_value):,}원", f"{profit:.2f}%")

    col_left, col_right = st.columns([2, 1])

    with col_left:
        # 1. 차트 표시
        fig = go.Figure(data=[go.Candlestick(x=current_data.index,
                        open=current_data['Open'], high=current_data['High'],
                        low=current_data['Low'], close=current_data['Close'])])
        fig.update_layout(title=f"{st.session_state.ticker} 과거 차트 (현재가: {current_price:,.0f})", xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        # 2. 투자 결정 버튼
        st.subheader("🛠 투자 결정")
        c1, c2, c3, c4 = st.columns(4)
        
        # 매수 로직
        if c1.button("💰 매수 (All-In)"):
            if st.session_state.balance > current_price:
                new_shares = int(st.session_state.balance // current_price)
                st.session_state.avg_price = ((st.session_state.avg_price * st.session_state.shares) + (new_shares * current_price)) / (st.session_state.shares + new_shares)
                st.session_state.shares += new_shares
                st.session_state.balance -= (new_shares * current_price)
                st.success(f"{new_shares}주 매수 완료!")
        
        # 물타기/추가매수 (남은 돈의 50%)
        if c2.button("💧 물타기 (50%)"):
            if st.session_state.balance > current_price:
                buy_money = st.session_state.balance * 0.5
                new_shares = int(buy_money // current_price)
                st.session_state.avg_price = ((st.session_state.avg_price * st.session_state.shares) + (new_shares * current_price)) / (st.session_state.shares + new_shares)
                st.session_state.shares += new_shares
                st.session_state.balance -= (new_shares * current_price)
                st.info(f"평균단가 조절: {st.session_state.avg_price:,.0f}원")

        # 매도 로직
        if c3.button("🚪 전량 매도"):
            if st.session_state.shares > 0:
                st.session_state.balance += (st.session_state.shares * current_price)
                st.session_state.shares = 0
                st.session_state.avg_price = 0
                st.warning("전량 매도 완료!")

        # 다음 단계
        if c4.button("⏩ 다음 달로 이동"):
            current_idx = df.index.get_loc(st.session_state.current_date)
            if current_idx + 20 < len(df): # 약 한 달(20영업일) 뒤로
                st.session_state.current_date = df.index[current_idx + 20]
                st.rerun()
            else:
                st.error("시뮬레이션 데이터가 끝났습니다.")

    with col_right:
        # 3. 당시 뉴스 요약 (AI)
        st.subheader("📰 당시 주요 뉴스 & 상황")
        with st.expander("뉴스 보기 (AI 분석)", expanded=True):
            news_context = get_ai_context(st.session_state.ticker, st.session_state.current_date)
            st.write(news_context)

        # 4. 종목 핵심 정보 3가지
        st.subheader("🔍 종목 핵심 요약")
        st.info(get_stock_info_summary(st.session_state.ticker))
        
        if st.session_state.shares > 0:
            st.divider()
            st.write(f"**현재 평단가:** {st.session_state.avg_price:,.0f}원")
            st.write(f"**현재가 대비:** {((current_price - st.session_state.avg_price)/st.session_state.avg_price*100):.2f}%")

else:
    st.info("왼쪽 사이드바에서 종목과 시작 연도를 선택하고 '시뮬레이션 시작'을 눌러주세요.")
    st.write("---")
    st.subheader("💡 이 시뮬레이터의 포인트")
    st.write("1. **과거 데이터 기반**: 2019~2025년 실제 주가 데이터로 실습합니다.")
    st.write("2. **AI 상황 재구성**: 선택한 시점의 실제 경제 뉴스를 AI가 요약해 의사결정을 돕습니다.")
    st.write("3. **투자 전략 연습**: 매수, 매도뿐만 아니라 물타기를 통한 평단가 관리 전략을 연습할 수 있습니다.")
