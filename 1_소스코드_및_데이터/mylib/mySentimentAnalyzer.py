"""
mySentimentAnalyzer.py
─────────────────────────────────────────────────────────────
감성 분석 모듈 — 순환신경망(LSTM) 모델 기반

강의 노트북 『09_순환신경망기반감성분석』의 SentimentAnalyzer 클래스 구조를 따른다.
  - 객체 생성 시 학습된 모델(.keras) · Tokenizer(.pkl) · 메타정보 로딩
  - 한국어 형태소 분석기(Okt)로 토큰화
  - 입력 리뷰의 긍/부정 판단

모델 학습은 train_sentiment_model.py 로 먼저 수행해야 한다.
무거운 의존성(tensorflow, konlpy)은 실제 사용 시점에 지연 임포트한다.
"""

import os

import numpy as np

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_FILE = os.path.join(_BASE_DIR, "model", "sa_model_movie.keras")
TOKENIZER_FILE = os.path.join(_BASE_DIR, "model", "sa_tokenizer_movie.pkl")
META_FILE = os.path.join(_BASE_DIR, "model", "sa_meta.pkl")

# 부정 판정 임계값 (>0.5)
#   모델이 긴 영화 코멘트를 부정 쪽으로 다소 과하게 분류하는 경향이 있어,
#   부정 확률이 이 값 이상일 때만 '부정'으로 판정해 과도한 부정 분류를 보정한다.
NEG_THRESHOLD = 0.6


def model_exists() -> bool:
    """학습된 모델·토크나이저가 모두 준비되었는지 확인."""
    return all(os.path.exists(p) for p in (MODEL_FILE, TOKENIZER_FILE, TOKENIZER_FILE))


class SentimentAnalyzer:
    """학습된 LSTM 모델로 한국어 리뷰의 긍/부정을 예측한다."""

    def __init__(
        self,
        model_file: str = MODEL_FILE,
        tokenizer_file: str = TOKENIZER_FILE,
        meta_file: str = META_FILE,
    ):
        # 지연 임포트 (tensorflow/konlpy는 무겁다)
        from tensorflow.keras.models import load_model
        import joblib
        from konlpy.tag import Okt

        self.model = load_model(model_file)
        self.tokenizer = joblib.load(tokenizer_file)

        if os.path.exists(meta_file):
            meta = joblib.load(meta_file)
            self.max_len = meta.get("max_len", 50)
            self.labels = meta.get("labels", ["부정", "긍정"])
        else:
            self.max_len = 50
            self.labels = ["부정", "긍정"]

        self.morphs = Okt().morphs
        self.neg_threshold = NEG_THRESHOLD
        self._neg_idx = self.labels.index("부정")
        self._pos_idx = self.labels.index("긍정")

    # ── 내부: 텍스트 → 패딩된 정수 시퀀스 ─────────────────────
    def _encode(self, texts: list[str]):
        from tensorflow.keras.preprocessing.sequence import pad_sequences

        tokenized = [self.morphs(str(t)) for t in texts]
        seqs = self.tokenizer.texts_to_sequences(tokenized)
        return pad_sequences(seqs, maxlen=self.max_len)

    def _classify(self, prob_row) -> tuple[str, float]:
        """확률 벡터 → (레이블, 확신도). 부정 임계값을 적용한다."""
        p_neg = float(prob_row[self._neg_idx])
        if p_neg >= self.neg_threshold:
            return "부정", p_neg
        return "긍정", float(prob_row[self._pos_idx])

    # ── 단일 리뷰 예측 (노트북과 동일 인터페이스) ──────────────
    def analyze_sentiment(self, text: str) -> tuple[str, float]:
        """리뷰 1건의 (레이블, 확률)을 반환한다."""
        X = self._encode([text])
        preds = self.model.predict(X, verbose=0)
        return self._classify(preds[0])

    # ── 여러 리뷰 일괄 예측 (대시보드 집계용) ─────────────────
    def analyze_many(self, texts: list[str]) -> list[tuple[str, float]]:
        """여러 리뷰를 한 번에 예측한다. [(레이블, 확률), ...]"""
        if not texts:
            return []
        X = self._encode(texts)
        preds = self.model.predict(X, verbose=0, batch_size=256)
        return [self._classify(p) for p in preds]


def aggregate(texts: list[str], analyzer: "SentimentAnalyzer") -> dict:
    """여러 코멘트의 감성 분포를 집계한다 (대시보드용).

    반환 dict:
      - counts       : {'긍정': n, '부정': n}
      - ratios       : 비율(%)
      - n            : 분석 코멘트 수
      - pos_ratio    : 긍정 비율(%)
      - avg_conf     : 평균 예측 확신도(%)
      - examples_pos : 확신도 높은 긍정 코멘트
      - examples_neg : 확신도 높은 부정 코멘트
    """
    results = analyzer.analyze_many(texts)

    counts = {"긍정": 0, "부정": 0}
    pos_items, neg_items = [], []
    conf_sum = 0.0

    for text, (label, prob) in zip(texts, results):
        counts[label] = counts.get(label, 0) + 1
        conf_sum += prob
        if label == "긍정":
            pos_items.append((text, prob))
        else:
            neg_items.append((text, prob))

    n = len(texts)
    ratios = {k: (v / n * 100 if n else 0) for k, v in counts.items()}
    pos_ratio = ratios.get("긍정", 0)

    pos_items.sort(key=lambda x: x[1], reverse=True)
    neg_items.sort(key=lambda x: x[1], reverse=True)

    return {
        "counts": counts,
        "ratios": ratios,
        "n": n,
        "pos_ratio": pos_ratio,
        "avg_conf": (conf_sum / n * 100) if n else 0,
        "examples_pos": [t for t, _ in pos_items[:5]],
        "examples_neg": [t for t, _ in neg_items[:5]],
        # 긍정/부정으로 나뉜 코멘트 전체 목록 (각 그룹별 단어 빈도 분석용)
        "pos_comments": [t for t, _ in pos_items],
        "neg_comments": [t for t, _ in neg_items],
    }
