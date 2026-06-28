"""
add_sentiment_profile.py
─────────────────────────────────────────────────────────────
기존 추천 모델(model/recommender.pkl)에 '영화별 호평률(pos_ratio)'을 추가한다.

- 토픽 유사도(코멘트 TF-IDF)는 그대로 두고,
- 각 영화의 코멘트를 LSTM 감성모델(왓챠 코멘트로 학습)로 분류해 긍정 비율을 계산.
- 추천기는 이 호평률을 '관객 반응(호불호) 유사도'로 함께 사용한다.

build_recommender.py 의 sentiment 단계와 동일 로직이며, 토픽 부분을 재계산하지
않으려고 분리해 둔 보조 스크립트다.  실행:  py add_sentiment_profile.py
"""
import os, sys, io, time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import joblib
from mylib import myTextAnalyzer as ta
from mylib.mySentimentAnalyzer import SentimentAnalyzer, model_exists

BASE = os.path.dirname(os.path.abspath(__file__))
PKL = os.path.join(BASE, "model", "recommender.pkl")

SENTI_PER_MOVIE = 150   # 영화당 감성 판정에 쓸 코멘트 표본 수


def main():
    if not os.path.exists(PKL):
        raise SystemExit("recommender.pkl 이 없습니다. 먼저 build_recommender.py 를 실행하세요.")
    if not model_exists():
        raise SystemExit("감성 모델이 없습니다. 먼저 train_sentiment_model.py 를 실행하세요.")

    data = joblib.load(PKL)
    movies = data["movies"]
    print(f"[1] 추천 모델 로드: 영화 {len(movies)}편")

    df = ta.load_data()
    print(f"[2] 코멘트 로드: {len(df):,}개")

    print("[3] 감성 모델 로딩 중... (tensorflow/konlpy, 30~60초)")
    t = time.time()
    sa = SentimentAnalyzer()
    print(f"    로딩 완료 ({time.time()-t:.0f}s)")

    pos_ratio = []
    for i, movie in enumerate(movies, 1):
        sub = df[df["movie_title"] == movie]
        if len(sub) > SENTI_PER_MOVIE:
            sub = sub.sample(n=SENTI_PER_MOVIE, random_state=42)
        texts = sub["comment"].tolist()
        results = sa.analyze_many(texts)
        n_pos = sum(1 for label, _ in results if label == "긍정")
        ratio = n_pos / len(results) if results else 0.5
        pos_ratio.append(ratio)
        if i % 20 == 0 or i == len(movies):
            print(f"    {i}/{len(movies)}편  (최근: {movie[:18]} 호평률 {ratio:.0%})", flush=True)

    data["pos_ratio"] = pos_ratio
    data["senti_per_movie"] = SENTI_PER_MOVIE
    joblib.dump(data, PKL)

    import numpy as np
    arr = np.array(pos_ratio)
    print(f"\n[4] 저장 완료 → {PKL}")
    print(f"    호평률 평균 {arr.mean():.0%} · 최저 {arr.min():.0%} · 최고 {arr.max():.0%}")


if __name__ == "__main__":
    main()
