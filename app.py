#version 3.1

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
from duckduckgo_search import DDGS

# ==========================================
# 1. 설정 및 API 키
# ==========================================
try:
    # 스트림릿 클라우드의 비밀 금고에서 키를 꺼내옴
    API_KEY = st.secrets["GEMINI_API_KEY"] 
except:
    # (내 컴퓨터에서 테스트할 때를 위한 예비용 - 깃허브 올릴 땐 지우는 게 좋음)
    API_KEY = "내_실제_키_입력" 

genai.configure(api_key=API_KEY)

st.set_page_config(
    page_title="AI 주식 애널리스트 Pro",
    layout="wide",
    initial_sidebar_state="expanded"
)

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
    'page': '📊 주식 분석',
    'rec_beginner': None,
    'rec_expert': None,
    'fx_period': '3mo',   # 환율 페이지 기간 선택 캐시
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
        with st.spinner("📦 주식 DB를 구축 중입니다... (최초 1회 실행)"):
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
                st.success(f"✅ DB 생성 완료! ({len(df_krx)}개 종목)")
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
# 7. 환율 차트 (공용)  ★ 신규: JPY 지원
# ==========================================
def get_fx_chart(symbol: str, label: str, color: str, period: str = "3mo", height: int = 180):
    """
    symbol  : 'USDKRW=X' 또는 'JPYKRW=X'
    label   : 호버·범례 이름
    color   : 라인 색상 hex
    period  : yfinance period 문자열 ('1mo','3mo','6mo','1y')
    height  : 차트 높이 px
    반환    : (fig, (현재환율, 전일대비변화, 변화율%))
    """
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
            x=df.index,
            y=df['Close'],
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
            xaxis=dict(showgrid=False, tickformat='%m/%d'),
            yaxis=dict(showgrid=True, gridcolor='rgba(200,200,200,0.15)'),
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
        )
        return fig, (current, change, chg_pct)
    except Exception:
        return None, None


# ==========================================
# 8. 추천 카드용 미니 차트
# ==========================================
def get_mini_chart(ticker: str, color: str = '#4c8ef7'):
    """
    1개월 종가 라인 차트 (카드 내 삽입용, 초소형)
    """
    try:
        df = yf.Ticker(ticker).history(period="1mo")
        if df.empty:
            return None
        # 수익률 색상: 상승=초록, 하락=빨강
        start = df['Close'].iloc[0]
        end   = df['Close'].iloc[-1]
        line_color = '#26a65b' if end >= start else '#e74c3c'

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df.index, y=df['Close'],
            mode='lines',
            line=dict(color=line_color, width=1.5),
            fill='tozeroy',
            fillcolor=f'rgba({int(line_color[1:3],16)},{int(line_color[3:5],16)},{int(line_color[5:7],16)},0.1)',
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

        # ── 오디오 (유튜브) ──────────────────────────────
        if content_type == "audio":
            uploaded_file = genai.upload_file(content_data)
            retry = 0
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(1)
                uploaded_file = genai.get_file(uploaded_file.name)
                retry += 1
                if retry > 60:
                    return "❌ 파일 처리 시간 초과 (1분 경과)"
            if uploaded_file.state.name == "FAILED":
                return "❌ 구글 AI 처리 실패"
            prompt = """
            이 주식 관련 영상의 핵심 내용을 투자자 입장에서 한국어로 요약해줘.
            양식:
            ## 1. 📺 영상 핵심 3줄 요약
            ## 2. 📈 매매 의견 (매수/매도/관망) 및 목표가
            ## 3. 💡 주요 근거 및 포인트
            """
            response = model.generate_content([uploaded_file, prompt])
            genai.delete_file(uploaded_file.name)
            return response.text

        # ── 뉴스 텍스트 분석 ─────────────────────────────
        elif content_type == "text":
            if market_type == 'US':
                prompt = f"""
                다음은 미국 주식 관련 영문 뉴스 기사들입니다.
                이를 한국어로 번역·종합하여 투자 리포트를 작성해줘.
                [뉴스 데이터]\n{content_data}
                양식:
                ## 1. 📰 최신 뉴스 종합 3줄 요약 (한국어)
                ## 2. 📈 시장의 종합적 의견 (매수/매도/관망)
                ## 3. ⚠️ 주요 리스크 및 호재 요인
                """
            else:
                prompt = f"""
                다음 뉴스 기사들을 종합하여 투자 리포트를 작성해줘.
                [뉴스 데이터]\n{content_data}
                양식:
                ## 1. 📰 최신 뉴스 종합 3줄 요약
                ## 2. 📈 시장의 종합적 의견 (매수/매도/관망)
                ## 3. ⚠️ 주요 리스크 및 호재 요인
                """
            return model.generate_content(prompt).text

        # ── 추천 종목 생성 ───────────────────────────────
        elif content_type == "recommend":
            level = content_data  # 'beginner' or 'expert'
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
        return f"❌ AI 분석 중 에러 발생: {e}"


# ==========================================
# 10. 뉴스 분석
# ==========================================
def get_news_analysis(keyword: str, market_type: str = 'KR'):
    try:
        q = f"{keyword} stock forecast analysis" if market_type == 'US' else f"{keyword} 주가 전망"
        results = DDGS().text(q, max_results=5)
        if not results:
            return "❌ 검색된 뉴스가 없습니다.", None
        news_text = "".join(
            f"[{i+1}] {r['title']}\n{r['body']}\nLink: {r['href']}\n\n"
            for i, r in enumerate(results)
        )
        return analyze_with_gemini("text", news_text, market_type), results
    except Exception as e:
        return f"❌ 뉴스 검색 오류: {e}", None


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
# 12. 추천 카드 렌더링 헬퍼  ★ 신규: 미니 차트 포함
# ==========================================
def parse_ticker_from_block(block: str) -> str:
    """블록 제목에서 (티커) 패턴 추출"""
    m = re.search(r'\(([A-Z0-9\.\-]{1,10})\)', block)
    return m.group(1) if m else None


def render_stock_cards(stock_list: list):
    """
    stock_list: [{"flag","name","ticker","desc","reason","risk","stars"}, ...]
    각 아이템을 카드(border) + 미니 차트로 렌더링
    """
    kr_list = [s for s in stock_list if '🇰🇷' in s['flag']]
    us_list = [s for s in stock_list if '🇺🇸' in s['flag']]

    for region_label, items in [("🇰🇷 국내", kr_list), ("🇺🇸 미국", us_list)]:
        st.markdown(f"**{region_label}**")
        cols = st.columns(3)
        for i, s in enumerate(items[:3]):
            with cols[i]:
                with st.container(border=True):
                    # 상단: 종목 이름 + 티커
                    st.markdown(f"#### {s['flag']} {s['name']}")
                    st.caption(f"`{s['ticker']}`")

                    # 미니 차트 + 1개월 수익률
                    fig_mini, ret = get_mini_chart(s['ticker'])
                    if fig_mini:
                        st.plotly_chart(fig_mini, use_container_width=True, config={'displayModeBar': False})
                        ret_color = "🟢" if ret and ret >= 0 else "🔴"
                        st.caption(f"{ret_color} 1개월 수익률: **{ret:+.1f}%**" if ret is not None else "")
                    else:
                        st.caption("📊 차트 데이터 없음")

                    st.markdown("---")
                    # 설명 텍스트
                    st.markdown(f"💬 {s['desc']}")
                    if s.get('reason'):
                        st.markdown(f"✅ {s['reason']}")
                    st.markdown(f"⚠️ 리스크: {s['risk']}")
                    st.markdown(f"📊 난이도: {s['stars']}")
        st.markdown("")


def render_ai_recommendation_cards(ai_text: str):
    """AI가 생성한 마크다운을 파싱 → 카드 + 미니 차트 렌더링"""
    blocks = [b.strip() for b in ai_text.split('---') if b.strip()]

    parsed = []
    for block in blocks:
        lines = [l.strip() for l in block.split('\n') if l.strip()]
        item = {'flag': '🇺🇸', 'name': '', 'ticker': '', 'desc': '', 'reason': '', 'risk': '', 'stars': '⭐'}
        for line in lines:
            if line.startswith('### '):
                title = line[4:]
                if '🇰🇷' in title:
                    item['flag'] = '🇰🇷'
                elif '🇺🇸' in title:
                    item['flag'] = '🇺🇸'
                # 종목명 추출 (티커 앞까지)
                name_part = re.sub(r'\([^)]+\)', '', title).replace('🇰🇷', '').replace('🇺🇸', '').strip()
                item['name'] = name_part
                # 티커 추출
                tk = parse_ticker_from_block(title)
                item['ticker'] = tk or ''
            elif line.startswith('**한 줄 요약:**'):
                item['desc'] = line.replace('**한 줄 요약:**', '').strip()
            elif line.startswith('**추천 이유:**'):
                item['reason'] = line.replace('**추천 이유:**', '').strip()
            elif line.startswith('**리스크:**'):
                item['risk'] = line.replace('**리스크:**', '').strip()
            elif line.startswith('**난이도:**'):
                item['stars'] = line.replace('**난이도:**', '').strip()
        if item['name']:
            parsed.append(item)

    if not parsed:
        st.markdown(ai_text)  # 파싱 실패 시 원문 표시
        return

    render_stock_cards(parsed)


# ==========================================
# 13. 사이드바 (공통)
# ==========================================
with st.sidebar:
    st.title("🤖 AI 주식 비서")
    st.markdown("---")

    page = st.radio(
        "📂 메뉴",
        options=["📊 주식 분석", "💱 환율", "⭐ 추천 종목"],
        index=["📊 주식 분석", "💱 환율", "⭐ 추천 종목"].index(
            st.session_state['page']
            if st.session_state['page'] in ["📊 주식 분석", "💱 환율", "⭐ 추천 종목"]
            else "📊 주식 분석"
        )
    )
    st.session_state['page'] = page
    st.markdown("---")

    if page == "📊 주식 분석":
        st.header("🔍 종목 검색")
        st.caption(
            "**국내:** 한글 종목명 (삼성전자, 카카오)\n\n"
            "**미국 티커:** 영대문자 (AAPL, TSLA)\n\n"
            "**미국 회사명:** 영문 (Apple, Tesla)"
        )
        query = st.text_input("종목명 또는 티커", placeholder="예: 삼성전자 / AAPL")

        if st.button("🔎 뉴스 분석 시작", use_container_width=True):
            if query:
                market_guess, clean_query = detect_market(query)
                ticker, real_name, market_type = None, None, 'KR'

                if market_guess == 'US_TICKER':
                    with st.spinner(f"🔍 {clean_query} 확인 중..."):
                        ticker, real_name = validate_us_ticker(clean_query)
                    market_type = 'US'
                elif market_guess == 'US_NAME':
                    with st.spinner(f"🔍 '{clean_query}' 검색 중..."):
                        ticker, real_name = get_us_ticker_by_name(clean_query)
                    market_type = 'US'
                else:
                    with st.spinner(f"🔍 '{clean_query}' 검색 중..."):
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
                    st.success(f"{flag} **{real_name}** ({ticker})")
                else:
                    st.error("종목을 찾을 수 없습니다.")
                    st.session_state['analyzed'] = False
            else:
                st.warning("종목명을 입력해주세요.")


# ==========================================
# 14. 페이지 1: 주식 분석
# ==========================================
if st.session_state['page'] == "📊 주식 분석":
    st.title("📊 AI 주식 애널리스트 Pro")
    st.markdown("국내·미국 주식 **뉴스 분석**과 **유튜브 영상 심층 분석**을 제공합니다.")

    if st.session_state['analyzed']:
        ticker      = st.session_state['current_ticker']
        real_name   = st.session_state['current_name']
        market_type = st.session_state['market_type']
        flag_label  = "🇺🇸 미국" if market_type == 'US' else "🇰🇷 국내"

        st.info(f"✅ **[{flag_label}]** **'{real_name}'** ({ticker}) 분석 결과입니다.")

        col_left, col_right = st.columns([1.2, 2])

        # ── 왼쪽: 주가 차트 + 환율 차트 ──────────────────────
        with col_left:
            # 주가 캔들 차트
            st.subheader("📈 주가 차트 (6개월)")
            df = get_stock_data(ticker)
            if not df.empty:
                fig_stock = go.Figure(data=[go.Candlestick(
                    x=df.index,
                    open=df['Open'], high=df['High'],
                    low=df['Low'],   close=df['Close']
                )])
                fig_stock.update_layout(xaxis_rangeslider_visible=False, height=340)
                st.plotly_chart(fig_stock, use_container_width=True)

                last_price = df['Close'].iloc[-1]
                prev_price = df['Close'].iloc[-2]
                delta = last_price - prev_price
                if market_type == 'US':
                    st.metric("현재가", f"${last_price:,.2f}", f"{delta:+.2f}")
                else:
                    st.metric("현재가", f"{last_price:,.0f}원", f"{delta:+,.0f}원")
            else:
                st.warning("차트 데이터 없음")

        # ── 오른쪽: 뉴스 분석 + 유튜브 분석 ─────────────────
        with col_right:
            st.subheader("📰 AI 뉴스 분석 리포트")

            if (
                st.session_state.get('news_result_text') is None
                or st.session_state.get('last_query') != real_name
            ):
                with st.spinner("최신 뉴스를 분석 중입니다..."):
                    news_result, news_links = get_news_analysis(real_name, market_type)
                    st.session_state['news_result_text'] = news_result
                    st.session_state['news_links'] = news_links
                    st.session_state['last_query'] = real_name

            st.markdown(st.session_state['news_result_text'])

            if st.session_state.get('news_links'):
                with st.expander("📎 참고 기사 링크"):
                    for n in st.session_state['news_links']:
                        st.markdown(f"- [{n['title']}]({n['href']})")

            st.markdown("---")

            st.subheader("📺 유튜브 영상 심층 분석")
            st.info("분석하고 싶은 영상의 링크를 입력하세요.")
            youtube_url = st.text_input("유튜브 URL 붙여넣기", key="yt_url")

            if st.button("🎬 이 영상 분석하기"):
                if youtube_url:
                    with st.status("🚀 영상 분석 중...", expanded=True) as status:
                        status.write("1️⃣ 오디오 다운로드 중...")
                        audio_file = download_audio(youtube_url)
                        if audio_file:
                            status.write("2️⃣ AI가 내용을 분석 중...")
                            video_result = analyze_with_gemini("audio", audio_file, market_type)
                            if "에러" not in video_result:
                                status.update(label="✅ 분석 완료!", state="complete")
                                st.markdown("### 🎬 영상 분석 결과")
                                st.markdown(video_result)
                            else:
                                status.update(label="❌ 분석 실패", state="error")
                                st.error(video_result)
                            if os.path.exists(audio_file):
                                os.remove(audio_file)
                        else:
                            status.update(label="❌ 다운로드 실패", state="error")
                            st.error("영상을 다운로드할 수 없습니다. (링크 확인 필요)")
                else:
                    st.warning("링크를 입력해주세요.")

    else:
        st.markdown("---")
        st.markdown(
            """
            ### 👈 왼쪽 사이드바에서 종목을 검색하세요!

            | 입력 예시 | 설명 |
            |---|---|
            | `삼성전자` | 🇰🇷 국내 주식 한글 검색 |
            | `AAPL` | 🇺🇸 미국 티커 직접 입력 |
            | `Apple` | 🇺🇸 미국 회사명 검색 |

            > 💡 **추천 종목**을 먼저 보고 싶다면 왼쪽 메뉴에서 **⭐ 추천 종목**을 클릭하세요!
            """
        )


# ==========================================
# 15. 페이지 2: 환율
# ==========================================
elif st.session_state['page'] == "💱 환율":
    st.title("💱 환율 대시보드")
    st.markdown("달러·엔화 환율의 흐름을 한눈에 확인하세요.")

    # 기간 선택
    period_label_map = {"1개월": "1mo", "3개월": "3mo", "6개월": "6mo", "1년": "1y"}
    period_choice = st.radio(
        "📅 조회 기간",
        options=list(period_label_map.keys()),
        index=list(period_label_map.keys()).index("3개월"),
        horizontal=True
    )
    selected_period = period_label_map[period_choice]

    st.markdown("---")

    tab_usd, tab_jpy = st.tabs(["🇺🇸 달러 (USD/KRW)", "🇯🇵 엔화 (JPY/KRW)"])

    # ── USD/KRW 탭 ────────────────────────────────────────
    with tab_usd:
        fig_usd, usd_info = get_fx_chart("USDKRW=X", "USD/KRW", "#f0a500",
                                         period=selected_period, height=380)
        if fig_usd and usd_info:
            rate, chg, chg_pct = usd_info

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("💵 현재 달러 환율", f"{rate:,.2f} 원",
                          f"{chg:+.2f}원 ({chg_pct:+.2f}%)")
            with m2:
                # 기간 내 최고가
                df_usd = yf.Ticker("USDKRW=X").history(period=selected_period)
                st.metric(f"📈 {period_choice} 최고", f"{df_usd['High'].max():,.2f} 원")
            with m3:
                st.metric(f"📉 {period_choice} 최저", f"{df_usd['Low'].min():,.2f} 원")

            st.plotly_chart(fig_usd, use_container_width=True, config={'displayModeBar': False})
            st.caption("출처: Yahoo Finance (USDKRW=X) · 장중 실시간 데이터가 아닐 수 있습니다.")

            # 해석 가이드
            with st.expander("💡 환율 해석 가이드"):
                st.markdown(
                    """
                    - **환율 상승(원화 약세):** 수출 기업(삼성전자·현대차 등) 수혜 / 수입 물가·유가 상승 압력
                    - **환율 하락(원화 강세):** 수입 소비재·해외여행 비용 절감 / 수출 기업 실적 압박
                    - **1,300원 돌파:** 외환시장 긴장 신호, 외국인 자금 유출 우려
                    - **1,200원 이하:** 원화 강세 국면, 외국인 순매수 유입 기대
                    """
                )
        else:
            st.warning("USD/KRW 데이터를 불러올 수 없습니다.")

    # ── JPY/KRW 탭 ────────────────────────────────────────
    with tab_jpy:
        fig_jpy, jpy_info = get_fx_chart("JPYKRW=X", "JPY/KRW", "#e74c3c",
                                         period=selected_period, height=380)
        if fig_jpy and jpy_info:
            rate, chg, chg_pct = jpy_info
            rate100    = rate * 100
            chg100     = chg * 100

            m1, m2, m3 = st.columns(3)
            with m1:
                st.metric("¥ 현재 엔화 환율 (100엔)", f"{rate100:,.2f} 원",
                          f"{chg100:+.2f}원 ({chg_pct:+.2f}%)")
            with m2:
                df_jpy = yf.Ticker("JPYKRW=X").history(period=selected_period)
                st.metric(f"📈 {period_choice} 최고 (100엔)", f"{df_jpy['High'].max()*100:,.2f} 원")
            with m3:
                st.metric(f"📉 {period_choice} 최저 (100엔)", f"{df_jpy['Low'].min()*100:,.2f} 원")

            st.plotly_chart(fig_jpy, use_container_width=True, config={'displayModeBar': False})
            st.caption("출처: Yahoo Finance (JPYKRW=X) · 100엔 기준 표시 · 장중 실시간이 아닐 수 있습니다.")

            with st.expander("💡 엔화 환율 해석 가이드"):
                st.markdown(
                    """
                    - **엔화 약세 (저환율):** 일본 여행 비용 절감 / 일본산 수입품 가격 하락
                    - **엔화 강세 (고환율):** 일본 수출 기업 수혜 / 한국 대일 수출 경쟁력 약화
                    - **800원대:** 사상적 엔저 수준, 일본은행 개입 가능성
                    - **900원 이상:** 엔화 정상화 국면, 일·한 금리차 축소 신호
                    """
                )
        else:
            st.warning("JPY/KRW 데이터를 불러올 수 없습니다.")


# ==========================================
# 16. 페이지 3: 추천 종목  ★ 신규: 카드 + 미니 차트
# ==========================================
elif st.session_state['page'] == "⭐ 추천 종목":
    st.title("⭐ AI 추천 종목")

    st.markdown("**기본 추천 목록** + 버튼 클릭 시 **AI 실시간 추천**을 함께 제공합니다.")

    tab_beginner, tab_expert = st.tabs(["🌱 초보자 추천", "🔥 고수 추천"])

    # ── 초보자 기본 목록 ───────────────────────────────────
    default_beginner = [
        {"flag": "🇰🇷", "name": "삼성전자",   "ticker": "005930.KS",
         "desc": "반도체·가전 글로벌 1위, 배당 안정적",
         "reason": "시가총액 1위 방어주, 초보자 장기투자 최적",
         "risk": "반도체 업황 사이클에 따른 주가 변동",   "stars": "⭐"},
        {"flag": "🇰🇷", "name": "KODEX 200",  "ticker": "069500.KS",
         "desc": "코스피200 추종 ETF, 분산투자 효과",
         "reason": "단일 종목 리스크 없이 시장 전체에 투자 가능",
         "risk": "코스피 지수 하락 시 동반 하락",          "stars": "⭐"},
        {"flag": "🇰🇷", "name": "한국전력",   "ticker": "015760.KS",
         "desc": "공기업 안정성, 배당 수익 기대",
         "reason": "경기 불황에도 실적 방어력 높은 유틸리티주",
         "risk": "전기요금 정책 변화에 따른 실적 영향",    "stars": "⭐"},
        {"flag": "🇺🇸", "name": "Apple",      "ticker": "AAPL",
         "desc": "세계 최대 시가총액, 안정적 성장",
         "reason": "강력한 생태계·브랜드 충성도, 배당·자사주 매입",
         "risk": "중국 시장 의존도 및 규제 리스크",        "stars": "⭐"},
        {"flag": "🇺🇸", "name": "S&P 500 ETF","ticker": "SPY",
         "desc": "미국 500대 기업 분산투자 ETF",
         "reason": "미국 주식 시장 전체에 한 번에 투자 가능",
         "risk": "미국 경기침체 시 지수 전반 하락",        "stars": "⭐"},
        {"flag": "🇺🇸", "name": "Coca-Cola",  "ticker": "KO",
         "desc": "60년 연속 배당 증가, 경기 방어주",
         "reason": "소비재 필수품, 불황에도 안정적 수익 유지",
         "risk": "저성장 업종, 고금리 시 상대적 매력 감소", "stars": "⭐"},
    ]

    # ── 고수 기본 목록 ─────────────────────────────────────
    default_expert = [
        {"flag": "🇰🇷", "name": "SK하이닉스",   "ticker": "000660.KS",
         "desc": "HBM 메모리 AI 최대 수혜주",
         "reason": "엔비디아 HBM 공급 1위, AI 인프라 폭증 직접 수혜",
         "risk": "메모리 가격 변동·DRAM 업황 사이클",     "stars": "⭐⭐⭐⭐"},
        {"flag": "🇰🇷", "name": "에코프로비엠", "ticker": "247540.KQ",
         "desc": "2차전지 양극재, 전기차 성장 직접 수혜",
         "reason": "글로벌 전기차 확대 수혜, 삼성SDI·SK온 납품",
         "risk": "전기차 수요 둔화 및 원재료 가격 변동",   "stars": "⭐⭐⭐⭐⭐"},
        {"flag": "🇰🇷", "name": "셀트리온",     "ticker": "068270.KS",
         "desc": "바이오시밀러 글로벌 확장 중",
         "reason": "미국·유럽 바이오시밀러 시장 점유율 확대",
         "risk": "임상 실패·경쟁사 진입 리스크",           "stars": "⭐⭐⭐"},
        {"flag": "🇺🇸", "name": "NVIDIA",       "ticker": "NVDA",
         "desc": "AI 인프라 핵심 GPU 독점적 지위",
         "reason": "데이터센터 AI 가속기 시장 80%+ 점유",
         "risk": "밸류에이션 고평가·AMD 경쟁 심화",        "stars": "⭐⭐⭐⭐"},
        {"flag": "🇺🇸", "name": "Meta Platforms","ticker": "META",
         "desc": "AI 광고·메타버스 실적 고성장",
         "reason": "AI 기반 광고 타겟팅 효율 극대화, EPS 성장세",
         "risk": "개인정보 규제·메타버스 투자 장기화",     "stars": "⭐⭐⭐⭐"},
        {"flag": "🇺🇸", "name": "Palantir",     "ticker": "PLTR",
         "desc": "정부·기업 AI 분석 플랫폼 고성장",
         "reason": "미 국방부·NATO 등 정부 계약 급증, AIP 플랫폼 확장",
         "risk": "높은 밸류에이션, 정부 예산 축소 리스크", "stars": "⭐⭐⭐⭐⭐"},
    ]

    # ── 탭 1: 초보자 ──────────────────────────────────────
    with tab_beginner:
        st.markdown("#### 🌱 처음 투자를 시작하는 분들을 위한 안정적인 종목")
        st.caption("✅ 변동성 낮음 · 배당 안정 · 장기 보유 적합 · 글로벌 브랜드")
        st.markdown("---")
        st.markdown("##### 📋 기본 추천 리스트")

        render_stock_cards(default_beginner)

        st.markdown("---")
        st.markdown("##### 🤖 AI 실시간 추천 (현재 트렌드 기반)")
        st.caption("버튼을 클릭하면 AI가 오늘의 시장 상황을 반영해 종목을 추천합니다.")

        if st.button("✨ AI에게 초보자 추천 종목 받기", use_container_width=True, key="ai_begin"):
            with st.spinner("AI가 시장을 분석 중입니다..."):
                st.session_state['rec_beginner'] = analyze_with_gemini("recommend", "beginner")

        if st.session_state.get('rec_beginner'):
            render_ai_recommendation_cards(st.session_state['rec_beginner'])

    # ── 탭 2: 고수 ────────────────────────────────────────
    with tab_expert:
        st.markdown("#### 🔥 경험 많은 투자자를 위한 성장·모멘텀 종목")
        st.caption("📈 성장 모멘텀 · 기관 매수세 · AI·반도체·바이오 핵심 테마")
        st.markdown("---")
        st.markdown("##### 📋 기본 추천 리스트")

        render_stock_cards(default_expert)

        st.markdown("---")
        st.markdown("##### 🤖 AI 실시간 추천 (현재 트렌드 기반)")
        st.caption("버튼을 클릭하면 AI가 오늘의 시장 상황을 반영해 종목을 추천합니다.")

        if st.button("✨ AI에게 고수 추천 종목 받기", use_container_width=True, key="ai_expert"):
            with st.spinner("AI가 시장을 분석 중입니다..."):
                st.session_state['rec_expert'] = analyze_with_gemini("recommend", "expert")

        if st.session_state.get('rec_expert'):
            render_ai_recommendation_cards(st.session_state['rec_expert'])

    # 면책 고지
    st.markdown("---")
    st.caption(
        "⚠️ **투자 유의사항:** 본 추천 종목은 AI가 공개 정보를 기반으로 생성한 참고 자료이며, "
        "투자 권유가 아닙니다. 모든 투자 결정과 그에 따른 손익은 투자자 본인에게 귀속됩니다."
    )
