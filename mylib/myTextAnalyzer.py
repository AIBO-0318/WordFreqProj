import pandas as pd

def load_corpus_from_csv(data_filename, column):
    data_df = pd.read_csv(data_filename)
    corpus = list(data_df[column])
    if data_df[column].isnull().sum():
        data_df.dropna(subset=[column], inplace=True)
    return corpus

def tokenize_korean_corpus(corpus, tokenizer, my_tags=None, my_stopwords=None):
    all_tokens = []
    if my_tags:
        #print('enter my_tags')
        for text in corpus:
            tokens = [word for word, tag in tokenizer(text) if tag in my_tags and word not in my_stopwords]
            all_tokens += tokens
    else:
        #print('enter no tags')
        for text in corpus:
            tokens = [word for word, tag in tokenizer(text) if word not in my_stopwords]
            all_tokens += tokens

    return all_tokens

from collections import Counter

def analyze_word_freq(tokens):
    return Counter(tokens)

import matplotlib.pyplot as plt
from matplotlib import font_manager, rc
def set_korean_font_for_matplotlib(font_path):
    # matplotlib 한글 폰트 설정
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    rc('font', family=font_name)

def visualize_barhgraph(counter, num_words, title=None, xlabel=None, ylabel=None, font_path=None):
    # 고빈도 단어를 num_words만큼 추출
    wordcount_list = counter.most_common(num_words)

    # x 데이터와 y 데이터 분리
    x_list = [word for word, count in wordcount_list]
    y_list = [count for word, count in wordcount_list]

    # matplotlib을 위한 한글 폰트 설정
    if font_path: set_korean_font_for_matplotlib(font_path)

    # 수평막대그래프 객체 생성
    plt.barh(x_list[::-1], y_list[::-1])

    # 그래프 정보 추가 (제목, x, y 레이블)
    if title: plt.title(title)
    if xlabel: plt.xlabel(xlabel)
    if ylabel: plt.ylabel(ylabel)

    # 화면에 출력
    plt.show()

from wordcloud import WordCloud
def visualize_wordcloud(counter, num_words, font_path):
    # wordcloud 객체 생성 (option 지정)
    wc = WordCloud(
        font_path = font_path,
        width = 800,
        height = 600,
        max_words = num_words,
        background_color='ivory'
    )

    # 빈도 리스트를 반영한 wordcloud 생성
    wc = wc.generate_from_frequencies(counter)

    # wordcloud를 matplotlib을 화면에 그리기
    plt.imshow(wc)
    plt.axis('off')
    plt.show()
