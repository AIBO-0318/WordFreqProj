# 🎬 왓챠피디아 코멘트 단어 빈도수 분석 웹 대시보드

왓챠피디아에서 크롤링한 영화 코멘트(약 150만 개 / 309편)를 형태소 분석하여
자주 쓰인 단어를 **워드클라우드**와 **막대그래프**로 시각화하는 Streamlit 대시보드입니다.

> 인공지능서비스개발 강의 — `03. Streamlit(웹대시보드개발 라이브러리)` 미니 프로젝트 구조를 따릅니다.

## 📁 프로젝트 구조

```
WordFreqProj/
├── crawler/                          # 원본 데이터 수집 크롤러 (파이프라인 시작점)
│   ├── watcha_comment_crawler.py     #   왓챠피디아 코멘트 (메인 데이터)
│   ├── cgv_review_crawler.py         #   CGV 실관람평
│   ├── rogerebert_crawler.py         #   rogerebert.com 영어 리뷰
│   ├── boxoffice_crawler.py          #   KOBIS 박스오피스 API
│   ├── preprocess.py                 #   왓챠 코멘트 정제
│   ├── _env.py / .env.example        #   비밀값(.env) 로더 · 예시
│   └── README.md                     #   크롤러 사용법
├── data/
│   ├── watcha_comments_clean.csv     # 왓챠 코멘트 데이터 (크롤러로 생성, .gitignore)
│   ├── SentiWord_info.json           # KNU 한국어 감성사전 (자동 라벨링용)
│   └── watcha_labeled.csv            # 자동 라벨링된 학습 데이터 (생성됨)
├── model/                            # 학습된 감성분석 모델 (train 후 생성)
│   ├── sa_model_movie.keras          #   LSTM 모델
│   ├── sa_tokenizer_movie.pkl        #   정수 인코딩 Tokenizer
│   └── sa_meta.pkl                   #   max_len · labels 메타
├── mylib/                            # 사용자 정의 패키지
│   ├── __init__.py
│   ├── myTextAnalyzer.py             # 코멘트 로드 · 형태소 분석 · 빈도 계산
│   ├── mySentimentAnalyzer.py        # LSTM 모델 기반 긍정/부정 분석 클래스
│   ├── myRecommender.py              # 코멘트 TF-IDF 유사도 기반 영화 추천
│   ├── myStreamlitVisualizer.py      # 워드클라우드 · 막대그래프 · 감성 차트
│   └── my_utils.py                   # 모델 학습용 보조 함수
├── make_watcha_labeled.py            # 왓챠 코멘트 자동 라벨링 (KNU 감성사전)
├── train_sentiment_model.py          # 감성분석 LSTM 모델 학습 스크립트
├── build_recommender.py             # 영화 추천 모델(유사도 행렬) 빌드 스크립트
├── WordFreqWebDashboard.py           # 메인 Streamlit 앱
├── requirements.txt
└── README.md
```

## 🛠️ 개발 환경

- 데이터 분석: numpy, pandas, matplotlib
- 한글 처리: konlpy (Okt) — **Java(JDK) 필요**
- 워드클라우드: wordcloud
- 딥러닝(감성분석): tensorflow(keras), scikit-learn, joblib
- 웹 대시보드: streamlit

## ▶️ 실행 방법

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# (선택) 0. 데이터 직접 수집 — data/ 가 비어 있다면 크롤러로 생성
#    자세한 사용법은 crawler/README.md 참고
cd crawler
cp .env.example .env             # 로그인/ API 키 입력
py watcha_comment_crawler.py     # 왓챠 코멘트 수집 → watcha_comments.csv
py preprocess.py                 # 정제 → watcha_comments_clean.csv 를 ../data/ 로 이동
cd ..

# 2. (감성분석용) 왓챠 코멘트 자동 라벨링 → LSTM 모델 학습 (최초 1회)
cd WordFreqProj
py make_watcha_labeled.py        # watcha_labeled.csv 생성 (~15분)
py train_sentiment_model.py      # model/ 에 학습 결과 저장

# 3. (추천용) 영화 추천 모델 빌드 (최초 1회)
py build_recommender.py          # model/recommender.pkl 생성 (~8분)

# 4. 대시보드 실행
py -m streamlit run WordFreqWebDashboard.py
```

브라우저에서 `http://localhost:8501` 자동 오픈.
(모델을 아직 학습하지 않았으면 감성분석 탭에 학습 안내가 표시되고, 단어 빈도 분석은 그대로 동작합니다.)

## ✨ 주요 기능

- **분석 기준 선택**: 영화별 / 연도별 / 전체
- **분석 옵션**: 샘플 코멘트 수, 표시 단어 개수, 최소 단어 길이, 추가 불용어
- **탭1 · 단어 빈도 분석**
  - 요약 지표(`st.metric`), 워드클라우드 + 가로 막대그래프
  - 단어 빈도 표 및 CSV 다운로드, 코멘트 미리보기
- **탭2 · 감성 분석** (순환신경망 LSTM, **왓챠 코멘트로 학습**)
  - 선택한 영화/연도 코멘트를 긍정/부정으로 분류 → 감성 분포 도넛 차트
  - **긍정 그룹 / 부정 그룹 각각** 특징어 워드클라우드 + 빈도 그래프 + 대표 코멘트
- **탭3 · 비슷한 영화 추천** (콘텐츠 기반)
  - 영화별 코멘트를 TF-IDF 벡터화 → 코사인 유사도로 분위기가 비슷한 영화 추천
  - 코멘트 단어만으로 감독·시리즈·스튜디오 관계를 잡아냄
    (예: 기생충→봉준호 작품, 인터스텔라→놀란 작품, 어벤져스→마블 시리즈)
- `@st.cache_data` / `@st.cache_resource`로 데이터·모델·분석 결과 캐싱

## 🤖 감성분석 모델

강의 노트북 『09. 순환신경망 기반 감성분석』 구조를 따르되,
**학습 데이터는 네이버 리뷰가 아니라 직접 크롤링한 왓챠 코멘트**를 사용합니다.

### 1단계 — 자동 라벨링 (make_watcha_labeled.py)
왓챠 데이터에는 별점이 없으므로 **KNU 한국어 감성사전**으로 라벨을 만든다.
- 코멘트 30만 건 샘플 → Okt 형태소 분석 → 감성어 극성 점수 합산
- 점수 ≥ +2 → 긍정 / ≤ −3 → 부정 / 그 사이 → 제외
- 긍정/부정 클래스 균형(downsample) 후 `watcha_labeled.csv` 저장
  (예: 긍정 31,785 / 부정 31,785)

### 2단계 — LSTM 학습 (train_sentiment_model.py)
1. 데이터 준비 — 결측/중복 제거, 한글만 정제, Okt 토큰화
2. 정수 인코딩(vocab 40,000) · 패딩(max_len=50) · 라벨 원핫
3. 모델: `Embedding(32) → LSTM(64) → Dense(16, tanh) → Dense(2, softmax)`
4. 학습: RMSprop, binary_crossentropy, EarlyStopping + ModelCheckpoint
5. 평가: `classification_report`
6. 저장: `.keras` 모델 + `tokenizer.pkl` + 메타 → 대시보드에서 재사용

> ⚠️ **정확도 해석 주의 (중요)**
> - 평가 정확도(~90%)는 *사전이 만든 자동 라벨* 기준이라 "모델이 감성사전과 얼마나
>   일치하는가"에 가깝다. 사람 기준 실제 정확도는 이보다 낮다.
> - **알려진 한계**: 영화 리뷰에 흔한 주제어(상실·후회·가난·계급·감정 등)를 감성사전이
>   '부정'으로 처리하므로, 슬프거나 진지한 내용을 호평한 글이 부정으로 오분류되는 경향이 있다.
>   (예: 인터스텔라 호평 코멘트 일부가 부정으로 분류됨)
> - 짧고 명확한 문장("시간이 아까움", "최고의 명작")은 비교적 잘 맞는다.
> - **근본 해결책**: 코멘트별 실제 별점으로 라벨을 만들면 된다(NSMC가 네이버 별점으로
>   만든 방식과 동일). 왓챠 API는 별점을 제공하므로 `watcha_session.pkl` + `visited_urls.txt`로
>   재수집이 가능하다(현재 프로젝트에서는 수행하지 않음).
