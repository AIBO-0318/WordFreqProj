import sys
sys.stdout.reconfigure(encoding="utf-8")

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException, StaleElementReferenceException, NoSuchElementException
)
import requests
import time
import random
import pickle
import pandas as pd
import csv
import os
import threading
import re
import string
from concurrent.futures import ThreadPoolExecutor, as_completed

# =====================================================================
# 설정값
# =====================================================================
# 로그인 정보는 코드에 직접 적지 않고 환경변수(.env)에서 읽는다.
#   - crawler/.env 파일에  WATCHA_EMAIL=... / WATCHA_PASSWORD=...  로 적어두면 자동 로드
#   - .env 는 .gitignore 처리되어 깃허브에 올라가지 않는다
from _env import load_env
load_env()
EMAIL = os.environ.get("WATCHA_EMAIL", "")
PASSWORD = os.environ.get("WATCHA_PASSWORD", "")

if not EMAIL or not PASSWORD:
    print("[경고] WATCHA_EMAIL / WATCHA_PASSWORD 가 설정되지 않았습니다.")
    print("       crawler/.env 파일에 로그인 정보를 적거나, 저장된 쿠키(watcha_session.pkl)로만 진행됩니다.")

# 수집할 총 영화 개수
MAX_MOVIES = 500

# 시간 제한 (시간 단위)
TIME_LIMIT_HOURS = 24

# 병렬 워커 수 — 같은 계정 쿠키 공유, rate limit 때문에 1이 안정적
N_WORKERS = 1

# API 호출 간 딜레이 (초) — 페이지 넘길 때마다
API_DELAY_MIN = 0.4
API_DELAY_MAX = 0.7

# 영화 간 딜레이 (초)
MOVIE_DELAY_MIN = 1.0
MOVIE_DELAY_MAX = 2.0

# 영화당 최대 코멘트 수 (0 = 무제한)
MAX_COMMENTS_PER_MOVIE = 0

# 연속 요청 N개마다 선제적으로 쉬기 (429 방지)
RATE_LIMIT_BURST = 25       # N번 요청 후
RATE_LIMIT_REST  = 20.0     # 이만큼 쉼 (초)

# -----------------------------------------------------------------------
# 연도별 덱 URL 목록
# -----------------------------------------------------------------------
YEAR_DECK_SOURCES = [
    (2025, "https://pedia.watcha.com/decks/gcdN5E3WyN",       "2025년 극장 영화 순위"),
    (2024, "https://pedia.watcha.com/ko/decks/gcdkWeMBdN",    "2024 개봉 영화 순위"),
    (2023, "https://pedia.watcha.com/decks/gcd98WWogN",       "2023년 영화 순위"),
    (2023, "https://pedia.watcha.com/decks/gcdN1WP6wk",       "2023년 영화 평점 순위"),
    (2022, "https://pedia.watcha.com/ko-KR/decks/gcdNJEX03b", "2022년 영화 순위"),
    (2021, "https://pedia.watcha.com/ko/decks/gcdbRlvyM9",    "2021년 영화 순위"),
    (2021, "https://pedia.watcha.com/decks/gcd9Pjr4Mb",       "2021 개봉작 순위"),
    (2020, "https://pedia.watcha.com/decks/gcdkXlZxok",       "2020 영화순위"),
    (2019, "https://pedia.watcha.com/decks/gcdbYnrGVN",       "2019년 영화 순위"),
    (2018, "https://pedia.watcha.com/decks/gcdbGRnAlk",       "2018년 영화순위"),
    (2017, "https://pedia.watcha.com/decks/gcdbRlnzM9",       "2017년 영화 순위"),
    (2016, "https://pedia.watcha.com/decks/gcd9qzjlmk",       "2016년 영화 순위"),
    (2015, "https://pedia.watcha.com/decks/gcd9zYA78N",       "2015년 영화 순위"),
    (2014, "https://pedia.watcha.com/decks/gcdkyYAvjk",       "2014년 영화 순위"),
    (2013, "https://pedia.watcha.com/decks/gcdbZlDPm9",       "2013년 영화순위"),
    (2012, "https://pedia.watcha.com/decks/gcdkaR7reb",       "2012년 영화 순위"),
    (2011, "https://pedia.watcha.com/decks/gcdNAVnPD9",       "2011년 영화 순위"),
    (2010, "https://pedia.watcha.com/decks/gcd93mZQdb",       "2010년 영화 순위"),
    (2009, "https://pedia.watcha.com/decks/gcdk2EjpL9",       "2009년 영화 순위"),
    (2008, "https://pedia.watcha.com/decks/gcd9KdnEjk",       "2008년 영화 순위"),
    (2007, "https://pedia.watcha.com/decks/gcdNDgwAAb",       "2007년 영화 순위"),
    (2006, "https://pedia.watcha.com/decks/gcdbpnAaJ9",       "2006년 영화 순위"),
    (2005, "https://pedia.watcha.com/decks/gcd9QlKDON",       "2005년 영화 순위"),
    (2004, "https://pedia.watcha.com/decks/gcd9dQo0ok",       "2004년 영화 순위"),
    (0,    "https://pedia.watcha.com/ko-KR/decks/gcd9zQLgaN", "역대 흥행 한국영화 Top200"),
    (0,    "https://pedia.watcha.com/ko-KR/staffmades/gsm872YZNo", "왓챠 평균별점 TOP"),
    (0,    "https://pedia.watcha.com/decks/gcdbpnG8w9",       "IMDB Top Rated Movies 250"),
]

COOKIE_FILE = "watcha_session.pkl"
VISITED_FILE = "visited_urls.txt"
OUTPUT_FILE = "watcha_comments.csv"

# API 기본 URL
API_BASE = "https://pedia.watcha.com"

stop_flag = False
csv_lock = threading.Lock()
visited_lock = threading.Lock()
progress_lock = threading.Lock()

completed_count = 0
total_comment_count = 0
total_movies_count = 0
crawl_start_time = 0
worker_status = {}


# =====================================================================
# 진행 현황 출력
# =====================================================================
def fmt_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def print_progress():
    with progress_lock:
        elapsed = time.time() - crawl_start_time if crawl_start_time else 0
        total = total_movies_count or 1
        done = completed_count

        eta_str = fmt_time((elapsed / done) * (total - done)) if done > 0 else "--:--:--"
        pct = done / total * 100
        bar_len = 28
        filled = int(bar_len * done / total)
        bar = "█" * filled + "░" * (bar_len - filled)

        lines = [
            "┌" + "─" * 53 + "┐",
            f"│  진행  [{bar}] {done}/{total} ({pct:.0f}%)  │",
            f"│  시간  경과 {fmt_time(elapsed)}  │  잔여 예상 {eta_str}  │",
            f"│  코멘트 누적 {total_comment_count:,}개{' ' * max(0, 36 - len(str(total_comment_count)))}│",
        ]
        for wid, status in sorted(worker_status.items()):
            line = f"│  W{wid}  {status}"
            lines.append(line[:55].ljust(55) + "│")
        lines.append("└" + "─" * 53 + "┘")
        print("\n" + "\n".join(lines))


# =====================================================================
# 엔터 키 중단
# =====================================================================
def listen_for_stop():
    global stop_flag
    input("\n[엔터 키를 누르면 수집을 중단합니다]\n")
    stop_flag = True
    print("\n중단 신호 감지! 현재 작업 완료 후 종료합니다...")


# =====================================================================
# 크롬 드라이버 초기화 (URL 수집 전용)
# =====================================================================
_ua_pool = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

def init_driver(worker_id=0):
    options = webdriver.ChromeOptions()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option("useAutomationExtension", False)
    options.add_argument(f"--user-agent={_ua_pool[worker_id % len(_ua_pool)]}")
    options.add_argument("--window-size=1366,900")
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.fonts": 2,
        "profile.managed_default_content_settings.media_stream": 2,
    }
    options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=options)
    driver.implicitly_wait(3)
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    })
    return driver


# =====================================================================
# 쿠키 저장 / 불러오기
# =====================================================================
def save_cookies(driver):
    pickle.dump(driver.get_cookies(), open(COOKIE_FILE, "wb"))
    print(f"쿠키 저장 완료 → {COOKIE_FILE}")


def load_cookies(driver):
    if not os.path.exists(COOKIE_FILE):
        return False
    driver.get("https://pedia.watcha.com/ko-KR")
    time.sleep(1.5)
    for cookie in pickle.load(open(COOKIE_FILE, "rb")):
        try:
            driver.add_cookie(cookie)
        except Exception:
            pass
    driver.refresh()
    time.sleep(2)
    return True


def is_logged_in(driver):
    try:
        driver.find_element(
            By.XPATH,
            "//a[contains(@href, '/ko/profile') or contains(@href, '/ko-KR/profile')]"
        )
        return True
    except NoSuchElementException:
        pass
    try:
        driver.find_element(By.XPATH, "//li[contains(@class,'SignIn') or .//a[contains(@href,'sign_in')]]")
        return False
    except NoSuchElementException:
        return True


def is_login_page(driver):
    url = driver.current_url
    return "sign_in" in url or "login" in url.lower()


# =====================================================================
# 로그인
# =====================================================================
def login(driver):
    print("로그인 중...")
    driver.get("https://pedia.watcha.com/ko-KR")
    time.sleep(2)
    try:
        login_btn = driver.find_element(
            By.XPATH, "/html/body/div[1]/header[1]/nav/section/ul/li[8]"
        )
        login_btn.click()
        time.sleep(1.5)

        email_login_btn = driver.find_element(
            By.XPATH, "/html/body/div[1]/main/div/div/section/div[1]/div[6]"
        )
        email_login_btn.click()
        time.sleep(1.5)

        driver.find_element(By.NAME, "email").send_keys(EMAIL)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(1)

        driver.find_element(By.NAME, "password").send_keys(PASSWORD)
        driver.find_element(By.XPATH, "//button[@type='submit']").click()
        time.sleep(3)

        print("로그인 완료!")
        return True
    except Exception as e:
        print(f"로그인 실패: {e}")
        return False


# =====================================================================
# 방문 URL 관리
# =====================================================================
def load_visited_urls():
    if os.path.exists(VISITED_FILE):
        with open(VISITED_FILE, "r", encoding="utf-8") as f:
            return set(f.read().splitlines())
    return set()


def save_visited_url(url):
    with visited_lock:
        with open(VISITED_FILE, "a", encoding="utf-8") as f:
            f.write(url + "\n")


# =====================================================================
# CSV 저장 (스레드 안전)
# =====================================================================
def load_existing_data():
    if os.path.exists(OUTPUT_FILE) and os.path.getsize(OUTPUT_FILE) > 0:
        try:
            df = pd.read_csv(OUTPUT_FILE, encoding="utf-8-sig", escapechar="\\",
                             on_bad_lines="skip")
            print(f"기존 저장된 코멘트: {len(df):,}개")
            return df
        except Exception as e:
            print(f"CSV 읽기 실패 ({e}) — 새로 시작합니다")
    return pd.DataFrame()


def append_to_csv(new_rows):
    """CSV에 새 행 추가. mode='a'로 기존 데이터를 절대 덮어쓰지 않음."""
    with csv_lock:
        if not new_rows:
            return
        df_new = pd.DataFrame(new_rows)
        write_header = (not os.path.exists(OUTPUT_FILE)
                        or os.path.getsize(OUTPUT_FILE) == 0)
        df_new.to_csv(
            OUTPUT_FILE, mode="a", index=False, encoding="utf-8-sig",
            header=write_header, quoting=csv.QUOTE_ALL, escapechar="\\",
        )


# =====================================================================
# API 세션 (requests 기반, 코멘트 수집 전용)
# =====================================================================
def _gen_device_id():
    """브라우저가 생성하는 방식의 device identifier 생성."""
    chars = string.ascii_letters + string.digits
    rand = "".join(random.choices(chars, k=30))
    return f"web-{rand}"


def make_api_session(worker_id=0):
    """쿠키 + frograms 헤더가 설정된 requests.Session 반환."""
    session = requests.Session()

    if os.path.exists(COOKIE_FILE):
        for c in pickle.load(open(COOKIE_FILE, "rb")):
            session.cookies.set(c["name"], c["value"], domain=c.get("domain", ""))

    session.headers.update({
        "accept": "application/vnd.frograms+json;version=2.1.0",
        "x-frograms-app-code": "Galaxy",
        "x-frograms-client": "Galaxy-Web-App",
        "x-frograms-client-version": "2.1.0",
        "x-frograms-device-identifier": _gen_device_id(),
        "x-frograms-galaxy-language": "ko",
        "x-frograms-version": "2.1.0",
        "User-Agent": _ua_pool[worker_id % len(_ua_pool)],
    })
    return session


def _extract_movie_code(movie_url):
    """URL에서 영화 코드 추출. 예: .../ko/contents/mOgjjzA → mOgjjzA"""
    parts = movie_url.rstrip("/").split("/")
    return parts[-1]


def get_movie_title_api(session, movie_code):
    """API로 영화 제목 조회."""
    try:
        url = f"{API_BASE}/api/contents/{movie_code}"
        r = session.get(
            url,
            headers={"Referer": f"{API_BASE}/ko/contents/{movie_code}"},
            timeout=10,
        )
        if r.status_code == 200:
            result = r.json().get("result", {})
            title = result.get("title", "")
            year = result.get("year", "")
            return f"{title} ({year})" if year else title
    except Exception:
        pass
    return "제목 없음"


def get_comments_via_api(session, movie_url, worker_id=0, movie_title=""):
    """
    API로 영화 전체 코멘트 수집.
    반환: [{"movie_title": ..., "comment": ...}, ...]
    """
    movie_code = _extract_movie_code(movie_url)
    referer = f"{API_BASE}/ko/contents/{movie_code}/comments"

    # 제목이 없으면 API로 한 번만 조회
    if not movie_title:
        movie_title = get_movie_title_api(session, movie_code)
    title = movie_title
    print(f"  [W{worker_id}] {title} 코멘트 수집 중...")

    comments = []
    next_uri = f"/api/contents/{movie_code}/comments?filter=all&order=popular&size=30"
    page = 0
    retry_count = 0
    req_count = 0          # 연속 요청 카운터 (선제적 속도 제한용)

    while next_uri and not stop_flag:
        # 최대 코멘트 도달 시 조기 종료
        if MAX_COMMENTS_PER_MOVIE and len(comments) >= MAX_COMMENTS_PER_MOVIE:
            break

        # 선제적 속도 제한: RATE_LIMIT_BURST번마다 미리 쉬어서 429 방지
        if req_count > 0 and req_count % RATE_LIMIT_BURST == 0:
            rest = RATE_LIMIT_REST + random.uniform(0, 5)
            print(f"  [W{worker_id}] 선제 대기 {rest:.0f}s (요청 {req_count}번 완료)")
            time.sleep(rest)

        url = API_BASE + next_uri
        if "size=" not in next_uri:
            url += "&size=30"
        try:
            r = session.get(url, headers={"Referer": referer}, timeout=15)
        except requests.exceptions.RequestException as e:
            print(f"  [W{worker_id}] 요청 오류: {e}")
            break

        if r.status_code == 429:
            retry_count += 1
            wait = min(30 * retry_count, 90) + random.uniform(0, 15)
            print(f"  [W{worker_id}] 429 → {wait:.0f}s 대기 (시도 {retry_count})")
            time.sleep(wait)
            req_count = 0   # 429 후 카운터 리셋
            continue

        retry_count = 0
        req_count += 1

        if r.status_code != 200:
            print(f"  [W{worker_id}] API 오류 {r.status_code} — 중단")
            break

        try:
            data = r.json()
            result = data["result"]
            page_comments = result.get("result", [])
            next_uri = result.get("next_uri")
        except Exception as e:
            print(f"  [W{worker_id}] 응답 파싱 오류: {e}")
            break

        for item in page_comments:
            text = item.get("text", "").strip()
            if len(text) <= 2 or "http" in text:
                continue
            comments.append({"movie_title": title, "comment": text})

        page += 1
        time.sleep(random.uniform(API_DELAY_MIN, API_DELAY_MAX))

    print(f"  [W{worker_id}] {title} — {len(comments)}개 ({page}페이지)")
    return comments


# =====================================================================
# 연도별 인기 순위 영화 URL 수집 (Selenium)
# =====================================================================
def _load_all_from_deck(driver, deck_url, wanted, already_collected, visited_urls):
    print(f"    덱 페이지 접속: {deck_url}")
    driver.get(deck_url)
    time.sleep(2.5)

    if is_login_page(driver):
        print(f"    로그인 페이지 리다이렉트 → 세션 만료")
        return []

    click_count = 0
    while True:
        more_btn = None
        try:
            candidates = driver.find_elements(
                By.XPATH,
                "//button[contains(text(),'더보기') or contains(text(),'더 보기')]"
                " | //a[contains(text(),'더보기') or contains(text(),'더 보기')]"
            )
            for c in candidates:
                if c.is_displayed() and c.is_enabled():
                    more_btn = c
                    break
        except Exception:
            pass

        if more_btn is None:
            break

        try:
            driver.execute_script("arguments[0].scrollIntoView(true);", more_btn)
            time.sleep(0.3)
            driver.execute_script("arguments[0].click();", more_btn)
            click_count += 1
            time.sleep(1.2)
        except Exception:
            break

        if click_count > 50:
            break

    if click_count > 0:
        print(f"    더보기 {click_count}회 클릭 → 전체 로드 완료")

    url_title_pairs = []
    all_taken = set(visited_urls) | set(already_collected)
    seen_hrefs = set()
    try:
        links = driver.find_elements(By.XPATH, "//a[contains(@href, '/ko/contents/')]")
        for link in links:
            try:
                href = link.get_attribute("href")
            except StaleElementReferenceException:
                continue
            if not href:
                continue
            path = href.replace("https://pedia.watcha.com", "").strip("/")
            parts = path.split("/")
            if len(parts) != 3 or parts[0] != "ko" or parts[1] != "contents":
                continue
            if href in all_taken or href in seen_hrefs:
                continue
            seen_hrefs.add(href)
            # 링크 텍스트에서 제목 추출 (없으면 빈 문자열)
            try:
                title = link.text.strip().split("\n")[0] or ""
            except Exception:
                title = ""
            url_title_pairs.append((href, title))
            if len(url_title_pairs) >= wanted:
                break
    except Exception as e:
        print(f"    URL 추출 오류: {e}")

    print(f"    {len(url_title_pairs)}개 URL 추출")
    return url_title_pairs


def get_year_based_movie_urls(driver, total_movies, visited_urls):
    print(f"\n연도별 인기 영화 URL 수집 시작 (목표: {total_movies}개)")

    all_urls = []   # (url, year, title) 튜플
    already = []    # 중복 방지용 url 목록

    for year, deck_url, desc in YEAR_DECK_SOURCES:
        if len(all_urls) >= total_movies:
            break

        remaining = total_movies - len(all_urls)
        print(f"\n  [{year if year else '기타'}] {desc} ({remaining}개 필요)")

        pairs = _load_all_from_deck(driver, deck_url, remaining, already, visited_urls)

        for url, title in pairs:
            if url not in already:
                all_urls.append((url, year, title))
                already.append(url)

        print(f"  누적: {len(all_urls)}개")

    print(f"\n총 {len(all_urls)}개 영화 URL 수집 완료")
    return all_urls[:total_movies]


# =====================================================================
# 워커 함수 (requests API 기반)
# =====================================================================
def _set_worker_status(worker_id, status):
    worker_status[worker_id] = status


def worker_run(url_year_chunk, worker_id, start_time, time_limit_seconds):
    global completed_count, total_comment_count

    # 워커 시작 시점 분산 (동시 burst 방지)
    time.sleep(worker_id * 3)

    session = make_api_session(worker_id)
    _set_worker_status(worker_id, "준비 완료")

    total_chunk = len(url_year_chunk)
    for idx, (url, year, deck_title) in enumerate(url_year_chunk, 1):
        if stop_flag:
            break
        if time.time() - start_time >= time_limit_seconds:
            _set_worker_status(worker_id, "시간 제한 도달")
            break

        label = deck_title or url.split("/")[-1]
        _set_worker_status(worker_id, f"[{idx}/{total_chunk}] {label[:20]}")

        comments = get_comments_via_api(session, url, worker_id, movie_title=deck_title)

        if comments:
            for c in comments:
                c["release_year"] = year
            append_to_csv(comments)
            save_visited_url(url)

            with progress_lock:
                completed_count += 1
                total_comment_count += len(comments)

            title_short = comments[0]["movie_title"][:20]
            _set_worker_status(worker_id, f"[{idx}/{total_chunk}] ✓ {title_short} ({len(comments)}개)")
            print_progress()
        else:
            with progress_lock:
                completed_count += 1
            _set_worker_status(worker_id, f"[{idx}/{total_chunk}] 코멘트 없음 — 건너뜀")
            print_progress()

        time.sleep(random.uniform(MOVIE_DELAY_MIN, MOVIE_DELAY_MAX))

    _set_worker_status(worker_id, "완료")


# =====================================================================
# 주기적 현황 출력 스레드
# =====================================================================
def periodic_status_printer():
    while not stop_flag:
        time.sleep(60)
        if not stop_flag and completed_count < total_movies_count:
            print_progress()


# =====================================================================
# 메인
# =====================================================================
def main():
    global stop_flag, total_movies_count, crawl_start_time, total_comment_count

    threading.Thread(target=listen_for_stop, daemon=True).start()
    threading.Thread(target=periodic_status_printer, daemon=True).start()

    crawl_start_time = time.time()
    start_time = crawl_start_time
    time_limit_seconds = TIME_LIMIT_HOURS * 3600

    existing = load_existing_data()
    if not existing.empty and "comment" in existing.columns:
        total_comment_count = len(existing)

    visited_urls = load_visited_urls()
    print(f"이미 수집한 영화: {len(visited_urls)}개")

    # Selenium은 URL 수집에만 사용
    main_driver = init_driver(worker_id=0)

    try:
        if os.path.exists(COOKIE_FILE):
            if load_cookies(main_driver) and is_logged_in(main_driver):
                print("쿠키로 로그인 완료!")
            else:
                if not login(main_driver):
                    print("로그인 실패")
                    return
                save_cookies(main_driver)
        else:
            if not login(main_driver):
                print("로그인 실패")
                return
            save_cookies(main_driver)

        url_year_list = get_year_based_movie_urls(main_driver, MAX_MOVIES, visited_urls)
        main_driver.quit()

        if not url_year_list:
            print("수집할 영화가 없습니다.")
            return

        total_movies_count = len(url_year_list)

        chunks = [url_year_list[i::N_WORKERS] for i in range(N_WORKERS) if url_year_list[i::N_WORKERS]]
        print(f"\n총 {total_movies_count}개 영화 → {N_WORKERS}개 워커 병렬 API 수집")
        print(f"{'─'*55}")
        print_progress()
        print()

        with ThreadPoolExecutor(max_workers=N_WORKERS) as executor:
            futures = [
                executor.submit(worker_run, chunk, wid, start_time, time_limit_seconds)
                for wid, chunk in enumerate(chunks)
                if chunk
            ]
            for f in as_completed(futures):
                try:
                    f.result()
                except Exception as e:
                    print(f"워커 오류: {e}")

    except Exception as e:
        print(f"\n오류 발생: {e}")
    finally:
        try:
            main_driver.quit()
        except Exception:
            pass

    if os.path.exists(OUTPUT_FILE):
        df = pd.read_csv(OUTPUT_FILE, encoding="utf-8-sig", escapechar="\\")
        print(f"\n완료! 총 {len(df):,}개 코멘트 → '{OUTPUT_FILE}'")
        if "release_year" in df.columns:
            print("\n[연도별 수집 현황]")
            print(df.groupby("release_year")["movie_title"].nunique().to_string())


if __name__ == "__main__":
    main()
