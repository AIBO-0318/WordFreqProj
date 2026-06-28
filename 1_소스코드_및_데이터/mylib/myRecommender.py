"""
myRecommender.py
─────────────────────────────────────────────────────────────
영화 추천 모듈 (콘텐츠 기반)

build_recommender.py 가 미리 만든 유사도 행렬(recommender.pkl)을 불러와,
선택한 영화와 코멘트가 가장 비슷한 영화를 추천한다.
"""

import os

_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_FILE = os.path.join(_BASE_DIR, "model", "recommender.pkl")


def model_exists() -> bool:
    return os.path.exists(MODEL_FILE)


class MovieRecommender:
    """코멘트 TF-IDF 코사인 유사도 기반 영화 추천기."""

    def __init__(self, model_file: str = MODEL_FILE):
        import joblib

        data = joblib.load(model_file)
        self.movies = data["movies"]                 # 영화 제목 리스트
        self.sim = data["sim"]                        # 유사도 행렬 (N x N)
        self.top_terms = data.get("top_terms", {})    # 영화별 대표 키워드
        self.tfidf = data.get("tfidf")                # 영화×단어 TF-IDF
        self.terms = data.get("terms")                # 단어 목록
        self.pos_ratio = data.get("pos_ratio")        # 영화별 호평률(0~1) — 감성모델 결과
        self._index = {m: i for i, m in enumerate(self.movies)}

    def movie_list(self) -> list[str]:
        return list(self.movies)

    def has_sentiment(self) -> bool:
        """호평률(감성) 정보가 모델에 포함되어 있는지."""
        return self.pos_ratio is not None

    def reception(self, movie: str) -> float | None:
        """영화의 관객 호평률(0~1). 감성 정보가 없으면 None."""
        if self.pos_ratio is None or movie not in self._index:
            return None
        return float(self.pos_ratio[self._index[movie]])

    def recommend(
        self, movie: str, top_n: int = 5, min_sim: float = 0.12, alpha: float = 0.7
    ) -> list[dict]:
        """주어진 영화와 비슷한 영화 top_n개를 반환한다.

        두 가지 신호를 결합한다 (둘 다 크롤링한 코멘트에서 나옴):
          - topic : 코멘트 단어(TF-IDF) 유사도 — '분위기·소재가 비슷한가'
          - recep : 호평률(LSTM 감성) 유사도 — '관객 호불호 반응이 비슷한가'
        최종점수 = alpha·topic + (1-alpha)·recep   (alpha=토픽 가중치)

        - min_sim 미만으로 topic 유사도가 약한 영화는 후보에서 제외(엉뚱한 추천 방지).
        - 감성 정보가 없는 모델이면 topic 만으로 동작(하위 호환).
        반환: [{title, score, topic, recep, pos_ratio}, ...]  (자기 자신 제외, score 내림차순)
        """
        if movie not in self._index:
            return []
        idx = self._index[movie]
        have_senti = self.pos_ratio is not None

        scored = []
        for j in range(len(self.movies)):
            if j == idx:
                continue
            topic = float(self.sim[idx][j])
            if topic < min_sim:                  # 토픽이 약하면 후보 제외
                continue
            if have_senti:
                recep = 1.0 - abs(self.pos_ratio[idx] - self.pos_ratio[j])
                score = alpha * topic + (1 - alpha) * recep
                pr = float(self.pos_ratio[j])
            else:
                recep, score, pr = None, topic, None
            scored.append({
                "title": self.movies[j], "score": score,
                "topic": topic, "recep": recep, "pos_ratio": pr,
            })

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_n]

    def keywords(self, movie: str) -> list[str]:
        """영화의 대표 키워드(추천 근거)."""
        return self.top_terms.get(movie, [])

    def common_terms(self, movie_a: str, movie_b: str, top_n: int = 6) -> list[str]:
        """두 영화가 '왜 비슷한지' — 유사도에 가장 크게 기여한 공통 단어.

        두 영화의 TF-IDF 벡터를 원소별로 곱해, 양쪽에서 모두 두드러진 단어를 뽑는다.
        """
        if self.tfidf is None or movie_a not in self._index or movie_b not in self._index:
            # TF-IDF가 없으면 대표 키워드 교집합으로 대체
            return [w for w in self.top_terms.get(movie_a, [])
                    if w in self.top_terms.get(movie_b, [])][:top_n]
        ia, ib = self._index[movie_a], self._index[movie_b]
        va = self.tfidf[ia].toarray().ravel()
        vb = self.tfidf[ib].toarray().ravel()
        contrib = va * vb                       # 공통 기여도
        order = contrib.argsort()[::-1][:top_n]
        return [self.terms[j] for j in order if contrib[j] > 0]
