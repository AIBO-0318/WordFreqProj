"""
왓챠피디아 코멘트 데이터 전처리
  1. 중복 제거
  2. 길이 필터 (5자 미만 제거)
  3. 노이즈 제거 (이모지만, 특수문자만)
  4. 텍스트 정규화 (공백, 개행 등)
  5. 결과 저장
"""
import sys, re, unicodedata
sys.stdout.reconfigure(encoding="utf-8")
import pandas as pd
import csv

INPUT_FILE  = "watcha_comments.csv"
OUTPUT_FILE = "watcha_comments_clean.csv"
MIN_LEN = 5   # 최소 코멘트 길이

print("=" * 55)
print("왓챠피디아 코멘트 전처리 시작")
print("=" * 55)

# ── 0. 원본 로드 ─────────────────────────────────────────
print(f"\n[1/6] 원본 파일 로드 중...")
df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig", escapechar="\\", on_bad_lines="skip")
df["comment"] = df["comment"].astype(str)
print(f"  원본: {len(df):,}개 코멘트 | {df['movie_title'].nunique()}편 영화")

# ── 1. 중복 제거 ─────────────────────────────────────────
print(f"\n[2/6] 중복 제거...")
before = len(df)
df = df.drop_duplicates(subset=["movie_title", "comment"], keep="first")
removed = before - len(df)
print(f"  영화+코멘트 중복 제거: -{removed:,}개 → {len(df):,}개")

# ── 2. 텍스트 정규화 ─────────────────────────────────────
print(f"\n[3/6] 텍스트 정규화...")

def normalize(text: str) -> str:
    # 1) 유니코드 정규화 (NFKC: 전각→반각, 합성 자모 등)
    text = unicodedata.normalize("NFKC", text)
    # 2) 유니코드 줄바꿈 문자 → 공백 (LS U+2028, PS U+2029 포함)
    text = re.sub(r"[\r\n\t  ]+", " ", text)
    # 3) 제어문자 제거 (인쇄 불가 문자)
    text = re.sub(r"[\x00-\x08\x0e-\x1f\x7f]", "", text)
    # 4) 연속 공백 → 공백 하나
    text = re.sub(r" {2,}", " ", text)
    # 5) 앞뒤 공백 제거
    text = text.strip()
    return text

df["comment"] = df["comment"].map(normalize)
print(f"  정규화 완료")

# ── 3. 길이 필터 ─────────────────────────────────────────
print(f"\n[4/6] 길이 필터 (최소 {MIN_LEN}자)...")
before = len(df)
df = df[df["comment"].str.len() >= MIN_LEN]
removed = before - len(df)
print(f"  {MIN_LEN}자 미만 제거: -{removed:,}개 → {len(df):,}개")

# ── 4. 노이즈 필터 ─────────────────────────────────────────
print(f"\n[5/6] 노이즈 필터...")

# 이모지·특수문자만으로 구성된 코멘트 제거
# (한글, 영문, 숫자, 기본 문장 부호 없이 기타 기호만 있는 경우)
def is_noise(text: str) -> bool:
    # 의미 있는 문자(한글, 영문, 숫자) 없는 경우
    return not bool(re.search(r"[가-힣a-zA-Z0-9]", text))

before = len(df)
noise_mask = df["comment"].apply(is_noise)
df = df[~noise_mask]
removed = before - len(df)
print(f"  의미 없는 문자열 제거: -{removed:,}개 → {len(df):,}개")

# ── 5. 연도 컬럼 보완 ─────────────────────────────────────
# release_year == 0인 영화들은 실제 연도 모름 (역대 흥행 / IMDB / 평균별점 덱)
# 영화 제목에서 (YYYY) 패턴 있으면 추출 시도
if "release_year" in df.columns:
    mask_zero = df["release_year"] == 0
    if mask_zero.sum() > 0:
        # movie_title에 "(YYYY)" 형태가 있으면 추출
        extracted = df.loc[mask_zero, "movie_title"].str.extract(r"\((\d{4})\)")
        filled = extracted[0].dropna()
        df.loc[filled.index, "release_year"] = filled.astype(int)
        still_zero = (df["release_year"] == 0).sum()
        print(f"\n  연도 보완: {len(filled)}개 영화 연도 추출 (남은 release_year=0: {still_zero:,}개)")

# ── 6. 저장 ─────────────────────────────────────────────
print(f"\n[6/6] 저장 중... → {OUTPUT_FILE}")
df.to_csv(
    OUTPUT_FILE, index=False, encoding="utf-8-sig",
    quoting=csv.QUOTE_ALL, escapechar="\\"
)

# ── 최종 리포트 ──────────────────────────────────────────
print()
print("=" * 55)
print("전처리 완료 리포트")
print("=" * 55)
print(f"  최종 코멘트 수: {len(df):,}개")
print(f"  영화 수: {df['movie_title'].nunique()}편")
print(f"  평균 길이: {df['comment'].str.len().mean():.1f}자")
print(f"  중앙값 길이: {df['comment'].str.len().median():.0f}자")
print()

if "release_year" in df.columns:
    print("[ 연도별 코멘트 수 ]")
    yr_stats = df.groupby("release_year").agg(
        영화수=("movie_title", "nunique"),
        코멘트수=("comment", "count")
    ).sort_index()
    print(yr_stats.to_string())
    print()

print(f"[ 코멘트 길이 분포 ]")
lens = df["comment"].str.len()
for cutoff in [10, 20, 50, 100, 200]:
    n = (lens < cutoff).sum()
    print(f"  {cutoff:>4}자 미만: {n:>10,}개 ({n/len(df)*100:5.1f}%)")

print()
print(f"  저장 위치: {OUTPUT_FILE}")
