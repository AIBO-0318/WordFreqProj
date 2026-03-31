from mylib import myTextAnalyzer as ta

# 데이터 로딩
data_filename = '.\data\daum_movie_review.csv'
column = 'review'
corpus = ta.load_corpus_from_csv(data_filename, column)
#print(corpus[:5])

# 토근화 -> 빈도수 추출
from konlpy.tag import Okt
tokenizer = Okt().pos
my_tags = ['Noun', 'Verb', 'Adjective']
my_stopwords = ['영화']
tokens = ta.tokenize_korean_corpus(corpus, tokenizer, my_tags, my_stopwords)
#print(tokens[:10])

counter = ta.analyze_word_freq(tokens)
#print(list(counter.items())[:10])

# 시각화
# 1. 수평 막대그래프
num_words = 20
title = '영화 리뷰'
ylabel = '키워드'
xlabel = '빈도수'
font_path = "c:/Windows/Fonts/malgun.ttf"
ta.visualize_barhgraph(counter, num_words, title, xlabel, ylabel, font_path)

# 2. 워드클라우드
ta.visualize_wordcloud(counter, num_words, font_path)
