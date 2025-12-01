# ✅ 수정된 core/core_utils_ui_api.py

import os
import re
import html
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
from sentence_transformers import SentenceTransformer

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

# === NEW: 도메인 화이트리스트 불러오기 ===
try:
    trusted_domains_file = resource_path("resources/매체사_도메인_정보.xlsx")
    _td_df = pd.read_excel(trusted_domains_file)
    if "도메인" in _td_df.columns:
        trusted_domains = (
            _td_df["도메인"]
            .dropna()
            .astype(str)
            .str.strip()
            .str.lower()
            .tolist()
        )
    else:
        log(f"⚠️ 매체사_도메인_정보.xlsx 에 '도메인' 컬럼 없음, 실제 컬럼: {list(_td_df.columns)}")
        trusted_domains = []
except Exception as e:
    log(f"⚠️ 도메인 화이트리스트 로딩 실패: {e}")
    trusted_domains = []
# === END NEW ===

def clean_text(text, preserve_newline=False):
    if not isinstance(text, str):
        text = str(text)

    # ✅ 第一步：把 HTML 实体解码成真实字符（例如 &#48; -> '0', &nbsp; -> ' ')
    text = html.unescape(text)

    if text.strip().lower() == 'nan':
        return ""
    patterns = [
        r"Video Player", r"Video 태그를 지원하지 않는 브라우저입니다\.",
        r"\d{2}:\d{2}",
        r"[01]\.\d{2}x", 
        r"출처:\s?[^\n]+", 
        r"/\s?\d+\.?\d*"
    ]
    for p in patterns:
        text = re.sub(p, "", text)

    text = re.sub(r"[ㅋㅎㅠㅜ]+", "", text)
    text = re.sub(r"[!?~\.,\-#]{2,}", "", text)
    #删除这行，不要再把实体模式直接清空
    #text = re.sub(r"&[a-z]+;|&#\d+;", "", text) 
    #text = re.sub(r"[\\\xa0\u200b\u3000\u200c_x000D_]", " ", text)
    #正确地处理不可见字符 / 特殊空白
    text = re.sub(r"(\\|\xa0|\u200b|\u3000|\u200c|_x000D_)", " ", text)
    if preserve_newline:
        # 保留换行，只合并多余空白
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)  # 连续3个以上换行变成2个
        return text.strip()
    else:
        return re.sub(r"\s+", " ", text).strip()

def extract_keywords(text, num_keywords=5):
    nouns = okt.nouns(text)
    return " ".join(nouns[:num_keywords])

def extract_first_sentences(text):
    s = text.replace("\r\n", "\n").replace("\r", "\n").strip()

    # ① 优先：空行分段（一个或多个空白行）
    paras = [p.strip() for p in re.split(r'\n\s*\n+', s) if p.strip()]
    # ② 退化：如果只有一段，改用“任意换行”再试一次
    if len(paras) < 2:
        paras = [p.strip() for p in re.split(r'\n+', s) if p.strip()]

    def first_sentence(p: str) -> str:
        if not p: 
            return ""
        parts = re.split(r'(?<=[\.!?。…])["”’\')\]]*\s+', p.strip())
        return (parts[0] if parts and parts[0].strip() else p).strip()

    first  = first_sentence(paras[0]) if len(paras) > 0 else ""
    second = first_sentence(paras[1]) if len(paras) > 1 else ""
    last   = first_sentence(paras[-1]) if len(paras) > 0 else ""

    return first, second, last

MAX_QUERY_LENGTH = 100

def generate_search_queries(title, first, second, last, press):
    def truncate(text): return text[:MAX_QUERY_LENGTH] if text else ""
    title_clean = truncate(clean_text(title))
    first_clean = truncate(clean_text(first))
    second_clean = truncate(clean_text(second))
    last_clean = truncate(clean_text(last))
    keywords = truncate(extract_keywords(title_clean))
    # 匹配到文本最多的依次是：title > first_clean > keywords+press > last_clean > second_clean
    # last_clean大多是结尾的一些版权信息或带“#”的话题标签
    # (label, query) 원본 순서 유지 + 중복 제거
    candidates = [
        ("title_clean",        title_clean),
        ("keywords+press",     f"{keywords} {press}".strip()),
        ("first_clean",        first_clean),
        ("second_clean",       second_clean),
        ("last_clean",         last_clean),
    ]

    seen = set()
    ordered_unique = []
    for label, q in candidates:
        if q and q not in seen:
            ordered_unique.append((label, q))
            seen.add(q)

    # 최대 5개 반환
    return ordered_unique[:5]

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

# === NEW: 블로그 본문에서 URL 추출 + 화이트리스트/신탁 OID 판단 ===
def extract_urls_from_text(text: str):
    """본문에서 URL 추출 (괄호/따옴표 등 꼬리 구두점 제거)"""
    if not isinstance(text, str) or not text.strip():
        return []
    pattern = r'(https?://[^\s)>\]\"\'}]+)'
    urls = re.findall(pattern, text)
    return [u.rstrip(').,"\']>') for u in urls]

def is_whitelisted_domain(url: str) -> bool:
    """매체사 도메인 화이트리스트 여부"""
    # 정확 일치 + 서브도메인만 허용 (ex: etnews.com허용, silvernetnews.com불허용)
    try:
        netloc = _normalize_domain(urlparse(url).netloc)
        return any(
            netloc == d or netloc.endswith("." + d)
            for d in trusted_domains
        )
    except Exception:
        return False

def is_trusted_oid(url: str) -> bool:
    """네이버 신탁 언론 OID 여부"""
    try:
        if "naver.com" not in url:
            return False
        oid = extract_oid_from_naver_url(url)
        if not oid:
            return False
        return (
            oid in trusted_news_oids or
            oid in trusted_sports_oids or
            oid in trusted_entertain_oids
        )
    except Exception:
        return False
# === END NEW ===

# ==== 뉴스 본문 selector 맵핑 ====
selector_map = {
    "n.news.naver.com": "article#dic_area",
    "m.sports.naver.com": "div._article_content",
    "m.entertain.naver.com": "article#comp_news_article div._article_content",
    "m.edaily.co.kr": "div.article_body", # 이데일리 모바일

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
    "yeongnam.com": "div.article-news-body", #46 영남일보
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
    "ilyo.co.kr": "div.contentView", #80 일요신문
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
    "gwangnam.co.kr": "div#content", #104광남일보
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

def _normalize_domain(netloc: str) -> str:
    d = netloc.lower()
    return d[4:] if d.startswith("www.") else d

def _pick_selector(netloc: str, selector_map: dict):
    
    if netloc in selector_map:
        return selector_map[netloc]
    
    nd = _normalize_domain(netloc)
    if nd in selector_map:
        return selector_map[nd]
    
    for key in selector_map:
        if nd.endswith(key):
            return selector_map[key]
    return None

def fallback_with_requests(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code != 200:
            return ""
        if "kookje.co.kr" in url:
            res.encoding = "euc-kr"
        elif res.apparent_encoding:
            res.encoding = res.apparent_encoding
        try:
            # 优先用res.text（如果编码已知或推断出来）
            soup = BeautifulSoup(res.text, "html.parser")
        except Exception:
            # 如果解码失败，fallback到res.content
            soup = BeautifulSoup(res.content, "html.parser")

        # 도메인 기반 selector 선택
        domain = urlparse(url).netloc
        selector =  _pick_selector(domain, selector_map)

        # selector로 본문 추출
        if selector:
            content_div = soup.select_one(selector)
            if content_div:
                for tag in content_div.select("script, style, iframe"):
                    tag.decompose()
                # 关键：保留网页中的换行和段落
                return content_div.get_text(separator="\n", strip=True)

        # fallback: 모든 <p> 태그 결합
        return "\n".join(p.get_text(separator="\n", strip=True) for p in soup.find_all("p"))

    except Exception as e:
        log(f"⚠️ fallback 요청 중 예외 발생: {e} - url: {url}")
        return ""

def calculate_tfidf_copy_ratio(article, post):
    def clean(t): return re.sub(r'\s+', ' ', re.sub(r'[^\w\s]', '', t)).strip()
    article, post = clean(article), clean(post)
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', article) if s.strip()]
    if not sentences:
        return 0.0
    scores = []
    for s in sentences:
        try:
            v = TfidfVectorizer(tokenizer=okt.morphs, token_pattern=None).fit([s, post])
            tfidf = v.transform([s, post])
            scores.append(cosine_similarity(tfidf[0:1], tfidf[1:2])[0][0])
        except:
            continue
    return round(sum(scores)/len(scores), 3) if scores else 0.0

def calculate_sequencematcher_copy_ratio(article, post):
    """
    A: 블로그 (post)
    B: 원문기사 (article)
    복사율: article 중 몇 %가 post에 나오는지(단방향)
    """
    def clean(t):
        if not isinstance(t, str): return ""
        t = re.sub(r'[^\w\s]', '', t)
        t = re.sub(r'\s+', ' ', t)
        return t.strip()

    article_clean = clean(article)
    post_clean = clean(post)

    if not article_clean or not post_clean:
        return 0.0

    matcher = SequenceMatcher(None, post_clean, article_clean)
    matching_blocks = matcher.get_matching_blocks()

    matched_length = sum(block.size for block in matching_blocks if block.size > 0)

    copy_ratio = matched_length / len(article_clean)
    return round(copy_ratio, 3)

# sbert
def split_sentences_korean(text):
    # 简单按句号、问号、感叹号分句
    return [s.strip() for s in re.split(r"[.!?]\s*", text) if s.strip()]

# batch_size: 8,16, 32(32X, 16相对于8，速度提升30%左右)
def calculate_sbert_copy_ratio(article, post, threshold=0.7):
    article = clean_text(article)
    post = clean_text(post)

    article_sents = split_sentences_korean(article)
    post_sents = split_sentences_korean(post)

    if not article_sents or not post_sents:
        return 0.0

    try:
        model = get_krsbert_model()
        art_vecs = model.encode(article_sents, batch_size=16, convert_to_numpy=True, show_progress_bar=False)
        post_vecs = model.encode(post_sents, batch_size=16, convert_to_numpy=True, show_progress_bar=False)

        hit = 0
        for art_vec in art_vecs:
            sims = cosine_similarity([art_vec], post_vecs)[0]
            max_sim = sims.max()
            if max_sim >= threshold:
                hit += 1

        return round(hit / len(article_sents), 3)
    except Exception as e:
        print(f"❌ 相似度计算出错: {e}")
        return 0.0

def is_excluded(url):
    return any(domain in url for domain in excluded_domains)

def search_naver_news_api(queries, index, client_id, client_secret):
    headers = {
        "X-Naver-Client-Id": client_id,
        "X-Naver-Client-Secret": client_secret
    }
    results = []
    # 仅用于避免重复抓取正文；但允许“同一 link 在不同 label 下各保留一条结果”
    body_cache = {}  # link -> body(str) or ""
    added_labels_by_link = {}  # link -> set(labels already added into results)

    for label, q in queries:
        try:
            # display max = 100,
            # naver一个页面上最多二十条，比较了5，10，20，20效果最佳
            # 후보군15개 from minjeong
            url = f"https://openapi.naver.com/v1/search/news.json?query={urllib.parse.quote(q)}&display=15&sort=sim"
            res = requests.get(url, headers=headers)
            time.sleep(0.25)  # API 요청 간 딜레이

            if res.status_code != 200:
                log(f"❌ API 응답 오류 [{res.status_code}] - query({label}): {q}", index)
                log(f"↪ 응답 내용: {res.text}", index)
                continue

            try:
                data = res.json()
            except Exception as e:
                log(f"❌ JSON 파싱 실패: {e} - query({label}): {q}", index)
                log(f"↪ 원본 응답: {res.text[:300]}...", index)
                continue

            for item in data.get("items", []):
                link = item.get("link")
                title = item.get("title")
                if not link or is_excluded(link):
                    continue

                # Naver 도메인 → OID 기반 신탁 필터
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
                # === NEW: 비-Naver 도메인 → 도메인 화이트리스트 필터 ===
                else:
                    if not is_whitelisted_domain(link):
                        log(f"🚫 비신탁 도메인 제외 : {link}", index)
                        continue
                # === END NEW ===

                # 抓正文：只对首次见到的 link 抓取网络；否则复用缓存
                if link not in body_cache:
                    body = fallback_with_requests(link)
                    body_cache[link] = body or ""
                else:
                    body = body_cache[link]
                
                if not body or len(body) <= 300:
                    continue

                if link not in added_labels_by_link:
                    added_labels_by_link[link] = set()

                # 关键：同一 link 在不同 label 下，可以各自添加一条记录
                if label not in added_labels_by_link[link]:
                    results.append({
                        "title": title,
                        "link": link,
                        "body": clean_text(body, preserve_newline=True),
                        "query_label": label,      # 保留 label
                        "query_text": q,           # 新增：保留原始 query 文本（用于核对）
                    })
                    added_labels_by_link[link].add(label)

        except Exception as e:
            log(f"❌ API 요청 중 예외 발생: {e} - query({label}): {q}", index)

    return results

_sbert_model = None
def get_krsbert_model():
    global _sbert_model
    if _sbert_model is None:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _sbert_model = SentenceTransformer("snunlp/KR-SBERT-V40K-klueNLI-augSTS", device=device)
        log(f"✅ KR-SBERT 모델 로딩 완료 - device: {_sbert_model.device}")
    return _sbert_model
