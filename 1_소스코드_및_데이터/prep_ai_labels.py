# -*- coding: utf-8 -*-
"""AI 라벨링용 코멘트 풀 생성: ai_pool.csv(전체텍스트) + ai_pool_view.tsv(읽기용)"""
import sys, io, re
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
import pandas as pd

df = pd.read_csv("data/watcha_comments_clean.csv", encoding="utf-8-sig")
df["comment"] = df["comment"].astype(str)
df = df[df["comment"].str.len() >= 5].drop_duplicates(subset=["comment"])

N = 1000
pool = df.sample(n=N, random_state=2024).reset_index(drop=True)
pool.insert(0, "id", range(1, len(pool) + 1))
pool[["id", "movie_title", "comment"]].to_csv("data/ai_pool.csv", index=False, encoding="utf-8-sig")

# 읽기용: id <TAB> (공백정리·220자 절단) 코멘트
def view(t):
    t = re.sub(r"\s+", " ", t).strip()
    return t[:220]

with io.open("data/ai_pool_view.tsv", "w", encoding="utf-8") as f:
    for _, r in pool.iterrows():
        f.write(f"{r['id']}\t{view(r['comment'])}\n")

print(f"pool 생성: {len(pool)}개 → data/ai_pool.csv, data/ai_pool_view.tsv")
