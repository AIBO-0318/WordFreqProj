import streamlit as st      # 웹 대시보드 UI 생성 (버튼, 슬라이더, 파일 업로더 등)
import pandas as pd          # CSV 파일을 읽고 데이터프레임으로 처리
import matplotlib.pyplot as plt  # 막대 그래프 그리기
from wordcloud import WordCloud  # 워드클라우드 이미지 생성
from collections import Counter  # 단어별 등장 횟수 자동 집계

# Windows 기본 한글 폰트(맑은 고딕)
# matplotlib은 기본적으로 한글을 지원하지 않아서 직접 지정해야 함
plt.rc('font', family='Malgun Gothic')

# WordCloud는 font_path를 별도로 요구하기 때문에 파일 경로 따로 저장
font_path = 'C:/Windows/Fonts/malgun.ttf'

# 한글 폰트 사용 시 마이너스(-) 기호가 깨지는 문제 방지
plt.rcParams['axes.unicode_minus'] = False

# 브라우저 탭 제목과 레이아웃 설정
st.set_page_config(page_title="단어 빈도수 시각화", layout="wide")


# 사이드바 UI를 구성하고 사용자 입력값을 딕셔너리로 반환하는 함수
# main()에서 이 함수를 호출해 모든 설정값을 한 번에 받아옴

def render_sidebar():
    with st.sidebar:
        st.header("파일 선택")

        # CSV 파일 업로더 (CSV 형식만 허용)
        uploaded_file = st.file_uploader("Drag and drop file here", type=['csv'])

        # 분석할 텍스트가 담긴 컬럼명을 직접 입력
        st.caption("데이터가 있는 컬럼명")
        col_name = st.text_input("", value="review", label_visibility="collapsed")

        # 데이터 미리보기 버튼
        check_data_btn = st.button("데이터 파일 확인")

        st.divider()
        st.header("설정")

        # 빈도수 막대 그래프 표시 여부 선택
        show_bar_chart = st.checkbox("빈도수 그래프", value=True)

        # 체크박스가 켜져 있을 때만 슬라이더 표시, 꺼져 있으면 None 저장
        bar_word_count = st.slider("단어 수", min_value=10, max_value=50, value=20, key='bar_slider') if show_bar_chart else None

        # 워드클라우드 표시 여부 선택
        show_wordcloud = st.checkbox("워드클라우드", value=False)

        # 워드클라우드 체크박스가 켜져 있을 때만 슬라이더 표시
        wc_word_count = st.slider("단어 수", min_value=20, max_value=500, value=50, key='wc_slider') if show_wordcloud else None

        # 분석 시작 버튼 (primary 타입은 강조 색상으로 표시됨)
        start_btn = st.button("분석 시작", type="primary")

    # 사용자가 입력한 모든 설정값을 딕셔너리로 묶어서 반환
    # main()에서 config["키이름"] 형태로 꺼내 사용
    return {
        "uploaded_file": uploaded_file,   # 업로드된 파일 객체
        "col_name": col_name,             # 분석할 컬럼명
        "check_data_btn": check_data_btn, # 미리보기 버튼 클릭 여부
        "show_bar_chart": show_bar_chart, # 막대 그래프 표시 여부
        "bar_word_count": bar_word_count, # 막대 그래프 단어 수
        "show_wordcloud": show_wordcloud, # 워드클라우드 표시 여부
        "wc_word_count": wc_word_count,   # 워드클라우드 단어 수
        "start_btn": start_btn,           # 분석 시작 버튼 클릭 여부
    }


# CSV 파일을 읽어서 단어 빈도수를 분석하는 함수
# 반환값: (Counter 객체, 리뷰 수) 또는 오류 시 (None, None)
def analyze_text(uploaded_file, col_name):
    # CSV 파일을 pandas 데이터프레임으로 읽기
    df = pd.read_csv(uploaded_file)

    # 사용자가 입력한 컬럼명이 실제 CSV에 존재하는지 확인
    # 존재하지 않으면 에러 메시지를 보여주고 None을 반환해 분석 중단
    if col_name not in df.columns:
        st.error(f"업로드한 파일에 '{col_name}' 컬럼이 존재하지 않습니다.")
        return None, None

    # 결측치 제거 후 문자열로 변환, 리스트로 저장
    text_data = df[col_name].dropna().astype(str).tolist()

    # 모든 리뷰를 하나의 문자열로 합친 뒤 공백 기준으로 단어 분리
    words = " ".join(text_data).split()

    # Counter로 각 단어의 등장 횟수를 집계 -> {"맛있어요": 10, "친절": 5, ...}
    counter = Counter(words)

    # 분석 완료 메시지 출력
    st.success(f"분석이 완료되었습니다 ({len(text_data):,}개의 리뷰, {len(words):,}개의 단어)")

    # Counter 객체와 리뷰 수를 함께 반환
    return counter, len(text_data)


# 단어 빈도수 가로 막대 그래프를 출력하는 함수
# counter: 단어 빈도수 딕셔너리 / bar_word_count: 표시할 단어 수
def render_bar_chart(counter, bar_word_count):
    st.subheader("단어 빈도수 그래프")

    # 빈도수 상위 bar_word_count개 단어 추출 → [(단어, 빈도수), ...] 형태
    top_words = counter.most_common(bar_word_count)

    if top_words:
        # zip(*top_words)로 단어 리스트와 빈도수 리스트를 각각 분리
        words_list, counts = zip(*top_words)

        fig, ax = plt.subplots(figsize=(10, 6))

        # 가로 막대 그래프 (barh)
        # [::-1]로 순서를 뒤집어 빈도 높은 단어가 위쪽에 오도록 정렬
        ax.barh(words_list[::-1], counts[::-1])
        ax.set_xlabel("빈도수")
        st.pyplot(fig)


# 워드클라우드 이미지를 생성하고 출력하는 함수
# counter: 단어 빈도수 딕셔너리 / wc_word_count: 표시할 최대 단어 수
def render_wordcloud(counter, wc_word_count):
    st.subheader("워드클라우드")

    # WordCloud 객체 생성
    # font_path: 한글 렌더링을 위한 폰트 경로
    # max_words: 워드클라우드에 표시할 최대 단어 수
    wc = WordCloud(
        font_path=font_path,
        background_color="white",
        max_words=wc_word_count,
        width=800,
        height=600
    )

    # 이미 집계된 Counter 딕셔너리를 바로 넘겨서 워드클라우드 생성
    # generate_from_frequencies()는 빈도수 딕셔너리를 직접 받아서 중복 계산 없이 처리
    wc.generate_from_frequencies(counter)

    fig_wc, ax_wc = plt.subplots(figsize=(10, 8))
    ax_wc.imshow(wc, interpolation="bilinear")  # 이미지 부드럽게 렌더링
    ax_wc.axis("off")                           # 축(axis) 숨기기
    st.pyplot(fig_wc)


# 전체 앱 흐름을 제어하는 메인 함수
# 각 함수를 순서대로 호출해서 앱을 구성함
def main():
    st.title("단어 빈도수 시각화")

    # 1단계: 사이드바 UI 렌더링 및 사용자 설정값 수집
    config = render_sidebar()

    # 2단계: 데이터 미리보기 (파일 업로드 + 미리보기 버튼 클릭 시)
    if config["uploaded_file"] and config["check_data_btn"]:
        df = pd.read_csv(config["uploaded_file"])
        st.write("데이터 미리보기:")
        st.dataframe(df.head())  # 상위 5개 행만 출력

    # 3단계: 분석 시작 (파일 업로드 + 분석 시작 버튼 클릭 시)
    if config["uploaded_file"] and config["start_btn"]:

        # 텍스트 분석 실행 → counter: 단어 빈도수, _: 리뷰 수 (여기선 사용 안 함)
        counter, _ = analyze_text(config["uploaded_file"], config["col_name"])

        # 분석 성공 시에만 시각화 출력 (오류 시 counter가 None이므로 건너뜀)
        if counter:
            # 4단계: 막대 그래프 출력 (체크박스가 켜져 있을 때만)
            if config["show_bar_chart"]:
                render_bar_chart(counter, config["bar_word_count"])

            # 5단계: 워드클라우드 출력 (체크박스가 켜져 있을 때만)
            if config["show_wordcloud"]:
                render_wordcloud(counter, config["wc_word_count"])


# 이 파일을 직접 실행할 때만 main() 호출
# 다른 파일에서 import해도 자동 실행되지 않도록 보호
if __name__ == "__main__":
    main()
