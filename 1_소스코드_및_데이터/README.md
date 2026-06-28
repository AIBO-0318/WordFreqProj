# ① 소스코드 + 데이터

전체 파이프라인(**수집 → 준비 → 학습 → 서비스**)의 소스코드와 학습 데이터입니다.
여기 코드만으로 데이터 수집부터 모델 학습, 서비스 실행까지 **처음부터 재현**할 수 있습니다.

## 단계별 구성

| 단계 | 파일 | 설명 |
|---|---|---|
| 수집 | `crawler/` | 왓챠·CGV·로저이버트·박스오피스 크롤러 (자세히는 `crawler/README.md`) |
| 준비 | `crawler/preprocess.py` | 코멘트 정제(중복·길이·노이즈 제거) |
| 준비 | `make_watcha_labeled.py` | KNU 한국어 감성사전으로 코멘트 자동 라벨링 |
| 학습 | `train_sentiment_model.py` | LSTM 감성분석 모델 학습 |
| 학습 | `build_recommender.py` | 추천 모델(코멘트 TF-IDF + 호평률) 빌드 |
| 서비스 | `WordFreqWebDashboard.py` | Streamlit 대시보드 |
| 공통 | `mylib/` | 텍스트분석·감성·추천·시각화 모듈 |

## 데이터 (`data/`, Git LFS)

| 파일 | 내용 |
|---|---|
| `watcha_comments_clean.csv` | 정제된 왓챠 코멘트 (약 150만 건 / 309편) — 분석 대상 |
| `watcha_labeled.csv` | 자동 라벨링된 감성 학습 데이터 |
| `SentiWord_info.json` | KNU 한국어 감성사전 |

## 처음부터 재현하기

```bash
pip install -r requirements.txt

# (선택) 1. 데이터 직접 수집 — crawler/README.md 참고
cd crawler && cp .env.example .env   # 로그인/API키 입력
py watcha_comment_crawler.py && py preprocess.py && cd ..

# 2. 감성분석: 자동 라벨링 → LSTM 학습
py make_watcha_labeled.py
py train_sentiment_model.py

# 3. 추천 모델 빌드 (코멘트 TF-IDF + 호평률)
py build_recommender.py

# 4. 서비스 실행
py -m streamlit run WordFreqWebDashboard.py
```

## 감성분석 모델 (요약)

강의 노트북 『09. 순환신경망 기반 감성분석』 구조를 따르되,
**학습 데이터는 네이버 리뷰가 아니라 직접 크롤링한 왓챠 코멘트**를 사용합니다.

- 자동 라벨링: 코멘트를 KNU 감성사전으로 극성 점수화 → 긍/부정 분리(균형 샘플링)
- 모델: `Embedding(32) → LSTM(64) → Dense(16) → Dense(2, softmax)`
- ⚠️ 평가 정확도(~90%)는 *자동 라벨* 기준이라 사람 기준 실제 정확도는 더 낮음.
  영화 리뷰 특유의 주제어(상실·가난 등)를 부정으로 오인하는 한계가 있음.
  근본 해결책은 코멘트별 실제 별점 라벨이나, 본 프로젝트에서는 수행하지 않음.
