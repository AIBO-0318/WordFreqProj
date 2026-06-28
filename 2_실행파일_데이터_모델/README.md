# ② 실행 파일 + 데이터 + 모델

**재학습 없이 바로 실행**할 수 있는 패키지입니다.
학습이 끝난 모델(`model/`)과 실행에 필요한 데이터(`data/`)가 포함되어 있습니다.

## 구성
```
2_실행파일_데이터_모델/
├── run.bat                      # Windows 더블클릭 실행
├── WordFreqWebDashboard.py      # 서비스 앱 (Streamlit)
├── mylib/                       # 실행에 필요한 공통 모듈
├── requirements.txt
├── model/   (Git LFS)           # 학습 완료된 모델
│   ├── sa_model_movie.keras     #   LSTM 감성분석
│   ├── sa_tokenizer_movie.pkl   #   토크나이저
│   ├── sa_meta.pkl              #   메타정보
│   └── recommender.pkl          #   추천(TF-IDF + 호평률)
└── data/    (Git LFS)
    └── watcha_comments_clean.csv  # 서비스가 사용하는 코멘트 데이터
```

## 실행 방법

> **사전 준비**: Python 3.10+, Java(JDK) 설치(KoNLPy용), 그리고 `git lfs pull`로 대용량 파일을 받아둘 것.

**방법 A — 스크립트**
```
run.bat   (더블클릭)
```

**방법 B — 직접 실행**
```bash
pip install -r requirements.txt
py -m streamlit run WordFreqWebDashboard.py
```
브라우저에서 `http://localhost:8501` 자동 오픈.

## 기능 (탭)
1. **단어 빈도 분석** — 워드클라우드 · 막대그래프 · CSV 다운로드
2. **감성 분석** — LSTM(왓챠 코멘트 학습)으로 긍/부정 분류, 분포·특징어
3. **비슷한 영화 추천** — 코멘트 TF-IDF(분위기) + 호평률(감성) 결합, 가중치 슬라이더
