import os
import re
import urllib.parse
from datetime import datetime, timedelta
from collections import Counter

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import feedparser
from pytrends.request import TrendReq
from wordcloud import WordCloud
import matplotlib.pyplot as plt

# ==========================================
# 1. 페이지 기본 설정 및 스타일
# ==========================================
st.set_page_config(
    page_title="Google 트렌드 & 뉴스 분석 대시보드",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    /* 메인 타이틀 및 카드 스타일 */
    .main-title {
        font-size: 2.1rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
        color: #1E3A8A;
    }
    .sub-title {
        font-size: 1.0rem;
        color: #64748B;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 10px;
        padding: 15px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.03);
    }
    .news-card {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 14px 18px;
        margin-bottom: 10px;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .news-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.06);
        border-color: #CBD5E1;
    }
    .news-title {
        font-size: 1.05rem;
        font-weight: 600;
        color: #1E293B;
        text-decoration: none;
    }
    .news-title:hover {
        color: #2563EB;
        text-decoration: underline;
    }
    .news-meta {
        font-size: 0.85rem;
        color: #64748B;
        margin-top: 6px;
    }
    .source-badge {
        display: inline-block;
        background-color: #EFF6FF;
        color: #2563EB;
        font-size: 0.78rem;
        font-weight: 600;
        padding: 2px 8px;
        border-radius: 12px;
        margin-right: 8px;
    }
    /* 상품 추천 카드 스타일 */
    .product-box {
        background-color: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 16px;
        box-shadow: 0 2px 5px rgba(0,0,0,0.03);
        transition: all 0.2s ease;
        min-height: 250px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .product-box:hover {
        border-color: #3B82F6;
        box-shadow: 0 6px 16px rgba(59,130,246,0.10);
        transform: translateY(-2px);
    }
    .product-tag {
        display: inline-block;
        background-color: #EEF2FF;
        color: #4F46E5;
        font-size: 0.78rem;
        font-weight: 600;
        padding: 3px 9px;
        border-radius: 6px;
        margin-bottom: 10px;
    }
    .product-name {
        font-size: 1.1rem;
        font-weight: 700;
        color: #0F172A;
        line-height: 1.4;
        margin-bottom: 6px;
    }
    .product-price {
        font-size: 0.95rem;
        font-weight: 600;
        color: #059669;
        margin-bottom: 10px;
    }
    .product-desc-list {
        font-size: 0.88rem;
        color: #475569;
        padding-left: 18px;
        margin-bottom: 15px;
        flex-grow: 1;
    }
    .product-desc-list li {
        margin-bottom: 4px;
    }
    .shop-hub-banner {
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%);
        color: white;
        border-radius: 12px;
        padding: 20px 24px;
        margin-bottom: 24px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        white-space: pre-wrap;
        font-weight: 600;
        border-radius: 8px 8px 0px 0px;
        padding: 10px 18px;
    }
</style>
""", unsafe_allow_html=True)


# ==========================================
# 2. 폰트 및 유틸리티 설정
# ==========================================
def get_korean_font_path():
    """Windows 환경 한글 폰트 경로 탐색"""
    font_candidates = [
        "C:/Windows/Fonts/malgun.ttf",       # 맑은 고딕
        "C:/Windows/Fonts/malgunbd.ttf",     # 맑은 고딕 Bold
        "C:/Windows/Fonts/gulim.ttc",        # 굴림
        "C:/Windows/Fonts/batang.ttc",       # 바탕
        "C:/Windows/Fonts/NanumGothic.ttf",  # 나눔고딕
    ]
    for font in font_candidates:
        if os.path.exists(font):
            return font
    return None

FONT_PATH = get_korean_font_path()

# 불용어(Stopwords) 목록
STOPWORDS_KO = {
    '기자', '뉴스', '속보', '단독', '포토', '영상', '종합', '일보', '신문', '닷컴',
    '헤럴드', '연합뉴스', '뉴시스', '뉴스1', '동아일보', '조선일보', '중앙일보', '기사',
    '오늘', '내일', '어제', '지난해', '올해', '이번', '지난', '최근', '관련', '대한',
    '위한', '통해', '대해', '것', '수', '등', '및', '또', '더', '그', '이', '저',
    '있다', '했다', '밝혔다', '말했다', '전했다', '열린', '개최', '발표', '사진', '이유',
    '시장', '국내', '글로벌', '세계', '한국', '미국', '대비', '전년', '기준', '올해'
}


# ==========================================
# 3. 데이터 수집 및 비즈니스 로직 함수
# ==========================================
@st.cache_data(ttl=600, show_spinner=False)
def fetch_google_trends(keywords, period_option, geo):
    """
    pytrends를 이용해 Google Trends 검색량 추이 데이터 수집
    """
    if not keywords:
        return pd.DataFrame(), None

    # 기간 설정
    end_date = datetime.now()
    if period_option == "지난 1개월":
        timeframe = "today 1-m"
    elif period_option == "지난 6개월":
        start_date = end_date - timedelta(days=180)
        timeframe = f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
    elif period_option == "지난 1년":
        timeframe = "today 12-m"
    else:
        timeframe = "today 1-m"

    geo_code = "" if geo == "GLOBAL" else geo

    try:
        pytrend = TrendReq(hl='ko-KR' if geo == 'KR' else 'en-US', tz=540, timeout=(10, 25))
        kw_list = [k.strip() for k in keywords[:5] if k.strip()]
        pytrend.build_payload(kw_list=kw_list, timeframe=timeframe, geo=geo_code)
        df = pytrend.interest_over_time()

        if df is not None and not df.empty:
            if 'isPartial' in df.columns:
                df = df.drop(columns=['isPartial'])
            return df, None
        else:
            return pd.DataFrame(), "조회된 검색량 트렌드 데이터가 없습니다."
    except Exception as e:
        err_msg = str(e)
        if "429" in err_msg:
            err_msg = "Google Trends 요청 한도(Rate Limit / HTTP 429)에 도달했습니다. 잠시 후 다시 시도해주세요."
        return pd.DataFrame(), err_msg


@st.cache_data(ttl=300, show_spinner=False)
def fetch_google_news(keyword, limit=30, geo='KR'):
    """
    feedparser를 이용해 Google News RSS 피드 수집
    """
    if not keyword:
        return pd.DataFrame()

    encoded_kw = urllib.parse.quote(keyword.strip())
    if geo == "KR":
        rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=ko&gl=KR&ceid=KR:ko"
    elif geo == "US":
        rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=en-US&gl=US&ceid=US:en"
    else:
        rss_url = f"https://news.google.com/rss/search?q={encoded_kw}&hl=en&gl=US&ceid=US:en"

    feed = feedparser.parse(rss_url)
    items = []

    for entry in feed.entries[:limit]:
        title = entry.title if hasattr(entry, 'title') else "제목 없음"
        link = entry.link if hasattr(entry, 'link') else "#"
        
        # 언론사 분리 (Google RSS는 '기사 제목 - 언론사' 형태로 제공)
        source = "Google News"
        clean_title = title
        if " - " in title:
            parts = title.rsplit(" - ", 1)
            clean_title = parts[0]
            source = parts[1]
        elif hasattr(entry, 'source') and hasattr(entry.source, 'title'):
            source = entry.source.title

        # 발행 일자 포맷팅
        pub_date = ""
        if hasattr(entry, 'published_parsed') and entry.published_parsed:
            try:
                dt = datetime(*entry.published_parsed[:6]) + timedelta(hours=9) # KST 변환
                pub_date = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                pub_date = entry.published if hasattr(entry, 'published') else ""
        elif hasattr(entry, 'published'):
            pub_date = entry.published

        items.append({
            'keyword': keyword,
            'title': clean_title,
            'original_title': title,
            'source': source,
            'link': link,
            'published': pub_date
        })

    return pd.DataFrame(items)


def extract_keywords_from_titles(titles, extra_stopwords=None):
    """
    뉴스 제목들로부터 명사 및 핵심 단어 빈도 추출
    """
    stopwords = set(STOPWORDS_KO)
    if extra_stopwords:
        stopwords.update(extra_stopwords)

    all_words = []
    for title in titles:
        words = re.findall(r'[가-힣a-zA-Z0-9]{2,}', title)
        for w in words:
            w_lower = w.lower()
            if w_lower not in stopwords and not w.isdigit():
                all_words.append(w)

    return Counter(all_words)


def get_recommended_products(keyword):
    """
    키워드별 추천 상품 카탈로그 및 동적 큐레이션 데이터 생성
    """
    kw = keyword.strip()
    
    # 대표 카테고리 큐레이션 데이터베이스
    curated_catalog = {
        "인공지능": [
            {
                "name": "Google Nest Hub (2세대) 스마트 디스플레이",
                "tag": "AI 스마트홈",
                "price": "약 80,000원 ~ 110,000원",
                "features": ["Google Assistant 탑재", "7인치 터치스크린 & 수면 센싱", "IoT 기기 통합 음성 제어"],
                "query": "구글 네스트 허브 2세대"
            },
            {
                "name": "라즈베리파이 5 AI 스타터 키트 (Raspberry Pi AI)",
                "tag": "개발 / 입문",
                "price": "약 140,000원 ~ 180,000원",
                "features": ["온디바이스 AI 비전 모델 구동 지원", "Hailo-8L NPU 모듈 확장 가능", "Python 기반 딥러닝 실습"],
                "query": "라즈베리파이 5 AI 키트"
            },
            {
                "name": "NVIDIA Jetson Orin Nano 개발자 키트",
                "tag": "고성능 AI",
                "price": "약 650,000원 ~ 780,000원",
                "features": ["최대 40 TOPS AI 연산 지원", "생성형 AI 및 임베디드 로보틱스 개발", "공식 CUDA 라이브러리 지원"],
                "query": "NVIDIA Jetson Orin Nano"
            },
            {
                "name": "생성형 AI & 챗GPT 실무 프롬프트 바이블",
                "tag": "도서 / 가이드",
                "price": "약 22,000원 ~ 30,000원",
                "features": ["ChatGPT, Claude, 미드저니 실무 활용법", "업무 자동화 템플릿 100종 수록", "입문자용 단계별 설명"],
                "query": "생성형 AI 프롬프트 도서"
            }
        ],
        "로봇": [
            {
                "name": "로보락 S8 Pro Ultra / MaxV 올인원 로봇청소기",
                "tag": "생활 가전 베스트",
                "price": "약 1,300,000원 ~ 1,600,000원",
                "features": ["자동 먼지 비움 및 물걸레 온수 세척", "AI 장애물 3D 인식 및 회피", "듀얼 롤러 및 강력한 흡입력"],
                "query": "로보락 올인원 로봇청소기"
            },
            {
                "name": "레고 스파이크 프라임 (SPIKE Prime) 코딩 로봇 교구",
                "tag": "교육 / 코딩",
                "price": "약 480,000원 ~ 560,000원",
                "features": ["초중고 STEAM 코딩 교육 표준 키트", "Scratch & Python 프로그래밍 지원", "다양한 서보모터 및 센서 포함"],
                "query": "레고 스파이크 프라임 로봇"
            },
            {
                "name": "스마트 4족 보행 로봇 키트 (Bionic Quadruped Robot)",
                "tag": "취미 / 공학",
                "price": "약 160,000원 ~ 240,000원",
                "features": ["카메라 기반 자율 주행 및 모션 제어", "스마트폰 앱 원격 조작 지원", "역동작 보행 알고리즘 탑재"],
                "query": "4족 보행 로봇 키트"
            },
            {
                "name": "초음파 유리창 청소 로봇 (스마트 윈도우 클리너)",
                "tag": "스마트 리빙",
                "price": "약 120,000원 ~ 210,000원",
                "features": ["초음파 듀얼 물분사 시스템", "진공 흡착 안전 낙하 방지", "원터치 스마트 경로 주행"],
                "query": "유리창 청소 로봇"
            }
        ],
        "챗봇": [
            {
                "name": "Amazon Echo Dot (5세대) 알렉사 스마트 스피커",
                "tag": "음성 대화 비서",
                "price": "약 65,000원 ~ 85,000원",
                "features": ["대화형 음성 AI 비서 지원", "선명한 사운드 및 모션 감지 센서", "스마트홈 조명 및 플러그 연동"],
                "query": "Amazon Echo Dot 5세대"
            },
            {
                "name": "ChatGPT API와 랭체인(LangChain)으로 만드는 챗봇",
                "tag": "추천 도서",
                "price": "약 26,000원 ~ 34,000원",
                "features": ["Python 기반 LLM 챗봇 개발 가이드", "RAG(검색 증강 생성) 시스템 구축", "카카오톡/슬랙 봇 연동"],
                "query": "ChatGPT API 랭체인 챗봇 도서"
            },
            {
                "name": "엘가토 스트림덱 (Stream Deck MK.2) 매크로 패드",
                "tag": "업무 생산성",
                "price": "약 190,000원 ~ 230,000원",
                "features": ["AI 프롬프트 원클릭 매크로 키 등록", "15개 커스텀 LCD 키패드", "반복적인 업무 효율 300% 향상"],
                "query": "엘가토 스트림덱 MK.2"
            },
            {
                "name": "AI 빔포밍 마이크 무선 헤드셋 (음성 대화 최적화)",
                "tag": "하드웨어",
                "price": "약 180,000원 ~ 320,000원",
                "features": ["AI 주변 소음 제거 알고리즘 탑재", "선명한 음성 인식율 보장", "장시간 화상 회의 및 음성 대화용"],
                "query": "AI 빔포밍 마이크 무선 헤드셋"
            }
        ]
    }
    
    # 큐레이션 데이터 매칭 확인
    for key, items in curated_catalog.items():
        if key in kw or kw in key:
            return items
            
    # 매칭되지 않는 일반 키워드: 동적 템플릿 생성
    return [
        {
            "name": f"실시간 인기 {kw} 베스트셀러 컬렉션",
            "tag": "인기 베스트",
            "price": "가격비교 확인",
            "features": [f"소비자 만족도 1위 {kw} 대표 아이템", "실시간 쇼핑 랭킹 상위권", "최신 트렌드 반영 디자인"],
            "query": f"{kw} 인기 베스트셀러"
        },
        {
            "name": f"{kw} 입문자 맞춤형 스타터 패키지",
            "tag": "입문 / 스타터",
            "price": "가성비 추천",
            "features": [f"{kw} 시작에 꼭 필요한 핵심 구성", "입문자 친화적 가성비 라인업", "손쉬운 사용 및 관리"],
            "query": f"{kw} 입문 추천"
        },
        {
            "name": f"프리미엄 하이엔드 {kw} 스펙 모델",
            "tag": "프리미엄",
            "price": "고급형",
            "features": [f"최고급 사양 및 우수한 내구성", f"{kw} 전문가 및 얼리어답터 강력 추천", "프리미엄 사후 지원"],
            "query": f"{kw} 프리미엄 추천"
        },
        {
            "name": f"{kw} 활용 극대화 필수 액세서리 & 도서",
            "tag": "액세서리 / 가이드",
            "price": "다양한 가격대",
            "features": [f"{kw} 사용 편의성을 높여주는 보조 용품", "실전 활용 가이드 및 보조 툴", "높은 호환성"],
            "query": f"{kw} 추천 액세서리"
        }
    ]


# ==========================================
# 4. 사이드바 UI
# ==========================================
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/google-trends.png", width=64)
    st.title("검색 조건 설정")
    st.markdown("비교할 키워드와 기간을 설정하세요.")

    # 키워드 입력
    default_keywords = "인공지능, 챗봇, 로봇"
    kw_input = st.text_input(
        "비교 키워드 (쉼표로 구분, 2~3개 권장)",
        value=default_keywords,
        help="예시: 인공지능, 로봇, 챗봇 (최대 5개까지 지원)"
    )
    
    # 키워드 파싱
    keywords = [k.strip() for k in kw_input.split(",") if k.strip()]
    
    # 기간 선택
    period_option = st.selectbox(
        "트렌드 분석 기간",
        options=["지난 1개월", "지난 6개월", "지난 1년"],
        index=1,
        help="Google Trends에서 수집할 검색량 기간을 선택합니다."
    )

    # 지역/국가 선택
    geo_option = st.selectbox(
        "분석 국가 / 지역",
        options=["KR (대한민국)", "US (미국)", "GLOBAL (전세계)"],
        index=0
    )
    geo_code = geo_option.split()[0]

    # 뉴스 수집 건수
    news_limit = st.slider(
        "키워드별 뉴스 수집 건수",
        min_value=10,
        max_value=50,
        value=25,
        step=5
    )

    st.markdown("---")
    refresh_button = st.button("🔄 데이터 새로고침", use_container_width=True)

    st.caption("💡 **안내**  \n- Google Trends API는 단시간 내 잦은 호출 시 일시적으로 조회가 지연될 수 있습니다. (캐싱 적용됨)  \n- 뉴스 데이터는 Google News 공식 RSS 피드를 통해 실시간 수집됩니다.")


# ==========================================
# 5. 메인 대시보드 뷰
# ==========================================

# 헤더 영역
st.markdown('<div class="main-title">📈 Google 트렌드 & 뉴스 분석 대시보드</div>', unsafe_allow_html=True)
st.markdown(f'<div class="sub-title">실시간 Google Trends 검색 관심도 추이, 최신 뉴스, 연관 상품 추천을 한눈에 비교 분석합니다. (기준: {period_option}, {geo_option})</div>', unsafe_allow_html=True)

if not keywords:
    st.warning("⚠️ 사이드바에서 분석할 키워드를 1개 이상 입력해주세요.")
    st.stop()

# 데이터 로딩 스피너
with st.spinner("Google Trends 및 뉴스 데이터를 수집하는 중입니다..."):
    # 1) Trends 데이터 수집
    df_trends, trends_err = fetch_google_trends(keywords, period_option, geo_code)
    
    # 2) News 데이터 수집 (키워드별)
    all_news_dfs = []
    for kw in keywords:
        news_df = fetch_google_news(kw, limit=news_limit, geo=geo_code)
        if not news_df.empty:
            all_news_dfs.append(news_df)
    
    combined_news_df = pd.concat(all_news_dfs, ignore_index=True) if all_news_dfs else pd.DataFrame()


# 상단 요약 KPI 메트릭 카드
st.markdown("### 📌 핵심 요약 지표")
metric_cols = st.columns(len(keywords))

for idx, kw in enumerate(keywords):
    with metric_cols[idx]:
        if not df_trends.empty and kw in df_trends.columns:
            avg_val = df_trends[kw].mean()
            max_val = df_trends[kw].max()
            last_val = df_trends[kw].iloc[-1]
            max_date = df_trends[kw].idxmax().strftime('%m-%d')
            
            # 이전 대비 증감
            if len(df_trends[kw]) >= 2:
                prev_val = df_trends[kw].iloc[-2]
                delta_val = last_val - prev_val
            else:
                delta_val = 0
            
            st.metric(
                label=f"🔍 {kw}",
                value=f"{last_val} pt",
                delta=f"{delta_val:+.0f} pt (최근)",
                help=f"기간 평균: {avg_val:.1f} pt | 최고: {max_val} pt ({max_date})"
            )
        else:
            kw_news_count = len(combined_news_df[combined_news_df['keyword'] == kw]) if not combined_news_df.empty else 0
            st.metric(label=f"🔍 {kw}", value=f"뉴스 {kw_news_count}건", delta=None)

st.markdown("<br>", unsafe_allow_html=True)


# ==========================================
# 6. 탭 구성
# ==========================================
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "📊 검색량 추이 분석 (Trends)",
    "📰 최신 뉴스 피드 (News)",
    "☁️ 키워드 & 워드클라우드 (Keywords)",
    "🛍️ 키워드별 상품 추천 (Products)",
    "💾 데이터 테이블 & 다운로드 (Data)"
])

# ------------------------------------------
# 탭 1: 검색량 추이 분석
# ------------------------------------------
with tab1:
    st.subheader("📊 키워드별 Google Trends 검색 관심도 추이")
    
    if trends_err:
        st.error(f"⚠️ 트렌드 데이터 조회 실패: {trends_err}")
        st.info("💡 안내: Google Trends 서비스의 일시적인 제한일 수 있습니다. '최신 뉴스 피드', '워드클라우드', '상품 추천' 탭은 정상적으로 이용 가능합니다.")
    elif df_trends.empty:
        st.warning("선택한 조건에 대한 트렌드 검색 결과가 없습니다.")
    else:
        # Plotly 라인 차트 생성
        fig = go.Figure()
        
        colors = ['#2563EB', '#EC4899', '#10B981', '#F59E0B', '#8B5CF6']
        for i, kw in enumerate(keywords):
            if kw in df_trends.columns:
                color = colors[i % len(colors)]
                fig.add_trace(go.Scatter(
                    x=df_trends.index,
                    y=df_trends[kw],
                    mode='lines+markers',
                    name=kw,
                    line=dict(width=2.5, color=color, shape='spline'),
                    marker=dict(size=4),
                    hovertemplate=f"<b>{kw}</b><br>날짜: %{{x|%Y-%m-%d}}<br>관심도: %{{y}} pt<extra></extra>"
                ))
        
        fig.update_layout(
            title={
                'text': f"Google Trends 상대 검색 관심도 비교 ({period_option})",
                'x': 0.01,
                'xanchor': 'left',
                'font': {'size': 16}
            },
            xaxis=dict(
                title="날짜",
                showgrid=True,
                gridcolor="#F1F5F9",
                zeroline=False
            ),
            yaxis=dict(
                title="상대 관심도 (0-100)",
                range=[0, 105],
                showgrid=True,
                gridcolor="#F1F5F9",
                zeroline=False
            ),
            hovermode="x unified",
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            ),
            margin=dict(l=40, r=40, t=60, b=40),
            plot_bgcolor='white',
            paper_bgcolor='white',
            height=460,
        )
        
        st.plotly_chart(fig, use_container_width=True)

        # 트렌드 통계 요약 테이블
        st.markdown("#### 📋 기간 내 트렌드 통계 요약")
        summary_rows = []
        for kw in keywords:
            if kw in df_trends.columns:
                series = df_trends[kw]
                summary_rows.append({
                    "키워드": kw,
                    "최고 검색량 (Max)": f"{series.max():.0f}",
                    "최고 기록 일자": series.idxmax().strftime('%Y-%m-%d'),
                    "평균 검색량 (Mean)": f"{series.mean():.1f}",
                    "최저 검색량 (Min)": f"{series.min():.0f}",
                    "최신 검색량 (Current)": f"{series.iloc[-1]:.0f}"
                })
        
        if summary_rows:
            summary_df = pd.DataFrame(summary_rows)
            st.dataframe(summary_df, use_container_width=True, hide_index=True)


# ------------------------------------------
# 탭 2: 최신 뉴스 피드
# ------------------------------------------
with tab2:
    st.subheader("📰 Google News 실시간 피드")

    if combined_news_df.empty:
        st.warning("수집된 뉴스가 없습니다.")
    else:
        # 뉴스 필터링 서브 헤더
        filter_col1, filter_col2 = st.columns([1, 2])
        with filter_col1:
            selected_news_kw = st.selectbox(
                "조회할 키워드 선택",
                options=["전체 키워드"] + keywords,
                index=0
            )
        with filter_col2:
            search_query = st.text_input("🔍 뉴스 제목 내 실시간 필터링", placeholder="검색어를 입력하면 관련 뉴스만 즉시 필터링됩니다.")

        filtered_news = combined_news_df.copy()
        if selected_news_kw != "전체 키워드":
            filtered_news = filtered_news[filtered_news['keyword'] == selected_news_kw]
        
        if search_query:
            filtered_news = filtered_news[filtered_news['title'].str.contains(search_query, case=False, na=False)]

        st.caption(f"총 **{len(filtered_news)}**건의 뉴스가 표시됩니다.")

        # 뉴스 리스트 렌더링
        for _, row in filtered_news.iterrows():
            st.markdown(f"""
            <div class="news-card">
                <div>
                    <a href="{row['link']}" target="_blank" class="news-title">{row['title']}</a>
                </div>
                <div class="news-meta">
                    <span class="source-badge">키워드: {row['keyword']}</span>
                    <span class="source-badge" style="background-color: #F1F5F9; color: #475569;">언론사: {row['source']}</span>
                    <span>🕒 {row['published']}</span>
                    <span style="float: right;">
                        <a href="{row['link']}" target="_blank" style="color: #2563EB; font-weight: 500; text-decoration: none;">원문 보기 ↗</a>
                    </span>
                </div>
            </div>
            """, unsafe_allow_html=True)


# ------------------------------------------
# 탭 3: 뉴스 키워드 & 워드클라우드
# ------------------------------------------
with tab3:
    st.subheader("☁️ 뉴스 제목 기반 키워드 빈도 & 워드클라우드")
    
    if combined_news_df.empty:
        st.warning("분석할 뉴스 데이터가 없습니다.")
    else:
        col_ctrl1, col_ctrl2 = st.columns([2, 2])
        with col_ctrl1:
            wc_keyword_sel = st.selectbox(
                "분석 대상 키워드",
                options=["전체 키워드 종합"] + keywords,
                index=0
            )
        with col_ctrl2:
            top_n = st.slider("상위 빈출 키워드 표시 개수", min_value=10, max_value=30, value=15)

        # 텍스트 추출 대상 필터링
        if wc_keyword_sel == "전체 키워드 종합":
            titles_to_analyze = combined_news_df['title'].tolist()
        else:
            titles_to_analyze = combined_news_df[combined_news_df['keyword'] == wc_keyword_sel]['title'].tolist()

        current_stopwords = set([k.lower() for k in keywords])
        word_counts = extract_keywords_from_titles(titles_to_analyze, extra_stopwords=current_stopwords)

        if not word_counts:
            st.info("유효한 키워드를 추출하지 못했습니다.")
        else:
            col_wc, col_bar = st.columns([1.1, 1.0])
            
            # 1) WordCloud 생성
            with col_wc:
                st.markdown("##### 📌 워드클라우드 (Word Cloud)")
                try:
                    wc_params = {
                        "width": 600,
                        "height": 450,
                        "background_color": "white",
                        "colormap": "Blues",
                        "max_words": 80,
                        "random_state": 42
                    }
                    if FONT_PATH:
                        wc_params["font_path"] = FONT_PATH

                    wc = WordCloud(**wc_params).generate_from_frequencies(word_counts)
                    
                    fig_wc, ax = plt.subplots(figsize=(6, 4.5))
                    ax.imshow(wc, interpolation="bilinear")
                    ax.axis("off")
                    st.pyplot(fig_wc)
                    plt.close(fig_wc)
                except Exception as ex:
                    st.error(f"워드클라우드 생성 중 오류 발생: {ex}")

            # 2) 상위 키워드 Plotly Bar 차트
            with col_bar:
                st.markdown(f"##### 📊 Top {top_n} 빈출 키워드")
                most_common = word_counts.most_common(top_n)
                words, counts = zip(*most_common)
                
                df_bar = pd.DataFrame({'단어': words, '빈도수': counts}).sort_values(by='빈도수', ascending=True)
                
                fig_bar = px.bar(
                    df_bar,
                    x='빈도수',
                    y='단어',
                    orientation='h',
                    text='빈도수',
                    color='빈도수',
                    color_continuous_scale='Blues'
                )
                fig_bar.update_traces(textposition='outside')
                fig_bar.update_layout(
                    height=450,
                    margin=dict(l=10, r=30, t=10, b=10),
                    xaxis_title="등장 빈도 (회)",
                    yaxis_title="",
                    plot_bgcolor='white',
                    paper_bgcolor='white',
                    coloraxis_showscale=False
                )
                st.plotly_chart(fig_bar, use_container_width=True)


# ------------------------------------------
# 탭 4: 키워드별 추천 상품 & 쇼핑 허브
# ------------------------------------------
with tab4:
    st.subheader("🛍️ 키워드별 대표 추천 상품 & 쇼핑 허브")
    st.markdown("현재 분석 중인 키워드와 연관된 인기 상품과 실시간 최저가 쇼핑 검색 바로가기를 제공합니다.")

    # 1. 대상 키워드 선택
    col_sel_kw, col_custom_kw = st.columns([1.5, 2])
    with col_sel_kw:
        active_shop_kw = st.selectbox(
            "상품 추천 대상 키워드 선택",
            options=keywords,
            index=0,
            key="product_tab_keyword_select"
        )
    with col_custom_kw:
        custom_search_kw = st.text_input(
            "🔎 세부 상품 검색어 직접 입력 (선택)",
            value=active_shop_kw,
            help="기본 키워드 대신 원하는 구체적인 상품명(예: 로봇청소기, 인공지능 스피커)을 입력할 수 있습니다."
        )

    target_query = custom_search_kw.strip() if custom_search_kw.strip() else active_shop_kw
    encoded_query = urllib.parse.quote(target_query)

    # 2. 실시간 원클릭 쇼핑 검색 허브 배너 & 버튼
    st.markdown(f"""
    <div class="shop-hub-banner">
        <h4 style="margin: 0; color: white;">🛒 '{target_query}' 실시간 쇼핑 가격비교 허브</h4>
        <p style="margin: 6px 0 0 0; opacity: 0.9; font-size: 0.92rem;">
            국내외 주요 쇼핑 플랫폼에서 '{target_query}' 관련 실시간 최저가, 사용자 평점 및 배송 정보를 즉시 비교할 수 있습니다.
        </p>
    </div>
    """, unsafe_allow_html=True)

    hub_col1, hub_col2, hub_col3, hub_col4 = st.columns(4)
    with hub_col1:
        google_shop_url = f"https://www.google.com/search?tbm=shop&q={encoded_query}"
        st.link_button("🌐 Google Shopping 최저가 ↗", google_shop_url, use_container_width=True)
    with hub_col2:
        naver_shop_url = f"https://search.shopping.naver.com/search/all?query={encoded_query}"
        st.link_button("🟢 네이버 쇼핑 검색 ↗", naver_shop_url, use_container_width=True)
    with hub_col3:
        danawa_url = f"https://search.danawa.com/dsearch.php?query={encoded_query}"
        st.link_button("🔵 다나와 가격비교 ↗", danawa_url, use_container_width=True)
    with hub_col4:
        coupang_url = f"https://www.coupang.com/np/search?q={encoded_query}"
        st.link_button("🚀 쿠팡 로켓배송 검색 ↗", coupang_url, use_container_width=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # 3. 키워드별 추천 상품 카드 그리드
    st.markdown(f"#### 💡 '{active_shop_kw}' 관련 대표 큐레이션 상품")
    recommended_items = get_recommended_products(active_shop_kw)

    # 2열 x 2행 카드 레이아웃
    col_prod_left, col_prod_right = st.columns(2)
    
    for idx, item in enumerate(recommended_items):
        target_col = col_prod_left if idx % 2 == 0 else col_prod_right
        with target_col:
            features_html = "".join([f"<li>{f}</li>" for f in item["features"]])
            item_search_url = f"https://www.google.com/search?tbm=shop&q={urllib.parse.quote(item['query'])}"
            
            st.markdown(f"""
            <div class="product-box">
                <div>
                    <span class="product-tag">{item['tag']}</span>
                    <div class="product-name">{item['name']}</div>
                    <div class="product-price">💰 예상 가격대: {item['price']}</div>
                    <ul class="product-desc-list">
                        {features_html}
                    </ul>
                </div>
            </div>
            """, unsafe_allow_html=True)
            st.link_button(
                label=f"🔍 '{item['query']}' Google Shopping 최저가 확인 ↗",
                url=item_search_url,
                use_container_width=True
            )
            st.markdown("<div style='margin-bottom: 20px;'></div>", unsafe_allow_html=True)

    st.info("💡 **쇼핑 팁**: 관심 있는 상품의 'Google Shopping 최저가 확인' 버튼을 누르면 실시간 최저가, 판매처별 가격 비교, 배송비 및 구매 후기를 즉시 확인할 수 있습니다.")


# ------------------------------------------
# 탭 5: 원본 데이터 & 다운로드
# ------------------------------------------
with tab5:
    st.subheader("💾 데이터 원본 및 내보내기")
    
    st.markdown("#### 1. Google Trends 시계열 데이터")
    if not df_trends.empty:
        st.dataframe(df_trends, use_container_width=True)
        csv_trends = df_trends.to_csv().encode('utf-8-sig')
        st.download_button(
            label="📥 트렌드 데이터 CSV 다운로드",
            data=csv_trends,
            file_name=f"google_trends_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("트렌드 데이터가 비어 있습니다.")

    st.markdown("---")
    st.markdown("#### 2. Google News 수집 데이터")
    if not combined_news_df.empty:
        st.dataframe(combined_news_df[['keyword', 'title', 'source', 'published', 'link']], use_container_width=True)
        csv_news = combined_news_df.to_csv(index=False).encode('utf-8-sig')
        st.download_button(
            label="📥 뉴스 데이터 CSV 다운로드",
            data=csv_news,
            file_name=f"google_news_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
        )
    else:
        st.info("수집된 뉴스 데이터가 없습니다.")

# ==========================================
# 7. 푸터
# ==========================================
st.markdown("---")
st.markdown(
    "<div style='text-align: center; color: #94A3B8; font-size: 0.85rem;'>"
    "Google Trends & Google News RSS Streamlit Dashboard | Built with pytrends, feedparser, plotly & wordcloud"
    "</div>",
    unsafe_allow_html=True
)
