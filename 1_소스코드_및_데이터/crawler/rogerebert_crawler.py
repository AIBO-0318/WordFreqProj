"""
rogerebert.com 영화 리뷰 크롤러
- title, review_text 만 CSV로 저장 (감정분석·워드클라우드용)
- HTML 구조를 자동 감지해서 본문 추출

설치: py -m pip install selenium webdriver-manager beautifulsoup4
실행: py rogerebert_crawler.py
"""

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup, Tag
import csv, time, random, logging
from pathlib import Path

# ── 설정 ───────────────────────────────────────────────────
MAX_PAGES  = 5          # 수집할 목록 페이지 수 (페이지당 약 20개)
DELAY      = (1.5, 2.5) # 요청 간 랜덤 딜레이 (초)
OUTPUT_CSV = Path("rogerebert_reviews.csv")

BASE_URL = "https://www.rogerebert.com"
LIST_URL = "https://www.rogerebert.com/reviews"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)


# ── 드라이버 ───────────────────────────────────────────────
def make_driver():
    opt = Options()
    opt.add_argument("--headless=new")
    opt.add_argument("--no-sandbox")
    opt.add_argument("--disable-dev-shm-usage")
    opt.add_argument("--window-size=1920,1080")
    opt.add_argument(
        "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    opt.add_experimental_option("excludeSwitches", ["enable-automation"])
    opt.add_experimental_option("useAutomationExtension", False)
    svc = Service(ChromeDriverManager().install())
    drv = webdriver.Chrome(service=svc, options=opt)
    drv.execute_cdp_cmd(
        "Page.addScriptToEvaluateOnNewDocument",
        {"source": "Object.defineProperty(navigator,'webdriver',{get:()=>undefined})"},
    )
    return drv


def sleep():
    time.sleep(random.uniform(*DELAY))


# ── 목록 페이지 → 링크 수집 ────────────────────────────────
def get_links(drv, page: int) -> list[str]:
    url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"
    log.info("목록 %d페이지: %s", page, url)
    drv.get(url)
    try:
        WebDriverWait(drv, 12).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "a[href*='/reviews/']"))
        )
    except Exception:
        log.warning("  로드 타임아웃")
    sleep()

    soup = BeautifulSoup(drv.page_source, "html.parser")
    seen, links = set(), []
    for a in soup.select("a[href*='/reviews/']"):
        href = a.get("href", "")
        # 목록·태그 페이지 제외, 순수 리뷰 URL만
        if not href or href == "/reviews" or "?" in href or "#" in href:
            continue
        full = BASE_URL + href if href.startswith("/") else href
        if full not in seen:
            seen.add(full)
            links.append(full)
    log.info("  → %d개 링크", len(links))
    return links


# ── 본문 추출 핵심 함수 ────────────────────────────────────
# rogerebert.com은 React/Next.js 기반으로 클래스명이 동적일 수 있음.
# 아래 전략을 순서대로 시도한다.
BODY_SELECTORS = [
    # 1) schema.org 마크업
    "[itemprop='reviewBody']",
    # 2) 일반적인 rogerebert 클래스 패턴
    ".review-page",
    ".article-content",
    ".post-content",
    ".entry-content",
    # 3) article 태그 내 첫 번째 div (긴 텍스트 포함)
    "article",
    # 4) main 영역
    "main",
]

JUNK_TAGS = ["script", "style", "aside", "figure", "nav", "header",
             "footer", "form", "button", "iframe", "noscript"]


def extract_body(soup: BeautifulSoup) -> str:
    """본문 텍스트를 여러 선택자로 시도해 추출."""
    for sel in BODY_SELECTORS:
        tag = soup.select_one(sel)
        if not tag:
            continue
        # 불필요한 태그 제거
        for junk in tag(JUNK_TAGS):
            junk.decompose()
        text = tag.get_text(separator="\n", strip=True)
        # 너무 짧으면 다음 선택자 시도 (광고·메뉴일 가능성)
        if len(text) > 300:
            return text
    return ""


# ── 개별 리뷰 파싱 ─────────────────────────────────────────
def parse_review(drv, url: str) -> dict | None:
    drv.get(url)
    try:
        WebDriverWait(drv, 12).until(
            EC.presence_of_element_located((By.TAG_NAME, "h1"))
        )
    except Exception:
        pass
    sleep()

    soup = BeautifulSoup(drv.page_source, "html.parser")

    # 제목
    title = ""
    for sel in ["h1.review-title", "h1[itemprop='name']", ".article-title h1", "h1"]:
        t = soup.select_one(sel)
        if t:
            title = t.get_text(strip=True)
            break
    if not title:
        return None

    # 본문
    review_text = extract_body(soup)

    if not review_text:
        # 최후 수단: 가장 긴 <p> 묶음
        paragraphs = [p.get_text(strip=True) for p in soup.find_all("p") if len(p.get_text(strip=True)) > 80]
        review_text = "\n\n".join(paragraphs)

    return {"title": title, "review_text": review_text}


# ── CSV 저장 ───────────────────────────────────────────────
def save_csv(rows: list[dict], path: Path):
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=["title", "review_text"])
        w.writeheader()
        w.writerows(rows)
    log.info("저장 완료 → %s  (%d개)", path, len(rows))


# ── 메인 ──────────────────────────────────────────────────
def main():
    drv = make_driver()
    try:
        # 1) 링크 수집
        all_links: list[str] = []
        for p in range(1, MAX_PAGES + 1):
            all_links.extend(get_links(drv, p))
        all_links = list(dict.fromkeys(all_links))  # 중복 제거
        log.info("총 링크: %d개", len(all_links))

        # 2) 리뷰 파싱
        rows: list[dict] = []
        for i, url in enumerate(all_links, 1):
            log.info("[%d/%d] %s", i, len(all_links), url)
            rv = parse_review(drv, url)
            if rv and rv["review_text"]:
                rows.append(rv)
                preview = rv["review_text"][:80].replace("\n", " ")
                log.info("  ✓ %s | 본문 %d자 | %.80s…", rv["title"], len(rv["review_text"]), preview)
            else:
                log.warning("  ✗ 본문 추출 실패: %s", url)
                # 실패한 URL의 HTML을 디버그 파일로 저장 (첫 번째만)
                if i == 1:
                    Path("debug_page.html").write_text(drv.page_source, encoding="utf-8")
                    log.info("  디버그 HTML 저장 → debug_page.html")

        log.info("파싱 완료: %d/%d개 성공", len(rows), len(all_links))

        # 3) 저장
        if rows:
            save_csv(rows, OUTPUT_CSV)

            # 미리보기
            print("\n─── 미리보기 (최대 3개) ───")
            for rv in rows[:3]:
                print(f"\n📽  {rv['title']}")
                print(rv["review_text"][:400])
                print("─" * 60)
        else:
            log.error("수집된 데이터가 없습니다. debug_page.html을 확인하세요.")

    finally:
        drv.quit()


if __name__ == "__main__":
    main()
    