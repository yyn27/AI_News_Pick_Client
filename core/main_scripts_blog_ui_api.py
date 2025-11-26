# ✅ 수정된 core/main_scripts_blog_ui_api.py

import os
import re
import pandas as pd
from datetime import datetime
from concurrent.futures import ProcessPoolExecutor, as_completed
from core.core_utils_ui_api import (
    clean_text, extract_first_sentences, generate_search_queries,
    search_naver_news_api, calculate_copy_ratio, log, calculate_sequence_matcher_ratio,
    extract_urls_from_text, is_whitelisted_domain, is_trusted_oid, fallback_with_requests,
)

import sys
def resource_path(relative_path):
    """兼容PyInstaller和源码运行的资源路径"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

def find_original_article_api(index, row_dict, total_count, output_dir, stop_event_flag, client_id, client_secret):
    try:
        # 检查中断
        if stop_event_flag:
            log("🛑 사용자 중단 요청 감지, 작업 중단", index)
            # 最后一个返回值 delete_row_flag
            return index, "", 0.0, "", 0.0, "", "", False
        
        content_raw = str(row_dict.get("게시글내용", ""))
        # ① 提取用：保留换行
        content_for_extract = clean_text(content_raw, preserve_newline=True)

        # === A. 从博客正文提取 URL,作为候选源
        inpost_urls = extract_urls_from_text(content_raw)
        blog_candidates = []  # 可能有多条博客 URL 候选
        seen_blog_links = set()

        title = clean_text(str(row_dict.get("게시글제목", "")))
        content = clean_text(str(row_dict.get("게시글내용", "")))
        press = clean_text(str(row_dict.get("검색어", "")))

        # 先把查询语句准备好
        first, second, last = extract_first_sentences(content_for_extract)
        queries = generate_search_queries(title, first, second, last, press)
        log(f"🔍 검색어: {queries}", index)

        # === B. 对所有“可信 URL”逐个打分，作为博客候选加入 ===
        # 可信定义：白名单域名 或 Naver 信托 OID
        for blog_url in inpost_urls:
            if not (is_whitelisted_domain(blog_url) or is_trusted_oid(blog_url)):
                continue  # 野站：直接忽略，不建候选
            if blog_url in seen_blog_links:
                continue
            seen_blog_links.add(blog_url)

            body = fallback_with_requests(blog_url)
            if not body or len(body) <= 100:
                continue  # 内容过短/抓不到正文，就不当候选

            body_clean = clean_text(body, preserve_newline=True)
            seq_score = calculate_sequence_matcher_ratio(body_clean, content)
            tfidf_score = calculate_copy_ratio(body_clean, title + " " + content)

            blog_candidates.append({
                "title": "",
                "link": blog_url,
                "body": body_clean,
                "seq": seq_score,
                "tfidf": tfidf_score,
                "query_label": "blog_url",       # 标记为来自博客正文URL
                "query_text": blog_url,
            })
            log(f"🧷 블로그 URL 후보: {blog_url} (TF-IDF={tfidf_score:.3f}, Seq={seq_score:.3f})", index)
        # === B 结束 ===

        # 再检查中断
        if stop_event_flag:
            log("🛑 사용자 중단 요청 감지, 작업 중단", index)
            return index, "", 0.0, "", 0.0, "", "", False

        # C. Naver 뉴스 API 후보 수집 + 打分
        search_results = search_naver_news_api(queries, index, client_id, client_secret)

        # Naver 候选为空且没有任何博客候选 → 没找到可信原文，但不删行
        if not search_results and not blog_candidates:
            log("❌ 관련 뉴스 없음 (네이버/블로그 신뢰 후보 모두 없음)", index)
            return index, "", 0.0, "", 0.0, "", "", False
        
        if stop_event_flag:
            log("🛑 사용자 중단 요청 감지, 작업 중단", index)
            return index, "", 0.0, "", 0.0, "", "", False

        enriched = []
        for item in search_results:
            body = item["body"]
            tfidf_score = calculate_copy_ratio(body, title + " " + content)
            seq_score = calculate_sequence_matcher_ratio(body, content)
            enriched.append({
                "title": item.get("title", ""),
                "link": item.get("link", ""),
                "body": body,
                "seq": seq_score,
                "tfidf": tfidf_score,
                "query_label": item.get("query_label", ""),
                "query_text": item.get("query_text", ""),
            })

        # D. 合并 Naver 候选 + 所有博客 URL 候选
        pool = enriched.copy()
        pool.extend(blog_candidates)

        if not pool:
            log("❌ 후보 기사 없음 (후보 풀 비어 있음)", index)
            return index, "", 0.0, "", 0.0, "", "", False

        # E. 只在“可信候选”中选 best（信托 OID 或 白名单域名）
        trusted_only = [
            x for x in pool
            if is_trusted_oid(x["link"]) or is_whitelisted_domain(x["link"])
        ]

        # 连一个可信候选都没有,视作“没找到可信原文”，但不删这条博客
        if not trusted_only:
            log("⚠️ 공식 매체 후보 없음 (비공식 매체만 존재)", index)
            return index, "", 0.0, "", 0.0, "", "", False

        # 在可信候选里按 TF-IDF/Seq 排序，选最高的一条
        trusted_only.sort(key=lambda x: (x.get("tfidf", 0.0), x.get("seq", 0.0)), reverse=True)
        best = trusted_only[0]

        score = float(best.get("tfidf", 0.0))
        sequence_score = float(best.get("seq", 0.0))

        body_with_newline = best["body"]
        query_label = best.get("query_label", "")
        query_text  = best.get("query_text", "")

        if score >= 0.0:
            safe_title = re.sub(r'[\\/*?:"<>|]', '', title)[:50]
            filename = os.path.join(output_dir, f"{index+1:03d}_{safe_title}.txt")
            with open(filename, "w", encoding="utf-8", errors="replace") as f:
                f.write(f"[URL] {best['link']}\n\n{body_with_newline}")
            log(f"📝 저장 완료 → {filename} (복사율: {score}, 쿼리: {query_label})", index)
            return index, best["link"], score, body_with_newline, sequence_score, query_label, query_text, False
        else:
            log(f"⚠️ 복사율 낮음 (복사율: {score})", index)
            return index, "", 0.0, "", 0.0, "", "", False

    except Exception as e:
        log(f"❌ 에러 발생: {e}", index)
        return index, "", 0.0, "", 0.0, "", "", False
    
def clean_surrogates(val):
    """非法 surrogate 제거"""
    if isinstance(val, str):
        # U+D800 - U+DFFF 范围字符去掉
        return re.sub(r'[\ud800-\udfff]', '', val)
    return val

def main(input_path, output_path, client_id, client_secret, stop_event=None):
    output_dir = os.path.splitext(output_path)[0] + "_본문"
    os.makedirs(output_dir, exist_ok=True)

    df = pd.read_excel(input_path, dtype={"게시글 등록일자": str})
    total = len(df)
    log(f"📄 전체 게시글 수: {total}개")

    df["원문기사 url"] = ""
    df["복사율"] = 0.0
    df["원문내용"] = ""   # 新增列
    df["SequenceMatcher유사도"] = 0.0  # 新增列
    df["query"] = ""
    df["query_text"] = ""

    def get_stop_flag():
        return stop_event.is_set() if stop_event else False

    tasks = [(i, row.to_dict(), total, output_dir, get_stop_flag(), client_id, client_secret) for i, row in df.iterrows()]

    with ProcessPoolExecutor(max_workers=3) as executor:
        futures = [executor.submit(find_original_article_api, *args) for args in tasks]
        try:
            for future in as_completed(futures):
                if stop_event and stop_event.is_set():
                    log("🛑 사용자 중단 요청 감지, 작업 중단")
                    executor.shutdown(cancel_futures=True)
                    break
                try:
                    # === NEW: delete_row_flag 处理 ===
                    index, link, score, body, sequence_score, query_label, query_text, delete_row_flag = future.result()

                    if delete_row_flag:
                        if 0 <= index < len(df):
                            df.drop(index, inplace=True)
                        continue

                    df.at[index, "원문기사 url"] = link
                    df.at[index, "복사율"] = score
                    df.at[index, "원문내용"] = body  # 存储原文内容
                    df.at[index, "SequenceMatcher유사도"] = sequence_score  # 存储相似度
                    df.at[index, "query"] = query_label
                    df.at[index, "query_text"] = query_text
                except Exception as e:
                    log(f"❌ 결과 처리 오류: {e}")
        except Exception as e:
            log(f"❌ 프로세스 풀 에러: {e}")

    matched_count = df["복사율"].gt(0).sum()
    above_90_count = df["복사율"].ge(0.9).sum()
    above_50_count = df["복사율"].ge(0.5).sum() - above_90_count
    above_0_count = matched_count - above_90_count - above_50_count

    stats_rows = pd.DataFrame([
        {"순번": "매칭건수", "검색": f"{matched_count}건"},
        {"순번": "0.5 이상", "검색": f"{above_50_count}건"},
        {"순번": "0.9 이상", "검색": f"{above_90_count}건"},
        {"순번": "0 이상", "검색": f"{above_0_count}건"},
    ])
    df = pd.concat([df, stats_rows], ignore_index=True)

    # surrogate 문자 제거
    df = df.applymap(clean_surrogates)
    
    df.to_excel(output_path, index=False)

    log("📊 통계 요약")
    log(f" 매칭건수: {matched_count}건")
    log(f" 0.5 이상: {above_50_count}건")
    log(f" 0.9 이상: {above_90_count}건")
    log(f" 0 이상: {above_0_count}건")
    log(f"🎉 완료! 저장됨 → {output_path}")
    