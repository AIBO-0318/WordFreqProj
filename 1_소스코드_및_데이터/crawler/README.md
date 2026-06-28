# 🕷️ crawler — 영화 리뷰/코멘트 수집기

이 폴더는 대시보드(`WordFreqWebDashboard.py`)와 감성분석·추천 모델이 사용하는
**원본 데이터를 직접 수집하는 크롤러**들입니다.
데이터(`data/`)와 모델(`model/`)은 용량이 커서 깃허브에 올리지 않으므로,
아래 크롤러로 데이터를 다시 만들 수 있습니다.

> 수집 → 전처리 → (대시보드/감성분석/추천) 으로 이어지는 **데이터 파이프라인의 출발점**입니다.

## 📁 구성

| 파일 | 대상 사이트 | 수집 내용 | 방식 |
|---|---|---|---|
| `watcha_comment_crawler.py` | 왓챠피디아 | 영화별 코멘트 (메인 데이터) | Selenium(URL 수집) + 내부 API(requests) |
| `cgv_review_crawler.py` | CGV | 영화별 실관람평 | Selenium |
| `rogerebert_crawler.py` | rogerebert.com | 영어 영화 리뷰 본문 | Selenium + BeautifulSoup |
| `boxoffice_crawler.py` | KOBIS OpenAPI | 일별 박스오피스 순위 | REST API |
| `save_cookie.py` | 왓챠피디아 | 로그인 세션 쿠키 저장(수동 로그인용) | Selenium |
| `preprocess.py` | — | 왓챠 코멘트 정제(중복/길이/노이즈 제거, 연도 보완) | pandas |
| `_env.py` | — | `.env` 파일에서 비밀값을 읽는 작은 로더 | — |

## 🔐 비밀값 설정 (.env)

로그인 정보와 API 키는 **코드에 직접 적지 않고** `.env` 파일에서 읽습니다.
`.env` 는 `.gitignore` 에 등록되어 깃허브에 올라가지 않습니다.

```bash
cd crawler
cp .env.example .env      # 복사 후 실제 값으로 채우기
```

`.env` 내용 예:
```
WATCHA_EMAIL=your_email@example.com
WATCHA_PASSWORD=your_password
KOBIS_API_KEY=your_kobis_api_key
```

## ▶️ 사용법

```bash
# 0) 패키지 설치 (프로젝트 루트의 requirements.txt)
pip install selenium webdriver-manager beautifulsoup4 requests pandas

cd crawler

# 1) 왓챠 코멘트 수집  → watcha_comments.csv 생성
py watcha_comment_crawler.py
#   - 최초 1회는 .env 의 계정으로 자동 로그인(또는 save_cookie.py 로 수동 로그인 쿠키 저장)
#   - 엔터를 누르면 안전하게 중단/저장. 이어받기 지원(visited_urls.txt)

# 2) 코멘트 전처리  → watcha_comments_clean.csv 생성
py preprocess.py

# 3) 정제 결과를 대시보드가 쓰는 위치로 이동
#    watcha_comments_clean.csv  →  ../data/watcha_comments_clean.csv

# (선택) 다른 소스
py cgv_review_crawler.py        # CGV 실관람평 → cgv_reviews.csv
py rogerebert_crawler.py        # 영어 리뷰   → rogerebert_reviews.csv
py boxoffice_crawler.py         # 박스오피스  → boxoffice_<연도>.csv
```

## ⚠️ 수집 시 주의

- **요청 간 딜레이·세션 쿠키**로 차단(403/429)을 피하도록 만들어져 있습니다. 딜레이를 너무 줄이면 차단될 수 있습니다.
- 왓챠 내부 API는 짧은 시간에 반복 호출하면 **403(봇 차단)** 이 발생하므로 페이싱이 중요합니다.
- 크롤링은 **학습·연구 목적**이며, 각 사이트의 이용약관/robots 정책을 준수하세요.
- `watcha_session.pkl`, `*_visited_urls.txt`, 수집된 `*.csv` 는 `.gitignore` 처리되어 깃허브에 올라가지 않습니다.
