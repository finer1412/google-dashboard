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
# 3. 데이터 수집 함수 (캐싱 적용)
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
        # 최대 5개 키워드까지 지원
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
        # 한글, 영문, 숫자 단어 추출 (2글자 이상)
        words = re.findall(r'[가-힣a-zA-Z0-9]{2,}', title)
        for w in words:
            w_lower = w.lower()
            if w_lower not in stopwords and not w.isdigit():
                all_words.append(w)

    return Counter(all_words)


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
st.markdown(f'<div class="sub-title">실시간 Google Trends 검색 관심도 추이와 Google News 최신 기사를 한눈에 비교 분석합니다. (기준: {period_option}, {geo_option})</div>', unsafe_allow_html=True)

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
            # 뉴스로만 표시
            kw_news_count = len(combined_news_df[combined_news_df['keyword'] == kw]) if not combined_news_df.empty else 0
            st.metric(label=f"🔍 {kw}", value=f"뉴스 {kw_news_count}건", delta=None)

st.markdown("<br>", unsafe_allow_html=True)


# ==========================================
# 6. 탭 구성
# ==========================================
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 검색량 추이 분석 (Trends)",
    "📰 최신 뉴스 피드 (News)",
    "☁️ 키워드 & 워드클라우드 (Keywords)",
    "💾 데이터 테이블 & 다운로드 (Data)"
])

# ------------------------------------------
# 탭 1: 검색량 추이 분석
# ------------------------------------------
with tab1:
    st.subheader("📊 키워드별 Google Trends 검색 관심도 추이")
    
    if trends_err:
        st.error(f"⚠️ 트렌드 데이터 조회 실패: {trends_err}")
        st.info("💡 안내: Google Trends 서비스의 일시적인 제한일 수 있습니다. '최신 뉴스 피드' 및 '워드클라우드' 탭은 정상적으로 이용 가능합니다.")
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

        # 입력 키워드 자체는 불용어에 추가하여 의미 있는 주변 연관어를 강조
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
# 탭 4: 원본 데이터 & 다운로드
# ------------------------------------------
with tab4:
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
