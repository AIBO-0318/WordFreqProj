# 🎬 왓챠피디아 코멘트 기반 영화 분석 · 추천 서비스

왓챠피디아에서 직접 크롤링한 영화 코멘트(약 150만 건 / 309편)를 활용해
**단어 빈도 분석 · 감성 분석(LSTM) · 비슷한 영화 추천**을 제공하는 Streamlit 웹 대시보드입니다.

> 파이프라인: **수집(크롤링) → 준비(전처리·라벨링) → 학습(LSTM·추천) → 서비스(대시보드)**

---

## 📁 제출 폴더 구조

제출 요건(① 소스코드+데이터 / ② 실행파일+데이터+모델 / ③ 문서)에 맞춰 3개 폴더로 구성했습니다.

```
WordFreqProj/
├── 1_소스코드_및_데이터/        # ① 소스코드 + 학습 데이터
│   ├── crawler/                  #   수집: 왓챠·CGV·로저이버트·박스오피스 크롤러
│   ├── mylib/                    #   공통 모듈(텍스트분석·감성·추천·시각화)
│   ├── make_watcha_labeled.py    #   준비: KNU 감성사전 자동 라벨링
│   ├── train_sentiment_model.py  #   학습: LSTM 감성분석
│   ├── build_recommender.py      #   학습: 추천(코멘트 TF-IDF + 호평률)
│   ├── WordFreqWebDashboard.py   #   서비스: Streamlit 앱
│   ├── requirements.txt
│   └── data/                     #   학습 데이터 (Git LFS)
│
├── 2_실행파일_데이터_모델/       # ② 바로 실행 가능한 패키지 (재학습 불필요)
│   ├── run.bat                   #   더블클릭 실행
│   ├── WordFreqWebDashboard.py   #   서비스 앱
│   ├── mylib/
│   ├── model/                    #   학습 완료된 모델 (Git LFS)
│   └── data/                     #   실행에 필요한 데이터 (Git LFS)
│
└── 3_문서/                       # ③ 문서
    ├── 발표자료/  watcha_presentation.pptx · 학습곡선.png
    ├── 시연영상/  시연영상.mp4
    └── Technical_Report/  Technical_Report.md
```

---

## ⬇️ 받는 법 (Git LFS 필수)

대용량 파일(데이터 260MB·모델·시연영상)은 **Git LFS**로 관리합니다.
먼저 LFS를 설치해야 정상적으로 받아집니다.

```bash
git lfs install
git clone https://github.com/AIBO-0318/WordFreqProj.git
```

이미 clone 한 뒤 LFS를 깔았다면: `git lfs pull`

---

## ▶️ 빠른 실행 (재학습 없이)

```bash
cd 2_실행파일_데이터_모델
pip install -r requirements.txt
py -m streamlit run WordFreqWebDashboard.py
#  Windows 에서는 run.bat 더블클릭으로도 실행
```

처음부터 재현(수집→학습)하려면 `1_소스코드_및_데이터/` 의 안내를 참고하세요.

## 🛠️ 개발 환경
- 한글 형태소: KoNLPy(Okt) — **Java(JDK) 필요**
- 딥러닝: tensorflow(keras) · 추천: scikit-learn · 웹: streamlit
- 크롤링: selenium · beautifulsoup4 · requests
