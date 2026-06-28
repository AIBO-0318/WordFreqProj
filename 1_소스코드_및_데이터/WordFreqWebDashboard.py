"""
WordFreqWebDashboard.py
─────────────────────────────────────────────────────────────
[미니 프로젝트] 왓챠피디아 코멘트 단어 빈도수 분석 웹 대시보드

실행:  streamlit run WordFreqWebDashboard.py

구성
  - 사이드바 : 분석 대상(영화/연도) · 옵션(샘플 수, 단어 길이, 표시 개수) 선택 폼
  - 본문 탭1 : 단어 빈도 분석 — 워드클라우드 · 막대그래프 · 빈도 표
  - 본문 탭2 : 감성 분석 — 긍정/부정 분포 · 대표 코멘트
"""

import pandas as pd
import streamlit as st

from mylib import myTextAnalyzer as ta
from mylib import mySentimentAnalyzer as sa
from mylib import myRecommender as rec
from mylib import myStreamlitVisualizer as viz


# ──────────────────────────────────────────────────────────
# 페이지 설정
# ──────────────────────────────────────────────────────────
st.set_page_config(
    page_title="왓챠피디아 코멘트 단어 빈도 분석",
    page_icon="🎬",
    layout="wide",
)


# ──────────────────────────────────────────────────────────
# 데이터 로드 (캐시 — 화면 갱신마다 재실행 방지)
# ──────────────────────────────────────────────────────────
@st.cache_data(show_spinner="데이터를 불러오는 중...")
def load_data():
    return ta.load_data()


@st.cache_data(show_spinner="형태소 분석 중... (잠시만 기다려 주세요)")
def run_analysis(movie, year, sample_size, min_len, top_n, extra_stopwords):
    """분석 결과를 캐싱한다. 같은 옵션이면 재계산하지 않는다."""
    df = load_data()
    return ta.analyze(
        df,
        movie=movie,
        year=year,
        sample_size=sample_size,
        min_len=min_len,
        top_n=top_n,
        extra_stopwords=set(extra_stopwords) if extra_stopwords else None,
    )


@st.cache_resource(show_spinner="감성분석 모델 로딩 중...")
def get_analyzer():
    """학습된 LSTM 감성분석 모델을 1회만 로딩해 재사용한다."""
    return sa.SentimentAnalyzer()


@st.cache_resource(show_spinner="추천 모델 로딩 중...")
def get_recommender():
    """영화 추천 모델(유사도 행렬)을 1회만 로딩해 재사용한다."""
    return rec.MovieRecommender()


@st.cache_data(show_spinner="감성 분석 중... (LSTM 모델 예측)")
def run_sentiment(movie, year, sample_size, top_n, extra_stopwords):
    """감성 분석 + 긍정/부정 그룹별 단어 빈도까지 계산해 캐싱한다.
    빈도 분석과 동일한 샘플을 사용한다."""
    df = load_data()
    comments, _ = ta.get_sample(df, movie=movie, year=year, sample_size=sample_size)
    analyzer = get_analyzer()
    result = sa.aggregate(comments, analyzer)

    # 불용어: 기본 + 영화 일반 주제어(감독·배우 등) + 사용자 추가(특정 이름 등)
    stop = set(ta.DEFAULT_STOPWORDS) | ta.FILM_STOPWORDS | set(extra_stopwords)

    # 긍정/부정 그룹의 '특징어'를 추출 (공통 주제어·인물명은 자동 약화)
    result["freq_pos"], result["freq_neg"] = ta.distinctive_frequency(
        result["pos_comments"], result["neg_comments"], top_n=top_n, stopwords=stop
    )
    # 캐시 용량 절약 — 계산 후 원본 목록은 제거
    del result["pos_comments"], result["neg_comments"]
    return result


# ──────────────────────────────────────────────────────────
# 헤더
# ──────────────────────────────────────────────────────────
st.title("🎬 왓챠피디아 코멘트 단어 빈도 분석")
st.caption(
    "왓챠피디아에서 크롤링한 영화 코멘트를 형태소 분석하여 "
    "자주 쓰인 단어를 워드클라우드와 막대그래프로 시각화합니다."
)

df = load_data()

# 상단 전체 데이터 요약
c1, c2, c3 = st.columns(3)
c1.metric("전체 코멘트 수", f"{len(df):,} 개")
c2.metric("영화 편수", f"{df['movie_title'].nunique():,} 편")
c3.metric("개봉연도 범위", f"{df['release_year'][df['release_year']>0].min()} ~ {df['release_year'].max()}")

st.divider()


# ──────────────────────────────────────────────────────────
# 사이드바 — 분석 옵션 입력 폼
# ──────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 분석 설정")

    mode = st.radio(
        "분석 기준",
        ["영화별", "연도별", "전체"],
        help="어떤 단위로 코멘트를 모아 분석할지 선택하세요.",
    )

    with st.form("analyze_form"):
        movie = None
        year = None

        if mode == "영화별":
            movie_list = ta.get_movie_list(df)
            movie = st.selectbox(
                "영화 선택",
                movie_list,
                help="코멘트가 많은 영화 순으로 정렬되어 있습니다.",
            )
        elif mode == "연도별":
            year_list = ta.get_year_list(df)
            year = st.selectbox("개봉연도 선택", year_list)

        st.markdown("**분석 옵션**")
        sample_size = st.slider(
            "분석할 코멘트 수 (샘플)",
            min_value=500, max_value=10000, value=3000, step=500,
            help="대상 코멘트가 많을 경우 무작위 샘플링합니다. 값이 클수록 정확하지만 느려집니다.",
        )
        top_n = st.slider("표시할 단어 개수", 10, 100, 50, 5)
        min_len = st.slider("최소 단어 길이(글자)", 1, 4, 2)

        extra_stop = st.text_input(
            "추가 불용어 (쉼표로 구분)",
            value="",
            placeholder="예: 배우, 감독, 연출",
            help="결과에서 제외하고 싶은 단어를 입력하세요.",
        )

        submitted = st.form_submit_button("🔍 분석 실행", width="stretch")


# ──────────────────────────────────────────────────────────
# 본문 — 분석 실행 & 결과 출력
# ──────────────────────────────────────────────────────────
# [분석 실행]을 한 번이라도 누르면 그 상태를 기억한다.
# (탭 안의 '예측하기' 같은 다른 버튼을 눌러 rerun 되어도 결과 화면을 유지)
if submitted:
    st.session_state["analyzed"] = True

if not st.session_state.get("analyzed", False):
    st.info("👈 왼쪽 사이드바에서 분석 대상과 옵션을 고르고 **[분석 실행]** 버튼을 눌러주세요.")
    st.stop()

extra_stopwords = [w.strip() for w in extra_stop.split(",") if w.strip()]

result = run_analysis(movie, year, sample_size, min_len, top_n, tuple(extra_stopwords))

# 코멘트가 너무 적으면 분석 결과가 무의미 → 즉시 중단하고 안내
MIN_COMMENTS = 50
_label = movie if movie else (f"{year}년 개봉작" if year else "선택한 조건")
if result["n_comments"] < MIN_COMMENTS:
    st.error(
        f"### ⚠️ 분석할 수 없습니다\n\n"
        f"**{_label}**의 코멘트는 **{result['n_comments']}개**뿐입니다. "
        f"신뢰할 만한 분석을 위해 최소 **{MIN_COMMENTS}개** 이상이 필요합니다.\n\n"
        f"👈 코멘트가 더 많은 영화를 선택해 주세요."
    )
    st.stop()

# ── 분석 대상 표시 ─────────────────────────────────────────
if mode == "영화별":
    target_label = f"🎞️ {movie}"
elif mode == "연도별":
    target_label = f"📅 {year}년 개봉작"
else:
    target_label = "🌐 전체 코멘트"
st.subheader(f"분석 결과 — {target_label}")

# ── 요약 지표 ─────────────────────────────────────────────
m1, m2, m3, m4 = st.columns(4)
m1.metric("대상 코멘트", f"{result['n_comments']:,} 개")
m2.metric("분석 코멘트", f"{result['n_analyzed']:,} 개")
m3.metric("추출 단어 수", f"{result['n_words']:,} 개")
m4.metric("고유 단어 수", f"{result['n_unique']:,} 개")

st.divider()

freq = result["freq"]

tab_freq, tab_senti, tab_rec = st.tabs(
    ["📊 단어 빈도 분석", "😊 감성 분석", "🎬 비슷한 영화 추천"]
)

# ══════════════════════════════════════════════════════════
# 탭 1 — 단어 빈도 분석
# ══════════════════════════════════════════════════════════
with tab_freq:
    # 워드클라우드 & 막대그래프
    col_wc, col_bar = st.columns([1, 1])

    with col_wc:
        st.markdown("#### ☁️ 워드클라우드")
        if freq:
            fig_wc = viz.make_wordcloud(freq)
            st.pyplot(fig_wc)
        else:
            st.write("표시할 단어가 없습니다.")

    with col_bar:
        st.markdown("#### 📊 단어 빈도 막대그래프")
        if freq:
            bar_n = min(20, len(freq))
            fig_bar = viz.make_barchart(freq, top_n=bar_n)
            st.pyplot(fig_bar)
        else:
            st.write("표시할 단어가 없습니다.")

    st.divider()

    # 빈도 표 & 코멘트 미리보기
    col_tbl, col_cmt = st.columns([1, 1])

    with col_tbl:
        st.markdown("#### 📋 단어 빈도 표")
        freq_df = pd.DataFrame(freq, columns=["단어", "빈도수"])
        freq_df.index = range(1, len(freq_df) + 1)
        freq_df.index.name = "순위"
        st.dataframe(freq_df, width="stretch", height=400)

        csv = freq_df.to_csv(encoding="utf-8-sig")
        st.download_button(
            "📥 빈도표 CSV 다운로드",
            data=csv,
            file_name="word_frequency.csv",
            mime="text/csv",
        )

    with col_cmt:
        st.markdown("#### 💬 코멘트 미리보기")
        for i, c in enumerate(result["sample_comments"], 1):
            st.markdown(f"**{i}.** {c[:200]}{'...' if len(c) > 200 else ''}")

# ══════════════════════════════════════════════════════════
# 탭 2 — 감성 분석 (LSTM 모델 기반 / 네이버 영화 리뷰 학습)
# ══════════════════════════════════════════════════════════
with tab_senti:
    st.markdown(
        "왓챠 코멘트로 학습한 **순환신경망(LSTM) 모델**이 코멘트를 "
        "**긍정/부정**으로 분류하고, 각 그룹의 단어 빈도를 따로 시각화합니다."
    )

    if not sa.model_exists():
        st.warning(
            "학습된 감성분석 모델이 없습니다.\n\n"
            "터미널에서 아래 명령으로 먼저 라벨 데이터 생성 → 모델 학습을 해주세요:\n\n"
            "```\npy make_watcha_labeled.py\npy train_sentiment_model.py\n```"
        )
    else:
        # ── 선택한 영화/연도 코멘트 집계 ─────────────────────
        st.markdown(f"#### 📈 {target_label} 코멘트 감성 분포")
        senti = run_sentiment(movie, year, sample_size, top_n, tuple(extra_stopwords))
        counts = senti["counts"]
        ratios = senti["ratios"]

        s1, s2, s3 = st.columns(3)
        s1.metric("😊 긍정", f"{counts.get('긍정', 0):,} 개", f"{ratios.get('긍정', 0):.1f}%")
        s2.metric("😡 부정", f"{counts.get('부정', 0):,} 개", f"{ratios.get('부정', 0):.1f}%")
        s3.metric("긍정 비율", f"{senti['pos_ratio']:.1f}%")

        if senti["n"] > 0:
            # 도넛 차트는 좁은 칸에 넣어 너무 커지지 않게
            pie_col, _spacer = st.columns([1, 2])
            with pie_col:
                st.pyplot(viz.make_sentiment_pie(counts), use_container_width=True)

        st.divider()

        # ── 긍정/부정 그룹별 '특징어' 워드클라우드 + 빈도 그래프 ──
        freq_pos = senti["freq_pos"]
        freq_neg = senti["freq_neg"]
        st.markdown("#### 🔍 긍정/부정 특징 단어")
        st.caption(
            "각 그룹에 **상대적으로 더 자주** 쓰인 단어만 보여줍니다. "
            "봉준호·기생충처럼 양쪽에 고루 나오는 인물명·주제어는 자동으로 약화됩니다."
        )

        col_pos, col_neg = st.columns(2)

        with col_pos:
            st.markdown("### 😊 긍정 코멘트")
            if freq_pos:
                st.markdown("**☁️ 긍정 특징어 워드클라우드**")
                st.pyplot(viz.make_wordcloud(freq_pos, colormap="summer"))
                st.markdown("**📊 긍정 특징 단어**")
                st.pyplot(viz.make_barchart(
                    freq_pos, top_n=min(15, len(freq_pos)), color="#2ecc71",
                    title="긍정에 두드러진 단어", xlabel="특징 점수"))
                st.markdown("**💚 대표 코멘트**")
                for c in senti["examples_pos"][:3]:
                    st.success(c[:150] + ("..." if len(c) > 150 else ""))
            else:
                st.caption("긍정으로 분류된 코멘트가 없습니다.")

        with col_neg:
            st.markdown("### 😡 부정 코멘트")
            if freq_neg:
                st.markdown("**☁️ 부정 특징어 워드클라우드**")
                st.pyplot(viz.make_wordcloud(freq_neg, colormap="autumn"))
                st.markdown("**📊 부정 특징 단어**")
                st.pyplot(viz.make_barchart(
                    freq_neg, top_n=min(15, len(freq_neg)), color="#e74c3c",
                    title="부정에 두드러진 단어", xlabel="특징 점수"))
                st.markdown("**❤️ 대표 코멘트**")
                for c in senti["examples_neg"][:3]:
                    st.error(c[:150] + ("..." if len(c) > 150 else ""))
            else:
                st.caption("부정으로 분류된 코멘트가 없습니다.")

# ══════════════════════════════════════════════════════════
# 탭 3 — 비슷한 영화 추천 (코멘트 TF-IDF 코사인 유사도)
# ══════════════════════════════════════════════════════════
with tab_rec:
    if not rec.model_exists():
        st.markdown(
            "영화 코멘트의 단어 사용을 **TF-IDF + 코사인 유사도**로 비교해 추천합니다."
        )
        st.warning(
            "추천 모델이 없습니다. 터미널에서 먼저 만들어 주세요:\n\n"
            "```\npy build_recommender.py\n```"
        )
    else:
        recommender = get_recommender()
        rec_movies = recommender.movie_list()
        has_senti = recommender.has_sentiment()

        if has_senti:
            st.markdown(
                "추천에 쓰는 두 신호 모두 **크롤링한 코멘트에서** 나옵니다.\n"
                "- 🗣️ **분위기·소재**: 코멘트 단어 TF-IDF 코사인 유사도\n"
                "- 😊 **관객 호불호 반응**: LSTM 감성모델(왓챠 코멘트로 학습)이 매긴 **호평률** 유사도"
            )
        else:
            st.markdown(
                "영화 코멘트의 단어 사용을 **TF-IDF + 코사인 유사도**로 비교해 추천합니다."
            )

        # 사이드바에서 고른 영화가 추천 대상(코멘트 50개 이상)이 아니면 안내
        if movie and movie not in rec_movies:
            st.info(
                f"‘{movie}’은(는) 코멘트가 적어 추천 대상에서 제외되었습니다. "
                "(추천은 코멘트 50개 이상 영화만 지원) 아래에서 다른 영화를 골라주세요."
            )

        # 기준 영화: 사이드바에서 영화별이면 그 영화, 아니면 직접 선택
        default_idx = rec_movies.index(movie) if (movie in rec_movies) else 0
        c1, c2 = st.columns(2)
        base_movie = c1.selectbox("기준 영화 선택", rec_movies, index=default_idx)
        n_rec = c2.slider("추천 개수", 3, 10, 5)
        min_sim = c2.slider("최소 분위기 유사도 (이 값 미만 숨김)", 0.05, 0.40, 0.12, 0.01)

        if has_senti:
            alpha = c1.slider(
                "가중치 (← 호불호 반응 중시  ·  분위기 중시 →)",
                0.0, 1.0, 0.7, 0.05,
                help="왼쪽일수록 '관객 호불호 반응'을, 오른쪽일수록 '코멘트 분위기·소재'를 더 본다",
            )
            base_pr = recommender.reception(base_movie)
            c1.caption(f"📊 **{base_movie}** 관객 호평률: **{base_pr:.0%}**")
        else:
            alpha = 1.0

        st.caption(f"🔑 **{base_movie}** 대표 키워드: "
                   + ", ".join(recommender.keywords(base_movie)))
        st.divider()

        recs = recommender.recommend(base_movie, top_n=n_rec, min_sim=min_sim, alpha=alpha)
        if not recs:
            st.info(
                f"분위기 유사도 {min_sim:.2f} 이상으로 충분히 비슷한 영화가 없습니다. "
                "(왓챠 코멘트 어휘가 뚜렷이 겹치는 영화가 없다는 뜻)"
            )
        else:
            st.markdown(f"#### 🎬 **{base_movie}** 와(과) 비슷한 영화")
            for rank, r in enumerate(recs, 1):
                title, score = r["title"], r["score"]
                common = recommender.common_terms(base_movie, title, top_n=6)
                reason = ("코멘트에 **" + " · ".join(common) + "** 가 함께 자주 등장") if common \
                    else "코멘트 어휘가 전반적으로 유사"
                detail = ""
                if has_senti:
                    detail = (f"  \n<span style='color:#10B981;font-size:0.85em'>"
                              f"🗣️ 분위기 {r['topic']:.2f} · 😊 반응유사 {r['recep']:.2f} · "
                              f"관객 호평률 {r['pos_ratio']:.0%}</span>")
                st.markdown(
                    f"**{rank}. {title}**  ·  종합점수 `{score:.2f}`  \n"
                    f"<span style='color:#3B82F6;font-size:0.9em'>🔗 비슷한 이유: {reason}</span>"
                    f"{detail}",
                    unsafe_allow_html=True,
                )
                st.progress(min(1.0, score))

st.divider()
st.caption(
    "데이터 출처: 왓챠피디아 크롤링 | 형태소 분석: KoNLPy(Okt) | "
    "감성분석: LSTM (왓챠 코멘트 학습) | 추천: 코멘트 TF-IDF + 호평률(감성) 결합 | "
    "시각화: WordCloud · Matplotlib · Streamlit"
)
