from selenium import webdriver
from selenium.webdriver.common.by import By
import time
import pandas as pd
import os
import threading

# =====================================================================
# 설정값
# =====================================================================
OUTPUT_FILE = "cgv_reviews.csv"       # 누적 저장 파일명
VISITED_FILE = "cgv_visited_urls.txt" # 수집 완료 URL 기록 파일

# 제외할 장르 목록
EXCLUDE_GENRES = ["콘서트", "스포츠", "다큐멘터리", "다큐", "공연", "생중계", "라이브"]

# 전역 중단 플래그 (엔터 키 누르면 True로 변경)
stop_flag = False


# =====================================================================
# 엔터 키 입력 감지 함수 (별도 스레드로 실행)
# 엔터 키를 누르면 stop_flag를 True로 변경해서 수집 중단
# =====================================================================
def listen_for_stop():
    global stop_flag
    input("\n[엔터 키를 누르면 수집을 중단하고 저장합니다]\n")
    stop_flag = True
    print("\n중단 신호 감지! 현재 영화 수집 완료 후 저장합니다...")


# =====================================================================
# 크롬 드라이버 초기화 함수
# =====================================================================
def init_driver():
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    # 봇 감지 방지
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(5)
    return driver


# =====================================================================
# 이미 수집한 URL 목록 불러오기
# =====================================================================
def load_visited_urls():
    if os.path.exists(VISITED_FILE):
        with open(VISITED_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    return set()


# =====================================================================
# 수집 완료한 URL 기록 저장
# =====================================================================
def save_visited_url(url):
    with open(VISITED_FILE, "a", encoding="utf-8") as f:
        f.write(url + "\n")


# =====================================================================
# 기존 CSV 불러오기 (누적 저장용)
# =====================================================================
def load_existing_data():
    if os.path.exists(OUTPUT_FILE):
        df = pd.read_csv(OUTPUT_FILE, encoding="utf-8-sig")
        print(f"기존 저장된 리뷰: {len(df):,}개")
        return df.to_dict("records")
    return []


# =====================================================================
# CSV 저장 함수
# =====================================================================
def save_data(all_reviews):
    if all_reviews:
        df = pd.DataFrame(all_reviews)
        df.to_csv(OUTPUT_FILE, index=False, encoding="utf-8-sig")
        print(f"\n저장 완료! 총 {len(all_reviews):,}개 리뷰 → '{OUTPUT_FILE}'")
    else:
        print("저장할 데이터가 없습니다.")


# =====================================================================
# CGV 무비차트 전체 목록에서 영화 URL 수집 함수
# =====================================================================
def get_movie_urls(driver, visited_urls):
    print("\nCGV 홈 접속 중...")
    driver.get("https://cgv.co.kr/")
    time.sleep(3)

    # 팝업 광고 닫기
    try:
        popup_close = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div/div/div[1]/div[2]/div[2]/div/div[2]/button[2]")
        driver.execute_script("arguments[0].click();", popup_close)
        print("팝업 광고 닫기 완료")
        time.sleep(1)
    except:
        print("팝업 없음, 계속 진행")

    # 전체보기 버튼 클릭
    try:
        view_all_btn = driver.find_element(By.XPATH, '//*[@id="contentArea"]/div[4]/div/div/div[1]/div[2]/button')
        driver.execute_script("arguments[0].click();", view_all_btn)
        print("전체보기 버튼 클릭 완료")
        time.sleep(2)
    except Exception as e:
        print(f"전체보기 버튼 클릭 실패: {e}")
        return []

    print("영화 URL 수집 중...")
    movie_urls = []
    movie_index = 1

    while True:
        if stop_flag:
            break

        try:
            detail_btn_xpath = f'//*[@id="contentArea"]/div/div[2]/div/section/div/ul/li[{movie_index}]/div[3]/button[1]'
            detail_btn = driver.find_element(By.XPATH, detail_btn_xpath)

            # 버튼이 보이도록 스크롤 후 JS 클릭
            driver.execute_script("arguments[0].scrollIntoView(true);", detail_btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", detail_btn)
            time.sleep(2)

            current_url = driver.current_url

            # 이미 수집한 URL이면 건너뜀
            if current_url not in visited_urls and current_url not in movie_urls:
                movie_urls.append(current_url)
                print(f"  [{len(movie_urls)}] 수집: {current_url}")

            # 뒤로가기
            driver.back()
            time.sleep(2)

            movie_index += 1

        except:
            print(f"더 이상 영화 없음, 총 {len(movie_urls)}개 URL 수집 완료!")
            break

    return movie_urls


# =====================================================================
# 특정 영화 페이지에서 실관람평 수집 함수
# =====================================================================
def get_reviews(driver, movie_url):
    driver.get(movie_url)
    time.sleep(2)

    # 영화 제목 수집
    try:
        title = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div/div/div[4]/div/div/main/section[1]/div[1]/div/h2/span").text.strip()
    except:
        title = "제목 없음"

    # 장르 확인 (콘서트, 스포츠 등 제외)
    try:
        genre = driver.find_element(By.XPATH, "/html/body/div[1]/div/div/div/div/div[4]/div/div/main/section[1]/div[1]/div/div[1]/span[3]").text.strip()
        print(f"  장르: {genre}")
        if any(g in genre for g in EXCLUDE_GENRES):
            print(f"  → 제외 대상 장르 ({genre}), 건너뜀")
            return []
    except:
        print("  장르 확인 실패, 계속 진행")

    # 실관람평 섹션 확인
    try:
        driver.find_element(By.XPATH, '//*[@id="reviewSection"]/div[3]/div[2]/h2')
    except:
        print("  실관람평 섹션 없음, 건너뜀")
        return []

    # 스크롤 끝까지 내리기 (더 이상 안 내려갈 때까지)
    last_height = driver.execute_script("return document.body.scrollHeight")
    no_change_count = 0
    while True:
        if stop_flag:
            break
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(0.5)
        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            no_change_count += 1
            if no_change_count >= 3:
                break
        else:
            no_change_count = 0
        last_height = new_height

    # 리뷰 텍스트만 수집
    reviews = []
    review_index = 1
    while True:
        try:
            review_xpath = f'//*[@id="reviewSection"]/div[3]/ul/li[{review_index}]/div/div[1]/div[1]/div[1]/div[2]/p'
            review_elem = driver.find_element(By.XPATH, review_xpath)
            text = review_elem.text.strip()
            if len(text) > 2:
                reviews.append({
                    "movie_title": title,
                    "review": text
                })
            review_index += 1
        except:
            break

    return reviews


# =====================================================================
# 메인 실행 함수
# =====================================================================
def main():
    global stop_flag

    # 엔터 키 감지 스레드 시작
    stop_thread = threading.Thread(target=listen_for_stop, daemon=True)
    stop_thread.start()

    driver = init_driver()

    # 기존 데이터 불러오기 (누적 저장)
    all_reviews = load_existing_data()

    # 이미 수집한 URL 불러오기
    visited_urls = load_visited_urls()
    print(f"이미 수집한 영화: {len(visited_urls)}개")

    try:
        # 1단계: 영화 URL 수집
        movie_urls = get_movie_urls(driver, visited_urls)

        if not movie_urls:
            print("새로 수집할 영화가 없습니다.")
            save_data(all_reviews)
            return

        # 2단계: 각 영화에서 실관람평 수집
        for i, url in enumerate(movie_urls):
            if stop_flag:
                print("중단 신호 감지, 수집 종료!")
                break

            print(f"\n[{i+1}/{len(movie_urls)}] 리뷰 수집 중: {url}")
            reviews = get_reviews(driver, url)
            all_reviews.extend(reviews)
            print(f"  → {len(reviews)}개 리뷰 수집 (누적: {len(all_reviews):,}개)")

            # 수집 완료한 URL 기록
            save_visited_url(url)
            time.sleep(1)

        # 3단계: CSV 저장
        save_data(all_reviews)

    except Exception as e:
        print(f"\n오류 발생: {e}")
        print("지금까지 수집한 데이터 저장 중...")
        save_data(all_reviews)

    finally:
        driver.quit()


if __name__ == "__main__":
    main()
    