# version 4.1 - AI Trading Pro (Fixed Edition)

import streamlit as st
import os
import time
import sqlite3
import re
import requests
import FinanceDataReader as fdr
import yt_dlp
import google.generativeai as genai
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
from duckduckgo_search import DDGS

# ==========================================
# 1. 설정 및 API 키
# ==========================================
try:
    API_KEY = st.secrets["GEMINI_API_KEY"]
except:
    # 환경변수에서 가져오거나 직접 입력
    API_KEY = os.getenv("GEMINI_API_KEY", "내_실제_키_입력")

genai.configure(api_key=API_KEY)

st.set_page_config(
    page_title="AI 주식 애널리스트 Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 디자인 토큰
IM_MINT   = "#00B496"
IM_DARK   = "#012E2A"
IM_BG     = "#F4F8F7"
IM_WHITE  = "#FFFFFF"
IM_BORDER = "#D0E8E4"
IM_TEXT   = "#1A1A1A"
IM_MUTED  = "#5A7068"
IM_UP     = "#0B8C5E"
IM_DOWN   = "#E05C5C"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
html, body, [class*="css"] {{ font-family: 'Noto Sans KR', sans-serif; background-color: {IM_BG}; color: {IM_TEXT}; }}
[data-testid="stSidebar"] {{ background-color: {IM_DARK} !important; }}
[data-testid="stSidebar"] * {{ color: #E8F5F2 !important; }}
.stButton > button {{ background-color: {IM_MINT} !important; color: white !important; font-weight: 600 !important; border-radius: 6px !important; border: none !important; }}
[data-testid="stMetric"] {{ background-color: {IM_WHITE}; border: 1px solid {IM_BORDER}; border-radius: 10px; padding: 1rem !important; box-shadow: 0 1px 4px rgba(0,0,0,0.04); }}
[data-testid="stMetricValue"] {{ font-size: 1.4rem !important; font-weight: 700 !important; }}
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. 세션 및 헬퍼 함수
# ==========================================
defaults = {'analyzed': False, 'current_ticker': None, 'current_name': None, 'market_type': None, 'page': '주식 분석'}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def detect_market(query: str):
    query = query.strip()
    if re.fullmatch(r'[A-Z]{1,5}', query): return 'US_TICKER', query.upper()
    if re.fullmatch(r'[a-zA-Z\s\.\-&]+', query): return 'US_NAME', query
    return 'KR', query

# ==========================================
# 3. 데이터 로드 및 지표 계산
# ==========================================
def get_stock_data_with_indicators(ticker: str, period: str = "6mo"):
    try:
        df = yf.Ticker(ticker).history(period=period)
        if not df.empty and len(df) >= 20:
            df['MA20'] = df['Close'].rolling(window=20).mean()
            std = df['Close'].rolling(window=20).std()
            df['Upper'] = df['MA20'] + (std * 2)
            df['Lower'] = df['MA20'] - (std * 2)
        return df
    except:
        return pd.DataFrame()

@st.cache_data(ttl=600)
def get_trending_stocks():
    """네이버 금융 실시간 거래량 순위 (헤더 추가로 403 방지)"""
    try:
        url = 'https://finance.naver.com/sise/sise_quant.naver'
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
        res = requests.get(url, headers=headers)
        tables = pd.read_html(res.text, encoding='euc-kr')
        df = tables[1].dropna(how='all')
        # 종목명 열이 있는지 확인 후 필터링
        df = df[df['종목명'].notna()]
        df = df[['종목명', '현재가', '전일비', '등락률', '거래량']].head(10)
        return df
    except Exception as e:
        st.error(f"데이터 수집 중 오류: {e}")
        return None

# ==========================================
# 4. AI 뉴스 분석
# ==========================================
def get_news_analysis_with_ai(keyword: str, market_type: str, price_info: dict):
    try:
        q = f"{keyword} stock news" if market_type == 'US' else f"{keyword} 주식 뉴스"
        
        # DDGS 사용 방식 수정 (Context Manager 사용)
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(q, max_results=3):
                results.append(r)
        
        if not results:
            return "최근 뉴스를 찾을 수 없습니다.", None
        
        news_text = "".join(f"- {r['title']}\n  {r['body']}\n" for r in results)
        
        # 모델명 유지: gemini-2.5-flash
        model = genai.GenerativeModel("models/gemini-2.5-flash")
        
        prompt = f"""
        당신은 탑티어 주식 트레이더입니다. 다음 데이터를 바탕으로 투자자에게 명쾌한 조언을 해주세요.
        
        [종목]: {keyword}
        [현재가]: {price_info['close']:,.0f}
        [지지선(하단)]: {price_info['lower']:,.0f}
        [저항선(상단)]: {price_info['upper']:,.0f}
        
        [최근 핵심 뉴스 3개]
        {news_text}
        
        위 기술적 지표와 뉴스를 종합하여 다음 양식으로 답변하세요:
        ### 🎯 AI 매매 포지션: [매수 / 매도 / 관망] 중 택 1
        **💡 핵심 이유 (3줄 요약):**
        1. 
        2. 
        3. 
        """
        response = model.generate_content(prompt)
        return response.text, results
    except Exception as e:
        return f"AI 분석 중 오류 발생: {e}", None

def get_ticker_from_db(stock_name: str):
    db_file = "stocks.db"
    if not os.path.exists(db_file):
        try:
            df_krx = fdr.StockListing('KRX')
            conn = sqlite3.connect(db_file)
            df_krx[['Code', 'Name', 'Market']].to_sql('stock_info', conn, if_exists='replace', index=False)
            conn.close()
        except: return None, None
    try:
        conn = sqlite3.connect(db_file)
        c = conn.cursor()
        c.execute("SELECT Code, Name, Market FROM stock_info WHERE Name LIKE ?", (f"%{stock_name}%",))
        res = c.fetchall()
        conn.close()
        if res:
            best = min(res, key=lambda x: len(x[1]))
            suffix = ".KS" if best[2] == 'KOSPI' else ".KQ"
            return best[0] + suffix, best[1]
    except: pass
    return None, None

def validate_us_ticker(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="1d")
        if not hist.empty:
            return ticker, stock.info.get('shortName', ticker)
    except: pass
    return None, None

def get_us_ticker_by_name(name: str):
    try:
        search = yf.Search(name, max_results=1)
        if search.quotes:
            return search.quotes[0]['symbol'], search.quotes[0].get('shortname', name)
    except: pass
    return None, None

# ==========================================
# 5. 사이드바
# ==========================================
with st.sidebar:
    st.markdown("### 🤖 AI 트레이딩 비서")
    st.markdown("---")
    page = st.sidebar.selectbox("메뉴 선택", ["주식 분석", "🔥 시장 트렌드", "💱 환율", "⭐ 추천 종목"])
    st.session_state['page'] = page
    st.markdown("---")

    if page == "주식 분석":
        query = st.text_input("종목명 또는 티커 검색", placeholder="삼성전자 / AAPL")
        if st.button("분석 시작", use_container_width=True) and query:
            ticker, name, mtype = None, None, 'KR'
            mg, cq = detect_market(query)
            with st.spinner("종목 검색 중..."):
                if mg == 'US_TICKER': ticker, name = validate_us_ticker(cq); mtype = 'US'
                elif mg == 'US_NAME': ticker, name = get_us_ticker_by_name(cq); mtype = 'US'
                else: ticker, name = get_ticker_from_db(cq); mtype = 'KR'
            
            if ticker:
                st.session_state.update({'analyzed': True, 'current_ticker': ticker, 'current_name': name, 'market_type': mtype})
            else:
                st.error("종목을 찾을 수 없습니다.")

# ==========================================
# 6. 메인 화면 - 주식 분석
# ==========================================
if st.session_state['page'] == "주식 분석":
    st.markdown(f"## 📊 {st.session_state.get('current_name', '주식 분석')} 종합 리포트")
    
    if st.session_state['analyzed']:
        ticker = st.session_state['current_ticker']
        name = st.session_state['current_name']
        mtype = st.session_state['market_type']
        
        df = get_stock_data_with_indicators(ticker)
        
        if not df.empty:
            col1, col2 = st.columns([1.5, 1])
            with col1:
                st.markdown("#### 📈 차트 및 기술적 지표")
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='주가'))
                if 'Upper' in df.columns:
                    fig.add_trace(go.Scatter(x=df.index, y=df['Upper'], line=dict(color='rgba(250, 0, 0, 0.3)', width=1, dash='dot'), name='상단'))
                    fig.add_trace(go.Scatter(x=df.index, y=df['Lower'], line=dict(color='rgba(0, 0, 250, 0.3)', width=1, dash='dot'), name='하단'))
                
                fig.update_layout(xaxis_rangeslider_visible=False, height=450, margin=dict(l=0,r=0,t=30,b=0))
                st.plotly_chart(fig, use_container_width=True)
                
                last_close = df['Close'].iloc[-1]
                upper = df['Upper'].iloc[-1] if 'Upper' in df.columns else last_close
                lower = df['Lower'].iloc[-1] if 'Lower' in df.columns else last_close
                
                st.markdown(f"""
                <div style="display:flex; justify-content:space-around; background:{IM_WHITE}; padding:1rem; border-radius:10px; border:1px solid {IM_BORDER};">
                    <div style="text-align:center;"><div style="color:{IM_MUTED};font-size:0.8rem;">하단 지지선</div><b>{lower:,.0f}</b></div>
                    <div style="text-align:center;"><div style="color:{IM_MUTED};font-size:0.8rem;">현재가</div><b style="font-size:1.2rem;color:{IM_MINT};">{last_close:,.0f}</b></div>
                    <div style="text-align:center;"><div style="color:{IM_MUTED};font-size:0.8rem;">상단 저항선</div><b>{upper:,.0f}</b></div>
                </div>
                """, unsafe_allow_html=True)

            with col2:
                st.markdown("#### 🧠 AI 뉴스 & 매매 전략")
                price_info = {'close': last_close, 'upper': upper, 'lower': lower}
                ai_opinion, links = get_news_analysis_with_ai(name, mtype, price_info)
                st.info(ai_opinion)
                if links:
                    with st.expander("🔗 관련 뉴스 보기"):
                        for l in links: st.markdown(f"- [{l['title']}]({l['href']})")
        else:
            st.warning("데이터를 불러올 수 없습니다. 티커를 확인해주세요.")
    else:
        st.info("👈 왼쪽 사이드바에서 종목을 검색해주세요.")

# ==========================================
# 7. 시장 트렌드 & 기타
# ==========================================
elif st.session_state['page'] == "🔥 시장 트렌드":
    st.markdown("## 🔥 실시간 거래량 상위 종목")
    trend_df = get_trending_stocks()
    if trend_df is not None:
        st.dataframe(trend_df, hide_index=True, use_container_width=True)
    else:
        st.error("데이터를 불러오지 못했습니다.")

elif st.session_state['page'] == "💱 환율":
    st.markdown("## 💱 환율 차트")
    df_fx = yf.Ticker("USDKRW=X").history(period="3mo")
    if not df_fx.empty: st.line_chart(df_fx['Close'])

elif st.session_state['page'] == "⭐ 추천 종목":
    st.markdown("## ⭐ AI 추천 테마")
    st.write("현재 시장에서 주목받는 테마 섹터 정보가 표시됩니다.")
