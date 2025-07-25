import pandas as pd
import undetected_chromedriver as uc
import time
from selenium.common.exceptions import NoAlertPresentException, WebDriverException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from datetime import datetime
import concurrent.futures

# === 설정: 파일 경로 ===
input_file = r"D:\AI_News_Pick_Client\네이버 블로그_매칭 데이터_6월_중복 게시물 url 제게 후.xlsx"
output_valid = r"D:\AI_News_Pick_Client\invalidUrlCheck\Blogvalid.xlsx"
output_deleted = r"D:\AI_News_Pick_Client\invalidUrlCheck\삭제된_URL_로그.xlsx"

# === 시작 시간 기록 ===
start_time = datetime.now()

# === 데이터 불러오기 ===
df = pd.read_excel(input_file)
valid_rows = []
deleted_rows = []

# === page_source 제한시간 보호 함수 ===
def get_page_source_safe(driver, timeout=10):
    def inner():
        return driver.page_source
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(inner)
        try:
            return future.result(timeout=timeout)
        except concurrent.futures.TimeoutError:
            return None

# === Chrome 실행 함수 (옵션 포함) ===
def create_browser():
    options = uc.ChromeOptions()
    options.add_argument("--headless")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    prefs = {
        "profile.managed_default_content_settings.images": 2,
        "profile.managed_default_content_settings.stylesheets": 2,
        "profile.managed_default_content_settings.cookies": 2,
        "profile.managed_default_content_settings.javascript": 1
    }
    options.add_experimental_option("prefs", prefs)
    return uc.Chrome(options=options)

# === 시작 브라우저 생성 ===
driver = create_browser()

# === 메인 처리 루프 ===
for idx, row in df.iterrows():
    url = row['게시물 url']

    # === 1000개마다 브라우저 재시작 ===
    if idx > 0 and idx % 1000 == 0:
        print(f"\n🔄 [재시작] {idx}번째 항목에서 브라우저 재시작 중...\n")
        driver.quit()
        time.sleep(5)
        driver = create_browser()

    try:
        driver.set_page_load_timeout(15)
        driver.get(url)

        # === alert 우선 처리 ===
        try:
            alert = driver.switch_to.alert
            alert_text = alert.text.strip()
            if any(msg in alert_text for msg in ["비공개 글 입니다", "삭제되었거나 다른 페이지로"]):
                print(f"[{idx}][제외됨] ALERT: {alert_text} | {url}")
                alert.accept()
                deleted_rows.append(row)
                continue
            else:
                alert.accept()
        except Exception:
            pass

        # === 페이지 로딩 대기 (최대 5초) ===
        try:
            WebDriverWait(driver, 5).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        except TimeoutException:
            print(f"[{idx}][경고] 로딩 지연 (timeout), 보류: {url}")
            valid_rows.append(row)
            continue

        # === page_source 보호 호출 ===
        page_text = get_page_source_safe(driver, timeout=10)
        if page_text is None:
            print(f"[{idx}][경고] page_source 타임아웃 (10초), 보류: {url}")
            valid_rows.append(row)
            continue

        if "비공개 블로그입니다" in page_text:
            print(f"[{idx}][제외됨] 비공개 블로그 본문: {url}")
            deleted_rows.append(row)
            continue

        # === 정상 페이지 ===
        print(f"[{idx}][유지됨] 공개 블로그: {url}")
        valid_rows.append(row)

    except Exception as e:
        print(f"[{idx}][오류] 알 수 없는 예외, 보류: {url} - {e}")
        valid_rows.append(row)
        continue

# === 브라우저 종료 ===
driver.quit()

# === 통계 출력 ===
end_time = datetime.now()
duration = end_time - start_time
total = len(df)
kept = len(valid_rows)
deleted = len(deleted_rows)

# === 파일 저장 ===
pd.DataFrame(valid_rows).to_excel(output_valid, index=False)
pd.DataFrame(deleted_rows).to_excel(output_deleted, index=False)

print(f"\n✅ 완료! 결과 파일 저장됨:\n - 유효: {output_valid}\n - 삭제됨: {output_deleted}")
print(f" - 전체 URL 수: {total}")
print(f" - 유효 (보존): {kept}")
print(f" - 삭제됨: {deleted}")
print(f"\n🕒 시작 시간: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"🕒 종료 시간: {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
print(f"⏱ 총 소요 시간: {str(duration)}")