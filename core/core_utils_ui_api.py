# ✅ 수정된 core/core_utils_ui_api.py

import os
import re
import time
import requests
import logging
import urllib.parse
import pandas as pd
from bs4 import BeautifulSoup
from konlpy.tag import Okt
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from datetime import datetime
from urllib.parse import urlparse

import sys
def resource_path(relative_path):
    """兼容PyInstaller和源码运行的资源路径"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

NAVER_CLIENT_ID = os.environ.get("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.environ.get("NAVER_CLIENT_SECRET", "")

# ==== 로그 설정 ====
today = datetime.now().strftime("%y%m%d")
log_dir = resource_path("data/log")
os.makedirs(log_dir, exist_ok=True)
log_path = os.path.join(log_dir, f"로그_{today}.txt")

logger = logging.getLogger()
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler(log_path, encoding="utf-8")
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
if not logger.hasHandlers():
    logger.addHandler(file_handler)

def log(msg, index=None):
    prefix = f"[{index+1:03d}] " if index is not None else ""
    logger.info(f"{prefix}{msg}")

okt = Okt()

# 제외 도메인 불러오기
excluded_domains_file = resource_path("resources/수집 제외 도메인 주소.xlsx")
excluded_domains = pd.read_excel(excluded_domains_file)["제외 도메인 주소"].dropna().tolist()

def clean_text(text):
    if not isinstance(text, str):
        text = str(text)
    if text.strip().lower() == 'nan':
        return ""
    patterns = [
        r"Video Player", r"Video 태그를 지원하지 않는 브라우저입니다\.",
        r"\d{2}:\d{2}", r"[01]\.\d{2}x", r"출처:\s?[^\n]+", r"/\s?\d+\.?\d*"
    ]
    for p in patterns:
        text = re.sub(p, "", text)
    text = re.sub(r"[ㅋㅎㅠㅜ]+", "", text)
    text = re.sub(r"[!?~\.,\-#]{2,}", "", text)
    text = re.sub(r"&[a-z]+;|&#\d+;", "", text)
    text = re.sub(r"[\\\xa0\u200b\u3000\u200c_x000D_]", " ", text)
    return re.sub(r"\s+", " ", text).strip()

def extract_keywords(text, num_keywords=5):
    nouns = okt.nouns(text)
    return " ".join(nouns[:num_keywords])

def extract_first_sentences(text):
    paras = re.split(r'\n{2,}', text.strip())
    get_first = lambda p: re.split(r'(?<=[.!?])(?=\s|[가-힣])', p.strip())[0] if p else ""
    get_last = lambda p: re.split(r'(?<=[.!?])(?=\s|[가-힣])', p.strip())[-1].strip() if p else ""
    first = get_first(paras[0]) if len(paras) > 0 else ""
    second = get_first(paras[1]) if len(paras) > 1 else ""
    last = get_last(paras[-1]) if len(paras) > 0 else ""
    return first, second, last

MAX_QUERY_LENGTH = 100

def generate_search_queries(title, first, second, last, press):
    def truncate(text): return text[:MAX_QUERY_LENGTH] if text else ""
    title_clean = truncate(clean_text(title))
    first_clean = truncate(clean_text(first))
    second_clean = truncate(clean_text(second))
    last_clean = truncate(clean_text(last))
    keywords = truncate(extract_keywords(title_clean))
    queries = list(set(filter(None, [
        title_clean,
        keywords + " " + press,
        first_clean,
        second_clean,
        last_clean
    ])))
    return queries[:5]

def load_trusted_oids():
    def load_oid_from_excel(filename):
        try:
            return set(
                pd.read_excel(filename)["oid"]
                .dropna()
                .astype(int)
                .astype(str)
                .apply(lambda x: x.zfill(3))
            )
        except Exception as e:
            log(f"⚠️ {filename} 로딩 실패: {e}")
            return set()

    news_oids = load_oid_from_excel(resource_path("resources/oid 리스트/네이버뉴스 신탁언론 oid.xlsx"))
    sports_oids = load_oid_from_excel(resource_path("resources/oid 리스트/네이버스포츠 신탁언론 oid.xlsx"))
    entertain_oids = load_oid_from_excel(resource_path("resources/oid 리스트/네이버엔터 신탁언론 oid.xlsx"))
    return news_oids, sports_oids, entertain_oids

trusted_news_oids, trusted_sports_oids, trusted_entertain_oids = load_trusted_oids()

def extract_oid_from_naver_url(link):
    parsed = urlparse(link)
    path = parsed.path
    match = re.search(r"/article/(\d{3})/\d+", path)
    if match:
        return match.group(1)
    match = re.search(r"/mnews/article/(\d{3})/\d+", path)
    if match:
        return match.group(1)
    return None

# ==== 뉴스 본문 selector 맵핑 ====
selector_map = {
    "n.news.naver.com": "article#dic_area",
    "m.sports.naver.com": "div._article_content",
    "m.entertain.naver.com": "article#comp_news_article div._article_content",
    "imbc.com": "div.news_txt[itemprop='articleBody']",
    "ytn.co.kr": "div#CmAdContent",
    "mt.co.kr": "div#textBody[itemprop='articleBody']",
    "heraldcorp.com": "article.article-body#articleText",
    "hankookilbo.com": "div.col-main[itemprop='articleBody']",
    "edaily.co.kr": "div.news_body[itemprop='articleBody']",
    "fnnews.com": "div#article_content",
    "seoul.co.kr": "div#articleContent .viewContent",
    "pressian.com": "div.article_body",
    "kbs.co.kr": "div#cont_newstext",
    "hani.co.kr": "div.article-text",
    "nocutnews.co.kr": "div#pnlContent",
    "asiae.co.kr": "div.article.fb-quotable#txt_area",
    "mediatoday.co.kr": "article#article-view-content-div",
    "khan.co.kr": "div#articleBody",
    "sedaily.com": "div.article_view[itemprop='articleBody']",
    "imaeil.com": "div#articlebody[itemprop='articleBody']",
    "ebn.co.kr": "article#article-view-content-div",
    "kyeongin.com": "div#article-body",
    "obsnews.co.kr": "article#article-view-content-div",
    "incheonilbo.com": "article#article-view-content-div",
}

def fallback_with_requests(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return ""
        soup = BeautifulSoup(res.text, "html.parser")

        # 도메인 기반 selector 선택
        hostname = urlparse(url).hostname or ""
        domain = ".".join(hostname.split('.')[-2:])  # 예: www.ytn.co.kr → ytn.co.kr
        selector = selector_map.get(domain)

        # selector로 본문 추출
        if selector:
            content_div = soup.select_one(selector)
            if content_div:
                return content_div.get_text(strip=True)

        # fallback: 모든 <p> 태그 결합
        return "\n".join(p.get_text(strip=True) for p in soup.find_all("p"))

    except Exception as e:
        log(f"⚠️ fallback 요청 중 예외 발생: {e} - url: {url}")
        return ""

# Load stopwords from external txt file
def load_stopwords():
    stopwords_path = resource_path("resources/stop_word_list.txt")
    if os.path.exists(stopwords_path):
        with open(stopwords_path, "r", encoding="utf-8") as f:
            return set(line.strip() for line in f if line.strip())
        log("✅ stop_word_list.txt Reading complete.")
    else:
        log("⚠️ stop_word_list.txt 파일이 존재하지 않습니다.")
        return set()

STOPWORDS = load_stopwords()

def tokenize_without_stopwords(text):
    tokens = okt.morphs(text)
    return [token for token in tokens if token not in STOPWORDS]

def calculate_copy_ratio(article, post):
    def clean(t): return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', t)).strip()
    article, post = clean(article), clean(post)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', article) if s.strip()]
    if not sentences:
        return 0.0
    scores = []
    for s in sentences:
        try:
            v = TfidfVectorizer(tokenizer=tokenize_without_stopwords).fit([s, post])
            tfidf = v.transform([s, post])
            scores.append(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
        except:
            continue
    return round(sum(scores)/len(scores), 3) if scores else 0.0

def is_excluded(url):
    return any(domain in url for domain in excluded_domains)

def search_naver_news_api(queries, index, client_id, client_secret):
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    results = []
    seen_links = set()

    for q in queries:
        try:
            url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(q)}&display=5&sort=sim"
            res = requests.get(url, headers=headers)
            time.sleep(0.25)  # API 요청 간 딜레이

            if res.status_code != 200:
                log(f"❌ API 응답 오류 [{res.status_code}] - query: {q}", index)
                log(f"↪ 응답 내용: {res.text}", index)
                continue

            try:
                data = res.json()
            except Exception as e:
                log(f"❌ JSON 파싱 실패: {e} - query: {q}", index)
                log(f"↪ 원본 응답: {res.text[:300]}...", index)
                continue

            for item in data.get("items", []):
                link = item.get("link")
                title = item.get("title")
                if not link or link in seen_links or is_excluded(link):
                    continue

                if "naver.com" in link:
                    oid = extract_oid_from_naver_url(link)
                    if not oid:
                        log(f"⚠️ OID 추출 실패 → 스킵: {link}", index)
                        continue
                    if "n.news.naver.com" in link and oid not in trusted_news_oids:
                        continue
                    if "sports.naver.com" in link and oid not in trusted_sports_oids:
                        continue
                    if "entertain.naver.com" in link and oid not in trusted_entertain_oids:
                        continue

                seen_links.add(link)
                body = fallback_with_requests(link)
                if body and len(body) > 300:
                    results.append({"title": title, "link": link, "body": clean_text(body)})

        except Exception as e:
            log(f"❌ API 요청 중 예외 발생: {e} - query: {q}", index)

    return results
