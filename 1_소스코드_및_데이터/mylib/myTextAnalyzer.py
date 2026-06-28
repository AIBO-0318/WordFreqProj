"""
myTextAnalyzer.py
─────────────────────────────────────────────────────────────
텍스트 분석 모듈 (왓챠피디아 코멘트)

기능
  - CSV 코멘트 데이터 로드
  - 영화별 / 연도별 코멘트 필터링
  - 한글 형태소 분석(명사 추출, KoNLPy Okt)
  - 불용어 제거 후 단어 빈도수 계산
"""

import os
import re
from collections import Counter

import pandas as pd

# ──────────────────────────────────────────────────────────
# 경로 설정 : 이 모듈(mylib) 기준 ../data/ 안의 CSV
# ──────────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PATH = os.path.join(_BASE_DIR, "data", "watcha_comments_clean.csv")

# ──────────────────────────────────────────────────────────
# 기본 불용어 (영화 코멘트에서 빈도는 높지만 의미가 약한 단어들)
# ──────────────────────────────────────────────────────────
DEFAULT_STOPWORDS = {
    "영화", "정말", "진짜", "그냥", "너무", "내가", "나는", "내", "이건", "저건",
    "그", "이", "저", "것", "수", "때", "거", "더", "좀", "잘", "또", "왜",
    "걍", "근데", "그리고", "하지만", "그래서", "그런", "이런", "저런", "우리",
    "보고", "보면", "본", "봤다", "봤음", "봤는데", "있는", "없는", "같은",
    "있다", "없다", "하는", "한다", "되는", "느낌", "생각", "사람", "정도",
}

# 감성 워드클라우드용 추가 불용어 — 평가가 아닌 '영화 일반 주제어'
# (긍/부정 어느 쪽도 아닌 단어라 감성 특징어에서 빼는 게 자연스럽다)
FILM_STOPWORDS = {
    "영화", "감독", "배우", "연기", "장면", "작품", "주인공", "캐릭터", "출연",
    "등장", "연출", "스토리", "내용", "관객", "평점", "별점", "시리즈", "개봉",
    "관람", "극장", "영화관", "장르", "주연", "조연", "제목", "예고편", "원작",
    "이야기", "부분", "처음", "마지막", "결말", "정도", "이번", "그것", "무엇",
}


# ──────────────────────────────────────────────────────────
# Okt 형태소 분석기 (지연 초기화 — JVM 부팅 비용 절약)
# ──────────────────────────────────────────────────────────
_okt = None


def _get_okt():
    """Okt 인스턴스를 한 번만 생성해서 재사용한다."""
    global _okt
    if _okt is None:
        from konlpy.tag import Okt
        _okt = Okt()
    return _okt


# ──────────────────────────────────────────────────────────
# 데이터 로드
# ──────────────────────────────────────────────────────────
def load_data(path: str = DATA_PATH) -> pd.DataFrame:
    """코멘트 CSV를 DataFrame으로 로드한다.

    컬럼: movie_title, comment, release_year
    """
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["comment"] = df["comment"].astype(str)
    # 연도 정수화 (결측/0 은 0으로)
    df["release_year"] = (
        pd.to_numeric(df["release_year"], errors="coerce").fillna(0).astype(int)
    )
    return df


def get_movie_list(df: pd.DataFrame, min_count: int = 1) -> list[str]:
    """코멘트가 min_count개 이상인 영화 제목 목록(코멘트 많은 순)."""
    vc = df["movie_title"].value_counts()
    vc = vc[vc >= min_count]
    return vc.index.tolist()


def get_year_list(df: pd.DataFrame) -> list[int]:
    """코멘트가 존재하는 개봉연도 목록(내림차순). 0(미상) 제외."""
    years = sorted([int(y) for y in df["release_year"].unique() if y > 0], reverse=True)
    return years


# ──────────────────────────────────────────────────────────
# 코멘트 필터링
# ──────────────────────────────────────────────────────────
def filter_comments(
    df: pd.DataFrame,
    movie: str | None = None,
    year: int | None = None,
) -> pd.DataFrame:
    """영화 제목 / 개봉연도로 코멘트를 필터링한다."""
    sub = df
    if movie:
        sub = sub[sub["movie_title"] == movie]
    if year:
        sub = sub[sub["release_year"] == year]
    return sub


# ──────────────────────────────────────────────────────────
# 텍스트 → 명사 토큰
# ──────────────────────────────────────────────────────────
def extract_nouns(
    texts: list[str],
    min_len: int = 2,
    stopwords: set[str] | None = None,
) -> list[str]:
    """코멘트 리스트에서 명사만 추출한다.

    - min_len  : 최소 글자 수 (기본 2 — 한 글자 명사 노이즈 제거)
    - stopwords: 제외할 단어 집합
    """
    if stopwords is None:
        stopwords = DEFAULT_STOPWORDS

    okt = _get_okt()

    # 코멘트들을 하나로 합쳐 한 번에 분석 (호출 비용 절감)
    joined = " ".join(texts)
    # 한글/영문/숫자/공백만 남기기
    joined = re.sub(r"[^가-힣a-zA-Z0-9\s]", " ", joined)

    nouns = okt.nouns(joined)
    result = [
        w for w in nouns
        if len(w) >= min_len and w not in stopwords
    ]
    return result


def count_frequency(words: list[str], top_n: int = 50) -> list[tuple[str, int]]:
    """단어 리스트의 빈도수를 세어 상위 top_n개를 반환한다."""
    counter = Counter(words)
    return counter.most_common(top_n)


def distinctive_frequency(
    pos_texts: list[str],
    neg_texts: list[str],
    top_n: int = 50,
    min_total: int = 4,
    min_len: int = 2,
    margin: float = 0.15,
    stopwords: set[str] | None = None,
) -> tuple[list[tuple[str, int]], list[tuple[str, int]]]:
    """긍정/부정 그룹 각각에 '특징적으로' 많이 쓰인 단어를 골라낸다.

    - 두 그룹의 단어 빈도를 그룹 크기로 정규화(rate)한 뒤,
      한쪽으로 뚜렷이 치우친 단어에만 가중치를 준다.
    - lean 이 중립 구간 [0.5-margin, 0.5+margin] 안인 단어(영화 제목·인물명 등
      양쪽에 고루 나오는 공통어)는 점수 0 → 어느 쪽 워드클라우드에도 안 나온다.

    반환: (긍정_특징어[(단어,점수)...], 부정_특징어[...])
    """
    cp = Counter(extract_nouns(pos_texts, min_len=min_len, stopwords=stopwords))
    cn = Counter(extract_nouns(neg_texts, min_len=min_len, stopwords=stopwords))
    total_p = sum(cp.values()) or 1
    total_n = sum(cn.values()) or 1

    high, low = 0.5 + margin, 0.5 - margin
    pos_scores, neg_scores = {}, {}
    for w in set(cp) | set(cn):
        a, b = cp.get(w, 0), cn.get(w, 0)
        if a + b < min_total:            # 너무 드문 단어는 제외(노이즈)
            continue
        pr, nr = a / total_p, b / total_n
        lean = pr / (pr + nr)            # 1=긍정전용, 0=부정전용, 0.5=공통
        # 중립 구간 밖에서만 가중 (구간 안은 공통어 → 0)
        pos_w = (lean - high) / (1 - high) if lean > high else 0.0
        neg_w = (low - lean) / low if lean < low else 0.0
        ps, ns = a * pos_w, b * neg_w
        if ps >= 1:
            pos_scores[w] = int(round(ps))
        if ns >= 1:
            neg_scores[w] = int(round(ns))

    fp = sorted(pos_scores.items(), key=lambda x: -x[1])[:top_n]
    fn = sorted(neg_scores.items(), key=lambda x: -x[1])[:top_n]
    return fp, fn


# ──────────────────────────────────────────────────────────
# 코멘트 샘플 추출 (빈도 분석 · 감성 분석 공용)
# ──────────────────────────────────────────────────────────
def get_sample(
    df: pd.DataFrame,
    movie: str | None = None,
    year: int | None = None,
    sample_size: int = 3000,
) -> tuple[list[str], int]:
    """필터링 후 무작위 샘플링한 코멘트 리스트와 전체 코멘트 수를 반환한다.

    random_state를 고정해 같은 조건이면 항상 같은 샘플을 쓴다
    (빈도 분석과 감성 분석이 동일한 코멘트를 대상으로 하도록).
    """
    sub = filter_comments(df, movie=movie, year=year)
    n_comments = len(sub)
    if n_comments > sample_size:
        sub = sub.sample(n=sample_size, random_state=42)
    return sub["comment"].tolist(), n_comments


# ──────────────────────────────────────────────────────────
# 통합 분석 함수 (단어 빈도)
# ──────────────────────────────────────────────────────────
def analyze(
    df: pd.DataFrame,
    movie: str | None = None,
    year: int | None = None,
    sample_size: int = 3000,
    min_len: int = 2,
    top_n: int = 50,
    extra_stopwords: set[str] | None = None,
) -> dict:
    """필터링 → 샘플링 → 명사 추출 → 빈도 계산을 한 번에 수행한다.

    반환 dict:
      - n_comments : 필터링된 전체 코멘트 수
      - n_analyzed : 실제 분석한(샘플링된) 코멘트 수
      - freq       : [(단어, 빈도), ...] 상위 top_n
      - sample_comments : 미리보기용 코멘트 일부
    """
    stopwords = set(DEFAULT_STOPWORDS)
    if extra_stopwords:
        stopwords |= extra_stopwords

    texts, n_comments = get_sample(df, movie=movie, year=year, sample_size=sample_size)
    nouns = extract_nouns(texts, min_len=min_len, stopwords=stopwords)
    freq = count_frequency(nouns, top_n=top_n)

    return {
        "n_comments": n_comments,
        "n_analyzed": len(texts),
        "n_words": len(nouns),
        "n_unique": len(set(nouns)),
        "freq": freq,
        "sample_comments": texts[:5],
    }
