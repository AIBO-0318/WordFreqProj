"""
train_sentiment_model.py
─────────────────────────────────────────────────────────────
순환신경망(LSTM) 기반 감성분석 모델 학습 — 왓챠피디아 코멘트

강의 노트북 『09_순환신경망기반감성분석』 구조를 그대로 따르되,
학습 데이터는 네이버 리뷰가 아니라 내가 크롤링한 왓챠 코멘트를 쓴다.
(별점이 없어 KNU 감성사전으로 자동 라벨링 → make_watcha_labeled.py)
  1. 데이터 준비 (로딩 · 전처리 · 분리)
  2. 학습 데이터 준비 (정수 인코딩 · 패딩 · 원핫)
  3. 모델 구축 (Embedding → LSTM → Dense → Dense softmax)
  4. 학습 (EarlyStopping · ModelCheckpoint)
  5. 평가 (classification_report)
  6. 저장 (.keras 모델 + tokenizer.pkl + meta)

실행:  py make_watcha_labeled.py   # 먼저 라벨 데이터 생성
       py train_sentiment_model.py
"""

import os
import re
import sys
import io

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")

import joblib
import numpy as np
import pandas as pd

from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report

from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.models import Sequential, load_model
from tensorflow.keras.layers import Embedding, LSTM, Dense, Input
from tensorflow.keras.optimizers import RMSprop
from tensorflow.keras.callbacks import EarlyStopping, ModelCheckpoint

from mylib.my_utils import word_status_below_threshold, text_len_status_below_maxlen

# ── 경로/하이퍼파라미터 ──────────────────────────────────────
BASE = os.path.dirname(os.path.abspath(__file__))
# 학습 데이터: 왓챠 코멘트를 KNU 감성사전으로 자동 라벨링한 데이터
# (make_watcha_labeled.py 로 먼저 생성)
LABELED_CSV = os.path.join(BASE, "data", "watcha_labeled.csv")
ING_CSV = os.path.join(BASE, "data", "watcha_labeled_ing.csv")  # 토큰화 캐시
MODEL_DIR = os.path.join(BASE, "model")
MODEL_FILE = os.path.join(MODEL_DIR, "sa_model_movie.keras")
CKPT_FILE = os.path.join(MODEL_DIR, "best_model.keras")
TOKENIZER_FILE = os.path.join(MODEL_DIR, "sa_tokenizer_movie.pkl")
META_FILE = os.path.join(MODEL_DIR, "sa_meta.pkl")

VOCAB_SIZE = 40000
NUM_WORDS = VOCAB_SIZE + 1   # 0은 OOV/패딩
MAX_LEN = 50
EMBEDDING_DIM = 32
LSTM_UNITS = 64
DENSE_UNITS = 16
OUTPUT_UNITS = 2
LABELS = ["부정", "긍정"]   # index 0=부정, 1=긍정

os.makedirs(MODEL_DIR, exist_ok=True)


# ══════════════════════════════════════════════════════════
# 1. 데이터 준비
# ══════════════════════════════════════════════════════════
def load_and_preprocess() -> pd.DataFrame:
    """토큰화 캐시(_ing)가 있으면 재사용, 없으면 라벨 데이터에서 전처리한다."""
    if os.path.exists(ING_CSV):
        print(f"[1] 전처리 완료 데이터 로딩: {os.path.basename(ING_CSV)}")
        df = pd.read_csv(ING_CSV, index_col=0)
        df = df.dropna(subset=["tokens_str"])
        return df

    print(f"[1] 라벨 데이터 로딩 후 전처리: {os.path.basename(LABELED_CSV)}")
    df = pd.read_csv(LABELED_CSV, encoding="utf-8-sig")
    df.dropna(inplace=True)                                    # 결측치 제거
    # 한글/공백만 남기고 제거 (NSMC 전처리와 동일)
    df["clean_review"] = df.document.apply(lambda x: re.sub("[^ 가-힣]+", " ", str(x)))
    df.clean_review = df.clean_review.apply(lambda x: re.sub("^ +", "", x))
    df.clean_review = df.clean_review.replace("", None)
    df.dropna(subset=["clean_review"], inplace=True)
    df.drop_duplicates(subset=["clean_review"], inplace=True)  # 중복 제거

    from konlpy.tag import Okt
    okt = Okt()
    print("    형태소 분석(Okt) 중... (수 분 소요)")
    df["tokens_str"] = df.clean_review.apply(lambda x: " ".join(okt.morphs(x)))
    df.to_csv(ING_CSV)
    return df


def main():
    df = load_and_preprocess()
    print(f"    데이터: {len(df):,}개 | 라벨 분포: {df.label.value_counts().to_dict()}")

    review_list = list(df.tokens_str)
    label_list = list(df.label)

    # 1-3. 학습/테스트 분리 (분포 유지)
    review_train, review_test, label_train, label_test = train_test_split(
        review_list, label_list, test_size=0.1, stratify=label_list, random_state=42
    )
    print(f"    학습 {len(review_train):,} / 테스트 {len(review_test):,}")

    # ══════════════════════════════════════════════════════
    # 2. 학습 데이터 준비
    # ══════════════════════════════════════════════════════
    # 2-1. Tokenizer (희귀 단어 비중 확인용)
    test_tokenizer = Tokenizer()
    test_tokenizer.fit_on_texts(review_train)
    word_status_below_threshold(test_tokenizer, threshold=3)

    # 단어 수 제한 Tokenizer
    tokenizer = Tokenizer(num_words=NUM_WORDS)
    tokenizer.fit_on_texts(review_train)
    print(f"[2] 전체 단어 수: {len(tokenizer.word_index):,} (사용 {VOCAB_SIZE:,})")

    # 2-2. 정수 인코딩 + 길이 0 제거
    encoded_train = tokenizer.texts_to_sequences(review_train)
    null_idx = {i for i, r in enumerate(encoded_train) if len(r) < 1}
    new_train = [r for i, r in enumerate(encoded_train) if i not in null_idx]
    new_label_train = [l for i, l in enumerate(label_train) if i not in null_idx]
    print(f"    길이 0 제거: {len(null_idx):,}개 → 학습 {len(new_train):,}")

    text_len_status_below_maxlen(new_train, MAX_LEN)

    # 2-3. 패딩 + 2-4. 원핫
    train_X = pad_sequences(new_train, maxlen=MAX_LEN)
    train_y = to_categorical(new_label_train)

    # 테스트 데이터 동일 처리
    encoded_test = tokenizer.texts_to_sequences(review_test)
    null_idx_t = {i for i, r in enumerate(encoded_test) if len(r) == 0}
    new_test = [r for i, r in enumerate(encoded_test) if i not in null_idx_t]
    new_label_test = [l for i, l in enumerate(label_test) if i not in null_idx_t]
    test_X = pad_sequences(new_test, maxlen=MAX_LEN)
    test_y = to_categorical(new_label_test)

    # ══════════════════════════════════════════════════════
    # 3. 모델 구축 및 컴파일
    # ══════════════════════════════════════════════════════
    model = Sequential([
        Input(shape=(MAX_LEN,)),
        Embedding(NUM_WORDS, EMBEDDING_DIM),
        LSTM(LSTM_UNITS),
        Dense(DENSE_UNITS, activation="tanh"),
        Dense(OUTPUT_UNITS, activation="softmax"),
    ])
    model.compile(
        loss="binary_crossentropy",
        metrics=["accuracy"],
        optimizer=RMSprop(learning_rate=0.001),
    )
    model.summary()

    es = EarlyStopping(monitor="val_loss", mode="min", patience=3, verbose=1)
    mc = ModelCheckpoint(CKPT_FILE, monitor="val_loss", mode="min", save_best_only=True)

    # ══════════════════════════════════════════════════════
    # 4. 학습
    # ══════════════════════════════════════════════════════
    print("[4] 학습 시작...")
    model.fit(
        train_X, train_y,
        epochs=20, batch_size=128,
        validation_split=0.1,
        callbacks=[es, mc],
        verbose=2,
    )

    # ══════════════════════════════════════════════════════
    # 5. 평가
    # ══════════════════════════════════════════════════════
    model = load_model(CKPT_FILE)
    loss, acc = model.evaluate(test_X, test_y, verbose=0)
    print(f"[5] 테스트 loss={loss:.4f}  accuracy={acc:.4f}")

    preds = model.predict(test_X, verbose=0)
    result = np.argmax(preds, axis=1)
    print(classification_report(new_label_test, result, target_names=LABELS))

    # ══════════════════════════════════════════════════════
    # 6. 저장
    # ══════════════════════════════════════════════════════
    model.save(MODEL_FILE)
    joblib.dump(tokenizer, TOKENIZER_FILE)
    joblib.dump({"max_len": MAX_LEN, "labels": LABELS}, META_FILE)
    print(f"[6] 저장 완료:")
    print(f"    - {MODEL_FILE}")
    print(f"    - {TOKENIZER_FILE}")
    print(f"    - {META_FILE}")


if __name__ == "__main__":
    main()
