# version 3.2 - iM Bank UI Edition


import streamlit as st
import os
import time
import sqlite3
import re
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
    API_KEY = "내_실제_키_입력"

genai.configure(api_key=API_KEY)

st.set_page_config(
    page_title="iM AI 주식 애널리스트",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded"
)


# ==========================================
# iM뱅크 디자인 토큰
# ==========================================
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

html, body, [class*="css"] {{
    font-family: 'Noto Sans KR', sans-serif;
    background-color: {IM_BG};
    color: {IM_TEXT};
}}

/* ── 사이드바 ── */
[data-testid="stSidebar"] {{
    background-color: {IM_DARK} !important;
}}
[data-testid="stSidebar"] * {{
    color: #E8F5F2 !important;
}}
[data-testid="stSidebar"] .stRadio label {{
    color: #B0D4CC !important;
    font-size: 0.9rem;
}}
[data-testid="stSidebar"] hr {{
    border-color: #1E4A44 !important;
}}
[data-testid="stSidebar"] .stTextInput input {{
    background-color: #1E4A44 !important;
    border: 1px solid #2D6B63 !important;
    color: #E8F5F2 !important;
    border-radius: 6px;
}}
[data-testid="stSidebar"] .stTextInput input::placeholder {{
    color: #7AADA5 !important;
}}

/* ── 버튼 ── */
.stButton > button {{
    background-color: {IM_MINT} !important;
    color: white !important;
    border: none !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
    padding: 0.5rem 1.2rem !important;
    transition: background-color 0.2s ease;
}}
.stButton > button:hover {{
    background-color: #009980 !important;
}}

/* ── 탭 ── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    border-bottom: 2px solid {IM_BORDER};
    gap: 0;
}}
[data-testid="stTabs"] [data-baseweb="tab"] {{
    background-color: transparent !important;
    border: none !important;
    color: {IM_MUTED} !important;
    font-weight: 500;
    padding: 0.6rem 1.4rem;
    border-bottom: 3px solid transparent;
    margin-bottom: -2px;
}}
[data-testid="stTabs"] [aria-selected="true"] {{
    color: {IM_MINT} !important;
    border-bottom: 3px solid {IM_MINT} !important;
    font-weight: 700 !important;
}}

/* ── 메트릭 카드 ── */
[data-testid="stMetric"] {{
    background-color: {IM_WHITE};
    border: 1px solid {IM_BORDER};
    border-radius: 10px;
    padding: 1rem 1.2rem !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04);
}}
[data-testid="stMetricLabel"] {{
    color: {IM_MUTED} !important;
    font-size: 0.78rem !important;
    font-weight: 500 !important;
    text-transform: uppercase;
    letter-spacing: 0.04em;
}}
[data-testid="stMetricValue"] {{
    color: {IM_TEXT} !important;
    font-size: 1.4rem !important;
    font-weight: 700 !important;
}}

/* ── 익스팬더 ── */
[data-testid="stExpander"] {{
    border: 1px solid {IM_BORDER} !important;
    border-radius: 8px !important;
    background-color: {IM_WHITE} !important;
}}

/* ── 메인 배경 ── */
[data-testid="stAppViewContainer"] > .main {{
    background-color: {IM_BG};
}}

/* ── 공통 컴포넌트 클래스 ── */
.im-page-header {{
    margin-bottom: 1.2rem;
    padding-bottom: 0.8rem;
    border-bottom: 1px solid {IM_BORDER};
}}
.im-page-title {{
    font-size: 1.4rem;
    font-weight: 700;
    color: {IM_DARK};
    margin: 0 0 0.2rem 0;
    border-left: 4px solid {IM_MINT};
    padding-left: 0.75rem;
}}
.im-page-subtitle {{
    font-size: 0.85rem;
    color: {IM_MUTED};
    margin: 0;
    padding-left: 1.05rem;
}}
.im-section-title {{
    font-size: 0.95rem;
    font-weight: 700;
    color: {IM_DARK};
    margin: 1.2rem 0 0.6rem 0;
    padding-bottom: 0.4rem;
    border-bottom: 1px solid {IM_BORDER};
}}
.im-data-source {{
    font-size: 0.75rem;
    color: {IM_MUTED};
    background-color: {IM_WHITE};
    border: 1px solid {IM_BORDER};
    border-radius: 4px;
    padding: 0.3rem 0.7rem;
    display: inline-block;
    margin-bottom: 0.6rem;
}}
.im-disclaimer {{
    font-size: 0.78rem;
    color: #7A5C00;
    background-color: #FFFBEB;
    border-left: 3px solid #F0A500;
    padding: 0.6rem 1rem;
    border-radius: 0 6px 6px 0;
    margin-top: 1.2rem;
}}
.im-ticker-badge {{
    display: inline-block;
    background-color: {IM_BG};
    color: {IM_MINT};
    border: 1px solid {IM_BORDER};
    border-radius: 4px;
    font-size: 0.78rem;
    font-weight: 700;
    padding: 0.15rem 0.5rem;
    margin-bottom: 0.5rem;
    font-family: monospace;
}}
</style>
""", unsafe_allow_html=True)


# ==========================================
# 공통 헬퍼 함수
# ==========================================
def get_data_source_badge(source: str = "Yahoo Finance"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M KST")
    return f'<span class="im-data-source">📡 {source} · 기준: {now}</span>'

def im_page_header(title: str, subtitle: str = ""):
    sub_html = f'<div class="im-page-subtitle">{subtitle}</div>' if subtitle else ""
    st.markdown(f"""
    <div class="im-page-header">
        <div class="im-page-title">{title}</div>
        {sub_html}
    </div>
    """, unsafe_allow_html=True)

def im_section(title: str):
    st.markdown(f'<div class="im-section-title">{title}</div>', unsafe_allow_html=True)


# ==========================================
# 2. 세션 상태 초기화
# ==========================================
defaults = {
    'analyzed': False,
    'current_ticker': None,
    'current_name': None,
    'market_type': None,
    'news_result_text': None,
    'news_links': None,
    'last_query': None,
    'page': '주식 분석',
    'rec_beginner': None,
    'rec_expert': None,
    'fx_period': '3mo',
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


# ==========================================
# 3. 시장 자동 감지
# ==========================================
def detect_market(query: str):
    query = query.strip()
    if re.fullmatch(r'[A-Z]{1,5}', query):
        return 'US_TICKER', query.upper()
    if re.fullmatch(r'[a-zA-Z\s\.\-&]+', query):
        return 'US_NAME', query
    return 'KR', query


# ==========================================
# 4. 국내 주식 DB
# ==========================================
def initialize_database():
    db_file = "stocks.db"
    if not os.path.exists(db_file):
        with st.spinner("주식 DB를 구축 중입니다... (최초 1회 실행)"):
            try:
                df_krx = fdr.StockListing('KRX')
                conn = sqlite3.connect(db_file)
                cursor = conn.cursor()
                cursor.execute("DROP TABLE IF EXISTS stock_info")
                cursor.execute("CREATE TABLE stock_info (code TEXT, name TEXT, market TEXT)")
                for _, row in df_krx.iterrows():
                    cursor.execute("INSERT INTO stock_info VALUES (?, ?, ?)",
                                   (row['Code'], row['Name'], row['Market']))
                conn.commit()
                conn.close()
                st.success(f"DB 생성 완료 ({len(df_krx)}개 종목)")
            except Exception as e:
                st.error(f"DB 생성 실패: {e}")

def get_ticker_from_db(stock_name: str):
    initialize_database()
    try:
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "stocks.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT code, name, market FROM stock_info WHERE name LIKE ?",
            (f"%{stock_name}%",)
        )
        results = cursor.fetchall()
        conn.close()
        if not results:
            return None, None
        best_match = min(results, key=lambda x: len(x[1]))
        code, name, market = best_match
        ticker = code + (".KS" if market == 'KOSPI' else ".KQ")
        return ticker, name
    except Exception:
        return None, None


# ==========================================
# 5. 미국 주식 검색
# ==========================================
def get_us_ticker_by_name(company_name: str):
    try:
        search = yf.Search(company_name, max_results=5)
        quotes = search.quotes
        if not quotes:
            return None, None
        for q in quotes:
            if q.get('quoteType', '').upper() in ('EQUITY', 'ETF'):
                return q.get('symbol', ''), q.get('shortname') or q.get('longname') or company_name
        q = quotes[0]
        return q.get('symbol', ''), q.get('shortname', company_name)
    except Exception:
        return None, None

def validate_us_ticker(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        name = info.get('shortName') or info.get('longName') or ticker
        hist = stock.history(period="5d")
        if hist.empty:
            return None, None
        return ticker, name
    except Exception:
        return None, None


# ==========================================
# 6. 주가 데이터 조회
# ==========================================
def get_stock_data(ticker: str, period: str = "6mo"):
    return yf.Ticker(ticker).history(period=period)


# ==========================================
# 7. 환율 차트
# ==========================================
def get_fx_chart(symbol: str, label: str, color: str, period: str = "3mo", height: int = 200):
    try:
        df = yf.Ticker(symbol).history(period=period)
        if df.empty:
            return None, None
        current = df['Close'].iloc[-1]
        prev    = df['Close'].iloc[-2]
        change  = current - prev
        chg_pct = (change / prev) * 100
        r, g, b = int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Close'],
            mode='lines',
            line=dict(color=color, width=2),
            fill='tozeroy',
            fillcolor=f'rgba({r},{g},{b},0.08)',
            name=label,
            hovertemplate='%{x|%Y-%m-%d}<br>%{y:,.2f} 원<extra></extra>'
        ))
        fig.update_layout(
            margin=dict(l=0, r=0, t=10, b=0),
            height=height,
            xaxis=dict(showgrid=False, tickformat='%m/%d', tickfont=dict(size=11)),
            yaxis=dict(showgrid=True, gridcolor=f'rgba(0,180,150,0.08)', tickfont=dict(size=11)),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            hoverlabel=dict(bgcolor=IM_DARK, font_color='white', font_size=12)
        )
        return fig, (current, change, chg_pct)
    except Exception:
        return None, None


# ==========================================
# 8. 추천 카드용 미니 차트
# ==========================================
def get_mini_chart(ticker: str, color: str = IM_MINT):
    try:
        df = yf.Ticker(ticker).history(period="1mo")
        if df.empty:
            return None, None
        start = df['Close'].iloc[0]
        end   = df['Close'].iloc[-1]
        line_color = IM_UP if end >= start else IM_DOWN
        r, g, b = int(line_color[1:3], 16), int(line_color[3:5], 16), int(line_color[5:7], 16)
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Close'],
            mode='lines',
            line=dict(color=line_color, width=1.5),
            fill='tozeroy',
            fillcolor=f'rgba({r},{g},{b},0.08)',
            hovertemplate='%{y:,.2f}<extra></extra>'
        ))
        fig.update_layout(
            margin=dict(l=0, r=0, t=0, b=0),
            height=80,
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
        )
        ret = ((end - start) / start) * 100
        return fig, ret
    except Exception:
        return None, None


# ==========================================
# 9. AI 분석 함수
# ==========================================
def analyze_with_gemini(content_type: str, content_data, market_type: str = 'KR'):
    try:
        model = genai.GenerativeModel("models/gemini-2.5-flash")

        if content_type == "audio":
            uploaded_file = genai.upload_file(content_data)
            retry = 0
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(1)
                uploaded_file = genai.get_file(uploaded_file.name)
                retry += 1
                if retry > 60:
                    return "파일 처리 시간 초과 (1분 경과)"
            if uploaded_file.state.name == "FAILED":
                return "구글 AI 처리 실패"
            prompt = """
            이 주식 관련 영상의 핵심 내용을 투자자 입장에서 한국어로 요약해줘.
            양식:
            ## 1. 영상 핵심 3줄 요약
            ## 2. 매매 의견 (매수/매도/관망) 및 목표가
            ## 3. 주요 근거 및 포인트
            """
            response = model.generate_content([uploaded_file, prompt])
            genai.delete_file(uploaded_file.name)
            return response.text

        elif content_type == "text":
            if market_type == 'US':
                prompt = f"""
                다음은 미국 주식 관련 영문 뉴스 기사들입니다.
                이를 한국어로 번역·종합하여 투자 리포트를 작성해줘.
                [뉴스 데이터]\n{content_data}
                양식:
                ## 1. 최신 뉴스 종합 3줄 요약 (한국어)
                ## 2. 시장의 종합적 의견 (매수/매도/관망)
                ## 3. 주요 리스크 및 호재 요인
                """
            else:
                prompt = f"""
                다음 뉴스 기사들을 종합하여 투자 리포트를 작성해줘.
                [뉴스 데이터]\n{content_data}
                양식:
                ## 1. 최신 뉴스 종합 3줄 요약
                ## 2. 시장의 종합적 의견 (매수/매도/관망)
                ## 3. 주요 리스크 및 호재 요인
                """
            return model.generate_content(prompt).text

        elif content_type == "recommend":
            level = content_data
            if level == 'beginner':
                prompt = """
                주식 투자 초보자에게 적합한 국내·미국 주식 각 3종목씩 총 6종목을 추천해줘.
                기준: 변동성 낮음, 배당 안정적, 글로벌 브랜드 인지도 높음, 장기 보유 적합.

                반드시 아래 형식으로만 작성해줘. 다른 텍스트 없이 블록 6개만:

                ---
                ### 🇰🇷 [종목명] ([티커])
                **한 줄 요약:** 한 문장 설명
                **추천 이유:** 구체적 이유 한 문장
                **리스크:** 주의사항 한 문장
                **난이도:** ⭐
                ---

                국내 3개(🇰🇷) 먼저, 미국 3개(🇺🇸) 이어서. 티커는 괄호 안에 정확히 표기.
                """
            else:
                prompt = """
                주식 고수(경험 많은 투자자)가 주목할 만한 국내·미국 주식 각 3종목씩 총 6종목을 추천해줘.
                기준: 성장 모멘텀 강함, 기관/외국인 매수세, AI·반도체·바이오 테마 유망.

                반드시 아래 형식으로만 작성해줘. 다른 텍스트 없이 블록 6개만:

                ---
                ### 🇰🇷 [종목명] ([티커])
                **한 줄 요약:** 한 문장 설명
                **추천 이유:** 구체적 이유 한 문장
                **리스크:** 주의사항 한 문장
                **난이도:** ⭐⭐⭐⭐
                ---

                국내 3개(🇰🇷) 먼저, 미국 3개(🇺🇸) 이어서. 티커는 괄호 안에 정확히 표기.
                """
            return model.generate_content(prompt).text

    except Exception as e:
        return f"AI 분석 중 오류 발생: {e}"


# ==========================================
# 10. 뉴스 분석
# ==========================================
def get_news_analysis(keyword: str, market_type: str = 'KR'):
    try:
        q = f"{keyword} stock forecast analysis" if market_type == 'US' else f"{keyword} 주가 전망"
        results = DDGS().text(q, max_results=5)
        if not results:
            return "검색된 뉴스가 없습니다.", None
        news_text = "".join(
            f"[{i+1}] {r['title']}\n{r['body']}\nLink: {r['href']}\n\n"
            for i, r in enumerate(results)
        )
        return analyze_with_gemini("text", news_text, market_type), results
    except Exception as e:
        return f"뉴스 검색 오류: {e}", None


# ==========================================
# 11. 유튜브 다운로드
# ==========================================
def download_audio(youtube_url: str):
    filename_base = "temp_audio_extra"
    for ext in ['m4a', 'webm', 'mp3']:
        fp = f"{filename_base}.{ext}"
        if os.path.exists(fp):
            os.remove(fp)
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/best',
        'outtmpl': filename_base + '.%(ext)s',
        'quiet': True,
        'socket_timeout': 10,
        'http_headers': {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(youtube_url, download=True)
            return ydl.prepare_filename(info)
    except Exception:
        return None


# ==========================================
# 12. 추천 카드 렌더링
# ==========================================
def parse_ticker_from_block(block: str) -> str:
    m = re.search(r'\(([A-Z0-9\.\-]{1,10})\)', block)
    return m.group(1) if m else None

def render_stock_cards(stock_list: list):
    kr_list = [s for s in stock_list if '🇰🇷' in s['flag']]
    us_list = [s for s in stock_list if '🇺🇸' in s['flag']]

    for region_label, items in [("국내 종목", kr_list), ("미국 종목", us_list)]:
        st.markdown(f'<div class="im-section-title">{region_label}</div>', unsafe_allow_html=True)
        cols = st.columns(3)
        for i, s in enumerate(items[:3]):
            with cols[i]:
                with st.container(border=True):
                    st.markdown(f"**{s['flag']} {s['name']}**")
                    st.markdown(
                        f'<span class="im-ticker-badge">{s["ticker"]}</span>',
                        unsafe_allow_html=True
                    )
                    fig_mini, ret = get_mini_chart(s['ticker'])
                    if fig_mini:
                        st.plotly_chart(fig_mini, use_container_width=True,
                                        config={'displayModeBar': False})
                        color = IM_UP if ret and ret >= 0 else IM_DOWN
                        sign  = "▲" if ret and ret >= 0 else "▼"
                        st.markdown(
                            f'<span style="color:{color};font-size:0.82rem;font-weight:600">'
                            f'{sign} 1개월 {ret:+.1f}%</span>',
                            unsafe_allow_html=True
                        )
                    else:
                        st.caption("차트 데이터 없음")

                    st.markdown("---")
                    st.caption(s['desc'])
                    if s.get('reason'):
                        st.markdown(
                            f'<span style="font-size:0.83rem;color:{IM_MUTED}">'
                            f'추천 이유: {s["reason"]}</span>',
                            unsafe_allow_html=True
                        )
                    st.markdown(
                        f'<span style="font-size:0.82rem;color:{IM_DOWN}">'
                        f'리스크: {s["risk"]}</span>',
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        f'<span style="font-size:0.82rem">난이도: {s["stars"]}</span>',
                        unsafe_allow_html=True
                    )
        st.markdown("")

def render_ai_recommendation_cards(ai_text: str):
    blocks = [b.strip() for b in ai_text.split('---') if b.strip()]
    parsed = []
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        item = {'flag': '🇺🇸', 'name': '', 'ticker': '',
                'desc': '', 'reason': '', 'risk': '', 'stars': '⭐'}
        for line in lines:
            if line.startswith('### '):
                title = line[4:]
                if '🇰🇷' in title: item['flag'] = '🇰🇷'
                elif '🇺🇸' in title: item['flag'] = '🇺🇸'
                name_part = re.sub(r'\([^)]+\)', '', title)\
                    .replace('🇰🇷', '').replace('🇺🇸', '').strip()
                item['name'] = name_part
                item['ticker'] = parse_ticker_from_block(title) or ''
            elif line.startswith('**한 줄 요약:**'):
                item['desc']   = line.replace('**한 줄 요약:**', '').strip()
            elif line.startswith('**추천 이유:**'):
                item['reason'] = line.replace('**추천 이유:**', '').strip()
            elif line.startswith('**리스크:**'):
                item['risk']   = line.replace('**리스크:**', '').strip()
            elif line.startswith('**난이도:**'):
                item['stars']  = line.replace('**난이도:**', '').strip()
        if item['name']:
            parsed.append(item)

    if not parsed:
        st.markdown(ai_text)
        return
    render_stock_cards(parsed)


# ==========================================
# 13. 사이드바
# ==========================================
with st.sidebar:
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, {IM_MINT}22, {IM_MINT}08);
        border: 1px solid {IM_MINT}44;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.5rem;
        text-align: center;
    ">
        <div style="font-size:1.6rem;margin-bottom:0.3rem">🏦</div>
        <div style="color:#E8F5F2;font-weight:700;font-size:1rem;letter-spacing:0.03em">
            iM AI 애널리스트
        </div>
        <div style="color:#7AADA5;font-size:0.72rem;margin-top:0.2rem">
            AI 기반 주식·환율 분석 서비스
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("---")

    page = st.radio(
        "메뉴",
        options=["주식 분석", "환율", "추천 종목"],
        index=["주식 분석", "환율", "추천 종목"].index(
            st.session_state['page']
            if st.session_state['page'] in ["주식 분석", "환율", "추천 종목"]
            else "주식 분석"
        ),
        format_func=lambda x: {
            "주식 분석": "📊  주식 분석",
            "환율":     "💱  환율",
            "추천 종목": "⭐  추천 종목"
        }[x]
    )
    st.session_state['page'] = page
    st.markdown("---")

    if page == "주식 분석":
        st.markdown(
            '<div style="color:#B0D4CC;font-size:0.78rem;font-weight:600;'
            'letter-spacing:0.05em;margin-bottom:0.4rem">종목 검색</div>',
            unsafe_allow_html=True
        )
        st.caption(
            "국내: 한글 종목명 (삼성전자)\n\n"
            "미국 티커: 영대문자 (AAPL)\n\n"
            "미국 회사명: 영문 (Apple)"
        )
        query = st.text_input(
            "종목명 또는 티커",
            placeholder="예: 삼성전자 / AAPL",
            label_visibility="collapsed"
        )

        if st.button("분석 시작", use_container_width=True):
            if query:
                market_guess, clean_query = detect_market(query)
                ticker, real_name, market_type = None, None, 'KR'

                if market_guess == 'US_TICKER':
                    with st.spinner(f"{clean_query} 확인 중..."):
                        ticker, real_name = validate_us_ticker(clean_query)
                    market_type = 'US'
                elif market_guess == 'US_NAME':
                    with st.spinner(f"'{clean_query}' 검색 중..."):
                        ticker, real_name = get_us_ticker_by_name(clean_query)
                    market_type = 'US'
                else:
                    with st.spinner(f"'{clean_query}' 검색 중..."):
                        ticker, real_name = get_ticker_from_db(clean_query)
                    market_type = 'KR'

                if ticker:
                    st.session_state.update({
                        'analyzed': True,
                        'current_ticker': ticker,
                        'current_name': real_name,
                        'market_type': market_type,
                        'news_result_text': None,
                        'news_links': None,
                        'last_query': None,
                    })
                    flag = "🇺🇸" if market_type == 'US' else "🇰🇷"
                    st.success(f"{flag} {real_name} ({ticker})")
                else:
                    st.error("종목을 찾을 수 없습니다.")
                    st.session_state['analyzed'] = False
            else:
                st.warning("종목명을 입력해주세요.")

    st.markdown(f"""
    <div style="margin-top:2rem;font-size:0.7rem;color:#3D7068;text-align:center">
        iM AI Analyst v3.2<br>
        데이터: Yahoo Finance · DuckDuckGo
    </div>
    """, unsafe_allow_html=True)


# ==========================================
# 14. 페이지 1: 주식 분석
# ==========================================
if st.session_state['page'] == "주식 분석":
    im_page_header(
        "주식 분석",
        "국내·미국 주식의 최신 뉴스 분석과 유튜브 영상 심층 분석을 제공합니다"
    )

    if st.session_state['analyzed']:
        ticker      = st.session_state['current_ticker']
        real_name   = st.session_state['current_name']
        market_type = st.session_state['market_type']
        flag_label  = "🇺🇸 미국" if market_type == 'US' else "🇰🇷 국내"

        # 종목 상태 배너
        st.markdown(f"""
        <div style="
            background: linear-gradient(90deg, {IM_MINT}18, transparent);
            border: 1px solid {IM_MINT}44;
            border-left: 4px solid {IM_MINT};
            border-radius: 8px;
            padding: 0.65rem 1rem;
            margin-bottom: 1rem;
            font-size: 0.9rem;
            color: {IM_DARK};
        ">
            <strong>{flag_label}</strong> &nbsp;|&nbsp;
            <strong>{real_name}</strong> &nbsp;
            <span style="font-family:monospace;background:{IM_BG};
                border:1px solid {IM_BORDER};border-radius:4px;
                padding:0.1rem 0.45rem;font-size:0.82rem;color:{IM_MINT}">{ticker}</span>
        </div>
        """, unsafe_allow_html=True)

        col_left, col_right = st.columns([1.2, 2])

        with col_left:
            im_section("주가 차트 (6개월)")
            st.markdown(get_data_source_badge(), unsafe_allow_html=True)
            df = get_stock_data(ticker)
            if not df.empty:
                fig_stock = go.Figure(data=[go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'],
                    low=df['Low'],   close=df['Close'],
                    increasing_line_color=IM_UP,
                    decreasing_line_color=IM_DOWN,
                    increasing_fillcolor=IM_UP,
                    decreasing_fillcolor=IM_DOWN,
                )])
                fig_stock.update_layout(
                    xaxis_rangeslider_visible=False,
                    height
