"""
myStreamlitVisualizer.py
─────────────────────────────────────────────────────────────
시각화 모듈

기능
  - 단어 빈도수 → 워드클라우드 (matplotlib Figure)
  - 단어 빈도수 → 가로 막대그래프 (matplotlib Figure)
한글 폰트(맑은 고딕)를 자동 설정한다.
"""

import os
import platform

import matplotlib
matplotlib.use("Agg")  # GUI 없는 환경(서버)에서도 동작
import matplotlib.pyplot as plt
from matplotlib import font_manager, rc
from wordcloud import WordCloud


# ──────────────────────────────────────────────────────────
# 한글 폰트 경로 탐색
# ──────────────────────────────────────────────────────────
def _find_korean_font() -> str | None:
    """OS별 대표 한글 폰트 경로를 찾는다. 없으면 None."""
    candidates = []
    system = platform.system()
    if system == "Windows":
        candidates = [
            r"C:\Windows\Fonts\malgun.ttf",     # 맑은 고딕
            r"C:\Windows\Fonts\NanumGothic.ttf",
        ]
    elif system == "Darwin":  # macOS
        candidates = ["/System/Library/Fonts/AppleSDGothicNeo.ttc"]
    else:  # Linux (Streamlit Cloud 등)
        candidates = [
            "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
            "/usr/share/fonts/truetype/nanum/NanumGothicCoding.ttf",
        ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None


FONT_PATH = _find_korean_font()


def set_korean_font():
    """matplotlib 전역 한글 폰트를 설정한다."""
    if FONT_PATH:
        font_name = font_manager.FontProperties(fname=FONT_PATH).get_name()
        rc("font", family=font_name)
    plt.rcParams["axes.unicode_minus"] = False  # 마이너스 깨짐 방지


set_korean_font()


# ──────────────────────────────────────────────────────────
# 워드클라우드
# ──────────────────────────────────────────────────────────
def make_wordcloud(
    freq: list[tuple[str, int]],
    width: int = 800,
    height: int = 400,
    background_color: str = "white",
    colormap: str = "tab10",
):
    """빈도수 리스트로 워드클라우드 Figure를 만든다."""
    freq_dict = dict(freq)

    wc = WordCloud(
        font_path=FONT_PATH,
        width=width,
        height=height,
        background_color=background_color,
        colormap=colormap,
        max_words=200,
        prefer_horizontal=0.9,
    ).generate_from_frequencies(freq_dict)

    fig, ax = plt.subplots(figsize=(width / 100, height / 100))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    fig.tight_layout(pad=0)
    return fig


# ──────────────────────────────────────────────────────────
# 막대그래프
# ──────────────────────────────────────────────────────────
def make_barchart(
    freq: list[tuple[str, int]],
    top_n: int = 20,
    color: str = "#ff4b4b",
    title: str | None = None,
    xlabel: str = "빈도수",
):
    """상위 top_n개 단어를 가로 막대그래프로 그린다."""
    data = freq[:top_n]
    words = [w for w, _ in data][::-1]   # 위에서부터 큰 값이 오도록 역순
    counts = [c for _, c in data][::-1]

    fig, ax = plt.subplots(figsize=(8, max(4, top_n * 0.35)))
    bars = ax.barh(words, counts, color=color)
    ax.set_xlabel(xlabel)
    ax.set_title(title if title else f"상위 {top_n}개 단어 빈도")

    # 막대 끝에 수치 표시
    for bar, count in zip(bars, counts):
        ax.text(
            bar.get_width(),
            bar.get_y() + bar.get_height() / 2,
            f" {count:,}",
            va="center",
            fontsize=9,
        )
    fig.tight_layout()
    return fig


# ──────────────────────────────────────────────────────────
# 감성 분포 도넛 차트
# ──────────────────────────────────────────────────────────
SENTIMENT_COLORS = {"긍정": "#2ecc71", "부정": "#e74c3c", "중립": "#95a5a6"}


def make_sentiment_pie(counts: dict[str, int]):
    """긍정/부정/중립 개수를 도넛 차트로 그린다."""
    labels = [k for k in ["긍정", "부정", "중립"] if counts.get(k, 0) > 0]
    sizes = [counts[k] for k in labels]
    colors = [SENTIMENT_COLORS[k] for k in labels]

    fig, ax = plt.subplots(figsize=(3.4, 3.4))
    wedges, _texts, autotexts = ax.pie(
        sizes,
        labels=labels,
        colors=colors,
        autopct=lambda p: f"{p:.1f}%",
        pctdistance=0.78,          # 퍼센트 숫자를 도넛 링 한가운데로
        labeldistance=1.12,        # 긍정/부정 라벨은 바깥쪽으로
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.42, "edgecolor": "white"},  # 도넛
        textprops={"fontsize": 11},
    )
    for at in autotexts:
        at.set_color("white")
        at.set_fontsize(10)
        at.set_fontweight("bold")
    ax.set_title("감성 분포", fontsize=13)
    ax.axis("equal")
    fig.tight_layout()
    return fig
