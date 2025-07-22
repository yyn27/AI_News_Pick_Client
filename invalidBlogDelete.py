import pandas as pd
import undetected_chromedriver as uc
import time
from selenium.common.exceptions import NoAlertPresentException, WebDriverException

# === 1. 文件路径设置 ===
input_file = "D:\AI_News_Pick_Client\privateblog.xlsx"
output_valid = "D:\AI_News_Pick_Client\Blogvalid.xlsx"
output_deleted = "D:\AI_News_Pick_Client\삭제된_URL_로그.xlsx"

# === 2. 加载原始数据 ===
df = pd.read_excel(input_file)
valid_rows = []
deleted_rows = []

# === 3. 启动浏览器 ===
options = uc.ChromeOptions()
options.add_argument("--headless")  # 如需可视化运行可注释此行
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")

driver = uc.Chrome(options=options)

# === 4. 遍历每条 URL ===
for idx, row in df.iterrows():
    url = row['게시물 url']
    try:
        driver.get(url)
        time.sleep(2.5)  # 等待加载

        # === 弹窗判断 ===
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text.strip()
            if any(msg in alert_text for msg in ["비공개 글 입니다", "삭제되었거나 다른 페이지로"]):
                print(f"[제외됨] ALERT: {alert_text} | {url}")
                alert.accept()
                deleted_rows.append(row)
                continue
        except NoAlertPresentException:
            pass

        # === 页面正文判断 ===
        page_text = driver.page_source
        if "비공개 블로그입니다" in page_text:
            print(f"[제외됨] 비공개 본문: {url}")
            deleted_rows.append(row)
            continue

        # === 保留有效行 ===
        print(f"[유지됨] 공개 블로그: {url}")
        valid_rows.append(row)

    except WebDriverException as e:
        print(f"[오류] {url} - {e}")
        deleted_rows.append(row)

# === 5. 关闭浏览器 ===
driver.quit()

# === 6. 保存结果文件 ===
pd.DataFrame(valid_rows).to_excel(output_valid, index=False)
pd.DataFrame(deleted_rows).to_excel(output_deleted, index=False)

print(f"\n✅ 완료! 결과 파일 저장됨:\n - 유효: {output_valid}\n - 삭제됨: {output_deleted}")
