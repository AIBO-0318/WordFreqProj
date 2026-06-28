"""
make_watcha_labeled.py
─────────────────────────────────────────────────────────────
왓챠 코멘트 → KNU 한국어 감성사전으로 자동 라벨링하여
감성분석 LSTM 학습용 데이터셋(watcha_labeled.csv)을 생성한다.

라벨링 방식 (비지도, 사전 기반)
  - 코멘트를 Okt로 형태소 분석(어간)
  - 각 형태소의 KNU 극성 점수(-2~+2) 합산
  - 합산 점수 >= +POS_TH : 긍정(1)
              <= -NEG_TH : 부정(0)
              그 사이      : 애매 → 학습에서 제외
  - 긍정/부정 클래스 수를 맞춰(balance) 저장

※ 별점이 없는 데이터의 한계를 보완하는 자동 라벨이라 라벨에 노이즈가 있다.
"""

import os
import re
import sys
import io
import json
from collections import Counter

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import pandas as pd
from konlpy.tag import Okt

BASE = os.path.dirname(os.path.abspath(__file__))
WATCHA_CSV = os.path.join(BASE, "data", "watcha_comments_clean.csv")
DICT_PATH = os.path.join(BASE, "data", "SentiWord_info.json")
OUT_CSV = os.path.join(BASE, "data", "watcha_labeled.csv")

SAMPLE_SIZE = 600_000   # 라벨링 대상 샘플 (전체 150만 중)
POS_TH = 2              # 긍정 판정 임계 점수 (긍정은 풍부 → 높게 잡아 정밀도↑)
NEG_TH = 1              # 부정 판정 임계 점수(절댓값) (부정은 희소 → 낮게 잡아 재현율↑)
MAX_CHARS = 300         # 너무 긴 코멘트는 앞부분만 (속도/노이즈)

# 점수화할 내용어 품사 (조사·어미 등은 제외 → "이/가" 같은 노이즈 차단)
CONTENT_POS = {"Noun", "Verb", "Adjective", "Adverb"}
# 부정어 (앞 감성어의 극성을 뒤집음)
NEG_WORDS = {"없다", "않다", "못하다", "말다", "아니다", "안", "못"}
# 부정 극성 '명사' 중 영화 평가가 아니라 줄거리·주제어인 경우가 많음
#   (가난·죽음·비극·계급·전쟁 등) → 부정 명사는 기본 제외하고,
#   아래 '평가성 부정 명사'만 점수에 반영한다.
NEG_NOUN_ALLOW = {
    "최악", "노잼", "핵노잼", "발연기", "쓰레기", "망작", "졸작",
    "시간낭비", "돈낭비", "비추", "최하", "별로", "낭비", "노답", "존노잼",
}

# 영화의 '내용·분위기'를 묘사하는 감정어 (리뷰 평가가 아니라 작품 설명).
#   특히 명작·진지한 영화 호평에 자주 쓰여 부정 오분류를 유발하므로 점수에서 제외한다.
#   (예: "가난과 계급이 공포영화보다 무서웠다" = 사실상 호평)
MOOD_EXCLUDE = {
    "무섭다", "두렵다", "무서움", "두려움", "공포", "슬프다", "슬픔", "눈물",
    "무겁다", "먹먹하다", "먹먹", "아프다", "잔인하다", "충격", "고통", "절망",
    "우울하다", "외롭다", "쓸쓸하다", "불쾌하다", "불편하다", "답답하다",
    "암울하다", "비극", "참혹하다", "처참하다", "소름", "전율", "오싹하다",
}

# KNU 감성사전에 없는 영화 리뷰 구어체 감성어를 직접 보강 (Okt가 내놓는 토큰 형태로)
CUSTOM_SENTI = {
    # 긍정 구어체
    "재밌다": 2, "재미있다": 2, "꿀잼": 2, "개꿀잼": 2, "존잼": 2,
    "명작": 2, "띵작": 2, "수작": 2, "걸작": 2, "명불허전": 2,
    "강추": 2, "대박": 2, "감동": 2, "최고": 2, "여운": 2, "갓영화": 2,
    # 부정 구어체
    "노잼": -2, "핵노잼": -2, "존노잼": -2, "발연기": -2,
    "망작": -2, "졸작": -2, "노답": -2, "낭비": -2, "쓰레기": -2,
}


def load_senti_dict() -> dict:
    with open(DICT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    d = {}
    for e in data:
        try:
            pol = int(e["polarity"])
        except (KeyError, ValueError):
            continue
        for key in (e.get("word_root"), e.get("word")):
            if key:
                d[key] = pol
    return d


def main():
    print("=" * 55)
    print("왓챠 코멘트 자동 라벨링 (KNU 감성사전)")
    print("=" * 55)

    senti = load_senti_dict()
    senti.update(CUSTOM_SENTI)          # 구어체 감성어 보강(덮어쓰기)
    print(f"[1] 감성사전 로드: {len(senti):,}개 단어 (구어체 {len(CUSTOM_SENTI)}개 보강)")

    df = pd.read_csv(WATCHA_CSV, encoding="utf-8-sig")
    df["comment"] = df["comment"].astype(str)
    print(f"[2] 왓챠 코멘트 로드: {len(df):,}개")

    if len(df) > SAMPLE_SIZE:
        df = df.sample(n=SAMPLE_SIZE, random_state=42).reset_index(drop=True)
    print(f"    라벨링 대상 샘플: {len(df):,}개")

    okt = Okt()

    def score_comment(text: str) -> int:
        """내용어만 점수화 + 부정어 처리로 감성 점수를 계산한다."""
        t = re.sub(r"[^ 가-힣a-zA-Z0-9]", " ", text)[:MAX_CHARS]
        tagged = okt.pos(t, stem=True, norm=True)
        content = [(w, tag) for w, tag in tagged if tag in CONTENT_POS]
        s = 0
        for i, (w, tag) in enumerate(content):
            if w in NEG_WORDS:           # 부정어 자체는 점수화하지 않음
                continue
            if w in MOOD_EXCLUDE:        # 작품 분위기 묘사어는 평가가 아님 → 제외
                continue
            pol = senti.get(w, 0)
            if pol == 0:
                continue
            # 부정 극성 명사는 주제어(가난·죽음 등)일 가능성이 높아 제외.
            # 단, 영화 평가성 부정 명사(최악·노잼 등)는 인정.
            if tag == "Noun" and pol < 0 and w not in NEG_NOUN_ALLOW:
                continue
            # 뒤따르는 1~2개 내용어에 부정어가 있으면 극성 반전
            negated = any(
                content[j][0] in NEG_WORDS
                for j in range(i + 1, min(i + 3, len(content)))
            )
            s += -pol if negated else pol
        return s

    labels = []
    print("[3] 형태소 분석(POS) + 점수 계산 중... (수십 분 소요 가능)")
    total = len(df)
    for i, text in enumerate(df["comment"]):
        score = score_comment(text)
        if score >= POS_TH:
            labels.append(1)
        elif score <= -NEG_TH:
            labels.append(0)
        else:
            labels.append(-1)   # 애매 → 제외
        if (i + 1) % 20000 == 0:
            print(f"    {i+1:,}/{total:,} 처리 ...", flush=True)

    df["label"] = labels
    dist = Counter(labels)
    print(f"[4] 라벨 분포: 긍정 {dist[1]:,} / 부정 {dist[0]:,} / 제외 {dist[-1]:,}")

    labeled = df[df["label"] != -1].copy()

    # 클래스 균형 (적은 쪽에 맞춰 downsample)
    n_pos = (labeled["label"] == 1).sum()
    n_neg = (labeled["label"] == 0).sum()
    n = min(n_pos, n_neg)
    pos = labeled[labeled["label"] == 1].sample(n=n, random_state=42)
    neg = labeled[labeled["label"] == 0].sample(n=n, random_state=42)
    balanced = pd.concat([pos, neg]).sample(frac=1, random_state=42).reset_index(drop=True)

    # NSMC와 동일하게 document/label 컬럼으로 저장
    out = balanced.rename(columns={"comment": "document"})[["document", "label"]]
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[5] 저장 완료: {OUT_CSV}")
    print(f"    최종 학습 데이터: {len(out):,}개 (긍정 {n:,} / 부정 {n:,})")


if __name__ == "__main__":
    main()
