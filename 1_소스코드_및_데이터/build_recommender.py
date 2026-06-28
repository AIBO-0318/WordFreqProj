"""
build_recommender.py
─────────────────────────────────────────────────────────────
영화 추천(콘텐츠 기반) 모델 미리 계산 스크립트

방식
  1. 영화별로 코멘트를 모아 명사를 추출 → 영화 1편 = 문서 1개
  2. TF-IDF 벡터화 (영화 × 단어)
  3. 코사인 유사도로 영화 간 유사도 행렬 생성
  4. 결과를 model/recommender.pkl 로 저장 → 대시보드에서 재사용

'코멘트에서 비슷한 단어가 자주 나오는 영화'를 비슷한 영화로 본다.

실행:  py build_recommender.py
"""

import os
import sys
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import joblib
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from mylib import myTextAnalyzer as ta

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_FILE = os.path.join(BASE, "model", "recommender.pkl")

PER_MOVIE = 500     # 영화당 사용할 코멘트 수(샘플) — 속도/대표성 균형
MIN_COMMENTS = 50   # 코멘트가 너무 적은 영화는 제외
TOP_TERMS = 8       # 영화별 대표 키워드 저장 개수
SENTI_PER_MOVIE = 150   # 영화별 호평률 계산에 쓸 코멘트 표본 수


def compute_pos_ratio(df, movies):
    """각 영화 코멘트를 LSTM 감성모델로 분류해 호평률(0~1) 리스트를 만든다.

    감성모델이 없으면 None을 반환(추천기는 토픽 유사도만으로 동작).
    """
    from mylib.mySentimentAnalyzer import SentimentAnalyzer, model_exists
    if not model_exists():
        print("    (감성 모델 없음 → 호평률 생략, 토픽 유사도만 사용)")
        return None
    print("    감성 모델 로딩 중... (tensorflow/konlpy)")
    sa = SentimentAnalyzer()
    ratios = []
    for k, movie in enumerate(movies, 1):
        sub = df[df["movie_title"] == movie]
        if len(sub) > SENTI_PER_MOVIE:
            sub = sub.sample(n=SENTI_PER_MOVIE, random_state=42)
        results = sa.analyze_many(sub["comment"].tolist())
        n_pos = sum(1 for label, _ in results if label == "긍정")
        ratios.append(n_pos / len(results) if results else 0.5)
        if k % 50 == 0:
            print(f"    호평률 {k}/{len(movies)}편...", flush=True)
    return ratios


def main():
    print("=" * 55)
    print("영화 추천 모델 빌드 (코멘트 TF-IDF + 코사인 유사도)")
    print("=" * 55)

    df = ta.load_data()
    print(f"[1] 코멘트 로드: {len(df):,}개 / 영화 {df['movie_title'].nunique()}편")

    # ── 영화별 명사 문서 만들기 ─────────────────────────────
    movies, docs = [], []
    vc = df["movie_title"].value_counts()
    targets = [m for m, c in vc.items() if c >= MIN_COMMENTS]
    print(f"[2] 대상 영화: {len(targets)}편 (코멘트 {MIN_COMMENTS}개 이상)")

    for i, movie in enumerate(targets, 1):
        sub = df[df["movie_title"] == movie]
        if len(sub) > PER_MOVIE:
            sub = sub.sample(n=PER_MOVIE, random_state=42)
        nouns = ta.extract_nouns(sub["comment"].tolist())
        if not nouns:
            continue
        movies.append(movie)
        docs.append(" ".join(nouns))
        if i % 50 == 0:
            print(f"    {i}/{len(targets)}편 처리...", flush=True)

    print(f"[3] 문서 {len(movies)}편 → TF-IDF 벡터화")
    vectorizer = TfidfVectorizer(max_features=20000, min_df=2)
    tfidf = vectorizer.fit_transform(docs)

    print("[4] 코사인 유사도 행렬 계산")
    sim = cosine_similarity(tfidf)

    # 영화별 대표 키워드(TF-IDF 상위) — 추천 근거 표시용
    terms = vectorizer.get_feature_names_out()
    top_terms = {}
    for idx, movie in enumerate(movies):
        row = tfidf[idx].toarray().ravel()
        top_idx = row.argsort()[::-1][:TOP_TERMS]
        top_terms[movie] = [terms[j] for j in top_idx if row[j] > 0]

    print("[5] 영화별 호평률(LSTM 감성) 계산 — 관객 반응 유사도용")
    pos_ratio = compute_pos_ratio(df, movies)

    joblib.dump(
        {
            "movies": movies, "sim": sim, "top_terms": top_terms,
            "tfidf": tfidf,                      # 영화×단어 TF-IDF (공통점 계산용)
            "terms": terms,                      # 단어 목록
            "pos_ratio": pos_ratio,              # 영화별 호평률(0~1) — 관객 반응 유사도용
            "senti_per_movie": SENTI_PER_MOVIE,
        },
        OUT_FILE,
    )
    print(f"[6] 저장 완료: {OUT_FILE} (영화 {len(movies)}편)")


if __name__ == "__main__":
    main()
