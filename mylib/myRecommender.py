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
        self._index = {m: i for i, m in enumerate(self.movies)}

    def movie_list(self) -> list[str]:
        return list(self.movies)

    def recommend(
        self, movie: str, top_n: int = 5, min_sim: float = 0.15
    ) -> list[tuple[str, float]]:
        """주어진 영화와 유사도가 높은 영화 top_n개를 반환한다.

        - min_sim 미만의 약한(억지) 추천은 제외한다.
        반환: [(영화제목, 유사도0~1), ...]  (자기 자신 제외)
        """
        if movie not in self._index:
            return []
        idx = self._index[movie]
        scores = list(enumerate(self.sim[idx]))
        scores.sort(key=lambda x: x[1], reverse=True)
        result = []
        for j, s in scores:
            if j == idx:                 # 자기 자신 제외
                continue
            if s < min_sim:              # 약한 추천은 잘라냄
                break
            result.append((self.movies[j], float(s)))
            if len(result) >= top_n:
                break
        return result

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
