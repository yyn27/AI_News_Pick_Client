# KoSBERT 相似度计算
# 速度大约 4250条每小时
import pandas as pd
import re
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import torch
from datetime import datetime

# ==========================
#  文本清洗函数
# ==========================
def clean_text(text, preserve_newline=False):
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
    if preserve_newline:
        # 保留换行，只合并多余空白
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)  # 连续3个以上换行变成2个
        return text.strip()
    else:
        return re.sub(r"\s+", " ", text).strip()

# ==========================
#  句子切分函数 (韩文)
# ==========================
def split_sentences_korean(text):
    # 简单按句号、问号、感叹号分句
    return [s.strip() for s in re.split(r"[.!?]\s*", text) if s.strip()]

# ==========================
#  加载 SBERT 模型
# ==========================
_sbert_model = None
def get_krsbert_model():
    global _sbert_model
    if _sbert_model is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        _sbert_model = SentenceTransformer("snunlp/KR-SBERT-V40K-klueNLI-augSTS", device=device)
        print(f"✅ KR-SBERT 模型加载完成 - device: {_sbert_model.device}")
    return _sbert_model

# ==========================
#  相似度计算函数
# ==========================
def calculate_copy_ratio(article, post, threshold=0.7):
    article = clean_text(article)
    post = clean_text(post)

    article_sents = split_sentences_korean(article)
    post_sents = split_sentences_korean(post)

    if not article_sents or not post_sents:
        return 0.0

    try:
        model = get_krsbert_model()
        art_vecs = model.encode(article_sents, batch_size=8, convert_to_numpy=True, show_progress_bar=False)
        post_vecs = model.encode(post_sents, batch_size=8, convert_to_numpy=True, show_progress_bar=False)

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

# ==========================
#  主程序
# ==========================
def main():
    input_file = r"D:\AI_News_Pick_Client\invalidUrlCheck\네이버 블로그_매칭 데이터_3월_중복 게시물 url 제게 후_공개게시글.xlsx"
    output_file = r"D:\AI_News_Pick_Client\simCalculating\원문포함_네이버 블로그_매칭 데이터_3월_중복 게시물 url 제게 후_공개게시글.xlsx"

    start_time = datetime.now()
    print(f"🕒 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

    # 读取 Excel
    df = pd.read_excel(input_file)

    total = len(df)
    results = []

    for idx, row in df.iterrows():
        sim = calculate_copy_ratio(str(row["원문내용"]), str(row["게시글내용"]))
        results.append(sim)
        print(f"progress: [{idx+1}/{total}] items completed", end="\r")

    df["KoSBERT"] = results

    # 保存结果
    df.to_excel(output_file, index=False)
    print(f"✅ result saved as {output_file}")

    end_time = datetime.now()
    duration = end_time - start_time
    print(f"\n🕒 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"⏱ 총 소요 시간: {duration}")

if __name__ == "__main__":
    main()
