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
from difflib import SequenceMatcher

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

    "edaily.co.kr": "div.news_body", # 1 이데일리
    "mt.co.kr": "div#textBody", # 2 머니투데이
    "fnnews.com": "div#article_content",  # 3 파이낸셜뉴스
    "khan.co.kr": "div#articleBody", # 4 경향신문
    "sedaily.com": "div.article_view", # 5 서울경제
    "dailian.co.kr": "div.article", # 6 데일리안
    "news.bizwatch.co.kr": "div.news_body.new_editor", # 7 비즈워치
    "asiae.co.kr": "div#txt_area",  # 8 아시아경제
    "kmib.co.kr": "div#articleBody", # 9 국민일보
    "biz.heraldcorp.com": "article#articleText", #10 헤럴드경제
    "newspim.com": "div#news-contents", #11 뉴스핌
    "hani.co.kr": "div.article-text", #12 한겨레
    "nocutnews.co.kr": "div#pnlContent", #13 노컷뉴스
    "ytn.co.kr": "div#CmAdContent",  #14 YTN
    "segye.com": "div#article_txt", #15 세계일보
    #"hankookilbo.com": "div.col-main", #16 한국일보
    "seoul.co.kr": "div.viewContent.body18.color700", #17 서울신문
    "imbc.com": "div.news_txt", #18 MBC
    "cctimes.kr": "div#article-view-content-div", #19 충청타임즈
    "busan.com": "div.article_content", #20 부산일보
    "sbs.co.kr": "div.text_area", #21 SBS
    "kbs.co.kr": "div#cont_newstext", #22 KBS
    "etoday.co.kr": "div.articleView", #23 이투데이
    "breaknews.com": "div#CLtag", #24 BreakNews
    "koreaherald.com": "article#articleText", #25 코리아헤럴드
    "incheonilbo.com": "article#article-view-content-div", #26 인천일보
    "etnews.com": "div#articleBody", #27 전자신문
    "kookje.co.kr": "div.news_article", #28 국제신문
    "ajunews.com": "div#articleBody", #29 아주경제
    "imaeil.com": "div#articlebody", #30 매일신문
    "kyeonggi.com": "div.article_cont_wrap", #31 경기일보
    "ggilbo.com": "article.article-veiw-body", #32 금강일보
    "domin.co.kr": "div#article-view-content-div",#33 전북도민일보
    "asiatoday.co.kr": "div#font", #34 아시아투데이
    "kado.net": "article.article-veiw-body", #35 강원도민일보
    "mbn.co.kr": "div#newsViewArea", #36 MBN
    "ksilbo.co.kr": "article.article-veiw-body", #37 경상일보
    "joongboo.com": "article.article-veiw-body", #38 중부일보
    "jbnews.com": "article.article-veiw-body", #39 중부매일
    "kwangju.co.kr": "div#joinskmbox", #40 광주일보
    "kwnews.co.kr": "div#articlebody", #41 강원일보
    "economist.co.kr": "div#article_body", #42 이코노미스트
    "sports.khan.co.kr": "div#articleBody",#43 스포츠경향
    "kgnews.co.kr": "div#news_body_area", #44 경기신문
    "nongmin.com": "div.news_txt.ck-content", #45 농민신문
    "yeongnam.com": "article.article-news-box", #46 영남일보
    "sisain.co.kr": "article.article-veiw-body", #47 시사IN
    "isplus.com": "div#article_body", #48 일간스포츠
    "inews365.com": "div.article", #49 충북일보
    "daejonilbo.com": "article.article-veiw-body", #50 대전일보
    "kihoilbo.co.kr": "article.article-veiw-body", #51 기호일보
    "newspenguin.com": "article.article-veiw-body", #52 뉴스펭귄
    "mediatoday.co.kr": "article.article-veiw-body", #53 미디어오늘
    "mdilbo.com": "div.article_view", #54 무등일보
    "kyeongin.com": "div#article-body", #55 경인일보
    "gnnews.co.kr": "div.news_text", #56 경남일보
    "sportsseoul.com": "div#article-body", #57 스포츠서울
    "idaegu.co.kr": "div.news_text", #58 대구신문
    "idaegu.com": "article.article-veiw-body", #59 대구일보
    "idomin.com": "article.article-veiw-body", #60 경남도민일보
    "namdonews.com": "article.article-veiw-body", #61 남도일보
    "obsnews.co.kr": "article.article-veiw-body", #62 OBS
    "kyongbuk.co.kr": "article.article-veiw-body", #63 경북일보
    "knnews.co.kr": "div.cont_cont", #64 경남신문
    "sports.hankooki.com": "article.article-veiw-body", #65 스포츠한국
    "jjan.kr": "div.article_txt_container", #66 전북일보
    "joongdo.co.kr": "div#font", #67 중도일보
    "hidomin.com": "div#article-view-content-div", #68 경북도민일보
    "naeil.com": "div.article-view", #69 내일신문
    "kjdaily.com": "div#content", #70 광주매일신문
    "cctoday.co.kr": "article.article-veiw-body", #71 충청투데이
    "jnilbo.com": "div#content", #72 전남일보
    "viva100.com": "div.news_content", #73 브릿지경제
    "sportsworldi.com": "article.viewBox2", #74 스포츠월드
    "sjbnews.com": "span.news_text.cl6.p-b-25", #75 새전북신문
    "dynews.co.kr": "article.article-veiw-body", #76 동양일보
    "iusm.co.kr": "article.article-veiw-body", #77 울산매일
    "dnews.co.kr": "div.text", #78 e대한경제
    "hellodd.com": "article.article-veiw-body", #79 헬로디디
    "ilyo.co.kr": "div.contentView.ctl-font-ty2.editorType2", #80 일요신문
    "ccdailynews.com": "article.article-veiw-body", #81 충청일보
    "djtimes.co.kr": "article.article-veiw-body", #82 당진시대
    "hkbs.co.kr": "article.article-veiw-body", #83 환경일보
    "h21.hani.co.kr": "div.arti-txt.0", #84 한겨레21
    "ihalla.com": "div.article_txt", #85 한라일보
    "ulsanpress.net": "article.article-veiw-body", #86 울산신문
    "jejunews.com": "div#article-view-content-div", #87 제주일보
    "wonjutoday.co.kr": "article.article-veiw-body", #88 원주투데이
    "kbmaeil.com": "div.news_content", #89 경북매일신문
    "weekly.hankooki.com": "article.article-veiw-body", #90 주간한국
    "yjinews.com": "article.article-veiw-body", #91 영주시민신문
    "ebn.co.kr": "article.article-veiw-body", #92 EBN산업뉴스
    "kidshankook.kr": "article.article-veiw-body", #93 소년한국일보
    "journalist.or.kr": "div#news_body_area", #94 기자협회보
    "jeollailbo.com": "article.article-veiw-body", #95 전라일보
    "jemin.com": "article.article-veiw-body", #96 제민일보
    "kukinews.com": "div#articleContent", #97 쿠키뉴스
    "ekn.kr": "div#news_body_area_contents", #98 에너지경제
    "pttimes.com": "article.article-veiw-body", #99 평택시민신문
    "mediapen.com": "div#articleBody", #100미디어펜
    "koreatimes.com": "div#print_arti", #101코리아타임스
    "okinews.com": "div#article-view-content-div", #102옥천신문
    "igimpo.com": "article.article-veiw-body", #103김포신문
    #"gwangnam.co.kr": "div#content", #104광남일보
    "pdjournal.com": "article.article-veiw-body", #105PD저널
    "pennmike.com": "article.article-veiw-body", #106펜앤드마이크
    "hsnews.co.kr": "article.article-veiw-body", #107홍성신문
    "metroseoul.co.kr": "div.col-12", #108메트로경제
    "pressian.com": "div.article_body", #109프레시안
    "womaneconomy.co.kr": "article.article-veiw-body", #110여성경제신문
    #"wooriy.com": "", #111영암우리신문
    "gynet.co.kr": "div#article-view-content-div", #112광양신문
    "newssc.co.kr": "div#article-view-content-div", #113뉴스서천
    "kidkangwon.co.kr": "div#article-view-content-div", #114어린이강원
    "mygoyang.com": "article.article-veiw-body", #115주간고양신문
    "soraknews.co.kr": "td#ct", #116주간설악신문
    "seoulwire.com": "article.article-veiw-body", #117서울와이어
}

def fallback_with_requests(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return ""
        soup = BeautifulSoup(res.text, "html.parser")

        # 도메인 기반 selector 선택
        domain = urlparse(url).netloc
        selector = selector_map.get(domain)

        # selector로 본문 추출
        if selector:
            content_div = soup.select_one(selector)
            if content_div:
                for tag in content_div.select("script, style, iframe"):
                    tag.decompose()
                return content_div.get_text(strip=True)

        # fallback: 모든 <p> 태그 결합
        return "\n".join(p.get_text(separator="\n", strip=True) for p in soup.find_all("p"))

    except Exception as e:
        log(f"⚠️ fallback 요청 중 예외 발생: {e} - url: {url}")
        return ""

def calculate_copy_ratio(article, post):
    def clean(t): return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', t)).strip()
    article, post = clean(article), clean(post)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', article) if s.strip()]
    if not sentences:
        return 0.0
    scores = []
    for s in sentences:
        try:
            v = TfidfVectorizer(tokenizer=okt.morphs).fit([s, post])
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
