# 📈 Google 트렌드 & 뉴스 분석 Streamlit 대시보드

Google Trends 검색 관심도 추이와 Google News RSS 피드를 종합 분석하고 시각화하는 Streamlit 대시보드 웹 애플리케이션입니다.

---

## 🌟 주요 기능

1. **Google Trends 검색량 추이 비교 (Plotly 라인 차트)**
   - `pytrends` 라이브러리를 활용한 상대 검색 관심도(0~100) 수집
   - 기간 선택 옵션: **지난 1개월**, **지난 6개월**, **지난 1년**
   - 부드러운 스플라인 곡선과 인터랙티브 툴팁(hovermode)이 적용된 라인 차트
   - 키워드별 최고 검색일자, 평균값, 변동량 등 핵심 요약 KPI 지표 제공

2. **Google News 실시간 피드 (feedparser)**
   - Google News 공식 RSS 피드를 통해 입력한 키워드 관련 최신 뉴스 실시간 수집
   - 기사 제목, 언론사 태그, 발행일시(KST 변환), 원문 바로가기 링크 제공
   - 뉴스 목록 내 실시간 키워드 필터링 및 키워드별 탭 조회 기능

3. **뉴스 제목 기반 키워드 빈도 & 워드클라우드**
   - Windows 시스템 한글 폰트(`malgun.ttf` 등)를 자동 감지하여 한글 깨짐 방지
   - 불용어(Stopwords) 제거 및 형태소/단어 빈도 카운팅
   - **WordCloud 시각화**와 **Top N 빈출 단어 수평 막대 차트(Plotly Bar)** 동시 제공

4. **키워드별 상품 추천 & 실시간 쇼핑 허브 (신규 🛍️)**
   - 선택된 키워드와 연관된 대표 추천 상품 큐레이션 (상품명, 카테고리 태그, 예상 가격대, 핵심 특징)
   - 임의의 키워드 입력 시에도 동적으로 상품 추천 및 최저가 검색 연계
   - **Google Shopping 실시간 최저가 검색** (`https://www.google.com/search?tbm=shop&q=...`) 원클릭 바로가기 버튼
   - 네이버 쇼핑, 다나와, 쿠팡 등 주요 쇼핑몰 바로가기 허브 제공

5. **사이드바 제어 및 편의 기능**
   - 쉼표(,)로 구분된 키워드 2~3개 자유 입력 (최대 5개)
   - 국가/지역 선택 (KR 대한민국, US 미국, GLOBAL 전세계)
   - 키워드별 뉴스 수집 건수 슬라이더 조절
   - `@st.cache_data` 적용을 통한 불필요한 API 재호출 방지 및 Rate Limit 대응
   - 수집된 트렌드 시계열 및 뉴스 목록의 **CSV 다운로드** 지원

---

## 🚀 실행 방법

### 1. 가상환경 활성화 및 실행
PowerShell에서 아래 명령어를 실행합니다:

```powershell
cd C:\Users\USER\.gemini\antigravity\scratch\google_trends_dashboard
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 주소로 접속하면 대시보드를 바로 이용하실 수 있습니다.
