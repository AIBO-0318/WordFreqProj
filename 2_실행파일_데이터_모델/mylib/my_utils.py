"""
my_utils.py
─────────────────────────────────────────────────────────────
감성분석 모델 학습용 보조 함수
(강의 노트북의 lib.my_utils 와 동일한 역할)
"""


def word_status_below_threshold(tokenizer, threshold: int):
    """등장 빈도가 threshold 미만인 단어(희귀 단어)가 차지하는 비율을 출력한다.

    Keras Tokenizer의 word_counts를 이용해
    '버릴 단어'와 '사용할 단어'의 비중을 확인한다.
    """
    total_cnt = len(tokenizer.word_index)          # 전체 단어 수
    rare_cnt = 0                                    # threshold 미만 단어 수
    total_freq = 0                                  # 전체 단어 등장 횟수
    rare_freq = 0                                   # threshold 미만 단어 등장 횟수

    for key, value in tokenizer.word_counts.items():
        total_freq += value
        if value < threshold:
            rare_cnt += 1
            rare_freq += value

    use_cnt = total_cnt - rare_cnt
    use_freq = total_freq - rare_freq

    print(f"=== 빈도수가 {threshold}번 이상인 단어만 사용하는 경우 ====")
    print(f"전체 단어 : {total_cnt:,}개 {total_freq:,}번")
    print(f"희귀 단어 : {rare_cnt:,}개 ({rare_cnt/total_cnt*100:.2f}%) "
          f"{rare_freq:,}번 ({rare_freq/total_freq*100:.2f}%)")
    print(f"사용할 단어 : {use_cnt:,}개 ({use_cnt/total_cnt*100:.2f}%)    "
          f"{use_freq:,}번 ({use_freq/total_freq*100:.2f}%)")

    return use_cnt


def text_len_status_below_maxlen(sequences, max_len: int):
    """길이가 max_len 이하인 데이터의 비중을 출력한다."""
    cnt = sum(1 for s in sequences if len(s) <= max_len)
    ratio = cnt / len(sequences) * 100
    print(f"전체 {len(sequences):,}개 중 길이 {max_len} 이하: "
          f"{cnt:,}개 ({ratio:.2f}%)")
    return ratio
