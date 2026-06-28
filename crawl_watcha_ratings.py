"""
crawl_watcha_ratings.py
─────────────────────────────────────────────────────────────
왓챠 코멘트를 '작성자 별점'과 함께 재수집하여
감성분석 학습용 라벨 데이터(watcha_labeled.csv)를 만든다.

NSMC가 네이버 별점으로 라벨을 만든 것과 동일한 방식:
  - 별점(0~10) ≥ POS_RATING → 긍정(1)
  - 별점(0~10) ≤ NEG_RATING → 부정(0)
  - 그 사이 → 제외
부정 표본(저평점)이 충분히 모이면 조기 종료한다.

실행:  py crawl_watcha_ratings.py
       (D:\\proj 의 watcha_session.pkl / visited_urls.txt 사용)
"""

import os
import sys
import io
import time
import random
import pickle
import string

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import requests
import pandas as pd

# ── 경로 ─────────────────────────────────────────────────
PROJ_BASE = os.path.dirname(os.path.abspath(__file__))   # WordFreqProj
SRC_BASE = os.path.dirname(PROJ_BASE)                    # D:\proj (세션/URL 위치)
COOKIE_FILE = os.path.join(SRC_BASE, "watcha_session.pkl")
VISITED_FILE = os.path.join(SRC_BASE, "visited_urls.txt")
RATED_CSV = os.path.join(PROJ_BASE, "data", "watcha_rated.csv")
OUT_CSV = os.path.join(PROJ_BASE, "data", "watcha_labeled.csv")

API_BASE = "https://pedia.watcha.com"

# ── 수집/라벨 파라미터 ────────────────────────────────────
MOVIE_LIMIT = 80           # 최대 영화 수
MAX_PER_MOVIE = 2500       # 영화당 최대 코멘트
TARGET_NEG = 15000         # 부정(저평점) 이만큼 모이면 종료
POS_RATING = 9             # 별점 9~10(4.5~5.0★) → 긍정
NEG_RATING = 4             # 별점 0~4(0~2.0★)   → 부정
API_DELAY = (0.3, 0.6)
BURST, REST = 30, 8.0      # 30요청마다 8초 휴식 (429 예방)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"


def make_session():
    s = requests.Session()
    for c in pickle.load(open(COOKIE_FILE, "rb")):
        s.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))
    dev = "web-" + "".join(random.choices(string.ascii_letters + string.digits, k=30))
    s.headers.update({
        "accept": "application/vnd.frograms+json;version=2.1.0",
        "x-frograms-app-code": "Galaxy",
        "x-frograms-client": "Galaxy-Web-App",
        "x-frograms-client-version": "2.1.0",
        "x-frograms-device-identifier": dev,
        "x-frograms-galaxy-language": "ko",
        "x-frograms-version": "2.1.0",
        "User-Agent": _UA,
    })
    return s


def get_title(s, code):
    try:
        r = s.get(f"{API_BASE}/api/contents/{code}",
                  headers={"Referer": f"{API_BASE}/ko/contents/{code}"}, timeout=10)
        if r.status_code == 200:
            res = r.json().get("result", {})
            return res.get("title", code)
    except Exception:
        pass
    return code


def crawl_movie(s, code, title):
    """한 영화의 (text, rating) 목록 수집."""
    rows = []
    referer = f"{API_BASE}/ko/contents/{code}/comments"
    next_uri = f"/api/contents/{code}/comments?filter=all&order=popular&size=30"
    req = 0
    while next_uri and len(rows) < MAX_PER_MOVIE:
        if req > 0 and req % BURST == 0:
            time.sleep(REST + random.uniform(0, 2))
        try:
            r = s.get(API_BASE + next_uri, headers={"Referer": referer}, timeout=15)
        except requests.RequestException:
            break
        if r.status_code == 429:
            time.sleep(30 + random.uniform(0, 15))
            req = 0
            continue
        if r.status_code != 200:
            break
        req += 1
        try:
            result = r.json()["result"]
            page = result.get("result", [])
            next_uri = result.get("next_uri")
        except Exception:
            break
        for it in page:
            text = (it.get("text") or "").strip()
            if len(text) <= 2 or "http" in text:
                continue
            rating = (it.get("user_content_action") or {}).get("rating")
            if rating is None:
                continue
            rows.append((title, text, rating))
        time.sleep(random.uniform(*API_DELAY))
    return rows


def main():
    print("=" * 55)
    print("왓챠 별점 재수집 (감성분석 라벨 생성)")
    print("=" * 55)
    s = make_session()
    urls = [u.strip() for u in open(VISITED_FILE, encoding="utf-8").read().splitlines() if u.strip()]

    all_rows = []
    neg_count = 0
    for idx, url in enumerate(urls[:MOVIE_LIMIT], 1):
        code = url.rstrip("/").split("/")[-1]
        title = get_title(s, code)
        rows = crawl_movie(s, code, title)
        all_rows.extend(rows)
        neg_count = sum(1 for _, _, r in all_rows if r <= NEG_RATING)
        print(f"[{idx}/{MOVIE_LIMIT}] {title[:24]:24s} +{len(rows):5d}개 "
              f"(누적 {len(all_rows):,} / 부정 {neg_count:,})", flush=True)
        if neg_count >= TARGET_NEG:
            print(f"  → 부정 표본 {TARGET_NEG} 도달, 수집 종료")
            break
        time.sleep(random.uniform(0.5, 1.2))

    df = pd.DataFrame(all_rows, columns=["movie_title", "comment", "rating"])
    df.to_csv(RATED_CSV, index=False, encoding="utf-8-sig")
    print(f"\n원본 별점 데이터 저장: {RATED_CSV} ({len(df):,}개)")

    # ── 별점 → 긍정/부정 라벨 ────────────────────────────
    df = df.drop_duplicates(subset=["comment"])
    pos = df[df["rating"] >= POS_RATING].copy()
    neg = df[df["rating"] <= NEG_RATING].copy()
    print(f"라벨: 긍정(별점≥{POS_RATING}) {len(pos):,} / 부정(별점≤{NEG_RATING}) {len(neg):,}")

    n = min(len(pos), len(neg))
    pos = pos.sample(n=n, random_state=42)
    neg = neg.sample(n=n, random_state=42)
    bal = pd.concat([pos, neg]).sample(frac=1, random_state=42)
    bal["label"] = (bal["rating"] >= POS_RATING).astype(int)
    out = bal.rename(columns={"comment": "document"})[["document", "label"]]
    out.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
    print(f"학습 데이터 저장: {OUT_CSV} ({len(out):,}개 / 긍정 {n:,} 부정 {n:,})")


if __name__ == "__main__":
    main()
