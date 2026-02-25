# version 7.0 - AI Multi-Stock Portfolio Simulator

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
# 1. 초기 설정 및 세션 상태 (포트폴리오 구조)
# ==========================================
st.set_page_config(page_title="AI 멀티 포트폴리오 시뮬레이터", page_icon="💼", layout="wide")

# API 설정
try: 
    API_KEY = st.secrets["GEMINI_API_KEY"]
except: 
    API_KEY = os.getenv("GEMINI_API_KEY", "")
genai.configure(api_key=API_KEY)

# 세션 상태 초기화
if 'cash' not in st.session_state:
    st.session_state.update({
        'cash': 1000000,
        'portfolio': {},      # {ticker: {'shares': 0, 'avg_price': 0}}
        'current_date': None,
        'selected_ticker': "005930.KS",
        'start_year': 2020
    })

# 스타일
st.markdown("""
<style>
    .stMetric { background: #FFFFFF; padding: 15px; border-radius: 10px; border: 1px solid #EEE; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }
    .portfolio-card { background: #F0F4F8; padding: 15px; border-radius: 10px; border-left: 5px solid #00B496; margin-bottom: 10px; }
    .news-box { background: #F9F9F9; padding: 15px; border-radius: 10px; border: 1px solid #E0E0E0; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 유틸리티 함수
# ==========================================

@st.cache_data
def get_company_name(ticker):
    """티커를 회사명으로 변환 (뉴스 검색용)"""
    try:
        df_krx = fdr.StockListing('KRX')
        clean_ticker = ticker.replace('.KS', '').replace('.KQ', '')
        match = df_krx[df_krx['Code'] == clean_ticker]
        if not match.empty:
            return match.iloc[0]['Name']
        return ticker
    except:
        return ticker

@st.cache_data(ttl=3600)
def get_stock_data(ticker, start_year):
    """주가 데이터 로드"""
    try:
        df = yf.download(ticker, start=f"{start_year}-01-01", end="2025-12-31")
        if df.empty: return None
        if isinstance(df.columns, pd.MultiIndex): 
            df.columns = df.columns.get_level_values(0)
        return df
    except: 
        return None

def get_ai_news_analysis(ticker, date):
    """실제 뉴스 검색 및 AI 요약"""
    company_name = get_company_name(ticker)
    query = f"{company_name} {date.year}년 {date.month}월 주요 뉴스"
    
    real_news_snippet = ""
    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=3))
            if results:
                real_news_snippet = "\n".join([r['title'] for r in results])
            else:
                real_news_snippet = "검색된 뉴스 제목이 없습니다."
    except: 
        real_news_snippet = "뉴스 검색 서비스를 이용할 수 없습니다."

    model = genai.GenerativeModel('gemini-1.5-flash')
    prompt = f"""
    당신은 전문 경제 분석가입니다. {date.strftime('%Y년 %m월')} 당시 {company_name}({ticker})의 시장 상황을 분석해주세요.
    검색된 뉴스 키워드: {real_news_snippet}
    
    위 정보와 당신의 지식을 결합해 당시 투자자가 반드시 알아야 했던 핵심 뉴스 3가지를 
    제목과 요약 내용으로 구성해 한국어로 작성해줘. 
    당시의 실제 경제 상황(코로나, 금리, 기업 이슈 등)을 반영해야 해.
    """
    try:
        response = model.generate_content(prompt)
        return response.text
    except: 
        return "AI 분석을 가져오는 데 실패했습니다."

# ==========================================
# 3. 메인 UI
# ==========================================

# 사이드바: 설정 및 포트폴리오 현황
with st.sidebar:
    st.title("💼 My Portfolio")
    
    if st.session_state.current_date is None:
        st.subheader("시뮬레이션 시작 설정")
        start_year = st.selectbox("시작 연도", [2019, 2020, 2021, 2022, 2023, 2024], index=1)
        if st.button("🚀 시뮬레이션 시작"):
            st.session_state.start_year = start_year
            st.session_state.current_date = datetime(start_year, 1, 2)
            st.rerun()
    else:
        st.metric("현금 잔고", f"{int(st.session_state.cash):,}원")
        st.write("---")
        st.subheader("📦 보유 종목 현황")
        
        has_holdings = False
        for t, info in st.session_state.portfolio.items():
            if info['shares'] > 0:
                has_holdings = True
                with st.container():
                    st.markdown(f"""
                    <div class="portfolio-card">
                        <b>{t}</b><br>
                        {info['shares']}주 보유<br>
                        평단: {int(info['avg_price']):,}원
                    </div>
                    """, unsafe_allow_html=True)
        
        if not has_holdings:
            st.write("현재 보유 중인 종목이 없습니다.")

        st.write("---")
        if st.button("⏪ 전체 리셋"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

# 메인 화면
if st.session_state.current_date:
    st.title(f"🚀 AI 자산 관리 시뮬레이터")
    st.subheader(f"📅 현재 시점: {st.session_state.current_date.strftime('%Y-%m-%d')}")
    
    # 1. 종목 검색 및 선택
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        ticker_input = st.text_input("분석 및 거래할 종목 입력 (예: 삼성전자 티커 005930.KS, NVDA, TSLA)", value=st.session_state.selected_ticker)
    with search_col2:
        if st.button("🔍 종목 조회"):
            st.session_state.selected_ticker = ticker_input
            st.rerun()

    # 데이터 로드
    df = get_stock_data(st.session_state.selected_ticker, st.session_state.start_year)
    
    if df is not None and not df.empty:
        # 현재 날짜의 가격 정보 가져오기
        try:
            available_dates = df.index[df.index <= st.session_state.current_date]
            if len(available_dates) == 0:
                st.warning("선택한 시점에 데이터가 없습니다. 시간을 더 진행시켜 보세요.")
                current_price = 0
            else:
                current_date_actual = available_dates[-1]
                current_price = float(df.loc[current_date_actual]['Close'])
        except: 
            current_price = 0

        # UI 레이아웃
        col_main, col_info = st.columns([2, 1])

        with col_main:
            # 차트
            hist_view = df.loc[:st.session_state.current_date].tail(50)
            fig = go.Figure(data=[go.Candlestick(
                x=hist_view.index, 
                open=hist_view['Open'], 
                high=hist_view['High'], 
                low=hist_view['Low'], 
                close=hist_view['Close'],
                name='Price'
            )])
            fig.update_layout(
                title=f"{st.session_state.selected_ticker} 주가 흐름 (현재가: {current_price:,.0f}원)", 
                xaxis_rangeslider_visible=False,
                height=500,
                template="plotly_white"
            )
            st.plotly_chart(fig, use_container_width=True)

            # 거래 섹션
            st.subheader("💳 주식 거래")
            t_col1, t_col2, t_col3 = st.columns([1, 1, 1])
            amount = t_col1.number_input("거래 수량(주)", min_value=1, value=1, step=1)
            
            if t_col2.button("🛒 매수하기", use_container_width=True):
                if current_price > 0:
                    cost = amount * current_price
                    if st.session_state.cash >= cost:
                        p = st.session_state.portfolio.get(st.session_state.selected_ticker, {'shares': 0, 'avg_price': 0})
                        new_shares = p['shares'] + amount
                        new_avg = ((p['avg_price'] * p['shares']) + cost) / new_shares
                        st.session_state.portfolio[st.session_state.selected_ticker] = {'shares': new_shares, 'avg_price': new_avg}
                        st.session_state.cash -= cost
                        st.success(f"{st.session_state.selected_ticker} {amount}주 매수 성공!")
                        st.rerun()
                    else: 
                        st.error("현금 잔고가 부족합니다.")
                else:
                    st.error("유효한 가격 데이터가 없습니다.")

            if t_col3.button("💰 매도하기", use_container_width=True):
                p = st.session_state.portfolio.get(st.session_state.selected_ticker, {'shares': 0, 'avg_price': 0})
                if p['shares'] >= amount:
                    st.session_state.cash += (amount * current_price)
                    p['shares'] -= amount
                    st.session_state.portfolio[st.session_state.selected_ticker] = p
                    st.warning(f"{st.session_state.selected_ticker} {amount}주 매도 성공!")
                    st.rerun()
                else: 
                    st.error("보유 수량이 부족합니다.")

        with col_info:
            # 뉴스 분석
            st.subheader("📰 당시 주요 뉴스 (AI)")
            if current_price > 0:
                with st.container():
                    with st.spinner("당시 시장 상황 분석 중..."):
                        analysis = get_ai_news_analysis(st.session_state.selected_ticker, st.session_state.current_date)
                        st.markdown(f'<div class="news-box">{analysis}</div>', unsafe_allow_html=True)
            
            st.divider()
            st.subheader("⌛ 시간 관리")
            if st.button("⏩ 한 달 뒤로 이동 (30일)", use_container_width=True):
                st.session_state.current_date += timedelta(days=30)
                st.rerun()
            
            # 자산 총계 요약
            st.write("---")
            total_stock_value = 0
            for t, info in st.session_state.portfolio.items():
                # 간단한 평가를 위해 현재 조회 중인 종목만 실시간 가격 반영 (다른 종목은 평단 기준 혹은 추가 조회 필요)
                # 여기서는 구현 단순화를 위해 보유 종목 리스트만 사이드바에 표시
                pass

    else:
        st.error(f"'{st.session_state.selected_ticker}' 데이터를 불러올 수 없습니다. 티커 형식을 확인해 주세요. (예: 삼성전자 005930.KS, 애플 AAPL)")
else:
    st.info("왼쪽 사이드바에서 시뮬레이션 시작 연도를 선택하고 '시뮬레이션 시작'을 눌러주세요.")
    st.markdown("""
    ### 💡 사용 방법
    1. **시작 연도 선택**: 2019~2024년 중 원하는 시점을 선택합니다.
    2. **종목 조회**: 중앙 상단에 종목 티커를 입력하고 조회를 누릅니다.
    3. **뉴스 확인**: 당시의 실제 뉴스를 AI가 요약해줍니다. 이를 바탕으로 투자를 결정하세요.
    4. **거래**: 원하는 수량만큼 매수/매도하여 포트폴리오를 구성합니다.
    5. **시간 여행**: '한 달 뒤로 이동'을 눌러 나의 투자 결과를 확인하고 다음 결정을 내립니다.
    """)
