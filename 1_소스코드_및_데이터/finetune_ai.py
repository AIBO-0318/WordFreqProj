# -*- coding: utf-8 -*-
"""AI 라벨(1000개)로 기존 LSTM 감성모델을 미세조정 + 전후 성능 비교."""
import os, sys, io, glob
os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import re
import numpy as np
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.optimizers import RMSprop
from tensorflow.keras.callbacks import EarlyStopping
from konlpy.tag import Okt

BASE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.join(BASE, "model", "sa_model_movie.keras")
TOK = os.path.join(BASE, "model", "sa_tokenizer_movie.pkl")
META = os.path.join(BASE, "model", "sa_meta.pkl")
OUT_MODEL = os.path.join(BASE, "model", "sa_model_finetuned.keras")

okt = Okt()
tokenizer = joblib.load(TOK)
meta = joblib.load(META)
MAX_LEN = meta["max_len"]

# ── AI 라벨 병합 ───────────────────────────────────────────
labs = pd.concat([pd.read_csv(f) for f in sorted(glob.glob("data/ai_labels_b*.csv"))])
pool = pd.read_csv("data/ai_pool.csv", encoding="utf-8-sig")
df = pool.merge(labs, on="id")
df = df[df["label"] != -1].copy()       # 중립 제외
print(f"AI 라벨(긍/부): {len(df)} | 긍정 {(df.label==1).sum()} 부정 {(df.label==0).sum()}")


def encode(texts):
    seqs = tokenizer.texts_to_sequences([okt.morphs(str(t)) for t in texts])
    return pad_sequences(seqs, maxlen=MAX_LEN)


# ── train/test 분리 (분포 유지) ───────────────────────────
tr, te = train_test_split(df, test_size=0.3, stratify=df.label, random_state=42)
Xtr, ytr = encode(tr.comment.tolist()), to_categorical(tr.label.values, 2)
Xte = encode(te.comment.tolist())
yte = te.label.values
print(f"학습 {len(tr)} / 평가 {len(te)}")

NEG = meta["labels"].index("부정")


def evaluate(model, tag):
    p = model.predict(Xte, verbose=0)
    pred = (p[:, NEG] < 0.6).astype(int)   # 부정 임계 0.6 → 긍정=1
    acc = accuracy_score(yte, pred)
    print(f"\n=== {tag} : 정확도 {acc*100:.1f}% ===")
    print(classification_report(yte, pred, target_names=["부정", "긍정"], digits=3))
    return acc


# ── 미세조정 전 ───────────────────────────────────────────
model = load_model(MODEL)
acc_before = evaluate(model, "미세조정 전 (기존 모델)")

# ── 미세조정 ──────────────────────────────────────────────
model.compile(loss="binary_crossentropy", metrics=["accuracy"],
              optimizer=RMSprop(learning_rate=2e-4))   # 작은 lr
es = EarlyStopping(monitor="val_loss", patience=4, restore_best_weights=True)
print("\n[미세조정 학습]")
model.fit(Xtr, ytr, epochs=30, batch_size=16, validation_split=0.2,
          callbacks=[es], verbose=2)

acc_after = evaluate(model, "미세조정 후")

model.save(OUT_MODEL)
print(f"\n저장: {OUT_MODEL}")
print(f"정확도: {acc_before*100:.1f}%  →  {acc_after*100:.1f}%  ({(acc_after-acc_before)*100:+.1f}%p)")
