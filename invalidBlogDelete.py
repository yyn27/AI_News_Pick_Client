import pandas as pd
import undetected_chromedriver as uc
import time
from selenium.common.exceptions import NoAlertPresentException, WebDriverException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from datetime import datetime

# === 1. 文件路径设置 ===
input_file = "D:\AI_News_Pick_Client\invalidUrlCheck\privateblog.xlsx"
output_valid = "D:\AI_News_Pick_Client\Blogvalid.xlsx"
output_deleted = "D:\AI_News_Pick_Client\삭제된_URL_로그.xlsx"

# === 记录起始时间 ===
start_time = datetime.now()

# === 2. 加载原始数据 ===
df = pd.read_excel(input_file)
valid_rows = []
deleted_rows = []

# === 3. 启动浏览器 ===
options = uc.ChromeOptions()
options.add_argument("--headless")  # 如需可视化运行可注释此行
options.add_argument("--no-sandbox")
options.add_argument("--disable-gpu")

# 禁用图像/CSS等资源
prefs = {
    "profile.managed_default_content_settings.images": 2,
    "profile.managed_default_content_settings.stylesheets": 2,
    "profile.managed_default_content_settings.cookies": 2,
    "profile.managed_default_content_settings.javascript": 1  # JS 保留检测 alert
}
options.add_experimental_option("prefs", prefs)

driver = uc.Chrome(options=options)

# === 4. 遍历每条 URL ===
for idx, row in df.iterrows():
    url = row['게시물 url']
    try:
        driver.get(url)

        # === 提前检查并处理 alert（防止 crash） ===
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text.strip()
            if any(msg in alert_text for msg in ["비공개 글 입니다", "삭제되었거나 다른 페이지로"]):
                print(f"[제외됨] ALERT: {alert_text} | {url}")
                alert.accept()
                deleted_rows.append(row)
                continue
            else:
                alert.accept()  # 非指定 alert 也关闭掉
        except NoAlertPresentException:
            pass

        # 智能等待页面加载（最大 5 秒）
        try:
            WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except TimeoutException:
            print(f"[제외됨] 페이지 로딩 실패 (timeout): {url}")
            deleted_rows.append(row)
            continue

        # === 页面正文判断 ===
        page_text = driver.page_source
        if "비공개 블로그입니다" in page_text:
            print(f"[제외됨] 비공개 블로그: {url}")
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

# === 7. 输出统计信息 ===
end_time = datetime.now()
duration = end_time - start_time
total = len(df)
kept = len(valid_rows)
deleted = len(deleted_rows)

# === 6. 保存结果文件 ===
pd.DataFrame(valid_rows).to_excel(output_valid, index=False)
pd.DataFrame(deleted_rows).to_excel(output_deleted, index=False)

print(f"\n✅ 완료! 결과 파일 저장됨:\n - 유효: {output_valid}\n - 삭제됨: {output_deleted}")
print(f" - 전체 URL 수: {total}")
print(f" - 유효 (보존): {kept}")
print(f" - 삭제됨: {deleted}")
print(f"\n🕒 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"\n🕒 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"⏱ 총 소요 시간: {str(duration)}")