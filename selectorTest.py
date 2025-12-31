# selector mapping validation
# 选择器测试脚本
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import os

selector_map = {
    "n.news.naver.com": "article#dic_area",
    "m.sports.naver.com": "div._article_content",
    "m.entertain.naver.com": "article#comp_news_article div._article_content",
    "m.newspim.com": "div#viewcontents", #뉴스핌 모바일
    "m.sedaily.com": "div.article",
    "m.segye.com": "div.viewCont", #세계일보 모바일


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
    #"hankookilbo.com": "div.end-body", #16 한국일보
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

    "news.hidoc.co.kr": "article.article-veiw-body", #除外
    "newstown.co.kr": "div#_article", 
    "blog.naver.com": "div.se-main-container",

    ###매일경제 중앙일보
    "mk.co.kr": "div.news_cnt_detail_wrap",
    "joongang.co.kr": "div#article_body.article_body.fs3",
}


example_urls = {
    "sports.khan.co.kr": "https://sports.khan.co.kr/article/202511281252003/?utm_source=urlCopy&utm_medium=social&utm_campaign=sharing", 
    
}

def get_domain(url):
    parsed_url = urlparse(url)
    return parsed_url.netloc

def extract_article_text(url, selector):
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # 判断是否为 EUC-KR 页面（比如 soraknews.co.kr）
        domain = get_domain(url)
        if domain.endswith("soraknews.co.kr"):
            response.encoding = 'euc-kr'
            soup = BeautifulSoup(response.text, 'html.parser')  # 使用 .text 解码后的内容
        else:
            soup = BeautifulSoup(response.content, 'html.parser')

        element = soup.select_one(selector)
        if not element:
            return None
        
        # 删除脚本、广告等无关内容
        for tag in element.select(".btn_viewer, script, style, iframe, .sub_ad_banner10, .sub_ad_banner4"):
            tag.decompose()

        return element.get_text(separator="\n", strip=True) if element else None
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"

def main():
    os.makedirs("articles", exist_ok=True)
    for domain, selector in selector_map.items():
        url = example_urls.get(domain)
        if not url:
            print(f"No example URL for {domain}")
            continue

        print(f"Testing {domain}...")
        text = extract_article_text(url, selector)
        filename = os.path.join("articles", domain.replace('.', '_') + ".txt")

        with open(filename, "w", encoding="utf-8") as f:
            f.write(text if text else "No content extracted.")

if __name__ == "__main__":
    main()