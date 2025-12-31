import os
import time
import base64
import pandas as pd
import undetected_chromedriver as uc
from datetime import datetime
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# === 滚动函数 ===
def scroll_page(driver, step=500, pause=0.5):
    """模拟滚动页面，触发懒加载"""
    last_height = driver.execute_script("return document.body.scrollHeight")
    pos = 0
    while pos < last_height:
        pos += step
        driver.execute_script(f"window.scrollTo(0, {pos});")
        time.sleep(pause)
        last_height = driver.execute_script("return document.body.scrollHeight")

# === 开始计时 ===
start_dt = datetime.now()
print(f"程序开始运行... 🕒 {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")

# === 读取表格数据 ===
df = pd.read_excel(r"D:\AI_News_Pick_Client\네이버_1월_유사도_모니터링결과_비교.xlsx")
urls = df['게시물 url'].dropna().tolist()

# === 配置 undetected_chromedriver ===
options = uc.ChromeOptions()
# options.add_argument("--headless=new")  # 如果需要隐藏浏览器，可以解开注释
options.add_argument("--disable-gpu")
options.add_argument("--window-size=1920,1080")

driver = uc.Chrome(options=options)

# 避免 driver 卡死：设置页面加载超时
driver.set_page_load_timeout(25)

# === 保存截图的文件夹 ===
output_dir = r"D:\AI_News_Pick_Client\screenshots"
os.makedirs(output_dir, exist_ok=True)

for idx, url in enumerate(urls, start=1):
    try:
        try:
            driver.get(url)
        except Exception:
            driver.execute_script("window.stop();")

        # 等待正文元素出现（避免只截到空白）
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
        except:
            print(f"⚠️ 警告: {url} 页面可能没加载完整")

        # 滚动触发懒加载
        scroll_page(driver, step=500, pause=0.5)
        time.sleep(2)  # 额外等待，确保图片加载清晰

        # 用 CDP 截整页
        screenshot = driver.execute_cdp_cmd(
            "Page.captureScreenshot",
            {"captureBeyondViewport": True}
        )
        screenshot_data = screenshot.get("data", "")

        screenshot_path = os.path.join(output_dir, f"{idx}.png")
        with open(screenshot_path, "wb") as f:
            f.write(base64.b64decode(screenshot_data))

        print(f"✅ 已保存整页截图: {screenshot_path}")

    except Exception as e:
        print(f"❌ 抓取失败 {url}: {e}")
        driver.execute_script("window.stop();")
        continue

driver.quit()

# === 结束计时 ===
end_dt = datetime.now()
elapsed = (end_dt - start_dt).total_seconds()
minutes, seconds = divmod(elapsed, 60)

print(f"\n🕒 开始时间: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"🕒 结束时间: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"⏱ 总耗时: {int(minutes)} 分 {seconds:.1f} 秒")
